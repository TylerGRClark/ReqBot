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

## Result of kind-rules-1 on the first sample (2026-10-11)

How it was rated: a second reader (a different model run as an agent that never saw the rules' labels; its labels are in `outputs/second_reader_rules1.json`, the rules' in `outputs/rule_labels_rules1.json`)
labelled all 30 rows blind. It agreed with the rules on 25. The owner adjudicated the 5 disagreements and 5 of the 25 agreements as a spot-check (random seed 11: the two commonest kinds, then three more).
The owner did not rate the other 20 agreed rows.

| Row | Rules said | Second reader said | Owner |
|---|---|---|---|
| DAFMAN 17-1305 4.1.7 ("may extend ... shall not authorize any consecutive waivers") | prohibition | permission | permission (second reader right) |
| AFMAN 17-2101 2.8.2.1 ("... retain their CMO responsibilities to: Provision ...") | unknown | duty with a named party | duty (second reader right) |
| AFI 10-2402 2.21.4 ("Assist in the execution of MAAs ...") | unknown | command, no party | duty (second reader right) |
| AFI 13-550 front matter ("This instruction applies to all ...") | cover page | applicability | both correct: it is front matter, and what it says is applicability |
| AFI 17-203 2.5.3.2 ("The I-NOSCs: Report suspected/confirmed events ...") | unknown | duty with a named party | duty (second reader right) |
| the 5 agreed spot-check rows | | | all right |

Against the registered pass: right 26 of 30 (87%), counting the 20 agreed rows the owner did not see as right (the 5 he did see were); rule 1 is met on that assumption. Rule 2: `unknown` had 3 sampled rows and all 3 were wrong
(limit 1). **Rule 2 failed, so stage 1 is not accepted as it stands.** Shares of every kind: `counts.json` (rules-1).

## Revision: kind-rules-2

Each change traces to the owner's answers above, to the open review comment on this pull request, or to reading `unknown` rows (the population, not the sample; no labels were involved).

1. A permission that a later negation limits is a permission: when "may" comes before the negation, the grant decides. ("may not" is still a prohibition.)
2. A sentence that opens with a command is a command with no party, whatever obligation word follows later: directly, after a tier mark, "In addition:", an -ly adverb, or a condition or role lead ("As the DIB lead, provide ...").
   "Use of ...", "Design authorities shall ..." and "units that will deploy" are not read as commands (Codex P2: leading imperatives were checked after embedded modal words, so "Ensure ..." and "Provide ... so they can ..." became duty-with-a-party or permission).
3. Command verbs that were seen opening `unknown` rows are added to a kind-local list (assist, serve, appoint, work, act, sign, inform, synchronize, ...). The shared "no actor stated" list used by the checklist hint is not changed.
4. "Actor: command" ("The I-NOSCs: Report ...") is a duty with a named party; "Note:", "Example:", "In addition:" and the like are not actors.
5. "retain / have / assume ... responsibilities" is a duty with a named party.
6. An applicability sentence in the front matter is `applicability`; the location is kept as the tag `front_matter`. Cover-page text with no scope statement stays `cover_page_text`.
7. Tier marks with a hyphen, "(T-1)", are read in the three patterns that look at the opening of a sentence (they were not).

Effect on the 1,418 rows of the six documents (before to after): unknown to command 129, duty with a party to command 116, unknown to duty with a party 19, cover page to applicability 6, permission to command 4, prohibition to permission 1.
Of the first sample only the 5 disputed rows change, and each now has the label the owner chose. I read 28 of the changed rows at random: all 28 were right. This is a regression check, not a measurement; the second sample is the measurement.

## Second sample (rules fixed before it is drawn)

Population: the same six documents, labelled by kind-rules-2. The 30 rows of the first sample are excluded (they were used to revise the rules). Seed 61. The draw rule is the one above.
The second reader labels all 30 rows blind. The owner adjudicates the rows where the two disagree and 5 of the rows where they agree (the two commonest kinds, then three more at random). If any of those 5 is wrong, he rates the remaining agreed rows too.
Pass: the same two rules, counted on the 30 rows (right at least 85%; no kind with more than one wrong among its sampled rows), and the share of every kind reported.
If it fails again, the rules are revised once more and a third sample is drawn with a new seed.

```
python3 cli/reqbot.py kinds --doc DOC                        # the six documents, rules-2
PYTHONPATH=. python3 eval/spike_results/requirement_kind/make_rating_sheet.py --seed 61 --exclude eval/spike_results/requirement_kind/outputs/sample.json
```

## Result of kind-rules-2 on the second sample (2026-10-11, owner adjudication pending)

The second reader (a different model run as an agent that never saw the rules' labels; `outputs/second_reader_rules2_seed61.json`; rules' labels `outputs/rule_labels_rules2_seed61.json`) agreed with the rules on 22 of 30 rows
(73%; the first sample was 25 of 30). The 8 disagreements, by what they show:

| Row | Rules said | Second reader said | What it shows |
|---|---|---|---|
| AFI 10-2402 2.20.1.1 ("... will be exempt from CARM programmatic responsibilities") | duty with a party | exemption | the exemption pattern reads "is/are exempt", not "will be exempt" |
| AFI 13-550 5.3.4 ("Be a voting member of ...") | unknown | command, no party | "Be" opens a command |
| AFI 10-2402 front matter ("This Instruction is applicable to ...") | cover page | applicability | the applicability hint reads "applies to", not "is applicable to" |
| AFI 10-2402 3.3.3.4.2 ("The ATR is provided to ... so coordination can occur ...") | permission | description | "can" inside a purpose clause read as a permission |
| DAFMAN 17-1305 4.1.11 ("Issuance of any vouchers requires the individual is assigned ...") | unknown | description (low confidence) | a judgment call: a condition stated with "requires" |
| AFPD 17-1 3.2.2 ("These responsibilities may be summarized as follows:: Execute all responsibilities ...") | permission | command, no party | a lead-in that only introduces a list is read as the row's kind |
| DAFMAN 17-1305 4.1.5 ("... are required to meet foundational qualifications ... but are not required to meet residential requirements ...") | exemption | duty with a party | the duty comes first; the exemption limits it (the same order rule as permission and prohibition) |
| AFI 17-203 3.7.2.3 ("Examples of strategies include ...") | unknown | description | a sentence that gives examples |

Counting every disagreement for the reader would give right 22 of 30 (73%): below the 85% bar. The owner's adjudication decides which of the 8 the reader is right on; the rules are revised after it, not before
(a third sample with a new seed follows). Nothing reads the labels, so no checklist changes while this is open.

