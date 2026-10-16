---
id: T-024
title: Apply the Owner's Experiment D postponement to 2026-10-20
status: in_review
level: 3
size: S
depends_on: []
decisions: [ADR-0002]
backlog: none
---

## Context and authorization

On 2026-10-16 the Owner explicitly postponed Experiment D to 2026-10-20.
The live strategy and pinned gate still use 2026-10-16, as do O2, O8, O9 and O11.
The approval changes the due date only. It does not resolve the gate, establish demand,
change the three-trial threshold, or authorize customer contact, payments or new sources.
Keep the project's existing UTC date interpretation.

The immutable execution base is origin/master
7ec4530b76a65c7f62da266870f9e28b295f919e. Calendar failures at the old due date are
an expected baseline class; record their actual output rather than claiming a green base.

## Goal

The current documents, pinned gate and Owner page agree on 2026-10-20. Before that date
the unresolved D gate and its four parked entries do not fail; from that date they still
require the original real conclusion and completed opportunity reviews.

## Workstream budget and stop rule

Protect scheduled data collection and deploy availability while preserving the decision
rule. One small source task, at most two review rounds, no added service or spend.
Stop and report a named conflict rather than changing unrelated rules or measurements.

## Files in scope

- docs/STRATEGY.md: the active Experiment D gate date and active prose explicitly tied to it.
- docs/OPPORTUNITIES.md: only the Blocked-until dates of O2, O8, O9 and O11.
- tests/test_gates_get_reviewed.py: only the Experiment D date in PINNED_GATES.
- tests/test_owner_page.py: named change below, only the real-file expected gate date.
- tests/test_experiment_d_deadline.py: new offline acceptance file, automatically discover tests.
- .github/workflows/test.yml: one ordinary offline step for that file, before the deploy guard.
- docs/OWNER.md: regenerate from the changed sources in a separate generated-artifact commit.

No source engine, production request, cache fill, benchmark, thresholds, permissions or
other workflow is in scope. No Owner-private facts belong in repository files.
The lead records this specification, ADR and status separately. The executor may run the
real Owner-page generator after the source implementation and commit docs/OWNER.md alone.
Do not hand-edit generated output or change the existing page-currency assertion. The
source-only probe reproduced that assertion failing when the source date moves without
regeneration; preserve the guard and remove that integration conflict before final checks.

## Conflict search and named change

Searches on the execution base cover 2026-10-16, 2026-10-20, PINNED_GATES,
gate_row_answered, parse_entries, owner.gates, and every reader of STRATEGY/OPPORTUNITIES.
Repeat the search and report any extra required change before touching it.

Allowed existing assertion change: tests/test_owner_page.py,
test_gates_come_from_section_8_only, the check named
"the real file: the four gates are unchanged": replace only the second expected
real date, 2026-10-16, with 2026-10-20. Its check label may say the dates match the
Owner-approved schedule. All synthetic Oct-16 test scenarios remain unchanged.

Changing PINNED_GATES is the actual policy edit; it is not an acceptance-test rewrite.
All original synthetic strategies, _GATE_DAY, _SYNTHETIC_ROWS, placeholder cases,
assertion helpers and automatic test discovery remain byte/AST unchanged.
Unrelated W5/W12 deadlines, closed O6 history, other gates, historical lead reviews and
dated measurements are not postponed.

## Acceptance criteria

1. The active D row in strategy is dated 2026-10-20. Its question, threshold and action
   are unchanged; there is no new Resolved marker. The other three gate rows are unchanged.
   PINNED_GATES has the same four question/date pairs except D's approved date.
2. Only the four named parked entries move to 2026-10-20. They remain parked and unresolved.
   Their other text, all other entries and historical review records remain unchanged.
3. Run the real guard logic over private temporary copies of the current documents with
   dates forced to Oct 16, 19, 20 and 21. The D gate and named entries do not fail before
   Oct 20; they do fail on and after Oct 20 while unresolved. Other rules remain active.
4. On Oct 20, a real conclusion alone still fails while entries remain parked. A placeholder
   conclusion still fails when entries are closed. A real conclusion and all four reviewed
   entries pass this gate. Use temporary copies, never alter the real gate to run controls.
5. Render the real Owner-page generator with the changed sources and forced dates. D appears
   with the correct Oct-20 date in its gate table, timeline and Needs-you section. It is
   upcoming on Oct 16/19, due on Oct 20 and overdue on Oct 21, with the same action requirements.
6. Tests are offline, use no external I/O and do not change any real tracked or raw data file.
   The first commit adds acceptance tests only and is actually red on the old schedule.
   Preserve every older test except the named real-file expectation. Register the new file
   using the existing workflow step shape; keep deployment/production workflows unchanged.
   After the source implementation commit, regenerate docs/OWNER.md with the real generator
   and commit that artifact separately before the immutable final full-runner check.
7. Demonstrate private safe mutants: roll back only the strategy date, only PINNED_GATES,
   and one parked entry, then bypass the unresolved check on Oct 20. Each must produce a
   meaningful acceptance failure. Restore actual pre-mutation bytes and avoid stale bytecode.
8. Final immutable head passes its acceptance file and the complete configured runner.
   Record real baseline/red/final outputs, scope diff, frozen old-case proof, and an
   exact-head READY report. No claim of experiment success, new observations or deployment.

## Threat model and review evidence

Prevent a partial date edit leaving CI red, a broad replacement moving unrelated deadlines,
or a date change weakening the decision guard. Review both calendar boundaries and the
half-answered case. Existing independent-label and fail-closed invariants remain binding.

READY includes base and commit SHAs, test-only behavioral red, final acceptance counts,
the full runner log and exit status, actual mutant evidence, the old-case scope comparison
and a clean branch. Write reports to private external evidence storage; do not merge/push.
