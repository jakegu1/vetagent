---
id: T-077
title: Register complete maintained suites from executable workflow commands
status: ready
design_status: adopted
level: 3
size: S
base: d06fba77321186ede837a01302ed6b59b6fcd94e
depends_on: [T-075_approved_maintained_responsibility_split, Root_incident_preservation_and_dispatch]
decisions: [ADR-0003_maintained_responsibility_amendment_20261103]
---

## Context and goal

The approved maintained native and clock commands use selectors instead of test
filenames. The current registration guard looks for filenames anywhere in the
workflow text. It rejects those complete commands while accepting a filename
in a comment or unrelated string. Repair that instrument: every existing test
file must have a real, complete registered command in its intended job.

This is registration-data repair under the approved responsibility split. It
does not change a product gate, threshold, budget, suite obligation or historical
result. It requires no new Owner product decision. Root has adopted this spec after preserving the failed-run evidence. The
executor must use the literal metadata-adoption commit supplied by the lead as
the contract base. The failed full remains failed and its old slot stays spent.
No actual full or quarantine change is authorized by this adoption.

## Scope and files

**In:** one registration helper and four bounded fixture-test functions inside
the existing, already registered `tests/test_decisions_enforcement.py`. Reuse the
unchanged offline parser as a read-only command reader. Keep the original guard's
workflow-exists and no-orphan assertions, its filename inventory, and every other
original assertion and runner obligation.

**Implementation file:** `tests/test_decisions_enforcement.py` only. No additional
implementation module is needed. The new acceptance functions are in this same
file; its existing `main()` discovers them automatically.

**Root metadata only:** eventual `lead/tasks/T-077-registration-guard.md`,
`lead/tasks/README.md`, `lead/STATE.md` and `lead/OWNER.md`, as needed for adoption
and the normal baton. Metadata adoption precedes the executor contract base.
Keep private paths, gate readings and incident identifiers outside these files.

**Out:** changes to `.github/workflows/test.yml`, any workflow step or command,
`.github/scripts/offline_suite.py`, `tests/test_deploy_gate.py`,
`tools/engine_versions.py`, `tests/test_engine_versions.py`, Source API behavior,
native/clock tests, frozen fixtures, catalogs, source profiles, manifests,
dependencies, parser grammar, deploy/lock/build rules, production/risk/data code,
operating-system or process controls, incidents/admission, budgets and thresholds.
No new test file, workflow step, broad parser, framework or dynamic fan-out.

## Named change to the existing test

**NC7-A — `test_every_test_file_runs_in_ci` registration-data seam.**
After the acceptance-only commit, use a separate commit titled
`T-077: named change (NC7-A command registration data)`.
In that existing function, replace only the raw-text membership data source
(`orphans = [fn for fn in files if fn not in ci]`) with the result of the new
`_registered_workflow_test_files(ci, files)` helper. The helper returns
`(registered_filenames, registration_errors)`. Compute the same complete orphan
list against `registered_filenames`, preserve both existing `check` calls and
their labels, and add a failing `check` for any registration error. A missing
workflow still fails and returns exactly as before. The same named commit may
add the helper and minimum stdlib import needed to load the existing parser.
No original assertion is deleted, bypassed, weakened, renamed or converted to a
skip. All other original functions and `main()` remain byte-exact.

No existing test in another file needs amendment. Preserve NC6-C's
`B12DispatchAcceptance.planned_workflow` and
`test_current_workflow_dispatch_is_real`, and
`MaintainedAdapterAcceptance.test_historical_workflow_fixture_cannot_qualify_current47_dispatch`.
An unexpected older-test conflict means BLOCKED for a named design amendment.

## Acceptance criteria

1. **Read actual commands, with a closed coverage rule.** Load a fresh namespace
   of the unchanged `.github/scripts/offline_suite.py` through the standard
   library, without calling `main()`. Use its `STRAY_BREAK`,
   `steps_from_workflow` and `SHELL_OPERATOR`; no second YAML parser or broad
   regular-expression workflow reader. Inspect command argv using the runner's
   actual whitespace split after its Python-prefix and shell-operator checks.
   Require a present, nonempty, refusal-free `test` job. Missing commands,
   refused syntax or stray line breaks cannot yield complete registration.
   Do not import or call Source API to discover coverage, execute a command, or
   read registry/Git/runtime data to parse the workflow.
2. **Whole-suite registration, with direct-script compatibility.** Only these
   exact six-token wrapper argv tuples can register the maintained files:
   `python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16`
   maps to `test_w40_native.py`, and the same prefix with `clock-all3` maps to
   `test_w40_native_clock.py`. Both must be in `test`. Unknown contract, profile,
   selector, extra argument, partial class, `adapter-test` staging subset,
   `verify-source` or old native/clock `legacy-test` grants no such coverage.
   Real direct `python tests/test_*.py` commands in `test` remain recognized.
   Native/clock direct commands must have no selection arguments. Preserve
   following arguments for other existing direct scripts, including
   `tests/test_backfill.py --offline`. Exact path tokens, not a substring inside
   a later argument, identify the executed file.
3. **Keep job boundaries and inventory completeness.** The sole existing
   live-only exception is direct `python tests/test_upstream_contract.py` in
   `upstream-contract`; recognize that exact command in that exact job by
   reusing the parser with a private namespace's `JOB` set to the fixed name.
   This cannot qualify an offline suite in another job. `test_backfill.py`
   still requires direct registration in `test`; its actual `--offline` command
   stays frozen and the existing Source API guard keeps that mode obligation.
   Every recognized test target
   must exist in the same test-file inventory; a registered-but-missing file
   is an explicit error even when absent from the orphan list. Every newly
   added unregistered `test_*.py` remains an orphan. Comments, labels, unrelated
   inline strings, no-ops and wrong jobs cannot satisfy either rule. Registration
   is not evidence that the registered child has actually passed.
4. **Meaningful tests first; four groups, exactly 24 fixed fixture cases.**
   Add only `_registration_fixture_checks` (local fixture harness), minimal
   stdlib test imports and these acceptance functions in the first commit:
   `test_registration_direct_and_maintained_commands`,
   `test_registration_rejects_textual_wiring`,
   `test_registration_rejects_unqualified_selectors`, and
   `test_registration_parser_and_inventory_fail_closed`.
   Each contains its six predeclared cases. The harness calls the actual
   unchanged `test_every_test_file_runs_in_ci`, with an external temporary
   workflow/test directory, the exact unchanged parser copied as fixture data,
   and captured `check` calls. Restore patched globals in `finally` or a scoped
   context; never invoke `main()` recursively. Fixture test bodies are inert
   stubs that fail if executed; forbid subprocess execution in fixture calls.
   Assert the specific orphan/error finding and overall acceptance, not merely
   absence of an exception. On the old guard, valid maintained cases fail by
   false orphaning and textual/legacy cases fail expected-rejection assertions
   because the old guard wrongly accepts them. Missing helpers/modules, syntax
   failures or imports are not acceptable REDs.
5. **Preserve the release contract.** Configured offline commands remain exactly
   47, in the same order, including approved native16 / explicit fixed-V1
   verify-source / clock3 responsibilities. No new step or count workaround.
   The helper does not hard-code the whole 47-command workflow or replace the
   Source API whole-workflow contract. All parser/deploy, engine-version and old
   test sources outside NC7-A stay byte-exact. Demonstrate detection of a
   raw-text-membership mutant and a widened-selector mutant in a controlled
   in-memory copy; assert exact match counts and never mutate shared source.
   A failed full run is never relabeled or resumed as a passing run.
6. **Contract and checks.** The first executor commit contains the four new
   acceptance functions and harness/imports only, with the old guard unchanged.
   Capture actual named fixture RED output before NC7-A; then capture focused
   guard GREEN at the fix head. Check the task-base tests-first contract, review
   the named-change diff line by line, and freeze every new acceptance input
   and assertion after the first commit. Independent Level-3 functional review
   must reach the project rubric with spec/invariants 2, plus no material
   red-team finding. Any full/project check, engine-version suite, actual
   native/clock or complete gate remains a separately issued, serialized Root
   operation after incident/readiness qualification. Focused fixture success
   is not full-source acceptance or release approval.

## Evidence required

- Literal metadata-adoption base, acceptance-only and named fix commits;
  contract-check result and exact named-change diff.
- RED and GREEN output from `python -B tests/test_decisions_enforcement.py`,
  identifying all 24 fixtures and their expected registration findings.
  RED shows a valid maintained selector's false orphan and a textual/legacy
  fixture's false acceptance through the actual old guard.
- Frozen-byte comparison for all out-of-scope paths and a static unchanged
  47-command/order comparison against Root's adopted workflow binding.
- Fresh independent focused results and bounded mutant observations. Every
  skipped, dropped, unrun or unobserved check remains explicit.
- Private accounting preserves the failed actual gate, spent slot and unrun
  tail. Do not copy private incident data into repository metadata/public claims.

## Risk, cost and stop rule

Level 3 is the lowest applicable level: `lead/QUALITY.md` explicitly treats
CI/release-gate behavior as high risk. Size S reflects one registration
instrument file; no runner, parser or responsibility change is authorized.
The realistic failure is a falsely green completeness claim caused by a comment,
wrong job, subset selector or missing file. The opposite failure blocks valid
complete maintained registration. Test both directions.

Planning estimate: no paid services and one working day for the bounded
implementation/review preparation, followed by Root's separately issued gates.
The design budget is one implementation/review cycle, four
design groups, 24 fixed cases, four new acceptance functions and one
implementation file. Stop for Root rescoping if a second implementation file,
new parser/API behavior, changed old assertion, different job policy, extra case
family, heavy execution or more than the configured two review rounds is needed.
Keep failed results and unmet prerequisites; do not move a bar to finish.
Root adoption and subsequent source/review/full phases remain distinct.

## Amendments

Root adopted the design without behavior amendments. The literal metadata
adoption commit is supplied in the executor dispatch and acceptance record.
