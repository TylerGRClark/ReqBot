# Logic diagrams

What ReqBot does today, from PDF to checklist, drawn from the code. One diagram per stage; the overview comes first.
Last checked against the code on 2026-10-22 (the switch to clause labeling, WP-4).

## How to read them

- Boxes are work, diamonds are decisions, cylinders are files.
- Green is built or passes. Amber is kept as it is, or a looser match. Red is rejected or nothing found.
  Blue is a side output or a note. Dashed grey is planned or switched off.
- The stages are named by job, as in the [redesign plan](../PIPELINE_REDESIGN_PLAN.md). The old step letters
  are not used here; section 6 of the plan translates them where an older document or a log line still has one.
- The main diagrams show only what runs today. Planned and switched-off parts are on the roadmap diagram.
- Code-style names (rejection labels, clause labels, hint flags) are the real names in the code, so they can be searched for.

## The diagrams

| Diagram | The question it answers |
|---|---|
| [Overview](00_overview.md) | The whole path today, in the order the code runs it. |
| [PDF reading and chunking](01_pdf_reading_and_chunking.md) | How a PDF becomes chunks that know which section they sit in. |
| [Requirement finding](02_requirement_finding.md) | How each line of a chunk is labeled, and which lines become rows. |
| [Screening](03_screening_today.md) | Which rows are rejected, and in what order the checks run. |
| [Anchoring](04_anchoring.md) | Where each row sits in its chunk (the splitter's offsets, checked). |
| [Context attaching](05_context_attaching.md) | How the explained text beside each row is built. |
| [De-duplication and identity](06_dedup_identity_stem.md) | De-duplication and requirement IDs. |
| [Totals and search indexing](07_totals_and_indexing.md) | What is written at the end, and what goes into search. |
| [Checklist building](08_checklist_building.md) | How each row gets its citation, party, flags and passage. |
| [Text scan](09_text_scan.md) | How duties that the labeler did not keep are found. |
| [Draft audit questions](10_draft_questions.md) | How a draft question is written, withheld and read back. |
| [Kind labels](11_kind_labels.md) | How each row is labelled by what sort of statement it is. |
| [Delivery](12_delivery.md) | How the checklist reaches an assessor. |
| [Network MCP door](13_network_mcp.md) | How a call from an AI tool on another machine is let in, run and written down. |
| [Roadmap: planned or switched off](90_roadmap_not_built.md) | What is planned or switched off, kept apart from what runs. |

Not drawn: Ask, Evidence, Trace and Compare (search and answers), the web app's upload and job path, and the screens of the web app.

## Keeping them true

A diagram is a claim about the code. When a change alters a check, a status, a threshold or a flag named in a
diagram, change the diagram in the same pull request.

[`tests/unit/test_logic_diagrams.py`](../../tests/unit/test_logic_diagrams.py) checks what a machine can: that no
step letters come back, that every code-style name in a diagram still exists in the source, and that this index lists
every diagram. It cannot check meaning, so read the diagram against the code. To check that a diagram still draws,
paste it into [mermaid.live](https://mermaid.live/) or preview it in an editor.
