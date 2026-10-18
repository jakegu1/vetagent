---
id: T-038
title: Separate live backfill observation gaps from genuine decoder failures
status: ready
level: 3
size: M
depends_on: [T-032, T-036]
decisions: [E11, E30]
backlog: W51
preparation_source: 457dffaac78c3ddb3be559720cd573004f93a9b4
---

The lead refreshes the actual dispatch base after the prerequisite source freezes.
Existing scope and fresh-review requirements remain. Preparation is feasibility evidence,
not approval of an implementation.

## Context and goal

At the preparation source, tests/test_backfill.py contains three deterministic functions
and two live functions. All five are dynamically discovered, but the whole file runs
only in the soft-failed backfill-roundtrip job. A served head followed by HTTP 400 from
log acquisition produces a decoder-test failure although no log was observed. The
saved bounded diagnostic contains two served heads and two refused log queries; it
contains no successful log array. Code 35 alone does not establish service policy,
malformed filters or a range that would work if narrowed. Saved message semantics are
historical observations, not new provider, terms or availability verification.

Make deterministic decoder/range controls required offline checks. Make the live job
fail for observed wrong pools/tokens, wrong boundaries, or local harness/engine faults,
while explicitly counting unavailable observations without counting them as passes.
This protects the existing decoder assertions; it does not repair RPC access.

This is one bounded test/CI finding. Stop at honest classification plus required
deterministic coverage. No new workstream, provider, benchmark or recurring service.

## Scope: exactly three implementation files

1. tests/test_backfill.py: additive narrow observation helpers, explicitly named live
   adaptations and a dynamically discovered offline CLI mode.
2. tests/test_backfill_observation_contract.py: new required offline acceptance and
   characterization; first commit alone.
3. .github/workflows/test.yml: exactly two required test-job registrations listed below,
   and remove the backfill-roundtrip job's continue-on-error only after the simulated
   classification/exit proof passes. Set its outer job timeout to three minutes.
   Keep its existing default live command.

Freeze every bench/backfill.py definition, including T-032's logs_in_range changes and
request/range semantics; tests/test_backfill_range_contract.py; all src, benchmark,
cache, fixture, dataset, archive, provider/configuration, baseline, other workflow,
monitor/history/rule and permission bytes. No CI Python/action/runner migration here.
No change to the nineteen original upstream-monitor functions. No new external request
is needed for acceptance or READY; do not infer primary availability from a fallback.

## Conflict search and exact named changes

Searched test_backfill, logs_in_range, decoder, backfill-roundtrip, fromBlock/toBlock,
continue-on-error, offline registration and runner discovery in tests, workflow and
backfill sources. The search and source hashes are in preparation-evidence.json.

Byte-freeze these existing functions, their helpers _word/_topic, and all their inputs,
assertions and messages: test_decode_offsets_offline;
test_pairs_of_quote_assets_are_not_launches;
test_a_refused_range_narrows_the_window_and_skips_no_blocks. They currently perform
eighteen checks, including HTTP 413/429 and JSON narrowing, HTTP 500 propagation and
floor refusal. Do not rewrite them to fit a new classification or T-032.

Named (a), test_decoded_pools_are_real_pools: only acquisition/observation handling,
coverage guards/counters and privacy-safe live diagnostics may change. Continue to use
the actual _decode and logs_in_range. Preserve its Base/quote/factory/topic inputs,
head offsets 25000/20000, step 5000/floor 200, six-candidate cap, token0/token1 selectors,
named sample threshold/predicate len(decoded) >= 3, served-empty/short-answer failure
path, expected log-side set, and genuine final predicate checked > 0 and verified ==
checked. A precondition guard may record insufficient candidates as unobserved before
the old sample assertion; it must not reduce the threshold. Fewer than three complete
observed round trips cannot earn aggregate success. An observed mismatch still executes
the original failing predicate even when coverage is insufficient or other probes fail.

Named (b), test_a_day_is_bracketed_by_its_own_boundaries: only acquisition/observation
handling and sanitized diagnostics may change. Preserve the UTC date-minus-45-days
input, actual block_at/_timestamp_of path, and all three check names/predicates:
t0 <= start; t_next > start; start - t0 < 60. Valid contradictory timestamps fail;
missing/unusable timestamp observations are named unobserved checks. Do not catch
arbitrary engine RuntimeError/ValueError/AssertionError as an outage.

Named (c), main: add --offline and explicit observation counters/summary/exit behavior.
Retain dynamic discovery over every test_ function. --offline excludes only the two
named live functions; an injected future offline canary must run automatically. Default
invocation still reaches every test function. Unknown CLI configuration fails. Existing
check semantics remain; no offline assertion is weakened. Unexpected per-test exceptions
may be caught only to produce sanitized hard failures and a nonzero result, never an
unobserved result. Standard-library imports and narrow additive helpers are allowed.

No changes to tests/test_decisions_enforcement.py, tests/test_deploy_gate.py or existing
monitor tests are expected. Their generic registration/discovery rules must still pass.
Any older test requiring an additional edit means BLOCKED, not implied permission.

## Acceptance criteria (eight)

1. **Required offline coverage and discovery.** Add required test-job commands
   `python tests/test_backfill.py --offline` and
   `python tests/test_backfill_observation_contract.py`, once each. The offline command
   invokes all three frozen functions with network denied and no live acquisition;
   their original eighteen checks execute. The new acceptance drives the actual changed
   main/CLI: existing offline functions plus an injected offline canary run, the two live
   canaries cannot run in offline mode, and default discovery reaches all functions.
   Do not substitute a hand-maintained tuple or let the optional job be their only run.
2. **Typed observation seam.** Only unavailable transport/HTTP, refused JSON-RPC or
   malformed/unusable envelopes/results become explicitly unobserved. Validate the
   envelope, strict integer matching ID (reject bool), exactly result or error, and
   method-relevant usable structure before feeding engine code. HTTP 400/429/5xx,
   JSON-RPC refusal (including opaque code 35), malformed JSON/envelopes/logs/timestamps
   are covered. Valid hex empty/short token-call answers are observed bad contract
   evidence. No request error becomes an empty success or a fact about the decoder.
3. **Round-trip facts and floor.** Three usable launch candidates and three complete
   observed token0/token1 pairs are required for an aggregate successful round trip.
   Empty/one/two candidate samples and fewer than three observed pairs report coverage
   unobserved; they are neither decoded success nor decoder defect. Preserve the named
   genuine predicate and all original controls. Served empty/wrong contract/token sides
   and a V3-offset mutant fail. An observed bad pair plus another unavailable pair
   produces both failure and unobserved evidence, with exit 1; fallback cannot erase it.
   Even an undersized nonempty candidate sample must still expose any observed bad
   pair; a coverage-floor guard must not return early and hide that contradiction.
4. **Boundary and local failures.** Healthy actual block_at controls pass all three
   original boundary predicates; valid wrong before/next/midnight answers fail. Missing
   or malformed observations cannot testify about a boundary. Injected decoder and
   boundary RuntimeError/ValueError/AssertionError and harness failures hard-fail the
   live job with sanitized diagnostics, even alongside upstream blindness. Catch typed
   observation errors at acquisition boundaries; never catch every Exception as outage.
5. **Honest outcomes and enforcement.** Report observed-check, failed-check and
   unobserved-check counts, with per-check safe reasons and a separate live
   observed/partial/blind/red state. Offline passes must not turn wholly blind live
   acquisition into observed or partial live success. Unobserved checks never increment passed checks. Any genuine or
   local failure gives nonzero; a wholly unavailable observation gives zero plus
   explicit blind/unobserved output, not "all passed". Only after the required fake-node
   grid proves these directions may the implementation remove continue-on-error from
   backfill-roundtrip. A return-zero-always or reintroduced soft-fail mutant must fail
   required offline acceptance. Required deterministic failures remain ordinary CI red.
6. **Finite acquisition and privacy.** A test-owned strict adapter may be scoped over
   the existing backfill RPC seam and must restore it on success and exceptions. Use
   only the two existing providers, one attempt each per logical call, at most 64 total
   HTTP attempts across both live functions, a shared 60-second acquisition deadline,
   per-attempt timeout at most 15 seconds and a 2 MiB response cap. Refuse redirects;
   check remaining time during bounded reads. The monotonic acquisition budget limits
   launched attempts and read timeouts; it does not claim to interrupt platform DNS
   blocking. The three-minute job timeout supplies the outer workflow bound.
   Exhausted budget/oversize/unavailable
   observations are explicit gaps. Preserve actual logs_in_range and its HTTP 413/429
   narrowing, with typed origin errors at the floor; JSON-RPC refusals may terminate as
   unobserved at the adapter, avoiding a generic RuntimeError catch. Do not add blanket
   HTTP-400 shrinking/retry or infer policy from error code alone. Emit only fixed class,
   method, coarse provider and status labels plus counts; no raw URL, params, pool/token,
   body, upstream message or arbitrary exception text. Inject private sentinels to prove
   redaction. Frozen offline synthetic assertion messages remain unchanged.
7. **Tests first and meaningful mutants.** First commit is only the new acceptance;
   characterize the frozen old controls before changing existing code. Record meaningful
   red against the parent for unavailable-as-defect, missing required offline routing
   and soft-failed genuine failures. Freeze every new acceptance input/assertion after
   that commit. Named (a)-(c) form one observation-classification finding. Required
   mutants include wrong V3 offset, omitted genuine predicate, floor three weakened to
   one, engine exception converted to unobserved, lost failure beside blindness,
   forced-zero exit, restored continue-on-error and dropped offline discovery. Use
   isolated/in-memory mutants with exact match counts and fresh bytecode.
8. **Contract and checks.** At a clean frozen head run the complete configured ordinary
   and inherited-network-denied inventories, preserving all parent steps plus the two
   exact registrations; test parent/child Python and network-subprocess denial controls.
   Verify real Python 3.12 and 3.13 acceptance/owner compatibility, compileall, contract
   and all frozen byte hashes. Obtain fresh independent/adversarial review, then an
   exact-head Linux preflight before release. No real RPC/benchmark is required for this
   classification repair. Existing unavailable live evidence stays unavailable; no
   measured decoder/primary-availability success is invented.

## Threat model and evidence required

Transport refusal, malformed observations or a thin sample must not become bad-decoder
claims, passes or chain facts. A wrong decoder, wrong observed boundary, source bug or
broken local harness must not become a benign outage. CI softness must not hide these
failures; filtering must not strand deterministic tests; retry/deadline/parser behavior
must remain bounded and diagnostics must not expose queried pools/tokens.

READY needs exact first-test/fix commits, red/green logs, per-check classification grid,
unchanged three-function source spans and predicate/input proofs, actual-main discovery
and workflow negative controls, bounded mutant results on both runtimes, complete
ordinary/denied inventories, privacy/budget evidence and source fingerprints. Preserve
T-032 logs_in_range/tests unchanged. Report dropped/unverified cases explicitly.

## Durable observer decision and preparation limits

Do not integrate the existing upstream durable observer in W51. That would expand the
nineteen-function freeze, source/history schema and monitoring rules. W51 therefore
does not provide consecutive-outage history or alerting: a permanently blind live job
can remain exit-zero while printing blind counts. State that residual explicitly in
READY; any durable consumer is a separate, named follow-up. No availability repair or
production-primary uptime claim follows from this classification task.

Private preparation ran the same 29 bounded fake-node cases on actual CPython 3.12.14
and 3.13.4 against immutable source at the preparation ref. The three original offline
functions pass eighteen checks; an actual in-memory V3-offset mutant produces two old
offline failures and a failed round trip. No network operation or repository write.
This is a feasibility model, not the future implementation. Its discovery proof is a
model; actual main/CLI/workflow, real redirect handler/read deadline/response cap and
future post-T-032 integration remain unverified and must be covered by the first frozen
acceptance. The model uses pre-T-032 source and is not proof of T-032's range repair.
No additional live access, terms/documentation refresh or benchmark was performed.


## Amendments

None. Counts and workflow registration are reconciled against the actual dispatch base.

