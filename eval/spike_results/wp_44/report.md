# WP-44 quote-integrity analysis (generated; do not hand-edit)

revision `c92bd873b7`; 13 documents; 1991 raw quotes with a known chunk.

## Category x Step D outcome

| category | survived Step D | rejected by Step D |
|---|---|---|
| exact | 1687 | 30 |
| format_only | 83 | 0 |
| elision | 5 | 0 |
| invented | 5 | 64 |
| stitched | 88 | 29 |

## Invented quotes (coverage < 0.8)

- total 69: 64 rejected by existing gates, **5 survived Step D (leaks)**
- leak coverage: [0.188, 0.333, 0.455, 0.474, 0.647]; leak fuzzy scores: [62.3, 62.7, 64.1, 73.0, 76.5]
- coverage of rejected invented quotes: min 0.0, max 0.714
- **lowest coverage among the 1922 non-invented quotes: 0.857**
- leaks absent from their whole document (independent label): 5 of 5
- rejected-invented absent from their whole document: 63 of 64

## The leaks

- `DODI 5200.48` chunk 76: coverage 0.474, fuzzy 62.3, present in corpus artifacts ['normalized', 'enriched', 'gated']: 'The organization is required to maintain accurate and up-to-date records of all dissemination control and distribution statements.'
- `DODI 5200.48` chunk 91: coverage 0.188, fuzzy 76.5, present in corpus artifacts ['normalized', 'enriched', 'gated']: 'The Defense Industrial Base shall be protected from unauthorized access, use, disclosure, disruption, modification, or destruction.'
- `afi10-2402` chunk 5: coverage 0.333, fuzzy 64.1, present in corpus artifacts ['normalized', 'enriched', 'gated']: 'The CIO shall be responsible for the overall management and oversight of the Critical Asset Risk Management Program.'
- `afi17-203` chunk 50: coverage 0.455, fuzzy 62.7, present in corpus artifacts ['normalized', 'enriched']: 'The organization is responsible for conducting a thorough Post-Incident Analysis.'
- `afi17-203` chunk 50: coverage 0.647, fuzzy 73.0, present in corpus artifacts ['normalized', 'enriched']: 'The organization shall ensure that the Post-Incident Analysis report includes lessons learned and resulting improvement plans.'

## Threshold sweep (non-invented quotes newly rejected / leaks blocked)

| threshold | leaks blocked | other quotes rejected |
|---|---|---|
| 0.7 | 5/5 | 0 of 1863 survivors |
| 0.8 | 5/5 | 0 of 1863 survivors |
| 0.9 | 5/5 | 3 of 1863 survivors |
| 0.95 | 5/5 | 6 of 1863 survivors |
