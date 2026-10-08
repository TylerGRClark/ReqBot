#!/usr/bin/env python3
"""WP-46.3: how often the parent paragraph read from an AFI's own numbering equals the owner-adjudicated lead-in (offline; no model).

  PYTHONPATH=. python3 eval/spike_results/wp_46_3/score_parent_paragraph.py

Items: the AFI records labeled "needs a lead-in" with adjudicated lead-in text in `wp_45_7/outputs/resolver_gold.json` (dev half and evaluation half) and `fresh_gold.json`.
For each: the parent paragraph (`checklist_audit.parent_paragraph`, from the pinned chunk files' text and headings) and the H3 "applies to" heading are compared with the lead-in
text under the WP-45.7 overlap rule (`score_resolver.overlaps`: at least 80% of the value's distinctive words are in the lead-in text). Exploratory: 25 items on three AFIs, one
labeler, and the numbering rule was written before this was run but not tuned on these items. Nothing is tuned or selected from the result.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "eval/spike_results/wp_45_7", ROOT / "eval/spike_results/wp_45_audit"):
    sys.path.insert(0, str(p))

import _inputs  # noqa: E402
import score_resolver as SR  # noqa: E402

from services import checklist_audit as A  # noqa: E402
from services import checklist_missed as M  # noqa: E402


def main():
    corpus = _inputs.corpus_inputs("normalized", "chunks")
    cache, rows = {}, []
    for name in ("resolver_gold.json", "fresh_gold.json"):
        for g in json.loads((ROOT / "eval/spike_results/wp_45_7/outputs" / name).read_text(encoding="utf-8"))["gold"]:
            if not (g["document"].startswith("afi") and g.get("standalone") == "needs_lead_in" and g.get("lead_in_text") not in (None, "None")):
                continue
            doc = g["document"]
            if doc not in cache:
                chunks = [json.loads(x) for x in Path(corpus[doc]["chunks"]).read_text(encoding="utf-8").splitlines() if x.strip()]
                units = []
                for c in chunks:
                    units += [str(p) for p in (c.get("section_title_path") or [])] + M.paragraph_units(c["raw_text"])
                recs = {json.loads(x)["requirement_id"]: json.loads(x) for x in Path(corpus[doc]["normalized"]).read_text(encoding="utf-8").splitlines() if x.strip()}
                cache[doc] = (A.paragraph_map(units), recs)
            pm, recs = cache[doc]
            rec = recs.get(g["requirement_id"]) or {}
            ref = rec.get("source_ref", "")
            pref, ptext = A.parent_paragraph(ref, pm)
            applies = A.applies_to(rec.get("section_title_path"))
            rows.append({"set": name[:5], "document": doc, "candidate_id": g["candidate_id"], "source_ref": ref, "lead_in_location": g["lead_in_location"], "gold_lead_in": g["lead_in_text"],
                         "parent_ref": pref, "parent_text": ptext, "applies_to": applies,
                         "parent_matches": bool(ptext) and SR.overlaps(ptext, g["lead_in_text"]), "applies_matches": bool(applies) and SR.overlaps(applies, g["lead_in_text"])})
    summary = {"items": len(rows), "parent_found": sum(1 for r in rows if r["parent_ref"]), "parent_matches_lead_in": sum(r["parent_matches"] for r in rows),
               "applies_to_matches_lead_in": sum(r["applies_matches"] for r in rows), "either_matches": sum(r["parent_matches"] or r["applies_matches"] for r in rows)}
    out = Path(__file__).resolve().parent / "outputs" / "parent_paragraph_scores.json"
    out.write_text(json.dumps({"summary": summary, "items": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
