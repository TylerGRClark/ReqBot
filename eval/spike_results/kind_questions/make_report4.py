"""Write report.md (round 4, plain words, for Tyler) from outputs/round4_*.json. No model, no grades."""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
A = json.loads((OUT / "round4_partA.json").read_text())
B = json.loads((OUT / "round4_partB_rows.json").read_text())
S = json.loads((OUT / "round4_partB_summary.json").read_text())
HELD = list(S["per_doc"])


def cut(t, n=230):
    t = (t or "").replace("|", "/").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "..."


def short(e):
    return f"{e['doc']} {e['citation'] or '(no number)'}"


if (HERE / "report.md").exists() and not (HERE / "report_round3.md").exists():
    shutil.copy(HERE / "report.md", HERE / "report_round3.md")

L = ["# Kind-aware draft audit questions, round 4: report for Tyler", "",
     "Plain words. Nothing in the live checklist or index was touched. Earlier reports are kept: `report_round1.md`, `report_round3.md` (round 3, which also holds the round-2 list). **I do not grade the questions in this report.** A different blind reviewer grades the held-out rows.", "",
     "Your rule applied here: a question that restates its source is not a defect by itself. A new question is only worse when today's live question was more meaningful.", ""]
n_new = sum(v["new_boundary_questions"] for v in S["per_doc"].values())
rate = S["check_rejection_rate"]
L += ["## The short version", "",
      f"- **Part A (the six AFIs, the reviewer's list):** the four waiver rows now have four different questions that name what is waived and the right office. The duration row keeps its JMAA scope. 4.4.1.3 ends as no question (the model kept dropping the word \"reimbursement\"; a check now catches that).",
      f"- **Part B (held out, rules frozen before it ran):** 7 documents, {S['rows']} rows, 0 dropped, {S['model_calls']} model calls (cap 150). {n_new} new boundary questions. The checks rejected {rate['rejected']} of {rate['model_questions']} questions the model wrote ({round(100 * rate['rejected'] / max(1, rate['model_questions']))}%); on the six AFIs the round-3 checks rejected 9 of 31 (29%, in-sample).",
      "- Every new question in part B keeps every number and qualifier of its source clause (mechanical check; " + (str(len(S["new_questions_missing_qualifier"])) + " exceptions: " + ", ".join(S["new_questions_missing_qualifier"]) if S["new_questions_missing_qualifier"] else "0 exceptions") + ").", ""]
L += ["## Part A: the rows from the reviewer's list", "",
      "| Row | Source text | Today's live question | Round 3 | Round 4 | How it came out |", "|---|---|---|---|---|---|"]
for a in A:
    how = a["rule"] + ("; retried once with feedback" if a.get("retry") else "") + ("; " + "; ".join(a["notes"]) if a["notes"] else "")
    L.append(f"| {short(a)} | {cut(a['source_quote'], 140)} | {cut(a['live_question']) if a['live_question'] else '(none)'} | {cut(a['round3_question']) if a['round3_question'] else '(none)'} | {cut(a['question'], 300) if a['question'] else '(no question)'} | {cut(how, 160)} |")
L += ["", "Part A criteria as set before running:", "",
      "- Four waiver rows, four different questions naming the waived thing and office: yes. Two (2.17.2.1 and 2.20.2.1) are built by rule from the sentence before them (\"When the requirement that ... is waived to a SECRET level, was there a justification memorandum sent through ...\"); they are stiff but name the clearance requirement.",
      "- 2.20.4 at least as specific as today's: yes by the word-count check (18 of the source's content words against today's 15).",
      "- 4.4.1.3: not met. The final result is no question.",
      "- 3.3.3.5.1 duration row keeps JMAA: yes.",
      "- Proposed additions: 4.1.12 and 4.2.1 drafted (4.2.1's text that the observation requirement \"may be waived\" is in the next sentence, outside the row's quote, so it is not covered); 1.2.2 keeps today's question; 3.8.1 and 3.2.2 not drafted.",
      "- Part A was run twice on the same 12 rows (a first pass, then again after I added a retry-with-feedback and the waiver rule); that is more than the one pass I was allowed to describe, so these results are in-sample.", ""]
L += ["## Part B: per document (held-out, frozen rules)", "",
      "| Document | Rows | Permission / recommendation / pointer | Model calls | New questions | No question | Today's kept | Checks rejected | Pointers suppressed | Labels | Rows that differ from today |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for d, v in S["per_doc"].items():
    k = v["kinds"]
    L.append(f"| {d} | {v['rows']} | {k.get('permission', 0)} / {k.get('recommendation', 0)} / {k.get('pointer', 0)} | {v['model_calls']} | {v['new_boundary_questions']} | {v['null_after']} | {v['todays_question_kept']} | {v['model_questions_rejected_by_checks']} of {v['model_gave_question']} | {v['pointer_suppressed']} | {v['recommended_labels']} | {v['rows_differ_from_live']} |")
L += ["", "### Every permission row whose question differs from today's live question", "", "| Row | Source text | Today's question | New question | How |", "|---|---|---|---|---|"]
perm = [e for e in B if e["model_called"] and e["final_question"] != e["live_question"]]
for e in sorted(perm, key=lambda e: (e["doc"], e["citation"] or "")):
    L.append(f"| {short(e)} | {cut(e['source_quote'], 150)} | {cut(e['live_question']) if e['live_question'] else '(none)'} | {cut(e['final_question'], 300) if e['final_question'] else '(no question)'} | {cut(e['rule'], 110)}{'; ' + '; '.join(e['notes']) if e['notes'] else ''} |")
L += ["", "### Permission rows where the checks turned the model's question into no question", "", "| Row | Source text | Model's question | Why rejected | Today's question |", "|---|---|---|---|---|"]
for e in sorted([e for e in B if e["model_called"] and e["model_question_rejected"]], key=lambda e: (e["doc"], e["citation"] or "")):
    L.append(f"| {short(e)} | {cut(e['source_quote'], 140)} | {cut(e.get('model_question_raw'), 200)} | {cut(e['rule'], 140)} | {cut(e['live_question']) if e['live_question'] else '(none)'} |")
L += ["", "### Pointer rows (read by hand for a real duty)", "", "| Row | Source text | Today's question | Decision |", "|---|---|---|---|"]
for e in B:
    if (e["rule"] or "").startswith("pointer ("):
        L.append(f"| {short(e)} | {cut(e['source_quote'], 220)} | {cut(e['live_question']) if e['live_question'] else '(none)'} | {cut(e['rule'], 120)} |")
L += ["", "### \"Recommended, not required\" labels (question text unchanged)", "", "| Row | Source text | Question |", "|---|---|---|"]
for e in sorted([e for e in B if e["flag"]], key=lambda e: (e["doc"], e["citation"] or "")):
    L.append(f"| {short(e)} | {cut(e['source_quote'], 140)} | {cut(e['live_question'], 140) if e['live_question'] else '(none)'} |")
moves = [e for e in B if e["kind_live"] != e["kind_wrapper"]]
L += ["", "### Rows whose kind changes under the wrapper", ""] + ([f"- {short(e)}: {e['kind_live']} to {e['kind_wrapper']}" for e in moves] or ["- none"])
lost = [e for e in B if e["model_called"] and e["live_question"] and not e["final_question"]]
kept = [e for e in B if e["model_called"] and e["live_question"] and e["final_question"] == e["live_question"]]
waiver = [e for e in B if "waiver question built" in (e["rule"] or "")]
retried = [e for e in B if e.get("retried")]
perm_all = [e for e in B if e["model_called"]]
L += ["", "## What still looks wrong", "",
      "I have not graded the questions; these are things I can see from counts and from reading the table, not quality grades.", "",
      f"1. **Today's questions disappear on many rows.** {len(lost)} permission rows had a live question and end with none; {len(kept)} keep today's. Many of the lost ones are rows where the \"may/can/should\" sits in a side clause and the main clause states something that looks checkable (for example NIST.SP.800-125 \"images need to be carefully protected\", \"monitoring ... on an ongoing basis\"). The kind rules sent them down the permission path; the permission path found no limit and removed the question. By your rule these are the rows to look at first.",
      f"2. **Most held-out permission rows end with no question** ({sum(1 for e in perm_all if not e['final_question'])} of {len(perm_all)}). NIST.SP.800-125 is mostly descriptive prose with \"can\" and \"may\"; that is expected, but it also means the permission path adds only {sum(v['new_boundary_questions'] for v in S['per_doc'].values())} new questions across seven documents.",
      f"3. **Check rejections:** {rate['rejected']} of {rate['model_questions']} model questions ({round(100 * rate['rejected'] / max(1, rate['model_questions']))}%), against 29% on the six AFIs in round 3. Lower, so this is not a sign of the checks being fitted to the AFIs in the way I feared; it can also mean the held-out sentences carry fewer qualifiers. One rejection reason (\"such\") sent back a question that did resolve its pronoun in two rows (DODI 5200.48 3.9).",
      f"4. **The waiver template fired {len(waiver)} time(s)** in the held-out set; it is specific to the AFI 10-2402 pattern. {len(retried)} rows used the retry-with-feedback.",
      "5. **Some new questions are thin.** For example NIST.SP.800-125 2.1 (\"was there careful control?\") and 5.5 (\"is data being wiped?\") keep the trigger but lose most of the sentence's meaning. By your rule they are only worse if today's question was more meaningful; there was no live question on those two.",
      "6. **Pointer suppressions:** 2 rows (DODI 5200.48 definitions link; DODI 8410.03 \"This instruction is available on the Directives Division Website\"). I read both: neither states a duty. The live question on the second (\"Is this instruction available ...?\") was about the document, not the unit.",
      "7. **Mechanical qualifier check:** 0 new questions drop a number, time word, condition word or \"for any specific\" scope word of their source clause.",
      "8. **What I cannot say:** whether the new questions are good. A blind reviewer has to decide that; the held-out rows were not tuned on.", ""]
(HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("written", len(L))
