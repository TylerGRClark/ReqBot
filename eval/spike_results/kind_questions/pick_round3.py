"""The 13 reviewer-flagged rows (3 wrong, 10 weak) as checklist_item_ids, for the prompt-v5 re-run. No model."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"
FLAGGED = {  # (doc, citation, start of source quote) -> reviewer grade
    ("afi10-2402", "3.3.3.5.2", "Significant changes"): "wrong",
    ("dafman17-1305", "4.2.1", "DAF Civilian"): "wrong",
    ("dafman17-1305", "4.1.12", "Such allowances"): "wrong",
    ("afi10-2402", "3.6.2", "Membership may"): "weak",
    ("afi17-203", "3.8", "An incident/event"): "weak",
    ("afi17-203", "3.8", "In such cases, information"): "weak",
    ("dafman17-1305", "1.2.3", "User network access"): "weak",
    ("dafman17-1305", "1.2.4", "They may"): "weak",
    ("dafman17-1305", "4.1.15", "Civilian personnel can"): "weak",
    ("dafman17-1305", "4.1.19 (inferred)", "An individual's"): "weak",
    ("dafman17-1305", "4.4.1.2", "Waivers may"): "weak",
    ("dafman17-1305", "4.4.1.3", "Maintenance of self-funded"): "weak",
    ("dafman17-1305", "6.2.1", "Reporting formats"): "weak",
}
rows = json.loads((OUT / "round2_rows.json").read_text())
picked = {}
for e in rows:
    for (doc, cit, start), grade in FLAGGED.items():
        if e["doc"] == doc and e["citation"] == cit and e["source_quote"].startswith(start) and e["new_question"] and e["new_question"] != e["live_question"]:
            picked[e["checklist_item_id"]] = {"grade": grade, "doc": doc, "citation": cit}
assert len(picked) == 13, len(picked)
(OUT / "round5_ids.json").write_text(json.dumps(list(picked)))
(OUT / "reviewer_grades_round2.json").write_text(json.dumps(picked, indent=1))
print(len(picked))
