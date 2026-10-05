"""Check a labeler's file against the pack: every piece labeled once, only allowed values, required fields present.

Self-contained on purpose (standard library only, reads only pack_a.md and the label file) so a labeler can run it in a
directory that holds just the pack. Exits non-zero and lists every problem found.

  python3 check_labels.py --pack-dir . --a labels_<name>_a.jsonl
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

LABELS = {"obligation", "lead_in", "scope", "not_obligation"}
ID = re.compile(r"^\[([A-Z]+-p\d{3}-\d{3})\] ", flags=re.M)


def piece_ids(path):
    return ID.findall(Path(path).read_text(encoding="utf-8"))


def check(pack_dir, labels_path):
    problems = []
    expected = piece_ids(Path(pack_dir) / "pack_a.md")
    if not expected:
        return [f"{Path(pack_dir) / 'pack_a.md'}: no pieces found"]
    labels = {}
    for n, line in enumerate(Path(labels_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{labels_path} line {n}: not valid JSON ({exc.msg})")
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
            problems.append(f'{labels_path} line {n}: expected an object with a string "id"')
            continue
        if rec["id"] in labels:
            problems.append(f"{rec['id']} appears more than once")
            continue
        labels[rec["id"]] = rec
    for pid in expected:
        rec = labels.get(pid)
        if rec is None:
            problems.append(f"no label for {pid}")
            continue
        if rec.get("label") not in LABELS:
            problems.append(
                f"{pid}: label must be one of {sorted(LABELS)}, got {rec.get('label')!r}"
            )
        if not isinstance(rec.get("segment_ok"), bool):
            problems.append(f"{pid}: segment_ok must be true or false")
        if "note" in rec and not isinstance(rec["note"], str):
            problems.append(f"{pid}: note must be a string")
    for pid in labels:
        if pid not in set(expected):
            problems.append(f"{pid} is not a piece in pack_a.md")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--a", required=True, help="the label file")
    args = ap.parse_args()
    problems = check(args.pack_dir, args.a)
    if problems:
        sys.exit("labels are not valid:\n  " + "\n  ".join(problems))
    counts = collections.Counter(
        json.loads(x)["label"] for x in Path(args.a).read_text().splitlines() if x.strip()
    )
    print("labels are valid:", args.a, dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
