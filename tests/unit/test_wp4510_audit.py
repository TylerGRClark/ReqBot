"""WP-45.10: the Docling audit's pure helpers (offline; no Docling conversion, no cache, no LLM)."""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_10"


def _load(name):
    if str(_DIR) not in sys.path:
        sys.path.insert(0, str(_DIR))
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(f"wp4510_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp4510_{name}"] = module
    spec.loader.exec_module(module)
    return module


AC = _load("analyze_chunks")
AD = _load("analyze_docs")
CM = _load("common")
CV = _load("convert")


def test_lead_in_pieces_split_on_pipes_and_ellipses_and_normalise():
    assert AC.pieces("The DOT&E shall: | the  Director\n... shall act") == ["the dot&e shall:", "the director", "shall act"]


def test_preservation_counts_lost_and_extra_shingles_independent_of_chunk_boundaries():
    base = {"d": [{"raw_text": "one two three four five six seven eight"}]}
    split = {"d": [{"raw_text": "one two three four"}, {"raw_text": "five six seven eight"}]}
    assert AC.preservation(base, split) == {"baseline_shingles": 3, "lost": 0, "extra": 0, "lost_share": 0.0, "extra_share": 0.0}
    cut = {"d": [{"raw_text": "one two three four five six seven"}]}
    assert AC.preservation(base, cut)["lost"] == 1


def test_list_continuations_ignore_first_markers():
    chunks = [{"raw_text": "(a) first item"}, {"raw_text": "(3) a list cut across chunks"}, {"raw_text": "Plain sentence."}, {"raw_text": "1. new list"}]
    assert AC.list_continuations(chunks) == 1


def test_token_estimate_matches_the_repository_formula():
    assert AC.est_tokens(1000) == 400 and AC.est_tokens(1) == 1


def test_diff_counters_reports_lost_and_extra_with_examples():
    lost, extra, lost_ex, extra_ex = AD.diff_counters(AD.collections.Counter(["a", "b", "b"]), AD.collections.Counter(["b", "c"]))
    assert (lost, extra, lost_ex, extra_ex) == (2, 1, ["a", "b"], ["c"])


def test_pinned_documents_are_the_thirteen_and_the_check_reports_a_missing_pdf(monkeypatch, tmp_path):
    assert len(CM.pinned_documents()) == 13
    monkeypatch.setattr(CM, "PDF_DIR", tmp_path)
    problems = CM.verify_pdfs()
    assert len(problems) == 13 and all("does not exist" in p for p in problems)


def test_every_variant_has_a_description_and_baseline_is_unmodified():
    assert "baseline" in CV.VARIANTS and all(CV.VARIANTS.values())
    CV._mutate(object(), "baseline")  # the baseline changes nothing


def test_a_cache_directory_from_a_different_dependency_set_is_refused(monkeypatch, tmp_path):
    import json

    import pytest
    monkeypatch.setattr(CM, "versions", lambda: {"docling": "2.94.0", "docling-core": "2.99.0", "docling-parse": "5.7.0", "docling-ibm-models": "3.13.0"})
    CM.check_manifest(tmp_path, "baseline")  # a new directory records the set
    CM.check_manifest(tmp_path, "baseline")  # the same set is accepted
    monkeypatch.setattr(CM, "versions", lambda: {"docling": "2.94.0", "docling-core": "2.100.0", "docling-parse": "5.7.0", "docling-ibm-models": "3.13.0"})
    with pytest.raises(SystemExit):
        CM.check_manifest(tmp_path, "baseline")
    assert json.loads((tmp_path / "_manifest.json").read_text())["versions"]["docling-core"] == "2.99.0"


def test_diff_counters_keeps_every_difference():
    lost, extra, lost_all, extra_all = AD.diff_counters(AD.collections.Counter(list("abcdefgh")), AD.collections.Counter())
    assert lost == 8 and lost_all == list("abcdefgh") and extra_all == []


def test_load_chunks_reads_the_named_release_tag(tmp_path, monkeypatch):
    monkeypatch.setattr(AC.common, "CACHE", tmp_path)  # the module analyze_chunks itself imported, not the copy loaded above
    d = tmp_path / "d9.9.9" / "chunks" / "default"
    d.mkdir(parents=True)
    (d / "x_chunks.jsonl").write_text('{"raw_text": "hello", "text": "hello"}\n', encoding="utf-8")
    assert AC.load_chunks("d9.9.9:default", "x") == [{"raw_text": "hello", "text": "hello"}]


def test_preservation_details_list_every_differing_shingle_with_multiplicity():
    base = {"d": [{"raw_text": "a b c d e f g a b c d e f g"}]}
    other = {"d": [{"raw_text": "a b c d e f g"}]}
    details = {}
    result = AC.preservation(base, other, details)
    assert result["lost"] == 7 and result["extra"] == 0
    assert details["d"]["lost"]["a b c d e f"] == 1 and details["d"]["extra"] == {}
