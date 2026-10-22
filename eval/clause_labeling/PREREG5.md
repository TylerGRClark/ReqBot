# PREREG5: fragmentation expectations for the clause-labeling method

Written 2026-10-22, before any run of the new method. Do not edit after a result exists; if a
bug is found, fix it, say so, and rerun everything.

Before-numbers: `fragmentation_before_2026-10-22.json` (made by `fragmentation.py` on the live
library with the old method; 8,940 rows; F2 114, F3 513, F4 35, F5 695, F6 1,210, F7 515,
F8 1,247, F9 1,174, F10 564 text-scan rows and 14 possible-missed).
After-numbers come from the same script on the re-extracted library.

(Corrected the same day, still before any new-method run: a reviewer found that "(a) Notify" was read as starting in lower case and that bullets were not seen as list items; the script and these numbers were fixed. The first version read F2 144, F3 236, F4 55.)

## Expectations (library totals, after versus before)
| Count | Expectation |
|---|---|
| F2 starts mid-sentence | down at least 50% |
| F3 list scraps | down at least 50% |
| F4 short lower-case scraps | down at least 50% |
| F6 not a complete sentence | down at least 30% |
| F8 root not exactly located | equal to 0 |
| F1 rows, F5 table-line rows | reported, not judged (F5 may rise: one row per table line) |
| F7, F9, F10 | reported, not judged |

A count of 0 before cannot go down: report it as "no room", not a pass.

## Lost-rows check (blind sample)
Old rows with no matching new row (match = same text after tidying, or the old text contained
in a new row) are "lost". On CNSSI_No1253 and dafi36-2903, draw a random sample of 40 lost
rows per document (all of them if fewer). A reviewer who sees only the row text, its section
and the surrounding passage (no pipeline labels, no earlier grades, not the author) marks each
"real requirement" or "not a requirement". Warn if more than 25% of the sampled lost rows are
real requirements. Report the sample size and the reviewer.

## Limits
Counts measure fragmentation, not whether the right sentences were chosen. Those two documents
are named in advance for the lost-rows check; none has been used to tune the new method.
