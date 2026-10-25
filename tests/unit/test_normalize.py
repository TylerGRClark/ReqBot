import json
from pathlib import Path

import pytest

from pipeline.parse_and_normalize import (
    SCHEMA_VERSION,
    OldExtractionFormatError,
    _is_heading_echo,
    _is_orphaned_list_item,
    clause_offset_mismatch,
    compute_stable_id,
    deduplicate_requirements,
    run,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _chunk(chunk_id: int, text: str, **extra) -> dict:
    return {
        "chunk_id": chunk_id,
        "page_start": 1, "page_end": 1,
        "text": text, "raw_text": text,
        "section_ref_path": [], "section_title_path": [],
        "parent_header_text": None, "parent_context": None,
        "document_id": "abc123", "source_pdf": "TEST.pdf",
        **extra,
    }


def _row(chunk: dict, quote: str, clause_index: int = 0, label: str = "DUTY", **extra) -> dict:
    """A row as clause labeling writes it: the quote is the chunk's own text at its offsets."""
    start = chunk["raw_text"].index(quote)
    return {
        "requirement_id": f"R-{chunk['chunk_id']}-{clause_index}",
        "description": "", "source_ref": "", "source_ref_origin": "none", "domain_tags": [], "requirement_type": "",
        "source_quote": quote, "chunk_id": chunk["chunk_id"], "clause_index": clause_index, "clause_label": label,
        "anchor_status": "exact", "anchor_start": start, "anchor_end": start + len(quote), "anchor_text": quote,
        "extraction_model": "labeler:1b", "label_prompt_sha": "abc", "schema_version": "3.0", "pipeline_version": "2.0",
        **extra,
    }


def _run(tmp_path, chunks: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    req_path = tmp_path / "test_extracted_requirements.jsonl"
    chunks_path = tmp_path / "test_chunks.jsonl"
    _write_jsonl(req_path, rows)
    _write_jsonl(chunks_path, chunks)
    out_dir = tmp_path / "out"
    run(str(req_path), str(chunks_path), "", str(out_dir))
    return _read_jsonl(out_dir / "test_requirements_normalized.jsonl"), _read_jsonl(out_dir / "test_normalization_failures.jsonl")


SAMPLE_TEXT = "1.1. Systems must enforce role-based access control policies."
SAMPLE_QUOTE = "Systems must enforce role-based access control policies."


def test_stable_id_is_deterministic():
    id1 = compute_stable_id("docabc123", "1.1", "Systems must enforce RBAC.", None, "technical-control", "Enforce RBAC.")
    id2 = compute_stable_id("docabc123", "1.1", "Systems must enforce RBAC.", None, "technical-control", "Enforce RBAC.")
    assert id1 == id2
    assert id1.startswith("REQ-")


def test_stable_id_differs_for_different_quotes():
    id1 = compute_stable_id("doc123", "1.1", "Quote A here.", None, "technical-control", "Desc A")
    id2 = compute_stable_id("doc123", "1.1", "Quote B here.", None, "technical-control", "Desc B")
    assert id1 != id2


def test_dedup_collapses_the_same_clause_under_the_same_reference(tmp_path):
    chunk = _chunk(1, "| Yes | Report it. |\n| No | Report it. |")
    first = _row(chunk, "| Yes | Report it. |", 0, source_ref="Table 3.1")
    second = dict(_row(chunk, "| No | Report it. |", 1, source_ref="Table 3.1"))
    twin = dict(first, clause_index=2, requirement_id="R-1-2")  # a repeated line: same text, same reference
    records, _ = _run(tmp_path, [chunk], [first, second, twin])
    assert [r["source_quote"] for r in records] == ["| Yes | Report it. |", "| No | Report it. |"]


def test_dedup_keeps_distinct_quotes_that_share_a_source_ref_and_the_shorter_copy():
    a = {"source_ref": "2.1", "source_quote": "The CFP shall notify the MCCC."}
    b = {"source_ref": "2.1", "source_quote": "The CFP  shall notify the MCCC."}  # same quote after whitespace tidying
    c = {"source_ref": "2.1", "source_quote": "The CFP shall file a report."}
    d = {"source_ref": "2.2", "source_quote": "The CFP shall notify the MCCC."}  # same quote, other reference
    out = deduplicate_requirements([a, b, c, d])
    assert out == [a, c, d]


def test_source_quote_required_gate(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    records, failures = _run(tmp_path, [chunk], [dict(_row(chunk, SAMPLE_QUOTE), source_quote="")])
    assert records == []
    assert [f["error"] for f in failures] == ["empty_source_quote"]


def test_hierarchy_fields_populated(tmp_path):
    chunk = _chunk(42, SAMPLE_TEXT, page_end=2, section_ref_path=["1", "1.1"], section_title_path=["Access Control", "Auth Requirements"],
                   parent_header_text="Access Control", parent_context="Section 1. Access Control. All systems must enforce RBAC.")
    records, _ = _run(tmp_path, [chunk], [_row(chunk, SAMPLE_QUOTE)])
    assert len(records) == 1
    r = records[0]
    assert r["section_ref_path"] == ["1", "1.1"]
    assert r["section_title_path"] == ["Access Control", "Auth Requirements"]
    assert r["parent_section_ref"] == "1"
    assert r["parent_context"] == "Section 1. Access Control. All systems must enforce RBAC."
    assert (r["page_start"], r["page_end"]) == (1, 2)


def test_optional_hierarchy_defaults_to_empty(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    records, _ = _run(tmp_path, [chunk], [_row(chunk, SAMPLE_QUOTE)])
    r = records[0]
    assert r["section_ref_path"] == []
    assert r["section_title_path"] == []
    assert r["parent_section_ref"] is None
    assert r["parent_context"] is None
    assert r["child_section_refs"] == []


def test_empty_input_produces_empty_output(tmp_path):
    records, failures = _run(tmp_path, [_chunk(1, SAMPLE_TEXT)], [])
    assert records == [] and failures == []


def test_all_records_missing_source_quote(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    records, failures = _run(tmp_path, [chunk], [dict(_row(chunk, SAMPLE_QUOTE, i), source_quote="") for i in range(3)])
    assert records == []
    assert len(failures) == 3


# Clause labeling (WP-4 of the extraction replacement): the record fields, the offset invariant, and the refusal of the old step's files.

def test_clause_fields_are_carried_through_and_the_schema_is_3(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    row = _row(chunk, SAMPLE_QUOTE, label="UNSURE", source_ref="1.1", source_ref_origin="own_number")
    records, failures = _run(tmp_path, [chunk], [row])
    assert failures == []
    r = records[0]
    assert {k: r[k] for k in ("clause_index", "clause_label", "source_ref_origin", "label_prompt_sha", "anchor_status", "anchor_start", "anchor_end", "anchor_text")} == {
        "clause_index": 0, "clause_label": "UNSURE", "source_ref_origin": "own_number", "label_prompt_sha": "abc", "anchor_status": "exact",
        "anchor_start": 5, "anchor_end": 61, "anchor_text": SAMPLE_QUOTE}
    assert r["source_quote"] == SAMPLE_QUOTE
    assert r["extraction_model"] == "labeler:1b"  # the row's own labeler, not a default
    assert SCHEMA_VERSION == "3.0" and r["schema_version"] == "3.0" and r["pipeline_version"] == "2.0"
    for gone in ("recovered_truncated", "parent_stem", "embedding_text", "merged_roots", "anchor_score", "anchor_lead_in"):
        assert gone not in r


def test_clause_offset_mismatch_rejects_a_row_whose_chunk_changed(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    row = _row(chunk, SAMPLE_QUOTE)
    changed = _chunk(1, "1.1. Systems must enforce mandatory access control policies.")  # re-chunked without a re-label
    with pytest.raises(RuntimeError, match="clause_offset_mismatch"):  # Codex P1 on #365: an invariant violation stops the pipeline instead of dropping rows quietly
        _run(tmp_path, [changed], [row])
    out_dir = tmp_path / "out"  # the files are still written for inspection
    assert _read_jsonl(out_dir / "test_requirements_normalized.jsonl") == []
    assert [f["error"] for f in _read_jsonl(out_dir / "test_normalization_failures.jsonl")] == ["clause_offset_mismatch"]


def test_clause_offset_mismatch_rules():
    raw = "  The unit  shall\n report it ."
    ok = {"source_quote": "The unit shall report it.", "anchor_start": 2, "anchor_end": len(raw)}
    assert clause_offset_mismatch(ok, raw) is False  # whitespace is tidied, nothing else
    assert clause_offset_mismatch(ok, None) is True  # unknown chunk
    assert clause_offset_mismatch(dict(ok, anchor_start=None), raw) is True
    assert clause_offset_mismatch(dict(ok, anchor_end=len(raw) + 1), raw) is True
    assert clause_offset_mismatch(dict(ok, source_quote="The unit shall report it"), raw) is True


def test_an_old_format_extraction_file_is_refused(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    old = {"requirement_id": "R-1", "source_quote": SAMPLE_QUOTE, "source_ref": "1.1", "chunk_id": 1, "recovered_truncated": False}
    with pytest.raises(OldExtractionFormatError, match="clause_index"):
        _run(tmp_path, [chunk], [old])


def test_a_missing_chunk_file_is_an_error(tmp_path):
    req_path = tmp_path / "test_extracted_requirements.jsonl"
    _write_jsonl(req_path, [])
    with pytest.raises(FileNotFoundError):
        run(str(req_path), str(tmp_path / "no_chunks.jsonl"), "", str(tmp_path / "out"))


def test_a_subject_less_clause_is_kept(tmp_path):
    """The dangling-clause rejection was deleted with the switch: "Is designated ..." is a real line of a responsibilities list."""
    text = "2.2.2. Is designated Computer Network Defense Service Provider Certification Authority."
    chunk = _chunk(1, text)
    records, failures = _run(tmp_path, [chunk], [_row(chunk, "Is designated Computer Network Defense Service Provider Certification Authority.")])
    assert len(records) == 1 and failures == []


def test_explained_layer_takes_the_marker_off_and_attaches_the_lead_in(tmp_path):
    text = "3.1. The Director will:\na. Identify the mission owner.\nb. Report incidents to the ISSM."
    chunk = _chunk(1, text)
    rows = [_row(chunk, "The Director will:", 0), _row(chunk, "a. Identify the mission owner.", 1), _row(chunk, "b. Report incidents to the ISSM.", 2)]
    records, failures = _run(tmp_path, [chunk], rows)
    assert failures == []  # the lead-in is kept as a row of its own
    assert [r["source_quote"] for r in records] == ["The Director will:", "a. Identify the mission owner.", "b. Report incidents to the ISSM."]  # the root is never changed
    assert [r["explained_text"] for r in records[1:]] == ["The Director will: Identify the mission owner.", "The Director will: Report incidents to the ISSM."]
    assert records[1]["explained_parts"] == [{"kind": "lead_in", "text": "The Director will:", "origin": "rule"},
                                             {"kind": "sentence", "text": "Identify the mission owner.", "origin": "rule"}]
    assert records[1]["explain_notes"] == ["list number or dash taken off", "lead-in attached from the line above that ends with a colon"]


def test_explained_layer_of_a_plain_sentence_is_the_clause(tmp_path):
    chunk = _chunk(1, SAMPLE_TEXT)
    records, _ = _run(tmp_path, [chunk], [_row(chunk, SAMPLE_QUOTE)])
    assert records[0]["explained_text"] == SAMPLE_QUOTE
    assert records[0]["explain_notes"] == []


def test_two_clauses_of_one_list_item_are_two_rows(tmp_path):
    """No same-sentence merge any more: each clause is its own row."""
    text = "a. Review the plan. Approve the plan."
    chunk = _chunk(1, text)
    records, _ = _run(tmp_path, [chunk], [_row(chunk, "a. Review the plan.", 0), _row(chunk, "Approve the plan.", 1)])
    assert [r["explained_text"] for r in records] == ["Review the plan.", "Approve the plan."]
    assert all("merged_roots" not in r for r in records)


# WP-34.2: heading-echo rejection. Fixtures are the 5
# real examples confirmed in archive/PHASE34_REQUIREMENTS.md (afpd_17-1.pdf and
# CJCSI 6510.02G.pdf docling re-ingests), plus the original WP-33.3 fixture.

def test_is_heading_echo_exact_match():
    assert _is_heading_echo(
        "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY",
        ["Purpose", "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY"],
    )


def test_is_heading_echo_second_real_fixture():
    assert _is_heading_echo(
        "All HAF Functionals, MAJCOMs, DRUs, and FOAs will:",
        ["All HAF Functionals, MAJCOMs, DRUs, and FOAs will:"],
    )


def test_is_heading_echo_trailing_punctuation_still_matches():
    # Minor punctuation difference from the heading shouldn't let a real echo
    # slip through -- fuzz.ratio's tolerance covers this without needing exact
    # string equality.
    assert _is_heading_echo(
        "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY.",
        ["COMPLIANCE WITH THIS PUBLICATION IS MANDATORY"],
    )


def test_is_heading_echo_false_for_unrelated_quote():
    assert not _is_heading_echo("KERs shall be approved by the MC4EB.", ["KER Approval Process"])


def test_is_heading_echo_false_when_heading_word_appears_incidentally():
    # A short, generic heading (e.g. "Purpose") merely appearing as a substring
    # inside a much longer, unrelated real requirement must NOT be flagged --
    # this is why the check uses whole-string fuzz.ratio rather than literal
    # substring containment.
    assert not _is_heading_echo(
        "Access badges shall be issued for the sole purpose of controlling entry to restricted areas.",
        ["Purpose"],
    )


def test_is_heading_echo_false_with_no_hierarchy():
    assert not _is_heading_echo("Any quote text.", [])












def test_is_heading_echo_false_when_no_heading_in_path_matches():
    assert not _is_heading_echo(
        "KERs shall be approved by the MC4EB.",
        ["Purpose", "KER Approval Process", "1.1. Executive Summary"],
    )


def test_is_heading_echo_false_for_none_section_title_path():
    # Gemini review, PR #181: removing the immediate-heading-only check also
    # dropped the guard against section_title_path being None (not just an
    # empty list) -- a bare `for heading in None:` raises TypeError. Must not
    # crash, same as the pre-existing empty-list case.
    assert not _is_heading_echo("Any quote text.", None)




def test_is_orphaned_list_item_no_longer_rejects_short_marker_items():
    # WP-38.2's marker+word-count branch (reject a list-marker-prefixed quote
    # whose remainder is too short) went through four review rounds (Gemini
    # rounds 1 and 6, Codex twice), narrowed 6 -> 3 -> 2 words each time, and
    # was ultimately removed entirely (Codex local review, PR #181, second
    # pass) rather than narrowed a fifth time: no text-level signal
    # distinguishes a short child list item that's genuinely self-contained
    # from one whose obligation is inherited from a parent stem (e.g.
    # REQ-c6aeb8df528b, "(3) Restrain competition." -- item 3 of a "shall not
    # be used to:" prohibition list, meaningless standalone), and rejecting
    # the wrong one silently drops a valid requirement. Product direction
    # (Tyler): preserve short enumerated child items until hierarchy-aware
    # parent-stem + child-item reconstruction exists, rather than filter them
    # here. See _is_orphaned_list_item()'s docstring and
    # archive/PHASE38_REQUIREMENTS.md's WP-38.2 Findings for the full history.
    #
    # This means REQ-c6aeb8df528b is now a known, accepted miss (a visible
    # fragment, not silently dropped) -- pinned here so that's read as
    # deliberate, not an unnoticed regression.
    assert not _is_orphaned_list_item("(3) Restrain competition.")
    assert not _is_orphaned_list_item("(1)")
    assert not _is_orphaned_list_item("(1) Encrypt stored CUI.")
    assert not _is_orphaned_list_item("(1) Encrypt CUI.")
    assert not _is_orphaned_list_item("(2) Patch systems.")
    assert not _is_orphaned_list_item("(a) Report incidents.")


def test_is_orphaned_list_item_defined_in_citation():
    # REQ-4523443092b8 (afi10-2402): the whole quote is just a term plus a
    # citation, no independent obligation content.
    assert _is_orphaned_list_item(
        "Suspicious activity reporting, as defined in DoDI 2000.26, "
        "Suspicious Activity Reporting."
    )


def test_is_orphaned_list_item_false_for_marker_with_real_content():
    # REQ-01a7421e8e0a (DODI 8551.01): a real, self-contained directive that
    # happens to start with a list marker -- must NOT be caught just because
    # of the marker.
    assert not _is_orphaned_list_item(
        "(6) Directs the PPSM PMO to document the assurance category for "
        "all PPS in the CAL."
    )


def test_is_orphaned_list_item_false_for_real_quote_no_marker():
    assert not _is_orphaned_list_item("KERs shall be approved by the MC4EB.")


def test_is_orphaned_list_item_false_for_citation_with_real_clause_after():
    # Gemini + Codex review, PR #181: _DEFINED_IN_CITATION_RE only anchors
    # the start of the quote, so a real requirement that opens with a
    # definitional qualifier but continues with a real governing clause must
    # not be swallowed just because it starts the same way as a genuine
    # citation-only fragment.
    assert not _is_orphaned_list_item(
        "Cybersecurity incidents, as defined in CNSSI 4009, shall be "
        "reported immediately to the ISSO."
    )
    assert not _is_orphaned_list_item(
        "Covered data, as defined in DoDI X, must be encrypted."
    )


def test_is_orphaned_list_item_false_for_citation_with_obligation_verb_outside_narrow_list():
    # Gemini review round 2, PR #181: the first fix checked for a small
    # obligation-verb whitelist (shall/must/will/...) -- any real verb
    # outside that list (e.g. "requires") still false-positived, because a
    # verb whitelist can never be exhaustive enough to make that failure
    # direction safe. Replaced with a structural check (does the remainder
    # look like ordinary lowercase prose vs. citation-shaped tokens) that
    # doesn't depend on naming every possible verb.
    assert not _is_orphaned_list_item(
        "Controlled Unclassified Information, as defined in Executive Order "
        "13556, requires safeguarding controls."
    )


def test_is_orphaned_list_item_false_for_citation_with_quoted_prose():
    # Gemini review round 4, PR #181: the structural check strips a fixed
    # punctuation set to find each word's real first character -- a lowercase
    # prose word wrapped in quotes or brackets (e.g. "'applies'") wasn't in
    # that set, so its leading quote mark was tested instead of the real
    # first letter, misclassifying it as citation-shaped. Fixed by stripping
    # *any* non-alphanumeric character from both ends instead of an
    # enumerated set, closing the whole class of gap rather than the one
    # example found this round.
    assert not _is_orphaned_list_item(
        "Some term, as defined in CNSSI 4009, 'applies within the DoD'."
    )


def test_is_orphaned_list_item_false_for_all_caps_citation_with_real_clause():
    # Gemini review round 6, PR #181 (guard scope corrected round 8): the
    # structural citation check tells a citation token from real prose by
    # checking whether a word's first letter is lowercase -- meaningless
    # when the whole quote is ALL CAPS, since every word "looks like" a
    # citation token regardless of what it actually is. Bails out (not
    # citation-only) whenever the *whole quote* is all-uppercase.
    assert not _is_orphaned_list_item(
        "COMPLIANCE DATA, AS DEFINED IN DODI 2000.26, SHALL BE REPORTED "
        "IMMEDIATELY TO THE ISSO."
    )


def test_is_orphaned_list_item_true_for_short_acronym_only_citation():
    # Gemini review round 8, PR #181: round 6's first fix checked
    # `remainder.isupper()` (just the text after "as defined in") instead of
    # the whole quote -- wrong scope. A short, genuine citation-only
    # remainder made purely of acronym/document-ID tokens (e.g. "CNSSI
    # 4009.") is *also* all-uppercase on its own even though the rest of the
    # quote ("Term,") isn't, which made that version wrongly preserve real
    # citation-only fragments as if they were real requirements. Checking
    # the whole quote's casing instead fixes both this and round 6's
    # original case.
    assert _is_orphaned_list_item("Term, as defined in CNSSI 4009.")
    assert _is_orphaned_list_item("Data, as defined in DODI 5200.01.")


def test_is_orphaned_list_item_false_for_two_word_acronym_citation_known_accepted_miss():
    # Gemini review, PR #181 (re-reviewing the ALL-CAPS-clause fix above):
    # found two real cases where _ALL_CAPS_CLAUSE_RUN_THRESHOLD=3 still let a
    # short all-caps obligation clause ("MUST COMPLY", 2 words, no digits)
    # through misclassified as citation-only. No text-level signal
    # distinguishes a real 2-consecutive-all-caps-word clause from a real
    # 2-consecutive-all-caps-word citation acronym pair (like "NIST SP") --
    # threshold lowered to 2, applying the same "prefer a missed catch over a
    # false rejection of real content" principle Tyler set for
    # _is_orphaned_list_item()'s marker+word-count branch. This costs the one
    # test below, which was always a synthetic calibration example (added
    # round 8), not a real fixture or live-corpus record -- pinned here as a
    # known, accepted miss rather than left silently changed.
    assert not _is_orphaned_list_item("Control, as defined in NIST SP 800-53.")


def test_is_orphaned_list_item_false_for_mixed_case_citation_with_all_caps_clause():
    # Codex local review, PR #181: round 8's guard checked
    # `source_quote.isupper()` -- true only when the *entire* quote is
    # uppercase. A real quote whose citation opener is normal/title case
    # while only its governing clause is rendered in caps has neither the
    # whole quote nor even the whole remainder all-uppercase, so round 8's
    # guard didn't fire and a real obligation clause got misclassified as
    # citation-shaped word by word. Confirmed via direct execution against
    # all three of these (the third mixes a title-case citation, "Executive
    # Order 13556", with an all-caps clause in the very same remainder --
    # the specific shape that motivated replacing the whole-string check
    # with a consecutive-all-caps-run check).
    assert not _is_orphaned_list_item(
        "Compliance data, as defined in DODI 2000.26, SHALL BE REPORTED "
        "IMMEDIATELY TO THE ISSO."
    )
    assert not _is_orphaned_list_item(
        "Cybersecurity incidents, as defined in CNSSI 4009, SHALL BE "
        "REPORTED IMMEDIATELY TO THE ISSO."
    )
    assert not _is_orphaned_list_item(
        "Controlled Unclassified Information, as defined in Executive "
        "Order 13556, REQUIRES SAFEGUARDING CONTROLS."
    )


def test_is_orphaned_list_item_false_for_all_caps_clause_with_digit_token():
    # Gemini review, PR #181: a digit-only token (e.g. "30" in "WITHIN 30
    # DAYS") failed `.isalpha()` in _has_all_caps_clause_run and *reset* the
    # consecutive-all-caps-word run instead of being skipped like a connector
    # word -- a real clause naturally contains numbers ("WITHIN 30 DAYS",
    # "within 5 business days") without that breaking the clause. Any token
    # containing a digit is now skipped (transparent), not just pure-digit
    # tokens, since a real document-ID-shaped token ("2000.26") also mixes
    # digits with punctuation.
    assert not _is_orphaned_list_item(
        "Requirement, as defined in DoDI 2000.26, SHALL REPORT WITHIN 30 DAYS."
    )


def test_is_orphaned_list_item_false_for_short_all_caps_clause_no_digits():
    # Gemini review, PR #181: a short (2-word) all-caps clause with no digit
    # token at all ("MUST COMPLY") wasn't fixed by the digit-skip fix above --
    # it needed _ALL_CAPS_CLAUSE_RUN_THRESHOLD itself lowered from 3 to 2 (see
    # the constant's own comment for the full reasoning and the one test this
    # trades away).
    assert not _is_orphaned_list_item(
        "Requirement, as defined in DoDI 2000.26, MUST COMPLY."
    )


def test_is_orphaned_list_item_defined_in_citation_with_multiple_references():
    # Live-corpus generalization check (not in the original 12-example set):
    # a citation-only quote referencing two documents joined by "and" is
    # still correctly caught.
    assert _is_orphaned_list_item(
        "Readiness Reporting, as defined in DoDD 7730.65, DoD Readiness "
        "Reporting System, and AFI 10-201, Force Readiness Reporting."
    )


def test_heading_echo_rejected_in_full_pipeline(tmp_path):
    chunk_text = "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY"
    chunk = _chunk(1, chunk_text, section_title_path=["Purpose", chunk_text])
    records, failures = _run(tmp_path, [chunk], [_row(chunk, chunk_text)])
    assert records == []
    assert [f["error"] for f in failures] == ["heading_echo_quote"]


def test_colon_lead_in_is_kept_in_full_pipeline(tmp_path):
    chunk_text = "3.2 The process will be as follows:\nstep one, step two, step three."
    chunk = _chunk(1, chunk_text)
    records, failures = _run(tmp_path, [chunk], [_row(chunk, "The process will be as follows:")])
    assert [r["source_quote"] for r in records] == ["The process will be as follows:"]
    assert failures == []


def test_negative_fixture_survives_full_pipeline(tmp_path):
    # "KERs shall be approved by the MC4EB." -- terse and real, must survive
    # the heading-echo check.
    chunk_text = "4.1 KER Approval Process. KERs shall be approved by the MC4EB."
    chunk = _chunk(1, chunk_text, section_title_path=["KER Approval Process"])
    records, failures = _run(tmp_path, [chunk], [_row(chunk, "KERs shall be approved by the MC4EB.")])
    assert len(records) == 1
    assert failures == []



def test_orphaned_list_item_rejected_in_full_pipeline(tmp_path):
    # Citation-only branch -- still active (only the marker+word-count branch
    # was removed; see test_is_orphaned_list_item_no_longer_rejects_short_marker_items).
    chunk_text = "Suspicious activity reporting, as defined in DoDI 2000.26, Suspicious Activity Reporting."
    chunk = _chunk(1, chunk_text)
    records, failures = _run(tmp_path, [chunk], [_row(chunk, chunk_text)])
    assert records == []
    assert [f["error"] for f in failures] == ["orphaned_list_item_quote"]


def test_marker_prefixed_short_fragment_survives_full_pipeline(tmp_path):
    # Product direction (Tyler, PR #181): a short enumerated list item may inherit its obligation from its lead-in
    # ("Classification shall not be used to:"), so it is not rejected; the explained layer puts the lead-in in front.
    chunk_text = "Classification shall not be used to:\n(1) Conceal violations of law.\n(3) Restrain competition."
    chunk = _chunk(1, chunk_text)
    records, _ = _run(tmp_path, [chunk], [_row(chunk, "(3) Restrain competition.", 2)])
    assert len(records) == 1
    assert records[0]["source_quote"] == "(3) Restrain competition."
    assert records[0]["explained_text"] == "Classification shall not be used to: Restrain competition."
