"""Builds report.md (for Tyler) and outputs/review_sheet_test.md (for the blind reviewer) from the frozen TEST results. No model call; reads outputs/ only.

The 'author notes' below were written by the experiment's author after reading every proposed split. They are observations to help the reviewer look, NOT grades.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
res = json.loads((OUT / "results_v2_test.json").read_text())
tune = json.loads((OUT / "results_v2_tune.json").read_text())["summary"]
tune1 = json.loads((OUT / "results_v1_tune.json").read_text())["summary"]
post = json.loads((OUT / "posthoc_test.json").read_text())
S = res["summary"]
rows = res["rows"]
changed = [r for r in rows if r["final"] == "split"]
fallbacks = [r for r in rows if r["decision"] == "split" and r["final"] != "split"]
hedge = {x["id"]: x["added"] for x in post["added_hedge"]}
broken = {x["id"] for x in post["broken_lead"]}
nogain = set(post["no_gain"])

# author observations by position in `changed` (1-based), plain words; observations, not grades
UNSURE = {
    5: "Part 3 says 'considerations are included', a word the source does not use.",
    7: "Parts invent 'as required' and 'the Service provides / maintains'; the source says the office leads the assessment so that the Service budgets for, develops, acquires, supports and maintains.",
    9: "The lead question stops mid-sentence ('... to ensure?').",
    15: "Five parts each say 'as required', which is not in the source; 'life cycle and risk management processes' became two separate items.",
    17: "The lead adds 'as required', which is not in the source.",
    25: "The lead stops mid-sentence ('... if they do not?'); the parts read as fragments.",
    30: "Adds 'when applicable' to every part and rewords 'in accordance with' to 'followed / adhered to'.",
    38: "Four parts replace a 3 x 2 list (establish and track, for investments, programs and acquisitions); two combinations are missing.",
    45: "The lead stops mid-sentence ('... disposed of according to?').",
    50: "The three parts hand each source (Master Plan, IEMA Roadmap, other roadmaps) to one verb (plan or program); the source does not say that.",
    58: "The source says the line 'may be omitted'; the part asks 'is the line omitted?'. The lead repeats today's whole question.",
    63: "The lead says 'on both networks, as appropriate'; neither phrase is in the question.",
    65: "Four parts each say 'as required', which is not in the source; 'forum allows posting' is reworded.",
    66: "The lead stops mid-sentence ('... required for?').",
    67: "Adds 'as appropriate' to a duty that is already conditional ('if ... remains solely in the RT&E network').",
    76: "Parts ask whether sources 'exist'; the source says the knowledge service 'provides' them for a stated purpose that no part keeps.",
}


def esc(t: str) -> str:
    return (t or "").replace("|", "\\|").replace("\n", " ")


def cut(t: str, n: int) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n].rstrip() + " (cut)"


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


per_doc: dict[str, Counter] = {}
for r in rows:
    c = per_doc.setdefault(r["doc"], Counter())
    c["candidates"] += 1
    c[r["decision"]] += 1
    c["changed"] += r["final"] == "split"

fb = S["fallback_by_check"]
words = {
    "qualifiers": "a number, time limit or condition word of today's question is missing",
    "terms": "a name, number or acronym that is not in today's question or the row",
    "shape": "wrong shape (more than 5 parts, only 1 part, or a part over 25 words)",
    "pronouns": "a 'they / it / this / these' with nothing before it to point at",
    "modality": "a 'may / should' turned into a duty, or the reverse",
    "coverage": "one of the listed items is missing from the pieces",
    "actor": "the lead does not name today's actor",
}
clean = post["passing_splits"] - len({x["id"] for x in post["added_hedge"]} | {x["id"] for x in post["broken_lead"]} | nogain)

L = []
a = L.append
a("# Splitting long audit questions into a lead and a/b/c parts: test result\n")
a("*For Tyler. Experiment only: nothing live changed, no checklist, index or question was edited. The numbers below are machine checks. Nobody has yet judged whether a split "
  "is faithful or easier; that needs a different, blind reviewer (a ready sheet is included).*\n")
a("## The short version\n")
a(f"- On five documents the model was asked about **{S['candidates']} long or stacked questions**: a random sample of at most 40 per document, out of 378 such questions and 763 questions in all.")
a(f"- It said **keep (already one thing) for {S['keep']}** ({pct(S['keep'], S['candidates'])}) and proposed a split for **{S['split_proposed']}**.")
a(f"- Of those {S['split_proposed']} splits, **{S['split_passed_all_checks']} ({pct(S['split_passed_all_checks'], S['split_proposed'])}) passed all seven machine checks**; the other {S['fallback_rows']} fell back to today's question unchanged. "
  f"**The target was 80%, so it was missed.**")
a(f"- **No row was dropped** ({S['rows_out']} in, {S['rows_out']} out); every question that failed a check simply stays as it is today.")
a(f"- The longest piece got shorter: among the {S['split_passed_all_checks']} changed rows the median longest piece went from {S['changed_rows_median_before']:.0f} to {S['changed_rows_median_after']:.0f} words (90th percentile {S['changed_rows_p90_before']:.0f} to {S['changed_rows_p90_after']:.0f}). "
  f"Across all {S['candidates']} candidates, counting the keeps and the fallbacks at their old length, the median went from {S['all_candidates_longest_piece_median_before']:.0f} to {S['all_candidates_longest_piece_median_after']:.0f} "
  f"and the 90th percentile from {S['all_candidates_longest_piece_p90_before']:.0f} to {S['all_candidates_longest_piece_p90_after']:.0f}.")
a(f"- **A third of the passing splits are not really easier.** In {len(nogain)} of the {len(changed)} the longest piece is still more than 80% as long as today's question; "
  f"in {len(hedge)} the model added 'as appropriate' / 'as required' / 'when applicable', which is in neither the question nor the source and makes a duty sound optional; "
  f"in {len(broken)} the lead question stops mid-sentence. Only {clean} of the {len(changed)} are free of all three.")
a("- **My recommendation: do not ship this as it is.** The idea works on clean lists (see the best rows below), but the machine checks are not enough, and the model copied a hedge phrase "
  "from my own prompt example. A second, tighter round and a blind review of the rows below would be the next step; nothing needs deciding before 2026-10-15.\n")

a("## How the test was run\n")
a("- Two tuning rounds on three other documents (AFI 10-2402, AFI 17-203, DAFMAN 17-1305), then the wording was frozen and the five test documents were run once.")
a(f"- Tuning: round 1 passed {tune1['split_passed_all_checks']} of {tune1['split_proposed']} proposed splits ({pct(tune1['split_passed_all_checks'], tune1['split_proposed'])}); round 2 passed {tune['split_passed_all_checks']} of {tune['split_proposed']} ({pct(tune['split_passed_all_checks'], tune['split_proposed'])}). "
  "The big win in round 2 was telling the model to repeat the noun in each part instead of writing 'they' or 'it'.")
a("- The test result fell short of tuning (61% vs 75%), as expected for wording tuned on three documents and tried on five new ones. DODI 5200.48 was the weakest "
  "(10 changed out of 22 proposed), and the model often produced more than five parts.")
a("- About 440 model calls in all, on the local model that writes today's questions. The model was not run twice on the same row, so run-to-run noise is not measured.\n")

a("## Per document\n")
a("| Document | Questions looked at | Model said keep | Split proposed | Passed checks (changed) |")
a("|---|---|---|---|---|")
for d, c in per_doc.items():
    a(f"| {d} | {c['candidates']} | {c['keep']} | {c['split']} | {c['changed']} |")
a("")
a("## Why the other splits fell back\n")
a("A row can fail more than one check, so these add up to more than the number of fallbacks.\n")
a("| Check | Rows | What it means |")
a("|---|---|---|")
for k in sorted(fb, key=lambda x: -fb[x]):
    a(f"| {k} | {fb[k]} | {words.get(k, '')} |")
a("")
a(f"- {S['only_one_check_failed']} of the {S['fallback_rows']} fallbacks failed exactly one check.")
a("- **The 'shape' fallbacks are mostly the model ignoring 'at most 5 parts'**: 11 of the 26 had 6 to 9 parts, 3 had only one part, and the rest had a part over 25 words. That is a model fault, not a check fault.")
a("- **The 'actor' check was too fussy on this test.** All 11 rows that failed it were things like 'CMO's' versus 'CMOs' or a verb caught in the window; the lead, "
  "'Does AMC do all of the following?', was fine. The check was frozen before the test, so I did not fix it; it cost about 10 passes. Even counting those, the pass rate would be about 69%, still under 80%.")
a("- The 'terms' check caught one real error (the model wrote Executive Order 12331 for 12333) and had two false alarms (a capitalised first word 'Leverage', and GS-15 written '(GS)-15').\n")

a("## What looks good\n")
a("Rows where the lead plus parts read cleanly and every item and condition of the question is kept (author's reading, not a grade): "
  "#1 (NC3 assessments to SecAF, CSAF, others), #13, #33, #42, #59, #68, #72, #77, #79, #80. "
  "These share a shape: one actor, one verb, a plain list of three or fewer objects, no side conditions.\n")

a("## Rows I am unsure about\n")
a("These are my reading notes on the rows below, so the reviewer knows where to look. They are not grades.\n")
for n in sorted(UNSURE):
    r = changed[n - 1]
    a(f"- **#{n}** ({r['doc']} {r['citation']}): {UNSURE[n]}")
a("")

a("## What still looks wrong\n")
a(f"1. **The model invents hedges.** In {len(hedge)} passing splits a part carries 'as appropriate', 'as required' or 'when applicable' that the source does not have. "
  "My worked example in the prompt used 'as appropriate', and the model copied it. A hedge on a duty is the very thing you were wary of (a duty turning into something optional). "
  "The machine checks only looked for dropped qualifiers, not added ones.")
a(f"2. **Not shorter.** {len(nogain)} of {len(changed)} passing splits repeat the whole question as the lead, or repeat a long closing condition in every part, so the auditor reads the same long words several times. "
  "Many 'in accordance with X, Y, and Z' rows came out this way; for those, the split is arguably worse than today's single question.")
a("3. **Lists that are not independent.** Where the question mixes verbs and objects (rows #38 and #50) the model splits them in ways the source does not say. The checks cannot see this; only a reader can.")
a("4. **Leads can be empty.** 'Does the unit do all of the following?' is formulaic and tells the auditor nothing alone. It is safe, but it is not the 'short lead question' you described.")
a("5. **Broken sentences.** Three leads end mid-sentence ('... to ensure?', '... according to?'). One part turns 'may be omitted' into 'is omitted' (row #58).")
a("6. **Wording drift.** Some parts reword the source ('followed' for 'in accordance with', 'exist' for 'provide'). Each is small; together they are the 'different' you said a rewrite must never be.")
a("7. **Checks are strict in places and blind in others.** They are strict on synonyms, 'within' for places, and on sentence-initial capitals; they are blind to a verb moved to the wrong object, an added hedge, or a lead that is just filler.")
a("8. **Only 197 of 378 candidates were tried** (a sample of at most 40 per document), and only one model at one setting.")
a("9. **A fault that is already in today's question** (not caused by the split): for DODI 8551.01 paragraph 1.1 the source says this issuance 'Does not alter or override' existing authorities; "
  "today's question reads 'Does this issuance alter or override ...?', which asks the opposite. The split inherited that (it was sent back for another reason). It is the kind of dropped 'not' "
  "you were worried about, found in the current questions.\n")

a("## Targets against the result\n")
a("| Target (set before the run) | Result |")
a("|---|---|")
a(f"| 0 rows dropped | Met: {S['rows_out']} in, {S['rows_out']} out (a fallback keeps today's question) |")
a(f"| At least 80% of proposed splits pass all checks | **Not met: {pct(S['split_passed_all_checks'], S['split_proposed'])}** ({S['split_passed_all_checks']} of {S['split_proposed']}) |")
a(f"| Longest piece falls (median and 90th percentile) | Met in direction: changed rows median {S['changed_rows_median_before']:.0f} to {S['changed_rows_median_after']:.0f}, 90th {S['changed_rows_p90_before']:.0f} to {S['changed_rows_p90_after']:.0f}; all candidates median {S['all_candidates_longest_piece_median_before']:.0f} to {S['all_candidates_longest_piece_median_after']:.0f}, 90th {S['all_candidates_longest_piece_p90_before']:.0f} to {S['all_candidates_longest_piece_p90_after']:.0f}; but see 'not shorter' above |")
a(f"| Report how many the model keeps | {S['keep']} of {S['candidates']} ({pct(S['keep'], S['candidates'])}) |")
a("| Blind reviewer grades faithfulness and ease | **Not done yet.** Sheet is ready; the author did not grade |")
a("")

a("## One decision for you\n")
a("Whether to spend more effort on splitting questions, given that the first real test was mixed. Nothing is live, so any choice can be undone.\n")
a("1. **Blind-review the 80 rows first (recommended).** A different reviewer fills in the sheet (about an hour); I then fix the prompt (drop the 'as appropriate' example, cap at 5 parts, add checks "
  "for added hedges and broken leads) and run one more round. Costs one evening of local-model calls; changes nothing live.")
a("2. **Park it.** Keep today's questions, which you called good, and revisit after you have used the checklist at work.")
a("3. **Use only the clean cases.** Ship splits only where one actor has one verb and a plain list of three or fewer, passing all checks. Smaller gain, lower risk, but still unreviewed.")
a("Reason for 1: the machine checks passed rows that are plainly unfaithful (invented hedges), so a person must see a sample before any decision about shipping.\n")

a("## Before and after for every changed question in the test set\n")
a(f"{len(changed)} rows. All of them passed the seven machine checks (so 'checks' here lists only the extra notes). The source quote is shown in full on the review sheet.\n")
a("| # | Document, paragraph | Source quote | Today's question | Proposed lead, then parts | Checks and notes |")
a("|---|---|---|---|---|---|")
for i, r in enumerate(changed, 1):
    parts = "<br>".join(f"{chr(97 + k)}) {esc(p)}" for k, p in enumerate(r["parts"]))
    notes = ["7 of 7 pass"]
    notes.append("not shorter" if r["id"] in nogain else "shorter")
    if r["id"] in hedge:
        notes.append("ADDED " + ", ".join(f"'{h}'" for h in hedge[r["id"]]))
    if r["id"] in broken:
        notes.append("lead ends mid-sentence")
    if i in UNSURE:
        notes.append("author unsure")
    a(f"| {i} | {esc(r['doc'])} {esc(r['citation'])} | {esc(cut(r['source_quote'], 420))} | {esc(r['today'])} | **{esc(r['lead'])}**<br>{parts} | {'; '.join(notes)} |")
a("")

a("## Splits the checks sent back to today's question\n")
a(f"{len(fallbacks)} rows (they stay exactly as today). The failed check is listed so you can see whether the check or the model was at fault.\n")
a("| Document, paragraph | Today's question | Failed check(s) | First problem |")
a("|---|---|---|---|")
for r in fallbacks:
    first = r["checks"][r["failed"][0]][0] if r["checks"].get(r["failed"][0]) else ""
    a(f"| {esc(r['doc'])} {esc(r['citation'])} | {esc(cut(r['today'], 200))} | {', '.join(r['failed'])} | {esc(cut(first, 140))} |")
a("")
a("*The files for this experiment are under eval/spike_results/compound_questions in the draft pull request: the plan written before any model call, the frozen wording, the results, and the review sheet.*")
(HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---- blind review sheet ----------------------------------------------------------------------------------------------------------------------------------------------------------
R = []
b = R.append
b("# Review sheet: split audit questions (blind)\n")
b("Reviewer: you did not write these and have not seen the machine checks. For each row, read the source quote, then today's question, then the proposal.\n")
b("Grade two things. Leave notes if unsure.\n")
b("- **Faithful**: does the proposal ask for exactly what the source quote requires? `Y` = yes, nothing dropped, added or made stronger or weaker (may/should/must, conditions, numbers, who acts). "
  "`N` = something is dropped, added, hedged or changed. `?` = cannot tell.")
b("- **Easier**: would an auditor find it easier to check than today's single question? `Y` / `N` / `same`.")
b("- An invented 'as appropriate' / 'as required' counts as N for Faithful. A part that is only filler counts as N for Easier.\n")
for i, r in enumerate(changed, 1):
    b(f"## {i}. {r['doc']} {r['citation']}\n")
    b(f"**Source quote:** {' '.join((r['source_quote'] or '').split())}\n")
    b(f"**Today's question:** {r['today']}\n")
    b(f"**Proposed lead:** {r['lead']}\n")
    for k, p in enumerate(r["parts"]):
        b(f"- {chr(97 + k)}) {p}")
    b("\nFaithful (Y/N/?): ____    Easier (Y/N/same): ____    Notes: ____________________\n")
(OUT / "review_sheet_test.md").write_text("\n".join(R) + "\n", encoding="utf-8")
print("report.md and review_sheet_test.md written;", len(changed), "changed rows,", len(fallbacks), "fallbacks")
