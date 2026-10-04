"""Tests for eval/step_d_replay.py's compare() gate and replay input checks (WP-44.1).

compare() is what certifies a Step D change, so its failure paths are tested directly with
synthetic summaries: it must not pass on unapproved removals, on runs made from different
inputs, on removals attributed to the wrong rule or document, or on a corpus that silently
shrank (Codex reviews, PR #196).
"""
import json

import pytest

from eval import step_d_replay as replay


def _expected(removed, new_code="new", docs=("d",)):
    return {"removed_ids": list(removed), "new_failure_code": new_code, "documents": list(docs)}


def _doc(ids, codes, run_dir="doc_20260101_000000", chunks="c1", extracted="e1", pdf="p1", hashes=None):
    return {
        "run_dir": run_dir, "chunks_sha256": chunks, "extracted_sha256": extracted, "pdf_sha256": pdf,
        "raw_records": 10, "survivors": len(ids), "unchecked_unknown_chunk": 0,
        "failure_codes": codes, "survivor_ids": sorted(ids),
        "survivor_hashes": hashes or {i: f"h-{i}" for i in ids},
    }


def _write(path, docs):
    path.mkdir(parents=True, exist_ok=True)
    summary = {"label": path.name, "git_revision": "a" * 40, "pipeline_or_core_dirty": False,
               "profile": "cybersecurity", "documents": docs}
    (path / "summary.json").write_text(json.dumps(summary))
    return path


def _pair(tmp_path, base_doc, after_doc):
    return _write(tmp_path / "base", {"d": base_doc}), _write(tmp_path / "after", {"d": after_doc})


def test_passes_when_removals_match_approved_set_and_are_accounted_for(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {"x": 1}), _doc(["A", "B"], {"x": 1, "new": 1}))
    assert replay.compare(base, after, expected=_expected(["C"])) == 0


def test_identical_runs_pass_with_no_expected_removals(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B"], {"x": 1}), _doc(["A", "B"], {"x": 1}))
    assert replay.compare(base, after) == 0


def test_any_removal_is_unapproved_without_an_expected_set(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {"x": 1}), _doc(["A", "B"], {"x": 1, "new": 1}))
    assert replay.compare(base, after) == 2


def test_removing_everything_with_matching_codes_still_fails_against_the_approved_set(tmp_path):
    # A faulty change that rejects every survivor: codes rise by exactly the removal count, nothing
    # added or changed -- the old compare() exited 0 here.
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {}), _doc([], {"new": 3}))
    assert replay.compare(base, after, expected=_expected(["C"])) == 2


def test_fewer_removals_than_expected_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {}), _doc(["A", "B", "C"], {}))
    assert replay.compare(base, after, expected=_expected(["C"])) == 2


def test_removal_not_accounted_for_by_a_failure_code_increase_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B"], {"x": 1}), _doc(["A"], {"x": 1}))
    assert replay.compare(base, after, expected=_expected(["B"])) == 2


def test_a_decreased_failure_code_count_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B"], {"x": 2}), _doc(["A", "B", "C"], {"x": 1}))
    assert replay.compare(base, after) == 2


def test_added_survivor_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A"], {}), _doc(["A", "B"], {}))
    assert replay.compare(base, after) == 2


def test_changed_survivor_field_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A"], {}, hashes={"A": "one"}), _doc(["A"], {}, hashes={"A": "two"}))
    assert replay.compare(base, after) == 2


def test_different_input_run_directory_is_rejected(tmp_path):
    # e.g. a newer ingest appeared between the baseline and after runs
    base, after = _pair(tmp_path, _doc(["A"], {}), _doc(["A"], {}, run_dir="doc_20260202_000000"))
    assert replay.compare(base, after) == 3


def test_different_input_hash_is_rejected(tmp_path):
    for key, value in (("chunks", "c2"), ("extracted", "e2"), ("pdf", "p2")):
        base, after = _pair(tmp_path / key, _doc(["A"], {}), _doc(["A"], {}, **{key: value}))
        assert replay.compare(base, after) == 3, key


def test_summary_without_input_hashes_is_rejected(tmp_path):
    old = _doc(["A"], {})
    del old["chunks_sha256"]
    base, after = _pair(tmp_path, old, _doc(["A"], {}))
    assert replay.compare(base, after) == 3


def test_different_document_sets_are_rejected(tmp_path):
    base = _write(tmp_path / "base", {"d": _doc(["A"], {})})
    after = _write(tmp_path / "after", {"d": _doc(["A"], {}), "extra": _doc(["Z"], {})})
    assert replay.compare(base, after) == 1


def test_removal_attributed_to_the_wrong_failure_code_fails(tmp_path):
    # Codex's scenario: the removal count is right, but the rise is booked under another rule.
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {"x": 1}), _doc(["A", "B"], {"x": 2}))
    assert replay.compare(base, after, expected=_expected(["C"])) == 2


def test_other_failure_code_moving_alongside_the_expected_one_fails(tmp_path):
    base, after = _pair(tmp_path, _doc(["A", "B", "C"], {"x": 1}), _doc(["A", "B"], {"x": 2, "new": 1}))
    assert replay.compare(base, after, expected=_expected(["C"])) == 2


def test_expected_code_must_rise_by_exactly_the_removal_count_per_document(tmp_path):
    base = _write(tmp_path / "base", {"d1": _doc(["A", "B"], {}), "d2": _doc(["C"], {})})
    # right total (1 removal, +1 code) but the code rise is booked on the other document
    after = _write(tmp_path / "after", {"d1": _doc(["A"], {}), "d2": _doc(["C"], {"new": 1})})
    assert replay.compare(base, after, expected=_expected(["B"], docs=("d1", "d2"))) == 2


def test_per_document_attribution_passes_when_correct(tmp_path):
    base = _write(tmp_path / "base", {"d1": _doc(["A", "B"], {}), "d2": _doc(["C"], {})})
    after = _write(tmp_path / "after", {"d1": _doc(["A"], {"new": 1}), "d2": _doc(["C"], {})})
    assert replay.compare(base, after, expected=_expected(["B"], docs=("d1", "d2"))) == 0


def test_corpus_that_shrank_in_both_arms_fails_against_the_manifest(tmp_path):
    # Codex's scenario: a document is missing from BOTH summaries, so the arms still agree.
    base, after = _pair(tmp_path, _doc(["A", "B"], {}), _doc(["A"], {"new": 1}))
    assert replay.compare(base, after, expected=_expected(["B"], docs=("d", "missing_doc"))) == 1


def test_unexpected_extra_document_fails_against_the_manifest(tmp_path):
    base, after = _pair(tmp_path, _doc(["A"], {}), _doc(["A"], {}))
    assert replay.compare(base, after, expected=_expected([], docs=())) == 1


def test_replay_fails_when_a_selected_document_has_no_pdf(tmp_path, monkeypatch):
    # No silent skipping: a missing PDF would shrink the evaluated corpus in both arms alike.
    monkeypatch.setattr(replay, "select_runs", lambda: {"has_no_pdf": tmp_path})
    monkeypatch.setattr(replay, "RAW_PDFS", tmp_path / "no_pdfs_here")
    with pytest.raises(RuntimeError, match="has_no_pdf"):
        replay.run_replay("test", tmp_path / "out")


def test_replay_uses_pinned_runs_and_ignores_the_latest_run_selection(tmp_path, monkeypatch):
    # The WP-44.2 audit pins the manifest's exact runs; a newer ingest must not be picked up.
    def boom():
        raise AssertionError("select_runs() must not be consulted when runs are pinned")

    monkeypatch.setattr(replay, "select_runs", boom)
    monkeypatch.setattr(replay, "RAW_PDFS", tmp_path / "no_pdfs_here")
    with pytest.raises(RuntimeError, match="pinned_doc"):  # reached the PDF check using the pinned runs
        replay.run_replay("test", tmp_path / "out", runs={"pinned_doc": tmp_path})
