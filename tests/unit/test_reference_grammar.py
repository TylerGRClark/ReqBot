"""Shared reference grammar (core/reference_grammar.py): labels each document item with the
paragraph reference it sits under, from the items in reading order. The fixtures copy the shapes
that real outline-numbered and mixed DoD documents have in the PDF reader's output (list items
that carry a separate marker, headings that carry the number in their text, enclosure headings)."""
import pytest

from core.reference_grammar import Grammar, Item, Ref, label_items, parse_grammar

ENC = r"^ENCLOSURE\s+([A-Z0-9]{1,2})\s*$"
OUTLINE = Grammar(enclosure_pattern=ENC)


def H(text):
    return Item("heading", text)


def L(marker, text="Some duty text."):
    return Item("list_item", text, marker=marker)


def T(text):
    return Item("text", text)


def refs(items, grammar=OUTLINE):
    return [r.text() for r in label_items(items, grammar)]


# --- outline numbering, enclosures -------------------------------------------------------------

def test_outline_label_under_an_enclosure():
    letters = [L(f"{c}.") for c in "abcdefghijk"]
    items = [H("ENCLOSURE A"), L("5.", "Director, NSA will:"), *letters]
    assert refs(items)[-1] == "Encl A, 5.k"


def test_numbering_restarts_in_the_next_enclosure():
    items = [H("ENCLOSURE A"), L("5."), L("a."), H("ENCLOSURE B"), L("3."), L("a.")]
    out = refs(items)
    assert out[2] == "Encl A, 5.a"
    assert out[4] == "Encl B, 3"
    assert out[5] == "Encl B, 3.a"


def test_the_same_enclosure_repeated_does_not_reset_the_numbering():
    """A running header repeats the enclosure heading on every page."""
    items = [H("ENCLOSURE 2"), L("1."), L("a."), H("ENCLOSURE 2"), L("b.")]
    assert refs(items)[-1] == "Encl 2, 1.b"


def test_all_four_levels():
    items = [L("4."), L("c."), L("(1)"), L("(2)"), L("(a)"), L("(b)")]
    assert refs(items)[-1] == "4.c(2)(b)"


def test_a_lower_marker_clears_when_a_higher_one_arrives():
    items = [L("4."), L("c."), L("(2)"), L("d.")]
    assert refs(items)[-1] == "4.d"
    items = [L("4."), L("c."), L("(2)"), L("5.")]
    assert refs(items)[-1] == "5"


def test_items_between_markers_inherit_the_current_reference():
    items = [L("4."), L("c."), T("A continuation paragraph with no number."), Item("table", "x")]
    assert refs(items)[2:] == ["4.c", "4.c"]


# --- the reader drops or misplaces things ------------------------------------------------------

def test_a_gap_in_the_numbering_is_tolerated():
    """Headings 8 to 10 were missing from the reader's output; "11." must still be taken."""
    items = [H("5.  DIRECTOR, NSA (DIRNSA)."), H("11. DOD COMPONENT HEADS."), L("a."), L("b.")]
    assert refs(items)[-1] == "11.b"


def test_a_gap_beyond_the_tolerance_is_a_stray_list():
    items = [L("1."), L("a."), L("9.")]
    assert refs(items, Grammar(gap_tolerance=6))[-1] == "1.a"
    assert refs(items, Grammar(gap_tolerance=8))[-1] == "9"


def test_the_first_marker_must_be_a_plausible_start():
    assert refs([L("7."), L("1.")])[0] == ""
    assert refs([L("7."), L("1.")])[1] == "1"


def test_a_stray_list_that_goes_backwards_or_repeats_is_ignored():
    items = [L("5."), L("c."), L("2."), L("a."), L("c.")]
    assert refs(items)[-1] == "5.c"


def test_a_stray_high_number_cannot_start_the_numbering():
    """A "9. Effective Date" list near the front once took over a whole document."""
    items = [L("9.", "Effective Date. This instruction is effective upon signature."), L("1."), L("a.")]
    out = refs(items)
    assert out[0] == ""
    assert out[-1] == "1.a"


def test_the_number_can_sit_at_the_start_of_the_item_text():
    """About 40 list items per document come with no separate marker."""
    items = [L("c."), Item("list_item", "d.  Establish and maintain a repository."), Item("list_item", "(1)  First point.")]
    assert refs(items)[-1] == "d(1)"
    assert refs(items)[1] == "d"


def test_a_heading_carries_its_number_in_its_text():
    assert refs([H("2.  NM DATA EXCHANGE GUIDELINES")]) == ["2"]


# --- dotted headings (mixed documents) ---------------------------------------------------------

def test_dotted_heading_then_lettered_sublist():
    items = [H("2.10.  OSD AND DOD COMPONENT HEADS."), L("b."), L("(1)"), L("(2)"), L("(3)")]
    out = refs(items)
    assert out[0] == "2.10"
    assert out[-1] == "2.10.b(3)"


def test_a_new_dotted_heading_clears_everything_below_it():
    items = [H("2.10.  A"), L("b."), L("(3)"), H("2.11.  B"), L("a.")]
    out = refs(items)
    assert out[3] == "2.11"
    assert out[4] == "2.11.a"


def test_dotted_headings_need_no_sequence_check():
    assert refs([H("3.2.  LEGACY INFORMATION REQUIREMENTS."), H("3.9.  GENERAL RELEASE.")])[-1] == "3.9"


def test_integer_list_markers_are_ignored_inside_a_dotted_document():
    items = [H("2.4.  DOD COMPONENT HEADS."), L("1."), L("a.")]
    assert refs(items)[1] == "2.4"
    assert refs(items)[-1] == "2.4.a"


def test_a_lettered_paragraph_filed_as_a_heading_still_counts():
    """The reader sometimes files "a.  Component heads" as a heading, not a list item (Codex, PR 391)."""
    items = [H("2.10.  DUTIES"), H("a.  Component heads"), L("(1)")]
    assert refs(items) == ["2.10", "2.10.a", "2.10.a(1)"]


def test_a_parenthesized_paragraph_filed_as_a_heading_counts():
    items = [L("4."), L("c."), H("(1)  Services and Defense Agencies must comply."), H("(2)  The PO will submit.")]
    assert refs(items)[-2:] == ["4.c(1)", "4.c(2)"]


def test_a_heading_marker_given_separately_is_read():
    items = [L("4."), Item("heading", "Services will:", marker="b.")]
    assert refs(items)[-1] == "4.b"


def test_a_stray_lettered_heading_is_ignored_like_any_stray_marker():
    items = [L("4."), L("c."), H("a.  A stray earlier letter")]
    assert refs(items)[-1] == "4.c"


# --- what must never become a marker -----------------------------------------------------------

@pytest.mark.parametrize("item", [
    T("1. Purpose ........................ 3"),            # table-of-contents line
    T("2. Applicability . . . 4"),
    T("e.g. a router or a switch"),                      # not a list letter
    T("3 apples were counted"),                          # no dot
    T("A. Uppercase letters are not list letters here."),
    Item("table", "5. in a cell", marker="5."),          # tables are not read
    Item("caption", "Table 3.1. Actions", marker="3."),
    H("UNCLASSIFIED"),                                   # a page banner
])
def test_non_markers_change_nothing(item):
    items = [L("4."), L("c."), item]
    assert refs(items)[-1] == "4.c"


def test_a_banner_word_inside_real_content_is_just_text():
    items = [L("4."), T("UNCLASSIFIED information shall be marked as required."), L("a.")]
    assert refs(items)[1] == "4"
    assert refs(items)[2] == "4.a"


def test_nothing_numbered_means_no_reference():
    assert refs([H("Purpose"), T("Plain prose.")]) == ["", ""]
    assert refs([]) == []


# --- turning pieces of the grammar off, and the output form ------------------------------------

def test_integer_headings_can_be_turned_off():
    g = Grammar(integer_headings=False)
    assert refs([H("2.  GENERAL"), L("1."), L("a.")], g)[-1] == "a"


def test_no_enclosure_pattern_means_no_enclosures():
    assert refs([H("ENCLOSURE A"), L("1.")], Grammar())[-1] == "1"


def test_ref_text_forms():
    assert Ref().text() == ""
    assert Ref(enclosure="2").text() == ""
    assert Ref(top="5").text() == "5"
    assert Ref(top="5", letter="k").text() == "5.k"
    assert Ref(top="5", number="4").text() == "5(4)"
    assert Ref(enclosure="2", letter="a").text() == "Encl 2, a"
    assert Ref(enclosure="A", top="4", letter="c", number="2", sub="g").text() == "Encl A, 4.c(2)(g)"


def test_labeling_is_repeatable_and_does_not_change_its_input():
    items = [H("ENCLOSURE A"), L("5."), L("a.")]
    snapshot = list(items)
    assert refs(items) == refs(items)
    assert items == snapshot


# --- the grammar's own data --------------------------------------------------------------------

def test_defaults():
    g = parse_grammar({})
    assert g == Grammar()
    assert g.gap_tolerance == 6 and g.enclosure_pattern is None and g.dotted_headings and g.integer_headings


def test_a_full_grammar_parses():
    g = parse_grammar({"gap_tolerance": 4, "enclosure_pattern": ENC, "dotted_headings": False, "integer_headings": True})
    assert g == Grammar(gap_tolerance=4, enclosure_pattern=ENC, dotted_headings=False, integer_headings=True)


@pytest.mark.parametrize("bad", [
    {"colour": "red"},
    {"gap_tolerance": 0},
    {"gap_tolerance": 21},
    {"gap_tolerance": True},
    {"gap_tolerance": "6"},
    {"enclosure_pattern": 5},
    {"enclosure_pattern": "(unclosed"},
    {"enclosure_pattern": r"^ENCLOSURE\s+[A-Z]$"},      # no group to capture the id
    {"dotted_headings": "yes"},
    {"integer_headings": 1},
])
def test_bad_grammar_data_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_grammar(bad)


def test_a_grammar_must_be_an_object():
    with pytest.raises(ValueError, match="object"):
        parse_grammar([1, 2])
