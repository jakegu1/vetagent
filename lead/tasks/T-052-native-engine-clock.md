---
id: T-052
title: Preserve the engine datetime contract across native acquisition contexts
status: done
level: 3
size: S
backlog: W40 prerequisite and escaped runtime regression
depends_on: [T-046, T-051]
decisions: [B1, B2, B11, B15, P4]
---

## Context and goal

A distinct source-bound native control completes real data-bearing GET and RPC
stages, then the real engine raises AttributeError at `_age_days`: its pinned
clock value is a float without `timestamp()`. The existing engine `_clock_now`
contract returns a datetime. Both native adapter_scope and collect_one currently
store numeric timestamps in the engine context. Passing fake engine functions in
older acquisition fixtures did not test this real engine seam.

Keep the original failed controls unchanged. This task repairs that deterministic
adapter-to-engine type seam with offline evidence first. It protects meaningful
age/staleness checks and complete acquisition, costs a small source/review loop,
and stops on an incompatible frozen contract. It introduces no Vendor requests,
new study, quota experiment, production verdict change or scientific-bar change.

## Bound dependency and conflict search

Base9dc8686a445c43fd568555b140bf715d9dbfdbac has actual local44, exact master push
39392487756 all44, upstream/backfill and two independently locked builds passing.
Original T046 API source is4dd847480659bc4c5100aade50dc10c04c45bb59; its canonical
native SHA256 isea483b0dc8afaebc4fe1e4b115af4930bb08f2427cc80e77390a1cc302831452.
The six engine/core FROZEN entries, dataset, clock/provider limits and original
scientific protocol remain unchanged. Only native's own derived source digest
changes after the repair; disclose that changed installation dependency.

Conflict search covers _BENCH_NOW, _clock_now, _age_days, adapter_scope,
collect_one, engine_bindings and native Clock in all tests/test_*.py and fixtures.
Existing benchmark replay and MCP tests already use datetime engine contexts;
existing native fixtures predominantly supply a fake engine. No existing test or
fixture requires the numeric context contract. Named old-test changes: none.
Repeat this search before tests and report any contradiction as BLOCKED rather
than changing an old assertion. No new test name/module collision was found.

## Scope

Only bench/w40_native.py, new tests/test_w40_native_clock.py and one additive
unconditional ordinary workflow command in .github/workflows/test.yml. Register
the new test exactly once, preserve all existing44 commands, jobs, conditions,
actions, build pins and runner bytes. Do not edit src/risk.py, T044/T045/core,
their tests/fixtures, source providers/retries, scoring, private study files,
existing runtime/control evidence, archive module, runner or permission files.
No network, actual scheduler action, package, credential or production mutation.
Lead-owned spec/status/generated metadata are separate from executor source.

## Acceptance criteria

1. Native scopes supply the engine with the bound Clock.utc() datetime at their
   existing sampling points. The real _clock_now and _age_days functions operate
   on it without AttributeError, retaining the bound instant, age/future-skew
   semantics and timezone. Cover the real default UTC Clock and a fixed aware
   datetime Clock. Keep native permit deadlines/monotonic accounting unchanged;
   no engine change or widening/coercion of a malformed clock is introduced.

2. Exercise both adapter_scope and the collect_one engine-entry path. Use bounded
   offline transport fixtures and actual engine age/staleness logic. At least one
   complete real risk.assess path must return a structurally valid answer using
   deterministic recorded/synthetic upstream fixtures, with physical network
   forbidden. A fake final answer or testing only context assignment is not seam
   proof. Verify collect_one refreshes the datetime at its existing engine-start
   sampling point after earlier fixture stages advance the clock. Preserve
   endpoints, raw/result accounting, unchanged fail-closed unknown behavior and
   all original caps. No old private live raw is copied into public tests.

3. Engine context and adapter globals restore exactly on normal completion,
   raised exception and cancellation, including an already pinned outer datetime
   and the stale/failure context variables. A later ordinary call receives no
   leaked float, pinned time, fetch adapter, onchain state or trace context. Test
   the real handoff and restoration, not a duplicate implementation. Include one
   private byte-exact controlled regression mutant restoring the old timestamp
   conversion in both sites and show the frozen acceptance fails; restore safely
   from an external byte copy and remove stale bytecode. No new mutant fan-out.

4. Contract and checks: first executor commit adds only the new acceptance file,
   with exactly three stdlib unittest methods and direct unittest.main():
   test_native_scope_datetime_and_real_engine_age;
   test_native_collect_one_datetime_real_assessment;
   test_native_clock_context_restores_after_failure_and_cancellation.
   Record the meaningful expected red on the old source before the source fix,
   then freeze all new assertions/helpers/imports/main. Existing tests stay exact.
   Use the real project runner; on this bound44 base the additive command makes45.
   If integrated after the independent archive task,46 commands are required;
   count the actual complete workflow rather than dropping the other new test.
   After focused/CLI/scope/contract checks, request the lead's exclusive full slot
   and freeze exact clean source/helper before one complete gate. Compare all
   tracked bytes before/after. Actual Linux all commands/two locked builds,
   fresh independent review at least10/12 with spec=2/invariants=2, and adversarial
   none precede integration. No own merge or push except a lead-authorized branch
   CI push. Original failed runtime controls are never relabeled by source PASS.

## Threat model and evidence

Never convert a missing critical observation to low risk, alter a pinned age or
allow a wall-clock fallback to hide a broken native clock. A narrow adapter repair
must not skip real engine logic, weaken source identity checks, change retries or
erase native intents. Tests make physical network fail immediately and preserve
actual CI rejection flags. Use external temporary roots; Git ancestry refusal is
not bypassed. Keep test/runtime private values outside the shared tree and safe
reports aggregate only. Actual native control is a later separately reviewed,
one-shot configuration with the newly published source pin; no live call here.

READY evidence must bind test-first commit/red, frozen acceptance hash, exact
source scope, both real handoffs, restoration/mutant, official configured gate,
actual Linux source/builds and source-bound sealed review artifacts. State all
unchecked scientific/runtime dimensions. No Worker upload is required for this
bench-only source change.

## Amendments

### A1 - Isolate only the offline fixture directory boundary

2026-10-20, before the first acceptance commit: conflict search finds that real
core._private_directory deliberately rejects actual CI/GITHUB_ACTIONS. Existing
native fixtures clear these flags, so reusing them would contradict this task's
requirement to retain real flags. The implementation contract is unchanged; name
the exact test isolation here instead of silently bypassing a real CLI refusal.

Only inside the new offline unittest fixture, after characterizing the unmodified
core/native/public CLI refusal under actual CI/GITHUB_ACTIONS before any fixture
write, a finally-restored mock of core._private_directory may validate the exact
fixture runtime/private directories. It must restrict inputs to those fixed
external fixture roots and retain real native.external/private_path checks,
ancestor and alias rejection, and disjointness. Do not substitute general
arbitrary path validation, clear real flags, patch a production guard/source or
run a live action. Physical network/default NativeWorker entry is forbidden and
must fail immediately. Test helper state and module/environment bytes are restored
on every exit. The mock supplies only a clock/engine seam fixture; it is not real
native transport, containment, private-runtime or LIVE eligibility evidence.

This named addition applies to the initial new test helpers and three unchanged
method names before they are committed/frozen. Existing acceptance files and all
source guards remain exact. No later test weakening or widened source scope is
authorized by A1.

### A2 - Preserve network guards and real worker class identity in fixtures

2026-10-20, before any source repair: initial acceptance c86d549 stops while
Windows asyncio constructs its internal event-loop socketpair. It is retained as
a fixture/platform failure, not the meaningful engine-clock red. Executor's
single platform-helper commit e4ac59e initializes stdlib asyncio.Runner before
installing network mocks, runs the same coroutines on that runner with all mocks
active, and closes it after mock restoration. It was committed before this named
lead reconciliation; preserve that chronology. Its60 assertion-call ASTs are
independently compared with the initial test and remain exact.

The resulting old-source run reaches the real float.timestamp defect but also
exposes a second helper error: replacing the NativeWorker class with MagicMock
invalidates the real cleanup isinstance check. This dated amendment permits
exactly replacing that constructor guard with a mock of NativeWorker.__init__
that raises AssertionError("native_worker_forbidden"). Keep the real class and
isinstance identity, every physical socket guard and assert_not_called assertion.
Do not change inputs, assertions, method names, expected answers or source guards.

Commit this constructor-only test fix separately, recheck all60 assertion ASTs
against c86d549, freeze the exact corrected acceptance and rerun on unchanged old
source. Only a meaningful actual clock-contract red counts before the separate
source repair. Both original fixture failures remain distinct records. A2 names
these two bounded helper corrections only; no general test-change exception or
claim that earlier failed runs passed is introduced.

### A3 - Count the retained header-only missing response honestly

2026-10-20: corrected acceptance6044a2a reaches the meaningful old-source clock
red with unchanged tracked bytes. The two-line datetime repair then returns the
real engine unknown answer and preserves all intended clock/restoration checks.
Its sole remaining failure is a wrong new fixture accounting expectation: the
unchanged engine _fetch_json(mark_missing=True) returns NO_DATA immediately on
the fixture's HP404 headers and never reads that body. Six requests are invoked
and retired, while five bodies complete. This is a tested distinction between a
physical attempt, a returned header and an observed complete body.

Name exactly one assertion-literal correction in
test_native_collect_one_datetime_real_assessment: the expected accounting tuple
changes from (6,6,6,1,1,0,6) to (6,6,5,1,1,0,6). Preserve the six exact routes,
unknown verdict, sellability gap, endpoint provenance, all other59 assertions,
all fixture inputs and production code. Never force a body read or alter a
production counter to satisfy the erroneous test expectation.

Retain the first meaningful red and the actual intermediate one-failure run.
Commit this named one-literal test change alone before the source implementation
commit, freeze it, and prove it still rejects the old two-site timestamp
conversion in the same already allowed controlled regression mutant. Source
had been narrowly edited but uncommitted when this mismatch was found; retain
its external exact byte backup and do not rewrite that chronology. A3 changes
neither scientific acceptance nor any existing acceptance test or source guard.
