# Source-based obligation sample: labeling rubric (WP-45.1e)

## What this is

ReqBot extracts "requirements" (obligations) from policy PDFs. To find out how many real obligations it **misses**, we
need an independent list of the obligations that are actually in the documents. `pack_a.md` holds a few pages of three
documents, already cut into short numbered pieces (sentences and list items), in the order they appear on the page. You
label every piece. You are one of two independent labelers. Do not compare notes and do not look at the other labeler's files.

## Rules

- Open only this file, `pack_a.md` and `check_labels.py`. Do not open other files on this machine, run any code other
  than the checker, or look at how the pipeline works. Run in a directory that holds only these three files.
- **Label each piece by reading it.** Do not write a script, regex or heuristic that assigns labels.
- Read the whole page first; a list item gets its meaning from the lead-in above it.
- Judge from the text shown. No outside knowledge of the document or the standard.
- One label per piece. If a piece is odd, say so in `note` (one short sentence) and pick the closest label.

## The label (`label`)

| Value | Use when |
|---|---|
| `obligation` | The piece states something an organization, role or person must, shall, will or should do or must not do, or a requirement or criterion that must be met, **or a recommendation a reader could act on** ("organizations should secure all of these elements"). Include a list item that carries the action even when the party is named only in the lead-in above it. A sentence that introduces a list **and** states its own action ("Register at least two officials who:") is an `obligation`. |
| `lead_in` | The piece only introduces a list and states no action of its own beyond who or when: "The USD(AT&L) shall:", "The Program Manager will:". Its list items are labeled on their own. |
| `scope` | Applicability or scoping text: who or what the document covers or does not cover ("This instruction applies to ..."). |
| `not_obligation` | Everything else: definitions, background, explanation of how a technology works, benefits, examples, headings, page headers and footers, tables of contents, references and citations, acknowledgements, legal or release boilerplate, permissions ("may", "can") that impose nothing, descriptions of what a person or system does. |

Rules of thumb: a "should" recommendation counts as an obligation; a plain description in the present tense ("The
hypervisor provides a sandbox") does not; "may" and "can" are permissions, not obligations.

## Whether the piece was cut correctly (`segment_ok`)

Pieces were cut by a program, so some are wrong. Set `segment_ok` to `false` when the piece is two separate sentences
joined together, one sentence cut into two pieces, or text that is garbled or out of order (for example a table or a
column that was read across). Otherwise `true`. Still give the label for what the piece says, and add a short note.

## Where to write the labels

One JSON object per line, in a file named with your labeler name (`claude` or `codex`): `labels_<name>_a.jsonl`. Every
piece id in `pack_a.md` must appear exactly once. (The ids below are examples and are not pieces.)

```json
{"id": "XXXX-p001-001", "label": "obligation", "segment_ok": true, "note": ""}
{"id": "XXXX-p001-002", "label": "lead_in", "segment_ok": true, "note": ""}
{"id": "XXXX-p001-003", "label": "not_obligation", "segment_ok": false, "note": "two sentences joined"}
```

Check the file (the checker reads only `pack_a.md` and your label file):

```bash
python3 check_labels.py --pack-dir . --a labels_<name>_a.jsonl
```

Send the label file back. Do not edit it after sending.
