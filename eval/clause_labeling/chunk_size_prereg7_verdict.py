#!/usr/bin/env python3
"""PREREG7 verdicts from the JSON the other chunk_size_* scripts wrote (metrics.json, windows.json). Read only, no model.

Label time: for runs that overlapped another job on the model server, pass --timing-root with a clean rerun (out_t/logs_t); its seconds replace the originals for those runs.

    python3 eval/clause_labeling/chunk_size_prereg7_verdict.py --root ~/reqbot-work/scratch/chunk_size2 [--timing-root ...] [--json OUT]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chunk_size_metrics as M  # noqa: E402

SEALED = (("afi17-203", "silver_exam"), ("afi13-550", "gold2_exam"))


def summarize(res: dict, arm: str, times: dict) -> dict:
    per = res[arm]
    s = {"end_cuts": 0, "F3": 0, "F9": 0, "F8": 0, "grid": 0, "chunks": 0, "li": 0, "li_in": 0, "labeled": 0, "found": 0, "rows_in_units": 0, "rows_right": 0, "secs": 0.0, "secs_missing": 0}
    sizes = []
    for doc, e in per.items():
        c = e["chunk"]
        s["end_cuts"] += c["end_cuts"]
        s["chunks"] += c["chunks"]
        s["li"] += c["list_item_clauses"]
        s["li_in"] += c["list_items_with_lead_in_in_chunk"]
        s["grid"] += c["grid_lines"]
        f = e.get("frag", {})
        for k in ("F3", "F8", "F9"):
            s[k] += f.get(k, 0)
        t = times.get((arm, doc), e.get("label_seconds"))
        if t is None:
            s["secs_missing"] += 1
        else:
            s["secs"] += t
        for d, key in SEALED:
            if d == doc:
                q = e[key]
                s["labeled"] += q["labeled"]
                s["found"] += q["found"]
                s["rows_in_units"] += q["rows_in_units"]
                s["rows_right"] += q["rows_right"]
    s["recall"] = 100 * s["found"] / s["labeled"]
    s["precision"] = 100 * s["rows_right"] / s["rows_in_units"]
    return s


def sizes_of(root: Path, arm: str) -> dict:
    v = []
    for doc in M.DOCS:
        d = M.run_dir(root, arm, doc)
        v += [len(c.get("raw_text") or "") for c in M._jsonl(d / f"{doc}_chunks.jsonl")]
    v.sort()
    return {"chunks": len(v), "median": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--timing-root", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    res = json.load(open(root / "metrics.json"))
    win = json.load(open(root / "windows.json"))
    times: dict = {}
    if a.timing_root:
        tr = Path(a.timing_root).expanduser()
        for arm in res:
            for doc in M.DOCS:
                p = tr / "logs_t" / f"{doc}_{arm}.log"
                if p.exists():
                    t = M.label_seconds(p)
                    if t is not None:
                        times[(arm, doc)] = t
    S = {arm: summarize(res, arm, times) for arm in res}
    ctl = S["control"]
    out = {}
    for arm in ("512", "1024", "A", "C"):
        s, w = S[arm], win[arm]
        wc = win["control"]
        n, nc = w["rows"], wc["rows"]
        beyond = {cap: 100 * (n - w[f"shipped_quote_in_{cap}"]) / n for cap in (1500, 1200)}
        beyond_c = {cap: 100 * (nc - wc[f"shipped_quote_in_{cap}"]) / nc for cap in (1500, 1200)}
        p1 = s["recall"] >= ctl["recall"] - 2.0 and s["precision"] >= ctl["precision"] - 2.0
        p2 = s["F8"] <= ctl["F8"]
        p3 = s["secs"] <= 1.5 * ctl["secs"]
        p4a = s["end_cuts"] <= 0.5 * ctl["end_cuts"]
        p4b = s["F9"] >= 1.25 * ctl["F9"] and s["F3"] <= ctl["F3"]
        p5 = s["grid"] >= 0.95 * ctl["grid"]
        p6s = all(beyond[c] <= beyond_c[c] + 2.0 for c in (1500, 1200))
        lead_c = 100 * wc["shipped_lead_in_in_1500"] / wc["rows_with_lead_in"]
        p6w = all(100 * w[f"win_quote_in_{c}"] / n >= 99 for c in (1500, 1200)) and 100 * w["win_lead_in_in_1500"] / w["rows_with_lead_in"] >= lead_c
        base = p1 and p2 and p3 and (p4a or p4b) and p5
        verdict = "PASS as shipped" if base and p6s else "PASS with window rule" if base and p6w else "FAIL"
        out[arm] = {"summary": s, "P1": p1, "P2": p2, "P3": p3, "P4a": p4a, "P4b": p4b, "P5": p5, "P6_shipped": p6s, "P6_window": p6w, "beyond_pct": beyond, "beyond_pct_control": beyond_c,
                    "window_lead_in_cov_pct": 100 * w["win_lead_in_in_1500"] / w["rows_with_lead_in"], "control_shipped_lead_in_cov_pct": lead_c, "verdict": verdict, "sizes": sizes_of(root, arm)}
    out["control"] = {"summary": ctl, "sizes": sizes_of(root, "control")}
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
