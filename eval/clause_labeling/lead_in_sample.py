#!/usr/bin/env python3
"""PREREG10: the rows that gain a heading lead-in (control vs heading explained layer, from renormalize_explained.py output), counted by document and style, plus a seeded stratified
sample printed for hand reading (row text, lead-in, the text just before the row). Read only, no model.

    python3 eval/clause_labeling/lead_in_sample.py --dir DIR_WITH_control_AND_heading [--n 60] [--seed 11]
"""
import argparse
import collections
import glob
import json
import random
from pathlib import Path


def load(root: Path, arm: str) -> dict:
    d = {}
    for f in glob.glob(str(root / arm / "*" / "*_requirements_normalized.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                d[r["requirement_id"]] = r
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    root = Path(a.dir).expanduser()
    c, h = load(root, "control"), load(root, "heading")
    has = lambda r: any(p["kind"] == "lead_in" for p in r["explained_parts"])  # noqa: E731
    new = [h[k] for k in h if has(h[k]) and not has(c[k])]
    print("rows that gain a lead-in:", len(new), dict(collections.Counter(r["source_pdf"] for r in new)))
    chunks = {}
    for f in glob.glob(str(root / "heading" / "*" / "*_chunks.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                ch = json.loads(ln)
                chunks[(Path(f).name.removesuffix("_chunks.jsonl"), ch["chunk_id"])] = ch
    random.seed(a.seed)
    by = collections.defaultdict(list)
    for r in new:
        by[r["source_pdf"]].append(r)
    sample = []
    for rs in by.values():
        sample += random.sample(rs, min(len(rs), max(2, round(a.n * len(rs) / len(new)))))
    for r in sample:
        ch = chunks.get((r["source_pdf"].removesuffix(".pdf"), r["chunk_id"]), {})
        pre = (ch.get("raw_text") or "")[: r["anchor_start"]][-110:].replace("\n", " | ")
        print(f"- {r['source_pdf']} {r['chunk_id']} | LEAD: {r['explained_parts'][0]['text'][:80]} | ITEM: {r['source_quote'][:80]} | BEFORE: {pre}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
