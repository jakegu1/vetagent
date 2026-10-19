---
id: T-050
title: Install and verify the exact owned W40 scheduler without changing its runtime
status: draft
level: 3
size: M
backlog: W40 prerequisite and live observation
depends_on: [T-049, T-047]
decisions: [B1, B2, B11, B15, P4]
---

## Context and goal

T047 owns verified source transactions, allocation and writer/trust primitives.
T049 owns the durable study/runtime and freezes tick, receipt, stop and clock
ports before its tests. This task implements the final PowerShell wrapper and
only the exact private owned Task Scheduler definition. The observable result is
one unchanged unarmed/live action, verified OS readbacks and two actual scheduled
ordinary-entry proofs before arming. Registration or an exit code is not execution
proof. Source quality, native transport, OS availability and study calendar remain
separate. No task or real study is started during ordinary source tests.

Draft only. Bind reviewed integrated T049 green46, T047 interface hashes and the
original reviewed green44 dependency chain before the first acceptance commit.
The native API remains `4dd847480659bc4c5100aade50dc10c04c45bb59` with source SHA256
`ea483b0dc8afaebc4fe1e4b115af4930bb08f2427cc80e77390a1cc302831452`.
This bounded final source/review loop costs existing local engineering/disk and
machine availability; stop on wrong/unverifiable identity, host policy, ownership
or cleanup. No elevation, account/source right, scientific bar, label, timing or
permission change is introduced. Unavailable scheduling is an explicit runtime
gap, not a reason to weaken the same action, proof or arm requirements.

## Scope and files

Only new `tools/w40-local.ps1`, new `tests/test_w40_scheduler.py`, and one additive
unconditional `python tests/test_w40_scheduler.py` ordinary step47 in
`.github/workflows/test.yml`. Preserve every prior46 source/test/fixture/AST/step/
job/pin/condition/build byte. Named old-test changes: none. No edits to T049/T047
runtime/API, T044/T045/T046, engine/labels/rules, active study, archive, offline
runner, benchmarks/cache, deployment, permissions, packages, services or keys.

Conflict search at the native base found no w40-local/w40_scheduler or proposed
method/Register-ScheduledTask/TaskScheduler collision. Existing source_ref/start/
target/intent/entry/retirement/endpoint/CI assertions and registration/reachability,
deploy inventory, runtime pins/private guards remain exact. Refresh every task,
CLI/schema/cmdlet and fixed interface name against the finally bound T049 base.
An incompatible dependency requires a named lead amendment before any edit;
wrapper convenience is not permission to change already frozen runtime tests/API.

## Acceptance criteria

1. **Private trust and offline entries.** Use only fixed -Entry values
   plan/install/status/stop/uninstall/tick/clock-epoch, the bound -Config path and
   required -ConfigSha256/-ManifestSha256 fixed reviewed arguments;
   default plan. Help/plan are offline with no source/vendor/Git or scheduler
   mutation. Status may query only the bound exact OS task and existing evidence.
   Before importing runtime/acquisition code or making an OS task call, verify
   wrapper/self, resolved reviewed PowerShell/Python executables, full final import
   closure, code/action/config hashes and non-aliased external roots through the
   frozen phase0/T047 contract. No code from current directory/archive or arbitrary
   config-specified module is loaded. Actual CI/GITHUB_ACTIONS rejects every
   mutating entry before directories/locks/raw/runtime/OS calls; no flag clearance,
   profile, environment persistence, permission or ExecutionPolicy change. Safe
   output<=1 MiB, fixed states/counts/UTC/hashes/ordinals with omission counts;
   never private paths, identities, URLs, raw sentinels or free exception text.

2. **Exact task ownership, XML and action.** Private fixed TaskPath is
   `\VetAgent\W40\`; TaskName is W40- plus the full validated study-ID SHA256.
   Query/create/disable/delete only that pair after config binding. No broad task
   enumeration, wildcard/name-prefix operations or replacement of a conflicting/
   unowned definition. An existing task is reusable only with complete matching
   ownership/install receipt and actual XML/action/config policy readback; drift
   refuses rather than overwrites. Fixed action: absolute reviewed PowerShell,
   -NoProfile -NonInteractive -WindowStyle Hidden -File absolute reviewed wrapper,
   -Entry tick -Config exact bound path -ConfigSha256 fixed config digest
   -ManifestSha256 fixed code-manifest digest. Any Start-Process helper is Hidden. The
   wrapper invokes absolute reviewed Python, isolated trusted imports, -I -B,
   absolute reviewed w40_local.py tick --config exact path --config-sha256 fixed
   digest --manifest-sha256 fixed digest. All argv are fixed/
   safely quoted, never eval, shell code assembled from config or arbitrary args.

   Principal is current-user Interactive/Limited, no password/elevation/service/
   account/power policy change. Exactly one Once trigger with PT1M repetition and
   omitted duration, plus current-user logon trigger. StartWhenAvailable,
   IgnoreNew, zero restarts, PT26M OS execution limit for the internal25-minute
   tick. Do not pass or enable WakeToRun. Do not alter policy to wake the machine.
   Preserve every material XML/action/principal/trigger/settings field during
   normalization; only insignificant XML serialization/namespace/whitespace may
   normalize. Actual Once start boundary is generated from real install UTC,
   committed in the install receipt and retained, not caller-controlled or erased
   from comparison. Compare reconstructed intended material definition to actual
   readback, then freeze its hash. Sleep/logoff/offline/late/ignored overlap remain
   explicit availability gaps. Task quota, rights and uptime are not inferred.

3. **Unchanged ordinary entry and two actual scheduled proofs.** Install only
   after all source quality gates, in unarmed offline state; preserve all runtime
   stop/history/budgets, never create a replacement study on install/reinstall.
   The tick action uses the exact frozen T049 port and returns its TickEntry/
   TickReceipt hashes. A real direct PowerShell unarmed fixture must execute that
   ordinary runtime entry, open zero source/vendor calls and leave not_started;
   it is not a scheduled firing. Keep action/config identical after arm. No
   wrapper --live mode or separate collector code path exists. Arm remains the
   existing explicit T049 command and requires the root runtime gates plus the
   SchedulerGate contract below.

   Observe two distinct actual OS scheduled run instances reaching that same
   ordinary entry while unarmed, correlate their immutable runtime process-
   creation/entry/completion evidence, and bind matching exact-task XML/action/
   config readbacks. Independently retained actual OS run evidence must distinguish
   those runs from a manual launch, a mock, registration metadata or exit0.
   LastTaskResult/LastRunTime alone is insufficient. Query instance evidence only
   for the exact registered task and a bounded observed run window; never broaden
   enumeration or enable/change OS logging/security policy. Missing/unreadable/
   ambiguous origin evidence is scheduler_proof_unavailable, never self-certified
   scheduled=true. Wrapper-only fixtures cannot satisfy actual arm. Record root's
   verification of real source/T044/native/Linux gates separately; no Owner
   permission is invented for ordinary authorized technical steps.

4. **Stop, original cleanup and exact uninstall.** First commit T047 immutable
   request_stop even if the runtime writer is busy; idempotent terminal stop must
   reach every future native/source admission check. Poll only fixed read-only
   stop_status/receipt ports within the existing original tick/child deadlines;
   do not acquire a new cleanup or process lifetime budget. Verify the active
   child retired, then disable and read back the exact owned task. If retirement,
   disable or readback cannot be established, expose terminal stop_unknown and
   prohibit further calls. Host/task failures do not undo the stop request or
   reset runtime state. Uninstall only that exact owned task after stopped cleanup;
   conflicting/unowned/missing-evidence state refuses deletion. Preserve every
   code/config/ledger/source/raw/receipt byte. No deletion/migration/auto-resume,
   evidence pruning, reinstallation reset or unrelated task mutation.

5. **Fixed ClockEpoch port and host compatibility.** Implement T049's already
   frozen `-Entry clock-epoch -Config <bound-config> -ConfigSha256 <fixed-pin>
   -ManifestSha256 <fixed-pin>` command: read-only validated
   self/config/interpreter, fixed Win32_OperatingSystem.LastBootUpTime query,
   UTC normalization and one bounded w40-boot-epoch-v1 JSON object on the private
   pipe. The absolute five-second parent timeout includes helper cleanup; timeout,
   malformed/unavailable data or process uncertainty fails closed, without a
   fallback epoch or CLI time override. Safe reports contain only its hash.
   Normalize only this process/child's PSModulePath to the trusted platform system
   Modules directory, including cross-PowerShell-edition launch; no persistent
   environment/profile/ExecutionPolicy/permission change. Use real actual Windows
   read-only helper/unarmed wrapper proof locally; module import/availability does
   not establish scheduler rights or firing. On Linux ordinary tests verify the
   fixed unsupported scheduler boundary and runtime's actual Linux restoration
   dependency; mocks never become a Windows OS guarantee. No skip is called PASS.

6. **Contract and checks.** First commit only new tests/test_w40_scheduler.py with
   exactly six stdlib unittest methods and direct unittest.main():
   `test_w40_scheduler_exact_owned_xml_and_action`;
   `test_w40_scheduler_private_bootstrap_ci_and_offline_defaults`;
   `test_w40_scheduler_unarmed_tick_and_actual_receipt_contract`;
   `test_w40_scheduler_stop_cleanup_and_owned_uninstall`;
   `test_w40_scheduler_clock_epoch_and_host_environment`;
   `test_w40_scheduler_cli_and_complete_existing_runner`.
   Native red is a missing wrapper at the fixed path, not an unrelated tool error.
   Freeze all assertions/helpers/AST/main after red except named amendments. Use
   bounded fake OS task objects/XML, fake/read-only clock ports and actual private
   Windows unarmed runtime entry; ordinary tests never register/disable/delete a
   real task, contact GitHub/vendors/production, benchmark or start a study. Test
   stale action/config/XML, wrong path/name/principal/trigger/repetition/duration/
   restart/execution limit, conflicting/unowned task, actualCI-before-write,
   raw aliases/sentinels, cross-edition environment, forged/manual/duplicate firing
   evidence, busy writer stop, cleanup uncertainty and exact owned uninstall with
   positive controls. CI fixture env changes are nested/exactly restored; actual
   CLI rejection stays intact. No extra controlled mutants here; batch total is
   T047's1 plus T049's2. Focused CLI/direct/contract/read-only host proof and exact
   freeze precede one lead-granted exclusive complete47-step gate at clean frozen
   HEAD with all tracked bytes compared. Independent>=10/12, spec=2/invariants=2,
   adversarial none, configured gates and actual Linux source results precede
   integration; branch CI may supply Linux. Actual OS registration/two firings
   remain later root runtime evidence. One finding per repair commit, red before
   fix; no own merge/push. No mocked/skipped/unrun runtime fact is called complete.

## Fixed interface D — task ownership and runtime gate

Apply the same acyclic trust graph as T047/T049: code manifest hashes only code,
trusted imports and interpreter identities, with no own/config/action/receipt
digest; immutable config pins that manifest but no own/action/future OS receipt
digest. Fixed action carries externally reviewed ConfigSha256 and ManifestSha256.
Phase0 requires both pins, verifies actual config/manifest/self/interpreters before
imports or OS calls and never learns a pin from the file it is meant to verify.
Install/OS receipts then bind actual normalized action/XML and both pins; scheduled
gate and arm refer backward only. Do not rewrite config after installation.

Consume T047 A/B and T049 C exactly; do not edit earlier source/tests/APIs. The
wrapper's task-state writer uses T047's same process lock and allocation namespace
owner=scheduler, and immutable contiguous receipt records; it has no independent
storage ceiling/reset or mutable manifest. Normal startup/status do not repair
torn/partial receipt state. The root supplies final frozen code/config once all
three loops pass, before real seed/install; later changing source/import/action/
config requires a new reviewed installation, never a mid-study auto-update or
reuse of earlier state under new bindings.

InstallReceipt schema=w40-task-install-v1 binds study/config/code/task identity,
material-policy/action hashes, actual normalized XML hash/bytes reference, actual
install UTC/Once boundary, exact readback/ownership evidence and allocation ticket.
No raw private identity/path is emitted safely. StatusResult
w40-task-status-v1 returns fixed state/reason, install-receipt hash, task/action/
config/XML hashes, current owned/matching/disabled booleans, pending-operation hash
or None and cleanup state;
private XML/proofs stay external. Ownership is a verified existing receipt plus
matching actual definition, not the name prefix alone.

SchedulerGate is exactly T049's w40-scheduler-gate-v1: two distinct complete unarmed
TickEntry/TickReceipt pairs, two actual correlated OS run-instance proofs and
matching install/current OS hashes under the fixed study/config/action. T050 owns
its append-only records and original OS evidence, runtime owns ordinary tick
records. Artifact direction is install receipt -> ordinary entries/completions ->
observed OS correlation -> SchedulerGate -> runtime arm event. No artifact hashes
a future arm event or changes the action to obtain proof. Root freezes the actual
technical evidence through this fixed gate; arbitrary caller JSON/fixtures are
never authority. If a bounded exact-task API cannot supply adequate correlation,
report the precise runtime gap and retain manual ordinary tick, without claiming
scheduled eligibility or arming around it.

PS calls only the fixed runtime plan/report/tick/stop/entry_receipt/stop_status
ports for runtime work. Stop requests use the existing runtime/T047 primitives.
The wrapper contains one fixed literal Python bridge, covered by its own reviewed
file hash, launched with the resolved interpreter and -I -B -c fixed-literal-code;
it imports only the verified frozen archive/runtime ports, never config-selected
code. Its closed commands are prepare-install/prepare-disable/prepare-uninstall,
complete-operation/read-status/record-observed-runs. Each private stdin message
is canonical bounded JSON<=1 MiB; no arbitrary path, function, code, task selector
or whitelist can be supplied. It uses the fixed config roots/operation ID only.

Prepare holds the T047 writer, verifies existing scheduler/runtime state and
unarmed install or stopped-cleanup removal eligibility, reserves a scheduler
allocation ticket and commits the already frozen SchedulerOperation schema before
returning. The OS cmdlet runs only after that durable intent. Completion reacquires
the same writer, verifies the exact intent and actual bounded private XML/OS
readback, appends immutable completion/install/gate receipts and settles through
T047. No serializable WriterLease is passed between processes. Pending intent
blocks any other scheduler mutation and live runtime admission; missing/torn/
ambiguous completion is terminal, not replayable. Thus no writer lock must span
an external PowerShell cmdlet, and a crash cannot silently release logical
ownership. Read-status is strictly read-only and does not acquire the writer;
record-observed-runs takes it and appends a verified individual RunReceipt, retaining
the first actual instance durably before a later firing. Each w40-task-run-v1
receipt binds its completed unarmed TickEntry/TickReceipt, distinct OS instance,
exact install/action/config/manifest/XML and actual correlation evidence hashes.
Only two distinct verified RunReceipts can produce SchedulerGate; no duplicate,
manual or unknown-origin receipt gains scheduled credit.
No PowerShell-written shadow driver journal/budget or later runtime API is allowed.
ClockEpoch is read-only and uses the fixed private pipe contract; other commands
never expose its raw value. T049's production Windows path remains unavailable
until this actual reviewed wrapper is present and bound.

## Evidence, threats and rollback

READY includes exact dependencies/interfaces/source/test/manifest/fixture/log
hashes, missing-wrapper red, contract/AST/unchanged prior46 comparison, bounded
actual Windows unarmed ordinary entry and ClockEpoch proof, all scheduler mocks
explicitly labeled, safe raw/CI/alias tests,47/47/native exit0 and all tracked bytes
before/after, actual Linux ordinary source evidence and fresh review verdicts.
Seal helpers before full; never edit sealed evidence. No task registration,
LastTaskResult, mocked OS run or T044/native control can start or prove W40.

Threats: wrong task deletion/overwrite, stale/private action drift, inherited module
paths/profiles, forged scheduler attribution, ambiguous cleanup, same-name unowned
tasks, logoff/sleep/late execution, manual launch counted as scheduled, lost stop
signal and runtime budget reset. Rollback writes terminal stop, verifies original
bounded retirement, disables/readbacks only the exact owned task and optionally
uninstalls it after cleanup; all evidence remains. Thirty actual elapsed days
from the immutable admitted vendor entry or an honest terminal earlier stop is
still required for readout, preserving every coverage/source/availability/late/
unknown/overlap/unasked denominator. Observation count is never success.

## Dependency appendix — lead completes before dispatch

Reviewed integrated green46 and immutable T047/T049 interface hashes: PENDING.
Original green44/T044/T045/T046 sources/manifests/reviews/Linux: PENDING. Final
private root runtime/installation/config/seed and two actual scheduled ordinary
firings remain activation requirements; the source tests cannot certify them.
