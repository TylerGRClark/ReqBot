#!/usr/bin/env python3
"""Compare a larger-chunk arm with control, clause by clause (PREREG6 metric 8 and the lost/added rows). Read only, no model.

A clause is matched across arms by its text (letters and digits only) and its n-th occurrence in the document. "Flips" are matched clauses whose label differs.
Rows lost / added are requirement rows (not NOT_REQUIREMENT clauses) whose text has no match among the other arm's rows, by the same text key.

    python3 eval/clause_labeling/chunk_size_compare.py --root ~/reqbot-work/scratch/chunk_size [--list N]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.clauses import chunk_clauses  # noqa: E402
import chunk_size_metrics as M  # noqa: E402


def labeled_clauses(d: Path, doc: str) -> dict:
    """{(text key, n-th occurrence): (label, clause text)} over the document, from the arm's chunks and its batch ledger."""
    chunks = M._jsonl(d / f"{doc}_chunks.jsonl")
    labels = {}
    for rec in M._jsonl(d / f"{doc}_raw_responses.jsonl"):
        for (cid, idx), lab in zip(rec["clause_keys"], rec["labels"] or []):
            labels[(cid, idx)] = lab
    seen = collections.Counter()
    out = {}
    for c in chunks:
        for cl in chunk_clauses(c):
            k = M.squash(cl["text"])
            seen[k] += 1
            out[(k, seen[k])] = (labels.get((cl["chunk_id"], cl["clause_index"]), "MISSING"), cl["text"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(M.SCRATCH / "chunk_size"))
    ap.add_argument("--list", type=int, default=30, help="how many lost and added rows to print per arm for dafman17-1304")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    out = {}
    for arm in ("512", "1024", "A", "C"):
        tot = collections.Counter()
        for doc in M.DOCS:
            dc, da = M.run_dir(root, "control", doc), M.run_dir(root, arm, doc)
            c, x = labeled_clauses(dc, doc), labeled_clauses(da, doc)
            both = set(c) & set(x)
            flips = [k for k in both if (c[k][0] == "NOT_REQUIREMENT") != (x[k][0] == "NOT_REQUIREMENT")]
            label_change = [k for k in both if c[k][0] != x[k][0]]
            only_c, only_x = set(c) - both, set(x) - both
            req = lambda d, k: d[k][0] != "NOT_REQUIREMENT"  # noqa: E731
            lost = [k for k in only_c if req(c, k)]
            added = [k for k in only_x if req(x, k)]
            tot.update(clauses_control=len(c), clauses_arm=len(x), same_text=len(both), flag_flips=len(flips), label_changes=len(label_change),
                       control_only=len(only_c), arm_only=len(only_x), control_only_rows=len(lost), arm_only_rows=len(added))
            out.setdefault(arm, {})[doc] = {"clauses_control": len(c), "clauses_arm": len(x), "same_text": len(both), "flag_flips": len(flips), "label_changes": len(label_change),
                                            "control_only_clauses": len(only_c), "arm_only_clauses": len(only_x), "control_only_rows": len(lost), "arm_only_rows": len(added)}
            if doc == "dafman17-1304":
                out[arm][doc]["flip_examples"] = [(c[k][0], x[k][0], c[k][1][:160]) for k in flips[:a.list]]
                out[arm][doc]["lost_examples"] = [c[k][1][:160] for k in lost[:a.list]]
                out[arm][doc]["added_examples"] = [x[k][1][:160] for k in added[:a.list]]
        out[arm]["TOTAL"] = dict(tot)
        print(arm, json.dumps(dict(tot)))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
