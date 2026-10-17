---
id: T-030
title: Disclose selected liquidity estimates whose reserve amounts cannot be checked
status: done
level: 3
size: M
depends_on: [T-026, T-028]
decisions: []
backlog: none
---

## Context and goal

E21 deliberately retains an upstream USD estimate when _independent_depth_cap returns
_NOT_CHECKABLE. The fallback shim has no raw reserve amounts. A bounded immutable
selection study confirms this branch can supply the selected pool; it does not measure
executable liquidity or justify a numerical cap. Current "Main pair holds" wording does
not disclose that limitation. Qualify it in both assessment and liquidity tool responses.

## Scope and dependencies

No numerical depth, pool selection, scoring, confidence, verdict, data-gap, provider,
request set, cache, identifier disclosure, price, threshold, archive or benchmark change.
Preserve E21 and T-013's compact display identifiers. This is the third and last
implementation task in the linked batch, dispatched only after T-028 passes review and
is merged by the lead.
It protects evidence interpretation; stop if it needs a numerical or coverage-policy change.

Files in scope: src/risk.py (_liquidity_signals, liquidity, slim-evidence retention and
a pure local disclosure helper/constant only), src/mcp_server.py (liquidity schema and
its description only), tests/test_risk.py and tests/test_mcp.py (additive acceptance
functions/helpers/imports only). Do not change _independent_depth_cap,
_reported_liquidity, _pick_best, _gt_to_pair, _load_pairs, _finalize or fetch/cache code.
The lead may regenerate docs/SCORECARD.md in a separate derived-only commit when the
new assertion totals make its existing correctness receipt stale. Use the existing
fixed-point script in explicit regenerate mode; restore only proved calendar/recent-log
display drift from exact external backups. No manual score or benchmark edits.

## Conflict search and named changes

Searched liquidity messages, evidence keys, outputSchema, compact-output budgets,
pool identifier rendering and depth-cap cases throughout the configured tests.
No old test/helper/input/discovery AST change is allowed. In particular preserve
test_output_is_compact, test_verbose_flag_changes_payload_size,
test_pool_identifier_rendering_and_disclosure_stay_unchanged, the optional best_pair
key set in test_finite_market_measurements, existing depth rejection/zero cases and
the new T-028 contract. Add evidence beside best_pair, never inside its fixed key set.
Both existing runners automatically discover added test_ functions; no workflow edit.

Replay amendment: the existing finalizer embeds a liquidity signal message in some
unknown/liquidity-driver recommendations. Keep that same qualification on this caller
surface; do not add a post-finalization boundary or change _finalize. The initial
allowlist overlooked this existing copy operation. Before review, add only
test_unchecked_reserve_qualification_follows_liquidity_recommendation in
tests/test_risk.py, in a separate tests-only commit named
"T-030: named change (recommendation qualification)". Preserve every earlier test,
helper, input and discovery AST, including the first acceptance commit. Show this
addition failing meaningfully against the original parent, passing against the frozen
implementation, and failing against an in-memory mutant that strips the qualification
from the recommendation alone. No numerical rebaseline or implementation change.

## Acceptance criteria

1. If the selected pool has positive credited depth and its existing reserve-cap result
   is _NOT_CHECKABLE, assess (slim and verbose) exposes evidence.liquidity_reserve_check
   exactly "not_checkable". Its existing liquidity signal message states "Upstream
   estimate; reserve amounts not checked." Signal names, severities and categories stay
   unchanged. No extra signal, data gap or positive verification claim is introduced.
   When the existing finalizer copies this message into a liquidity-driver
   recommendation, retain the same exact qualification there. All other recommendation
   text, advice and next-action behavior stay unchanged; _finalize remains untouched.
2. For the same selected pool, liquidity exposes liquidity_reserve_check with the same
   value and a note with that same qualification, retaining status ok and all ordinary
   measurements. Its MCP output schema declares the optional field and enum, and its
   description explains that ok is usable upstream data, not independently verified
   reserves or executable sell depth. Missing this optional marker never asserts that
   reserves, prices or an exit trade were independently verified.
3. Derive the marker from the existing cap semantics, not the upstream brand or an ID
   join. Cover fallback with one anchor, missing reserves from another provider,
   unknown anchor-table chain, ordinary finite reserve cap, both-anchor infinite cap,
   invalid operands, unbacked pairs, zero depth and no selected pool. Only the positive
   _NOT_CHECKABLE case gets the marker/qualification; other outputs stay unchanged.
   No new request, clock dependency, cache key, address exposure or identifying log.
4. Exercise real MCP structured/text responses for both tools. Characterize before/after
   pool identity, all numerical fields, signals except the exact allowed message suffix,
   data gaps and verdict/confidence. Only the same qualification naturally copied into
   an existing liquidity-driver recommendation may also differ. Keep old compact-output
   budgets and display IDs.
   First commit adds acceptance tests alone; produce meaningful red for the missing
   disclosure, then freeze them and all earlier ASTs. In-memory mutants omitting the
   marker, labelling only by provider and marking a checked finite-cap pool must fail.
5. Independently copy source and the genuine existing benchmark cache for parent/head,
   with the same effective clock and an identical fixed response timestamp. Block fills,
   external network, cache writes and after-clock use; deliberately watch guards fail.
   Parent reproduces committed JSON and markdown exactly. All 576 benchmark row fields
   and published summaries remain byte-identical after the fix. Whole verbose answers
   are identical after removing only the conditional marker, exact signal-message suffix,
   and that same qualification at the existing liquidity-message location in an eligible
   recommendation. Eligibility requires the positive _NOT_CHECKABLE marker and an
   existing liquidity-driver recommendation. Do not strip arbitrary recommendation
   changes or alter an unqualified answer. Report the number of each allowed difference.
   Report gains and regressions as measured zero for the unchanged numeric logic, not
   as an accuracy improvement or a fresh market observation. Preserve source/cache hashes.
6. Freeze source/tests, complete any lead-owned derived receipt refresh, then freeze a
   clean final head and run python lead/checks.py, all 35 configured steps green.
   New acceptance, controls and mutants are network blocked; disclose the full runner's
   existing read-only Ethereum RPC check. READY supplies exact commits, scope, red/final,
   contract, AST freeze, replay and mutant evidence privately. Fresh independent and
   red-team review, at most two rounds. No merge or push by the executor.

## Threat model

An upstream estimate can be valid without an independently computable reserve cap.
Neither suppress it nor certify it. A conditional observation about missing reserve
amounts must not become a new financial assertion, a scoring penalty, or an implied
verification of every unmarked pool. Preserve zero versus unavailable and fail-closed
verdict behavior. Do not turn the evidence study into a live RPC or identifier rollout.
No live VetAgent requests; any later authorized production readback must carry
x-mcp-client: vetagent-manual-probe.
