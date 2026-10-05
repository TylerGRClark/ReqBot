#!/usr/bin/env python3
"""Check a label file against its pack (WP-45.7). Reads only the pack and the label file; standard library only.

  python3 check_labels.py --pack pack_heldout.md --mode heldout --labels labels_<name>_heldout.jsonl
  python3 check_labels.py --pack pack_devkind.md --mode devkind --labels labels_<name>_devkind.jsonl

Exits non-zero and lists every problem if the file is not valid.
"""

import argparse
import json
import re
import sys
from pathlib import Path

LABELS = ("obligation", "lead_in", "scope", "not_obligation")
KINDS = ("obligation", "recommendation", "permission", "prohibition")
PIECE_LINE = re.compile(r"^\[(?P<id>[A-Za-z0-9]+-p\d{3}-\d{3})\] ")


def pack_ids(pack_text):
    """Ids of the pieces to label: lines that start with an id in square brackets, in order."""
    ids = []
    for line in pack_text.splitlines():
        m = PIECE_LINE.match(line)
        if m:
            ids.append(m.group("id"))
    return ids


def check(pack_text, label_lines, mode):
    problems = []
    expected = pack_ids(pack_text)
    seen = {}
    for n, line in enumerate(label_lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError as e:
            problems.append(f"line {n}: not valid JSON ({e})")
            continue
        if not isinstance(rec, dict):
            problems.append(f"line {n}: not a JSON object")
            continue
        pid = rec.get("id")
        if pid in seen:
            problems.append(f"line {n}: duplicate id {pid}")
        seen[pid] = rec
        if not isinstance(rec.get("note", ""), str):
            problems.append(f"{pid}: note must be a string")
        if mode == "heldout":
            if rec.get("label") not in LABELS:
                problems.append(f"{pid}: label {rec.get('label')!r} is not one of {LABELS}")
            if not isinstance(rec.get("segment_ok"), bool):
                problems.append(f"{pid}: segment_ok must be true or false")
            kind = rec.get("kind", "")
            if rec.get("label") == "obligation":
                if kind not in KINDS:
                    problems.append(f"{pid}: an obligation needs a kind from {KINDS}, got {kind!r}")
            elif kind != "":
                problems.append(f"{pid}: kind must be empty unless label is obligation, got {kind!r}")
        else:
            if rec.get("kind") not in KINDS + ("none",):
                problems.append(f"{pid}: kind {rec.get('kind')!r} is not one of {KINDS + ('none',)}")
    missing = [i for i in expected if i not in seen]
    extra = [i for i in seen if i not in set(expected)]
    if missing:
        problems.append(f"{len(missing)} pieces have no label, first: {missing[:5]}")
    if extra:
        problems.append(f"{len(extra)} labels name pieces not in the pack, first: {extra[:5]}")
    return expected, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", required=True)
    ap.add_argument("--mode", choices=("heldout", "devkind"), required=True)
    ap.add_argument("--labels", required=True)
    args = ap.parse_args()
    expected, problems = check(
        Path(args.pack).read_text(encoding="utf-8"),
        Path(args.labels).read_text(encoding="utf-8").splitlines(),
        args.kind_pack_mode,
    )
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print(f"ok: {len(expected)} pieces labeled")


if __name__ == "__main__":
    main()
