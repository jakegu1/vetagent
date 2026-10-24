---
id: T-062
title: Preserve prospective sellability response availability clocks
status: ready
level: 3
size: M
depends_on: [T-061]
backlog: W7 preparation
---

## Context, benefit, cost and stop

T-061 correctly refuses sellability seen_at as a response clock: that value
comes from the earlier pool batch. The current collector has no later local
response-availability timestamp. Waiting longer will grow the archive without
repairing that prospective input gap. Historical response times cannot be
reconstructed. This task makes newly collected responses usable for a bounded
as-of availability inventory; it does not establish historical engine replay.

Benefit: preserve the availability time of responses already requested, without
extra Vendor traffic. Cost: a small additive collector record and matching
offline reader, three implementation/test files, independent functional and
adversarial reviews and the existing complete release gates. Stop after those
gates and an offline collector-to-writer-to-reader handoff. Do not expand into
new collection, labels, outcomes, scoring or monitoring. W7 remains open.

T-061 dependency source3316698 is accepted locally after combined second-round
12/12 and RED-TEAM:none, independent complete45/native0 and executor
complete45/native0. It remains unpublished pending the live-study boundary.
Use that exact reviewed dependency as this implementation base; do not import
the earlier5971f45 candidate or restart its completed review loop.
Publication must wait for qualified closure of the active frozen study: normal
publication CI emits Vendor requests. This draft authorizes no actual request,
pilot, canary, study observation, dispatch or production probe.

## Scope and conflict search

Implementation: bench/snapshot.py and bench/snapshot_readiness.py only.
Acceptance: additive functions before unchanged main in the already registered
tests/test_sellability_archive.py. Task/index/review metadata is handled by the
lead separately. No new workflow or runner step is needed.

Out: fetcher.py, its retry/throttle/cache/provenance behavior, scientific files
and their imports, all historical archive bytes, endpoint/parameters, selection,
order, call count/budget, outcomes, raw response fields, existing schema=2,
engine code, permissions, policies, labels, thresholds and public claims.

Conflict search on source3316698 covered all tests for probe_sellability,
_write_sellability, snapshot_readiness, seen_at, fetched_at, schema=2,
batch_time_only_rows, the clock reason and existing request/pacing seams.
Direct hits are in tests/test_sellability_archive.py; static runner/source
guards were also inspected. The existing batch-only fixtures contain no new
timing record, so their exact unknown/count/reason expectations remain valid.
Named changes to existing tests: NONE. Every existing test function, helper,
assertion, fixture and runner stays byte/AST exact; another old-test failure
means BLOCKED. Add no import to the frozen study or its import closure.

## Timing record contract

Keep top-level schema=2 and every prior field. Add one optional timing object:

    {"schema": "sellability-fetch-clock-v1", "scope": "fetch_json",
     "request_started_at": "aware UTC ISO",
     "operation_completed_at": "aware UTC ISO",
     "response_available_at": "aware UTC ISO or null",
     "elapsed_ns": "nonnegative integer or null", "status": "valid or invalid"}

The three clock fields are JSON strings or null, not the explanatory strings
above. Capture one local aware UTC wall clock and monotonic_ns at each side of
the existing fetch_json invocation. This is the whole fetch-operation envelope,
including its existing throttle/retries, not a wire-attempt or server timestamp.
For returned data and NOT_FOUND, response_available_at equals the completion
clock. For None/unreachable it is null, even when the operation clock is valid.
Keep outcome=no_record distinct from outcome=unreachable, answered unchanged.

Valid operation timing requires aware supported clocks, completion >= start,
nonnegative integer elapsed_ns <= 2**63-1 (bool excluded), and absolute wall
duration minus monotonic duration <= 1 second. That fixed engineering tolerance
detects material wall-clock steps; it is not a scientific threshold or proof of
UTC synchronization. Compare duration without lossy float normalization. A
clock read/format error, backward step, material forward step or invalid elapsed
value marks timing invalid and response_available_at null. Preserve the original
row/raw response and do not retry the request to obtain a better clock.

## Acceptance criteria

1. Prospective collection adds the versioned timing record around each existing
   fetch_json operation, including successful, NOT_FOUND and unreachable rows.
   Every pre-existing row field/value, schema=2, filtering, round-robin/order,
   attempt cap, URL, role and call kwargs stay exact. No extra request, sleep,
   retry, cache access/write or new endpoint is introduced. Return/existing
   write behavior is unchanged. Historical records are never edited/backfilled.
2. Clock anomalies fail closed only for timing. Test backward/forward steps,
   failed clock reads, naive/invalid clocks, invalid elapsed values and valid
   zero/positive latency. The raw response and outcome survive. The completion
   clock is conservative availability, never the batch clock/request start or
   a manufactured server timestamp. The reader repeats validity checks rather
   than trusting a row's status field alone.
3. The offline inventory admits new sellability timing only for the exact
   recognized schema/scope, valid ordered operation clocks/duration and an exact
   completion-equal response_available_at, with consistent existing outcome:
   ok/answered=true or no_record/answered=false. Apply T-061's precise aware
   timestamp grammar (one-to-six decimal digits, minute offsets); missing,
   unsupported, lossy, malformed, reordered or unreachable timing stays unknown.
   NOT_FOUND is dated observed absence, never a usable simulation. Legacy
   fetched_at/seen_at and filenames never substitute for the new record.
4. The as-of boundary uses response_available_at. Test old filename/batch/start
   with a future completed response, exact cutoff, one-microsecond future,
   offset-equivalent clocks and nonzero latency. Missing/invalid timing retains
   explicit unknown accounting. Legacy batch-only counts and the exact existing
   legacy reason remain unchanged. Conditionally report the existing missing-
   clock reason when no timing record exists, and a fixed new
   sellability_response_clock_unusable reason for present but unusable timing;
   do not assert a missing clock for a fully valid new-response-only fixture.
   replay_ready, independent_outcomes_established and
   full_engine_inputs_validated remain false in every case.
5. Test the real seam using a temporary OUT_DIR, deterministic local clocks and
   a fake fetch_json: probe_sellability -> _write_sellability -> actual NDJSON
   bytes -> inventory and real inventory CLI. Include success, NOT_FOUND,
   unreachable, legacy and invalid-clock responses. Assert exact prior-field
   projection, all rows preserved, source SHA256/bytes unchanged by inventory,
   unchanged call kwargs/order/count and no actual network. Exercise the real
   fetcher/throttle/retry seam with fake HTTP/clock only if needed to prove the
   added clock reads do not alter the existing request sequence or pacing.
6. Preserve T-061's bounds, source-mutation/symlink defenses, aggregate output
   schema and no-network/import contract. No raw identity, token, URL, row key,
   path or exception text may enter diagnostics/CLI output. With sentinel input,
   malformed timing and unknown nested keys, output stays fixed and redacted.
   Independently reproduce a start-clock/future-response mutant and a privacy
   mutant going red, then restore exact working bytes without stale bytecode.
7. Contract and checks: first commit adds only acceptance/characterization tests
   in the existing test file and proves a meaningful old-source red; then the
   minimal source fix. Fresh independent functional and focused adversarial
   review must approve exact final source with no material finding. Run focused
   tests, syntax and the actual complete45-command runner, serializing heavy
   Windows runs. Before publication verify every frozen scientific file/import
   and retained raw archive blob/prefix. After qualified study closure, integrate
   normally, regenerate in explicit regenerate mode, verify exact-head Linux
   and both locked builds, complete master CI/read-back and source-bound receipts.

## Threat model and READY evidence

Ordinary failures: early batch/start clocks admit future responses; retry-boundary
clocks are misrepresented as wire timestamps; wall-clock jumps appear ordered;
unreachable becomes a dated observed absence; a new clock drops raw fields/rows;
a compatibility fix changes selection or request pacing; raw timing diagnostics
leak identities; deployment CI contaminates a frozen live study.

Provide tests-only/fix SHAs, preserved original red and final focused/full green,
old-test byte/AST proof, fake-network call/pacing witnesses, real write-to-reader
handoff evidence, exact final source hashes, independent review verdicts,
mutation/restoration witnesses and complete source-bound release receipts.
All real archive/operational readings remain private. If the three-file scope
cannot meet a criterion, stop and ask the lead for a named amendment; never
quietly add fetcher instrumentation, relax timing, drop a field or weaken a gate.
