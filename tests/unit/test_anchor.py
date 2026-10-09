"""Anchoring: where a root quote sits in its chunk and how exact the match is."""
from pipeline.anchor import anchor

RAW = ("2.2.13.  AFNWC/NC will:\n- 2.2.13.1.  Sustain, modernize and recapitalize the AN/USQ-225. (T-1)\n"
       "- 2.2.13.2.  Act  as  lead  systems  engineer  and  technical  configuration  manager  for  the AN/USQ-225. (T-1)\n"
       "The AFOSI:\n2.3.1.1.  Is the sole AF entity with responsibility for conducting felony investigations.\n")


def test_an_exact_root_gets_its_position_and_the_source_spelling():
    a = anchor("Act as lead systems engineer and technical configuration manager for the AN/USQ-225.", RAW)
    assert a["anchor_status"] == "exact" and a["anchor_text"].startswith("Act  as  lead") and RAW[a["anchor_start"]:a["anchor_end"]] == a["anchor_text"]


def test_a_dash_or_number_in_front_is_removed_and_the_rest_is_exact():
    a = anchor("- Sustain, modernize and recapitalize the AN/USQ-225.", RAW)
    assert a["anchor_status"] == "marker_removed" and a["anchor_text"] == "Sustain, modernize and recapitalize the AN/USQ-225."


def test_a_glued_lead_in_anchors_to_the_item_and_keeps_the_lead_in():
    a = anchor("AFNWC/NC will: Sustain, modernize and recapitalize the AN/USQ-225.", RAW)
    assert a["anchor_status"] == "lead_in_joined" and a["anchor_text"] == "Sustain, modernize and recapitalize the AN/USQ-225."
    assert a["anchor_lead_in"] == "AFNWC/NC will:" and a["anchor_lead_in_start"] == RAW.index("AFNWC/NC will:")  # the lead-in is also exact, and its place is recorded


def test_a_subject_restated_in_front_is_trimmed_to_the_exact_sentence():
    a = anchor("AFOSI is the sole AF entity with responsibility for conducting felony investigations.", RAW)
    assert a["anchor_status"] == "words_trimmed" and a["anchor_text"].startswith("the sole AF entity") and a["anchor_words_trimmed"] == 2


def test_a_root_that_occurs_twice_gets_no_position():
    a = anchor("Report to the Director every quarter.", "A. Report to the Director every quarter. B. Report to the Director every quarter.")
    assert a["anchor_status"] == "exact_ambiguous" and a["anchor_start"] is None and a["anchor_matches"] == 2


def test_something_not_in_the_chunk_is_not_found_and_empty_inputs_do_not_raise():
    assert anchor("The CIO shall ensure that all systems are properly configured to prevent unauthorized access.", RAW)["anchor_status"] == "not_found"
    assert anchor("", RAW)["anchor_status"] == "not_found" and anchor("text", "")["anchor_status"] == "not_found"


def test_the_root_itself_is_never_changed():
    root = "  - Sustain, modernize and recapitalize the AN/USQ-225.  "
    anchor(root, RAW)
    assert root == "  - Sustain, modernize and recapitalize the AN/USQ-225.  "


def test_a_glued_lead_in_that_is_not_in_the_source_is_not_vouched_for():
    a = anchor("The Commander will: Sustain, modernize and recapitalize the AN/USQ-225.", RAW)
    assert a["anchor_status"] == "lead_in_not_in_source" and a["anchor_text"] == "Sustain, modernize and recapitalize the AN/USQ-225." and "anchor_lead_in" not in a


def test_a_lead_in_that_comes_after_the_item_is_not_vouched_for():
    raw = "Sustain, modernize and recapitalize the AN/USQ-225. AFNWC/NC will: something else entirely."
    assert anchor("AFNWC/NC will: Sustain, modernize and recapitalize the AN/USQ-225.", raw)["anchor_status"] == "lead_in_not_in_source"


def test_a_repeated_trimmed_piece_is_ambiguous_not_fuzzy():
    raw = "1. Report the incident to the Director now. 2. Report the incident to the Director now."
    a = anchor("The unit shall Report the incident to the Director now.", raw)
    assert a["anchor_status"] == "exact_ambiguous" and a["anchor_start"] is None


def test_an_unknown_chunk_gets_the_same_fields():
    a = anchor("Anything at all that is long enough.", "")
    assert a["anchor_status"] == "not_found" and a["anchor_start"] is None and a["anchor_end"] is None and a["anchor_text"] is None


def test_regex_special_characters_in_a_quote_are_matched_literally():
    assert anchor("(T-1) [x] *( unclosed ((( ++ ??? \\", "see (T-1) [x] *( unclosed ((( ++ ??? \\ here")["anchor_status"] in ("exact", "words_trimmed")


def test_a_repeated_lead_in_uses_the_nearest_occurrence_before_the_item():
    raw = "AFMC will: First duty here that is long.\nAFMC will:\n- 1. Identify the funding requirements for the program."
    a = anchor("AFMC will: Identify the funding requirements for the program.", raw)
    assert a["anchor_status"] == "lead_in_joined" and a["anchor_lead_in_start"] == raw.index("AFMC will:", 5)


def test_a_lead_in_that_is_only_in_the_heading_is_marked_as_from_the_heading():
    raw = "- 1. Collect, monitor, and analyze data in support of Cyber workforce management actions."
    a = anchor("Air Combat Command shall: Collect, monitor, and analyze data in support of Cyber workforce management actions.", raw, "[ROLES > 2.4. Air Combat Command]")
    assert a["anchor_status"] == "lead_in_from_heading" and a["anchor_lead_in"] == "Air Combat Command shall:"
    assert anchor("The Wing shall: Collect, monitor, and analyze data in support of Cyber workforce management actions.", raw, "[ROLES > 2.4. Air Combat Command]")["anchor_status"] == "lead_in_not_in_source"
