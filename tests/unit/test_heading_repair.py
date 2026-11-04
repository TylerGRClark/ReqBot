"""Heading-path repair (services/heading_repair.py): a stale path is rebuilt from the chunk's own paragraph numbers."""
import copy
import json
from pathlib import Path

from services import checklist_service
from services.heading_repair import repair_heading_paths


def _chunk(cid, text, refs, titles):
    return {"chunk_id": cid, "raw_text": text, "section_ref_path": refs, "section_title_path": titles}


def _doc():
    """Three chunks of an AFI-like roles chapter; the parser left chunks 1 and 2 on the 3.6 heading."""
    return [
        _chunk(0, "3.6. Security Control Assessor (SCA). The SCA:\n- 3.6.1. Ensures assessments are done.", ["3.6"], ["3.6. Security Control Assessor (SCA). The SCA:"]),
        _chunk(1, "- 3.9. Information System Owners (ISO). Official responsible for systems.\n- 3.9.1. Must plan the system.", ["3.6"], ["3.6. Security Control Assessor (SCA). The SCA:"]),
        _chunk(2, "- 3.9.4. Reports the security status.\n- 3.9.5. Will manage access.", ["3.6"], ["3.6. Security Control Assessor (SCA). The SCA:"]),
    ]


def test_stale_path_is_rebuilt_from_the_documents_own_heading():
    fixed = repair_heading_paths(_doc())
    assert fixed[1]["section_ref_path"] == ["3.9"]
    assert fixed[1]["section_title_path"][-1].startswith("3.9. Information System Owners (ISO).")
    assert fixed[2]["section_ref_path"] == ["3.9"]


def test_a_chunk_whose_path_already_holds_its_first_paragraph_is_untouched():
    chunks = _doc()
    assert repair_heading_paths(chunks)[0] == chunks[0]


def test_input_is_not_changed():
    chunks = _doc()
    before = copy.deepcopy(chunks)
    repair_heading_paths(chunks)
    assert chunks == before


def test_chunk_without_numbered_text_or_without_a_path_keeps_what_it_has():
    plain = _chunk(0, "Just prose, no paragraph numbers.", ["3.6"], ["3.6. Heading"])
    no_path = _chunk(1, "3.9. Title here. Body text goes on.", [], [])
    assert repair_heading_paths([plain, no_path]) == [plain, no_path]


def test_a_long_sentence_paragraph_is_not_used_as_a_heading():
    chunks = [
        _chunk(0, "2.2.13. AFMC designates the Air Force Nuclear Weapons Center and its integration office as the lead for the program in this instruction.\n- 2.2.13.1. Plans the work.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
        _chunk(1, "- 2.2.13.2. Reports status.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"] == ["2.2.4"]  # the 2.2.13 line reads as a sentence, so the stored path stays


def test_an_instruction_is_not_used_as_a_heading():
    chunks = [
        _chunk(0, "- 2.2.6.2. Ensure the following are done:\n- 2.2.6.2.1. Represent the AF.", ["2.2.4"], ["2.2.4. A5/8 will:"]),
        _chunk(1, "- 2.2.6.2.2. Chair the boards.", ["2.2.4"], ["2.2.4. A5/8 will:"]),
    ]
    assert repair_heading_paths(chunks)[1]["section_ref_path"] == ["2.2.4"]


def test_an_actor_line_ending_in_will_counts_as_a_heading():
    chunks = [
        _chunk(0, "- 5.3.5. AFNWC/NC , as Principal Integrator of the AN/USQ-225, will:\n- 5.3.5.1. Establish a board.", ["5.3.4"], ["5.3.4. AFNC3C will:"]),
        _chunk(1, "- 5.3.5.2. Chair the board.", ["5.3.4"], ["5.3.4. AFNC3C will:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"][-1] == "5.3.5"


def test_load_chunks_returns_the_repaired_paths(tmp_path: Path):
    run = tmp_path / "doc1_20260101_120000"
    run.mkdir()
    (run / "doc1_chunks.jsonl").write_text("\n".join(json.dumps(c) for c in _doc()), encoding="utf-8")
    req = run / "doc1_requirements_normalized.jsonl"
    req.write_text("", encoding="utf-8")
    chunks = checklist_service._load_chunks(req)
    assert chunks[1]["section_ref_path"] == ["3.9"]


def test_a_path_with_fewer_titles_than_refs_does_not_raise():
    chunks = [
        _chunk(0, "3.9. Information System Owners (ISO). Official responsible.\n- 3.9.1. Must plan.", ["3", "3.6"], ["3.6. SCA. The SCA:"]),
        _chunk(1, "- 3.9.4. Reports status.", ["3", "3.6"], ["3.6. SCA. The SCA:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"][-1] == "3.9"
    assert all(fixed[1]["section_title_path"])


def test_a_third_person_duty_sentence_is_not_used_as_a_heading():
    chunks = [
        _chunk(0, "- 2.2.6. Program Manager.\n- 2.2.6.1. Plans the work.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
        _chunk(1, "- 2.2.7.1. Ensures assessments are done.\n- 2.2.7.1.1. Records them.\n- 2.2.7.2. Reports status.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
        _chunk(2, "- 2.2.7.3. Chairs the board.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert not any("Ensures assessments" in t for t in fixed[2]["section_title_path"])


def test_the_paragraph_map_keeps_the_full_paragraph_not_a_shortened_title():
    chunks = [
        _chunk(0, "2.2.6. Program Manager. The PM is responsible for the program.\n- 2.2.6.1. Plans the work.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
        _chunk(1, "- 2.2.6.2. Reports status.", ["2.2.4"], ["2.2.4. AFNWC/NC will:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[0]["section_title_path"][-1].startswith("2.2.6. Program Manager.")
    para = checklist_service._paragraph_map({c["chunk_id"]: c for c in fixed})
    assert "responsible for the program" in para["2.2.6"]


def test_prompt_window_section_identity_ignores_the_repair():
    """A chunk that ends with the next section's lead-in keeps its old path; the chunk after it is repaired.
    The two must still look like one section to the prompt window, or the lead-in is cut off."""
    from services import checklist_audit

    chunks = [
        _chunk(0, "- 3.6.1. Ensures assessments are done.\n3.9. System Owners will:", ["3.6"], ["3.6. Security Control Assessor (SCA). The SCA:"]),
        _chunk(1, "- 3.9.1. Plan the system.", ["3.6"], ["3.6. Security Control Assessor (SCA). The SCA:"]),
    ]
    before = checklist_audit.document_lines({c["chunk_id"]: c for c in chunks})
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"] != chunks[1]["section_ref_path"]  # the repair did change the second chunk
    after = checklist_audit.document_lines({c["chunk_id"]: c for c in fixed})
    assert [line[1] for line in after] == [line[1] for line in before]


def test_an_abbreviation_does_not_end_a_heading_title():
    from services.heading_repair import _title

    assert _title("3.9", "U.S. Air Force commanders will: Plan the work.") == "3.9. U.S. Air Force commanders will:"
    assert _title("3.9", "Information System Owners (ISO). Official responsible for systems.") == "3.9. Information System Owners (ISO)."
    assert _title("3.4", "Alteration/Modification. Intentional alterations are not allowed.") == "3.4. Alteration/Modification."
    assert _title("3.2", "Dr. Smith leads the board. Other text.") == "3.2. Dr. Smith leads the board."


def test_a_chunk_with_a_chapter_title_but_no_numbered_path_gets_one():
    chunks = [
        _chunk(0, "- 4.9. Mobile Computing Devices. Rules for mobile devices.\n- 4.9.1. Configure devices.", [], ["ENDPOINT SECURITY"]),
        _chunk(1, "- 4.9.3. Government-owned devices need approval.\n- 4.9.4. Report loss.", [], ["ENDPOINT SECURITY"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"] == ["4.9"]
    assert fixed[1]["section_title_path"][0] == "ENDPOINT SECURITY"  # the chapter title stays in front
    assert fixed[1]["section_title_path"][-1].startswith("4.9. Mobile Computing Devices.")
    assert fixed[1]["stored_section_ref_path"] == []


def test_a_repaired_path_keeps_its_unnumbered_chapter_title():
    chunks = [
        _chunk(0, "3.6. Security Control Assessor (SCA). The SCA:\n- 3.6.1. Ensures assessments are done.", ["3.6"], ["RMF ROLES AND RESPONSIBILITIES", "3.6. Security Control Assessor (SCA). The SCA:"]),
        _chunk(1, "- 3.9. Information System Owners (ISO). Official responsible.\n- 3.9.1. Must plan.", ["3.6"], ["RMF ROLES AND RESPONSIBILITIES", "3.6. Security Control Assessor (SCA). The SCA:"]),
    ]
    fixed = repair_heading_paths(chunks)
    assert fixed[1]["section_ref_path"] == ["3.9"]
    assert fixed[1]["section_title_path"][0] == "RMF ROLES AND RESPONSIBILITIES"
    assert fixed[1]["section_title_path"][-1].startswith("3.9. Information System Owners")


def test_a_chunk_with_no_numbered_text_and_no_path_is_left_alone():
    chunk = _chunk(0, "Plain prose with no paragraph numbers at all.", [], ["INTRODUCTION"])
    assert repair_heading_paths([chunk]) == [chunk]
