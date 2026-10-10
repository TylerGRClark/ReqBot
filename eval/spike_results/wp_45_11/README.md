# WP-45.11 — results of the first two one-change trials (Docling 2.122.0 and the table fix)

Plan: [PHASE45_WP4511_PLAN.md](../../../docs/PHASE45_WP4511_PLAN.md) (#247). T2's test was changed to the five chunks it changes by an addendum written before any T2 run: [PHASE45_WP4511_ADDENDUM.md](../../../docs/PHASE45_WP4511_ADDENDUM.md) (#253). Everything is scratch and offline apart from the model calls: runs are in `~/reqbot-work/scratch/wp45_11_scratch/<arm>/<document>/` (outside the repository), `pipeline/` is unchanged, and the report files are in `outputs/`.

**Setup.** The 13 pinned documents (source-PDF hashes checked). Extraction model `llama3.1:8b-instruct-q4_K_M` (digest `46e0c10c039e…`, the same in every record, enforced by the scorer), the unchanged Step C prompt, Step D and parent-stem reconstruction, run by `pipeline/run_pipeline.py --skip-to C` on a scratch copy of each arm's chunk files. Step C samples at temperature 0.1 with no seed. Recall is measured on the 74 adjudicated, unflagged obligations of the WP-45.1(e) source sample (3 documents). The scorer compares the pipeline code of the compared arms (`git diff` over `pipeline/`, `core/`, `services/` between each arm's recorded revision; the two baseline runs predate the field and were scored with `--unrecorded-head 8db159f`, the revision they ran at, whose code directories are identical to the later arms' revision), and it refuses an arm unless all 13 documents finished with return code 0, no Step C chunk failed, the ledger has one row per chunk, one chunk specification and one model file were used throughout, and (for comparisons) every arm used the same model file.

## The noise floor (B0a, B0b: two runs of today's pipeline)

| | B0a | B0b |
|---|---|---|
| Sample obligations extracted (of 74) | 45 | 50 |
| Survive Step D | 44 | 49 |
| Step C records / Step D survivors, all 13 documents | 2,024 / 1,867 | 2,015 / 1,869 |

All 839 chunks completed in both. B0b found 5 obligations B0a did not and **none the other way**; all 5 are on pages 4 and 9 of afman17-2101 (the model extracts or skips a whole list as a unit). The surviving quote sets overlap at 0.85 (0.87 with spacing and punctuation ignored). The earlier WP-45.1(e) statement of "one piece each way" understated this. **Practical consequence: a difference of up to about five obligations on this sample is noise.** The registered rules use these runs directly: an arm must find at least 43 (2 below the lower replicate) and lose at most 7 obligations that both baseline runs found (the larger one-way difference, 5, plus 2).

## T1: Docling 2.122.0 (conversion and its default chunker, `docling-core` 2.100.0), two runs

| | B0a | B0b | T1 | T1b |
|---|---|---|---|---|
| Chunks | 839 | 839 | 845 | 845 |
| Sample obligations extracted (of 74) | 45 | 50 | 44 | 45 |
| Step C records / survivors | 2,024 / 1,867 | 2,015 / 1,869 | 1,985 / 1,829 | 1,980 / 1,833 |
| Step D failure codes (not-grounded / unrepairable fragment / heading echo / orphaned list item) | 67 / 37 / 25 / 4 | 58 / 35 / 27 / 4 | 74 / 30 / 25 / 0 | 70 / 27 / 25 / 0 |

**Registered rules.** R1(i) recall not more than 2 below the lower replicate (43): **pass** (44, 45). R1(ii) paired losses at most 7: **pass** (2 obligations found by both baseline runs were found by neither Docling run). R2 survivors within 10% and no document more than 25% off: **pass** (total -2%; the largest per-document difference is -7%, afi17-203). R4 every lost obligation read: of the five found by either baseline run and by neither Docling run, three (AFMAN-p009-002, -014, -015) were found by B0b only, in the same noisy afman17-2101 page-9 region B0a also misses; AFMAN-p009-024 ("2.3.15 Serves as the AF Transition Lead … by acting as the:", a lead-in) was extracted by the baseline but rejected at Step D, so it never reached the index either way; **DODI-p012-002** ("k. Provide the NM and SM data necessary to fulfill the commander's critical information requirements …") was extracted in both baseline runs and in neither Docling run, and the chunk text around it is identical except nine single-space deletions and a double-space breadcrumb. I cannot explain it from the input; it is one item, inside the noise range. **No obligation was found only by a Docling run.**

**Read beyond the rules.** The surviving quotes differ more between the versions than between runs of one version: overlap 0.73 across versions against 0.87 within a version (spacing and punctuation ignored). Quotes found by both runs of one version and by neither run of the other: 177 baseline-only, 147 Docling-only, spread across all 13 documents (afi10-2402, dafman17-1305, DODI 5200.48 most), and the samples read are ordinary requirement sentences in both directions. So the upgrade moves roughly 13 points more of the extracted set than noise does, and net survivors fall about 2%, without a measurable change in recall on the sample. This sample cannot say whether those other differences are better or worse. Step D rejects more quotes as not grounded in the chunk (70 and 74 against 58 and 67) and fewer as unrepairable fragments (27 and 30 against 35 and 37), and the 4 orphaned-list-item rejections disappear; none of these is a registered gate.

**T1 outcome by the plan's rule:** R1 and R2 hold, nothing was lost beyond noise; T1 has no gain requirement. It is *adoptable* on these rules if the owner wants the newer release (the audit found OCR fixes in the text). It is not an extraction improvement: it is neutral on recall and changes which quotes are picked.

## Exploratory: does running extraction more than once help? (not registered)

Over all four runs the union of extracted sample obligations is only 50 of 74, and **24 obligations (32%) are found by no run**. Combining two runs gives 45 to 50, three runs 47 to 50. The misses are systematic, not luck, so repeating the extraction would not recover them; a change to the prompt or model would (WP-45.7 discovery found +30 points of 8B recall).

## T2: the table fix on the five chunks it changes (five interleaved repeats each way)

The fix changes exactly 9 of 1,166 chunks; 5 reach Step C (DODI 5200.48 chunks 76 and 87, DODI 8551.01 chunk 26, afi10-2402 chunks 121 and 123). `T2base` is today's text, `T2new` the fix's; `outputs/t2_report.json` holds every quote with its repeat counts.

| Chunk | Step D survivors per repeat, today's text | with the fix |
|---|---|---|
| DODI 5200.48 chunk 76 (dissemination-control marking table) | 0, 0, 0, 5, 5 | 10, 10, 10, 10, 10 |
| DODI 5200.48 chunk 87 (definitions lead-in) | 2, 2, 2, 2, 2 | 2, 2, 2, 2, 2 |
| DODI 8551.01 chunk 26 | 0 ×5 | 0 ×5 |
| afi10-2402 chunk 121 | 0 ×5 | 0 ×5 |
| afi10-2402 chunk 123 (sample vulnerability table) | 0 ×5 | 4, 4, 4, 4, 4 |

**Registered rules.** R2a: no chunk's median survivors falls, none falls to zero: **pass**. R3: at least one chunk gives grid-row quotes in at least 3 of 5 repeats where today's text gave none in 3 of 5: **pass** (chunk 76: 10 table quotes in 5 of 5 repeats against table quotes in 2 of 5 with today's text; chunk 123: 4 in 5 of 5 against none) and no quote that appears in at least 3 of 5 repeats of today's text disappears (chunk 87's two quotes are in both): **pass**. R4 (all records read): see below.

**What the records show.** With today's flat text, chunk 76's few quotes carry the chunker's artifacts ("…, ALIGNMENT TO CURRENT = ." and "…, ALIGNMENT TO CURRENT = DISTRO E."), appear in only 2 of 5 repeats, and in one repeat the model echoed invented examples from its own prompt ("All DoD information systems shall implement multi-factor authentication …"), which Step D rejected. With the grid, the same chunk gives ten clean, verbatim row labels ("Display Only (DISPLAY ONLY)", "Federal Employees Only (FED ONLY)", …) every time, all kept. No quote merges two cells or mixes rows. **But the rows it surfaces are mostly marking labels (chunk 76) and example descriptions in a sample risk-assessment table (chunk 123: "Vehicles can park within 10 feet of the building due to lack of barriers or fencing"), not obligations.** So T2 is a correctness and stability gain (clean, repeatable, verbatim table rows, no garbling or echoed examples), not a recall gain: it adds 14 survivors across these chunks (about 0.7% of 1,868), which are the kind of table-label content Phase 45's junk work will want to flag rather than delete. Chunks 26 and 121 give nothing either way. 

**T2 outcome by the addendum's rules:** R2a, R3 and R4 hold. Whether the added table rows are wanted is the owner's call; the fix itself makes extraction from tables deterministic and faithful to the source layout.

## T3 — chunk limit (512 and 1,024 tokens), on the T2 state

Base = the merged table fix (#249) at `cc0b67e`, Docling 2.94.0 with the pinned set (#254), run twice (**T2a**, **T2b**). Arms: **T3_512**, **T3_1024** (same code and model digest, interleaved T2a, T3_512, T2b, T3_1024; 44, 40, 44 and 39 minutes). Rules: plan section 4 plus [the T3 addendum](../../../docs/PHASE45_WP4511_T3_ADDENDUM.md) (including the R2 clarification the owner asked for: a fall in the record count alone is not a failure). Reports: `outputs/t3_{512,1024}_arms_report.json` (R1, R2, R4) and `outputs/t3_{512,1024}_report.json` (R3).

| | T2a | T2b | T3_512 | T3_1024 |
|---|---|---|---|---|
| chunks | 839 | 839 | 514 | 390 |
| Step C records / Step D survivors | 2,025 / 1,880 | 2,025 / 1,890 | 1,813 / 1,712 | 1,787 / 1,695 |
| the 74 obligations found (extracted) | 46 | 47 | 47 | **59** |
| found by both base runs, not by the arm | | | 5 (limit 4) | 1 (limit 4) |
| found by the arm and by neither base run | | | 5 | 12 |
| labeled lead-in quotes still extracted (of 145; bar 90% of 142 = 128) | 142 | 142 | 124 (87%) | 110 (77%) |
| lead-in in the quote's chunk (of 145) | 107 | 107 | 134 (+18.6 pts) | 143 (+24.8 pts) |

Noise floor on the T2 state: one obligation one way, two the other (limit for paired losses 2 + 2 = 4); the two base runs extract all 145 labeled quotes except 3; survivor quotes overlap 0.85.

**Registered verdicts.** Neither arm is adoptable.
- **T3_512 fails R1(ii)** by one (5 paired losses against 4) **and R3** (124 of 142 = 87% against 90%). R2 holds (-8.9% in survivors; CJCSI 6510.02G is -26%).
- **T3_1024 passes R1** (59 found; 1 paired loss) **and R2 by three records** (1,695 against a trigger of 1,692; -9.8% against the lower base run; per-document: NIST SP 800-125 -36%, DODI 5200.01 -26%, DODI 8410.03 -20%, DODI 5200.48 -15%), but **fails R3**: 110 of 142 labeled quotes (77%) are still extracted.

**What the failures are (R4, read).**
- *512, the 18 labeled quotes lost:* 16 are not covered in substance by any other record in the document (best word coverage 0.3 to 0.7) - list sub-items such as "(2) Send a copy of their PPSM CCB appointment letter to the DoD CISO." and "Execute Lead Command oversight and management of the AN/USQ-225."; two are measurement artifacts (a space before a full stop, one changed verb).
- *1,024, the 32 lost:* 7 are covered in substance by a longer record that restates the lead-in ("CUI training standards must, at minimum: Identify individual responsibilities for protecting CUI.", which my containment test misses because the list marker is gone) or differ only by spacing; 4 are partly covered; **21 are not covered**. Counting the 0.9-or-better word-coverage cases as extracted still leaves 126 of 142 (88.7%) at 512 and 117 of 142 (82.4%) at 1,024, so the R3 verdict does not depend on my matching rule.
- *1,024, the two documents over 25% different, read:* the dropped records are mostly real obligations in running prose ("all unneeded applications should be removed.", "if a system hosts guest oss with different impact levels, the system should be secured in accordance with the highest of those levels.", "classified information released to industry will be safeguarded in accordance with DoDI 5220.22 (reference (j)).", "sci will be safeguarded in accordance with policies and procedures established by the dni."). The records new at 1,024 in the same documents are also ordinary requirements, fewer of them. This is under-extraction by the 8B model on longer prose chunks, not consolidation of fragments: the owner's point that a lower count can be good applies to merged fragments, and here the dropped records are not covered by any merged record.
- *1,024, the 12 obligations gained:* 10 are on pages 9 and 10 of afman17-2101, the list region that already flickers between identical runs (the model extracts or skips a whole list as a unit; the baseline replicates differ there too), and 2 are in NIST SP 800-125. So most of the large recall gain comes from one list in one document where a 1,024-token chunk holds the whole list; the 74-obligation sample has only three documents, so this should not be read as a corpus-wide +12. The one obligation lost (AFMAN-p004-013, "1.1.4. The AF Long Haul Communications Flight ... executes and manages all facets of the DISN Enterprise Long Haul Communications Program on behalf of the AF.") sits in the same document.
- *Stem match* (production `parent_stem` overlapping the labeled lead-in; reported, not gated): 44 and 47 in the base runs, 33 at 512, 26 at 1,024. It falls because fewer of the labeled fragments are extracted at all, so it is not evidence about attachment quality.

**Outcome.** The larger limit does what the audit predicted for lead-ins (107 to 134 to 143 of 145 co-located), but the 8B model extracts less from longer chunks, losing real obligations in prose and list sub-items, while stabilising one long list. Under the registered rules neither 512 nor 1,024 is adopted and nothing in the pipeline changes; the chunk limit stays 256. The measured trade-off points at attaching the lead-in to small chunks (WP-45.8) instead of enlarging them. A design not tested here: extract from small windows but show the model the lead-in as context.

**Limits.** One model, three documents in the recall sample, the labeled quotes were drawn from production's own 256-token records (so "still extracted" can only fall and favors the base, as the addendum said), a noise floor from two runs, and the R2 pass at 1,024 is by three records. The R2 read was done for the two documents named above, not by the 40-record draw, because the total trigger did not fire.

## Deviations and limits, disclosed

1. **A failed first launch.** T1 and T1b were first started from a path inside the working tree; switching branches removed the scripts and both exited at once (code 2). They were re-run from a pinned git worktree (`~/wp45_11_wt` at the commit recorded in each arm record). Nothing from the failed launch was kept. B0a and B0b ran from the main checkout whose `pipeline/`, `core/` and `services/` are byte-identical to that commit (checked with `git diff`); their arm records lack the `git_head` field that was added afterwards.
2. **Punctuation-insensitive quote overlap** (0.73 / 0.87) was computed after the registered, normalized-quote overlap (0.69 / 0.85) to read the difference fairly; both are in the report. The union-of-runs numbers are exploratory.
3. The table-fix chunk files used here are from the **narrow** version of the fix. Earlier versions of #249 changed list markers and restored dropped text; they were discarded before any arm ran (see that PR).
4. Limits: 74 obligations on 3 documents, a noise floor of about five, and one model; T1 has two runs and the baseline two; the five T2 chunks are in three documents. Nothing here says whether the other differences T1 introduces are better or worse than the baseline's.

## Decisions for the owner

1. **T1 (Docling 2.122.0).** Adoptable by the registered rules; neutral on recall, changes about 13 points more quotes than noise, fixes some OCR text, rejects a few more quotes as ungrounded. A pull request would also pin `docling-core` (the chunker comes from it). If adopted, T2's test is rebuilt on the 2.122.0 chunk files and T2 and T3 get replicates on that base.
2. **T2 (table fix, #249, merged 2026-10-08 on the owner's go-ahead).** Passed its rules; correctness gain, small footprint (5 chunks of 839). It does not change chunk ids at the 256 default; adopting it still means re-extracting the three affected documents.
3. **T3 (chunk limit).** Run; neither 512 nor 1,024 tokens passes the registered rules (see above); the limit stays 256. T2 (#249) and the Docling pin (#254) are merged.
