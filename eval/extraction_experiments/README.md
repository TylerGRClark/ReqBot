# Preparing the extraction experiments (nothing here changes extraction)

Goal: measure whether a change to extraction (a per-document-type prompt or rule set, for example AFI against NIST) finds more of what an auditor needs without
adding noise. This folder holds the measuring tools and the rules for using them. No model call is made by any file here, and no document is re-extracted.

## What is being measured
1. **Coverage of human checklists** (`coverage.py`): of the questions a person wrote from a publication, how many have a counterpart in our checklist for it.
   Two blind labelers say yes / partial / no per item; strict = both say yes, lenient = neither says no. Disagreements go to the owner.
2. **Precision on a sample** (to build): 100 rows per document type, seeded, owner or two blind labelers mark real requirement / not a requirement / fragment.
3. **Recall against a paragraph sample** (to build, the extraction silver set): for N sampled paragraphs per document type, labelers list every obligation in the
   paragraph; compare with the extracted rows. This is the measure the IG checklists cannot give, because humans pick a subset (their lists are mostly Tier 0 and Tier 1).

## Baselines recorded so far (current extraction, kind-rules-6; two blind Opus labelers; n is small)
| Publication | Their items | Strict | Lenient | Missing | Note |
|---|---|---|---|---|---|
| DoDI 5200.48 (CUI tab of an IG unit workbook) | 18 | 9 | 17 | 1 | the miss: CUI removed from the workplace; not yet checked against the source |
| AFI 17-101 (2020 edition; their sheet is a later revision) | 15 | 7 | 15 | 0 | the partials are enterprise duties the IG rewrote as per-system checks |

Reading: the topics are there; the gaps are wording and scope, which extraction changes are unlikely to fix. An extraction experiment must therefore be judged on
the paragraph-sample recall (3) and the precision sample (2), not on (1) alone.

## Rules for an experiment (written before any run)
- One change at a time. The control and the arm run on the same documents and rows, and the control is run twice to measure the noise floor.
- Documents: tune on a development set, confirm once on documents not used for tuning. Sealed documents (afpd_17-1, DODI 8410.03, NIST.SP.800-125) are never tuned on.
- Labelers are never the author. Two blind copies agreeing is not correctness: sample their agreements for the owner as well as their disagreements.
- Adopt rules (recall up by at least X points without precision falling by more than Y) are written into the experiment's own README before any output exists.
- Re-extraction, a new model call and any change to stored text are on the owner's ask-first list: an experiment is written up and proposed, not run, until he says so.

## Candidate document-type differences to test first (hypotheses, not findings)
- Directive publications (AFI, DAFI, DAFMAN) carry duties on named roles; the DAFI 36-2903 trial showed a different mix (permission 15.5%, prohibition 12%) and front-matter noise.
- Standards (NIST) are control statements with parameters; guidance (DAFPAM) is mostly "should" and examples (DAFPAM 90-803: 40% of rows have no question).
- Candidate lever per type: the extraction prompt's examples and its handling of lists and tables. Compare each against the paragraph-sample recall.

## Using the tools
    python3 eval/extraction_experiments/reference_sets.py <workbook.xlsx> --out ~/reqbot-work/checklists/reference_records.json
    python3 eval/extraction_experiments/coverage.py packets --records ~/reqbot-work/checklists/reference_records.json --publication DAFI16-1403 \
        --questions ~/documents/processed/<run>/<doc>_audit_questions.jsonl --out <scratch dir>
    (two blind labelers write match_A.json and match_B.json: [{"id": "T01", "verdict": "yes|partial|no", "pool_ids": [...]}])
    python3 eval/extraction_experiments/coverage.py score --a match_A.json --b match_B.json

Keep the workbooks and the records JSON outside the repository: they are internal work product and this repository is public.
