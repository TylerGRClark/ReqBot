# Round 3 pre-registration (written before any round-3 model call)

Trigger: an independent blind reviewer graded the round-2 output 18 good / 10 weak / 3 wrong (my self-grade was 27 / 4 / 0). The self-grades were too generous. This round does not defend round 2 and does not certify itself: the final grades are the next blind reviewer's.

## Reviewer's cases (regression set, 13 rows of the 31 new boundary questions; the other 18 were graded good)

WRONG: afi10-2402 3.3.3.5.2; dafman17-1305 4.2.1; dafman17-1305 4.1.12.
WEAK: afi10-2402 3.6.2; afi17-203 3.8 (deviation); afi17-203 3.8 (law-enforcement sensitive); dafman17-1305 1.2.3 (suspension); 1.2.4; 4.1.15; 4.1.19; 4.4.1.2; 4.4.1.3; 6.2.1.
LOST-USEFUL: afi10-2402 3.3.3.3.4 (restore today's question).
Note: afi10-2402 2.17.2.1 / 2.17.5 and 2.20.2.1 / 2.20.4 carry identical questions because their permission sentences are word-for-word identical ("This may be waived to a SECRET level with a justification memorandum sent through ...").

## Changes

1. **Qualifier check** (deterministic, `round3_checks.py`): every number, time word (temporarily, annually, within, until, during, before, after ...) and condition word (while, if, unless, only, provided) in the permission's own sentence must appear in the question, else the question becomes null. List numbering, tier marks, paragraph numbers and identifiers are not counted. A **subject check**: at least half of the content words of the permission's subject must appear in the question (else the trigger or actor was dropped).
2. **Future / other-party check**: a permission sentence about a "future" revision, or whose decision belongs to another party (accepted for credit at the college), becomes null. The other-party marker list is narrow and was fitted to the reviewer's case.
3. **Dangling-reference check**: a permission sentence that opens with They/Such/These/Those/It/"In such cases", or a question containing "such", becomes null. A limit that only points at "applicable provisions/procedures" becomes null.
4. **Fallback**: a rejected or null row falls back to today's question when it passes the round-2 fallback; plus two narrow additions: (a) when the model said the "may" only describes, a Do/Does-shaped old question is kept if it has no must/shall/required and no "does the unit"; (b) when a check rejects a question whose sentence uses a descriptive modal (may necessitate / include / vary / need / result), today's question is kept if grounded and has no must/shall/required.
5. **Prompt v5**: scope clause keeps every qualifier; reasons, means, pointers to provisions, pronoun subjects, future and other-party decisions are null.

## Which rows are re-run

Only the 13 reviewer-flagged rows get the model again (prompt v5), and only if a first v5 round leaves a flagged row failing a check do I run a second round on those rows. The other 18 rows keep their round-2 text unchanged unless a deterministic check rejects them. Maximum 2 prompt rounds, at most 30 calls.

## Criteria (fixed now)

- (R1) The 3 WRONG rows: each ends as null, today's question, or a question that passes every check; none stays as in round 2. Mechanical count reported; "good" for a rewritten question is for the reviewer.
- (R2) At least 7 of the 10 WEAK rows end as null, today's question or a rewritten question that passes every check and differs from round 2. Reported separately: how many become null (certain not to be weak) and how many are rewritten (reviewer must decide).
- (R3) No row the reviewer graded good gets worse: every row whose question text differs from round 2 is listed. A good row that a check turns to null counts as worse and is reported as a false alarm.
- (R4) afi10-2402 3.3.3.3.4 gets today's question back.
- (R5) At most 2 prompt rounds, at most 30 calls.

## Limits stated in advance

The deterministic checks were calibrated on the round-2 outputs including the reviewer's cases, so they are fitted, and a dry run on those outputs (no model) was done before this file. Zero false alarms on the 18 good rows is therefore expected, not evidence of generalisation. The prompt, the checks and the final read are all mine; the grade that counts is the next blind reviewer's.
