---
id: T-061
title: Inventory point-in-time snapshot input availability without replay claims
status: in_progress
level: 3
size: M
depends_on: [T-053]
backlog: W7 preparation
---

## Goal, benefit, cost and stop rule

W7 needs contemporaneous engine inputs and independent outcomes, not merely
date-named pool files. Current archives preserve market observations and partial
sellability responses. Pool fetched_at is a response observation clock, whereas
the sellability seen_at is copied from the earlier collection batch and cannot
prove when the later response became available. An offline as-of inventory must
make that difference observable without calling an engine or upstream.

Benefit: prevent future-data leakage and false replay readiness before any
historical evaluation. Cost: one bounded read-only module, additive acceptance
and source-bound review/publication gates. Stop after those gates and one bounded
local inventory. Do not expand into collection, new labels, a replay engine,
new scientific rules or a new monitoring service. W7 is not closed by this task.

## Scope and conflict search

Implementation: new `bench/snapshot_readiness.py`. Acceptance: additive
`test_snapshot_readiness_*` functions before the unchanged main in already
registered `tests/test_sellability_archive.py`. Preserve every old test function,
helper, assertion, fixture and runner byte/AST except additive imports if needed.
No new workflow step is needed. Lead spec/index/state/Owner/review metadata is
separate. Search covered fetched_at, seen_at, _check_coverage, replay, readiness
and existing snapshot/archive tests. No existing expectation changes are allowed.

Use the clean published scientific source and normally retained bot data as the
base. All five active W57 controls, their imports, snapshot collection/writers,
raw archive bytes, engine/verdicts, old studies, source rights, weights, labels,
permissions and T047/49/50 remain out of scope. Never import this new module into
the live study or alter its private operation wrappers/budgets.

## Acceptance criteria

1. A real `python bench/snapshot_readiness.py --archive DIR --as-of AWARE_ISO`
   CLI produces a versioned aggregate JSON inventory from existing pools,
   sellability and run NDJSON files only. It includes per-kind/per-file counts,
   exact source-byte SHA256, aware UTC observation bounds and explicit limits.
   It performs no network, engine assessment, label lookup, collection or write
   to the archive. Input bytes remain exact. Exit0 means inventory completed,
   never that replay is ready; a distinct explicit replay_ready=false and
   independent_outcomes_established=false remain in output with reasons.
2. Eligibility uses pool fetched_at, not earlier seen_at or filename date. A
   future fetched_at is future data even when seen_at and the filename are old.
   Offset-equivalent aware instants compare equally. Missing/naive/invalid
   observation times remain unknown; do not repair them using the filename.
   Sellability seen_at alone is a batch timestamp and never certifies response
   availability as of the cutoff. Do not backfill an actual response timestamp.
   Other field-presence counts must not impersonate valid full engine inputs.
3. Report absence, valid empty files, unasked/unknown times, malformed input,
   unreadable input and cap exhaustion distinctly. Corrupt/unknown/truncated
   inventory cannot report complete. Bounds are enforced before allocation/read:
   at most256 directory entries,64MiB/file,512MiB total,256KiB/line and1000000
   rows. Files are streamed and never extracted. Any skipped coverage is explicit;
   no silent cap, fallback to older success or complete-market/continuous-day claim.
4. Refuse symlink inputs and detect source mutation while reading using bounded
   before/after identity/stat and byte-count consistency. Only fixed known
   source-kind/date metadata, hashes, numbers, booleans, UTC dates and fixed
   diagnostic enums enter output. Never echo raw rows, token/name/query values,
   arbitrary keys, input paths, exception text or caller strings in diagnostics.
   Reject invalid CLI arguments with fixed safe diagnostics, including hostile
   values. This is a local inventory, not a security review of T047.
5. Tests first in an isolated task worktree, committed alone. Demonstrate a
   meaningful missing-feature/CLI red before implementation. Test the real CLI,
   future-leak seam, offset/unknown times, empty/corrupt inputs, every cap through
   controlled local small limits, mutation/refusal, byte preservation, forbidden
   network/assessment and identity-bearing inputs/diagnostics. At least one
   controlled future-clock mutant and one output-privacy mutant must fail tests.
   No repetitive stress runs or changes to old acceptance are authorized.
6. Fresh independent functional review and separate focused adversarial review
   verify final source, with no outstanding material findings. Contract, syntax,
   existing actual complete45-command runner, exact tracked-byte preservation,
   actual same-head Linux and both locked builds gate publication. Serialize
   heavy Windows runs on this host. After normal integration regenerate with
   explicit regenerate mode, verify all five science controls and all retained
   raw archive blobs/prefixes, and run complete checks and actual master CI.

## Threat model and READY evidence

Realistic failures: an early batch clock admits later observations; absent
response clocks become invented timestamps; a directory/line/byte cap silently
reads as a complete inventory; mutable source bytes produce a dishonest digest;
untrusted row keys/values or exceptions leak identities. Defend these ordinary
offline-input seams without creating a generic sandbox or changing evaluation.

Provide tests-only/fix SHAs, original red and final green outputs, unchanged old
acceptance proof, no-network/read-only witnesses, final source/fixture hashes,
configured command inventory, complete native/source/CI/build receipts and a
private bounded real-archive invocation. Real output stays private; no archive
counts, strategy, physical local paths or live-study results enter shared docs.
