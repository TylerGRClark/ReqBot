"""Tests for the raw-query leg fix, 2026-10-29.

Measured on a 318-question sealed set (see agent notes search_overnight): when the
rewrite step changes the query, letting it fully replace the user's own words costs
about 0.10 MRR. Adding the user's original words back as their own leg -- alongside
the rewritten one, never instead of it -- recovers the loss in full. This only
applies when rewrite actually changes the text; no_rewrite=True (or a rewrite that
falls back to the original question) must not add a duplicate leg.

Same mocking pattern as tests/unit/test_hyde.py: ollama.Client / SparseTextEmbedding /
QdrantClient are mocked, so no real Ollama/Qdrant/sparse-model calls are made.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.ask import retrieve


class _FakeSparseEmb:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


def _fake_sparse_embedding():
    return SimpleNamespace(indices=_FakeSparseEmb([1, 2]), values=_FakeSparseEmb([0.5, 0.4]))


def _patched_ask_deps():
    mock_ollama_client = MagicMock()
    mock_ollama_client.embed.return_value = SimpleNamespace(embeddings=[[0.1, 0.2]])

    mock_sparse_model = MagicMock()
    mock_sparse_model.embed.side_effect = lambda *a, **kw: iter([_fake_sparse_embedding()])

    mock_qdrant_client = MagicMock()
    mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[])

    return mock_ollama_client, mock_sparse_model, mock_qdrant_client


def test_a_rewrite_that_changes_the_query_adds_raw_dense_and_sparse_legs():
    mock_ollama, mock_sparse, mock_qdrant = _patched_ask_deps()
    with (
        patch("core.ask.ollama.Client", return_value=mock_ollama),
        patch("core.ask.SparseTextEmbedding", return_value=mock_sparse),
        patch("core.ask.QdrantClient", return_value=mock_qdrant),
        patch("core.ask.rewrite_query", return_value={
            "expanded_query": "encryption at rest requirements", "control_ids": [], "domain_tags": [],
        }),
    ):
        retrieve("how do we keep data safe when it's just sitting there", hyde=False)

    _, kwargs = mock_qdrant.query_points.call_args
    # rewritten dense + rewritten sparse + raw dense + raw sparse = 4 legs
    assert len(kwargs["prefetch"]) == 4
    using = sorted(leg.using for leg in kwargs["prefetch"])
    assert using == ["dense", "dense", "sparse", "sparse"]


def test_a_rewrite_that_falls_back_to_the_original_question_adds_no_extra_leg():
    mock_ollama, mock_sparse, mock_qdrant = _patched_ask_deps()
    question = "how do we keep data safe when it's just sitting there"
    with (
        patch("core.ask.ollama.Client", return_value=mock_ollama),
        patch("core.ask.SparseTextEmbedding", return_value=mock_sparse),
        patch("core.ask.QdrantClient", return_value=mock_qdrant),
        patch("core.ask.rewrite_query", return_value={
            "expanded_query": question, "control_ids": [], "domain_tags": [],
        }),
    ):
        retrieve(question, hyde=False)

    _, kwargs = mock_qdrant.query_points.call_args
    assert len(kwargs["prefetch"]) == 2


def test_no_rewrite_true_adds_no_extra_leg():
    mock_ollama, mock_sparse, mock_qdrant = _patched_ask_deps()
    with (
        patch("core.ask.ollama.Client", return_value=mock_ollama),
        patch("core.ask.SparseTextEmbedding", return_value=mock_sparse),
        patch("core.ask.QdrantClient", return_value=mock_qdrant),
        patch("core.ask.rewrite_query") as mock_rewrite,
    ):
        retrieve("encryption at rest", no_rewrite=True, hyde=False)

    mock_rewrite.assert_not_called()
    _, kwargs = mock_qdrant.query_points.call_args
    assert len(kwargs["prefetch"]) == 2


def test_control_ids_appended_to_sparse_still_counts_as_a_rewrite_needing_a_raw_leg():
    """sparse_query can differ from the question (control IDs appended) even when
    dense_query happens to equal it -- either difference alone must add its matching
    raw leg; this covers dense_query == question but sparse_query != question."""
    mock_ollama, mock_sparse, mock_qdrant = _patched_ask_deps()
    question = "access control policy"
    with (
        patch("core.ask.ollama.Client", return_value=mock_ollama),
        patch("core.ask.SparseTextEmbedding", return_value=mock_sparse),
        patch("core.ask.QdrantClient", return_value=mock_qdrant),
        patch("core.ask.rewrite_query", return_value={
            "expanded_query": question, "control_ids": ["AC-3"], "domain_tags": [],
        }),
    ):
        retrieve(question, hyde=False)

    _, kwargs = mock_qdrant.query_points.call_args
    # rewritten dense (== raw, no extra leg) + rewritten sparse (with AC-3) + raw sparse = 3 legs
    assert len(kwargs["prefetch"]) == 3
    using = sorted(leg.using for leg in kwargs["prefetch"])
    assert using == ["dense", "sparse", "sparse"]


def test_raw_dense_embed_uses_the_original_question_text():
    mock_ollama, mock_sparse, mock_qdrant = _patched_ask_deps()
    question = "how do we keep data safe when it's just sitting there"
    with (
        patch("core.ask.ollama.Client", return_value=mock_ollama),
        patch("core.ask.SparseTextEmbedding", return_value=mock_sparse),
        patch("core.ask.QdrantClient", return_value=mock_qdrant),
        patch("core.ask.rewrite_query", return_value={
            "expanded_query": "encryption at rest requirements", "control_ids": [], "domain_tags": [],
        }),
    ):
        retrieve(question, hyde=False)

    embed_inputs = [call.kwargs["input"] for call in mock_ollama.embed.call_args_list]
    assert question in embed_inputs
    assert "encryption at rest requirements" in embed_inputs
