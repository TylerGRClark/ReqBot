# PR #201 review at ea651a0

Reviewed: 2026-10-04. Commit: `ea651a01be5ba4b2d3867bef276df8a0fc11b264`.
PR: https://github.com/TylerGRClark/ReqBot/pull/201

## Verdict

The prioritization is sound: protect reindex completeness and Step C recovery first,
then measure attachment correctness before changing extraction or introducing another
model. The PR is an audit/backlog change with local evidence scripts; the actual Phase
45 requirements document is explicitly outside this PR. This review does not approve
that uncommitted implementation plan.

I recommend correcting the evidence limits and prerequisite handling below before
merging. These are medium-priority review findings, not production regressions introduced
by this PR. No production code, corpus, index, or GitHub discussion was changed by this review.

## Findings

### 1. P2 — The negation scan cannot support “no dropped negation”

Locations: `eval/spike_results/wp_45_audit/check_f07.py:48–58`,
`docs/TODO_future_improvements.txt:499–500`, and the README's F07 result.

The scan skips contiguous quotes and counts negation only inside RapidFuzz's selected
destination span. Both choices can exclude the omitted negation itself. Fixing the
contraction regex does not fix this limitation.

I ran the actual script against two synthetic records:

| Quote | Source chunk | Why the scan misses it |
|---|---|---|
| `Share passwords.` | `Do not share passwords.` | Quote is a contiguous substring, so scanning is skipped. |
| `Share passwords with visitors.` | `Do not share passwords with any visitors.` | Quote is non-contiguous, but the selected alignment excludes `Do not`. |

It reported two survivors checked, one non-contiguous quote, and zero possible dropped
negations. This demonstrates a false negative; it does **not** establish a dropped
negation in the real corpus.

Smallest correction: say “this heuristic found no excess negation tokens in its selected
alignment spans; omitted governing negation remains unmeasured.” If this becomes a
detector, evaluate source-clause context and retain these examples as challenge cases.
Do not reject quotes merely because their containing chunk has an unrelated negation.

### 2. P2 — Missing evidence inputs can still produce a successful, misleading census

Locations: `check_f05.py:29–32`, `check_f04.py:67–69`, and the equivalent reconstruction
source loading in `check_f04_sample.py`.

The README added in ea651a0 says missing inputs stop the scripts rather than silently
shrinking counts. This is only partly enforced:

- F05 prints `PDF missing` and continues. With one available PDF and one missing PDF,
  its original census loop finishes normally and reports the available document's
  totals. With no PDFs, the eventual division by zero is not an intentional input check.
- F04 verifies the normalized file indirectly through its glob, but its production
  `_load_reconstruction_sources()` helper deliberately returns empty dictionaries when
  Step C or chunk files are missing. The audit then measures absent evidence as absent
  stems. I ran the actual F04 script with a normalized record but neither source file:
  it completed successfully and reported one candidate with `no stem`.

Require every input used by each corpus script before measurement starts, using exact
document filenames and a clear nonzero failure listing missing inputs. Preserve the
current fail-fast behavior for missing normalized files. Do not adopt Gemini's suggested
`continue` for missing artifacts: that would weaken the corpus guarantee further.

For reproducibility, also validate the existing manifest's chunk/extraction hashes where
applicable and record hashes for other inputs. Selecting a pinned directory alone does
not establish that its contents still match the saved experiment.

### 3. P2 — Better attachments will not make governing clauses appear in checklists

Location: `docs/TODO_future_improvements.txt:638–644`, particularly “it may largely solve
itself once stem accuracy improves.”

The item correctly identifies that `services/checklist_service.py` ignores `parent_stem`
and `embedding_text`. Its item builder also ignores `description` and copies only
`source_quote` as requirement text. Improving stored stems or composing a description
therefore leaves the checklist output unchanged.

Deferring display until attachment accuracy improves is reasonable. Replace the
“solve itself” sentence with an explicit dependency: **after attachment validation,
checklist consumers still need an additive change to expose verified governing context**.
Keep source quotes intact and distinguish supplied context from quoted text. This also
needs to be reflected in any Phase 45 checklist-usability acceptance criterion.

## Implementation-plan advice

- Keep WP-45.0.1 and WP-45.0.2 first. I verified the reindex caller ignores the indexer's
  returned count, while individual embedding failures can be skipped. The saved F02
  transport-failure reproduction also reproduces locally.
- For the completion ledger, define success as a complete response with durable output,
  not merely some recovered JSON. Step C currently recovers objects from truncated
  responses. Define retry handling for truncation, crashes between requirement writes
  and completion writes, duplicate chunk text, model/profile changes, and valid empty
  results. Writing the raw record last alone does not make retries idempotent.
- For the reindex guard, compare against distinct eligible point IDs and verify actual
  collection coverage before promotion. Row counts alone do not handle duplicate IDs.
  Test requirements and context independently; the current context path also skips
  documents with missing chunk files.
- Treat the 7/16 attachment labels as development evidence, as the PR already does.
  Preserve independent, contextual labeling and a held-out gate before changing rules.
- Distinguish the 1,847 normalized records used by F04/F07 from the 1,845 records in the
  artifact/index reconciliation. They are different populations, not interchangeable
  live-index quality estimates.
- Leaving hosted providers and broad identity changes for later is reasonable. Do not
  let “no missing IDs” become a claim that payloads, vectors, or extraction completeness
  have all been verified; reconciliation only checks the recorded identity coverage.

## Verification and limits

- Read the PR files at the exact reviewed commit and checked relevant production paths.
- Ran the committed F02 reproduction: failed request remains cached; resume makes zero
  generation calls and leaves requirements empty.
- Ran the actual F07 and F04 scripts with isolated synthetic artifacts and mocked input
  configuration/manifest; reproduced the limitations above.
- Executed F05's unchanged census loop with synthetic parser/chunker outputs to check
  missing-PDF handling; did not run PDF conversion.
- Existing unit tests: **113 passed** across `test_reindex.py`,
  `test_parent_stem_reconstruction.py`, and `test_normalize.py`.
- The original processed corpus, PDFs, and live Qdrant service are not available in this
  review checkout. I did not independently rerun the reported corpus totals or adjudicate
  the real attachment sample. The PR's reported 936-test full-suite result is not a
  result independently reproduced by this review.
