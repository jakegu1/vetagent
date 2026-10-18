---
id: T-039
title: Describe a withheld provisional score without claiming its chain is unsupported
status: in_progress
level: 3
size: S
depends_on: [T-038]
decisions: [E11, E24, E32, E33]
backlog: W55(a) only
---

## Context and measured boundary

A bounded read-only probe at 7ccccf1 on actual Python 3.12.14 and 3.13.4 runs
thirteen component/seam controls each, with sockets and fetch denied. A provisional
gap harvested from the actual RugCheck signal path, presented alone, makes
_not_covered_clause say that the token's chain is unsupported. That is false: the
score was withheld. The real unconditional E24 gap correctly selects the Solana
sell-simulator clause and masks this latent wording error in current answers.

W55(b,c) are conditional policy couplings. An actual sellability-category observation
can make the existing completeness boolean true; moving a critical gap or restoring
a rugcheck category is not a wording repair. Keep E24/E32 unchanged. This task fixes
only the reproduced sentence in W55(a), not Solana sellability or future taxonomy.

## Readiness and conflict search

Searched _not_covered_clause, _NOT_COVERED, has_sellability and the fallback sentence
in src and tests. The existing composed-gap test explicitly excludes provisional-only
W55(a); it is not permission to rewrite that old truth table. tests/test_risk.py main
dynamically discovers every test_ function, so no workflow or runner edit is needed.
Reconfirm these source spans and conflicts at the actual post-T-038 dispatch head.
Start only after T-038's source is freshly approved, integrated and passes its full
41-step gate. Final publication may batch both tasks after their separate reviews.

## Scope: exactly two implementation files

- src/risk.py: only _not_covered_clause, limited to selecting and wording the actual
  provisional-score limitation. Preserve precedence and exact current output for real
  sell-simulator coverage, including when both gaps occur in either order. Preserve
  the old fallback for unrelated non-provisional coverage reasons.
- tests/test_risk.py: add exactly the three named functions below before main, with
  any imports/fixtures local to those functions. Every original module statement,
  test, helper, input, assertion, message and the original runner remains byte/AST
  frozen. No fixture file or new test runner/registration.

Do not change _rugcheck_signals, _our_coverage_gap, _finalize, _unknown_guidance,
_expiry, the clock, thresholds, categories/weights, severities, critical dimensions,
data gaps, result schemas, next actions, retry decisions, providers, packages,
workflows, permissions, gates, datasets, caches or benchmark source/results.
There is no new simulator, source, product or fourth gap kind.

## Tests first

First commit adds only these new acceptance/characterization functions:

1. test_a_withheld_rugcheck_score_never_claims_its_chain_is_uncovered
2. test_real_simulator_coverage_survives_provisional_gap_wording
3. test_provisional_gap_wording_preserves_current_solana_contracts

Harvest gaps from the actual signal path with synthetic parsed inputs and a fixed
effective clock; do not replace the engine with a helper model. Prove the first
function red against the unchanged parent on both actual Python versions before
the source fix. Freeze all new function ASTs, inputs and assertions at that commit.
Then one finding/fix commit changes only the scoped helper and records the red.
Older test edits or a needed b/c policy change mean BLOCKED pending a named amendment.

In particular preserve these old functions and all other existing tests exactly:
test_a_provisional_rugcheck_score_is_not_a_clean_bill_of_health;
test_solana_never_claims_a_sell_was_tested;
test_our_coverage_gap_never_speaks_for_the_token;
test_a_coverage_gap_scores_nothing;
test_every_data_gap_declares_which_of_three_things_it_is.

## Acceptance criteria

1. An actual provisional-only gap produces a clause naming the provisional score as
   withheld or unavailable for safety evidence. It never calls the chain unsupported
   or implies clean/sellable evidence. Drive both the actual helper and composed
   guidance. Cover known index time and missing/unreadable time; preserve the known
   expiry, and invent no expiry for an unreadable time.
2. Real unconditional Solana simulator gaps alone and beside the provisional gap in
   both orders retain their exact original clause. A real unsupported EVM-chain
   simulator control and an unrelated non-provisional fallback retain original output.
   Mixed outage/token evidence preserves the existing E33 kind, next action, retry
   seconds and expiry. All current E24-containing complete result fields stay exact.
3. Characterize six bounded report shapes: provisional revoked authorities, retained
   mint authority, settled retained mint, warn-band twenty, high-band fifty and
   unreadable index time. Compare actual composed signal/finalizer/guidance results
   before and after at the same effective clock. Current verdict, score, confidence,
   signals, named concerns, gaps and result fields are unchanged. Preserve the
   retained/revoked completeness distinction, critical provisional dimension and
   zero-weight coverage. A synthetic real sellability-category control documents the
   conditional b mechanism without clearing a gap or changing source policy.
4. Tests-first and scope are proven by commits, meaningful two-runtime parent red,
   frozen old/new ASTs and exact source spans. At most six bounded in-memory mutants
   per reviewer: restoring the false fallback, putting the provisional clause before
   real simulator coverage, losing/wrongly naming the real simulator clause, and
   treating an unrelated coverage reason as a provisional score must be detected.
   Match counts are asserted; no disk/cache mutant or stale bytecode evidence.
5. Actual 3.12/3.13 affected regression runners and owner compatibility, compile and
   generic contract pass at the final clean head. Complete configured ordinary and
   inherited-denied inventories pass all 41 steps, including real parent/child Python
   and network-subprocess refusal controls. No workflow registration is added. Any
   generated correctness-test count changes only through the normal generator and
   actual runner output; no benchmark accuracy figure or rule changes.
6. Fresh independent and adversarial reviews approve the exact source; then exact-head
   Linux required checks and both locked builds/artifacts pass before authorized
   publication. Lead-owned final release performs actual Worker upload/smoke, tagged
   readback, observer preservation/generation/snapshot health, retains bot history and
   verifies following bot CI. No live RPC or real benchmark is needed for READY.

## Evidence and stop rule

READY binds base/test/fix heads, exact commands/runtimes, red/green and composed-control
outputs, old/new freeze proof, finite mutant results, full ordinary/denied receipts,
compile/contract outcomes and final source hashes. Follow the lead's exclusive full
suite slot; no shared-cache benchmark. The lead owns metadata, generated pages,
backlog reconciliation and publication. Preserve all failed attempts and distinguish
pure controls, Linux packaging and production results.

W55 remains open for its conditional b/c integration constraints after part (a) is
fixed. Neither this repair nor synthetic controls implement an observed Solana sale,
validate a third-party opinion, settle W54/W57, or change Experiment D's Oct-20 gate.
