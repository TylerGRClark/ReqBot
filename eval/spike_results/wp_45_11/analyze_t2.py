#!/usr/bin/env python3
"""WP-45.11 T2 test: per changed chunk, every Step C quote each version produced and in how many of the repeats (offline; reads scratch runs only).

  python3 analyze_t2.py --out outputs/t2_report.json

Versions are `T2base_1..N` (today's chunk text) and `T2new_1..N` (the table fix's text). For each chunk and version: records and Step D survivors per repeat, every
distinct normalized quote with the number of repeats that produced it and whether Step D kept it, and whether the quote lies in the chunk's table (a quote whose
words are at least 80% inside one markdown row of the new text's table). The registered rules (docs/PHASE45_WP4511_ADDENDUM.md) are evaluated from this output.
"""

import argparse
import collections
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DOCS = {"DODI 5200.48": [76, 87], "DODI 8551.01": [26], "afi10-2402": [121, 123]}
SCRATCH = Path.home() / "wp45_11_scratch"


def words(text):
    return re.findall(r"\w+", (text or "").lower())


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(path).exists() else []


def table_rows(text):
    """Word lists of the markdown table rows in a chunk's text."""
    return [words(line) for line in (text or "").splitlines() if line.strip().startswith("|") and not re.match(r"^\|[-| ]+\|$", line.strip())]


def in_table(quote, trows):
    q = words(quote)
    return bool(q) and any(len([w for w in q if w in set(r)]) / len(q) >= 0.8 for r in trows)


def check_repeats(repeats, scratch):
    """All ten runs must be complete and successful for the three documents before any number is computed (a missing output would otherwise read as zero)."""
    import score_arms

    for version in ("T2base", "T2new"):
        for i in range(1, repeats + 1):
            score_arms.check_complete(f"{version}_{i}", scratch=scratch, docs=list(DOCS))


def analyze(repeats, scratch=SCRATCH):
    check_repeats(repeats, scratch)
    out = {}
    for doc, chunk_ids in DOCS.items():
        new_chunks = {c["chunk_id"]: c for c in rows(scratch / "T2new_1" / doc / f"{doc}_chunks.jsonl")}
        for cid in chunk_ids:
            trows = table_rows(new_chunks[cid]["raw_text"])
            entry = {"table_rows_in_new_text": len(trows), "versions": {}}
            for version in ("T2base", "T2new"):
                per, freq, kept = [], collections.Counter(), collections.defaultdict(int)
                example = {}
                for i in range(1, repeats + 1):
                    d = scratch / f"{version}_{i}" / doc
                    ext = [r for r in rows(d / f"{doc}_extracted_requirements.jsonl") if r["chunk_id"] == cid]
                    norm = rows(d / f"{doc}_requirements_normalized.jsonl")
                    survivors = {" ".join(words(r["source_quote"])) for r in norm if r["chunk_id"] == cid}
                    keys = {" ".join(words(r["source_quote"])) for r in ext}
                    per.append({"records": len(ext), "survivors": len(survivors)})
                    for k in keys:
                        freq[k] += 1
                    for k in survivors:
                        kept[k] += 1
                    for r in ext:
                        example.setdefault(" ".join(words(r["source_quote"])), r["source_quote"])
                entry["versions"][version] = {
                    "per_repeat": per, "median_survivors": statistics.median(p["survivors"] for p in per),
                    "quotes": sorted(({"quote": example[k], "repeats_extracted": n, "repeats_survived_step_d": kept[k], "in_table": in_table(example[k], trows)}
                                      for k, n in freq.items()), key=lambda q: (-q["repeats_extracted"], q["quote"])),
                }
            out[f"{doc} chunk {cid}"] = entry
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--scratch", default=str(SCRATCH))
    ap.add_argument("--out")
    args = ap.parse_args()
    report = analyze(args.repeats, Path(args.scratch))
    for chunk, e in report.items():
        b, n = e["versions"]["T2base"], e["versions"]["T2new"]
        print(f"== {chunk}: table rows in new text {e['table_rows_in_new_text']} | median survivors base {b['median_survivors']} new {n['median_survivors']} | "
              f"per repeat base {[p['survivors'] for p in b['per_repeat']]} new {[p['survivors'] for p in n['per_repeat']]}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
