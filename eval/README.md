# eval/

Evaluation scripts, gold sets and the frozen results of past experiments (`spike_results/`).

## Scripts that no longer run on the current code (2026-10-23)

When clause labeling replaced the list-writing requirement-finding step, these modules were
deleted: `pipeline/llm_extract_requirements.py`, `pipeline/anchor.py`,
`sentence_expand.expand()` and its same-sentence merge, `pipeline/enrich_requirements.py`
(enrichment, with its parent-stem reconstruction), `pipeline/entailment_gate.py` (the description
check; `eval/modality_fabrication_check.py`, which imported it, went with it), and normalizing's
grounding, word-coverage and dangling-clause checks.

The experiment scripts below import them. They are kept unchanged because their files are
hash-pinned (their sealed results cite them); their recorded results stay valid. To run one
again, check out the commit before the switch (`git checkout dc4daac`) in a separate worktree.

- `spike_results/wp_45_1/census.py`
- `spike_results/wp_45_7/run_discovery.py`, `spike_results/wp_45_7/discovery_prompts.py`
- `spike_results/wp_45_10/analyze_chunks.py`
- `spike_results/wp_45_14/evaluate.py`
- `spike_results/wp_45_audit/check_f02.py`
- `spike_results/wp_45_13/analyze_d1x.py` names the deleted extraction module in its list of
  changed code paths
- `spike_results/wp_45_1c/variants.py` and `spike_results/wp_45_8/stage_b_run.py` still import,
  but the variants they build from `embedding_text` no longer match what the index embeds.

The unit tests that imported the deleted modules through these scripts were deleted with them.
Two one-off scripts outside `spike_results/` that exercised only deleted code were deleted:
`eval/actionability_spike.py` (WP-33.3 prompt A/B test) and `eval/verify_wp38_2_rules.py`
(WP-38.2 check of the dangling-clause rule).

`spike_results/requirement_kind/make_rating_sheet.py` needs the `reqbot kinds` command and the kind sidecar helpers (`RULES_VERSION`, `load`, `sidecar_path`), which were removed as unread. It is kept unchanged and runs only at the commit before that removal (`git checkout 3c0990a` in a separate worktree).
