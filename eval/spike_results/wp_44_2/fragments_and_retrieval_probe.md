# WP-44.2: dangling fragments in the live data, and a crude retrieval probe

One-off checks (2026-10-04), recorded so the findings are not lost. **Not reproducible evidence** --
Phase 45's designed retrieval test supersedes the probe (see below for why it is weak).

## 1. What text is embedded

`pipeline/embed_and_index.py: build_embedding_text()` returns `embedding_text` (the parent stem
joined to the fragment, from WP-39.2's reconstruction) when present, else `source_quote`, plus
`Ref: <source_ref>`. The same text feeds both the dense vector and the sparse BM25 vector. So a
parent stem that was found IS attached before embedding; a record without one is embedded bare.

## 2. 16 fragment-type survivors in the live (selected) artifacts

| Fragment | parent_stem / embedding_text | Attachment assessment |
|---|---|---|
| implement the following recommendations (NIST.SP.800-125) | yes: "organizations should implement the following recommendations:" | good |
| enforce security requirements (NIST.SP.800-125) | **none** | bare |
| developing virtualization policy (NIST.SP.800-125) | **none** | bare |
| in coordination with USD(I&S) (DODI 5200.48) | **none** | bare |
| satisfy the CUI requirements (DODI 5200.48) | **none** | bare |
| then take the indicated Actions (afi17-203) | **none** | bare |
| and the Primary Recipient will be (afi17-203) | yes, but the stem is itself a fragment ("then take the indicated Actions") | chain of fragments; one sentence split by docling |
| and Informational Recipients will be (afi17-203) | yes, but the stem is the previous fragment | same |
| Using software assurance and hardware assurance tools... (DODI 5200.44) | yes: "e. Establish TSN processes to assess vulnerabilities..." | plausible |
| shall be coordinated with the customer (afman17-2101) | yes: "Denies/terminates DISN LHC requests when it is in the best interest of the AF..." | plausible |
| and 4) continuous professional development... (dafman17-1305) | **none** | bare |
| Required NM data update rates. (DODI 8410.03) | yes: "This section will define for all parties:" | good |
| Location of the NM event. (DODI 8410.03) | yes: same stem | good |
| (1) Network latency and packet loss... (DODI 8410.03) | yes: "NM SLAs and other agreements shall establish baseline and minimum service levels..." | plausible |
| (3) Restrain competition. (DODI 5200.01) | yes: "Information will not be classified, continue to be maintained as classified..." | plausible |
| Maintains Reference (n). (DODI 5200.01) | yes, but the stem is the **previous sibling list item**, not the governing "At a minimum, the Director, DIA:" | wrong parent |

Summary: 10 of 16 have an attachment (at least 2 look wrong or are fragment chains); **6 of 16 are
embedded bare.** The `description` field (Step D.5, grounding-gated) is **empty** for "Required NM
data update rates.", "Location of the NM event." and "enforce security requirements", and merely
repeats the fragment for "satisfy the CUI requirements" and "then take the indicated Actions". So
even a correctly attached fragment ("This section will define for all parties: Required NM data
update rates.") is not a standalone requirement for checklist use. Sample is 16 records.

## 3. Crude retrieval probe (6 hand-written queries, live index, HyDE off, top 20)

| Fragment | Has stem | Result |
|---|---|---|
| Required NM data update rates. | yes | rank 2 |
| Location of the NM event. | yes | not found |
| implement the following recommendations | yes | not found |
| enforce security requirements | no | rank 11 (query reused the fragment's own words) |
| developing virtualization policy | no | rank 1 (query reused the fragment's own words) |
| satisfy the CUI requirements | no | not found |

**Why this is weak:** six queries, hand-written by the same reviewer who had read the fragments.
For the stem-less cases the queries echoed the fragment's own wording, which makes them easy to
find. The directional reading -- a bare fragment is findable only when the query happens to reuse
its words, and a topical question misses it -- is plausible but unproven. Phase 45 must write test
queries from the *meaning* of stem + fragment without copying the fragment's wording.

## 4. Prior evidence this connects to

`eval/spike_results/wp_40_baseline_refresh/classification_report.md`: `missing_context` = 9 of the
retrieval misses in the WP-40 audit, e.g. a fragment-shaped record with an empty `parent_stem`.
