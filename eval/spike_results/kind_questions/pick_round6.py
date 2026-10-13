"""Round 6 (second and last prompt round): the one row whose v5 answer is circular (afi10-2402 3.6.2)."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"
r5 = json.loads((OUT / "permission_round5.json").read_text())
ids = [x["checklist_item_id"] for x in r5 if x["doc"] == "afi10-2402" and x["citation"] == "3.6.2"]
(OUT / "round6_ids.json").write_text(json.dumps(ids))
print(ids)
