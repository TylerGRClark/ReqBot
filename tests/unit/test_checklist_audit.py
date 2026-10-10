"""WP-46.1: the checklist's audit layout — who a row applies to, the document's own passage, and specific rule-based flags."""
import json

from services import checklist_audit as A
from services.checklist_service import generate


def test_applies_to_is_the_leaf_heading_only_when_it_names_the_responsible_party():
    assert A.applies_to(["ROLES AND RESPONSIBILITIES", "2.17. MAJCOM/DRUs."]) == "MAJCOM/DRUs."
    assert A.applies_to(["SECTION 2", "The DAF Chief Information Officer (SAF/CN) shall:"]) == "The DAF Chief Information Officer (SAF/CN) shall:"
    assert A.applies_to(["ROLES AND RESPONSIBILITIES", "2.1. Purpose"]) == ""  # a procedural label names no one
    assert A.applies_to(["Containment", "3.5.1. Preliminary response"]) == ""  # no responsibilities ancestor, no colon
    assert A.applies_to([]) == "" and A.applies_to(None) == ""


def test_flags_are_specific_and_never_remove_a_row():
    assert A.item_flags("Research actions that can be taken to respond.", "3.6.1.4", "") == ["no_stated_actor"]
    assert A.item_flags("Research actions that can be taken to respond.", "3.6.1.4", "AF/A3") == []  # the role heading supplies the actor
    assert A.item_flags("Supports USCYBERCOM in Mission Analysis development.", "2.5.1", "SAF/AAZ.") == []  # third-person duty under a role heading
    assert "starts_mid_sentence" in A.item_flags("and the Primary Recipient will be", "Table 3.1", "")
    assert "table_fragment" in A.item_flags("and the Primary Recipient will be", "Table 3.1", "")
    assert "list_item" in A.item_flags("(2) Send a copy of the letter to the CISO.", "5.1", "")
    assert "definition_or_description" in A.item_flags("The report breaks down adverse actions into ten categories.", "1.2", "")
    assert "definition_or_description" not in A.item_flags("Issues cyber orders to subordinate wings via the 624 OC.", "2.5.1", "SAF/AAZ.")
    assert A.item_flags("The Director shall report monthly.", "1.2", "") == []


def test_passage_is_verbatim_with_the_quote_marked_and_tolerates_spacing():
    chunk = {"raw_text": "3.1. Intro text. The CFP shall  notify the MCCC ( see Table 1 ) .\nNext paragraph."}
    passage, found = A.build_passage("The CFP shall notify the MCCC (see Table 1).", chunk)
    assert found and ">> The CFP shall  notify the MCCC ( see Table 1 ) . <<" in passage
    assert passage.startswith("3.1. Intro text.") and passage.endswith("Next paragraph.")


def test_a_list_item_gets_the_tail_of_the_previous_chunk_in_front():
    prev = {"raw_text": "x" * 800 + " The Director will:"}
    chunk = {"raw_text": "(a) Review logs monthly."}
    passage, found = A.build_passage("(a) Review logs monthly.", chunk, prev, flags=["list_item"])
    assert found and passage.startswith("... ") and "The Director will:" in passage and ">> (a) Review logs monthly. <<" in passage
    assert len(passage) < 700  # only the tail, not the whole previous chunk
    plain, _ = A.build_passage("(a) Review logs monthly.", chunk, prev, flags=[])
    assert "The Director will:" not in plain


def test_missing_chunk_or_unlocated_quote_is_reported_not_hidden():
    assert A.build_passage("anything", None) == ("", False)
    passage, found = A.build_passage("text that is not there", {"raw_text": "The chunk says something else."})
    assert not found and passage == "The chunk says something else."


def test_generate_adds_the_audit_layout_and_flags_a_missing_chunk_file(tmp_path):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "(a) Review logs monthly.", "source_ref": "2.1", "chunk_id": 2, "section_title_path": ["ROLES AND RESPONSIBILITIES", "2.1. AF/A3"],
           "domain_tags": ["x"], "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "doc_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    no_chunks = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert no_chunks["passage"] == "" and "no_passage" in no_chunks["item_flags"] and no_chunks["applies_to"] == "AF/A3"
    chunks = [{"chunk_id": 1, "raw_text": "The Director will:"}, {"chunk_id": 2, "raw_text": "(a) Review logs monthly."}]
    (run_dir / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
    result = generate(tmp_path, "doc", "cybersecurity")
    item = result["items"][0]
    assert result["format_version"] == "1.1" and "The Director will:" in item["passage"] and ">> (a) Review logs monthly. <<" in item["passage"]
    assert "no_passage" not in item["item_flags"] and "list_item" in item["item_flags"]
    assert result["summary"]["items_with_flags"] == 1


def test_chunk_file_is_found_when_the_document_name_contains_requirements(tmp_path):
    run_dir = tmp_path / "policy_requirements_v1_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "Review logs monthly.", "source_ref": "2.1", "chunk_id": 1, "section_title_path": ["Logs"], "domain_tags": ["x"],
           "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "policy_requirements_v1_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    (run_dir / "policy_requirements_v1_chunks.jsonl").write_text(json.dumps({"chunk_id": 1, "raw_text": "Review logs monthly."}) + "\n")
    item = generate(tmp_path, "policy_requirements_v1", "cybersecurity")["items"][0]
    assert "no_passage" not in item["item_flags"] and ">> Review logs monthly. <<" in item["passage"]


def test_parent_paragraph_comes_from_the_documents_own_numbering():
    units = ["2.5.1.1.7. Directorate of Security (SAF/AAZ).", "2.5.1.1.7.1. Coordinates AF-wide activities.", "2.17. MAJCOM/DRUs.", "2.18. Responsibilities."]
    pm = A.paragraph_map(units)
    assert pm["2.5.1.1.7"] == "Directorate of Security (SAF/AAZ)."
    assert A.parent_paragraph("2.5.1.1.7.2", pm) == ("2.5.1.1.7", "Directorate of Security (SAF/AAZ).")
    assert A.parent_paragraph("2.17.22", pm) == ("2.17", "MAJCOM/DRUs.")
    assert A.parent_paragraph("2.5.1.1.7.1.1.1", pm)[0] == "2.5.1.1.7.1"  # the nearest ancestor that exists
    assert A.parent_paragraph("2.18.1", pm) == ("", "")  # a generic label names no one
    assert A.parent_paragraph("(T-2)", pm) == ("", "") and A.parent_paragraph("Table 3.1", pm) == ("", "") and A.parent_paragraph("", pm) == ("", "")
    assert A.parent_paragraph("3.1", pm) == ("", "")  # a two-part number has only a top-level parent, which is the section path


def test_generate_fills_the_parent_paragraph_from_headings_and_chunk_text(tmp_path):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    rec = {"requirement_id": "REQ-1", "source_quote": "Coordinates AF-wide CNDSP activities in accordance with DoDD O-8530.1.", "source_ref": "2.5.1.1.7.1", "chunk_id": 1,
           "section_title_path": ["ROLES", "2.5.1.1.7. Directorate of Security (SAF/AAZ)."], "domain_tags": ["x"], "confidence": 0.9, "page_start": 1, "page_end": 1}
    (run_dir / "doc_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    chunk = {"chunk_id": 1, "raw_text": "2.5.1.1.7.1. Coordinates AF-wide CNDSP activities in accordance with DoDD O-8530.1.", "section_title_path": rec["section_title_path"]}
    (run_dir / "doc_chunks.jsonl").write_text(json.dumps(chunk) + "\n")
    item = generate(tmp_path, "doc", "cybersecurity")["items"][0]
    assert item["parent_ref"] == "2.5.1.1.7" and item["parent_text"].startswith("Directorate of Security")


def test_citation_is_the_paragraph_number_else_read_back_from_the_document():
    assert A.citation("2.5.1.1.7.2", "", []) == "2.5.1.1.7.2"
    assert A.citation("A2.1.3", "", []) == "A2.1.3"  # an annex paragraph is a paragraph number too
    passage = "3.4.3. Preliminary analysis.\n3.4.4.3.  Based on the incident category,\n>> determine if the forensics process should start. <<"
    assert A.citation("(T-2)", passage, []) == "3.4.4.3 (inferred)"
    assert A.citation("", passage, ["INCIDENT HANDLING", "3.4. Detection"]) == "3.4.4.3 (inferred)"
    assert A.citation("Table 3.1", ">> then take the indicated Actions <<", ["INCIDENT HANDLING", "3.4. Detection and Reporting"]) == "3.4 (inferred)"
    assert A.citation("", ">> orphan quote <<", ["INCIDENT HANDLING"]) == ""
    assert "(inferred)" not in A.citation("3.1", passage, [])  # a real reference is kept as extracted


def test_table_label_reads_the_caption_and_follows_a_table_across_chunks():
    grid = "| a | b |\n|---|---|\n| 1 | 2 |"
    chunks = {1: {"raw_text": "3.3.1. Objectives. Some paragraph."}, 2: {"raw_text": "Table 3.1.  Incident Reporting Action Matrix.\n\n" + grid}, 3: {"raw_text": grid},
              4: {"raw_text": "A paragraph after the table."}, 5: {"raw_text": grid}, 6: {"raw_text": "Table 3.1 shows the matrix.\n" + grid}}
    assert A.table_label(chunks, 2) == ("Table 3.1", "Table 3.1 Incident Reporting Action Matrix")
    assert A.table_label(chunks, 3) == ("Table 3.1", "Table 3.1 Incident Reporting Action Matrix")  # the table runs on into the next chunk, which has no caption
    assert A.table_label(chunks, 1) == ("", "") and A.table_label(chunks, 4) == ("", "")  # ordinary paragraphs
    assert A.table_label(chunks, 5) == ("", "")  # a grid with no caption anywhere before it has no label to give
    assert A.table_label(chunks, 6) == ("", "")  # "Table 3.1 shows ..." is prose, not a caption (a caption has a full stop after the number)
    assert A.table_label(chunks, None) == ("", "") and A.table_label({}, 2) == ("", "")
    # an attachment table ("Table A2.1") is a table too
    attach = {1: {"raw_text": "Table A2.1.  AF Critical Asset Identification Process.\n\n" + grid}}
    assert A.table_label(attach, 1) == ("Table A2.1", "Table A2.1 AF Critical Asset Identification Process")


def test_a_merged_chunk_with_prose_before_the_table_is_the_tables_only_after_the_caption():
    raw = "2.1. Intro paragraph. The CFP will notify the MCCC.\n\nTable 3.1.  Reporting Matrix.\n\n| If the originator is | then |\n|---|---|\n| the AFOSI | notify the CFP |"
    chunks = {7: {"raw_text": raw}, 8: {"raw_text": "| more | rows |\n| a | b |"}}
    assert A.table_label(chunks, 7, "notify the CFP") == ("Table 3.1", "Table 3.1 Reporting Matrix")  # a cell, located after the caption
    assert A.table_label(chunks, 7, "The CFP will notify the MCCC.") == ("", "")  # the prose in front of the table keeps its paragraph citation
    assert A.table_label(chunks, 7, "text that is nowhere in the chunk") == ("", "") and A.table_label(chunks, 7) == ("", "")  # not located: no guess
    assert A.table_label(chunks, 8, "more") == ("Table 3.1", "Table 3.1 Reporting Matrix")  # the grid runs on into the next chunk


def test_a_grid_chunk_continues_a_table_only_when_it_picks_up_the_same_grid():
    grid = "| a | b |\n|---|---|\n| 1 | 2 |"
    captioned = "Table 3.1.  First.\n\n" + grid
    assert A.table_label({1: {"raw_text": captioned}, 2: {"raw_text": grid}}, 2) == ("Table 3.1", "Table 3.1 First")
    assert A.table_label({1: {"raw_text": captioned + "\n\nA paragraph after the table."}, 2: {"raw_text": grid}}, 2) == ("", "")  # the table ended before the chunk did
    assert A.table_label({1: {"raw_text": captioned}, 2: {"raw_text": "| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |"}}, 2) == ("", "")  # a different grid with no caption of its own
    assert A.table_label({1: {"raw_text": captioned}, 2: {"raw_text": "Intro line.\n\n" + grid}}, 2) == ("", "")  # prose first: not the same grid carrying on


def test_a_merged_chunk_with_two_tables_gives_each_row_the_nearest_caption_before_it():
    raw = ("Table 3.1.  First.\n\n| a | b |\n|---|---|\n| x1 | y1 |\n\nA paragraph between the tables says they will meet.\n\n"
           "Table 3.2.  Second.\n\n| c | d |\n|---|---|\n| x2 | y2 |")
    chunks = {3: {"raw_text": raw}}
    assert A.table_label(chunks, 3, "x1 | y1") == ("Table 3.1", "Table 3.1 First")
    assert A.table_label(chunks, 3, "x2 | y2") == ("Table 3.2", "Table 3.2 Second")
    assert A.table_label(chunks, 3, "Second. | c | d |") == ("Table 3.2", "Table 3.2 Second")  # a quote that starts on the caption line belongs to that table
    assert A.table_label(chunks, 3, "A paragraph between the tables says they will meet.") == ("", "")  # prose between the tables is not a table row
    assert A.table_label(chunks, 3, "a row joined from cells that is not in the chunk") == ("", "")  # two tables and no position: no guess


def test_a_row_from_a_table_is_cited_by_the_table_and_names_no_party(tmp_path):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    grid = "| If the originator is | then take the indicated Actions |\n|---|---|\n| the AFOSI | notify the CFP |"
    recs = [{"requirement_id": "REQ-1", "source_quote": "then take the indicated Actions", "source_ref": "", "chunk_id": 2, "page_start": 14, "page_end": 14,
             "section_title_path": ["INCIDENT HANDLING", "3.3.1. Objectives."], "domain_tags": [], "confidence": None},
            {"requirement_id": "REQ-2", "source_quote": "Notify the CFP within one hour.", "source_ref": "3.3.2", "chunk_id": 3, "page_start": 15, "page_end": 15,
             "section_title_path": ["INCIDENT HANDLING", "3.3.1. Objectives."], "domain_tags": [], "confidence": None}]
    (run_dir / "doc_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    chunks = [{"chunk_id": 1, "raw_text": "3.3.1. Objectives. Detect events."}, {"chunk_id": 2, "raw_text": "Table 3.1.  Incident Reporting Action Matrix.\n\n" + grid},
              {"chunk_id": 3, "raw_text": "3.3.2. Notify the CFP within one hour."}]
    (run_dir / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
    table_row, paragraph_row = generate(tmp_path, "doc", "cybersecurity")["items"]
    assert table_row["citation"] == "Table 3.1" and table_row["section_heading"] == "Table 3.1 Incident Reporting Action Matrix" and table_row["applies_to"] == ""
    assert paragraph_row["citation"] == "3.3.2" and "Table" not in paragraph_row["section_heading"]  # a row outside the table is cited as before


def test_citation_prefers_the_quotes_own_number_and_never_reads_an_unmarked_passage():
    passage = "3.4.3. Preliminary analysis.\n>> 3.4.4. Assess and categorize the event. <<"
    assert A.citation("SECTION 2", passage, [], "3.4.4. Assess and categorize the event.") == "3.4.4"  # the number the quote opens with is its own
    unmarked = "1.1. Intro.\n9.9. A paragraph somewhere after the requirement, which was not located."
    assert A.citation("", unmarked, ["INCIDENT HANDLING", "3.4. Detection"], "some requirement text") == "3.4 (inferred)"  # no marker: the heading fallback only
    assert A.citation("", unmarked, [], "some requirement text") == ""


def test_section_heading_comes_from_the_numbering_not_the_converters_nesting():
    units = ["3.6. Incident Analysis .  Incident analysis is a series of analytical steps. Include the mission owner in the process.",
             "3.6.1.1. Ensure the accuracy and completeness of incident reports.", "2.5.3. I-NOSCs. The I-NOSCs ...", "3.1. Responsibilities. text"]
    hmap = A.heading_map(["Actions", "3.5.2. Methodology."], units)
    assert hmap["3.6"] == "Incident Analysis" and hmap["3.5.2"] == "Methodology" and "3.6.1.1" not in hmap  # a sentence is not a title
    assert A.section_heading("3.6", hmap) == "3.6 Incident Analysis"
    assert A.section_heading("3.6.1.4 (inferred)", hmap) == "3.6 Incident Analysis"
    assert A.section_heading("3.1.2", hmap) == ""  # a generic label names no section
    assert A.section_heading("", hmap) == "" and A.section_heading("(T-2)", hmap) == ""


def test_applies_to_numbered_names_the_party_from_the_numbered_ancestor_never_from_a_wrong_path():
    units = ["2.5.3. I-NOSCs. The I-NOSCs provide ...", "2.2.12. AFNC3C , as the designated lead organization, will:", "3.6. Incident Analysis .  Steps."]
    hmap = A.heading_map([], units)
    wrong_path = ["ROLES AND RESPONSIBILITIES", "2.2. Directorate of Security (SAF/AAZ)."]  # the converter's nesting is wrong for 2.5.3.x
    assert A.applies_to_numbered("2.5.3.1", hmap, wrong_path) == "I-NOSCs"
    assert A.applies_to_numbered("2.2.12.5", hmap, wrong_path).startswith("AFNC3C")
    assert A.applies_to_numbered("3.6.1.4", hmap, ["Actions", "3.6.1. Objectives."]) == ""  # not a responsibilities section, title does not introduce a list
    assert A.applies_to_numbered("2.9.9.9", hmap, wrong_path) == ""  # dotted number, no titled ancestor: blank, not the wrong path's party
    assert A.applies_to_numbered("(T-2)", hmap, wrong_path) is None and A.applies_to_numbered("2.1", {}, wrong_path) is None  # no numbering knowledge: use the path


def test_a_numbered_lead_in_paragraph_titles_its_children_with_the_sentence_that_introduces_the_list():
    hmap = A.heading_map([], ["2.3.1. AFOSI is a Federal Law Enforcement agency and a member of the Intelligence Community. The AFOSI:"])
    assert hmap["2.3.1"] == "The AFOSI:"


def test_a_chunk_with_one_numbered_paragraph_keeps_its_number_with_its_text():
    from services import checklist_missed as MM
    units = MM.paragraph_units("3.6. Incident Analysis .  Incident analysis is a series of analytical steps. Include the mission owner in the process.")
    assert units[0].startswith("3.6. Incident Analysis") and A.heading_map([], units)["3.6"] == "Incident Analysis"


def test_attachment_paragraph_numbers_are_numbers_too():
    hmap = A.heading_map([], ["A2.2. Reporting Chain. The chain is ...", "A2.2.3.1. Report within 24 hours."])
    assert hmap["A2.2"] == "Reporting Chain"
    assert A.section_heading("A2.2.3.1", hmap) == "A2.2 Reporting Chain"
    assert A.parent_paragraph("A2.2.3.1", A.paragraph_map(["A2.2.3. Parent text here.", "A2.2.3.1. Child."])) == ("A2.2.3", "Parent text here.")


def test_applicability_statements_are_hinted_not_dropped():
    for text in ("This Instruction also applies to incidents involving systems which are not directly connected to an AF network.",
                 "This Instruction does not apply to AF Intelligence Community systems, networks and assets.",
                 "It applies to all military and civilian AF personnel, members of the AF Reserve and DoD contractors."):
        assert "applicability_statement" in A.item_flags(text, "1.1", ""), text
    assert "applicability_statement" not in A.item_flags("The CFP shall apply the patch within 24 hours.", "3.1", "")
    assert "applicability_statement" not in A.item_flags("Units will apply the guidance in this Instruction when reporting.", "3.1", "")
    assert "applicability_statement" in A.item_flags("1.1. It applies to all personnel.", "1.1", "")  # a retained paragraph number is allowed before the pronoun
    assert "applicability_statement" not in A.item_flags("This Instruction requires commanders to apply the controls within 30 days.", "3.1", "")
    assert "applicability_statement" not in A.item_flags("The organizations to which this instruction applies must act within 30 days.", "3.1", "")
