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
