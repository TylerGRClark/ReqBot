# HyPE spike: do index-side generated questions find what meaning-queries miss?

Plan and rule: [PREREGISTRATION.md](PREREGISTRATION.md) and [decision_rule.json](decision_rule.json), committed before any result. Backlog item: `docs/TODO_future_improvements.txt` item 3. **Status: harness built and dry-run on 10 records; the full run has not been done.**

## What it does

| File | Job |
|---|---|
| `run_hype.py` | the whole experiment: `generate`, `build`, `evaluate`, `cleanup` (or `all`) |
| `hype_lib.py` | pure parts: prompt, parsing, grounding filter, collapse to `requirement_id`, decision rule |
| `miss_queries.jsonl` | the 15 meaning-written miss-set queries, fixed in advance |
| `decision_rule.json` | the pre-registered rule |
| `../../../tests/unit/test_hype_lib.py` | unit tests (grounding filter, collapse, rule, scratch-name guard) |

- **Questions:** same model as the draft audit questions (`services.audit_questions.MODEL`), temperature 0, at most 3 per record, kept only if every number, acronym and capitalised term is in the record's own text (`unverified_terms`). Appended to `questions.jsonl` as it goes; a restart skips finished records; stops after 5 Ollama failures in a row.
- **Arm A:** `core.ask.retrieve()` on the live `grc_requirements` alias, config defaults, top 20.
- **Arm B:** the same call on a scratch collection `grc_hype_spike_<timestamp>` that holds a copy of the live points plus one extra point per question (payload = the record's payload plus `hype_question`). Hits are collapsed to `requirement_id`, best point wins, then cut to 20.
- Both arms reuse one cached query rewrite and one cached HyDE hypothesis per query, so they differ only by the extra points.
- **Nothing live changes:** the live collection is only read; the scratch name is guarded (`grc_hype_spike_*` only); no requirement JSONL, `pipeline/`, `core/` or `services/` file is touched. Output goes to `~/reqbot-work/scratch/hype_spike/` (not the repo).

## Run

```
PYTHONPATH=. python3 eval/spike_results/hype/run_hype.py all
```

Resumable: run the same line again after any interruption. Then read `~/reqbot-work/scratch/hype_spike/report.md` (verdict at the top; `result.json` has the numbers; `eval_rows.jsonl` per query and arm; `questions.jsonl` every question and every rejected one). Delete the scratch collection when done: `run_hype.py cleanup`.

## Dry run (2026-10-13, 10 records, scratch collection created then deleted)

Generation 2.2 s per record (about 2.7 hours for the 4,462 live records); 25 to 28 questions kept for 10 records, 2 to 5 rejected (all on a spelled-out "Department of Defense" where the text says "DoD"; a strict reading, kept). Build: 4,462 points copied plus questions in seconds. Evaluate: 15 miss + 22 gold queries, both arms, 116 s. On the dry run arm A already finds 7 of 15 miss queries in its top 5 (recall@5 0.467), so there is room to rise. Those numbers are not evidence about the idea: only 10 records had questions.

The dry run found and fixed one filter flaw: a sentence-initial "Which" or "Where" counted as a capitalised term and rejected good questions; the first word is now lower-cased before the check (unit-tested).

## Limits

See PREREGISTRATION.md. In short: 15 miss queries (one is 6.7 points); queries were written by an agent that had read the target records; gold labels are partly stale after the re-ingest, so labels are restricted to live ids; a single run, no repeats.
