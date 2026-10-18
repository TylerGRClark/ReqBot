# Checklist enhancement: draft questions plus a rough criticality flag (plan, not implemented)

*Written 2026-10-17 after the owner chose to wire the criticality score in as a second job beside draft audit questions. Evidence: the pre-registered experiments on a local branch (`spike/criticality-pilot`, results not yet merged); numbers below are summaries only.*

## 1. What the owner decided

- Criticality is a **flag column**, a hint about what to look at first. It removes nothing and changes no existing field.
- It is **part of the same optional service as draft audit questions**: one user toggle, one model setting (the model already chosen for checklist questions), but **two separate model calls per row** (one writes the question, one gives the score). Merging the calls into one prompt is not allowed: the score was measured as a one-digit answer and only that test is evidence.
- ReqBot stays model agnostic: any Ollama model can be chosen. Evidence exists for `qwen2.5:14b` (good) and `llama3.1:8b-instruct-q4_K_M` (rough but usable).

## 2. What the evidence says (so the label is honest)

Plain prompt (the FIPS 199 impact scale mapped to 1 to 5, no examples, no extra rules), the score read from the model's own probabilities for the digits 1 to 5 (expected value, temperature 0), averaged over three wordings of the instruction. Answer keys: Opus on NIST SP 800-53 (224 controls), and two outside judges (Codex and Gemini) on SP 800-171 (110) and on 100 Air Force requirements. Measures: rank agreement with the key, share of the key's "important" rows found in the top quarter of the ranking, and agreement between two wording sets.

| Model | Rank agreement (bar 0.50) | Important rows in top quarter (bar 60%) | Wording stability (bar 0.80) |
|---|---|---|---|
| qwen2.5:14b, Air Force 100 | 0.63 | 6 of 8 | 0.96 |
| qwen2.5:14b, SP 800-171 | 0.70 | 12 of 19 | 0.94 |
| llama3.1:8b, Air Force 100 | 0.50 | 5 of 8 | 0.94 |
| llama3.1:8b, SP 800-171 | 0.64 | 9 of 19 (missed the bar) | 0.95 |

Limits to state on the label: the judges agree with each other more (0.86 on Air Force) than either model agrees with them; the "important" sets are small (8 rows on Air Force); the 8B is a coarse filter; tuning the 8B prompt on NIST did not carry over to Air Force text, so the prompt stays plain. The score ranks rows **within a document**; it is not an absolute severity.

## 2b. Owner decisions on display (2026-10-17)

- No high/medium/low bands. The flag ("look first", top quarter per document) is shown with the rounded 1 to 5 number beside it; the number is always stored and may be hidden later.
- The score stays a separate column from the compliance tier (T-0 to T-3). On 1,066 tier-marked rows the two were nearly unrelated (rank agreement -0.13; T-0 rows were in the top quarter 42% of the time, T-1 only 16%), so they are different signals. No combined filter in the first version.

## 2c. Change after the first real run (2026-10-18)

The owner rejected the number and the single "look first" mark: decimals are useless to filter on. The checklist now shows one word per row, Critical, High, Medium or Low, set by rank within the document (top 5%, next 20%, next 35%, the rest). Critical plus High is the same top quarter the tests measured; the split inside it and the Medium/Low cut are display choices that the tests did not check. The number stays in the sidecar only. The flag-share setting is gone.

## 3. Design

- **Same job, second call.** `reqbot questions` (and the queued job it already has) gains a second pass per eligible row. Both write beside the document's requirements: questions to `*_audit_questions.jsonl` as today, scores to a new sidecar `*_criticality.jsonl` (the same pattern: keyed by row, with an input hash so a changed row or model recomputes it). The new sidecar is added to the list of per-document files, so removing or moving a document handles it like the questions file. No change to the requirements records, no re-extraction, no Qdrant change.
- **The call.** One request per row to `/api/chat` with `logprobs` and `top_logprobs`, one generated token, temperature 0. Score = expected value of the digits 1 to 5 over the returned probabilities. The prompt is the plain scale plus the row's quote and parent passage as context. The three wordings are three requests; the stored score is their mean, so a row costs three tiny calls (each generates one token).
- **The flag.** Per document, rank rows by score; the top quarter get "look first" and the rest are unflagged. The stored number is also shown, rounded, as "rough criticality (model)". The cut is 25% by default and is a setting.
- **Fallbacks.** If the model service does not return probabilities (not Ollama, or an old version), the column stays blank for that document and the job log says why. It never invents a score. Rows skipped by the questions rules (fragments, definitions, headings) are also skipped here.
- **Checklist.** One new column, plain header, with the label "rough filter" and a one-line note. Sorting and filtering by it is optional extra.
- **Existing 0 to 10 "second opinion" score** (`wants_second_opinion`, `ask_score`) is a different job: it decides whether an unclear row is a real requirement. It is not replaced and shares no code path; the plan keeps the names distinct. That job runs inside the questions pass for unclear rows only; the criticality pass runs after it, once per eligible row, so a run of the questions job can make up to four calls for a row (a second opinion for unclear rows, the question, and three one-token score reads). Rows the questions job withholds a question from (the model answered null, or the second opinion scored them low) get no score and no flag.

## 4. Gates before merge (all registered here, before any code is run)

1. The product code, run on the three frozen sets above with the same model settings, reproduces the experiment numbers within 0.03 (rank agreement) and 1 row (important rows found). The experiment scripts stay the reference.
2. With the toggle off, nothing changes: the checklist and sidecars are byte-for-byte as before.
3. Missing probabilities and a dead server degrade to a blank column with a logged reason; a stored score written for another model or for changed row text is ignored until the job is run again (unit tests with a stubbed call).
4. No real hostnames or addresses in tracked files; docs updated (configuration, architecture, checklist).

## 5. Stop and ask before building

New model calls and a new sidecar file need the owner's go on this plan. Not in scope: tuning prompts further, ranking across documents, using the score to drop or reorder anything by default.
