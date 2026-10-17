"""No model: kind counts (wrapper) per document for a list of checklist JSON files. Usage: count_kinds.py <dir> <doc> [<doc> ...]"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import held_out  # noqa: E402
import kind_questions as kq  # noqa: E402

scratch = Path(sys.argv[1])
rows = held_out.load_rows(scratch, sys.argv[2:])
for d in sys.argv[2:]:
    c = Counter(kq.classify_wrapper(r)["kind"] for r in rows if r["_doc"] == d)
    n = sum(c.values())
    print(d, n, {k: v for k, v in c.most_common()}, "perm+rec share", round((c["permission"] + c["recommendation"]) / max(1, n), 3))
