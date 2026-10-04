"""WP-45.1(c)/(d): the cells the README quotes, side by side for the plain run and each production-path repeat (offline).

Run from the repo root:  python3 eval/spike_results/wp_45_1c/key_cells.py [--out PATH]
"""

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import analyze as A  # noqa: E402

CELLS = (
    # (arm, mode, group, style, label)
    ("quote_alone", "target_only", "misleading", "topic", "Q1  wrong stem removed"),
    ("quote_alone", "target_only", "misleading", "party", "Q1  wrong stem removed"),
    ("quote_alone", "target_only", "incomplete", "topic", "Q1  chain stem removed"),
    ("quote_alone", "target_only", "incomplete", "party", "Q1  chain stem removed"),
    ("quote_alone", "target_only", "right", "topic", "Q2  right stem removed"),
    ("quote_alone", "target_only", "right", "party", "Q2  right stem removed"),
    ("oracle", "target_only", "bare", "topic", "Q3  lead-in added, no stem"),
    ("oracle", "target_only", "bare", "party", "Q3  lead-in added, no stem"),
    ("oracle", "target_only", "misleading", "topic", "Q3  lead-in replaces wrong stem"),
    ("oracle", "target_only", "misleading", "party", "Q3  lead-in replaces wrong stem"),
    ("oracle", "target_only", "incomplete", "party", "Q3  lead-in replaces chain stem"),
    ("h3_both", "target_only", "bare", "topic", "H3  rule heading, dense+BM25"),
    ("h3_both", "target_only", "bare", "party", "H3  rule heading, dense+BM25"),
    ("h3_dense", "target_only", "bare", "party", "H3  rule heading, dense only"),
    ("h4_both", "target_only", "bare", "party", "H4  rulings' heading, dense+BM25"),
)


def runs():
    found = [("plain", _HERE / "outputs/results_plain.json")]
    found += [(f"prod r{k}", _HERE / f"outputs/results_prod_r{k}.json") for k in (1, 2, 3)]
    return [(name, json.loads(p.read_text(encoding="utf-8"))) for name, p in found if p.exists()]


def cell_text(data, groups, arm, mode, group, style):
    rows = data["rows"]
    present = {r["rid"] for r in rows}
    docs = {rid: groups["records"][rid]["document"] for rid in present}
    no_party = {r["rid"] for r in rows if r["no_party"]}
    rids = [r for r in groups["groups"][group] if r in present and not (style == "party" and r in no_party)]
    if not any(r["arm"] == arm and r["mode"] == mode for r in rows):
        return "—"
    c = A.summarize(rows, docs, rids, arm, mode, style, "recall@10")
    m = A.summarize(rows, docs, rids, arm, mode, style, "mrr")
    b = c["best"]
    return f"{b['mean']:+.2f} [{b['lo']:+.2f},{b['hi']:+.2f}] {A.verdict(c)[:6]} | MRR {m['best']['mean']:+.2f} (n={b['n']})"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out")
    args = ap.parse_args()
    groups = json.loads((_HERE / "groups.json").read_text(encoding="utf-8"))
    loaded = runs()
    lines = ["Paired change in recall@10 (best-case ties; arm minus production), record bootstrap 95% interval, verdict, and MRR change.", ""]
    for arm, mode, group, style, label in CELLS:
        lines.append(f"{label:36s} {group:10s} {style:5s}")
        for name, data in loaded:
            lines.append(f"    {name:8s} {cell_text(data, groups, arm, mode, group, style)}")
    lines.append("")
    lines.append("Gold counterchecks, paired per query, cohort-wide (arm minus production), recall@10 [interval] and MRR:")
    for arm in ("quote_alone", "oracle", "h3_dense", "h3_both", "h4_dense", "h4_both"):
        for name, data in loaded:
            g = A.gold_paired(data["gold"], arm, "cohort")
            if g["recall@10"]["n"]:
                r, m = g["recall@10"], g["mrr"]
                lines.append(f"    {arm:12s} {name:8s} recall@10 {r['mean']:+.3f} [{r['lo']:+.3f},{r['hi']:+.3f}]  MRR {m['mean']:+.3f} [{m['lo']:+.3f},{m['hi']:+.3f}]")
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
