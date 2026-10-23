---
id: T-057
title: Start a refusal cancellation test after durable child headers
status: in_progress
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
