"""The prompt window around a marked requirement, and the stored clause offsets that place the marker. Expected values are written out, not recomputed."""
import json

from services import audit_questions as Q
from services import checklist_audit as A
from services.checklist_service import generate

SEC = ("S",)


def _lines(*chunks):
    """chunks: (chunk_id, raw text) in the same section."""
    return A.document_lines({cid: {"raw_text": raw, "section_title_path": list(SEC)} for cid, raw in chunks})


def test_offsets_pick_the_occurrence_the_clause_is_at_not_the_first():
    raw = "Staff must log events. Other text. Staff must log events."
    chunk = {"raw_text": raw}
    first, _ = A.build_passage("Staff must log events.", chunk)
    assert first == ">> Staff must log events. << Other text. Staff must log events."
    second, found = A.build_passage("Staff must log events.", chunk, span=(35, 57))
    assert found and second == "Staff must log events. Other text. >> Staff must log events. <<"


def test_offsets_that_do_not_hold_the_quote_fall_back_to_text_search():
    passage, found = A.build_passage("Staff must log events.", {"raw_text": "Staff must log events. More."}, span=(10, 15))
    assert found and passage == ">> Staff must log events. << More."


def test_cut_is_enough_needs_the_whole_marker_and_the_lead_in_inside():
    p = "a" * 100 + ">> Do it. <<" + "b" * 2000
    assert A.cut_is_enough(p, 1500) is True
    assert A.cut_is_enough(p, 105) is False  # the closing marker falls outside the cut
    assert A.cut_is_enough("The operator shall: " + "z" * 1600 + ">> (a) Log. <<", 1500) is False
    assert A.cut_is_enough("The operator shall: >> (a) Log. <<", 1500, A.squash("The operator shall:")) is True
    assert A.cut_is_enough("Other lead. >> (a) Log. <<", 1500, A.squash("The operator shall:")) is False
    assert A.cut_is_enough("no marker here", 1500) is False


def _window(chunks, chunk_id, quote_raw_marked, lead, cap=1500):
    return A.prompt_window(_lines(*chunks), chunk_id, quote_raw_marked, lead, cap)


def test_window_reaches_back_to_the_lead_in_and_one_line_before():
    chunks = [(1, "Intro line.\nThe operator shall:"), (2, "x" * 1400 + "\n(a) log events.")]
    w = _window(chunks, 2, "x" * 1400 + "\n>> (a) log events. <<", A.squash("The operator shall:"))
    assert w == "Intro line.\nThe operator shall:\n" + "x" * 1400 + "\n>> (a) log events. <<"


def test_window_keeps_the_lead_in_line_alone_when_the_lines_between_do_not_fit():
    chunks = [(1, "Intro line.\nThe operator shall:"), (2, "x" * 1600 + "\n(a) log events.")]
    w = _window(chunks, 2, "x" * 1600 + "\n>> (a) log events. <<", A.squash("The operator shall:"))
    assert w == "... The operator shall:\n>> (a) log events. <<"


def test_window_grows_into_neighbouring_lines_and_marks_cut_sides_with_ellipses():
    chunks = [(1, "one\ntwo\nthree"), (2, "four\nfive\nsix")]
    # cap 25: quote line "five" marked is ">> five <<" (10 chars + 1) ; after: "six" (4) then before: "four" (5) ; then no room for "three"
    w = _window(chunks, 2, "four\n>> five <<\nsix", "", cap=25)
    assert w == "... four\n>> five <<\nsix"
    w2 = _window(chunks, 2, "four\n>> five <<\nsix", "", cap=1500)
    assert w2 == "one\ntwo\nthree\nfour\n>> five <<\nsix"


def test_window_never_crosses_a_section_change():
    lines = A.document_lines({1: {"raw_text": "other section line", "section_title_path": ["T"]}, 2: {"raw_text": "alpha\nbeta", "section_title_path": ["S"]}})
    assert A.prompt_window(lines, 2, ">> alpha\nbeta <<", "", 1500) == ">> alpha\nbeta <<"


def test_a_single_overlong_line_is_cropped_around_the_requirement_at_word_boundaries():
    line = ("aaaa " * 400) + ">> must do it. <<" + (" bbbb" * 400)
    w = _window([(1, line)], 1, line, "")
    assert w.startswith("... aaaa ") and w.endswith(" bbbb ...") and ">> must do it. <<" in w
    assert 1400 <= len(w) <= 1510


def test_an_unplaceable_marked_chunk_gives_none():
    assert A.prompt_window(_lines((1, "a\nb")), 9, ">> a <<", "", 1500) is None
    assert A.prompt_window(_lines((1, "a\nb")), 1, "no markers\nhere", "", 1500) is None


def test_prompt_passage_uses_the_stored_window_for_that_cut_only():
    item = {"passage": "p" * 2000, "prompt_windows": {"1500": "WINDOW"}}
    assert Q.prompt_passage(item, 1500) == "WINDOW"
    assert Q.prompt_passage(item, 1200) == "p" * 1200
    assert Q.prompt_passage({"passage": "short"}, 1500) == "short"


def _doc(tmp_path, chunks, rec):
    run_dir = tmp_path / "doc_20260101_120000"
    run_dir.mkdir()
    (run_dir / "doc_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n")
    (run_dir / "doc_chunks.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
    return generate(tmp_path, "doc", "cybersecurity")["items"][0]


def test_generate_stores_a_window_only_for_a_row_whose_plain_cut_loses_the_requirement(tmp_path):
    quote = "(a) Review logs monthly."
    chunk = {"chunk_id": 1, "raw_text": "y" * 1700 + "\n" + quote, "section_title_path": ["Logs"]}
    base = {"requirement_id": "REQ-1", "source_quote": quote, "source_ref": "2.1", "chunk_id": 1, "section_title_path": ["Logs"], "page_start": 1, "page_end": 1}
    long_row = _doc(tmp_path, [chunk], base)
    assert set(long_row["prompt_windows"]) == {"1500", "1200"}
    assert long_row["prompt_windows"]["1500"].endswith(">> (a) Review logs monthly. <<") and "y" * 100 not in long_row["prompt_windows"]["1500"]
    assert long_row["passage"].startswith("y" * 1700)  # the sheet's passage column is unchanged
    short = tmp_path / "short"
    short.mkdir()
    assert "prompt_windows" not in _doc(short, [{"chunk_id": 1, "raw_text": "Intro.\n" + quote, "section_title_path": ["Logs"]}], base)


def test_generate_marks_the_occurrence_at_the_stored_offsets(tmp_path):
    raw = "Staff must log events. Other text. Staff must log events."
    rec = {"requirement_id": "REQ-1", "source_quote": "Staff must log events.", "source_ref": "2.1", "chunk_id": 1, "section_title_path": ["Logs"], "page_start": 1, "page_end": 1,
           "anchor_status": "exact", "anchor_start": 35, "anchor_end": 57, "anchor_text": "Staff must log events."}
    item = _doc(tmp_path, [{"chunk_id": 1, "raw_text": raw, "section_title_path": ["Logs"]}], rec)
    assert item["passage"] == "Staff must log events. Other text. >> Staff must log events. <<"
    stale = tmp_path / "stale"
    stale.mkdir()
    rec2 = dict(rec, anchor_text="something else")  # offsets that do not hold the text are not trusted
    item2 = _doc(stale, [{"chunk_id": 1, "raw_text": raw, "section_title_path": ["Logs"]}], rec2)
    assert item2["passage"] == ">> Staff must log events. << Other text. Staff must log events."
