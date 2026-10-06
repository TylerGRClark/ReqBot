# WP-45.7e — fix the menu defects the verdict exposed, and test the same frozen configuration once on fresh labeled candidates (plan, pre-registered)

*Status: plan only, no code, no draw and no model runs yet. Follows WP-45.7d ([PHASE45_WP457D_PLAN.md](PHASE45_WP457D_PLAN.md); verdict in #236: a fail by one record on the misleading gate). The owner chose to fix the menu and retest on fresh cases.*

## 1. What the verdict showed, and what this plan changes

The WP-45.7d configuration (R2, `qwen2.5:14b`, kind prompt `6200fa25a374eb35`) beat production's attachment by 20 points on unseen candidates with zero invented parties and zero modality errors, and failed the misleading margin by one record (16 against at most 15 of 55). Reading the 16 misleading answers afterwards (exploratory, on a half that is now spent) found two defects in the **menu**, not in the model:

1. **Entries that can never be a correct answer.** Seven of the 16 picked a `preceding` entry that is only a list number or a dash ("2.17.22.", "- 7.3.4.3.", "-", "- c.").
2. **A heading offered twice, with and without its section number.** Audit R050 picked "2.17. MAJCOM/DRUs." when "MAJCOM/DRUs." was also on the menu, and the overlap rule counts the section number against a match. The decisive record of the verdict was this case.

**Registered change, nothing else (the model, the tier, the prompt, the schema, the assembler, the checker and every gate are unchanged):** the menu generator (a) drops any entry with fewer than two letters (list numbers, dashes, a lone "c."), and (b) offers a heading only without its section number (the numbered form is no longer offered when the number-stripped form exists). Every entry stays a verbatim substring of its source. Both are deterministic. The generator's frozen hash changes and is re-recorded.

**What this admits.** The change was motivated by the spent evaluation half, so that half cannot test it. The 130 audit records and the 90 cards are all spent (they designed or scored every earlier step). The test below uses **fresh** candidates.

## 2. The fresh set

- **Source and draw.** The same corpus, the same strata and the same seeded procedure as the WP-45.1(b) attachment audit (`audit_pack.py`): each stratum's candidates are sorted, excluded of the 16 earlier hand-labeled ones, and shuffled with the seed `wp45.1b/<stratum>`; the audit took the first n of each shuffle "so it can be extended later without a redraw". **The fresh set is the next records of the same shuffles**, so none of them was in the audit. Draw: same-chunk 30, cross-chunk 28, none+signal 28, none+nosignal 12, not-a-candidate+signal 8, not-a-candidate+nosignal 8 (the `heading` stratum has only two records, both used): up to 114 records.
- **Exclusions.** Any fresh record whose document and quote text equal those of a record in the spent gold (the 220 audit and card candidates) is dropped and replaced by the next record of its stratum, so no duplicate of a spent record is scored (the corpus holds duplicated sentences).
- **Labels.** The audit's own rubric (`audit_pack/RUBRIC.md`) and checker: pass A on source text only (is it complete, does it need a lead-in, where is it, its exact text), then pass B (the verdict on the production stem, for the records that have one). **There is one labeler, Claude; the audit had two labelers and the owner's adjudication.** That is a weaker gold and is stated as the main limit of this test. To keep it honest: pass A is labeled before pass B is opened, and **no model output and no menu is looked at** until the labels are frozen; the labels are committed and reviewed before any run; the owner may spot-check a random sample of the records (offered, not required); a second labeler can be added later and the verdict re-read against disagreements.
- **The baseline for the gates is production on the fresh records**, computed from pass B (a stem is right if the labeler says so; wrong kinds are misleading; none attached on a record that needs one is incomplete), as before.
- **Sufficiency check at freeze, before any run:** at least 80 real requirements and at least 8 non-requirements, and at least 60 attachment-scored records; otherwise the plan stops and reports without running (a gate with nothing to measure would silently vanish).

## 3. The one-shot test

The configuration is **declared here, not chosen**: tier R2, model `qwen2.5:14b` (the model file whose digest the WP-45.7d runs recorded), kind prompt `6200fa25a374eb35`, temperature 0.1, context 8192, answer limit 200, with the new menu generator. It runs once on the fresh set through a guarded runner like `run_stage_c.py` (frozen choice, every code file by hash, the model digest, no earlier run, no override options), and is scored once with the WP-45.7d gates as registered, as a new `v6` rule: attachment right at least production's rate on the fresh set plus 20 points, misleading at most production's plus 5 points, real wrongly rejected at most 5%, non-requirements rejected at least 60%, scope-or-unresolved at most 10%, incomplete at most production's plus 5 points, valid at least 95%, invented at most 2%, gated modality errors zero. All exact fractions. **A pass is the WP-45.7e verdict; a fail is a fail, with no second try on this set.**

A **sanity run** of the same configuration with the new menu on the spent halves, before the fresh run, is allowed and reported as information only (it shows whether the two menu changes broke anything); it is not a gate and no number from it can be a verdict. S1 (the menu's ceiling on the spent gold) must not fall below the WP-45.7c numbers (R1 89.1%, R2 94.5%) or the change is reverted.

## 4. Staging (several branches may be open at once; each is one PR)

- **A.** This plan.
- **B.** The menu change, S1, the `v6` rule, the declared configuration, the guarded runner and the frozen-code manifest, with tests. No labels, no fresh-set model run. (Independent of C.)
- **C.** The draw, the pack, the pass A labels, the pass B labels, the frozen fresh gold and its sufficiency check. No model runs on these candidates. (Independent of B.)
- **D.** The sanity run on the spent halves (information only), then the one-shot run and the verdict. Only after B and C are merged.

## 5. What this does and does not claim

- A pass would show that, on candidates nobody designed against (same 13 documents, a different draw, **one labeler**), the configuration beats production's attachment by at least 20 points with no invented text, no gated modality error and a misleading rate within 5 points of production's.
- It would **not** show anything about unseen documents, the held-out set, or agreement with a second human; the gold is one labeler's.
- Nothing here is integrated into the production pipeline; that would be a separate work package.
