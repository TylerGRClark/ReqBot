#!/usr/bin/env python3
"""WP-45.7b: run the selection resolver over the resolver gold's candidates at one bundle tier, into a scratch ledger.

Measurement only. One candidate per call. For each candidate `menu.py` builds the menu of verbatim spans, `bundle.py` the evidence, the model
answers `{status, actor, parent}` under an enum schema, `selection.assemble` builds the answer in the resolver's shape, and the unchanged
`check_resolution.py` validates it. The ledger has the same fields as `run_resolver.py`'s (so `score_resolver.py` reads it as it is) plus
the menu and the model's raw selection. A candidate whose prompt cannot fit is recorded `untreatable` and never sent; a call that reaches
num_ctx is `window_overrun`; both count as failures in the gates.

The selection half only, unless `--final` is passed for the one scoring after the choice is frozen (the plan's rule).

  python3 eval/spike_results/wp_45_7/run_selection.py --tier R1 --model qwen2.5:14b --run-label v3_sel_r1_14b \\
      --ollama-url http://192.168.90.100:11434
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
import menu as M  # noqa: E402
import ollama_run as OR  # noqa: E402
import run_resolver as RR  # noqa: E402
import selection as S  # noqa: E402

GOLD = _HERE / "outputs/resolver_gold.json"
TIERS = ("R1", "R2")  # R0 supplies no context and is not part of this experiment (plan section 3)


def gold_candidates(half):
    """{candidate_id, document, chunk_id, quote} for every audit and card candidate of one half of the frozen resolver gold."""
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["gold"]
    return [{k: g[k] for k in ("candidate_id", "document", "chunk_id", "quote")} for g in gold if g["half"] == half]


def run_candidates(candidates, docs, *, tier, model, digest, run_label, ledger, ollama_url, num_ctx=OR.NUM_CTX, num_predict=200,
                   temperature=0.1, timeout=300, dry_run=False, log=print):
    phash = S.prompt_hash()
    fixed = S.fixed_tokens()
    calls = 0
    for cand in candidates:
        chunks, step = docs[cand["document"]]
        menu = M.build_menu(cand["quote"], cand["chunk_id"], chunks, tier, step_c_by_chunk=step)
        menu_tokens = B.estimate_tokens(len(S.render_menu(menu)))
        bundle = B.build(cand["quote"], cand["chunk_id"], chunks, tier, step_c_by_chunk=step, fixed_tokens=fixed + menu_tokens, num_ctx=num_ctx)
        key = OR.resolver_key(cand["document"], cand["candidate_id"], cand["chunk_id"], OR.sha(cand["quote"]),
                              bundle.bundle_hash() + S.menu_hash(menu), phash, digest, run_label)
        if ledger.done(key):
            continue
        prompt = S.render_prompt(bundle, menu)
        rec = {
            "entry_id": key, "kind": "selection", "run_label": run_label, "tier": tier, "model": model, "digest": digest,
            "candidate_id": cand["candidate_id"], "document": cand["document"], "chunk_id": cand["chunk_id"],
            "quote": cand["quote"], "prompt_hash": phash, "bundle": bundle.to_dict(), "menu": menu, "prompt_chars": len(prompt),
            "estimated_prompt_tokens": B.estimate_tokens(len(prompt)), "num_ctx": num_ctx, "num_predict": num_predict,
            "temperature": temperature, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if bundle.untreatable or rec["estimated_prompt_tokens"] > B.prompt_cap(num_ctx):
            rec.update(status="untreatable", raw_response="", meta={}, selection=None, answer=None, issues=[])
            ledger.append(rec)
            continue
        if dry_run:
            continue
        try:
            text, meta = OR.generate(prompt, model, ollama_url, num_ctx=num_ctx, num_predict=num_predict, temperature=temperature,
                                     schema=S.json_schema(menu), timeout=timeout)
        except Exception as e:  # noqa: BLE001
            rec.update(status="failed", raw_response=f"ERROR: {e}", meta={}, selection=None, answer=None, issues=[])
            ledger.append(rec)
            calls += 1
            continue
        calls += 1
        status = OR.classify(meta, num_ctx)
        selection = answer = None
        issues = []
        try:
            selection = json.loads(text)
            answer, spans = S.assemble(selection, menu, bundle.to_dict()["spans"], cand["quote"])
            issues = [{"code": i.code, "field": i.field, "severity": i.severity, "message": i.message} for i in C.check(answer, spans)]
        except (ValueError, TypeError, KeyError, AttributeError):
            answer, status = None, "failed"  # unparseable, or a choice the schema should have made impossible
        rec.update(status=status, raw_response=text, meta=meta, selection=selection, answer=answer, issues=issues)
        ledger.append(rec)
        errors = [i for i in issues if i["severity"] == "error"]
        log(f"{cand['candidate_id']}: {status}, {meta.get('prompt_eval_count')} prompt tokens, {meta.get('wall_seconds')}s, "
            f"selection={selection}, menu {len(menu)}, {len(errors)} error(s) {sorted({i['code'] for i in errors})}")
    return calls


def summarize(ledger):
    summary = RR.summarize(ledger)
    recs = list(ledger.records.values())
    summary["fixed_prompt_estimated_tokens"] = S.fixed_tokens()
    summary["mean_menu_size"] = round(sum(len(r.get("menu") or []) for r in recs) / len(recs), 2) if recs else None
    summary["answers_with_a_selection"] = sum(1 for r in recs if r.get("selection") is not None)
    return summary


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", choices=TIERS, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-label", required=True)
    ap.add_argument("--half", choices=("selection", "evaluation"), default="selection")
    ap.add_argument("--final", action="store_true", help="allow the evaluation half (only after the choice is frozen)")
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--scratch", default=str(OR.DEFAULT_SCRATCH))
    ap.add_argument("--num-ctx", type=RR._positive_int, default=OR.NUM_CTX)
    ap.add_argument("--num-predict", type=RR._positive_int, default=200)
    ap.add_argument("--temperature", type=RR._non_negative_float, default=0.1)
    ap.add_argument("--timeout", type=RR._positive_int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="build the menus, bundles and prompts; call nothing")
    args = ap.parse_args()
    if args.half == "evaluation" and not args.final:
        sys.exit("the evaluation half is read once, after the choice is frozen: pass --final")
    candidates = gold_candidates(args.half)
    docs = RR.load_documents(sorted({c["document"] for c in candidates}))
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
    summary.update(run_label=args.run_label, tier=args.tier, model=args.model, digest=digest, prompt_hash=S.prompt_hash(),
                   half=args.half, calls_made=calls, wall_seconds=round(time.time() - started, 1))
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
