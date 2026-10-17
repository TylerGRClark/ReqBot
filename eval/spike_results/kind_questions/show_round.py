"""Print a permission round's answers with the round-3 checks applied. Usage: show_round.py <n>"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import round3_checks as r3  # noqa: E402

for x in json.loads((HERE / "outputs" / f"permission_round{sys.argv[1]}.json").read_text()):
    print(x["doc"], x["citation"], "|", x["source_quote"][:160].replace("\n", " "))
    print("   LIMIT:", x["limit"])
    print("   Q:", x["question"] or ("NULL: " + str(x["why_null"])[:110]), "| old checks:", x["failures"], "| new:", r3.rejection(x["question"], x["source_quote"], x["limit"]))
