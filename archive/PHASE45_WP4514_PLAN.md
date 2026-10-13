# WP-45.14 — whole sentences, never pieces (plan, pre-registered)

*Owner's rule (2026-10-09): when a requirement is extracted, extract at minimum the whole sentence it sits in, never an incomplete sentence. Motivation: the checklist shows rows such as "installation of vulnerable applications, and other breaches of existing AF or DoD policy", "then take the indicated Actions" and "Include the mission owner in the process.", and the inclusive prompt (WP-45.13) re-cuts already-covered paragraphs into more and smaller records (AFI 17-203: 157 rows against about 113, quote overlap with the baseline 0.35). Expanding every quote to its whole sentence also merges the pieces of one sentence into one record.*

## 1. The rule under test (one change, offline)

For every Step D survivor, find its `source_quote` in the text of its chunk (whitespace-tolerant, the way the checklist locates a quote) and expand it to the whole sentence: left to the sentence's start, right to its end, where a sentence ends at `.`, `?` or `!` followed by a space and a capital letter, a digit or an opening bracket, or at the end of a paragraph unit; not after an abbreviation (single capital + full stop, `U.S.`, `e.g.`, `i.e.`, `No.`, `Fig.`, `Sec.`, `Para.`), not after a paragraph number (`3.6.1.1.`), and not at `;` or `:` (a list item's sentence starts where the list's sentence starts). The leading paragraph number or bullet is dropped from the expanded text. Records whose expanded quote is identical (same chunk, same text) become one record, keeping the first record's other fields. The result is always a verbatim substring of the chunk. A quote that cannot be located, or whose sentence would exceed 700 characters, is left as it is and counted.

Applied to the Step D survivors of **T2a, T2b** (current prompt) and **D1x** (inclusive prompt), from the scratch runs of WP-45.11 and WP-45.13. No model call, no pipeline change.

## 2. Measures and rules (fixed now)

- **E1 no loss of coverage.** Recall of the 74 owner-labeled obligations by the Step D survivors, before and after, per arm; it must not fall (a longer quote can only cover more).
- **E2 completeness.** The share of survivors that are incomplete (the quote starts with a lower-case letter, or ends without `.`, `?`, `!`, `:`, `;` or a closing bracket after one of these) before and after, per arm. The rule is met if the share after is at most 2% of the survivors that could be expanded.
- **E3 size.** Survivors before and after (after merging) per arm and per document; quotes that could not be located; quotes over 700 characters after expansion (left unexpanded). Reported, not gated; the owner's view is that fewer, whole-sentence records are acceptable.
- **E4 the owner reads.** A seeded sample of 30 survivors whose quote changed (`random.Random(4514)`), shown as the original and the expanded text with the source paragraph; the owner rates the expanded one **better**, **same** or **worse**. The rule is adopted for a pull request only if E1 and E2 are met and at least 80% of the rated pairs are better or same.
- **AFI view, reported:** the AFI 17-203 checklist built from the expanded T2a and D1x survivors against the originals: row counts and hint counts (`starts_mid_sentence`, `table_fragment`, `quote_not_located_in_passage`, `no_stated_actor`).

## 3. Decision

If E1, E2 and E4 hold, a pull request adds the expansion as a step after Step D's grounding (before enrichment and indexing), with tests; it changes `source_quote` and the number of records for every document and therefore needs the owner's go-ahead, re-extraction is **not** needed (it runs on existing Step D output), and a reindex is. If not, the result is reported and nothing changes.

## 4. Limits stated now

The sentence splitter is a rule, not a language model: it will mis-split some legal citations and sentences with unusual punctuation; the labeled recall is 74 obligations on three documents; E4 is one rater's reading of 30 pairs.
