#!/usr/bin/env python3
"""HyPE spike round 2 (PREREGISTRATION_V2.md): re-indexing and evaluation only, no question generation.

  # 1. checklists of the library documents (one JSON per document in a directory), then:
  PYTHONPATH=. python3 eval/spike_results/hype/run_hype_v2.py all --checklists DIR

Stages (resumable): gate (which records have a draft audit question), build (scratch collections C and C2, copied from the
round-1 scratch collection, no new embedding), evaluate (arms A, B, C, C2 on the 232 queries and the gold queries).
Reads the live collection and the round-1 scratch collection; writes only new grc_hype_spike_v2_* collections.
"""
import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parents[2]), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hype_lib as H  # noqa: E402
import run_hype as R  # noqa: E402

log = logging.getLogger("hype2")
QUERY_SET = Path.home() / "reqbot-work" / "scratch" / "retrieval_set" / "retrieval_set_v1.json"
V1_OUT = Path.home() / "reqbot-work" / "scratch" / "hype_spike"
DEFAULT_OUT = Path.home() / "reqbot-work" / "scratch" / "hype_spike_v2"
MIN_CHARS = 60
ARMS = ("A", "B", "C", "C2")


def stage_gate(args, out: Path) -> int:
    from qdrant_client import QdrantClient
    files = sorted(Path(args.checklists).glob("*.json"))
    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    gate = H.gated_ids(docs)
    payloads = [p.payload for p in R.live_payloads(QdrantClient(url=R.settings(args)[0]))]
    ids = {p["requirement_id"] for p in payloads}
    c_in = {p["requirement_id"] for p in payloads if H.gate_c(p, gate)}
    c2_in = {p["requirement_id"] for p in payloads if H.gate_c(p, gate, MIN_CHARS)}
    summary = {"checklist_documents": [f.stem for f in files], "live_records": len(ids), "gated_in_C": len(c_in), "gated_in_C2": len(c2_in),
               "share_C": round(len(c_in) / len(ids), 4), "share_C2": round(len(c2_in) / len(ids), 4),
               "gate_ids_not_in_live_index": len(gate - ids)}
    (out / "gate.json").write_text(json.dumps({"summary": summary, "C": sorted(c_in), "C2": sorted(c2_in)}), encoding="utf-8")
    log.info("gate: %s", summary)
    return 0


def stage_build(args, out: Path) -> int:
    from qdrant_client import QdrantClient, models

    from pipeline import embed_and_index as EI
    client = QdrantClient(url=R.settings(args)[0])
    source = R.guard_scratch(R.load_state(V1_OUT)["collection"])
    gate = json.loads((out / "gate.json").read_text(encoding="utf-8"))
    sets = {"C": set(gate["C"]), "C2": set(gate["C2"])}
    state = R.load_state(out)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    names = state.get("collections") or {k: R.guard_scratch(f"grc_hype_spike_v2_{k}_{stamp}") for k in sets}
    state.update({"collections": names, "source": source})
    R.save_state(out, state)
    for k, n in names.items():
        if not client.collection_exists(n):
            dim = client.get_collection(source).config.params.vectors["dense"].size
            EI.create_collection(client, R.guard_scratch(n), dim)
    bufs = {k: [] for k in sets}
    counts = {k: {"base": 0, "questions": 0} for k in sets}

    def flush(k, force=False):
        if bufs[k] and (force or len(bufs[k]) >= 200):
            client.upsert(collection_name=R.guard_scratch(names[k]), points=bufs[k])
            bufs[k] = []

    offset = None
    while True:
        batch, offset = client.scroll(source, limit=256, offset=offset, with_payload=True, with_vectors=True)
        for p in batch:
            is_q = bool(p.payload.get("hype"))
            for k, ids in sets.items():
                if is_q and p.payload["requirement_id"] not in ids:
                    continue
                if is_q and k == "C2" and len(H.record_text(p.payload)) < MIN_CHARS:
                    continue
                bufs[k].append(models.PointStruct(id=p.id, vector=p.vector, payload=p.payload))
                counts[k]["questions" if is_q else "base"] += 1
                flush(k)
        if offset is None:
            break
    for k in sets:
        flush(k, force=True)
    state["counts"] = counts
    R.save_state(out, state)
    log.info("build: %s %s", names, counts)
    return 0


def prepare_queries(args, client) -> tuple[list[dict], list[dict]]:
    rows = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    qs = [dict(r, set="v1", anchor_norm=H.normalise(r["anchor_quote"])) for r in rows]
    live_ids = {p.payload["requirement_id"] for p in R.live_payloads(client)}
    gold = []
    for q in R.read_jsonl(R.GOLD_FILE):
        rel = sorted(H.live_labels(q, live_ids))
        if q.get("shape") != "zero" and rel:
            gold.append({"id": q["query_id"], "query": q["query"], "relevant": rel, "set": "gold"})
    return qs, gold


def retrieve_arm(arm: str, question: str, collections: dict, qdrant_url: str, ollama_url: str, min_score: float) -> list[dict]:
    from core import ask as A
    original = A.COLLECTION_NAME
    A.COLLECTION_NAME = R.LIVE_COLLECTION if arm == "A" else collections[arm]
    try:
        k = R.TOP_K if arm == "A" else R.TOP_K * (1 + H.MAX_QUESTIONS)
        res = A.retrieve(question, top_k=k, min_score=min_score, qdrant_url=qdrant_url, ollama_url=ollama_url)
    finally:
        A.COLLECTION_NAME = original
    return H.collapse_to_requirement_id(res["results"], limit=R.TOP_K)


def stage_evaluate(args, out: Path) -> int:
    from qdrant_client import QdrantClient

    from core import ask as A
    from eval.retrieval_eval_harness import compute_metrics
    qdrant_url, ollama_url, min_score = R.settings(args)
    state = R.load_state(out)
    collections = {"B": R.guard_scratch(state["source"]), **{k: R.guard_scratch(v) for k, v in state["collections"].items()}}
    client = QdrantClient(url=qdrant_url)
    queries, gold = prepare_queries(args, client)
    cache_path = out / "query_cache.json"
    if not cache_path.exists() and (V1_OUT / "query_cache.json").exists():
        shutil.copy(V1_OUT / "query_cache.json", cache_path)  # round-1 rewrites and HyDE text: the gold queries see the same ones as before
    _, save_cache, _ = R._cache_wrappers(A, cache_path)
    rows_path = out / "eval_rows.jsonl"
    rows = {(r["query_id"], r["arm"]): r for r in R.read_jsonl(rows_path)}
    items = [(q["id"], q["query"], q) for q in queries] + [(q["id"], q["query"], q) for q in gold]
    t0 = time.monotonic()
    for i, (qid, text, q) in enumerate(items, 1):
        for arm in ARMS:
            if (qid, arm) in rows:
                continue
            try:
                ranked = retrieve_arm(arm, text, collections, qdrant_url, ollama_url, min_score)
            except Exception as e:  # noqa: BLE001
                log.error("%s arm %s failed: %s", qid, arm, e)
                return 1
            ids = [r["requirement_id"] for r in ranked]
            row = {"query_id": qid, "arm": arm, "set": q["set"], "retrieved": ids, "via_question": [bool(r.get("hype_question")) for r in ranked]}
            if q["set"] == "v1":
                hits = [H.target_hit(r, q["requirement_ids"], q["anchor_norm"]) for r in ranked]
                rank = next((n for n, h in enumerate(hits, 1) if h), None)
                row.update({"rank": rank, "found5": bool(rank and rank <= 5), "found10": bool(rank and rank <= 10),
                            "mrr": round(1 / rank, 4) if rank else 0.0})
            else:
                row.update(compute_metrics(set(q["relevant"]), ids))
            rows[(qid, arm)] = row
            R.append_jsonl(rows_path, row)
        save_cache()
        if i % 10 == 0 or i == len(items):
            log.info("evaluate: %d/%d queries, %.0fs", i, len(items), time.monotonic() - t0)
    result = summarise(queries, gold, rows, state)
    (out / "result_v2.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / "report_v2.md").write_text(format_report(result), encoding="utf-8")
    log.info("evaluate: wrote %s", out / "report_v2.md")
    return 0


def summarise(queries, gold, rows, state) -> dict:
    def pts(x):
        return round(100 * x, 2)

    def mean_of(subset, arm, key):
        v = [rows[(q["id"], arm)][key] for q in subset]
        return sum(v) / len(v) if v else None

    hard = [q for q in queries if q["fragment_hard"] or q["ambiguous_target"]]
    easy = [q for q in queries if not (q["fragment_hard"] or q["ambiguous_target"])]
    sealed = [q for q in queries if q["sealed"]]
    a_p5 = mean_of(gold, "A", "precision@5")
    res = {"queries": len(queries), "gold_queries": len(gold), "hard_rows": len(hard), "other_rows": len(easy), "sealed_rows": len(sealed),
           "collections": state["collections"], "counts": state.get("counts"), "arms": {}}
    base = [float(rows[(q["id"], "A")]["found5"]) for q in queries]
    for arm in ARMS:
        found = [float(rows[(q["id"], arm)]["found5"]) for q in queries]
        mean, lo, hi = H.paired_bootstrap([f - b for f, b in zip(found, base)])
        new_found = [q["id"] for q in queries if rows[(q["id"], arm)]["found5"] and not rows[(q["id"], "A")]["found5"]]
        new_lost = [q["id"] for q in queries if rows[(q["id"], "A")]["found5"] and not rows[(q["id"], arm)]["found5"]]
        entry = {
            "recall@5": round(mean_of(queries, arm, "found5"), 4), "recall@10": round(mean_of(queries, arm, "found10"), 4),
            "mrr": round(mean_of(queries, arm, "mrr"), 4), "gold_precision@5": round(mean_of(gold, arm, "precision@5"), 4),
            "rise_points": pts(mean), "ci95_points": [pts(lo), pts(hi)],
            "split": {"hard_rows_rise_points": pts(mean_of(hard, arm, "found5") - mean_of(hard, "A", "found5")),
                      "other_rows_rise_points": pts(mean_of(easy, arm, "found5") - mean_of(easy, "A", "found5"))},
            "sealed": {"recall@5": round(mean_of(sealed, arm, "found5"), 4), "A_recall@5": round(mean_of(sealed, "A", "found5"), 4)},
            "newly_found": new_found, "newly_lost": new_lost,
            "per_document": {d: {"n": len(sub), "recall@5": round(mean_of(sub, arm, "found5"), 3), "A": round(mean_of(sub, "A", "found5"), 3)}
                             for d in sorted({q["document"] for q in queries}) for sub in [[q for q in queries if q["document"] == d]]},
        }
        entry["gold_fall_points"] = pts(a_p5 - entry["gold_precision@5"])
        if arm != "A":
            entry["rule"] = H.decide_v2(entry["rise_points"], entry["ci95_points"][0], entry["gold_fall_points"], entry["split"]["other_rows_rise_points"])
        res["arms"][arm] = entry
    return res


def format_report(r: dict) -> str:
    L = ["# HyPE spike round 2: result", "",
         f"{r['queries']} queries ({r['hard_rows']} fragment_hard/ambiguous, {r['other_rows']} others, {r['sealed_rows']} sealed), "
         f"{r['gold_queries']} gold queries. Only the source row counts as correct, so absolute numbers run low; the paired comparison is the point.", ""]
    L += ["| arm | recall@5 | rise (pts) | 95% interval | recall@10 | MRR | gold p@5 | gold fall | hard rows | other rows | sealed r@5 (A) | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, e in r["arms"].items():
        rule = e.get("rule", {}).get("verdict", "-")
        L.append(f"| {arm} | {e['recall@5']:.3f} | {e['rise_points']:+.1f} | {e['ci95_points'][0]:+.1f} to {e['ci95_points'][1]:+.1f} | {e['recall@10']:.3f} | "
                 f"{e['mrr']:.3f} | {e['gold_precision@5']:.3f} | {e['gold_fall_points']:+.1f} | {e['split']['hard_rows_rise_points']:+.1f} | "
                 f"{e['split']['other_rows_rise_points']:+.1f} | {e['sealed']['recall@5']:.3f} ({e['sealed']['A_recall@5']:.3f}) | {rule} |")
    L += ["", "## Newly found / newly lost versus A at recall@5", ""]
    for arm in ARMS[1:]:
        e = r["arms"][arm]
        L += [f"- {arm}: found {len(e['newly_found'])}: {', '.join(e['newly_found']) or '-'}; lost {len(e['newly_lost'])}: {', '.join(e['newly_lost']) or '-'}"]
    L += ["", "## Per document, recall@5 (A / B / C / C2)", "", "| document | n | A | B | C | C2 |", "|---|---|---|---|---|---|"]
    for d, v in r["arms"]["A"]["per_document"].items():
        L.append(f"| {d} | {v['n']} | " + " | ".join(f"{r['arms'][a]['per_document'][d]['recall@5']:.2f}" for a in ARMS) + " |")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["all", "gate", "build", "evaluate"])
    ap.add_argument("--checklists", default="", help="directory of checklist JSON files, one per library document")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--qdrant-url", default="")
    ap.add_argument("--ollama-url", default="")
    ap.add_argument("--limit", type=int, default=0)  # unused; settings() shares the argparse shape of run_hype
    args = ap.parse_args()
    out = Path(args.out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stages = {"gate": stage_gate, "build": stage_build, "evaluate": stage_evaluate}
    for name in (["gate", "build", "evaluate"] if args.stage == "all" else [args.stage]):
        if name == "gate" and args.stage == "all" and not args.checklists and (out / "gate.json").exists():
            continue
        code = stages[name](args, out)
        if code:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
