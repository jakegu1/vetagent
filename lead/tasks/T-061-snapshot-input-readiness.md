---
id: T-061
title: Inventory point-in-time snapshot input availability without replay claims
status: done
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

## Amendments

### A1: exact line-cap fixture boundary, before source acceptance

The tests-only contract set max_line_bytes=3 for the three-byte line b'{}\n'
while requiring line_byte_cap. The registered at-most bound admits equality;
the fixture premise is incorrect, not the source's inclusive comparison.
The lead reproduced len(b'{}\n') == 3 directly. Authorize only the
max_line_bytes case value3 ->2 in
test_snapshot_readiness_every_cap_is_explicit_and_bounded, in its own test-only
commit before source acceptance. Preserve every assertion, all other cases and
all original archive tests. Keep both original and candidate red outputs. This
does not change production bounds, coverage, the scientific bar or any old test.

### A2: preserve the as-of order across timestamp precision and offsets

Before acceptance, the executor and two independent reviewers reproduce real
future data admitted by datetime.fromisoformat normalization: more than six
fraction digits truncate, and a negative subsecond zero-hour/minute/second UTC
offset can disappear even with six or fewer fractional digits. This violates
AC2. Preserve the old candidate and its gate evidence; fix the entire timestamp
normalization class prospectively in the new offline inventory only.

Authorize additive test_snapshot_readiness_lossy_timestamp_precision_is_unknown
before the unchanged archive main. Assert request-clock fractions beyond six
digits, negative fractional offsets with both short and long precision and
offset seconds cannot be normalized into an admitted response; report unknown
without echoing raw input. Apply the same acceptance policy to the CLI cutoff,
returning fixed invalid_as_of diagnostics for unsupported forms. Preserve valid
exact-cutoff, one-microsecond future, UTC Z and equivalent minute-offset clocks.
Existing naive/wholly invalid cutoff cases keep their frozen invalid_arguments
diagnostic. Only unsupported aware forms previously recognized by the old parser
use invalid_as_of; recognizing them for error classification never admits data.
Cover positive and negative fractional offsets and comma fractions as well as
excessive precision. Preserve every old diagnostic assertion.

The inventory's supported input grammar is now explicit: calendar date, T or
space separator, hour/minute/second, optional one-to-six decimal fractional
digits, and Z or a signed hour:minute offset. Unsupported precision/offset forms
remain unknown, not rewritten timestamps or missing rows. Existing original and
new acceptance functions/assertions stay exact; this is an additive tests-only
commit with a reproduced old-source red, followed by the minimal parser fix.
No active scientific source, record, window, score or decision bar changes.

### A3: clarify the existing bounded-report interface, no acceptance changes

Independent review finds the existing CLI contract deliberately returns zero
after generating a bounded diagnostic report even when its explicit completeness
or replay fields are false. Exit0 means report generation, not complete evidence
or readiness. Consumers must read inventory_complete/replay_ready and diagnostics;
do not silently change the frozen real-CLI expectations. No current replay or
assessment consumer invokes this new inventory.

The directory cap bounds retained entries and source opens to256. At most one
additional metadata-only lookahead detects overflow, refuses content reads and
reports entry_cap/incomplete explicitly. This is the same bounded sentinel
principle as reading one extra byte to detect a line overflow. No further
enumeration, allocation or content read is allowed after the refusal. Tests and
production cap values remain unchanged. The observed timestamp class in A2 is
the sole material first-round source finding; these interface clarifications
are not grounds for an unrelated implementation expansion.
