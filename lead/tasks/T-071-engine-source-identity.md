---
id: T-071
title: Qualify explicit historical W40 source identity without changing production
status: in_review
level: 3
size: M
depends_on: []
---

## Context and goal

See DESIGN and DEPENDENCIES. Build only the closed registry and read-only source-verification
primitive so a source fixture and its actually loaded code can be proved to be V1. Production
and the scientific modules remain byte-exact. Cost one bounded slice, fresh functional and
adversarial review. Stop before CI rerouting, price changes, real historical operations or
T047 adoption. Root must assign a formal T-number and accepted exact base before dispatch.

## Files in scope

New `bench/engine_versions.json`, new `tools/engine_versions.py`, new
`tests/test_engine_versions.py`, new `docs/ENGINE-VERSIONS.md` (technical only).
Root-owned `.github/workflows/test.yml` adds exactly `run: python tests/test_engine_versions.py`
through a separately serialized registration patch, coordinated with A. No old command changes
in this slice. Total five named paths. No `src`, existing `bench/*.py`, old tests, permissions,
locks, generated pages, research corpus, private paths, schema/API output or legal text edits.

## Required closed data and interface

Use the exact eleven members and Git blob/raw/canonical profiles in `catalog-inputs.json`.
Two supported profile IDs are `git-lf` and `observed-windows-crlf`; each contains a complete
fixed raw hash set. These are fixture profiles, not assertions of historic execution. Use
the exact source commit/tree there. Preserve six FROZEN entry order and canonical pins.
The new schema separates `engine_source_commit` from any old plan's declared `source_commit`;
the old field remains unchanged and is not upgraded to proof of engine execution.

Only fixed commands `verify-source <contract-id> <profile-id>` and test-internal source-view
preparation are in scope. No arbitrary executable/test/commit/path; no legacy-test CLI until
B1.2. Output is bounded fixed categories/hash metadata, no absolute host paths in public files.
Actual child paths may appear only in private local acceptance evidence.

Materialization reads fixed Git blobs, verifies membership/modes/hashes and caps before load,
writes one new external source view, and rehashes after use. Suggested fixed caps: 16 members,
4 MiB/member, 8 MiB total, 128 KiB registry. They are engineering safety bounds for a measured
1.27 MB closure, not scientific sampling caps; hitting one refuses with an explicit error,
never silently drops members. No dynamic closure growth or open archive extraction.
Use a fixed boundary marker as specified in DESIGN. No network/ref writes or full clone.

## Acceptance criteria

1. Closed schema and role selection satisfy V1-01; unknown or malformed inputs cannot select
   production bytes as historical. Missing fixed Git objects fail without a fetch.
2. Exact materialization/profile verification satisfies V1-02. Canonical equality is necessary
   but insufficient; raw profile mismatches fail. Missing/mutated member and alias/path escape
   refuse before source execution or evidence access. No partial success receipt.
3. A fresh isolated child verifies actual V1 module paths/code/defaults/closure/RPC roots using
   the original predicates (V1-03); it cannot inherit current `risk` through module state.
4. Existing synthetic core plans validate under matching raw V1 only and retain every byte;
   wrong bindings/profile refuse (V1-04/05). No actual old record/runtime is claimed verified.
5. No operational API is exposed. Default/help is offline; collect/recover/pilot/study/scheduler
   arguments and arbitrary test paths refuse without native actions. Production/science files,
   rules/labels/raw evidence, source pins, flags and current command set remain exact.
6. Tests-first contract, all accepted current checks, fresh functional/adversarial review and
   exact-source root gate pass. Root integrates only the accepted registration patch. No B1.2
   permission is implied by this slice's acceptance.

## Tests first and executable plan

First commit adds the new test file alone; new tests fail cleanly for absent registry/helper.
Use standard unittest or the project's dynamic harness, with the proposed V1-01..05 test
names in ACCEPTANCE-MATRIX. Fixtures include a core plan made from original V1, both exact
newline profiles, same bytes/wrong role, missing Git object, changed member, correct source
with wrong loaded module/default and unknown complete tuple. No repository mutation; in-memory
or external-copy mutants must assert target count and preserve bytecode isolation.

Light command after tests commit and helper implementation:

```
python -B tests/test_engine_versions.py
python -B tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf
python -B tools/engine_versions.py verify-source w40-v1-e3ec46a observed-windows-crlf
```

Root grants an exact-head heavy slot before `python lead/checks.py`. Do not run the old
native suite as an unscheduled nested side effect of these light tests. Preserve all
original CI/GITHUB_ACTIONS values; existing scoped old fixture behavior is not authorization
for the wrapper to clear flags. No new test bypasses CI guards.

## Conflict search and named changes

New filename/symbols have no published collision in the B0 search; recheck on assigned base.
No existing tests change. The current six canonical frozen pins and old direct native commands
must still pass on the unchanged production parent. Registration is additive and root-owned.
Unforeseen old conflicts require a named amendment; do not reinterpret them as allowed.

## Evidence, risk and rollback

READY includes exact base/tests-only/fix/head, member and helper/test hashes, AC-to-command
mapping, raw UTF-8 stdout/stderr/native exits, both byte profiles, one observed schema/profile
and wrong-runtime mutant red, unchanged source manifest, all failures and untested dimensions.
The threat is accidental cross-version import, raw normalization silently rebinding an old
plan, missing-object auto-fetch, path alias escape or a green verifier that never examines
actual code. Review this finite mechanism only; it is not a T047 seed/archive security review.
Rollback by a normal inverse commit before B1.2, retaining evidence and registry history.

## Root accepted R2 amendments and current dispatch

Owner explicitly approved the exact B historical-source/test-context scope on 2026-11-02, after both R2 design reviews. This approval accepts the bounded design, not this implementation or any historical execution. This task is B1.1 only: implement verify-source and test-internal source-view preparation; reject legacy-test and all operational commands in this slice. R2's shared legacy-test grammar is a later B1.2 requirement and does not authorize dispatch now.

Mandatory R2 clauses are authoritative over the original draft: both explicit git-lf and observed-windows-crlf identities qualify only their own complete raw profile, with no default/OS/failure fallback; four independent result layers and all applicable expected vectors follow the accepted R2 AMENDMENT, RECEIPT-CONTRACT and ACCEPTANCE-AMENDMENT. These documents are bound by revision-manifest SHA256 f9425edc841ee3c27d01f8feb94c2810f0cefb3df3b4b618b8dc8cc705b5815d. source_fixture and current loaded_runtime may pass, but B1 historical_record_tuple and historical_interpreter remain explicitly not_evaluated, unavailable or unknown as appropriate; historical_execution_qualified is always false. No complete historical-record/interpreter input or operational verifier is exposed. Current generic core is unchanged and does not become a universal registry.

Implement on exact base e3ec46ad8e4c485243fe20a606ac263564d350f0 in the existing B worktree, using branch codex/t071-engine-source-identity-20261102. Root owns additive workflow registration, task/index/STATE integration and all actual heavy gates; do not change the two existing native commands or any old assertions. First commit contains only new acceptance tests (and permitted synthetic test fixtures only if explicitly named by an amendment); the original fixed five-path scope otherwise stands. Missing implementation should produce an intentional assertion red, not an import/collection crash.

Global refs are shared. Root permits this one branch creation before the T069 gate lease; register and confirm ref-write freeze immediately afterwards. A's imminent author full gate has priority. You may finish a clean-source shared compressed baseline, waiting for its actual completion, then draft acceptance tests and run bounded meaningful parent reds with no ref writes. Do not commit, tag, create more refs or begin implementation until root grants a ref-write window; the tests-only commit must precede source implementation. Do not run full/native/benchmark work without a separate exact-source root slot. A source workflow remains the original45 steps; B's new registration needs its own updated source/count instrumentation qualification, not reuse of an unchanged45 receipt.

Goal completion requires author READY evidence after all assigned checks. Report milestone TESTS_PREPARED_FOR_COMMIT, any concrete blocking old-test conflict, and SOURCE_READY_FOR_FULL with exact chain/head. No root merge/push/deployment authority is delegated. T047/T049/T050 and the original partial T068 candidate remain held; the two price repairs are not part of T-071.

## R1 named additive correction

Source764113e preserves the original fourteen tests and passes both explicit
present-runtime profile commands. Independent review requires the already accepted
result-vector cases: runtime not checked, historical evidence unavailable and
historical evidence unknown, plus rejected historical-promotion vectors. This is
an incomplete test obligation, not an observed historical qualification bug.

Add test_r2_all_valid_result_layer_vectors, test_r2_rejects_result_layer_promotions
and test_r2_real_receipt_uses_layer_guard first in a new tests-only commit. Retain
the original fourteen methods, inputs and assertions exactly. Then add a pure
internal four-layer receipt guard and connect it to actual verify-source/CLI
emission. The guard must reject status copying, promotion and bypass mutants.
Rejected results remain sanitized/nonzero. No new historical input, file reader,
command, operational adopter or execution qualification is authorized. Real
verify-source histories remain not_evaluated with the original fixed reasons.

All source/full-gate/review duties remain. Root registers the additive step after
the corrected exact source qualifies for that stage; old commands stay intact.
