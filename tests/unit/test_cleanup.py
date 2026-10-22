"""Cleanup flag (docs/CLEANUP_FLAG_PLAN.md): sidecar judgments, the priority-cell suffix and the exports. The model call is injected, never made."""
import json

from services import cleanup as CL


def _item(n, quote="Units shall patch servers.", passage="Section 2. Units shall patch servers.", criticality=None):
    item = {"checklist_item_id": f"CL-{n}", "source_quote": quote, "passage": passage}
    if criticality:
        item["criticality"] = criticality
    return item


def test_sidecar_name_follows_the_requirements_file(tmp_path):
    assert CL.sidecar_path(tmp_path / "afi17-203_requirements_gated.jsonl").name == "afi17-203_cleanup.jsonl"


def test_only_a_clear_no_flags_the_row():
    assert [CL.is_junk(a) for a in ("NO", " no.", "No", "YES", "", None, "Maybe", "NOT SURE", "NONE", "Nothing", "No, it is not")] == [True, True, True, False, False, False, False, False, False, False, True]


def test_prompt_carries_passage_and_quote_and_none_without_passage():
    p = CL.build_prompt(_item(1))
    assert 'Passage:\nSection 2. Units shall patch servers.\n' in p and 'Sentence to check:\n"Units shall patch servers."' in p and p.endswith("Answer with one word: YES or NO.")
    assert CL.build_prompt(_item(2, passage="")) is None
    assert CL.build_prompt(_item(3, quote="")) is None


def test_prompt_judges_the_root_quote_not_the_explained_text():
    item = {**_item(1, quote="MCCCs: Coordinate with units."), "extracted_quote": "Coordinate with units."}
    assert 'Sentence to check:\n"Coordinate with units."' in CL.build_prompt(item)


def test_judge_writes_sidecar_and_counts(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"
    items = [_item(1), _item(2, quote="This section describes scope."), _item(3, passage="")]
    answers = iter(["YES", "NO"])
    counts = CL.judge_rows(items, path, model="m1", call=lambda prompt: next(answers))
    assert counts == {"rows": 3, "judged": 2, "flagged": 1, "no_passage": 1, "reused": 0, "errors": 0}
    recs = CL.load(path)
    assert {k: v["junk"] for k, v in recs.items()} == {"CL-1": False, "CL-2": True}


def test_unchanged_rows_are_reused_and_changed_model_recomputes(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"
    items = [_item(1), _item(2)]
    CL.judge_rows(items, path, model="m1", call=lambda p: "NO")
    calls = []
    again = CL.judge_rows(items, path, model="m1", call=lambda p: calls.append(p) or "YES")
    assert again["reused"] == 2 and again["flagged"] == 2 and calls == []
    other = CL.judge_rows(items, path, model="m2", call=lambda p: calls.append(p) or "YES")
    assert other["judged"] == 2 and other["flagged"] == 0 and len(calls) == 2


def test_failed_call_flags_nothing_and_five_in_a_row_abort(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"

    def boom(prompt):
        raise ConnectionError("down")
    counts = CL.judge_rows([_item(n) for n in range(8)], path, model="m", call=boom)
    assert counts["errors"] == 5 and counts["aborted"] is True and counts["flagged"] == 0 and CL.load(path) == {}


def test_a_reply_with_no_message_is_a_failed_call_not_a_flag(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"

    def odd(prompt):
        raise KeyError("message")
    counts = CL.judge_rows([_item(1)], path, model="m", call=odd)
    assert counts["errors"] == 1 and counts["flagged"] == 0


def test_apply_adds_suffix_and_keeps_the_rating(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"
    rated, unrated, kept = _item(1, criticality="High"), _item(2, quote="Scope text."), _item(3, quote="Units shall log.", criticality="Low")
    CL.judge_rows([rated, unrated, kept], path, model="m", call=lambda p: "YES" if "Units shall log." in p else "NO")
    assert CL.apply([rated, unrated, kept], path) == 2
    assert rated["criticality"] == "High · junk" and rated["junk"] is True
    assert unrated["criticality"] == "junk" and unrated["junk"] is True
    assert kept["criticality"] == "Low" and "junk" not in kept


def test_apply_with_no_sidecar_changes_nothing(tmp_path):
    items = [_item(1, criticality="High"), _item(2)]
    assert CL.apply(items, tmp_path / "missing_cleanup.jsonl") == 0
    assert items == [_item(1, criticality="High"), _item(2)]


def test_stale_record_is_ignored(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"
    item = _item(1, criticality="High")
    CL.judge_rows([item], path, model="m", call=lambda p: "NO")
    changed = _item(1, quote="A different sentence.", criticality="High")
    assert CL.apply([changed], path) == 0 and changed["criticality"] == "High"
    rec = json.loads(path.read_text())
    assert rec["junk"] is True and rec["prompt_version"] == "strict-may-1"


def test_chunk_texts_gives_the_whole_chunk_and_skips_rows_without_a_record(tmp_path):
    (tmp_path / "d_chunks.jsonl").write_text(json.dumps({"chunk_id": 7, "text": "short", "raw_text": "The whole chunk of text."}) + "\n", encoding="utf-8")
    req = tmp_path / "d_requirements_gated.jsonl"
    req.write_text(json.dumps({"requirement_id": "REQ-1", "chunk_id": 7}) + "\n", encoding="utf-8")
    items = [{**_item(1), "requirement_ids": ["REQ-1"]}, {**_item(2), "requirement_ids": []}, {**_item(3), "requirement_ids": ["REQ-9"]}]
    assert CL.chunk_texts(req, items) == {"CL-1": "The whole chunk of text."}
    assert CL.chunk_texts(tmp_path / "gone_requirements_gated.jsonl", items) == {}
    assert 'Passage:\nThe whole chunk of text.\n' in CL.build_prompt(items[0], "The whole chunk of text.")


def test_apply_ignores_a_record_made_from_different_chunk_text(tmp_path):
    path = tmp_path / "d_cleanup.jsonl"
    item = _item(1, criticality="High")
    CL.judge_rows([item], path, model="m", call=lambda p: "NO", texts={"CL-1": "Chunk A."})
    assert CL.apply([item], path, {"CL-1": "Chunk B."}) == 0 and item["criticality"] == "High"
    assert CL.apply([item], path, {"CL-1": "Chunk A."}) == 1 and item["criticality"] == "High · junk"
