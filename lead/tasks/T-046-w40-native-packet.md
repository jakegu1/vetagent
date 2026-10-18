---
id: T-046
title: Acquire one due W40 paired packet through a bounded native engine adapter
status: in_progress
level: 3
size: M
backlog: W40 prerequisite
design_base: cdf6face858e592d774279b92b5f89ec6a78e2bc
depends_on: [T-044, T-045]
decisions: [B1, B2, B11, E21, E23]
---

## Readiness and workstream boundary

The lead adopts this ready specification after both corrected sources pass
fresh independent and adversarial review, and the actual integrated ordinary
gate passes forty-three of forty-three with native exit zero and exact tracked
bytes. This task starts implementation only. Actual Linux publication and the
sole T044 live readout remain separate gates before native LIVE use. Neither a
short quota pilot nor this source implementation starts a prospective study.

Frozen dependency bindings:
- T044 source 6d300a30654d1bb9bcfc6bf39ac2af07caa041e1; combined twelve of
  twelve, RED-TEAM none; actual independent forty-two-step gate passes.
- T045 source 2090c3da3c9ed94767b543b05b8a7166f66e17cc; combined twelve of
  twelve, RED-TEAM none; actual independent forty-two-step gate passes.
- Integrated green source base cdf6face858e592d774279b92b5f89ec6a78e2bc;
  final actual forty-three-step log SHA256 a3cea5a1af553ae5fd7343d6c2d6e0daa9c7e040c17bf57fbb5df406d7ad91f1.

Canonical Git blob SHA256 bindings (runtime copies also bind actual bytes):
- bench/goplus_quota_probe.py: 3ec1e7688240fbd705b386ee7680758e6606bb9354938e994927a440e6e4b8f4
- bench/w40_evidence.py: 2e312e319229402088f6f1aaf15e53460d41a56468d6dd7d249c4123734e140d
- src/risk.py: 67b52bd3f7610aa98d6ed5f94457e875d16b489f633be54d170453e313dd8d2d
- bench/labels.py: ebbb4585c9cd829dcd1fbd374a8147918fcc742e525909a326a357f9246ae75c
- docs/BACKLOG.md: 0f0febb99e8cb2a7c0b14fba1affcf689b7ba40fc18af641e6478f1d267b3e1a
- tests/test_dataset_replayable.py: db43e79361584716a6f48bd40cd1225ffc2d6c344391cedcb2d5e4fa9e44e1ab
- .github/workflows/test.yml: aadbfeeab9ababd1e63b2e72c423245b504860c2c5fdae09b2263c9b9ba7a1fc

This task protects one real birth-timed paired observation from missing transport,
wrong identities, data leakage and lost partial attempts. It costs one M engineering
loop and zero vendor calls during implementation/review. Stop at reviewed single-packet
capability. Scheduler installation, global enrollment and the thirty-day clock are T047.

## Context and goal

T045 can replay saved raw packets but never fetches. Outside Workers, risk.cf_fetch
is None; both risk._fetch_json and risk._eth_get_code need real native HTTP support.
The benchmark adapter is not the driver: importing/running it would share its cache,
access log and publication paths. T044's native request_once is restricted to GoPlus,
so do not widen that held module into an arbitrary HTTP client.

Given a previously immutable T045 enrollment and one due ordinal, acquire at-label
reserve, current daily OHLCV, exact-token GoPlus and an unchanged verbose risk.assess
answer. Preserve each actual source/time/raw dependency, then import a complete or
explicitly partial packet into the unchanged T045 core. The command is safely offline
unless collection is explicitly requested, and does not begin a thirty-day study.

## Scope

In: a small native GET/JSON-RPC POST transport, process-local engine adapter, one
ordinal's private raw capture and intent journal, offline import/readout and acceptance.
Out: recurring processes, new providers/keys/packages/paid plans, CI raw retention,
src/ edits, label/rule edits, benchmark/cache/access-log changes, snapshot mutation,
new scientific tolerances, publication, engine variants, ablation or engine score changes.

The native allowlist is role-specific, derived from the frozen existing call sites:

| Role | Permitted HTTPS requests |
|---|---|
| Label | GT /api/v2/networks/{existing_net}/pools/{enrolled_pool}; that path plus /ohlcv/day?limit=1000; GoPlus /api/v1/token_security/{existing_chain_id}?contract_addresses={exact_enrolled_token} |
| Engine GET | api.dexscreener.com/latest/dex/tokens/{token}, /token-pairs/v1/{chain}/{token}, /latest/dex/search?q={encoded_symbol}; api.geckoterminal.com/api/v2/networks/{net}/tokens/{token}/pools and /api/v2/networks/{net}/pools/{validated_pool}; api.honeypot.is/v2/IsHoneypot with only the frozen engine's address/chainID/pair parameters |
| Engine POST | Current _CHAIN_RPC roots rpc.mevblocker.io, mainnet.base.org and bsc-dataseed.bnbchain.org, only the existing bounded JSON-RPC eth_getCode address/latest request |

The EVM cohort does not need RugCheck. Engine-role GoPlus, OHLCV/history, keyed
CoinGecko, credentials in URLs, redirects, unexpected hosts/paths/methods, arbitrary
ports and unknown runtime source changes refuse before calls. The bytecode.vetagent.internal
key is a private cache key only, never a native network destination. Do not change an
upstream to make a failed allowlist case work. Bound URL/payload/headers before transport.

## Files in scope and conflict search

1. New bench/w40_native.py: transport, adapter context, collect_one, recover/report CLI.
2. New tests/test_w40_native.py: stdlib unittest suite containing exactly the seven
   named acceptance methods below, plus a direct unittest.main() CLI. Commit this
   file alone first and preserve its assertions thereafter. Use nested or clearly
   bounded fixture helpers. Never edit the existing T045 containing test file.
3. .github/workflows/test.yml: add one unconditional offline step invoking the new
   file, retaining all prior forty-three required steps, jobs, conditions, pins,
   commands and build matrix exactly. This becomes the forty-fourth ordinary step.
   The three implementation files frozen by the active T043 study remain untouched.

No existing assertion/fixture changes. Source searches found no w40_native or collect_one
implementation/test. Existing tests requiring exact preservation include:

- test_the_stored_subset_covers_every_field_the_labeller_reads and
  test_the_committed_dataset_is_replayable in the existing dataset runner;
- all seven test_w40_* T045 functions, including the four amended regression blocks;
- tests/test_risk.py::test_benchmark_oracle_stays_out_of_the_engine,
  test_upstream_failure_yields_unknown, test_an_error_body_is_not_data,
  test_every_tool_discloses_stale_data,
  test_the_simulator_gets_a_second_chance_on_our_pool,
  test_a_fallback_that_says_not_found_has_answered,
  test_a_refusal_carries_the_upstreams_own_error_code and
  tests/test_upstream_contract.py::test_owner_power_rpc_contract;
- tests/test_benchmark_replay.py::test_ac3_defaults_no_cache_and_transient_failures,
  test_ac4_replay_roundtrip_and_complete_miss_refusal, and all clock/cache isolation tests;
- tests/test_decisions_enforcement.py::test_every_test_file_runs_in_ci and
  test_no_test_function_is_unreachable_by_its_own_runner;
- current T044 seven tests, telemetry privacy tests, workflow/deploy/archive guards.

Conflict searches cover w40_native, collect_one, cf_fetch, _fetch_json, _eth_get_code,
_cache_get/_cache_put, _BENCH_NOW, assess, source_commit, endpoints, raw_directory_refused,
ohlcv/day, before_timestamp, independence, intent and existing packet fields under
the configured tests/test_*.py and tests/fixtures/** globs. No old expectation must change.
Any additional old-test change requires a named amendment; do not weaken its contract.

## Acceptance criteria

1. Offline validated binding and due check. Default/help/plan/report/recover perform no
   HTTP, engine or Git calls. collect-one requires explicit live mode, immutable T045
   store/source manifests and ordinal, frozen code manifest, a newly claimed external
   runtime directory, and a distinct external private raw directory. Validate actual
   source bytes, T045 plan/engine/label/rule hashes and resolved identity before calls.
   A wrong source, existing/conflicting claim, CI environment, Git/safe-tree raw location,
   invalid clock or ordinal refuses with fixed safe categories. Do not collect before
   born_at plus twenty-four hours. Never turn a caller's earlier boundary into earlier
   enrollment; preserve T045's actual ingestion/boundary correction. Collection after
   target records actual lateness without asserting an approved tolerance.

2. Real native frozen engine seam. In a scoped context, provide risk.cf_fetch with a
   working native response object for the ordinary engine GETs and its existing
   JSON-RPC eth_getCode POST. Preserve the original risk._fetch_json, _eth_get_code,
   assess, label helpers, verdict policy and engine source bytes. Invoke
   assess(token, chain_hint=enrolled_chain, verbose=True), with an actual engine
   acquisition context clock, keyless existing-source configuration and an initially
   empty private per-packet engine cache. Record that configuration. Restore cf_fetch,
   cache/context ports and prior process state on success, exception and cancellation.
   No benchmark module/cache/access log, production MCP/HTTP service or all-failed
   adapter may be represented as live engine evidence. Only existing keyless engine
   hosts/path families and the three current eth_getCode RPC roots/method are allowed.
   Retain the frozen engine's existing transport retries and alternative-pair behavior,
   accounting for every physical attempt under criterion 4.

3. Paired exact raw/source/time packet. Fresh reserve GET is the current GT single-pool
   endpoint for the enrolled pool. Use its finite reported reserve to decide whether
   the unchanged USD 5,000 floor is observed; below-floor or unobserved reserve produces
   a partial saved packet with remaining stages explicitly not_asked for that reason.
   For an observed eligible reserve, request current OHLCV/day?limit=1000 without
   before_timestamp, one exact-token existing GoPlus GET, and the full engine answer.
   Persist actual request/response times independently, HTTP/body/envelope states,
   byte hashes, raw bounded responses, engine answer/context/source commit and selected
   pool. Preserve HTTP headers already observed if body acquisition later fails.
   T045 performs its unchanged raw/identity/clock/volume/B11 label replay, including its
   stale/historical-candle and missing-response-clock repairs. Missing data, 429,
   permission refusal, invalid result key, engine unknown, mismatch and below-floor
   reserve remain distinct. Include reserve endpoint in BOTH label and eligibility
   sets; include all actual engine dependencies, including failed and cached ones.
   Actual overlap fails B1; no filtering or role relabeling restores independence.

4. Hard bounded native transport. No implicit label retries or redirects. One active
   physical request at a time. At most three label attempts and sixteen engine attempts,
   nineteen total per ordinal. Host start gaps: GT 12.1 seconds, GoPlus 2.1,
   honeypot.is 2.0, DexScreener 0.25, existing RPC hosts 1.0. Every physical attempt
   has a durable intent before opening transport, an independently captured actual
   invocation clock and a thirty-second absolute boundary covering connection,
   headers, body and bounded worker cleanup. Engine cancellation at its own shorter
   deadline must retire that native worker; no background request survives into a
   next attempt. Recheck clocks, pacing and full remaining allowance after blocking
   persistence and before opening transport. Packet wall bound is twenty minutes;
   no new request opens when its full allowance cannot fit. Stop further calls on
   first actual 401/403, source drift, persistence/clock/history failure or interruption.
   Cap each body at 256 KiB plus one overflow byte; cap verbose answer at 256 KiB and
   produced packet at two MiB, below T045's existing maxima. Oversize, native
   HTTPException, recursion/JSON failures, byte-trickle, DNS/connect stall and unknown
   cleanup outcome remain unavailable/uncertain; retain known status without leaking
   raw exceptions. No cap exhaustion may silently delete a meaningful engine signal.

5. Private evidence and safe output. Every vendor body and raw verbose answer remains
   outside all Git worktrees and outside the safe output tree; honor real CI and
   GITHUB_ACTIONS flags without modification. No raw upload channel, credential or
   keyed CoinGecko path. Safe console/report/journal contain only hashes, source
   ordinals, clocks, fixed states, bounded numeric statuses and counts, no addresses,
   URLs, raw prose, paths, traceback or credentials. The safe report is at most one MiB;
   each source row still obeys T045's 64 KiB limit. Use fixed safe failure diagnostics
   for malformed inputs and worker/subprocess errors. Persist engine upstream bodies
   and their request metadata privately even when the final verdict is unknown. Do
   not call a provider-reported reserve independently verified depth. No automatic
   evidence deletion, new telemetry or repository privacy change is allowed.

6. Immutable partial and cross-process handoff. Persist every attempt claim, bounded
   raw response/commit and prepared packet incrementally, preserving the preceding
   committed bytes on any failure. Separate network acquisition from offline T045
   ingest. report/recover are read-only with respect to vendor work: an interrupted
   attempt consumes its slot and becomes uncertain/unobserved; it is never re-asked.
   If every required prepared byte is present, a fresh process can verify/import that
   same packet offline exactly once; an already imported or conflicting receipt
   refuses. Incomplete T045 import history stops that store and later live work;
   never clear an intent/orphan or rewrite the core's index to resume. Actual
   subprocess tests must kill one acquisition between intent and response, invoke
   the normal offline recovery/import entry in another process, retain known earlier
   HTTP evidence and prove zero vendor re-asks. Record all unfinished/unasked cells.

7. Tests first, truthful readout and checks. Add exactly these seven tests, acceptance
   alone first, and freeze them after their native missing-module red:
   test_w40_native_default_binding_and_birth_due_are_offline;
   test_w40_native_real_get_rpc_and_frozen_engine_context;
   test_w40_native_paired_sources_raw_times_and_independence;
   test_w40_native_caps_pacing_deadline_and_cancellation;
   test_w40_native_private_boundary_and_safe_failures;
   test_w40_native_partial_acquisition_recovers_without_reask;
   test_w40_native_cli_and_existing_contract.
   Tests use fake time/transport and bounded native localhost fixtures only, never a
   provider or production service; synthetic CI-environment patches are fixture-local
   and restore exact prior values, while a separate real guard rejection is retained.
   Prove both GET and POST using actual native HTTP machinery and the ordinary adapter,
   then a stubbed frozen engine-to-core handoff. Protect source bytes and at most three
   meaningful mutants (attempt cap bypass, uncertain attempt replay, raw sentinel leak).
   Run focused/real CLI tests, exact old-byte/AST freeze and the new direct runner,
   then one root-granted globally exclusive full ordinary inventory. Preserve red/green
   commands, native exits, hashes and complete logs. Fresh independent plus adversarial
   review and actual Linux checks precede integration. Report attempted/completed/error/
   not_asked/unknown/overlap denominators and actual timing; do not print a quota, full
   availability, simultaneous/T+24h pass, started study or W40 success.

## Required evidence and root runtime boundary

READY: exact dependency/source/test hashes, tests-first red, no old-byte changes, native
GET/POST/cancel/header/body proofs, child-to-child restore proof, complete configured
inventory, independent review at least 10/12 with spec/invariants 2 and RED-TEAM: none.
No real provider is called by executor/review tests. Root may run one predeclared
bounded existing-source packet/adapter observation after integration under existing
authorization; it must show actual data-bearing native HTTP and the RPC seam rather
than count an all-failed-fetch verdict. A control-token adapter proof is explicitly
non-cohort and does not start W40. A real future-enrolled due packet belongs to T047's
start receipt. Distinguish source READY from runtime evidence still unavailable.

## Threat model and rollback

Hostile/malformed upstream text, wrong token/pool, error envelopes, sparse/stale candles,
native cancellation leaving a request alive, inherited retry/cache inflation, disk-full
after intent, lost worker header evidence, accidental public logs and retrospective
selection must fail visibly. Normal source ports must restore even on cancellation.
Rollback removes only new source/test additions through normal reviewed Git history;
private evidence remains byte-exact and readable offline. Do not modify T044/T045,
source/label/bar policy, public snapshot archive or agent permission files.

## Lead preflight choices, fixed before acceptance tests

The separate read-only ready-spec preflights found seven concrete seams. These
choices resolve them before the first acceptance commit. They add no scientific
tolerance, provider, source right, quota claim, production engine edit or study start.

1. Bind T045's reviewed b2 endpoint normalization. Include all actual RPC, cached,
   failed and GT reserve dependencies. Reserve is in label and eligibility. A known
   overlap remains failed even if another endpoint is invalid; incomplete disjoint
   inventories cannot pass. Preserve the corrected core source and tests exactly.

2. One physical request owns one killable child across both await boundaries.
   The unchanged engine separately waits up to eight seconds for ordinary fetch
   and text, or six seconds for RPC fetch and text. cf_fetch resolves after captured
   headers; response.status is numeric and asynchronous response.text() consumes
   that same request, never another GET/POST. The original thirty-second absolute
   parent deadline spans spawn, invocation, headers, body and bounded retirement;
   never reset it at the second await. Persist and acknowledge observed status
   before the body wait. Cancellation during pacing, headers or body must retire
   the owned child; unknown cleanup stops acquisition. Preserve reserved/consumed
   slots separately from confirmed child invocation. Apply pacing to actual child
   invocation after all blocking persistence, not only intent creation or parent
   process spawn. A wait cancelled before invocation is not a fabricated HTTP error.
   Restore after callers discard a response without text(), including RPC non-200
   and ordinary mark_missing/404 early returns. Own every outstanding worker in the
   adapter context and retire it before another physical attempt or scope exit;
   do not depend on garbage collection. Accepted explicit application headers are
   the unchanged Accept and RPC content-type forms; freeze the decoded eth_getCode
   payload keys/values to the existing engine call. Normal CLI cannot select a
   localhost address/port; bounded HTTP fixture routing is direct test injection.

3. Separate the native acquisition journal from the core ordinal import journal.
   Native fixed safe events are claim, attempt_intent, headers, attempt_end,
   packet_prepared and import_result, linked to prior event, plan, ordinal, source
   reference, code manifest and private blob hashes. Raw targets/headers/bodies
   exist only in private sidecars. Up to sixteen engine bodies of 256 KiB each
   remain sidecars; only the four required stage bodies and bounded provenance
   enter the two-MiB prepared packet. Offline recovery can seal a partial packet
   and ingest exact verified bytes once, with no new transport. If producer
   import_result persistence fails after the core succeeded, read back the actual
   core receipt to distinguish imported from uncertain. Never edit core events,
   clear an intent/writer, repair its index or automatically re-ask a consumed slot.

4. Validate observed reserve HTTP/body, exact data.id, exact attributes.address
   and finite reserve before applying the unchanged floor and opening later calls.
   A high number attached to another pool opens no OHLCV, GoPlus or engine work.
   Persist the invalid reserve and all remaining not_asked reasons; the unchanged
   core validates independently again at import.

5. Exact permitted engine context ports are cf_fetch, _cache_get, _cache_put,
   _BENCH_NOW, _ONCHAIN, _STALE_HITS and _FETCH_FAILURES. Preserve the original
   _fetch_json, _eth_get_code and assess function objects and source bytes. The
   benchmark clock port does not control direct checked_at wall time: retain
   actual engine_context_at within acquisition start/end and checked_at separately.
   A new packet starts with an empty private cache and records real age/dependency
   history. Restore exact original functions, ContextVar unset/value state and
   original _ONCHAIN object contents on success, exception and cancellation.
   Same-process sentinel controls prove restoration; a new process is insufficient.

The seven acceptance methods cover these choices through actual GET/POST native
HTTP fixtures, before-header and byte-trickle cancellation, discarded response,
status durability, sixteen sidecars, uncertain-core-import readback, wrong-pool
eligibility refusal, same-process state restoration, and a separate actual CLI CI
raw refusal before writes. Long pacing/budget simulations use fake clocks; actual
child retirement uses actual native subprocesses and bounded local HTTP fixtures.
Keep the new native test's accepted assertion bytes frozen after its first red.

6. Expose one optional Python-only admission/observation policy in collect_one
   and its native adapter; the standalone default enforces this task's bounds.
   It is the same policy for every label and engine physical attempt, including
   retries. before_attempt receives only fixed role/host codes, plan/code hashes,
   ordinal, immutable attempt ID/number and proposed full allowance. Before it
   returns a single-use permit it durably reserves the attempt and worst-case
   private write allocation. A permit binds its durable journal sequence/hash,
   reserved UTC date, absolute monotonic expiry and effective request, packet,
   external tick/study deadlines. No URL, identity, path or prose enters that safe
   interface. Recheck after blocking persistence, policy callbacks, pacing and
   child containment/handshake. An expired, midnight-crossing or insufficient-
   allowance permit opens no transport and stays consumed as not_invoked or
   uncertain; never transfer it to another date or replay that attempt. Fixed
   observer events are native_invocation with actual UTC/monotonic samples,
   headers with numeric status, attempt_end with fixed state/body hash/size, and
   child_retired with verified fixed retirement state. Bind them to the permit
   hash and persist them for a later process. A claim/spawn timestamp is not
   native invocation proof. A callback failure retires the child and stops.
   These injectable ports let a later driver supply global budgets and retrieve
   the first invocation without editing this frozen module. Lost possible-first-
   invocation proof requires terminal start_uncertain, not adopting a later call.
   Test injected blocking callbacks, midnight/expiry/cap refusal, engine retries,
   first-event retrieval and callback failure with zero extra transport. They add
   no ordinary CLI flag or permission/source/deadline bypass.

7. Cooperative cleanup is insufficient for a killed parent. A native child starts
   disarmed behind a control handshake and cannot open transport until containment
   is verified. On Windows, use a non-inheritable kill-on-close Job Object, assign
   the blocked child and verify assignment before acknowledging eligibility; the
   child must not inherit the last job handle or request breakaway. Before that
   acknowledgement, a closed parent/control channel exits without a request. On
   Linux, install parent-death SIGKILL before readiness and verify expected parent
   before/after arming. An equivalent mechanically demonstrated containment is
   acceptable; a containment/API/assignment failure refuses before transport.
   Private child creation identity/start token is retained in a sidecar; safe
   evidence carries its hash and confirmed retirement state. Recovery must never
   release the next live attempt solely because the prior parent PID disappeared.
   In actual local subprocess tests on each tested operating system, hard-kill
   the acquisition parent once before acknowledgement and once after confirmed
   native entry while awaiting a local response. Independently verify that exact
   child exits, invoke normal offline recovery in a fresh process, and prove no
   re-ask/no next request before retirement and retained intent/first-entry proof.
   Unprovable child retirement or possible first invocation is a fixed terminal
   safe-stop. Show actual Linux results in CI and actual Windows results locally;
   do not claim an operating-system guarantee from a mock. No new dependency,
   T044/T045 edit, agent permission change or study start is introduced.

## Named native premature-EOF regression

2026-10-19 (a): before READY, an actual localhost probe on held source 9303ef9
reproduces an original AC4 transport-integrity defect. HTTPResponse.read1 can
return EOF while the declared Content-Length still has positive remaining bytes.
A flushed valid JSON prefix is then accepted as a complete response. Preserve
that meaningful private red and any actual complete gate at its original head;
do not rebind either to a repaired source.

Permit exactly one self-contained append-only regression block at the end of
test_w40_native_caps_pacing_deadline_and_cancellation, after its current last
assertion. Nested fixture classes/helpers/imports belong in that block only.
All earlier statements/assertions/order, the other six methods, shared helpers,
original module/main bytes and seven-method discovery remain exact.

Use actual localhost native HTTP: return status 200, declare a Content-Length
longer than a flushed valid JSON prefix, and close the connection. The known
status and exact prefix/hash remain retained privately; the body is truncated or
unavailable and must not be accepted/cached/imported as a complete observation.
The worker is retired, no retry is introduced and no raw identity/prose enters
safe output. A counterpart response with exact declared length and the same valid
JSON remains a complete positive control. Fake only the destination route through
the existing technical test injection, never the native body reader.

After the running held-head gate completes and its global slot is released, commit
this ordinary-CI regression alone and reproduce its native red on held 9303ef9.
Then one separate finding repair rejects premature EOF with remaining declared
bytes and preserves already observed headers/prefix/retirement. Stay in the same
new source file; do not edit any other source, rule, bound, original assertion,
dependency or workflow contract. Re-run focused/native controls, mechanically
verify the sole approved appended block, freeze the new head and request its own
root-granted exact-head complete gate. Fresh independent and adversarial review
and actual Linux remain required before publication; no live request or study
start follows from this correction.

## Named policy-request-deadline consistency regression

2026-10-19 (b): a separate native localhost probe on held 9303ef9 returns a
policy permit whose request_deadline is twenty-five seconds earlier while the
proposed thirty-second allowance remains unchanged. One actual GET still opens.
That mismatched permit must not silently shrink the native observation window.
Preserve the independent red and the held source's actual complete log.

Permit exactly one more self-contained append-only block in
test_w40_native_caps_pacing_deadline_and_cancellation, after the named a block.
Keep all previous assertions/order, helpers, other methods and runner exact.
An injected policy preserves all proposed identity and allowance fields but
shortens only request_deadline. With the actual native localhost destination
fixture, the permit refuses before invocation and no server request occurs.
Keep an unchanged-permit positive control, existing expiry controls and shorter
external packet/tick/study boundary refusals. Original engine cancellation at its
own deadline still retires the worker; it does not change the admitted permit.

The technical choice is that the proposed native request_deadline is an immutable
permit identity field. The external policy may refuse or tighten its external
expiry/packet/tick/study boundary, provided a full proposed allowance still fits;
it cannot change the native request deadline while retaining that allowance.
Commit this additional regression alone with its meaningful red, then one separate
same-finding repair in the new native module. No test weakening, policy/source,
quota, study window, engine function or accepted fixture change is allowed.
Both a and b require current focused/native proof, a new frozen exact-head full
gate and fresh independent/adversarial review before publication. The old 44-step
green at 9303ef9 is held-source evidence only.
