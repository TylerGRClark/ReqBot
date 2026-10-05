"""WP-45.6: score the extraction-model comparison against the pre-set rules in docs/PHASE45_WP456_PLAN.md (offline).

Reads the pack key, the two labelers' pass A files and Tyler's adjudication, resolves the final labels with the WP-45.1(b)
scorer's own machinery, then estimates for each of the three sets (14B-only, 8B-only, both) the share that are genuine
requirements and complete, weights them by the sets' sizes from the comparison files, and evaluates the rule:

  (a) (G - L) / N8 >= 0.10 with a 95% bootstrap interval excluding zero   G, L = genuine 14B-only / 8B-only records, N8 = genuine 8B
  (b) the not-a-requirement share of the 14B-only set is not higher than the 8B-only set's by more than 0.10
  (c) the 14B's fragment composite is not demonstrably higher than the baseline's (interval of the difference reaches zero or below)
  (d) the 14B loses (failed or cut-off) no more than 5 percentage points more chunks than today's fresh 8B run
  (e) the 14B's net unique difference exceeds the fresh 8B's own by at least 0.05 of the baseline survivors

Run from the repo root:
  python3 eval/spike_results/wp_45_6/score.py --key KEY --labels-dir DIR --pack-dir PACK --new qwen2.5_14b \\
      [--sheet-out PATH] [--answers adjudication.txt]
"""

import argparse
import importlib.util
import json
import math
import sys
import types
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
DOCS = ("DODI 8410.03", "afman17-2101", "NIST.SP.800-125")
CONTROL_TAG = "llama3.1_8b-instruct-q4_K_M"
SETS = ("new_only", "base_only", "both")
RESAMPLES = 10_000
SEED = 4560
GAIN = 0.10
JUNK_MARGIN = 0.10
CHUNK_LOSS_MARGIN = 0.05
NOISE_MARGIN = 0.05


def load_scorer():
    spec = importlib.util.spec_from_file_location(
        "wp45_score_audit_for_456", _ROOT / "eval/spike_results/wp_45_1/score_audit.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def wilson(x, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = x / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def shares(items, ra):
    """{set: {"n", "genuine": [0/1], "complete": [0/1]}} from the final pass A labels."""
    out = {s: {"genuine": [], "complete": []} for s in SETS}
    for rid, it in items.items():
        standalone = ra[rid][0]
        out[it["set"]]["genuine"].append(0 if standalone == "not_a_requirement" else 1)
        out[it["set"]]["complete"].append(1 if standalone == "complete" else 0)
    for s in SETS:
        out[s]["n"] = len(out[s]["genuine"])
    return out


def net_gain(g, pop):
    """Estimated (G, L, N8, net) from per-set genuine shares g[set] and set sizes pop (new_only, base_only, base_matched)."""
    G = pop["new_only"] * g["new_only"]
    L = pop["base_only"] * g["base_only"]
    N8 = pop["base_matched"] * g["both"] + L
    return G, L, N8, ((G - L) / N8 if N8 else float("nan"))


def bootstrap_net(sh, pop, resamples=RESAMPLES, seed=SEED):
    rng = np.random.default_rng(seed)
    draws = {s: np.asarray(sh[s]["genuine"], dtype=float) for s in SETS}
    if any(len(v) == 0 for v in draws.values()):
        return float("nan"), float("nan")
    means = {
        s: draws[s][rng.integers(0, len(draws[s]), size=(resamples, len(draws[s])))].mean(axis=1)
        for s in SETS
    }
    G = pop["new_only"] * means["new_only"]
    L = pop["base_only"] * means["base_only"]
    N8 = pop["base_matched"] * means["both"] + L
    net = (G - L) / N8
    lo, hi = np.percentile(net, [2.5, 97.5])
    return float(lo), float(hi)


def diff_interval(a, b, resamples=RESAMPLES, seed=SEED):
    """Bootstrap 95% interval of mean(a) - mean(b) for two 0/1 lists."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    da = a[rng.integers(0, len(a), size=(resamples, len(a)))].mean(axis=1)
    db = b[rng.integers(0, len(b), size=(resamples, len(b)))].mean(axis=1)
    lo, hi = np.percentile(da - db, [2.5, 97.5])
    return float(a.mean() - b.mean()), float(lo), float(hi)


def rate_difference(x1, n1, x2, n2, z=1.96):
    """Wald interval for p1 - p2 (the fragment composite on the 14B survivors against the baseline's)."""
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return p1 - p2, p1 - p2 - z * se, p1 - p2 + z * se


def comparison_totals(new_tag, docs=DOCS):
    """Pooled counts over the documents from compare.py's output files."""
    tot = {
        "new_only": 0,
        "base_only": 0,
        "base_matched": 0,
        "new_matched": 0,
        "base_survivors": 0,
        "new_survivors": 0,
        "base_fragments": 0,
        "new_fragments": 0,
        "chunks": 0,
        "new_lost": 0,
    }
    for doc in docs:
        r = json.loads(
            (_HERE / "outputs" / f"comparison_{doc}_{new_tag}.json").read_text(encoding="utf-8")
        )
        o = r["overlap"]
        tot["new_only"] += o["new_only"]
        tot["base_only"] += o["base_only"]
        tot["base_matched"] += o["base_matched"]
        tot["new_matched"] += o["new_matched"]
        tot["base_survivors"] += r["baseline"]["survivors"]
        tot["new_survivors"] += r["new"]["survivors"]
        tot["base_fragments"] += r["baseline"]["fragment_composite"]
        tot["new_fragments"] += r["new"]["fragment_composite"]
        st = r["new_run"].get("step_c") or {}
        tot["chunks"] += st.get("chunks", 0)
        tot["new_lost"] += st.get("status", {}).get("failed", 0) + st.get("status", {}).get(
            "truncated", 0
        )
    return tot


def net_unique(new_tag, docs=DOCS):
    """(new-only minus base-only) over the baseline survivors, pooled, for one comparison."""
    t = comparison_totals(new_tag, docs)
    return (t["new_only"] - t["base_only"]) / t["base_survivors"]


def evaluate(sh, pop_tot, control_tot, net14, net_control):
    """The five pre-set criteria. Returns (rows, all_pass)."""
    pop = {
        "new_only": pop_tot["new_only"],
        "base_only": pop_tot["base_only"],
        "base_matched": pop_tot["base_matched"],
    }
    g = {s: (sum(sh[s]["genuine"]) / sh[s]["n"]) if sh[s]["n"] else float("nan") for s in SETS}
    G, L, N8, net = net_gain(g, pop)
    lo, hi = bootstrap_net(sh, pop)
    rows = [
        (
            "a",
            f"(G - L) / N8 = {net:+.3f} [{lo:+.3f}, {hi:+.3f}]  (G {G:.0f}, L {L:.0f}, N8 {N8:.0f}); needs >= {GAIN} with the interval above 0",
            net >= GAIN and lo > 0,
        )
    ]
    junk_new = [1 - x for x in sh["new_only"]["genuine"]]
    junk_base = [1 - x for x in sh["base_only"]["genuine"]]
    d, dlo, dhi = diff_interval(junk_new, junk_base)
    rows.append(
        (
            "b",
            f"not-a-requirement share, 14B-only minus 8B-only = {d:+.3f} [{dlo:+.3f}, {dhi:+.3f}]; needs <= {JUNK_MARGIN}",
            d <= JUNK_MARGIN,
        )
    )
    fd, flo, fhi = rate_difference(
        pop_tot["new_fragments"],
        pop_tot["new_survivors"],
        pop_tot["base_fragments"],
        pop_tot["base_survivors"],
    )
    rows.append(
        (
            "c",
            f"fragment composite, 14B minus baseline = {fd:+.3f} [{flo:+.3f}, {fhi:+.3f}]; needs the lower bound <= 0",
            flo <= 0,
        )
    )
    new_loss = pop_tot["new_lost"] / pop_tot["chunks"] if pop_tot["chunks"] else float("nan")
    ctl_loss = (
        control_tot["new_lost"] / control_tot["chunks"] if control_tot["chunks"] else float("nan")
    )
    rows.append(
        (
            "d",
            f"chunks lost (failed or cut off): 14B {new_loss:.3f} vs fresh 8B {ctl_loss:.3f}; needs the 14B no more than {CHUNK_LOSS_MARGIN} above",
            new_loss - ctl_loss <= CHUNK_LOSS_MARGIN,
        )
    )
    rows.append(
        (
            "e",
            f"net unique difference: 14B {net14:+.3f} vs fresh 8B {net_control:+.3f} (of baseline survivors); needs the 14B above it by >= {NOISE_MARGIN}",
            net14 - net_control >= NOISE_MARGIN,
        )
    )
    return rows, all(r[2] for r in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--labels-dir", required=True)
    ap.add_argument("--pack-dir")
    ap.add_argument("--sheet-out")
    ap.add_argument("--answers")
    ap.add_argument("--new", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    sa = load_scorer()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    # The WP-45.1(b) machinery expects a key with a `stem` per item and pass B files; this pack has neither, so give it
    # empty stems and empty pass B files.
    pseudo = {"items": {rid: {"stem": ""} for rid in key["items"]}}
    pseudo_path = Path(args.labels_dir) / "_pseudo_key.json"
    pseudo_path.write_text(json.dumps(pseudo), encoding="utf-8")
    for who in sa.LABELERS:
        (Path(args.labels_dir) / f"labels_{who}_b.jsonl").touch()
    load_args = types.SimpleNamespace(key=str(pseudo_path), labels_dir=args.labels_dir)
    pk, labels = sa.load(load_args)
    a_pairs, b_pairs, dis_a, dis_b = sa.disagreements(pk, labels)
    spot = sa.spot_check_items(a_pairs, b_pairs, dis_a, dis_b)
    lines = [
        f"pass A agreement: {sum(1 for p in a_pairs.values() if sa.a_key(p[0]) == sa.a_key(p[1]))}/{len(a_pairs)}; disagreements {len(dis_a)}; spot-checks {len(spot)}"
    ]
    if args.sheet_out:
        sa.sheet(
            types.SimpleNamespace(
                **{**vars(load_args), "pack_dir": args.pack_dir, "sheet_out": args.sheet_out}
            ),
            pk,
            labels,
            a_pairs,
            b_pairs,
            dis_a,
            dis_b,
            spot,
        )
        lines.append(f"adjudication sheet: {args.sheet_out}")
    if args.answers:
        answers = sa.parse_answers(Path(args.answers))
        ra, _, unresolved, spot_changes, corrections = sa.resolve(
            a_pairs, b_pairs, dis_a, dis_b, spot, answers
        )
        if unresolved:
            sys.exit(f"unresolved disagreements: {unresolved}")
        sh = shares(key["items"], ra)
        pop_tot = comparison_totals(args.new)
        control_tot = comparison_totals(CONTROL_TAG)
        rows, ok = evaluate(sh, pop_tot, control_tot, net_unique(args.new), net_unique(CONTROL_TAG))
        for s in SETS:
            n, x = sh[s]["n"], sum(sh[s]["genuine"])
            lo, hi = wilson(x, n)
            c = sum(sh[s]["complete"])
            lines.append(
                f"{s:9s} n={n:3d} genuine {x}/{n} = {x / n:.2f} [{lo:.2f},{hi:.2f}]  complete {c}/{n} = {c / n:.2f}  junk {n - x}/{n}"
            )
        lines.append(
            f"spot-checks: {len(spot) - len(spot_changes)} of {len(spot)} confirmed; later corrections {len(corrections)}"
        )
        lines += [f"({k}) {'PASS' if p else 'fail'}  {msg}" for k, msg, p in rows]
        lines.append(
            "RESULT: "
            + (
                "14B meaningfully better under the pre-set rule"
                if ok
                else "no demonstrated meaningful improvement under the pre-set rule (not 'no difference')"
            )
        )
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
