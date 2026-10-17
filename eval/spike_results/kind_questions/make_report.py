"""Write report.md (plain words, for Tyler) from outputs/*.json. No model."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
perm = json.loads((OUT / "permission_final.json").read_text())
ptr = json.loads((OUT / "pointers.json").read_text())
rec = json.loads((OUT / "recommendations.json").read_text())
r7 = json.loads((OUT / "rules7_changes.json").read_text())
S = json.loads((OUT / "summary.json").read_text())


def find(doc, cite, start):
    return next(x for x in perm if x["doc"] == doc and x["citation"] == cite and x["source_quote"].startswith(start))


def cut(t, n=230):
    t = (t or "").replace("|", "/").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "..."


def row(x, note=""):
    after = x["question"] or "(no question)"
    return f"| {x['doc']} {x['citation']} | {cut(x['source_quote'], 170)} | {cut(x['before_question']) if x['before_question'] else '(none)'} | {cut(after)} | {note} |"


PICK = [
    ("afi10-2402", "2.17.5", "This may be waived", "The example from the brief, now produced."),
    ("afi10-2402", "2.20.4", "2) In addition", "Old question asked the unit to do the waiver; new one checks the memo route."),
    ("afi10-2402", "2.17.2", "(T-1) In addition: Exemptions", "Old question was about a different paragraph (an appointment letter)."),
    ("afi10-2402", "3.3.3.5.1", "Waivers can be granted", "A numeric limit becomes a check."),
    ("afman17-2101", "2.10.1 (inferred)", "AFOs can only", "Same idea, plainer wording."),
    ("afman17-2101", "3.1.1.1.4", "Per reference", "A 'may' with no limit: the old 'Does X support...' question goes away."),
    ("afi17-203", "3.8", "In such cases, information", "Old question invented a 'need to know' rule that is not in the text."),
    ("afi17-203", "3.1", "Intrusion activity may include", "Descriptive 'may include': no question."),
    ("dafman17-1305", "1.2.3", "User network access may be suspended", "The old question asked if controls CAN suspend; new one asks if suspension was for the stated reason."),
    ("dafman17-1305", "1.2.3", "Unit training managers are authorized", "Grant with a stated condition."),
    ("dafman17-1305", "4.1.7", "Authorizing Officials may extend", "Old one kept only the last clause (no consecutive waivers); new one covers all the limits."),
    ("dafman17-1305", "4.2.1", "DAF Civilian and military", "Supervision condition."),
    ("dafman17-1305", "4.4.2", "SAF/CN may direct", "Coordination condition."),
    ("dafman17-1305", "4.4.1.3", "Maintenance of self-funded", "Reimbursement limit."),
    ("dafman17-1305", "4.1.1", "Completion of residential", "Two options, no restriction: no question (old one asked 'can').") ,
]
lines = ["# Kind-aware draft audit questions: spike report", "", "For Tyler. Plain words. Nothing in the live checklist or index was touched; every result is a file in this folder.", ""]
lines += ["## The short version", "",
          f"- I looked at 1,418 checklist rows in six documents. {S['permission_rows_after_rules7'] + 3} are classed as permissions (\"may\", \"can\", \"is authorized to\"), 24 as recommendations (\"should\"), 11 as pointers (\"can be found in ...\").",
          f"- **Permissions.** The new rule asks \"was the stated limit met when the permission is used?\" It produced {S['final_questions']} questions and kept {S['final_nulls']} rows without one. "
          f"No question failed the form checks (made-up words, filler, not a yes/no, or a \"may\" turned into a \"must\"); one question paraphrased the limit instead of quoting it. "
          f"Reading them myself: {S['final_hand_grades']['good']} good, {S['final_hand_grades']['weak']} weak, {S['final_hand_grades']['wrong']} wrong.",
          "- **Recommendations.** All 24 keep their question unchanged and get a separate \"recommended, not required\" label. Two rows are mislabelled as recommendations by the kind rules (see below).",
          "- **Pointers.** 8 pure pointers lose their question (one had a question; it was a wrong one). 3 rows that also state a duty keep theirs. I read all 11: no real duty is lost.",
          "- **The \"Authorize release...\" fix.** Three rows change kind (from permission to a plain duty: a command with no named actor) and nothing else in 1,418 rows changes. The cause was not the word \"authorize\": the verb list did not know it, so a \"can\" in the next sentence won.",
          "- **No row was dropped.** Every row is still in the output, with its before and after.", ""]
lines += ["## What a number like \"0 failures\" does and does not mean", "",
          "The checks only look at the form of a question. I also read all 36 myself. 8 of 36 (22%) are weak or wrong, mostly because the model treats a *purpose* (\"to reflect the new data\") as if it were a *limit*. "
          "A weak question is not harmful, but it is always answered \"yes\", so it adds noise. I could not fix this with the prompt in three rounds. A cheap guard (flag any question whose \"limit\" starts with \"for\" or \"to\", or is one adverb) catches "
          f"{S['guard_flags_that_are_hand_weak_or_wrong']} of the 8 and wrongly flags 4 good ones, so it would be a review hint, not a filter.", ""]
lines += ["## The prompt rounds", "",
          "| Round | Change | Rows run | Questions | Failed form checks | Failed quote check |", "|---|---|---|---|---|---|",
          f"| 1 | first prompt | 67 | {S['rounds']['1']['questions']} | {S['rounds']['1']['fail_C1_to_C4']} (two tripped the must/required check, one of them a false alarm that quoted the source; one made-up word) | 0 |",
          f"| 2 | said what counts as a real limit; null for descriptive \"may include/vary/need\"; two worked examples; banned \"is it required\" | 67 | {S['rounds']['2']['questions']} | 0 | 1 |",
          f"| 3 | purposes, bare adverbs and always-yes questions are not limits | 18 (the weak ones plus 10 good ones as a check) | {S['rounds']['3']['questions']} | 0 | 1 |",
          "", "Round 3 changed the wording of the weak ones but not their weakness; I stopped there (limit: 3 rounds).", ""]
lines += ["## Before and after: permission rows (the most informative 15)", "",
          "| Row | Source text | Before | After | Note |", "|---|---|---|---|---|"]
for doc, cite, start, note in PICK:
    lines.append(row(find(doc, cite, start), note))
lines += ["", "## Rows I am unsure about (every one)", "",
          "| Row | Source text | Before | After | Why unsure |", "|---|---|---|---|---|"]
unsure = [
    ("afi10-2402", "3.3.3.4.2 (inferred)", "A geometric mean", "First half is a method statement (\"A geometric mean is used\"); the \"can use\" half is the permission. The old question was about the first half and is lost."),
    ("dafman17-1305", "3.2.2", "In some circumstances", "A list of four qualification parts; item 4 (20 hours a year of continuing development) looks like a real requirement. Kind \"permission\" is a poor fit for the row, and the old question is lost."),
    ("afi10-2402", "3.3.3.3.4", "Although PSS", "\"Standard PSS activities include ...\" reads as a description of what is normally done; the old question is lost and may have been useful."),
    ("dafman17-1305", "4.1.3", "Continuing education requirements that have", "The overlap condition looks like a real limit; the model said none."),
    ("afi10-2402", "3.3.3.5.1", "CCMDs, Services, and Agencies may coordinate", "\"Up to two (2) years\" is a real limit; the model picked \"if required\" and refused it (the next row, Waivers can be granted a maximum of two years, does carry it)."),
    ("afpd_17-1", "3.15 (inferred)", "The application of the provisions", "\"Where they may complement ...\" is a condition; round 1 asked it, rounds 2 and 3 said null."),
    ("afi17-203", "3.4.2.1", "As the investigation", "Question restates the permission (always yes)."),
    ("afi17-203", "3.4.4.2", "The author may contact", "Asks whether the contact was for guidance: the purpose, not a limit."),
    ("dafman17-1305", "1.2.2", "Users without network access", "Question is about presenting a certificate; the real limit is \"without network access\"."),
    ("dafman17-1305", "1.1.6", "Commanders and Program Managers", "The \"limit\" is a purpose (to reflect mission directives)."),
    ("dafman17-1305", "6.3.1", "SAF/CNSF may periodically", "\"Periodically\" is not a limit; always yes."),
    ("afi17-203", "3.8", "An incident/event investigation involving LE/CI", "\"Is it depending upon the nature...\" is awkward and close to a restatement."),
]
for doc, cite, start, why in unsure:
    lines.append(row(find(doc, cite, start), why))
lines += ["", "## Permission rows that still get no question, and why", "",
          f"{S['final_nulls']} rows. Reasons the model gave and I agreed with (27): the \"may\" only describes (\"may include\", \"may vary\", \"may need\"), the row states no restriction (\"can register for an account\", \"may be established for ...\"), "
          "the listed \"limit\" is only a purpose, or the row offers alternatives without restricting them. 13 of the 31 had a question before; those are in the unsure list when I think the loss matters. "
          "4 I think are missed limits (listed above: 3.3.3.5.1, 3.15, 4.1.3, 4.1.13).", ""]
nl = [x for x in perm if not x["question"]]
lines += ["| Row | Source text | Before | Reason given |", "|---|---|---|---|"]
for x in nl:
    lines.append(f"| {x['doc']} {x['citation']} | {cut(x['source_quote'], 150)} | {cut(x['before_question'], 120) if x['before_question'] else '(none)'} | {cut(x['why_null'], 110)} |")
lines += ["", "## Recommendations: how the flag would look", "",
          "Question text is not changed. A separate field says: *Recommended, not required: the text says \"should\". A \"no\" is worth noting but is not a violation.* Example:", "",
          "| Row | Source text | Question (unchanged) | Flag |", "|---|---|---|---|"]
for r in rec[:6]:
    lines.append(f"| {r['doc']} {r['citation']} | {cut(r['source_quote'], 150)} | {cut(r['before_question'], 150) if r['before_question'] else '(none)'} | recommended |")
lines += ["", "Two of the 24 are not really recommendations: afi10-2402 3.3.2 (\"... assess the mission impact *should* those vulnerabilities be successfully exploited\" is an \"if\"), and afi17-203 3.4.4.3 (\"determine if the process *should* be initiated\" is a duty, and it carries a tier mark). "
          "Both would be wrongly labelled \"recommended\". A kind rule that skips \"should\" before \"those/these/this\" and inside an \"if\" clause would fix them; not done here.", ""]
lines += ["## Pointer rows (all 11, read by hand)", "", "| Row | Source text | Before | Decision |", "|---|---|---|---|"]
for p in ptr:
    lines.append(f"| {p['doc']} {p['citation']} | {cut(p['source_quote'], 170)} | {cut(p['before_question']) if p['before_question'] else '(none)'} | {p['action']}: {cut(p['reason'], 90)} |")
lines += ["", "One bug was caught on the way: my first version suppressed \"Lead support efforts with Centers/Wings ... Assessment types are described in section 3.3\" because \"Lead\" was not in the verb list. It now keeps its question. "
          "That is the kind of miss to expect elsewhere: the check for \"also states a duty\" depends on the verb list.", ""]
lines += ["## The fix for rows that open with a command (candidate kind rules, version 7)", "", "| Row | Source text | Kind before | Kind after | Why |", "|---|---|---|---|---|"]
for c in r7["changes"]:
    lines.append(f"| {c['doc']} {c['citation']} | {cut(c['source_quote'], 150)} | {c["kind_old"]} | {c["kind_new"].replace("duty_imperative", "duty (command, no named actor)")} | first word is a command the verb list did not know; the \"can\" in the second sentence had decided the kind |")
lines += ["", "All three are right by my reading. The questions on these rows do not change (they already ask about the duty). Nothing else among the 1,418 rows changes kind. "
          "Verbs added for the test: authorize, allow, permit, grant, deny, delegate, withhold, revoke, suspend, restrict, prevent, lead.", ""]
lines += ["## What looks wrong", "",
          "1. **Weak questions (8 of 36).** The model confuses a purpose with a limit. This is the main weakness and I could not remove it with wording.",
          "2. **13 old questions disappear** when the new rule answers null. For about 8 the loss is fine or an improvement (a \"does the unit do X\" on a \"may\", or a purely descriptive row). For about 4 (the unsure list) it removes something useful. A safer policy: when the new rule says null and the old question was a plain \"Can ...?\", keep the old one.",
          "3. **\"Permission\" is applied to whole sentences.** A row with a duty in one half and a \"may\" in the other (3.3.3.4.2, 3.2.2) is judged on the \"may\" half only.",
          "4. **\"may\" that is not a grant is common** (common among permission rows: \"may include\", \"may vary\"). The kind rules cannot tell them apart; the model did, mostly.",
          "5. **I graded my own output** and I wrote the prompt. Tyler's review is the real test; the weak/wrong labels are one reader's opinion.",
          "6. Small sample: 67 permission rows, one run per prompt, no repeat to measure run-to-run noise.",
          ""]
(HERE / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("ok", len(lines))
