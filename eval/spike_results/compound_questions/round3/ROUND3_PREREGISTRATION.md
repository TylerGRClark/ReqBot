# Round 3 pre-registration: the narrow split (nothing live changes)

Written and committed 2026-10-14 BEFORE any round 3 model call. Branch `feat/compound-question-split-spike` (PR #342). Same guardrails as rounds 1 and 2: nothing under services/, pipeline/,
sidecars, the index or the checklist is touched; today's questions are never edited; the author does not grade faithfulness.

## Why

A blind reviewer graded the 80 passing TEST splits of round 2 (frozen prompt v2): faithful 43 Y / 29 N / 8 ?; easier 38 Y / 28 same / 14 N; only 32 of 80 both. Failures: 13 rows invent
"as required / as appropriate / when applicable"; 4 leads end mid-sentence; 2 duplicate parts; cross-product loss when a list is split (38, 50, 29, 39); strength / actor changes (7, 43);
one "may be omitted" became "is the line omitted?". Plain verb-list and recipient-list splits worked. So: split only those, and refuse the rest by rule.

## Rule 1: when a split is attempted at all (code, before any model call)

A candidate (a row whose question is over 30 words, or a series of 3+ items with at least 20 words; same selector as rounds 1 and 2) is sent to the model only when ALL hold
(`round3/narrow.py: eligible`):
- today's question opens with Does or Do (an active question; passives such as "Are ... notified" are not attempted);
- it holds exactly one "and" and 2 to 4 commas (a 3 to 5 item list "A, B, and C"); no brackets, semicolons or colons;
- neither today's question nor the source quote holds any of: may, might, can, cannot, could, should, if, unless, only, solely, at least, within, until, no later than, except, when, whenever,
  upon, once, before, after, prior to, or, and/or, not, never, no, none, without, prohibited, forbidden, as appropriate, as required, as necessary, as needed, as applicable, when applicable,
  annually, quarterly, monthly, weekly, daily, immediately, promptly, minimum, maximum, up to, such as, including, to include, e.g., i.e., for example, in addition, also, as well as, both,
  either, neither, than, but, while; or a number with a time unit ("5 days", "one hour").
Everything else keeps today's question, with no model call ("kept by the gate").
The model is also asked to say `kind` = verbs (one actor, a list of actions) or objects (one action, a list of things or recipients) or to say keep. A proposed split whose kind is neither
counts as a Rule 1 violation by the model, whatever the checks say.

## Rule 2: hard checks (any failure = today's question unchanged)

(a) **hedge**: no word of a fixed hedge list (as required, as appropriate, when applicable, if applicable, as necessary, as needed, necessary, properly, proper, appropriate(ly), applicable,
    allow(s/ed/ing), needed, adequate(ly), effective(ly), sufficient(ly), timely, reasonable/reasonably, where possible, ...) in any piece unless the same word is in the source quote.
(b) **lead**: opens Does/Do; ends with "?"; contains "the following"; at most 30 words; its last word is not one of: to, of, in, with, for, by, on, at, from, if, whether, that, which, who, and, or,
    the, a, an, not, as, than, according, accordance, ensure(s), so, under, over, per, via.
(c) **coverage**: every content stem (words of 4+ letters, simple suffix stripping, function words removed) of today's question appears in the lead or some part, and no content stem appears in a
    piece that is in neither today's question nor the source quote (only "following", "done", "mean" are allowed extras). This catches dropped and added verbs, objects, recipients, qualifiers.
(c2) **parts**: exactly one part per list item (commas + 1), kind verbs or objects; verbs parts are Does/Do questions; objects parts are noun phrases of at most 14 words; each ends with "?" and
    has at most 25 words. This is the cross-product guard (a list of verbs times a list of objects is refused because it has two "and").
(d) **distinct**: no two parts have the same stem set.
(e) **strength and actor**: no permission word (may, might, can, could, should, permitted, allowed, optional, encouraged, recommended, authorized) and no duty word (must, shall, required, requires,
    mandatory, need to, have to) in the output that is not in the source quote or today's question; the lead's actor words equal the words after today's opening Does/Do (a verb of today's question
    may follow them).

## Prompt

`round3/prompts3.py`. v1 has no "as appropriate" example (round 2's copied example is gone); all three worked examples use only words from their own source and contain no hedge word.
At most 2 prompt rounds on the TUNE documents only (afi10-2402, afi17-203, dafman17-1305), ALL candidates, gated. Then the prompt id and the code are frozen (section "Freeze", committed before
the fresh run) and the FRESH set is run once.

## FRESH set (documents the round 1 and 2 TEST set did not use)

CJCSI 6510.02G, DODI 5200.01, DODI 5200.44, and dafi36-2903 capped at 40 candidates (seeded random sample before the gate, seed `compound-split-round3-2026-10-14`).
Excluded: DODI 5200.48 and 8551.01, afi13-550, afman17-2101, afpd_17-1 (used); DODI 8410.03, NIST.SP.800-125 (sealed).
All candidates of the three smaller documents are used (no sample), so the number of model calls is the number of gate-eligible rows (expected a few dozen).

## Pre-registered targets (FRESH set)

1. 0 rows dropped (rows in = rows out; a refused split keeps today's question).
2. Of the splits the model proposes, at least 90% pass all checks. A proposal whose kind is not verbs / objects is counted as a failure of Rule 1 and reported separately.
3. Zero hedge words in passing splits (by construction of check (a)); also report the raw count of hedge words in the model's proposals before the check.
4. Report the keep rate (all candidates that end with today's question) and the share of ALL candidates that end with a split. Expected: small. This variant trades coverage for safety.
5. A blind review sheet in the round 2 format for every passing split, with no machine-check results on it. The author does not grade.

## Freeze

Frozen 2026-10-14 after two TUNE rounds, before any FRESH call. **Prompt v2, id `c26881680f6d1d6b`** (model qwen2.5:14b, temperature 0.1), with `narrow.py` (gate and checks) as committed with
this freeze. No edit to the prompt, gate, checks or candidate selector is allowed before the FRESH run; the FRESH set is run once.

TUNE record (all 365 candidates of the three TUNE documents, gate applied; only a handful pass the gate, so tuning evidence is thin and I say so):

| | v1 | v2 (frozen) |
|---|---|---|
| candidates passing the gate (sent to the model) | 12 | 10 |
| model says keep | 7 | 6 |
| splits proposed | 5 | 4 |
| splits passing all checks | 4 (80%) | 4 (100%) |
| hedge words in raw model output | 0 | 0 |

Changes made during tuning (after seeing round 1): (1) the gate gained `requested, tasked, as directed, directed, as specified, specified, as determined, determined, as designated, as defined,
if any` (a split of "... as requested" passed every check but "as requested" is a condition); this removed 2 rows from the sent set. (2) Prompt v2 changes only the lead rule (words before the
list go before "all of the following", words after it go after) and adds one worked example with words after the list, because one v1 lead dropped "for continued network access"
(caught by check (c)). All v1 and v2 answers are in `outputs/`. With n this small, "100%" on the TUNE set is not evidence of a 90% pass rate; the FRESH run is the test.
