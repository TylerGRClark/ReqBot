# Can the local model sort the `unknown` rows into real requirements and noise? (an experiment; nothing is wired in)

Why: after kind-rules-8 the `unknown` bucket (about a quarter of all rows) is the main place noise hides, and it still holds real requirements (11 real of 44 in a representative
sample). A rule cannot tell "The Wing Cybersecurity Office addresses all unclassified COMSEC ..." (real) from "Tier Two provides direction and support ..." (a description).
Gating the whole bucket would lose about 7% of all real questions (the owner's bar is about 1%). This tests whether the local model can separate them.

## Data (fixed before any model output)
228 rows the current rules call `unknown` that two blind Opus labelers agreed on: 73 real requirements, 155 not. They come from two samples (the proportional 223-row sample and the
240-row unknown-bucket sample). The labels are the answer key; they are never shown to the model. The row text itself is not committed (public repo); `rows` is read from a local file.
- Dev: the 89 rows of the unknown-bucket sample's first half, used to write the prompt and choose the threshold.
- Held out: the other 139 rows (second half of that sample + the proportional sample's unknown rows), run once.

## Arms (same model qwen2.5:14b, temperature 0.1, same server)
- **W (baseline, no new calls):** the existing question writer: a row "kept" when it got a question. On all 228: keeps 62 of 73 real, drops 57 of 155 not.
- **S1:** a single scored question: "How clearly is the marked sentence a requirement an auditor could check? 0 to 10", with the labelers' definition of requirement / not / fragment.
- **S2:** S1 plus 6 worked examples taken from the dev rows only.
A row is kept when its score is at or above a threshold chosen on the dev rows (the lowest threshold that keeps at least 90% of the dev real rows).

## Adopt rules (registered now)
On the held-out rows, at the dev-chosen threshold, an arm is a candidate only if:
1. It keeps at least 90% of the real rows (which holds the overall loss near the owner's 1%: unknown real rows are about 7% of all real rows).
2. It drops more of the noise than W does (W drops 37%), and at least 60%.
3. S2 does not beat S1 by relying on a dev example that reappears in the held-out rows (checked by hand).
If neither qualifies, the bucket stays as it is.

## Limits
Same-family labelers (Opus) made the key; 139 held-out rows; one run. Adopting means a new model call per `unknown` row at question time (about 1,700 rows across the 22 documents,
a few minutes each document) behind a default-off switch, which is a separate decision.

## Run
`PYTHONPATH=. python3 eval/spike_results/unknown_second_opinion/run_second_opinion.py --rows <local rows json> --ollama-url <url>`
