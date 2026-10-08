#!/usr/bin/env python3
"""WP-46.3: how often the parent paragraph read from an AFI's own numbering equals the owner-adjudicated lead-in (offline; no model).

  PYTHONPATH=. python3 eval/spike_results/wp_46_3/score_parent_paragraph.py

Scoring (docs/PHASE46_REQUIREMENTS.md section 2, WP-46.3): one rule for every predictor. A value counts as RIGHT only if it overlaps the adjudicated lead-in text under the
WP-45.7 rule (`score_resolver.overlaps`: at least 80% of its distinctive words are in the lead-in text) **and** names a party or a governing clause (a modal word, a colon at the
end, an acronym, or a role word such as Director, Chief, Commander, Wing, MAJCOM). The original, looser score (overlap alone) is reported beside it. For records labeled
"complete" (a sentence that stands alone) any shown parent counts as misleading; for "needs a lead-in" records a parent that does not match counts as misleading when shown and
as none when absent. The sets are kept apart: development = the resolver gold's selection half, consumed earlier = its evaluation half, test = the fresh gold. 25 + 12 AFI
records on three documents, one labeler; exploratory. The "applies to" figures are for the number-based rule of WP-46.6, which I adjusted after reading a first run of this
same script (numbered lead-in paragraphs became titles; a dotted row no longer falls back to the converter's path), so on these 37 records they are development numbers, not held-out.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "eval/spike_results/wp_45_7", ROOT / "eval/spike_results/wp_45_audit"):
    sys.path.insert(0, str(p))

import _inputs  # noqa: E402
import score_resolver as SR  # noqa: E402

from services import checklist_audit as A  # noqa: E402
from services import checklist_missed as M  # noqa: E402
from services import checklist_service as CS  # noqa: E402

_MODAL = re.compile(r"\b(shall|must|will|should|may|required|are to|is to)\b", re.IGNORECASE)
_ACRONYM = re.compile(r"\b[A-Z]{2,}[A-Za-z0-9/&-]*")
_ROLE = re.compile(r"\b(director|chief|commander|secretary|officer|council|board|wing|squadron|group|center|centre|directorate|command|agency|office|unit|MAJCOM|FOA|DRU)s?\b", re.IGNORECASE)


def names_party_or_clause(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and (value.endswith(":") or bool(_MODAL.search(value)) or bool(_ACRONYM.search(value)) or bool(_ROLE.search(value)))


def sets(name: str, g: dict) -> str:
    if name == "fresh_gold.json":
        return "test (fresh gold)"
    return "development (resolver gold, selection half)" if g.get("half") == "selection" else "consumed earlier (resolver gold, evaluation half)"


def main():
    corpus = _inputs.corpus_inputs("normalized", "chunks")
    cache, rows = {}, []
    for name in ("resolver_gold.json", "fresh_gold.json"):
        for g in json.loads((ROOT / "eval/spike_results/wp_45_7/outputs" / name).read_text(encoding="utf-8"))["gold"]:
            if not g["document"].startswith("afi") or g.get("standalone") not in ("needs_lead_in", "complete"):
                continue
            if g["standalone"] == "needs_lead_in" and g.get("lead_in_text") in (None, "None"):
                continue
            doc = g["document"]
            if doc not in cache:
                chunks = [json.loads(x) for x in Path(corpus[doc]["chunks"]).read_text(encoding="utf-8").splitlines() if x.strip()]
                units = []
                for c in chunks:
                    units += [str(p) for p in (c.get("section_title_path") or [])] + M.paragraph_units(c["raw_text"])
                recs = {json.loads(x)["requirement_id"]: json.loads(x) for x in Path(corpus[doc]["normalized"]).read_text(encoding="utf-8").splitlines() if x.strip()}
                cache[doc] = (A.paragraph_map(units), recs, CS._heading_map({c["chunk_id"]: c for c in chunks}))
            pm, recs, hmap = cache[doc]
            rec = recs.get(g["requirement_id"]) or {}
            ref = rec.get("source_ref", "")
            pref, ptext = A.parent_paragraph(ref, pm)
            cite = A.citation(ref, "", rec.get("section_title_path"), rec.get("source_quote", ""))
            numbered = A.applies_to_numbered(cite, hmap, rec.get("section_title_path"))  # WP-46.6: who the row applies to is read from the numbering when the row has a dotted number
            applies = numbered if numbered is not None else A.applies_to(rec.get("section_title_path"))
            lead = g["lead_in_text"] if g["standalone"] == "needs_lead_in" else ""

            def score(value):
                if g["standalone"] == "complete":
                    return {"shown": bool(value), "strict_right": not value, "loose_right": not value, "misleading": bool(value)}
                loose = bool(value) and SR.overlaps(value, lead)
                strict = loose and names_party_or_clause(value)
                return {"shown": bool(value), "strict_right": strict, "loose_right": loose, "misleading": bool(value) and not strict}

            rows.append({"set": sets(name, g), "label": g["standalone"], "document": doc, "candidate_id": g["candidate_id"], "source_ref": ref, "gold_lead_in": lead,
                         "parent_ref": pref, "parent_text": ptext, "applies_to": applies, "parent": score(ptext), "applies": score(applies),
                         "either_strict": score(ptext)["strict_right"] or score(applies)["strict_right"]})
    summary = {}
    for s in sorted({r["set"] for r in rows}):
        for label in ("needs_lead_in", "complete"):
            sub = [r for r in rows if r["set"] == s and r["label"] == label]
            if sub:
                summary[f"{s} | {label}"] = {
                    "records": len(sub),
                    "parent_shown": sum(r["parent"]["shown"] for r in sub), "parent_strict_right": sum(r["parent"]["strict_right"] for r in sub),
                    "parent_loose_right": sum(r["parent"]["loose_right"] for r in sub), "parent_misleading_shown": sum(r["parent"]["misleading"] for r in sub),
                    "applies_shown": sum(r["applies"]["shown"] for r in sub), "applies_strict_right": sum(r["applies"]["strict_right"] for r in sub),
                    "applies_misleading_shown": sum(r["applies"]["misleading"] for r in sub), "either_strict_right": sum(r["either_strict"] for r in sub)}
    out = Path(__file__).resolve().parent / "outputs" / "parent_paragraph_scores.json"
    out.write_text(json.dumps({"summary": summary, "items": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
