# Engineering workflow and review evidence

This is the first engineering-workflow package: reliable review evidence and CI.
It does not implement automated acceptance or change repository rules. Tyler
retains merge authority. ReqBot's runtime, deployment and extraction behavior are
outside this package.

## Review the final candidate

For each bounded change, agree on scope and acceptance criteria before coding.
The implementer supplies the changed paths, test results and their limitations.
An independent reviewer checks the final candidate and records its full head SHA
and base SHA. Every substantive finding needs a disposition: fixed with evidence,
declined with a verifiable explanation, or accepted by Tyler as a recorded risk.
A finished review, a green job or silence does not establish owner acceptance.

A new push requires fresh review. A base change requires fresh review evidence
and appropriate integration checks. Check the revisions against GitHub at the
time of the owner's decision. This package records evidence; an authenticated
acceptance validator and repository-rule changes are a separate follow-up.

## Gemini advisory evidence

The credential-bearing `Gemini PR Review` workflow uses `pull_request_target` and
checks out the event's base SHA. Its script and architecture brief come from that
trusted revision. It fetches the event's base/head Git objects and reads the diff
and changed-file blobs as data, without checking out or executing candidate code.
The diff is computed from their merge base to the head, matching a PR comparison.
The provider has no tools. Candidate text remains untrusted even when it contains
instructions or claims of approval.

The script validates structured provider output and writes `review-evidence.json`:

| Field | Meaning |
| --- | --- |
| `status` | `complete`, `unavailable`, or `invalid` |
| `base_sha`, `head_sha` | Exact event revisions reviewed |
| `diff_sha256` | Hash of the Git diff bytes submitted, before UTF-8 decoding |
| `context_sha256` | Hash of the trusted architecture brief |
| `model`, `attempts` | Model selected after fallback and number of provider attempts |
| `provider_attempts` | Per-call status, fixed finish reason, response size/hash and numeric token usage; parseable rejected responses are retained as unvalidated evidence |
| `run_id`, `run_attempt`, `run_url` | GitHub run and rerun attempt reference |
| `changed_paths` | Paths in the pinned diff |
| `review` | Summary, what was checked, findings and provider limitations |
| `limitations`, `reason` | Omitted context and incomplete-review explanation |
| `publication` | `not_published`, `published`, `stale`, or `failed` |

`complete` means the response passed the evidence contract. It does not prove the
model's claims or resolve its findings. A completed review with findings can have
a successful job; unavailable/invalid evidence, stale publication and publication
failure exit unsuccessfully. Gemini remains advisory and is not a newly required
repository check. If a work package explicitly requires Gemini, an outage needs
an owner-approved alternative or exception, rather than a clean-review claim.

Each run posts its own revision-labeled comment. It never edits an older comment.
Reruns have separate identities using the GitHub run-attempt number.
The script checks head/base freshness before any provider call and immediately
before each fallback call and publication. GitHub does not provide an atomic state-check/comment-write
operation: a push can occur between them, so the comment identifies only the
reviewed revision and never claims current approval. Concurrency cancellation
reduces wasted work; the revision checks and immutable comments handle older runs.

Limits are eight model/key attempts, a 240-second budget for starting provider
calls, at most 60 seconds of HTTP timeout per request, one SDK HTTP attempt per
request, a 120,000-byte diff, 60,000
bytes of surrounding source, 16,384 combined thinking/output tokens, a 48,000-byte response, and 20
findings. HTTP timeouts are not an independent wall-clock kill switch; the job
timeout bounds the whole run. An oversized diff is rejected instead of silently reviewing a prefix.
Omitted surrounding files are recorded as limitations. The job also has a
12-minute timeout. A forced cancellation/timeout or dependency-install failure
can prevent evidence creation; the artifact step requires the file, so missing
evidence cannot become success. Artifacts are retained for 30 days.

Fallback applies to provider errors, abnormal finish reasons (including
`MAX_TOKENS`), malformed JSON and invalid review contracts, within the same
eight-call/240-second start budget. Only a normal `STOP` response that passes
validation completes the review. A valid review with findings stops fallback;
the script never asks another model to replace it with a clean review. Parseable
rejected responses remain in the artifact as unvalidated evidence, and comments
flag those responses for inspection and finding disposition. This includes bare
arrays and scalar JSON values, not just the expected object wrapper.

Gemini 3 uses medium thinking; Gemini 2.5 uses a 4,096-token thinking budget.
The larger total token cap leaves room for a full review JSON after reasoning.
Finish reasons and numeric token usage are retained; raw response text and
provider exception messages are not written to job logs. Unknown finish reasons
are recorded as `UNKNOWN` and cannot establish completion.

Gemini is a required part of ReqBot's coding process: obtain a complete review
of the current candidate and resolve its findings before owner acceptance.
An unavailable or invalid run requires recovery or an explicit owner-approved
alternative. This process requirement does not silently change GitHub branch
rules; repository check enforcement remains a separate owner decision.

The reviewer SDK is installed in the reviewer workflow and credential-free
protocol-test job, with its direct version pinned in
`.github/scripts/requirements-review.txt`; it is not a runtime dependency. Transitive packages are not
locked by this first package. The architecture brief is
[`.github/review_context.md`](../.github/review_context.md); keep it consistent with
approved architecture changes.

Automatic paid review runs only for non-draft PRs from this repository, on open,
push and ready-for-review events. Forks use an independent manual review that
records the reviewed revisions, checks, findings and limitations; no automatic
paid fork route is added. After a base-only change, update the candidate branch
to trigger a new event with current revisions. Rerunning an old event keeps its
old pinned revisions and can be rejected as stale.

Changes to this reviewer become active after merging because the privileged
workflow uses trusted base code. The PR that introduces them is reviewed by the
previous version. Pre-merge tests use fake providers; the first subsequent normal
PR run supplies live integration evidence. Do not run candidate workflow code with
reviewer credentials to work around this trust boundary.

## CI checks and proposed required-check list

Confirm these names and successful runs before changing repository rules:

| Check | Evidence and intended policy |
| --- | --- |
| `lint` | Repository Ruff checks |
| `test` | Python tests, including workflow failure cases |
| `reviewer-protocol` | Pinned reviewer SDK and fallback tests against fake HTTP, without provider credentials |
| `secrets` | Gitleaks scan |
| `frontend-test` | Standalone frontend tests |
| `frontend-typecheck` | Standalone `npm exec tsc -- --noEmit` under Node 20 |
| `Analyze (python)` | Python CodeQL analysis and SARIF gate |
| `Analyze (javascript-typescript)` | JS/TS CodeQL analysis and SARIF gate |
| `docker` | Container build/start, configuration, served frontend and PDF parse/chunk smoke checks |

The proposed routine required list is `lint`, `test`, `secrets`, `frontend-test`,
`frontend-typecheck`, `Analyze (python)` and `Analyze (javascript-typescript)`.
The separate `reviewer-protocol` check exercises SDK compatibility and is not
added to repository rules by this change. Keep `docker`
mandatory for packaging, dependency, deployment and parse/chunk changes, and
visible for other changes. Before adopting rules, decide how to enforce that
conditional requirement. Any exception must record the candidate SHA, affected
check, reason and Tyler's authorization. This PR changes no required-check list.

### CodeQL blocking policy

The gate requires a SARIF directory containing readable SARIF 2.1.0 files with
CodeQL runs and explicit results lists. The accepted driver names are `CodeQL`
and the [documented CLI name](https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-cli/sarif-output),
`CodeQL command-line toolchain`. Empty results are valid; missing output
is not. Present invocation records must report successful execution. Every result
must resolve to a driver rule, with consistent rule ID/index and valid metadata.
Unsupported references or malformed evidence fail rather than disappear.

The proposed blocking policy is an effective result level of `error` **or** a
rule's numeric `security-severity` of at least **7.0**, regardless of precision.
An omitted result level inherits `defaultConfiguration.level`, then defaults to
`warning`. `pass` and `notApplicable` results do not represent findings. Suppression
metadata does not exempt a blocking finding. This is a severity policy; it makes
no claim that every result has high confidence. The owner reviews this policy
before merging it. Other findings remain visible in GitHub code scanning.

This custom gate checks evidence shape and severity, not full SARIF-schema
conformance or scan authenticity. It runs after the CodeQL action, whose failure
also fails the job. The gate is ordinary candidate CI code; it is not the trusted
acceptance validator planned for the next package. Branch rules alone must not
be described as protection against a candidate weakening its own CI.

## Local validation

Use the project's system-Python development setup. The focused workflow tests
need pytest and do not need provider credentials, the Gemini SDK or live services:

```bash
python3 -m pytest tests/unit/test_ci_evidence.py -q
python3 -m ruff check .
cd frontend
npm ci
npm exec tsc -- --noEmit
npm run test
```

SDK transport probes also need the separately pinned reviewer requirements;
they use fake HTTP rather than live API keys. The `reviewer-protocol` CI job
installs those requirements and runs `tests/unit/test_gemini_sdk_transport.py`
alongside the evidence tests. Runtime-only test environments may skip the
SDK-specific module; they must still run the evidence/fallback tests.

Use Node 20 to match CI. Broader Python tests use the existing project/dev
dependencies. Record missing dependencies or infrastructure failures explicitly;
do not report a suite that never collected as a passing run.
