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
| P1 | A fixture with liquidity.usd set to "NaN" or "Infinity" yields an adequate-liquidity helper signal. Production occurrence has not been measured. | T-021: validate numeric boundaries and preserve unavailable depth. | Strict JSON outputs, full stubbed handoffs, unchanged valid readings and reproducible benchmark evidence. |
| P1 follow-up | Source inspection confirms that upstream-contract --write returns before the comparison that populates its collapse-refusal list. T-016 already keeps manual freeze checks mandatory. | Specify a small guard that compares observed coverage with the old baseline before writing; retain the current manual rules until that fix is separately verified. | Offline collapse/write-order reproduction and red-first tests; never replace observations with synthetic baseline data. |
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
upstream answer, leaving the other 574 rows unchanged. Publication awaits the complete
guarded rebaseline and fresh independent review. T-022's first independent and
red-team reviews instead found a variable-connection-delay gap: 12.1 seconds configured
can produce only 4.1 seconds between real HTTP starts. Its named opt-in pacing repair is
implemented at frozen 8b54497 and approved by combined second review at 12/12, with no
remaining material red-team finding. A separate slow-retry
preservation regression also has its own tests-only red and scoped collection deadline.
The approved source is merged locally as 9d2ed35. Full integrated checks, exact-head
preflight and actual published manual and scheduled release gates remain pending.

The prior write restriction is historical. Current unrestricted execution works and the
Owner explicitly authorized continuing technical deployment. Other sign-off categories
and product gates remain in force; no permission guard was bypassed.
