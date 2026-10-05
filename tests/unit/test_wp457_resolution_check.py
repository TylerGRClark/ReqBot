"""WP-45.7: the resolver schema, prompt, worked examples and the answer checker (offline; no LLM)."""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"


def _load(name):
    sys.path.insert(0, str(_DIR))
    try:
        spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_DIR))


@pytest.fixture(scope="module")
def R():
    _load("bundle")
    return _load("resolver")


@pytest.fixture(scope="module")
def C(R):
    return _load("check_resolution")


def _spans(*texts, unverified=()):
    return [{"id": f"E{i}", "kind": "x", "label": "x", "text": t, "unverified": i in unverified} for i, t in enumerate(texts, 1)]


def _base(R, **over):
    """A minimal valid answer for 'Administrators should rotate keys.' that the tests then perturb."""
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a.update(over)
    return a


def codes(issues, severity="error"):
    return [(i.code, i.field) for i in issues if i.severity == severity]


# ---- schema, prompt and examples ---------------------------------------------------------------------------------------


def test_every_worked_example_passes_the_checker_against_its_own_bundle(R, C):
    for ex in R.EXAMPLES:
        spans = R.example_bundle(ex).to_dict()["spans"]
        assert C.check(ex["answer"], spans) == [], ex["title"]


def test_the_examples_in_the_prompt_are_strictly_valid_json_with_no_placeholder_unions(R):
    text = R.render_examples()
    answers = re.findall(r"^Answer: (\{.*\})$", text, flags=re.M)
    assert len(answers) == len(R.EXAMPLES)
    for raw, ex in zip(answers, R.EXAMPLES):
        assert json.loads(raw) == ex["answer"]
    assert " | " not in R.render_prompt(R.example_bundle(R.EXAMPLES[0]))
    assert "//" not in text  # no comments inside the JSON the model is shown


def test_the_schema_enforces_the_enums_and_accepts_the_examples(R):
    jsonschema = pytest.importorskip("jsonschema")
    schema = R.json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    for ex in R.EXAMPLES:
        jsonschema.validate(ex["answer"], schema)
    assert schema["properties"]["status"]["properties"]["value"]["enum"] == list(R.STATUS)
    assert schema["properties"]["modality"]["properties"]["class"]["enum"] == list(R.CLASS)
    assert schema["properties"]["logic"]["properties"]["value"]["enum"] == list(R.LOGIC)
    bad = copy.deepcopy(R.EXAMPLES[0]["answer"])
    bad["status"]["value"] = "mandatory"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_the_fixed_prompt_fits_beside_the_bundle_budget_and_the_hash_is_stable(R):
    B = sys.modules["bundle"]
    tokens = R.fixed_tokens()
    assert 1000 < tokens < 4000
    assert tokens + B.BUNDLE_TOKEN_CAP + B.ANSWER_RESERVE_TOKENS < B.NUM_CTX  # instructions + full bundle + answer fit the window
    assert R.prompt_hash() == R.prompt_hash() and len(R.prompt_hash()) == 16
    assert B.preflight(tokens, 500)


# ---- modality table ----------------------------------------------------------------------------------------------------


def test_the_modal_phrase_table_maps_to_the_four_classes(C):
    for phrase, cls in (
        ("shall", "obligation"), ("is required to", "obligation"), ("will", "obligation"), ("has to", "obligation"),
        ("should", "recommendation"), ("should not", "recommendation"), ("ought not", "recommendation"),
        ("may", "permission"), ("is authorized to", "permission"), ("can", "permission"),
        ("shall not", "prohibition"), ("must not", "prohibition"), ("may not", "prohibition"), ("is prohibited from", "prohibition"),
    ):
        assert C.phrase_class(phrase) == cls, phrase
    assert C.phrase_class("shall be") == "obligation"  # a phrase may continue past the table entry
    assert C.phrase_class("kind of requires") is None


def test_modals_in_text_takes_the_longest_phrase_without_overlap(C):
    assert C.modals_in("Users shall not share accounts; admins should rotate keys and may grant waivers.") == [
        ("shall not", "prohibition"), ("should", "recommendation"), ("may", "permission")
    ]
    assert C.modals_in("Nothing here.") == []


# ---- extractive fields -------------------------------------------------------------------------------------------------


def test_an_extractive_value_must_be_in_a_cited_span_after_normalization(R, C):
    spans = _spans("Administrators  should not\nreuse passwords.")  # raw spacing and a line break
    assert codes(C.check(_base(R), spans)) == []
    a = _base(R)
    a["actor"] = {"value": "Operators", "evidence": ["E1"]}
    assert ("not_in_cited_span", "actor") in codes(C.check(a, spans))
    a["actor"] = {"value": "Administrators", "evidence": []}
    assert ("uncited_value", "actor") in codes(C.check(a, spans))
    a["actor"] = {"value": "Administrators", "evidence": ["E9"]}
    assert ("bad_evidence_id", "actor") in codes(C.check(a, spans))


def test_soft_hyphenated_spans_do_not_cause_a_false_failure(R, C):
    spans = _spans("Administrators should not reuse pass-\nwords.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["target"] = {"value": "passwords", "evidence": ["E1"]}
    assert ("not_in_cited_span", "target") not in codes(C.check(a, spans))


# ---- modality and status -----------------------------------------------------------------------------------------------


def test_should_cannot_become_an_obligation_in_the_class_or_the_status(R, C):
    spans = _spans("Administrators should not reuse passwords.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["modality"]["class"] = "obligation"  # phrase "should not" is a recommendation
    assert ("modality_strengthened", "modality") in codes(C.check(a, spans))
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["status"]["value"] = "obligation"  # class recommendation, status obligation
    assert ("modality_strengthened", "status") in codes(C.check(a, spans))
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["status"]["value"] = "prohibition"  # a negative recommendation is not a prohibition
    assert ("modality_strengthened", "status") in codes(C.check(a, spans))


def test_may_cannot_become_shall_in_a_generated_sentence(R, C):
    spans = _spans("The Authorizing Official may grant a waiver for up to six months.")
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["standalone_statement"]["value"] = "The Authorizing Official shall grant a waiver for up to six months."
    assert ("modality_strengthened", "standalone_statement") in codes(C.check(a, spans))
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["plain_language"]["value"] = "The Authorizing Official must give a waiver that lasts up to six months."
    assert ("modality_strengthened", "plain_language") in codes(C.check(a, spans))


def test_a_null_phrase_needs_class_none_and_an_imperative_may_not_gain_a_modal(R, C):
    spans = _spans("Disable unused services.")
    a = copy.deepcopy(R.EXAMPLES[4]["answer"])  # unresolved example, null phrase, class none
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["action"] = {"value": "Disable unused services", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": "Unused services must be disabled.", "evidence": ["E1"]}
    assert ("modality_added", "standalone_statement") in codes(C.check(a, spans))
    a["standalone_statement"] = {"value": "Disable unused services.", "evidence": ["E1"]}
    assert codes(C.check(a, spans)) == []
    a["modality"]["class"] = "obligation"
    assert ("modality_class", "modality") in codes(C.check(a, spans))


def test_a_modal_in_the_evidence_is_an_error_for_requirements_but_fine_for_non_requirements(R, C):
    spans = _spans("The hypervisor can pause a guest OS.")
    a = copy.deepcopy(R.EXAMPLES[5]["answer"])  # scope_or_context, null modality
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["applicability"] = {"value": None, "evidence": []}
    a["actor"] = {"value": "The hypervisor", "evidence": ["E1"]}
    assert ("modal_in_evidence", "modality") in codes(C.check(a, spans))  # an obligation with a modal in the evidence needs it
    a["status"] = {"value": "not_a_requirement", "evidence": ["E1"]}  # a non-deontic "can": no modal rule applies
    assert C.check(a, spans) == []


def test_class_none_is_only_for_a_modal_free_obligation(R, C):
    spans = _spans("Rotate keys.")
    for status in ("recommendation", "permission", "prohibition"):
        a = copy.deepcopy(R.EXAMPLES[4]["answer"])  # null phrase, class none
        a["status"] = {"value": status, "evidence": ["E1"]}
        a["action"] = {"value": "Rotate keys", "evidence": ["E1"]}
        assert ("modality_class", "status") in codes(C.check(a, spans)), status
    a = copy.deepcopy(R.EXAMPLES[4]["answer"])
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["action"] = {"value": "Rotate keys", "evidence": ["E1"]}
    assert codes(C.check(a, spans)) == []  # a genuinely modal-free obligation is fine
    # an obligation inferred from explicit "should" evidence cannot hide behind class none
    spans = _spans("Administrators should rotate keys.")
    a["action"] = {"value": "rotate keys", "evidence": ["E1"]}
    assert ("modal_in_evidence", "modality") in codes(C.check(a, spans))


def test_an_extractive_value_must_be_inside_one_cited_span_not_stitched_across_two(R, C):
    spans = _spans("The Authorizing Official and the Program", "Manager review waivers.")
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["actor"] = {"value": "Program Manager", "evidence": ["E1", "E2"]}
    assert ("not_in_cited_span", "actor") in codes(C.check(a, spans))
    spans = _spans("The Authorizing Official and the Program Manager review waivers.")
    a["actor"] = {"value": "Program Manager", "evidence": ["E1"]}
    assert ("not_in_cited_span", "actor") not in codes(C.check(a, spans))


def test_a_subordinate_modal_the_source_contains_is_a_faithful_copy_but_a_new_one_is_not(R, C):
    spans = _spans("Administrators must record whether users may obtain access.")
    a = copy.deepcopy(R.EXAMPLES[1]["answer"])
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["actor"] = {"value": "Administrators", "evidence": ["E1"]}
    a["action"] = {"value": "record whether users may obtain access", "evidence": ["E1"]}
    a["target"] = {"value": None, "evidence": []}
    a["exceptions"] = []
    a["modality"] = {"verbatim": "must", "class": "obligation", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": "Administrators must record whether users may obtain access.", "evidence": ["E1"]}
    a["plain_language"] = {"value": "Administrators have to note whether users may get access.", "evidence": []}
    assert codes(C.check(a, spans)) == []  # the "may" is in the source; "have to" is the same class as "must"
    a["standalone_statement"] = {"value": "Administrators must record whether users shall obtain access.", "evidence": ["E1"]}
    assert ("added_token", "standalone_statement") not in codes(C.check(a, spans))
    a["standalone_statement"] = {"value": "Administrators must record whether users may obtain access and should audit it.", "evidence": ["E1"]}
    assert ("modality_strengthened", "standalone_statement") in codes(C.check(a, spans))  # a new "should" is a changed modal


def test_the_cited_operator_must_match_the_logic_value(R, C):
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    for key in ("actor", "action", "target", "timing"):
        a[key] = {"value": None, "evidence": []}
    a["modality"] = {"verbatim": "must", "class": "obligation", "evidence": ["E1"]}
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": None, "evidence": []}
    a["plain_language"] = {"value": None, "evidence": []}
    only_or = _spans("Keys must be stored apart from the data, or custodians shall be named.")
    a["logic"] = {"value": "and", "evidence": ["E1"]}
    assert ("logic_without_text", "logic") in codes(C.check(a, only_or))
    a["logic"] = {"value": "or", "evidence": ["E1"]}
    assert ("logic_without_text", "logic") not in codes(C.check(a, only_or))


def test_status_class_consistency_applies_only_to_requirement_statuses(R, C):
    spans = _spans("The system may fail during startup.")
    a = copy.deepcopy(R.EXAMPLES[5]["answer"])
    a["status"] = {"value": "not_a_requirement", "evidence": ["E1"]}
    a["modality"] = {"verbatim": "may", "class": "permission", "evidence": ["E1"]}
    a["applicability"] = {"value": None, "evidence": []}
    assert codes(C.check(a, spans)) == []  # permission class with a non-requirement status is not a mismatch


# ---- composed fields ---------------------------------------------------------------------------------------------------


def test_new_tokens_ignore_sentence_starts_and_case_but_catch_numbers_acronyms_and_names(C):
    src = "Administrators should rotate shared secrets."
    assert C.new_tokens("The administrators should rotate shared secrets.", src) == []
    assert C.new_tokens("Shared secrets should be rotated by Administrators.", src) == []
    assert C.new_tokens("Administrators should rotate shared secrets every 90 days.", src) == ["90"]
    assert C.new_tokens("Administrators should rotate shared secrets using PKI.", src) == ["PKI"]
    assert C.new_tokens("Administrators should rotate shared secrets for Acme Corp.", src) == ["Acme", "Corp"]


def test_plain_language_is_checked_against_the_standalone_sentence_and_its_spans(R, C):
    spans = _spans("Administrators should rotate shared secrets every 90 days.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["target"] = {"value": "shared secrets", "evidence": ["E1"]}
    a["action"] = {"value": "rotate shared secrets", "evidence": ["E1"]}
    a["modality"] = {"verbatim": "should", "class": "recommendation", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": "Administrators should rotate shared secrets every 90 days.", "evidence": ["E1"]}
    a["plain_language"] = {"value": "Administrators are advised to change shared secrets every 90 days.", "evidence": []}
    assert codes(C.check(a, spans)) == []  # "90" is in the standalone sentence, so keeping it is faithful
    a["plain_language"] = {"value": "Administrators are advised to change shared secrets every 60 days.", "evidence": []}
    assert ("added_token", "plain_language") in codes(C.check(a, spans))
    a["standalone_statement"] = {"value": None, "evidence": []}
    assert ("plain_without_standalone", "plain_language") in codes(C.check(a, spans))


def test_a_standalone_sentence_that_adds_a_party_or_number_is_flagged(R, C):
    spans = _spans("Administrators should rotate shared secrets.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["actor"] = {"value": "Administrators", "evidence": ["E1"]}
    a["action"] = {"value": "rotate shared secrets", "evidence": ["E1"]}
    a["target"] = {"value": "shared secrets", "evidence": ["E1"]}
    a["modality"] = {"verbatim": "should", "class": "recommendation", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": "Administrators should rotate shared secrets every 90 days.", "evidence": ["E1"]}
    assert ("added_token", "standalone_statement") in codes(C.check(a, spans))


# ---- logic, unresolved, shape ------------------------------------------------------------------------------------------


def test_logic_other_than_none_needs_and_or_text_in_a_cited_span(R, C):
    spans = _spans("Keys must be stored apart from the data; and custodians shall be named.")
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["logic"] = {"value": "and", "evidence": ["E1"]}
    a["actor"] = {"value": None, "evidence": []}
    a["action"] = {"value": None, "evidence": []}
    a["target"] = {"value": None, "evidence": []}
    a["timing"] = {"value": None, "evidence": []}
    a["modality"] = {"verbatim": "must", "class": "obligation", "evidence": ["E1"]}
    a["status"] = {"value": "obligation", "evidence": ["E1"]}
    a["standalone_statement"] = {"value": None, "evidence": []}
    a["plain_language"] = {"value": None, "evidence": []}
    assert codes(C.check(a, spans)) == []
    assert ("logic_without_text", "logic") in codes(C.check(a, _spans("Keys must be stored apart from the data.")))


def test_an_unresolved_answer_without_a_reason_is_a_warning(R, C):
    spans = _spans("Comply with the requirements of paragraph 4.2.")
    a = copy.deepcopy(R.EXAMPLES[4]["answer"])
    a["unresolved_reason"] = {"value": None, "evidence": []}
    assert ("missing_reason", "unresolved_reason") in codes(C.check(a, spans), "warn")


def test_shape_issues_are_reported_per_field_and_stop_further_checks(R, C):
    spans = _spans("x")
    a = copy.deepcopy(R.EXAMPLES[0]["answer"])
    del a["timing"]
    a["modality"] = {"class": "obligation"}
    a["conditions"] = {"value": "not a list"}
    a["status"]["value"] = "mandatory"
    issues = C.check(a, spans)
    assert issues and all(i.code == "shape" for i in issues)
    assert ("shape", "timing") in codes(issues)
    assert C.shape_issues("not an object")[0].code == "shape"
    assert C.shape_issues(R.EXAMPLES[0]["answer"]) == []


def test_a_dropped_primary_modal_or_a_reassigned_subordinate_modal_is_caught(R, C):
    spans = _spans("The Authorizing Official may grant a waiver.")
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["timing"] = {"value": None, "evidence": []}
    a["standalone_statement"] = {"value": "The Authorizing Official grants a waiver.", "evidence": ["E1"]}
    a["plain_language"] = {"value": None, "evidence": []}
    assert ("modality_removed", "standalone_statement") in codes(C.check(a, spans))  # the permission was dropped
    a["standalone_statement"] = {"value": "The Authorizing Official may grant a waiver.", "evidence": ["E1"]}
    assert codes(C.check(a, spans)) == []
    # a source with both "must" and a subordinate "may": swapping the "may" for "must" changes the meaning
    spans = _spans("Administrators must record whether users may obtain access.")
    b = copy.deepcopy(R.EXAMPLES[1]["answer"])
    b["status"] = {"value": "obligation", "evidence": ["E1"]}
    b["actor"] = {"value": "Administrators", "evidence": ["E1"]}
    b["action"] = {"value": "record whether users may obtain access", "evidence": ["E1"]}
    b["target"] = {"value": None, "evidence": []}
    b["exceptions"] = []
    b["modality"] = {"verbatim": "must", "class": "obligation", "evidence": ["E1"]}
    b["plain_language"] = {"value": None, "evidence": []}
    b["standalone_statement"] = {"value": "Administrators must record whether users must obtain access.", "evidence": ["E1"]}
    assert ("modality_strengthened", "standalone_statement") in codes(C.check(b, spans))
    # plain language is held to the standalone sentence's modals the same way
    b["standalone_statement"] = {"value": "Administrators must record whether users may obtain access.", "evidence": ["E1"]}
    b["plain_language"] = {"value": "Administrators have to note whether users have to get access.", "evidence": []}
    assert ("modality_strengthened", "plain_language") in codes(C.check(b, spans))


def test_wrong_primitive_types_are_shape_issues_not_crashes(R, C):
    spans = _spans("Administrators should not reuse passwords.")
    for field, bad in (
        ("actor", {"value": 123, "evidence": ["E1"]}),
        ("action", {"value": "x", "evidence": [1]}),
        ("status", {"value": ["obligation"], "evidence": []}),
        ("logic", {"value": None, "evidence": []}),
        ("plain_language", {"value": {"a": 1}, "evidence": []}),
    ):
        a = copy.deepcopy(R.EXAMPLES[3]["answer"])
        a[field] = bad
        issues = C.check(a, spans)  # must not raise
        assert issues and all(i.code == "shape" for i in issues), field
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["modality"] = {"verbatim": 5, "class": "recommendation", "evidence": ["E1"]}
    assert all(i.code == "shape" for i in C.check(a, spans))
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["conditions"] = [{"value": None, "evidence": []}]
    assert any(i.code == "shape" for i in C.check(a, spans))  # a list item's value must be a string


def test_plain_language_and_unresolved_reason_evidence_is_validated_and_must_stay_empty(R, C):
    spans = _spans("Administrators should not reuse passwords.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["plain_language"] = {"value": a["plain_language"]["value"], "evidence": ["E999"]}
    got = codes(C.check(a, spans))
    assert ("bad_evidence_id", "plain_language") in got and ("evidence_not_allowed", "plain_language") in got
    a = copy.deepcopy(R.EXAMPLES[4]["answer"])
    a["unresolved_reason"] = {"value": "x", "evidence": ["E1"]}
    assert ("evidence_not_allowed", "unresolved_reason") in codes(C.check(a, _spans("Comply with paragraph 4.2.")))


def test_the_requirement_statuses_are_listed_explicitly_not_by_position(R):
    assert R.REQUIREMENT_STATUS == ("obligation", "recommendation", "permission", "prohibition")
    assert set(R.REQUIREMENT_STATUS) <= set(R.STATUS)


def test_plain_language_must_keep_the_primary_modal_too(R, C):
    spans = _spans("The Authorizing Official may grant a waiver.")
    a = copy.deepcopy(R.EXAMPLES[2]["answer"])
    a["timing"] = {"value": None, "evidence": []}
    a["standalone_statement"] = {"value": "The Authorizing Official may grant a waiver.", "evidence": ["E1"]}
    a["plain_language"] = {"value": "The Authorizing Official is allowed to give a waiver.", "evidence": []}
    assert codes(C.check(a, spans)) == []
    a["plain_language"] = {"value": "The Authorizing Official gives a waiver.", "evidence": []}
    assert ("modality_removed", "plain_language") in codes(C.check(a, spans))  # the permission disappeared


def test_an_unresolved_answer_is_not_validated_for_modality(R, C):
    spans = _spans("Operators are expected to comply with paragraph 4.2.")
    a = copy.deepcopy(R.EXAMPLES[4]["answer"])
    a["action"] = {"value": "comply with paragraph 4.2", "evidence": ["E1"]}
    a["modality"] = {"verbatim": "are expected to", "class": "obligation", "evidence": ["E1"]}  # not in the phrase table
    a["unresolved_reason"] = {"value": "paragraph 4.2 is not in the evidence", "evidence": []}
    assert codes(C.check(a, spans)) == []
    a["status"] = {"value": "obligation", "evidence": ["E1"]}  # resolved: now the phrase must be in the table
    a["unresolved_reason"] = {"value": None, "evidence": []}
    assert ("unknown_modal_phrase", "modality") in codes(C.check(a, spans))


def test_a_sentence_start_after_a_closing_bracket_or_quote_is_not_a_new_name(C):
    src = "Operators review logs."
    assert C.new_tokens("(Operators review logs.) Contractors review logs.", src + " Contractors") == []
    assert C.new_tokens('The rule says "Operators review logs." Next, review logs.', src) == []
    assert C.new_tokens("Operators review logs with Acme.", src) == ["Acme"]


def test_a_reason_on_a_resolved_answer_is_a_warning_and_the_modality_error_set_is_defined(R, C):
    spans = _spans("Administrators should not reuse passwords.")
    a = copy.deepcopy(R.EXAMPLES[3]["answer"])
    a["unresolved_reason"] = {"value": "something", "evidence": []}
    assert ("superfluous_reason", "unresolved_reason") in codes(C.check(a, spans), "warn")
    a["modality"]["class"] = "obligation"
    got = C.check(a, spans)
    assert {i.code for i in C.modality_errors(got)} >= {"modality_strengthened"}
    assert "modality_removed" in C.MODALITY_ERROR_CODES and "added_token" not in C.MODALITY_ERROR_CODES
