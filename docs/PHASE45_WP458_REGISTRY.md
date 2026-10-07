# WP-45.8 Stage B registry — the retrieval-test rules for the selection resolver, fixed before any resolver stem has been produced

*Follows [PHASE45_WP458_PLAN.md](PHASE45_WP458_PLAN.md) (#243), which said the Stage B thresholds would be registered in their own pull request before any Stage B number exists. No resolver stem exists yet (Stage A has not run) and no Stage B arm has been computed.*

## 1. The apparatus and what it can resolve

Stage B reuses the WP-45.1(c)/(d) retrieval test unchanged (`eval/spike_results/wp_45_1c/`): 111 tested records in frozen groups (right stem 25, misleading stem 22, incomplete chain stem 11, no stem but needs a lead-in 36, no stem and complete 17: the control record R053 is in the pinned corpus files but not in the live index, as in the apparatus), two blind-written questions per record (topic and party plus topic), an in-memory copy of the live index, target-only mode as the primary view (only the queried record's text changes), and one plain run plus three production-path repeats. That work fixed its own rule for a difference: **"meaningful" = a paired change in recall@10 of at least 0.10 whose 95% record-bootstrap interval excludes zero, in the same direction under best- and worst-case tie ranks; anything else is "no demonstrated difference", never "no effect".**

Its intervals on these groups are wide (for example +0.17 with interval [+0.06, +0.31] at n=35; [-0.36, -0.05] at n=22). **A rule that demanded proof that the resolver is "not worse" within a small margin on groups of 11 to 36 records could not be passed whatever the resolver does.** The rules below therefore ask for evidence of harm or benefit at the apparatus's own resolution and say in advance what an inconclusive result means.

## 2. Arms (the one new arm replaces the stem in the target-only mode)

- **production**: today's stem (the apparatus' production arm);
- **resolver**: the string fixed by the Stage A plan (the chosen actor span and the chosen parent span, each verbatim, joined with ` | ` when both exist), **no stem when the resolver abstains**;
- **hybrid** (reported beside, never primary): the resolver string, else production's stem when the resolver abstains;
- the apparatus' existing **none** and **oracle** arms for reference.

Stage A must have produced a resolver string for every record of the live index (1,845 points) so the cohort-wide gold counterchecks can use it, and for the 111 tested records for the target-only mode.

## 3. Rules (fixed now)

Computed for the **resolver minus production** paired change in recall@10, topic and party questions separately, in the plain run and in each of the three production-path repeats (four runs), per group and for the pooled stemmed groups (right, misleading, incomplete).

- **Evaluation order.** A cell (a group, a question style and a run) whose 95% interval is wider than 0.40 is marked **inconclusive** and is **excluded before H and G are evaluated**; it counts neither as harm nor as gain.
- **H (harm).** Among the cells that remain, any group, or the pooled stemmed groups, shows a *meaningful decrease* (at most -0.10, interval excluding zero, same direction at both tie ranks) in **two or more of the four runs** on the same question style. Harm on a single run is reported but does not alone fail.
- **G (gain).** The no-stem-needs-lead-in group shows a *meaningful increase* in **at least three of the four runs** for at least one question style.
- **C (cohort check; triggered = harm).** On the 35 gold topical queries (cohort mode, paired per query), C is **triggered** when the interval of the resolver's change in recall@10 lies wholly below -0.02 (its upper bound is below -0.02) in the plain run and in at least two of the three repeats. An interval that reaches -0.02 or above, such as [-0.05, 0.00], does not trigger C. Policies earlier measured here (a lead-in on the 80 oracle records, -0.017 [-0.049, 0.000]) are the reference scale.

**Outcomes, fixed in advance.**
- *Proposal for integration* only if **G holds and neither H nor C is triggered**.
- If **H or C is triggered**: no proposal; the harm is read record by record.
- If **G does not hold and neither H nor C is triggered**: *no demonstrated benefit*. The resolver is not proposed on retrieval grounds; its case would rest on display and trust (attachment accuracy), which the owner decides separately.
- A cell whose interval is wider than 0.40 is marked **inconclusive** in the report (see the evaluation order above); it is neither a pass nor a harm.

## 4. What this does and does not claim

- It can show a retrieval benefit or harm of the size the apparatus resolves (about 0.10 or more on groups of 11 to 36). It cannot show that the resolver is no worse than production by a small margin.
- The 111 records come from the audit, whose labels are the owner's adjudication; the resolver was tested on a different, fresh labeled set. Stage B tests different records, in a different measure.
- The wrong-stem finding of WP-45.1(c) stands for scale: a wrong stem did not measurably hurt its own record's rank, so a rise in the resolver's *misleading* attachments (the weak point recorded in WP-45.7) is not expected to show here either way; that question is outside what this apparatus measures.
