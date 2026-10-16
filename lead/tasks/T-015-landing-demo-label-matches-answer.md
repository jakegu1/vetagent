---
id: T-015
title: Describe the landing demo's failed trade simulation without claiming a proven inability to sell
status: done
level: 3
size: S
depends_on: [T-024]
decisions: []
backlog: none
---

## Context and scope amendment

The first landing example still reads "a token that cannot be sold". The saved
hp_align_simfail.json identifies that example address and records simulationSuccess=false
with BUY_FAILED. Existing test_simulation_failure_is_fail_closed explicitly preserves the
distinction: failed simulation is a warning and critical missing evidence, not proof of
a honeypot or of a universally impossible sell. The Owner confirmed the exact replacement
on 2026-10-15: a token whose trade simulation fails. The current optimization request
authorizes implementing that already-confirmed correction.

An unimplemented local draft proposed a live recorder and four new whole-engine recordings.
Before any acceptance commit, this ready specification narrows that footprint to the public
wording and a guard in the existing advertised-coverage runner. It adds no recording pipeline,
network traffic or new factual verdict claim. Current upstream conditions are not measured
by these offline tests; the existing fixture is dated evidence, not a fresh production probe.

Base: 7ec4530b76a65c7f62da266870f9e28b295f919e. The complete runner has the known old-date
baseline failure (33/34; the gate test reports 94/5). T-024 fixes it before integration.
Do not borrow unreviewed date changes into this branch.

## Goal, budget and files

A visitor sees the Owner-confirmed description of a failed simulation. A future edit cannot
silently restore the stronger claim or change which example that wording describes.
One small copy correction; zero spend or added network behavior; at most two review rounds.
New acceptance and mutants are offline. The unchanged configured full runner retains
test_owner_powers.py's existing Ethereum bytecode RPC check; disclose that dependency.

Only two files:
- src/landing.html: only the text of the first example button.
- tests/test_advertised_coverage.py: additive acceptance tests and their local helpers/imports.

No existing test-function AST or runner edits. No fixtures, engine, script behavior, addresses,
chain hints, default input, other public wording, figures, workflows, permissions or providers.
The lead owns task/status/review records outside the executor branch.

## Conflict search

Search the old label across src, README.md and docs; inspect all readers of landing.html.
The existing advertised-coverage test parses public capability nouns. Its original 103
assertions and automatic test discovery remain unchanged. Existing risk, HTTP telemetry,
published-number and public-claim guards remain unchanged. No older assertion needs a named
change. Report a newly discovered conflict before expanding scope.

## Acceptance criteria

1. The first example button reads exactly a token whose trade simulation fails. Against the
   base, the entire src/landing.html diff is one line and only that button's text changes.
   The old label is absent from src, README.md and docs. Default address, all three example
   addresses, chain hints, order, other labels and script behavior remain byte-identical.
2. Add offline tests to the existing runner that parse the real page and check the expected
   first example address and Ethereum hint, its exact approved label, and the input default
   matching it. Use the fixed expected values rather than deriving expectations from the page.
   Tie the wording to the existing saved honeypot fixture's matching token address, false
   simulationSuccess and nonempty simulationError. Re-run the existing fail-closed risk
   regression unchanged. Do not assert a fresh/live verdict or silently promote unknown.
3. Acceptance tests are committed first and alone. On that exact commit, only the new label
   assertion is behaviorally red; the existing 103 advertising assertions and fixture checks
   pass. The separate one-line source fix makes it green. Original test ASTs and automatic
   discovery are unchanged. A private old-label mutant and a changed-address mutant must
   each be caught; restore exact pre-mutation bytes, clearing relevant stale bytecode.
4. The final clean immutable head passes the advertising runner, unchanged risk and HTTP
   telemetry tests, and the configured full runner except only the documented old-date
   baseline. Record base/tests/fix/head SHAs, actual red/final outputs, safe mutation evidence,
   frozen older ASTs and exact two-file diff. Final integration after T-024 must be all green.

## Threat model and READY

Protect against equating a failed observation with a proven inability to trade, a misleading
example/address mismatch, and an unrelated UI change hidden in a copy correction. This is a
Level-3 public-claim repair; require fresh independent and adversarial review. Write evidence
and signed READY privately. No merge or push by the executor. Deployment remains a lead step.
