"""WP-45.7: how big are the evidence bundles on the real pinned corpus? (offline; no LLM, no Qdrant)

Builds the R0, R1 and R2 bundles for every production Step C record of the 13 pinned documents and reports sizes, how often
the window budget forced a cut, how often a bundle was untreatable, how many records got a governing-clause candidate, and
how many cross-references were resolved or not found. A smoke measurement of the builder, not an evaluation of the resolver.

  python3 eval/spike_results/wp_45_7/bundle_stats.py [--fixed-tokens 2000]
"""

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _inputs  # noqa: E402
import bundle as B  # noqa: E402


def _positive_int(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fixed-tokens", type=_positive_int, default=2000, help="estimated tokens of the fixed prompt text")
    args = ap.parse_args()
    inputs = _inputs.corpus_inputs("chunks", "extracted")
    stats = {t: collections.defaultdict(list) for t in B.TIERS}
    n = 0
    for doc, paths in inputs.items():
        chunks = {}
        for line in Path(paths["chunks"]).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            chunks[rec["chunk_id"]] = rec
        step = {}
        for line in Path(paths["extracted"]).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            step.setdefault(rec["chunk_id"], []).append(rec)
        for chunk_id, records in step.items():
            for rec in records:
                n += 1
                for tier in B.TIERS:
                    b = B.build(rec["source_quote"], chunk_id, chunks, tier, step_c_by_chunk=step, fixed_tokens=args.fixed_tokens)
                    s = stats[tier]
                    s["chars"].append(b.chars())
                    s["truncated"].append(bool(b.truncated))
                    s["untreatable"].append(b.untreatable)
                    s["stem"].append(any(x.kind == "stem" for x in b.spans))
                    s["unresolved"].append(len(b.unresolved_references))
                    s["reference_spans"].append(sum(1 for x in b.spans if x.kind == "reference"))
    print(f"candidates {n}; fixed tokens {args.fixed_tokens}; budget {B.prompt_budget_chars(args.fixed_tokens)} characters")
    for tier in B.TIERS:
        s = stats[tier]
        chars = sorted(s["chars"])
        print(
            f"{tier}: mean {round(statistics.mean(chars))} chars, p95 {chars[int(0.95 * len(chars))]}, max {chars[-1]}; "
            f"truncated {sum(s['truncated'])}; untreatable {sum(s['untreatable'])}; "
            f"with a governing-clause candidate {sum(s['stem'])} ({100 * sum(s['stem']) / n:.1f}%); "
            f"records with a reference not found {sum(1 for v in s['unresolved'] if v)}; reference spans added {sum(s['reference_spans'])}"
        )


if __name__ == "__main__":
    main()
