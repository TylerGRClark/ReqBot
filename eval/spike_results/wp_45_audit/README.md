# WP-45 audit verification (read-only, local)

Evidence behind the Phase 45 backlog items in `docs/TODO_future_improvements.txt` (items 34, 35, 38-45, retrieval
item 7 and dependency item 7). Each script checks one finding from an external pipeline audit (ChatGPT,
2026-10-04) against the real ReqBot code and, where noted, the 13 documents
pinned in `eval/spike_results/wp_44/manifest.json`. Nothing here writes to the corpus, the live Qdrant index or
the Ollama server (`check_reconcile.py` reads Qdrant; `check_f02.py` and `check_f01.py` use mocks and a
synthetic document). Run from the repo root with `python3 eval/spike_results/wp_45_audit/check_<name>.py`.
The corpus scripts need those 13 documents' processed output under the configured `processed_dir`. If one is
missing they stop with an error instead of skipping it, because a skipped document would silently shrink the counts.

| Script | Finding | What it shows | Result (2026-10-04) |
|---|---|---|---|
| `check_f01.py` | F01 | Real `HybridChunker` splits one oversized paragraph; does `_chunk_raw_text` give each segment the full text? | Yes: 6 of 7 chunks carried the full 7,597-character paragraph. |
| `check_f02.py` | F02 | Real Step C `run()` with a failing, then working, mocked transport. | Resume made 0 generation calls; requirements file empty. |
| `check_f03.py` | F03 | The report's dedup probe, the dedup score arithmetic, and how many Step C records the dedup keys collapse in the corpus. | Probe 2 to 1; 500 vs 580; 33 records collapsed across chunks (23 groups), 17 are F01 twins. |
| `check_f04.py` | F04 | The report's two stem probes, then attachment method counts and cross-section checks on the corpus. | Probes reproduce; 142 same-chunk, 59 cross-chunk, 2 heading, 636 none; 0 of 59 cross a section path. |
| `check_f04_sample.py` | F04 | 16 random same-chunk attachments (seed 45) for hand labeling. | Labels below. |
| `check_f05.py` | F05 | Re-runs Steps A and B offline on the 13 PDFs and counts chunks whose items span more than one section path. | 0 of 1,166 raw chunks; no equal-depth ties. |
| `check_f07.py` | F07 | Polarity probe on `quote_word_coverage`; non-contiguous quote count; negation-drop scan. | Coverage 1.0 for the negated pair; 177 of 1,847 non-contiguous; 0 negation drops. |
| `check_reconcile.py` | F08, F09 | Resolved artifacts versus live `grc_requirements` points. | 1,845 expected, 1,845 live, 0 missing, 0 stale, 0 multi-edition PDFs. |

Other numbers cited in the triage came from one-off commands recorded in the triage text: Step C failure counts
from `*_raw_responses.jsonl` and `*_parse_failures.jsonl` (0 of 839), duplicated `raw_text` across chunks (16 of
839 in 8 groups), embedding input lengths (max 819 characters, about 204 tokens, against nomic-embed-text's 2,048
token context), context chunks over the 1,500-character embedding cut (24 of 839), the WP-40 category counts, and
the WP-43 table. Environment: docling 2.94.0, docling-core 2.99.0.

## F04 hand labels (one reviewer: Claude; not audited)

Sample from `outputs/f04_sample.txt` (seed 45, 16 of 142). **Plausible governing stem:** 2, 3, 7, 9, 10, 11, 12,
14, 16 (nine). **Wrong or doubtful:** 1 (unrelated previous bullet), 4 and 5 (two fragments of one split
sentence), 6 and 8 (sibling imperative used as the stem), 13 (sibling used as the stem), 15 (checklist sibling
"Have load-shedding plan" as the stem for "Have portable equip. avail.") — seven. 7 of 16 is 44%, 95% interval
roughly 21% to 70%. This is a lead for WP-45.1's two-reviewer audit, not a measured rate.
