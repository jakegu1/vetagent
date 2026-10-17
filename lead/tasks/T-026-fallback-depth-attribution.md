---
id: T-026
title: Attribute selected fallback-pool depth before proposing reserve verification
status: draft
level: 3
size: S
depends_on: [T-015, T-024, T-025]
decisions: []
backlog: none
---

## Hypothesis and boundary

An upstream-declared USD reserve can influence best-pool selection when the fallback shim
cannot independently check raw reserve amounts. A saved forensic case motivates investigation;
it is not proof that every eligible fallback pool is inaccurate, that a benchmark row actually
used that fallback, or that an ERC-20 balance proves executable sell depth.

Review this parked line on 2026-10-17 after the current three repairs close. Before marking
ready, inspect the current shim, selection path, benchmark replay hooks and current evidence.

## Cheapest decisive experiment

Zero additional spend and at most one workday. Use an isolated immutable source copy, an
independently copied cache and the benchmark's effective clock. Block external network and
all fills. Trace actual shim and final selection attribution without changing the engine's
returned values, then compare all result rows and input hashes with an uninstrumented parent
run. An ID join alone is insufficient attribution.

Record observed selected fallback uses, unresolved provenance, supported normal pool
addresses versus shared managers, possible existing-RPC request budgets and cache needs.
Test the saved suspicious case alongside an honest deep control and both candidate orders.
Keep upstream declaration, independent balance observation and executable liquidity separate.

## Stop rule and subsequent decision

If attribution is not reliable or immutable replay differs, stop the runtime proposal and
report the missing evidence. Do not add providers, RPC traffic, production source changes,
reserve caps, risk bands, threshold changes, benchmark fills or a rebaseline in this study.

A later runtime spec needs a threat model for shared managers, unknown decimals, missing
balances, stale observations, RPC failures and extra latency. It must preregister a same-cache
and same-clock comparison in both directions: new false blocks and missed danger as well
as removed mistakes and unknown changes. Source rights and any cost remain Owner decisions.

## Readiness gaps

### 2026-10-18 check-in

The lead starts the bounded private evidence study from the current frozen source and
independent cache copies. Its parent replay must reproduce every committed output before
instrumentation. This is an investigation before a runtime task, not implementation
authorization or an exception to the tests-first contract. The runtime specification
remains draft until actual selection attribution and missing-evidence behavior are known.

The executor's exact source/copy locations, scope, safe instrumentation, expected output
contract, immutable control and acceptance tests remain to be specified. This draft is
not authorization to implement a production cap or a claim that the experiment has run.
