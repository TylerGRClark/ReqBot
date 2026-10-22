# TUNE log (prompt wording changes; TUNE documents only)

Splitter and context rules fixed before any model call (two splitter bugs found and fixed on B0/rule-only checks before the first model call: abbreviations such as E.O. split a sentence, and hard line wraps inside a sentence split a clause; neither involved model output).
Matching/metrics exactly as PREREG. Run L8 = llama3.1:8b-instruct-q4_K_M, shuffle seed 1, TUNE pooled (593 labeled requirements, 626 B0 rows).

B0 (no model): recall 0.798, precision 0.743.

| version | recall | precision | flagged | note |
|---|---|---|---|---|
| v1 | 0.938 | 0.767 | 730 | PREREG wording, first draft |
| v2 | 0.936 | 0.784 | 716 | change 1 |
| v3 | 0.943 | 0.790 | 713 | change 2 (FROZEN) |

Change 1 (v1 to v2): added to NOT_REQUIREMENT: plain statements of fact/description with no instruction, and step/section titles and figure captions. Why: v1 false positives (read 20) were mostly descriptions, step titles and captions. Result: precision +1.7 pts, recall -0.2 pts (dafpam90-803 prec .368 to .412).
Change 2 (v2 to v3): added to DUTY: passive/impersonal wording counts ("will be classified", "should be put in place", "is recommended", "need to"). Why: v2 misses (read 20) were mostly passive should/may/recommended statements. Result: recall +0.7, precision +0.6.
No further changes after this point.

## FROZEN prompt
File: ~/reqbot-work/scratch/clause_label/prompt_FROZEN.txt
sha256: b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4

```
You are labeling clauses taken from a policy or standards document. For EACH clause below, decide whether it is a requirement, using the context shown with it.

A requirement tells someone to do something, not to do something, or that they may or should do something, in a way an auditor could check. Labels:
- DUTY: an obligation or responsibility. Passive or impersonal wording counts too ("X will be classified per Y", "controls should be put in place", "X is recommended", "personnel need to ..."). Counts: "shall", "must", "will" statements; "should" statements; commands ("Identify the root cause."); and third-person duties with no modal verb ("The office coordinates with DISA to resolve issues." "Serves as the lead for X.").
- PROHIBITION: says not to do something ("shall not", "must not", "do not", "is prohibited").
- PERMISSION: says someone may do something ("may", "is authorized to", "is permitted to").
- NOT_REQUIREMENT: does not ask or allow anything. Headings and titles, definitions, background or explanation of how something works, statements of purpose or scope, what something is or where it is located, statements of fact or description that give no instruction ("X is a core function of Y", "Data is collected by spot observations"), bare cross-references, effective dates, names and signature blocks, notices, step or section titles and figure captions ("Step 3 - Develop Controls", "Figure 6.3. Actions by Leaders"), a lead-in line ending in a colon with no content of its own, table headers.
- UNSURE: you cannot tell.

Answer ONLY with a JSON list, one entry per clause, like:
[{"id": 1, "label": "DUTY"}, {"id": 2, "label": "NOT_REQUIREMENT"}]

{CLAUSES}
```
