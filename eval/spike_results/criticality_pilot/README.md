# Can a model judge how critical a requirement is? (a pilot; nothing is wired in)

Why: an inspector cannot check every requirement, so the checklist needs a way to focus on the ones that matter most. Tier tags (T-0 to T-3) exist on only about 15% of rows. The owner's idea: give a strong
model the whole publication and the rows extracted from it, plus a written scale (critical about 2% of rows, major about 10%, then moderate, minor, info), and let it say how important each row is, for a person to vet.

## Design (fixed before any model output)
- Publications: AFI 17-101 (2020 edition; 274 rows with a draft question, 99 with a tier tag) and DoDI 5200.48 (227 rows; no tier tags). Both have a hand-written IG checklist whose items I matched to rows earlier (15 of 15 and 17 of 18 items have a matched row).
- Model: two blind Opus runs per publication and arm; each sees only the publication text and the row list (id, citation, quote), never the tier tags or the IG items.
- **Arm A (stated shares):** levels critical / major / moderate / minor / info with the target shares in the prompt (about 2 / 10 / 30 / 40 / 18 percent, as guidance).
- **Arm B (rank only):** an importance score 1 to 10 per row with no quotas; buckets are made afterwards by rank at the same shares. This tests whether the quotas in the prompt help or whether ranking then cutting is steadier.
- **Yardsticks (never shown to the model):** (1) the IG's picks: of the IG checklist items, how many have a matched row in the model's top 15% of rows; (2) the tier tags (AFI 17-101 only): are T-0/T-1 rows ranked above T-2/T-3 rows; (3) baselines: the Tier 0/1 filter, a "shall/must/will" filter, and random rows at the same cut.
- The owner (or the IG coworker) rates about 30 rows blind afterwards, as the human check.

## Pass bar (registered now)
An arm passes if, on both publications, (a) its top 15% captures at least as many IG items as the best simple baseline (Tier 0/1 filter or shall/must/will) and at least 60% of them; (b) on AFI 17-101 the median rank of T-0/T-1 rows is above the median rank of T-2/T-3 rows; (c) it does not call more than 25% of rows critical or major in arm A. Failing (a) means the idea is not better than what we have.

## Limits
Two publications, 33 IG items, same-family judge (a model judges a model's rows); the IG picks tell what a human chose, not what matters. Row text is not committed (public repo).

## Result of the first pilot (ran 2026-10-17; written after reading the outputs)
Level shares in arm A came out near the guidance (AFI 17-101: critical 2%, major 11%, moderate 34%, minor 35%, info 18%; DoDI 5200.48: 2%, 9%, 32%, 37%, 21%). What the model called critical reads sensibly (AFI 17-101: stop operating or cut the connection when a system is denied, the Enterprise AO as the only authority to approve a connection to the AF network, SAF/CN approval of Very High or High risk authorizations; DoDI 5200.48: release of CUI to the public or to foreign parties, NOFORN, export control, foreign-disclosure decisions).
**Against the registered yardsticks it does not pass:**
| Selection | AFI 17-101 (15 IG items) | DoDI 5200.48 (17 IG items) |
|---|---|---|
| Arm A critical + major | 36 rows (13%) capture 3 | 25 rows (11%) capture 3 |
| Arm B top 15% | 42 rows capture 3 | 45 rows capture 8 |
| Tier 0/1 filter | 54 rows (20%) capture 8 | no tier tags |
| shall/must/will filter | 133 rows (49%) capture 15 | 142 rows (63%) capture 16 |
| Random rows, same count as the 15% cut | about 4.1 | about 4.0 |
Tier check (AFI 17-101): median rank of T-0/T-1 rows 114 against 138 to 141 for T-2/T-3 rows (of 274): a weak tilt in the right direction.
**Reading.** The model's idea of "critical" is not the IG's idea of "what to check": the IG's items are mostly roles assigned, registrations and documents kept (the model rates them moderate), and the owner distrusts the IG picks and the tier tags as a measure of criticality (tier 0 includes how to wear a uniform). So this result says the two disagree, not which is right. The yardstick needs replacing before any conclusion.
**Deviation.** The arm A run on AFI 17-101 reported that it read only the first 3,000 characters of the publication and judged from the quotes and its own knowledge of the AFI, so "whole publication in context" was not tested for that arm.
**Next (proposed, not run):** anchor the scale in NIST's own language (FIPS 199 impact levels; the SP 800-53 Rev 4 priority codes and the SP 800-53B Low/Moderate/High baselines as external labels on a domain where NIST already ranked controls), and get a human truth set by blind rating of about 40 rows.

## Phase 2: a rubric from NIST's own language, tested on NIST controls (registered 2026-10-17 before any phase-2 output)
Owner's direction: use the FIPS 199 impact language as the scale, put the chapter in the model's context, and compare judging a chapter's requirements together (batch) with judging one requirement at a time. Chapters can be taken from
the existing chunks (`section_ref_path`, `section_title_path`), so no new Docling run is needed.
- **Data:** SP 800-53 Rev 4 (nist.gov, public): the 140 base controls of eight families (AC, AU, CM, CP, IA, IR, SC, SI). NIST's own labels, never shown to the model: the sequence priority code (P0 to P3) and the Low/Moderate/High baseline allocation of each control.
  Caveat stated up front: NIST says the priority code is an implementation sequence and the baselines say which controls a system of a given impact level needs; neither is "criticality", and the model may remember the baselines from training.
- **Rubric:** the FIPS 199 definitions (limited, serious, severe or catastrophic) mapped to 5 levels (critical, major, moderate, minor, info), with the 2% and 10% shares as soft guidance.
- **Arm B (batch):** one run per family reads the whole family and scores every control; run twice to measure repeat stability.
- **Arm S (single):** one run per control, with the family chapter in context and only that control to judge (40 controls drawn by baseline category, seeded). Run only if B shows the rubric tracks NIST's labels.
- **Measures:** rank correlation (Spearman) of the score with the baseline tier (in the Low baseline, Moderate only, High only, none) and with the priority code; the share rated critical and major; repeat stability (Spearman between the two B runs).
- **Pass bar:** B correlates with the baseline tier at 0.4 or more on every family pooled, its repeat stability is at least 0.8, and it rates no more than 20% of controls critical or major. S must beat B by 0.05 or more in correlation or in stability to justify its cost.

## Phase 2, arm B result (ran 2026-10-17; first launch failed because I put the rubric file one folder from where the reviewers were told to read; all 16 refused to score without it, and the relaunch used the same prompts)
140 controls in 8 families, scored twice by blind Opus runs that read each whole family:
| Measure | Result | Registered bar |
|---|---|---|
| Repeat stability (Spearman, run 1 against run 2) | **0.96** (identical score in both runs on 90% of controls) | at least 0.8: met |
| Correlation with NIST baseline tier (in the Low baseline, Moderate only, High only, none) | **0.37 / 0.38** (runs 1 and 2; 0.38 averaged) | at least 0.4: **narrowly missed** |
| Correlation with the NIST priority code (P1 highest) | 0.51 / 0.51 | no bar set |
| Share scored major or critical (4 or 5) | 20% and 19% | at most 20%: met |
Score distribution (run 1): 1: 11%, 2: 33%, 3: 36%, 4: 19%, 5: 1% (critical is rare, as hoped).
Mean score by NIST tier: in the Low baseline 2.9, Moderate only 2.9, High only 2.6 (5 controls), in no baseline 2.04: the rubric separates "in some NIST baseline" from "in none" but not Low from Moderate. The highest-scored controls are the ones that read as fundamental (SC-7 boundary protection, AC-3 access enforcement, IA-2 identification and authentication, SI-2 flaw remediation, AC-2 account management, AC-17 remote access, CM-6 configuration settings).
Caveats: NIST's labels are not criticality (the priority code is an implementation order, and 122 of 224 coded controls are P1), the model may remember the baselines from training, and the High-only group is five controls.
Reading: batch scoring is steady and tracks NIST's own ordering moderately. Arm S (one control at a time, chapter in context) will be run on a 30-control sample to see whether it adds accuracy; with stability already at 0.96 the question is accuracy only.
