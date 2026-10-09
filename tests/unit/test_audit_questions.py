"""WP-46.6: draft audit questions (sidecar file; the model call is injected, never made)."""
import json

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
