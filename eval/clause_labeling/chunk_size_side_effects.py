#!/usr/bin/env python3
"""Side effects of a larger chunk size on the readers of chunk text (PREREG6, reported not judged). Read only, no model.

For each arm and document it builds the checklist the normal way and measures, over the rows that carry a passage:
- passage length (the passage is the whole chunk that holds the row, plus the tail of the previous chunk for a mid-sentence or list row);
- where the marked requirement (>> <<) sits inside the passage, against the cut-offs other jobs apply: the draft-question prompt keeps the first 1500 characters
  (services/audit_questions.build_prompt), the criticality prompt the first 1200;
- rows whose quote is not located in the passage;
- the share of chunk text beyond the first 1500 characters, which is all the context index embeds (pipeline/embed_context_index).

    python3 eval/clause_labeling/chunk_size_side_effects.py --root ~/reqbot-work/scratch/chunk_size [--json OUT]
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services import checklist_audit, checklist_service  # noqa: E402
import chunk_size_metrics as M  # noqa: E402

CUTS = {"questions_1500": 1500, "criticality_1200": 1200}


def pct(sorted_vals, p):
    return sorted_vals[int(p * (len(sorted_vals) - 1))] if sorted_vals else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(M.SCRATCH / "chunk_size"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--arms", default=",".join(M.ARMS))
    args = ap.parse_args()
    root = Path(args.root).expanduser()
    out: dict = {}
    for arm in args.arms.split(","):
        agg = {"rows": 0, "with_passage": 0, "not_located": 0, "lengths": [], "beyond": {k: 0 for k in CUTS}, "chunk_chars": 0, "chunk_chars_beyond_1500": 0}
        for doc in M.DOCS:
            d = M.run_dir(root, arm, doc)
            if d is None:
                continue
            for c in M._jsonl(d / f"{doc}_chunks.jsonl"):
                n = len(c.get("text") or "")
                agg["chunk_chars"] += n
                agg["chunk_chars_beyond_1500"] += max(0, n - 1500)
            cl = checklist_service.generate(root / "out" / arm, doc, "cybersecurity")
            for it in cl.get("items", []):
                if not it.get("requirement_ids"):
                    continue
                agg["rows"] += 1
                p = it.get("passage") or ""
                if not p:
                    continue
                agg["with_passage"] += 1
                agg["lengths"].append(len(p))
                i = p.find(checklist_audit.MARK_OPEN)
                if i < 0:
                    agg["not_located"] += 1
                    continue
                j = p.find(checklist_audit.MARK_CLOSE, i)
                for k, lim in CUTS.items():
                    if j + len(checklist_audit.MARK_CLOSE) > lim:  # the marked quote is not wholly inside the first `lim` characters
                        agg["beyond"][k] += 1
        L = sorted(agg.pop("lengths"))
        agg.update(passage_median=pct(L, 0.5), passage_p95=pct(L, 0.95), passage_max=L[-1] if L else 0)
        out[arm] = agg
        print(arm, json.dumps(agg))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
