"""WP-46.1: the checklist's audit layout — who a row applies to, the document's own passage, and specific rule-based flags."""
import json

from services import checklist_audit as A
from services.checklist_service import generate


def test_applies_to_is_the_leaf_heading_only_when_it_names_the_responsible_party():
    assert A.applies_to(["ROLES AND RESPONSIBILITIES", "2.17. MAJCOM/DRUs."]) == "MAJCOM/DRUs."
    assert A.applies_to(["SECTION 2", "The DAF Chief Information Officer (SAF/CN) shall:"]) == "The DAF Chief Information Officer (SAF/CN) shall:"
    assert A.applies_to(["ROLES AND RESPONSIBILITIES", "2.1. Purpose"]) == ""  # a procedural label names no one
    assert A.applies_to(["Containment", "3.5.1. Preliminary response"]) == ""  # no responsibilities ancestor, no colon
    assert A.applies_to([]) == "" and A.applies_to(None) == ""


def test_flags_are_specific_and_never_remove_a_row():
    assert A.item_flags("Research actions that can be taken to respond.", "3.6.1.4", "") == ["no_stated_actor"]
    assert A.item_flags("Research actions that can be taken to respond.", "3.6.1.4", "AF/A3") == []  # the role heading supplies the actor
    assert A.item_flags("Supports USCYBERCOM in Mission Analysis development.", "2.5.1", "SAF/AAZ.") == []  # third-person duty under a role heading
    assert "starts_mid_sentence" in A.item_flags("and the Primary Recipient will be", "Table 3.1", "")
    assert "table_fragment" in A.item_flags("and the Primary Recipient will be", "Table 3.1", "")
    assert "list_item" in A.item_flags("(2) Send a copy of the letter to the CISO.", "5.1", "")
    assert "definition_or_description" in A.item_flags("The report breaks down adverse actions into ten categories.", "1.2", "")
    assert "definition_or_description" not in A.item_flags("Issues cyber orders to subordinate wings via the 624 OC.", "2.5.1", "SAF/AAZ.")
    assert A.item_flags("The Director shall report monthly.", "1.2", "") == []


def test_passage_is_verbatim_with_the_quote_marked_and_tolerates_spacing():
    chunk = {"raw_text": "3.1. Intro text. The CFP shall  notify the MCCC ( see Table 1 ) .\nNext paragraph."}
    passage, found = A.build_passage("The CFP shall notify the MCCC (see Table 1).", chunk)
    assert found and ">> The CFP shall  notify the MCCC ( see Table 1 ) . <<" in passage
    assert passage.startswith("3.1. Intro text.") and passage.endswith("Next paragraph.")


def test_a_list_item_gets_the_tail_of_the_previous_chunk_in_front():
    prev = {"raw_text": "x" * 800 + " The Director will:"}
    chunk = {"raw_text": "(a) Review logs monthly."}
    passage, found = A.build_passage("(a) Review logs monthly.", chunk, prev, flags=["list_item"])
    assert found and passage.startswith("... ") and "The Director will:" in passage and ">> (a) Review logs monthly. <<" in passage
    assert len(passage) < 700  # only the tail, not the whole previous chunk
    plain, _ = A.build_passage("(a) Review logs monthly.", chunk, prev, flags=[])
    assert "The Director will:" not in plain


def test_missing_chunk_or_unlocated_quote_is_reported_not_hidden():
    assert A.build_passage("anything", None) == ("", False)
    passage, found = A.build_passage("text that is not there", {"raw_text": "The chunk says something else."})
    assert not found and passage == "The chunk says something else."


def test_generate_adds_the_audit_layout_and_flags_a_missing_chunk_file(tmp_path):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "(a) Review logs monthly.", "source_ref": "2.1", "chunk_id": 2, "section_title_path": ["ROLES AND RESPONSIBILITIES", "2.1. AF/A3"],
           "domain_tags": ["x"], "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "doc_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    no_chunks = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert no_chunks["passage"] == "" and "no_passage" in no_chunks["item_flags"] and no_chunks["applies_to"] == "AF/A3"
    chunks = [{"chunk_id": 1, "raw_text": "The Director will:"}, {"chunk_id": 2, "raw_text": "(a) Review logs monthly."}]
    (run_dir / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
    result = generate(tmp_path, "doc", "cybersecurity")
    item = result["items"][0]
    assert result["format_version"] == "1.1" and "The Director will:" in item["passage"] and ">> (a) Review logs monthly. <<" in item["passage"]
    assert "no_passage" not in item["item_flags"] and "list_item" in item["item_flags"]
    assert result["summary"]["items_with_flags"] == 1


def test_chunk_file_is_found_when_the_document_name_contains_requirements(tmp_path):
    run_dir = tmp_path / "policy_requirements_v1_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "Review logs monthly.", "source_ref": "2.1", "chunk_id": 1, "section_title_path": ["Logs"], "domain_tags": ["x"],
           "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "policy_requirements_v1_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    (run_dir / "policy_requirements_v1_chunks.jsonl").write_text(json.dumps({"chunk_id": 1, "raw_text": "Review logs monthly."}) + "\n")
    item = generate(tmp_path, "policy_requirements_v1", "cybersecurity")["items"][0]
    assert "no_passage" not in item["item_flags"] and ">> Review logs monthly. <<" in item["passage"]


def test_parent_paragraph_comes_from_the_documents_own_numbering():
    units = ["2.5.1.1.7. Directorate of Security (SAF/AAZ).", "2.5.1.1.7.1. Coordinates AF-wide activities.", "2.17. MAJCOM/DRUs.", "2.18. Responsibilities."]
    pm = A.paragraph_map(units)
    assert pm["2.5.1.1.7"] == "Directorate of Security (SAF/AAZ)."
    assert A.parent_paragraph("2.5.1.1.7.2", pm) == ("2.5.1.1.7", "Directorate of Security (SAF/AAZ).")
    assert A.parent_paragraph("2.17.22", pm) == ("2.17", "MAJCOM/DRUs.")
    assert A.parent_paragraph("2.5.1.1.7.1.1.1", pm)[0] == "2.5.1.1.7.1"  # the nearest ancestor that exists
    assert A.parent_paragraph("2.18.1", pm) == ("", "")  # a generic label names no one
    assert A.parent_paragraph("(T-2)", pm) == ("", "") and A.parent_paragraph("Table 3.1", pm) == ("", "") and A.parent_paragraph("", pm) == ("", "")
    assert A.parent_paragraph("3.1", pm) == ("", "")  # a two-part number has only a top-level parent, which is the section path


def test_generate_fills_the_parent_paragraph_from_headings_and_chunk_text(tmp_path):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "Coordinates AF-wide CNDSP activities in accordance with DoDD O-8530.1.", "source_ref": "2.5.1.1.7.1", "chunk_id": 1,
           "section_title_path": ["ROLES", "2.5.1.1.7. Directorate of Security (SAF/AAZ)."], "domain_tags": ["x"], "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "doc_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    chunk = {"chunk_id": 1, "raw_text": "2.5.1.1.7.1. Coordinates AF-wide CNDSP activities in accordance with DoDD O-8530.1.", "section_title_path": rec["section_title_path"]}
    (run_dir / "doc_chunks.jsonl").write_text(json.dumps(chunk) + "\n")
    item = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert item["parent_ref"] == "2.5.1.1.7" and item["parent_text"].startswith("Directorate of Security")
