#!/usr/bin/env python3
"""PREREG10: classify every F3 row (list item with no lead-in attached) of a processed folder by cause. Read only, no model. Heuristics, spot-read by hand (see PREREG10.md).

    python3 eval/clause_labeling/f3_causes.py --processed-dir DIR [--json OUT]

Causes, first match wins:
  heading     the nearest section heading (skipping page-header junk such as "UNCLASSIFIED") ends in a colon or a modal ("The DoD CIO, shall:")
  further     the finder finds a lead-in when it may look back more than one chunk (all chunks in between in the same section)
  junk_blocked  a lead-in sits at the end of the previous chunk but the page-header junk changed the section path, so the finder did not look
  self_head   the item itself ends with a colon (it heads a sub-list)
  sibling     a colon line earlier in the same chunk exists but the finder rejected it as a sibling of the item
  form        form or letter template with numbered statements
  period      the lead-in is a sentence that ends in a period ("... five basic steps as shown at Figure A4.1.")
  none_junk   nothing governs the item, and the path is page-header junk
  none        nothing governs the item (a standalone lettered or numbered paragraph, a bullet under a plain sentence)
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fragmentation as F  # noqa: E402
from core.artifact_resolver import resolve_latest_requirement_files  # noqa: E402
from pipeline import lead_in as LI  # noqa: E402
from pipeline.clauses import _as_list  # noqa: E402
from services import checklist_service  # noqa: E402

FORM = re.compile(r"^(figure|attachment|appendix|template|sample|memorandum|formal statement)|memorandum for record|\bSUBJECT:", re.I)
FOLLOW = re.compile(r"(following|as follows|below|steps|include)[^.:]{0,80}\.\s*$", re.I)
ORDER = ["heading", "further", "junk_blocked", "self_head", "sibling", "form", "period", "none_junk", "none"]


def _sec(c):
    return (tuple(_as_list(c.get("section_ref_path"))), tuple(_as_list(c.get("section_title_path"))))


def _raw(c):
    return (c or {}).get("raw_text") or (c or {}).get("text") or ""


def classify(rec, chunks):
    cid, start = rec.get("chunk_id"), rec.get("anchor_start")
    ch = chunks.get(cid, {})
    raw = _raw(ch)
    path = _as_list(ch.get("section_title_path"))
    junk = bool(path) and LI.is_junk_heading(path[-1])
    heading = LI.heading_lead_in(path)
    if heading:
        return "heading", junk
    prev = _raw(chunks.get(cid - 1)) if isinstance(cid, int) else ""
    deep = None
    for k in range(1, 9):
        if not isinstance(cid, int) or cid - k not in chunks or _sec(chunks[cid - k]) != _sec(ch):
            break
        if LI.find_lead_in(raw, start, "\n".join(_raw(chunks[cid - j]) for j in range(k, 0, -1))):
            deep = k
            break
    if deep:
        return "further", junk
    if junk and prev and LI.find_lead_in(raw, start, prev):
        return "junk_blocked", junk
    units = [(s, t) for s, t in LI._units(raw) if s <= (start or 0)]
    if units and LI._COLON_END.search(LI._text_of(units[-1][1])):
        return "self_head", junk
    if any(LI._COLON_END.search(LI._text_of(t)) for s, t in units[:-1]):
        return "sibling", junk
    pre = raw[:start] if start else ""
    ctx = (prev[-300:] + "\n" + pre[-300:]) if not pre.strip() else pre[-300:]
    if FORM.search(" ".join(path)) or "SUBJECT:" in raw:
        return "form", junk
    if FOLLOW.search(ctx.strip()):
        return "period", junk
    return ("none_junk" if junk else "none"), junk


def f3_rows(processed: Path):
    files = resolve_latest_requirement_files(processed)
    for key in sorted(files):
        checklist = checklist_service.generate(processed, key, "cybersecurity")
        recs = F._records_by_id(files[key])
        chunks = {}
        for ln in open(files[key].parent / f"{key}_chunks.jsonl", encoding="utf-8"):
            if ln.strip():
                c = json.loads(ln)
                chunks[c["chunk_id"]] = c
        for it in checklist.get("items", []):
            ids = it.get("requirement_ids") or []
            if not ids:
                continue
            rec = recs.get(ids[0], {})
            root = it.get("extracted_quote") or it.get("source_quote", "")
            if F.classify_row(it.get("source_quote", ""), root, rec)["F3"]:
                cause, junk = classify(rec, chunks)
                yield {"doc": key, "chunk_id": rec.get("chunk_id"), "root": root[:120], "cause": cause, "junk_path": junk}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed-dir", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = list(f3_rows(Path(a.processed_dir).expanduser()))
    c = collections.Counter(r["cause"] for r in rows)
    print("F3 rows", len(rows), "| junk path entry", sum(r["junk_path"] for r in rows))
    for k in ORDER:
        print(f"{c[k]:5d}  {k}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
