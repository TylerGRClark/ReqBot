#!/usr/bin/env python3
"""HyPE spike harness (see PREREGISTRATION.md, decision_rule.json).

  PYTHONPATH=. python3 eval/spike_results/hype/run_hype.py all            # generate -> build -> evaluate
  PYTHONPATH=. python3 eval/spike_results/hype/run_hype.py all --limit 10 --out-dir ~/reqbot-work/scratch/hype_spike_dry   # dry run
  PYTHONPATH=. python3 eval/spike_results/hype/run_hype.py cleanup        # delete the scratch collection

Stages (each resumable; run `all` again after an interruption):
  generate  up to 3 grounded questions per record -> <out-dir>/questions.jsonl (one line per record, appended as it goes)
  build     scratch collection grc_hype_spike_<timestamp>: a copy of the live points plus one extra point per question
  evaluate  arm A (live collection) vs arm B (scratch) on the miss set and the gold set -> result.json, report.md
  cleanup   delete the scratch collection this harness created (refuses any other name)

Reads the live collection; never writes to it. Writes nothing under pipeline/, core/, services/ or any requirement JSONL.
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hype_lib as H  # noqa: E402

log = logging.getLogger("hype")

LIVE_COLLECTION = "grc_requirements"  # the alias the app reads; this harness only reads it
TOP_K = 20
MISS_FILE = _HERE / "miss_queries.jsonl"
RULE_FILE = _HERE / "decision_rule.json"
GOLD_FILE = _ROOT / "eval" / "gold_retrieval_queries.jsonl"
DEFAULT_OUT = Path.home() / "reqbot-work" / "scratch" / "hype_spike"


def read_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_state(out: Path) -> dict:
    p = out / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_state(out: Path, state: dict) -> None:
    (out / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def guard_scratch(name: str) -> str:
    """Every write or delete goes through here: only a name this harness invented, never the live alias."""
    if not name.startswith(H.SCRATCH_PREFIX) or name in (LIVE_COLLECTION, "grc_context"):
        raise RuntimeError(f"refusing to touch collection {name!r}: not a {H.SCRATCH_PREFIX}* scratch collection")
    return name


def live_payloads(client, with_vectors: bool = False) -> list:
    """Every point of the live collection (read-only scroll)."""
    out, offset = [], None
    while True:
        batch, offset = client.scroll(LIVE_COLLECTION, limit=256, offset=offset, with_payload=True, with_vectors=with_vectors)
        out += batch
        if offset is None:
            return out


def settings(args):
    from core import config as _config
    cfg = _config.load()
    return (args.qdrant_url or cfg.qdrant_url, args.ollama_url or cfg.ollama_url, cfg.min_score)


# ---------------------------------------------------------------- generate

def ollama_questions(prompt: str, model: str, ollama_url: str, timeout: int = 180, retries: int = 2) -> str:
    import requests
    from services import audit_questions as AQ
    payload = {"model": model, "prompt": prompt, "stream": False, "format": H.QUESTIONS_SCHEMA,
               "options": {"temperature": 0, "seed": 0, "num_predict": 300, "num_ctx": AQ.NUM_CTX}}
    for attempt in range(retries + 1):
        try:
            resp = requests.post(f"{ollama_url.rstrip('/')}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["response"]
        except requests.RequestException as e:
            if attempt == retries:
                raise
            log.warning("Ollama request failed (%s); retrying in %ds", e, 2 ** (attempt + 1))
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def generation_order(payloads: list[dict], miss_ids: set[str]) -> list[dict]:
    """The miss-set records first (so a short dry run exercises them), then everything else by id. Deterministic."""
    seen, rows = set(), []
    for p in payloads:
        rid = p.get("requirement_id")
        if rid and rid not in seen and (p.get("source_quote") or "").strip():
            seen.add(rid)
            rows.append(p)
    return sorted(rows, key=lambda p: (p["requirement_id"] not in miss_ids, p["requirement_id"]))


def stage_generate(args, out: Path) -> int:
    from qdrant_client import QdrantClient
    from services import audit_questions as AQ
    qdrant_url, ollama_url, _ = settings(args)
    model = args.model or AQ.MODEL
    miss_ids = {i for q in read_jsonl(MISS_FILE) for i in q["relevant_requirement_ids"]}
    payloads = [p.payload for p in live_payloads(QdrantClient(url=qdrant_url))]
    todo_all = generation_order(payloads, miss_ids)
    if args.limit:
        todo_all = todo_all[: args.limit]
    qfile = out / "questions.jsonl"
    done = {r["requirement_id"] for r in read_jsonl(qfile) if r.get("status") != "error"}
    todo = [p for p in todo_all if p["requirement_id"] not in done]
    log.info("generate: %d records in scope, %d done, %d to do (model %s, %s)", len(todo_all), len(todo_all) - len(todo), len(todo), model, ollama_url)
    fails, started, n = 0, time.monotonic(), 0
    for p in todo:
        rid, material = p["requirement_id"], H.record_text(p)
        t0 = time.monotonic()
        try:
            raw = ollama_questions(H.build_prompt(p), model, ollama_url)
        except Exception as e:  # noqa: BLE001  (a network or model failure; the record is retried on restart)
            fails += 1
            log.error("record %s failed (%s) [%d consecutive]", rid, e, fails)
            if fails >= AQ.MAX_CONSECUTIVE_FAILURES:
                log.error("stopping after %d consecutive Ollama failures; run again to resume", fails)
                return 2
            continue
        fails = 0
        proposed = H.parse_questions(raw)
        kept, rejected = H.ground_questions(proposed, material)
        append_jsonl(qfile, {"requirement_id": rid, "status": "ok" if proposed else "none","model": model, "proposed": len(proposed),
                             "questions": kept, "rejected": rejected, "seconds": round(time.monotonic() - t0, 2),
                             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        n += 1
        if n % 25 == 0 or n == len(todo):
            rate = (time.monotonic() - started) / n
            log.info("generate: %d/%d this run, %.1fs per record, about %.0f min left", n, len(todo), rate, rate * (len(todo) - n) / 60)
    log.info("generate: finished (%d written this run)", n)
    return 0


# ---------------------------------------------------------------- build

def stage_build(args, out: Path) -> int:
    import ollama
    from fastembed import SparseTextEmbedding
    from qdrant_client import QdrantClient, models

    from core import ask as A
    from pipeline import embed_and_index as EI
    qdrant_url, ollama_url, _ = settings(args)
    client = QdrantClient(url=qdrant_url)
    state = load_state(out)
    if not state.get("collection"):
        state = {"collection": guard_scratch(H.SCRATCH_PREFIX + datetime.now().strftime("%Y%m%d_%H%M%S")), "created": None}
        save_state(out, state)
    name = guard_scratch(state["collection"])
    live = live_payloads(client, with_vectors=True)
    if not live:
        log.error("live collection is empty; nothing to copy")
        return 1
    qrows = {r["requirement_id"]: r for r in read_jsonl(out / "questions.jsonl") if r.get("questions")}
    by_id = {p.payload["requirement_id"]: p for p in live}
    expected_q = sum(len(r["questions"]) for rid, r in qrows.items() if rid in by_id)
    if client.collection_exists(name):
        have = client.get_collection(name).points_count
        if have == len(live) + expected_q:
            log.info("build: scratch %s already complete (%d points)", name, have)
            return 0
    else:
        dim = len(live[0].vector["dense"])
        EI.create_collection(client, name, dim)
        state["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_state(out, state)
    log.info("build: copying %d live points into %s", len(live), name)
    for i in range(0, len(live), 200):
        client.upsert(collection_name=name, points=[models.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in live[i:i + 200]])
    # question points: embedded bare (the question text), same dense model and BM25 as the live index
    flat = [(rid, k, q) for rid, r in qrows.items() if rid in by_id for k, q in enumerate(r["questions"])]
    log.info("build: embedding %d questions from %d records", len(flat), len(qrows))
    oc = ollama.Client(host=ollama_url)
    sparse = SparseTextEmbedding(model_name=A.SPARSE_MODEL)
    for i in range(0, len(flat), 64):
        chunk = flat[i:i + 64]
        texts = [q for _, _, q in chunk]
        dense = EI.embed_batch(texts, oc, A.EMBEDDING_MODEL)
        sp = EI.embed_sparse_batch(texts, sparse)
        pts = []
        for (rid, k, q), d, s in zip(chunk, dense, sp):
            payload = dict(by_id[rid].payload)
            payload.update({"hype_question": q, "hype": True})  # the requirement's own fields stay untouched; the question lives in its own key
            pts.append(models.PointStruct(id=H.question_point_id(rid, k), vector={"dense": d, "sparse": s}, payload=payload))
        client.upsert(collection_name=name, points=pts)
    total = client.get_collection(name).points_count
    log.info("build: scratch %s has %d points (%d live + %d questions)", name, total, len(live), len(flat))
    return 0


# ---------------------------------------------------------------- evaluate

def _cache_wrappers(core_ask, cache_path: Path):
    """Both arms must see the same query rewrite and the same HyDE hypothesis (HyDE samples at 0.3)."""
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    real_rewrite, real_hyde = core_ask.rewrite_query, core_ask.generate_hyde_hypothesis

    def rewrite(question, model, client):
        slot = cache.setdefault(question, {})
        if "rewrite" not in slot:
            slot["rewrite"] = real_rewrite(question, model, client)
        return slot["rewrite"]

    def hyde(question, model, client, *a, **kw):
        slot = cache.setdefault(question, {})
        if "hyde" not in slot:
            slot["hyde"] = real_hyde(question, model, client)
        return slot["hyde"]

    core_ask.rewrite_query, core_ask.generate_hyde_hypothesis = rewrite, hyde
    return cache, (lambda: cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")), (real_rewrite, real_hyde)


def run_arm(arm: str, question: str, collection: str, qdrant_url: str, ollama_url: str, min_score: float) -> dict:
    from core import ask as A
    original = A.COLLECTION_NAME
    A.COLLECTION_NAME = collection
    try:
        # B asks for more points so that collapsing question points to their requirement still leaves TOP_K requirements
        k = TOP_K * (1 + H.MAX_QUESTIONS) if arm == "B" else TOP_K
        res = A.retrieve(question, top_k=k, min_score=min_score, qdrant_url=qdrant_url, ollama_url=ollama_url)
    finally:
        A.COLLECTION_NAME = original
    ranked = H.collapse_to_requirement_id(res["results"], limit=TOP_K)
    return {"ids": [r["requirement_id"] for r in ranked], "via_question": [bool(r.get("hype_question")) for r in ranked],
            "points_returned": res["total"], "ms": res["retrieval_ms"]}


def stage_evaluate(args, out: Path) -> int:
    from qdrant_client import QdrantClient

    from core import ask as A
    from eval.retrieval_eval_harness import compute_metrics
    qdrant_url, ollama_url, min_score = settings(args)
    state = load_state(out)
    if not state.get("collection"):
        log.error("no scratch collection recorded in %s; run build first", out)
        return 1
    scratch = guard_scratch(state["collection"])
    client = QdrantClient(url=qdrant_url)
    live_ids = {p.payload["requirement_id"] for p in live_payloads(client)}
    rule = json.loads(RULE_FILE.read_text(encoding="utf-8"))

    miss = [dict(q, set="miss", relevant=sorted(H.live_labels(q, live_ids))) for q in read_jsonl(MISS_FILE)]
    gold = []
    for q in read_jsonl(GOLD_FILE):
        rel = sorted(H.live_labels(q, live_ids))
        if q.get("shape") != "zero" and rel:
            gold.append(dict(q, set="gold", relevant=rel))
    queries = miss + gold
    log.info("evaluate: %d miss queries, %d gold queries with live labels (of %d)", len(miss), len(gold), len(read_jsonl(GOLD_FILE)))

    rows_path = out / "eval_rows.jsonl"
    rows = {(r["query_id"], r["arm"]): r for r in read_jsonl(rows_path)}
    cache, save_cache, _ = _cache_wrappers(A, out / "query_cache.json")
    t_start = time.monotonic()
    for i, q in enumerate(queries, 1):
        for arm, collection in (("A", LIVE_COLLECTION), ("B", scratch)):
            if (q["query_id"], arm) in rows:
                continue
            try:
                r = run_arm(arm, q["query"], collection, qdrant_url, ollama_url, min_score)
            except Exception as e:  # noqa: BLE001
                log.error("%s arm %s failed: %s", q["query_id"], arm, e)
                continue
            row = {"query_id": q["query_id"], "set": q["set"], "arm": arm, "relevant": q["relevant"], "retrieved": r["ids"],
                   "via_question": r["via_question"], "ms": r["ms"], **compute_metrics(set(q["relevant"]), r["ids"])}
            rows[(q["query_id"], arm)] = row
            append_jsonl(rows_path, row)
        save_cache()
        if i % 5 == 0 or i == len(queries):
            log.info("evaluate: %d/%d queries, %.0fs elapsed", i, len(queries), time.monotonic() - t_start)

    def metric(set_name: str, arm: str, key: str):
        vals = [rows[(q["query_id"], arm)][key] for q in queries
                if q["set"] == set_name and (q["query_id"], arm) in rows and (q["query_id"], "A" if arm == "B" else "B") in rows]
        return H.mean(vals), len(vals)

    a_r5, n_miss = metric("miss", "A", "recall@5")
    b_r5, _ = metric("miss", "B", "recall@5")
    a_p5, n_gold = metric("gold", "A", "precision@5")
    b_p5, _ = metric("gold", "B", "precision@5")
    if None in (a_r5, b_r5, a_p5, b_p5):
        log.error("evaluate: incomplete (some queries failed); rerun to resume")
        return 1
    qfile = read_jsonl(out / "questions.jsonl")
    summary = {
        "scratch_collection": scratch, "records_with_questions": sum(1 for r in qfile if r.get("questions")), "records_generated": len(qfile),
        "questions_kept": sum(len(r.get("questions", [])) for r in qfile), "questions_rejected": sum(len(r.get("rejected", [])) for r in qfile),
        "miss_queries": n_miss, "gold_queries": n_gold,
        "A": {"miss_recall@5": round(a_r5, 4), "gold_precision@5": round(a_p5, 4)},
        "B": {"miss_recall@5": round(b_r5, 4), "gold_precision@5": round(b_p5, 4)},
        "decision": H.decide(a_r5, b_r5, a_p5, b_p5, rule),
    }
    if args.limit:
        summary["WARNING"] = "DRY RUN: questions exist for only a few records; these numbers prove the pipeline works, not the idea"
    (out / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "report.md").write_text(format_report(summary, queries, rows), encoding="utf-8")
    log.info("evaluate: verdict %s; wrote %s", summary["decision"]["verdict"], out / "report.md")
    return 0


def format_report(s: dict, queries: list[dict], rows: dict) -> str:
    d = s["decision"]
    L = ["# HyPE spike result", ""]
    if "WARNING" in s:
        L += [f"**{s['WARNING']}**", ""]
    L += [f"Verdict (pre-registered rule): **{d['verdict']}**", "",
          f"- Miss set ({s['miss_queries']} queries): recall@5 A {s['A']['miss_recall@5']:.3f} -> B {s['B']['miss_recall@5']:.3f} "
          f"({d['miss_recall_at_5_rise_points']:+.1f} points; need at least +15): {'met' if d['rise_requirement_met'] else 'NOT met'}",
          f"- Gold set ({s['gold_queries']} queries with live labels): precision@5 A {s['A']['gold_precision@5']:.3f} -> B {s['B']['gold_precision@5']:.3f} "
          f"(fell {d['gold_precision_at_5_fall_points']:.1f} points; allowed at most 2): {'met' if d['fall_limit_met'] else 'NOT met'}",
          f"- Questions: {s['questions_kept']} kept, {s['questions_rejected']} rejected as ungrounded or bad, for {s['records_with_questions']} of {s['records_generated']} records",
          f"- Scratch collection: {s['scratch_collection']}", "",
          "## Miss set, per query (rank of the target record in the top 20; `q` = reached through a generated question)", "",
          "| query | A rank | B rank | gain via question |", "|---|---|---|---|"]

    def rank(row):
        rel = set(row["relevant"])
        for pos, (rid, vq) in enumerate(zip(row["retrieved"], row["via_question"]), 1):
            if rid in rel:
                return pos, vq
        return None, False

    for q in queries:
        if q["set"] != "miss":
            continue
        ra, _ = rank(rows[(q["query_id"], "A")]) if (q["query_id"], "A") in rows else (None, False)
        rb, vq = rank(rows[(q["query_id"], "B")]) if (q["query_id"], "B") in rows else (None, False)
        L.append(f"| {q['query_id']} | {ra or '-'} | {rb or '-'} | {'q' if vq else ''} |")
    L += ["", "## Gold set, queries whose precision@5 differs", "", "| query | A | B |", "|---|---|---|"]
    for q in queries:
        if q["set"] == "gold" and (q["query_id"], "A") in rows and (q["query_id"], "B") in rows:
            a, b = rows[(q["query_id"], "A")]["precision@5"], rows[(q["query_id"], "B")]["precision@5"]
            if a != b:
                L.append(f"| {q['query_id']} | {a:.2f} | {b:.2f} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- cleanup

def stage_cleanup(args, out: Path) -> int:
    from qdrant_client import QdrantClient
    state = load_state(out)
    name = state.get("collection")
    if not name:
        log.info("cleanup: no scratch collection recorded in %s", out)
        return 0
    guard_scratch(name)
    client = QdrantClient(url=settings(args)[0])
    if client.collection_exists(name):
        client.delete_collection(name)
        log.info("cleanup: deleted %s", name)
    save_state(out, {})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["all", "generate", "build", "evaluate", "cleanup"])
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=0, help="dry run: generate questions for only the first N records")
    ap.add_argument("--model", default="", help="default: services.audit_questions.MODEL")
    ap.add_argument("--qdrant-url", default="")
    ap.add_argument("--ollama-url", default="")
    args = ap.parse_args()
    out = Path(args.out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stages = {"generate": stage_generate, "build": stage_build, "evaluate": stage_evaluate, "cleanup": stage_cleanup}
    order = ["generate", "build", "evaluate"] if args.stage == "all" else [args.stage]
    for name in order:
        code = stages[name](args, out)
        if code:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
