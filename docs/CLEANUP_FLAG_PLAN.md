# Checklist cleanup: flag rows that are probably not requirements (plan, not implemented)

*Written 2026-10-21 after the owner chose to build this as a third job of the checklist enhancement. Evidence: a labeled set built for this (about 1,700 paragraphs and 1,300 extracted rows from 12 documents, each labeled by two blind Sonnet copies that agree on about 97%), held in the owner's work folder, not in this repository.*

## 1. What the owner decided
- A **flag**, never a deletion. A flagged row stays in the records, the sidecar and the sheet; the sheet can filter it out.
- A third job beside draft audit questions and the criticality flag: one toggle in the enhancement settings, **off by default**, its own model call per row.
- **Optional model setting** ("cleanup model"), empty by default so first-time setup gains no new required field. Empty means the main model, the same fallback pattern as the extraction and enrichment models. Help text says a larger model removes about twice as much.
- **Phase 1: double flag.** The row keeps its Critical / High / Medium / Low rating and also carries the junk flag, so we can see how often a row is both. **Phase 2 (tracked, see section 5):** once the overlap is near zero, make the two mutually exclusive.
- Display: the existing Priority column carries the flag (for example "High · junk") so one filter covers both. The stored rating is never overwritten.
- One locked wording, no user-editable prompt.

## 2. Evidence (so the label is honest)
Rows are the production rows after Step D. Junk = labeled "not a requirement" or "fragment". Chosen on six tuning documents, confirmed once on a fresh batch of 331 rows (320 where the two labelers agreed) from the same 12 documents.

| Setup | Junk removed | Real requirements dropped | Real rows on the sheet |
|---|---|---|---|
| 35B (Ornith), strict wording with "may counts" | 56.5% | 0 of 258 | 80.6% to 90.5% |
| 35B, careful wording | 32% | 0 | 86% |
| Llama 8B, careful wording | 21% | 1 | 84% |
| qwen 14B, strict wording | worse than careful (13% on the tuning documents) | 0-1 | |

Limits to state: one labeler family; 12 documents; a stricter wording helped only the 35B; "may"-only rows are 4% of real rows and the wording keeps them; junk left after cleanup is still about 1 in 10.

## 3. Design
- `services/cleanup.py`: the locked prompt, one request per eligible row to `/api/chat` (temperature 0, 4 tokens, thinking off where the model supports it), "NO" means flag, anything else keeps the row. Sidecar `<doc>_cleanup.jsonl` keyed by row with an input hash (row text, passage, model, prompt version) so changes recompute it. Added to the per-document artifact list.
- Runs inside `reqbot questions` as a third pass, after criticality, only when enabled. Rows the questions job withheld are skipped as for criticality. Failures degrade to no flag and a logged reason; five consecutive connection failures stop the pass.
- The model sees the row's quote and its chunk text, as in the tests.
- Checklist: the Priority cell and CSV/Markdown carry "junk"; no model call at build time.

## 4. Gates before merge
1. Product code on the 331-row batch reproduces the tested numbers: real rows dropped 0 and junk removed within 3 points of 56.5% with the 35B.
2. Toggle off: checklist and sidecars byte-identical to before.
3. Missing server or model: no flag, logged reason, no crash; a stored flag for another model or changed text is ignored.
4. No real hostnames in tracked files; CLI, configuration and architecture docs updated.

## 5. Tracked follow-up: make rating and junk exclusive (do not lose this)
After the first cleanup runs across the 22 documents, count rows flagged junk that also rate Critical or High. If at most 1% of Critical rows and at most 3% of High rows are flagged junk, and the owner has read those overlaps and agrees they are not real, change the rule: a row flagged junk gets no priority band and a row rated Critical cannot be flagged junk. Until then both show. Entry also in `docs/TODO_future_improvements.txt`.

## 6. Stop and ask before building
New model calls and a new sidecar file need the owner's go on this plan. Not in scope: tuning the wording further, dropping or hiding flagged rows by default, the extractor.
