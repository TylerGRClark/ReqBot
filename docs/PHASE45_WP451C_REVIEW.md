# WP-45.1(c)/(d) sanity check

Reviewed 2026-10-04 against the local `PHASE45_WP451C_PLAN.md` and the retrieval
implementation in the existing PR #201 review checkout. I did not inspect other
labelers' answers, modify the plan, or run a retrieval experiment.

**Recommendation: proceed with a bounded measurement experiment after the adjustments
below.** The core idea is good: use the same questions and target records across text
variants, freeze the corpus, and separate topic queries from party-specific queries.
Correcting wrong actors remains worthwhile even if retrieval metrics are inconclusive.

## Changes that matter before running

1. **Separate the target-text effect from changing all its competitors.**
   The quote-alone arm removes stems from all 203 stemmed records, including correctly
   attached competitors. A target can move up because its competitors got worse, even
   if removing its own stem did nothing. Conversely, improving several oracle records
   can make them compete with one another. These are valid comparisons of index-wide
   policies, but they do not isolate whether this target's stem helps or hurts.

   For primary Q1–Q3 diagnosis, substitute only the queried target's vector and hold
   competitor texts fixed. Build the replacement vectors once and reuse them. Then run
   the cohort-wide replacement as a separate check of what applying the policy does
   to the whole search result. Distinguish those two effects in the report.

2. **Reuse generated query inputs across arms, including the production-path repeats.**
   For each query and repeat, generate the rewrite and HyDE hypothesis once, save their
   text and vectors, and reuse them for every arm. Repeat generation three times if
   desired, but keep each repeat paired. Otherwise a change in the invented hypothesis
   can masquerade as a change in document context. HyDE currently uses temperature 0.3;
   identical settings do not guarantee identical outputs. This also reduces model calls.

3. **Keep the actual top-20 retrieval inputs while exposing deeper ranks.**
   Do not obtain the depth-100 diagnostic by calling `retrieve(top_k=100)`. The inspected
   implementation then changes per-leg prefetch from 100 to 500, changing RRF inputs.
   At `top_k=20`, `min_score=0.02`, it fetches 100 per leg, requests 60 fused results,
   filters by score, and returns 20. Capture the intermediate lists in the eval adapter;
   if requesting 100 fused results, retain those same per-leg inputs and identify the
   wider fused output as a diagnostic. Report both raw fused rank and whether the target
   actually survives the production threshold and reaches the returned results.

4. **H4 is an informative benchmark, not an upper bound on retrieval.**
   Correct context can still dilute an embedding or promote competing results. Selecting
   every semantically appropriate heading need not be the best selection for ranking;
   a different subset or a generated context description can perform better. Therefore
   “H4 failed, so an LLM cannot do better” does not follow.

   A sensible practical stop remains available: if verified headings show no convincing
   benefit, defer the LLM experiment because it has not earned priority. Describe that
   as a resource decision, not proof that the method cannot help. Likewise, concatenating
   adjudicated context in Q3 tests that representation rather than every possible use of
   correct context.

## Keep the first run small

- Start with the primary production / quote-alone / adjudicated-context comparisons.
- For the heading extension, start with H0, H3 and H4. Comparing dense-only against
  dense-plus-BM25 is useful and worth retaining.
- H1 is optional background, not a prerequisite. A reconstruction on today's corpus,
  models and expanded queries cannot reproduce the historical experiment exactly or
  overturn its original result. H2 can wait if the selective comparison answers the
  immediate question. Save and hash the actual text variants, not just their recipes.
- Use the in-memory engine initially, with the live collection's vector configuration
  and sparse IDF settings preserved. If an apparent win depends on small ordering
  differences, validate that candidate against server-backed scratch collections before
  recommending a production change.

## Pin down these contracts in the harness

- **Eligible IDs and denominators:** the four listed groups sum to 119, but excluding
  18 non-requirements and one unnecessary-stem record from 130 leaves 111. Resolve
  overlap/exclusions before query writing. Freeze explicit group ID lists. Report
  misleading siblings/other stems separately from incomplete fragment-chain stems;
  removing a useful partial stem can have a different effect from removing a wrong one.
- **Two query styles:** report topic and party-plus-topic effects separately. Keep both
  queries together when bootstrapping records; repeats are not additional independent
  records. Where document clustering matters, report that uncertainty too. Pooling both
  styles can hide the specific benefit the heading hypothesis predicts.
- **Inconclusive outcomes:** retain the predeclared benefit gate, but a point estimate
  below 0.05 with a wide interval is not evidence that context has little value. Say
  “no demonstrated improvement,” rather than converting an inconclusive result into
  “readability only.” Q4 remains descriptive regardless of its apparent significance.
- **Heading correctness:** an actor-shaped leaf heading is not necessarily the actor
  governing every record below it. Check H3's assignments against the existing audit
  before recommending an applies-to display field. Freeze the rule before retrieval;
  Codex can review it for source correctness without examining retrieval outcomes.
- **Query quality:** party-specific questions are appropriate for this hypothesis.
  Keep the topic-only and existing gold queries as counterchecks, and spot-check a
  small selection before running. Preserve natural wording; ordinary terminology
  overlap is not itself leakage. One-target recovery measures whether the expected
  record was found, not whether other returned records could answer the question.

The plan does not need a redesign of the pipeline or an LLM feature to start. It needs
a precise paired measurement contract and a smaller initial set of experiments.
