"""WP-45.14: expanding a quote to the whole sentence it sits in."""
from pipeline import sentence_expand as SE


def test_a_fragment_becomes_the_whole_sentence_around_it():
    chunk = "Intro sentence here. The CFP shall report the incident to the NOS within one hour. Next one follows."
    assert SE.expand("report the incident to the NOS", chunk) == ("The CFP shall report the incident to the NOS within one hour.", "expanded")
    assert SE.expand("The CFP shall report the incident to the NOS within one hour.", chunk)[1] == "unchanged"


def test_abbreviations_initials_and_decimals_do_not_end_a_sentence():
    chunk = "See U.S. Code for details. The unit shall comply with e.g. AFI 17-203 and J. Smith's guidance within 5.5 days. Done."
    text, status = SE.expand("comply with", chunk)
    assert status == "expanded" and text == "The unit shall comply with e.g. AFI 17-203 and J. Smith's guidance within 5.5 days."


def test_a_paragraph_number_is_not_a_sentence_end_and_is_dropped():
    chunk = "3.6.1.1.  Ensure the accuracy and completeness of incident reports.\n3.6.1.2.  Characterize and communicate the potential impact of the incident."
    assert SE.expand("accuracy and completeness", chunk) == ("Ensure the accuracy and completeness of incident reports.", "expanded")
    assert SE.expand("potential impact", chunk) == ("Characterize and communicate the potential impact of the incident.", "expanded")


def test_a_list_tail_takes_the_sentence_the_list_began():
    chunk = "This includes administrative and user actions such as failure to apply security patches;\ninstallation of vulnerable applications, and other breaches of existing AF or DoD policy."
    text, status = SE.expand("installation of vulnerable applications, and other breaches of existing AF or DoD policy", chunk)
    assert status == "expanded" and text.startswith("This includes administrative and user actions") and text.endswith("existing AF or DoD policy.")


def test_a_bullet_or_numbered_item_is_its_own_unit():
    chunk = "- 2.5.1.1.  The Director shall review logs monthly.\n- 2.5.1.2.  The Director shall report spills to the NOS."
    assert SE.expand("report spills", chunk) == ("The Director shall report spills to the NOS.", "expanded")


def test_spaced_punctuation_and_tier_tags_are_tidied_not_split():
    chunk = "Units shall retain logs for one year (T-2) . The next sentence starts here."
    assert SE.expand("retain logs", chunk) == ("Units shall retain logs for one year (T-2).", "expanded")


def test_a_quote_not_in_the_chunk_and_a_sentence_that_is_too_long_are_left_as_given():
    assert SE.expand("text that is not there", "Some other text.") == ("text that is not there", "not_located")
    long_sentence = "The unit shall " + "do something and then " * 60 + "stop."
    text, status = SE.expand("then stop", long_sentence)
    assert status == "too_long" and text == "then stop"


def test_completeness_check():
    assert SE.is_complete("The unit shall report.") and SE.is_complete("(a) The unit shall report to:") and SE.is_complete("3 units shall report.")
    assert not SE.is_complete("installation of vulnerable applications, and other breaches of existing policy")
    assert not SE.is_complete("The unit shall report to the") and not SE.is_complete("then take the indicated Actions") and not SE.is_complete("")


def test_a_bracketed_reference_label_ends_a_sentence_and_an_initial_does_not():
    chunk = "Services shall report to the NSS National Manager via the DoD CIO IAW section 1 (b).(iv).(D) of reference (k). Points of contact are listed in Enclosure A."
    text, status = SE.expand("report to the NSS National Manager", chunk)
    assert text.endswith("of reference (k).") and "Points" not in text and status == "expanded"
    assert SE.expand("J. Smith", "Briefed by J. Smith on the plan. Then it ended.")[0] == "Briefed by J. Smith on the plan."


def test_an_inline_list_marker_does_not_open_the_expanded_sentence():
    chunk = "(f) The request will be filed. (g) During Joint Staff processing, the request will be forwarded to the NSA. (h) Next step."
    assert SE.expand("the request will be forwarded to the NSA", chunk)[0] == "During Joint Staff processing, the request will be forwarded to the NSA."


def test_a_sentence_ending_in_a_dotted_citation_still_ends_there():
    chunk = "Components shall implement the controls in DoDI 8510.01. Reports go to the CIO. Reviews are annual."
    assert SE.expand("implement the controls", chunk) == ("Components shall implement the controls in DoDI 8510.01.", "expanded")
    assert SE.expand("Reports go", chunk)[0] == "Reports go to the CIO."


def test_flat_numbered_and_uppercase_lettered_lists_are_separate_units():
    chunk = "1. First item;\n2. Second item;\n3. Third item."
    assert SE.expand("Second item", chunk) == ("Second item;", "expanded")
    assert SE.expand("Third item", chunk)[0] == "Third item."
    lettered = "A. Review the logs.\nB. Report the findings to the CIO."
    assert SE.expand("Report the findings", lettered)[0] == "Report the findings to the CIO."


def test_bare_bullet_is_dropped():
    assert SE.expand("Directs actions in accordance with X.", "- Directs actions in accordance with X.") == ("Directs actions in accordance with X.", "unchanged")


def test_run_of_markers_is_dropped():
    text, _ = SE.expand("Enhance baseline standards in accordance with DoDI 8500.01.", "3. (a)  Enhance baseline standards in accordance with DoDI 8500.01.")
    assert text == "Enhance baseline standards in accordance with DoDI 8500.01."


def test_one_word_quote_is_not_expanded():
    assert SE.expand("CNSI", "CNSI classified national security information CPM Component program manager") == ("CNSI", "too_short")


def test_unpunctuated_term_before_a_sentence_is_not_grafted_on():
    text, _ = SE.expand("Use of CUI in a manner not in accordance with policy.", "CUI misuse Use of CUI in a manner not in accordance with policy.")
    assert text == "Use of CUI in a manner not in accordance with policy."


def test_lead_in_with_colon_is_still_grafted():
    text, status = SE.expand("Obtain the qualification.", "Individuals shall: Obtain the qualification.")
    assert text == "Individuals shall: Obtain the qualification."
    assert status == "expanded"


def test_expand_records_expands_merges_and_copies():
    raw = {1: "Units shall retain logs for one year (T-2), and review them monthly. Other text."}
    recs = [{"chunk_id": 1, "source_quote": "retain logs for one year (T-2)"}, {"chunk_id": 1, "source_quote": "review them monthly"}, {"chunk_id": 2, "source_quote": "Missing quote here."}]
    out, counts = SE.expand_records(recs, raw)
    assert [r["source_quote"] for r in out] == ["Units shall retain logs for one year (T-2), and review them monthly.", "Missing quote here."]
    assert counts["merged"] == 1 and counts["expanded"] == 2 and counts["not_located"] == 1
    assert recs[0]["source_quote"] == "retain logs for one year (T-2)"


def test_a_quote_that_occurs_twice_in_the_chunk_is_not_expanded_or_merged():
    raw = {1: "Administrators shall review logs. Auditors shall review logs."}
    recs = [{"chunk_id": 1, "source_quote": "review logs"}, {"chunk_id": 1, "source_quote": "review logs"}]
    out, counts = SE.expand_records(recs, raw)
    assert [r["source_quote"] for r in out] == ["review logs", "review logs"] and counts["ambiguous"] == 2 and counts["merged"] == 0


def test_an_unlocated_record_does_not_swallow_a_later_record_with_the_same_text():
    raw = {1: "Units shall keep logs for one year."}
    recs = [{"chunk_id": 1, "source_quote": "Units shall keep logs for one year."}, {"chunk_id": 1, "source_quote": "keep logs for one year"}]
    out, _ = SE.expand_records([{"chunk_id": 2, "source_quote": "Units shall keep logs for one year."}] + recs, raw)
    assert len(out) == 2 and out[0]["chunk_id"] == 2
