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
