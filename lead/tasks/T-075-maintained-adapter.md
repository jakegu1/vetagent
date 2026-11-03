---
id: T-075
title: Separate maintained native regression execution from historical source qualification
status: ready
level: 3
size: M
base: bb6e1b2cc5e602e94f0560c37dbc3bd79674edab
base_role: code_parent; formal_tests_first_base_is_the_actual_root_metadata_adoption_commit
depends_on: [T-071, T-072, ADR-0003, Owner_maintained_scope_approval]
decisions: [ADR-0003_maintained_responsibility_amendment_20261103]
---

## Context and observable goal

T073 currently exercises original13/clock3 on an immutable original adapter, and
only staging3 on the maintained adapter. Exercise all preserved native16 and
clock3 on the actual maintained candidate plus fixed V1 dependencies, with explicit
historical provenance remaining independent. This proposal is justified by that
coverage gap, not by a desire to turn the failed original execution green.

The Owner approved this exact responsibility scope on 2026-11-03. Root adopts
the independently accepted original design and exact R2 addendum as T-075.
The frontmatter base is the code parent, not the tests-first contract base.
The latter is the actual metadata-adoption commit issued in the Root dispatch.
Only the separately dispatched executor phase is authorized. Workflow registration,
source review, incident admission, heavy gates and publication remain Root-owned.
The historical pending-approval labels in the verbatim annexes below are superseded
by this adoption. Their substantive acceptance criteria and bounds are unchanged.

## Scope and files

Executor source files: tools/engine_versions.py, tests/test_engine_versions.py and
docs/ENGINE-VERSIONS.md. Root-owned registration: .github/workflows/test.yml,
the eventual task/index and ADR0003 amendment. No new generic catalog/framework,
engine copy, source module, runner/parser or test file is needed.

Permitted symbols are a closed maintained_context_sources builder, a two-selector
maintained_test dispatcher, the unique validate_maintained_receipt(value) validator, fixed ID
membership metadata, main grammar/help, workflow_dispatch_contract, and the exact
legacy native/clock execution-eligibility check. Reuse existing bounded Git/source
view/launch/admission primitives. Preserve historical verify-source functions,
_validate_result_layers and both historical source profiles byte-exact.

Out: native/core/risk/labels/backlog/probe/dataset/clock source edits, original11
registry edits, current native tests/helpers/runner edits, FROZEN/hash refresh,
archive/safety/process changes, diagnostics that reinterpret this incident,
arbitrary selectors, old-artifact rewriting, T047/49/50/68, production/Vendor calls,
new snapshot or recovery/admission policy. The existing QA quarantine is a separate
unsatisfied prerequisite, not something this task can repair.

## Fixed interfaces

```
python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16
python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3
```

Only these selectors are new. Existing verify-source, historical dataset legacy
execution and eight-member staging3 adapter-test remain supported as before.
Under the explicit Owner-approved scope, both CLI and public legacy_test calls for the
old native and clock runners refuse with legacy_native_execution_unqualified,
wrapper2/not_run, before creating an operation or child. Unknown contract/profile/
runner checks retain their original refusal semantics. Do not quietly leave a
second executable entry point that bypasses the new eligibility boundary.

Read-only validation of old receipt schemas remains; failed legacy evidence is
never promoted or deleted. A metadata reader's acceptance is not execution
eligibility. The old historical RUNNERS identity/count metadata may remain for
that reader, while execution eligibility is explicitly narrower.

## Acceptance criteria

1. **Closed grammar and distinct roles.** Add only the two fixed selectors above,
   git-lf and the fixed V1 dependency tuple. Unknown/missing/extra selector, caller
   path/class/commit, profile fallback, malformed registry/object or wrong role
   refuses before launch. Explicit old native/clock eligibility refusal applies
   to both supported calling surfaces. Verify-source and dataset behavior, old
   profiles, all17 original acceptance methods/helpers and original four-layer
   guard remain exact. Show meaningful pre-fix pure metadata/spies, not actual
   whole native tests, for each new boundary.
2. **Exact member recipes.** Build native9 and clock8 exactly as CONTEXTS.md and
   closed-contexts.json specify. Candidate members come from the actual clean
   candidate commit/tree with mode/blob/canonical/physical-raw identity; fixed
   support members come from original V1 objects, locally, without fetch. Missing,
   duplicate, alias, extra, wrong profile or changed member refuses. Rehash before
   and after success/failure. The historical workflow member cannot certify the
   current real workflow. A common10-member view is not substituted without a
   newly reviewed explicit recipe. No old catalog or FROZEN member is changed.
3. **Whole unmodified obligations.** native-all16 runs the candidate native file's
   original __main__ with exact original13 plus staging3; clock-all3 runs the
   unchanged original clock __main__ with exact3. Preserve every old method,
   assertion, helper, order, runner, actual subprocess, cap, deadline and clock
   predicate. Check exact unique top-level ID sets and digest, with no skipped,
   expected-failed or swallowed case. No full native/clock is embedded in the
   version suite; its unit positives use bounded spies. Historical dataset9 still
   executes once inside that suite and current dataset9 remains a separate step.
4. **Truthful runtime and execution evidence.** The actual test child runs unchanged
   code_manifest and engine_bindings against the selected fixed V1 dependency.
   Bind actual PID/operation nonce, modules/interpreter, distinct context/runtime
   seals, exact IDs, actual wrapper/child exits and bounded complete/prefix stream
   states. Use engine-maintained-adapter-execution-v1, distinct context_source,
   maintained_loaded_runtime and maintained_tests fields. All original-V1,
   historical and production-V2 promotion flags remain false/unsupported. Neither
   source proof nor execution proof certifies the other domain. Refuse coherent
   relabels across the old11, old staging8, maintained9/8 and production roles.
   Keep16/4MiB/8MiB/128KiB/1MiB/16-operation and900s/180s limits, all original
   native resource limits and A1 incomplete-deep-telemetry semantics unchanged.
5. **Exact actual47 and production responsibility.** Root replaces only38,39,40
   according to workflow-inventory.json: maintained native16, explicit historical
   verify-source LF, maintained clock3. Other44 commands/order, live jobs,
   --offline backfill, deploy/bot/parser/runtime-pin duties remain unchanged.
   Existing staging3 stays a supported diagnostic command but is included in16,
   not an additional workflow step. workflow_dispatch_contract registers only
   this exact new47; the pinned bb6 old47 is registration_pending, never accepted
   as the new release gate. Missing/commented/no-op/extra selector or swallowed
   child exit must fail. Actual current-risk/HTTP/MCP/numeric/service tests use the
   sole evolving src/risk.py, never the fixed view. Preserve the existing original
   native changed-source refusal test; an actual later V2 repair additionally
   needs actual repair-head current regressions and original source/binding
   rejection. Synthetic refusal cannot qualify that future head.
6. **Incident and eligibility cannot substitute for qualification.** Keep failed
   original execution and all old artifacts unchanged. Unknown ownership or
   postlaunch evidence failure persists quarantine/unfinished admission refusal;
   failed quarantine publication cannot finish an operation. Exact finished-state
   identity remains required. No new action, version, scope, source or ledger can
   clear the current incident. Test these seams with isolated synthetic metadata,
   preserve actual known exits and unknown values, and provide an independently
   reviewed root-operator binding before any separately authorized heavy slot.
7. **Contract and complete acceptance.** New acceptance tests alone first, actual
   meaningful REDs then finding-specific fixes; exact named changes below in
   separate correctly prefixed commits, no rewrite or checker exception. Full
   task-base contract must hold with old originals preserved. Independently review
   source at least10/12, spec/invariants2 and applicable no-material boundary
   findings. After independently qualified incident retirement/admission and new
   operator readiness, root may separately issue serialized exact-source author,
   independent and integrated new47 slots, followed by actual normal feature/
   master CI, upstream/backfill and locked-build gates. No such slot, retry,
   publication or merge is granted by this draft. Failure stays failed; a new
   source does not automatically consume or replace the failed author slot.

## Tests and named changes

NAMED_CHANGES.md is the exhaustive proposed amendment. Everything not explicitly
listed stays byte-exact; an unexpected conflict means BLOCKED, not opportunistic
assertion editing. This includes the original native13 and clock3 files and the
original17 B1.1 methods/helpers. The existing whole historical dataset and
staging3-domain tests remain exact.

## Evidence required

READY must provide task-base/test-only/fix SHAs and actual RED/GREEN originals;
exact old17/native13/clock3/staging3 preservation; complete9/8 member provenance
and source/runtime seals; coherent negative receipt vectors; exact parser/47
inventory and actual registered commands; actual complete native16/clock3 IDs and
exits only from separately authorized slots; unchanged current production and
applicable real V2 negative evidence; all-ref/raw/mode/main/env/store gates and
power completeness. Preserve partial fields, unknown and missing after-capture
states instead of filling them from a different layer or a previous green run.

## Risk and split of responsibility

The Level3 risk is changing the duties of a release gate and accidentally promoting
a maintained result into historical/production proof. The threat model includes
wrong source role, missing workflow support member, fake/nonzero/no-op execution,
truncated evidence and a new version bypassing quarantine. No native safety or
process-control mechanism is implemented or examined by this task.

Keep this M task to three source files plus root's one workflow registration.
Root's ADR/task adoption and private operator readiness are separate bounded
administrative/acceptance phases. A generic support-version registry, parser
change, source dependency edit or extra safety feature requires a new design,
not expansion of this draft.

## Exact accepted named-change annex

The following annexes are reproduced verbatim from the accepted immutable
design. Their historical pending-approval labels are superseded only by the
verified Owner receipt; root task/base adoption and implementation dispatch are
still required. Where NC6-D is incomplete in the first annex, the exact R2
addendum takes precedence. No test or source has been edited by this projection.

# Proposed acceptance amendment, approval pending

This is an exact proposed change list for a future root-issued task. It authorizes
nothing now. Existing tests are not edited by this design.

## Preserve verbatim

All EngineVersionAcceptance original17 methods and their helpers, including the
already accepted exact NC3 form, remain byte-exact at bb6. Preserve every original
native13 and clock3 method/assertion/helper/runner and the current staging3 source.
No native-test source file is in scope. Preserve these B12 methods verbatim:
test_whole_historical_dataset_dispatches_once,
test_receipt_scopes_match_executed_domain,
test_current_adapter_context_is_separate_and_complete,
test_original_native_refuses_changed_production_source, and
test_finished_operation_state_requires_exact_identity. Keep existing generic tiny
view/observation/CLI/subject helpers unchanged.

## Proposed named changes, each in a separate commit

Use the eventual real task ID and exact `T-NNN: named change (NC6-X ...)` prefix.
These are new prospective changes to previously frozen B12 tests, requiring the
new accepted amendment; none is silently covered by the earlier NC5 permission.

| Name | Exact scope and changed expectation |
|---|---|
| NC6-A | B12DispatchAcceptance.test_legacy_dispatch_whitelist_and_exact_argv: retain its unknown grammar refusals; add fixed native/clock legacy refusal with no child/operation. Move only its two successful spy vectors to maintained_test(native-all16/clock-all3), expecting16/3 IDs,900/180s and the new explicit domain/runner. Keep nonzero/refusal/one-launch assertions. |
| NC6-B | B12DispatchAcceptance.test_legacy_execution_and_exit_are_real: preserve its actual tiny-child0/7 block and all qualification negatives. Move only its final fake-exit7 invocation from legacy native to maintained native-all16; read maintained_tests instead of legacy_tests, retain actual child7/wrapper7/failed/exact one runner assertions. |
| NC6-C | B12DispatchAcceptance.planned_workflow and test_current_workflow_dispatch_is_real: construct the exact three replacements from pinned bb6 old47, assert new47 registration, old47 pending and unchanged44 order. Keep all comment/no-op/extra selector/backfill mutation refusals, retargeting their command literals to the two new maintained commands and explicit verify-source. The former old46 actual-count alternative is no longer a valid new-registration expectation. |
| NC6-D | B12ReviewRegressionAcceptance.test_postlaunch_evidence_failures_preserve_admission_quarantine: change only its dispatch call to maintained_test native-all16 and the result test-layer lookups to maintained_tests. Preserve all8 vectors, capture spies, every admission/state/exit assertion, caps, valid A1 deep-null positive and every failure mode. Subject/observation helpers stay exact. |
| NC6-E | B12ReviewRegressionAcceptance.test_dispatch_receipt_cannot_cross_source_and_case_domains: keep every current adapter8-to-legacy relabel and malformed/type/hash/duplicate/exit/counter negative. Legacy native/clock/CRLF positive reader fixtures become explicitly synthetic closed metadata, because the executor is now ineligible; no real legacy native is run. Add genuine maintained-spy native16/clock3 receipts, distinct maintained9/8 identity/category vectors, and relabels in both directions. Keep existing current dataset and adapter3 positive cases and their original counts. Native13/clock3 legacy metadata reader counts remain13/3; maintained counts are separately16/3, never relabelled. No negative family or assertion strength is removed. |

For NC6-E, synthetic reader fixtures must be produced by a new local pure metadata
helper, not by importing a saved old executable module or invoking the withheld
API. They must have no provenance claim outside unit data. Their contents bind
the same old11 identities, expected ID sets and profiles. Existing real failed
receipts must retain failure/unknown semantics when read. Full originals are
checked by private root review rather than committed private payloads.

## Proposed new acceptance block

Add exactly seven methods under MaintainedAdapterAcceptance in the existing
registered tests/test_engine_versions.py. First commit adds these alone; they
initially fail on missing closed maintained behavior, not an import/typo error.
They use bounded metadata/spies; no new whole native/clock inside the unit suite.

1. test_maintained_selectors_and_legacy_execution_eligibility
2. test_native9_and_clock8_source_closure_and_actual_candidate_identity
3. test_maintained_original13_staging3_clock3_ids_and_real_exit_separation
4. test_maintained_receipts_cannot_qualify_historical_or_production_domains
5. test_historical_workflow_fixture_cannot_qualify_current47_dispatch
6. test_maintained_failure_and_quarantine_admission_remain_closed
7. test_legacy_receipt_reader_preserves_failed_and_unknown_states

This proposes34 version-suite methods (existing27 plus7), not a result measured
here. The historical dataset remains one nested full9 child, not an extra
workflow step. Meaningful mutations must expose missing workflow member, omitted
original/staging ID, wrong V1 dependency, substituted old adapter, V2 risk drift,
no-op/nonzero child, adapter/historical promotion and quarantine bypass.

## Conflict-search result and stop rule

conflict-search.json records ten matched existing methods/helpers; no other
tests/test_*.py contains the searched dispatch terms. Four matches are explicitly
preserved above or in original17; six test methods/helpers are covered by the
five named groups (NC6-C contains its helper plus method). Declarations and exact
current/proposed command inventory are separately bound in workflow-inventory.json.
The deployment parser reads generic Python commands and contains no selector
whitelist requiring a parser edit. Its existing enforcement tests remain exact.

Refresh this search at the eventual task base. Any additional changed assertion,
helper, selector, parser or dependency is a new conflict for root review. Do not
apply the current draft as a blanket permission to edit the complete test file.


## Exact accepted R2 precedence annex

# SPEC_READY_R2: NC6-D maintained-validator spy seam

Status: design revision only, pending independent R2 review. This addendum closes
one Definition of Ready gap; it grants no implementation or execution permission.

Applies only to the original B12 design package whose manifest SHA256 is
4fdd5eb4ea5673c974d09b6ad3ed96b23dbc20774c65ad6a1b950755f8b86348.
That manifest and all19 members remain byte-exact. Read them by reference; no
replacement copy or rewritten original spec is supplied.

## Exact pending-spec symbol clarification

In PENDING_SPEC.md's permitted-symbol paragraph, the phrase "a separate maintained
receipt validator" means exactly this single new module-level function in
tools/engine_versions.py:

`validate_maintained_receipt(value)`

The maintained dispatcher must resolve and call this exact module attribute for
its pre-publication receipt validation, before receipt publication and operation
completion. Maintained CLI receipt validation must use the same attribute. A
captured alias or a different validation route cannot replace this injection
point. This names the already proposed guard; it adds no alternative route or
weaker guard. Its complete constraints remain the original pending spec's AC4.

The existing validate_dispatch_receipt and _validate_result_layers bodies remain
unchanged. This revision does not make the historical/staging validator accept
maintained receipts, relax either domain, or authorize changes to old guards.

## Exact NC6-D additional permission

NC6-D in NAMED_CHANGES.md retains its already specified dispatch-call migration
to maintained_test/native-all16 and its two result-layer lookups to maintained_tests.
In the same one existing method, additionally allow exactly these two references:

```diff
- original_validator = m.validate_dispatch_receipt
+ original_validator = m.validate_maintained_receipt

- patch.object(m, "validate_dispatch_receipt", side_effect=validate)
+ patch.object(m, "validate_maintained_receipt", side_effect=validate)
```

The first reference is the original source line728; the second is line737 in
tests/test_engine_versions.py at bb6e1b2cc5e602e94f0560c37dbc3bd79674edab.
The existing local validate(value) spy body and its timing remain byte-exact:
receipt_protocol plus seen raises VersionError(child_protocol_invalid); every
other mode delegates to the original_validator saved before patching.

These are the only newly permitted edits. Keep all8 mode names and order,
fixture inputs, write/capture/launch spies, local helper bodies, caps, assertions,
admission/state/exit checks, known child0 retention and the A1 valid deep-null
positive unchanged. No assertion/input change, new case, skip, expected failure
or reinterpretation of the negative protocol mode is permitted.

## Single review bar

For receipt_protocol with a valid launched spy report, the patched attribute and
the actual maintained dispatcher validation attribute must both be
validate_maintained_receipt. The existing spy therefore raises at the intended
postlaunch, pre-publication seam; the unchanged assertions still require admission
refusal, unfinished/quarantined state, wrapper nonzero and retained known child0.
Without both reference migrations the plain-text counterexample in
CONFLICT_AND_COUNTEREXAMPLE.md remains possible. No runtime experiment is claimed.

All other adopted/proposed facts remain outside this revision: native9/clock8,
original13+staging3=16, clock3, actual47 with unchanged44, old17/catalog preservation,
the new Owner responsibility decision, and current heavy/incident HELD status.
The new design/source/context does not clear either quarantine. B stops at this
small R2 packet; independent review and any later implementation remain root-owned.

## Root issue record required before execution

Code parent: bb6e1b2cc5e602e94f0560c37dbc3bd79674edab. Proposed executor branch: codex/t075-maintained-adapter-20261103.
Root must issue the literal hash of its task/ADR metadata adoption commit as
the formal tests-first base; the executor must not infer it from the code-base
frontmatter. That commit does not yet exist in this packet. Use real T-075
commit titles, including T-075: named change (NC6-A/B/C/D/E ...).


## Adopted exact context appendix

# Proposed closed contexts and proof boundaries

No context was materialized or executed. closed-contexts.json records exact
existing object identities and sizes for static review. Candidate commit bb6 is
the inspected design subject, not a permanent future adapter pin.

## Member recipes

The fixed6 are bench/goplus_quota_probe.py, bench/w40_evidence.py, src/risk.py,
bench/labels.py, docs/BACKLOG.md and tests/test_dataset_replayable.py, all selected
from e3ec46ad8e4c485243fe20a606ac263564d350f0 with the original git-lf hashes/modes.
They are required by unchanged FROZEN and core._bindings, including dependencies
that a particular test path only hashes rather than imports. No fixture copies
the evolving production risk file.

| Fixed selector | Members | Why every extra member is required |
|---|---|---|
| native-all16 | fixed6 + actual candidate bench/w40_native.py + actual candidate tests/test_w40_native.py + fixed original .github/workflows/test.yml =9 | The original13 plus staging3 are in the candidate native-test file. NativeAcceptance.test_w40_native_cli_and_existing_contract reads workflow and asserts its old direct-run literal. Current47 lacks that literal, so substituting current workflow would break the unchanged assertion. |
| clock-all3 | fixed6 + actual candidate bench/w40_native.py + original tests/test_w40_native_clock.py =8 | The clock file imports risk/core/native, reads only fixture-generated data besides FROZEN6, and needs neither the native-test file nor workflow. Its current blob equals the original ddd83b387f5ab2baaed819d19535528978dbd32c. |
| Existing staging3, unchanged | fixed6 + candidate native + candidate native tests =8 | Only its selected class runs, so the old13 workflow-reading method does not execute. It cannot substitute for native-all16. |
| Optional common superset | fixed6 + candidate native/tests + original workflow + original clock =10 | Convenient but larger; do not mislabel it8 or9. Not the recommended per-command minimum. |

Local import/read closure was examined as static data: native imports core; core
imports labels and binds risk/labels/backlog; native tests dynamically import
native/core/risk and execute the native CLI from the same layout; clock imports
the same three modules. Native FROZEN requires all6 before use. Standard-library
imports and runtime-generated private fixtures are not additional source members.
The .git marker is a boundary file, outside source membership, exactly as before.
This establishes the recipe for the examined fixed selectors, not runtime
qualification; future source changes require renewed closure review.

## Grammar, provenance and runtime

Proposed new operation:

```
python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16
python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3
```

Only these two selectors, this dependency contract and git-lf are eligible. No
arbitrary classname/path/commit/profile, host-default fallback or latest-source
resolution is accepted. Read the exact clean candidate HEAD/tree and required
member modes/blobs/raw/canonical hashes before launch and after success/failure.
The named candidate may evolve only through ordinary independent source review.

Native runs the complete unchanged candidate __main__ harness: original13 plus
exact staging3. Clock runs the complete unchanged original clock harness. No
unittest filtering, suppressed failure or changed assertion makes the count pass.
The same actual test child runs unmodified code_manifest and engine_bindings on
the fixed V1 risk dependency. The maintained adapter hashes its own actual bytes;
it is not itself a FROZEN dependency. No FROZEN or source predicate is patched.

Proposed receipts use engine-maintained-adapter-execution-v1 and the explicit
domain maintained_adapter_on_fixed_v1_dependencies. They contain context_source,
maintained_loaded_runtime and maintained_tests, with distinct evidence digests,
candidate identity, fixed dependency/support identity, exact test IDs, actual
wrapper/child exits and source-view seal. They do not reuse historical
source_fixture=passed as a shorthand for the new9/8 membership.

original_v1_fixture_qualified_by_maintained_result=false,
historical_execution_qualified=false, current_production_behavior_qualified=false,
and positive V2 historical-native compatibility=unsupported are mandatory.
The unchanged historical verify-source result retains its independent four-layer
guard and11-member catalog. With no historical input supplied, historical record
and interpreter remain not_evaluated; known absence/unknown stay separate when
read as existing evidence. No new historical record-input API is proposed.

Neither a source seal nor a test receipt authenticates the other domain. Old
failed legacy receipts remain readable with their original schema/status; reader
compatibility does not make their old execution commands eligible. Metadata-only
unit fixtures must be explicitly described as synthetic, never actual V1 passes.

## Limits and future negative production evidence

Retain16 members/4MiB file/8MiB total/128KiB public receipt,1MiB streams/private
observations,16 scope operations and all original per-attempt/tree/byte/time bounds.
Use existing native900s and clock180s outer bounds, not a larger maintenance budget.
No amount of telemetry truncation grants completeness or a guessed numeric exit.
Unknown ownership and postlaunch evidence failures keep admission closed.

Current production checks continue to import the sole real current src/risk.py.
They do not import fixed V1 from these views. At each actual future V2 repair
head, independently show current-risk/service regressions and actual original
native source_drift/engine binding refusal. The current synthetic changed-source
negative remains, but cannot stand in for a real V2 repair-head measurement.
No positive V2 native compatibility is introduced by this design.


## Reviewed design-subject member identities

The following candidate identities describe bb6 only. Every actual later candidate
requires its own exact binding and ordinary review; they are not future static pins.

```json
{
  "clock": [
    {
      "blob": "18785d8def90ca7b166cabc219211e506c0a3fc4",
      "bytes": 37807,
      "canonical_sha256": "3ec1e7688240fbd705b386ee7680758e6606bb9354938e994927a440e6e4b8f4",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/goplus_quota_probe.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "06b7ceffea1024914d0d584908dae6b380bb9dd8",
      "bytes": 49658,
      "canonical_sha256": "2e312e319229402088f6f1aaf15e53460d41a56468d6dd7d249c4123734e140d",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/w40_evidence.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "be42fe24a818bbba9565a4991a2bc4c1e55f49cb",
      "bytes": 258720,
      "canonical_sha256": "67b52bd3f7610aa98d6ed5f94457e875d16b489f633be54d170453e313dd8d2d",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "src/risk.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "ff6d7ad02aabe1ccb247828c7b77e32875b95b12",
      "bytes": 18007,
      "canonical_sha256": "ebbb4585c9cd829dcd1fbd374a8147918fcc742e525909a326a357f9246ae75c",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/labels.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "6ba4a388d88fe24b7231428574a74ba297de1666",
      "bytes": 81140,
      "canonical_sha256": "0f0febb99e8cb2a7c0b14fba1affcf689b7ba40fc18af641e6478f1d267b3e1a",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "docs/BACKLOG.md",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "01ec092bc84c6566f9b32e07c765d6293a62ab8e",
      "bytes": 48248,
      "canonical_sha256": "db43e79361584716a6f48bd40cd1225ffc2d6c344391cedcb2d5e4fa9e44e1ab",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "tests/test_dataset_replayable.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "9b852267cd37dbce3bb0c29f4f439f33e15aba3b",
      "bytes": 104439,
      "canonical_sha256": "90635f95580a7df7a8a8d608d84aaea6cdf55cc6a8f3077153b16e1b006c07a8",
      "commit_for_design_only": "bb6e1b2cc5e602e94f0560c37dbc3bd79674edab",
      "path": "bench/w40_native.py",
      "role": "actual_candidate"
    },
    {
      "blob": "ddd83b387f5ab2baaed819d19535528978dbd32c",
      "bytes": 18353,
      "canonical_sha256": "37e96eb85efea6b20d984db2f0c1b5c0527f769ea0289f50dcacbd5441ed2f71",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "tests/test_w40_native_clock.py",
      "role": "fixed_v1_dependency_or_support"
    }
  ],
  "external_git_marker_not_counted_as_source_member": true,
  "native": [
    {
      "blob": "18785d8def90ca7b166cabc219211e506c0a3fc4",
      "bytes": 37807,
      "canonical_sha256": "3ec1e7688240fbd705b386ee7680758e6606bb9354938e994927a440e6e4b8f4",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/goplus_quota_probe.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "06b7ceffea1024914d0d584908dae6b380bb9dd8",
      "bytes": 49658,
      "canonical_sha256": "2e312e319229402088f6f1aaf15e53460d41a56468d6dd7d249c4123734e140d",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/w40_evidence.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "be42fe24a818bbba9565a4991a2bc4c1e55f49cb",
      "bytes": 258720,
      "canonical_sha256": "67b52bd3f7610aa98d6ed5f94457e875d16b489f633be54d170453e313dd8d2d",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "src/risk.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "ff6d7ad02aabe1ccb247828c7b77e32875b95b12",
      "bytes": 18007,
      "canonical_sha256": "ebbb4585c9cd829dcd1fbd374a8147918fcc742e525909a326a357f9246ae75c",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "bench/labels.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "6ba4a388d88fe24b7231428574a74ba297de1666",
      "bytes": 81140,
      "canonical_sha256": "0f0febb99e8cb2a7c0b14fba1affcf689b7ba40fc18af641e6478f1d267b3e1a",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "docs/BACKLOG.md",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "01ec092bc84c6566f9b32e07c765d6293a62ab8e",
      "bytes": 48248,
      "canonical_sha256": "db43e79361584716a6f48bd40cd1225ffc2d6c344391cedcb2d5e4fa9e44e1ab",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": "tests/test_dataset_replayable.py",
      "role": "fixed_v1_dependency_or_support"
    },
    {
      "blob": "9b852267cd37dbce3bb0c29f4f439f33e15aba3b",
      "bytes": 104439,
      "canonical_sha256": "90635f95580a7df7a8a8d608d84aaea6cdf55cc6a8f3077153b16e1b006c07a8",
      "commit_for_design_only": "bb6e1b2cc5e602e94f0560c37dbc3bd79674edab",
      "path": "bench/w40_native.py",
      "role": "actual_candidate"
    },
    {
      "blob": "f9e49ffb6b71f14c8993e17c650b54fd3afe1105",
      "bytes": 91675,
      "canonical_sha256": "4d9edd6c60df9563489c323ee1f34c24596b6dbeb8db2c5c4e1e0ca6a9f0bcd9",
      "commit_for_design_only": "bb6e1b2cc5e602e94f0560c37dbc3bd79674edab",
      "path": "tests/test_w40_native.py",
      "role": "actual_candidate"
    },
    {
      "blob": "e8fd47a52270608d44a6db06d8f26193def9a3eb",
      "bytes": 21798,
      "canonical_sha256": "06b9e9da04e626519ec8c7f972ddb3f871275d9cc1fe1ed81ccf508ffdacd9ba",
      "commit": "e3ec46ad8e4c485243fe20a606ac263564d350f0",
      "mode": "100644",
      "path": ".github/workflows/test.yml",
      "role": "fixed_v1_dependency_or_support"
    }
  ],
  "reason_clock_does_not_need_native_test_or_workflow": "clock module imports risk/core/native; its file reads are fixture-generated data and native FROZEN6 checks.",
  "reason_native_needs_workflow": "NativeAcceptance.test_w40_native_cli_and_existing_contract reads ROOT/.github/workflows/test.yml and requires the old direct-run literal.",
  "runtime_qualification": "not_run",
  "status": "proposed; not constructed or run",
  "unified_member_count": 10
}
```

## Root-owned current workflow registration

The code-parent workflow has exactly 47 commands. Replace only ordinal 38 with
`python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16`,
ordinal 39 with `python tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf`,
and ordinal 40 with
`python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3`.
The other 44 commands and their order remain byte-exact. Root registers after
source readiness and before any separately authorized heavy gate. The executor
does not modify the workflow, parser, deploy/bot duties or runtime locks.

## Initial dispatch boundary

The initial executor phase adds only the seven new MaintainedAdapterAcceptance
methods in its first test-only commit, with pure bounded metadata/spies. It stops
at TESTS_ONLY_READY, supplying immutable test source, exact command/import plan
and preservation evidence before any test execution. Root then issues a finite
focused execution plan for meaningful RED, named changes and minimum source work.
This source-work boundary does not grant a historical/native/clock/full execution
slot and does not clear any incident or quarantine.
