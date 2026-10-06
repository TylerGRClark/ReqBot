# WP-45.7d — code sets the requirement's strength from the modal word; the model decides only whether it is a requirement, who acts and what governs it (plan, pre-registered)

*Status: plan only, no code and no model runs yet. Follows WP-45.7c ([PHASE45_WP457C_PLAN.md](PHASE45_WP457C_PLAN.md), results in #231). The owner asked to write this plan and press on.*

## 1. What the last run showed, and the design change it points at

On the selection half, three of four configurations cleared the production-anchored attachment bar (61.8, 56.4 and 61.8% against 54.5% needed) with zero invented parties; every configuration failed the zero-modality gate
with 4 to 6 answers. The ledgers say where those come from: the **model's status disagrees with a modal word the code can read in the same text**, or the model cites no modal at all. The strength of a requirement
(`shall` is an obligation, `should` a recommendation, `may` a permission, `shall not` a prohibition) is a table lookup. Asking the model for it is the one place it keeps slipping; letting code own it removes that error class by construction,
in the same way the menu removed invented parties.

Two cases the review of #231 found must be designed, not ignored:
- **A governing modal the model did not select.** On R2 8B, audit R011 and its duplicate chose the subject entry, left the parent empty and answered `obligation`, while the lead-in on the menu says `should`; the gates saw nothing. A lookup on the quote and the chosen parent alone would never see that `should`.
- **A quote with more than one modal.** Card R081 says "shall be modified ... shall not be utilized": an obligation and a prohibition. One status cannot fit it.

## 2. The registered design (the menu generator, the checker, the gold, the halves and every gate threshold are unchanged)

1. **The model's answer.** `{kind, actor, parent}`, where `kind` is one of `requirement`, `scope_or_context`, `not_a_requirement`, `unresolved` (the status enum minus the four strengths), and actor and parent are menu ids or `none`, as before. The prompt changes accordingly (new hash): no instruction about modal words or strengths; the fragment, actor-versus-parent and `preceding` rules of the current prompt stay.
2. **Code sets the status.** For `scope_or_context`, `not_a_requirement` and `unresolved` the status is the kind. For `requirement` the status is the class of the **governing modal**, read by code from the first of these sources that has one (the same table as the checker, including the hint phrases; the ambiguous `can` is not read):
   1. the candidate quote;
   2. the parent entry the model chose;
   3. the menu's **colon lead-in** (the generator's `lead_in` entry that ends with a colon, which by construction has list items, hence this quote, after it), if the model chose no parent;
   4. the menu's **preceding clause** that contains a modal, if the quote starts with a lowercase letter (it continues that clause, as "ensure that policies are updated ..." continues "Organizations should also be aware ... and"). The lowercase test is a heuristic: a continuation that starts with a capital (an acronym, a proper noun) is missed and falls through to the default; the inferred-source list below is how that is checked, not a claim that it never happens.
   The chosen actor is never read. If no source has a modal, the status is `obligation` with class `none` (a modal-free imperative or item, as the checker already allows). The record keeps which source supplied the modal (`quote`, `parent`, `menu lead-in`, `preceding clause`, `none`).
3. **More than one modal in the quote.** The record's modality and status use the **first** modal, in reading order; every modal found, with its class, is kept in the ledger record (`all_modals`), and the multi-modal candidates are listed in the run summary for the owner's spot check. **This is a known weakness, not a solved case:** the first modal is not always the governing one ("Whether users may obtain access must be recorded" would read as a permission), and a clause-level rule cannot tell them apart reliably. Measured before registering: 74 of the 1,991 production quotes (3.7%) and 4 of the 104 selection-half quotes hold more than one modal; in 14 of the 74 a subordinating word ("that", "where", "if", ...) precedes the first modal, and in the samples read that word does *not* reliably mark the modal as subordinate ("agreements that include ... shall take ...": the first modal governs), so a "skip modals after a subordinator" rule would be wrong in as many cases as it fixed. Identifying the governing modal needs a clause parser and is out of scope here; splitting a quote into one requirement per modal is a separate, later change. This plan does not claim to represent the second requirement or to pick the governing one.
4. **Gates.** The same as WP-45.7c (the v4 rule: production-anchored attachment bar and misleading margin, real rejected at most 5%, non-requirements rejected at least 60%, scope-or-unresolved at most 10%, incomplete at most baseline plus 5 points, valid at least 95%, invented at most 2%, modality errors zero), as the `v5` registry for the same four configurations. The invented and modality gates are **structural** now (code writes both) and are kept as tests of the assembler. A `requirement` kind counts as a requirement status for the real-rejected and non-requirement gates.

**Scope.** This is an offline experiment in `eval/spike_results/wp_45_7/` (scratch scripts, nothing in the production pipeline: not `section_parser.py`, `chunk_text.py` or `llm_extract_requirements.py`, and no Step C cache is touched). Moving any of this into the pipeline would be a separate work package, with its own plan, after a passing verdict.

## 3. Staging, stop rules (the same shape as WP-45.7c)

- **Stage A (offline).** The assembler, the kind schema and prompt, the `v5` registry and tests; the dry run. One PR.
- **Stage B (selection half).** The four configurations (R1 and R2 by 8B and 14B); the rule from the selection half only. **One prompt revision is allowed after the first run**, registered before it is run, then the rule is applied over the revised runs alone. If no configuration passes, the best is reported failing and **the evaluation half is not scored**.
- **Stage C (evaluation half, once).** Only for a passing choice; the same gates; that result is the WP-45.7d verdict.

## 4. What this does and does not claim

- The strength of each requirement then rests on the modal table and on code's choice of the governing modal, **not on a human label**: the gold has no strength labels, so the gates cannot score it. The report therefore lists how often each source supplied the modal, and every record whose modal came from a menu lead-in or a preceding clause (the inferred sources), so the owner can spot-check them; no pass is claimed about their correctness.
- Setting the strength by code takes a choice away from the model that it sometimes made correctly (a hint with no modal that the model read as a recommendation from context): such items become `obligation` with class `none`, unless a modal is found in a source above. That is a deliberate over-extraction-friendly default (the item is kept, flagged by its class), not a claim that it is an obligation.
- The model is still judged on what it chooses: whether something is a requirement, the actor and the parent.
- The owner's idea of a reviewer pass (a second model call that checks the actor and parent against the sentence) stays out of scope; it would be a second change at once.
