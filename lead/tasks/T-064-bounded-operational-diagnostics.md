---
id: T-064
title: Preserve bounded diagnostics from existing collector attempts in result manifests
status: in_progress
level: 3
size: M
depends_on: [T-061, T-062, T-063]
backlog: W7 operational evidence diagnosis
---

## Context and root acceptance

The current independent study has qualified operational closure: its original
report, complete original preservation, frozen-source reconstruction and owned
workflow stop have been independently verified from local original evidence.
Its scientific result remains inconclusive. All executed historical sources,
protocols, windows, original evidence and conclusions remain immutable.

The lead accepts the independently reviewed private design after resolving its
closure dependency. The sealed draft and design review remain unchanged outside
the shared tree. This public task adopts their complete operational contract.
Design source was38ea876; the dispatch parent reconciles todbc34d0. Every scoped
runtime/test file, workflow, runner and conflict-census input remains byte-exact
in both LF-canonical and checked-out raw form. Companion source fingerprints and
old test-function census remain external evidence for this contract.

This task protects diagnosis of future existing attempts. It cannot recover old
missing400 bodies, native exits or budget decisions. Cost is oneM task plus fresh
functional/adversarial review and the related batch's complete gates. Stop HELD
if the implementation requires a new persistence framework, raised cap, discarded
scientific bytes, rewritten historical binding or larger scope. A split requires
lead preregistration before dependent work and never permits partial publication.

## Goal

An ordinary future collector operation can retain fixed, anonymous counts of its
actual attempts and original budget decisions in its existing result manifest,
including after normal finalize and restore. Missing diagnostics remain visibly
unrecorded. Scientific observations, readout, protocol and operation traces retain
their original behavior.

## Scope

**In:** minimal optional diagnostic capture inside the existing curl; a transient
per-operation accumulator; result-manifest validation and bounded attachment;
normal finalize, interruption, terminal closure and admission binding; fixed
diagnostic status in existing receipts and summary; additive tests; named P below.

**Out:** state/intent/scientific-row diagnostic members; new output filenames or
Artifact types; raw response/error/stderr/message/traceback storage, body hashes,
addresses, identities, labels, token ordinals, per-token or per-attempt retained
arrays; new source/provider, retry, request, pilot, study or probe; changing original
HTTP/report eligibility or T058; source/lease/clock-refusal instrumentation beyond
what is explicitly covered below; schedule, protocol, caps, gates, scientific
conclusions, production engine, workflow or generator changes; old evidence edits
or backfill. Ordinary authorized CI is a later release gate, not a diagnostic run
to launch during this task.

## Files in scope

Runtime changes are limited to:

- `bench/rugcheck_coverage_probe.py`
- `bench/rugcheck_w57_ci.py`
- `bench/rugcheck_w57_session.py`

Acceptance tests are additive blocks in the already registered files:

- `tests/test_rugcheck_coverage_probe.py`
- `tests/test_rugcheck_w57_ci.py`

No new test file or runner step is required. Root owns later task/index/STATE
administration. No existing fixture, workflow, generator, T058 test or assertion
may change except the following precisely preregistered compatibility change.

**Named change P:** in
`RunningSessionTests.test_source_freeze_covers_every_executed_control_and_legacy_bytes`,
replace only the fixed expected **current probe LF-canonical SHA literal** at
current line 1194, presently
`3734d9c3b51114a90c7512ee77c6d90754e205a14085bbf22eee012acb4fbc21`.
The replacement is unknown until the minimal final probe implementation is
root-reviewed and independently hashed. Commit the reviewed resulting fixed
literal; never compute it from the implementation at test runtime. The legacy
protocol fixture assertion, five-actual-files `source_freeze` equality, source and
composite guards, and every other old statement remain byte-exact. Actual old
probe/archive hashes remain historical evidence and are not rewritten. This is
source contract renewal after qualified closure, not a protocol or gate change.

## Exact transport and collection contract

1. Keep `curl(url)` and its default return `(original_code, original_body_or_None)`.
   Keep the same single original `subprocess.run`, argv, timeout, exception classes,
   decode behavior and return semantics. Do not intercept/proxy subprocess, retry,
   re-fetch, or parse a second body. `observe` and scientific `_row` output do not
   gain diagnostic fields.
2. Add one private optional transient hook:
   `probe._ATTEMPT_DIAGNOSTIC = None`, or `(source, callback)`, where source is only
   `rugcheck` or `geckoterminal`. Driver code binds and restores its prior value in
   `finally` around exactly one existing transport call, in the existing sequential
   wrapper pattern. No cross-operation global counter/history exists. The curl
   invokes the callback once with a newly constructed, fixed-key safe record
   `{http_status, native_exit, reason, usable_body}`. Here HTTP/native are the fixed
   buckets below, never arbitrary native/HTTP strings. No body or exception text
   crosses this new hook. An unexpected internal diagnostic failure must not issue
   another request or replace the original transport result; the operation's
   aggregate becomes unrecorded rather than claiming full capture.
3. Add keyword-only `diagnostics=None` to core/session `collect` and the existing
   result serializer/writer APIs as necessary. Legacy defaults and return shapes
   remain unchanged. A provided caller-owned dict is replaced for this operation,
   not accumulated. Session's ordinary live/live192 CLI creates a fresh transient
   accumulator and passes it through its existing collection/writer path. Canary,
   prepare, report and the legacy core CLI do not manufacture recorded diagnostics.
4. Existing injected `curl(url)` transports remain callable without new keywords.
   If such a transport returns a legacy tuple without invoking the hook, native
   evidence is `unavailable`; a well-formed returned code/body may classify a fixed
   safe HTTP/body reason from those available inputs, but cannot establish native
   zero. Its diagnostic `usable_body` is false without native-zero evidence.
   When parse status cannot be established (notably returned `None`), use
   `unclassified`, not an invented malformed/empty distinction. This fallback is
   explicitly diagnostic incompleteness and cannot change scientific eligibility.
5. Reason behavior with actual native/parse evidence is exactly T058
   `_attempt_reason` for the two applicable sources, including precedence:
   native failure; HTTP429; exact rugcheck HTTP400 `Token not found`; non-200 or
   rejected body; malformed parse; empty body; object/list success. The nested
   `status.error_code` predicate is **is not None**, including false, zero, empty
   string/list/object. Do not import the live test module or production risk engine
   into the collector. Copy only the small fixed semantic predicate; add differential
   tests against an isolated pure T058 classifier. T058's own four-key attempt schema,
   purposes, retries, sleeps and source coverage remain byte-exact.
6. A diagnostic `usable_body` follows that transport/body contract. It does not
   assert a scientific report's fields exist. In particular, old HTTP200 error-body
   scientific behavior stays characterized and unchanged even if diagnostics call
   the same document rejected. This task changes no verdict or scientific readout.

## Exact manifest schema and bounds

Only `manifest["operational_diagnostics"]` may hold the aggregate. It is optional,
allowed only for an actual result manifest in live/live192, including the existing
admission-result envelope when it must reproduce an already pinned result. It is
forbidden on intents, state, scientific rows and canary. No new independent digest
is added. The complete compact UTF-8 encoded **object** is at most 2048 bytes,
using existing `encoded` formatting; the JSON member overhead also counts toward
all original outer limits.

Every object has exactly these keys (unknown/missing keys, bool-as-int, negatives,
NaN/Infinity, wrong enum, and inconsistent totals are invalid on write and read):

```text
version: exact integer 1
operation: "pilot" | "start" | "tick"
status: "recorded"
sources: exactly rugcheck and geckoterminal, each containing exactly:
  opportunities, attempted, not_attempted, usable_body: nonnegative integers
  http: exactly "200", "400", "429", "other_http", "no_http" integer counters
  reason: exactly ok, token_not_found, vendor_rejected, rate_limited,
          transport_failed, malformed_body, empty_body, unclassified counters
  native_exit: exactly "0", "6", "7", "23", "28", "35", "52", "56", "60",
               other_nonzero, unavailable integer counters
budget: exactly:
  checks, allowed, refused, timing_samples, timing_unavailable: integer counters
  required_ms: exact integer 32000
  first_remaining_ms, minimum_remaining_ms, last_remaining_ms: integer or null
  limiting_deadline: exactly phase_deadline, study_end, equal integer counters
vendor_call_ceiling: integer 0 or 1
```

Per-source `opportunities = attempted + not_attempted` counts report/listing
function entries actually reached in this operation, not hypothetical cohort cells.
An attempt means entering its existing curl call, including a spawn failure.
Each HTTP/reason/native counter family sums to that source's attempted count.
`usable_body <= reason.ok`, and usable-body evidence also requires native bucket 0
and HTTP200. With actual complete evidence usable-body equals reason.ok; injected
legacy fallback can have a safe reason without establishing native success.
Every observed nonzero native bucket is transport_failed. `unavailable` never
becomes zero. No classification equates a refused/unasked request with an attempt.

Operation maxima are source-derived, not scientific threshold changes:

| Operation | RugCheck opportunities | GeckoTerminal opportunities | completed room decisions |
|---|---:|---:|---:|
| pilot | 6 | 1 | 7 |
| start | 240 | 8 | 496 |
| tick | 63 | 0 | 63 |

Start has at most 8 pages, 30 candidate reports/page, one post-candidate room check
and one post-page room check: `8 + 240 + 240 + 8 = 496`. Short circuits can reduce
that number. All related counters are bounded by their applicable maximum.

`budget.checks = allowed + refused` counts completed evaluations of the **original**
`room()` expression, including recruitment loop checks. It is not a count of
unattempted tokens. Increment refusal only when that original comparison returns
false; use its already-read clock value. No extra clock read is permitted.
`vendor_call_ceiling` counts the original core `vendor_room` rejection only when
that exact guard establishes it, after which collection stops. Session preflight
lease/source/clock/ceiling failures retain their original fixed error path and are
`not_recorded` if no complete operation aggregate was committed. Do not infer a
guard cause from collection_unavailable or surviving rows.

For each completed room refusal, choose the limiting deadline from the original
phase deadline and, for tick only, `state.ends_at + acquisition_grace`. Equal values
use equal; non-tick uses phase_deadline. `study_end` names that effective acquisition
bound, including the unchanged legacy grace. Deadline counts sum to refused.
Remaining milliseconds are `floor((effective_deadline - original_guard_value)*1000)`
only when both operands/result are finite built-in int/float (not bool) and the
result is within signed 32-bit integer range. Do not clip or serialize an arbitrary
large number. Otherwise count timing_unavailable and record no timing value.
`timing_samples + timing_unavailable = refused`. The first/minimum/last fields
cover those representable refused decisions in their original order; all three
are null exactly when timing_samples is zero. If non-null, minimum is no larger
than first or last. No absolute timestamp or extra clock, sleep or guard occurs.

The conservative field-width witness is 1287 bytes, below 2048. It deliberately
uses maximum-width counters simultaneously even where invariants make that exact
object unreachable. It proves schema width only, not implementation or runtime
reachability. Original state 64-KiB, intent 64-KiB, row 2048-B, result/ZIP 1-MiB,
read limits, source hashes and scientific row projection remain authoritative.

## Persistence, fallback and missing evidence

The existing manifest digest, transport.core_digest, uploaded ZIP digest and
durable reference digest retain their original meanings. Recompute through the
existing constructors after attaching the validated aggregate; do not weaken a
reference check to make a modified manifest fit an old pin.

Construct/validate the original scientific files first. If those were invalid or
over limit before diagnostics, preserve the original failure. Only then try bounded
attachment and the original expanded/ZIP bounds. If a previously valid scientific
result plus its unverified salvage tail has no room for the aggregate, emit the
**exact original valid scientific bundle without the aggregate**. No row/tail
truncation, cap increase, altered scientific state or invented zero counts is allowed.

Persist only fixed `diagnostics_status` in the existing `collection.json` receipt
for that fallback, preserving its existing fields. Finish copies that fixed status
to existing `receipt.json` beside its unchanged pin/artifact-budget fields and into
the existing allowlisted summary. Never place the aggregate there. Valid statuses:
`recorded`, `not_recorded`, `diagnostics_not_recorded_capacity`. The capacity status
may be written only by the exact candidate-overflow fallback. Existing collection
receipt is small; require a bounded read, exact status allowlist, atomic preservation
of existing fields, and a readback test across process boundaries. A failed/unsafe
status write keeps scientific evidence preserved but makes this task HELD. Do not
create a new status file/framework to resolve it.

Normal core/session finalize must retain and revalidate a valid aggregate when
rebuilding its manifest. Recovery that salvages only scientific rows and cannot
validate the original complete aggregate must omit it and say not_recorded;
never infer complete diagnostics from rows, old state or a previous operation.
Missing legacy/interrupted member means not_recorded, never recorded-zero or
complete. A later operation replaces its transient aggregate and never inherits
counts. No attempt is made to recover an old 400 document or native exit.

Terminal closure that republishes an existing terminal result retains that same
operation's manifest member. Its existing local result manifest is the only place
the aggregate is carried into close-index/admission-result: read and validate it
there; do not add it to closure.json, state, plan or intent. A rescue-created result
has no new observation aggregate and is not_recorded. Retaining an already pinned
terminal manifest is mandatory: if admission cannot reproduce its exact digest
within the unchanged limits, HELD rather than dropping the member, altering the pin
or creating a parallel evidence route. Summaries expose only the fixed status and
their existing durable reference, never an unbounded diagnostic object/history.

## Acceptance criteria

1. **Same original attempt, safe transport facts.** Add
   `CoverageProbeContract.test_t064_original_curl_emits_one_safe_attempt_without_changing_legacy_tuple`:
   synthetic native-zero known/unknown400, 429, malformed/empty200; exits28/23 with
   otherwise parseable200; OSError and SubprocessError. Each invokes exactly one
   original fake subprocess with exact argv and returns the original tuple. The
   optional safe hook has exactly the fixed keys/buckets, cannot make a native
   failure usable, and is restored on every path. Current parent red is absent
   diagnostic capture, not a missing import or deliberate syntax failure.
2. **Reason/privacy contract.** Add
   `CoverageProbeContract.test_t064_safe_reasons_match_t058_without_changing_scientific_observations`:
   differential pure T058 cases, every falsey nested non-null error, huge/unfamiliar
   and credential/URL/address-like synthetic strings, malformed native types,
   and original HTTP200 error-body scientific behavior. Add
   `StudyTests.test_t064_legacy_injected_transport_has_explicit_missing_native_evidence`:
   old vendor(url) callbacks still work; absent native/parse evidence is visible;
   no stderr, message, body, hash or identity reaches manifest/receipts/summary.
3. **Actual guards, no extra time/read/request.** Add
   `StudyTests.test_t064_budget_counts_reuse_original_decisions_and_do_not_change_traces`:
   original 31/32-second boundary, phase/study/equal limiter, slow30-second calls,
   recruitment loop decisions, exact core vendor-ceiling rejection, nonrepresentable
   timing and original clock failure. Same enabled/disabled fake executions have
   identical ordered request argv, count, sleep, guarded-clock and on_row traces.
   Source opportunities/attempts and budget invariants match what actually ran;
   unseen lease/source causes are not inferred. Parent red is absent counts/timing.
4. **Bounded manifest contract.** Add
   `StudyTests.test_t064_result_manifest_schema_is_exact_bounded_and_operation_local`:
   both protocols, recorded-zero versus missing, count maxima/invariants, bool,
   unknown keys/enums, invalid timing, >2048 bytes, intent/canary exclusion, and
   successive operation replacement. On enabled/disabled same-source executions,
   original state and all scientific row bytes/readout fields are identical;
   `state.json`, observations and unverified bytes do not gain diagnostic data.
5. **Real end-to-end persistence/binding.** Add
   `New192SessionTests.test_t064_existing_attempt_collect_bundle_finalize_decode_finish_preserves_diagnostics`:
   run actual probe.observe -> driver._observe_fields -> core.collect -> session
   collect -> existing writer -> core/session finalize -> real decode -> finish
   receipt/summary on synthetic transports/clocks. Publish the **actual generated
   ZIP bytes** into the fake service; do not rebuild from state/rows and silently
   discard the member. Check original manifest/transport/ref/ZIP digest bindings;
   stale transport or reference pin rejects changed diagnostics. Exercise both
   live/live192 through the same helpers, with no network.
6. **Interrupted/capacity evidence remains honest.** Add
   `New192SessionTests.test_t064_interruption_and_capacity_fallback_preserve_exact_scientific_bundle`:
   normal member survives both finalizers; unvalidated interrupted member is
   not_recorded; legacy missing differs from recorded-zero; valid near-limit
   unverified salvage that cannot accept diagnostics produces byte-identical old
   valid scientific files/ZIP and fixed capacity status through existing
   collection/receipt/summary process boundaries. All original rows/tail remain.
   An originally overflowing bundle still overflows; failed status persistence
   produces HELD evidence. Never claim a capacity test establishes every runtime
   state is reachable.
7. **Terminal history remains connected.** Add
   `New192SessionTests.test_t064_terminal_closure_admission_and_rescue_keep_original_digest_contract`:
   exact-byte fake Artifact service carries a diagnostic-bearing terminal result
   through closure and close-index/admission; the existing manifest/reference pin
   still agrees. Rescue has no fabricated aggregate. Mutated aggregate, stale
   transport/core/reference digest and attempted member loss fail their existing
   binding checks. No aggregate appears in state/intent/closure.json/other file.
8. **Contract, independent review and full gates.** First commit adds only these
   acceptance tests and characterization blocks. Retain meaningful parent-red
   output. Minimal implementation follows; retain old pin failure. Named P is a
   separate tests-only commit after root-reviewed probe bytes and independently
   computed canonical fixed SHA, changing only that literal. All old test blocks
   otherwise remain byte-exact against `conflict-evidence.json`; runners and
   coverage remain intact. Run the two registered focused file runners, offline
   T058 handoff runner, compile, and applicable full project checks. Fresh
   functional review (>=10/12, spec/invariants=2) and adversarial review (none
   material) are mandatory. Reviewers reproduce meaningful mutants below.
   Root coordinates exact final/integrated complete45 Windows gates once per
   required source, using the established isolated non-Git D-drive TEMP, then
   normal same-source Linux CI and both locked builds only after qualified
   closure. Preserve actual native exits, command/source/Artifact provenance,
   prefrozen tracked bytes, and failures. No unchanged reruns merely for green.
   This diagnostic work is one related publication batch with T061/T062/T063;
   no T064-only partial publication, new live diagnostic probe or scientific run.

## Evidence required for READY

- Actual qualified-closure prerequisite and root acceptance recorded privately;
  branch parent and unchanged pre-implementation five-control fingerprints.
- Acceptance-only commit, raw meaningful parent reds, minimal fix, P-only commit,
  root-reviewed final probe SHA plus an independent canonical hash computation.
- Named per-criterion focused green output, schema-size result, exact trace and
  original scientific-byte comparisons, actual-byte fake-service seam receipts,
  capacity/interruption/terminal binding negatives. Record omissions and all
  runtime-unverified conclusions explicitly.
- At most six bounded synthetic mutation classes across independent reviewers:
  (a) erase native exit or mark unavailable as zero; (b) discard non-200 safe
  reason/replace nested `is not None` with truthiness; (c) add one diagnostic clock
  read or corrupt budget/opportunity counts; (d) allow a private string/unknown
  field or >2048 aggregate; (e) drop member in finalize or weaken digest binding;
  (f) drop salvage data/change a cap or make missing/capacity become recorded-zero.
  Each must make the relevant added test fail. Use controlled in-memory mutants
  with exact match counts, or byte-exact external backups/restoration with stale
  bytecode prevention. Do not mutate retained old evidence.
- Full current-source/final integration gate receipts and independent verdicts;
  root retains the full related release gate. No local-only READY claim releases
  a production push before these requirements hold.

## Conflict search and known uncertainty

The static census covers all current `tests/test_*.py` and the configured fixture
tree for chosen new names. It found 315 tests mentioning at least one broad touched
symbol; the four relevant test modules have 105 old test-function fingerprints.
New operational_diagnostics/diagnostics_status/hook names had no existing test or
fixture occurrences. Existing runner registration is test.yml lines50/53; T058's
offline guard is already registered at234. Companion evidence enumerates every
matched function and line, not only expected assertion changes.

The sole expected old failure is P. Particular unchanged constraints include:
`test_curl_preserves_status_for_empty_malformed_and_refused_json`,
`test_refused_and_transport_failed_requests_never_become_report_observations`,
`test_terminal_deadline_and_remaining_timeout_bound_calls_and_preserve_partial_rows`,
`test_slow_live_phase_keeps_unavailable_and_unattempted_cells_distinct`,
`test_strict_completion_deadline_retains_boundary_overrun_and_unattempted_cells`,
`test_new_strict_end_preserves_late_response_and_readout_censoring`,
`test_actual_generated_new_cli_graph_excludes_slot192_and_restores_192_results`,
`test_new_partial_finalize_local_restore_and_read_only_closure_bind_protocol`, and
T058's real monitor/status handoff and nested-refusal tests. Any other old failure
is BLOCKED, not an invitation to update assertions/mocks.

Only schema width and existing pure reason semantics were executed in this design
pass (two bounded offline witnesses). The proposed optional hook, writer capacity
status path, enabled CLI binding, and finalization/terminal-admission preservation
are code-derived **unimplemented and runtime-unverified**. Feasibility established
ordinary manifest capacity and an existing state/intent counterexample, not this
new runtime integration. Acceptance tests must settle those uncertainties; the
implementation remains HELD if those obligations cannot be met within scope.

## Threat model

Prevent accidental private text/identity retention through error documents, curl
stderr/exceptions and arbitrary native values; false native success from missing
capture; stale callback/counts leaking across operations; false zero/completeness
after interruption; extra requests or time reads altering scientific execution;
lost manifests in finalize/closure; stale digest pins; scientific salvage loss
under capacity pressure; and a test hash rewritten to whatever implementation
exists without independent root review. Fixed enums, strict read/write schema,
bounded objects, old-byte characterization and adversarial seam tests address
these realistic causes. No legal/privacy wording or source terms change occurs.

## Amendments

2026-10-24, private preregistration: root authorizes named P only after actual
qualified closure and minimal-probe review, rather than subprocess interception
to preserve the obsolete current-source literal. Root also permits a preregistered
dependent T-065 split if implementation would exceed M; such a split does not
permit partial publication. That original draft was dependency-held until the
root acceptance below; its historical source/evidence remains unchanged.


2026-10-26, root acceptance: the original qualified closure, report, complete
original archive and owned-only stop bindings are reverified. The exact design
passes DoR after unchanged-source reconciliation; implementation is now authorized.
NamedP and every original scientific/transport boundary remain exactly as above.

2026-10-26, A1 named additive-test fixture repair: the first acceptance-only
commit exposes two setup defects before the intended missing-diagnostics seam.
Only the newly added StudyTests.t064_run synthetic tick cohort may change its
three synthetic members from fresh to control so enrollment-free members satisfy
the unchanged parent state validator. Only the newly added session helper may
initialize its fake service's reads/downloads/seconds_spent/runs statistics to
their appropriate empty values required by the unchanged existing _stats seam.
Do not alter old helpers/classes, any old or new assertion, expected diagnostic
count, runner, source validator or other fixture. Keep the original failure logs.
Commit this exact setup-only repair separately before the runtime fix, and rerun
the original parent to establish meaningful missing-diagnostic reds through the
now valid setup. No assertion or acceptance threshold is relaxed.

2026-10-26, A2 supersedes only A1's synthetic tick population choice. The unchanged
active-state validator requires40-45 fresh members and the exact existing control
population; three enrollment-free controls are also invalid. Only the new
StudyTests.t064_run tick-cohort setup may instead contain40 synthetic fresh mints
with fixed valid HTTP200/ok enrollment, fixed aware detectedAt one minute before
the existing EPOCH, ts=EPOCH, followed by exact probe.MAJORS controls in their
existing order. Both original protocol validators accept this proposed setup.
Keep all assertions, expected counts, clocks, guard behavior, old helpers and
runtime validators unchanged. Commit A2 tests-only and reproduce the intended
missing-diagnostics parent red, preserving both earlier setup-failure records.

2026-10-26, A3 named new-test serialization fixtures only: in the added manifest
read-rejection case, serialize the deliberately malformed manifest with
json.dumps(...).encode('utf-8') so its intended NaN reaches the production decoder
instead of being rejected by the valid-output encoder in test setup. The write
rejection and every existing/new assertion remain unchanged. In the added
capacity case, enumerate all actual on-disk result files in the original _files
key order before constructing the actual ZIP comparison. Retain every actual
file; unexpected filenames must remain included and fail the existing dictionary
equality, never be silently filtered. This corrects NTFS enumeration-order input
to the deterministic ZIP constructor, not ZIP/file bytes or digest assertions.
Only these two added test-setup paths may change in a separate tests-only commit;
retain the original failures and all old tests/helpers/source behavior.

2026-10-26, A4 named status-persistence failure injection: only the newly added
capacity test's os.replace fault may delegate to the original replacement for
every destination except collection.json, where it raises the same synthetic
OSError. The prior module-wide replacement fault also interrupted scientific
file persistence before reaching the required status seam. All assertions,
scientific data, original os.replace behavior outside that fixed destination,
and original runtime/test code remain unchanged. Keep the earlier failure and
commit this setup-only change separately before the runtime fix.

2026-10-26, A5 named salvage-fixture preservation: only the added capacity test's
later legacy/missing-diagnostics write may pass the same existing unverified tail
explicitly. The existing writer correctly rejects a leftover scientific tail
whose rebuilt manifest did not name it. Do not delete the tail, change the writer
or alter any assertion to make this setup pass. Preserve its failure and commit
the one input-wiring correction tests-only before the runtime fix.

2026-10-26, A6 bounded acceptance supplement before the runtime fix: add only
these four new methods in the already registered test file; every original and
previously committed assertion remains unchanged:

- StudyTests.test_t064_refusal_limiters_and_unrepresentable_timing_preserve_original_traces
- StudyTests.test_t064_recorded_zero_missing_and_reused_target_remain_distinct
- New192SessionTests.test_t064_capacity_status_survives_actual_finish_receipt_and_summary
- New192SessionTests.test_t064_rescue_has_no_aggregate_and_canary_rejects_result_member

They complete the existing AC3-7 obligations for phase/study/equal limiters and
nonrepresentable timing, recorded-zero versus missing and caller-dict replacement,
actual finish receipt/allowlisted summary capacity status, rescue and valid
canary-member rejection. This is no new behavior or scope: runtime stays in the
same three files, all caps/traces/science remain original, and all new methods
are tests-only before the runtime fix. Reproduce missing-feature reds against
unmodified parent runtime in an isolated bounded fixture; preserve the originals.
Characterizations already supported by the old runtime need not be falsely made
red. Distinguish synthetic pure unreachable-schema witnesses from actual operation
evidence. Report HELD if any required seam cannot be demonstrated within thisM
task; no partial publication or self-certified READY from code inspection.

2026-10-26, namedP fixed literal approval: the lead reviewed the final minimal
probe diff and an independent source-identity check computed the same LF-canonical
SHA using Python and PowerShell, with a byte-exact retained copy. For those exact
probe bytes only, the approved replacement is
c1fb2e3b5b0fb68c43a2a6442aa404aeb5a9b5983dc5107aa7bbff22abe2bf6c.
Apply only the previously named expected current-probe literal in its separate
tests-only commit after the runtime fix. Preserve every other legacy fixture,
old assertion and historical source pin. Changed probe bytes require renewed
review/hash agreement. This narrow approval is not task or publication acceptance.

2026-10-26, A7 named near-capacity fixture headroom: only the added capacity
fixture's artificial margin changes from100 to1024 bytes. A bounded eight-case
witness actually loads the five original parent sources and executes unmodified
finalizers: the original100-byte setup already overflows without diagnostics;
the1024-byte setup permits ordinary original finalization in both namespaces
while still refusing the added aggregate. Keep all original outer caps, every
scientific/unverified byte within that chosen valid fixture, fallback/status/ZIP
assertions and the original invalid-bundle failure. This is a test-input repair,
not a capacity increase or permission to suppress original clock sealing.
Commit A7 tests-only before the runtime fix and preserve both candidate and true
original-parent witnesses with their distinct provenance.

2026-10-26, R1 decision/A8 mixed-native consistency: independent functional and
adversarial runtime checks reproduce one material AC4 gap. A restored aggregate
can undercount usable bodies when any native evidence is unavailable. Add only
StudyTests.test_t064_mixed_native_evidence_enforces_usable_bounds_on_write_and_read
as a tests-only commit against the frozen R1 runtime. Exercise actual mixed
native/legacy capture, all-unavailable and all-native controls, representable
valid bounds, and inconsistent lower-bound values in both protocols and both
source envelopes where their original operation maxima allow a mixture. Test
write rejection and real generated-ZIP read rejection through core and session
constructors/decoders; keep independent stale transport/reference checks effective.
Read-rejection fixtures must carry otherwise valid recomputed envelope digests so
they fail for the actual schema inconsistency, not an unrelated stale pin.

Keep every prior test/assertion/fixture and namedP exact. The minimum source fix
enforces usable_body >= max(0,reason.ok-native_exit.unavailable), retaining all
existing upper bounds, nonzero-native transport-failure constraints and complete
evidence equality. No classification/request/clock/science/protocol/cap change,
probe edit or new persisted field is authorized. Preserve meaningful R1-parent
red before the separate fix commit. This closes the malformed mixed-evidence
class; final fresh combined R2 review and actual exact-source complete45 remain
mandatory. The existing six mutation classes remain the cap; direct R1-parent
reproduction is not a new mutation family. An unrelated dated-data baseline
failure stays explicit and must be resolved before normal source publication.
