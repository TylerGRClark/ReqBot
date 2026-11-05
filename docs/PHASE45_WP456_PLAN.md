# WP-45.6 — Extraction-model comparison: plan (draft, local, untracked)

*Draft 2026-10-04 for Codex's review and Tyler's go. Nothing here has been run. It refines the WP-45.6 section of
`docs/PHASE45_REQUIREMENTS.md`; where they differ, this plan is the proposal.*

## 1. Question and why it is next

Does a larger local model, `qwen2.5:14b` (already on Tyler's Ollama), read these documents better than the current
`llama3.1:8b-instruct-q4_K_M`? Extraction strength is the cornerstone, and part of today's junk, fragment and missing-lead-in
problem may be model skill rather than document structure. It is the cheapest way to find out, it uses no outside service,
and the plan's own sequencing puts it right after the WP-45.1 baseline (which is now frozen: census, audit, retrieval test).
Measurement only; nothing in the pipeline changes.

## 2. Design

- **One change.** Re-run Step C and Step D only, for **three documents**, with `--extraction-model qwen2.5:14b`, from the pinned
  chunk files (`--skip-to C`, `--skip-enrichment`, output to a scratch directory, no `--index`, no Qdrant write, no change to
  `~/documents/processed`). Same chunks, same prompt, same profile, same Step D rules; the frozen 8B outputs are the comparison.
- **Documents (proposed, to give three different shapes):** DODI 8410.03 (list-heavy, 42 chunks), afman17-2101 (role and
  responsibility lists, 63 chunks), NIST.SP.800-125 (narrative "should" guidance, 109 chunks): 214 chunks. A pilot on the
  smallest first (DODI 8410.03) measures time and parse failures before the other two start.
- **Run recording:** model digest, `num_ctx`, Ollama version, per-chunk wall time and tokens per second from the Ollama
  response fields, and the WP-45.0.2 ledger counts (failed, cut-off, retried chunks) for both models. GPU memory is read from
  Ollama's `/api/ps` (`size_vram`) while the model is loaded.

- **Control run (added 2026-10-04 after the pilot finished, before any comparison was looked at).** Step C samples at temperature
  0.1 with no seed, so two runs of the same 8B differ. A fresh 8B run on the same chunks, on today's hardware, is therefore run too.
  It gives the **noise floor** for the overlap counts (how many records one 8B run finds that another does not) and a like-for-like
  speed. The pilot confirmed the Step C prompt hash is identical on all 42 chunks between the July 8B run and the 14B run, so only
  the model differs.

### What needs no new labeling (computed for both models, per document)

1. Records extracted at Step C and surviving Step D; Step D rejections by code.
2. Overlap with the 8B survivors: a 14B record and an 8B record are **the same record** if they are in the same chunk and
   their whitespace-normalized quotes are equal or one contains the other. Counts: both, 8B-only, 14B-only.
3. The WP-45.1(a) census signals on each model's survivors (lowercase start, list marker, open ending, dangling clause,
   not contiguous in its chunk) and the attachment-method mix of the reconstruction cascade.
4. Step C failures and cut-offs from the ledger, and throughput.

### What needs the audit's two labelers (reuse the WP-45.1(b) pass A pack and rubric unchanged)

A blind sample of **100 records**, drawn once with a seeded shuffle: up to 40 14B-only, 40 8B-only and 20 in both (the "both"
records are the labelers' own check: they should look the same whichever model produced them). Source text only, no model
name, no stem. Claude and Codex label independently with the existing pass A labels (`complete`, `needs_lead_in`,
`not_a_requirement`); Tyler adjudicates disagreements and spot-checks about ten agreements, exactly as in WP-45.1(b). The scorer
extension reports, per set, the share that are genuine requirements and the share that are complete.

## 3. What counts as a meaningful difference (fixed before anything is run)

Let N8 be the estimated number of genuine 8B survivors in the three documents, G the estimated genuine 14B-only records, and L
the estimated genuine 8B-only records (each estimated as the labeled genuine share of that set times its size, with a Wilson
interval).

- **14B is meaningfully better** only if **all** of (a) to (e) hold: (a) (G − L) / N8 is at least 0.10 and its interval excludes zero;
  (b) the not-a-requirement share of the 14B-only set is not higher than that of the 8B-only set by more than 0.10; (c) the
  census fragment composite on 14B survivors is no higher than on 8B survivors by more than its sampling interval; (d) Step C
  loses no more chunks (failed or cut off, after the ledger's one retry) than 8B does by more than 5% of chunks.
- **(e) The 14B's difference is larger than the noise floor:** the 14B's net unique difference, (14B-only minus 8B-only) over the
  baseline survivors, must exceed the same quantity for the fresh 8B run against the baseline by at least 0.05.
- **Cost is reported, not gated:** tokens per second, wall time per chunk, GPU memory. A model that is far slower is flagged for
  the discussion, not disqualified.
- **Stops:** if the pilot document shows more than 10% of chunks unusable (parse failure or cut-off after the retry), or a
  projected run longer than 90 minutes for all three documents, the run stops and reports that, rather than continuing.
- **Reading:** if all four hold, the question moves on to whether a larger or hosted model is worth building a provider path for
  (backlog item 45). Anything else is "no demonstrated difference", and a small sample means that is not "no difference".

## 4. Evidence limits (said now)

- 14B versus 8B says nothing certain about frontier hosted models.
- The comparison counts what each model finds that the other does not. A requirement **neither** finds is invisible until the
  source-based sample (WP-45.1(e)) exists, so "requirements gained or lost" is relative, not recall.
- Three documents, a sample of 100 labeled records, two labelers sharing the same rubric. Intervals will be wide.
- Records are matched by quote overlap within a chunk; a model that splits or merges quotes differently shows up as unique on both
  sides. That is counted, and the labeling shows whether the "unique" records are real.
- Qwen's output format may differ (JSON habits, refusals); parse failures are results, not noise, and are reported as such.

## 5. Deliverables and process

One branch `eval/wp-45-6-model-comparison`, branched first from `main`. Under `eval/spike_results/wp_45_6/`: the runner that
wraps the existing pipeline into the scratch directory, `compare.py` (overlap, census signals, rejections, throughput), the pack
builder reusing `audit_pack`'s card code, the scorer extension, outputs with manifests (model digests, pinned input hashes,
code digests), and a README with the results. Unit tests for the matching rule, the sample draw and the estimates. No
production change. Codex reviews this plan, then the PR.

## 6. Decisions for Tyler

1. Go on the design and on the pre-set rule in section 3 (the 0.10 and 0.05 thresholds are mine; change them before the run,
   not after).
2. The three documents above, or others.
3. GPU: the 14B model will occupy your Ollama host for the run. The pilot is about one document's worth; the full run is bounded
   by the 90-minute stop. Say when it is a good time, or whether it should run now.
4. Labeling: the same hand-off as WP-45.1(b) (Codex labels the pack in its own folder; you adjudicate), about 100 records.
