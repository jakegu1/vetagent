---
id: T-066
title: Measure packed Git storage in linked worktrees without false zero readings
status: done
level: 3
size: S
depends_on: [T-065]
backlog: B15 archive capacity measurement
---

## Context, benefit, cost and stop

The existing packed_mb helper walks ROOT/.git. That is a pointer file in a
linked worktree, so it reports zero while the shared object database contains
real packs. A normal checkout instead includes loose objects, logs and metadata
in a number described as packed storage. Both are measurement defects. The
capacity gate must measure the quantity B15 already names, without changing its
budget or triggering any migration. The independently measured current values
and operational trial receipts remain private.

Benefit: capacity warnings can actually work in the supported development
layout. Cost: one small guard repair, tests first, fresh independent and focused
adversarial reviews, the existing complete checks and normal publication gates.
Stop after the measurement repair. Do not clean disks, delete snapshots, archive
worktrees, migrate storage, change retention or build a storage-management system.

## Scope and conflict search

Implementation and acceptance: tests/test_archive_budget.py only. The existing
main automatically discovers test_ functions, so no workflow or runner changes
are required. Lead metadata and copied independent verdicts are lead-owned.

Searches cover archive_budget, packed_mb, BUDGET_MB, WARN_AT and RETAIN_DAYS
across tests, tools, bench and workflows. The configured runner invokes this
file; no other test calls packed_mb. All three constants, all existing numeric
budget/warning comparisons and the B15 decision row must remain exact.
No collector, engine, dependency, workflow, historical evidence, permission,
scientific source, T047 investigation or production behavior is in scope.

## Explicit named source changes inside the guard file

The guard implementation currently lives in the acceptance file. After the
first additive tests-only commit, permit one separate commit titled
T-066: named change (packed-size acquisition). It may change only:

1. The packed_mb implementation and its docstring, using Git's packed-storage
   accounting instead of walking .git. Return a numeric MiB value when measured,
   and None when measurement is unavailable.
2. The prologue/imports needed by that implementation, including correction of
   the old exact-server-storage wording. Existing-pack storage is not an exact
   GitHub allocation or clone estimate. Do not redefine B15 or its constants.
3. test_the_repository_is_inside_its_budget may add a fixed unavailable-measurement
   failure/early return before numeric formatting and comparisons. Preserve its
   original numeric budget assertion, warning interval and retention message.

Every other old function, the runner and all newly committed acceptance
functions stay exact. This is an explicit source-code change to a guard, not
permission to weaken tests. An unexpected old conflict means BLOCKED.

## Acceptance criteria

1. packed_mb uses read-only Git accounting for ROOT's shared packed object
   store and works in both a normal checkout and a linked worktree from an
   unrelated working directory. Use size-pack's KiB quantity converted by the
   original binary unit; do not count checkout data, loose storage, logs, refs
   or metadata as packed bytes. Compare a real tiny packed fixture against its
   pack/index files, including Git's KiB precision. Adding unrelated .git bytes
   changes neither normal nor linked readings. No real repository repack/GC.
2. Missing Git, failed commands, timeouts, malformed/duplicate/missing required
   statistics, undecodable output or implausible negative/invalid integers
   produce unavailable, never a zero success. A genuinely empty Git database
   may measure zero; a loose-only nonempty database has no complete packed-size
   reading and must be unavailable. Ordinary mixed loose/packed stores report
   the existing packed portion, without claiming a fully repacked clone size.
3. ROOT explicitly selects the measured repository. Execute a fixed argv list
   without a shell, finite command timeout and captured output. Ignore inherited
   Git routing variables that would redirect another object database, while
   preserving CI/GITHUB_ACTIONS flags. Never expose raw paths, exception text,
   config, stderr or arbitrary stdout in guard output. A native Git warning with
   valid successful statistics does not invent a failure or suppress a reading.
4. The actual gate rejects unavailable measurement. Literal boundary controls
   retain the current budget and warning behavior: below the warning threshold,
   at the warning threshold, just below the budget and at/above the budget.
   BUDGET_MB=200, WARN_AT=0.8, RETAIN_DAYS=90 and the decision row remain exact.
   Unknown is not under budget. Do not relax any comparison or silently skip.
5. Acceptance uses isolated temporary Git fixtures and deterministic command
   responses, no network. Fixture packing/worktree setup is confined to verified
   temporary paths; never modify the actual source object database or globals.
   Verify actual source/primary bytes and Git refs stay unchanged by tests.
   Demonstrate meaningful parent reds and kill a zero-reading mutant plus an
   unavailable-as-zero mutant. Preserve original red evidence and source bytes.
6. Commit additive tests first, then only the named source change. Fresh
   reviewers verify every old/new function outside the exact named scope stays
   text/AST exact. Author, independent reviewer and final integration run the
   actual complete suite with raw-byte preservation and non-Git temporary
   storage. Independent functional review and separate adversarial review pass;
   publication requires actual exact-head source/master CI and two real locked
   builds. No new snapshot, study, benchmark or production probe is dispatched.

## Evidence and threat model

Realistic linked-worktree layout, unavailable tooling and misleading unrelated
Git metadata must not keep a capacity guard green with an unmeasured zero, or
trigger an unnecessary migration. Report existing packed storage honestly;
disk allocation, all local branches and a newly packed published head are
separate measurements. Preserve the source measurement, fixed vocabulary,
threshold boundary controls and every retained failure. Old scientific and
security gates remain unchanged. No spending, removal or migration is authorized.

## Amendments

None.
