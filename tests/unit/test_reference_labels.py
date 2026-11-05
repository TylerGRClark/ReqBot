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

OLD_CHUNKS = [{"chunk_id": 0, "raw_text": "- a.  one"}, {"chunk_id": 1, "raw_text": "- b.  two"}, {"chunk_id": 2, "raw_text": "- c.  three"}]


def test_merge_adds_spans_where_the_text_matches_and_keeps_everything_else():
    new = [{"chunk_id": 0, "raw_text": "- a.  one", "reference_spans": [[0, 9, "5.a"]]}, {"chunk_id": 1, "raw_text": "- b.  two"},
           {"chunk_id": 2, "raw_text": "- c.  three", "reference_spans": [[0, 11, "5.c"]]}]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert merged[0]["reference_spans"] == [[0, 9, "5.a"]] and "reference_spans" not in merged[1] and merged[2]["reference_spans"] == [[0, 11, "5.c"]]
    assert [c["raw_text"] for c in merged] == [c["raw_text"] for c in OLD_CHUNKS]
    assert report == {"stored_chunks": 3, "fresh_chunks": 3, "matched": 3, "unmatched_stored": 0}


def test_chunks_are_lined_up_by_text_not_by_id():
    """A skipped section in the middle shifts the fresh ids; the spans still land on the right stored chunk."""
    new = [{"chunk_id": 0, "raw_text": "- a.  one", "reference_spans": [[0, 9, "5.a"]]}, {"chunk_id": 1, "raw_text": "- c.  three", "reference_spans": [[0, 11, "5.c"]]}]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert merged[2]["reference_spans"] == [[0, 11, "5.c"]] and "reference_spans" not in merged[1]
    assert report["unmatched_stored"] == 1


def test_a_stored_chunk_whose_text_moved_gets_no_spans_instead_of_wrong_ones():
    new = [{"chunk_id": 0, "raw_text": "- a.  one", "reference_spans": [[0, 9, "5.a"]]}, {"chunk_id": 1, "raw_text": "- b.  TWO", "reference_spans": [[0, 9, "9.z"]]},
           {"chunk_id": 2, "raw_text": "- c.  three"}]
    merged, report = RLB.merge_spans(OLD_CHUNKS, new)
    assert "reference_spans" not in merged[1] and merged[1]["raw_text"] == "- b.  two"
    assert report["matched"] == 2


def test_extra_stored_chunks_at_the_end_are_left_alone():
    merged, report = RLB.merge_spans(OLD_CHUNKS, [{"chunk_id": 0, "raw_text": "- a.  one", "reference_spans": [[0, 9, "5.a"]]}])
    assert merged[0]["reference_spans"] == [[0, 9, "5.a"]] and report["unmatched_stored"] == 2


def test_merge_refuses_when_nothing_matches():
    with pytest.raises(ValueError, match="full re-run"):
        RLB.merge_spans(OLD_CHUNKS, [{"chunk_id": 0, "raw_text": "entirely different"}])


def test_only_the_reference_may_change():
    old = [{"requirement_id": "R1", "source_quote": "q", "run_timestamp": "t1", "reference": ""}]
    RLB.assert_only_reference_added(old, [{"requirement_id": "R1", "source_quote": "q", "run_timestamp": "t2", "reference": "5.a"}])
    RLB.assert_only_reference_added([{"requirement_id": "R1", "source_quote": "q"}], [{"requirement_id": "R1", "source_quote": "q", "reference": "5.a"}])  # a record with no field yet
    for bad in ([{"requirement_id": "R1", "source_quote": "CHANGED", "reference": "5.a"}],
                [{"requirement_id": "R2", "source_quote": "q"}],
                [{"requirement_id": "R1", "source_quote": "q"}, {"requirement_id": "R3"}]):
        with pytest.raises(ValueError):
            RLB.assert_only_reference_added(old, bad)
