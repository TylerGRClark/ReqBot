"""Blind coverage check: does a document's checklist hold what a human checklist asks?

Three steps, and the model-judging step is done by two separate blind labelers outside this file (agreement between two copies of one model is not correctness):
  1. `packets`: write theirs.txt (T01..) and pool.txt (Q001.., shuffled, no arm names) for one document.
  2. each labeler writes a JSON list [{"id": "T01", "verdict": "yes|partial|no", "pool_ids": [...]}].
  3. `score`: combine two labelers' files into counts, the disagreements and the misses.

    python3 eval/extraction_experiments/coverage.py packets --records records.json --publication DAFI16-1403 --questions <doc>_audit_questions.jsonl --out DIR
    python3 eval/extraction_experiments/coverage.py score --a match_A.json --b match_B.json
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

VERDICTS = ("yes", "partial", "no")


def build_packets(records: list[dict], publication: str, questions: list[str], seed: int = 9) -> dict:
    theirs = [r for r in records if publication.upper() in r.get("publications", [])]
    pool = [q for q in questions if q and q.strip() and q.strip().lower() != "null"]
    random.Random(seed).shuffle(pool)
    return {
        "theirs": [{"id": f"T{i + 1:02d}", "text": r["text"], "tier": r.get("tier", ""), "paragraph": r.get("paragraph", "")} for i, r in enumerate(theirs)],
        "pool": [{"id": f"Q{i + 1:03d}", "text": q} for i, q in enumerate(pool)],
    }


def combine(a: list[dict], b: list[dict], expected: int | None = None) -> dict:
    """Per hand-written item: both labelers' verdicts, whether they agree, and the strict (both say yes) and lenient (neither says no) readings.

    Raises ValueError when the two labelers did not rate the same items (an omitted item must not shrink the denominator) or, with `expected`, when fewer were rated."""
    by_a, by_b = {r["id"]: r for r in a}, {r["id"]: r for r in b}
    if len(by_a) != len(a) or len(by_b) != len(b):
        raise ValueError("a labeler gave the same item twice")
    if set(by_a) != set(by_b):
        raise ValueError(f"the labelers did not rate the same items: only A has {sorted(set(by_a) - set(by_b))}, only B has {sorted(set(by_b) - set(by_a))}")
    ids = sorted(by_a)
    rows = []
    for i in ids:
        va, vb = by_a[i]["verdict"], by_b[i]["verdict"]
        if va not in VERDICTS or vb not in VERDICTS:
            raise ValueError(f"{i}: verdicts must be one of {VERDICTS}, got {va!r} and {vb!r}")
        rows.append({"id": i, "a": va, "b": vb, "agree": va == vb})
    if expected is not None and len(rows) != expected:
        raise ValueError(f"expected {expected} rated items, got {len(rows)}")
    both = Counter((r["a"], r["b"]) if r["a"] <= r["b"] else (r["b"], r["a"]) for r in rows)
    return {
        "items": len(rows),
        "strict_covered": sum(1 for r in rows if r["a"] == r["b"] == "yes"),
        "lenient_covered": sum(1 for r in rows if "no" not in (r["a"], r["b"])),
        "both_no": sum(1 for r in rows if r["a"] == r["b"] == "no"),
        "labelers_agree": sum(1 for r in rows if r["agree"]),
        "pairs": {f"{x}/{y}": n for (x, y), n in sorted(both.items())},
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("packets")
    p.add_argument("--records", required=True)
    p.add_argument("--publication", required=True, help="Normalized publication key, e.g. DAFI16-1403")
    p.add_argument("--questions", required=True, help="<doc>_audit_questions.jsonl of the run being judged")
    p.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--expected", type=int, default=None, help="How many items should have been rated (the count in theirs.txt)")
    args = ap.parse_args(argv)
    if args.cmd == "packets":
        records = json.loads(Path(args.records).expanduser().read_text(encoding="utf-8"))
        questions = [json.loads(ln).get("question") or "" for ln in Path(args.questions).expanduser().read_text(encoding="utf-8").splitlines() if ln.strip()]
        packets = build_packets(records, args.publication, questions)
        out = Path(args.out).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        (out / "theirs.txt").write_text("\n".join(f"{t['id']}: {t['text']}" for t in packets["theirs"]), encoding="utf-8")
        (out / "pool.txt").write_text("\n".join(f"{q['id']}: {q['text']}" for q in packets["pool"]), encoding="utf-8")
        print(f"{len(packets['theirs'])} hand-written items, {len(packets['pool'])} pool questions written to {out}")
        return 0
    result = combine(json.loads(Path(args.a).read_text(encoding="utf-8")), json.loads(Path(args.b).read_text(encoding="utf-8")), args.expected)
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
