# WP-45.12 — how the extractor is asked what a requirement is (results)

Plan and rules: [docs/PHASE45_WP4512_PLAN.md](../../../docs/PHASE45_WP4512_PLAN.md) (merged before any run). Arms on `llama3.1:8b-instruct-q4_K_M` at temperature 0.1, scratch only: **D0** the production Step C prompt, **D1** the inclusive discovery prompt frozen in WP-45.7, **P1** one call per paragraph asking whether it states a duty (the paragraph's own text becomes the quote). Scripts: `p1.py`, `run_arms.py`, `analyze.py`; report: `outputs/wp4512_report.json`.

## Labeled development pages (74 owner-adjudicated obligations, 38 chunks; two repeats per arm)

| arm | recall (repeat 1 / 2) | precision (1 / 2) | records (1 / 2) | mean F1 |
|---|---|---|---|---|
| D0 (production prompt) | 62.2% / 60.8% | 72.6% / 71.2% | 82 / 84 | 0.663 |
| **D1** (inclusive prompt) | **91.9% / 90.5%** | 55.6% / 57.1% | 143 / 136 | **0.697** |
| P1 (per paragraph) | 100% / 100% | **44.7% / 43.8%** | 174 / 177 | 0.614 |

**By the registered rules:** P1 **fails** (precision below the 50% gate in both repeats; it is not recommended). D1 **meets** the labeled-page gates (recall 29 points above D0, precision above 50% in both repeats) and has the best F1; whether it is recommended also needs the owner's rating of its additions (rule 3), which is pending. Caveat from the plan: D1 was designed on these pages; P1 was not.

## AFI 17-203, whole document (197 paragraph-sized units, one run per arm)

| | D0 | D1 | P1 |
|---|---|---|---|
| candidates | 120 | 173 | 195 |
| units covered by a candidate | 98 (49.7%) | 100 (50.8%) | 195 (99%) |

- **P1 says "duty" about 195 of 197 paragraphs**, including the cover page, a website notice and an effective date. The 8B model answers yes to almost anything in a yes/no question about a paragraph; this is the yes-bias the labeled pages measured (precision 44%), not coverage worth having.
- **D1 barely changes which paragraphs get a record** on this document (100 against 98; 22 units covered by D1 and not by D0, 20 the other way, which is the size of run-to-run variation). Its gain on the labeled pages is real but comes from prose and manual text (NIST SP 800-125, AFMAN 17-2101), not from AFI 17-203.
- **What both prompts miss.** 77 units are covered by neither D0 nor D1. By a crude rule (a modal word, or an imperative or third-person verb opener) 15 of them look like duties; the rest are introductions, definitions and table text. The 15 include "Submit requests for waivers as directed ...", "No event will be closed out as a Category 8.", "2.5.3.3 Coordinate with and inform the 624 OC, MCCC, CFP ...", "3.7.1.5 Collaborate with LE or IC partners ...". These are the rows the checklist's "possible missed requirements" section already lists.
- **Correction to what I told the owner earlier:** "only about half of an AFI's paragraphs have an extracted record" overstates the gap. Half of the units are not duties; the real residue after D1 is on the order of 15 duty-looking paragraphs in 197 units, not 100.
- D1 also produced 37 quotes (of 173) that match no paragraph of the chunk text, some of them words from its own prompt example ("the director will: (1) review access lists annually."); Step D's grounding check rejects quotes that are not in the chunk, so they would not reach the index, but they are noise to filter.

## What this says

1. Re-asking the question per paragraph (P1) is not workable with the 8B model as the judge. Another model, or a harder prompt, would be a new arm.
2. The inclusive prompt (D1) is still the only prompt change with measured support: it lifts recall from about 62% to about 91% on the labeled pages at a precision cost the checklist's hints already absorb. It does not fix the handful of AFI duties that both prompts miss.
3. Nothing is changed in the pipeline. Adopting D1 changes Step C for every document, forces re-extraction and a reindex: the owner's decision, after rating `outputs/afi17-203_D1_additions_rating_sheet.md` (the 22 units D1 adds over D0 on AFI 17-203).

`outputs/afi17-203_additions_rating_sheet.md` is the registered seeded sample of P1-or-D1 additions (40 of 97); because P1 failed its gate it is mostly P1 noise and is not asked of the owner.

## Limits found in review

- P1 classifies at most the first 1,500 characters of a unit but emits the whole unit as the quote. It matters for 1 of 197 units on AFI 17-203 and 0 of 183 on the labeled pages, so it does not change the registered numbers; it would matter for table-shaped units in other documents.
- The owner's rating sheets show the paragraph, its number, its heading and its parent paragraph read from the numbering; units longer than 1,800 characters are cut in the sheet only.
