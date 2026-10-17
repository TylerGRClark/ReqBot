# Round 5 pre-registration (written before any round-5 model call)

Experiment folder only; `services/`, sidecars, index and checklist untouched. Today's live question is the baseline for every comparison.

## Status of the held-out documents

CJCSI 6510.02G, DODI 5200.01, 5200.44, 5200.48, 8410.03, 8551.01 and NIST.SP.800-125 drove these fixes (an independent reviewer graded their round-4 rows and the fixes below answer that review). **They are no longer a clean test.** The only clean test left is the fresh document dafi36-2903, run once with the frozen rules.

## Reviewer's round-4 findings being fixed

Of 13 new questions 4 good, 7 weak, 2 wrong; 16 live questions removed, 9 of them useful. All 9 losses came from "the checker rejected the model question, or found no stated limit, and today's question was deleted".

## Changes (round5_checks.py, prompt v8)

1. **Additive only.** The permission path may add a question where the row has none, or replace today's question only when a mechanical test says the new one is clearly better (it carries at least 80% of the content words of the stated limit while today's carries under 50%, and it is not less specific overall), or when today's question is a bare capability question ("Can X ...?" with no number or limit word) or an invented "recognize / consent / acknowledge" question. A rejected question or "no stated limit" leaves today's question unchanged. A bare capability or invented question is removed only when the rule found no stated limit; every removal is listed.
2. **"such as" is not dangling; "such X" is dangling only inside the first six words of the question.**
3. **Main-verb gate** (before any model call, so a gated-out row keeps today's question): may/can/is authorized to must be the main verb of the row's own sentence. Detection: the sentence holding the first genuine permission word; drop an introductory clause up to its comma; keep what follows the last colon or semicolon; the subject region before the modal must hold no subordinator (that, which, who, if, when, unless, because, while ...), no duty word (shall, must, will, should, need to, ensure, is responsible ...), no negation (No ..., unless, may not, prohibited), must not open with a third-person command verb (a role-list bullet whose main verb is the first word), must be at most 25 words, and the words after the modal must not be a description (may include / vary / need / contain / require ...); "authority" as a noun does not count.
4. **May-to-duty check:** a content verb that follows the source's modal ("may be used", "may need to be wiped") may not appear only in the asked half of the question (after the first comma) and not in the scope clause.
5. **Document gate:** the permission path is off for a document whose permission + recommendation rows are at least 25% of its rows (guidance prose). Labels for "should" rows stay; today's questions stay. Expected to exclude NIST.SP.800-125 only (38%); all others are under 8%.

Prompt v8 = v7 plus "keep 'only'" and "never turn 'may be used' into 'was used'". Retry-with-feedback as in round 4.

## Criteria (fixed now)

- (R-a) No live question is removed except a bare capability or invented question, and only where the rule found no stated limit and the row passed the gates. Pointer suppression (round-4 rule, reviewer found both fine) remains and is listed separately.
- (R-b) The three missed-limit cases are regression cases, reported not graded: DODI 8551.01 2.4 (OIG representative "may attend in a non-voting role only"), DODI 5200.48 4.1 ("may be transmitted via first class mail, parcel post, or bulk shipments"), DODI 5200.48 3.7 (dissemination "to conduct official business ... in accordance with law").
- (R-c) The DODI 5200.48 3.9 rows are not rejected for "such" (mechanical).
- (R-d) No accepted new question trips the may-to-duty check, drops a number / time / condition / "for any specific" scope word (mechanical), or uses a bare "this/it" scope subject.
- (R-e) Report which documents the gate excludes and the shares.
- (R-f) Fresh document dafi36-2903: only permission, recommendation and pointer rows are processed; model calls at most 150 in total for the round. If the document has more gate-passing permission rows than the remaining budget, a fixed deterministic sample (first N by SHA-1 of the checklist item id) is asked and the rest are left at today's question; the sample size and count of rows not asked are reported.
- Every row whose question or label differs from today's live question is listed; I give no quality grades.

## Order

1. This file and the code are committed. 2. Regression run on the seven documents. 3. A freeze marker commit (FREEZE section appended below). 4. The one fresh run on dafi36-2903. Nothing in the rules or prompt changes after step 3.

## Limits

I wrote the gates after reading the reviewer's findings and the round-4 rows, so the seven-document numbers are in-sample. The fresh document is a dress-and-appearance instruction, a different style from the others: a good or bad outcome there says little about other documents.

## FREEZE (committed before the fresh-document run)

Frozen code and prompt: commit `81adca3989768ddbfce86af9fecb3a1d0841189e` (round5_checks.py, round4_checks.py, round3_checks.py, kind_questions.py, run_round5.py; prompt v8). Changes made during the regression pass, before this freeze, and disclosed: purpose guard exempts a limit that also states a restriction ("in accordance with", "only", ...); retry hints for a sentence that says "only" and for a closed list of permitted means ("via a, b, or c"); subject check reads the subject after the last colon; the may-to-duty check reads the permitted verb, not later nouns; the third-person-command gate needs two or more words before the modal. Regression calls: 35 in total (27 first pass; later passes reused cached answers and asked only where a new hint or rule applied). The three missed-limit cases from the reviewer (OIG representative "non-voting role only", CUI "first class mail, parcel post, or bulk shipments", dissemination "to conduct official business ... in accordance with a law") were tuned for; they are regression cases, not evidence. Fresh run: dafi36-2903, permission / recommendation / pointer rows, remaining budget 150 - 35 = 115 calls, sample 80% = 92 gate-passing permission rows (SHA-1 order). No change after this commit.
