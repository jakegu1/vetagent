## Review: T-064 - Changes required

Head `97e71dd973164e2af2eab2f88957b53afccbf4ab`; base `f763a51500275cdfe1aad08989c3d5a8b11ae39c`.

One material acceptance gap remains: mixed native availability disables the required lower bound on usable-body evidence. The current validator and complete writer/decoder path accept an aggregate that contradicts the evidence already recorded by the same operation. AC4 is unmet.

Independent checks: `python tests/test_rugcheck_coverage_probe.py` passed 19/19; `python tests/test_rugcheck_w57_ci.py` passed 78/78; `python tests/test_upstream_contract_is_observed.py` passed 240/240. All three commands returned native exit 0. Compilation of src, tests and the three scoped collectors returned 0. The lead contract checker returned `CONTRACT HOLDS`, native 0. All 1,018 prefrozen tracked files remained byte-exact.

The independent full45 run was explicitly deferred after the first-round material finding. Full45, final integrated gates, same-source Linux CI and locked-build release evidence remain outstanding. This review does not certify those gates.

Contract and scope: the first task commit adds only tests. I inspected A1-A7 and P line by line against the adopted amendments. All 105 old function fingerprints match the frozen conflict census, with only P's approved literal normalized. The two changed test modules retain all 85 old test methods except that literal, and add 12 methods. Python and PowerShell independently reproduce the approved LF-canonical probe SHA `c1fb2e3b5b0fb68c43a2a6442aa404aeb5a9b5983dc5107aa7bbff22abe2bf6c`. The P commit changes only that fixed literal. Runtime scope is exactly the three named collector files; workflows, runners, historical data, production engine and old protocol fixtures are unchanged.

| AC | Result | Independently reproduced evidence |
|---|---|---|
| 1 | Pass | Original fake subprocess argv/options, one safe record, unchanged legacy tuple, native28/23, malformed/empty/refused bodies and exceptions. A failed diagnostic hook preserves the original science and ordered trace; the prior hook is restored. |
| 2 | Pass | Differential isolated T058 classifier, falsey nested non-null errors, malformed native types, bounded private-string exclusion and unchanged HTTP200 scientific characterization. Legacy injected transports record unavailable native evidence without claiming native zero. |
| 3 | Pass | Enabled/disabled request, sleep, guarded-clock and row traces agree across original boundary, slow calls, recruitment, both protocols, phase/study/equal limiters, exact vendor ceiling and unavailable timing cases. |
| 4 | Fail | Strict keys/types/enums, operation replacement and most consistency checks pass; an actual mixed native-evidence operation yields a usable-body lower-bound counterexample described below. The deliberately unreachable conservative width witness encodes to 1,287 bytes. |
| 5 | Pass | Both namespaces run original observe, field capture, collect, writer, both finalizers, actual on-disk ZIP bytes, fake Artifact service, decoder, finish receipt and allowlisted summary. Independent stale transport and changed-source negatives reject. |
| 6 | Pass | Both namespaces preserve every scientific file and salvage-tail byte under the valid near-capacity fixture, including exact ZIP equality. Fixed capacity status survives finish and another process. Original overflow remains rejected; failed status persistence raises; an invalid interrupted aggregate becomes not_recorded. |
| 7 | Pass | Diagnostic-bearing terminal results retain their manifest digest through closure and admission. Rescue has no fabricated aggregate; valid canary envelopes reject the member. Independent pinned-member loss and changed aggregate with stale reference both reject as admission_dependency. |
| 8 | Incomplete | Tests-first contract, approved old-test preservation, parent reds, focused checks, compile and assigned mutants are reproduced. Full/final release gates await the corrected exact source. |

Required change:

1. **[P1] Enforce the usable-body lower bound with mixed missing native evidence.** `bench/rugcheck_w57_ci.py:226-228` checks an upper bound and enforces equality only when native unavailable is zero. I ran one ordinary synthetic pilot through the actual hook and collector, suppressing capture for exactly one existing report call. The result has six RugCheck HTTP200/ok attempts, five native-zero attempts, one native-unavailable attempt and five usable bodies. Changing only usable_body from 5 to 0 is accepted by `_validate_diagnostics` and by `bundle_bytes` followed by `decode_bundle`. The admitted aggregate falsely erases five established usable bodies. At least `max(0, reason.ok - native_exit.unavailable)` usable bodies are guaranteed by the stated contract. Preregister a new additive acceptance test covering a valid mixed operation and rejection on both write and read, then strengthen the consistency validation without changing transport, clocks, scientific eligibility, caps or historical bytes.

Assigned in-memory mutants, each guarded by exactly one source match:

- (a) Erase the original nonzero native exit: the original-curl acceptance test fails for native28 and native23.
- (b) Replace nested non-null error detection with truthiness: the T058 differential test fails with ok versus vendor_rejected.
- (c) Add one diagnostic guard-clock read: the ordered trace acceptance test fails in all five selected phase/budget scenarios.

The corresponding unmutated assertions pass. Mutants never change repository files. No additional mutation classes were dispatched by this reviewer.

Four representative final acceptance methods were also executed against an isolated original-parent runtime with all five original controls verified against Git. Each returned expected native exit 1 at its intended missing-diagnostics assertion, without an import or fixture-setup error.

Rubric: spec 0; scope 2; correctness 0; tests 2; invariants 2; maintainability 2 = **8/12**. Spec conformance and correctness cannot pass while the demonstrated schema contradiction remains. No additional material issue was found within this bounded review.

VERDICT: CHANGES_REQUIRED
