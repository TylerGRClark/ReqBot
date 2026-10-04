#!/usr/bin/env python3
"""WP-44: replay Step D (parse_and_normalize.run) over saved Step C output.

No Ollama, no Qdrant, no writes under ~/documents/processed/. For each document's latest
ingest run it feeds the *saved* extracted requirements + chunks + original PDF + profile to
the real production Step D entry point, writing to an isolated output directory, and records
what survives and why the rest were rejected. Run once before a Step D change and once after;
`--compare` diffs two such runs.

    python3 eval/step_d_replay.py --label baseline --out /tmp/wp44_replay/baseline
    python3 eval/step_d_replay.py --label after    --out /tmp/wp44_replay/after
    python3 eval/step_d_replay.py --compare /tmp/wp44_replay/baseline /tmp/wp44_replay/after \
        --expected eval/spike_results/wp_44/expected_gate.json

`--compare` exits nonzero unless: both runs used identical input run directories and chunk /
extraction / PDF hashes; the documents compared are exactly the expected manifest; no survivor was
added or had a stable field changed; the survivors removed are exactly the approved IDs (any
removal is unapproved when no expectations file is given); and, **per document**, the failure-code
change is exactly the expected new code rising by that document's removal count with every other
code unchanged. Expectations live in one JSON file (`--expected`):

    {"removed_ids": [...], "new_failure_code": "quote_words_not_in_chunk", "documents": [...]}

Replay itself fails (exit 4) if any selected document has no PDF, rather than silently shrinking
the corpus. Exit codes: 0 pass, 1 document-set mismatch, 2 gate failure, 3 input mismatch,
4 replay inputs missing.
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

PROCESSED = Path(os.path.expanduser("~/documents/processed"))
RAW_PDFS = _ROOT / "raw_pdfs"
VOLATILE = {"run_timestamp"}  # known-volatile metadata, excluded from field-level comparison


def select_runs() -> dict[str, Path]:
    """Latest timestamped run directory per document that has both Step B and Step C output."""
    latest: dict[str, Path] = {}
    for d in sorted(PROCESSED.glob("*_20*")):
        stem = re.sub(r"_\d{8}_\d{6}$", "", d.name)
        if glob.glob(str(d / "*_chunks.jsonl")) and glob.glob(str(d / "*_extracted_requirements.jsonl")):
            latest[stem] = d  # sorted ascending -> last timestamp wins
    return latest


def _canon(rec: dict) -> str:
    return json.dumps({k: v for k, v in rec.items() if k not in VOLATILE}, sort_keys=True, ensure_ascii=False)


def _load(path: str) -> list[dict]:
    p = Path(path)
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def replay_one(stem: str, run_dir: Path, out_root: Path, profile: dict) -> dict:
    from pipeline import parse_and_normalize

    chunks_path = glob.glob(str(run_dir / "*_chunks.jsonl"))[0]
    reqs_path = glob.glob(str(run_dir / "*_extracted_requirements.jsonl"))[0]
    pdf = RAW_PDFS / f"{stem}.pdf"
    out_dir = out_root / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    parse_and_normalize.run(reqs_path, chunks_path, str(pdf), str(out_dir), profile=profile)
    input_hashes = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for name, path in (("chunks_sha256", chunks_path), ("extracted_sha256", reqs_path), ("pdf_sha256", str(pdf)))}

    base = Path(reqs_path).name.replace("_extracted_requirements.jsonl", "")
    survivors = _load(str(out_dir / f"{base}_requirements_normalized.jsonl"))
    failures = _load(str(out_dir / f"{base}_normalization_failures.jsonl"))
    raw = _load(reqs_path)
    chunk_ids = {c["chunk_id"] for c in _load(chunks_path)}
    unchecked = sum(1 for r in raw if r.get("chunk_id") is None or r["chunk_id"] not in chunk_ids)

    return {
        "run_dir": run_dir.name,
        **input_hashes,
        "raw_records": len(raw),
        "survivors": len(survivors),
        "unchecked_unknown_chunk": unchecked,
        "failure_codes": dict(Counter(f.get("error") for f in failures)),
        "survivor_ids": sorted(s["requirement_id"] for s in survivors),
        "survivor_hashes": {s["requirement_id"]: hashlib.sha256(_canon(s).encode()).hexdigest()[:16] for s in survivors},
    }


def run_replay(label: str, out: Path) -> dict:
    from core.profiles import load_profile

    out.mkdir(parents=True, exist_ok=True)
    profile = load_profile("cybersecurity")
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "pipeline", "core"],
                                cwd=_ROOT, capture_output=True, text=True).stdout.strip())
    summary = {"label": label, "git_revision": rev, "pipeline_or_core_dirty": dirty,
               "profile": "cybersecurity", "documents": {}}
    selected = select_runs()
    missing = sorted(stem for stem in selected if not (RAW_PDFS / f"{stem}.pdf").exists())
    if missing:
        # A silently skipped document would shrink the evaluated corpus in both arms alike.
        raise RuntimeError(f"replay inputs missing -- no PDF in {RAW_PDFS} for: {missing}")
    for stem, run_dir in selected.items():
        summary["documents"][stem] = replay_one(stem, run_dir, out, profile)
        d = summary["documents"][stem]
        print(f"{stem:18s} raw={d['raw_records']:4d} survivors={d['survivors']:4d} failures={d['failure_codes']}")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    tot = Counter()
    for d in summary["documents"].values():
        tot["raw"] += d["raw_records"]
        tot["survivors"] += d["survivors"]
        tot["unchecked"] += d["unchecked_unknown_chunk"]
    print(f"TOTAL raw={tot['raw']} survivors={tot['survivors']} unchecked_unknown_chunk={tot['unchecked']}")
    return summary


def compare(a_dir: Path, b_dir: Path, expected: dict | None = None) -> int:
    expected = expected or {}
    a = json.loads((a_dir / "summary.json").read_text())
    b = json.loads((b_dir / "summary.json").read_text())
    if set(a["documents"]) != set(b["documents"]):
        print(f"document set differs between runs: {sorted(set(a['documents']) ^ set(b['documents']))}")
        return 1
    if "documents" in expected and set(a["documents"]) != set(expected["documents"]):
        # Both arms could silently omit the same documents; only a manifest catches that.
        print("documents compared differ from the expected manifest: "
              f"missing {sorted(set(expected['documents']) - set(a['documents']))}, "
              f"unexpected {sorted(set(a['documents']) - set(expected['documents']))}")
        return 1

    # Both arms must have replayed the identical inputs, or corpus changes (e.g. a newer ingest
    # appearing between the two runs) would be attributed to the code under test.
    mismatched = []
    for stem in sorted(a["documents"]):
        da, db = a["documents"][stem], b["documents"][stem]
        for key in ("run_dir", "chunks_sha256", "extracted_sha256", "pdf_sha256"):
            if da.get(key) is None or da.get(key) != db.get(key):
                mismatched.append((stem, key))
    if mismatched:
        print("INPUT MISMATCH -- the two runs did not use identical inputs (or a summary predates input hashing):")
        for stem, key in mismatched:
            print(f"  {stem}: {key}")
        return 3

    new_code = expected.get("new_failure_code")
    removed, added, changed, code_problems = [], [], [], []
    codes_a, codes_b = Counter(), Counter()
    for stem in sorted(a["documents"]):
        da, db = a["documents"][stem], b["documents"][stem]
        codes_a.update(da["failure_codes"])
        codes_b.update(db["failure_codes"])
        sa, sb = set(da["survivor_ids"]), set(db["survivor_ids"])
        removed_here = sorted(sa - sb)
        removed += [(stem, i) for i in removed_here]
        added += [(stem, i) for i in sorted(sb - sa)]
        changed += [(stem, i) for i in sorted(sa & sb) if da["survivor_hashes"][i] != db["survivor_hashes"][i]]
        # Per document: the new code must rise by exactly this document's removals; no other
        # code may move at all (a removal attributed to the wrong rule must not pass).
        for code in sorted(set(da["failure_codes"]) | set(db["failure_codes"])):
            delta = db["failure_codes"].get(code, 0) - da["failure_codes"].get(code, 0)
            want = len(removed_here) if code == new_code else 0
            if delta != want:
                code_problems.append(f"{stem}: failure code {code!r} changed by {delta:+d}, expected {want:+d}")
        if new_code and new_code not in da["failure_codes"] and new_code not in db["failure_codes"] and removed_here:
            code_problems.append(f"{stem}: {len(removed_here)} removal(s) but no {new_code!r} failures recorded")

    print(f"baseline rev {a['git_revision'][:8]} (dirty={a['pipeline_or_core_dirty']})  vs  after rev {b['git_revision'][:8]} (dirty={b['pipeline_or_core_dirty']})")
    print(f"failure codes baseline: {dict(codes_a)}\nfailure codes after:    {dict(codes_b)}")
    print(f"removed survivors: {len(removed)}  added: {len(added)}  changed fields: {len(changed)}")
    for stem, rid in removed:
        # show what was removed, from the baseline normalized file
        for f in glob.glob(str(a_dir / stem / "*_requirements_normalized.jsonl")):
            for r in _load(f):
                if r["requirement_id"] == rid:
                    print(f"  REMOVED {stem}: {r['source_quote'][:110]!r}")
    for stem, rid in added:
        print(f"  ADDED   {stem}: {rid}")
    for stem, rid in changed[:10]:
        print(f"  CHANGED {stem}: {rid}")

    problems = list(code_problems)
    if added:
        problems.append(f"{len(added)} survivor(s) added")
    if changed:
        problems.append(f"{len(changed)} survivor(s) with changed fields")
    removed_ids = {rid for _, rid in removed}
    if "removed_ids" not in expected:
        if removed_ids:
            problems.append(f"{len(removed_ids)} unapproved removal(s) (no expectations given)")
    else:
        approved = set(expected["removed_ids"])
        if removed_ids - approved:
            problems.append(f"unexpected removals: {sorted(removed_ids - approved)}")
        if approved - removed_ids:
            problems.append(f"expected removals missing: {sorted(approved - removed_ids)}")
    if problems:
        print("GATE FAILED:")
        for pr in problems:
            print(f"  - {pr}")
        return 2
    print("GATE PASSED: identical inputs; expected documents; removals match the approved set; "
          "failure-code change is exactly the expected new code, per document.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="run")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("BASELINE_DIR", "AFTER_DIR"))
    ap.add_argument("--expected", type=Path, metavar="JSON",
                    help='gate expectations: {"removed_ids": [...], "new_failure_code": "...", "documents": [...]}')
    args = ap.parse_args()
    if args.compare:
        expected = json.loads(args.expected.read_text()) if args.expected else None
        return compare(*args.compare, expected=expected)
    if not args.out:
        ap.error("--out is required unless --compare is given")
    if str(args.out.resolve()).startswith(str(PROCESSED.resolve())):
        ap.error("--out must be outside ~/documents/processed/")
    try:
        run_replay(args.label, args.out)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
