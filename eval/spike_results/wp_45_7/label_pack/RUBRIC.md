# Held-out and kind labeling: rubric (WP-45.7, version 2)

## What this is

ReqBot extracts "requirements" from policy PDFs. To measure how many real ones it finds and misses, we need an independent
list of what is actually in the documents. You label short numbered pieces (sentences and list items) of source pages. You
are one of two independent labelers. Do not compare notes and do not look at the other labeler's files.

There are two packs. Do the one you were given.

- `pack_heldout.md`: pages of eleven documents you have not seen. Label every piece (`label`, `kind`, `segment_ok`, `note`).
- `pack_devkind.md`: pages with some pieces marked for a second look. Give each marked piece a `kind` (or `none`) and a note.
  Lines without an id in square brackets are context only; do not label them.

## Rules

- Open only this file, your pack and `check_labels.py`. Do not open other files on this machine, run any code other than the
  checker, or look at how the pipeline works. Run in a directory that holds only these files.
- **Label each piece by reading it.** Do not write a script, regex or heuristic that assigns labels.
- Read the whole page first; a list item gets its meaning from the lead-in above it.
- Judge from the text shown. No outside knowledge of the document or the standard.
- One label per piece. If a piece is odd, say so in `note` (one short sentence) and pick the closest label.

## What counts (changed from version 1)

Version 1 counted only "must / shall / will / should" statements. **Version 2 counts anything a reader could act on that the
document asks of, allows, or advises for a party**, because many sources (NIST for example) rarely say "must", and the end
user decides what to enforce. So "you should probably do this", a hint at it, and a permission each count.

## The label (`label`, held-out pack only)

| Value | Use when |
|---|---|
| `obligation` | The piece states something a party **must, shall, will, should or may do, or must not do**, or a requirement or criterion to be met, **or a recommendation or hint a reader could act on**, or a **permission or authorization given to a party** ("The AO may grant a waiver for up to six months."). Include a list item that carries the action even when the party is named only in the lead-in above it, and a third-person duty statement under a mandatory lead-in ("Provides quarterly reports."). A sentence that introduces a list **and** states its own action is an `obligation`. Give it a `kind` (below). |
| `lead_in` | The piece only introduces a list and states no action of its own beyond who or when: "The Director will:". Its list items are labeled on their own. |
| `scope` | Applicability or scoping text: who or what the document covers or does not cover ("This instruction applies to ..."). |
| `not_obligation` | Everything else: definitions, background, explanation of how a technology works, benefits, examples, headings, page headers and footers, tables of contents, references and citations, acknowledgements, legal or release boilerplate, and **descriptions of what a person, system or technology does or can do** ("Hypervisors can permit interactions between guest OSs"; "Resources may be partitioned physically or logically"). Role descriptions nobody can act on or audit are not obligations. |

The test for `may` and `can`: is there a party and an act that the text lets, advises or asks that party to do? Then it is a
permission (an `obligation` with kind `permission`). If it only says what a technology is able to do or what may happen,
it is `not_obligation`.

## The kind (`kind`)

Required when `label` is `obligation` (held-out pack), and the only label in the kind pack. One of:

| Value | Wording and meaning |
|---|---|
| `obligation` | Mandatory: shall, must, will, is required to, has to, is to; also a verb-free duty statement under a mandatory lead-in; also a requirement or criterion that must be met. |
| `recommendation` | Advised, not mandated: should, is recommended, ought, "organizations should consider ...", and the negative forms **should not** and ought not (a negative recommendation stays a recommendation). A hint at what to do counts here. |
| `permission` | Allowed or authorized, not required: may, is authorized to, is permitted to, can (when it gives a party an option). |
| `prohibition` | Forbidden: shall not, must not, is prohibited from, may not (when it forbids), never. |
| `none` | (kind pack only) The marked piece is not a requirement of any kind under the rules above. |

When two kinds appear in one piece, use the strongest in the order obligation, prohibition, recommendation, permission, and
mention the other in `note`. A conditional or exception does not change the kind ("shall ... unless the Manager approves" is
an obligation).

## Whether the piece was cut correctly (`segment_ok`, held-out pack only)

Pieces were cut by a program, so some are wrong. Set `segment_ok` to `false` when the piece is two separate sentences joined
together, one sentence cut into two pieces, or text that is garbled or out of order (for example a table or a column read
across; this pack includes pages from a control catalog with tables). Otherwise `true`. Still give the label for what the
piece says, and add a short note.

## Where to write the labels

One JSON object per line, in a file named with your labeler name (`claude` or `codex`). Every piece id in your pack must
appear exactly once. (The ids below are examples and are not pieces.)

Held-out pack, file `labels_<name>_heldout.jsonl`:

```json
{"id": "XXXX-p001-001", "label": "obligation", "kind": "recommendation", "segment_ok": true, "note": ""}
{"id": "XXXX-p001-002", "label": "lead_in", "kind": "", "segment_ok": true, "note": ""}
{"id": "XXXX-p001-003", "label": "not_obligation", "kind": "", "segment_ok": false, "note": "two sentences joined"}
```

Kind pack, file `labels_<name>_devkind.jsonl`:

```json
{"id": "XXXX-p001-004", "kind": "permission", "note": ""}
{"id": "XXXX-p001-005", "kind": "none", "note": "describes what the technology can do"}
```

`kind` is empty (`""`) unless `label` is `obligation`. Check your file (the checker reads only your pack and your label file):

```bash
python3 check_labels.py --pack pack_heldout.md --mode heldout --labels labels_<name>_heldout.jsonl
python3 check_labels.py --pack pack_devkind.md --mode devkind --labels labels_<name>_devkind.jsonl
```

Send the label file back. Do not edit it after sending.
