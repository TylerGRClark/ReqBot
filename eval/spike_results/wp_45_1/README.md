# WP-45.1 measurement foundations (evidence, read-only)

Part of Phase 45. No production code changes; scripts here only read the 13 documents pinned in
`eval/spike_results/wp_44/manifest.json`. Sub-steps land as separate pull requests.

| Sub-step | What | Status |
|---|---|---|
| (a) | Fragment census: documented text signals over every record, crossed with the attachment method | merged (#204) |
| (b) | Attachment audit: two independent labelers, Tyler adjudicates | pack built (below); labels and analysis land in the next PR |
| (c) | Fair retrieval test (queries written from meaning, frozen configuration) | after (b) |
| (d) | Does a wrong stem hurt retrieval? | after (c) |
| (e) | Small source-based sample (obligations labeled in the PDF, traced to first loss point) | not started |

## (a) Fragment census: `census.py`

```bash
python3 eval/spike_results/wp_45_1/census.py --manifest-out eval/spike_results/wp_45_1/outputs/manifest.json
# optional: --records-out PATH  (one JSON line per record: signals, attachment method, stem)
```

Inputs are checked first by the shared helper `eval/spike_results/wp_45_audit/_inputs.py` (exact filenames, sha256
against the WP-44 manifest, with the two WP-44.1-edited files pinned to their post-edit hashes); a missing or
changed file stops the run. No LLM and no
Qdrant access. Output: `outputs/census.txt` (two runs are byte-identical) and `outputs/manifest.json` (Python, docling and docling-core
versions, Step C prompt-template hash, sha256 of every input, and sha256 of the code that ran: the census script, the
input helper and the production modules it calls; the recorded git revision is only the HEAD at run time and can
precede the commit that adds the script).

**Attachment method** is the production cascade (`enrich_requirements.reconstruct_parent_stem`), recomputed with
the same functions: candidate check, then same-chunk, cross-chunk, heading.

**Signals** are sampling aids, not classifiers. WP-38.1 found that lowercase-first, modal-first and trailing-comma
each also flag genuine, correctly kept requirements here (see `_is_dangling_clause`).

| Signal | Meaning |
|---|---|
| `lowercase_start` | first alphabetic character is lowercase |
| `list_marker` | production list-marker regex (`(a) `, `1. `) or a bullet character |
| `open_ending` | ends with `;`, `,`, or a trailing `and`/`or` |
| `dangling_clause` | production predicate: starts with a bare copula |
| `introduces_list` | ends with `:` (a governing stem, not a fragment) |
| `not_contiguous` | normalized quote is not a substring of its chunk (audit F07) |
| `no_obligation_verb` | none of the profile's obligation verbs; context only |

The first four make up the "fragment signals" composite. `no_obligation_verb` is reported but kept out of it: it fires
on 56% of all records: 524 of the 1,045 records over 20 words and 515 of the 802 at 20 words or fewer (table C2 in
`outputs/census.txt`), so it does not separate fragments from requirements in this corpus. That choice was made after seeing the data; the composite is a sampling
aid and nothing is tuned to an outcome.

### Results (2026-10-04, 1,847 normalized-tier records)

- **Baseline reproduced.** 839 reconstruction candidates; attachment 142 same-chunk, 59 cross-chunk, 2 heading, 636
  none (as in the audit). The 203 stems stored in the data equal the 203 recomputed now: 0 differ.
- **Fragment-shaped by the lexical signals: 211 records (11.4%) fire at least one, 19 fire two or more.**
- **The 636 candidates with no stem are mostly not fragment-shaped:** 546 (86%) fire no fragment signal, 86 fire one,
  4 fire two. The permissive candidacy rule (up to 20 words) sweeps in many short complete requirements.
- **Attached stems:** of 142 same-chunk, 45 are on fragment-shaped quotes and 97 are not; of 59 cross-chunk, 20 and
  39; both heading attachments are fragment-shaped.
- **No kept record ends with `:`** (`introduces_list` is 0 across all 1,847), so a bare governing stem is never itself
  a kept requirement.
- 177 records (9.6%) are not contiguous substrings of their chunk (same as audit F07).

### Limits

The signals are lexical. A fragment written as a capitalised imperative sentence (a sibling bullet such as "Retain
visitor logs.") fires none of them, so the counts above are a floor on fragment-shaped records, not a prevalence, and
"attached to a quote that does not look like a fragment" does not mean the attachment is wrong. Prevalence and
attachment correctness come from the labeled audit, (b) and (e). Nothing here estimates an error rate.

## (b) Attachment audit pack: `audit_pack.py`, `audit_pack/`

```bash
python3 eval/spike_results/wp_45_1/audit_pack.py --out-dir eval/spike_results/wp_45_1/audit_pack \
    --key-out PATH_OUTSIDE_THE_PACK/key.json --manifest-out eval/spike_results/wp_45_1/outputs/audit_pack_manifest.json
```

Same pinned inputs and no LLM or Qdrant, as in (a). The run stops if a stratum's population differs from the table
below. Two runs are byte-identical (pack files and key).

**What the labelers do** (full rules in `audit_pack/RUBRIC.md`). Pass A shows only source text: the quote, its chunk
and the previous chunk. The labeler says whether the quote needs a lead-in (`complete` / `needs_lead_in` /
`not_a_requirement`), where the governing text is (`same_chunk` / `previous_chunk` / `section_heading` /
`not_shown`) and copies it. Only then does pass B show the stem the pipeline attached, for the 66 sampled records that
have one, and the labeler rules on it (`right` / `wrong_sibling` / `fragment_chain` / `not_needed` / `wrong_other`).
Two passes so that the labeler forms their own view before seeing the pipeline's answer; asking "is this stem right?"
first would anchor on it. Claude and Codex label independently; Tyler adjudicates the disagreements and spot-checks
about 10 agreements (the shared-mistake check). `audit_pack/check_labels.py` validates a label file (standard library
only, so it runs in a directory holding just the pack). `tests/unit/test_wp45_audit_pack.py` covers the checker and the builder's pure parts (card rendering, the seeded draw).

**Sample.** 130 records, ids `R001`..`R130` in random order; the ids and card order carry no stratum information. The
answer key (id to record, stratum, attachment method) is written only to `--key-out`, not into the repository. It is
reproduced byte for byte by rerunning the script, and the manifest records its sha256.

| Stratum | Population | Frame | Sampled | Why |
|---|---|---|---|---|
| same-chunk stem | 142 | 126 | 36 | precision of the largest attached group (the 16 hand-labeled in audit F04 are left out of the frame) |
| cross-chunk stem | 59 | 59 | 28 | precision of the cross-chunk lookup |
| heading stem | 2 | 2 | 2 | all of them |
| no stem, fragment signal | 90 | 90 | 28 | fragment-shaped records that got nothing: the misses we can see |
| no stem, no signal | 546 | 546 | 20 | the census's blind spot (capitalised imperative fragments) |
| not a candidate, signal | 54 | 54 | 8 | check that the 20-word candidacy cut is not hiding fragments |
| not a candidate, no signal | 954 | 954 | 8 | same, unsignalled |

Each stratum is the first n of a seeded shuffle, so it can be extended later without a redraw. Estimates are weighted
by stratum (frame size over sample size). **Expected precision is modest.** Worst-case 95% half-widths (a rate near 50%, finite-population corrected):
+/-14 points for same-chunk, +/-13.5 cross-chunk, +/-15.5 for no-stem with a signal, +/-21.5 for no-stem without a
signal, and +/-32 to +/-35 for the two not-a-candidate strata, which only bound a rate. That is enough to say whether
a problem is large (the lead is 7 of 16 wrong), not to rank a 5-point difference. The fix WPs are checked by replay
on all 142 and 59 attachments, not by this sample.

**Limits.**
- Both main labelers are language models and can share mistakes; Tyler's agreement spot-check is the only guard.
- Labelers read the text, not the Docling item tree, so root cause (2) "hierarchy missing or wrong" cannot be
  established here. Causes (1) different chunk, (3) rules do not cover the shape and (4) sibling accepted as the
  stem are read from the labels; (2) is reported as not separable from this evidence.
- Blinding is by instruction plus a pack folder that holds only the labelers' files. Run a labeler in a copy of
  `audit_pack/` in an empty directory, not in this checkout (where the census and audit outputs are readable).
- The first main labeler (Claude) authored the pack and had seen the F04 hand labels and the census totals; the 16
  F04 records are excluded for that reason.
- 8 of 130 quotes are not verbatim in their chunk (audit F07); each such card says so and is judged as written.
