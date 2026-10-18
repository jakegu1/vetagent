---
id: T-044
title: Make the held-out GoPlus quota pilot bounded, observable and executable
status: ready
level: 3
size: M
backlog: W40 prerequisite only
design_base: 0f4ac27389b522225b80d888dd1cf25787e3a4b3
---

## Goal, benefit, cost and stop rule

Make one existing-source quota/throughput measurement executable without rebuilding the
benchmark or feeding GoPlus into production. Preserve every attempted, refused and
unobserved cell, using a fixed queue and a hard ceiling of 316 single-contract requests.
This replaces the vague next action in W40 with a runnable instrument, not a new study
framework. The Experiment C publication dependency is already met; it is not a new
approval gate.

One run is limited to one UTC date and thirty elapsed minutes, whichever ends first.
Stop at 316 claimed attempts, the first HTTP authentication/permission refusal
(401 or 403), the time/day bound, source/plan mismatch, persistence
failure or interruption. Do not retry, resume live work, refill the queue, cross into
another UTC date or run another pilot automatically. Missing observations stay missing.
Implementation and ordinary read-only use of this existing endpoint are within current
authorization. No extra Owner confirmation is required for those routine actions.

## Existing code and the narrow gap

`bench/build_dataset.py::label_one` already calls
`https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={address}`
using `labels.GOPLUS_CHAIN_ID` and `labels.goplus_label`. It also requests GeckoTerminal
OHLCV, uses the default cached/retried transport and participates in dataset generation;
it must not be invoked as this pilot. `bench/second_oracle.py` is Quick Intel, not GoPlus.
Its overwrite refusal and incremental-save pattern are examples, not another provider
to call. `fetcher.fetch_json` has diagnostics but defaults to retries and cache writes
and does not preserve raw HTTP-error bodies; leave it unchanged.

Source/workflow searches find no W40/316/one-day/T+24h dedicated executor. The existing
chain mapping and label function are reusable; quota accounting and safe receipts are
the missing seam.

## Scope and conflicts

Exactly two implementation files, disjoint from T043:

1. New `bench/goplus_quota_probe.py`: a small plan/run/report CLI and its bounded native
   HTTP adapter. Use only the existing endpoint, stdlib and labels module.
2. `tests/test_second_oracle.py`: append exactly seven named offline acceptance
   functions before main, with helpers/imports inside those functions. Its existing
   dynamic runner and network/sleep/disk/time contract already cover bounded oracle
   measurements and remain byte-exact. Commit only the additions first and show the
   real missing-tool red. All old top-level statements, functions and AST stay exact.

No existing test assertion or fixture change is authorized. The new module name has
no current matches. Existing label/replay tests are in
`tests/test_benchmark_replay.py`, `tests/test_dataset_replayable.py` and
`tests/test_second_oracle.py`; their behavior stays frozen. The existing unconditional
CI invocation of that runner must execute all seven new functions. Preserve its
under-five-seconds and no-network/no-real-sleep/no-bench-writes contract; do not weaken
the bound to accommodate the additions. Large synthetic cap tests can use an in-memory
receipt sink while small real-file CLI cases verify persistence seams. No workflow or
registration changes are part of this task. This removes the shared-file conflict with
T043 and permits bounded parallel implementation in separate worktrees.

Out of scope: `src/`, `labels.py`, `fetcher.py`, `build_dataset.py`, current benchmark
dataset/results/cache/access log, the 17-record unsafe cohort, public numbers, build
performance bars, legal/privacy text, new sources/keys/packages/paid plans, a recurring
job, 24-hour monitoring, a 30-day collector, or any new label decision.

## Acceptance criteria

1. **Offline frozen plan.** Default invocation and `plan` make no network request.
   From a declared local copy of the current tracked dataset, validate bytes against its
   declared source commit/blob SHA. In original dataset order, take the first 316 unique
   supported `(chain, address)` rows, validating EVM addresses and using the existing
   `GOPLUS_CHAIN_ID`. Do not select by label, verdict or fresh response. Record dataset
   SHA, source commit, label-code SHA, original array indices, queue SHA and exclusions.
   Fewer than 316 valid unique rows, duplicate/invalid indices, changed source, reordered
   plan, unknown chains or more than 316 entries refuse before calls. Public plans contain
   only source identifiers/SHAs and indices; addresses are resolved in memory. This old
   dataset is a fixed quota workload, not a representative T+24h cohort.

2. **Hard request and wall bounds.** Only explicit `run --plan ... --output ...` can
   call GoPlus. One process owns a newly created run directory/claim; existing output or
   a concurrent claim is refused. Sequentially make at most one GET per planned index,
   one contract per request, at least 2.1 seconds between request starts, no retries,
   no batching, no redirect following and a thirty-second request deadline. Count a
   durable intent before opening transport; an uncertain interrupted intent consumes
   its attempt and remains unobserved. Do not start a call unless its pacing and full
   timeout fit both the thirty-minute run deadline and the chosen UTC date. An actual
   HTTP 401 or 403 stops further calls and remains a measured refusal; it does not
   determine unused contracts' status. Remaining
   indices are not_asked with a fixed reason. Do not call GeckoTerminal, the production
   service, `assess`, a benchmark runner or any paid/authentication path.

3. **Observation stages stay separate.** Retain scheduled/actual request/response UTC
   times, monotonic duration, HTTP status, JSON/envelope state, requested-result-match
   state and finite field-readability states. Distinguish 429, other HTTP failures,
   transport/timeout, empty body, malformed JSON, oversized body, missing result and a
   matching nonempty result. Cap a response at 256 KiB plus a one-byte overflow check.
   Hash captured bytes and explicitly flag truncated versus complete content. Never
   let HTTP 200, an API error envelope or a different contract's entry imply a valid
   label. Validate the exact requested result key before calling `goplus_label`, whose
   legacy first-entry fallback must not be used here. Record a bounded numeric API code
   if available and fixed schema/error categories, never arbitrary messages. Keep the
   label function's returned/null/error status separate from transport and field
   availability. Pass only finite existing `outcome_facts.recent_volume_7d`, otherwise
   `None`; no invented volume and no change to existing honeypot/label thresholds.
   Do not call a missing tax/holder field zero or a null label safe.

4. **Privacy-limited outputs.** Console and the CI-uploadable report contain only
   declared source/dataset/queue hashes and indices, actual times, fixed states/counts,
   HTTP/API numeric statuses, body hashes and bounded field-validity booleans/enums.
   No addresses, URLs, full GoPlus bodies, free upstream text, raw exceptions, account
   or credential information. Cap the complete safe report/receipts bundle at one MiB.
   A local explicit `--private-raw-dir` outside all Git worktrees may retain raw bounded
   bodies named by queue index and their manifests; no encryption framework. Refuse
   that option before calls on CI. Default use works without raw retention. Any later
   CI artifact upload selects only the safe report bundle; do not add a live workflow
   or artifact upload to the ordinary offline test job in this task.

5. **Partial evidence survives.** Save the immutable plan and append/persist each
   intent before transport; atomically update receipt/report after each response.
   Persistence failure stops further calls. An interrupted output is readout-only:
   `report` reconstructs attempted/not_asked/unobserved counts without network and never
   retries an uncertain slot. Re-running `run` against that output refuses. Preserve
   prior bytes and state hashes. A run which stopped early or has unavailable label
   observations returns a non-success observation conclusion while keeping its report;
   429 is a measured refusal and is counted, never hidden by a later retry. A successful
   process or completed request count alone must never be described as a usable oracle
   quota, a negative finding, full indexing or stable uptime.

6. **Truthful readout and cost.** State requested/claimed/attempted/completed HTTP
   counts, each 429/error/unobserved/not_asked denominator, matching-result and finite
   field coverage, label-function availability, first/last observation and actual elapsed
   time. Do not calculate demand, new unsafe yield or a new benchmark label. Say this
   measures this egress's single-date paced request behavior on the fixed old-token
   workload. It does not establish a daily reset, a remaining account-wide allowance,
   continuous 24-hour availability, fresh T+24h indexing, a 30-day success rate or the
   W40 eighteen-token target. A short run must print its actual minutes, never "24h
   observed". Report unsent cells and concurrent same-egress/account usage as unknown.

7. **Tests first and complete contract.** Append only these named acceptance functions:
   test_goplus_quota_plan_is_offline_fixed_and_source_bound,
   test_goplus_quota_run_caps_pacing_and_utc_bounds,
   test_goplus_quota_http_and_exact_result_stages,
   test_goplus_quota_safe_output_and_private_raw,
   test_goplus_quota_partial_intents_and_persistence,
   test_goplus_quota_readout_denominators_and_limits,
   test_goplus_quota_cli_and_existing_runner_contract.
   Fake-clock/fake-transport tests exercise
   the real CLI and transport seams: 316/317 cap; source/hash mismatch; default offline;
   duplicate/concurrent start; 429 without retry; HTTP-200 error/missing/wrong-result
   envelopes; malformed/nonfinite/missing fields; timeout/oversize; UTC-day/deadline
   stop; intent-only interruption; failed output persistence; public-output sentinels;
   explicit local raw retention and CI raw refusal. Freeze acceptance after its first
   commit. At most three scratch mutants: cap bypass, failed cell treated as observed,
   and raw body leaked into safe output. Keep all old source/test bytes unchanged
   apart from the seven named additive functions. Run the actual containing runner and
   then one ordinary configured full inventory only in a root-granted GLOBAL slot.
   Preserve exact source/red/green/command/log hashes. Fresh independent and adversarial
   source reviews precede root's actual pilot; no test invokes a real vendor.

## Cost and READY evidence

Offline plan/report/tests: zero vendor calls. One explicit live run: at most 316 GoPlus
HTTP attempts, zero retries and zero other vendor/control-plane requests from this CLI.
At 2.1-second start spacing, 315 gaps total 661.5 seconds before response overhead;
this is approximately eleven minutes of pacing, not one day. The thirty-minute/day
deadline can reduce the count and must remain visible. Private raw upper bound is
316 * 256 KiB = 79 MiB plus small manifests; default safe output is at most one MiB.
These are code ceilings, not verified provider pricing, free allowance or CI capacity.

READY contains the exact tests-first red, scope/old-byte freeze, synthetic transport
and actual CLI receipts, caps/privacy mutants, complete configured inventory and
sanitized output example. Runtime pilot receipts are a separate root-owned observation,
not something a green synthetic test can supply. Root may run the bounded existing-
source read after reviewed integration under current authorization. It needs no new
Owner wait. If a new paid tier/source/legal change is needed, stop that expansion and
report it separately rather than assuming permission.

## Threat model

Realistic faults are inherited retries/cache hits inflating or suppressing quota counts,
redirects or stdout leaking request identities, HTTP-200 error bodies counted as data,
the labeler's first-entry fallback assigning another contract, interruption losing the
only receipt, and a short burst relabeled as a whole-day/30-day result. The fixed queue,
intent ledger, caps, stage states and safe output boundary must fail visibly on those
cases. No production upstream, label policy, bar or published number changes.

## Pre-test clarification

2026-10-19 (a): the lead places the acceptance functions in the existing dynamically
discovered oracle-measurement runner, preserving all its original bytes and timing
contract. Implementation files are disjoint from T043; no workflow registration is
changed. This is a test-placement choice made before the first acceptance commit,
not a frozen-test edit. Also stop after the first HTTP 401/403 rather than spending
the remaining workload on a known permission refusal; report every unasked index.

2026-10-19 (b), named mechanical acceptance-helper correction: the added source-freeze
helper splits on a main-declaration string which appears inside the helper itself.
The lead independently reproduces its unterminated-string AST red and proves the
two delimiter spellings with surrounding newline characters preserve the actual old
prefix/main bytes and expose exactly the same seven added functions. After the first
acceptance commit, permit only those two split-argument changes in a separate named
test-only commit. No assertion, test input, coverage, timing rule or implementation
workaround changes; every old statement and all other acceptance bytes remain frozen.

2026-10-19 (c), named additive regression pins before READY: three executor scratch
reds expose raw-directory nesting inside the safe output, a torn final receipt, and
an HTTP permission header whose body then times out. Their private red probes precede
the respective source repairs, but ordinary CI must retain these exact combinations.
Permit only one new self-contained check block, with nested helpers/imports, inside
each corresponding existing added acceptance function: safe_output_and_private_raw,
partial_intents_and_persistence, and http_and_exact_result_stages. Keep every previous
statement/assertion in these functions in the same order, every other function exact,
the seven-function set, original module/main bytes and timing/network/disk contracts.
Commit these additive pins alone, reproduce each against its named pre-fix module
in a controlled isolated/in-memory overlay, then verify the corrected source. Do not
rewrite the existing repair history or describe retrospective CI pins as earlier
commits. No implementation changes are authorized by this amendment. The native
permission/body-timeout case must show one attempted request, the retained permission
status, distinct unobserved body, and all remaining indices unasked; no retry.

2026-10-19 (d), named native transport-boundary correction before READY: the lead
reproduces two further source defects on 7dd2e83. A response with an observed HTTP
403 followed by native http.client.IncompleteRead loses its known header through
the outer generic transport handler. A native urllib byte-trickle response exceeds
the total timeout even though every socket read finishes within that timeout; a
scaled 0.12-second private local-server probe finishes after 0.435 seconds. This is
an instrument correctness finding, not a provider availability measurement.

Permit one further additive nested check block in each of these two existing added
acceptance functions: http_and_exact_result_stages, and run_caps_pacing_and_utc_bounds.
Preserve every earlier statement/assertion in order, every other function exact,
the seven-function set and all original module/main and offline/time contracts.
Commit the additions alone before the narrow implementation repairs. The first
must exercise a standard HTTPException during body reading after an observed
permission header, retaining that header, one consumed attempt, an unavailable body
and 315 unasked cells. Interruption must still propagate to the run's interruption
handler rather than becoming an ordinary transport retry. The second must exercise
the actual total-deadline supervisor seam with fake process/clock/transport controls,
proving expiry stops the in-flight native request and does not create background
requests, overlapping calls, retries, raw-output leakage or unbounded cleanup.
Keep the thirty-second configured limit and all other request/day/run ceilings.

The implementation may add small stdlib helpers inside the existing new module.
Use an interruptible bounded native transport boundary, such as a supervised worker
process with bounded private pipes, if needed to enforce an absolute deadline over
connection, headers and body. Header evidence received before body failure/deadline
must survive. No new source, dependency, CLI live bypass, public raw channel, daemon,
permission or file is authorized. Do not describe a per-socket timeout as an enforced
total deadline, or leave an in-flight background request running while starting
another one. Default and all ordinary tests remain offline. Root will independently
repeat the bounded native local transport seam after repair, before any real pilot.
Retain the earlier green 42-step candidate's evidence as held, not READY. Freeze the
repaired head, reproduce the added reds, run focused checks, then request a new
exclusive full slot and fresh independent plus adversarial reviews.

2026-10-19 (e), named first-review corrections: independent review of b7133b7
requires changes (seven of twelve); adversarial review reproduces three material
classes despite the actual forty-two-step inventory and native deadline checks
passing. Keep that source held. Apply one bounded second implementation/review round.
Do not change the queue, caps, source, label rule, old assertions or scientific bar.

Add exactly one self-contained nested regression block at the end of each of these
three existing added acceptance functions, retaining all prior statements/assertions
and their order, every other function exact and the original seven-function set.
Commit the three additions alone before the repairs; then separate fix commits per
finding, with each specific assertion's native parent-red evidence retained.

1. run_caps_pacing_and_utc_bounds: exercise real run_plan and durable FileSink seams
   with fake-clock latency during intent persistence and pacing sleep. Actual transport
   invocation starts must remain at least 2.1 seconds apart. Capture actual invocation
   time immediately before transport, distinguishing it from the earlier durable
   intent time; persisted evidence must not mislabel an intent timestamp as actual
   transport time. Recheck the chosen UTC date, remaining absolute timeout/cleanup
   allowance and thirty-minute budget after every blocking persistence/pacing step
   before opening transport. Cover both forward and backward wall-date changes and
   exact run/day edges. A durable intent whose request cannot begin must remain an
   explicit consumed/unopened or uncertain cell, with truthful denominators and no
   live retry. Do not open a request after its available day/run budget became too
   short while persisting its intent. No silent extra requests or source changes.
2. partial_intents_and_persistence: a real FileSink subclass flushes a prefix of the
   second receipt and then raises OSError. Continue through real run_plan return and
   the actual offline CLI report against the exact remaining bytes. It must recover
   the preceding complete HTTP 429 and both durable claims, explicitly retaining the
   second missing/uncertain response and remaining unasked cells. Do not append a
   stop record onto a torn JSON fragment, erase partial evidence, skip arbitrary
   corrupt interior records or report a completed/available pilot. Earlier complete
   receipts and the original torn bytes remain auditable, with no replay or network.
3. http_and_exact_result_stages: a bounded deeply nested JSON response triggers the
   native decoder's recursion limit within the existing response byte cap. Through
   real classify/run/CLI/report, retain a known HTTP 403 as a refusal, report malformed/
   unavailable body state, consume one claim and leave 315 unasked with no retry.
   No uncaught RecursionError, raw exception, traceback, local path or body sentinel
   may reach console/error output. Include an ordinary HTTP-200 malformed-body
   control; it does not become an API/label observation. Preserve the fixed source
   HTTP/body/result/label stages and the child output/privacy boundary.

The repair stays in the existing new module. No acceptance weakening, provider,
package, workflow, public raw channel, benchmark/cache write or live call is allowed.
Retain all earlier native-deadline and header/body evidence with original source IDs;
do not rebind prior green logs to the repaired head. Re-run focused/CLI/contract checks,
request one exclusive actual full inventory on the new frozen head, and send that
head to one fresh combined second reviewer under the two-round cap. Root then performs
the actual Linux/integrated gates before its sole live pilot. Known failure evidence
is not a provider-capacity measurement and does not veto the project.

## Named partial-readout correction

2026-10-19 (e2): while sealing the corrected source's actual partial-append CLI
evidence, the executor reproduced a numeric-integrity regression in the same
failure-finalization class (e). Two durable claims include actual fake transport
starts at 0 and 2.1 seconds, but both the immediate failure return and standalone
CLI readout report elapsed_seconds=0, elapsed_minutes=0 and ended_at=null. A
last completed receipt cannot establish a terminal time after an interrupted
claim. Hold 49abae7a5d503f7775ad8bab1f4ffb0b18f70e25; keep its actual full result
as held-source evidence, without rebinding it to a repair.

Permit one additional self-contained regression block at the end of the existing
(e) nested partial-persistence block in
test_goplus_quota_pilot_preserves_partial_intents_and_persistence. Preserve all
earlier statements, order, assertions, other functions and the seven-function
runner contract. Exercise both immediate failure return and real standalone CLI
report against the same torn ledger. With no valid terminal event, elapsed_seconds
and elapsed_minutes are null/unobserved; started_at and independently known claim,
HTTP and request clocks remain observed. Do not invent an end or add a new
lower-bound metric. Prior 429, two claims, one uncertain attempt and remaining
not_asked counts, original torn bytes and refusal to append through corruption
must remain exact. Completed valid-terminal positive controls keep their actual
numeric elapsed durations.

Commit this regression alone with a meaningful red on the held source, then a
separate same-finding fix. Preserve the earlier sealed proof sets and full log;
record the authorized contract addition mechanically. Source changes require a
new focused pass and one new exact-head globally exclusive full slot before
READY. The fresh combined second review must close (e2) with (c), (d) and (e).
This is evidence correction within the existing repair round, with no policy,
provider, queue, request allowance, deadline or study-calendar change.
