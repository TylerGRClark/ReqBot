# WP-45.7b — a selection resolver: code proposes the spans, the model chooses (plan, pre-registered)

*Status: plan only, no code and no model runs yet. Follows WP-45.7 ([PHASE45_WP457_PLAN.md](PHASE45_WP457_PLAN.md)), whose generative resolver failed G2 on the
development side (#222). The owner approved trying an extractive-only resolver; this plan picks the design and registers the gates before anything is run.*

## 1. Why the first resolver failed, and why "just drop two fields" is not enough

The v2 resolver (`wp_45_7/outputs/resolver_v2_runs/`, six configurations, 104 selection candidates) failed on invented parties and modality errors. A post hoc recount of
the same ledgers, counting only the issues raised on the fields an extractive resolver would keep (everything except `standalone_statement` and `plain_language`):

| Config (v2) | Answers with any error | Of which in a copied field | Modality errors, all fields | Modality errors, copied fields only | Actor or parent not a span |
|---|---|---|---|---|---|
| R0 14B | 38 | 22 | 20 | 6 | 1 |
| R1 8B | 57 | 46 | 30 | 10 | 13 |
| R1 14B | 66 | 48 | 40 | 18 | 13 |
| R2 14B | 60 | 46 | 35 | 17 | 9 |

The composed fields explain about half of the modality errors, but the copied fields still fail a large share of answers. A sample of those failures: a modal
phrase that is not one ("in coordination with", "could be", "The DoD Component heads:"), a verb normalised while "copying" ("coordinates with" for "coordinate"), an actor
with a leading article, a parent that is a whole sentence. These are copy errors of small models, so asking the same models to copy more carefully will not reach a
2% invented rate or zero modality errors. (This recount was made after the selection results were known, from the selection half only; it motivates the design and is not
a gated result.)

## 2. Design: selection, not copying

The model never writes a value. Code proposes every span; the model picks among them; code assembles the record.

1. **Candidate menu (code).** For one candidate requirement, code builds a numbered menu of spans that already exist in the evidence: the candidate quote's own subject (text before
   its first modal phrase), the leaf heading and its ancestors, the lead-in and stem candidates `bundle.py` already finds, and bounded neighbors (R2). Each menu entry is a verbatim
   substring of one bundle span; the generator is deterministic.
2. **Model output (the only free choice).** `{status, actor: <menu id or null>, parent: <menu id or null>}`, with the status enum unchanged. Enforced by the Ollama JSON schema
   (menu ids are an enum per prompt). No free-text field, no evidence list.
3. **Modality is read by code, not by the model.** The modal phrase and its class are taken from the existing `MODAL_TABLE` over the candidate quote, or over the chosen parent when
   the quote has none (the "The Records Officer will:" lead-in case); an ambiguous `can` stays `none` as today. This removes the model from the field that failed the gate hardest.
4. **Assembly (code).** The answer is assembled in the existing `{value, evidence}` shape with `standalone_statement` and `plain_language` null, then run through the **unchanged**
   `check_resolution.py` and `score_resolver.py` (gates, attachment, ledger). Conditions, exceptions and timing are out of scope for this experiment; the tracked backlog item for them is unchanged.

Because every value is a verbatim span and the modality is read by code, the **invented-party gate and the wording-related modality errors** (a modal added, dropped or strengthened while
copying) cannot occur through the model's wording; the invented gate is still computed and must be zero, as a test of the generator and the assembler. The **modality gate is not structural**,
though: the unchanged checker compares the model's `status` with the code-read modal class (for example `obligation` for a quote that says "should" is `modality_strengthened`), so a status
that contradicts the quote's own modal still counts, at zero tolerance, against the model. That is a real error and is kept as a gate: it measures whether the model's classification respects
the modality the code found. The model is judged on what it actually chooses: status (including that consistency) and attachment.

## 3. Staging, gates and stop rules (registered now)

All development uses the **selection half** of the frozen resolver gold only (104 candidates). The **evaluation half (116) is not read** until the choice is frozen, and is scored once.
The selection half was already used to design prompts v1 and v2 and to write section 1, so a pass on it is necessary, not sufficient; the evaluation half is the verdict.

- **S1, candidate ceiling (offline, no model).** Using the existing `attachment()` match against the audit gold, the menu must contain a span that makes the attachment
  *right* for at least **75%** of the attachment-scored selection candidates (the best v2 rate is 63.6%, production stems 34.5%), with a mean menu size of at most 8 spans. At most
  **two generator revisions**, made looking only at selection-half misses; then freeze. If S1 fails after the second revision: **stop, no model run**, and report the ceiling.
- **S2, model gates on the selection half.** Four configurations (R1 and R2 evidence tiers by 8B and 14B; R0 is dropped because it supplies no context and attached 27% in v1 and v2). Same
  gates and thresholds as G2 in the earlier plan section 4.5: valid share at least 95%, real wrongly rejected at most 5%, real scope-or-unresolved at most 10%, non-requirements rejected
  at least 60%, incomplete at most the production baseline plus 5 points, invented zero (structural, see above) and modality errors zero (model-dependent through the status, see above), **plus** attachment right at least **63.6%**
  (not worse than the best generative result). One prompt revision allowed after the first run; failures count against gates as before.
- **Choice rule (same shape as before, from the selection half only).** Keep configurations passing every gate; take the highest attachment-right rate, ties to the lower tier, then the smaller
  model. If none passes, report the best one as failing and **stop**: the evaluation half is not scored and the held-out set is not run. The rule is applied by `score_resolver.py --choose`
  with a registry of these four configurations (the six-configuration v2 registry stays as it is).
- **S3, evaluation half, once.** Only if S2 yields a passing configuration: score it on the 116 evaluation candidates with the same gates. That result is the WP-45.7b verdict. The held-out
  resolver run and end-to-end comparison stay out of scope until the owner decides (they need the second labeler).

## 4. Pull requests, one at a time

1. This plan.
2. Menu generator + offline S1 measurement + unit tests (no model).
3. Selection prompt, assembler, runner, `--choose` registry for the four configurations + unit tests.
4. Selection-half runs and the choice report (scores and ledgers committed, as in #222).
5. Evaluation-half scoring, only if S2 passes.

## 5. What this does not claim

- Nothing about standalone or plain-language rewriting; those fields are dropped here and stay a separate question.
- A model that chooses well among code-proposed spans is a smaller claim than "the resolver understands the clause"; the gates measure choices against the audit gold, no more.
- The code reading of modality is rule-based: its rare misses (an ambiguous `can`, a modal in an unusual place) are reported as a descriptive count, and when a status/modality conflict traces to the code's reading rather than the model's choice, the run report says so (the gate is not relaxed).
- If S1 fails, the finding is that the evidence bundle does not reliably contain the right span at all, which would point at Step B (chunking) rather than at the resolver.
