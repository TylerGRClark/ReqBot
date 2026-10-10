#!/usr/bin/env python3
"""WP-45.8 Stage B: the retrieval test with the resolver's string as the embedded stem (docs/PHASE45_WP458_REGISTRY.md and PHASE45_WP458_STAGEB_ADDENDUM.md).

  python3 stage_b_run.py --inputs plain
  python3 stage_b_run.py --inputs prod --repeat 1        # also 2 and 3; uses the saved rewrite/HyDE inputs of WP-45.1(c), never regenerates them

Reuses the WP-45.1(c)/(d) apparatus unchanged (frozen groups and questions, in-memory copy of the live index read once, target-only mode primary). New arms: `resolver`
(the Stage A string in the stem's place; no stem where the resolver has none) and `hybrid` (the string, else production's own text). Read-only on the live Qdrant;
writes only `outputs/stageb_results_*.json` here. Nothing is written to the pipeline, Qdrant or the apparatus' own outputs.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
C1 = _ROOT / "eval/spike_results/wp_45_1c"
for _p in (_HERE, C1, _ROOT, _ROOT / "eval"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engine as E  # noqa: E402  (wp_45_1c)
import run_test as RT  # noqa: E402  (wp_45_1c: frozen-input check, targets, query inputs, swap/restore)
import variants as V  # noqa: E402  (wp_45_1c)

SHADOW = Path.home() / "reqbot-work/scratch/wp45_8_scratch" / "wp458_shadow_processed" / "shadow_output.jsonl"
STAGE_A_REPORT = _HERE / "outputs" / "wp458_shadow_processed_report.json"
ARMS = ("resolver", "hybrid")


def resolver_strings(shadow_path=SHADOW, report_path=STAGE_A_REPORT):
    """({requirement_id: string}, evaluated ids): the Stage A string for each record that has one the addendum allows (unflagged, spans verbatim), and the ids Stage A
    covered at all, so a record Stage A never saw is not mistaken for one the resolver abstained on."""
    bad = {b["requirement_id"] for b in json.loads(Path(report_path).read_text(encoding="utf-8"))["spans_not_in_document"]}
    out, evaluated = {}, set()
    for line in Path(shadow_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            evaluated.add(r["requirement_id"])
            string = (r.get("resolver_string") or "").strip()
            if not r["flag"] and string and r["requirement_id"] not in bad:
                out[r["requirement_id"]] = string
    return out, evaluated


def resolver_text(payload, string):
    """Resolver arm: the string in the stem's place, or the quote alone when the resolver has no string."""
    if not string:
        return V.quote_alone_text(payload)
    quote = (payload.get("source_quote") or "").strip()
    return V.build_embedding_text({**payload, "embedding_text": f"{string}\n{quote}"})


def hybrid_text(payload, string):
    """Hybrid arm: the string, else what production embedded."""
    return resolver_text(payload, string) if string else V.production_text(payload)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    import ollama
    from fastembed import SparseTextEmbedding

    from pipeline.embed_and_index import EMBEDDING_MODEL, SPARSE_MODEL

    frozen = RT.verify_frozen()
    groups, targets = RT.load_targets()
    gold = RT.load_gold()
    strings, evaluated = resolver_strings()
    outdir = _HERE / "outputs"
    t0 = time.time()

    points, info, snap_digest = E.snapshot(args.qdrant_url)
    earlier = json.loads((C1 / "outputs" / "results_plain.json").read_text(encoding="utf-8"))["manifest"]["snapshot"]["digest"]
    not_indexed = [t["rid"] for t in targets if t["requirement_id"] not in points]
    targets = [t for t in targets if t["requirement_id"] in points]
    unseen_targets = [t["rid"] for t in targets if t["requirement_id"] not in evaluated]
    if unseen_targets:
        sys.exit(f"Stage A did not cover these tested records (the index or the corpus changed since Stage A): {unseen_targets}")
    not_in_stage_a = sorted(rid for rid in points if rid not in evaluated)  # keep production's vectors for these in both arms; reported
    client = E.build_memory_index(points, info["dense_size"])
    oc = ollama.Client(host=args.ollama_url)
    sm = SparseTextEmbedding(model_name=SPARSE_MODEL)

    texts = {"resolver": {}, "hybrid": {}}
    for requirement_id, p in points.items():
        s = strings.get(requirement_id, "")
        if requirement_id in evaluated:
            texts["resolver"][requirement_id] = resolver_text(p["payload"], s)
            texts["hybrid"][requirement_id] = hybrid_text(p["payload"], s)
        else:  # not covered by Stage A: no resolver result authorizes a change
            texts["resolver"][requirement_id] = texts["hybrid"][requirement_id] = V.production_text(p["payload"])
    target_ids = {t["requirement_id"] for t in targets}
    all_texts = sorted({tx for arm in ARMS for tx in texts[arm].values()})
    dvec = dict(zip(all_texts, E.embed_dense(all_texts, oc, EMBEDDING_MODEL)))
    svec = dict(zip(all_texts, E.embed_sparse(all_texts, sm)))
    vec = {arm: {rid: (dvec[tx], svec[tx]) for rid, tx in texts[arm].items()} for arm in ARMS}

    questions = sorted({t[s] for t in targets for s in RT.STYLES} | {g["query"] for g in gold})
    if args.inputs == "prod":
        cache = C1 / "outputs" / f"prod_inputs_r{args.repeat}.json"
        if not cache.exists():
            sys.exit(f"{cache} is missing: Stage B uses the saved rewrite/HyDE inputs and never regenerates them")
    inputs = RT.make_inputs(questions, args.inputs, args.repeat, oc, args.rewrite_model, C1 / "outputs")
    qvec = RT.vectorize(inputs, oc, EMBEDDING_MODEL, sm)

    def fused_for(question):
        return E.search(client, *qvec[question])

    rows, gold_rows = [], []

    def add(arm, mode, t, style, fused):
        rows.append({"pid": t["pid"], "rid": t["rid"], "group": t["group"], "style": style, "no_party": t["no_party"], "arm": arm, "mode": mode,
                     "applied": True, "has_string": strings.get(t["requirement_id"]) is not None, **E.rank_info(fused, t["requirement_id"])})

    for t in targets:
        for s in RT.STYLES:
            add("production", "base", t, s, fused_for(t[s]))
    for t in targets:  # target-only: only this record's vectors change
        for arm in ARMS:
            RT.swap(client, points, t["requirement_id"], *vec[arm][t["requirement_id"]])
            try:
                for s in RT.STYLES:
                    add(arm, "target_only", t, s, fused_for(t[s]))
            finally:
                RT.restore(client, points, t["requirement_id"])

    from retrieval_eval_harness import compute_metrics

    def gold_pass(arm, mode):
        for g in gold:
            ids = [rid for rid, _ in E.returned(fused_for(g["query"]))]
            gold_rows.append({"query_id": g["query_id"], "shape": g["shape"], "arm": arm, "mode": mode, "returned": ids,
                              **compute_metrics(set(g["relevant_requirement_ids"]), ids)})

    gold_pass("production", "base")
    for arm in ARMS:  # cohort: the policy on every indexed record at once
        for rid, vs in vec[arm].items():
            RT.swap(client, points, rid, *vs)
        try:
            for t in targets:
                for s in RT.STYLES:
                    add(arm, "cohort", t, s, fused_for(t[s]))
            gold_pass(arm, "cohort")
        finally:
            for rid in vec[arm]:
                RT.restore(client, points, rid)

    first = {(r["rid"], r["style"]): (r["best_rank"], r["worst_rank"], r["score"]) for r in rows if r["arm"] == "production"}
    drift = [(t["rid"], s) for t in targets for s in RT.STYLES
             if (lambda r: (r["best_rank"], r["worst_rank"], r["score"]))(E.rank_info(fused_for(t[s]), t["requirement_id"])) != first[(t["rid"], s)]]
    if drift:
        sys.exit(f"the index did not return to production state after the swaps: {drift[:5]}")

    manifest = {
        "script": "eval/spike_results/wp_45_8/stage_b_run.py", "inputs_mode": args.inputs, "repeat": args.repeat if args.inputs == "prod" else None,
        "frozen_hashes": frozen["sha256"], "snapshot": {**info, "digest": snap_digest, "digest_matches_wp451c_results": snap_digest == earlier, "earlier_digest": earlier},
        "strings": {"records_with_string": sum(1 for rid in points if rid in strings), "records_in_index": len(points), "index_records_not_in_stage_a": not_in_stage_a,
                    "targets_with_string": sum(1 for t in targets if t["requirement_id"] in strings), "targets": len(targets),
                    "shadow_output_sha256": sha256(SHADOW), "stage_a_report_sha256": sha256(STAGE_A_REPORT)},
        "constants": {"top_k": E.TOP_K, "min_score": E.MIN_SCORE, "fusion_limit": E.FUSION_LIMIT, "prefetch_per_leg": E.PREFETCH, "diagnostic_depth": E.DIAG_DEPTH},
        "prod_input_cache_sha256": sha256(C1 / "outputs" / f"prod_inputs_r{args.repeat}.json") if args.inputs == "prod" else None,
        "models": {"embedding": EMBEDDING_MODEL, "sparse": SPARSE_MODEL, "rewrite": args.rewrite_model if args.inputs == "prod" else None},
        "ollama_digests": {m.model: m.digest for m in oc.list().models}, "restore_check": f"all {len(first)} production-state ranks identical after the last swap was undone",
        "code_sha256": {n: sha256(_HERE / n) for n in ("stage_b_run.py", "stage_b_analyze.py")}, "excluded_not_in_live_index": not_indexed,
        "target_ids_in_index": len(target_ids), "seconds": round(time.time() - t0, 1),
    }
    out = outdir / ("stageb_results_" + args.inputs + (f"_r{args.repeat}" if args.inputs == "prod" else "") + ".json")
    out.write_text(json.dumps({"manifest": manifest, "rows": rows, "gold": gold_rows}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(rows)} target rows, {len(gold_rows)} gold rows -> {out} ({manifest['seconds']}s); index digest matches the WP-45.1(c) run: {snap_digest == earlier}")


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", choices=("plain", "prod"), default="plain")
    ap.add_argument("--repeat", type=int, choices=(1, 2, 3), default=1)
    ap.add_argument("--qdrant-url", default=cfg.qdrant_url)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--rewrite-model", default="llama3.1:8b-instruct-q4_K_M")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
