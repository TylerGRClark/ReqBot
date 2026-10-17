"""Part B documents (held out): build checklist JSON (no model) into a scratch folder and load the rows.
  python3 held_out.py <scratch_dir>     # builds missing files, prints kind counts
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import kind_questions as kq  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

HELD_OUT = ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125"]


def fname(doc: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", doc) + ".json"


def build(scratch: Path) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    for d in HELD_OUT:
        out = scratch / fname(d)
        if not out.exists():
            subprocess.run([sys.executable, str(ROOT / "cli/reqbot.py"), "checklist", "--doc", d, "--format", "json", "--output", str(out)], check=True, cwd=ROOT)


def load_rows(scratch: Path, docs=None) -> list[dict]:
    rows = []
    for d in docs or HELD_OUT:
        for it in json.load(open(scratch / fname(d)))["items"]:
            if (it.get("source_quote") or "").strip():
                it["_doc"] = d
                rows.append(it)
    return rows


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    build(scratch)
    rows = load_rows(scratch)
    c = Counter((r["_doc"], kq.classify_wrapper(r)["kind"]) for r in rows)
    docs = sorted({r["_doc"] for r in rows})
    for d in docs:
        print(d, sum(1 for r in rows if r["_doc"] == d), {k: n for (dd, k), n in sorted(c.items()) if dd == d and k in ("permission", "recommendation", "pointer")})
    print("total rows", len(rows), "permission", sum(n for (d, k), n in c.items() if k == "permission"))
    _ = rk
