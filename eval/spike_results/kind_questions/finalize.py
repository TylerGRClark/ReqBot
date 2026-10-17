"""Combine the rounds into the final per-row table and the summary numbers. No model. Run after run_experiment.py (det, perm 1..3).
Hand grades are the agent's reading of each final question (index = position in outputs/permission_round2.json). They are one reader's judgement, not Tyler's.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kind_questions as kq  # noqa: E402

OUT = HERE / "outputs"
load = lambda n: json.loads((OUT / n).read_text())  # noqa: E731

# index in round 2 -> (grade, note). Anything not listed with a question is "good"; unlisted nulls are "null_ok".
HAND = {
    11: ("weak", "the 'may necessitate' is a description; the question asks about the scheduled cycle, which is not the limit"),
    19: ("weak", "restates the permission: a category changed 'to reflect the new data' is always yes"),
    20: ("wrong", "asks whether the contact was for guidance: the purpose, not a limit"),
    22: ("weak", "the 'working in conjunction' limit is about the staff option only; reads stilted"),
    26: ("weak", "'is it depending upon' is awkward and nearly restates the permission"),
    36: ("weak", "the 'limit' is the purpose (to reflect mission directives)"),
    37: ("wrong", "the question is about presenting a certificate; the limit is 'without network access'; hollow"),
    65: ("weak", "'periodically' is not a limit; always yes when the report is made"),
    9: ("null_missed", "the 'up to two (2) years' bound is a real limit; the model picked 'if required' and then correctly refused it"),
    35: ("null_missed", "'where they may complement or address areas not otherwise addressed' is a condition (this is an 'encouraged' row)"),
    44: ("null_missed", "'that have overlapping KSAs ... within the overlap' is a real condition"),
    49: ("null_missed", "applies only to members cyber coded but serving in civilian development positions (a who-limit)"),
    43: ("null_ok", "two alternatives, no restriction (round 1 asked a question; round 2 refused)"),
}
WEAK_LIMIT = re.compile(r"^\W*(?:for|to|in order to)\b|^\W*[a-z]+ly\W*$", re.IGNORECASE)  # a purpose or a bare adverb as the 'limit'


def main() -> None:
    r1 = {x["checklist_item_id"]: x for x in load("permission_round1.json")}
    r2 = load("permission_round2.json")
    r3 = {x["checklist_item_id"]: x for x in load("permission_round3.json")}
    final = []
    for i, x in enumerate(r2):
        f = r3.get(x["checklist_item_id"], x)
        grade, note = HAND.get(i, ("good" if f["question"] else "null_ok", ""))
        if i in (37, 65, 36, 19, 20, 22, 26) and f["question"]:
            pass
        final.append({**{k: f[k] for k in ("doc", "citation", "checklist_item_id", "source_quote", "before_question", "limit", "question", "why_null", "failures")},
                      "kind_old": "permission", "kind_new": "permission", "prompt": f["prompt"], "round1_question": r1[x["checklist_item_id"]]["question"],
                      "hand_grade": grade, "hand_note": note, "weak_limit_guard": bool(f["question"] and f["limit"] and WEAK_LIMIT.match(f["limit"]))})
    (OUT / "permission_final.json").write_text(json.dumps(final, indent=1, ensure_ascii=False))
    ids2 = {x["checklist_item_id"] for x in r2}
    rows = {}
    for rnd, name in ((1, "permission_round1.json"), (2, "permission_round2.json"), (3, "permission_round3.json")):
        data = [x for x in load(name) if x["checklist_item_id"] in ids2]
        q = [x for x in data if x["question"]]
        failing = [x for x in q if [f for f in x["failures"] if f != "C5_limit_not_verbatim"]]
        c5 = [x for x in q if "C5_limit_not_verbatim" in x["failures"]]
        anyfail = [x for x in q if x["failures"]]
        rows[rnd] = {"rows_run": len(data), "questions": len(q), "nulls": len(data) - len(q), "fail_C1_to_C4": len(failing), "fail_C5": len(c5), "fail_any": len(anyfail),
                     "by_check": dict(Counter(f for x in q for f in x["failures"]))}
    q = [x for x in final if x["question"]]
    summary = {"permission_rows_after_rules7": len(final), "rounds": rows,
               "final_questions": len(q), "final_nulls": len(final) - len(q),
               "final_fail_C1_to_C4": sum(1 for x in q if [f for f in x["failures"] if f != "C5_limit_not_verbatim"]),
               "final_fail_any": sum(1 for x in q if x["failures"]),
               "final_hand_grades": dict(Counter(x["hand_grade"] for x in final)),
               "final_weak_limit_guard_flags": sum(x["weak_limit_guard"] for x in final),
               "guard_flags_that_are_hand_weak_or_wrong": sum(1 for x in final if x["weak_limit_guard"] and x["hand_grade"] in ("weak", "wrong")),
               "hand_weak_or_wrong_total": sum(1 for x in final if x["hand_grade"] in ("weak", "wrong"))}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    # recommendation questions: do any carry duty words?
    recs = load("recommendations.json")
    print("recommendation rows:", len(recs), "with a question:", sum(1 for r in recs if r["before_question"]))
    print("recommendation questions containing must/shall/required:", [r["citation"] for r in recs if r["before_question"] and kq._DUTY_WORDS.search(r["before_question"])])


if __name__ == "__main__":
    main()
