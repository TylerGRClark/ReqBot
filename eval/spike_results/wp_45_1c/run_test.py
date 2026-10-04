"""WP-45.1(c)/(d): run the retrieval test on an in-memory copy of the live index (read-only on the live Qdrant).

Arms (see docs/PHASE45_WP451C_PLAN.md, written before this ran):
  production    the live vectors, untouched
  quote_alone   the record's own text without its stem        (records the live index embedded with a stem)
  oracle        the adjudicated lead-in in the stem's place   (records Tyler's rulings say need a lead-in)
  h3_*          the leaf heading in front of the text, where the frozen deterministic rule (heading_rule.py) applies
  h4_*          the leaf heading in front of the text, for the 31 audited records Tyler's rulings place in the heading
                (an informative benchmark, not an upper bound); *_dense changes the dense vector only, *_both also the BM25 one
Modes:
  target_only   only the queried target's vectors are swapped; every competitor keeps its production vector (primary)
  cohort        the policy applied to every affected record at once (secondary: what it does to the whole result)
Query inputs:
  plain         no rewrite and no HyDE: identical query vectors in every arm (headline)
  prod          rewrite and a HyDE hypothesis generated once per query and repeat, cached, reused for every arm

Run from the repo root:
  python3 eval/spike_results/wp_45_1c/run_test.py --inputs plain
  python3 eval/spike_results/wp_45_1c/run_test.py --inputs prod --repeat 1
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engine as E  # noqa: E402
import heading_rule as H  # noqa: E402
import variants as V  # noqa: E402

logging.disable(logging.CRITICAL)

FROZEN = _HERE / "outputs" / "queries_frozen.json"
STYLES = ("topic", "party")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen():
    """Stop if anything frozen before the first retrieval has changed since."""
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    changed = [n for n, h in frozen["sha256"].items() if sha256(_HERE / n) != h]
    if changed:
        sys.exit(
            f"frozen inputs changed since the freeze: {changed}; queries and groups are never edited after a retrieval"
        )
    return frozen


def load_targets():
    groups = json.loads((_HERE / "groups.json").read_text(encoding="utf-8"))
    ids = json.loads((_HERE / "query_ids.json").read_text(encoding="utf-8"))["ids"]
    queries = {}
    for line in (_HERE / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            queries[q["pid"]] = q
    targets = []
    for pid, rid in sorted(ids.items()):
        rec = groups["records"][rid]
        targets.append(
            {
                "pid": pid,
                "rid": rid,
                "requirement_id": rec["requirement_id"],
                "group": rec["group"],
                "lead_in": rec["lead_in_text"],
                "in_oracle": rid in set(groups["oracle_set"]),
                "no_party": bool(queries[pid].get("no_party")),
                "topic": queries[pid]["topic"],
                "party": queries[pid]["party"],
            }
        )
    return groups, targets


def load_gold():
    gold = []
    for line in (
        (_ROOT / "eval/gold_retrieval_queries.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        if line.strip():
            g = json.loads(line)
            if g["relevant_requirement_ids"]:
                gold.append(g)
    return gold


# ------------------------------------------------------------------------------------------------- query inputs


def make_inputs(questions, mode, repeat, ollama_client, rewrite_model, cache_dir):
    """{question: {"dense_query", "sparse_query", "hypothesis"}} for the chosen input mode."""
    if mode == "plain":
        return {q: {"dense_query": q, "sparse_query": q, "hypothesis": None} for q in questions}
    import core.ask as ask

    cache = cache_dir / f"prod_inputs_r{repeat}.json"
    done = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for q in questions:
        if q in done:
            continue
        rw = ask.rewrite_query(q, rewrite_model, ollama_client)
        dense_q = rw["expanded_query"]
        sparse_q = dense_q + (" " + " ".join(rw["control_ids"]) if rw["control_ids"] else "")
        done[q] = {
            "dense_query": dense_q,
            "sparse_query": sparse_q,
            "control_ids": list(rw["control_ids"]),
            "hypothesis": ask.generate_hyde_hypothesis(
                q, rewrite_model, ollama_client, enabled=False
            ),
        }
        cache.write_text(json.dumps(done, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {q: done[q] for q in questions}


def vectorize(inputs, ollama_client, embedding_model, sparse_model):
    """{question: (dense, sparse, hyde_or_None)}; each distinct text is embedded once."""
    texts = sorted({t for v in inputs.values() for t in (v["dense_query"], v["hypothesis"]) if t})
    dense = dict(zip(texts, E.embed_dense(texts, ollama_client, embedding_model)))
    sp_texts = sorted({v["sparse_query"] for v in inputs.values()})
    sparse = dict(zip(sp_texts, E.embed_sparse(sp_texts, sparse_model)))
    return {
        q: (
            dense[v["dense_query"]],
            sparse[v["sparse_query"]],
            dense[v["hypothesis"]] if v["hypothesis"] else None,
        )
        for q, v in inputs.items()
    }


# --------------------------------------------------------------------------------------------------- the test


def write_variant_texts(path, variant_texts):
    """One JSON object per line, id before text (a sentence that ends in 'access.' followed by the next id trips the secrets scanner)."""
    with open(path, "w", encoding="utf-8") as f:
        for arm in sorted(variant_texts):
            for requirement_id in sorted(variant_texts[arm]):
                row = {"arm": arm, "requirement_id": requirement_id, "text": variant_texts[arm][requirement_id]}
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def swap(client, points, rid, dense, sparse):
    client.upsert(E.COLLECTION, [E.point_struct(points[rid], dense=dense, sparse=sparse)])


def restore(client, points, rid):
    client.upsert(E.COLLECTION, [E.point_struct(points[rid])])


def run(args):
    import ollama
    from fastembed import SparseTextEmbedding

    from pipeline.embed_and_index import EMBEDDING_MODEL, SPARSE_MODEL

    frozen = verify_frozen()
    groups, targets = load_targets()
    gold = load_gold()
    outdir = _HERE / "outputs"
    t0 = time.time()

    points, info, snap_digest = E.snapshot(args.qdrant_url)
    # A record that is in the pinned corpus files but not in the live index cannot be retrieved; it is left out, said so,
    # and the frozen group file is not touched (the exclusion depends on the index, never on a result).
    not_indexed = [t["rid"] for t in targets if t["requirement_id"] not in points]
    targets = [t for t in targets if t["requirement_id"] in points]
    client = E.build_memory_index(points, info["dense_size"])
    oc = ollama.Client(host=args.ollama_url)
    sm = SparseTextEmbedding(model_name=SPARSE_MODEL)

    # texts for the two non-production arms
    qa_text, or_text = {}, {}
    for requirement_id, p in points.items():
        if V.has_stem(p["payload"]):
            qa_text[requirement_id] = V.quote_alone_text(p["payload"])
    for t in targets:
        if t["in_oracle"]:
            or_text[t["requirement_id"]] = V.oracle_text(
                points[t["requirement_id"]]["payload"], t["lead_in"]
            )
    variant_texts = {
        "quote_alone": qa_text,
        "oracle": or_text,
        "production_for_targets": {
            t["requirement_id"]: V.production_text(points[t["requirement_id"]]["payload"])
            for t in targets
        },
    }

    h3_text, h4_text = {}, {}
    for requirement_id, p in points.items():
        path = H.heading_path(p["payload"])
        if H.h3_applies(path):
            h3_text[requirement_id] = V.heading_text(p["payload"], H.leaf_heading(path))
    heading_located = set(groups["heading_located"])
    for t in targets:
        if t["rid"] in heading_located:
            p = points[t["requirement_id"]]
            h4_text[t["requirement_id"]] = V.heading_text(p["payload"], H.leaf_heading(H.heading_path(p["payload"])))
    variant_texts.update({"h3": h3_text, "h4": h4_text})
    write_variant_texts(outdir / "text_variants.jsonl", variant_texts)

    all_texts = sorted(set(qa_text.values()) | set(or_text.values()) | set(h3_text.values()) | set(h4_text.values()))
    dvec = dict(zip(all_texts, E.embed_dense(all_texts, oc, EMBEDDING_MODEL)))
    svec = dict(zip(all_texts, E.embed_sparse(all_texts, sm)))
    vec = {
        "quote_alone": {rid: (dvec[txt], svec[txt]) for rid, txt in qa_text.items()},
        "oracle": {rid: (dvec[txt], svec[txt]) for rid, txt in or_text.items()},
        "h3_dense": {rid: (dvec[txt], None) for rid, txt in h3_text.items()},
        "h3_both": {rid: (dvec[txt], svec[txt]) for rid, txt in h3_text.items()},
        "h4_dense": {rid: (dvec[txt], None) for rid, txt in h4_text.items()},
        "h4_both": {rid: (dvec[txt], svec[txt]) for rid, txt in h4_text.items()},
    }
    arms = list(vec)

    questions = sorted({t[s] for t in targets for s in STYLES} | {g["query"] for g in gold})
    inputs = make_inputs(questions, args.inputs, args.repeat, oc, args.rewrite_model, outdir)
    qvec = vectorize(inputs, oc, EMBEDDING_MODEL, sm)

    if args.inputs == "prod":
        # Proof that the adapter equals the real retrieve() when both are given these exact cached rewrite and HyDE inputs.
        sample = [g["query"] for g in gold[:8]]
        cached = {
            q: {
                "expanded_query": inputs[q]["dense_query"],
                "control_ids": inputs[q]["control_ids"],
                "hypothesis": inputs[q]["hypothesis"],
            }
            for q in sample
        }
        bad = E.check_adapter(client, sample, args.ollama_url, args.qdrant_url, oc, EMBEDDING_MODEL, sm, cached=cached)
        if bad:
            sys.exit(f"the adapter differs from retrieve() on cached production-path inputs: {bad[:1]}")

    def fused_for(question):
        return E.search(client, *qvec[question])

    rows, gold_rows = [], []

    def add(arm, mode, t, style, fused, applied=True):
        info_ = E.rank_info(fused, t["requirement_id"])
        rows.append(
            {
                "pid": t["pid"],
                "rid": t["rid"],
                "group": t["group"],
                "style": style,
                "no_party": t["no_party"],
                "arm": arm,
                "mode": mode,
                "applied": applied,
                **info_,
            }
        )

    # base (production) for every target, and gold
    for t in targets:
        for s in STYLES:
            add("production", "base", t, s, fused_for(t[s]))
    # target-only substitution; a heading arm that does not apply to a target leaves it at its production result
    base_by_key = {(r["rid"], r["style"]): r for r in rows if r["arm"] == "production"}
    for t in targets:
        for arm in arms:
            vs = vec[arm].get(t["requirement_id"])
            if vs is None:
                if arm.startswith("h"):
                    for s in STYLES:
                        copy = {**base_by_key[(t["rid"], s)], "arm": arm, "mode": "target_only", "applied": False}
                        rows.append(copy)
                continue
            swap(client, points, t["requirement_id"], *vs)
            try:
                for s in STYLES:
                    add(arm, "target_only", t, s, fused_for(t[s]))
            finally:
                restore(client, points, t["requirement_id"])
    # gold queries and cohort-wide substitution
    from retrieval_eval_harness import compute_metrics

    def gold_pass(arm, mode):
        for g in gold:
            ids = [rid for rid, _ in E.returned(fused_for(g["query"]))]
            gold_rows.append(
                {
                    "query_id": g["query_id"],
                    "shape": g["shape"],
                    "arm": arm,
                    "mode": mode,
                    "returned": ids,
                    **compute_metrics(set(g["relevant_requirement_ids"]), ids),
                }
            )

    gold_pass("production", "base")
    for arm in arms:
        for requirement_id, vs in vec[arm].items():
            swap(client, points, requirement_id, *vs)
        try:
            for t in targets:
                for s in STYLES:
                    add(arm, "cohort", t, s, fused_for(t[s]))
            gold_pass(arm, "cohort")
        finally:
            for requirement_id in vec[arm]:
                restore(client, points, requirement_id)

    # Proof that every swap was undone: the production-state ranks, measured again at the end, equal the first ones.
    first = {(r["rid"], r["style"]): (r["best_rank"], r["worst_rank"], r["score"]) for r in rows if r["arm"] == "production"}
    drift = []
    for t in targets:
        for s in STYLES:
            r = E.rank_info(fused_for(t[s]), t["requirement_id"])
            if (r["best_rank"], r["worst_rank"], r["score"]) != first[(t["rid"], s)]:
                drift.append((t["rid"], s))
    if drift:
        sys.exit(f"the index did not return to production state after the swaps: {drift[:5]}")

    manifest = {
        "script": "eval/spike_results/wp_45_1c/run_test.py",
        "adapter_check": "12 plain-mode and 8 cached production-path gold queries matched retrieve() exactly (see engine.check_adapter)" if args.inputs == "prod" else "see engine.check_adapter (plain mode, 12 gold queries, run during development)",
        "restore_check": f"all {len(first)} production-state ranks identical after the last swap was undone",
        "inputs_mode": args.inputs,
        "repeat": args.repeat if args.inputs == "prod" else None,
        "frozen_manifest_sha256": sha256(FROZEN),
        "frozen_hashes": frozen["sha256"],
        "snapshot": {
            **info,
            "digest": snap_digest,
            "note": "live collection read once, with vectors, read-only",
        },
        "constants": {
            "top_k": E.TOP_K,
            "min_score": E.MIN_SCORE,
            "fusion_limit": E.FUSION_LIMIT,
            "prefetch_per_leg": E.PREFETCH,
            "diagnostic_depth": E.DIAG_DEPTH,
        },
        "models": {
            "embedding": EMBEDDING_MODEL,
            "sparse": SPARSE_MODEL,
            "rewrite": args.rewrite_model if args.inputs == "prod" else None,
        },
        "ollama_digests": {m.model: m.digest for m in oc.list().models},
        "code_sha256": {
            n: sha256(_HERE / n) for n in ("engine.py", "variants.py", "run_test.py", "groups.py")
        },
        "variant_texts_sha256": sha256(outdir / "text_variants.jsonl"),
        "targets": len(targets),
        "excluded_not_in_live_index": not_indexed,
        "arm_sizes": {arm: len(v) for arm, v in vec.items()},
        "seconds": round(time.time() - t0, 1),
    }
    out = outdir / (
        f"results_{args.inputs}" + (f"_r{args.repeat}" if args.inputs == "prod" else "") + ".json"
    )
    out.write_text(
        json.dumps(
            {"manifest": manifest, "rows": rows, "gold": gold_rows}, indent=1, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(rows)} target rows, {len(gold_rows)} gold rows -> {out} ({manifest['seconds']}s)")


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", choices=("plain", "prod"), default="plain")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--qdrant-url", default=cfg.qdrant_url)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--rewrite-model", default="llama3.1:8b-instruct-q4_K_M")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
