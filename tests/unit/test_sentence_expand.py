"""WP-45.14: expanding a quote to the whole sentence it sits in."""
import json

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


def test_explain_records_adds_the_explained_layer_and_never_changes_the_root():
    raw = {1: "Units shall retain logs for one year (T-2), and review them monthly. Other text."}
    recs = [{"chunk_id": 1, "source_quote": "retain logs for one year (T-2)"}, {"chunk_id": 1, "source_quote": "review them monthly"}, {"chunk_id": 2, "source_quote": "Missing quote here."}]
    out, counts = SE.explain_records(recs, raw)
    assert [r["source_quote"] for r in out] == ["retain logs for one year (T-2)", "Missing quote here."]  # roots untouched
    assert out[0]["explained_text"] == "Units shall retain logs for one year (T-2), and review them monthly."
    assert out[0]["merged_roots"] == ["review them monthly"] and "expanded to the whole sentence" in out[0]["explain_notes"]
    assert out[1]["explained_text"] == "Missing quote here." and any("not expanded" in n for n in out[1]["explain_notes"])
    assert counts["merged"] == 1 and "explained_text" not in recs[0]  # the input records are copied


def test_a_glued_lead_in_backed_by_the_source_is_kept_in_front_of_the_sentence():
    raw = {1: "AFMC will:\n- 4.3.7.1.  Identify AF NC3 funding requirements within AFMC. (T-1)\n- 4.3.7.2.  Identify facility requirements."}
    rec = {"chunk_id": 1, "source_quote": "AFMC will: Identify AF NC3 funding requirements within AFMC.", "anchor_status": "lead_in_joined",
           "anchor_text": "Identify AF NC3 funding requirements within AFMC.", "anchor_lead_in": "AFMC will:"}
    out, _ = SE.explain_records([rec], raw)
    assert out[0]["explained_text"] == "AFMC will: Identify AF NC3 funding requirements within AFMC."
    assert [p["kind"] for p in out[0]["explained_parts"]] == ["lead_in", "sentence"] and out[0]["source_quote"] == rec["source_quote"]


def test_a_root_with_a_list_number_in_front_is_explained_from_its_exact_piece():
    raw = {1: "- 2.2.13.1.  Sustain, modernize and recapitalize the AN/USQ-225. (T-1)\n- 2.2.13.2.  Act as lead."}
    rec = {"chunk_id": 1, "source_quote": "- Sustain, modernize and recapitalize the AN/USQ-225.", "anchor_status": "marker_removed", "anchor_text": "Sustain, modernize and recapitalize the AN/USQ-225."}
    out, _ = SE.explain_records([rec], raw)
    assert out[0]["explained_text"].startswith("Sustain, modernize") and out[0]["source_quote"] == "- Sustain, modernize and recapitalize the AN/USQ-225."


def test_a_quote_that_occurs_twice_in_the_chunk_is_not_expanded_or_merged():
    raw = {1: "Administrators shall review logs. Auditors shall review logs."}
    recs = [{"chunk_id": 1, "source_ref": "1.1", "source_quote": "review logs"}, {"chunk_id": 1, "source_ref": "1.2", "source_quote": "review logs"}]
    out, counts = SE.explain_records(recs, raw)
    assert len(out) == 2 and counts["merged"] == 0 and counts["ambiguous"] == 2  # two citations, two records: neither may be dropped because their text is the same


def test_step_d_keeps_the_root_exactly_as_requirement_finding_returned_it(tmp_path):
    """Invariant: after normalizing, every record's source_quote is a quote requirement finding returned (trimmed), and the explained layer sits beside it."""
    from pipeline import parse_and_normalize as PN
    chunks = [{"chunk_id": 0, "page_start": 1, "page_end": 1, "section_title_path": ["Logs"], "section_ref_path": ["1"], "breadcrumb": "Logs",
               "raw_text": "1.1.  Commanders shall review logs monthly, and report findings to the CIO.\n1.2.  AFMC will:\n- 1.2.1.  Identify funding requirements within AFMC.",
               "text": "[Logs]\n1.1.  Commanders shall review logs monthly, and report findings to the CIO.\n1.2.  AFMC will:\n- 1.2.1.  Identify funding requirements within AFMC."}]
    extracted = [{"chunk_id": 0, "requirement_id": "R-0-0", "source_ref": "1.1", "source_quote": "  review logs monthly  "},
                 {"chunk_id": 0, "requirement_id": "R-0-1", "source_ref": "1.2.1", "source_quote": "AFMC will: Identify funding requirements within AFMC."}]
    (tmp_path / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    (tmp_path / "doc_extracted_requirements.jsonl").write_text("".join(json.dumps(r) + "\n" for r in extracted), encoding="utf-8")
    out = PN.run(str(tmp_path / "doc_extracted_requirements.jsonl"), str(tmp_path / "doc_chunks.jsonl"), "", str(tmp_path))
    records = [json.loads(line) for line in open(out, encoding="utf-8")]
    returned = {r["source_quote"].strip() for r in extracted}
    assert records and all(r["source_quote"] in returned for r in records)
    by_ref = {r["source_ref"]: r for r in records}
    assert by_ref["1.1"]["explained_text"] == "Commanders shall review logs monthly, and report findings to the CIO."
    assert by_ref["1.2.1"]["explained_text"] == "AFMC will: Identify funding requirements within AFMC." and by_ref["1.2.1"]["anchor_status"] == "lead_in_joined"
    assert len({r["requirement_id"] for r in records}) == len(records)


def test_table_rows_that_differ_only_in_their_last_words_are_not_merged():
    raw = {1: "If the originator / recipient of the incident report (IR) is\n| End user | then take the indicated actions |\n| CST/CSL | then take the indicated actions |"}
    recs = [{"chunk_id": 1, "source_quote": "If the originator / recipient of the incident report (IR) is End user", "anchor_status": "words_trimmed", "anchor_trim_side": "end",
             "anchor_text": "If the originator / recipient of the incident report (IR) is"},
            {"chunk_id": 1, "source_quote": "If the originator / recipient of the incident report (IR) is CST/CSL", "anchor_status": "words_trimmed", "anchor_trim_side": "end",
             "anchor_text": "If the originator / recipient of the incident report (IR) is"}]
    out, counts = SE.explain_records(recs, raw)
    assert len(out) == 2 and counts["merged"] == 0 and out[0]["explained_text"].endswith("End user") and out[1]["explained_text"].endswith("CST/CSL")


def test_a_definition_whose_front_words_were_trimmed_and_cannot_be_expanded_keeps_its_root():
    raw = {1: "authorizing official Defined in Committee on National Security Systems Instruction (CNSSI) No. 4009. " + "filler words here " * 60}
    rec = {"chunk_id": 1, "source_quote": "authorizing official is Defined in Committee on National Security Systems Instruction (CNSSI) No. 4009.", "anchor_status": "words_trimmed", "anchor_trim_side": "front",
           "anchor_text": "Defined in Committee on National Security Systems Instruction (CNSSI) No. 4009."}
    out, _ = SE.explain_records([rec], raw)
    assert out[0]["explained_text"] == rec["source_quote"]
    assert not any("taken off" in n for n in out[0]["explain_notes"]) and any("were kept" in n for n in out[0]["explain_notes"])


def test_the_note_says_when_only_a_list_number_was_taken_off():
    out, _ = SE.explain_records([{"chunk_id": 1, "source_quote": "(3) Inform the CSAO of concerns raised by the subordinate elements."}], {1: "(3)  Inform the CSAO of concerns raised by the subordinate elements."})
    assert out[0]["explained_text"] == "Inform the CSAO of concerns raised by the subordinate elements." and out[0]["explain_notes"] == ["list number or dash taken off"]


def test_the_previous_chunk_is_used_for_a_lead_in_only_inside_the_same_section():
    raws = {1: "Some intro here.\nThe Wing Commander shall:\n- a. Appoint a monitor.", 2: "- b. Brief the staff weekly and keep the records."}
    rec = {"chunk_id": 2, "source_quote": "Brief the staff weekly and keep the records."}
    same, _ = SE.explain_records([rec], raws, {1: (("4",), ("Duties",)), 2: (("4",), ("Duties",))})
    other, _ = SE.explain_records([rec], raws, {1: (("4",), ("Duties",)), 2: (("5",), ("Reports",))})
    legacy, _ = SE.explain_records([rec], raws)  # no section information: as before
    assert same[0]["explained_text"].startswith("The Wing Commander shall: Brief")
    assert other[0]["explained_text"] == "Brief the staff weekly and keep the records."
    assert legacy[0]["explained_text"].startswith("The Wing Commander shall:")
