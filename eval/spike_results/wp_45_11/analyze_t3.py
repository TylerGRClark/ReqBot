#!/usr/bin/env python3
"""WP-45.11 T3 targeted measure (docs/PHASE45_WP4511_PLAN.md section 3, docs/PHASE45_WP4511_T3_ADDENDUM.md): the chunk-limit arm against the T2-state replicates, on the labeled lead-in items.

  python3 analyze_t3.py --base T2a T2b --base-chunks d2.94.0:T2_256 --arm T3_512 --arm-chunks d2.94.0:T2_512 --out outputs/t3_512_report.json

Offline; reads chunk caches and scratch arm outputs only. The rules it evaluates (fixed before any T3 arm output was read, see the addendum):
  fixed set  = labeled items (audit and fresh gold, "needs a lead-in" with adjudicated lead-in text) whose quote is findable in the chunks of BOTH chunk specifications;
               items findable in only one, or neither, are counted and listed, never dropped from a rate silently.
  co-located = the quote's chunk text holds every piece of the labeled lead-in text (the WP-45.10 rule). Deterministic from the chunk files.
  extracted  = a Step D survivor of the arm whose normalized source_quote contains, or is contained in, the normalized gold quote (both at least 40 characters).
  stem match = that survivor's production `parent_stem` overlaps the labeled lead-in text under the WP-45.7 rule (`score_resolver.overlaps`; a lenient proxy that
               credits a party-less fragment, stated again here). Reported, not gated.
  R3 (T3)    = extracted count on the fixed set >= 90% of the LOWER of the two base replicates' counts, and the co-located share up by >= 5 percentage points.
"""

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_10", _ROOT / "eval/spike_results/wp_45_7", _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import score_arms as SA  # noqa: E402  (this folder: the same arm validation R1/R2 use)
import analyze_chunks as AC  # noqa: E402  (wp_45_10: gold items, norm, chunk loading, lead-in pieces)
import score_resolver as SR  # noqa: E402  (wp_45_7: the registered stem-overlap rule)

SCRATCH = Path.home() / "wp45_11_scratch"
MIN_QUOTE = 40


def find_chunk(chunks, quote):
    """The chunk holding the quote (whole normalized quote first, then its first 60 characters, as WP-45.10 did), or None."""
    q = AC.norm(quote)
    return next((c for c in chunks if q in AC.norm(c["raw_text"])), None) or next((c for c in chunks if q[:60] in AC.norm(c["raw_text"])), None)


def colocated(chunk, lead_in):
    text = AC.norm(chunk["text"])
    return all(p in text for p in AC.pieces(lead_in))


def survivors(arm, doc):
    path = SCRATCH / arm / doc / f"{doc}_requirements_normalized.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def extracted_record(arm_records, quote):
    q = AC.norm(quote)
    if len(q) < MIN_QUOTE:
        return None
    for r in arm_records:
        s = AC.norm(r.get("source_quote", ""))
        if len(s) >= MIN_QUOTE and (q in s or s in q):
            return r
    return None


def per_arm(arm, items, fixed_ids, cache):
    out = {}
    for it in items:
        if it["id"] not in fixed_ids:
            continue
        rec = extracted_record(cache.setdefault((arm, it["document"]), survivors(arm, it["document"])), it["quote"])
        out[it["id"]] = {"extracted": rec is not None, "stem_match": bool(rec and SR.overlaps(rec.get("parent_stem") or "", it["lead_in"]))}
    return out


def validate(arms_and_specs):
    """The same refusals `score_arms.py` makes, before any number is computed: every document finished with no failed Step C chunk, one chunk specification per arm and
    the specification each arm is declared to have run, one model file, identical pipeline code across the compared arms."""
    for arm, spec in arms_and_specs:
        SA.check_complete(arm, SCRATCH)
        SA.check_one_spec_per_arm(arm, SCRATCH)
        for doc in sorted(SA.common.pinned_documents()):
            ran = json.loads((SA.arm_dir(arm, doc, SCRATCH) / "arm_record.json").read_text(encoding="utf-8")).get("chunks_spec")
            if ran != spec:
                raise SystemExit(f"arm {arm}/{doc} ran chunk specification {ran}, not {spec}")
    arms = [a for a, _ in arms_and_specs]
    SA.check_same_model(arms, SCRATCH)
    SA.check_same_code(arms, SCRATCH)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", nargs=2, required=True, metavar=("A", "B"), help="the two replicate arms of the T2 state")
    ap.add_argument("--base-chunks", required=True, help="TAG:LABEL of the T2 state's chunk files")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--arm-chunks", required=True, help="TAG:LABEL of the T3 arm's chunk files")
    ap.add_argument("--out")
    args = ap.parse_args()

    validate([(args.base[0], args.base_chunks), (args.base[1], args.base_chunks), (args.arm, args.arm_chunks)])
    items = AC.gold_items()
    chunk_cache = {}

    def chunks_for(spec, doc):
        return chunk_cache.setdefault((spec, doc), AC.load_chunks(spec, doc))

    hits = {}
    for it in items:
        base_hit, arm_hit = find_chunk(chunks_for(args.base_chunks, it["document"]), it["quote"]), find_chunk(chunks_for(args.arm_chunks, it["document"]), it["quote"])
        hits[it["id"]] = (base_hit, arm_hit)
    fixed = [it for it in items if all(hits[it["id"]])]
    if not fixed:
        raise SystemExit("no labeled quote is findable in both chunk specifications; check --base-chunks / --arm-chunks")
    fixed_ids = {it["id"] for it in fixed}
    only_base = [it["id"] for it in items if hits[it["id"]][0] and not hits[it["id"]][1]]
    only_arm = [it["id"] for it in items if hits[it["id"]][1] and not hits[it["id"]][0]]
    neither = [it["id"] for it in items if not any(hits[it["id"]])]

    co = {it["id"]: (colocated(hits[it["id"]][0], it["lead_in"]), colocated(hits[it["id"]][1], it["lead_in"])) for it in fixed}
    n = len(fixed)
    base_co, arm_co = sum(v[0] for v in co.values()), sum(v[1] for v in co.values())

    rec_cache = {}
    results = {a: per_arm(a, items, fixed_ids, rec_cache) for a in (*args.base, args.arm)}
    ext = {a: sum(v["extracted"] for v in r.values()) for a, r in results.items()}
    stem = {a: sum(v["stem_match"] for v in r.values()) for a, r in results.items()}
    lower_base = min(ext[b] for b in args.base)

    def one_way(a, b):
        return sorted(i for i in fixed_ids if results[a][i]["extracted"] and not results[b][i]["extracted"])

    report = {
        "base_arms": list(args.base), "arm": args.arm, "base_chunks": args.base_chunks, "arm_chunks": args.arm_chunks,
        "labeled_items": len(items), "fixed_set": n,
        "findable_only_in_base_chunks": only_base, "findable_only_in_arm_chunks": only_arm, "findable_in_neither": neither,
        "colocated": {"base": base_co, "arm": arm_co, "base_share": round(base_co / n, 4), "arm_share": round(arm_co / n, 4),
                      "gain_points": round(100 * (arm_co - base_co) / n, 1),
                      "gained": sorted(i for i, v in co.items() if v[1] and not v[0]), "lost": sorted(i for i, v in co.items() if v[0] and not v[1])},
        "extracted": {"counts": ext, "lower_base": lower_base, "arm_over_lower_base": round(ext[args.arm] / lower_base, 3) if lower_base else None,
                      "base_replicate_one_way_differences": {f"{args.base[0]}_not_{args.base[1]}": one_way(args.base[0], args.base[1]),
                                                              f"{args.base[1]}_not_{args.base[0]}": one_way(args.base[1], args.base[0])},
                      "arm_lost_vs_each_base": {b: one_way(b, args.arm) for b in args.base},
                      "arm_gained_vs_each_base": {b: one_way(args.arm, b) for b in args.base}},
        "stem_match_reported_not_gated": {
            "counts": stem, "arm_minus_each_base": {b: stem[args.arm] - stem[b] for b in args.base},
            "paired_vs_each_base": {b: {"gained": sorted(i for i in fixed_ids if results[args.arm][i]["stem_match"] and not results[b][i]["stem_match"]),
                                        "lost": sorted(i for i in fixed_ids if results[b][i]["stem_match"] and not results[args.arm][i]["stem_match"])}
                                    for b in args.base}},
    }
    r3_ext = ext[args.arm] >= 0.9 * lower_base
    r3_co = report["colocated"]["gain_points"] >= 5
    report["R3"] = {"extracted_at_least_90_percent_of_lower_base": r3_ext, "colocated_up_5_points": r3_co, "pass": bool(r3_ext and r3_co)}

    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
