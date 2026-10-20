---
id: T-053
title: Select snapshot coverage by observed UTC chronology rather than append order
status: done
level: 1
size: S
depends_on: [T-029]
backlog: W7 reliability prerequisite
decisions: []
---

## Goal and observed defect

The existing coverage CLI chooses the last line of the lexically last run file.
A synthetic four-row manifest with a newer failed pass followed by an older
successful pass returns complete/exit0. Chronological ordering returns incomplete/
exit1 for the same rows. The separate freshness monitor already chooses the latest
UTC instant correctly. No occurrence in the real archive is asserted.

Make the existing read-only coverage CLI select the latest observed pass across
run manifests by timezone-aware UTC chronology. This protects snapshot diagnosis
without changing collection, scientific evidence or the active studies.

Cost: one bounded source/test correction and existing ordinary quality gates.
Stop when the named cases, fresh ordinary review and complete actual gates pass;
do not expand into new monitors, schedules, upstream calls or archive recovery.

## Scope and ceremony

Implementation: only `_check_coverage` in `bench/snapshot.py`. Acceptance: additive
functions in existing `tests/test_sellability_archive.py`, discovered by its
unchanged real main runner. No new test module or workflow registration is needed.
Lead metadata uses this spec, tasks/README.md, STATE.md, OWNER.md and its review
record only. Base is reviewed published `2cbf159`; normally reconcile later bot
observations at integration.

Level1: a small ordinary read-only selection correction. No verdict, telemetry,
source provider, published product claim, permission, workflow or deploy-runner
change. No T047 archive or native source, frozen W57 source, scientific clock,
threshold, schema, age policy, `_coverage` predicate or pool/sellability data edit.
Existing acceptance functions/helpers/assertions/inputs/discovery stay exact.

## Acceptance criteria

1. The real `--check-coverage` CLI selects the latest aware UTC instant across all
   nonempty runs-*.ndjson manifests, independent of line ordering and filename
   ordering. A latest failed pass followed by older success stays incomplete/1;
   latest success followed by older failure stays complete/0. Cover both input
   orders and a two-file case with misleading filename chronology.
2. Equivalent timezone-aware representations of the same instant form one pass,
   so separate new/trending rows with equivalent offsets remain complete together.
   Missing, malformed or naive timestamps and invalid JSON/shapes remain bounded
   incomplete/1; no invalid row is silently dropped to fall back to older success.
   Older valid timestamp rows with legacy coverage shape do not replace the latest
   pass or require validating their irrelevant coverage fields.
3. Coverage predicates, aggregate output and exit meanings stay unchanged. No
   freshness clock is added. Only run manifests are read; the operation performs
   no collection or sellability request and writes no archive data. Add acceptance
   using the real CLI, temporary external manifests and fail-on-call collection/
   sellability controls; assert fixture bytes unchanged and fixed safe diagnostics.
4. Tests precede implementation in their own commit, with a meaningful old-source
   failure for the ordering case and preserved old tests. Focused acceptance,
   contract, syntax and the actual complete45-command runner pass at an exact clean
   head with all tracked bytes unchanged. One fresh ordinary reviewer reproduces
   the evidence; actual same-head Linux CI and both locked builds gate publication.

## Conflict search and named changes

Searches cover `_check_coverage`, the CLI flag, last-recorded wording, fixed error
category and the existing coverage/freshness test groups. The current test at
test_snapshot_health_cli_checks_last_pass_and_rejects_absence_corruption_and_zero
contains only chronological older-success/newer-failure ordering. Other registered
tests cover workflow preservation and freshness. None requires alteration.
Named changes to existing acceptance bodies or helpers: none. Add one or more
new test_ functions to the already registered archive module; preserve its main.

## READY evidence

Report the tests-only and source commits, actual red and green raw outputs, exact
changed files, preserved original test ASTs, contract and configured45 inventory,
complete-gate native exit and before/after byte maps. Keep failures immutable and
qualify any live-data occurrence as unverified unless separately measured. Do not
infer whole-engine replay, elapsed study completion or security approval.

## Source completion

Tests-only3a6a0ff precedes source8ad2fce and reproduces13 ordering/validation
failures. The frozen head passes34/34. Fresh ordinary review passes12/12 with
twenty-five independent subprocess cases and three caught scratch mutants.
Executor and independent complete45 pass with all978 tracked raw bytes exact.
Actual same-head Linux39440532687 passes all45, upstream/backfill and both locked
builds; benchmark is skipped. Normal integration859bed8 passes complete45 with
all979 tracked bytes exact, including its independent review record. A separate
read-only CLI succeeds against every retained real run manifest with unchanged
bytes. Explicit fixed-point generation passes; only proved ephemeral display and
line-ending output is restored from external exact copies. Publication receipts
are separate from this source completion. No real historical occurrence, study
result or T047 security verdict is inferred. See lead/reviews/T-053.md.
