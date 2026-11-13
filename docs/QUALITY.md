# Measured quality

*Last updated 2026-11-13. Every figure below comes from a test or a count run against this repository's code, and names its source. These are small labeled samples, so read them as indicators, not guarantees. ReqBot's output always needs human review.*

## Finding requirements

Requirement finding is clause labeling (since 2026-10-23): rules cut each chunk into clauses at exact offsets, and a local model labels each clause. It replaced a method in which the model wrote a list of requirements.

| Test | Method | Recall | Precision |
|---|---|---|---|
| Sealed exam, 5 documents never used in tuning, 250 labeled requirements, 3 runs ([REPORT4](../eval/spike_results/clause_labeling/REPORT4.md)) | previous method (stored rows) | 78.0% | 67.8% |
| same | clause labeling, 35B model | **96.4%** | **91.0%** |
| same | clause labeling, 8B model | 94.8% | 73.4% |
| 74-obligation development set (REPORT4, regression check) | clause labeling, 35B model | 94.6% | 93.7% |
| Sealed set, AFI 17-203 and AFI 13-550, 172 labeled requirements ([PREREG7 report](../eval/clause_labeling/PREREG7_REPORT.md)) | clause labeling, 35B model | 97.7% | 90.9% |

Quote integrity: in these runs no row quoted text that was not in the document (quote errors: 0), because every row is a clause located at exact offsets in its chunk.

**Older figures you may find in the archive.** Early October 2026 development notes (`archive/PHASE45*`) report roughly 62 to 70 percent recall on the same 74-obligation set. That was the retired list-writing method. The same set scores 94.6% under clause labeling.

**Which model.** The guides' default setup (an 8B model) works and finds nearly as many requirements, but it adds many more rows that are not requirements (precision 73% against 91%). For best results set `extraction_model` to a 35B-class model; the numbers above were measured with Ornith 1.5 35B-A3B (Q4_K_M, about 23 GB), configured as `ornith:35b`.

**Limits.** The truth in these tests comes from two AI labeler families plus 31 rulings by the owner, not a full human audit. Precision is measured against the agreed lists, so it is a lower bound. Units were paragraph-sized; whole-document behavior was tested once (one document, 59% of the added rows were real, just under the bar). Tables of controls are the weak spot (CNSSI 1253: 10 agreed requirements, precision 57.7%).

## Citations (live library, counted 2026-11-13)

23 documents, 6,773 requirement rows. A row's citation is read from the document's own numbering when the sentence carries a number, or worked out from the numbered text before it and marked "(inferred)":

| | rows | cited directly | marked "(inferred)" | blank |
|---|---|---|---|---|
| Air Force publications (15 documents) | 5,723 | 49% | 49% | 1.6% |
| DoD, CJCS, CNSS and NIST (8 documents) | 1,050 | 62% | 23% | 14.9% |
| All | 6,773 | 51% | 45% | 3.7% |

[Document styles](DOCUMENT_STYLES.md) make this exact for outline-numbered documents. In the five DoD and CJCS documents they were applied to on 2026-11-05, rows with a blank citation fell from 117 to 1 (CJCSI 6510.02G), 78 to 0 (DoDI 5200.01), 143 to 0 (DoDI 8410.03) and 21 to 4 (DoDI 5200.48), and all 233 inferred citations in DoDI 5200.48 and 64 in DoDI 8551.01 became exact paragraphs. Of more than 600 labels checked against an independent method (and by reading the pages wherever the two disagreed), one was wrong: a form page where the PDF reader files the enclosure title after the form's first items. Control documents (NIST 800-53 and 800-171, CNSSI 1253 tables) have styles built and tested on the PDF reader's output (682 of 682 sampled control IDs agree with the PDF text order) but are not yet applied to a live library.

## Not measured

- Time saved in an audit. No timing study has been run.
- Use by people other than the owner.
- Search ranking as a published figure. An optional re-ranker improved ranking in internal tests; the numbers are in the project notes, not in this repository.
- Behavior on documents of types not listed above.
