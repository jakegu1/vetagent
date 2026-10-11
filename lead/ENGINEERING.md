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

## Current release limitation

T-020's four frozen engineering files now have preserved chronological Git commits after
the second independent and adversarial reviews found no material technical defect. The
original and additive acceptance reds are reproduced and the final archive suite is green.
Full release-head checks, Linux preflight and independent completion audit precede release;
actual collection and scheduled execution are checked afterwards. A registered DNS fixture
reusing an expired deadline needs a small follow-up; independent fresh-budget probes verify
the current pending-worker cap and catch its mutant. T-016 remains separate while its
observed baseline and full asynchronous evidence are completed.

The refreshed remote base is ea545c0. Scheduled snapshot run 38126683939 started at
2026-10-11 08:58 UTC and succeeded; its manifest still records failed requests alongside
real rows. Latest master tests run 38127088651 succeeded. The lead ran the complete offline
suite on that fresh base successfully. Observe real post-release coverage rather than
inferring collection completeness from the old green job.

The earlier session's write restrictions prevented branch creation and complete local
validation. On 2026-10-11 the Owner restored the execution permissions and asked the lead
to continue. Git fetch, clean managed-worktree status and a real asyncio probe now succeed.
Release work resumes from inspected origin/master ea545c0, with the frozen chronological
patches preserved. Commits, full checks, Linux preflight and actual collection are verified
in that order before reporting release completion. No permission guard is bypassed.
