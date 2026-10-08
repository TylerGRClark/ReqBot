#!/usr/bin/env python3
"""WP-45.8 Stage B: evaluate the registry's rules (H, R, G, C) on the four runs (docs/PHASE45_WP458_REGISTRY.md, PHASE45_WP458_STAGEB_ADDENDUM.md section 2).

  python3 stage_b_analyze.py --out outputs/stageb_report.json            # reads outputs/stageb_results_{plain,prod_r1,prod_r2,prod_r3}.json

Pure computation on saved results; calls nothing. The decision logic (`evaluate`) is separate from the I/O so it can be tested with synthetic cells.
"""

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
C1 = _HERE.parents[1] / "spike_results" / "wp_45_1c"
for _p in (_HERE, C1):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import analyze as A  # noqa: E402  (wp_45_1c: bootstrap intervals, tie readings, the "meaningful" rule)

RUNS = ("plain", "prod_r1", "prod_r2", "prod_r3")
STYLES = ("topic", "party")
STEMMED = ("right", "misleading", "incomplete")
GROUP_NAMES = ("right", "misleading", "incomplete", "bare", "control", "pooled_stemmed")
WIDE = 0.40
HARM = -0.10
GOLD_FLOOR = -0.02


def classify(cell):
    """One cell's reading from the apparatus' summary (both tie readings): inconclusive, decrease, increase or none; and whether both point estimates are at most HARM."""
    best, worst = cell["best"], cell["worst"]
    if best["n"] == 0:
        return {"inconclusive": True, "empty": True, "meaningful": None, "point_at_most_harm": False}
    wide = any(c["hi"] - c["lo"] > WIDE for c in (best, worst))
    both = [A.meaningful(c["lo"], c["hi"], c["mean"]) for c in (best, worst)]
    same_sign = (best["mean"] > 0) == (worst["mean"] > 0)
    kind = None
    if all(both) and same_sign:
        kind = "increase" if best["mean"] > 0 else "decrease"
    return {"inconclusive": wide, "empty": False, "meaningful": kind, "point_at_most_harm": best["mean"] <= HARM and worst["mean"] <= HARM}


def evaluate(cells, gold):
    """Apply the registry. `cells[run][arm_style][group]` = classify() output; `gold[run]` = {'hi': upper bound of the recall@10 change}. Returns the triggers and outcome."""
    h, r, g, c = [], [], [], []
    for style in STYLES:
        for group in GROUP_NAMES:
            reads = [cells[run][style][group] for run in RUNS]
            if sum(1 for x in reads if not x["inconclusive"] and x["meaningful"] == "decrease") >= 2:
                h.append({"style": style, "group": group, "runs": [run for run, x in zip(RUNS, reads) if not x["inconclusive"] and x["meaningful"] == "decrease"]})
            if group in ("right", "pooled_stemmed", "control") and all(x["point_at_most_harm"] for x in reads):
                r.append({"style": style, "group": group})
            if group == "bare" and sum(1 for x in reads if not x["inconclusive"] and x["meaningful"] == "increase") >= 3:
                g.append({"style": style, "runs": [run for run, x in zip(RUNS, reads) if not x["inconclusive"] and x["meaningful"] == "increase"]})
    low = [run for run in RUNS if gold[run]["hi"] < GOLD_FLOOR]
    if len(low) >= 2:
        c.append({"runs": low})
    triggered = bool(h or r or c)
    outcome = ("no proposal: " + ", ".join(n for n, v in (("H", h), ("R", r), ("C", c)) if v) + " triggered; read the records behind it") if triggered else (
        "proposal for integration" if g else "no demonstrated benefit")
    return {"H": h, "R": r, "G": g, "C": c, "G_holds": bool(g), "outcome": outcome}


def load(run_name, directory):
    return json.loads((Path(directory) / f"stageb_results_{run_name}.json").read_text(encoding="utf-8"))


def pools(groups, present):
    by_group = {g: sorted(r for r in groups["groups"][g] if r in present) for g in ("right", "misleading", "incomplete", "bare", "control")}
    by_group["pooled_stemmed"] = sorted(set().union(*(by_group[g] for g in STEMMED)))
    return by_group


def analyze(directory, arm="resolver", metric="recall@10"):
    groups = json.loads((C1 / "groups.json").read_text(encoding="utf-8"))
    cells, gold, detail = {}, {}, {}
    for run in RUNS:
        data = load(run, directory)
        rows = data["rows"]
        present = {r["rid"] for r in rows}
        rid_docs = {rid: groups["records"][rid]["document"] for rid in present}
        no_party = {r["rid"] for r in rows if r["no_party"]}
        by_group = pools(groups, present)
        cells[run], detail[run] = {}, {}
        for style in STYLES:
            cells[run][style], detail[run][style] = {}, {}
            for group, rids in by_group.items():
                pool = [x for x in rids if not (style == "party" and x in no_party)]
                summary = A.summarize(rows, rid_docs, pool, arm, "target_only", style, metric)
                cells[run][style][group] = classify(summary)
                detail[run][style][group] = {"n": summary["best"]["n"], "summary": summary, **cells[run][style][group]}
        gp = A.gold_paired(data["gold"], arm, "cohort")[metric]
        gold[run] = gp
        detail[run]["gold"] = gp
        detail[run]["gold_mrr"] = A.gold_paired(data["gold"], arm, "cohort")["mrr"]
        # pre-registered diagnostics, reported and never gating: the other metrics, and how many records in each group have a resolver string
        detail[run]["other_metrics"] = {
            name: {style: {group: A.summarize(rows, rid_docs, [x for x in rids if not (style == "party" and x in no_party)], arm, "target_only", style, name)
                           for group, rids in by_group.items()} for style in STYLES} for name in ("recall@5", "recall@20", "mrr")}
        has = {(r["rid"]): r["has_string"] for r in rows if r["arm"] == arm and r["mode"] == "target_only"}
        detail[run]["string_coverage"] = {group: {"with_string": sum(1 for x in rids if has.get(x)), "without_string": sum(1 for x in rids if x in has and not has[x])}
                                          for group, rids in by_group.items()}
        detail[run]["manifest"] = {k: data["manifest"][k] for k in ("snapshot", "strings", "excluded_not_in_live_index")}
    return evaluate(cells, gold), detail


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=str(_HERE / "outputs"))
    ap.add_argument("--out")
    args = ap.parse_args()
    report = {}
    for arm in ("resolver", "hybrid"):  # hybrid is reported beside, never gating
        verdict, detail = analyze(args.dir, arm)
        report[arm] = {"verdict": verdict, "runs": detail}
    print(json.dumps({arm: report[arm]["verdict"] for arm in report}, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
