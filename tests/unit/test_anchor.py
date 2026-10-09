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
    assert a["anchor_status"] in ("words_trimmed", "fuzzy") and "sole AF entity" in a["anchor_text"]


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
