# Requirement kind, stage 1 (labels in a sidecar; nothing reads them yet)

Plan: `docs/PIPELINE_REDESIGN_PLAN.md` section 10. The owner settled the list of 13 kinds on 2026-10-11. Stage 1 writes `kind`, `kind_reasons` and `kind_tags` for every checklist row to
`<doc>_kinds.jsonl` (`reqbot kinds --doc DOC`, `services/requirement_kind.py`, rules version `kind-rules-1`). No model, no behavior change: no reader, sheet, question or index uses the labels.

One choice made for stage 1, not in the plan's wording: the labels go to a sidecar beside the requirements (like the draft questions) and not into a new full-copy pipeline file between
steps 6 and 7. The kind needs the citation context (table caption, front matter, figure caption) and hint flags that are worked out per checklist today and not stored (plan, status table);
moving the step into the pipeline waits for stored citations and for the rules to be rated. The rating below decides whether it is worth moving.

## Rules, fixed before any sample was drawn

**Population.** The checklist rows of the six Air Force documents (AFI 10-2402, AFI 13-550, AFI 17-203, AFMAN 17-2101, AFPD 17-1, DAFMAN 17-1305) that have a requirement text.

**Sample (30 rows, `random.Random(50)`).** Two rows for each kind that has at least two rows in the population (13 kinds at most, 26 rows); the remaining places go, one each, to `duty_with_actor`,
`duty_imperative`, `unknown` and `permission`, in that order. A kind with fewer than two rows gives its places to the same four. Rows within a kind are drawn at random; the sheet is shuffled
so the kind is not shown in sheet order.

**The owner rates** each sampled row: the label shown is the kind and the rule that fired. He answers **right**, **wrong** or **unclear**, and for a wrong one says what kind he would call it.

**Pass** (stage 1 is accepted, and stage 2 may be planned) only if:
1. right is at least 85% of the rated rows (unclear rows count as not right);
2. no kind has more than one wrong among its sampled rows (the practical form of "no kind below 70%" with two or three rows per kind);
3. the share of every kind, and of `unknown` in particular, is reported.

If it fails, the rules are revised (`rules_version` bumped), a new sample is drawn with a new seed and the failure is recorded here. Nothing reads the labels in the meantime.

## Run

```
python3 cli/reqbot.py kinds --doc afi10-2402          # and the other documents
PYTHONPATH=. python3 eval/spike_results/requirement_kind/make_rating_sheet.py
```
