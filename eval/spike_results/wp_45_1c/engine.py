"""WP-45.1(c)/(d): an in-memory copy of the live index and an adapter that mirrors core.ask.retrieve()'s hybrid path.

Measurement only. Nothing here writes to the real Qdrant (the live collection is only read, once, with its vectors) and
nothing here changes production code: the real `core.ask.retrieve()` is exercised, with the collection swapped by
patching `core.ask.QdrantClient` inside the eval process, only to prove that the adapter returns the same list.

Why an adapter at all (Codex review): `retrieve(top_k=100)` would change the per-leg prefetch from 100 to 500 and so
change the RRF inputs. At top_k 20 and min_score 0.02 production prefetches 100 per leg, fuses 60, drops fused scores
below 0.02 and returns 20. The adapter issues the same legs with the same prefetch, asks for a wider fused list as a
labelled diagnostic, and derives the production-returned list from its first 60 exactly as production does.
"""

import hashlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qdrant_client import QdrantClient, models  # noqa: E402

COLLECTION = "grc_requirements"  # core.ask.COLLECTION_NAME; asserted equal in `check_adapter`
TOP_K = 20
MIN_SCORE = 0.02
FUSION_LIMIT = (
    max(TOP_K * 3, 50) if MIN_SCORE > 0 else TOP_K
)  # 60: how many fused results production requests
PREFETCH = max(100, TOP_K * 5, FUSION_LIMIT)  # 100: candidates per leg
DIAG_DEPTH = 100  # how deep the diagnostic fused list goes; same legs as production, only the fused limit differs
BATCH = 64


# ---------------------------------------------------------------------------------------------------------- snapshot


def snapshot(qdrant_url, collection=COLLECTION):
    """Read every point of the live collection once, with vectors. Returns (points, info, digest).

    points: {requirement_id: {"id", "payload", "dense", "sparse_indices", "sparse_values"}}
    The digest covers ids and vectors, so a result can be tied to the exact index it was measured on.
    """
    live = QdrantClient(url=qdrant_url)
    points, offset = {}, None
    while True:
        batch, offset = live.scroll(
            collection, limit=256, offset=offset, with_payload=True, with_vectors=True
        )
        for p in batch:
            rid = p.payload["requirement_id"]
            sp = p.vector["sparse"]
            points[rid] = {
                "id": p.id,
                "payload": p.payload,
                "dense": list(p.vector["dense"]),
                "sparse_indices": list(sp.indices),
                "sparse_values": list(sp.values),
            }
        if offset is None:
            break
    cfg = live.get_collection(collection).config.params
    info = {
        "collection": collection,
        "points": len(points),
        "dense_size": cfg.vectors["dense"].size,
        "dense_distance": str(cfg.vectors["dense"].distance),
        "sparse_modifier": str(getattr(cfg.sparse_vectors["sparse"], "modifier", None)),
    }
    return points, info, digest(points)


def digest(points):
    h = hashlib.sha256()
    for rid in sorted(points):
        p = points[rid]
        h.update(rid.encode())
        h.update(repr([round(x, 6) for x in p["dense"]]).encode())
        h.update(
            repr(list(zip(p["sparse_indices"], [round(x, 6) for x in p["sparse_values"]]))).encode()
        )
    return h.hexdigest()


def point_struct(rec, dense=None, sparse=None):
    """A PointStruct for a snapshot record; `dense` / `sparse` = (indices, values) override its vectors."""
    s_idx, s_val = sparse if sparse is not None else (rec["sparse_indices"], rec["sparse_values"])
    return models.PointStruct(
        id=rec["id"],
        vector={
            "dense": dense if dense is not None else rec["dense"],
            "sparse": models.SparseVector(indices=s_idx, values=s_val),
        },
        payload=rec["payload"],
    )


def build_memory_index(points, dense_size):
    """In-memory collection with the live configuration (dense cosine, sparse BM25 with no IDF modifier)."""
    client = QdrantClient(":memory:")
    client.create_collection(
        COLLECTION,
        vectors_config={
            "dense": models.VectorParams(size=dense_size, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
        },
    )
    items = [point_struct(points[rid]) for rid in sorted(points)]
    for i in range(0, len(items), 256):
        client.upsert(COLLECTION, items[i : i + 256])
    return client


# ---------------------------------------------------------------------------------------------------------- embedding


def embed_dense(texts, ollama_client, model):
    out = []
    for i in range(0, len(texts), BATCH):
        out += [
            list(v) for v in ollama_client.embed(model=model, input=texts[i : i + BATCH]).embeddings
        ]
    return out


def embed_sparse(texts, sparse_model):
    return [(e.indices.tolist(), e.values.tolist()) for e in sparse_model.embed(texts)]


# ----------------------------------------------------------------------------------------------------------- search


def search(client, dense_vec, sparse_vec, hyde_vec=None, depth=DIAG_DEPTH):
    """The same legs production builds, with a wider fused limit.

    Returns the fused list [(requirement_id, score)] in the engine's order, `depth` long at most.
    """
    legs = [
        models.Prefetch(query=dense_vec, using="dense", limit=PREFETCH),
        models.Prefetch(
            query=models.SparseVector(indices=sparse_vec[0], values=sparse_vec[1]),
            using="sparse",
            limit=PREFETCH,
        ),
    ]
    if hyde_vec is not None:
        legs.append(models.Prefetch(query=hyde_vec, using="dense", limit=PREFETCH))
    hits = client.query_points(
        COLLECTION,
        prefetch=legs,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=depth,
        with_payload=["requirement_id"],
    ).points
    return [(h.payload["requirement_id"], h.score) for h in hits]


def returned(fused):
    """What production hands back from the same fusion: its first FUSION_LIMIT, minus scores under MIN_SCORE, first TOP_K."""
    return [(rid, s) for rid, s in fused[:FUSION_LIMIT] if s >= MIN_SCORE][:TOP_K]


def rank_info(fused, target):
    """Where `target` sits in the fused list, with ties reported as best and worst case.

    best  = 1 + the number of results scoring strictly higher; worst = the number scoring at least as high (itself included).
    A target beyond the list gets None. `survives` is whether its fused score clears MIN_SCORE; `in_returned` whether it
    is in the list production would return (position-based, so it also reflects tie order).
    """
    for i, (rid, score) in enumerate(fused):
        if rid == target:
            best = 1 + sum(1 for _, s in fused if s > score)
            worst = sum(1 for _, s in fused if s >= score)
            return {
                "found": True,
                "best_rank": best,
                "worst_rank": worst,
                "score": score,
                "survives": score >= MIN_SCORE,
                "in_returned": any(r == target for r, _ in returned(fused)),
            }
    return {
        "found": False,
        "best_rank": None,
        "worst_rank": None,
        "score": None,
        "survives": False,
        "in_returned": False,
    }


# ------------------------------------------------------------------------------------------- proof against retrieve()


def check_adapter(
    client,
    questions,
    ollama_url,
    qdrant_url,
    ollama_client,
    embedding_model,
    sparse_model,
    cached=None,
):
    """Run the real core.ask.retrieve() against the in-memory index and compare with the adapter.

    `cached[question] = {"expanded_query", "control_ids", "hypothesis"}` is injected through the two LLM-backed
    functions so both sides see identical inputs (hyde and rewrite off when `cached` is None). Returns a list of
    mismatches (empty = identical returned ids and scores for every question).
    """
    import core.ask as ask

    assert ask.COLLECTION_NAME == COLLECTION, (
        "core.ask.COLLECTION_NAME changed; the adapter targets the old name"
    )
    real = (ask.QdrantClient, ask.rewrite_query, ask.generate_hyde_hypothesis)
    mismatches = []
    try:
        ask.QdrantClient = lambda *a, **k: client
        if cached is not None:
            ask.rewrite_query = lambda q, m, c: {
                "expanded_query": cached[q]["expanded_query"],
                "control_ids": cached[q]["control_ids"],
                "domain_tags": [],
            }
            ask.generate_hyde_hypothesis = lambda q, m, c, **k: cached[q]["hypothesis"]
        for q in questions:
            got = ask.retrieve(
                q,
                top_k=TOP_K,
                min_score=MIN_SCORE,
                no_rewrite=cached is None,
                hyde=cached is not None,
                qdrant_url=qdrant_url,
                ollama_url=ollama_url,
            )
            want_ids = [(r["requirement_id"], round(r["score"], 6)) for r in got["results"]]
            dense_q, sparse_q, hypo = q, q, None
            if cached is not None:
                dense_q = cached[q]["expanded_query"]
                sparse_q = dense_q + (
                    " " + " ".join(cached[q]["control_ids"]) if cached[q]["control_ids"] else ""
                )
                hypo = cached[q]["hypothesis"]
            dv = embed_dense([dense_q], ollama_client, embedding_model)[0]
            sv = embed_sparse([sparse_q], sparse_model)[0]
            hv = embed_dense([hypo], ollama_client, embedding_model)[0] if hypo else None
            mine = [(rid, round(s, 6)) for rid, s in returned(search(client, dv, sv, hv))]
            if mine != want_ids:
                mismatches.append({"question": q, "retrieve": want_ids, "adapter": mine})
    finally:
        ask.QdrantClient, ask.rewrite_query, ask.generate_hyde_hypothesis = real
    return mismatches
