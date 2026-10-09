#!/usr/bin/env python3
"""WP-45.12: score the arms by the rules of docs/PHASE45_WP4512_PLAN.md (offline; reads scratch ledgers, calls nothing).

  PYTHONPATH=. python3 analyze.py            # writes outputs/wp4512_report.json and outputs/afi17-203_additions_rating_sheet.md

1. Labeled development pages: recall of the 74 owner-adjudicated obligations and precision (WP-45.7 `score_discovery.score_run`) for D0, D1 (the committed WP-45.7 repeats) and P1 (two repeats);
   a gate counts as met only if it holds in both repeats; the F1 that ranks arms is the mean of the two repeats' F1.
2. AFI 17-203: the share of paragraph units covered by a candidate, per arm, and the units covered by one arm only.
3. The seeded sample of 40 additions (covered by P1 or D1, not by D0) for the owner's rating.
"""
import collections
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_7", _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
    sys.path.insert(0, str(_p))

import ollama_run as OR  # noqa: E402
import p1 as P  # noqa: E402
import run_discovery as RD  # noqa: E402
import score_discovery as SD  # noqa: E402

from services import checklist_audit as A  # noqa: E402
from services import checklist_missed as M  # noqa: E402

S12 = Path.home() / "wp45_12_scratch"
S7 = Path.home() / "wp45_7_scratch"
DOC = "afi17-203"
SEED, SAMPLE = 4512, 40
RUNS = {"D0": [S7 / "d0_8b_dev_r1", S7 / "d0_8b_dev_r2"], "D1": [S7 / "d1_8b_dev_r1", S7 / "d1_8b_dev_r2"], "P1": [S12 / "p1_dev_r1", S12 / "p1_dev_r2"]}
MIN_COVER = 25


def f1(recall, precision):
    return round(2 * recall * precision / (recall + precision), 4) if recall and precision else 0.0


def dev_scores():
    final, index, obligations, pages = SD.load_dev_labels()
    out = {}
    for arm, dirs in RUNS.items():
        reps = []
        for d in dirs:
            r = SD.score_run(d, final, index, obligations, pages)
            r.pop("traces")
            n = len(obligations)
            recall = r["recall"]["count"] / n if isinstance(r["recall"], dict) and "count" in r["recall"] else None
            prec = SD.precision_rate(r["precision"])
            reps.append({"run": d.name, "recall": r["recall"], "recall_share": recall, "precision": r["precision"], "precision_rate": prec, "records": r["records"], "status": r["status"]})
        out[arm] = reps
    return out


def quotes_of(arm_label):
    ledger = OR.Ledger(S12 / arm_label / "discovery.jsonl")
    return [M.normalize(rec["source_quote"]) for _doc, rec in RD.extracted_records(ledger)]


def afi_coverage():
    chunks = P.afi_chunks(DOC)
    seen, units = set(), []
    for _d, chunk in chunks:
        for unit, quote, ref in P.units_of(chunk, seen):
            units.append({"unit": unit, "norm": M.normalize(unit), "quote": quote, "ref": ref, "chunk_id": chunk["chunk_id"], "page": chunk.get("page_start"), "path": chunk.get("section_title_path") or []})
    arms = {"D0": quotes_of(f"d0_{DOC}"), "D1": quotes_of(f"d1_{DOC}"), "P1": quotes_of(f"p1_{DOC}")}
    covered = {a: {i for i, u in enumerate(units) if any(len(q) >= MIN_COVER and (q in u["norm"] or u["norm"] in q) for q in qs)} for a, qs in arms.items()}
    return units, arms, covered


def sample_sheet(units, covered):
    pool = sorted((covered["P1"] | covered["D1"]) - covered["D0"])
    picked = sorted(random.Random(SEED).sample(pool, min(SAMPLE, len(pool))))
    lines = [f"# WP-45.12 — additions to rate ({len(picked)} of {len(pool)} units covered by P1 or D1 and not by D0, seeded sample)", "",
             "Rate each: **requirement** (an auditor would want it on the sheet) / **partial** (a requirement, but cut or merged oddly) / **not a requirement**.", ""]
    for n, i in enumerate(picked, 1):
        u = units[i]
        arms = [a for a in ("P1", "D1") if i in covered[a]]
        lines += [f"## {n}. {u['ref'] or '(no number)'} — p. {u['page']}", "", f"**Heading:** {(u['path'] or ['—'])[-1]}  ", f"**Found by:** {', '.join(arms)}  ", "", f"> {u['unit'][:900]}", "", "**Rating:** ", "", "---", ""]
    return "\n".join(lines) + "\n", picked, pool


def duty_looking(u):
    """A crude, rule-based guess (a modal word, or an imperative or third-person verb opener) used only to size what both prompts miss; it labels nothing."""
    import re
    fw = A._first_word(u["unit"])
    return bool(re.search(r"\b(shall|must|will|should|may|required|responsible)\b", u["unit"], re.IGNORECASE)) or A._is_verb(fw, A.IMPERATIVE_VERBS)


def d1_sheet(units, covered):
    ids = sorted(covered["D1"] - covered["D0"])
    lines = [f"# WP-45.12 — AFI 17-203: the {len(ids)} units D1 covers and the current prompt (D0) does not", "",
             "Rate each: **requirement** (an auditor would want it on the sheet) / **partial** / **not a requirement**.", ""]
    for n, i in enumerate(ids, 1):
        u = units[i]
        lines += [f"## {n}. {u['ref'] or '(no number)'} — p. {u['page']}", "", f"**Heading:** {(u['path'] or ['—'])[-1]}  ", "", f"> {u['unit'][:900]}", "", "**Rating:** ", "", "---", ""]
    return "\n".join(lines) + "\n", ids


def main():
    report = {"dev": dev_scores()}
    units, arms, covered = afi_coverage()
    n = len(units)
    sheet, picked, pool = sample_sheet(units, covered)
    report["afi17-203"] = {"units": n, "candidates": {a: len(q) for a, q in arms.items()}, "covered": {a: len(c) for a, c in covered.items()},
                           "covered_share": {a: round(len(c) / n, 3) for a, c in covered.items()},
                           "only_this_arm": {a: len(covered[a] - set().union(*(covered[b] for b in covered if b != a))) for a in covered},
                           "additions_vs_D0": {"P1_or_D1_not_D0": len(pool), "P1_not_D0": len(covered["P1"] - covered["D0"]), "D1_not_D0": len(covered["D1"] - covered["D0"])},
                           "sample_ids": picked}
    both_miss = [i for i in range(n) if i not in covered["D0"] and i not in covered["D1"]]
    report["afi17-203"]["uncovered_by_D0_and_D1"] = {"units": len(both_miss), "duty_looking_by_crude_rule": sum(1 for i in both_miss if duty_looking(units[i]))}
    report["afi17-203"]["D1_quotes_matching_no_unit"] = sum(1 for q in arms["D1"] if not any(len(q) >= MIN_COVER and (q in u["norm"] or u["norm"] in q) for u in units))
    sheet_d1, d1_ids = d1_sheet(units, covered)
    report["afi17-203"]["D1_additions_units"] = d1_ids
    out = _HERE / "outputs"
    out.mkdir(exist_ok=True)
    (out / "afi17-203_D1_additions_rating_sheet.md").write_text(sheet_d1, encoding="utf-8")
    (out / "wp4512_report.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    (out / "afi17-203_additions_rating_sheet.md").write_text(sheet, encoding="utf-8")
    print(json.dumps(report["afi17-203"], indent=1))
    for arm, reps in report["dev"].items():
        for r in reps:
            print(arm, r["run"], "recall", r["recall"] if not isinstance(r["recall"], dict) else {k: r["recall"][k] for k in list(r["recall"])[:3]}, "precision", r["precision_rate"], "records", r["records"])


if __name__ == "__main__":
    main()
