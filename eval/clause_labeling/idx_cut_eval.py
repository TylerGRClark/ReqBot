#!/usr/bin/env python3
"""PREREG12: score one arm collection on the remapped gold set through the real core.ask.retrieve() path.

Only core.ask.COLLECTION_NAME is pointed at the throwaway collection; everything else (query rewrite, HyDE, 3-leg
hybrid RRF, min_score, optional reranker) is the production code. Modes:
  prod   : rewrite on, HyDE on, no reranker (what `reqbot ask` runs today)
  nohyde : rewrite on, HyDE off (deterministic given the index)
  rerank : rewrite on, HyDE off, reranker on (pool 100)
Writes JSON to --out-dir/<arm>_<mode>_<run>.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
import core.ask as ASK  # noqa: E402
from retrieval_eval_harness import run_harness, load_gold_queries  # noqa: E402


def hit_at(rel, ids, k):
    return 1.0 if set(ids[:k]) & rel else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--mode", required=True, choices=["prod", "nohyde", "rerank"])
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--gold", default=str(Path(__file__).with_name("PREREG12_gold_remapped.jsonl")))
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    from core import config
    cfg = config.load()
    coll = f"idxtest_{a.arm}"
    assert coll.startswith("idxtest_")
    ASK.COLLECTION_NAME = coll
    qs = load_gold_queries(a.gold)
    t0 = time.time()
    rep = run_harness(qs, qdrant_url=cfg.qdrant_url, ollama_url=cfg.ollama_url, top_k=20, min_score=cfg.min_score,
                      hyde=(a.mode == "prod"), rerank=(a.mode == "rerank"))
    gold = {q["query_id"]: set(q["relevant_requirement_ids"]) for q in qs}
    for r in rep["per_query"]:
        if "retrieved_ids" in r and gold[r["query_id"]]:
            for k in (1, 3, 5, 10):
                r[f"hit@{k}"] = hit_at(gold[r["query_id"]], r["retrieved_ids"], k)
    rep["arm"], rep["mode"], rep["run"], rep["collection"] = a.arm, a.mode, a.run, coll
    rep["seconds"] = round(time.time() - t0, 1)
    out = Path(a.out_dir) / f"{a.arm}_{a.mode}_{a.run}.json"
    out.write_text(json.dumps(rep, indent=1))
    print(out, json.dumps(rep["aggregate"]))


if __name__ == "__main__":
    main()
