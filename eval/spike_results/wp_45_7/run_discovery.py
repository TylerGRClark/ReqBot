#!/usr/bin/env python3
"""WP-45.7: run a discovery arm (D0 production prompt, D1 inclusive prompt) over a chunk set, into a scratch ledger.

Measurement only. Nothing is written to ~/documents/processed, to Qdrant or to the repo. Each run label (a repeat, a model, an
arm) has its own directory and its own ledger, so no run can reuse another's answer. A chunk whose estimated prompt exceeds the
prompt cap is recorded `untreatable` and never sent; a call whose prompt plus answer reaches num_ctx is recorded
`window_overrun` (kept in every denominator as a failure, never excluded). Resume skips records that finished; `failed` ones
are redone.

  python3 eval/spike_results/wp_45_7/run_discovery.py --arm D1 --set dev --model llama3.1:8b-instruct-q4_K_M \\
      --run-label d1_8b_dev_r1 --ollama-url http://192.168.90.100:11434 [--limit 10] [--dry-run]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bundle as B  # noqa: E402
import chunk_sets as CS  # noqa: E402
import discovery_prompts as DP  # noqa: E402
import ollama_run as OR  # noqa: E402
from pipeline import llm_extract_requirements as S  # noqa: E402


def _positive_int(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be a positive integer")
    return n


def _non_negative_float(value):
    x = float(value)
    if x < 0:
        raise argparse.ArgumentTypeError(f"{value} must be a non-negative number")
    return x


def run_chunks(chunks, *, arm, model, digest, run_label, ledger, ollama_url, num_ctx=OR.NUM_CTX, num_predict=4096,
               temperature=0.1, timeout=300, dry_run=False, log=print):
    """Process [(document, chunk)] into the ledger; returns the number of calls made."""
    phash = DP.prompt_hash(arm)
    calls = 0
    for document, chunk in chunks:
        key = OR.discovery_key(document, chunk["chunk_id"], phash, digest, run_label)
        if ledger.done(key):
            continue
        prompt = DP.render(arm, chunk["text"])
        est = B.estimate_tokens(len(prompt))
        rec = {
            "entry_id": key, "kind": "discovery", "run_label": run_label, "arm": arm, "model": model, "digest": digest,
            "document": document, "chunk_id": chunk["chunk_id"], "prompt_hash": phash, "prompt_chars": len(prompt),
            "estimated_prompt_tokens": est, "num_ctx": num_ctx, "num_predict": num_predict, "temperature": temperature,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if est > B.prompt_cap(num_ctx):  # too long for the selected window: a failure for this arm, never an exclusion
            rec.update(status="untreatable", raw_response="", meta={})
            ledger.append(rec)
            continue
        if dry_run:
            continue
        try:
            text, meta = OR.generate(prompt, model, ollama_url, num_ctx=num_ctx, num_predict=num_predict,
                                     temperature=temperature, schema=DP.SCHEMA, timeout=timeout)
        except Exception as e:  # noqa: BLE001  (a request error is a recorded failure, redone on resume)
            rec.update(status="failed", raw_response=f"ERROR: {e}", meta={})
            ledger.append(rec)
            calls += 1
            continue
        calls += 1
        status = OR.classify(meta, num_ctx)
        parsed, recovered = S.extract_json_array(text)
        if parsed is None:
            status = "failed"
        elif recovered and status == "complete":
            status = "truncated"
        rec.update(status=status, raw_response=text, meta=meta)
        ledger.append(rec)
        log(f"{document} chunk {chunk['chunk_id']}: {status}, {meta.get('prompt_eval_count')} prompt tokens, "
            f"{meta.get('eval_count')} answer tokens, {meta.get('wall_seconds')}s")
    return calls


def extracted_records(ledger):
    """Step C-shaped records from a discovery ledger, validated by the production validator: [(document, record)].

    Only `complete` and `truncated` answers are exported. A `window_overrun` call may have lost the start of its prompt (the
    instructions), so its answer is not trusted: its ledger record stays, and the chunk counts as a miss in every denominator, but
    it contributes no records, so scoring cannot credit candidates from an invalid call."""
    out = []
    for rec in sorted(ledger.records.values(), key=lambda r: (r["document"], r["chunk_id"])):
        if rec["status"] not in ("complete", "truncated"):
            continue
        parsed, _ = S.extract_json_array(rec["raw_response"])
        for n, item in enumerate(parsed or [], 1):
            clean = S.validate_requirement(item)
            if clean:
                clean.update(chunk_id=rec["chunk_id"], requirement_id=f"R-{rec['chunk_id']}-{n}")
                if rec["status"] == "truncated":
                    clean["recovered_truncated"] = True
                out.append((rec["document"], clean))
    return out


def write_extracted(ledger, out_dir):
    """One `<document>_extracted_requirements.jsonl` per document in Step C's format, so Step D can read it."""
    by_doc = {}
    for document, record in extracted_records(ledger):
        by_doc.setdefault(document, []).append(record)
    paths = []
    for document, records in by_doc.items():
        path = Path(out_dir) / f"{document}_extracted_requirements.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        paths.append(path)
    return paths


def prompt_sizes(chunks, arm, num_ctx=OR.NUM_CTX):
    """Estimated prompt tokens over a chunk set (the dry-run report): mean, p95, max and how many exceed the cap that the run
    itself uses for the selected context window."""
    est = sorted(B.estimate_tokens(len(DP.render(arm, c["text"]))) for _, c in chunks)
    cap = B.prompt_cap(num_ctx)
    return {
        "mean": round(sum(est) / len(est)), "p95": est[int(0.95 * len(est))], "max": est[-1],
        "over_prompt_cap": sum(1 for e in est if e > cap), "cap": cap, "num_ctx": num_ctx,
    }


def summarize(ledger):
    recs = list(ledger.records.values())
    counts = {}
    for r in recs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    metas = [r["meta"] for r in recs if r.get("meta")]

    def mean(key):
        vals = [m[key] for m in metas if m.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    est = [r["estimated_prompt_tokens"] for r in recs if r.get("meta")]
    real = [r["meta"]["prompt_eval_count"] for r in recs if r.get("meta") and r["meta"].get("prompt_eval_count")]
    return {
        "chunks": len(recs), "status": counts, "records": len(extracted_records(ledger)),
        "mean_prompt_tokens": mean("prompt_eval_count"), "mean_answer_tokens": mean("eval_count"),
        "mean_wall_seconds": mean("wall_seconds"),
        "estimate_over_real": round(sum(est) / sum(real), 2) if real and est and len(est) == len(real) else None,
    }


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", choices=DP.ARMS, required=True)
    ap.add_argument("--set", choices=CS.SETS, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-label", required=True, help="unique per arm, model and repeat; its directory holds the ledger")
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--scratch", default=str(OR.DEFAULT_SCRATCH))
    ap.add_argument("--num-ctx", type=_positive_int, default=OR.NUM_CTX)
    ap.add_argument("--num-predict", type=_positive_int, default=4096)
    ap.add_argument("--temperature", type=_non_negative_float, default=0.1)
    ap.add_argument("--timeout", type=_positive_int, default=300)
    ap.add_argument("--limit", type=_positive_int, default=None, help="pilot: this many chunks, spread evenly over the set")
    ap.add_argument("--dry-run", action="store_true", help="build the prompts and report sizes; call nothing")
    args = ap.parse_args()

    chunks = CS.spread(CS.chunk_set(args.set), args.limit)
    digest = "dry-run" if args.dry_run else OR.model_digest(args.ollama_url, args.model)
    out_dir = Path(args.scratch) / args.run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = OR.Ledger(out_dir / "discovery.jsonl")
    started = time.time()
    calls = run_chunks(
        chunks, arm=args.arm, model=args.model, digest=digest, run_label=args.run_label, ledger=ledger,
        ollama_url=args.ollama_url, num_ctx=args.num_ctx, num_predict=args.num_predict, temperature=args.temperature,
        timeout=args.timeout, dry_run=args.dry_run,
    )
    if not args.dry_run:
        write_extracted(ledger, out_dir)
    summary = summarize(ledger)
    if args.dry_run:
        summary["estimated_prompt_tokens"] = prompt_sizes(chunks, args.arm, args.num_ctx)
    summary.update(run_label=args.run_label, arm=args.arm, set=args.set, model=args.model, digest=digest,
                   prompt_hash=DP.prompt_hash(args.arm), chunks_selected=len(chunks), calls_made=calls,
                   wall_seconds=round(time.time() - started, 1))
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
