---
id: T-027
title: Separate recorded owner-power regression evidence from live RPC monitoring
status: in_progress
level: 3
size: M
depends_on: [T-015, T-024, T-025, T-031]
decisions: [E11, E30]
backlog: none
---

## Context, measured red and goal

The Owner requests RPC dependency separation after reviewed T-031, then direct technical
deployment. This replaces the Oct-17 draft; implementation waits for T-031's reviewed
merge and green integrated checks. No new provider, paid service or engine behavior.

At c49fac0 the configured runner passes 35/35 with RPC available. With a private inherited
Python/subprocess network guard it passes 34/35 in 195.6 seconds; only owner powers fails
(51 passed, four failed: missing three bytecodes and the WETH control). All 238 Python
processes load the guard. Parent, child and curl controls deliberately fail before the
run. Keep deterministic regression and current observation separately, with all controls.

## Scope and conflict search

Implementation files in scope:

- tests/test_owner_powers.py: named acquisition-only change (a), additive strict fixture
  loader/imports if needed; freeze all other original functions/assertions/inputs.
- tests/fixtures/owner_powers_eth_26216600.json: exact verified historical recording.
- tests/test_upstream_contract.py: named additive live implementation (b) only.
- tests/test_owner_power_evidence_split.py: new acceptance tests.
- .github/workflows/test.yml: exactly one offline step registering the new acceptance.

The lead alone may regenerate docs/SCORECARD.md separately if needed. Existing runners,
deploy/production workflows, baseline, monitor rules, every src function, benchmark and
cache remain frozen. No implicit fixture refresh. Acquisition has already finished.

Searched CASES, real-contract test, rpc_batch/eth_getCode, fixture loading, power/proxy
controls, discovered live functions, status/unobserved sources, workflow registration and
runner inventory across tests/workflows. The recall guard scans owner-test prose: retain
recall claims. The existing observed-monitor harness stubs added live tests dynamically;
keep that entire file and its twelve-test contract unchanged. Existing enforcement and
deploy guards derive registration. Do not add RPC to JSON-field PROBED_TEMPLATES or
re-freeze upstream_baseline.json.

Named change (a): test_a_real_contract_reads_correctly in test_owner_powers.py. Replace
only sys.path/backfill import, live acquisition and transport exception handling with
strict fixture loading; update its docstring and printed live label to historical.
Keep its name, all three CASES literally, and its complete original control tail from
the first for-loop through final WETH assertion. Fixture failure must fail, never skip
or fetch. Every other original owner test stays unchanged.

Named implementation (b): test_upstream_contract.py may add test_owner_power_rpc_contract,
narrow _owner_rpc_* helpers/constants and necessary imports. This live test is operational
monitor implementation, not late acceptance. Keep every old function/constant, including
T-031's template reconciliation. Main already discovers it; no main edit.

## Verified provenance

Four read-only HTTP requests, each bounded at twenty seconds, use the existing
https://rpc.mevblocker.io; no fallback/new provider. Chain ID 1; finalized block
26216600 (0x1900898), hash
0xb917f8fa494a872068e4db321a5e05ef7b1a80125914b0eea3cd69379ac1bfda,
timestamp 2026-10-18T02:56:23Z. Capture: 2026-10-18T03:10:06.348713Z through
03:10:08.826104Z. A fourth request rechecks the same block hash/timestamp. All three
eth_getCode requests use that numeric block. The unchanged original control function
supplied recorded codes yields six passes and no failures with network denied.

The independently audited fixture candidate SHA-256 is
4f466743974be548c6ead1c4b75ec2fecb7a9a9f0bef30aa664bd1c1db251912.
The lead supplies its private location. Copy exact bytes into the fixture in the first
test commit. Relative raw-receipt references are audit references, not bundled responses
or proof of current availability. Do not add raw headers, machine paths/account details.

## Acceptance criteria

1. Strict fixture loading verifies the LF-canonical whole-file hash pinned outside the fixture,
   canonical identities/order, chain/source/capture/finalized-block provenance and recheck,
   complete nonempty hex bytecodes and decoded-byte SHA-256 hashes. Missing, malformed,
   damaged, duplicate, mismatched or incomplete records fail deterministically, without
   network fallback. All six original contract controls and all other owner assertions
   still execute: USDT blacklist/pause and nonproxy; USDC proxy; WETH nonproxy/no powers.
2. The discovered live monitor reads those three canonical contracts at latest from only
   the two existing backfill Ethereum providers, validates chain ID 1 and keeps original
   power/proxy controls on observed current code. Bound it to two providers, at most two
   HTTP requests each, explicit timeouts at most twenty seconds, no full backfill retries.
   Preserve JSON-RPC envelopes through strict ID validation. Identify the supplying
   existing provider; fallback coverage is not proof of production-primary availability.
3. Missing transport, non-200, malformed/empty JSON or envelopes, unmatched/duplicate/
   missing IDs and matched RPC errors cannot testify about contract powers: record safe
   unobserved reasons. Map reordered IDs; reject bool IDs impersonating integers. Valid
   matched results with empty code, wrong type or invalid hex are observed bad data and
   fail. Wrong chain, powers or proxy fails. Partial blindness and observed failures can
   coexist; fallback must not erase a failure already observed. Status diagnostics never
   contain addresses, bytecode, raw bodies or arbitrary upstream messages.
4. Existing normal main discovery and daily status writing include the live function.
   Use stable source label ethereum-rpc for the existing public test-provider coverage,
   not production usage. If no provider observes every required contract, mark it blind
   even with partial results. Acceptance covers main discovery, combined red/blind status
   and the existing durable observer using this source. No threshold/history/rule edits,
   quiet skips, or successful live observations supplied from the historical fixture.
5. First commit adds only the new acceptance and exact fixture, matching the configured
   acceptance-test globs. Add its single workflow registration with the later separation
   implementation; no non-test file belongs in the first commit. Reproduce meaningful
   red for old acquisition under denied transport and
   missing separate monitoring. Freeze new acceptance/inputs thereafter. Commit named
   acquisition/live separation as one finding, describing the red. Original control tail
   and unrelated tests remain frozen. Acceptance never recursively runs the full suite
   or calls external network. Live implementation (b) is explicitly permitted afterwards.
6. Controlled mutants removing a required power, changing proxy detection, giving WETH
   powers, omitting a live assertion/probe, accepting corrupt fixture or recording refused
   RPC as observed must fail meaningfully. Use exact backups or isolated/in-memory mutants,
   unique replacements and fresh bytecode. Verify all unrelated src/test/benchmark bytes.
7. Run the complete configured inventory with the inherited tested network guard: every
   step including new acceptance passes with external networking denied in parent/child
   Python and network subprocesses. Prove parent/child/curl controls fail, protect tracked
   bytes, and pass ordinary python lead/checks.py and contract checks at a clean frozen
   head. Separately run a bounded fresh live RPC observation and report observed/unobserved
   honestly. Existing CI and daily recorder retain full API monitoring; a live outage
   cannot justify weakening deterministic regression.

## Threat model and delivery

Corrupt/mislabeled fixture, response IDs from another request/chain and transport outage
hidden by a green deterministic test must not become reassurance. Preserve source/block
provenance, exact original controls, explicit blindness and durable monitoring. No invented
bytecode or unprovenanced cache. No production VetAgent calls by the executor.

Start only after reviewed/green T-031 integration. Require fresh independent/adversarial
review, maximum two rounds. Private signed READY includes commits, provenance audit,
red/green logs, named AST diffs, response classification grid, mutants, inherited offline
proof, fresh live receipt and artifact hashes. The lead merges and deploys under the
Owner's scoped technical authorization; all other sign-off categories remain unchanged.

## Amendments

### 2026-10-18: measured Windows/Linux serialization equivalence, before acceptance

The genuine candidate has 38,266 bytes and 137 CRLF line endings. Its raw capture hash
above remains unchanged. Git normalizes the tracked text to LF; that representation's
SHA-256 is f7d3e06858bc7b9dafd9d2967e903ec8fde2907d4a0e5d1887391adcabe2d62c.
Define whole-file integrity as SHA-256 after replacing CRLF with LF only. No other
normalization, whitespace, JSON reserialization, field, bytecode or metadata change.
Copy the original candidate bytes, retain the original acquisition hash, and pin the
LF-canonical hash outside the fixture. Do not alter .gitattributes or Git configuration.
The first acceptance contract covers exact CRLF and exact LF forms, rejecting bare CR
and every other corruption. The executor confirmed no acceptance was yet written or
committed, so this clarification precedes and becomes part of the first frozen contract.
