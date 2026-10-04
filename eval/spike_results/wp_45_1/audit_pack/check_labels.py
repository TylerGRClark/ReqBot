"""Check a labeler's files against the pack: every card labeled once, only allowed values, required fields present.

Self-contained on purpose (standard library only, reads only the two pack files and the label files) so a labeler can
run it in a directory that holds just the pack. Exits non-zero and lists every problem found.

  python3 check_labels.py --pack-dir . --a labels_<name>_a.jsonl [--b labels_<name>_b.jsonl]
"""

import argparse
import json
import re
import sys
from pathlib import Path

STANDALONE = {"complete", "needs_lead_in", "not_a_requirement"}
LOCATIONS = {"same_chunk", "previous_chunk", "section_heading", "not_shown"}
TEXT_REQUIRED = {"same_chunk", "previous_chunk", "section_heading"}
VERDICTS = {"right", "wrong_sibling", "fragment_chain", "not_needed", "wrong_other"}


def card_ids(path):
    return re.findall(r"^## (R\d{3})$", Path(path).read_text(encoding="utf-8"), flags=re.M)


def read_labels(path, problems):
    labels = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{path} line {n}: not valid JSON ({exc.msg})")
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
            problems.append(f'{path} line {n}: expected an object with a string "id"')
            continue
        if rec["id"] in labels:
            problems.append(f"{path}: {rec['id']} appears more than once")
            continue
        labels[rec["id"]] = rec
    return labels


def check_pass_a(rec, problems, where):
    s, loc, text = rec.get("standalone"), rec.get("lead_in_location"), rec.get("lead_in_text")
    if s not in STANDALONE:
        problems.append(f"{where}: standalone must be one of {sorted(STANDALONE)}, got {s!r}")
        return
    if s != "needs_lead_in":
        if loc is not None or text is not None:
            problems.append(
                f"{where}: lead_in_location and lead_in_text must be null unless standalone is needs_lead_in"
            )
        return
    if loc not in LOCATIONS:
        problems.append(
            f"{where}: lead_in_location must be one of {sorted(LOCATIONS)}, got {loc!r}"
        )
    elif loc in TEXT_REQUIRED and not (isinstance(text, str) and text.strip()):
        problems.append(f"{where}: lead_in_text is required when lead_in_location is {loc}")
    elif loc == "not_shown" and text is not None:
        problems.append(f"{where}: lead_in_text must be null when lead_in_location is not_shown")


def check_pass_b(rec, problems, where):
    if rec.get("stem_verdict") not in VERDICTS:
        problems.append(
            f"{where}: stem_verdict must be one of {sorted(VERDICTS)}, got {rec.get('stem_verdict')!r}"
        )


def check(pack_dir, a_path, b_path):
    problems = []
    pack_dir = Path(pack_dir)
    for label, path, ids_file, checker in (
        ("pass A", a_path, "pack_a.md", check_pass_a),
        ("pass B", b_path, "pack_b.md", check_pass_b),
    ):
        if path is None:
            continue
        expected = card_ids(pack_dir / ids_file)
        if not expected:
            problems.append(f"{pack_dir / ids_file}: no cards found")
            continue
        labels = read_labels(path, problems)
        for cid in expected:
            if cid not in labels:
                problems.append(f"{label}: no label for {cid}")
            else:
                checker(labels[cid], problems, f"{label} {cid}")
        for cid in labels:
            if cid not in expected:
                problems.append(f"{label}: {cid} is not a card in {ids_file}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--a", required=True, help="pass A label file")
    ap.add_argument("--b", help="pass B label file (after pass B)")
    args = ap.parse_args()
    problems = check(args.pack_dir, args.a, args.b)
    if problems:
        sys.exit("labels are not valid:\n  " + "\n  ".join(problems))
    print("labels are valid:", args.a, args.b or "(pass B not checked)")


if __name__ == "__main__":
    main()
