#!/usr/bin/env python3
"""Fragmentation counts for the checklist rows of every library document (read only, no model).

Run before and after a change to how requirements are found, to see whether the rows got
more whole. For each document it builds the checklist the normal way (checklist_service.generate)
and counts, over the rows that came from the requirements file:

  F1  rows
  F2  shown text starts mid-sentence (first letter is lower case, after any bullet, list label or paragraph number)
  F3  list scraps: the root is a list item (bullet, "(a)", "1)" label) and no lead-in is attached
  F4  short lower-case scraps: mid-sentence and under 60 characters
  F5  table-line rows: shown text contains a pipe
  F6  shown text that is not a complete sentence (pipeline.sentence_expand.is_complete)
  F7  rows under 5 words
  F8  root not exactly located (anchor_status other than "exact"; a record with none counts)
  F9  rows with a lead-in attached (explained_parts has a lead_in)

(The text scan and its F10 columns were removed with the scan; fragmentation_before_2026-10-22.json
still carries them as a historical record and nothing reads it.)

"Shown text" is what the sheet shows (the explained text when the record has one, else the
root); "root" is the record's source_quote.

    python3 eval/clause_labeling/fragmentation.py [--processed-dir DIR] [--doc KEY] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.artifact_resolver import resolve_latest_requirement_files  # noqa: E402
from pipeline.sentence_expand import is_complete  # noqa: E402
from services import checklist_audit, checklist_service  # noqa: E402

COUNT_KEYS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]
_BULLET = re.compile(r"^\s*[-\u2022\u2013*]\s+")
SHORT_SCRAP_CHARS = 60
SHORT_ROW_WORDS = 5


def strip_label(text: str) -> str:
    """The text without its leading bullet, list label ("(a)", "1)") or paragraph number ("2.3.1."), so "(a) Notify" is not read as starting in lower case."""
    text = _BULLET.sub("", text or "", count=1)
    text = checklist_audit._LIST_MARKER.sub("", text, count=1)
    return checklist_audit._PARAGRAPH_NUMBER.sub("", text, count=1)


def is_list_item(text: str) -> bool:
    return bool(_BULLET.match(text or "")) or checklist_audit.has_list_marker(text)


def classify_row(shown: str, root: str, record: dict) -> dict:
    """Which of F2 to F9 apply to one row. `record` is the requirements record (may be empty)."""
    shown = (shown or "").strip()
    root = (root or "").strip()
    parts = record.get("explained_parts") or []
    lead_in = any(p.get("kind") == "lead_in" for p in parts)
    mid = checklist_audit.starts_mid_sentence(strip_label(shown))
    return {
        "F2": mid,
        "F3": is_list_item(root) and not lead_in,
        "F4": mid and len(shown) < SHORT_SCRAP_CHARS,
        "F5": "|" in shown,
        "F6": not is_complete(shown),
        "F7": len(shown.split()) < SHORT_ROW_WORDS,
        "F8": record.get("anchor_status") != "exact",
        "F9": lead_in,
    }


def _records_by_id(jsonl_path: Path) -> dict:
    out = {}
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("requirement_id"):
                out[rec["requirement_id"]] = rec
    return out


def count_document(checklist: dict, records: dict) -> dict:
    """Counts for one checklist envelope. Rows without a requirement id are skipped."""
    counts = {k: 0 for k in COUNT_KEYS}
    for item in checklist.get("items", []):
        ids = item.get("requirement_ids") or []
        if not ids:
            continue
        record = records.get(ids[0], {})
        root = item.get("extracted_quote") or item.get("source_quote", "")
        flags = classify_row(item.get("source_quote", ""), root, record)
        counts["F1"] += 1
        for k, v in flags.items():
            counts[k] += int(v)
    return counts


def run(processed_dir: Path, doc: str | None = None, profile: str = "cybersecurity") -> dict:
    files = resolve_latest_requirement_files(processed_dir)
    keys = [doc] if doc else sorted(files)
    per_doc = {}
    for key in keys:
        if key not in files:
            raise ValueError(f"No requirements file for document '{key}' in {processed_dir}")
        checklist = checklist_service.generate(processed_dir, key, profile)
        per_doc[key] = count_document(checklist, _records_by_id(files[key]))
    totals = {k: sum(d[k] for d in per_doc.values()) for k in COUNT_KEYS}
    return {"documents": per_doc, "totals": totals}


def format_table(result: dict) -> str:
    cols = COUNT_KEYS
    width = max([len(k) for k in result["documents"]] + [6, len("TOTAL")])
    lines = ["  ".join([f"{'document':<{width}}"] + [f"{c:>6}" for c in cols])]
    for key, d in list(result["documents"].items()) + [("TOTAL", result["totals"])]:
        lines.append("  ".join([f"{key:<{width}}"] + [f"{d[c]:>6}" for c in cols]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--processed-dir", default=None, help="default: processed_dir from the config")
    ap.add_argument("--doc", default=None, help="one document key (default: every library document)")
    ap.add_argument("--profile", default="cybersecurity")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)
    if args.processed_dir:
        processed = Path(args.processed_dir).expanduser().resolve()
    else:
        from core import config
        processed = config.load().processed_dir_path()
    try:
        result = run(processed, args.doc, args.profile)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else format_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
