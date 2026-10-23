---
id: T-055
title: Distinguish a disappeared Linux process from inaccessible identity
status: ready
level: 2
size: S
depends_on: [T-046, T-052]
---

## Context and goal

Actual source Linux run39913228133 fails the existing partial-acquisition recovery
test: reading an already opened /proc PID stat file races with exit and raises
ProcessLookupError, errno3. identity_alive catches FileNotFoundError as absent but
misclassifies ProcessLookupError as cleanup_uncertain. A pure offline fixture
reproduces the same exception at the unchanged parent. Treat this explicit process
absence as absent while keeping unreadable or malformed identity fail closed.

## Scope

- bench/w40_native.py: only identity_alive's Linux stat-read exception boundary.
- Additive acceptance in the registered tests/test_w40_native.py module.
- This task and lead status/review records for governance.

No existing assertion or fixture input changes. Preserve the Windows path, PID
creation matching, zombie handling, retirement actions, network, policy/clock
limits, all T047 archive/queue code, permission files and scientific sources.
This is an independent regression repair, not a retry of the held T047 review.

## Acceptance

1. Commit new tests alone first. Mock only the Linux stat read/platform in a
   bounded offline fixture; the parent reproduces cleanup_uncertain on ESRCH.
   Both FileNotFoundError and ProcessLookupError return False after the repair.
2. PermissionError and unrelated OSError retain cleanup_uncertain. Valid matching
   creation is alive; mismatched creation and zombies are absent. Malformed stat
   remains uncertain. No process kill, real child or Vendor request is needed for
   this deterministic regression witness.
3. Change only the named boundary, retain all old tests, and show the new test
   fails if ESRCH handling is removed. Run the focused native module and the
   configured full45 with native exits, exact-head/raw-byte preservation and
   external temporary storage. The separately measured float-assertion defect in
   T056 may be integrated as an explicitly named test-only companion before the
   combined gate; do not hide either original failed run or claim it passed.
4. Obtain a fresh independent review and actual source-bound Linux checks before
   authorized integration/publication. Combined post-integration/master checks
   with T054/T056 must pass; no Worker upload or scientific enrollment follows.

## Evidence and risk

Keep tests-first/source SHAs, original red, deterministic all-branch witness,
meaningful caught mutant, native logs, pre-start ordered commands/source freeze
and tracked bytes before/after. The material risk is confusing inaccessible
identity with absence, so only the two explicit disappearance exceptions may
return False. Never broaden the whole OSError catch or weaken retirement proof.

Conflict search must name existing identity_alive/cleanup_uncertain callers and
tests. No new test module or workflow registration is required. Heavy local gates
remain serialized by the lead; isolated Linux may overlap.
