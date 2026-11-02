---
id: T-073
title: Dispatch complete historical tests and retain contemporary adapter regressions
status: ready
level: 3
size: M
base: 9b83558481ae54afd5fc4e9b59c9cb27caa0e3d6
depends_on: [T-071, T-072, ADR-0003, root-NC3-NC4-decision, independent-design-review]
---

## Root adoption and precedence

Root accepts the exact NC3/NC4 design after independent functional and bounded
provenance review, with the observation amendment below taking precedence over
the original stronger descendant-telemetry condition. Conditional wording below
describes the reviewed proposal; its selected commands and contexts are now
formally adopted. It is not source/runtime/47-command acceptance.

The ordinary technical scope is covered by the Owner-approved ADR0003 split.
Tests-first implementation is authorized only by the separately bound root task
base. Root issues its actual metadata-commit SHA as the tests-first range base;
the frontmatter code base remains the published9b source. Do not use a range
that accidentally includes root's earlier administrative commits as tests-first.
Heavy execution, workflow registration, pushes and publication remain root-owned.
Focused offline version tests may run the single required historical dataset
child once per version suite; complete native/clock runners are reserved for
the separately granted full47 windows. New unit positives use tiny fixed spies.

## Context and observable goal

The Owner's exact V1/current-production separation is approved. T072 is now
published at9b83558 with actual qualified feature/master CI. Its first natural
snapshot qualification is still pending and belongs to the unique root watcher.
The release checkpoint supersedes older pending paragraphs in RESUME/STATE for
current code-release facts; those originals are not edited by this design.

The actual gate must run both complete original native runners under the exact
V1 identity, both complete current/historical dataset runners, the contemporary
T072 data regressions, and all unrelated current production checks. Evidence must
identify the source domain and actual child exit for each obligation. A repaired
production V2 must still be rejected by the original historical native predicate.
No successful V2 native compatibility is promised.

Root has adopted the named resolutions for two concrete conflicts: NC3, the
existing valid legacy-test rejection vector; and NC4, current T072 fixtures
reaching FROZEN on a genuinely changed V2 source. The observation amendment below
also resolves the independent design finding. Tests-first implementation requires
the separately issued root task-base plan; source/runtime acceptance remains open.

## Scope and files

Proposed executor files: `tools/engine_versions.py`, `tests/test_engine_versions.py`
and `docs/ENGINE-VERSIONS.md`. Root owns `.github/workflows/test.yml` registration
and administrative task/review files. Existing registry11, both profiles, every
original native/clock/dataset file and current T072 file stay exact. No parser,
lead/checks.py, deploy/bot/runtime-pin guard, source pin, writer/control path,
production engine, data, scientific rule or source/dependency file changes.

No T047/T049/T050 work or old partial T068 integration, research/live/native API,
price repair, telemetry transition or study restart belongs here. No current
accepted producer source may be superseded before the ordinary natural-snapshot
qualification required by root; this design neither runs nor resets its watcher.

## Fixed commands and domains

NC1/NC2 are the already approved exact replacements:

```
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native_clock.py
```

The current `python tests/test_dataset_replayable.py` remains unchanged. The version
suite additionally invokes the entire historical dataset exactly once:

```
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_dataset_replayable.py
```

Conditional NC4 adds one real configured command, not a comment/filename match:

```
python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests
```

The literal `adapter-test` is adopted in this design; it is not implemented. Its domain is
`current_adapter_on_v1_dependencies`, NOT historical V1 or production V2. It uses
a separate sealed8-member context: the six unchanged FROZEN dependency members
from the verified fixed V1 git-lf identity plus the actual candidate's current
`bench/w40_native.py` and `tests/test_w40_native.py`. Never insert or replace either
current member in the closed historical11-member view. Read current members only
from the exact clean candidate whose Git/canonical/raw identity is recorded;
there is no caller path, latest historical source or alternative test selector.
Changes to either current member require new ordinary source review. No FROZEN,
engine predicate or original test byte is patched to assemble this context.

The context runs exactly the unchanged T072 class's three methods, including its
real hardlink/cap/refusal and fresh offline recovery assertions. The original13
native and3 clock methods remain whole and V1-only in separate direct runners.
The new context does not import the repaired production V2 engine and cannot
prove V2 native interoperation. Current service and dataset checks still import
the real current production tree. The responsibility matrix spells out each ID.

## Acceptance criteria

1. **Closed sources/grammar.** Preserve all existing verify-source behavior and
   both explicit profiles. Add only the three whitelisted legacy runners and,
   under accepted NC4, the single fixed adapter class/context. Validate every
   required member before import/child and rehash after success/failure. Reject
   arbitrary version/profile/path/selector/action, absent object, alias, malformed
   member, wrong raw profile or source drift, without fetch or profile fallback.
   Existing source limits remain16 members/4MiB file/8MiB total/128KiB receipt;
   the separate8-member context fits the same limits, not an expanded V1 catalog.
2. **Actual original execution.** Run each whole historical native file once in
   the configured gate, with all13+3 test IDs, original main/harness, fixtures,
   descendants, timings, predicates, source topology and actual exits. Run the
   whole historical dataset's9 functions once inside the version suite; retain
   the unchanged current dataset's9 functions as its own current command. Preserve
   all dynamic pass/fail/not-checked counters, not only a count of functions.
   No complete native dispatch is embedded in unit tests/version-suite positives.
3. **Contemporary adapter obligation.** The separate current-adapter context
   executes exactly all3 unchanged current methods against the actual current
   corrected adapter and fixed dependencies. Record both identities, real children
   and actual exits, before/after seals and every refusal. Mutating/removing a
   selected test, substituting old adapter source, trusting staging, accepting a
   hardlink, growing15/570/byte caps or returning a fake green must go red.
   Relabeling this result as historical-original or production-V2 positive fails.
4. **Source/runtime/exit evidence.** Legacy receipts retain the accepted four
   independent layers and actual test result. The actual test interpreter must
   itself pass original code_manifest and engine_bindings before original tests;
   do not copy runtime proof from an earlier different child. Separate adapter
   receipts use the exact schema/domain in DECISIONS.md. Missing/interrupted/
   timeout/not-run work never becomes passed; propagate actual nonzero exits and
   retain bounded raw stdout/stderr/test IDs. Historical record/interpreter stay
   not_evaluated, historical_execution_qualified=false in every B1 result.
5. **Negative production boundary.** Same-byte production role is refused by the
   outer role boundary. A real changed-source scratch must trigger original native
   source_drift and a wrong loaded runtime must fail engine_bindings.9b baseline
   matching original source is not falsely claimed to trigger native rejection.
   At each later separately authorized B2 repair head, repeat the actual current
   tree's original native refusal and current production regressions; neither a
   synthetic T073 witness nor historical success substitutes for those results.
6. **Real runner coverage.** Keep the unchanged offline parser and every unrelated
   command. The conditional inventory is47 top-level commands: replace exactly2
   of46, add1 adapter command, preserve the other44 in order. Historical dataset
   is one separately evidenced nested child, not a fictitious48th workflow step.
   Prove actual execution through local/deploy/bot seams. Dropped/commented step,
   no-op wrapper, skipped test ID, missing member, wrong domain and swallowed
   child failure are mandatory reds. Filename registration remains only a coarse
   existing guard; it is not this semantic proof.
7. **Contract, full checks and release.** Exact root adoption and independent
   design review are complete. Commit new acceptance alone,
   observe meaningful parent REDs, make NC3 alone in its named commit, and implement
   only assigned files. Preserve all remaining17 existing acceptance methods and
   all old artifacts. Require full original-base CONTRACT HOLDS, fresh functional
   review at least10/12 with spec/invariants2 and applicable boundary review with
   no material finding, serialized exact-source author/independent actual47,
   integrated47, actual feature/master CI/upstream/backfill/locked builds and normal
   release evidence. Do not reuse T072's46 operator/budget as a47 receipt.

## Proposed new acceptance block

Exactly seven proposed methods in a new B12 class in the already registered
version suite: `test_legacy_dispatch_whitelist_and_exact_argv`,
`test_legacy_execution_and_exit_are_real`,
`test_whole_historical_dataset_dispatches_once`,
`test_current_workflow_dispatch_is_real`,
`test_receipt_scopes_match_executed_domain`,
`test_current_adapter_context_is_separate_and_complete`, and
`test_original_native_refuses_changed_production_source`.
Seventeen existing methods plus seven proposed means24 version-suite methods;
this is a future inventory, not an executed result. Tiny fixed children/spies
test unit dispatch/exit failures; root full gates provide actual native evidence.

## Implementation notes and cost/stop

Keep the existing verify-runtime child and its deny-all socket/Popen audit hook
unchanged. A different fixed legacy-test child is required: otherwise original
loopback/fixture descendants cannot execute. It performs actual runtime checks
then executes the unchanged original __main__ harness. A bounded call observer
records actual whitelisted test-code identities without selecting/replacing any
test. Its child/exit reporting and same-source seals must be tested with tiny
fixed fixtures first. The original native predicates and process budgets do not
change. New outer observation/time/output bounds must be pinned before execution
in the root-reviewed operator, with cap exhaustion marked failed/unknown, no
silent truncation or automatic retry; no unreviewed timeout may be invented by
the executor. This operator readiness is a required pre-full gate, not a source
or scientific allowance change.

Estimated implementation effort: one M slice,8–16 engineering hours including
tests-first and receipts (estimate, not measured). Budget one independent design
review, then separate functional/boundary review and ordinary exact gates; no
new model fan-out or experiment. Stop for any unlisted old-test conflict, source
member addition, profile/predicate relaxation, incomplete child evidence, changed
producer source during pending natural trial, exceeded observation cap, or need
to change the held archive/runtime/price candidates. Preserve every failure.

Threat: a green gate that silently loses current regressions, runs an old adapter
instead of the corrected one, treats an explicit hybrid test context as V1/V2
native qualification, or suppresses a real original child failure. Review each
domain/exit/membership boundary independently before release.


## Adopted exact routing appendix

# Exact conditional routing and evidence contract

This is NC4's adopted routing contract after independent design review. No
operation described here was implemented or run in the design pass. The
observation amendment below takes precedence over the earlier stronger claim.

## Two disjoint source contexts

Historical context: the existing closed11 members, exact e3ec46a commit/tree,
existing modes/blobs and selected explicit profile remain untouched. Legacy-test
accepts only native, clock or dataset full original filenames. Its two workflow
commands and nested historical dataset command use git-lf; the explicitly known
Windows-CRLF profile remains valid for historical dispatch, never a fallback.

Contemporary adapter context: only the following8 source members, all100644:

| Member | Origin and byte rule |
|---|---|
| bench/goplus_quota_probe.py | Exact V1 Git blob and git-lf hash from the existing catalog |
| bench/w40_evidence.py | Exact V1 Git blob and git-lf hash from the existing catalog |
| src/risk.py | Exact V1 Git blob and git-lf hash from the existing catalog |
| bench/labels.py | Exact V1 Git blob and git-lf hash from the existing catalog |
| docs/BACKLOG.md | Exact V1 Git blob and git-lf hash from the existing catalog |
| tests/test_dataset_replayable.py | Exact V1 Git blob and git-lf hash from the existing catalog |
| bench/w40_native.py | Actual candidate Git blob, canonical LF bytes; current physical raw identity recorded separately |
| tests/test_w40_native.py | Actual candidate Git blob, canonical LF bytes; current physical raw identity recorded separately |

The two current members are not forever pinned to9b/T072. At entry capture the
actual candidate HEAD/tree once; use only existing rev-parse/ls-tree/cat-file
read plumbing for those two paths, require mode100644, and independently compare
the current physical files' canonical contents with those exact blobs. Recheck
candidate HEAD and both physical files afterward. The root full-gate seal owns
whole-candidate clean/raw/ref qualification. This helper qualifies only its named
members and must not falsely claim it checked the whole current tree.

Derive the six dependencies only after validating the unchanged catalog and all
original objects. The new constructor is closed to this literal8-set; do not turn
source_view/select/load_registry into a general arbitrary-member/ref loader.
Reuse existing metadata/no-alias/read/storage guards where appropriate, with
regular single-link files, explicit before/after hashes, existing file/member/
total caps and an owned external non-Git parent. A boundary marker is metadata,
not a ninth source member. The original11-member source_view still rejects this
composition if incorrectly presented as historical V1.

The new command is exactly
`python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests`.
No other class, test path, ref, profile or operational action is accepted. Neither
this context nor its receipt can qualify original11 membership. Tests include
wrong/missing/hardlinked member, changed candidate source, changed fixed dependency,
wrong class, missing current method and role/schema substitution refusals.

## Actual child and case evidence

The fixed historical test bootstrap must perform original code_manifest and
engine_bindings in the same interpreter that runs the original __main__ harness.
Do not reuse the verify-source child whose audit hook deliberately blocks sockets
and Popen. Keep that existing child/behavior exact. Original runner bytes, test
functions, source topology, descendants and native/refusal semantics remain exact.
No arbitrary extra argv or selected historical subset is accepted.

A bounded observer records actual calls to the expected test code identities,
derived from the sealed full original runner; it does not replace those calls.
For unittest originals, all13 native and3 clock IDs must run. For the dynamic
dataset main, all9 original top-level test functions and its original runtime
pass/fail/not-checked summary are retained. A fixed runpy/__main__ bootstrap with
exact sys.argv and code-filename call observation is the proposed mechanism;
its observer transparency is an implementation acceptance requirement, not a
proven design-pass runtime fact. Missing/extra/duplicate top-level IDs refuse.
Every original descendant remains governed by its unchanged fixture and asserts;
retain actual descendant command/exit observations separately from the top child.
If the observer cannot evidence an original child, report that dimension unknown
and stop qualification rather than inventing command text from a static list.

For the contemporary context, the exact unchanged current class runs all3
methods, with original helpers/fresh recovery child behavior. Current class
selection is allowed only for this distinct duty; it cannot select a subset of
the13+3 historical originals. Existing version-suite unit positives use fixed
tiny children/spies; the47 configured gate executes each whole native runner
once and the current adapter class once. It also executes one historical dataset
child within the version suite. This count excludes runtime-verifier/unit-spy
children and original fixture descendants, all of which remain separately visible.

Root must pin a new47-command operator before heavy execution. Adopted new
outer envelopes, fixed before measurement: historical native child
900seconds, clock180, dataset120, adapter120;1MiB per raw stdout/stderr stream,
128KiB public receipt. These are new validation envelopes, not changes to any
existing native fixture/attempt/packet/process timeout, source/storage cap or
scientific bar. Overflow, timeout, interruption or uncertain retirement fails
closed, preserves bounded partial evidence and remains unqualified; no automatic
retry. Root reviews owned-test-child retirement before granting a full slot.
Do not enlarge an envelope after a failed result to manufacture a green run.

## Receipt vocabulary and exit rules

Existing verify-source receipts and their accepted layer guard remain exact.
Legacy-test extends only its allowed operation and test-execution fields under
engine-version-qualification-v1. legacy_tests status is not_run/passed/failed;
passed requires actual exit0, exact executed IDs, valid same-child runtime and
unchanged source seals. Runtime proof from another child cannot fill this layer.

The separate adapter receipt is engine-adapter-regression-v1 with the fields in
DECISIONS.md. Its four source/current-runtime/history layers concern only the
explicit adapter context. Add explicit fixed false boundaries:
original_v1_fixture_qualified_by_adapter_result=false,
current_production_behavior_qualified=false, historical_execution_qualified=false,
and v2_historical_native_positive_compatibility=unsupported. Both historical
layers stay not_evaluated with the accepted absence reasons. A source-fixture
pass here is a pass of8-member composition only; never transfer it to the11-member
historical receipt. No historical interpreter is recovered by today's interpreter.

Required execution reasons are a closed set: unknown_runner, unknown_test_context,
invalid_arguments, source_unavailable, source_mismatch, unsafe_source_view,
role_mismatch, runtime_mismatch, test_failed, test_timeout, test_interrupted,
test_output_limit, test_execution_unobserved, test_ids_mismatch and
child_protocol_invalid. Existing verify-source reason semantics are preserved;
new execution reasons do not promote or overwrite the four source/history states.
Record actual child_exit_code independently. Normal observed child exit7 yields
wrapper7; normal0 is wrapper0 only after all execution/seal checks pass. Refusal
or missing child is wrapper2/not_run. A signal, timeout or platform exit outside
the portable0..255 range retains its exact observed child value (or null if
unobserved), reports failed/interrupted/unknown as appropriate and yields a
nonzero wrapper2; never fake an observed child exit2 or map it to success.

Public receipts contain bounded fixed categories, relative member IDs and digests;
private raw evidence contains actual resolved paths, interpreter identity,
TEMP/CI/GHA flags, command/exit, output and descendant provenance. Unknown fields
are explicit, not reconstructed from assertions or today's environment.


## Adopted receipt fields

Keep legacy receipts exactly `engine-version-qualification-v1`, operation
verify-source/legacy-test, historical role and the four accepted result layers.
Use a separate bounded `engine-adapter-regression-v1` receipt for adapter-test:

- operation adapter-test; domain current_adapter_on_v1_dependencies; wrapper
  invocation_status completed/refused/failed and actual wrapper exit.
- dependency_identity: fixed historical contract/commit/tree/profile/registry
  digest, six-member subset hashes derived only after verifying the closed11.
- current_adapter_identity: exact candidate commit/tree and the two current
  member paths/blob/canonical/raw hashes. Never call this historical V1 identity.
- context_manifest_sha256 and actual child argv; source_fixture and loaded_runtime
  results apply only to this explicit contemporary context, with evidence from
  this actual test child. Its module files and original code_manifest/engine_bindings
  must match the composition; no result copied from the historical verification child.
- historical_record_tuple and historical_interpreter remain not_evaluated with
  the accepted absence reasons; historical_execution_qualified=false and
  v2_historical_native_positive_compatibility=unsupported.
- adapter_tests: expected class/three exact IDs, actual executed-ID hash, complete
  stdout/stderr hashes, actual child exit and passed/failed/not_run status.
  No legacy test is reported executed in this receipt. Failed/unobserved or
  interrupted children never receive passed. Bounded fixed reasons only, no
  private absolute paths/token/address content in public receipts.

Adopted named boundary: extend the technical routing/schema scope only
for this command/context; retain V1's11 members, profiles, existing verify-source
child/guard and all old test bytes. Root-owned NC4 registers the one real command
and its47-command operator inventory. Acceptance must reject interpreting either
context as production-V2 native compatibility. All47/full/CI evidence is future.



## Adopted observation amendment (precedence)

# T073 A1: truthful test observation and uncertain-retirement quarantine

Root decision before implementation or measurement, 2026-11-03.
This amendment resolves the sole bounded design-review finding. It supplements
the immutable c9561108 design packet and NC3/NC4 direction78b2b3bb. It does not
accept implementation, actual47 or any historical/production native execution.

## Exact choice and precedence

Adopt the narrower observation claim proposed by the boundary reviewer. This
replaces only the NEW packet's stronger promise that a top-interpreter observer
must record every deeper descendant's numeric command/exit before test-execution
qualification. It changes no original source, tests, fixture/control semantics,
scientific rule, operational native predicate or approved product gate.

The original fixture path top runner -> fixture-parent -> native-child remains
intact. Run every original test/harness/descendant and assertion unmodified.
Never inject a replacement harness, observer into a deeper worker, process killer
or synthetic successful child result to satisfy the new observation fields.

## Separate qualification and evidence

1. `test_execution_qualified` requires the selected domain's verified source seal,
   original code_manifest and engine_bindings in the ACTUAL test interpreter,
   exact expected top-level test IDs once, original harness/dynamic counters,
   actual observed top-child exit0, unchanged after-seal and no timeout,
   interruption, output overflow, protocol failure or unresolved outer lifecycle
   uncertainty. Existing nonzero/source/ID/role refusals remain failures.
2. Preserve actual command/exit observations of directly observed fixture children
   and their observation source. A known negative/signal exit is its actual value,
   not0 or wrapper2. Test execution is not proof that every descendant branch ran.
3. For a deeper command or numeric exit not exported/observed, record null with
   fixed `not_recorded` state. Keep original identity absence and lifecycle
   assertions as ORIGINAL HARNESS ASSERTION evidence. Do not transform those
   assertions or source-derived expected argv into numeric exit or independent
   process telemetry. `descendant_observations_complete=false` for the known
   unobserved nested path; no stronger qualification follows from test success.
4. That false telemetry-completeness field alone does not reject an otherwise
   complete successful ORIGINAL TEST EXECUTION. It does forbid a complete-tree
   observation/retirement claim. Historical records/interpreter/execution,
   original-V1 qualification by the adapter context, current production behavior
   and positive V2 native compatibility retain all specified false/not_evaluated/
   unsupported boundaries. Unchecked/skipped fields and dynamic counters remain
   explicit; source-based expected IDs are not observed pass counts.
5. The current adapter3 obligation is unchanged. The functional reviewer's sole
   audit-guard attempt remains exit1 with four fresh-recovery scenarios unverified;
   it is not a source failure or completed closure. Implementation must actually
   satisfy the complete unchanged class and later47 gates. Do not repeat that
   reviewer attempt or rewrite its result.

## Timeout and retirement are a different gate

6. Top child exit/kill/wait alone does not establish that an existing fixture-parent
   or worker has retired. Timeout/interruption/overflow, a missing final ownership
   observation, or actual reported uncertain outer retirement is unqualified.
   Preserve partial outputs, actual values and source views/ownership evidence;
   do not delete an owned view while a possibly live child could still use it.
   A truncated stream's hash describes its recorded prefix, not a complete stream.
7. On such uncertainty, the local validation operation and root gate enter a
   persistent per-validation-scope quarantine BEFORE any successor heavy command
   or heavy slot. Root must review an explicit admission/notification mechanism
   in the NEW47 operator before granting full execution. A nonzero return that
   the ordinary local runner ignores is insufficient. CI must retain its failure
   and nonexecuted steps; a later green run never replaces that attempt.
8. The quarantine cannot be cleared because only the top parent exited, the next
   command wants to run, a fixed delay elapsed or a ledger was reset. A separately
   recorded recovery must establish owned-child retirement for that incident;
   otherwise stop heavy work and return the concrete unresolved condition to root.
   No new general process killer/containment framework or T047 dependency is
   authorized. No automatic rerun or descendant-exit guess is allowed.
9. Expected negative synthetic cases and caught fixture exceptions are not, by
   their text alone, outer ownership uncertainty. Unit negatives use their own
   bounded private scope and must not poison or clear the enclosing real full
   gate. Record any actual uncertainty in a REAL operation; do not hide it through
   a test flag or altered CI/GHA flags. Full operator readiness must demonstrate
   unknown-retirement -> no successor launch, including failure propagation from
   a nested version-suite child, with tiny controlled fixtures before heavy runs.

## Fixed new envelopes and remaining gates

10. Adopt the proposed new OUTER test-child caps before execution: native900s,
    clock180s, dataset120s, adapter120s; each raw output stream1MiB and public
    receipt128KiB. These are fail-closed observation limits for the new dispatcher,
    not permission to change old fixture/native/process/scientific bounds. Record
    actual elapsed/interpreter/TEMP/CI/GHA in new private execution evidence.
    Exhaustion stays failed/unknown; no automatic extension or new attempt.
11. Include meaningful pre-fix acceptance vectors in the seven proposed methods:
    identity absence is not numeric exit0; top success does not imply complete
    descendant telemetry; missing IDs/nonzero cannot pass; timeout uncertainty
    cannot admit a successor. The NEW root47 operator separately tests its actual
    quarantine/admission seam. Original17 methods change only by exact NC3.
12. `commands.json` plus actual test.yml parsing is the authority for the47 offline
    commands. Per-ID mapping also refers to existing live backfill/upstream jobs;
    in particular retain `tests/test_backfill.py --offline` in the test job and
    the unchanged separate live job. No live command is authorized as a focused
    offline design/implementation check. The other44 commands and all applicable
    real workflows stay intact.

The two R1 reviews and failed reviewer harness remain immutable. A1 is accepted
after bounded independent re-review against the one finding and its regressions.
The root task-base plan binds formal NC3/NC4 adoption. No full/CI/source-stage
qualification, old study restart, extra Vendor request or snapshot call occurs
through this amendment. The original finite normal-trial callback stays untouched.


## Formal acceptance changes and current limits

NC3 is exactly the removal of the legacy-test literal from the existing eight-
action CLI rejection tuple. Keep the other seven vectors, all assertions and
shared helpers, help behavior and all other existing17 methods. Commit this
alone as `T-073: named change (NC3 fixed legacy dispatch context)` after the new
tests-only meaningful RED. No other old acceptance change is authorized.

NC4 is exactly the separate eight-member current_adapter_on_v1_dependencies
context and the one adapter-test command above. Current adapter/test member
identity is the actual candidate, never a permanently selected T072 adapter.
Do not change the original11-member registry, profiles or original source/tests.
All prior failures, original reviewer exit1 and unverified recovery closure
remain retained. Design evidence is not implementation/runtime qualification.

The actual current gate is46 commands until root registers the accepted47 plan.
Do not mark47 executed from this file or a static source inventory. The new root
47 operator must pass independent readiness including persistent retirement-
uncertainty admission/stop tests before author or reviewer full execution.
No automatic retry, threshold change, skipped original duty or extra Vendor
request is authorized. No push of this successor occurs before the preceding
normal-snapshot qualification required by root. T047/T049/T050 remain held.
