# Engineering priorities

Prepared during the Owner-requested technical audit. This is a release queue, not a claim
that queued fixes are implemented or deployed. Existing task criteria and product gates
remain binding. No runtime rewrite, paid upstream or permission change is part of this work.

| Priority | Finding and evidence | Action | Release condition |
|---|---|---|---|
| P0 | Scheduled snapshots save rows while page fetches fail; the job remains successful. The latest inspected complete UTC day also shows these holes. | T-020: bounded recovery, safe diagnostics, zero-pass manifests and a final coverage failure after preserving data. | Frozen tests, independent and red-team review, full offline CI, then an observed scheduled pass. |
| P1 | RugCheck pool accounts are summed as wallets; absent holder lists are represented as zero. Current code and saved fixtures reproduce the seam. | T-016: separate pool accounts conservatively, disclose exclusions, retain fallback bands and represent absent readings as null. | Offline handoffs, observed contract re-freeze under the five pre-registered rules, independent review and tagged deployment smoke checks. |
| P1 | Benchmark ages use the wall clock and uncached negative requests can reach live upstreams. Existing T-011/T-019 evidence separates these inputs. | T-011, then T-019: pinned replay clock, dated negative entries, explicit misses and allowlisted one-time fills. | Replay never reaches the network; a complete recorded cache reproduces committed outputs on the reviewed engine. |
| P1 | V4 identifiers are display-truncated before a network lookup; traded tokens can be swept into the no-trace escalation. | T-013, then T-012, after benchmark dependencies. | Deterministic row-level before/after evidence; publication updates only when measured and authorized. |
| P1 | Complete offline assessment with liquidity.usd set to "NaN" returns low and fails strict JSON; "Infinity" returns medium. A zero/unavailable mix also falsely claims all pools empty. Production occurrence is unmeasured. | T-021 after the existing dependencies: validate scalar boundaries, nullable MCP output and depth handoffs. | Strict JSON outputs, full stubbed handoffs, unchanged valid readings and reproducible benchmark evidence. |
| P1 follow-up | A fully offline cold --write probe overwrites a baseline after a path falls from full observation to zero; running the comparison first detects and refuses the same collapse. T-016 already keeps manual freeze checks mandatory. | Specify a small guard that compares observed coverage with the old baseline before writing; retain the current manual rules until that fix is separately verified. | Offline collapse/write-order reproduction and red-first tests; never replace observations with synthetic baseline data. |
| P2 | Discovery uses the keyless source and converts some absent figures to zero; partial scans need an explicit status. | T-017, then T-018 at its existing allowed date. | Existing privacy-text sign-off and timing condition still apply; verify discovery-to-assessment inputs. |
| P2 | The risk engine is a large module; there is no fresh latency profile in this audit. | Extract pure normalization and provider adapters in small follow-ups after correctness repairs; first measure latency and upstream request fan-out. | No behavior drift under replay. Tune only measured bottlenecks. |

## What is already sound

The Python Worker has no application runtime dependency, keeps critical coverage gaps
fail-closed, isolates per-request disclosures with context variables, and discloses stale
cache use. The deploy runner derives its offline test list from the test workflow and runs
the full list before shipping. Preserve these seams while fixing the measured defects.

## Current release evidence

T-020 is published at master 5bb391f with actual tests-first and additive-test commits,
full checks, required Linux jobs and independent completion review. Manual snapshot run
38139242886 preserved its actual pool rows and manifest before correctly failing incomplete
coverage. Committed data confirms recovery adds twenty-seven rows across three pages; HTTP
429 responses remain observed gaps. A scheduled run on the published code is still required
before task completion. The earlier green job never established complete coverage.

A disposable read-only branch experiment measures the unchanged collector with slower
request pacing on a GitHub runner, without repository writes or a new scheduler:
https://github.com/jakegu1/vetagent/actions/runs/38140061977. This is a hypothesis test,
not a deployed pacing change or a claim that slower requests resolve shared-egress limits.
The saved data independently confirms 672 pool rows, forty HTTP 200 pages and zero gaps.
T-022 now prepares the measured 12.1-second interval for scheduled pool collection.
Retain its actual rows and manifest during integration. The original recovery
limits and final coverage gate are unchanged. The minor registered DNS-fixture follow-up
also remains, supported by independent fresh-budget pending-worker probes.

T-016 is deployed at master c18de92. Exact source and integrated checks, actual observed
contract freeze, independent review and required Linux jobs all passed. Actual Worker
deployment and production smoke run 38139780104 completed, with no skipped deployment
steps. A separately tagged live Solana answer returns the new outside-pool holder field
and retains fail-closed behavior. T-011 is deployed on this published base; no real fill or
published benchmark change belongs to that task.

T-011's exact e120fe5 source has independent round-2 approval at 12/12 and passing
required Linux jobs. Published integration fefe6d1 retains its tests-first and named-change
history; actual deployment 38146148169 runs and passes offline and tagged smoke steps.
The real read-only cache replay identified 89 unrecorded URLs. T-019 independently
reproduced those misses, protected the whole cache and completed one listed fill without
changing old entries. Its zero-miss replay changes two rows through a successful recorded
upstream answer, leaving the other 574 rows unchanged. Exact 393346f now has independent
approval at 12/12 and red-team none; approved source is merged as e93169a. The lead's
combined replay is byte-identical and immutable with zero network calls or misses. Full
integrated checks and exact-head Linux preflight pass; actual Worker deployment 38150990382
and tagged smoke pass on published a19c3dc. Public figures and health are read back.
T-013 starts from that exact base. T-022's first independent and
red-team reviews instead found a variable-connection-delay gap: 12.1 seconds configured
can produce only 4.1 seconds between real HTTP starts. Its named opt-in pacing repair is
implemented at frozen 8b54497 and approved by combined second review at 12/12, with no
remaining material red-team finding. A separate slow-retry
preservation regression also has its own tests-only red and scoped collection deadline.
The approved source is merged as 9d2ed35. Full integrated checks pass thirty-one steps;
exact-head preflight 38148113901 passes required jobs and all 219 observed upstream checks,
with zero unobserved or collapsed path. Published head is 86a8111. Manual collection
38148501978 succeeds; independent raw counts verify 676 unique pools, forty HTTP 200
pages, all eight chains and zero gaps, with every old byte preserved. Real scheduled
verification remains pending; the earlier branch experiment is not substituted for it.

The prior write restriction is historical. Current unrestricted execution works and the
Owner explicitly authorized continuing technical deployment. Other sign-off categories
and product gates remain in force; no permission guard was bypassed.

T-013's exact b99f2e7 passes fresh independent review at 12/12 and red-team review
with no material finding after 563 independent probes. Approved source is merged as
46fb2a6. Its one protected fill adds five successful complete-id seller answers,
preserving every old cache file. Actual requested-URL attribution explains four
changed rows; 572 complete rows and all old high verdicts stay unchanged. The lead's
own immutable combined replay is zero-miss, zero-network and byte-identical to both
raw result blobs for all 576 rows. Source Linux preflight 38153547356 passes required
jobs and 219 observed upstream checks with no unobserved or collapsed path. Full
integrated checks pass thirty-one steps in 79.6 seconds. Exact-head preflight
38155937648 passes required jobs and 219 observed upstream checks with no unobserved
or collapsed path. Published 7f796e4 deploys successfully in actual run 38156203366;
offline, Worker deployment and tagged smoke all run and pass. Tagged public figures
and health are independently read back. T-013 is complete; T-012 starts on this base.

T-012's exact 8771725 now passes combined second-round review at 12/12, red-team none.
The new transaction-container availability regression is repaired with independently
reproduced red-first acceptance and both caught guard mutants. All old acceptance remains
immutable, and independent replay reproduces both raw result blobs and every cache/request
byte. Three registered high-to-unknown moves retain critical data gaps; all dead/unsafe
verdicts and 572 otherwise complete rows remain unchanged. Approved source is merged as
248d64d. Both scoped stale Experiment C passages and W49 are closed from actual data;
integrated release checks and actual deployment remain pending.

T-012 is now complete on published e657c32. Full integrated checks pass thirty-one
steps, and exact final preflight 38162435754 passes required jobs and all 219 observed
upstream checks with zero unobserved or collapsed path. Actual deployment 38162750450
runs and passes offline tests, Worker deployment and tagged production smoke. Worker
version is 6d7ccb28-ecab-4623-9c61-8ded53e45644. Separately tagged readback verifies
the new public figures and HTTP 200/ok health. T-021's exact-base numeric caller/conflict
search and zero-miss immutable replay now pass on this published head. It is ready,
with all older tests frozen and any benchmark row drift requiring an explicit amendment.
