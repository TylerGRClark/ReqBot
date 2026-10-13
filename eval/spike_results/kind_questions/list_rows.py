"""List the rows of the three kinds under test (and 'authorize' rows) with the current question. No model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rows import load_rows  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

rows = load_rows(Path(sys.argv[1]))
want = set(sys.argv[2].split(","))
for r in rows:
    c = rk.classify(r)
    if c["kind"] in want or (("authoriz" in sys.argv[2]) and r["source_quote"].lower().startswith("authoriz")):
        print(f"[{r['_doc']}] {r['citation']} | {c['kind']} | {c['kind_reasons']}\n   Q: {r['source_quote'][:420]}\n   A: {r.get('audit_question')!r} flags={r.get('item_flags')}\n")
