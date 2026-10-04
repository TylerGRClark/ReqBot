"""WP-45.1(c)/(d): score a results file with the decision rules fixed in docs/PHASE45_WP451C_PLAN.md (offline).

Per record, arm and query style it takes the rank of the target in the fused list, with ties as best and worst case, and
reports PAIRED differences against production for the same record with a record-level bootstrap (10,000 resamples,
fixed seed) plus a document-level bootstrap as a sensitivity check. "Meaningful" is decided before looking: a paired
change in recall@10 of at least 0.10 whose 95% interval excludes zero, under BOTH tie conventions. A smaller or
unconvincing change is "no demonstrated difference", never "no effect".

Run from the repo root:  python3 eval/spike_results/wp_45_1c/analyze.py outputs/results_plain.json [--report-out PATH]
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent

KS = (5, 10, 20)
STYLES = ("topic", "party")
GROUPS = ("right", "misleading", "incomplete", "bare", "control")
TIES = ("best", "worst")
RESAMPLES = 10_000
SEED = 4510
MEANINGFUL = 0.10  # recall@10


# --------------------------------------------------------------------------------------------------------- metrics


def rank_of(row, tie):
    """The target's rank under a tie convention; None when it was beyond the diagnostic list."""
    return row["best_rank"] if tie == "best" else row["worst_rank"]


def recall_at(row, k, tie):
    r = rank_of(row, tie)
    return 1.0 if r is not None and r <= k else 0.0


def reciprocal_rank(row, tie):
    r = rank_of(row, tie)
    return 1.0 / r if r else 0.0


def metric(row, name, tie):
    if name == "mrr":
        return reciprocal_rank(row, tie)
    return recall_at(row, int(name.split("@")[1]), tie)


def bootstrap_ci(deltas, clusters=None, resamples=RESAMPLES, seed=SEED):
    """95% percentile interval of the mean of `deltas`. With `clusters` (a label per delta) whole clusters are resampled."""
    d = np.asarray(deltas, dtype=float)
    if d.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    if clusters is None:
        idx = rng.integers(0, d.size, size=(resamples, d.size))
        means = d[idx].mean(axis=1)
    else:
        labels = sorted(set(clusters))
        members = [np.flatnonzero([c == lab for c in clusters]) for lab in labels]
        sums = np.array([d[m].sum() for m in members])
        sizes = np.array([len(m) for m in members], dtype=float)
        pick = rng.integers(0, len(labels), size=(resamples, len(labels)))
        means = sums[pick].sum(axis=1) / sizes[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def meaningful(lo, hi, mean):
    """Pre-registered rule for recall@10: |change| >= 0.10 and the interval excludes zero."""
    return abs(mean) >= MEANINGFUL and (lo > 0 or hi < 0)


# ------------------------------------------------------------------------------------------------------- the tables


def index_rows(rows):
    return {(r["rid"], r["style"], r["arm"], r["mode"]): r for r in rows}


def paired(rows, rids, arm, mode, style, name, tie, base_mode="base"):
    """[(rid, delta)] of metric(arm) - metric(production) for records that have both rows."""
    ix = index_rows(rows)
    out = []
    for rid in rids:
        a, b = ix.get((rid, style, arm, mode)), ix.get((rid, style, "production", base_mode))
        if a is not None and b is not None:
            out.append((rid, metric(a, name, tie) - metric(b, name, tie)))
    return out


def summarize(rows, rid_docs, rids, arm, mode, style, name):
    """Mean paired difference with both intervals and both tie conventions for one cell of a table."""
    cell = {}
    for tie in TIES:
        pairs = paired(rows, rids, arm, mode, style, name, tie)
        deltas = [d for _, d in pairs]
        mean, lo, hi = bootstrap_ci(deltas)
        _, dlo, dhi = bootstrap_ci(deltas, clusters=[rid_docs[r] for r, _ in pairs])
        cell[tie] = {
            "n": len(deltas),
            "mean": mean,
            "lo": lo,
            "hi": hi,
            "doc_lo": dlo,
            "doc_hi": dhi,
            "better": sum(1 for d in deltas if d > 0),
            "worse": sum(1 for d in deltas if d < 0),
            "same": sum(1 for d in deltas if d == 0),
        }
    return cell


def verdict(cell):
    """meaningful in the same direction under both tie conventions, else not demonstrated."""
    flags = [meaningful(cell[t]["lo"], cell[t]["hi"], cell[t]["mean"]) for t in TIES]
    signs = {cell[t]["mean"] > 0 for t in TIES}
    if all(flags) and len(signs) == 1:
        return "BETTER" if cell["best"]["mean"] > 0 else "WORSE"
    return "no demonstrated difference"


def fmt_cell(cell):
    b, w = cell["best"], cell["worst"]
    if b["n"] == 0:
        return "n=0"
    return (
        f"n={b['n']:3d}  best {b['mean']:+.3f} [{b['lo']:+.3f},{b['hi']:+.3f}]  worst {w['mean']:+.3f} [{w['lo']:+.3f},{w['hi']:+.3f}]"
        f"  doc-boot best [{b['doc_lo']:+.3f},{b['doc_hi']:+.3f}]  up/down/same {b['better']}/{b['worse']}/{b['same']}"
    )


def descriptive(rows, rids_by_group, style):
    """Q4: production only, recall@k and MRR by group (confounded by query difficulty; descriptive)."""
    ix = index_rows(rows)
    out = {}
    for g, rids in rids_by_group.items():
        cells = {}
        for tie in TIES:
            vals = {n: [] for n in ("recall@5", "recall@10", "recall@20", "mrr")}
            for rid in rids:
                r = ix.get((rid, style, "production", "base"))
                if r is None:
                    continue
                for n in vals:
                    vals[n].append(metric(r, n, tie))
            cells[tie] = {n: (statistics.mean(v) if v else float("nan")) for n, v in vals.items()}
            cells[tie]["n"] = len(vals["mrr"])
        out[g] = cells
    return out


def gold_summary(gold_rows):
    """Mean recall@k and MRR of the gold counterchecks per arm and mode."""
    by = {}
    for r in gold_rows:
        by.setdefault((r["arm"], r["mode"]), []).append(r)
    out = {}
    for key, rs in by.items():
        out[key] = {
            n: statistics.mean(r[n] for r in rs)
            for n in ("recall@5", "recall@10", "recall@20", "mrr")
        }
        out[key]["n"] = len(rs)
    return out


def gold_paired(gold_rows, arm, mode):
    """Per-query paired difference (arm minus production) of recall@10 and MRR over the gold counterchecks."""
    base = {r["query_id"]: r for r in gold_rows if r["arm"] == "production"}
    cur = {r["query_id"]: r for r in gold_rows if r["arm"] == arm and r["mode"] == mode}
    out = {}
    for name in ("recall@10", "mrr"):
        deltas = [cur[q][name] - base[q][name] for q in cur if q in base]
        mean, lo, hi = bootstrap_ci(deltas)
        out[name] = {"n": len(deltas), "mean": mean, "lo": lo, "hi": hi, "up": sum(d > 0 for d in deltas), "down": sum(d < 0 for d in deltas)}
    return out


def survival(rows):
    """How often a target clears the production score threshold and reaches the returned 20, by arm and mode."""
    by = {}
    for r in rows:
        by.setdefault((r["arm"], r["mode"]), []).append(r)
    return {
        k: {
            "n": len(v),
            "survives": sum(r["survives"] for r in v) / len(v),
            "in_returned": sum(r["in_returned"] for r in v) / len(v),
        }
        for k, v in by.items()
    }


# ------------------------------------------------------------------------------------------------------------ report


def build_report(data, groups):
    rows, gold_rows = data["rows"], data["gold"]
    present = {r["rid"] for r in rows}
    rec = groups["records"]
    rid_docs = {rid: rec[rid]["document"] for rid in present}
    by_group = {g: sorted(r for r in groups["groups"][g] if r in present) for g in GROUPS}
    no_party = {r["rid"] for r in rows if r["no_party"]}
    oracle = [r for r in groups["oracle_set"] if r in present]
    out = []
    emit = out.append
    emit(
        f"# Results: {data['manifest']['inputs_mode']} query inputs, {len(present)} target records"
    )
    emit(
        f"groups present: { {g: len(v) for g, v in by_group.items()} }; excluded (not in the live index): {data['manifest'].get('excluded_not_in_live_index')}"
    )
    emit(
        "Paired difference = arm minus production for the same record; recall values are 0/1 per record, so a mean is a share of records."
    )
    emit(
        f"'meaningful' = |recall@10 change| >= {MEANINGFUL} with a 95% interval excluding zero, same direction under best and worst tie case.\n"
    )

    def party_ok(style, rids):
        return [r for r in rids if not (style == "party" and r in no_party)]

    def section(title, groups_to_use, arm, mode, rid_pool=None):
        emit(f"## {title}")
        for style in STYLES:
            for g in groups_to_use:
                pool = (
                    by_group[g] if rid_pool is None else [r for r in by_group[g] if r in rid_pool]
                )
                pool = party_ok(style, pool)
                for name in ("recall@5", "recall@10", "recall@20", "mrr"):
                    cell = summarize(rows, rid_docs, pool, arm, mode, style, name)
                    tag = (
                        f"  -> {verdict(cell)}" if name == "recall@10" and cell["best"]["n"] else ""
                    )
                    emit(f"- {style:5s} {g:10s} {name:9s} {fmt_cell(cell)}{tag}")
        emit("")

    stemmed = {r["rid"] for r in rows if r["arm"] == "quote_alone" and r["mode"] == "target_only"}
    section(
        "Q1/Q2 primary: quote alone vs production, only the target's vector swapped",
        ("misleading", "incomplete", "right"),
        "quote_alone",
        "target_only",
        stemmed,
    )
    section(
        "Q3 primary: adjudicated lead-in + quote vs production, only the target's vector swapped",
        GROUPS,
        "oracle",
        "target_only",
        set(oracle),
    )
    section(
        "Secondary (policy check): quote alone for every stemmed record at once",
        ("misleading", "incomplete", "right"),
        "quote_alone",
        "cohort",
        stemmed,
    )
    section(
        "Secondary (policy check): adjudicated lead-in applied to the whole oracle set at once",
        GROUPS,
        "oracle",
        "cohort",
        set(oracle),
    )
    hrows = {(r["arm"], r["mode"]): r for r in rows}
    for arm, label in (("h3_dense", "H3 rule, dense only"), ("h3_both", "H3 rule, dense + BM25"), ("h4_dense", "H4 rulings' selection, dense only"), ("h4_both", "H4 rulings' selection, dense + BM25")):
        if (arm, "target_only") not in hrows:
            continue
        applied = {r["rid"] for r in rows if r["arm"] == arm and r["mode"] == "target_only" and r.get("applied", True)}
        emit(f"## Heading arm {label}: leaf heading in front of the text; applies to {len(applied)} of {len(present)} target records")
        section(f"{label}, target-only, whole group (records the arm does not touch count as zero)", GROUPS, arm, "target_only")
        section(f"{label}, target-only, only the records it applies to", GROUPS, arm, "target_only", applied)
        section(f"{label}, cohort-wide (applied to every record it applies to, whole index)", GROUPS, arm, "cohort")
    sub = [r for r in groups["stem_on_complete_quote"] if r in stemmed]
    emit(
        f"## Subgroup: stemmed records whose quote is already complete (n={len(sub)}), quote alone vs production, target-only"
    )
    for style in STYLES:
        for name in ("recall@10", "mrr"):
            cell = summarize(
                rows, rid_docs, party_ok(style, sub), "quote_alone", "target_only", style, name
            )
            emit(f"- {style:5s} {name:9s} {fmt_cell(cell)}")
    emit("\n## Q4 (descriptive only): findability of each group as it stands, production text")
    for style in STYLES:
        d = descriptive(rows, {g: party_ok(style, by_group[g]) for g in GROUPS}, style)
        for g in GROUPS:
            b, w = d[g]["best"], d[g]["worst"]
            emit(
                f"- {style:5s} {g:10s} n={b['n']:3d} recall@10 best {b['recall@10']:.3f} worst {w['recall@10']:.3f}; recall@5 {b['recall@5']:.3f}/{w['recall@5']:.3f}; MRR {b['mrr']:.3f}/{w['mrr']:.3f}"
            )
    emit(
        "\n## Survival of the production score threshold and presence in the returned 20 (all rows)"
    )
    for (arm, mode), v in sorted(survival(rows).items()):
        emit(
            f"- {arm:12s} {mode:11s} n={v['n']:4d} survives {v['survives']:.3f} in returned list {v['in_returned']:.3f}"
        )
    emit("\n## Gold counterchecks (35 scored topical queries): mean over queries")
    for (arm, mode), v in sorted(gold_summary(gold_rows).items()):
        emit(
            f"- {arm:12s} {mode:7s} n={v['n']:2d} recall@5 {v['recall@5']:.3f} @10 {v['recall@10']:.3f} @20 {v['recall@20']:.3f} MRR {v['mrr']:.3f}"
        )
    emit("\nGold counterchecks, paired per query (arm minus production), bootstrap 95% interval:")
    for arm, mode in (("quote_alone", "cohort"), ("oracle", "cohort"), ("h3_dense", "cohort"), ("h3_both", "cohort"), ("h4_dense", "cohort"), ("h4_both", "cohort")):
        if not any(r["arm"] == arm and r["mode"] == mode for r in gold_rows):
            continue
        for name, v in gold_paired(gold_rows, arm, mode).items():
            emit(f"- {arm:12s} {mode:7s} {name:9s} n={v['n']:2d} {v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}] queries up/down {v['up']}/{v['down']}")
    return "\n".join(out)


def low_overlap_filter(rows, ids_by_pid, queries, cards, qc):
    """Keep only (record, style) queries at or below the median content-word overlap of their style."""
    checked, _ = qc.check(queries, cards)
    keep = set()
    for style in STYLES:
        vals = sorted(c["overlap"] for c in checked if c["style"] == style)
        median = statistics.median(vals)
        keep |= {(ids_by_pid[c["pid"]], style) for c in checked if c["style"] == style and c["overlap"] <= median}
    return [r for r in rows if (r["rid"], r["style"]) in keep]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results")
    ap.add_argument("--report-out")
    ap.add_argument(
        "--low-overlap",
        action="store_true",
        help="keep only queries at or below the median content-word overlap with their card (pre-planned counter-check)",
    )
    args = ap.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    if args.low_overlap:
        sys.path.insert(0, str(_HERE))
        import query_check as qc

        queries = [json.loads(x) for x in (_HERE / "queries.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        cards = qc.parse_packet((_HERE / "query_packet.md").read_text(encoding="utf-8"))
        ids = json.loads((_HERE / "query_ids.json").read_text(encoding="utf-8"))["ids"]
        data["rows"] = low_overlap_filter(data["rows"], ids, queries, cards, qc)
        data["manifest"]["inputs_mode"] += " (queries at or below the median overlap only)"
    groups = json.loads((_HERE / "groups.json").read_text(encoding="utf-8"))
    text = build_report(data, groups)
    if args.report_out:
        Path(args.report_out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    sys.exit(main())
