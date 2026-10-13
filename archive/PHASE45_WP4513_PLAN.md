# WP-45.13 — trial of the inclusive extraction prompt (D1) on the 13 documents (plan, pre-registered)

*Follows WP-45.12 ([plan](PHASE45_WP4512_PLAN.md), results in `eval/spike_results/wp_45_12/`). On the owner-labeled pages D1 raised the 8B model's recall from about 62% to about 91% at a precision of about 56%, and the owner rated 15 of the 22 AFI 17-203 paragraphs it adds as requirement or partial (68%, against a 60% bar). That is a scratch measurement of a prompt on a few chunks; adopting D1 changes Step C for every document. This plan tests the change the way WP-45.11 tested the others: the real pipeline, all 13 documents, the same noise floor. No pipeline change is made by this plan.*

## 1. The change under test (one change)

Step C's prompt (`PASS1_PROMPT_TEMPLATE`) replaced by the D1 text frozen in WP-45.7 (prompt hash `7da34da9994793c5` when rendered by `discovery_prompts.py`), with the same two placeholders (`{source_ref_hints}`, `{chunk_text}`), the same output schema, the same model and parameters, the same chunk files (`d2.94.0:T2_256`, the merged table-fix chunking), and unchanged Step D and parent-stem reconstruction. Arm name **D1x**. The prompt change is made on a trial branch only; it is not merged.

**Baseline and noise floor:** the two existing replicate runs of the unchanged pipeline on the same chunk files, **T2a** and **T2b** (found 46 and 47 of the 74 obligations; 1,880 and 1,890 Step D survivors; one-way differences 1 and 2, so the paired-loss limit is 2 + 2 = 4).

## 2. Rules (fixed now)

- **R1 no loss.** The arm finds at least 44 of the 74 (2 below the lower replicate), and at most 4 obligations that both replicates found (the larger one-way difference, 2, plus 2).
- **R2 more records are not a failure; they are read.** Step D survivors may rise (D1 is inclusive by design). The arm's survivor quotes that are absent from both replicates (containment either way, 40+ characters) are drawn with `random.Random(4513)`, 40 of them (all if fewer), ordered by (document, quote), and shown to the owner with source paragraph and heading. **R2 is met only if the owner rates at least 60% requirement or partial.** A fall of more than 10% in survivors is read the same way as in the WP-45.11 T3 addendum (a seeded sample of the replicates' records the arm lost).
- **R3 gain.** The arm finds at least 6 more of the 74 than the higher replicate (47), beyond run-to-run noise (about 5 pieces).
- **R4 read.** Every obligation lost against either replicate is printed with its source text and both arms' records.
- **Reported, never gating:** Step D failure codes and counts (in particular quotes rejected as not grounded, which is how echoed prompt examples would show); survivors per document, any document more than 25% different listed; the share of AFI 17-203 paragraph units covered by a survivor against T2a and T2b; the number of checklist rows carrying each hint (including `applicability_statement`) on AFI 17-203, 13-550 and 10-2402; wall time.

## 3. Decision

D1 is **proposed for adoption** (a pull request changing the Step C prompt, with the measurement in it) only if R1, R2 and R3 are all met. Adoption forces re-extraction of the corpus and a reindex; it needs the owner's go-ahead after the result and is not part of this plan. If R1 or R3 fails, or the owner's rating is below 60%, the result is reported and Step C stays as it is.

## 4. Limits stated now

Single model; 74 labeled obligations on three documents (two of the three also supplied the labeled pages D1 was designed on, so recall is not independent of the design set); noise floor from two runs; the owner rates one sample of 40, not the whole increase; the survivors that D1 adds on the documents that have no labels are judged only through that sample.
