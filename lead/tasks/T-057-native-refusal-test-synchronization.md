---
id: T-057
title: Start a refusal cancellation test after durable child headers
status: done
level: 1
size: S
depends_on: [T-046, T-052, T-055, T-056]
---

## Context and goal

The fresh T054 combined full gate atcd1c534 records44of45 and a named(e)
refusal_control assertion of two attempts rather than one. Original temporary
sidecars were removed, so its exact request/header state is unobserved. A bounded
external diagnostic reproduces the timing-premise class on bothcd1c534 and the
unchanged base18fa904: a one-second first NativeWorker.start delay exceeds the
test's0.7second engine timeout before any invocation/header exists; the legitimate
second attempt then observes401 and stops. Fast control observes401 on attempt1.
This is evidence of a pre-existing fixture premise, not proof of the original
run's precise cause or a T054 runtime regression.

Make the cancellation test start its existing short cancellation interval after
the first child's durable headers are actually observed. Keep a separate bounded
startup wait. This is a test-harness repair; native/engine behavior stays exact.

## Scope and named changes

Only tests/test_w40_native.py and governance records are in scope. In
NativeAcceptance.test_w40_native_caps_pacing_deadline_and_cancellation,
change only the named(e) refusal fixture and its local
helpers. Preserve every original response, status, attempts, journal, commit,
retirement, identity and loopback-call assertion, all four401/403/callback/200
cases, retries1, the0.7second cancellation and one-second post-header hold.
Do not merely increase those times or replace actual cancellation with a thrown
ordinary exception. Refactor this fixture into a reusable test-local helper if
needed; that exact extraction is a named existing-test change.

Add test_native_refusal_cancellation_after_slow_startup in this already registered
module. In a tests-only commit, exercise the same original named(e) assertions
with a bounded one-time first-child startup delay longer than0.7second. The
parent must fail its existing attempt-count premise, not an import/name error.
Keep old-case inputs and all unrelated tests byte/AST unchanged. A narrowly
scoped real-loopback fixture may coordinate events/tasks and the engine's first
fetch handoff; never patch production timeout/policy semantics to force success.

## Acceptance and evidence

1. Freeze conflict search and the exact tests-only/source SHAs. Preserve the new
   deterministic parent red and original44of45 receipt. Do not retry an unchanged
   full gate for green or claim the old failure vanished.
2. Use explicit synchronization with a finite separately asserted startup bound
   to establish durable first headers before starting the short cancellation.
   Retain genuine task cancellation or callback failure through the unchanged
   native adapter. The existing fast case and delayed case both run all original
   refusal cases;401/403 stop after one physical observed request, while200 keeps
   its legitimate retry behavior. Keep exact cleanup/journal/identity assertions.
3. Removing refusal reconciliation or its stop behavior must still be detected
   by a bounded meaningful mutant. An unavailable header must fail the startup
   premise explicitly within its bound rather than count as refused or passed.
   All traffic is local synthetic loopback; zero Vendor/production requests.
4. Production files, runtime locks, scientific modules, T054 implementation/tests,
   source limits and other workflows remain byte exact. Obtain a fresh independent
   review of this narrow test change. After approved normal integration, run the
   newly changed exact-head complete45 with raw inventories and native exits;
   actual Linux/master checks and both locked builds must pass before deployment.

This one small companion protects the final release gate. Stop at its verified
test repair; no local archive/queue/scheduler dependency, new study or new service
is authorized. Keep every failed attempt and report timing evidence precisely.

## Amendments

### A1 - 2026-10-23: isolate cancellation injection from normal retry startup

First-round sourcef9cd525 passes independent native12/12 and source review12/12,
and actual Linux39925732179 passes all45 and both locked builds. Its later exact
Windows combined gate still fails44of45: the200 positive control returns None
instead of the original observed body. The failed gate remains failed; its exact
fast/slow invocation and temporary sidecars are unobserved.

A separate bounded extracted-fixture diagnostic confirms the timing class. In
the unchanged control, first durable200 headers precede a real first-task
cancellation. The second worker is cancelled during start before durable headers
are observed; two physical loopback requests are recorded, so absence of header
evidence is not absence of a request. Observer overhead may affect this control.
In the separately retained one-second delay before only the second worker start,
the original assertion deterministically sees None. The first request has durable
200 headers; the second has no arming, invocation or headers, and only one
physical request occurs. Both children retire. This does not prove the earlier
full gate's exact internal timeline.

The original engine timeout parameter also bounds the ordinary successful retry,
which was not the intended injected failure. Separate that test-only watchdog
from the fault: keep a genuine0.7second asyncio.wait_for cancellation around the
first native task after durable headers and the unchanged one-second hold. The
unchanged engine function may receive a separate five-second fixture watchdog so
normal second-child startup is not itself the injected failure. This is the exact
named input change superseding the original engine timeout0.7 requirement only
inside named(e); it does not alter any production timeout, source guard, policy,
scientific deadline or decision bar. Retain the separate five-second first-header
startup bound, retries1, all four cases, every original assertion and real task
cancellation/callback behavior. Do not replace cancellation with an ordinary
raised exception, mock a successful answer, suppress an assertion, pre-issue the
second physical request before the engine asks, or patch engine bindings.

Before implementation, a tests-only named-change commit may extract exactly the
old named(e) statements into NativeAcceptance._run_native_refusal_cases. Its
statement/input/assertion AST must remain exact. Replace only that old block with
the helper call, and replace only the fixture call in the already-added
test_native_refusal_cancellation_after_slow_startup with this helper call. This
removes duplicate unrelated cap/deadline subcases from that new slow-start test;
the original registered method continues to cover every such case unchanged.
All original slow-first delay inputs and assertions stay exact.

In that same tests-only commit, add
test_native_retry_preserves_slow_second_startup. Delay only the second native
worker in the named(e) fixture by one second, retain all original cases and
assertions, and assert exactly one matching second-worker delay. The new test
must fail at the original None-versus-observed-body assertion before the fix,
not an import/name failure. Freeze both new slow methods thereafter. Implement
only the described fault/watchdog separation in a subsequent correctly titled
named-change fix commit whose body states the observed red.

The second-round reviewer independently reproduces the parent red, healthy fast,
slow-first and slow-second paths, genuine first cancellation timing, explicit
unavailable-header failure, meaningful reconciliation/refusal-stop mutants and
the unchanged non-target cases/source. A new exact-head complete45 with raw
inventories/native exit is required, alongside actual new source Linux/master
and locked builds. That independent complete gate may serve the combined frozen
T054 source because its five controls and acceptance remain exact; do not run
another duplicate unchanged full gate solely to relabel prior failures. Root's
post-integration complete gate remains required. This is T057's bounded second
round; only actual regressions or broken invariants justify another bounce.
