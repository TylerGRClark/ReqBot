#!/usr/bin/env python3
"""WP-45.13: score the D1x arm by the rules of docs/PHASE45_WP4513_PLAN.md (offline; reads scratch arms, calls nothing).

  PYTHONPATH=. python3 eval/spike_results/wp_45_13/analyze_d1x.py

R1/R3 from `score_arms` (recall of the 74, paired losses against the two replicates T2a and T2b), R2's seeded sample of added survivors for the owner's rating, R4's list of losses, and the reported
(never gating) figures: Step D failure codes, survivors per document, AFI 17-203 paragraph coverage and checklist hint counts for the three AFIs.
"""
import collections
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_11", _ROOT / "eval/spike_results/wp_45_12", _ROOT / "eval/spike_results/wp_45_7"):
    sys.path.insert(0, str(_p))

import analyze_t3 as T3  # noqa: E402  (wp_45_11: survivors, validate, find_chunk)
import p1 as P  # noqa: E402  (wp_45_12: the paragraph units)
import r2_sample as R2  # noqa: E402  (wp_45_11: the absent-from-both-replicates pools)
import score_arms as SA  # noqa: E402

from services import checklist_audit as A  # noqa: E402
from services import checklist_missed as M  # noqa: E402
from services.checklist_service import generate  # noqa: E402

BASE = ("T2a", "T2b")
ARM = "D1x"
SEED, SAMPLE = 4513, 40
SCRATCH = Path.home() / "reqbot-work/scratch/wp45_11_scratch"
# The trial changes the Step C prompt on purpose. The baseline replicates ran at cc0b67e; the trial branch is main at f7cb892 plus that one change, and main moved on in between only in the
# checklist's presentation code (the four files below, which Step C/D and the parent-stem reconstruction never import). They are declared here so the same-code check is not simply switched off.
CODE = ["pipeline/llm_extract_requirements.py", "pipeline/checklist_export.py", "services/checklist_audit.py", "services/checklist_missed.py", "services/checklist_service.py"]


def rules(report):
    arms, pairs = report["arms"], report["pairs"]
    found = {a: arms[a]["recall"]["extracted_covered"] for a in arms}
    ids = lambda k, side: {x["id"] for x in pairs[k]["recall_extracted"][side]}  # noqa: E731
    lost_both = ids(f"{BASE[0]} vs {ARM}", "only_first") & ids(f"{BASE[1]} vs {ARM}", "only_first")
    gained_both = ids(f"{BASE[0]} vs {ARM}", "only_second") & ids(f"{BASE[1]} vs {ARM}", "only_second")
    limit = max(len(ids(f"{BASE[0]} vs {BASE[1]}", "only_first")), len(ids(f"{BASE[0]} vs {BASE[1]}", "only_second"))) + 2
    low, high = min(found[b] for b in BASE), max(found[b] for b in BASE)
    return {"found": found, "R1": {"found_at_least_lower_minus_2": found[ARM] >= low - 2, "paired_losses": sorted(lost_both), "paired_loss_limit": limit,
                                   "paired_losses_within_limit": len(lost_both) <= limit},
            "R3": {"found_at_least_higher_plus_6": found[ARM] >= high + 6, "higher_replicate": high, "gained_over_both": sorted(gained_both)},
            "survivors": {a: arms[a]["totals"]["survivors"] for a in arms}}


def added_survivors():
    docs = sorted(SA.common.pinned_documents())
    recs = {a: {d: T3.survivors(a, d) for d in docs} for a in (*BASE, ARM)}
    quotes = {a: {d: [T3.AC.norm(r.get("source_quote") or "") for r in recs[a][d]] for d in docs} for a in recs}
    pools = R2.pools(quotes[BASE[0]], quotes[BASE[1]], quotes[ARM])
    flat = [(d, q) for d, (_both, new) in pools.items() for q in new]
    chunk_of = {d: {T3.AC.norm(r.get("source_quote") or ""): r.get("chunk_id") for r in recs[ARM][d]} for d in docs}
    original = {d: {T3.AC.norm(r.get("source_quote") or ""): r.get("source_quote") for r in recs[ARM][d]} for d in docs}  # the quote as written, for the owner's sheet
    return flat, chunk_of, original


def _window(passage, radius=900):
    """The whole passage when it is short; otherwise the stretch around the marked quote (marked >> <<), with an ellipsis where text was cut, so the owner always sees the context."""
    if len(passage) <= 2 * radius:
        return passage
    i = passage.find(">>")
    i = 0 if i < 0 else i
    a, b = max(0, i - radius), min(len(passage), i + radius)
    return ("... " if a else "") + passage[a:b] + (" ..." if b < len(passage) else "")


def sheet(flat, chunk_of, original):
    picked = flat if len(flat) <= SAMPLE else sorted(random.Random(SEED).sample(sorted(flat), SAMPLE))
    lines = [f"# WP-45.13 — D1x survivors absent from both baseline runs ({len(picked)} of {len(flat)}, seeded sample)", "",
             "Rate each: **requirement** (an auditor would want it on the sheet) / **partial** / **not a requirement**.", ""]
    cache = {}
    for n, (doc, quote) in enumerate(sorted(picked), 1):
        if doc not in cache:
            chunks = {c["chunk_id"]: c for c in (json.loads(x) for x in (SCRATCH / ARM / doc / f"{doc}_chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
            cache[doc] = chunks
        chunk = cache[doc].get(chunk_of[doc].get(quote))
        passage, _found = A.build_passage(original[doc].get(quote, quote), chunk) if chunk else ("", False)
        lines += [f"## {n}. {doc} — chunk {chunk_of[doc].get(quote)}", "", f"**Heading:** {((chunk or {}).get('section_title_path') or ['—'])[-1]}  ", "", f"> {original[doc].get(quote, quote)}", "",
                  "**Passage:**", "", "    " + (_window(passage).replace("\n", "\n    ") or "(not located)"), "", "**Rating:** ", "", "---", ""]
    return "\n".join(lines) + "\n", len(picked)


def checklist_counts(arm):
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for doc in ("afi17-203", "afi13-550", "afi10-2402"):
            run = Path(tmp) / f"{doc}_20260101_000000"
            run.mkdir()
            for f in (SCRATCH / arm / doc).iterdir():  # rglob does not follow a symlinked directory, so link the files
                (run / f.name).symlink_to(f)
            r = generate(Path(tmp), doc, "cybersecurity")
            out[doc] = {"rows": len(r["items"]), "possible_missed": len(r["possible_missed"]), "flags": dict(collections.Counter(f for i in r["items"] for f in i["item_flags"]))}
    return out


def afi_unit_coverage(arm):
    seen, units = set(), []
    for _d, chunk in P.afi_chunks("afi17-203"):
        for unit, _quote, _ref in P.units_of(chunk, seen):
            units.append(M.normalize(unit))
    qs = [T3.AC.norm(r.get("source_quote") or "") for r in T3.survivors(arm, "afi17-203")]
    covered = sum(1 for u in units if any(len(q) >= 25 and (q in u or u in q) for q in qs))
    return {"units": len(units), "covered": covered}


def main():
    out = _HERE / "outputs"
    out.mkdir(exist_ok=True)
    done = subprocess.run([sys.executable, str(_ROOT / "eval/spike_results/wp_45_11/score_arms.py"), "--arms", *BASE, ARM, "--allow-code-diff", *CODE, "--out", "../wp_45_13/outputs/d1x_arms_report.json"],
                          capture_output=True, text=True, cwd=_ROOT / "eval/spike_results/wp_45_11")
    if done.returncode != 0:  # show why the scorer refused (a missing arm, a failed chunk, different model or code), not just that it did
        sys.exit(f"score_arms.py failed:\n{done.stdout}\n{done.stderr}")
    report = json.loads((out / "d1x_arms_report.json").read_text(encoding="utf-8"))
    result = rules(report)
    flat, chunk_of, original = added_survivors()
    text, n = sheet(flat, chunk_of, original)
    (out / "d1x_additions_rating_sheet.md").write_text(text, encoding="utf-8")
    result["R2"] = {"added_survivors_absent_from_both_replicates": len(flat), "sampled_for_the_owner": n,
                    "survivors_vs_lower_base": round(result["survivors"][ARM] / min(result["survivors"][b] for b in BASE), 3),
                    "owner_rating": "pending: outputs/d1x_additions_rating_sheet.md"}
    result["step_d_failure_codes"] = {a: report["arms"][a]["failure_codes"] for a in report["arms"]}
    result["survivors_per_document"] = {d: {a: report["arms"][a]["per_document"][d]["survivors"] for a in report["arms"]} for d in report["arms"][ARM]["per_document"]}
    result["afi17-203_unit_coverage"] = {a: afi_unit_coverage(a) for a in (*BASE, ARM)}
    result["checklist_hints"] = {a: checklist_counts(a) for a in (BASE[0], ARM)}
    (out / "d1x_report.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("found", "R1", "R3", "R2", "survivors")}, indent=1))


if __name__ == "__main__":
    main()
