"""The sentence helpers (WP-45.14) and the explained layer built from a clause (WP-4 of the extraction replacement).

`expand()` and the same-sentence merge were deleted with the list-writing extraction step; the sentence-boundary rules they were tested
through live on in `split_sentences` (used by the lead-in rule), so those cases are kept here against it."""
from pipeline import sentence_expand as SE


def test_abbreviations_initials_and_decimals_do_not_end_a_sentence():
    text = "See U.S. Code for details. The unit shall comply with e.g. AFI 17-203 and J. Smith's guidance within 5.5 days. Done."
    assert SE.split_sentences(text) == ["See U.S. Code for details.", "The unit shall comply with e.g. AFI 17-203 and J. Smith's guidance within 5.5 days.", "Done."]


def test_a_paragraph_number_does_not_end_a_sentence():
    text = "3.6.1.1. Ensure the accuracy of incident reports. 3.6.1.2. Characterize the impact."
    assert SE.split_sentences(text) == ["3.6.1.1. Ensure the accuracy of incident reports.", "3.6.1.2. Characterize the impact."]


def test_a_bracketed_reference_label_ends_a_sentence_and_an_initial_does_not():
    text = "Services shall report IAW section 1 (b).(iv).(D) of reference (k). Points of contact are listed in Enclosure A."
    assert SE.split_sentences(text) == ["Services shall report IAW section 1 (b).(iv).(D) of reference (k).", "Points of contact are listed in Enclosure A."]
    assert SE.split_sentences("Briefed by J. Smith on the plan. Then it ended.") == ["Briefed by J. Smith on the plan.", "Then it ended."]


def test_a_sentence_ending_in_a_dotted_citation_still_ends_there():
    text = "Components shall implement the controls in DoDI 8510.01. Reports go to the CIO."
    assert SE.split_sentences(text) == ["Components shall implement the controls in DoDI 8510.01.", "Reports go to the CIO."]


def test_tidy_and_flex_pattern():
    assert SE.tidy("Units shall retain logs  for one year (T-2) .") == "Units shall retain logs for one year (T-2)."
    assert SE.tidy("( a ) item") == "(a) item"
    assert SE.flex_pattern("retain logs (T-2).").search("Units shall retain  logs ( T-2) . Next") is not None


def test_completeness_check():
    assert SE.is_complete("The unit shall report.") and SE.is_complete("(a) The unit shall report to:") and SE.is_complete("3 units shall report.")
    assert not SE.is_complete("installation of vulnerable applications, and other breaches of existing policy")
    assert not SE.is_complete("The unit shall report to the") and not SE.is_complete("then take the indicated Actions") and not SE.is_complete("")


def test_expand_is_gone():
    assert not hasattr(SE, "expand")


def _rec(chunk_id, raw, quote):
    start = raw.index(quote)
    return {"chunk_id": chunk_id, "source_quote": quote, "anchor_start": start, "anchor_end": start + len(quote)}


def test_the_explained_sentence_is_the_clause_without_its_marker_and_the_root_never_changes():
    raw = "- a. Appoint a monitor.\n3. (a)  Enhance baseline standards in accordance with DoDI 8500.01.\nUnits shall retain logs for one year (T-2)."
    recs = [_rec(1, raw, "- a. Appoint a monitor."), _rec(1, raw, "3. (a)  Enhance baseline standards in accordance with DoDI 8500.01."),
            _rec(1, raw, "Units shall retain logs for one year (T-2).")]
    out, counts = SE.explain_records(recs, {1: raw})
    assert [r["source_quote"] for r in out] == [r["source_quote"] for r in recs]  # roots untouched
    assert [r["explained_text"] for r in out] == ["Appoint a monitor.", "Enhance baseline standards in accordance with DoDI 8500.01.",
                                                  "Units shall retain logs for one year (T-2)."]
    assert out[0]["explain_notes"] == ["list number or dash taken off"] and out[2]["explain_notes"] == []
    assert counts == {"marker_removed": 2, "lead_in_attached": 0}


def test_a_list_item_gets_its_lead_in_in_front():
    raw = "The Wing Commander shall:\na. Appoint a monitor.\nb. Brief the staff weekly."
    out, counts = SE.explain_records([_rec(1, raw, "b. Brief the staff weekly.")], {1: raw})
    assert out[0]["explained_text"] == "The Wing Commander shall: Brief the staff weekly."
    assert out[0]["explained_parts"] == [{"kind": "lead_in", "text": "The Wing Commander shall:", "origin": "rule"},
                                         {"kind": "sentence", "text": "Brief the staff weekly.", "origin": "rule"}]
    assert counts["lead_in_attached"] == 1


def test_the_previous_chunk_is_used_for_a_lead_in_only_inside_the_same_section():
    raws = {1: "Some intro here.\nThe Wing Commander shall:\n- a. Appoint a monitor.", 2: "- b. Brief the staff weekly and keep the records."}
    rec = _rec(2, raws[2], "- b. Brief the staff weekly and keep the records.")
    same, _ = SE.explain_records([rec], raws, {1: (("4",), ("Duties",)), 2: (("4",), ("Duties",))})
    other, _ = SE.explain_records([rec], raws, {1: (("4",), ("Duties",)), 2: (("5",), ("Reports",))})
    legacy, _ = SE.explain_records([rec], raws)  # no section information
    assert same[0]["explained_text"] == "The Wing Commander shall: Brief the staff weekly and keep the records."
    assert other[0]["explained_text"] == "Brief the staff weekly and keep the records."
    assert legacy[0]["explained_text"].startswith("The Wing Commander shall:")


def test_records_are_never_merged():
    raw = "| Yes | Report it. |\n| Yes | Report it. |"
    recs = [{"chunk_id": 1, "source_quote": "| Yes | Report it. |", "anchor_start": 0, "anchor_end": 20},
            {"chunk_id": 1, "source_quote": "| Yes | Report it. |", "anchor_start": 21, "anchor_end": 41}]
    out, _ = SE.explain_records(recs, {1: raw})
    assert len(out) == 2 and all("merged_roots" not in r for r in out)
