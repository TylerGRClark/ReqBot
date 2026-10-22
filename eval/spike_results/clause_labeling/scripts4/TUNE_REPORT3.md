# TUNE_REPORT3: prompt tuning stage 2 (PREREG4 Amendment 1)

1. Tuning pools only (gold2 TUNE: 4 docs, 248 requirements; silver TUNE: 6 docs, 593 requirements). Recall / precision, mean of the two pools: B0 stored rows 81.8 / 73.4; v3 35B 95.1 / 93.4 (gold2 96.2 / 94.5, silver 93.9 / 92.2). Best prompt = v3, so the "best" column equals v3.
2. Noise floor (35B, two batch orders): 0.3 recall, 1.45 precision; 1.5 points used for every keep decision. Keep needed more than 1.5 on one metric, under 1 lost on the other, and no pool worse than 1 point on either.
3. Rounds a (permission words) and b (body/process descriptions) were both reverted, so the amendment's stop rule froze v3 after round b. Rounds c-f were still run, labelled as diagnostics. None of them would have been kept either.
4. Every round moved 15 to 50 individual errors in both directions. Net changes stayed inside the noise, or recall rose only by giving up precision (a: +2.2 recall / -1.1 precision; f, Codex's prompt: +1.3 / -0.7). The reason line (d) cost 4.2 points of silver recall.
5. Remaining error types: "can/may" used for possibility versus permission; descriptions of how a body works versus duties given to a role; colon lead-ins; gerund and command list items under a role heading; form-template text; pamphlet advice (dafpam90-803 is the weakest document, about 80 / 70).
6. Frozen: prompt_FROZEN3.txt, a byte copy of v3, sha256 b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4. Nothing was run on any EXAM document. EXAM commands are below; run them only after the owner approves.

## Numbers (35B, mean of seeds 1 and 2, %)
| round | change | gold2 rec | gold2 prec | silver rec | silver prec | mean rec | mean prec | verdict |
|---|---|---|---|---|---|---|---|---|
| B0 | stored production rows | 83.9 | 72.5 | 79.8 | 74.3 | 81.8 | 73.4 | baseline |
| 0 | v3 | 96.2 | 94.5 | 93.9 | 92.2 | 95.1 | 93.4 | best |
| a | permission words (can, discretion, optional, not required) | 98.4 | 94.1 | 96.1 | 90.4 | 97.3 | 92.2 | reverted |
| b | descriptions of a body or process are not duties | 96.0 | 95.1 | 94.3 | 93.6 | 95.1 | 94.3 | reverted -> FREEZE |
| c* | colon lead-ins whose list carries the duty | 95.6 | 95.9 | 92.9 | 92.8 | 94.2 | 94.3 | would revert |
| d* | one-line reason before the label | 95.4 | 95.1 | 89.7 | 93.5 | 92.5 | 94.3 | would revert |
| e* | 9 worked examples from the other pool | 95.0 | 95.7 | 95.0 | 91.7 | 95.0 | 93.7 | would revert |
| f* | full prompt rewritten by Codex from tuning-pool errors | 97.8 | 94.2 | 94.9 | 91.0 | 96.4 | 92.6 | would revert |

\* Post-freeze diagnostics. They cannot change the frozen prompt.
8B: v3 only (gold2 96.6 / 73.9, silver 94.7 / 79.5). It was not run on any round because no change was kept.

## What each round did, in plain words
- a: told the model that "can be worn", "has the discretion" and "is optional" are permissions. It caught the uniform permissions it used to miss, but it also flagged "can" used for possibility ("certificates can be obtained from vendors").
- b: told the model that explaining how a council or system works is not a duty, while a task given to a role still is. This helped slightly in the right direction but stayed inside the noise.
- c: told the model that "The Heads of the Components shall:" is not a requirement on its own. It fixed those lead-ins but lost lead-ins that the labelers count as full duties ("Establish TSN processes ... by:").
- d: asked for a short reason first. This made the model stricter: it missed command-style list items under role headings, it was 1.5 times slower, and recall fell.
- e: showed nine labeled examples taken from the other pool. Errors moved around: lead-ins were fixed, but scope lines and template text were now flagged.
- f: Codex wrote a full new prompt from 60 tuning errors. Recall went up and precision went down, the same trade as round a.

## Remaining errors
- Missed: permissions written as description; passive "will include" content rules; gerund or command list items under a role lead-in; "should"-style advice in the pamphlet.
- Wrongly flagged: "may/can" used for possibility; how a body or process works; colon lead-ins; purpose and scope lines; CJCSI form-template sentences; principle titles in afi90-802.
- Each fix tried so far trades one of these for another. The labelers' own boundary (for example, lead-ins with a full duty) is not fully consistent either.

## EXAM stage (NOT run; run only after the owner approves)
Candidate = control = prompt_FROZEN3.txt (identical to v3 and to gold2_tune/prompt_FROZEN2.txt). Use the stage-1 EXAM harness in ~/reqbot-work/scratch/gold2_tune. It loads only split=exam gold2 units and refuses TUNE documents. It does not yet include CNSSI_No1253: its units, rows and labels live in ~/reqbot-work/scratch/gold2_cnssi (units_gold2_cnssi.jsonl, rows_gold2_cnssi.jsonl, gold_both_cnssi.json) and must be added to the EXAM harness first. Run one 35B request at a time and never the 8B and the 35B together.
```
cd ~/reqbot-work/scratch/gold2_tune
cp ~/reqbot-work/scratch/gold2_tune2/prompt_FROZEN3.txt . && sha256sum prompt_FROZEN3.txt   # expect b9b20379...dbc4
python3 -c "import tl_exam as t;t.show('B0',t.metrics('B0'))"                              # B0 on EXAM
C='{"prompt":"prompt_FROZEN3.txt","bs":4}'
for s in 1 2 3; do python3 run2_exam.py ornith:35b $s e_L35_s$s "$C"; done
for s in 1 2 3; do python3 run2_exam.py llama3.1:8b-instruct-q4_K_M $s e_L8_s$s "$C"; done
```
Because candidate and control are the same prompt, one set of three seeds serves both. The PASS rules are those in PREREG4 (recall at least B0 + 8; precision at least B0 + 10, or at least B0 - 5 with recall at least B0 + 12; no EXAM document worse than B0 by more than 5 recall). Regression checks: the 74-obligation set and silver EXAM in ~/reqbot-work/scratch/clause_label, using the same prompt file. The prompt is unchanged from v3, so those numbers already exist there.

## Files
TUNE_LOG3.md (full log), prompt_FROZEN3.txt, the round prompts (pa_permission.txt, pb_description.txt, pc_leadin.txt, pd_reason.txt, pe_fewshot.txt with fewshot_block.txt and fewshot_from_gold2.txt, pf_codex.txt), the Codex inputs and outputs in codex/, the arms arm_r{0,a..f}_L35_s{1,2}.json, and cache.jsonl. The guard test (test_guard.py) passed again at the end: 13 refusals, and only the 10 TUNE documents loaded.
