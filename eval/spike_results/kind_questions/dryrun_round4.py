"""No model: show the antecedent extracted for the part A rows and check the part A prompt renders."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import round4_checks as r4  # noqa: E402
from build_rows import load_rows  # noqa: E402
from part_a import PART_A  # noqa: E402

rows = load_rows(Path(sys.argv[1]))
for r in rows:
    for doc, cit, start in PART_A:
        if r["_doc"] == doc and (r.get("citation") or "") == cit and r["source_quote"].startswith(start):
            print(doc, cit, "|", r["source_quote"][:70])
            print("   ANTECEDENT:", r4.antecedent(r))
