"""Round 3 final table: every permission row through guard -> round-3 checks -> fallback, compared with today's live question and with round 2. No model.
  python3 round3_final.py <scratch_dir>
Writes outputs/round3_rows.json and outputs/round3_summary.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kind_questions as kq  # noqa: E402
import round3_checks as r3  # noqa: E402
from build_rows import load_rows  # noqa: E402

OUT = HERE / "outputs"
load = lambda n: json.loads((OUT / n).read_text())  # noqa: E731


def latest_answers() -> dict:
    """checklist_item_id -> the latest model answer for that row (round 1/2/3 final table, then round 4, 5, 6)."""
    ans = {x["checklist_item_id"]: x for x in load("permission_final.json")}
    for name in ("permission_round4.json", "permission_round5.json", "permission_round6.json"):
        for x in load(name):
            ans[x["checklist_item_id"]] = x
    return ans


def main(scratch: Path) -> None:
    rows = {r["checklist_item_id"]: r for r in load_rows(scratch)}
    ans = latest_answers()
    round2 = {e["checklist_item_id"]: e for e in load("round2_rows.json")}
    r2_final = {x["checklist_item_id"]: x for x in load("permission_final.json")}
    reviewer = load("reviewer_grades_round2.json")
    out = []
    for cid, a in ans.items():
        r = rows[cid]
        live = r.get("audit_question") or None
        q, limit, why_null = a.get("question"), a.get("limit"), a.get("why_null")
        rule, rejected_by_check = "new boundary question" if q else "no stated limit", False
        if q and kq.purpose_not_limit(limit):
            q, rule = None, f"limit is only a {kq.purpose_not_limit(limit)}"
        if q:
            why = r3.rejection(q, r["source_quote"], limit)
            if why:
                q, rule, rejected_by_check = None, "rejected: " + why, True
        r2_entry = round2.get(cid)
        prev_q = r2_entry["new_question"] if r2_entry and r2_entry["new_question"] != live else None
        prev_rejected = bool(prev_q and r3.rejection(prev_q, r["source_quote"], r2_entry.get("limit")))  # the previous answer for this row fails a check
        if not q:
            keep, reason = r3.fallback_after_rejection(live, r, why_null, rejected_by_check or prev_rejected)
            if keep:
                q, rule = live, rule + "; today's question kept (" + reason + ")"
        r2_entry = round2.get(cid)
        r2_q = r2_entry["new_question"] if r2_entry else live
        out.append({"doc": r["_doc"], "citation": r.get("citation"), "checklist_item_id": cid, "source_quote": r["source_quote"], "live_question": live, "round2_question": r2_q,
                    "final_question": q, "limit": limit, "why_null": why_null, "rule": rule, "reviewer_round2": reviewer.get(cid, {}).get("grade", "good" if r2_q != live and r2_q else None),
                    "changed_from_round2": q != r2_q, "differs_from_live": q != live, "prompt": a.get("prompt")})
    (OUT / "round3_rows.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    flagged = [x for x in out if x["checklist_item_id"] in reviewer]
    wrong = [x for x in flagged if reviewer[x["checklist_item_id"]]["grade"] == "wrong"]
    weak = [x for x in flagged if reviewer[x["checklist_item_id"]]["grade"] == "weak"]
    def end_state(x):
        if x["final_question"] is None:
            return "null"
        if x["final_question"] == x["live_question"]:
            return "today's question"
        return "rewritten" if x["final_question"] != x["round2_question"] else "unchanged from round 2"
    summary = {
        "permission_rows": len(out),
        "wrong_end_states": {f"{x['doc']} {x['citation']}": end_state(x) for x in wrong},
        "weak_end_states": {f"{x['doc']} {x['citation']} ({x['source_quote'][:25]})": end_state(x) for x in weak},
        "weak_counts": dict(Counter(end_state(x) for x in weak)),
        "good_rows_changed": [{"row": f"{x['doc']} {x['citation']}", "round2": x["round2_question"], "final": x["final_question"]}
                              for x in out if x["checklist_item_id"] not in reviewer and x["changed_from_round2"] and x["round2_question"] != x["live_question"]],
        "all_rows_changed_from_round2": [f"{x['doc']} {x['citation']}" for x in out if x["changed_from_round2"]],
        "restored_today": [f"{x['doc']} {x['citation']}" for x in out if x["changed_from_round2"] and x["live_question"] and x["final_question"] == x["live_question"]],
        "final_new_questions": sum(1 for x in out if x["final_question"] and x["final_question"] != x["live_question"]),
        "final_none": sum(1 for x in out if not x["final_question"]),
    }
    (OUT / "round3_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    _ = r2_final, kq


if __name__ == "__main__":
    main(Path(sys.argv[1]))
