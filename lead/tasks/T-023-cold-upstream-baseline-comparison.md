---
id: T-023
title: Compare observed coverage before a cold upstream-baseline write
status: draft
level: 3
size: S
depends_on: [T-016]
decisions: []
backlog: none
---

## Context and goal

T-016 explicitly parked the collapse-refusal bypass: main() returns write_baseline()
before test_generated_field_contract(), the only producer of _COLLAPSES. An independent
offline cold CLI probe on the published engine has all probes observed and a common
field's value share falling from full observation to zero. It exits zero and overwrites
the private synthetic baseline. The same observation, compared first, populates the
collapse list and causes the existing writer to refuse with unchanged bytes.

Make cold --write detect the existing R2 coverage collapse before opening the baseline
for writing. Preserve the exact VALUE_BAND, MIN_FOR_SHARE, partial-run refusal, generated
field policy and ordinary monitor/status behavior. No real baseline is re-frozen here.

## Scope

In: one shared comparison for the existing R2 condition, called by the normal generated
contract test and the writer before writing; additive offline cold-CLI tests.

Files: tests/test_upstream_contract.py, narrowly the R2 comparison and write_baseline;
tests/test_upstream_contract_is_observed.py, additive offline acceptance functions and
private helpers only. This latter file is already registered and discovers test functions.

Out: all committed baseline/status data; live probes and any --write of the real file;
probe cohorts, request count, URL templates, provider choice or keys; thresholds, manual
five-rule freeze gate, persistence windows; other test assertions, status shape, CI steps,
runtime source, published figures, generators, agent permissions and new dependencies.
Do not invoke the entire normal network test suite from --write. It would repeat probes
and apply structural comparisons to deliberate schema re-freezes beyond this task.

## Acceptance criteria

1. The first commit adds only offline acceptance functions/helpers in the existing
   monitor-observation file. A cold main() invocation with sys.argv containing --write has a fresh module with
   empty _COLLAPSES/_UNOBSERVED, an old temporary baseline, all MIN_FOR_SHARE observations,
   matching key/type shape and a value-share collapse. Fake measure returns the actual
   synthetic observations; network calls are fatal test failures. The measured initial
   red is successful overwrite instead of refusal, not a missing helper or import crash.
2. Cold --write now returns nonzero, identifies the collapsed source/path, preserves the
   old baseline byte for byte, and never opens it in a write mode. It makes only one
   measurement pass. A second cold case has a partial but nonzero old share falling by
   more than VALUE_BAND; it too refuses. No caller needs to run a test function first.
3. The comparison is exactly the existing R2 rule: common observed paths only; at least
   MIN_FOR_SHARE usable probes; strict less-than old share minus VALUE_BAND. Equality
   and a just-above boundary are not collapsed; just-below is. A sub-minimum fully
   observed synthetic source does not acquire a new R2 threshold. Existing new/removed
   path and key/type checks remain in the normal monitor. All constants stay identical.
4. Fully observed noncollapsed cold writes still succeed, produce the usual payload
   and current measured timestamp, and use the observed sources, current path count
   and unchanged rule constants. No-old-file bootstrap still works if fully observed.
   An existing unreadable or non-object baseline cannot be compared and is refused
   without replacing any bytes. Do not treat it as a missing baseline.
5. Existing partial-run and already-populated collapse refusals remain active; both
   preserve bytes and retain their truthful diagnostics. No global list is cleared to
   permit a write. Normal generated-contract comparison produces the same collapsed
   path names, ordinary checks and status record. Repeated calls do not double-count
   the same new collapse. No fake fixture updates enter the committed baseline.
6. Every pre-existing assertion and helper is immutable, except extracting the exact
   source R2 predicate into the shared helper without changing its behavior. No existing
   offline test is edited. Full configured checks remain green. Additive acceptance is
   reached by its current main runner and offline CI registration; no live probe runs.
7. Prove three restored mutants red: remove the writer's fresh comparison; change the
   R2 strict comparison to inclusive; bypass the existing unobserved refusal. Confirm
   baseline byte protection, one-measurement behavior and restored tracked source after
   each mutant, clearing stale bytecode safely. Independent and red-team review must
   separately reproduce cold versus warm behavior and default-monitor equivalence.
8. No actual baseline/status/source publication data changes. Keep the manual five-rule
   freeze gate in force. Record the actual red in every source-fix commit message, run
   the full configured suite on the reviewed head, and give the lead the frozen SHA.

## Conflict/readiness gate and evidence

Before ready, refresh exact-base searches for write_baseline, _COLLAPSES, _UNOBSERVED,
measure, test_generated_field_contract, MIN_FOR_SHARE, VALUE_BAND, baseline/status output
and observation-file discovery. Current inspection finds no other caller of the writer;
main is the cold bypass. The source predicate is in test_generated_field_contract, and
write_status accepts path-name lists. Source and existing offline guard contracts are
retained. Required old assertion changes: none.

READY evidence: exact base/head and test-only/fix SHAs; cold initial overwrite receipt;
head refusal/no-write bytes and one-measurement logs; all R2 boundary, partial, bootstrap,
corrupt-file and populated-list controls; default monitor/status equivalence; assertion
AST/source comparisons; three restored mutants; fullsuite summary; clean scope and no
baseline/status/cache changes. Two review rounds. Stop on a required threshold, manual
freeze-rule, probe/source or data change. This is a draft until the lead completes that
exact-base conflict refresh and dispatches it after the current correctness repairs.

Threat: a temporary missing field becomes the new normal because cold writing never
computes the comparison its own refusal checks. Synthetic data exercises this solely
offline; it never substitutes for the live observations required for a genuine freeze.

## Dated draft clarification

2026-10-12: main() takes no arguments; exercise the unchanged actual CLI through a fresh
module and temporary sys.argv containing --write, then restore argv. No signature change
is in scope. The ready amendment remains pending the actual post-T-021 published base and
renewed writer/caller/observation-contract search. This clarification does not dispatch
another task or change any R2 rule.
