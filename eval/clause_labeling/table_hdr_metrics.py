#!/usr/bin/env python3
"""PREREG11 metrics (read only, no model): flips, noise floor, rows, F5/F6, gold recall/precision on the table-chunk clauses, for the arms written by table_hdr_run.py.
Scoring functions are the PREREG8 ones (label_ctx_metrics) plus the CNSSI gold file as in PREREG9.

    python3 eval/clause_labeling/table_hdr_metrics.py [--json OUT]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import confirm_metrics as C  # noqa: E402
import label_ctx_metrics as M  # noqa: E402
from table_hdr_run import DOCS  # noqa: E402

from pipeline.sentence_expand import is_complete, tidy  # noqa: E402

OUT = Path.home() / "reqbot-work/scratch/table_hdr"
NR = M.NR


def load(arm):
    return {d: json.load(open(OUT / arm / f"{d}.json", encoding="utf-8")) for d in DOCS if (OUT / arm / f"{d}.json").exists()}


def in_scope_units(res, units):
    """Gold units that contain at least one labeled clause (so the unit is inside the labeled table chunks)."""
    sq = [M.squash(m["text"]) for m in res["clauses_meta"]]
    out = []
    for t, reqs in units:
        nt = M.squash(t)
        if any(s and s in nt for s in sq):
            out.append((t, reqs))
    return out


def gold_score(res_by_doc, silver, gold, docs):
    tot = collections.Counter()
    for d in docs:
        if d not in res_by_doc:
            continue
        units = (silver.get(d) or gold.get(d) or (None, []))[1]
        # scope fixed from the control arm's clause set (same in every arm)
        units = in_scope_units(res_by_doc[d], units)
        rows = [tidy(m["text"]) for m in res_by_doc[d]["clauses_meta"] if res_by_doc[d]["labels"].get(m["key"], NR) != NR]
        tot.update(M.quality(rows, units))
    return {**tot, "recall": 100 * tot["found"] / tot["labeled"] if tot["labeled"] else None,
            "precision": 100 * tot["rows_right"] / tot["rows_in_units"] if tot["rows_in_units"] else None}


def arm_stats(res):
    s = collections.Counter()
    for r in res.values():
        s["clauses"] += r["clauses"]
        s["seconds"] += r["seconds"]
        s["bad_batches"] += r["unparsed"] + r["failed"]
        for m in r["clauses_meta"]:
            row = r["labels"].get(m["key"], NR) != NR
            s["rows"] += row
            if m["is_grid"]:
                s["grid"] += 1
                s["grid_rows"] += row
                if row:
                    s["F5"] += "|" in m["text"]
                    s["F6"] += not is_complete(tidy(m["text"]))
    return dict(s)


def diff(a, b, grid_only=True):
    n = lab = st = 0
    per = collections.Counter()
    for d in a:
        for m in a[d]["clauses_meta"]:
            if grid_only and not m["is_grid"]:
                continue
            la, lb = a[d]["labels"].get(m["key"], NR), b[d]["labels"].get(m["key"], NR)
            n += 1
            lab += la != lb
            flip = (la == NR) != (lb == NR)
            st += flip
            per[d] += flip
    return {"n": n, "label_diff": lab, "status_flips": st, "per_doc": dict(per)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    silver, gold = C.gold_all()
    arms = {k: load(k) for k in ("control", "header", "control2")}
    out = {"stats": {k: arm_stats(v) for k, v in arms.items() if v}}
    if arms["control"] and arms["header"]:
        out["header_vs_control"] = diff(arms["control"], arms["header"])
        out["header_vs_control_all_clauses"] = diff(arms["control"], arms["header"], False)
    if arms["control"] and arms["control2"]:
        out["control2_vs_control"] = diff(arms["control"], arms["control2"])
        out["control2_vs_control_all_clauses"] = diff(arms["control"], arms["control2"], False)
    gdocs = [d for d in DOCS if (silver.get(d) or gold.get(d))]
    out["gold_docs"] = gdocs
    for k, v in arms.items():
        if v:
            out.setdefault("gold", {})[k] = {"pooled": gold_score(v, silver, gold, gdocs), **{d: gold_score(v, silver, gold, [d]) for d in gdocs}}
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
