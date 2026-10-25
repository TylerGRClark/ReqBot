#!/usr/bin/env python3
"""PREREG12: aggregate the arm runs in a results folder and apply the pre-registered pass rule."""
import glob
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

SEGS = ["narrow", "broad", "parent_child_context", "table_derived", "messy_pdf_overgrab"]
M = ["mrr", "hit@1", "hit@5", "hit@10", "recall@10"]


def load(d):
    runs = defaultdict(list)
    for f in sorted(glob.glob(str(Path(d) / "*_*_*.json"))):
        j = json.loads(Path(f).read_text())
        if "arm" in j:
            runs[(j["mode"], j["arm"])].append(j)
    return runs


def scored(run):
    return [r for r in run["per_query"] if r.get("shape") != "zero" and "error" not in r and r.get("relevant_count", 0) > 0]


def means(run, shape=None):
    q = [r for r in scored(run) if shape in (None, r["shape"])]
    return {m: (sum(r[m] for r in q) / len(q) if q else None) for m in M}, len(q)


def main(d):
    runs = load(d)
    out = {}
    for (mode, arm), rs in sorted(runs.items()):
        ms = [means(r)[0] for r in rs]
        seg = {s: [means(r, s)[0]["mrr"] for r in rs] for s in SEGS}
        zero = [r["aggregate"]["zero_query_mean_returned_count"] for r in rs]
        out[(mode, arm)] = {
            "n_runs": len(rs), "n_scored": means(rs[0])[1],
            **{m: [round(x[m], 4) for x in ms] for m in M},
            "seg_mrr": {s: round(st.mean(v), 4) for s, v in seg.items()},
            "zero_returned": zero, "failed": sum(r["aggregate"]["failed_query_count"] for r in rs),
            "seconds": [r["seconds"] for r in rs],
        }
    for (mode, arm), v in out.items():
        print(mode, arm, json.dumps(v))
    # pass rule, prod mode
    verdicts = {}
    c = out.get(("prod", "control"))
    if c:
        rng = {m: max(c[m]) - min(c[m]) for m in ("mrr", "hit@5")}
        print("control prod range", rng, "control means", {m: round(st.mean(c[m]), 4) for m in M})
        for arm in ("head", "head1"):
            a = out.get(("prod", arm))
            if not a:
                continue
            d_mrr = st.mean(a["mrr"]) - st.mean(c["mrr"])
            d_h5 = st.mean(a["hit@5"]) - st.mean(c["hit@5"])
            segworse = {s: round(a["seg_mrr"][s] - c["seg_mrr"][s], 4) for s in SEGS}
            zero_ok = st.mean(a["zero_returned"]) <= st.mean(c["zero_returned"]) + 1.0
            r1 = d_mrr >= max(0.02, rng["mrr"]) and d_h5 >= max(0.02, rng["hit@5"])
            r2 = all(x >= -0.02 for x in segworse.values())
            equiv = abs(d_mrr) <= 0.02 and abs(d_h5) <= 0.02 and r2
            verdicts[arm] = {"d_mrr": round(d_mrr, 4), "d_hit5": round(d_h5, 4), "seg_delta_mrr": segworse,
                             "rule1_gain": r1, "rule2_no_segment_worse": r2, "rule3_zero": zero_ok,
                             "pass": bool(r1 and r2 and zero_ok), "equivalent": bool(equiv and zero_ok)}
        print(json.dumps(verdicts, indent=1))
    Path(d, "summary.json").write_text(json.dumps({"{}|{}".format(*k): v for k, v in out.items()} | {"verdicts": verdicts}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
