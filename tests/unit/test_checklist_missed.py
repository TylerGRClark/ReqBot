"""WP-46.2: the rule-based scan for passages that look like obligations but were not extracted."""
import csv
import io
import json

import openpyxl

from pipeline.checklist_export import to_csv, to_markdown, to_xlsx
from services import checklist_missed as M
from services.checklist_service import generate

CHUNKS = {
    1: {"chunk_id": 1, "page_start": 4, "section_title_path": ["ROLES AND RESPONSIBILITIES", "2.3. AF/A3"], "raw_text": (
        "2.3.1. AF/A3 will:\n"
        "2.3.2. The CFP will notify the servicing MCCC within 24 hours of detection.\n"
        "2.3.3. Reports are filed in the system of record.\n"
        "2.3.4. Support the ACD unit as directed during investigation of the incident.\n"
        "2.3.5. No event will be closed out as a Category 8 without review by the NOS.")},
    2: {"chunk_id": 2, "page_start": 5, "section_title_path": ["Intro"], "raw_text": "This section describes the process. The CFP will notify the servicing MCCC within 24 hours of detection."},
}


def test_units_split_at_paragraph_markers_else_at_sentence_ends():
    assert len(M.paragraph_units(CHUNKS[1]["raw_text"])) == 5
    assert M.paragraph_units("One sentence here. Another one follows; and a third.")[0] == "One sentence here."


def test_only_uncovered_obligation_looking_paragraphs_are_listed_once():
    quotes = ["The CFP will notify the servicing MCCC within 24 hours of detection."]
    found = M.find_possible_missed(CHUNKS, quotes)
    texts = [f["source_quote"] for f in found]
    assert any(t.startswith("2.3.4. Support the ACD unit") for t in texts)  # imperative, not covered
    assert any("No event will be closed out" in t for t in texts)  # modal, not covered
    assert not any("AF/A3 will:" in t for t in texts)  # a lead-in (ends with a colon) is carried by its items
    assert not any("Reports are filed" in t for t in texts)  # no modal, no imperative opener
    assert not any("CFP will notify" in t for t in texts)  # covered by an extracted quote; the repeat in chunk 2 is covered too
    first = next(f for f in found if "Support the ACD" in f["source_quote"])
    assert first["source_ref"] == "2.3.4" and first["page_refs"] == [4] and first["applies_to"] == "AF/A3"
    assert first["item_flags"] == ["possible_missed", "imperative"] and first["checklist_item_id"].startswith("MISS-") and first["requirement_ids"] == []


def test_coverage_ignores_spacing_before_punctuation():
    chunks = {1: {"chunk_id": 1, "page_start": 1, "section_title_path": [], "raw_text": "The CFP shall review the access logs ( weekly ) and report findings ."}}
    assert M.find_possible_missed(chunks, ["The CFP shall review the access logs (weekly) and report findings."]) == []
    assert len(M.find_possible_missed(chunks, [])) == 1


def _write(tmp_path, quotes, chunks):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    recs = [{"requirement_id": f"REQ-{i}", "source_quote": q, "source_ref": "2.3", "chunk_id": 1, "section_title_path": ["ROLES"], "domain_tags": ["x"], "confidence": 0.9,
             "page_start": 4, "page_end": 4} for i, q in enumerate(quotes)]
    (run_dir / "doc_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    if chunks:
        (run_dir / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks.values()))


def test_generate_lists_candidates_apart_from_items_and_counts_them_separately(tmp_path):
    _write(tmp_path, ["The CFP will notify the servicing MCCC within 24 hours of detection."], CHUNKS)
    result = generate(tmp_path, "doc", "cybersecurity")
    assert result["summary"]["total_items"] == 1 and result["summary"]["possible_missed"] == len(result["possible_missed"]) >= 2
    assert all("possible_missed" in m["item_flags"] for m in result["possible_missed"])


def test_without_a_chunk_file_there_are_no_candidates_and_no_crash(tmp_path):
    _write(tmp_path, ["The CFP will notify the MCCC."], None)
    result = generate(tmp_path, "doc", "cybersecurity")
    assert result["possible_missed"] == [] and result["summary"]["possible_missed"] == 0


def test_exports_show_the_section_clearly_apart(tmp_path):
    _write(tmp_path, ["The CFP will notify the servicing MCCC within 24 hours of detection."], CHUNKS)
    checklist = generate(tmp_path, "doc", "cybersecurity")
    n_missed = len(checklist["possible_missed"])
    rows = list(csv.DictReader(io.StringIO(to_csv(checklist))))
    assert len(rows) == 1 + n_missed and sum(1 for r in rows if "possible_missed" in r["item_flags"]) == n_missed
    assert "# Possible missed requirements" in to_markdown(checklist)
    ws = openpyxl.load_workbook(io.BytesIO(to_xlsx(checklist)))["Checklist"]
    assert ws.max_row == 2 + 1 + 1 + 1 + n_missed  # 2 header rows, 1 item, a blank row, the banner row, the candidates
    banner = [r for r in range(3, ws.max_row + 1) if str(ws.cell(row=r, column=1).value or "").startswith("POSSIBLE MISSED REQUIREMENTS")]
    assert banner == [5]
    assert ws.auto_filter.ref.endswith("3")  # the filter covers the extracted rows only
    assert any(ws.cell(row=6, column=8).coordinate in dv.sqref for dv in ws.data_validations.dataValidation)  # the Status dropdown reaches the candidates too


def test_text_before_the_first_marker_and_bare_bullets_are_units():
    raw = "the Director to notify the CISO within 48 hours.\n2.1. The CFP will log all contacts.\n2.2. Report spills to the NOS."
    units = M.paragraph_units(raw)
    assert units[0].startswith("the Director to notify") and len(units) == 3
    bullets = M.paragraph_units("- Review the access logs every quarter and record the findings.\n- Report anomalies to the security manager.")
    assert len(bullets) == 2
    chunks = {1: {"chunk_id": 1, "page_start": 3, "page_end": 5, "section_title_path": [], "raw_text": "- Review the access logs every quarter and record the findings.\n- Report anomalies to the security manager."}}
    found = M.find_possible_missed(chunks, [])
    assert [f["source_quote"] for f in found] == ["Review the access logs every quarter and record the findings.", "Report anomalies to the security manager."]
    assert found[0]["page_refs"] == [3, 4, 5]  # the whole range the chunk spans
