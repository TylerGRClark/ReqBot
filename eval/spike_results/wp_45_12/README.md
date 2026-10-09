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

## Owner's rating of D1's additions on AFI 17-203 (2026-10-09)

The owner rated all 22 units D1 covers and the current prompt does not (`outputs/afi17-203_D1_additions_rating_sheet.md`, with his words kept as written).

| rating | count | units |
|---|---|---|
| requirement ("is req", "is a req") | 11 | 4, 5, 7, 8, 9, 10, 11, 13, 14, 17, 18 |
| partial or borderline ("is sort of a req"; "gives authority to but isn't necessarily a req, I'd let it slide") | 4 | 12, 19, 20, 21 |
| not a requirement | 7 | 1, 2, 3 (who the instruction applies to or does not apply to), 6 ("describes a role"), 15, 16 ("describes how to comply with a requirement but isn't actually one"), 22 (a table he could not read) |

**Against the registered rule** (at least 60% requirement or partial). The registered rubric allows *partial* only for a requirement that is cut or merged oddly. Three of the owner's ratings (units 19-21, "gives authority to but isn't necessarily a req, I'd let it slide with it is") are neither: they are intact paragraphs that he says are not necessarily requirements, though he would accept them. So the gate result depends on how those three are read, and it is the owner's to decide:

- counting them as requirement-or-partial (his "let it slide"): 15 of 22 = 68% (15 of 21 = 71% leaving out the unreadable table); D1 clears the 60% bar;
- counting them as not a requirement (his literal "isn't necessarily a req"): 12 of 22 = 55% (12 of 21 = 57% leaving out the table); D1 **does not** clear the bar.

**Owner's call (2026-10-09): units 19-21 count as passes.** Unit 21 ("adversary activity may be allowed to continue ...") becomes auditable once phrased as a question ("is adversarial activity allowed to continue ...?"), so it is a valid extraction even though on its own it is a permission, and he will not try to separate suggestions from requirements at this stage; unit 19 is a requirement for the same reason (requirements can be drawn from the text), and unit 20 is read the same way. The 68% reading therefore stands, and with the labeled-page gates met (recall 91% against 62%, precision 56%) D1 passed the WP-45.12 gates. P1 had already failed and was not rated.

What the seven "not a requirement" ratings show: three are applicability statements ("It applies to all military and civilian AF personnel ...", "This Instruction does not apply to ..."), which D1's prompt deliberately returns so a later step can attach them. A checklist hint for these rows is proposed separately (#275, not part of this change).

**Nothing is adopted.** Adopting D1 changes what Step C asks for every document, and forces re-extraction and a reindex. The measured trial is planned in #276 (WP-45.13) against the two table-fix baseline runs.
