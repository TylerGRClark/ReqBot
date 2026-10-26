#!/usr/bin/env python3
"""PREREG12: re-point the old retrieval gold set at the current library.

eval/gold_retrieval_queries.jsonl names requirement_ids from the old list-writing method; only 22 of its
130 ids exist in the 2026-10-24 library. This finds each old row's quote in the old run folders and maps it to
the live rows by text. Rule (frozen in PREREG12.md): after lowercasing and dropping punctuation, a live row
matches an old quote when one is a substring of the other, or when >=90% of the shorter one's words occur in the
longer one and the shorter one has >=6 words. Only rows of the same source_pdf are considered.
Output: PREREG12_gold_remapped.jsonl (same fields, new ids, plus old_unmapped).
"""
import argparse
import collections
import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def newest_normalized(processed):
    best = {}
    for d in glob.glob(os.path.join(processed, "*_2026*")):
        k = re.sub(r"_\d{8}_\d{6}$", "", os.path.basename(d))
        f = glob.glob(d + "/*_requirements_normalized.jsonl")
        if f and (k not in best or d > best[k][0]):
            best[k] = (d, f[0])
    return best


def matches(old_quote, old_pdf, rows):
    oq = norm(old_quote)
    ow = set(oq.split())
    out = set()
    for r in rows:
        if old_pdf and r["source_pdf"] != old_pdf:
            continue
        nq = r["_n"]
        if len(nq.split()) < 6:
            continue
        if nq in oq or oq in nq:
            out.add(r["requirement_id"])
            continue
        sh, lo = (r["_w"], ow) if len(r["_w"]) <= len(ow) else (ow, r["_w"])
        if len(sh) >= 6 and len(sh & lo) / len(sh) >= 0.9:
            out.add(r["requirement_id"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", default=os.path.expanduser("~/documents/processed"))
    ap.add_argument("--old-roots", nargs="+", default=[os.path.expanduser("~/documents")])
    ap.add_argument("--gold", default=str(ROOT / "eval" / "gold_retrieval_queries.jsonl"))
    ap.add_argument("--out", default=str(Path(__file__).with_name("PREREG12_gold_remapped.jsonl")))
    a = ap.parse_args()
    gold = [json.loads(l) for l in open(a.gold, encoding="utf-8") if l.strip()]
    ids = {i for g in gold for i in g["relevant_requirement_ids"]}
    old = collections.defaultdict(set)  # id -> {(quote, pdf)}
    for root in a.old_roots:
        for f in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
            try:
                for line in open(f, encoding="utf-8"):
                    if "REQ-" not in line:
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("requirement_id") in ids and r.get("source_quote"):
                        old[r["requirement_id"]].add((r["source_quote"], r.get("source_pdf", "")))
            except OSError:
                pass
    rows = []
    for _, (_, f) in newest_normalized(a.processed).items():
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            r["_n"] = norm(r["source_quote"])
            r["_w"] = set(r["_n"].split())
            rows.append(r)
    mapping = {}
    for rid in ids:
        m = set()
        for q, pdf in old.get(rid, ()):
            m |= matches(q, pdf, rows)
        mapping[rid] = sorted(m)
    with open(a.out, "w", encoding="utf-8") as fh:
        for g in gold:
            new, un = set(), 0
            for i in g["relevant_requirement_ids"]:
                if mapping[i]:
                    new |= set(mapping[i])
                else:
                    un += 1
            g2 = dict(g)
            g2["relevant_requirement_ids"] = sorted(new)
            g2["old_ids"] = g["relevant_requirement_ids"]
            g2["old_unmapped"] = un
            fh.write(json.dumps(g2) + "\n")
    scored = sum(1 for g in gold if g["shape"] != "zero" and any(mapping[i] for i in g["relevant_requirement_ids"]))
    print(f"{len(gold)} queries; ids with a live match: {sum(1 for v in mapping.values() if v)}/{len(ids)}; scored non-zero queries: {scored}")


if __name__ == "__main__":
    main()
