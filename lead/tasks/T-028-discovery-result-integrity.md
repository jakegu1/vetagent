---
id: T-028
title: Preserve discovery completeness across malformed listings and public interfaces
status: changes_requested
level: 3
size: M
depends_on: [T-025]
decisions: []
backlog: W28
---

## Context and goal

new_pools names its successful/failed listings but declares no top-level status.
It also treats a parsed object without a data list as a successful empty listing.
A partial scan can look complete; malformed input can abort the other usable listing.
Make the observed completeness explicit without changing risk verdicts or historic usage.

## Budget and scope

One bounded task, no new spending/provider/live recording. Files in scope:
src/risk.py (new_pools and a local listing parser only), src/mcp_server.py (discovery
output schema only), tests/test_mcp.py (additive acceptance helpers/functions/imports).
No other production helper, scoring, cache/fetch policy, privacy/telemetry code, gate,
fixture, dependency or permission change. No source work outside these three files.

Use a separate branch/worktree from the lead's ready-spec commit. This is the sole
writer of src/risk.py in this phase. Preserve every old test/helper/input/discovery AST.
Existing tests/test_mcp.py discovers test_ functions automatically; add functions there,
not a new unregistered runner. All new tests are committed first and then frozen.

## Conflict search and named changes

Searched new_pools/new-pools, sources_ok/sources_failed, outputSchema and telemetry
status use across all test files, plus risk's new-pool regression cases, finite-market
discovery seam, MCP schema/output comparison and HTTP telemetry handlers. No older
acceptance change is allowed. Existing all-source failure must still raise RuntimeError;
MCP/HTTP error envelopes and existing fields/count semantics stay compatible.

## Acceptance criteria

1. Successful discovery includes status exactly ok when both listings were observed,
   or partial when only one usable listing was observed. Valid empty data: [] is an
   observed empty result, with status ok when both listings are valid and empty. Count,
   scanned, limit, order, deduplication, chain defaults and stale disclosure are preserved.
2. A usable listing is an object with an explicit list-valued data member. Missing/null/
   scalar/object data and non-object top-level JSON are failures, never empty successes.
   Malformed row/container types that the existing parser would crash on fail that
   listing while allowing the other usable listing to return a partial result. Validate
   into temporary per-listing state so a failure cannot leave unacknowledged half-merged
   rows. Preserve ordinary optional missing fields accepted by the old tests.
3. If neither listing is usable, raise the existing RuntimeError. One malformed listing
   plus one valid empty listing is partial with zero observed pools; two valid empty
   listings are ok; an older healthy listing must not conceal the current failed one.
   Endpoint failures remain source failures rather than token-risk evidence.
4. The real MCP handler's structuredContent and text describe the same status/data.
   Discovery outputSchema declares status as required with enum [ok, partial] and clear
   completeness-only semantics. Exercise actual HTTP routing and prospective telemetry
   with the project's existing offline runtime shim; prior error behavior and self-client
   separation remain. Do not rewrite usage artifacts, historic gate inputs or their rules.
5. First commit adds only new acceptance tests in tests/test_mcp.py. Reproduce meaningful
   red for the original false-empty/completeness behaviors. Commit status/schema and
   malformed-listing handling as separate source findings, preserving the test contract.
   In-memory mutants for always-ok, accepting missing data, and losing the usable listing
   must each fail meaningful assertions. Verify unique replacements and fresh processes.
6. Freeze a clean final head; original risk, MCP, finite-market and HTTP telemetry runners
   remain green, then python lead/checks.py passes all configured steps. New acceptance,
   controls and mutants block external network; the full runner's existing read-only
   Ethereum RPC dependency is disclosed, not described as wholly offline. Report exact
   commits, frozen ASTs, red/final outputs, mutants and complete three-file scope.

## Threat model and delivery

Upstream transport success may carry no usable listing; malformed upstream JSON must not
become market absence or hide the other source. An ok scan may contain no pools; partial
is completeness, never an investment endorsement. Adding status changes prospective tool
telemetry only; no retrospective caller/gate reclassification or extra identifying data.
No live VetAgent request. If later authorized by the lead, every production probe uses
x-mcp-client: vetagent-manual-probe. Require fresh independent and adversarial review,
at most two rounds. Write a signed READY and evidence privately; do not merge or push.

## Amendments

### 2026-10-18: lead-owned derived correctness-test receipt

The frozen source head's configured checks are 34/35 solely because the generated
docs/SCORECARD.md correctness receipt still says 80 MCP assertions instead of the
observed 554. Its production assertions pass; the generator reports exactly that
one stale normalized line. This is stale derived evidence, not a reason to alter tests.

Add docs/SCORECARD.md to scope solely for the lead to regenerate with the existing
fixed-point script in explicit regenerate mode and commit separately after source.
The lead may restore only proved calendar/recent-log display drift from exact external
backups. All original/new tests and source remain frozen. No benchmark result, score,
threshold or historical usage changes. The full configured gate must then pass before
READY/review; reviewers use this amended spec as the contract.

### 2026-10-18 round 1: contain numeric creation-time overflow per listing

Adversarial valid-JSON probes reproduce OverflowError for pool_created_at equal to
an integer with 401 digits or the finite number -1e308. The age helper's numeric
conversion can raise outside the local listing containment, aborting the other usable
listing and yielding HTTP/MCP errors. This is the same malformed-listing boundary,
not a reason to expand the global timestamp or risk logic.

Named additive acceptance change: add
test_discovery_extreme_creation_times_keep_other_listing to tests/test_mcp.py.
Keep all first-round ASTs, assertions, fixtures and helpers frozen. Commit this
addition alone as T-028: named change (creation-time overflow containment), observe
red on 32ea4ec, then fix only the discovery listing boundary in a separate source
finding commit. Cover both numeric values in both listing directions, atomic discard
of the bad listing after an earlier good row, one valid empty survivor, all-bad errors
and real HTTP/MCP survivor responses. No additional numeric or scoring behavior change.

Do not catch BaseException or weaken the network/mutation guards. A mutant removing
the overflow containment must be rejected by the added acceptance. Source/tests then
freeze, the lead separately regenerates the allowed correctness receipt, and the full
configured runner passes on the final clean head. Round 2 is one fresh combined
independent/adversarial review of this bar and regressions, without unrelated fronts.
