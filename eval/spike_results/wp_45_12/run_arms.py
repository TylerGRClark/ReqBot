#!/usr/bin/env python3
"""WP-45.12: run the arms of docs/PHASE45_WP4512_PLAN.md into ~/reqbot-work/scratch/wp45_12_scratch (scratch only; nothing touches the pipeline, Qdrant or ~/documents/processed).

  python3 run_arms.py --arm P1 --set dev --run-label p1_dev_r1          # per-paragraph arm on the 38 labeled development chunks
  python3 run_arms.py --arm D0 --set afi17-203 --run-label d0_afi17-203 # chunk-level arms on a whole AFI (D0, D1) or the per-paragraph arm (P1)
"""
import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_7"):
    sys.path.insert(0, str(_p))

import chunk_sets as CS  # noqa: E402
import discovery_prompts as DP  # noqa: E402
import ollama_run as OR  # noqa: E402
import p1 as P  # noqa: E402
import run_discovery as RD  # noqa: E402

from core import config  # noqa: E402

SCRATCH = Path.home() / "reqbot-work/scratch/wp45_12_scratch"


def main():
    cfg = config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", choices=("D0", "D1", "P1"), required=True)
    ap.add_argument("--set", required=True, help="dev, or an AFI key such as afi17-203")
    ap.add_argument("--run-label", required=True)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    chunks = CS.chunk_set("dev") if args.set == "dev" else P.afi_chunks(args.set)
    if args.limit:
        chunks = chunks[: args.limit]
    digest = OR.model_digest(args.ollama_url, P.MODEL)
    ledger = OR.Ledger(SCRATCH / args.run_label / "discovery.jsonl")
    if args.arm == "P1":
        calls = P.run_chunks(chunks, model=P.MODEL, digest=digest, run_label=args.run_label, ledger=ledger, ollama_url=args.ollama_url)
    else:
        calls = RD.run_chunks(chunks, arm=args.arm, model=P.MODEL, digest=digest, run_label=args.run_label, ledger=ledger, ollama_url=args.ollama_url)
    print(f"{args.arm} on {args.set}: {len(chunks)} chunks, {calls} calls, ledger {SCRATCH / args.run_label / 'discovery.jsonl'}")


if __name__ == "__main__":
    main()
