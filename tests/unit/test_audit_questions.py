"""WP-46.6: draft audit questions (sidecar file; the model call is injected, never made)."""
import json
import re

from services import audit_questions as AQ


def _item(i, quote, **kw):
    base = {"checklist_item_id": f"CL-{i}", "source_quote": quote, "applies_to": "Commanders", "parent_ref": "", "parent_text": "", "passage": f">> {quote} <<", "item_flags": [], "generation_notes": "", "audit_question": ""}
    base.update(kw)
    return base


def _answer(q):
    return json.dumps({"question": q})


def test_sidecar_path_sits_beside_the_requirements_file(tmp_path):
    assert AQ.sidecar_path(tmp_path / "afi17-203_requirements_gated.jsonl").name == "afi17-203_audit_questions.jsonl"
    assert AQ.sidecar_path(tmp_path / "DODI 8551.01_requirements_normalized.jsonl").name == "DODI 8551.01_audit_questions.jsonl"


def test_questions_are_written_skipped_rows_get_none_and_the_model_is_not_called_for_them(tmp_path):
    prompts = []
    items = [_item(1, "Commanders shall review logs monthly."), _item(2, "some tail of a sentence", item_flags=["starts_mid_sentence"]), _item(3, "")]
    counts = AQ.draft_questions(items, tmp_path / "q.jsonl", call=lambda p: prompts.append(p) or _answer("Do Commanders review logs monthly?"))
    assert counts["rows"] == 2 and counts["questions"] == 1 and counts["skipped_by_code"] == 1 and len(prompts) == 1
    saved = AQ.load(tmp_path / "q.jsonl")
    assert saved["CL-1"]["question"].startswith("Do Commanders") and saved["CL-2"]["question"] is None and saved["CL-2"]["skipped_because"] == ["starts_mid_sentence"]


def test_unchanged_rows_are_reused_and_a_changed_row_is_asked_again(tmp_path):
    calls = []
    call = lambda p: calls.append(p) or _answer("Do Commanders review logs monthly?")  # noqa: E731
    path = tmp_path / "q.jsonl"
    AQ.draft_questions([_item(1, "Commanders shall review logs monthly.")], path, call=call)
    counts = AQ.draft_questions([_item(1, "Commanders shall review logs monthly.")], path, call=call)
    assert counts["reused"] == 1 and len(calls) == 1
    AQ.draft_questions([_item(1, "Commanders shall review logs weekly.")], path, call=call)
    assert len(calls) == 2


def test_a_malformed_answer_is_retried_once_then_recorded_as_an_error_and_retried_next_run(tmp_path):
    answers = iter(["not json", "{}"])
    counts = AQ.draft_questions([_item(1, "Commanders shall review logs monthly.")], tmp_path / "q.jsonl", call=lambda p: next(answers))
    assert counts["errors"] == 1 and counts["questions"] == 0
    counts = AQ.draft_questions([_item(1, "Commanders shall review logs monthly.")], tmp_path / "q.jsonl", call=lambda p: _answer("Do Commanders review logs monthly?"))
    assert counts["errors"] == 0 and counts["questions"] == 1 and counts["reused"] == 0


def test_a_null_answer_is_no_question_not_an_error(tmp_path):
    counts = AQ.draft_questions([_item(1, "Commanders may waive the review.")], tmp_path / "q.jsonl", call=lambda p: _answer(None))
    assert counts["no_question"] == 1 and counts["errors"] == 0


def test_terms_the_row_does_not_contain_are_marked_not_removed(tmp_path):
    item = _item(1, "Commanders shall review logs monthly.")
    AQ.draft_questions([item], tmp_path / "q.jsonl", call=lambda p: _answer("Do Commanders review logs monthly using SIEM-9?"))
    assert AQ.apply([item], tmp_path / "q.jsonl") == 1
    assert item["audit_question"].endswith("SIEM-9?") and "SIEM-9" in item["generation_notes"] and "check it before use" in item["generation_notes"]


def test_the_prohibition_rule_is_added_only_for_a_prohibition():
    assert "forbids" in AQ.build_prompt(_item(1, "Users shall not share accounts."))
    assert "forbids" not in AQ.build_prompt(_item(1, "Users shall review accounts."))


def test_prohibition_forms_are_recognized():
    for text in ("Do not release the report.", "(T-1) Do not release the report.", "Users cannot reuse passwords.", "Disclosure is prohibited.", "Personnel must not leave the area.",
                 "Waivers are not appropriate for granting time extensions.", "The requirements outlined are not waivable.", "Visitors are not allowed in the room.", "Personnel may not enter.",
                 "Submit the form to the office. Do not release the report.", "Notify the commander. (T-1) Do not release the report.", "2) Do not release the report."):
        assert AQ.PROHIBITION.search(text), text
    assert not AQ.PROHIBITION.search("Examples include, but are not limited to, logs.")
    assert not AQ.PROHIBITION.search("This issuance: Does not alter existing authorities.")  # a description that follows a colon, not a sentence that opens with Do not


def test_a_plain_negation_in_a_condition_or_description_is_not_a_prohibition():
    for text in ("MAJCOM/DRUs will inform the HAF CARM Program office if this capability does not exist.", "DCAs are not an independent tier of assets, but are a high-priority subset of Tier 1 TCAs.",
                 "This list does not include every weapon system.", "The unit does not share keys.", "Report systems that do not meet the standard."):
        assert not AQ.PROHIBITION.search(text), text
        assert "forbids" not in AQ.build_prompt(_item(1, text))


def test_the_narrowed_pattern_never_fires_where_the_old_one_did_not():
    old = re.compile(r"\b(?:shall|must|should|will|may|can|could|would|do|does|did|is|are|be)\s+not\b(?!\s+(?:limited|only|necessarily))|\bcannot\b|\bnever\b|\bprohibited\b|\bforbidden\b", re.IGNORECASE)
    for text in ("Do not release.", "(T-1) Do not release.", "Waivers are not appropriate.", "It is not to be shared.", "This does not apply.", "The unit shall not exceed it.", "The CFP shall notify the MCCC."):
        assert old.search(text) or not AQ.PROHIBITION.search(text), text


def test_apply_leaves_rows_without_a_record_alone(tmp_path):
    item = _item(1, "Commanders shall review logs monthly.")
    assert AQ.apply([item], tmp_path / "missing.jsonl") == 0 and item["audit_question"] == "" and item["generation_notes"] == ""


def test_generate_fills_the_audit_question_from_the_sidecar(tmp_path):
    from services.checklist_service import generate
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    req = {"requirement_id": "REQ-1", "source_quote": "Commanders shall review logs monthly.", "source_ref": "1.1", "section_title_path": ["Logs"], "domain_tags": ["logging"], "confidence": 0.9, "page_start": 1, "page_end": 1, "chunk_id": 0}
    (run / "doc_chunks.jsonl").write_text(json.dumps({"chunk_id": 0, "raw_text": "1.1. Commanders shall review logs monthly. Reports go to the CIO.", "text": "x", "section_title_path": ["Logs"], "page_start": 1, "page_end": 1}) + "\n", encoding="utf-8")
    (run / "doc_requirements_normalized.jsonl").write_text(json.dumps(req) + "\n", encoding="utf-8")
    plain = generate(tmp_path, "doc", "cybersecurity")
    assert plain["items"][0]["audit_question"] == "" and plain["summary"]["items_with_draft_question"] == 0
    AQ.draft_questions(plain["items"], AQ.sidecar_path(run / "doc_requirements_normalized.jsonl"), call=lambda p: _answer("Do Commanders review logs monthly?"))
    filled = generate(tmp_path, "doc", "cybersecurity")
    assert filled["items"][0]["audit_question"] == "Do Commanders review logs monthly?" and filled["summary"]["items_with_draft_question"] == 1


def test_a_plain_word_must_match_a_whole_word_and_the_first_word_after_a_sentence_start_is_still_checked():
    assert AQ.unverified_terms("Do the units file a port report?", "Units file the report monthly.") == []  # "port" is lower case: not a checked term
    assert AQ.unverified_terms("Do Administrators review logs?", "Commanders review logs monthly.") == ["Administrators"]
    assert AQ.unverified_terms("CIO approval is documented?", "Commanders review logs monthly.") == ["CIO"]
    assert AQ.unverified_terms("Does the unit review logs?", "Commanders review logs monthly.") == []
    assert AQ.unverified_terms("Does the unit use SIEM-9?", "The unit uses a tool (SIEM-9a).") == []  # inside a longer token
    assert AQ.unverified_terms("Does the unit use SIEM-9?", "The unit uses a tool.") == ["SIEM-9"]


def test_apply_ignores_a_record_written_from_a_different_row(tmp_path):
    path = tmp_path / "q.jsonl"
    AQ.draft_questions([_item(1, "Commanders shall review logs monthly.")], path, call=lambda p: _answer("Do Commanders review logs monthly?"))
    changed = _item(1, "Commanders shall review logs monthly.", passage=">> Commanders shall review logs monthly. <<  Auditors verify.")
    assert AQ.apply([changed], path) == 0 and changed["audit_question"] == ""
    flagged = _item(1, "Commanders shall review logs monthly.", item_flags=["table_fragment"])
    assert AQ.apply([flagged], path) == 0


def test_unverified_terms_become_a_review_reason(tmp_path):
    item = _item(1, "Commanders shall review logs monthly.")
    AQ.draft_questions([item], tmp_path / "q.jsonl", call=lambda p: _answer("Do Commanders review logs monthly using SIEM-9?"))
    AQ.apply([item], tmp_path / "q.jsonl")
    assert any(r.startswith("question-has-terms-not-in-row") for r in item["review_reasons"]) and item["requires_human_review"] is True


def test_a_checkpoint_keeps_the_records_of_rows_not_reached_yet(tmp_path):
    path = tmp_path / "q.jsonl"
    items = [_item(i, f"Commanders shall review log number {i} monthly.") for i in range(1, 31)]
    AQ.draft_questions(items, path, call=lambda p: _answer("Do Commanders review the log?"))
    seen = []

    def boom(prompt):
        if len(seen) >= 26:
            raise ValueError("stop")
        seen.append(1)
        return _answer("Do Commanders review the log monthly?")

    changed = [_item(i, f"Commanders shall review log number {i} weekly.") for i in range(1, 31)]
    AQ.draft_questions(changed, path, call=boom, progress=lambda c: None)
    assert len(AQ.load(path)) == 30


def test_an_unreachable_model_stops_the_run_and_keeps_earlier_rows(tmp_path):
    import requests
    path = tmp_path / "q.jsonl"
    items = [_item(i, f"Commanders shall review log number {i} monthly.") for i in range(1, 12)]
    done = []

    def call(prompt):
        if len(done) < 2:
            done.append(1)
            return _answer("Do Commanders review the log?")
        raise requests.ConnectionError("down")

    counts = AQ.draft_questions(items, path, call=call)
    assert counts.get("aborted") is True and counts["questions"] == 2
    assert sum(1 for r in AQ.load(path).values() if r.get("question")) == 2


def test_a_part_of_a_longer_token_a_plural_and_a_camel_case_name_count_as_present():
    material = "Install the DISA StoreFront roles; Networx/EIS contracts apply to the Installation."
    assert AQ.unverified_terms("Does the unit use the DISA StoreFront for Networx and EIS contracts at the Installations?", material) == []
    assert AQ.unverified_terms("Does the unit use the DISA StoreFront for Cloudx contracts?", material) == ["Cloudx"]


def test_reused_questions_get_their_unverified_terms_recomputed(tmp_path):
    item = _item(1, "Commanders shall review logs monthly.")
    path = tmp_path / "q.jsonl"
    AQ.draft_questions([item], path, call=lambda p: _answer("Do Commanders review logs monthly using SIEM-9?"))
    saved = AQ.load(path)
    saved["CL-1"]["unverified_terms"] = ["stale"]
    AQ.write(path, saved)
    AQ.draft_questions([item], path, call=lambda p: 1 / 0)
    assert AQ.load(path)["CL-1"]["unverified_terms"] == ["SIEM-9"]


def test_mixed_case_names_with_acronym_parts_are_checked_whole():
    assert AQ.unverified_terms("Does the unit use FedRAMP and DoD controls?", "The unit uses controls.") == ["FedRAMP", "DoD"]
    assert AQ.unverified_terms("Does the unit use FedRAMP?", "The unit uses FedRAMP controls.") == []
    assert AQ.unverified_terms("Does the unit follow Camel guidance?", "The unit follows guidance.") == ["Camel"]  # a single capitalized word is still checked


def test_a_lead_in_attached_from_above_does_not_stop_the_passage_from_being_found(tmp_path):
    from services.checklist_service import generate
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    raw = "The USD(A&S):\n- a. Establishes policy for acquisition.\n- b. Develops budget recommendations."
    (run / "doc_chunks.jsonl").write_text(json.dumps({"chunk_id": 0, "raw_text": raw, "text": raw, "section_title_path": ["Duties"], "page_start": 1, "page_end": 1}) + "\n", encoding="utf-8")
    req = {"requirement_id": "REQ-1", "source_quote": "- b. Develops budget recommendations.", "explained_text": "The USD(A&S): Develops budget recommendations.",
           "explained_parts": [{"kind": "lead_in", "text": "The USD(A&S):", "origin": "rule"}, {"kind": "sentence", "text": "Develops budget recommendations.", "origin": "rule"}],
           "source_ref": "b", "section_title_path": ["Duties"], "page_start": 1, "page_end": 1, "chunk_id": 0}
    (run / "doc_requirements_normalized.jsonl").write_text(json.dumps(req) + "\n", encoding="utf-8")
    item = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert "quote_not_located_in_passage" not in item["item_flags"] and ">> Develops budget recommendations. <<" in item["passage"]
    assert item["source_quote"] == "The USD(A&S): Develops budget recommendations."


def test_a_lead_in_from_the_previous_chunk_brings_the_previous_chunk_into_the_passage(tmp_path):
    from services.checklist_service import generate
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    chunks = [{"chunk_id": 0, "raw_text": "Intro sentence here.\nThe USD(A&S):\n- a. Establishes policy for acquisition.", "section_title_path": ["Duties"], "page_start": 1, "page_end": 1},
              {"chunk_id": 1, "raw_text": "- b. Develops budget recommendations.", "section_title_path": ["Duties"], "page_start": 1, "page_end": 1}]
    (run / "doc_chunks.jsonl").write_text("".join(json.dumps({**c, "text": c["raw_text"]}) + "\n" for c in chunks), encoding="utf-8")
    req = {"requirement_id": "REQ-1", "source_quote": "- b. Develops budget recommendations.", "explained_text": "The USD(A&S): Develops budget recommendations.",
           "explained_parts": [{"kind": "lead_in", "text": "The USD(A&S):", "origin": "rule"}, {"kind": "sentence", "text": "Develops budget recommendations.", "origin": "rule"}],
           "source_ref": "b", "section_title_path": ["Duties"], "page_start": 1, "page_end": 1, "chunk_id": 1}
    (run / "doc_requirements_normalized.jsonl").write_text(json.dumps(req) + "\n", encoding="utf-8")
    item = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert "The USD(A&S):" in item["passage"] and ">> Develops budget recommendations. <<" in item["passage"]


def test_the_prompt_takes_the_actor_from_the_requirement_before_the_applies_to_line():
    assert "the \"Applies to\" line is the actor only when the requirement names none" in AQ.PROMPT
    assert "Name who must act if the material says so" not in AQ.PROMPT
    prompt = AQ.build_prompt(_item(1, "Required courses will be designated by the program office."))
    assert "Requirement: Required courses will be designated by the program office." in prompt and "Applies to: Commanders" in prompt


def test_a_subject_term_found_only_in_the_surrounding_text_is_marked_for_review(tmp_path):
    passage = "3.3.3.6. The HAF CARM Program will collaborate with the MA office to provide submissions. >> Submissions should include justification. <<"
    item = _item(1, "Submissions should include justification.", applies_to="", parent_ref="3.3", parent_text="TCA Assessment Processes.", passage=passage)
    assert AQ.passage_only_terms("Does the HAF CARM Program include justification in submissions?", item) == ["HAF", "CARM", "Program"]
    AQ.draft_questions([item], tmp_path / "q.jsonl", call=lambda p: _answer("Does the HAF CARM Program include justification in submissions?"))
    AQ.apply([item], tmp_path / "q.jsonl")
    assert any(r.startswith("question-actor-not-in-row: HAF, CARM, Program") for r in item["review_reasons"]) and item["requires_human_review"] is True
    assert "surrounding text" in item["generation_notes"]


def test_an_actor_named_in_the_requirement_its_heading_or_its_parent_is_not_marked(tmp_path):
    passage = "2.6.1. Serve as the lead. >> Provide SMEs when requested. <<"
    item = _item(1, "Provide SMEs when requested.", applies_to="Assistant Secretary of the Air Force, Financial Management and Comptroller (SAF/FM)", passage=passage)
    assert AQ.passage_only_terms("Does SAF/FM provide SMEs when requested?", item) == []
    assert AQ.passage_only_terms("Does the unit provide SMEs when requested?", item) == []
    item2 = _item(2, "Provide SMEs when requested.", applies_to="", parent_ref="2.12.6", parent_text="Establish a HAF CARM program office, which:", passage=">> Provide SMEs when requested. <<")
    assert AQ.passage_only_terms("Does the HAF CARM program office provide SMEs when requested?", item2) == []
    AQ.draft_questions([item], tmp_path / "q.jsonl", call=lambda p: _answer("Does SAF/FM provide SMEs when requested?"))
    AQ.apply([item], tmp_path / "q.jsonl")
    assert not any(r.startswith("question-actor-not-in-row") for r in item.get("review_reasons", []))


def test_a_question_that_does_not_open_with_an_auxiliary_has_no_subject_to_check():
    item = _item(1, "Provide SMEs when requested.", passage="The HAF CARM Program ... >> Provide SMEs when requested. <<")
    assert AQ.passage_only_terms("Whether the HAF CARM Program provides SMEs.", item) == []
    assert AQ.passage_only_terms("", item) == [] and AQ.passage_only_terms(None, item) == []


def test_the_word_null_written_as_text_is_no_question_not_a_question():
    assert AQ.parse_answer('{"question": null}') is None
    assert AQ.parse_answer('{"question": "null"}') is None
    assert AQ.parse_answer('{"question": " Null. "}') is None
    assert AQ.parse_answer('{"question": "N/A"}') is None and AQ.parse_answer('{"question": ""}') is None
    assert AQ.parse_answer('{"question": "Does the unit report nulls?"}') == "Does the unit report nulls?"


def test_a_stored_null_string_is_read_as_no_question(tmp_path):
    item = _item(1, "Commanders shall review logs monthly.")
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps({"checklist_item_id": "CL-1", "question": "null", "skipped_because": [], "unverified_terms": [], "model": AQ.MODEL, "input_hash": "x"}) + "\n")
    assert AQ.load(path)["CL-1"]["question"] is None
    assert AQ.apply([item], path) == 0 and not item.get("audit_question")


def test_a_run_that_gets_the_string_null_counts_it_as_no_question(tmp_path):
    item = _item(1, "This document will guide the assessment team.")
    counts = AQ.draft_questions([item], tmp_path / "q.jsonl", call=lambda p: json.dumps({"question": "null"}))
    assert counts["questions"] == 0 and counts["no_question"] == 1 and counts["errors"] == 0
    assert AQ.load(tmp_path / "q.jsonl")["CL-1"]["question"] is None


def test_a_question_opening_with_a_modal_is_checked_for_an_actor_from_the_surrounding_text():
    item = _item(1, "Provide SMEs when requested.", applies_to="", passage="The HAF CARM Program will meet. >> Provide SMEs when requested. <<")
    assert AQ.passage_only_terms("Can the HAF CARM Program provide SMEs when requested?", item) == ["HAF", "CARM", "Program"]
    assert AQ.passage_only_terms("Will the HAF CARM Program provide SMEs when requested?", item) == ["HAF", "CARM", "Program"]


def test_a_statement_of_what_the_document_leaves_untouched_gets_no_question():
    # DODI 8551.01 1.1: the model asked "Does this issuance alter or override ...?", the opposite of the source
    item = _item(1, "This issuance: Does not alter or override existing Director of National Intelligence authorities and policies regarding the protection of sensitive compartmented information.")
    assert AQ.skipped_because(item) == ["document_states_its_own_effect"]
    assert AQ.skipped_because(_item(1, "This Instruction does not apply to AF Intelligence Community systems.")) == ["document_states_its_own_effect"]
    for text in ("Units shall not alter the baseline.", "The unit does not share keys.", "Do not release the report.", "This list does not include every weapon system.",
                 "The policy on mobile devices shall not be violated by users.", "The manual for each unit shall not be altered without approval.",
                 "The issuance of waivers by commanders must not exceed one year."):  # the document noun must be the whole subject (Codex P2 on this PR)
        assert AQ.skipped_because(_item(1, text)) == [], text


def test_the_kind_gate_is_off_unless_asked_for(monkeypatch):
    monkeypatch.delenv("REQBOT_QUESTION_GATE", raising=False)
    item = _item(1, "Compliance with this publication is mandatory.", citation="Front matter")
    assert AQ.skipped_because(item) == []


def test_the_kind_gate_withholds_rows_the_kind_rules_call_not_a_duty(monkeypatch):
    monkeypatch.setenv("REQBOT_QUESTION_GATE", "on")
    front = _item(1, "Compliance with this publication is mandatory.", citation="Front matter")
    assert AQ.skipped_because(front) == ["kind:cover_page_text"]
    duty = _item(2, "The commander will appoint a records manager.")
    assert AQ.skipped_because(duty) == []
    unknown = _item(3, "The method is used extensively in the acquisition of new weapons systems.")
    assert AQ.skipped_because(unknown) == []  # `unknown` is not in the default set: it holds real duties too


def test_the_kind_gate_takes_a_comma_list_of_kinds_and_can_be_turned_off(monkeypatch):
    unknown = _item(3, "The method is used extensively in the acquisition of new weapons systems.")
    monkeypatch.setenv("REQBOT_QUESTION_GATE", "unknown, pointer")
    assert AQ.skipped_because(unknown) == ["kind:unknown"]
    monkeypatch.setenv("REQBOT_QUESTION_GATE", "off")
    assert AQ.skipped_because(unknown) == []


def test_a_gated_row_gets_no_question_and_is_not_sent_to_the_model(monkeypatch, tmp_path):
    monkeypatch.setenv("REQBOT_QUESTION_GATE", "on")
    calls = []
    items = [_item(1, "Compliance with this publication is mandatory.", citation="Front matter"), _item(2, "The commander will appoint a records manager.")]
    counts = AQ.draft_questions(items, tmp_path / "q.jsonl", call=lambda prompt: calls.append(prompt) or '{"question": "Does the commander appoint a records manager?"}')
    saved = AQ.load(tmp_path / "q.jsonl")
    assert len(calls) == 1 and saved["CL-1"]["question"] is None and saved["CL-1"]["skipped_because"] == ["kind:cover_page_text"]
    assert saved["CL-2"]["question"].startswith("Does the commander") and counts["skipped_by_code"] == 1


def test_a_duty_in_a_figure_or_front_matter_is_not_withheld_because_of_where_it_sits(monkeypatch):
    monkeypatch.setenv("REQBOT_QUESTION_GATE", "on")
    figure_duty = _item(1, "Provide the name of the asset owner.", citation="Figure A3.1")
    assert AQ.skipped_because(figure_duty) == []
    front_duty = _item(2, "The commander will appoint a records manager.", citation="Front matter")
    assert AQ.skipped_because(front_duty) == []
    figure_text = _item(3, "Asset Owner Name: ______", citation="Figure A3.1")
    assert AQ.skipped_because(figure_text) == ["kind:form_template_text"]
