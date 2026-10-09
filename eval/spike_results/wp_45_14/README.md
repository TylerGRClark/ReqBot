# WP-45.14 — whole sentences, never pieces (results so far)

Plan and rules: [docs/PHASE45_WP4514_PLAN.md](../../../docs/PHASE45_WP4514_PLAN.md) (pushed before any measurement). The owner's rule: an extracted requirement is at minimum the whole sentence it sits in. `pipeline/sentence_expand.py` (pure functions, **not wired into the pipeline**) finds each Step D survivor's quote in its chunk and expands it to the sentence; survivors with the same expanded text in the same chunk merge. Offline on the survivors of the existing scratch runs: **T2a, T2b** (current prompt) and **D1x** (inclusive prompt). `evaluate.py` produces `outputs/sentence_rule_report.json` and the owner's sample `outputs/sentence_rule_sample_for_rating.md`.

Two bugs found by reading the first sample pairs (before any rating) and fixed: a bracketed reference label such as `(k).` was treated as an initial, so a sentence ran into the next one and ended with a cut word; and an inline list marker such as `(g)` stayed at the start of the expanded sentence. Both have tests. Review then found two more, also fixed with tests and the numbers below re-measured: a sentence that ends in a dotted citation ("... in DoDI 8510.01.") was read as ending in a paragraph number, so unrelated sentences were joined; and flat numbered or capital-lettered list items (`1.`, `A.`) were not treated as separate units.

## Registered measures

| | T2a | T2b | D1x |
|---|---|---|---|
| **E1** labeled obligations (of 74) covered by the survivors, before → after | 45 → 47 | 46 → 48 | 67 → 68 |
| **E2** incomplete quotes among those that could be expanded, before → after | 162 → 19 of 1,717 (**1.1%**) | 176 → 18 of 1,732 (**1.0%**) | 358 → 40 of 2,336 (**1.7%**) |
| **E3** Step D survivors, before → after merging | 1,880 → 1,868 | 1,890 → 1,875 | 2,501 → 2,434 |
| quotes changed / unchanged / not located / left as given for length | 281 / 1,436 / 145 / 18 | 304 / 1,428 / 138 / 20 | 725 / 1,611 / 158 / 7 |

**E1 is met** (a longer quote can only cover more; recall of the labeled sample does not fall in any arm) and **E2 is met** (at most 2% incomplete in every arm; the bar was 2%). **E4 is pending**: 30 changed quotes for the owner to rate better / same / worse (`outputs/sentence_rule_sample_for_rating.md`, a seeded sample of 1,006 changed quotes from T2a and D1x); the rule is proposed for adoption only if at least 80% of the rated pairs are better or same.

## What the numbers show

- The rule repairs about 87% of the incomplete quotes (162 → 19, 176 → 18, 358 → 40). What remains is mostly table rows, glossary strings and quotes that run to the end of a chunk.
- **It merges little.** Survivors fall by about 1% on the current prompt and 3% on the inclusive prompt (2,501 → 2,434). The inclusive prompt's extra records are mostly different sentences, not pieces of the same one, so the whole-sentence rule alone does not bring the record count back down; the "more and smaller records" seen on AFI 17-203 (157 rows against about 113) is not mainly pieces of one sentence.
- **Quotes that could not be located (about 8%)** are mostly composites already built by the pipeline: of six I read, four were a lead-in joined to its list item ("Individuals (Contractor Personnel) shall: Obtain or meet appropriate cyberspace qualification ..."), which are whole sentences by construction and are left alone.
- On the AFI sheets the rule trims the hints a little: AFI 17-203 D1x `starts_mid_sentence` 13 → 9 and rows 157 → 153, T2a 6 → 4 (rows unchanged at 111); AFI 13-550 D1x 6 → 0 mid-sentence; AFI 10-2402 D1x 356 → 352 rows. Table scraps and quotes not located in the passage are unaffected.

## Limits

The splitter is a rule, not a language model; a sentence that runs past the end of its chunk stays unfinished (no terminal punctuation) and is counted as incomplete; E4 is one rater's reading of 30 pairs. Nothing is wired: adopting the rule is a step after Step D's grounding (before enrichment and indexing), changes `source_quote` and the record count for every document, needs the owner's go-ahead, and a reindex but not a re-extraction.
