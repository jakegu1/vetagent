---
id: T-043
title: Start and preserve the pre-registered RugCheck 48-hour CI observation
status: ready
level: 3
size: M
depends_on: [T-040]
decisions: [E11, E32]
backlog: W57
design_base: 66ffa4e17fa79628e779a084877bda1f92b31b5a
---

## Goal, benefit, cost and stop rule

Make W57 startable on CI, with bounded jobs and durable Artifact checkpoints rather
than a laptop process. Preserve its original inference rule. This is one measurement
instrument task, followed by a small CI-egress pilot and one explicitly started study.
Implementation, tests and reviews can proceed under the existing technical approval;
there is no additional Owner decision or spending/provider approval in this task.

Stop vendor requests after a failed pilot, fewer than forty qualified recruits,
terminal failure, source-version mismatch or study completion. Never restart or recruit
from a cron event. A missing/expired Artifact means idle or an explicit unavailable
history, never a new study. Root can disable the independent workflow after terminal
readout to avoid idle jobs continuing indefinitely.

## One proposed design

Add an independent small driver which imports T040's observe(), age_minutes(), band(),
MAJORS and source constants. Leave rugcheck_coverage_probe.py and its historical report
contract unchanged. Use a standalone workflow with workflow_dispatch (pilot/start/report)
and a fifteen-minute cron for resume-only ticks. Use the existing pinned checkout,
Python and upload-artifact actions and explicit ubuntu-24.04. Use only contents: read
and actions: read. Artifact transport uses the existing GITHUB_TOKEN and GitHub's
control plane, with no new data provider, key, package, repository write or permission
increase. Do not add a download action or broaden the action allowlist.

Use one workflow-wide concurrency group, cancel-in-progress: false. Reject another
start while any study is active, and reject reuse of an existing study ID. Manual
start must name a successful pilot Artifact from a preceding CI run. It first proves
cross-run restoration with current read permissions, then recruits. Pilot failure or
unavailable Artifact access cannot silently authorize recruitment.

Each checkpoint is immutable: state.json, manifest.json and this job's observations.jsonl.
State includes the frozen cohort with its enrollment records, initial source head,
schema version, hashes of driver/probe/workflow bytes, start/end clocks, completed or
missing slots, parent Artifact ID/digest and prior chunk IDs/digests. Retain old chunks;
never overwrite them with a later successful observation. New default-branch heads are
allowed only if all three implementation hashes are identical; otherwise terminal
source_changed. No automatic migration, cohort substitution or renewal occurs.

Before a job makes vendor requests, upload a bounded intent checkpoint naming its
parent and claimed slot. If intent persistence fails, make no vendor calls. After
collection, an always() upload preserves available partial rows and a final checkpoint
before the job signals failure. A later tick finding an intent without its completed
result marks the affected cells unobserved/lost_checkpoint and stops the study; it
does not replay the slot. A runner destroyed before upload can lose its current local
rows; this remains explicit lost observation, never a successful negative measurement.

## Exact implementation scope and conflicts

1. New bench/rugcheck_w57_ci.py: pure state/cohort/slot/readout functions, bounded
   Artifact adapter and explicit pilot/start/tick/report CLI. No daemon or engine code.
2. New .github/workflows/rugcheck-w57.yml: the independent workflow above. No existing
   snapshot/production/test trigger or live job condition changes.
3. New tests/test_rugcheck_w57_ci.py: network-free, deterministic acceptance tests with
   fake UTC clock, probe transport and Artifact service. Commit this file first, red.
4. .github/workflows/test.yml: one unconditional offline test-job step invoking the new
   test file. Preserve all prior jobs, steps, commands, conditions, pins and runners.
5. tests/test_workflow_runtime_pins.py: the named existing-policy amendment only:
   WORKFLOWS adds rugcheck-w57.yml while retaining all six existing entries; replace
   policy_errors()'s exact-six diagnostic and test_known_valid_action_and_runner_forms_pass()'s
   six-workflow control label with the corresponding seven-workflow wording. Keep the
   exact-set equality, actual-directory traversal and every other assertion unchanged.
   Root explicitly approved this narrow conflict amendment.

Conflict search found no existing W57 driver or workflow. Existing T040 tests cover
recruit_fresh(), run_probe(), historical report(), offsets, future dates and append/restart
pairing; preserve them byte for byte. tests/test_risk.py::_settling_figures and
test_the_settling_figures_in_the_engine_are_the_measured_ones read the six-hour reference;
do not replace it or change their assertions. test_every_test_file_runs_in_ci requires
the new registration. The workflow pin guard requires the exact seven-file amendment
above. The deploy inventory guard consumes test.yml, so the new unconditional step must
remain executable through the ordinary inventory. No change to these guard bodies is
authorized beyond the named pin-policy amendment.

## Acceptance criteria

1. **Explicit state machine and source provenance.** Default CLI is offline/help.
   Only explicit pilot or start can create a study; cron is resume-only. Test missing,
   expired, malformed, wrong repository/workflow/default-branch provenance, incompatible
   schema, source-hash drift, duplicate start and duplicate/overlapping slot cases.
   They make zero vendor calls and do not overwrite prior artifacts. Use only read
   CI permissions. Tokens, signed Artifact URLs and token identities never enter console
   logs; public-source mint identities exist only in the measurement Artifacts.

2. **Small CI-egress pilot first.** One GeckoTerminal new-pools page and exactly the
   first six established MAJORS in their existing declaration order, at the existing
   two-second gap, with at most one RugCheck request per mint and no retries. Pilot is
   bounded to five job minutes. Operational launch guard: a readable HTTP-200 listing,
   six attempted and six usable HTTP-200 finite-score reports with readable, nonfuture detectedAt, plus
   successful Artifact persistence/restoration. Otherwise terminal pilot_failed with
   all HTTP/body/field statuses preserved. This is an instrument-health guard, not a
   change to W57's scientific decision rule. These fixed established controls test CI
   egress without conflating a newly listed mint's unindexed state with transport failure.
   Start must independently recruit its fresh cohort; it cannot use pilot observations
   as fresh enrollment. The same MAJORS remain established controls in later sweeps.

3. **Fresh frozen cohort, retaining enrollment evidence.** Explicit start requests up
   to eight new-pool pages, examining at most thirty distinct candidate mints per page
   and 240 total; disclose skipped/duplicate/truncated candidates. Recruit up to the
   existing target of forty-five fresh mints, with the existing minimum forty. For each
   enrollment retain its own HTTP/body envelope, observed UTC timestamp, detectedAt,
   computed age and score availability. Require 0 <= age <= ten minutes at that actual
   enrollment observation, using T040 age parsing. This is upstream indexing age,
   never pool/token age. Preserve failed and rejected enrollment attempts too. Fewer
   than forty after the request or twenty-minute job bound is terminal insufficient_cohort;
   no long run starts. Freeze members and enrollment ages; subsequent report parsing
   must not re-enroll them from a later first-successful sweep. Keep the eighteen
   established MAJORS as W57 controls, distinct from the forty-five fresh members.

4. **Real elapsed duration and bounded slots.** The study lasts forty-eight elapsed
   UTC hours from its recorded start clock, with nominal fifteen-minute slots, including
   the initial and terminal boundary: at most 193 sweeps, at most 63 mints per sweep.
   Duration is never counted from successful observations or successful jobs. Each tick
   attempts at most one due slot, with an eight-minute job limit and six-minute vendor
   work budget, retaining time for Artifact upload. Retain the existing two-second gap
   and thirty-second request timeout; do not begin another call without sufficient
   remaining budget. Record actual scheduled/due/start/response times and unavailable
   cells. Missed slots remain not_observed; no burst catch-up or invented historical
   sample. A terminal acquisition started late may retain its actual endpoint with a
   lateness flag. Its operational acquisition deadline is the scientific end plus one
   nominal fifteen-minute interval; no call begins unless its timeout and gap fit before
   that deadline. The scientific window still ends at forty-eight hours: later responses
   are separately outside-window/censored and cannot establish an in-window flip or
   a negative tail. After that deadline no further vendor calls occur. A late or
   absent boundary observation cannot be represented as exact forty-eight-hour coverage.

5. **Observation integrity and durable partial results.** Reuse T040 HTTP/body/field
   validity. A refused, transport-failed, empty, malformed or invalid-score reply cannot
   vote as clean, dangerous, absent holders or an observed negative. Separately valid
   fields remain available. Stable (study, slot, mint, attempt) IDs prevent double
   counting. Test real driver -> probe.observe -> persisted chunk -> restore -> readout
   with synthetic 429/error bodies, invalid scores, valid positives/negatives, interruption,
   intent-only state, upload failure, and valid resumed observations. Prior chunks stay
   byte-exact. Missing scheduled jobs and failed requests appear separately in coverage.

6. **Bounded Artifact handling.** Accept only the expected repository, exact workflow,
   default-branch trusted runs and fixed study/source/schema. Verify IDs, parent chain,
   digests, expected file set, counts, duplicate IDs and path safety before use. No
   arbitrary zip extraction. Per intent: at most 64 KiB; each result bundle: at most
   one MiB compressed and uncompressed, with at most four entries; state: at most 64 KiB.
   Normalize only the predeclared W57 measurement fields (identity, timestamps, HTTP/body,
   raw numeric score or explicit invalid-field metadata, detectedAt and gated powers),
   not arbitrary upstream prose. Oversized input or state is terminal unavailable,
   retaining already written measurements and an explicit overflow receipt. At most
   five metadata pages and two checkpoint downloads per tick; no unbounded history scan.
   Report restores at most 195 result chunks with a finite request/time budget. Use
   seven-day retention and include parent/checkpoint metadata in each bundle so state
   can be audited and exported before expiry. Artifact expiry never recreates a study.

7. **Original inference rule only.** Readout binds the fixed enrolled population, wall
   duration, actual observation gaps and per-field denominators. Use the existing score
   bands (clean below twenty; warn at twenty; critical at fifty), and report observed
   clean-to-dangerous events with both index-age and study elapsed timestamps. Preserve
   the original W57 rule: latest flip within the run implies a proposed larger settling
   lower bound with censoring still stated; flips in the final tenth imply proposing
   the different Solana clean-score rule for its own E14 review. Forty-eight hours and
   the final tenth are time bounds, never a fraction of successful rows. Missing late
   observations do not establish settling or a negative tail. Retain crossing intervals
   and censoring when outages hide the actual transition time. No automatic engine,
   established-clause, taxonomy, constant, public claim or benchmark update occurs.

8. **Tests first, frozen contract and quality.** Add characterization and red-before-fix
   tests for every seam above, with the permitted pin-policy fixture amendment in the
   first acceptance commit. Freeze all new acceptance assertions thereafter. Demonstrate
   at most four bounded meaningful mutants: lost enrollment age, reset elapsed clock,
   failed observation counted as clean, and missing state auto-recruiting. Restore exact
   bytes. Run focused component/registration/pin checks, then one actual complete ordinary
   configured inventory in a root-granted exclusive slot. Preserve exact source, red/green
   commands, exits, log hashes and artifact-schema fixtures. Fresh independent plus
   adversarial review and actual Linux verification precede real pilot/start; no live
   request is required from the executor's deterministic acceptance tests.

## Request, runner and storage ceilings

Data-source calls, one pilot plus one study, no retries:
- Pilot: one GeckoTerminal plus six RugCheck calls.
- Enrollment: at most eight GeckoTerminal plus 240 RugCheck calls.
- Sweeps: at most 193 * 63 = 12,159 RugCheck calls.
- Total: at most 12,414 data-source calls (12,405 RugCheck; nine GeckoTerminal).
  A wall budget can stop below these ceilings, which remains explicit partial coverage.

GitHub control-plane reads are bounded independently: at most twelve per active
collection job and at most six hundred for final reconstruction. No vendor retry loop
or paid tier is introduced. Pilot five + enrollment twenty + 193 ticks of eight + final
readout fifteen gives 1,584 runner-minutes as a conservative active-job timeout ceiling,
not a prediction of billable minutes. Idle cron jobs are additional until root disables
the terminal workflow. At most 195 intent/result pairs plus a one-MiB report bound
Artifact payload storage below 209 MiB for seven days. Platform accounting, available
CI allowance and egress availability are runtime facts, not claimed free capacity.

## Real remaining gates and handoff

No repository mutation, test execution or upstream/CI request was made in this design
pass. Root already has official Artifact sources; executor should use those, not open
another research track. Current permissions' cross-run Artifact access, upload/restore
behavior, schedule delay, free-source CI egress and account headroom remain unmeasured
here. The approved pilot and startup checks make these operational facts visible and
stop safely if unavailable; they do not create a new Owner waiting point.

After reviewed implementation and actual Linux checks, root dispatches pilot, reads its
receipt, then explicitly dispatches start referencing that pilot. Root records the
actual cohort/start Artifact and checks that the first resumed tick runs. Root checks
the terminal report and disables the independent workflow. Artifact retention is finite;
export evidence before expiry. A failed/underpowered study stays terminal and W57 stays
open; any later cohort needs an explicit new start and ID.

W54 is entirely out of scope. Its missing original sixteen-mint set is not replaced by
the eighteen MAJORS used here as W57 controls. Keep the original six-hour JSONL, all
benchmarks/caches/reference bytes, T040 tests, thresholds and production source untouched.

## Pre-test clarification

2026-10-19 (a): define the previously unnamed terminal acquisition deadline as one
nominal interval after the scientific end. This is a bounded scheduling grace only;
the original elapsed scientific window, final-tenth bounds and inference bar do not
move. Responses after the scientific end remain outside-window observations. Apply
this clarification before freezing the first acceptance-test commit.

## Named first-review correction

2026-10-19 (b): first-round independent and adversarial review of
8b927582fc5478cd71f7460c4edadb475f1de569 found five related evidence and recovery
defects despite the actual 43-step offline gate passing. Correct these in one bounded
second implementation round. This corrects the data supplied to the original inference
rule; it changes no score band, duration, final-tenth boundary, enrollment rule or
production policy. Do not publish the reviewed defective head.

Add exactly five regression methods to tests/test_rugcheck_w57_ci.py, committing the
tests before the repairs. Use these names and exercise the actual CLI/observe/persist/
restore/readout seams with only clock, vendor and Artifact transports substituted:

1. test_readout_discloses_groups_field_denominators_and_unattempted_gaps:
   disclose both fixed populations, scheduled/missing slots and actual observation
   intervals. For score, detectedAt, holder count and each retained gated field,
   distinguish usable fields, attempted but unavailable/invalid fields, outside-window
   readings and never-attempted cells. A budget-limited sweep with eleven actual calls
   must not count its thirty-four unasked fresh cells as failed requests. Control-group
   failures must affect the control coverage report. Missing or nonboolean source
   powers must not acquire an observed false value merely through normalization, and
   negative/nonfinite holder values must not become valid holder observations. Preserve
   separately usable fields when another field fails. These are availability statements,
   not additional signals or new policy thresholds.
2. test_cli_interruption_preserves_a_restorable_partial_checkpoint:
   prepare and persist intent, flush measurements through the real observe seam, then
   interrupt collection before normal finalization. Package the exact upload directory,
   decode, restore, resume and reconstruct. Preserve verified partial measurements and
   a coherent terminal receipt, or explicitly retain unverifiable raw evidence separately
   and record lost observations. No corrupt zero-row manifest may shadow flushed rows;
   no new vendor request may replay the interrupted slot. Earlier bundles remain exact.
3. test_intent_only_terminal_checkpoint_reconstructs_without_replay:
   publish an intent, omit its result, prepare and publish the next terminal checkpoint,
   then reconstruct the report. Preserve the lost intent's ID/digest, missing slot,
   frozen population/source and valid prior result chain. Report the loss and censoring
   without a history_chain exception or a vendor retry.
4. test_crossing_intervals_do_not_assert_a_right_endpoint_as_a_lower_bound:
   retain both elapsed and index-age interval endpoints. A clean observation before
   the final-tenth boundary, intervening unavailable/missing cells and first dangerous
   observation at forty-four hours cannot locate the transition inside the final tenth.
   Its report remains inconclusive about that policy proposal, exposing the ambiguous
   crossing instead of asserting a definite tail event. Do not label the right endpoint
   as a lower bound. Any numeric lower bound must be supported by the last verified
   clean endpoint and compatible indexing-origin evidence; otherwise it is unavailable.
   Include an interval wholly within the final tenth as the positive control. Preserve
   the original forty-eight-hour and 0.9 bounds and outside-window exclusions.
5. test_normalized_overflow_preserves_prior_rows_and_an_explicit_receipt:
   after one ordinary flushed response, an oversized normalized finite integer raises
   the existing row bound. Retain the prior row and a valid restorable terminal bundle,
   plus a bounded explicit overflow reason/receipt identifying the lost observation.
   Do not raise the row, bundle, state or request ceilings to make this example pass.

Exactly one old acceptance assertion is corrected by name: in
test_readout_uses_fixed_time_final_tenth_and_marks_late_or_missing_samples_censored,
replace the expected proposal different_rule_e14_review for the existing wide
early-clean/late-dangerous interval with inconclusive. That fixture spans almost the
entire study and cannot locate a tail transition. Preserve every other existing test
statement, fixture and assertion in that method and all fourteen other original
methods byte-for-byte. No change to the pin-policy test, T040 tests, historical reference,
workflow guards, engine or scientific bar is authorized by this amendment.

Keep the implementation repair within the original driver/workflow scope. Separate
commits per reproduced finding may share the preceding tests-only commit. Record each
red's native exit and failing assertion, the exact old/new test delta, prior evidence
hashes and controlled restoration proof. Re-run focused checks and one root-granted
exclusive full inventory on the frozen repaired head. The second fresh review covers
all named corrections, the CLI seams and preserved invariants before Linux, pilot or
start. The two-round review cap still applies.

2026-10-19 (b2): before the repaired head's full gate, the lead reproduces a regression
on 3ee244197a055002ce25cf61261fe19f2649b2d4: strict-Boolean-only capture discards the
existing permanentDelegate object and freeze/mint public-key forms. The unchanged
probe observes these positive powers; the new capture changes them to unavailable.
Existing risk tests and engine source already use these domain shapes. Preserving
availability must not silently remove meaningful existing signals.

Permit exactly one additive self-contained block at the end of the new
test_readout_discloses_groups_field_denominators_and_unattempted_gaps method.
Preserve every previous statement/assertion in order, all other new methods and the
original fifteen-method contract including its sole named proposal correction.
Commit this block alone and reproduce the existing-domain red before the repair.
Cover supported permanent-delegate/close-authority objects, pausable configuration
objects and freeze/mint public keys through real observe, normalized row, persistence,
restore and field coverage. Retain their usable declared positive power observations.
Explicitly supplied schema-valid null/no-authority values, genuinely missing fields
and malformed values remain distinguishable; an arbitrary truthy string such as
false is not authenticated as a public key or configuration. Use the existing engine/
fixture source shapes and no new signal, policy, score, permission or provider.

Keep the repair inside the same-response capture/normalization helpers in the driver;
do not modify T040, engine helpers, old tests or references, and do not add a request.
This is the same bounded second implementation round, not a third review round.
Freeze the new corrected head and run its own focused/full evidence before the
fresh combined second review. Keep the prior clean-head evidence with its original
source identity; it does not certify this later source.
