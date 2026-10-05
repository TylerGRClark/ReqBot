#!/usr/bin/env python3
"""WP-45.7: run the resolver over candidate quotes at one bundle tier, into a scratch ledger.

Measurement only. One candidate per call. For each candidate the bundle builder assembles the evidence (tier R0, R1 or R2), the
prompt is the fixed resolver prompt plus that bundle, and the answer is validated by `check_resolution.py`; the ledger keeps the
bundle, the parsed answer, every issue and Ollama's own token counts. A candidate whose bundle cannot fit is recorded
`untreatable` and never sent (the pre-call check); a call whose prompt plus answer reaches num_ctx is `window_overrun`.

Candidates are a JSONL file of {"candidate_id", "document", "chunk_id", "quote"}. `--pilot-from-corpus N` instead takes N
production Step C records of the pinned corpus, spread evenly (a schema and prompt smoke test, not an evaluation).

  python3 eval/spike_results/wp_45_7/run_resolver.py --tier R1 --model llama3.1:8b-instruct-q4_K_M --run-label pilot_r1_8b \\
      --ollama-url http://192.168.90.100:11434 --pilot-from-corpus 10
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bundle as B  # noqa: E402
import check_resolution as C  # noqa: E402
import ollama_run as OR  # noqa: E402
import resolver as R  # noqa: E402


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


def load_documents(documents):
    """{document: (chunks_by_id, step_c_by_chunk)}. Pinned documents come from the WP-44 manifest files (production Step C
    records feed the same-chunk stem finder); a catalog document (CNSSI 1253) has only its pinned chunk file, so its Step C map
    is empty and the finder simply has nothing to offer."""
    import _inputs
    import chunk_sets as CS

    pinned = _inputs.corpus_inputs("chunks", "extracted")
    out = {}
    for document in documents:
        step = {}
        if document in pinned:
            chunks = {c["chunk_id"]: c for c in CS.load_document_chunks(document)[document]}
            for line in Path(pinned[document]["extracted"]).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    step.setdefault(rec["chunk_id"], []).append(rec)
        elif document in CS.H.CATALOG_DOCUMENTS:
            chunks = {c["chunk_id"]: c for c in CS.load_document_chunks(document)[document]}
        else:
            raise SystemExit(f"{document} is neither a pinned document nor a pinned catalog document")
        out[document] = (chunks, step)
    return out


def pilot_candidates(n):
    """n production Step C records of the pinned corpus, spread evenly over (document, chunk, record) order."""
    import _inputs

    inputs = _inputs.corpus_inputs("extracted")
    pool = []
    for document in sorted(inputs):
        for line in Path(inputs[document]["extracted"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                pool.append({"candidate_id": f"{document}:{rec['requirement_id']}", "document": document,
                             "chunk_id": rec["chunk_id"], "quote": rec["source_quote"]})
    step = len(pool) / n
    return [pool[int(i * step)] for i in range(n)] if n < len(pool) else pool


def run_candidates(candidates, docs, *, tier, model, digest, run_label, ledger, ollama_url, num_ctx=OR.NUM_CTX,
                   num_predict=900, temperature=0.1, timeout=300, dry_run=False, log=print):
    phash = R.prompt_hash()
    fixed = R.fixed_tokens()
    calls = 0
    for cand in candidates:
        chunks, step = docs[cand["document"]]
        bundle = B.build(cand["quote"], cand["chunk_id"], chunks, tier, step_c_by_chunk=step, fixed_tokens=fixed, num_ctx=num_ctx)
        key = OR.resolver_key(cand["document"], cand["candidate_id"], cand["chunk_id"], OR.sha(cand["quote"]),
                              bundle.bundle_hash(), phash, digest, run_label)
        if ledger.done(key):
            continue
        prompt = R.render_prompt(bundle)
        rec = {
            "key": key, "kind": "resolver", "run_label": run_label, "tier": tier, "model": model, "digest": digest,
            "candidate_id": cand["candidate_id"], "document": cand["document"], "chunk_id": cand["chunk_id"],
            "quote": cand["quote"], "prompt_hash": phash, "bundle": bundle.to_dict(), "prompt_chars": len(prompt),
            "estimated_prompt_tokens": B.estimate_tokens(len(prompt)), "num_ctx": num_ctx, "num_predict": num_predict,
            "temperature": temperature, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if bundle.untreatable or rec["estimated_prompt_tokens"] > B.prompt_cap(num_ctx):  # the full prompt, not a stub
            rec.update(status="untreatable", raw_response="", meta={}, answer=None, issues=[])
            ledger.append(rec)
            continue
        if dry_run:
            continue
        try:
            text, meta = OR.generate(prompt, model, ollama_url, num_ctx=num_ctx, num_predict=num_predict,
                                     temperature=temperature, schema=R.json_schema(), timeout=timeout)
        except Exception as e:  # noqa: BLE001
            rec.update(status="failed", raw_response=f"ERROR: {e}", meta={}, answer=None, issues=[])
            ledger.append(rec)
            calls += 1
            continue
        calls += 1
        status = OR.classify(meta, num_ctx)
        try:
            answer = json.loads(text)
        except ValueError:
            answer, status = None, "failed"
        issues = []
        if answer is not None:
            issues = [{"code": i.code, "field": i.field, "severity": i.severity, "message": i.message}
                      for i in C.check(answer, bundle.to_dict()["spans"])]
        rec.update(status=status, raw_response=text, meta=meta, answer=answer, issues=issues)
        ledger.append(rec)
        errors = [i for i in issues if i["severity"] == "error"]
        log(f"{cand['candidate_id']}: {status}, {meta.get('prompt_eval_count')} prompt tokens, {meta.get('eval_count')} answer "
            f"tokens, {meta.get('wall_seconds')}s, status={(answer or {}).get('status', {}).get('value')}, "
            f"{len(errors)} error(s) {sorted({i['code'] for i in errors})}")
    return calls


def summarize(ledger):
    recs = list(ledger.records.values())
    counts, codes = {}, {}
    shape_ok = 0
    valid = [r for r in recs if r["status"] == "complete"]  # an overrun, a truncation or a failure is a failed resolution
    for r in recs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for r in valid:
        if r.get("answer") is not None:
            if not any(i["code"] == "shape" for i in r["issues"]):
                shape_ok += 1
            for i in r["issues"]:
                if i["severity"] == "error":
                    codes[i["code"]] = codes.get(i["code"], 0) + 1
    sent = [r for r in recs if r.get("meta")]
    real = [r["meta"]["prompt_eval_count"] for r in sent if r["meta"].get("prompt_eval_count")]
    est = [r["estimated_prompt_tokens"] for r in sent if r["meta"].get("prompt_eval_count")]

    def mean(key):
        vals = [r["meta"][key] for r in sent if r["meta"].get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "candidates": len(recs), "status": counts, "valid_answers": len(valid),
        "parsed": sum(1 for r in valid if r.get("answer") is not None),
        "shape_conformant": shape_ok, "error_codes": dict(sorted(codes.items())),
        "answers_with_no_error": sum(1 for r in valid if r.get("answer") is not None and not any(i["severity"] == "error" for i in r["issues"])),
        "mean_prompt_tokens": mean("prompt_eval_count"), "mean_answer_tokens": mean("eval_count"),
        "mean_wall_seconds": mean("wall_seconds"),
        "estimate_over_real": round(sum(est) / sum(real), 2) if real and est else None,
        "fixed_prompt_estimated_tokens": R.fixed_tokens(),
    }


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", choices=B.TIERS, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-label", required=True)
    ap.add_argument("--candidates", help="JSONL of {candidate_id, document, chunk_id, quote}")
    ap.add_argument("--pilot-from-corpus", type=_positive_int, default=None, metavar="N")
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--scratch", default=str(OR.DEFAULT_SCRATCH))
    ap.add_argument("--num-ctx", type=_positive_int, default=OR.NUM_CTX)
    ap.add_argument("--num-predict", type=_positive_int, default=900)
    ap.add_argument("--temperature", type=_non_negative_float, default=0.1)
    ap.add_argument("--timeout", type=_positive_int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="build the bundles and prompts; call nothing")
    args = ap.parse_args()
    if bool(args.candidates) == bool(args.pilot_from_corpus):
        sys.exit("give exactly one of --candidates and --pilot-from-corpus")
    if args.candidates:
        candidates = [json.loads(x) for x in Path(args.candidates).read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        candidates = pilot_candidates(args.pilot_from_corpus)
    docs = load_documents(sorted({c["document"] for c in candidates}))
    digest = "dry-run" if args.dry_run else OR.model_digest(args.ollama_url, args.model)
    out_dir = Path(args.scratch) / args.run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = OR.Ledger(out_dir / "resolver.jsonl")
    started = time.time()
    calls = run_candidates(
        candidates, docs, tier=args.tier, model=args.model, digest=digest, run_label=args.run_label, ledger=ledger,
        ollama_url=args.ollama_url, num_ctx=args.num_ctx, num_predict=args.num_predict, temperature=args.temperature,
        timeout=args.timeout, dry_run=args.dry_run,
    )
    summary = summarize(ledger)
    summary.update(run_label=args.run_label, tier=args.tier, model=args.model, digest=digest, prompt_hash=R.prompt_hash(),
                   calls_made=calls, wall_seconds=round(time.time() - started, 1))
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
