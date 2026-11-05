"""The stored `reference` field on a requirement record (docs/DOCUMENT_STYLES.md) and how a row's citation uses it.

The rule that protects existing documents: a record's reference only replaces a BLANK or INFERRED citation, never one read from the row itself, a "Front matter" / "Figure" one, or a table's,
and an inferred number is only ever made more exact. A record with no `reference` is cited exactly as before."""
import json
from pathlib import Path

import pytest

from services.checklist_service import _label_fits, generate, requirement_citations

QUOTE = "The Director, NSA will provide communications security keying material for cryptographic products."
CHUNKS = [
    {"chunk_id": 0, "raw_text": "Front page of the instruction.", "section_title_path": ["Front"], "page_start": 1, "page_end": 1},
    {"chunk_id": 1, "raw_text": "1.2. Units will report incidents within twenty four hours of discovery.", "section_title_path": ["Reporting"], "page_start": 2, "page_end": 2},
    {"chunk_id": 2, "raw_text": "b. " + QUOTE, "section_title_path": ["Responsibilities"], "page_start": 2, "page_end": 2},
]


def _req(rid, quote, source_ref, chunk_id, **extra):
    return {"requirement_id": rid, "source_quote": quote, "source_ref": source_ref, "chunk_id": chunk_id, "source_pdf": "doc.pdf", "document_id": "d1",
            "section_title_path": CHUNKS[chunk_id]["section_title_path"], "page_start": CHUNKS[chunk_id]["page_start"], "page_end": CHUNKS[chunk_id]["page_end"], **extra}


def _doc(base: Path, reqs: list[dict], chunks=CHUNKS) -> Path:
    run = base / "doc_20260101_120000"
    run.mkdir(parents=True)
    (run / "doc_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reqs), encoding="utf-8")
    (run / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    return run / "doc_requirements_normalized.jsonl"


def test_a_reference_replaces_a_blank_citation(tmp_path):
    cites = requirement_citations(_doc(tmp_path, [_req("REQ-1", QUOTE, "", 2, reference="Encl A, 5.b")]))
    assert cites["REQ-1"] == "Encl A, 5.b"


def test_without_a_reference_the_citation_is_exactly_as_before(tmp_path):
    with_field = requirement_citations(_doc(tmp_path / "a", [_req("REQ-1", QUOTE, "", 2, reference="")]))
    without = requirement_citations(_doc(tmp_path / "b", [_req("REQ-1", QUOTE, "", 2)]))
    assert with_field == without
    assert without["REQ-1"] != "Encl A, 5.b"


def test_a_reference_never_replaces_a_citation_read_from_the_row_itself(tmp_path):
    req = _req("REQ-n", "Units will report incidents within twenty four hours of discovery.", "1.2", 1, reference="Encl A, 5.b")
    assert requirement_citations(_doc(tmp_path, [req]))["REQ-n"] == "1.2"


def test_a_reference_does_not_replace_front_matter(tmp_path):
    quote = "Compliance with this publication is mandatory for all units and personnel."
    chunks = [{"chunk_id": 0, "raw_text": quote, "section_title_path": ["BY ORDER"], "page_start": 1, "page_end": 1}, CHUNKS[1]]
    req = _req("REQ-f", quote, "", 0, reference="Encl A, 5.a")
    req["section_title_path"] = ["BY ORDER"]
    assert requirement_citations(_doc(tmp_path, [req], chunks))["REQ-f"] == "Front matter"


def test_the_sheet_and_the_index_use_the_same_label(tmp_path):
    path = _doc(tmp_path, [_req("REQ-1", QUOTE, "", 2, reference="Encl A, 5.b"), _req("REQ-n", "Units will report incidents within twenty four hours of discovery.", "1.2", 1)])
    on_sheet = {i["requirement_ids"][0]: i["citation"] for i in generate(tmp_path, "doc", "cybersecurity")["items"]}
    assert on_sheet == requirement_citations(path)


@pytest.mark.parametrize("old,label,ok", [
    ("", "Encl A, 5.b", True),                    # nothing to contradict
    ("2.1 (inferred)", "2.1.a", True),            # more exact
    ("2.1 (inferred)", "2.1(3)", True),
    ("2.1 (inferred)", "2.1", True),
    ("3.3 (inferred)", "2.2", False),             # a different section: keep the old one
    ("2.1 (inferred)", "2.10.b", False),          # "2.1" is not a prefix of "2.10" as a paragraph
    ("3.4.4.2 (inferred)", "3.4.4", False),       # a shallower label is not "more exact"
    ("Front matter", "1.a", False),               # anything not a plain number stays as it is
])
def test_a_reference_only_refines_an_inferred_number(old, label, ok):
    assert _label_fits(old, label) is ok


MIXED_CHUNK = {"chunk_id": 0, "raw_text": "2.1. COMMANDERS. Commanders will:\n- Ensure plans exist.\n- Test plans annually and report the result to the wing commander.",
               "section_title_path": ["2. Responsibilities"], "page_start": 4, "page_end": 4}
MIXED_QUOTE = "Test plans annually and report the result to the wing commander."


def _mixed(base: Path, **extra):
    req = {"requirement_id": "REQ-m", "source_quote": MIXED_QUOTE, "source_ref": "", "chunk_id": 0, "source_pdf": "doc.pdf", "document_id": "d1",
           "section_title_path": ["2. Responsibilities"], "page_start": 4, "page_end": 4, **extra}
    _doc(base, [req], [MIXED_CHUNK])
    return generate(base, "doc", "cybersecurity")["items"][0]


def test_an_inferred_number_becomes_the_exact_paragraph_and_every_other_column_is_unchanged(tmp_path):
    plain = _mixed(tmp_path / "a")
    labeled = _mixed(tmp_path / "b", reference="2.1.b")
    assert plain["citation"] == "2.1 (inferred)" and labeled["citation"] == "2.1.b"
    assert labeled["section_heading"] == plain["section_heading"] != ""      # the heading column is looked up from the old citation
    assert {k: v for k, v in labeled.items() if k != "citation"} == {k: v for k, v in plain.items() if k != "citation"}


def test_a_reference_from_the_wrong_section_is_not_used(tmp_path):
    assert _mixed(tmp_path, reference="5.9.b")["citation"] == "2.1 (inferred)"
