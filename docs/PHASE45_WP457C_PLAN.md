# WP-45.7c — fix the two defects the gates exposed, re-register the bar, and let the unread half decide (plan, pre-registered)

*Status: plan only, no code and no model runs yet. Follows WP-45.7b ([PHASE45_WP457B_PLAN.md](PHASE45_WP457B_PLAN.md)), whose selection resolver beat production on attachment
(about 54 to 60% right against 34.5%) with zero invented parties, but missed a bar set at 63.6% and could not meet a zero-modality gate on one record (#228). The owner
asked to fix the defects, re-register the bar and rerun.*

## 1. Why a new registration, and what it admits

Three things in WP-45.7b were defects of the *test*, not findings about the model:

1. **The bar.** 63.6% was "not worse than the best generative result". That was a convenient anchor, not a derived requirement; it ties the new method's pass mark to a
   method that was abandoned for inventing parties.
2. **The modality gate.** The checker's phrase table has no entry for a modal-free hint such as "Consider using ...". The project's ruling is that such hints are recommendations, so a
   *correct* answer on that record (card R025) always fails the zero-modality gate.
3. **The generator.** The revision-2 rule that a colon governs only when list items follow it does not recognize multi-level numbering ("2.1.5.1."), so two selection candidates (audit R011, card R064) lose a lead-in the text plainly contains.

**What this admits:** the new bar and the two fixes are being chosen *after* the selection-half results were seen. A pass on the selection half therefore cannot validate them. The **evaluation half
(116 candidates, never read by any experiment)** is the verdict, scored once. The selection half is used only to choose the configuration, as before.

## 2. The three registered changes (nothing else changes)

Unchanged: the prompt (hash `435a1561313c6d64`), the schema, the assembler, the gold and its two halves, every other gate threshold, and the choice-rule shape.

1. **Checker phrase table.** Add recommendation phrases `is advisable`, `are advisable`, and `consider` **only at the start of a sentence** (optionally after a list marker), so "factors to consider" does not count. The same table is used by the
   assembler's code-read modality, so "Consider using ..." is read as a recommendation. This is a table change, not a gate change: the zero-modality gate stays at zero.
2. **Menu generator.** One change: a list marker is also a multi-level number ending in a dot or a parenthesis ("2.1.5.1.", "3)"); still not "30 daily" in "10:30 daily". The generator's frozen hash changes and is re-recorded. **S1 is re-measured** on the selection half and must not fall below the revision-2 numbers
   (R1 87.3%, R2 92.7%, mean menu at most 8); if it does, the change is reverted and the experiment continues with the old generator.
3. **Attachment bar, derived from production, not from the generative resolver.** The attachment-right rate must be at least **20 points above the production stems' rate on the same records of the same half** (selection half: production is 19 of 55 = 34.5%, so at least 54.5%, that is 30 of 55; the evaluation half uses its own
   production rate). A gain that size is eleven records on 55, more than the prompt-to-prompt flipping of two to eight records in each direction seen in WP-45.7b. **One new gate** goes with it, so that attaching more cannot hide attaching wrongly: the *misleading* rate may be at most production's misleading rate plus 5 points (production is
   19 of 55 = 34.5%, so at most 39.5%; a gate on incomplete answers already exists). Both are compared as exact fractions, as every gate is.

## 3. Staging, stop rules

- **Stage A (offline).** The two code changes and the new registry (`--registry v4`: the same four configurations, the relative bar and the misleading gate), with unit tests; S1 re-measured. One PR.
- **Stage B (selection half).** Run the four configurations (R1 and R2 by 8B and 14B) on the selection half with the unchanged prompt; apply the rule from the selection half only (configurations passing every gate, then the highest attachment-right rate, ties to the lower tier then the smaller model; if none
  passes, the best is reported as failing and **the evaluation half is not scored**). No prompt revision is allowed in this plan. One PR.
- **Stage C (evaluation half, once).** Only if Stage B chose a configuration that passes every gate: score it on the 116 evaluation candidates with the same gates. That result is the WP-45.7c verdict. One PR. Held-out resolver, end-to-end and adoption into the pipeline are separate decisions.

## 4. What this does not claim

- Passing here would show the selection resolver beats production on attachment by at least 20 points with no invented text and no modality or misleading regression, on documents the design never saw (the evaluation half). It would **not** show anything about the held-out set, nor that the
  models understand the clauses; the gates measure choices against the audit gold.
- The 20-point bar and the 5-point misleading margin are judgment calls, stated before the run; they are chosen so that a result inside the noise cannot pass.
- The owner's idea of a **reviewer pass** (a second model call that checks the chosen parent and actor against the sentence) is a possible later step; it is out of scope here because it would be a second change at once.
