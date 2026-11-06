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


# --- the control-ID family (NIST SP 800-53 / 800-171): shapes copied from the PDF reader's output ----------------------------------

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from core.reference_grammar import label_table_lines  # noqa: E402

NIST = parse_grammar(json.loads((Path(__file__).resolve().parent.parent.parent / "doc_styles" / "nist-controls.json").read_text(encoding="utf-8"))["reference_grammar"])


def S(text):          # a section header
    return Item("heading", text)


def LI(marker, text="Some statement text."):
    return Item("list_item", text, marker=marker)


def nist(items):
    return [r.text() for r in label_items(items, NIST)]


def test_a_control_statement_with_lettered_and_numbered_items():
    """AC-2 as the reader produced it."""
    items = [S("AC-2 ACCOUNT MANAGEMENT"), S("Control:"), LI("a."), LI("b."), LI("c."), LI("d.", "Specify:"), LI("1."), LI("2."), LI("3."), LI("e."),
             LI("f."), LI("g."), LI("h.", "Notify:"), LI("1."), LI("2.")]
    out = nist(items)
    assert out[:2] == ["AC-2", "AC-2"]
    assert out[2] == "AC-2 a" and out[5] == "AC-2 d" and out[6] == "AC-2 d.1" and out[8] == "AC-2 d.3"
    assert out[-2:] == ["AC-2 h.1", "AC-2 h.2"]        # numbering restarts under the next letter


def test_discussion_and_related_controls_are_parts_not_the_statement():
    items = [S("AC-2 ACCOUNT MANAGEMENT"), S("Control:"), LI("a."), Item("text", "Discussion:  Examples of system account types include individual."),
             Item("text", "Where access involves personally identifiable information, programs collaborate."), Item("text", "Related Controls:  AC-3, AC-5.")]
    out = nist(items)
    assert out[2] == "AC-2 a"
    assert out[3] == out[4] == "AC-2 Discussion"
    assert out[5] == "AC-2 Related Controls"


def test_enhancements_filed_as_list_items_or_headings_are_found_by_their_shape():
    items = [S("AC-2 ACCOUNT MANAGEMENT"), S("Control:"), LI("a."), S("Control Enhancements:"),
             S("(1) ACCOUNT MANAGEMENT | AUTOMATED SYSTEM ACCOUNT MANAGEMENT"), Item("text", "Support the management of system accounts."),
             Item("text", "Discussion:  Automated system account management includes using automated mechanisms."),
             LI("(2)", "ACCOUNT MANAGEMENT | AUTOMATED TEMPORARY AND EMERGENCY ACCOUNT MANAGEMENT"), Item("text", "Automatically remove temporary accounts.")]
    out = nist(items)
    assert out[3] == "AC-2"
    assert out[4:7] == ["AC-2(1)", "AC-2(1)", "AC-2(1) Discussion"]
    assert out[7:] == ["AC-2(2)", "AC-2(2)"]


def test_parenthesized_items_under_an_enhancement_keep_the_documents_own_form():
    """AC-19(4): (a) (b) with (1) (2) under (b), then (c) is the next letter, not a sub-item."""
    items = [S("AC-19 ACCESS CONTROL FOR MOBILE DEVICES"), LI("(4)", "ACCESS CONTROL FOR MOBILE DEVICES | RESTRICTIONS FOR CLASSIFIED INFORMATION"),
             LI("", "(a) Prohibit the use of unclassified mobile devices."), LI("", "(b) Enforce the following restrictions:"), LI("(1)", "Connection is prohibited;"),
             LI("(2)", "Connection requires approval;"), LI("", "(c) Restrict the connection of classified mobile devices.")]
    assert nist(items)[1:] == ["AC-19(4)", "AC-19(4)(a)", "AC-19(4)(b)", "AC-19(4)(b)(1)", "AC-19(4)(b)(2)", "AC-19(4)(c)"]


def test_a_sub_item_under_a_dotted_letter_and_number():
    """CM-1 a.1(a): the (a) after "1." is a sub-item."""
    items = [S("CM-1 POLICY AND PROCEDURES"), S("Control:"), LI("a.", "Develop:"), LI("1.", "A policy that:"), LI("(a)", "Addresses purpose;"), LI("(b)", "Is consistent;"), LI("2.", "Procedures;")]
    assert nist(items)[2:] == ["CM-1 a", "CM-1 a.1", "CM-1 a.1(a)", "CM-1 a.1(b)", "CM-1 a.2"]


def test_800_171_requirements_and_their_parts():
    items = [S("3.1. Access Control"), S("03.01.01 Account Management"), LI("a."), LI("b."), LI("c.", "Specify:"), LI("1."), LI("2."), S("DISCUSSION"),
             Item("text", "This requirement focuses on account management."), S("REFERENCES"), Item("text", "Source Controls: AC-02, AC-02(03)"),
             S("03.01.02    Access Enforcement"), Item("text", "Enforce approved authorizations.")]
    out = nist(items)
    assert out[0] == ""                                      # a family heading is not a requirement
    assert out[1] == "03.01.01" and out[4] == "03.01.01 c" and out[5] == "03.01.01 c.1"
    assert out[8] == "03.01.01 Discussion" and out[10] == "03.01.01 References"
    assert out[12] == "03.01.02"


def test_the_bibliography_after_the_last_requirement_is_not_part_of_it():
    items = [S("03.17.03 Supply Chain Requirements"), Item("text", "Establish a process."), S("REFERENCES"), Item("text", "Supporting Publications: SP 800-161"),
             S("References"), Item("text", "[1] Executive Order 14028, May 2021.")]
    out = nist(items)
    assert out[1] == "03.17.03" and out[3] == "03.17.03 References"
    assert out[5] == ""                                       # the document's own bibliography


def test_text_outside_any_control_has_no_reference():
    assert nist([Item("text", "Introduction text."), LI("a.", "A list in the foreword.")]) == ["", ""]


def test_markers_inside_a_part_are_not_statement_items():
    items = [S("AC-2 ACCOUNT MANAGEMENT"), S("Control:"), LI("a."), Item("text", "Discussion:  Examples."), LI("a.", "A list inside the discussion.")]
    assert nist(items)[-1] == "AC-2 Discussion"


@pytest.mark.parametrize("bad", [
    {"id_heading_patterns": "AC"},
    {"id_heading_patterns": ["(unclosed"]},
    {"id_heading_patterns": ["^[A-Z]{2}-\\d+"]},                         # no group for the id
    {"enhancement_pattern": "^X\\|"},                                     # needs id patterns
    {"id_heading_patterns": ["^(AC-\\d)"], "enhancement_pattern": 5},
    {"statement_patterns": ["^Control:$"]},
    {"part_patterns": {"Discussion": "^Discussion"}},
    {"id_heading_patterns": ["^(AC-\\d)"], "part_patterns": ["x"]},
    {"id_heading_patterns": ["^(AC-\\d)"], "part_patterns": {"": "x"}},
    {"id_heading_patterns": ["^(AC-\\d)"], "part_patterns": {"Discussion": 3}},
    {"reset_patterns": ["^CHAPTER"]},
    {"table_id_pattern": 5},
    {"table_id_pattern": "(unclosed"},
])
def test_bad_control_grammar_data_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_grammar(bad)


def test_the_shipped_control_styles_parse():
    for name in ("nist-controls", "control-tables"):
        data = json.loads((Path(__file__).resolve().parent.parent.parent / "doc_styles" / f"{name}.json").read_text(encoding="utf-8"))
        parse_grammar(data["reference_grammar"])


# --- tables of controls (CNSSI 1253) -------------------------------------------------------------------------------------------

CTRL = Grammar(table_id_pattern=r"^[A-Z]{2}-\d{1,2}(?:\(\d{1,2}\))?$")
PAGE = "\n".join([
    "| ID       | Control Text                          |",
    "|----------|---------------------------------------|",
    "|          | information]                          |",
    "| CP-10(4) | [Assignment: restoration time-periods] |",
    "| CP-11    | [Assignment: alternative protocols]   |",
    "| IA-1     | a. [Assignment: personnel or roles]   |",
    "| IA-1     | b.1. Identification policy            |",
    "| CM-7(1)  | (b) [Assignment: functions]           |",
    "|          | more of the same cell                 |",
    "| Family   | PS                                    |",
    "|          | text after a non-control row          |",
])


def test_table_rows_are_cited_by_the_control_in_their_first_cell():
    refs, carry = label_table_lines(PAGE, CTRL, carry="CP-10(3)")
    assert refs == [None, None, "CP-10(3)", "CP-10(4)", "CP-11", "IA-1 a", "IA-1 b.1", "CM-7(1)(b)", "CM-7(1)", None, None]   # a continuation row inherits the control, not the part
    assert carry is None                                      # the "Family" row ended the control


def test_a_blank_first_cell_continues_the_previous_page_through_the_repeated_header():
    refs, carry = label_table_lines("| ID | Control Text |\n|---|---|\n| | continuation |\n| IA-5(8) | text |", CTRL, carry="IA-5(7)")
    assert refs == [None, None, "IA-5(7)", "IA-5(8)"] and carry == "IA-5(8)"


def test_continuation_with_nothing_to_continue_has_no_reference():
    refs, _ = label_table_lines("| | orphan row |", CTRL, carry=None)
    assert refs == [None]


def test_lines_that_are_not_table_rows_get_none_and_the_carry_survives():
    refs, carry = label_table_lines("Table 3-1. Controls\n| IA-1 | a. text |\nnot a row", CTRL, carry=None)
    assert refs == [None, "IA-1 a", None] and carry == "IA-1"


def test_without_a_table_pattern_nothing_is_labeled():
    refs, carry = label_table_lines("| IA-1 | a. text |", Grammar(), carry="X")
    assert refs == [None] and carry == "X"
