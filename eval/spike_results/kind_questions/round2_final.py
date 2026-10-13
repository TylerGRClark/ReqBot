"""Round 2: fallback, purpose guard and if-clause fix applied to the round-1 answers plus the round-4 re-run. No model.
  python3 round2_final.py <scratch_dir>
Writes outputs/round2_rows.json (every row whose question or flag differs from the live question) and outputs/round2_summary.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kind_questions as kq  # noqa: E402
from build_rows import load_rows  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

OUT = HERE / "outputs"
load = lambda n: json.loads((OUT / n).read_text())  # noqa: E731


def main(scratch: Path) -> None:
    rows = load_rows(scratch)
    by_id = {r["checklist_item_id"]: r for r in rows}
    old_final = {x["checklist_item_id"]: x for x in load("permission_final.json")}
    r4 = {x["checklist_item_id"]: x for x in load("permission_round4.json")}
    ptr = {p["checklist_item_id"]: p for p in load("pointers.json")}
    out, summary = [], Counter()
    kept_fallback, guard_hits, flag_moves = [], [], []
    for r in rows:
        cid = r["checklist_item_id"]
        live = r.get("audit_question") or None
        k_old, k_new = rk.classify(r), kq.classify_wrapper(r)
        entry = {"doc": r["_doc"], "citation": r.get("citation"), "checklist_item_id": cid, "source_quote": r["source_quote"], "kind_live": k_old["kind"], "kind_wrapper": k_new["kind"],
                 "live_question": live, "new_question": live, "flag": None, "rule": None, "checks": []}
        if k_old["kind"] != k_new["kind"]:
            entry["rule"] = "kind"
        if cid in old_final:  # a permission row under rules-7 (67 rows)
            src = r4.get(cid) or old_final[cid]
            q, limit = src["question"], src.get("limit")
            why = kq.purpose_not_limit(limit) if q else None
            entry["limit"] = limit
            entry["prompt"] = src.get("prompt")
            if q and why:
                guard_hits.append({"citation": r.get("citation"), "doc": r["_doc"], "limit": limit, "why": why, "hand_grade_round1": old_final[cid]["hand_grade"]})
                q = None
                entry["rule"] = f"permission (guard rejected a {why} as limit)"
            else:
                entry["rule"] = "permission (new boundary question)" if q else "permission (no stated limit)"
            if not q:
                keep, reason = kq.fallback_keeps(live, r)
                entry["fallback"] = {"kept": keep, "reason": reason}
                q = live if keep else None
                if keep and live:
                    kept_fallback.append({"doc": r["_doc"], "citation": r.get("citation"), "question": live})
                    entry["rule"] += "; old question kept"
            else:
                entry["checks"] = kq.check_question(q, r, limit)
            entry["new_question"] = q
        elif cid in ptr:
            p = ptr[cid]
            if p["action"] == "suppress":
                entry["new_question"] = None
                entry["rule"] = "pointer (no question: " + p["reason"] + ")"
            else:
                entry["rule"] = "pointer that also states a duty (question kept)"
        if k_old["kind"] == "recommendation" or k_new["kind"] == "recommendation":
            f_old = kq.recommendation_flag(r) if k_old["kind"] == "recommendation" else None
            f_new = kq.recommendation_flag_v2(r)
            entry["flag"] = f_new["strength"] if f_new else None
            if (f_old is None) != (f_new is None):
                flag_moves.append(f"{r['_doc']} {r.get('citation')}")
            if not entry["rule"] or entry["rule"] == "kind":
                entry["rule"] = "recommendation (flag only)" if f_new else "recommendation flag removed (should inside an if-clause)"
        changed = entry["new_question"] != live or entry["flag"] or entry["kind_live"] != entry["kind_wrapper"] or entry["rule"]
        if changed:
            out.append(entry)
    kind_moves = [f"{e['doc']} {e['citation']}: {e['kind_live']} -> {e['kind_wrapper']}" for e in out if e["kind_live"] != e["kind_wrapper"]]
    # wrapper vs rules-7 alone: which rows move because of the if-clause fix?
    ifclause = [f"{r['_doc']} {r.get('citation')}" for r in rows if kq.classify_rules7(r)["kind"] != kq.classify_wrapper(r)["kind"] or kq.should_is_condition(r["source_quote"])]
    vanished = [x for x in old_final.values() if x["before_question"] and not x["question"]]
    vanished_ids = {x["checklist_item_id"] for x in vanished}
    # round-4 answers can turn a null into a question or the reverse; recompute the vanished set from the final answers
    final_q = {cid: (r4.get(cid) or x)["question"] for cid, x in old_final.items()}
    vanished_ids = {cid for cid, x in old_final.items() if x["before_question"] and not final_q[cid]}
    recovered = [e for e in out if e["checklist_item_id"] in vanished_ids and e["new_question"]]
    summary = {
        "rows": len(rows), "rows_that_differ_from_live": len(out),
        "permission_rows": len(old_final), "vanished_in_round1": len(vanished_ids), "vanished_recovered_by_fallback": len(recovered),
        "fallback_kept_total": len(kept_fallback), "fallback_kept": kept_fallback,
        "guard_hits": guard_hits,
        "weak_or_wrong_graded_round1": sum(1 for x in old_final.values() if x["hand_grade"] in ("weak", "wrong")),
        "good_graded_round1": sum(1 for x in old_final.values() if x["hand_grade"] == "good"),
        "wrapper_kind_moves": kind_moves, "ifclause_rows": ifclause, "recommendation_flag_moves": flag_moves,
        "new_question_counts": dict(Counter("question" if e["new_question"] else "none" for e in out)),
    }
    (OUT / "round2_rows.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (OUT / "round2_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("fallback_kept",)}, indent=1, ensure_ascii=False))
    print("by_id check", len(by_id))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
