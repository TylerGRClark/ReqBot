#!/usr/bin/env python3
"""WP-45.7d Stage C: the one-shot run of the frozen configuration on the evaluation half, with every check made BEFORE any model call.

The evaluation half can be read once. `run_selection.py --half evaluation --final` would let a wrong tier, model or design consume it, and
only the scoring would notice. This command takes the tier, model, design and runner parameters from the frozen Stage B choice (there are no
options to change them) and refuses, before the evaluation candidates are even loaded, unless:

  - the registry's committed Stage B choice report says a configuration passed every gate (a stopped protocol has no Stage C);
  - every file in the committed frozen-code manifest (the runner's import closure, the gold and the input pins) is byte-identical to the commit
    the Stage B runs used;
  - the model file Ollama reports for the frozen model has the frozen digest;
  - no run with this label has already been completed in the scratch directory (the half is one-shot; a crashed run resumes, a finished one does not
    rerun), and every record already in an unfinished ledger was written by exactly this configuration (the resume key ignores the temperature and the
    answer limit, so a ledger left by a differently-configured run would otherwise be silently continued).

  python3 eval/spike_results/wp_45_7/run_stage_c.py --ollama-url http://192.168.90.100:11434          # runs the half
  python3 eval/spike_results/wp_45_7/run_stage_c.py --ollama-url ... --preflight-only                  # checks only; reads no candidate

Then score the ledger once: `score_resolver.py --verdict r2_14b=<dir> --registry v5` (README step 21).
"""

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import kind_selection as K  # noqa: E402
import ollama_run as OR  # noqa: E402
import run_resolver as RR  # noqa: E402
import run_selection as RS  # noqa: E402
import score_resolver as SR  # noqa: E402

DESIGNS = {"v5": K}  # the registries that have a Stage C, and the design each one is for


def check_partial_ledger(path, frozen, label):
    """An unfinished ledger may be resumed only if every record in it was written by the frozen configuration: same label, tier, model, model file,
    prompt and runner parameters. Raises SystemExit naming the first record that is not."""
    want = {"run_label": label, "kind": "selection", "tier": frozen["tier"], "model": frozen["model"], "digest": frozen["digest"],
            "prompt_hash": K.prompt_hash(), "temperature": float(frozen["temperatures"][0]), "num_ctx": int(frozen["num_ctxs"][0]),
            "num_predict": int(frozen["num_predicts"][0])}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            raise SystemExit(f"{path} line {n} is not JSON: an unfinished ledger that cannot be validated is not resumed") from None
        differ = {k: rec.get(k) for k, v in want.items() if rec.get(k) != v}
        if differ:
            raise SystemExit(f"{path} line {n} (candidate {rec.get('candidate_id')}) was not written by the frozen configuration: {differ}; "
                             "move the ledger away before running, and do not resume it")


def preflight(registry, ollama_url, *, digest_fn=OR.model_digest, outputs=None, root=None, scratch=None):
    """Every check, and no model call except the digest lookup. Returns (frozen choice, run label, output directory). Raises SystemExit."""
    if registry not in DESIGNS:
        raise SystemExit(f"Stage C exists only for {sorted(DESIGNS)}, not {registry}")
    frozen = SR.frozen_choice(registry, outputs)
    SR.check_frozen_code(registry, outputs, root)
    have = digest_fn(ollama_url, frozen["model"])
    if have != frozen["digest"]:
        raise SystemExit(f"the model file differs from the frozen one: {frozen['model']} is {have!r} on this server, the frozen run used {frozen['digest']!r}")
    label = f"{registry}_eval_{frozen['name']}"
    out_dir = Path(scratch or OR.DEFAULT_SCRATCH) / label
    if (out_dir / "run_summary.json").exists():
        raise SystemExit(f"{label} has already been run ({out_dir}): the evaluation half is one-shot, score that ledger instead of running again")
    if (out_dir / "resolver.jsonl").exists():
        check_partial_ledger(out_dir / "resolver.jsonl", frozen, label)
    return frozen, label, out_dir


def run_frozen(registry, frozen, candidates, docs, label, out_dir, ollama_url, log=print):
    """Run the frozen configuration over `candidates`; the parameters come from the frozen run, not from the caller."""
    design = DESIGNS[registry]
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = OR.Ledger(out_dir / "resolver.jsonl")
    started = time.time()
    calls = RS.run_candidates(
        candidates, docs, tier=frozen["tier"], model=frozen["model"], digest=frozen["digest"], run_label=label, ledger=ledger,
        ollama_url=ollama_url, num_ctx=int(frozen["num_ctxs"][0]), num_predict=int(frozen["num_predicts"][0]),
        temperature=float(frozen["temperatures"][0]), log=log, design=design)
    summary = RS.summarize(ledger, design)
    summary.update(run_label=label, tier=frozen["tier"], model=frozen["model"], digest=frozen["digest"], prompt_hash=design.prompt_hash(),
                   half="evaluation", design="kind", calls_made=calls, wall_seconds=round(time.time() - started, 1))
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", choices=sorted(DESIGNS), default="v5")
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--scratch", default=str(OR.DEFAULT_SCRATCH))
    ap.add_argument("--preflight-only", action="store_true", help="run every check and stop; no evaluation candidate is loaded")
    args = ap.parse_args()
    frozen, label, out_dir = preflight(args.registry, args.ollama_url, scratch=args.scratch)
    print(f"preflight passed: {frozen['name']} ({frozen['tier']}, {frozen['model']}, digest {frozen['digest'][:12]}), run label {label}")
    if args.preflight_only:
        return
    candidates = RS.gold_candidates("evaluation")
    docs = RR.load_documents(sorted({c["document"] for c in candidates}))
    summary = run_frozen(args.registry, frozen, candidates, docs, label, out_dir, args.ollama_url)
    print(json.dumps(summary, indent=1))
    print(f"\nnext, once: python3 eval/spike_results/wp_45_7/score_resolver.py --verdict {frozen['name']}={out_dir} --registry {args.registry}")


if __name__ == "__main__":
    main()
