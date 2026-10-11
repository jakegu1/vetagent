---
id: T-020
title: Recover snapshot page failures and report incomplete collection after preserving data
status: done
level: 3
size: M
depends_on: []
decisions: []
---

## Context

The Owner requested a live check and repair of the daily snapshot collector. At inspected
remote head 2d69034c7d484ac6536d4c5e8109c5835a8cdacd, pool files exist for every day from
2026-09-03 through 2026-10-09. The latest observed scheduled job succeeded, but its manifest
records nine failed page fetches among forty-one requests. Failed pages are abandoned;
the manifest cannot identify the HTTP failure, and an all-empty collection returns before
writing its manifest. Existing workflow ordering protects pool commits from the optional
sellability probe and must remain.

Evidence: https://github.com/jakegu1/vetagent/actions/runs/37909537096 and
bench/snapshots/runs-2026-10-09.ndjson at the inspected remote head. An upstream outage or
limit is a hypothesis: old logs do not expose its cause. This task improves recovery and
observability without claiming to fix a measured provider-specific cause.

## Goal

Preserve all fetched snapshot rows, make one bounded attempt to recover missing pages,
and make remaining holes visible in the scheduled job after its data has been committed.

## Scope

In: pool-page recovery, safe fetch diagnostics, zero-row manifests, a final workflow
coverage check, deterministic acceptance tests.
Out: new providers, API keys, paid services, scheduling migration, cron changes, product
risk logic, benchmark re-baselining, historical backfills, permission-file edits.

## Files in scope

- bench/snapshot.py
- bench/fetcher.py
- .github/workflows/snapshot.yml
- Acceptance tests: tests/test_sellability_archive.py (extend the existing registered suite)
- Lead task/status records are maintained by the lead, not the executor.

Conflict search: the existing manifest test checks source shapes in collect(); keep its
failed-page/empty-page distinction and the initial two-miss stop. The workflow test checks
that pool commit precedes optional sellability and that sellability failure cannot discard
pool rows. Preserve these. Other fetch_json callers must keep the same return/cache contract.
No existing assertions may be weakened. No new test file requires CI registration.

## Acceptance criteria

1. The initial sweep uses at most one retry per page and a ten-second timeout per attempt
   so its request budget fits before the job's existing twenty-five-minute timeout.
   A failed page and pages skipped by the initial two-miss stop remain explicit gaps.
   After the initial sweep, retry missing pages once, prioritizing early new-pool pages.
   Limit recovery to at most twelve extra fetches and a ninety-second attempt budget;
   each recovery fetch has zero internal retries and a timeout bounded by the remaining
   budget, capped at ten seconds. Preserve confirmed listing ends and deduplicate pool rows.
2. Recovered rows are real fetched observables. Keep the existing pass timestamp grouping,
   expose actual fetch time for recovered rows, and record initial failure plus recovery
   outcome in the manifest. Remaining skipped/failed pages are never recorded as empty.
   Invalid payload shapes are failures, not exhausted listings.
3. Optional diagnostics on fetch_json report only bounded HTTP status/error categories and
   attempt count. They preserve existing return values, throttling, cache and provenance
   behavior. No credentials, URLs, payload bodies or arbitrary exception messages are logged.
   Snapshot reads and recovery never read or write the benchmark response cache.
4. Write fetched pool rows and the pass manifest before optional work. An all-zero pass writes
   its failure manifest and exits nonzero without manufacturing an empty pool file.
   Do not edit or rewrite existing archive rows.
5. A CLI coverage check for the last recorded pass exits zero only for a nonempty complete
   collection; remaining gaps, absent/malformed manifests or zero collected rows fail visibly.
   Print counts and causes without private information. Recovery can produce a complete pass.
6. The scheduled workflow commits collected pool/manifest data even when collection reports
   failure; it skips optional sellability when pool collection failed. Keep commits before
   optional work. A final coverage check runs after preservation, makes an incomplete pass
   fail the job, and also propagates a collection-step failure even if an older pass was healthy.
   Preserve the existing four daily schedule slots and push retry guards.
7. Acceptance tests exercise recovery, deduplication, skipped pages, budget/exhaustion,
   invalid payloads, diagnostics redaction, zero-row persistence, health CLI statuses and
   workflow preservation order. They use stubs/temporary directories, no network or waiting.
   Run the archive suite, relevant workflow guards and syntax checks.
8. Contract and checks: acceptance tests come first, alone, then implementation. Capture the
   red result and hashes before implementation. First commit must contain only acceptance
   tests before the task can be READY; no merge or push without the existing A1 Owner approval.
   Checks must pass or match a reproduced baseline. If the environment prevents commits or
   full-suite execution, prepare the authorized patch and test evidence, report the limitation,
   and do not claim READY, merged, deployed, or full-suite green.

## Evidence required

- Red/green acceptance output and test-file hash/immutability evidence.
- A captured replay recovering a failed page and one retaining a gap under the fixed budget.
- A zero-row pass manifest and failure exit; complete/partial CLI coverage examples.
- Workflow order/failure-propagation verification, diagnostics redaction verification.
- Patch plus relevant suite results; public live verification is required after a future push.

## Notes

Workstream protects live observables that cannot be recreated from today's state.
No new cash expense; stop at one recovery stage and one coverage-reporting stage, with at
most two review rounds. Do not add a scheduler or rebuild the collector.

Threat model: an outage must not discard successful data; a partial listing must not
masquerade as market inactivity; retries must not exhaust the job before preservation;
optional probe failure must not destroy pool rows; diagnostics must not leak secrets;
an old healthy manifest must not make a failed current collection green. Failures must
remain documented rather than changing a threshold to get a green job.

The earlier restricted environment reproduced Windows asyncio initialization and Git-write
failures, so source preparation stayed isolated. On 2026-10-11 the Owner restored execution
permissions; fresh-origin Git and real asyncio now work. Preserve the frozen tests and
chronological commits while completing the original release checks. Observe the scheduled
workflow on the published code as the post-publication completion check.

## Amendments

### (a) Enforce and test absolute HTTP attempt limits (2026-10-11, round 1)

Independent review reproduced a surviving mutant: replacing the fetcher's deadline branch
with unbounded throttling and the original timeout leaves all archive acceptance checks
green. Its separate real-fetcher probes detect the lost protections. Add acceptance tests
to tests/test_sellability_archive.py that call the real fetch_json with isolated clocks and
HTTP/socket stubs. Cover an already expired deadline, a throttle wait greater than the
remaining budget, and an HTTP timeout capped by the budget after throttling. Preserve all
previous inputs and assertions. Record this additive test change separately as
`T-020: named change (a) protect absolute HTTP attempt limits`.

Red-team M1 also reproduced a functional defect through the real urllib/http.client path:
socket inactivity timeouts permit indefinitely progressing reads. A twelve-byte body took
108 simulated seconds against the ninety-second recovery deadline; slowly arriving headers
took 522. The initial body probe took 2043 simulated seconds, exceeding the existing job
window before preservation. These are offline synthetic failures, not observed upstream
incidents. The lead reran the reproduction before accepting the finding.

For snapshot requests, enforce the existing ten-second limit over each whole HTTP attempt,
including headers and response bodies. Recovery also remains within its existing absolute
ninety-second budget, including throttle time. Slowly progressing input must not extend
either limit. Add deterministic real-stdlib-path header and body drip tests; an attempt cut
off by the limit is unavailable, with a bounded timeout/budget diagnostic, and its manifest
must retain the gap. Preserve successful rows and the zero-row manifest. Checking only
after urlopen/read returns is insufficient. A cancellation mechanism must not leave
unbounded workers, continued retries or cache/log writes after reporting a cutoff.

Keep ordinary fetch_json callers' cache, provenance, missing-record and retry contracts.
No new dependency, network call, real wait, fixture adjustment, recovery-limit increase or
CI guard relaxation is permitted. Keep the original frozen tests, red evidence and patch;
capture the additive tests red on the round-1 implementation before changing production
code. Round 2 reviews this bar and regressions in the amendment only. Git commits, full
checks and observed scheduled execution remain release requirements.
