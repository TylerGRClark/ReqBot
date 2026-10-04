# WP-45.1 measurement foundations (evidence, read-only)

Part of Phase 45. No production code changes; scripts here only read the 13 documents pinned in
`eval/spike_results/wp_44/manifest.json`. Sub-steps land as separate pull requests.

| Sub-step | What | Status |
|---|---|---|
| (a) | Fragment census: documented text signals over every record, crossed with the attachment method | this directory |
| (b) | Attachment audit: two independent labelers, Tyler adjudicates | not started (needs a sample size and labeling time) |
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
