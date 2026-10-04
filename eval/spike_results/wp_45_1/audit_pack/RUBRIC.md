# Attachment audit: labeling rubric (WP-45.1b)

## What this is

ReqBot extracts "requirements" from policy PDFs as short quotes. Many quotes are list items or half-sentences that
only make sense with the text that introduces them: `The Program Manager:` ... `(a) Maintains the
access roster.` The pipeline tries to attach that introducing text (the **stem**) to the quote.
This audit measures two things on a random sample of records:

1. Does the quote need a lead-in, and where is it? (pass A, source text only)
2. Is the stem the pipeline attached the right one? (pass B)

You are one of two independent labelers. Do not compare notes, and do not look at the other labeler's files.

## Rules

- Open only this file, `pack_a.md` and `pack_b.md`. Do not open other files in the repository, run any code, or look at
  how the pipeline works. Run in a directory that holds only these three files.
- **Two passes, in order.** Label every card in `pack_a.md` and save the file before you open `pack_b.md`. Do not
  change pass A answers after you have seen pass B.
- Judge from the text shown. No outside knowledge of the document or the standard.
- One label per card. If a card is odd, say so in `note` (one short sentence) and still pick the closest label.
- Cards are in random order. Their numbers carry no meaning.

## Pass A: source text only

For each card in `pack_a.md`, answer in this order.

**1. `standalone`**

| Value | Use when |
|---|---|
| `complete` | Read alone, the quote says who is obligated (or what is required) and what they must do or meet, and it would not mislead. Missing nice-to-have context is still `complete`. An imperative with a generic addressee ("Retain visitor logs for 90 days.") is `complete`. |
| `needs_lead_in` | The quote is missing something it depends on: who is obligated ("Maintains the access roster."), a condition or scope it applies under, or the sentence it continues ("unless the system owner approves otherwise"). Retrieved alone it would be ambiguous or misleading. |
| `not_a_requirement` | The quote states no obligation or requirement at all (a definition, description, background, heading, citation, boilerplate, or unreadable text). If you choose this, leave the two fields below empty. |

**2. `lead_in_location`** (only when `standalone` is `needs_lead_in`; otherwise `null`)

| Value | Use when |
|---|---|
| `same_chunk` | The governing text is earlier in the chunk where the quote is marked. |
| `previous_chunk` | The governing text is in the previous chunk shown. |
| `section_heading` | The only governing context is the section heading in square brackets at the top of the chunk. |
| `not_shown` | The quote needs a lead-in, but nothing shown supplies it (or none exists). |

If more than one applies, pick the text that most directly governs the quote: the sentence or clause that introduces
the list or that the quote continues, before a heading.

**3. `lead_in_text`** (required when `lead_in_location` is `same_chunk`, `previous_chunk` or `section_heading`;
otherwise `null`). Copy the shortest passage that supplies the missing context, exactly as shown. Use `...` to skip
words inside it. Do not paraphrase.

A quote marked `(the quote does not appear verbatim in this chunk ...)` was reworded or assembled by the extractor.
Judge it as written.

## Pass B: the stem the pipeline attached

Only some cards appear in `pack_b.md`. For each, judge the stem against the quote. Look at the first value, then the
next, and take the first that fits:

| Order | `stem_verdict` | Use when |
|---|---|---|
| 1 | `right` | The stem is the text that governs the quote, and stem plus quote together read as one complete, correct statement. Includes the first half of the same sentence the quote finishes. |
| 2 | `wrong_sibling` | The stem is another item of the same list or at the same level as the quote (a peer), not the text that introduces it. |
| 3 | `fragment_chain` | The stem is related and sits in the right place, but is itself an incomplete piece (a list item or half-sentence), so stem plus quote still lacks its lead-in. |
| 4 | `not_needed` | The quote is already complete, and the stem is accurate, relevant context that does it no harm. |
| 5 | `wrong_other` | The stem is unrelated to the quote, or belongs to a different list, clause or section. |

## Where to write the labels

One JSON object per line, one file per pass, named with your labeler name (`claude` or `codex`):
`labels_<name>_a.jsonl` and `labels_<name>_b.jsonl`. Every card id must appear exactly once in its pass. (The ids above are examples and are not cards.)

```json
{"id": "R997", "standalone": "needs_lead_in", "lead_in_location": "same_chunk", "lead_in_text": "The Program Manager:", "note": ""}
{"id": "R998", "standalone": "complete", "lead_in_location": null, "lead_in_text": null, "note": ""}
{"id": "R999", "standalone": "not_a_requirement", "lead_in_location": null, "lead_in_text": null, "note": "heading text"}
```

```json
{"id": "R999", "stem_verdict": "wrong_sibling", "note": ""}
```

When both files are written, check them (the checker reads only the two pack files and your label files):

```bash
python3 check_labels.py --pack-dir . --a labels_<name>_a.jsonl [--b labels_<name>_b.jsonl]
```

Send the label files back. Do not edit them after sending.
