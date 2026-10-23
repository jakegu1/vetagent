---
id: T-060
title: Bind finite W57 sessions and the real pilot to the new192-start protocol
status: in_progress
level: 3
size: M
depends_on: [T-059]
backlog: W57
design_base: 952288b586a60b9bc9104eae2193c67a68252c3b
---

## Context, goal, benefit, cost and stop rule

The Owner approves a NEW independent192-start W57 study after the separately scoped T058 instrument/per-probe/partial-native repair prompted by four historical RugCheck HTTP400 readings, new protocol implementation, fresh review and a real qualified pilot. The lead reports sixteen fresh HTTP200 responses, two instrument-capped bodies, and missing historical failure identities; these do not explain the historical400cause or qualify the future new source automatically. Old studies remain inconclusive and immutable. T059 supplies explicit immutable policy selection and legacy-compatible science; this task makes the existing finite session transport and workflow execute the NEW protocol without changing the old default or promoting a canary/old pilot into new evidence.

Benefit: one explicit launch and bounded running jobs preserve fixed opportunities without relying on repeated cron admission. Cost: one bounded session/workflow task plus the already authorized new real pilot and study. Stop Vendor requests on failed pilot, insufficient cohort, terminal source/clock/protocol/persistence failure, physical budget exhaustion or completion. Never retry merely to obtain a green pilot, restart a failed study, extend the window, or fill old gaps. Closure/reporting after48h is read-only and may preserve evidence without making Vendor requests.

## Scope and files

1. `bench/rugcheck_w57_session.py`.
2. `.github/scripts/render_w57_session_workflow.py`.
3. Generated `.github/workflows/rugcheck-w57.yml`.
4. Additive `New192SessionTests` in existing `tests/test_rugcheck_w57_ci.py`.

T059 core/protocol contract is a dependency, not a file to patch opportunistically. If its contract blocks this task, return a concrete mismatch to the lead. No new workflow or registered test module. Keep production, other workflows, sources/terms, original data, pre-registered scientific/pilot rules, dependencies and permission files outside scope. Lead governance records are separate from this private draft.

## Explicit entrypoints

Add explicit new modes, suggested `pilot192`, `start192`, `report192`, selected from trusted mode/protocol handling and passed via environment variables. Preserve old modes/default LEGACY193 behavior and `legacy-report`; help/default remains offline and the workflow safe default remains unarmed canary. The workflow remains manual-only, one fixed concurrency group, no cancellation of a running study, no auto-dispatch/recruit/restart.

Use v3 intent/result/admission/report names and transport marker carrying the canonical protocol ID/digest. New pilot and new study use the same exact source freeze and protocol; admission rejects an old/synthetic/current-run/different-source/different-protocol/expired/unavailable pilot. Preserve original cross-run Artifact restoration and run-attempt-one controls. Source freeze contains all five executed raw sources; the protocol capsule is inside the frozen core and its canonical descriptor/digest is also bound explicitly.

Keep the single generated workflow and its existing legacy193graph; conditions expose exactly slots0..191 to `start192`, while the old explicit start graph keeps0..192. Do not duplicate every job/step graph. Slot192 is unreachable from the new mode, not an idle successful scientific point. At most ten sampling segments plus closure, each job<=330minutes with current five-minute preservation reserve and at most twenty opportunities. No YAML anchors or hidden action arrays.

## Conflict search and named changes

No existing acceptance assertion changes are authorized in this task. T059 separately names the sole driver-byte assertion amendment. Retain default compatibility in:

- `RunningSessionTests::test_source_freeze_covers_every_executed_control_and_legacy_bytes` as amended by T059.
- `test_full_193_slot_schedule_uses_absolute_time_and_ten_finite_handoffs`.
- `test_missed_due_is_explicit_and_never_replayed_or_backfilled`.
- `test_clock_jumps_source_changes_and_job_reserve_stop_without_vendor`.
- `test_versioned_metadata_is_validated_before_normalizing_or_downloading`.
- `test_dangling_intent_and_failed_persistence_close_without_another_acquisition`.
- `test_v2_manifest_source_and_parent_chain_reject_corruption`.
- `test_slow_live_phase_keeps_unavailable_and_unattempted_cells_distinct`.
- `test_unarmed_canary_three_real_intervals_cross_two_jobs_and_never_enters_live_readout`.
- `test_admission_combines_v1_v2_history_and_three_distinct_bounded_proofs`.
- `test_final_phase_clock_drift_cannot_pass_readiness`, `test_canary_readiness_requires_every_matching_intent`, `test_canary_rows_cover_exact_frozen_cells`, `test_completed_run_requires_successful_conclusion`, `test_run_attempt_boolean_is_not_integer_one`.
- `test_generated_explicit_workflow_is_manual_finite_default_canary_and_drift_guarded`.
- `StudyTests::test_workflow_is_independent_read_only_pinned_and_preserves_before_failure`.

Search every use of workflow/Artifact/namespace/schema/protocol/source/run/prepare/finalize/finish/closure literals and every generated-step scanner before first test commit. Preserve `tests/test_workflow_runtime_pins.py` exact seven-workflow inventory, pins and validation; `tests/test_deploy_gate.py` scanners and `tests/test_decisions_enforcement.py::test_every_test_file_runs_in_ci` stay unchanged. If a genuine conflict needs amendment, name its exact old/new expectation before freezing acceptance; do not weaken the guard.

## Acceptance criteria

1. **Explicit v3 protocol binding and safe defaults.** New modes select only the immutable T059new protocol and pass it explicitly through context, source composite, validation, prepare/admission, collect, bundling, decode, restore, reconstruction and closure. Reject unknown/mismatched protocol/descriptor/digest/schema/source before Vendor calls. Old defaults/v1/v2 reports and source semantics remain compatible. New Artifact names never overwrite old names. Global used/active study admission spans v1/v2/v3 and fails closed on unresolved/partial history. No monkeypatch or implicit migration.

2. **Exact finite new schedule.** A fake-clock traversal of the actual generated new CLI graph gives exactly192distinct slot opportunities0..191 with frozen absolute UTC due times and no193rd call; legacy graph still gives193. Keep at most11jobs,20opportunities/segment,330minute hard timeouts,300second reserve,<=30second waits, monotonic/UTC drift checks and final-operation clock proof. New acquisition obeys strict response deadline `T0+48h` with no grace. Late/omitted/failed operations are preserved as such; no replay/catch-up or reset. Final index191can terminalize the planned schedule without implying an observed48h endpoint. Closure/report afterend makes zero Vendor calls.

3. **Original immutable transport and bounded proofs.** Preserve durable-intent-before-call, always-finalize/upload-before-failure, exact parent/ZIP/manifest/source/run/generation/protocol binding, opaque IDs, path safety, exactly-once/rerun refusal, partial-journal and lost-checkpoint closure. Admission remains<=16counted reads/3ZIPs/110seconds; ordinary phases<=12reads/2ZIPs; report<=600reads/195ZIPs/720seconds. Preserve64KiBstate/intent,1MiBbundle and row/count bounds,seven-day retention. Cross-protocol/foreign/expired/ambiguous/dangling/failed completed-run evidence cannot qualify or silently disappear from active history.

4. **Source-bound real pilot and separate recruitment.** Keep the pilot exactly one readable HTTP200Gecko new-pools page plus the first six MAJORS, one RugCheck request each with existing pacing/no retries. All six need usable HTTP200finite-score/nonfuture readable detectedAt and persisted/restored evidence; otherwise terminal pilot_failed. Successful new pilot must come from a different preceding CI run with the same exact new protocol/source. Start independently recruits using unchanged<=8pages/30distinct candidates/page/240total,target45,min40,0..10minute enrollment age and all18controls. Underpower never starts T0. Retain failures/skips/truncation. A real pilot proves access/restore only, not48h reliability or guaranteed recruitment.

5. **Readout and failure visibility.** Reconstruct actual new rows through the T059new readout with192fixed denominators, fresh/control field states, scheduled/actual timings, missing and outside-window cells, individual last usable timestamps and endpoint censoring. Job success/configuration is never asserted as sampling completeness. Retain original20/50bands/latestflip/finaltenth/proposal rules. Preserve old reports/results exactly under their old protocol; no engine/public/benchmark policy update. Failure records expose the last durable references and stop further Vendor work without a desktop wakeup.

6. **Generated workflow and acceptance first.** Commit additive acceptance alone, meaningful red on parent before implementation, then freeze it. Rendering/check mode is deterministic and<=500KB; inputs travel through env; safe default canary, manual-only trigger, pinned actions/ubuntu runtime, read-only contents/actions, no persisted checkout credentials, no new secrets/provider/permissions and all preservation ordering stay intact. Existing pin/step scanners see every generated action/command. Use at most four bounded meaningful faults: new slot192enabled, v2pilot promoted, wrong protocol digest admitted, post-end response counted usable; restore exact bytes and prove healthy legacy/new/canary behavior. No real requests from executor tests.

7. **Independent delivery evidence.** Fresh ordinary and adversarial reviewers independently exercise the real generated graph/seams, original regressions and new boundaries; the spec author/implementer is ineligible as fresh reviewer. Provide tests-only/implementationSHAs,parent-red/focused-green/native exits, before/after source seals, per-criterion evidence, transport/call-budget witnesses and zero-real-request statement. Root schedules serialized complete configured Windows checks and exact-head Linux/build/integrated/master checks, source publication and read-back. Do not repeat heavy gates without a new failure/change requiring them.

8. **Operational launch/readout gates.** After the four-HTTP400repair has its measured evidence and reviewed source is integrated/published/read-back, root runs one NEW source-bound real pilot, restores and inspects its actual receipt, then explicitly starts one new ID only if the existing pilot/active-history/cohort/runtime-budget gates pass. Preserve pilot/start failures without automatic retry. Verify actual initial sweep and first physical job handoff without counting self traffic as usage. Final reconstruction/export verifies immutable rows, actual192denominators, crossings and right-censoring; export seven-day evidence before expiry. Keep old studies inconclusive and never backfill/extend/rename them. No additional routine Owner approval is introduced by this task; changes to other gates, money/legal/privacy/public claims remain outside scope.

## Cost and evidence limits

Existing pilot+enrollment+new study ceilings:6+240+192*63=12342RugCheck;1+8=9Gecko;12351total, no retries. Preserve phase wall budgets, so actual acquisition can be lower with explicit missingness. Bound timeout/account costs from the generated graph and current verified headroom, not from assumed free capacity. Seven-day retention is finite and cannot be treated as long-term archival.

No extra real canary is authorized by this spec solely to chase green; the existing canary remains unarmed and covered by deterministic compatibility tests. The newly required real pilot is the qualification measurement. Pilot/start actions require exact source/protocol evidence and root control; executor and reviewers stay network-free.

## Threat model

Accidental old-study restart, same-run/old-source pilot reuse, protocol digest omitted from a composite, source drift after final pacing, hidden new index192, workflow generated but different from execution, incomplete listing forgotten by admission, malformed/provenance-confused v3 objects, expensive duplicate graph, final raw response crossing48h, and a complete192schedule represented as continuous48h evidence. Preserve original thresholds and all failure evidence. Never trade inference integrity for a green delivery report.

The author of this spec must not be its fresh independent reviewer.

## Amendments

2026-10-23 A1, before acceptance is authored: fix the global admission proof
contract explicitly. New-protocol admission scans all six exact selectors
(v1 intent/result, v2 admission intent/result, v3 admission intent/result),
with at most eight total metadata pages and at most two pages per selector;
legacy admission retains its five-page cap. All total16-read/three-ZIP and
110-second admission bounds, ordinary12-read/two-ZIP bounds and report limits
remain unchanged. Partial, changed, excessive or ambiguous pages fail closed;
do not silently skip an old namespace to fit a budget.

A provenance-verified terminal admission index may carry the cumulative
used-study ledger instead of independently downloading every version's latest
root. Verify its immutable binding, parent/history coverage and terminal state.
Examine every metadata stream for unresolved intents, active or conflicting
history. An older unresolved stream is not cleared merely because another
terminal index is newer. If closure/coverage cannot be proved within the
existing three ZIPs, return unavailable without another download or launch.
Freeze this seam in additive acceptance, including mixed old/new history,
older unresolved history behind a later index and explicit budget refusal.
No existing assertion change or new scientific gate is authorized by A1.

2026-10-23 A2, before acceptance is authored: the six-selector global admission
contract applies to the explicit new pilot192/start192 entries. Those entries
must examine v1/v2/v3 history together under A1. Legacy defaults retain their
original four-selector/five-page behavior, historical readers and source
semantics; a legacy reader must not interpret schema3. This continuation
authorizes no real legacy pilot/start. Preserve the shared workflow concurrency
group. No existing assertion, scientific rule or transport ceiling changes.

2026-10-23 A3: correct only the new acceptance helper
`New192SessionTests.memory().Store.publish`. Its inherited legacy fixture
rejects the same fixed admission name across different runs, whereas the
production adapter validates duplicate publications by `(run_id, name)`.
Implement the new helper's publication with that exact uniqueness pair,
retaining opaque IDs, exact ZIP/metadata/source binding and timestamp behavior.
Same-run duplicate names must still fail. Preserve every acceptance input and
assertion, every old helper/method, and the original parent-red receipt. Record
this as a separate `T-060: acceptance test fix (A3)` commit before proceeding.
No source behavior, scientific bar or permission is changed by this amendment.

2026-10-23 A4: replace only the initial healthy-terminal fixture block in
`New192SessionTests.test_global_six_stream_admission_blocks_older_unresolved_and_foreign_pilots`.
The fixture currently leaves an admission intent in run300 and fabricates a
terminal result/index in run301 without closure proof; A1 correctly refuses it.
Changing only the context would collide with the existing run300/g000 result.
Instead invoke the actual `closure` operation under the existing fake Artifact
service in the original run300, restore its rescue through `_local` with the
explicit new protocol, and publish/index that rescue under the original context.
The real closure supplies the next generation and verified parent/chunks and
terminal loss evidence. Keep every assertion, all later inputs and the old
run200 dangling-intent rejection unchanged. Preserve the earlier fixture failure
and record a separate `T-060: acceptance test fix (A4)` commit. Do not weaken
source admission, add a retry, or accept a newer unrelated index as closure.

2026-10-23 A5: add a frozen regression for direct `reconstruct`, `_local`,
`finalize` and `closure` helper calls with conflicting legacy/new contexts,
protocols, namespaces or phase selection. Each must reject a conflict before
constructing or using any GitHub or Vendor transport; required bounded local
validation and failure preservation may still occur. Trap every transport in
the regression, not only Vendor calls. Preserve all previous assertions.

The initial private probe attempted a synthetic-repository GitHub read when its
closure transport trap was missing. Record that attempt honestly; zero Vendor
calls does not mean zero transport attempts. Retain the unreviewed fix1fcd87f
and its original probe evidence on the existing branch. On a separate branch
from6c821c5, adopt this amendment, commit the additive A5 test alone, reproduce
its red under complete traps, then normally cherry-pick the identical source
repair. No history rewrite, deleted failure or checker change is authorized.


