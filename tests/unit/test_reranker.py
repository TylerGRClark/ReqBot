"""Unit tests for WP-43's core/reranker.py.

FlashRank is always faked via a fake `flashrank` module injected into
sys.modules -- these tests must not require the optional 'rerank' extra to
be installed to run, matching this codebase's convention for optional-dependency scorers.
Faking the whole module (not just core.reranker._get_ranker) also exercises
rerank()'s own `from flashrank import RerankRequest` import, not just the
Ranker construction seam.
"""
import sys
import types

import pytest

from core import reranker


class _FakeRanker:
    """Stand-in for flashrank.Ranker. Scores each passage via a caller-
    supplied function of its text."""

    def __init__(self, score_fn, *_args, **_kwargs):
        self._score_fn = score_fn

    def rerank(self, request):
        for p in request.passages:
            p["score"] = self._score_fn(p["text"])
        return sorted(request.passages, key=lambda p: p["score"], reverse=True)


class _FakeRerankRequest:
    def __init__(self, query=None, passages=None):
        self.query = query
        self.passages = passages if passages is not None else []


def _install_fake_flashrank(monkeypatch, score_fn):
    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = lambda *a, **kw: _FakeRanker(score_fn)
    fake_module.RerankRequest = _FakeRerankRequest
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    monkeypatch.setattr(reranker, "_rankers", {})


def _by_length(text: str) -> float:
    """Deterministic fake score: longer scoring text wins."""
    return float(len(text))


def _contains_restrain(text: str) -> float:
    return 1.0 if "restrain" in text.lower() else 0.0


def test_rerank_reorders_by_score(monkeypatch):
    _install_fake_flashrank(monkeypatch, _by_length)
    candidates = [
        {"requirement_id": "REQ-short", "description": "", "source_quote": "Short."},
        {"requirement_id": "REQ-long", "description": "", "source_quote": "A much longer piece of source quote text."},
    ]
    result = reranker.rerank("query", candidates, top_k=5)
    assert [r["requirement_id"] for r in result] == ["REQ-long", "REQ-short"]


def test_rerank_attaches_rerank_score(monkeypatch):
    _install_fake_flashrank(monkeypatch, _by_length)
    candidates = [{"requirement_id": "REQ-1", "description": "", "source_quote": "abc"}]
    result = reranker.rerank("query", candidates, top_k=5)
    assert result[0]["rerank_score"] == pytest.approx(3.0)
    assert isinstance(result[0]["rerank_score"], float)


def test_rerank_respects_top_k(monkeypatch):
    _install_fake_flashrank(monkeypatch, _by_length)
    candidates = [
        {"requirement_id": f"REQ-{i}", "description": "", "source_quote": "x" * i}
        for i in range(1, 6)
    ]
    result = reranker.rerank("query", candidates, top_k=2)
    assert len(result) == 2
    assert [r["requirement_id"] for r in result] == ["REQ-5", "REQ-4"]


def test_rerank_empty_candidates_returns_empty(monkeypatch):
    _install_fake_flashrank(monkeypatch, _by_length)
    assert reranker.rerank("query", [], top_k=5) == []


def test_rerank_raises_clear_error_when_flashrank_not_installed(monkeypatch):
    # The standard technique for forcing `import X` to fail without actually
    # uninstalling X: a None entry in sys.modules.
    monkeypatch.setitem(sys.modules, "flashrank", None)
    monkeypatch.setattr(reranker, "_rankers", {})
    candidates = [{"requirement_id": "REQ-1", "description": "", "source_quote": "abc"}]
    with pytest.raises(ImportError, match="rerank"):
        reranker.rerank("query", candidates, top_k=5)


def test_get_ranker_constructs_once(monkeypatch):
    calls = []
    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = lambda *a, **kw: calls.append(1) or _FakeRanker(_by_length)
    fake_module.RerankRequest = _FakeRerankRequest
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    monkeypatch.setattr(reranker, "_rankers", {})

    reranker._get_ranker()
    reranker._get_ranker()
    assert len(calls) == 1


def test_get_ranker_uses_default_model_name(monkeypatch):
    calls = []
    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = lambda *a, **kw: calls.append(kw.get("model_name")) or _FakeRanker(_by_length)
    fake_module.RerankRequest = _FakeRerankRequest
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    monkeypatch.setattr(reranker, "_rankers", {})

    reranker._get_ranker()
    assert calls == [reranker.DEFAULT_RERANK_MODEL]


def test_get_ranker_caches_separately_per_model(monkeypatch):
    calls = []
    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = lambda *a, **kw: calls.append(kw.get("model_name")) or _FakeRanker(_by_length)
    fake_module.RerankRequest = _FakeRerankRequest
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    monkeypatch.setattr(reranker, "_rankers", {})

    reranker._get_ranker("model-a")
    reranker._get_ranker("model-b")
    reranker._get_ranker("model-a")  # already cached -- must not construct again
    assert calls == ["model-a", "model-b"]


def test_rerank_passes_model_name_through(monkeypatch):
    fake_module = types.ModuleType("flashrank")
    captured = {}

    def _fake_ranker_ctor(*a, **kw):
        captured["model_name"] = kw.get("model_name")
        return _FakeRanker(_by_length)

    fake_module.Ranker = _fake_ranker_ctor
    fake_module.RerankRequest = _FakeRerankRequest
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    monkeypatch.setattr(reranker, "_rankers", {})

    candidates = [{"requirement_id": "REQ-1", "description": "", "source_quote": "abc"}]
    reranker.rerank("query", candidates, top_k=5, model_name="ms-marco-MiniLM-L-12-v2")
    assert captured["model_name"] == "ms-marco-MiniLM-L-12-v2"


def test_scoring_text_prefers_embedding_text_over_source_quote():
    candidate = {
        "description": "",
        "source_quote": "(3) Restrain competition.",
        "embedding_text": "Units will actively work to prevent anti-competitive practices, "
                           "including: (3) Restrain competition.",
    }
    text = reranker._scoring_text(candidate)
    assert text == candidate["embedding_text"]


def test_scoring_text_falls_back_to_source_quote_when_no_embedding_text():
    candidate = {"description": "", "source_quote": "Passwords must be 15 characters.", "embedding_text": ""}
    text = reranker._scoring_text(candidate)
    assert text == "Passwords must be 15 characters."


def test_scoring_text_includes_description():
    candidate = {"description": "Password length", "source_quote": "Must be 15 characters.", "embedding_text": ""}
    text = reranker._scoring_text(candidate)
    assert "Password length" in text
    assert "Must be 15 characters." in text


def test_scoring_text_includes_source_ref_when_present():
    # Codex review, PR #191: for a control-catalog-style corpus, source_ref
    # can itself be the control ID (e.g. "AC-3") -- an exact-match signal
    # that should reach the reranker on the candidate side too.
    candidate = {
        "description": "", "source_quote": "Enforce access control policy.",
        "embedding_text": "", "source_ref": "AC-3",
    }
    text = reranker._scoring_text(candidate)
    assert "AC-3" in text


def test_scoring_text_omits_ref_line_when_source_ref_absent():
    candidate = {"description": "", "source_quote": "Enforce access control policy.", "embedding_text": ""}
    text = reranker._scoring_text(candidate)
    assert "Ref:" not in text


def test_parent_child_context_fragment_scores_using_governing_clause(monkeypatch):
    """Codex review (PR #190): a fragment-shaped quote with no visible
    antecedent must be scored using its parent-stem-reconstructed
    embedding_text, not the bare fragment -- otherwise a reranker that
    scores on lexical/semantic content would never see the term that makes
    it relevant. Same underlying requirement (identical source_quote),
    varying only whether embedding_text is present, isolates the variable:
    without it, the dangling fragment alone doesn't mention "restrain" and
    scores 0; with it, the reconstructed governing clause does and scores 1."""
    _install_fake_flashrank(monkeypatch, _contains_restrain)
    dangling_fragment = "(3) Prevent monopolistic behavior."

    fragment_only = [{
        "requirement_id": "REQ-fragment",
        "description": "",
        "source_quote": dangling_fragment,
        "embedding_text": "",
    }]
    reconstructed = [{
        "requirement_id": "REQ-reconstructed",
        "description": "",
        "source_quote": dangling_fragment,
        "embedding_text": "Units will actively work to restrain anti-competitive practices, "
                           f"including: {dangling_fragment}",
    }]

    fragment_result = reranker.rerank("competition restraint rules", fragment_only, top_k=1)
    reconstructed_result = reranker.rerank("competition restraint rules", reconstructed, top_k=1)

    assert fragment_result[0]["rerank_score"] == pytest.approx(0.0)
    assert reconstructed_result[0]["rerank_score"] == pytest.approx(1.0)


def test_hf_cross_encoder_scores_requirement_text_and_orders_by_score(monkeypatch):
    seen = {}

    def fake_scores(query, candidates, model_name):
        seen["args"] = (query, [c["source_quote"] for c in candidates], model_name)
        return [0.1, 2.5, -1.0]

    monkeypatch.setattr(reranker, "_hf_scores", fake_scores)
    cands = [{"source_quote": "a"}, {"source_quote": "b"}, {"source_quote": "c"}]
    out = reranker.rerank("q", cands, top_k=2, model_name="BAAI/bge-reranker-v2-m3")
    assert [c["source_quote"] for c in out] == ["b", "a"]
    assert out[0]["rerank_score"] == 2.5
    assert seen["args"] == ("q", ["a", "b", "c"], "BAAI/bge-reranker-v2-m3")


def test_a_model_name_without_a_slash_still_uses_flashrank(monkeypatch):
    monkeypatch.setattr(reranker, "_hf_scores", lambda *a: (_ for _ in ()).throw(AssertionError("must not run")))
    assert reranker._is_hf_model("ms-marco-TinyBERT-L-2-v2") is False
    assert reranker._is_hf_model("BAAI/bge-reranker-v2-m3") is True


def test_is_remote_model_detects_url_schemes():
    assert reranker._is_remote_model("http://192.168.0.218:8732") is True
    assert reranker._is_remote_model("https://rerank.example.internal") is True
    assert reranker._is_remote_model("BAAI/bge-reranker-v2-m3") is False
    assert reranker._is_remote_model("ms-marco-TinyBERT-L-2-v2") is False


def test_rerank_routes_a_url_model_name_to_remote_scores_not_hf(monkeypatch):
    seen = {}

    def fake_remote(query, candidates, base_url):
        seen["args"] = (query, [c["source_quote"] for c in candidates], base_url)
        return [0.1, 2.5, -1.0]

    monkeypatch.setattr(reranker, "_remote_scores", fake_remote)
    monkeypatch.setattr(reranker, "_hf_scores", lambda *a: (_ for _ in ()).throw(AssertionError("must not run")))
    cands = [{"source_quote": "a"}, {"source_quote": "b"}, {"source_quote": "c"}]
    out = reranker.rerank("q", cands, top_k=2, model_name="http://192.168.0.218:8732")
    assert [c["source_quote"] for c in out] == ["b", "a"]
    assert out[0]["rerank_score"] == 2.5
    assert seen["args"] == ("q", ["a", "b", "c"], "http://192.168.0.218:8732")
