"""WP-45.1(c)/(d): record the hashes of everything that must be fixed before the first retrieval (offline).

Run after groups.json, query_packet.md and queries.jsonl exist and query_check.py passes. The manifest it writes is
committed BEFORE any retrieval script is run, so the commit history shows the queries and groups were frozen first.

Run from the repo root:  python3 eval/spike_results/wp_45_1c/freeze_inputs.py
"""

import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import query_check as qc  # noqa: E402

FILES = (
    "groups.json",
    "query_packet.md",
    "QUERY_WRITING.md",
    "queries.jsonl",
    "query_check.py",
    "query_ids.json",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    queries = [
        json.loads(x)
        for x in (_HERE / "queries.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    cards = qc.parse_packet((_HERE / "query_packet.md").read_text(encoding="utf-8"))
    rows, problems = qc.check(queries, cards)
    if problems:
        sys.exit("query rules are not satisfied, not freezing:\n  " + "\n  ".join(problems))
    summary = {}
    for style in ("topic", "party"):
        ov = [r["overlap"] for r in rows if r["style"] == style]
        summary[style] = {
            "n": len(ov),
            "median_overlap": round(statistics.median(ov), 3),
            "mean_overlap": round(statistics.mean(ov), 3),
            "max_overlap": max(ov),
        }
    out = {
        "frozen_before_any_retrieval": True,
        "sha256": {name: sha256(_HERE / name) for name in FILES},
        "queries": len(queries),
        "no_party": sum(1 for q in queries if q.get("no_party")),
        "overlap_with_card": summary,
        "git_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "git_revision_note": "HEAD when frozen; the commit that adds this file follows it",
    }
    target = _HERE / "outputs" / "queries_frozen.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["overlap_with_card"]), "\nfrozen ->", target)


if __name__ == "__main__":
    main()
