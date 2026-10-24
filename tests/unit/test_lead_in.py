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


def test_a_lead_in_whose_colon_is_followed_by_a_tier_tag_is_a_lead_in():
    raw = "Training will use one of the following options: (T-2).\n- classroom courses"
    assert find_lead_in(raw, _at(raw, "classroom")) == "Training will use one of the following options: (T-2)."
    raw2 = "Background text. The Director will: (T-1)\n- Approve plans."
    assert find_lead_in(raw2, _at(raw2, "Approve")) == "The Director will: (T-1)"
    prev = "Intro.\nUnits shall do the following: (T-3)."
    raw3 = "- Keep logs."
    assert find_lead_in(raw3, 2, prev) == "Units shall do the following: (T-3)."


# ---- PREREG10 (proposed): the section heading as the lead-in of a list that has none
DOD_CIO = ["1.  DoD CHIEF INFORMATION OFFICER (DoD CIO).  The DoD CIO, shall:"]


def test_heading_lead_in_is_the_last_sentence_of_a_heading_that_ends_in_a_colon():
    from pipeline.lead_in import heading_lead_in
    assert heading_lead_in(DOD_CIO) == "The DoD CIO, shall:"
    assert heading_lead_in(["3.  POLICY.  It is DoD policy that:"]) == "It is DoD policy that:"
    assert heading_lead_in(["The DoD CIO:"]) == "The DoD CIO:"


def test_heading_lead_in_accepts_a_modal_ending_without_a_colon_and_refuses_labels_and_plain_headings():
    from pipeline.lead_in import heading_lead_in
    assert heading_lead_in(["5.  The Services will"]) == "The Services will"
    assert heading_lead_in(["3.4.  MARKING REQUIREMENTS."]) is None
    assert heading_lead_in(["SCENARIO:"]) is None  # one word: a label
    assert heading_lead_in(["Reply to :"]) is None  # a memo header: ends in a preposition
    assert heading_lead_in(["6.  DISA will:"]) == "DISA will:" and heading_lead_in(["The DDI(CL&S):"]) == "The DDI(CL&S):"
    assert heading_lead_in([]) is None and heading_lead_in(None) is None


def test_heading_lead_in_skips_page_header_junk_but_looks_at_one_entry_only():
    from pipeline.lead_in import heading_lead_in, is_junk_heading
    assert [is_junk_heading(x) for x in ("UNCLASSIFIED", "CUI", "UNCLASSIFIED//FOUO", "12", "Page 3 of 9", "ROLES AND RESPONSIBILITIES")] == [True, True, True, True, True, False]
    assert heading_lead_in(["4.  Services and Agencies will:", "UNCLASSIFIED"]) == "Services and Agencies will:"
    assert heading_lead_in(["UNCLASSIFIED"]) is None
    assert heading_lead_in(["2.  The MC4EB will:", "2.1.  GENERAL."]) is None  # the nearest real heading does not end in a colon: never climb past it


def test_a_list_item_that_opens_its_section_gets_the_heading_and_without_the_path_nothing_changes():
    raw = "- a.  Provide strategy, policy, and oversight.\n- b.  Coordinate with the Components."
    assert find_lead_in(raw, _at(raw, "Coordinate")) is None  # control: unchanged
    assert find_lead_in(raw, _at(raw, "Coordinate"), "", DOD_CIO) == "The DoD CIO, shall:"
    assert find_lead_in(raw, _at(raw, "Provide"), "", DOD_CIO) == "The DoD CIO, shall:"


def test_the_heading_is_used_only_when_nothing_closer_governs():
    raw = "Intro paragraph that stands alone.\n- a.  Provide strategy.\n"
    assert find_lead_in(raw, _at(raw, "Provide"), "", DOD_CIO) is None  # a plain paragraph above the list: the heading does not govern it
    raw2 = "The Director will:\n- a.  Provide strategy."
    assert find_lead_in(raw2, _at(raw2, "Provide"), "", DOD_CIO) == "The Director will:"  # a lead-in line wins over the heading
    plain = "The DoD CIO coordinates with the Components."
    assert find_lead_in(plain, 0, "", DOD_CIO) is None  # a plain sentence stands on its own
    prev = "Some background paragraph.\n- a.  Provide strategy."
    assert find_lead_in("- b.  Coordinate.", 0, prev, DOD_CIO) is None  # a plain paragraph in the previous chunk of the same section
    assert find_lead_in("- b.  Coordinate.", 0, "- a.  Provide strategy.", DOD_CIO) == "The DoD CIO, shall:"
