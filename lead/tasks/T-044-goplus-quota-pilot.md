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
