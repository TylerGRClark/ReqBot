# WP-45.14 — whole sentences, never pieces (results so far)

Plan and rules: [docs/PHASE45_WP4514_PLAN.md](../../../docs/PHASE45_WP4514_PLAN.md) (pushed before any measurement). The owner's rule: an extracted requirement is at minimum the whole sentence it sits in. `pipeline/sentence_expand.py` (pure functions, **not wired into the pipeline**) finds each Step D survivor's quote in its chunk and expands it to the sentence; survivors with the same expanded text in the same chunk merge. Offline on the survivors of the existing scratch runs: **T2a, T2b** (current prompt) and **D1x** (inclusive prompt). `evaluate.py` produces `outputs/sentence_rule_report.json` and the owner's sample `outputs/sentence_rule_sample_for_rating.md`.

Two bugs found by reading the first sample pairs (before any rating) and fixed: a bracketed reference label such as `(k).` was treated as an initial, so a sentence ran into the next one and ended with a cut word; and an inline list marker such as `(g)` stayed at the start of the expanded sentence. Both have tests. Review then found two more, also fixed with tests and the numbers below re-measured: a sentence that ends in a dotted citation ("... in DoDI 8510.01.") was read as ending in a paragraph number, so unrelated sentences were joined; and flat numbered or capital-lettered list items (`1.`, `A.`) were not treated as separate units.

## Registered measures

| | T2a | T2b | D1x |
|---|---|---|---|
| **E1** labeled obligations (of 74) covered by the survivors, before → after | 45 → 47 | 46 → 48 | 67 → 68 |
| **E2** incomplete quotes among those that could be expanded, before → after | 162 → 18 of 1,717 (**1.05%**) | 176 → 17 of 1,732 (**0.98%**) | 358 → 56 of 2,336 (**2.4%**) |
| **E3** Step D survivors, before → after merging | 1,880 → 1,868 | 1,890 → 1,875 | 2,501 → 2,461 |
| quotes changed / unchanged / not located / left as given for length | 247 / 1,470 / 145 / 18 | 263 / 1,469 / 138 / 20 | 669 / 1,640 / 158 / 7 (+27 one-word quotes left alone) |

**E1 is met** (a longer quote can only cover more; recall of the labeled sample does not fall in any arm) and **E2 is met on the current prompt but NOT on D1x**: after the fixes the one-word table cells are left alone and still counted, so D1x ends at 56 of 2,336 = 2.4% incomplete (bar 2%). 26 of those 56 are the one-word acronym-table cells (`CNSI`, `DNI`), which are table scraps, not cut sentences, and carry the `table_fragment` hint; the first version scored 1.7% only because it expanded them into whole glossaries (units 11 and 13, which the owner could not relate to the originals). This was found by review of #279 and is reported as measured. **E4 (owner's rating of the first version, `outputs/sentence_rule_sample_for_rating.md`, 30 of 1,006 changed quotes from T2a and D1x): 25 of 30 better or same = 83%, met (bar 80%).** 22 were "better" (mostly the list marker dropped: "- a. ", "(3) "), and 3 of those were "much better" or "one of the best examples" (units 23, 26, 27: pieces that become whole requirements; 27 restores a second requirement that had been dropped silently), and 5 not: unit 18 (worse), 25 (worse), 11 and 13 (a one-word cell expanded into a whole glossary), 19 (a glossary definition, not a requirement; the expansion is garbled). Counting 11, 13 and 19 as not better is the strict reading; unit 22 was "better" but kept an inner "(a)".

## Fixes after the rating (2026-10-09)

The ratings exposed five behaviours, fixed in `pipeline/sentence_expand.py` with tests (`tests/unit/test_sentence_expand.py`, 17 passing) and checked offline against the same 30 pairs:

| unit | what he saw | fix | now |
|---|---|---|---|
| 7, 25 | a bare bullet `- ` kept at the start | a bare bullet and any run of markers (`3. (a) `) is dropped | clean |
| 22 | `3.` removed but `(a)` left | same | clean |
| 11, 13 | a one-word cell (`CNSI`, `DNI`) expanded to a whole glossary | a one-word quote is not expanded (status `too_short`) | stays `CNSI` / `DNI` |
| 18 | `CUI misuse` (a table cell) put in front of a complete sentence | up to six words with no punctuation before a quote that is already a whole sentence are a cell, not part of it | clean |
| 19 | a glossary definition (lowercase term) joined to its neighbours | **not fixed**: the owner says it is not a requirement; glossary definitions stay a known limit | unchanged |

Only these six of the 30 outputs changed; the other 24 are identical, so the 83% is for the first version and the fixed version is the same or better on every rated pair. A fresh sample for any further rating is `outputs/sentence_rule_sample_after_fixes.md` (not rated). Re-measured with the fixes (table above): E1 unchanged and met; E2 met for T2a and T2b, **not met for D1x (2.4%)** once the 27 one-word quotes are counted.

## After wiring review (#280)

Review of the wiring found that a quote occurring twice in one chunk was expanded around its first occurrence (and the second record then merged away, losing a duty). The rule now leaves such a quote as given (`ambiguous`: T2a 1, T2b 1, D1x 7 records), and the pipeline also de-duplicates by source reference and quote after expansion so that two chunks reaching the same sentence cannot share one record ID. Re-measured: T2a 1,880 → 1,868 survivors (18 of 1,717 incomplete); T2b 1,890 → 1,875 (17 of 1,732); D1x 2,501 → 2,462 (55 of 2,331 = 2.4%, still above the 2% bar for the reason given above); labeled coverage unchanged (47, 48, 68).

## What the numbers show

- The rule repairs about 87% of the incomplete quotes (162 → 18, 176 → 17 on the current prompt; D1x 358 → 56 counting the one-word cells). What remains is mostly table rows, glossary strings and quotes that run to the end of a chunk.
- **It merges little.** Survivors fall by about 1% on the current prompt and 3% on the inclusive prompt (2,501 → 2,461). The inclusive prompt's extra records are mostly different sentences, not pieces of the same one, so the whole-sentence rule alone does not bring the record count back down; the "more and smaller records" seen on AFI 17-203 (157 rows against about 113) is not mainly pieces of one sentence.
- **Quotes that could not be located (about 8%)** are mostly composites already built by the pipeline: of six I read, four were a lead-in joined to its list item ("Individuals (Contractor Personnel) shall: Obtain or meet appropriate cyberspace qualification ..."), which are whole sentences by construction and are left alone.
- On the AFI sheets the rule trims the hints a little: AFI 17-203 D1x `starts_mid_sentence` 13 → 9 and rows 157 → 153, T2a 6 → 4 (rows unchanged at 111); AFI 13-550 D1x 6 → 0 mid-sentence; AFI 10-2402 D1x 356 → 352 rows. Table scraps and quotes not located in the passage are unaffected.

## Limits

The splitter is a rule, not a language model; a sentence that runs past the end of its chunk stays unfinished (no terminal punctuation) and is counted as incomplete; E4 is one rater's reading of 30 pairs. Nothing is wired: adopting the rule is a step after Step D's grounding (before enrichment and indexing), changes `source_quote` and the record count for every document, needs the owner's go-ahead, and a reindex but not a re-extraction.
