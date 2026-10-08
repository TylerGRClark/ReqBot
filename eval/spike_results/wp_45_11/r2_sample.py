#!/usr/bin/env python3
"""WP-45.11 T3 R2 read (docs/PHASE45_WP4511_T3_ADDENDUM.md section 2a): totals, the trigger, and the seeded 40-record sample to be sorted by hand.

  python3 r2_sample.py --base T2a T2b --arm T3_512 --base-chunks d2.94.0:T2_256 --arm-chunks d2.94.0:T2_512 --out outputs/t3_512_r2_sample.json

Fall: more than 10% below the LOWER base replicate's total Step D survivors; pool = survivor quotes present in BOTH replicates and absent from the arm.
Rise: more than 10% above the HIGHER replicate; pool = the arm's survivors absent from both replicates. "Absent" = no survivor of the other side contains the
quote or is contained in it (both at least 40 characters). Pool sorted by (document, normalized quote); 40 drawn with random.Random(45).sample (all if fewer).
Each sampled record is printed (stdout, and --out) with the text of the chunk the survivor itself came from (its recorded chunk_id), on the side that holds it, for sorting into (1)/(2)/(3) (fall) or (a)/(b)/(c) (rise). Nothing is sorted here.
"""

import argparse
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_10"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import analyze_t3 as T3  # noqa: E402
import score_arms as SA  # noqa: E402

SEED, SIZE, THRESHOLD, MIN_QUOTE = 45, 40, 0.10, 40


def covered(quote, others):
    return any(len(o) >= MIN_QUOTE and (quote in o or o in quote) for o in others)


def pools(base_a, base_b, arm):
    """{doc: (quotes in both replicates and not in the arm, arm quotes in neither replicate)} from {doc: [normalized quotes]} mappings."""
    out = {}
    for doc in arm:
        both = [q for q in base_a[doc] if len(q) >= MIN_QUOTE and covered(q, base_b[doc]) and not covered(q, arm[doc])]
        new = [q for q in arm[doc] if len(q) >= MIN_QUOTE and not covered(q, base_a[doc]) and not covered(q, base_b[doc])]
        out[doc] = (sorted(set(both)), sorted(set(new)))
    return out


def draw(items):
    items = sorted(items)
    return items if len(items) <= SIZE else sorted(random.Random(SEED).sample(items, SIZE))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", nargs=2, required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--base-chunks", required=True)
    ap.add_argument("--arm-chunks", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    T3.validate([(args.base[0], args.base_chunks), (args.base[1], args.base_chunks), (args.arm, args.arm_chunks)])
    docs = sorted(SA.common.pinned_documents())
    recs = {a: {d: T3.survivors(a, d) for d in docs} for a in (*args.base, args.arm)}
    q = {a: {d: [T3.AC.norm(r.get("source_quote") or "") for r in recs[a][d]] for d in docs} for a in recs}
    chunk_of = {a: {d: {T3.AC.norm(r.get("source_quote") or ""): r.get("chunk_id") for r in recs[a][d]} for d in docs} for a in recs}  # the survivor's own chunk
    totals = {a: sum(len(v) for v in q[a].values()) for a in q}
    low, high = min(totals[b] for b in args.base), max(totals[b] for b in args.base)
    if not low or not high:
        raise SystemExit(f"a base replicate has no Step D survivors: {totals}")
    fall = totals[args.arm] < low * (1 - THRESHOLD)
    rise = totals[args.arm] > high * (1 + THRESHOLD)
    report = {"totals": totals, "lower_base": low, "higher_base": high, "arm_over_lower_base": round(totals[args.arm] / low, 4),
              "arm_over_higher_base": round(totals[args.arm] / high, 4), "trigger": "fall" if fall else "rise" if rise else "none",
              "seed": SEED, "sample_size": SIZE}
    if fall or rise:
        pl = pools(q[args.base[0]], q[args.base[1]], q[args.arm])
        flat = [(d, quote) for d, (both, new) in pl.items() for quote in (both if fall else new)]
        report["pool_size"] = len(flat)
        chunk_spec, holder = (args.base_chunks, args.base[0]) if fall else (args.arm_chunks, args.arm)  # the side whose survivor the sampled quote is
        by_id = {}
        sample = []
        for d, quote in draw(flat):
            cid = chunk_of[holder][d].get(quote)
            chunk = by_id.setdefault(d, {c["chunk_id"]: c for c in T3.AC.load_chunks(chunk_spec, d)}).get(cid)
            sample.append({"document": d, "quote": quote, "chunk_id": cid, "chunk_text": chunk and chunk["text"], "class": None})
        report["sample"] = sample
    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
