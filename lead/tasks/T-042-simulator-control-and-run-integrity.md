---
id: T-042
title: Make the independent simulator prototype honor its adopted controls and preserve runs
status: in_progress
level: 3
size: M
depends_on: [T-039]
decisions: [E11, E14]
backlog: W41 measurement prerequisites and W47 evidence boundary
---

## Context, bounded benefit and stop rule

W41's prototype exists outside the engine. Its adopted design amendment requires a
positive control's same-day Honeypot answer to state at least USD 1,000 of pool liquidity.
The current countable predicate checks only the Honeypot shape. It can also classify a
failed approval as a sell revert, and main overwrites the same dated output after live
calls while printing token addresses. These are measurement/lifecycle defects, not
permission to adopt a simulator or alter a product verdict.

Protect one repeatable, independent experiment. Cost: one implementation and at most
two review rounds, followed by at most six eligibility refresh requests. Stop if fewer
than five refreshed positives satisfy the already-adopted requirements. A bounded
screen does not prove that all other candidates are ineligible. No V3 implementation
or engine integration follows automatically from this task.

## Scope and conflict search

Exactly two implementation files, disjoint from T-040 and T-041:

- bench/sim_probe.py: same-day control eligibility, simulation-stage evidence, explicit
  planning/refresh/run CLI, bounded acquisition and safe isolated output/cache lifecycle.
- tests/test_sellability_archive.py: append exactly three named test functions before
  main; all local helpers/imports belong inside them. Preserve every old statement,
  function, assertion and the dynamic test runner. No new test.yml step is needed.

Searched sim_probe, hp_shape, countable, cache_sim, output filename, reference run and
SELL_SIMULATION across tests/bench/docs. No existing dedicated prototype test covers
these defects. The archive test runner discovers all test_ functions. No existing test
change is authorized. Preserve raw targets, historical reference JSON, archive, shared
cache/access log, all src files, providers, packages, permissions and every decision bar.

## Acceptance criteria

1. **Adopted positive control.** A positive counts only when the current run's own
   same-day control response has the existing proven-honeypot shape and finite numeric
   Honeypot pair liquidity of at least USD 1,000. Below-floor, missing, Boolean,
   nonfinite, malformed or unavailable amounts cannot count. Clean controls keep their
   original shape/tax rule. Record eligibility and unobserved reasons separately; an
   excluded control is not a simulator disagreement. Do not retroactively re-score run 1.
2. **Executed sell versus failed setup.** A failed/unobserved buy, balance read,
   approval or second-request setup cannot count as a definite executed sell. A true
   executed sell revert and a successful sold/tax result still count exactly as the
   existing design says. Validate stages used to support a conclusion; return a bounded
   no-answer class rather than crash or expose arbitrary RPC exception text. Keep the
   router ABI, source hosts, block pinning and tax tolerance unchanged.
3. **Plan and bounded refresh.** Default/--plan is offline and performs no fetch/cache
   write. Explicit --refresh-controls only refreshes current positive-control eligibility,
   never claims simulation agreement or BUILD. It has a hard maximum of six requests
   over a deterministic predeclared candidate slice, reports eligible/excluded/unobserved
   and not-asked counts, and stops when the screen cannot meet five countable controls.
   Preserve exact selection provenance, rather than selecting after seeing answers.
   Full --run remains explicitly separate, preserves original U13 and clean sets and all
   active design bars, and cannot silently truncate a control population into a pass.
4. **No overwrite or shared state.** Live modes require explicit new isolated output
   and cache paths; reject existing output/cache and protected source/shared-cache paths
   before any network call. Reserve output exclusively, preserve partial observations
   incrementally, and never overwrite a prior run or the frozen reference. A failed
   request remains a failed observation, not a cache hit or no-token evidence. No raw
   token addresses, arbitrary symbols/revert strings, secrets or private paths in console
   diagnostics; detailed public-source inputs may stay in the explicit private artifact.
5. **Decision/source preservation.** Keep the active SELL_SIMULATION design:
   U_DEFINITE_BUILD=10, U_DEFINITE_STOP=7, U_N=13; clean agreement >=90%; positive
   agreement >=80%, with at least five countable; tax tolerance five percentage points;
   same-day positive floor USD 1,000. The older backlog Aerodrome/18-of-20 description
   does not replace the adopted design. No rule, benchmark, engine output or public
   accuracy figure changes. Source-only eligibility screens do not close W41 or W47.
6. **Frozen tests and quality.** First commit adds only these tests, visibly red on the
   parent: test_sim_probe_requires_same_day_qualified_positive_controls,
   test_sim_probe_distinguishes_failed_setup_from_executed_sell,
   test_sim_probe_plan_refresh_and_outputs_are_bounded_and_non_destructive. Include
   existing valid characterization, explicit floor boundaries, unavailable/malformed
   source replies, approval failure, actual sell failure, plain plan/CLI behavior,
   preexisting output/cache, partial preservation and truncation disclosure. No network
   in tests. Keep each finding in its own fix commit, with red described. Kill at most
   four meaningful mutants with byte-exact restoration and fresh bytecode. Preserve all
   old archive tests and reference bytes. Run the final full configured checks in root's
   exclusive slot and bind READY to exact source/commands/log hashes.

## Threat model and runtime handoff

Realistic failures are a drained former positive retained as a current positive,
approval failure mistaken for an independently verified sell rejection, a second run
destroying first-run evidence, and an interrupted request sequence recording no useful
measurement. Use only already-approved sources and read-only eth_simulateV1, never
sign/broadcast a transaction or use GoPlus inside the engine. Root may perform the
bounded six-control refresh only after fresh source reviews and actual Linux checks;
fewer than five means current positive eligibility remains unmeasurable on this screen.

## Amendments

None.
