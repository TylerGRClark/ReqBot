"""Reference labels beside a document (core/reference_lookup.py) and their use in a row's citation
(services/checklist_service.py): built once from the PDF reader's items under a document style,
read when the checklist or the search index works out a citation.

The rule that protects existing documents: a label only replaces a BLANK or INFERRED citation,
never one read from the row itself, and a document with no labels file is cited exactly as before."""
import json
from pathlib import Path

import pytest

from core import reference_lookup as RL
from core.doc_styles import load_style
from services.checklist_service import generate, requirement_citations

QUOTE_A = "The Director, NSA will provide communications security keying material for cryptographic products."
QUOTE_B = "The Joint Staff J-6 will process the request and prepare it for the MC4EB board."
REPEATED = "In addition to the responsibilities in Paragraph two the official shall also coordinate."


def _items():
    """Reader items for a small outline document: an enclosure, a numbered list, a repeated sentence."""
    def h(t, p): return {"kind": "heading", "text": t, "page": p}
    def li(m, t, p): return {"kind": "list_item", "text": t, "marker": m, "page": p}
    return [
        h("ENCLOSURE A", 2),
        li("5.", "Director, NSA (DIRNSA) will:", 2),
        li("a.", "Plan and budget for the work.", 2),
        li("b.", QUOTE_A, 2),
        li("7.", "Joint Staff J-6 will:", 3),
        li("a.", QUOTE_B, 3),
        h("ENCLOSURE B", 5),
        li("3.", "Prior to submitting a request:", 5),
        li("a.", REPEATED, 5),
        li("4.", "Process to request an extension:", 6),
        li("a.", REPEATED, 6),
    ]


def _lookup():
    return RL.ReferenceLookup(RL.build_sidecar(_items(), load_style("outline-dod")))


# --- building and looking up --------------------------------------------------------------------

def test_outline_dod_style_is_shipped_and_has_a_grammar():
    style = load_style("outline-dod")
    assert style["reference_grammar"]["enclosure_pattern"]
    assert "outline-dod" in __import__("core.doc_styles", fromlist=["x"]).list_styles()


def test_the_general_style_cannot_build_labels():
    with pytest.raises(ValueError, match="no reference grammar"):
        RL.build_sidecar(_items(), load_style("general"))


def test_a_quote_is_found_under_its_reference():
    lookup = _lookup()
    assert lookup.find(QUOTE_A, 2, 2) == "Encl A, 5.b"
    assert lookup.find(QUOTE_B, 3, 3) == "Encl A, 7.a"


def test_a_leading_list_marker_in_the_quote_is_ignored():
    assert _lookup().find("b.  " + QUOTE_A, 2, 2) == "Encl A, 5.b"
    assert _lookup().find("- (1) " + QUOTE_B, 3, 3) == "Encl A, 7.a"


def test_a_repeated_sentence_is_found_by_its_pages():
    lookup = _lookup()
    assert lookup.find(REPEATED, 5, 5) == "Encl B, 3.a"
    assert lookup.find(REPEATED, 6, 6) == "Encl B, 4.a"


def test_a_repeated_sentence_with_no_pages_to_tell_them_apart_is_not_guessed():
    assert _lookup().find(REPEATED) == ""
    assert _lookup().find(REPEATED, 5, 6) == ""


def test_a_quote_outside_its_pages_is_not_found():
    assert _lookup().find(QUOTE_A, 9, 9) == ""


def test_a_short_or_empty_quote_is_never_matched():
    assert _lookup().find("Plan and budget.", 2, 2) == ""
    assert _lookup().find("", 2, 2) == ""
    assert _lookup().find(None, 2, 2) == ""


def test_a_quote_that_is_not_in_the_document_is_blank():
    assert _lookup().find("A sentence the document never contained anywhere at all.", 2, 3) == ""


def test_pages_one_off_are_still_searched():
    assert _lookup().find(QUOTE_B, 2, 2) == "Encl A, 7.a"   # the chunk says page 2, the quote starts on page 3


def test_items_with_no_text_are_dropped_from_the_file():
    content = RL.build_sidecar([{"kind": "text", "text": "  ...  "}, {"kind": "text", "text": "Real words here."}], load_style("outline-dod"))
    assert len(content["items"]) == 1
    assert content["style"] == {"name": "outline-dod", "version": "1"}


@pytest.mark.parametrize("label,kind", [("DocItemLabel.SECTION_HEADER", "heading"), ("DocItemLabel.LIST_ITEM", "list_item"),
                                        ("DocItemLabel.TEXT", "text"), ("DocItemLabel.TABLE", "other"), ("picture", "other")])
def test_reader_labels_map_to_grammar_kinds(label, kind):
    assert RL.item_kind(label) == kind


# --- the file beside the document ----------------------------------------------------------------

def test_a_missing_file_means_no_lookup(tmp_path):
    assert RL.load_lookup(tmp_path, "doc") is None


def test_a_damaged_or_unknown_file_is_ignored_not_fatal(tmp_path):
    p = RL.sidecar_path(tmp_path, "doc")
    p.write_text("{not json", encoding="utf-8")
    assert RL.load_lookup(tmp_path, "doc") is None
    p.write_text(json.dumps({"format": 99, "items": []}), encoding="utf-8")
    assert RL.load_lookup(tmp_path, "doc") is None
    p.write_text("[1]", encoding="utf-8")
    assert RL.load_lookup(tmp_path, "doc") is None


@pytest.mark.parametrize("content", [
    {"format": 1, "items": None},                                          # not a list
    {"format": 1},                                                         # no items
    {"format": 1, "items": "oops"},
    {"format": 1, "items": [{"p": 2, "n": "textofthequote"}]},             # no reference
    {"format": 1, "items": [{"p": 2, "r": "5.a"}]},                        # no text
    {"format": 1, "items": [{"p": "2", "n": "text", "r": "5.a"}]},         # page is not a number
    {"format": 1, "items": [{"p": True, "n": "text", "r": "5.a"}]},
    {"format": 1, "items": [{"p": 2, "n": 5, "r": "5.a"}]},                # text is not a string
    {"format": 1, "items": [{"p": 2, "n": "text", "r": None}]},
    {"format": 1, "items": ["not an item"]},
    {"format": 1, "items": [{"p": 2, "n": "text", "r": "5.a"}, None]},     # one bad item spoils the file
])
def test_a_file_of_the_wrong_shape_is_ignored_not_fatal(tmp_path, content):
    """Valid JSON with the right format number but the wrong contents must leave citations as before (Codex, PR 393)."""
    RL.sidecar_path(tmp_path, "doc").write_text(json.dumps(content), encoding="utf-8")
    assert RL.load_lookup(tmp_path, "doc") is None


def test_a_wrong_shaped_file_leaves_the_checklist_and_the_index_citations_alone(tmp_path):
    run = _doc(tmp_path / "a", labels=False)
    for content in ({"format": 1, "items": None}, {"format": 1, "items": [{"p": 2, "n": "planprogramandbudgetforthetransformation"}]}):
        RL.sidecar_path(run, "doc").write_text(json.dumps(content), encoding="utf-8")
        assert _cites(run) == _cites(_doc(tmp_path / f"b{len(str(content))}", labels=False))
        generate(tmp_path / "a", "doc", "cybersecurity")   # the checklist builds too


def test_the_file_round_trips(tmp_path):
    content = RL.build_sidecar(_items(), load_style("outline-dod"))
    RL.write_sidecar(RL.sidecar_path(tmp_path, "doc"), content)
    assert RL.load_lookup(tmp_path, "doc").find(QUOTE_A, 2, 2) == "Encl A, 5.b"


# --- in the checklist and the search index -------------------------------------------------------

CHUNKS = [
    {"chunk_id": 0, "raw_text": "Front page of the instruction.", "section_title_path": ["Front"], "page_start": 1, "page_end": 1},
    {"chunk_id": 1, "raw_text": "b. " + QUOTE_A, "section_title_path": ["Responsibilities"], "page_start": 2, "page_end": 2},
    {"chunk_id": 2, "raw_text": "1.2. Units will report incidents within twenty four hours of discovery.", "section_title_path": ["Reporting"], "page_start": 2, "page_end": 2},
]


def _req(rid, quote, ref, chunk_id, **extra):
    return {"requirement_id": rid, "source_quote": quote, "source_ref": ref, "chunk_id": chunk_id, "source_pdf": "doc.pdf", "document_id": "d1",
            "section_title_path": CHUNKS[chunk_id]["section_title_path"], "page_start": CHUNKS[chunk_id]["page_start"],
            "page_end": CHUNKS[chunk_id]["page_end"], **extra}


REQS = [
    _req("REQ-blank", QUOTE_A, "", 1),
    _req("REQ-numbered", "Units will report incidents within twenty four hours of discovery.", "1.2", 2),
]


def _doc(tmp_path: Path, labels: bool) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    (run / "doc_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in REQS), encoding="utf-8")
    (run / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in CHUNKS), encoding="utf-8")
    if labels:
        RL.write_sidecar(RL.sidecar_path(run, "doc"), RL.build_sidecar(_items(), load_style("outline-dod")))
    return run


def _cites(run):
    return requirement_citations(run / "doc_requirements_normalized.jsonl")


def test_without_a_labels_file_citations_are_exactly_as_before(tmp_path):
    cites = _cites(_doc(tmp_path, labels=False))
    assert cites["REQ-blank"] != "Encl A, 5.b"
    assert cites["REQ-numbered"] == "1.2"


def test_a_label_replaces_a_blank_or_inferred_citation(tmp_path):
    cites = _cites(_doc(tmp_path, labels=True))
    assert cites["REQ-blank"] == "Encl A, 5.b"


def test_a_label_never_replaces_a_citation_read_from_the_row_itself(tmp_path):
    """The numbered row keeps "1.2" even though the labels file does not know that sentence."""
    assert _cites(_doc(tmp_path, labels=True))["REQ-numbered"] == "1.2"


def test_the_sheet_and_the_index_use_the_same_label(tmp_path):
    run = _doc(tmp_path, labels=True)
    env = generate(tmp_path, "doc", "cybersecurity")
    on_sheet = {i["requirement_ids"][0]: i["citation"] for i in env["items"]}
    assert on_sheet == _cites(run)
    assert on_sheet["REQ-blank"] == "Encl A, 5.b"


def test_a_damaged_labels_file_leaves_the_citations_alone(tmp_path):
    run = _doc(tmp_path, labels=False)
    RL.sidecar_path(run, "doc").write_text("{broken", encoding="utf-8")
    assert _cites(run) == _cites(_doc_copy_without_labels(tmp_path))


def _doc_copy_without_labels(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    return _doc(other, labels=False)


# --- a label may only refine an inferred number, and the section heading column is unchanged -----

from services.checklist_service import _label_fits  # noqa: E402


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
def test_a_label_only_refines_an_inferred_number(old, label, ok):
    assert _label_fits(old, label) is ok


MIXED_CHUNKS = [
    {"chunk_id": 0, "raw_text": "2.1. COMMANDERS. Commanders will:\n- Ensure plans exist.\n- Test plans annually and report the result to the wing commander.",
     "section_title_path": ["2. Responsibilities"], "page_start": 4, "page_end": 4},
]
MIXED_QUOTE = "Test plans annually and report the result to the wing commander."
MIXED_REQS = [{"requirement_id": "REQ-m", "source_quote": MIXED_QUOTE, "source_ref": "", "chunk_id": 0, "source_pdf": "doc.pdf", "document_id": "d1",
               "section_title_path": ["2. Responsibilities"], "page_start": 4, "page_end": 4}]
MIXED_ITEMS = [
    {"kind": "heading", "text": "2.1.  COMMANDERS.", "page": 4},
    {"kind": "list_item", "text": "Ensure plans exist.", "marker": "a.", "page": 4},
    {"kind": "list_item", "text": MIXED_QUOTE, "marker": "b.", "page": 4},
]


def _mixed(tmp_path, labels):
    tmp_path.mkdir(exist_ok=True)
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    (run / "doc_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in MIXED_REQS), encoding="utf-8")
    (run / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in MIXED_CHUNKS), encoding="utf-8")
    if labels:
        RL.write_sidecar(RL.sidecar_path(run, "doc"), RL.build_sidecar(MIXED_ITEMS, load_style("outline-dod")))
    return tmp_path


def test_an_inferred_number_becomes_the_exact_paragraph_and_the_heading_column_is_kept(tmp_path):
    plain = generate(_mixed(tmp_path / "a", labels=False), "doc", "cybersecurity")["items"][0]
    labeled = generate(_mixed(tmp_path / "b", labels=True), "doc", "cybersecurity")["items"][0]
    assert plain["citation"] == "2.1 (inferred)"
    assert labeled["citation"] == "2.1.b"
    assert labeled["section_heading"] == plain["section_heading"] != ""
    assert {k: v for k, v in labeled.items() if k != "citation"} == {k: v for k, v in plain.items() if k != "citation"}


def test_a_label_from_the_wrong_section_is_not_used(tmp_path):
    wrong = [{"kind": "heading", "text": "5.9.  OTHER.", "page": 4}, {"kind": "list_item", "text": MIXED_QUOTE, "marker": "b.", "page": 4}]
    root = _mixed(tmp_path, labels=False)
    run = next(root.iterdir())
    RL.write_sidecar(RL.sidecar_path(run, "doc"), RL.build_sidecar(wrong, load_style("outline-dod")))
    assert generate(root, "doc", "cybersecurity")["items"][0]["citation"] == "2.1 (inferred)"
