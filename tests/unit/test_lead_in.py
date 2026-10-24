"""The lead-in that governs a list item, read from the document's own lines."""
from pipeline.lead_in import find_lead_in


def _at(raw, needle):
    return raw.index(needle)


def test_the_nearest_earlier_line_ending_in_a_colon_is_the_lead_in():
    raw = "3.6. Incident Analysis. Include the mission owner.\nThe CFP will:\n- 3.6.1.1.  Ensure the accuracy of reports.\n- 3.6.1.2.  Characterize the impact."
    assert find_lead_in(raw, _at(raw, "Characterize")) == "The CFP will:"


def test_a_plain_sentence_has_no_lead_in():
    raw = "The CFP will review. Units shall retain logs for one year. Other text follows."
    assert find_lead_in(raw, _at(raw, "Units shall")) is None


def test_a_sibling_that_also_ends_in_a_colon_is_not_the_parent():
    raw = "The Director will:\na. Review the following:\n   (1) logs\n   (2) reports\nb. Approve the plan."
    assert find_lead_in(raw, _at(raw, "Approve")) == "The Director will:"
    assert find_lead_in(raw, _at(raw, "reports")) == "Review the following:"


def test_a_deeper_numbered_line_is_not_the_parent_of_a_shallower_one():
    raw = "2.1. The Director will:\n2.1.1. Review the logs, which means:\n2.1.1.1. Weekly checks.\n2.1.2. Approve the plan."
    assert find_lead_in(raw, _at(raw, "Approve")) == "The Director will:"
    assert find_lead_in(raw, _at(raw, "Weekly")) == "Review the logs, which means:"


def test_the_lead_in_can_be_at_the_end_of_the_previous_chunk_when_the_list_started_there():
    prev = "Some intro sentence here.\nThe Wing Commander shall:\n- a. Appoint a monitor."
    raw = "- b. Brief the staff weekly.\n- c. Keep the records."
    assert find_lead_in(raw, _at(raw, "Keep"), prev) == "The Wing Commander shall:"


def test_a_plain_paragraph_before_the_item_in_the_chunk_stops_the_search():
    prev = "The Wing Commander shall:\n- a. Appoint a monitor."
    raw = "An unrelated sentence closes the list.\n- 1. Brief the staff weekly."
    assert find_lead_in(raw, _at(raw, "Brief"), prev) is None


def test_nothing_is_guessed_when_no_line_ends_in_a_colon():
    raw = "- a. Appoint a monitor.\n- b. Brief the staff weekly."
    assert find_lead_in(raw, _at(raw, "Brief")) is None


def test_an_abbreviation_in_the_lead_in_does_not_cut_it():
    raw = "Some intro. The U.S. Cyber Command will:\n- a. Brief the staff weekly.\n- b. Keep the records."
    assert find_lead_in(raw, _at(raw, "Keep")) == "The U.S. Cyber Command will:"
    raw2 = "Dr. Smith will:\n- a. Brief the staff weekly.\n- b. Keep the records."
    assert find_lead_in(raw2, _at(raw2, "Keep")) == "Dr. Smith will:"


def test_a_bare_number_line_after_a_list_item_is_a_plain_sentence_with_no_lead_in():
    # CNSSI 1253 footnote-style lines: "2 Examples ..." follows the bullets; units split only at markers, so it used to inherit the lead-in above the list.
    raw = "The assumptions are:\n- Systems are networked.\n2 Examples of systems that diverge include test rigs."
    assert find_lead_in(raw, _at(raw, "Systems are")) == "The assumptions are:"
    assert find_lead_in(raw, _at(raw, "2 Examples")) is None
    raw2 = "Complete the following:\n- Document the gap.\nAt the discretion of the AO this may be filed.\n8 All guidance applies to NSS."
    assert find_lead_in(raw2, _at(raw2, "8 All")) is None


def test_a_bare_number_inside_a_numbered_item_or_a_wrapped_line_keeps_its_lead_in():
    raw = "Duties:\n- 2.5.1.1.7.  24 AF is designated as the CNDSP."
    assert find_lead_in(raw, _at(raw, "24 AF")) == "Duties:"
    raw2 = "Duties:\n- Brief the units assigned to\n24 AF every week."  # wrapped line: the previous line did not end a sentence
    assert find_lead_in(raw2, _at(raw2, "24 AF")) == "Duties:"
