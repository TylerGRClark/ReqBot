"""Pick the rows whose model answer can change in round 4 (prompt v4): the 3 weak rows the guard cannot see, the 4 missed limits, and every third good row as a check."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"
f = json.loads((OUT / "permission_final.json").read_text())
weak_uncaught = {"3.3.3.5.2", "3.5.2.1.1", "3.8.1"}
ids = [x["checklist_item_id"] for x in f if x["citation"] in weak_uncaught and x["hand_grade"] in ("weak", "wrong")]
ids += [x["checklist_item_id"] for x in f if x["hand_grade"] == "null_missed"]
good = [x for x in f if x["hand_grade"] == "good" and x["question"]]
ids += [x["checklist_item_id"] for x in good[::3][:9]]
(OUT / "round4_ids.json").write_text(json.dumps(ids))
print(len(ids))
