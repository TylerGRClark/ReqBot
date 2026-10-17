"""Build the checklist rows (no model) for the six AFI-type documents into a scratch folder, then print kind counts.
Usage: python3 eval/spike_results/kind_questions/build_rows.py <scratch_dir>
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services import requirement_kind as rk  # noqa: E402

DOCS = ["afi10-2402", "afi13-550", "afi17-203", "afman17-2101", "afpd_17-1", "dafman17-1305"]


def build(scratch: Path) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    for d in DOCS:
        out = scratch / f"{d}.json"
        subprocess.run([sys.executable, str(ROOT / "cli/reqbot.py"), "checklist", "--doc", d, "--format", "json", "--output", str(out)], check=True, cwd=ROOT)


def load_rows(scratch: Path) -> list[dict]:
    rows = []
    for d in DOCS:
        for it in json.load(open(scratch / f"{d}.json"))["items"]:
            if (it.get("source_quote") or "").strip():
                it["_doc"] = d
                rows.append(it)
    return rows


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    if not all((scratch / f"{d}.json").exists() for d in DOCS):
        build(scratch)
    rows = load_rows(scratch)
    by = Counter()
    for r in rows:
        k = rk.classify(r)["kind"]
        by[(k, bool(r.get("audit_question")))] += 1
    print(len(rows), "rows")
    for (k, q), n in sorted(by.items()):
        print(k, "with_question" if q else "no_question", n)
