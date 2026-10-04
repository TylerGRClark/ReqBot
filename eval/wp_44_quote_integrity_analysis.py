#!/usr/bin/env python3
"""WP-44: reproduce the source-quote integrity measurement behind docs/PHASE44_REQUIREMENTS.md §1.

Reads the latest ingest run of each document under ~/documents/processed/ (read-only) and, for
every raw Step C quote, records how it relates to its own chunk's text, its word coverage, its
fuzzy-grounding score, its Step D disposition, and whether it appears anywhere else in its
document. Writes manifest.json, per_record.jsonl and report.md to --out (default:
eval/spike_results/wp_44/).

    python3 eval/wp_44_quote_integrity_analysis.py

Categories (assigned in this order):
  exact          normalized quote is a substring of the chunk body (`raw_text`)
  format_only    alphanumeric-only comparison is a substring of the chunk body
  elision        quote contains an ellipsis
  invented       word coverage < 0.8 (most words absent from the chunk)
  stitched       not contiguous in the chunk, but every/most words present (list lead-in + item)
`not_anywhere_in_document` is an INDEPENDENT label (alphanumeric-normalized quote vs the
concatenated text of all chunks of that document); it does not use the coverage rule.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rapidfuzz import fuzz  # noqa: E402

from pipeline.parse_and_normalize import normalize_text  # noqa: E402

PROCESSED = Path(os.path.expanduser("~/documents/processed"))
THRESHOLD = 0.8


def squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(s))


def coverage(quote: str, chunk_text: str) -> float:
    q = tokens(quote)
    c = set(tokens(chunk_text))
    return sum(t in c for t in q) / len(q) if q else 0.0


def sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def select_runs() -> dict[str, Path]:
    latest: dict[str, Path] = {}
    for d in sorted(PROCESSED.glob("*_20*")):
        stem = re.sub(r"_\d{8}_\d{6}$", "", d.name)
        if glob.glob(str(d / "*_chunks.jsonl")) and glob.glob(str(d / "*_extracted_requirements.jsonl")):
            latest[stem] = d
    return latest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=_ROOT / "eval" / "spike_results" / "wp_44")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"git_revision": rev, "profile": "cybersecurity",
                "selection_rule": "latest timestamped run dir per document with both *_chunks.jsonl and "
                                  "*_extracted_requirements.jsonl",
                "coverage_threshold_under_study": THRESHOLD, "documents": {}}
    rows, cats = [], Counter()

    for stem, run in select_runs().items():
        chunks_f = glob.glob(str(run / "*_chunks.jsonl"))[0]
        ext_f = glob.glob(str(run / "*_extracted_requirements.jsonl"))[0]
        fail_fs = glob.glob(str(run / "*normalization_failures.jsonl"))
        norm_fs = glob.glob(str(run / "*_requirements_normalized.jsonl"))
        art = {k: glob.glob(str(run / f"*_requirements_{k}.jsonl")) for k in ("normalized", "enriched", "gated")}
        manifest["documents"][stem] = {
            "run_dir": run.name,
            "chunks_sha256": sha(chunks_f), "extracted_sha256": sha(ext_f),
            "normalized_sha256": sha(norm_fs[0]) if norm_fs else None,
            "artifacts_present": [k for k, v in art.items() if v],
        }
        chunks = {c["chunk_id"]: c for c in load(chunks_f)}
        doc_text = squash(" ".join((c.get("raw_text") or c["text"]) for c in chunks.values()))
        rejected = {}
        for f in fail_fs:
            for r in load(f):
                rejected[r.get("requirement_id")] = r.get("error")
        art_quotes = {k: {squash(r["source_quote"]) for r in load(v[0])} for k, v in art.items() if v}

        for r in load(ext_f):
            q0, c = r.get("source_quote") or "", chunks.get(r.get("chunk_id"))
            if not q0 or c is None:
                cats["unusable(no quote / unknown chunk)"] += 1
                continue
            body = c.get("raw_text") or c["text"]
            qn, bn = normalize_text(q0), normalize_text(body)
            cov = coverage(q0, c["text"])
            fuzzy = fuzz.partial_ratio(qn, normalize_text(c["text"]))
            if qn in bn:
                cat = "exact"
            elif squash(q0) in squash(body):
                cat = "format_only"
            elif re.search(r"\.\.\.|…", q0):
                cat = "elision"
            elif cov < THRESHOLD:
                cat = "invented"
            else:
                cat = "stitched"
            nowhere = squash(q0) not in doc_text
            disposition = f"rejected:{rejected[r['requirement_id']]}" if r.get("requirement_id") in rejected else "survived_step_d"
            in_artifacts = [k for k, qs in art_quotes.items() if squash(q0) in qs]
            rows.append({"document": stem, "chunk_id": r["chunk_id"], "requirement_id": r.get("requirement_id"),
                         "category": cat, "coverage": round(cov, 3), "fuzzy_score": round(fuzzy, 1),
                         "step_d_disposition": disposition, "not_anywhere_in_document": nowhere,
                         "in_corpus_artifacts": in_artifacts, "source_quote": q0})
            cats[(cat, "survived" if disposition == "survived_step_d" else "rejected")] += 1

    with (args.out / "per_record.jsonl").open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))

    inv = [x for x in rows if x["category"] == "invented"]
    leaks = [x for x in inv if x["step_d_disposition"] == "survived_step_d"]
    caught = [x for x in inv if x["step_d_disposition"] != "survived_step_d"]
    other = [x for x in rows if x["category"] != "invented"]
    lines = [
        "# WP-44 quote-integrity analysis (generated; do not hand-edit)",
        f"\nrevision `{rev[:10]}`; {len(manifest['documents'])} documents; {len(rows)} raw quotes with a known chunk.",
        "\n## Category x Step D outcome\n", "| category | survived Step D | rejected by Step D |", "|---|---|---|",
    ]
    for cat in ("exact", "format_only", "elision", "invented", "stitched"):
        lines.append(f"| {cat} | {cats[(cat, 'survived')]} | {cats[(cat, 'rejected')]} |")
    lines += [
        "\n## Invented quotes (coverage < 0.8)\n",
        f"- total {len(inv)}: {len(caught)} rejected by existing gates, **{len(leaks)} survived Step D (leaks)**",
        f"- leak coverage: {sorted(x['coverage'] for x in leaks)}; leak fuzzy scores: {sorted(x['fuzzy_score'] for x in leaks)}",
        f"- coverage of rejected invented quotes: min {min(x['coverage'] for x in caught)}, max {max(x['coverage'] for x in caught)}",
        f"- **lowest coverage among the {len(other)} non-invented quotes: {min(x['coverage'] for x in other)}**",
        f"- leaks absent from their whole document (independent label): {sum(x['not_anywhere_in_document'] for x in leaks)} of {len(leaks)}",
        f"- rejected-invented absent from their whole document: {sum(x['not_anywhere_in_document'] for x in caught)} of {len(caught)}",
        "\n## The leaks\n",
    ]
    for x in sorted(leaks, key=lambda x: (x["document"], x["chunk_id"])):
        lines.append(f"- `{x['document']}` chunk {x['chunk_id']}: coverage {x['coverage']}, fuzzy {x['fuzzy_score']}, "
                     f"present in corpus artifacts {x['in_corpus_artifacts']}: {x['source_quote']!r}")
    lines += ["\n## Threshold sweep (non-invented quotes newly rejected / leaks blocked)\n", "| threshold | leaks blocked | other quotes rejected |", "|---|---|---|"]
    for t in (0.7, 0.8, 0.9, 0.95):
        lines.append(f"| {t} | {sum(x['coverage'] < t for x in leaks)}/{len(leaks)} | {sum(x['coverage'] < t for x in rows if x not in leaks and x['step_d_disposition'] == 'survived_step_d')} of "
                     f"{sum(x['step_d_disposition'] == 'survived_step_d' for x in rows if x not in leaks)} survivors |")
    (args.out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
