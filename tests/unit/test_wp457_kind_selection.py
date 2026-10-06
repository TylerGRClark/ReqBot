"""WP-45.7d: the kind-selection resolver: code sets the strength from the modal word (offline; no LLM, no corpus)."""

import importlib.util
import itertools
import json
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"
_ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    for p in (str(_DIR), str(_ROOT), str(_ROOT / "eval/spike_results/wp_45_audit")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"wp457d_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457d_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def K():
    return _load("kind_selection")


@pytest.fixture(scope="module")
def C():
    return _load("check_resolution")


@pytest.fixture(scope="module")
def RS():
    return _load("run_selection")


@pytest.fixture(scope="module")
def SC():
    return _load("score_resolver")


def _spans(quote):
    return [{"id": "E1", "kind": "candidate", "label": "candidate quote", "text": quote, "source": "", "unverified": False}]


def _entry(i, kind, text):
    return {"id": f"M{i}", "kind": kind, "source": "", "text": text}


def _run(K, C, kind, quote, menu, actor="none", parent="none"):
    answer, spans, info = K.assemble({"kind": kind, "actor": actor, "parent": parent}, menu, _spans(quote), quote)
    errors = [i for i in C.check(answer, spans) if i.severity == "error"]
    return answer, info, errors


def test_the_schema_has_no_strength_and_the_prompt_does_not_ask_for_one(K):
    schema = K.json_schema([_entry(1, "heading", "H")])
    assert list(schema["properties"]) == ["kind", "actor", "parent"]
    assert schema["properties"]["kind"]["enum"] == ["requirement", "scope_or_context", "not_a_requirement", "unresolved"]
    assert schema["properties"]["actor"]["enum"] == ["M1", "none"]
    assert "You do not say how strong a requirement is" in K.INSTRUCTIONS
    assert '"status"' not in K.INSTRUCTIONS and '"kind"' in K.INSTRUCTIONS
    for ex in K.EXAMPLES:
        assert set(ex["answer"]) == {"kind", "actor", "parent"} and ex["answer"]["kind"] in K.KINDS


def test_every_example_assembles_to_the_strength_the_status_design_gave_it_and_passes_the_checker(K, C):
    """The kind form of each example must produce exactly the old example's status, with no checker error."""
    for ex in K.EXAMPLES:
        menu = K.S._example_menu(ex)
        answer, spans, info = K.assemble(ex["answer"], menu, K.example_bundle(ex).to_dict()["spans"], ex["quote"])
        assert answer["status"]["value"] == ex["status"], ex["title"]
        assert not [i for i in C.check(answer, spans) if i.severity == "error"], ex["title"]


def test_the_governing_modal_is_read_from_the_quote_first(K, C):
    menu = [_entry(1, "lead_in", "All staff must:")]
    answer, info, errors = _run(K, C, "requirement", "The Auditor Should review logs.", menu)
    assert answer["status"]["value"] == "recommendation" and answer["modality"]["verbatim"] == "Should" and info["modal_source"] == "quote"
    assert not errors


def test_the_chosen_parent_is_the_second_source(K, C):
    menu = [_entry(1, "lead_in", "The Records Officer will:"), _entry(2, "lead_in", "The Records Officer")]
    answer, info, errors = _run(K, C, "requirement", "(2) Report findings.", menu, actor="M2", parent="M1")
    assert answer["status"]["value"] == "obligation" and info["modal_source"] == "parent" and answer["modality"]["verbatim"] == "will"
    assert not errors


def test_with_no_parent_the_menu_lead_in_supplies_the_modal_and_the_actor_is_never_read(K, C):
    """The R2 8B case of #231: subject chosen, parent left empty, the lead-in on the menu says "should"."""
    menu = [_entry(1, "heading", "ROLES"), _entry(2, "lead_in", "All Service component organizations should:"), _entry(3, "lead_in", "All Service component organizations")]
    answer, info, errors = _run(K, C, "requirement", "Ensure their facilities perform control.", menu, actor="M3")
    assert answer["status"]["value"] == "recommendation" and info["modal_source"] == "menu lead-in"
    assert answer["modality"]["verbatim"] == "should" and answer["actor"]["value"] == "All Service component organizations"
    assert not errors
    # the actor is not a source: a lead-in picked as the actor with no parent cannot lend its modal when the colon lead-in is absent
    only_actor = [_entry(1, "stem", "Organizations should")]
    answer, info, errors = _run(K, C, "requirement", "(1) Encrypt backups.", only_actor, actor="M1")
    assert info["modal_source"] == "none" and answer["status"]["value"] == "obligation"
    assert {e.code for e in errors} == {"modal_in_evidence"}  # still surfaced as the non-gated malformed choice


def test_a_chosen_parent_without_a_modal_ends_the_search(K, C):
    """Nothing is inferred over the model's choice: a heading chosen as parent means no lead-in is read."""
    menu = [_entry(1, "heading", "ROLES"), _entry(2, "lead_in", "All staff should:")]
    answer, info, errors = _run(K, C, "requirement", "(1) Encrypt backups.", menu, parent="M1")
    assert info["modal_source"] == "none" and answer["status"]["value"] == "obligation" and answer["modality"]["class"] == "none"
    assert not errors


def test_a_lowercase_continuation_reads_the_preceding_clause_and_an_uppercase_quote_does_not(K, C):
    """The R052 case: "ensure that policies are updated ..." continues "Organizations should also be aware ... and"."""
    menu = [_entry(1, "heading", "5.1 Initiation"), _entry(2, "preceding", "Organizations should also be aware of new types of solutions and"),
            _entry(3, "preceding", "Organizations")]
    answer, info, errors = _run(K, C, "requirement", "ensure that policies are updated accordingly as needed.", menu, actor="M3")
    assert answer["status"]["value"] == "recommendation" and info["modal_source"] == "preceding clause" and not errors
    answer, info, errors = _run(K, C, "requirement", "Ensure that policies are updated accordingly as needed.", menu, actor="M3")
    assert info["modal_source"] == "none" and answer["status"]["value"] == "obligation"  # a new sentence is not a continuation
    # a continuation whose preceding entries have no modal falls through to none
    plain = [_entry(1, "preceding", "2.1.5.2."), _entry(2, "preceding", "Some earlier words and")]
    assert _run(K, C, "requirement", "ensure access.", plain)[1]["modal_source"] == "none"


def test_the_colon_lead_in_comes_before_the_preceding_clause(K, C):
    menu = [_entry(1, "lead_in", "Staff will:"), _entry(2, "preceding", "Staff should also and")]
    answer, info, _ = _run(K, C, "requirement", "ensure access.", menu)
    assert info["modal_source"] == "menu lead-in" and answer["status"]["value"] == "obligation"
    no_modal_lead = [_entry(1, "lead_in", "Responsibilities include:"), _entry(2, "preceding", "Staff should also and")]
    answer, info, _ = _run(K, C, "requirement", "ensure access.", no_modal_lead)
    assert info["modal_source"] == "preceding clause" and answer["status"]["value"] == "recommendation"


def test_a_quote_with_several_modals_uses_the_first_and_keeps_all(K, C):
    """Card R081 of #231: an obligation and a prohibition in one sentence."""
    quote = "The community strings shall be modified from default settings - default 'public' and 'private' strings shall not be utilized."
    answer, info, errors = _run(K, C, "requirement", quote, [])
    assert answer["status"]["value"] == "obligation" and answer["modality"]["verbatim"] == "shall" and not errors
    assert info["all_modals"] == [{"phrase": "shall", "class": "obligation"}, {"phrase": "shall not", "class": "prohibition"}]


def test_a_modal_free_hint_and_a_modal_free_item_are_kept_with_the_right_default(K, C):
    answer, info, errors = _run(K, C, "requirement", "Consider using introspection capabilities to monitor activity.", [])
    assert answer["status"]["value"] == "recommendation" and answer["modality"]["verbatim"] == "Consider" and not errors
    answer, info, errors = _run(K, C, "requirement", "Procedures for revising the plan.", [])
    assert answer["status"]["value"] == "obligation" and answer["modality"] == {"verbatim": None, "class": "none", "evidence": []}
    assert info["modal_source"] == "none" and info["all_modals"] == [] and not errors


def test_the_other_kinds_set_their_own_status_and_read_no_modal(K, C):
    for kind in ("scope_or_context", "not_a_requirement", "unresolved"):
        answer, info, errors = _run(K, C, kind, "The system may be configured by the vendor.", [])
        assert answer["status"]["value"] == kind and answer["modality"]["verbatim"] is None and info["modal_source"] == "none"
        assert not errors


def test_no_choice_the_model_can_make_produces_a_gated_error(K, C):
    """The point of the design: whatever kind, actor and parent the model picks, the strength cannot contradict the modal and no party is
    invented, so the gated modality codes and the added-token code never appear."""
    gated = set(C.MODALITY_ERROR_CODES) | {"added_token", "not_in_cited_span", "uncited_value"}
    quotes = ["The Auditor shall review logs.", "(1) Report findings.", "ensure that policies are updated.", "Consider using TLS.",
              "Users shall not share passwords and may not reuse them.", "Procedures for revising the plan.", "The system can run."]
    menu = [_entry(1, "heading", "ROLES"), _entry(2, "lead_in", "The Officer will:"), _entry(3, "lead_in", "The Officer"),
            _entry(4, "preceding", "Staff should also and"), _entry(5, "stem", "Staff may"), _entry(6, "subject", "The Auditor")]
    ids = [m["id"] for m in menu] + ["none"]
    for quote, kind, actor, parent in itertools.product(quotes, K.KINDS, ids, ids):
        answer, info, errors = _run(K, C, kind, quote, menu, actor, parent)
        assert not [e for e in errors if e.code in gated], (quote, kind, actor, parent, [e.code for e in errors])


def test_assemble_rejects_what_the_schema_makes_impossible_and_does_not_mutate(K):
    quote = "The Auditor shall act."
    for bad in ({"kind": "obligation", "actor": "none", "parent": "none"}, {"kind": "requirement", "actor": "M9", "parent": "none"},
                {"kind": "requirement", "actor": "none"}):
        with pytest.raises(ValueError):
            K.assemble(bad, [], _spans(quote), quote)
    spans = _spans(quote)
    before = [dict(s) for s in spans]
    K.assemble({"kind": "requirement", "actor": "M1", "parent": "none"}, [_entry(1, "subject", "The Auditor")], spans, quote)
    assert spans == before


def test_prompt_hash_differs_from_the_status_design_and_fits_the_window(K):
    assert K.prompt_hash() != K.S.prompt_hash() and K.fixed_tokens() < 3500
    assert K.prompt_hash() == K.prompt_hash()


def test_the_runner_stores_the_modal_source_and_summarizes_the_sources(RS, tmp_path, monkeypatch):
    chunks = {2: {"chunk_id": 2, "raw_text": "The Records Officer will: (1) Review logs monthly. (2) Report findings to the Director.",
                  "parent_header_text": "2.3. RECORDS OFFICER", "section_title_path": ["PART 1", "2.3. RECORDS OFFICER"]}}
    docs = {"DOC": (chunks, {})}
    cands = [{"candidate_id": "audit:A1", "document": "DOC", "chunk_id": 2, "quote": "(2) Report findings to the Director."},
             {"candidate_id": "audit:A2", "document": "DOC", "chunk_id": 2, "quote": "(1) Review logs monthly."}]

    def gen(prompt, model, url, **kw):
        assert kw["schema"]["properties"].keys() == {"kind", "actor", "parent"}
        return json.dumps({"kind": "requirement", "actor": "none", "parent": "none"}), {
            "done_reason": "stop", "prompt_eval_count": 900, "eval_count": 20, "total_duration": 1, "load_duration": 0, "wall_seconds": 0.4}

    monkeypatch.setattr(RS.OR, "generate", gen)
    ledger = RS.OR.Ledger(tmp_path / "k.jsonl")
    n = RS.run_candidates(cands, docs, tier="R2", model="m", digest="dg", run_label="k", ledger=ledger, ollama_url="http://x",
                          log=lambda *a: None, design=RS.K)
    assert n == 2
    recs = {r["candidate_id"]: r for r in ledger.records.values()}
    assert recs["audit:A1"]["prompt_hash"] == RS.K.prompt_hash() and recs["audit:A1"]["kind"] == "selection"
    assert recs["audit:A1"]["modal_source"] == "menu lead-in" and recs["audit:A1"]["answer"]["status"]["value"] == "obligation"
    summary = RS.summarize(ledger, RS.K)
    assert summary["modal_sources"] == {"menu lead-in": 2} and summary["inferred_source_candidates"] == ["audit:A1", "audit:A2"]
    assert summary["multi_modal_candidates"] == [] and summary["fixed_prompt_estimated_tokens"] == RS.K.fixed_tokens()
    report = RS.dry_run_report(cands, docs, "R2", design=RS.K)
    assert report["prompt_hash"] == RS.K.prompt_hash() and report["untreatable"] == 0


def test_the_v5_registry_scores_with_the_v4_bar(SC):
    assert SC.REGISTRIES["v5"] == SC.REGISTRIES["v4"] == {"r1_8b", "r1_14b", "r2_8b", "r2_14b"}
    base = {"right": 19, "misleading": 19, "incomplete": 17}
    sel = {"all": {"candidates": 40, "valid": 40, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                   "attachment": {}, "invented_answers": 0, "modality_error_answers": 0},
           "audit": {"attachment": {"right": 30, "misleading": 21, "incomplete": 4}, "baseline_attachment": base}}
    runs = {k: {"selection": sel} for k in SC.REGISTRIES["v5"]}
    report = SC.choose_report(runs, "v5")
    assert report["chosen"]["passes_every_gate"] and "attachment_gain_over_production" in report["configs"]["r1_8b"]["gates"]
