---
id: T-054
title: Preserve finite research slots inside bounded running CI sessions
status: in_progress
level: 3
size: M
depends_on: [T-043, T-048, T-053]
---

## Context and goal

The delivered timer jobs completed, but most planned fixed-window slots had no
corresponding workflow run. A timer expression is not a delivery guarantee. Keep
the scientific core, cohort rules, original evidence, and old readers immutable;
replace repeated timer admission with one explicitly requested finite run whose
already-running jobs wait on absolute UTC deadlines. Preserve each intent and
result before moving on. This work protects empirical coverage rather than
changing a scientific conclusion.

The engineering cost is one bounded source task and one actual unarmed canary.
Stop after green independent reviews, configured gates, an actual source-bound
Linux run, publication, and the canary. Do not enroll or restart a scientific
study, add a paid service/provider, modify production risk code, or continue the
unrelated dependency-held local archive/queue/scheduler work.

## Files in scope

- New `bench/rugcheck_w57_session.py`.
- New `.github/scripts/render_w57_session_workflow.py`.
- Generated `.github/workflows/rugcheck-w57.yml`.
- Additive acceptance in `tests/test_rugcheck_w57_ci.py`, plus the named change below.
- This task, task index, STATE/OWNER, and final review record for governance only.

`bench/rugcheck_w57_ci.py`, `bench/rugcheck_coverage_probe.py`, scientific literals,
production sources, other workflows, dependency/runtime locks, agent permission
files and every original data Artifact are out of implementation scope. Reuse the
unchanged legacy scientific functions as an adapter boundary; do not monkeypatch
their module globals in the live path or duplicate a different scientific rule.

## Named existing test change and conflict search

`tests/test_rugcheck_w57_ci.py::StudyTests::test_workflow_is_independent_read_only_pinned_and_preserves_before_failure`:
replace its assertion that a
quarter-hour cron string is present with an assertion that the root workflow has
no `schedule` trigger. Retain its existing read-only permissions, pinned actions,
preservation ordering, credential, cancellation and seven-day-retention checks.
Make this named test change in the tests-first commit. No other existing assertion
or fixture input may change without a named amendment.

Search all tests for the old workflow, Artifact names, runtime-pins validators,
source hashes, prepare/finalize/finish commands and workflow step parsing before
implementation. The new tests stay in the existing registered module, so the
configured runner registration does not change. Generated workflow steps must be
explicit: the current step scanners do not inspect anchored step arrays reliably.

## Acceptance criteria

1. **Unchanged scientific and legacy contract.** Leave both legacy modules byte
   unchanged. Preserve target/minimum enrollment, all eighteen controls, fifteen
   minutes, forty-eight hours, 193 original slots, per-call pacing, request ceiling,
   field states, missing/censoring and readout rules. Old Artifact decoding and an
   explicit legacy report remain available. A late observation is never reassigned
   or backfilled. Preserve the existing endpoint rule even though it cannot by
   itself establish a complete negative result with positive response duration.

2. **Versioned immutable transport.** The new adapter handles multiple generations
   in the same workflow run with unique, non-overwriting intent/result names and
   explicit run/head/branch/workflow/study/generation/kind bindings. Numeric Artifact
   IDs remain opaque. Verify actual metadata, ZIP digests, manifest/file digests,
   parent chain and state before consuming data; reject unexpected, duplicate,
   malformed, foreign, ambiguous, stale, expired or failed/partial metadata rather
   than recording absence. Preserve original per-ZIP/uncompressed/state/row size
   limits and bounded history. Ordinary slot discovery/collection stays within the
   existing twelve-read/two-download transport budget; report stays within the
   existing 600-read/195-download/720-second envelope. If a new admission seam
   requires a different finite read envelope, report BLOCKED before changing it.
   Preserve global used-study and active-study admission semantics across both
   formats; a per-run listing must not silently forget prior/active studies.

3. **Exactly-once admission and complete freeze.** Refuse reruns with
   `GITHUB_RUN_ATTEMPT != 1` before any Vendor request. One fixed workflow-level
   concurrency group prevents overlap without cancelling a running study. A
   durable intent must exist before each acquisition; a lost/partial intent stops
   collection and remains explicit evidence. Freeze every executed source: legacy
   core, probe, session adapter, generated workflow and generator. An explicitly
   documented composite digest may retain the legacy three-key source schema;
   never omit a control source or misrepresent a raw-file digest as composite.
   Source/cohort/window changes fail closed and no auto-recruit/restart is possible.

4. **Finite absolute-time segments.** Generate a fixed chain of at most eleven
   jobs, each at most twenty slot opportunities, with a hard timeout no greater
   than 330 minutes (below the hosted six-hour limit) and at least five minutes of
   stop/preservation reserve before the job deadline. Determine each next due time
   from the frozen actual study start and slot index, not `sleep(900)` after prior
   work. Measure UTC and monotonic time, handle clock jumps without unbounded wait
   or replay, wait in bounded increments, and stop before a request that cannot fit
   the remaining per-phase/job/scientific budget. Finish, failure, source change,
   cancellation and an interrupted handoff never start a new window. Preserve and
   expose missed due times, operation start/completion times and late/unknown
   coverage; never label configuration or a passed job as complete sampling.

5. **Generated, scoped workflow.** The root workflow is manually dispatched only
   and has an unarmed canary as its safe default. Pilot, explicitly selected new
   study, and report modes are distinct. Inputs pass through environment variables,
   not shell source interpolation. Preserve read-only actions/contents permission,
   full action SHA pins, seven-day retention, no persisted checkout credentials,
   no extra secrets, always-preserve-before-failure and no production probes.
   Regeneration/check mode is deterministic and guards drift. Explicit generated
   steps stay below 500 KB and every action is seen by the existing pins/step
   guards. No YAML anchors, new provider, extra account permission, external
   notification message or automatic workflow enable/dispatch from the code.

6. **Real, unarmed canary through the same seams.** An explicit canary creates no
   scientific enrollment and makes zero Vendor requests. Its synthetic transport
   is selected only by the trusted canary path, carries a distinct namespace and
   disclosure, and is excluded from live admission/readout. It uses the same
   clock/adapter/intent-upload/result-upload/reconstruction paths for three real
   quarter-hour slot opportunities across two jobs. Preserve actual UTC timings,
   handoff, per-generation receipts and source pins. The readiness bar is all
   three distinct pairs preserved/reconstructed, no duplicate/replayed slot or
   changed clock, every acquisition beginning within sixty seconds of its due
   time, no publication or promotion into scientific/usage evidence, and no
   inference that thirty minutes proves forty-eight-hour reliability. One finite
   actual canary is authorized for deployment verification; do not retry it merely
   to obtain a green result. Fast fake-clock acceptance additionally proves the
   full 193-slot schedule, failures, clock jumps, replay and segment handoffs.

7. **Failure visibility and safe closure.** Job summaries and artifacts distinguish
   no run/no attempt, attempted-unavailable, outside-window, failed persistence,
   late sampling and complete observed data. A failed canary readiness bar signals
   failure after evidence is saved. Abnormal/terminal paths leave explicit last
   durable references and no further Vendor call; finite execution does not rely
   on a desktop wakeup to stop. The shipped workflow cannot silently reactivate a
   cron or old terminal study. Final reporting is read-only.

8. **Contract and gates.** Acceptance is committed alone first and is red against
   the parent source. Run the project’s actual configured complete runner and the
   focused module with UTF-8, native exit captured, safe external temp, exact-head
   source bindings and before/after tracked-byte inventories. Obtain fresh ordinary
   and adversarial review, actual feature Linux and both locked build evidence,
   post-integration checks and actual master checks. The parent owns heavy-gate
   scheduling, integration, publication, read-back and the finite actual canary.

## Evidence required for READY

Tests-only and implementation SHAs; meaningful parent-red output; exact acceptance
command; every relevant existing test conflict; a deterministic generated workflow
check and byte count; fake-clock full-run/late/replay/transport-bound witnesses;
zero real Vendor requests; complete configured gate/native exit/byte inventory;
per-criterion evidence and explicit remaining operational verification. Preserve
all failed attempts and do not amend/rebase pushed commits. Stage named files.

## Threat model

Realistic failures include missed admission, a job dying after one physical call,
duplicate/rerun dispatch, a dangling intent, out-of-order opaque IDs, stale/partial
API pages, malicious or foreign Artifact metadata, source or cohort drift, a
segment killed at its deadline, UTC clock changes, hidden test steps, synthetic
data reaching live interpretation, leaked addresses in logs, and scientific
coverage falsely inferred from green infrastructure. Exercise these boundaries
with bounded local fixtures; no production attack, new Vendor probe, or unrelated
blocked security-review retry is authorized.

## Amendments

None.
