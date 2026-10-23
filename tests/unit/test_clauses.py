"""The clause splitter (pipeline/clauses.py): exact offsets, sentence and line rules, lead-in context. Expected values are written by hand."""
from pipeline.clauses import chunk_clauses, chunk_unit, clauses_of, split_clauses


def _texts(text):
    return [text[s:e] for s, e in split_clauses(text)]


def _unit(text, heading="", ref=""):
    return {"unit_id": 7, "text": text, "heading": heading, "ref": ref}


def test_offsets_are_exact_and_the_clause_is_the_slice():
    text = "Units shall retain logs. Owners will review them."
    assert split_clauses(text) == [(0, 25), (25, 49)]
    assert _texts(text) == ["Units shall retain logs. ", "Owners will review them."]
    for c in clauses_of(_unit(text)):
        assert text[c["start"]:c["end"]] == c["text"]


def test_abbreviations_do_not_end_a_sentence():
    text = "Follow U.S. Code requirements. Use tools, e.g. Scanners and loggers. See para. 4 of the plan. Apply E.O. 13526 rules."
    assert _texts(text) == [
        "Follow U.S. Code requirements. ",
        "Use tools, e.g. Scanners and loggers. ",
        "See para. 4 of the plan. ",
        "Apply E.O. 13526 rules.",
    ]


def test_a_tier_tag_does_not_start_a_new_sentence():
    text = "The wing will keep records. (T-2). The unit will report. (T-3)"
    assert _texts(text) == ["The wing will keep records. (T-2). ", "The unit will report. (T-3)"]


def test_a_two_level_paragraph_number_stays_with_its_text():
    text = "3.6. Incident Analysis. The CFP will review. 2.1 Units will report."
    assert _texts(text) == ["3.6. Incident Analysis. ", "The CFP will review. ", "2.1 Units will report."]


def test_a_deeper_paragraph_number_is_cut_off_and_dropped_as_the_experiment_measured():
    # "3.6.1.1." is not protected (only d.d. is), so the cut falls after it and the number alone has no letters: it is dropped.
    # The clause text starts at the sentence; the number stays in the chunk text just before the clause start.
    text = "3.6.1.1. The CFP will ensure accuracy. 3.6.1.2. The CFP will characterize impact."
    assert _texts(text) == ["The CFP will ensure accuracy. ", "The CFP will characterize impact."]
    assert split_clauses(text)[0] == (9, 39)


def test_list_markers_start_their_own_clause():
    text = "The Director will:\n(a) review the logs\n1. approve the plan\n- sign the form\n• file the copy"
    assert _texts(text) == ["The Director will:", "(a) review the logs", "1. approve the plan", "- sign the form", "• file the copy"]


def test_table_grid_lines_are_one_clause_each_and_separator_lines_are_skipped():
    text = "| Role | Duty |\n|---|---|\n| ISSM | Reviews logs |\n| ISSO | Files reports |"
    assert _texts(text) == ["| Role | Duty |", "| ISSM | Reviews logs |", "| ISSO | Files reports |"]


def test_a_hard_line_wrap_is_joined_into_one_clause():
    text = "The commander will ensure that all\npersonnel complete training annually."
    assert split_clauses(text) == [(0, len(text))]
    assert _texts(text) == ["The commander will ensure that all\npersonnel complete training annually."]


def test_a_line_after_a_finished_sentence_is_not_joined():
    text = "Units will report.\nthe next line starts lower case."
    assert _texts(text) == ["Units will report.", "the next line starts lower case."]


def test_a_line_that_does_not_start_a_list_is_joined_to_an_unfinished_list_item():
    text = "- review logs\nThe ISSO will:"
    assert _texts(text) == ["- review logs\nThe ISSO will:"]


def test_a_blank_line_breaks_a_block():
    text = "The commander will ensure that all\n\npersonnel complete training."
    assert _texts(text) == ["The commander will ensure that all", "personnel complete training."]


def test_a_clause_without_two_letters_in_a_row_is_dropped():
    assert _texts("12\n\n3.4.\nA b.") == []


def test_lead_in_detection_and_context():
    text = "Background text. The ISSM will:\n- review logs\n- file reports"
    cl = clauses_of(_unit(text, heading="Chapter 3", ref="3.6"))
    assert [c["text"] for c in cl] == ["Background text. ", "The ISSM will:", "- review logs", "- file reports"]
    assert [c["is_lead_in"] for c in cl] == [False, True, False, False]
    assert [c["ctx_lead"] for c in cl] == [None, None, "The ISSM will:", "The ISSM will:"]
    assert [c["clause_index"] for c in cl] == [0, 1, 2, 3]
    assert {c["heading"] for c in cl} == {"Chapter 3"}
    assert {c["ref"] for c in cl} == {"3.6"}
    assert {c["chunk_id"] for c in cl} == {7}


def test_the_context_lead_in_resets_at_the_next_lead_in():
    text = "The ISSM will:\n- review logs.\nThe ISSO will:\n- file reports"
    cl = clauses_of(_unit(text))
    assert [(c["text"], c["ctx_lead"]) for c in cl] == [
        ("The ISSM will:", None),
        ("- review logs.", "The ISSM will:"),
        ("The ISSO will:", None),
        ("- file reports", "The ISSO will:"),
    ]


def test_chunk_unit_uses_raw_text_parent_header_and_the_last_section_ref():
    chunk = {"chunk_id": 3, "raw_text": "Units will report.", "text": "[Crumb]\n\nUnits will report.", "breadcrumb": "Crumb",
             "parent_header_text": "1.2. Reporting", "section_ref_path": ["1", "1.2"]}
    assert chunk_unit(chunk) == {"unit_id": 3, "text": "Units will report.", "heading": "1.2. Reporting", "ref": "1.2"}
    old = {"chunk_id": 4, "text": "Units will report.", "breadcrumb": "Crumb", "section_ref_path": "['1', '1.3']"}
    assert chunk_unit(old) == {"unit_id": 4, "text": "Units will report.", "heading": "Crumb", "ref": "1.3"}
    assert chunk_unit({"chunk_id": 5, "raw_text": "x"})["ref"] == ""
    assert [c["text"] for c in chunk_clauses(chunk)] == ["Units will report."]


def test_every_closing_delimiter_after_a_sentence_end_stays_with_its_clause():
    # Codex P2 on #361: the cut kept only the first closer, so ")" was in no clause.
    text = 'The policy says ("Report.") Owners comply.'
    assert _texts(text) == ['The policy says ("Report.")', "Owners comply."]


def test_a_lead_in_with_a_tier_tag_after_its_colon_is_a_lead_in():
    # Codex P2 on #361 (one case in the library, afi90-802): "options: (T-2)." governs the list under it.
    text = "Training will use one of the following options: (T-2).\n- classroom courses"
    cl = clauses_of(_unit(text))
    assert [(c["text"], c["is_lead_in"], c["ctx_lead"]) for c in cl] == [
        ("Training will use one of the following options: (T-2).", True, None),
        ("- classroom courses", False, "Training will use one of the following options: (T-2)."),
    ]


def test_a_new_sentence_after_a_tier_tag_is_cut_off():
    text = "A copy of the letter will be provided to the office. (T-1) In addition:\n(1) Do x."
    assert _texts(text) == ["A copy of the letter will be provided to the office. (T-1)", "In addition:", "(1) Do x."]


def test_a_tier_tag_in_the_middle_of_a_sentence_does_not_cut():
    text = "Advocate in accordance with DoDI 8500.01, (T-0) AFI 17-130, and more. (T-2)"
    assert _texts(text) == [text]
