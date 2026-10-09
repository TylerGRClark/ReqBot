#!/usr/bin/env python3
"""Lead-in attaching by rule (docs/PIPELINE_REDESIGN_PLAN.md, context attaching): how many list items get the line above them that ends in a colon, how that compares with the owner-adjudicated
lead-ins of the earlier gold sets, and a seeded sample for the owner to rate. Re-runs Step D on copies of the newest runs of the 13 reference documents (offline; no model).

  PYTHONPATH=. python3 eval/spike_results/pipeline_redesign/lead_in_report.py
"""
import collections
import glob
import json
import random
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from pipeline import parse_and_normalize as PN  # noqa: E402

DOCS = ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125", "afi10-2402", "afi13-550", "afi17-203", "afman17-2101", "afpd_17-1", "dafman17-1305"]
PROCESSED = Path.home() / "documents" / "processed"
GOLD = ROOT / "eval/spike_results/wp_45_7/outputs"
SEED, N = 4702, 30


def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


def overlap(candidate, gold):
    cw, gw = words(candidate), words(gold)
    return len(cw & gw) / len(cw) if cw else 0.0


def main():
    records, before = {}, {}
    with tempfile.TemporaryDirectory() as tmp_all:
        for doc in DOCS:
            run = Path(sorted(glob.glob(str(PROCESSED / f"{doc}_2026*")))[-1])
            tmp = Path(tmp_all) / doc
            tmp.mkdir()
            for suffix in ("_chunks.jsonl", "_extracted_requirements.jsonl"):
                shutil.copy2(run / f"{doc}{suffix}", tmp)
            records[doc] = read(PN.run(str(tmp / f"{doc}_extracted_requirements.jsonl"), str(tmp / f"{doc}_chunks.jsonl"), str(ROOT / "raw_pdfs" / f"{doc}.pdf"), str(tmp)))
    attached = [(d, r) for d, rs in records.items() for r in rs if any(p["kind"] == "lead_in" and p["origin"] == "rule" for p in r.get("explained_parts", []))]
    glued = sum(1 for rs in records.values() for r in rs if any(p["kind"] == "lead_in" and p["origin"] != "rule" for p in r.get("explained_parts", [])))
    total = sum(len(rs) for rs in records.values())
    per_doc = collections.Counter(d for d, _ in attached)

    # the owner-adjudicated gold: records labeled "needs a lead-in" (with the lead-in text and where it is) and "complete" (stands alone)
    gold_rows = []
    for name in ("resolver_gold.json", "fresh_gold.json"):
        gold_rows += json.loads((GOLD / name).read_text(encoding="utf-8"))["gold"]
    outcome = collections.Counter()
    detail = []
    for g in gold_rows:
        if g["document"] not in records or g.get("standalone") not in ("needs_lead_in", "complete"):
            continue
        q = " ".join((g["quote"] or "").split()).lower()[:60]
        rec = next((r for r in records[g["document"]] if q and q in " ".join((r["source_quote"] + " " + r.get("explained_text", "")).split()).lower()), None)
        if rec is None:
            outcome["gold record not found in the new run"] += 1
            continue
        lead = next((p["text"] for p in rec.get("explained_parts", []) if p["kind"] == "lead_in"), None)
        if g["standalone"] == "complete":
            outcome["complete: a lead-in was attached (wrong)" if lead else "complete: none attached (right)"] += 1
        elif g.get("lead_in_text") in (None, "None"):
            continue
        else:
            where = g.get("lead_in_location") or "?"
            key = f"needs a lead-in, in {where}"
            if lead and overlap(lead, g["lead_in_text"]) >= 0.8:
                outcome[f"{key}: the adjudicated lead-in was attached"] += 1
            elif lead:
                outcome[f"{key}: a different lead-in was attached"] += 1
                detail.append((g["document"], g["quote"][:80], lead[:100], g["lead_in_text"][:100]))
            else:
                outcome[f"{key}: none attached"] += 1
    report = {"records": total, "lead_in_attached_by_rule": len(attached), "lead_in_already_glued_by_the_model": glued, "per_document": dict(per_doc), "against_the_adjudicated_gold": dict(sorted(outcome.items())),
              "different_lead_in_examples": detail[:12]}
    out_dir = Path(__file__).resolve().parent / "outputs"
    (out_dir / "lead_in_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    picked = sorted(random.Random(SEED).sample(sorted(attached, key=lambda t: (t[0], t[1]["requirement_id"])), min(N, len(attached))), key=lambda t: (t[0], t[1]["requirement_id"]))
    lines = [f"# Lead-ins attached by rule — {len(picked)} rows (seeded sample of {len(attached)} rows that got one)", "",
             "For each row: the **item** as it reads without a lead-in, the **lead-in** the rule found (the nearest earlier line that ends in a colon), and the **result**.",
             "Rate each: **right** (that line governs this item and the result reads better) / **neutral** (right line, no real gain) / **wrong** (that line does not govern this item, or it makes the row confusing).", ""]
    for n, (doc, r) in enumerate(picked, 1):
        lead = next(p["text"] for p in r["explained_parts"] if p["kind"] == "lead_in")
        item = next(p["text"] for p in r["explained_parts"] if p["kind"] == "sentence")
        lines += [f"## {n}. {doc} — {r.get('source_ref') or '(no ref)'}", "", f"**Item:** {item}", "", f"**Lead-in found:** {lead}", "", f"**Result:** {r['explained_text']}", "", "**Rating:** ", "", "---", ""]
    (out_dir / "lead_in_rating_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "different_lead_in_examples"}, indent=1))
    for d in detail[:8]:
        print("DIFFERENT:", d)


if __name__ == "__main__":
    main()
