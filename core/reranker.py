"""WP-43: standalone, retrieval-agnostic reranker.

Deliberately decoupled from core.ask.retrieve() -- takes a query and a list
of already-fetched candidate dicts, returns them reordered by a local
cross-encoder's relevance score. Any future caller (Evidence, Compare) can
reuse this once it has its own candidate-pool headroom; this module makes no
assumption about who fetched its input. See archive/PHASE43_REQUIREMENTS.md §4.

Uses FlashRank (flashrank.Ranker), imported lazily so this module can be
imported without the optional 'rerank' extra installed -- only actually
calling rerank() requires it.
"""
import logging

log = logging.getLogger(__name__)

# FlashRank's own default. Named explicitly here (not left implicit in a bare
# Ranker() call) because WP-43's spike measured this exact model and found it
# doesn't clear the Precision@5 gate -- see archive/PHASE43_REQUIREMENTS.md §11.
# model_name is a parameter specifically so a stronger bundled FlashRank model
# (e.g. "ms-marco-MiniLM-L-12-v2") can be swapped in and measured without
# touching this module's shape -- see §11.5's Backlog.
DEFAULT_RERANK_MODEL = "ms-marco-TinyBERT-L-2-v2"

_rankers: dict = {}
_hf_models: dict = {}

# A Hugging Face cross-encoder (any model id with a "/", e.g. "BAAI/bge-reranker-v2-m3") is scored
# through transformers instead of FlashRank. Measured 2026-10-28 on three query sets (see
# notes/search_overnight in the agent docs): the 568M bge-reranker-v2-m3 over the hybrid list raised MRR by
# +0.07 to +0.10 where the small FlashRank model gave none. Opt-in like everything here: retrieve(rerank=True).
HF_MAX_LENGTH = 256
HF_BATCH = 16

# A model_name that is itself a URL (e.g. "http://192.168.0.218:8732") routes to a remote
# rerank_server.py instance instead of loading the cross-encoder in this process -- for
# running the same bge-reranker-v2-m3 scoring on a machine with a GPU when this one has
# none. See notes/search_overnight 2026-10-29: CPU-only scoring was too slow to ship.
REMOTE_TIMEOUT_SECONDS = 30


def _is_remote_model(model_name: str) -> bool:
    return model_name.startswith("http://") or model_name.startswith("https://")


def _remote_scores(query: str, candidates: list[dict], base_url: str) -> list[float]:
    """Relevance scores from a remote rerank_server.py instance's /rerank endpoint."""
    import json
    import urllib.request

    from core.display import requirement_text

    texts = [requirement_text(c) for c in candidates]
    payload = json.dumps({"query": query, "texts": texts}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/rerank", data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=REMOTE_TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read())
    return body["scores"]


def _is_hf_model(model_name: str) -> bool:
    return "/" in model_name


def _get_hf(model_name: str):
    """(tokenizer, model) for a Hugging Face cross-encoder, loaded once per process."""
    if model_name not in _hf_models:
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "A Hugging Face reranker needs transformers and torch (installed with docling)."
            ) from exc
        _hf_models[model_name] = (
            AutoTokenizer.from_pretrained(model_name),
            AutoModelForSequenceClassification.from_pretrained(model_name).eval(),
        )
    return _hf_models[model_name]


def _hf_scores(query: str, candidates: list[dict], model_name: str) -> list[float]:
    """Relevance logit for (query, requirement text as the reader sees it) per candidate."""
    import torch

    from core.display import requirement_text

    tokenizer, model = _get_hf(model_name)
    texts = [requirement_text(c) for c in candidates]
    scores: list[float] = []
    with torch.no_grad():
        for start in range(0, len(texts), HF_BATCH):
            batch = texts[start:start + HF_BATCH]
            enc = tokenizer([query] * len(batch), batch, padding=True, truncation=True,
                            max_length=HF_MAX_LENGTH, return_tensors="pt")
            scores.extend(model(**enc).logits.view(-1).tolist())
    return scores


def _get_ranker(model_name: str = DEFAULT_RERANK_MODEL):
    """Lazily construct and cache one FlashRank Ranker per model_name for the
    process lifetime -- loading the ONNX model/tokenizer on every call would
    dominate latency and contaminate any latency measurement."""
    if model_name not in _rankers:
        try:
            from flashrank import Ranker
        except ImportError as exc:
            raise ImportError(
                "Reranking requires the 'rerank' extra: pip install '.[rerank]' "
                "(or `pip install flashrank`)."
            ) from exc
        _rankers[model_name] = Ranker(model_name=model_name)
    return _rankers[model_name]


def _scoring_text(candidate: dict) -> str:
    """Text FlashRank scores against the query for one candidate.

    Prefers embedding_text (a parent stem in front of the quote) over bare
    source_quote. Only points indexed before clause labeling carry it: the
    step that wrote it was deleted with the list-writing extraction, and a
    point indexed since has none, so it is scored on source_quote. Whether
    it should be scored on explained_text, as the index now embeds, changes
    search ranking and is a separate, measured decision (not made here).

    Also includes source_ref when present (Codex review, PR #191), for the
    same reason build_embedding_text() appends it at index time: for a
    control-catalog-style corpus (e.g. NIST 800-53), source_ref can itself be
    the control ID (e.g. "AC-3") -- an exact-match signal on the candidate
    side that would otherwise only exist in the query (dense_query/
    expanded_query already retains control ID text as verified live against
    the rewrite model; sparse/BM25 already gets it explicitly). No document
    currently indexed has a control-ID-shaped source_ref (verified live
    against the corpus), but source_ref itself (section/paragraph numbers
    for this corpus's actual documents) is present on virtually every
    record, so this changes the scoring text for every candidate today, not
    just a hypothetical future one -- §11's committed artifacts were
    regenerated after this change for that reason.
    """
    description = (candidate.get("description") or "").strip()
    body = (candidate.get("embedding_text") or "").strip() or (candidate.get("source_quote") or "").strip()
    source_ref = (candidate.get("source_ref") or "").strip()
    parts = [p for p in (description, body) if p]
    text = "\n".join(parts)
    if source_ref:
        text += f"\nRef: {source_ref}"
    return text


def rerank(
    query: str, candidates: list[dict], top_k: int, model_name: str = DEFAULT_RERANK_MODEL,
) -> list[dict]:
    """Reorder candidates by relevance to query, trim to top_k.

    Each returned dict is the same object passed in, with a new
    rerank_score field attached (float, FlashRank's own confidence score --
    higher is more relevant). Order is descending by rerank_score.
    """
    if not candidates:
        return []

    if _is_remote_model(model_name):
        for c, score in zip(candidates, _remote_scores(query, candidates, model_name)):
            c["rerank_score"] = float(score)
        return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]

    if _is_hf_model(model_name):
        for c, score in zip(candidates, _hf_scores(query, candidates, model_name)):
            c["rerank_score"] = float(score)
        return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]

    # _get_ranker() first -- it's the seam that raises the clear "install the
    # 'rerank' extra" error. Importing RerankRequest before it would instead
    # surface flashrank's own bare ModuleNotFoundError when the extra isn't
    # installed.
    ranker = _get_ranker(model_name)
    from flashrank import RerankRequest

    passages = [
        {"id": i, "text": _scoring_text(c)}
        for i, c in enumerate(candidates)
    ]
    scored = ranker.rerank(RerankRequest(query=query, passages=passages))
    score_by_id = {p["id"]: p["score"] for p in scored}

    for i, c in enumerate(candidates):
        c["rerank_score"] = float(score_by_id[i])

    ordered = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ordered[:top_k]
