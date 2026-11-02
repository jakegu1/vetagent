# Explicit historical source-fixture identity

`tools/engine_versions.py` verifies one fixed W40 source fixture and its actually loaded
code in the present Python interpreter. It does not qualify a historical study, migrate
an old plan, run a native collector, or change the sole production engine in `src/risk.py`.

## Commands

```
python tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf
python tools/engine_versions.py verify-source w40-v1-e3ec46a observed-windows-crlf
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native_clock.py
python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_dataset_replayable.py
python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests
```

The profile is mandatory. Default/help performs no verification. Missing/unknown contract
or profile refuses; host OS, checkout line endings and failures cannot select another
profile. Collect, recover, report, study, pilot and scheduler are unsupported commands.
No arbitrary test/source path, executable, commit, old record or interpreter input exists.
Only the three original runners above are accepted by legacy-test. Both explicit historical
profiles are supported; configured historical dispatch uses git-lf. Adapter-test accepts
only the literal class and git-lf. Workflow registration remains root-owned: the helper
reports registration_pending for the unchanged46-command workflow and registered only
for the exact reviewed47 commands. A focused pass is not an actual47 execution.

## Source and execution checks

The reviewed registry pins a single commit/tree, role and ordered complete source closure.
The helper pins the registry's canonical SHA256, so changing a member, hash, mode, role,
profile or extra key requires another explicit reviewed source change. Duplicate JSON keys
and over-limit registry data refuse. The two profiles have independent complete raw-byte
hashes and sizes; canonical CRLF-to-LF equality alone grants no identity.

Read-only Git plumbing checks exact tree membership, blob mode/type/size, raw SHA256 and
Git object ID. Object replacement and lazy object fetching are disabled. Missing objects
refuse locally; no fetch, clone, ref update, shell or open-ended source acquisition occurs.
Fixed engineering limits are declared by `REGISTRY_CAP`, `MEMBER_CAP`, `FILE_CAP` and
`TOTAL_CAP`. Hitting a limit refuses, never truncates a source set.

A temporary external source view preserves the original relative layout. All members are
new regular files, not writable hardlinks; path aliases/reparse points and unexpected
members refuse. The fixed `.git` marker preserves the old raw-storage boundary and does
not make this a Git checkout. The complete selected raw/canonical identity is checked
before use and again on success or failure, then the private temporary view is removed.
No whole repository/dependency copy is created. Temporary storage follows the process's
external TEMP configuration and is refused inside a Git checkout.

A fresh child uses `-I -S -B`: no parent module state, PYTHONPATH, site packages or bytecode.
It checks the actual loaded original native/core/risk paths, original `code_manifest()`
and `engine_bindings()` (code filenames, compiled functions, defaults, closures and RPC
roots). Socket and descendant-process actions are refused in this verification child.
No engine assessment, acquisition or native test runner executes in verify-source. Its interpreter hash,
version/cache tag, source manifest and predicate evidence are recorded as a digest.

The child also validates an original synthetic empty-source core plan without changing its
bytes, and observes original `source_drift` rejection for the opposite raw profile and an
unknown engine binding. Its `source_commit` remains a declaration, distinct from the
registry's verified `engine_source_commit`. Synthetic checks do not qualify an actual
historical record. The unchanged generic core has no global role/registry enforcement;
identical bytes alone do not make a production-role request eligible for this fixture.

## Receipt scope

Every verification/refusal receipt uses `engine-version-qualification-v1`. Invocation
status describes this request only. Contract/source identity, explicit requested/selected
profile, fixed command vector, actual wrapper exit and four separate result layers remain
visible. Unknown caller strings are not echoed: unrecognized profile/contract values use
null identity fields and a fixed refusal category. Receipt text contains hashes/fixed
categories, not private host paths or arbitrary exception prose.

| Result | What a pass proves | What remains unproved |
|---|---|---|
| `source_fixture` | Complete selected source bytes match the accepted fixture. | Any historical execution of those bytes. |
| `loaded_runtime` | This child loaded matching code in the present interpreter and passed original predicates. | The interpreter used by an old study, or successful V2 native interoperation. |
| `historical_record_tuple` | Not evaluated by these commands; no historical-record input is accepted. | Original study raw tuple/artifact qualification. |
| `historical_interpreter` | Not evaluated by these commands. | Historical interpreter/runtime provenance. |

Historical layers stay `not_evaluated` with fixed reasons and empty evidence. Missing source
objects/runtime may be `unavailable`; examined mismatches are `failed`, unexamined dimensions
are not fabricated failures. `historical_execution_qualified` is always false. Legacy tests
are `not_run` for verify-source/refusal; a legacy-test receipt separately records the actual
original test execution and child exit. Positive production-V2 compatibility with the historical native adapter
is `unsupported`. No fixture/runtime success promotes either historical layer.

## Test responsibilities and holds

The historical dispatch runs the complete old native GET/RPC/cache/context and datetime contracts
in V1, while the current dataset runner remains current and the entire historical dataset
version runs once within the version suite. The workflow guard checks today's exact commands.
Those native tests are V1-only;
current production risk/MCP/HTTP/benchmark/numeric regressions retain their distinct duties.
Repaired V2 must still be rejected by the original native source predicates. Rejection is
a negative guarantee and not positive V2 native execution evidence.

## Contemporary adapter and actual child evidence

The separate eight-member adapter context combines six fixed V1 dependency blobs with the
actual candidate's current native adapter and unchanged current native-test file. It does
not modify the closed eleven-member registry. Current HEAD/tree/blob/canonical/physical-raw
origins are recorded and rechecked; current members are not pinned forever to an older fix.
The only selected class runs all three current staging regressions. Its source-fixture pass
refers solely to this composed context, not original-V1 membership or production behavior.
The receipt schema is engine-adapter-regression-v1, with domain
current_adapter_on_v1_dependencies and explicit false historical/original-V1/production
qualification fields. Positive V2 historical-native compatibility remains unsupported.

A different fixed test child uses the same isolated interpreter flags, checks original
code_manifest and engine_bindings in that actual test process, then runs the unchanged
original __main__ harness. It observes exact top-level test IDs; nested calls to another
test function remain separately recorded internal calls. Dataset pass/fail/not-checked
counters remain the original dynamic values. No whole native/clock positive is embedded
in version-suite unit tests; those units use controlled small children/spies.

Actual observed command representations are preserved in private evidence: Windows command
line strings are not guessed into POSIX argv. Direct Popen.poll values are their actual
values, including negative/signal exits. Deeper unexported commands/exits are null with
not_recorded state. Original lifecycle assertions remain labelled original harness evidence;
they never become independent exit0 telemetry. descendant_observations_complete is false
even when test_execution_qualified is true. Neither implies complete-tree retirement.

The new outer child bounds are native900s, clock180s and dataset/adapter120s; each recorded
raw stream is at most1MiB and each public receipt128KiB. Private metadata is bounded by1MiB,
256 direct/audit/nested observations and65 top-level ID entries; dropped observations are
explicit and an unobserved direct owner fails closed. A validation scope holds at most16
operations. These bounds do not change original fixture/process/source/scientific limits.
Original output hashes describe a complete stream only when its completeness flag is true;
otherwise they bind only the retained prefix. All operation views and partial evidence are
retained, including on failed or uncertain executions.

## Quarantine admission interface

The root47 operator must pin one dedicated external non-Git directory in
VETAGENT_VALIDATION_SCOPE and inherit it into every nested version-suite/dispatcher child.
Without it, the dispatcher uses a persistent external TEMP scope keyed by workspace path.
The private scope contains operations, atomic state/intent/observation records and an
immutable quarantine.json marker. TEMP, CI/GHA, actual interpreter and commands are recorded.
CI/GHA are never cleared by the dispatcher. Unit-negative fixtures have their own explicit
private scopes; they cannot clear the real operation's quarantine.

Before EVERY successor command, the root operator calls
`validation_admission(scope)` from this helper. It must refuse admission on a quarantine,
unfinished operation, corrupt state or unknown admission owner. A nested dataset timeout
therefore blocks a later native command even if an ordinary local runner would keep going
after a nonzero test. Calling the ordinary runner without this independently reviewed
operator does not satisfy the new full-gate contract.

Timeout/interruption/overflow, incomplete output or missing/uncertain final ownership
observation persist quarantine before returning. Top-child exit, waiting, a new demand or
changing a ledger cannot clear it. There is no automatic clear, process-tree killer or
recovery API. Root must separately qualify incident-bound owned-child retirement before
allowing a later heavy operation. Do not change scope to bypass an unresolved real incident.
The root operator's actual admission/notification propagation, including nested failures,
requires independent small-fixture readiness before any full47 slot is granted.

An internal pure guard checks all four result layers before returning a verification and
again before emitting a CLI receipt. It rejects historical promotion, a passed runtime
without a passed fixture, copied fixture/runtime evidence, malformed hashes/reasons and
fabricated evidence on unexamined layers. Synthetic contract tests preserve known-absent
historical states as `unavailable` and inconclusive states as `unknown`; these tests do
not introduce a historical input or operation. Real commands still leave both historical
layers `not_evaluated`. Rejected result shapes produce a fixed sanitized refusal/nonzero,
with no positive historical qualification.

No T047/T049/T050 archive/seed/runtime/scheduler API or incomplete mandatory verdict is
adopted or replaced. Original research sources, windows, rules, labels, thresholds, originals,
failed/unknown states and closed conclusions remain unchanged. Prices and the old partial
T068 candidate are outside this source-identity slice. Any future operational adopter,
production repair or release needs its own assigned contract and actual acceptance.

## Review corrections: admission and exported execution receipts

A dispatched operation remains running until source rechecks, execution-domain receipt
validation and receipt publication succeed. Uncertainty is recorded before optional
observation publication. A postlaunch capacity, protocol or write failure quarantines the
operation; if quarantine publication itself fails, the unchanged unfinished state still
refuses admission. The retained failure receipt reports failed execution, preserving an
actually observed top-child exit independently of the nonzero wrapper exit. Neither a
generic exception nor a known top-child exit establishes complete descendant retirement.
A bounded private failure-stage.json records the failure phase and both exit fields;
missing child observation remains null and never becomes a guessed numeric exit.

Admission accepts only an exact two-key finished-state object whose string operation_id
matches its canonical lowercase hexadecimal directory. Missing, copied, malformed,
unexpected-key, aliased or unfinished state refuses admission without rewriting that
evidence. Enumeration stops at the existing sixteen-operation bound. No migration or
quarantine-clear interface exists.

The separate execution-domain guard preserves the original four-layer source guard.
Legacy execution receipts bind the fixed contract, commit, tree, profile, runner, exact
sorted top-level ID count/digest and eleven-member raw-profile context seal. The ID
digests are derived from the pinned original runner blobs, not supplied by the caller.
Adapter receipts bind their own three IDs, six exact dependency records and two members
of their named candidate Git commit/tree; they retain an eight-member context seal.
Their candidate is not permanently pinned to an earlier adapter revision. An adapter
receipt cannot qualify the original fixture, historical execution or production V2.

Malformed types, duplicate membership, unknown fields and contradictory status/exit
claims produce bounded VersionError codes. Known-absent historical layers stay
unavailable and unexamined or inconclusive layers retain their separate meanings.
This exported-artifact check does not prove actual execution: original raw reports,
source views, runtime predicates and actual process/operation identity remain required.
Missing deep telemetry stays null/not_recorded even for an A1-valid passing execution.
