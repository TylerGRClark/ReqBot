#!/usr/bin/env python3
"""WP-45.7b S1: the candidate ceiling of the menu generator, offline (no model).

For every attachment-scored audit record of one half of the resolver gold, build the menu at a tier and ask whether a model that
chose perfectly from it could be marked *right* by the same `attachment()` rule the resolver is scored with: a complete record is
right when nothing is attached, a record that needs a lead-in is right when some menu span names the adjudicated lead-in text
(`overlaps`, 0.8 of its distinctive words inside it). The ceiling is that share; the mean menu size is reported with it.

Only the selection half is read while the generator is being developed (the plan's rule); `--half evaluation` is refused unless
`--final` is passed, which is for the one scoring after the choice is frozen.

  python3 eval/spike_results/wp_45_7/measure_menu.py --tier R1 --out eval/spike_results/wp_45_7/outputs/menu_ceiling_r1.json
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import menu as M  # noqa: E402
import score_resolver as S  # noqa: E402

GOLD = _HERE / "outputs/resolver_gold.json"
CEILING_GATE = 0.75
MEAN_MENU_GATE = 8


def reachable(gold, entries):
    """Could a perfect choice from `entries` be marked right for this audit record?"""
    if gold["standalone"] == "complete":
        return True  # choosing nothing is right
    return any(S.overlaps(e["text"], gold["lead_in_text"]) for e in entries)


def measure(golds, docs, tier):
    rows = []
    for g in golds:
        chunks, step = docs[g["document"]]
        entries = M.build_menu(g["quote"], g["chunk_id"], chunks, tier, step_c_by_chunk=step)
        rows.append({
            "candidate_id": g["candidate_id"], "standalone": g["standalone"], "lead_in_location": g["lead_in_location"],
            "menu_size": len(entries), "reachable": reachable(g, entries), "menu": entries, "lead_in_text": g["lead_in_text"],
        })
    n = len(rows)
    needs = [r for r in rows if r["standalone"] == "needs_lead_in"]
    by_location = {}
    for r in needs:
        by_location.setdefault(r["lead_in_location"], []).append(r["reachable"])
    return {
        "tier": tier, "scored": n, "generator_sha256": hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest()[:16],
        "ceiling": sum(r["reachable"] for r in rows) / n if n else 0.0,
        "ceiling_needs_lead_in": sum(r["reachable"] for r in needs) / len(needs) if needs else 0.0,
        "needs_lead_in": len(needs),
        "by_lead_in_location": {k: {"n": len(v), "reachable": sum(v)} for k, v in sorted(by_location.items())},
        "mean_menu_size": sum(r["menu_size"] for r in rows) / n if n else 0.0,
        "max_menu_size": max((r["menu_size"] for r in rows), default=0),
        "passes_s1": bool(n) and sum(r["reachable"] for r in rows) / n >= CEILING_GATE
        and sum(r["menu_size"] for r in rows) / n <= MEAN_MENU_GATE,
        "misses": [r for r in rows if not r["reachable"]],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", choices=("R1", "R2"), required=True)
    ap.add_argument("--half", choices=("selection", "evaluation"), default="selection")
    ap.add_argument("--final", action="store_true", help="allow the evaluation half (only after the choice is frozen)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.half == "evaluation" and not args.final:
        raise SystemExit("the evaluation half is read once, after the choice is frozen: pass --final")
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["gold"]
    golds = [g for g in gold if g["set"] == "audit" and g["half"] == args.half and S.attachment_scored(g)]
    import run_resolver as RR

    docs = RR.load_documents(sorted({g["document"] for g in golds}))
    result = measure(golds, docs, args.tier)
    print(f"{args.tier} {args.half}: ceiling {result['ceiling']:.1%} of {result['scored']} "
          f"(needs-lead-in only {result['ceiling_needs_lead_in']:.1%} of {result['needs_lead_in']}), "
          f"mean menu {result['mean_menu_size']:.1f}, S1 {'PASS' if result['passes_s1'] else 'FAIL'}")
    print("  by lead-in location:", result["by_lead_in_location"])
    if args.out:
        args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
