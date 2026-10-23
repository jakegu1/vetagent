---
id: T-056
title: Compare an elapsed float budget at its representable precision
status: ready
level: 1
size: S
depends_on: [T-052]
---

## Goal and named test change

An actual unchanged acceptance assertion on a real monotonic clock observes
1200.0000000000018 instead of1200.0. This is representable subtraction error, not
a measured extension of the packet limit. Correct only
tests/test_w40_native_clock.py::NativeClockAcceptance::test_native_scope_datetime_and_real_engine_age:
replace exact equality for deadline minus start with a comparison allowing only
the rounding error bounded by the two input floats' ULPs. Keep the expected
PACKET_SECONDS and every other assertion/fixture unchanged. Import math only if
needed. No production code, clock policy, scientific threshold or permission
change is allowed.

## Acceptance and evidence

- Preserve the actual failed full45 log and demonstrate the old comparison fails
  on the recorded pair or an explicitly labelled deterministic float witness.
- The new comparison accepts that rounding witness, still rejects a one
  millisecond extension and a one-second shortening, and passes the whole native
  clock module for real/default and fixed clocks. Do not add reflective tests that
  merely inspect the implementation; preserve these small arithmetic witnesses
  outside the repository.
- One clearly named test-fix commit contains only this assertion/import. It is a
  test-only correction: production behavior and its packet deadline stay exact.
  A fresh independent reviewer checks the mathematical bound and named diff.
- A combined exact-head full45 and actual Linux/master gates with T054/T055 must
  be green before deployment. Preserve every failed attempt and use external TMP,
  UTF8, source pins and byte inventories. Do not rerun an unchanged flaky gate to
  claim the original failure disappeared.

This narrow companion makes the observed CI failure actionable without weakening
the runtime budget. It does not authorize resuming held T047 work or a new study.
