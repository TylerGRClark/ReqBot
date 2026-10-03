# WP-44 hand-written labels and review notes

Companion to the generated `report.md` / `per_record.jsonl` (reproduce with
`python3 eval/wp_44_quote_integrity_analysis.py`). Everything here was read by hand against the
source chunk text; none of it depends on the proposed coverage rule.

## 1. The five leaks — what each one invents

Each quote passed the existing fuzzy gate (scores 62–76), appears nowhere in its own document, and
states an obligation the chunk it came from does not.

| Document / chunk | What the chunk actually is | What the quote invents |
|---|---|---|
| DODI 5200.48 chunk 76 | A marking table ("Table 2. Dissemination Control and Distribution Statement Markings…") | a records-keeping duty ("required to maintain accurate and up-to-date records of all dissemination control and distribution statements") that the table does not state |
| DODI 5200.48 chunk 91 | A bare glossary term, 23 characters: "Defense Industrial Base" | a FISMA-style protection obligation ("shall be protected from unauthorized access, use, disclosure, disruption, modification, or destruction") from a term with no definition text |
| afi10-2402 chunk 5 | The cover page: "29 AUGUST 2017 Operations CRITICAL ASSET RISK MANAGEMENT PROGRAM" | a role responsibility ("The CIO shall be responsible for the overall management and oversight of the … Program") from a title line |
| afi17-203 chunk 50 | Table 3.2, a descriptive activities-by-phases matrix with no obligation language | an obligation to conduct a thorough Post-Incident Analysis |
| afi17-203 chunk 50 | the same table chunk | an obligation that the report "shall include lessons learned and resulting improvement plans" |

Pattern: every leak comes from a chunk with nothing extractable (cover page, glossary term, marking
table, descriptive matrix). Note: the two afi17-203 leaks sit on the table chunk that docling
2.94.0 lays out differently (see PR #159). They are in the existing 2.84.0-era ingest; a separate
Step C test on the 2.94.0 layout produced a similar invented quote that also survived Step D, so
the leak does not depend on the docling version.

## 2. Stitched quotes — what was checked, and how

88 stitched quotes survive Step D (list lead-in + item, e.g. "AFGSC will: Chair the AF NLCC/NC3
Council."). Decision (Tyler): they stay.

- **Automated screen** (71 with a colon-delimited lead-in): 43 match the chunk's governing header
  or section title; 26 have the lead-in verbatim elsewhere in the chunk text (multi-section chunks);
  2 lead-ins are not verbatim in the chunk (§3 below); 17 have no lead-in to check.
- **Read by hand:** 12 random samples with chunk context; the ~28 header-mismatch cases (quote
  compared with the header, not the full chunk); one case read in full — afi13-550 chunk 33, whose
  parallel lists repeat "Co-chair the AF NLCC/NC3 Board and Group" under both AF/A10 (3.3.1.1) and
  AFGSC (3.3.3.2); each was attributed to the correct office.
- **Result:** no lead-in attached to an unrelated item in what was reviewed. This is a partial
  review; absence of evidence, not proof. No governance validator is built because of it.

## 3. The two stitched quotes whose lead-in is not verbatim in the chunk

- **dafman17-1305 chunk 41** — "Wing/Delta Cyberspace Offices (formerly known as Cybersecurity
  Offices) shall: Monitor status on all Wing/Delta cyberspace workforce personnel." The source
  header is "2.14. Wing/Delta Cyberspace Offices (formerly known as Cybersecurity Offices)
  **(WCO/DCO)** shall:" and the item is 2.14.1. The model dropped the acronym parenthetical.
  **Harmless:** correct attribution, one parenthetical omitted.
- **DODI 8410.03 chunk 13** — this is not really a stitched quote. The quote reads "…including but
  not specifically determining architectures and technical approaches for:" where the source
  (item 3.d under the USD(AT&L)) reads "…including but not specifically **limited to** determining
  architectures…". The model **dropped the words "limited to"**. Attribution is correct, but the
  quote is not verbatim and the dropped words change the sense of the phrase.
  **Not caught by the coverage check** (every remaining word is in the chunk, so coverage is 1.0)
  — this is a concrete instance of the documented bag-of-words limit and is recorded as a backlog
  observation, not something WP-44.1 claims to fix.

## 4. Ligature note

`pipeline/repair_ligatures.py` is a standalone, manual repair tool targeting one document-specific
font defect; `run_pipeline.py` never calls it. Nothing in this analysis establishes that any of
these inputs were ligature-repaired, and the coverage check adds no ligature handling.
