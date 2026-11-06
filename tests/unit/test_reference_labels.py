"""pipeline/reference_labels.py: labeling the PDF reader's items under a document style, recording where each sits in a chunk's text, and reading the reference back for a clause's offset."""
import inspect
from types import SimpleNamespace

import pytest

from core.doc_styles import load_style
from pipeline import chunk_text
from pipeline import reference_labels as RLB


def item(label, text, page=1, marker=None, ref=None):
    return SimpleNamespace(label=label, text=text, marker=marker, self_ref=ref, prov=[SimpleNamespace(page_no=page)])


class FakeDoc:
    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        return iter((i, 0) for i in self._items)


QUOTE = "The Director shall maintain the central repository of service level agreements."
ITEMS = [
    item("DocItemLabel.SECTION_HEADER", "ENCLOSURE 2", ref="#/texts/0"),
    item("DocItemLabel.LIST_ITEM", "DIRECTOR, DISA.", marker="2.", ref="#/texts/1"),
    item("DocItemLabel.LIST_ITEM", "Establish repositories.", marker="a.", ref="#/texts/2"),
    item("DocItemLabel.LIST_ITEM", QUOTE, marker="b.", ref="#/texts/3"),
    item("DocItemLabel.PICTURE", "", ref="#/pictures/0"),
    item("DocItemLabel.TEXT", "Unnumbered closing remark.", ref="#/texts/4"),
]


def test_reader_labels_map_to_grammar_kinds():
    assert [RLB.item_kind(x) for x in ("DocItemLabel.SECTION_HEADER", "DocItemLabel.LIST_ITEM", "DocItemLabel.TEXT", "DocItemLabel.TABLE", "picture")] == \
        ["heading", "list_item", "text", "other", "other"]


def test_every_numbered_item_gets_its_reference():
    refs = RLB.label_document(FakeDoc(ITEMS), load_style("outline-dod"))
    assert refs["#/texts/1"] == "Encl 2, 2"
    assert refs["#/texts/3"] == "Encl 2, 2.b"
    assert refs["#/texts/4"] == "Encl 2, 2.b"          # an unnumbered paragraph inherits the reference it follows
    assert "#/pictures/0" not in refs or refs["#/pictures/0"]


def test_the_general_style_cannot_label():
    with pytest.raises(ValueError, match="no reference grammar"):
        RLB.label_document(FakeDoc(ITEMS), load_style("general"))


# --- where each item sits in a chunk's text ------------------------------------------------------

def chunk_of(*items):
    return SimpleNamespace(meta=SimpleNamespace(doc_items=list(items)))


def test_spans_are_offsets_into_the_raw_text_and_start_at_the_line_start():
    a, b = ITEMS[2], ITEMS[3]
    raw = "- a.  " + a.text + "\n- b.  " + b.text
    spans = RLB.spans_for_chunk(chunk_of(a, b), None, raw, {"#/texts/2": "Encl 2, 2.a", "#/texts/3": "Encl 2, 2.b"})
    assert [s[2] for s in spans] == ["Encl 2, 2.a", "Encl 2, 2.b"]
    assert raw[spans[1][0]:spans[1][1]] == "- b.  " + b.text            # the list marker is inside the span
    assert spans[0][1] <= spans[1][0]                                   # spans do not overlap
    assert RLB.reference_at(spans, raw.index(QUOTE)) == "Encl 2, 2.b"   # a clause that starts after the marker
    assert RLB.reference_at(spans, raw.index("- b.")) == "Encl 2, 2.b"  # and one that starts with it


def test_a_sentence_repeated_in_one_chunk_is_matched_in_order():
    first = item("DocItemLabel.LIST_ITEM", "Same words here.", marker="a.", ref="#/texts/10")
    second = item("DocItemLabel.LIST_ITEM", "Same words here.", marker="b.", ref="#/texts/11")
    raw = "- a.  Same words here.\n- b.  Same words here."
    spans = RLB.spans_for_chunk(chunk_of(first, second), None, raw, {"#/texts/10": "2.a", "#/texts/11": "2.b"})
    assert RLB.reference_at(spans, 10) == "2.a"
    assert RLB.reference_at(spans, raw.rindex("Same")) == "2.b"


def test_headings_unlabeled_items_and_items_not_in_the_text_are_skipped():
    heading = item("DocItemLabel.SECTION_HEADER", "2.10.  DUTIES", ref="#/texts/20")
    plain = item("DocItemLabel.TEXT", "No label for me.", ref="#/texts/21")
    missing = item("DocItemLabel.LIST_ITEM", "Words that are not in the chunk.", ref="#/texts/22")
    kept = item("DocItemLabel.LIST_ITEM", "Kept text.", ref="#/texts/23")
    raw = "No label for me.\n- a.  Kept text."
    spans = RLB.spans_for_chunk(chunk_of(heading, plain, missing, kept), None, raw,
                                {"#/texts/20": "2.10", "#/texts/22": "2.10.z", "#/texts/23": "2.10.a"})
    assert [s[2] for s in spans] == ["2.10.a"]


def test_a_generic_reference_resolves_through_the_document():
    class Generic:                      # a merged chunk's item: only a self_ref, no text of its own
        label = "DocItemLabel.LIST_ITEM"
        self_ref = "#/texts/30"
    assert RLB.spans_for_chunk(chunk_of(Generic()), None, "- a.  x", {"#/texts/30": "2.a"}) == []   # unresolvable: skipped, never guessed


@pytest.mark.parametrize("spans,offset,expected", [
    ([[0, 10, "5.a"], [11, 20, "5.b"]], 0, "5.a"),
    ([[0, 10, "5.a"], [11, 20, "5.b"]], 9, "5.a"),
    ([[0, 10, "5.a"], [11, 20, "5.b"]], 10, ""),      # the newline between two items
    ([[0, 10, "5.a"], [11, 20, "5.b"]], 19, "5.b"),
    ([[0, 10, "5.a"], [11, 20, "5.b"]], 20, ""),      # past the end
    ([[0, 10, "5.a"]], -1, ""),
    ([[0, 10, "5.a"]], None, ""),                      # a record with no offset
    ([[0, 10, "5.a"]], True, ""),
    (None, 3, ""), ("oops", 3, ""), ([], 3, ""),
    ([None], 3, ""), ([[0, 10]], 3, ""), ([[0, 10, 7]], 3, ""),
])
def test_reference_at(spans, offset, expected):
    assert RLB.reference_at(spans, offset) == expected


def test_chunking_accepts_item_references_and_leaves_the_default_alone():
    sig = inspect.signature(chunk_text.run_structure_aware)
    assert sig.parameters["item_references"].default is None


# --- adding references to an ingested document ---------------------------------------------------

def place(chunk_id, text, page=1, section="S", **extra):
    return {"chunk_id": chunk_id, "raw_text": text, "page_start": page, "page_end": page, "section_ref_path": [section], "section_title_path": [section], **extra}


OLD_CHUNKS = [place(0, "- a.  one"), place(1, "- b.  two"), place(2, "- c.  three")]


def test_merge_adds_spans_where_the_text_matches_and_keeps_everything_else():
    new = [place(0, "- a.  one", reference_spans=[[0, 9, "5.a"]]), place(1, "- b.  two"), place(2, "- c.  three", reference_spans=[[0, 11, "5.c"]])]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert merged[0]["reference_spans"] == [[0, 9, "5.a"]] and "reference_spans" not in merged[1] and merged[2]["reference_spans"] == [[0, 11, "5.c"]]
    assert [c["raw_text"] for c in merged] == [c["raw_text"] for c in OLD_CHUNKS]
    assert report == {"stored_chunks": 3, "fresh_chunks": 3, "matched": 3, "unmatched_stored": 0}


def test_chunks_are_lined_up_by_text_not_by_id():
    """A skipped section in the middle shifts the fresh ids; the spans still land on the right stored chunk."""
    new = [place(0, "- a.  one", reference_spans=[[0, 9, "5.a"]]), place(1, "- c.  three", reference_spans=[[0, 11, "5.c"]])]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert merged[2]["reference_spans"] == [[0, 11, "5.c"]] and "reference_spans" not in merged[1]
    assert report["unmatched_stored"] == 1


def test_a_stored_chunk_whose_text_moved_gets_no_spans_instead_of_wrong_ones():
    new = [place(0, "- a.  one", reference_spans=[[0, 9, "5.a"]]), place(1, "- b.  TWO", reference_spans=[[0, 9, "9.z"]]), place(2, "- c.  three")]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert "reference_spans" not in merged[1] and merged[1]["raw_text"] == "- b.  two"
    assert report["matched"] == 2


def test_extra_stored_chunks_at_the_end_are_left_alone():
    merged, report = RLB.merge_spans(OLD_CHUNKS, [place(0, "- a.  one", reference_spans=[[0, 9, "5.a"]])])
    assert merged[0]["reference_spans"] == [[0, 9, "5.a"]] and report["unmatched_stored"] == 2


def test_merge_refuses_when_nothing_matches():
    with pytest.raises(ValueError, match="full re-run"):
        RLB.merge_spans(OLD_CHUNKS, [place(0, "entirely different")])


def test_only_the_reference_may_change():
    old = [{"requirement_id": "R1", "source_quote": "q", "run_timestamp": "t1", "reference": ""}]
    RLB.assert_only_reference_added(old, [{"requirement_id": "R1", "source_quote": "q", "run_timestamp": "t2", "reference": "5.a"}])
    RLB.assert_only_reference_added([{"requirement_id": "R1", "source_quote": "q"}], [{"requirement_id": "R1", "source_quote": "q", "reference": "5.a"}])  # a record with no field yet
    for bad in ([{"requirement_id": "R1", "source_quote": "CHANGED", "reference": "5.a"}],
                [{"requirement_id": "R2", "source_quote": "q"}],
                [{"requirement_id": "R1", "source_quote": "q"}, {"requirement_id": "R3"}]):
        with pytest.raises(ValueError):
            RLB.assert_only_reference_added(old, bad)


def test_the_same_sentence_in_two_places_is_not_stamped_with_the_other_ones_reference():
    """Codex, PR 393: two stored chunks with identical text under different enclosures, only the second kept today."""
    sentence = "- a.  The PO will submit the request."
    stored = [place(0, sentence, page=7, section="ENCLOSURE A"), place(1, sentence, page=13, section="ENCLOSURE B")]
    fresh = [place(0, sentence, page=13, section="ENCLOSURE B", reference_spans=[[0, 37, "Encl B, 3.a"]])]
    merged, report = RLB.merge_spans(stored, fresh)
    assert "reference_spans" not in merged[0]                       # enclosure A must not get enclosure B's reference
    assert merged[1]["reference_spans"] == [[0, 37, "Encl B, 3.a"]]
    assert report["matched"] == 1 and report["unmatched_stored"] == 1


@pytest.mark.parametrize("field,value", [("page_start", 9), ("page_end", 9), ("section_ref_path", ["X"]), ("section_title_path", ["X"])])
def test_a_chunk_that_moved_pages_or_sections_is_left_unstamped(field, value):
    fresh = place(0, "- a.  one", reference_spans=[[0, 9, "5.a"]])
    fresh[field] = value
    with pytest.raises(ValueError):          # nothing else matches, so the whole document is refused rather than guessed at
        RLB.merge_spans([place(0, "- a.  one")], [fresh])


# --- tables: step over the grid ------------------------------------------------------------------

class FakeTable:
    label = "DocItemLabel.TABLE"
    self_ref = "#/tables/0"

    def export_to_markdown(self, doc=None):
        return "| Action | Owner |\n| --- | --- |\n| Units shall report incidents. | Unit |"


def test_a_paragraph_that_repeats_a_table_cell_is_matched_after_the_table():
    """Codex, PR 393: the table has no text of its own, so the cursor used to stay before the grid."""
    sentence = "Units shall report incidents."
    para = item("DocItemLabel.LIST_ITEM", sentence, marker="a.", ref="#/texts/40")
    raw = FakeTable().export_to_markdown() + "\n- a.  " + sentence
    spans = RLB.spans_for_chunk(chunk_of(FakeTable(), para), None, raw, {"#/texts/40": "Encl 2, 2.a"})
    assert len(spans) == 1
    assert raw[spans[0][0]:spans[0][1]] == "- a.  " + sentence          # the paragraph, not the table cell
    assert spans[0][0] > raw.index("Unit |")


def test_tables_and_pictures_carry_no_reference_of_their_own():
    doc = FakeDoc([item("DocItemLabel.LIST_ITEM", "DIRECTOR.", marker="2.", ref="#/texts/1"), item("DocItemLabel.TABLE", "", ref="#/tables/0"),
                   item("DocItemLabel.PICTURE", "", ref="#/pictures/0")])
    refs = RLB.label_document(doc, load_style("outline-dod"))
    assert "#/tables/0" not in refs and "#/pictures/0" not in refs and refs["#/texts/1"] == "2"


def test_a_document_with_an_enriched_or_gated_file_is_refused(tmp_path):
    """Codex, PR 393: rewriting only the normalized file would make it the freshest and silently drop the enrichment."""
    from pathlib import Path
    for tier in ("enriched", "gated"):
        run = tmp_path / tier
        run.mkdir()
        for name in ("chunks", "extracted_requirements", "requirements_normalized"):
            (run / f"doc_{name}.jsonl").write_text("{}\n", encoding="utf-8")
        (run / f"doc_requirements_{tier}.jsonl").write_text("{}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="enriched or gated"):
            RLB.add_references(Path("doc.pdf"), run, "outline-dod", "doc")


# --- tables of controls in a document ------------------------------------------------------------------------------------------

class ControlTable:
    label = "DocItemLabel.TABLE"

    def __init__(self, ref, markdown):
        self.self_ref = ref
        self._md = markdown
        self.prov = [SimpleNamespace(page_no=85)]

    def export_to_markdown(self, doc=None):
        return self._md


T1 = "| ID | Control Text |\n|---|---|\n| IA-1 | a. [Assignment: roles] |\n| IA-1 | b. [Assignment: frequency] |"
T2 = "| ID | Control Text |\n|---|---|\n| | continuation of IA-1 |\n| IA-4 | [Assignment: time period] |"


def test_a_table_of_controls_maps_to_one_reference_per_line_with_the_id_carried_across_tables():
    doc = FakeDoc([ControlTable("#/tables/0", T1), ControlTable("#/tables/1", T2)])
    refs = RLB.label_document(doc, load_style("control-tables"))
    assert refs["#/tables/0"] == [None, None, "IA-1 a", "IA-1 b"]
    assert refs["#/tables/1"] == [None, None, "IA-1", "IA-4"]          # the blank first cell continues the previous page's control


def test_tables_get_no_reference_under_a_style_without_a_table_pattern():
    doc = FakeDoc([ControlTable("#/tables/0", T1)])
    assert RLB.label_document(doc, load_style("outline-dod")) == {}


def test_spans_for_a_table_are_one_per_row_line_at_the_right_offsets():
    table = ControlTable("#/tables/0", T1)
    raw = "Intro line.\n" + T1
    spans = RLB.spans_for_chunk(chunk_of(table), None, raw, {"#/tables/0": [None, None, "IA-1 a", "IA-1 b"]})
    assert [s[2] for s in spans] == ["IA-1 a", "IA-1 b"]
    for start, end, _ref in spans:
        assert raw[start:end].startswith("| IA-1 |")
    assert RLB.reference_at(spans, raw.index("[Assignment: frequency]")) == "IA-1 b"
    assert RLB.reference_at(spans, raw.index("Intro")) == ""


def test_a_paragraph_after_a_table_of_controls_is_still_matched_after_it():
    table = ControlTable("#/tables/0", T1)
    para = item("DocItemLabel.TEXT", "After the table.", ref="#/texts/50")
    raw = T1 + "\nAfter the table."
    spans = RLB.spans_for_chunk(chunk_of(table, para), None, raw, {"#/tables/0": [None, None, "IA-1 a", "IA-1 b"], "#/texts/50": "Encl 2, 3"})
    assert [s[2] for s in spans] == ["IA-1 a", "IA-1 b", "Encl 2, 3"]


def test_a_table_item_with_an_empty_text_attribute_still_advances_the_cursor():
    """Gemini, PR 394: a table item that also carries text="" must be read by its grid, not skipped."""
    sentence = "Units shall report incidents."
    table = FakeTable()
    table.text = ""
    para = item("DocItemLabel.LIST_ITEM", sentence, marker="a.", ref="#/texts/60")
    raw = FakeTable().export_to_markdown() + "\n- a.  " + sentence
    spans = RLB.spans_for_chunk(chunk_of(table, para), None, raw, {"#/texts/60": "Encl 2, 2.a"})
    assert len(spans) == 1 and spans[0][0] > raw.index("Unit |")
