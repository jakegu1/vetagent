---
id: T-032
title: Preserve complete and terminating inclusive backfill log ranges
status: ready
level: 3
size: S
depends_on: [T-027]
decisions: [E11]
backlog: W51
---

## Context and goal

Read-only, network-denied probes at 72bf264 reproduce two related range-iteration
findings in logs_in_range. Its docstring promises every log in [lo, hi], but [10, 12]
with step one omits block twelve, and [10, 10] makes no request. Separately, an explicit
negative step repeats invalid ranges; a negative floor lets a refused range shrink to
zero and repeat. Bounded fake-node canaries stop these loops; no live request or archive
change is needed to reproduce them. Existing offline backfill assertions miss the edges.

Protect collected history by making valid inclusive ranges complete and invalid
negative/noninteger window configuration fail before RPC. Preserve existing nonnegative
integer delta semantics: explicit step zero progresses one block, floor zero terminates
on a refused zero-width window, and default singleton acquisition remains valid.

## Scope and conflict search

- bench/backfill.py: logs_in_range only. All other definitions and constants frozen.
- tests/test_backfill_range_contract.py: new offline acceptance and characterization.
- .github/workflows/test.yml: exactly one offline registration for the new file.

Existing tests/test_backfill.py is byte-frozen. Its live decoder/day-boundary tests stay
live. Its three offline narrowing/error functions, original inputs and assertions are
also frozen and must still run in controlled verification. Searched every logs_in_range,
step/floor and refusal use. Production callers are harvest (step 5000, floor 200) and
harvest_traded (default delta, floor 20); no caller depends on negative/noninteger values.
The live roundtrip uses step 5000 and floor 200. No named existing test change is needed.

No HTTP-400 retry policy, provider, decoder, outer UTC-day boundary, source engine,
benchmark, cache, fixture or raw observation change. W51 outage/defect classification is
a separate task. This does not claim to recover historically omitted blocks.

## Acceptance criteria

1. A fake node returning one uniquely identified log per block proves exact ordered,
   duplicate-free [lo, hi] coverage for default and explicit singleton, terminal
   singleton, exact and uneven windows, zero delta and shifted large block numbers.
   Inverted ranges retain empty/no-RPC behavior. Assert requests never exceed bounds
   and impose a small canary budget so a broken test cannot hang.
2. HTTP 413, HTTP 429 and existing JSON refusals narrow windows without losing any
   requested block, including a terminal singleton. Preserve address/topics/request
   shape, existing delta semantics, floor refusal, HTTP-500 propagation and successful
   empty observed ranges. Do not turn errors into empty success or add blanket retries.
3. Negative or noninteger effective step/floor is rejected deterministically before
   any RPC on a nonempty range. Reject booleans as integer configuration. Default None
   step and nonnegative integer zero remain as characterized above. Prove the original
   negative loops with bounded canaries; do not falsely describe zero as a proven hang.
4. First commit adds only the new acceptance file. Keep all acceptance inputs/assertions
   frozen thereafter. Record meaningful red for missing terminal/default singleton and
   negative iteration. Characterize unaffected request/error behavior before the fixes.
   Commit one source finding per commit: inclusive termination, then invalid negative/
   noninteger window configuration. Add workflow registration with the first source
   commit, never to the tests-only commit. No other source or old test edits.
5. Demonstrate an exclusive-end mutant, a skipped/repeated-block mutant and removal of
   negative-configuration rejection fail assertions. Protect tracked bytes with exact
   external backups or in-memory compilation; no stale bytecode or shared benchmark.
6. Run fresh independent and adversarial reviews, capped at two rounds, comparing the
   full ordinary and inherited-network-denied configured inventories. The new single
   registration makes thirty-seven steps. Compileall and the tests-first contract pass
   at a clean frozen head; unrelated engine/data/test bytes are unchanged. No external
   RPC is necessary for this deterministic iteration repair.

## Threat model and evidence

A terminal event must not disappear because of partition arithmetic, and an invalid
internal window must not run forever. Refusal must preserve unread blocks or fail, never
testify that no events existed. Keep red logs, complete request-range receipts, original
offline-test results, bounded mutants, byte/AST manifests and a signed READY outside the
repository. The lead integrates only after reviewed green T-027; technical deployment is
authorized, while provider, paid, legal and product-gate decisions remain unchanged.
