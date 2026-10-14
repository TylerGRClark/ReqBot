# Round 4 pre-registration (written before any round-4 model call)

Approved by Tyler. Same guardrails as before: experiment folder only; `services/`, sidecars, index and checklist untouched.

## Tyler's grading rule (new)

A restatement of the source is not a defect by itself. A new question is only worse than the live one when TODAY's live question was more meaningful. I use this rule to describe results and to decide fallbacks. I do not grade my own questions; a different blind reviewer grades the held-out rows.

## Part A: the six AFIs (at most 1 prompt round, 12 calls)

Rows: afi10-2402 2.17.2.1, 2.17.5, 2.20.2.1, 2.20.4 (the four waivers); dafman17-1305 4.4.1.3; afi10-2402 3.3.3.5.1 (both rows: "coordinate ... waive periodicity requirements for up to two years" and "Waivers can be granted a maximum of two years for any specific JMAA"); proposed additions: afi17-203 3.8.1, dafman17-1305 4.1.12, 1.2.2, 3.2.2, 4.2.1.

Changes: prompt v7 gives the model the sentence(s) just before the requirement so "this/such/they" can be named; new deterministic checks: bare "this/it/they" as the scope clause's subject is rejected; a sentence that opens with a pronoun is accepted only if the question names something from the antecedent; scope words after "for any specific X / each X" must stay in the question; a new question that carries fewer of the source's content words than a grounded, non-duty today's question yields to today's question.

Criteria (A):
- (A1) The four waiver rows get four different questions; each names what is waived (the TS / SCI clearance for personnel, or the TS / SCI facility access) and the approving office (HAF CARM Program office, or the FOA's HHQ's functional manager).
- (A2) afi10-2402 2.20.4's question is at least as specific as today's (it names the facility requirement and the functional manager; mechanical check: the question carries every one of today's source content words that today's question carries, or today's question is kept).
- (A3) dafman17-1305 4.4.1.3 names the reimbursement, the self-funded certification, the new role's foundational requirement and the end-of-fiscal-year funding allowance.
- (A4) afi10-2402 3.3.3.5.1 "Waivers can be granted..." keeps JMAA.
- (A5) Proposed additions are listed as proposals only if every check passes; a row whose limit sits outside its own quote (4.2.1's "observational requirement may be waived", which is in the next sentence) is reported as not drafted.
- (A6) No "Does the unit" for a may; no placeholders; every kept number/qualifier (mechanical).

## Freeze

After part A the code and prompt are committed and the commit id is written below in a "Freeze" section (a separate commit made before any part B call). No change to rules, prompt or checks between that commit and the end of part B.

## Part B: held-out test (no tuning; the real test)

Documents (never used so far): CJCSI 6510.02G, DODI 5200.01, DODI 5200.44, DODI 5200.48, DODI 8410.03, DODI 8551.01, NIST.SP.800-125. Rows from `cli/reqbot.py checklist --doc "<key>" --format json`, kinds from the wrapper (rules-7 verbs + if-clause fix). Frozen pipeline: permission rows get one model call (prompt v7, serial) and `decide()`; recommendation rows get the label; pointer rows are decided deterministically. Model-call cap 150 (stop and report if reached).

Criteria (B), fixed now:
- (B-a) 0 rows dropped (every checklist row appears in the output).
- (B-b) No pointer suppression removes a real duty; each suppressed row read by hand and said so in the report.
- (B-c) Report the rate at which the deterministic checks reject a model question (rejected / questions the model gave). A high rate (more than about 40%, versus the six AFIs' rate in round 3, reported next to it) is read as over-fitting to the AFIs.
- (B-d) Every new question keeps every number, time word, condition word and "for any specific X" scope word of its source clause (mechanical; the count of violations should be 0 by construction, and any hit is a bug).
- Reported without grades: per document, row counts by kind; new boundary questions; nulls; today's questions kept; pointer suppressions; recommended labels; and EVERY row whose question differs from today's live question.

## Limits stated in advance

The checks were written after reading AFI outputs, so part A numbers are in-sample. Part B is the held-out test, but I wrote the rules and I can read the rows, so any statement about quality there waits for the blind reviewer. The checklist rows for the held-out documents come from the live index as of 2026-10-14.
