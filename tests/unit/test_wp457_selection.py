"""WP-45.7b: the selection resolver's schema, prompt, examples and assembler (offline; no LLM, no corpus)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"


def _load(name):
    for p in (str(_DIR), str(_DIR.parents[2])):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"wp457b_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457b_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def S():
    return _load("selection")


@pytest.fixture(scope="module")
def C():
    return _load("check_resolution")


def _spans(quote, *extra):
    spans = [{"id": "E1", "kind": "candidate", "label": "candidate quote", "text": quote, "source": "", "unverified": False}]
    for i, text in enumerate(extra, 2):
        spans.append({"id": f"E{i}", "kind": "chunk", "label": "same chunk", "text": text, "source": "", "unverified": False})
    return spans


def _menu(*texts):
    return [{"id": f"M{i}", "kind": "heading", "source": "", "text": t} for i, t in enumerate(texts, 1)]


def test_schema_allows_only_the_status_enum_and_this_menus_ids(S):
    schema = S.json_schema(_menu("A", "B"))
    assert list(schema["properties"]) == ["status", "actor", "parent"] and schema["required"] == ["status", "actor", "parent"]
    assert schema["properties"]["actor"]["enum"] == ["M1", "M2", "none"] == schema["properties"]["parent"]["enum"]
    assert "not_a_requirement" in schema["properties"]["status"]["enum"]
    assert S.json_schema([])["properties"]["actor"]["enum"] == ["none"]  # an empty menu leaves only "none"


def test_every_example_is_a_valid_answer_that_the_unchanged_checker_accepts(S, C):
    for n, ex in enumerate(S.EXAMPLES, 1):
        menu = S._example_menu(ex)
        schema = S.json_schema(menu)
        assert ex["answer"]["actor"] in schema["properties"]["actor"]["enum"], n
        assert ex["answer"]["parent"] in schema["properties"]["parent"]["enum"], n
        bundle = S.example_bundle(ex)
        answer, spans = S.assemble(ex["answer"], menu, bundle.to_dict()["spans"], ex["quote"])
        errors = [i for i in C.check(answer, spans) if i.severity == "error"]
        assert not errors, (n, ex["title"], errors)


def test_examples_cover_the_choices_the_model_must_make(S):
    answers = [ex["answer"] for ex in S.EXAMPLES]
    assert {a["status"] for a in answers} >= {"obligation", "recommendation", "not_a_requirement", "scope_or_context"}
    assert any(a["parent"] != "none" for a in answers) and any(a["parent"] == "none" and a["actor"] != "none" for a in answers)
    assert any(a["actor"] == "none" and a["parent"] == "none" for a in answers)


def test_assemble_builds_the_resolver_shape_with_verbatim_actor_and_parent(S):
    quote = "(2) Report findings to the Director."
    menu = _menu("RECORDS OFFICER", "The Records Officer will:", "The Records Officer")
    answer, spans = S.assemble({"status": "obligation", "actor": "M3", "parent": "M2"}, menu, _spans(quote, "The Records Officer will: " + quote), quote)
    assert list(answer) == list(S.R.ORDER)
    assert answer["actor"]["value"] == "The Records Officer" and answer["parent"]["value"] == "The Records Officer will:"
    by_id = {s["id"]: s for s in spans}
    assert by_id[answer["actor"]["evidence"][0]]["text"] == "The Records Officer"  # an exact-text span, not the big chunk
    assert by_id[answer["parent"]["evidence"][0]]["text"] == "The Records Officer will:"
    assert answer["modality"] == {"verbatim": "will", "class": "obligation", "evidence": [answer["parent"]["evidence"][0]]}
    for name in ("action", "target", "applicability", "timing", "standalone_statement", "plain_language", "unresolved_reason"):
        assert answer[name] == {"value": None, "evidence": []}
    assert answer["conditions"] == [] and answer["exceptions"] == [] and answer["logic"] == {"value": "none", "evidence": []}


def test_none_choices_attach_nothing_and_an_existing_exact_span_is_reused(S):
    quote = "The Auditor shall review logs."
    answer, spans = S.assemble({"status": "obligation", "actor": "none", "parent": "none"}, _menu("The Auditor"), _spans(quote), quote)
    assert answer["actor"] == {"value": None, "evidence": []} == answer["parent"]
    assert answer["modality"] == {"verbatim": "shall", "class": "obligation", "evidence": ["E1"]}
    assert len(spans) == 1  # nothing was added
    answer, spans = S.assemble({"status": "obligation", "actor": "M1", "parent": "none"}, _menu(quote), _spans(quote), quote)
    assert answer["actor"]["evidence"] == ["E1"] and len(spans) == 1  # the quote itself is already an exact span


def test_modality_is_read_by_code_from_the_quote_before_the_chosen_spans(S):
    quote = "The Auditor Should review logs."
    answer, _ = S.assemble({"status": "recommendation", "actor": "none", "parent": "M1"}, _menu("All staff must:"), _spans(quote), quote)
    assert answer["modality"]["verbatim"] == "Should" and answer["modality"]["class"] == "recommendation"  # surface text, quote first
    quote = "Disable unused services."
    answer, _ = S.assemble({"status": "obligation", "actor": "none", "parent": "none"}, [], _spans(quote), quote)
    assert answer["modality"] == {"verbatim": None, "class": "none", "evidence": []}  # an imperative: no modal, class none
    quote = "The system can run."
    answer, _ = S.assemble({"status": "not_a_requirement", "actor": "none", "parent": "none"}, [], _spans(quote), quote)
    assert answer["modality"]["verbatim"] is None  # "can" is not read as a modal


def test_a_status_that_contradicts_the_quotes_own_modal_is_still_the_models_error(S, C):
    """The review finding on the plan: the modality gate stays model-dependent through the status."""
    quote = "Organizations should test restores."
    answer, spans = S.assemble({"status": "obligation", "actor": "none", "parent": "none"}, [], _spans(quote), quote)
    codes = {i.code for i in C.check(answer, spans) if i.severity == "error"}
    assert codes == {"modality_strengthened"}
    good, spans = S.assemble({"status": "recommendation", "actor": "none", "parent": "none"}, [], _spans(quote), quote)
    assert not [i for i in C.check(good, spans) if i.severity == "error"]
    bare, spans = S.assemble({"status": "recommendation", "actor": "none", "parent": "none"}, [], _spans("Disable services."), "Disable services.")
    assert {i.code for i in C.check(bare, spans) if i.severity == "error"} == {"modality_class"}  # a recommendation needs a modal


def test_assemble_rejects_what_the_schema_should_have_made_impossible(S):
    quote = "The Auditor shall act."
    with pytest.raises(ValueError):
        S.assemble({"status": "mandatory", "actor": "none", "parent": "none"}, [], _spans(quote), quote)
    with pytest.raises(ValueError):
        S.assemble({"status": "obligation", "actor": "M9", "parent": "none"}, _menu("A"), _spans(quote), quote)
    with pytest.raises(ValueError):
        S.assemble({"status": "obligation", "actor": "none"}, [], _spans(quote), quote)


def test_assemble_does_not_mutate_its_inputs(S):
    quote = "(1) Report."
    spans = _spans(quote, "The Officer will: (1) Report.")
    before = [dict(s) for s in spans]
    S.assemble({"status": "obligation", "actor": "none", "parent": "M1"}, _menu("The Officer will:"), spans, quote)
    assert spans == before


def test_prompt_pieces(S):
    assert S.render_menu([]).startswith("Menu (choose by id): empty")
    text = S.render_menu([{"id": "M1", "kind": "stem", "text": "In this case,"}, {"id": "M2", "kind": "heading", "text": "4.4 X"}])
    assert "M1 [stem, found by rule] In this case," in text and "M2 [heading] 4.4 X" in text
    bundle = S.example_bundle(S.EXAMPLES[0])
    prompt = S.render_prompt(bundle, S._example_menu(S.EXAMPLES[0]))
    assert prompt.startswith(S.INSTRUCTIONS) and prompt.rstrip().endswith("Answer:") and "Menu (choose by id):" in prompt
    assert S.fixed_tokens() < 3500  # the fixed part leaves most of the window to the evidence (the resolver's was ~4,500)


def test_prompt_hash_tracks_the_instructions_and_the_menu_hash_the_menu(S, monkeypatch):
    before = S.prompt_hash()
    assert before == S.prompt_hash()
    monkeypatch.setattr(S, "INSTRUCTIONS", S.INSTRUCTIONS + " Extra.")
    assert S.prompt_hash() != before
    assert S.menu_hash(_menu("A")) != S.menu_hash(_menu("B")) and S.menu_hash(_menu("A")) == S.menu_hash(_menu("A"))
