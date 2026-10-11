---
id: T-021
title: Reject invalid market scalars while preserving unavailable depth and observed zero
status: in_progress
level: 3
size: M
depends_on: [T-011, T-019, T-013, T-012]
decisions: []
---

# Numeric-boundary repair after the completed dependencies

The dated readiness amendment below records the completed dependencies, actual published
base, renewed conflict search and zero-miss replay prerequisite. Existing publication gates
and Owner authorization stay as defined by QUALITY/config.

## Context and goal

At the preparation audit, risk engine git blob
`a0ae14779b345a5e1f9ecb889f549b119dd55dfd`, was probed offline with copied tracked fixtures
and local fake fetchers. On the Ethereum USDC fixture, changing only liquidity.usd to the
valid JSON string "NaN" returned a complete `low` assessment and adequate-liquidity signal;
"Infinity" returned `medium` with an abandoned-market warning. Both public assessments and
liquidity responses failed `json.dumps(..., allow_nan=False)`. Malformed strings became
observed zero; huge integer conversion raised OverflowError. These are offline measurements,
not production sightings.

A real zero-depth pool beside null/tiny depth also returned a false all-pools-empty fatal
finding with an otherwise clean simulator. Filtering unknown readings out of the `stated`
list before testing whether it is all zero does not establish that every in-scope pool was
observed empty. The numeric fix must close that handoff as well as parse valid scalars.

Unavailable numeric observations remain unavailable, while genuine finite zero remains an
observation. Only finite valid measurements may support market depth, price, activity and
turnover claims. Preserve anchored-depth admission, the USD credibility floor, chain scope,
valid tiny prices and T-012's narrow no-trace rule.

## Scope and files

In: scalar validation and optional rounding for the existing market leaves and their direct
consumers in `src/risk.py`: USD/reserve depth, reserve-cap operands, primary/derived target
prices, h24 volume, signed h24 price change, market counts used as evidence, and discovery's
three optional figures. Include selection, cap arithmetic, whole-market turnover and the
stated-depth empty/gap handoff. Preserve absence provenance through the GT shim. Normalize
invalid GT counts before `_num` can erase their boolean/invalid provenance; T-012's accepted
GT boolean residual is removed by this numeric-boundary fix, with no threshold change.

Files in scope, exactly:

1. `src/risk.py` (bounded helpers and listed market consumers only).
2. `src/mcp_server.py` (`get_token_liquidity` outputSchema price_usd and volume_24h_usd become
   number-or-null; depth and discovery are already nullable).
3. New `tests/test_finite_market_measurements.py` (all acceptance tests and characterization).
4. `.github/workflows/test.yml` (register that file in the offline test steps).
5. `tests/test_risk.py`, only the mixed-depth tail of
   `test_a_fork_pool_cannot_silence_a_drained_rug` under named change (a) below.
6. `docs/SCORECARD.md`, only the real-generator test-count evidence under amendment (b).

Every existing test and fixture is frozen except that named mixed-depth assertion block.
Do not change `_num` or the default `_sig_round`
behavior, HP/simulator numeric fields, RugCheck/Token-2022/holder policies, risk thresholds,
anchor tables, freshness rules, chain selection policy, sources/fallback ordering, transport,
cache, telemetry labels, public pages/legal text or permission files. Do not add upstream
fields, dependencies or gap kinds. Whole-payload shape validation is out. No live calls,
benchmark fills, cache recording, rebaseline or public-number regeneration in T-021.

Reuse T-012's merged reason, predicate and finalizer exclusion for its no-observed-depth
plus finite positive in-scope sells path. Do not introduce another exclusion. For a mixed
scope containing genuine zero and unavailable readings, remove the false drained finding
but keep T-012's final escalation rule: zero is still a stated measurement, so its exception
for **no stated depth** does not apply. Use an existing about-token liquidity gap class with
truthful qualified wording, for example `_gap(_ABOUT_TOKEN, "among the sources queried, no
source reported pool depth for some listed pairs")`. This keeps the existing `no depth`
telemetry/publication reader phrase, introduces no label, and does not imply that every
source was queried. A clean simulator then yields unknown; NO_DATA may still yield the
existing no-trace high, with no fatal/drained or `pools_all_empty` claim. The exact wording
must satisfy these properties and the existing AST gap guard.

## Acceptance criteria

1. **Tests first and finite-scalar contract.** Commit only the new acceptance-test file first;
   record its red output. Register it in the workflow in the subsequent scoped change.
   Parameterize null, empty and
   whitespace strings, nonparseable strings, True/False, dict/list including empty forms,
   negative numeric/string values, float/string NaN and both infinities, overflow string
   "1e309", and a JSON integer `10**400`. These are unavailable at nonnegative market
   measurement leaves; none raises or becomes observed zero. Finite numeric strings and
   numbers remain measurements; 0, "0" and "-0" remain zero. Preserve signed finite price
   change, including negatives, with invalid optional change null. Characterize unchanged
   ordinary output rounding, legitimate missing-price pool selection, and non-market helper
   use. The initial tests run to completion and are red for end-to-end NaN, invalid-as-zero,
   and strict JSON failures, not just a missing helper name.
2. **Credible depth and arithmetic.** Credited USD uses the existing 1e-6 floor: zero is
   observed zero; nonzero below it is unavailable; exactly 1e-6, ordinary dust, normal numbers
   and numeric strings remain valid. Check both stated USD and a computed cap. Reject invalid
   operands actually needed for an anchored cap and reject non-finite computed products,
   quotients or sums before they can support a claim. Invalid-present required operands
   cannot retain reassuring stated depth or become cap zero. Preserve known `_NOT_CHECKABLE`
   residuals for absent reserve amounts/unknown chains and the deliberate two-anchor
   unbounded marker; do not treat that internal marker as upstream infinity. Unused
   non-anchored-side amounts cannot disqualify a valid cap. Tiny finite prices and raw
   discovery figures have no USD depth floor. Genuine anchored zero and ordinary capped
   cases retain their existing behavior.
3. **Complete depth handoffs and finalization.** With complete stubbed `assess` and
   `liquidity`, a single invalid/all-invalid depth scope cannot produce adequate-liquidity,
   fatal empty, `pools_all_empty`, or `drained`. With the clean `hp_matic.json` simulator it
   is unknown/unpriced and depth null, never low or medium. With NO_DATA and valid finite
   positive in-scope sells, the all-unavailable case uses T-012's integrated non-absence
   gap/exclusion and is unknown. A genuinely zero pool beside unavailable/null/tiny depth
   does not establish all pools empty: unpriced/depth null, no empty count or fatal, and the
   mixed-case finalization contract in Scope applies. All-genuine-zero stays drained/high;
   known-chain no pair, untraded/buys-only, invalid-sell and off-chain-only-sell controls
   preserve T-012's escalation. A real fatal HP finding remains high regardless of missing
   depth. An invalid candidate beside valid finite depth must select the valid alternative
   in either input order and remain within the unchanged home-chain scope.
4. **Prices, volume and market activity.** Validate stated primary prices before they can
   qualify a candidate and validate GT multiplication/target quote inversion results.
   Missing or unusable public target prices are null, not invented zero; valid tiny positive
   prices survive and genuine discovery price zero remains an observation. Invalid volume
   is null; valid zero volume is zero. If an included venue has unavailable volume, aggregate
   turnover is unavailable and cannot justify "Looks abandoned"/"Very little trading".
   Best-pool turnover is unavailable when its own volume is. When all venue readings are
   valid, preserve existing venue scope, aggregation, rounding and thresholds. Invalid/non-
   finite/negative/boolean market counts cannot support `_sells_demonstrated` or market-data
   simulator adjudication, or leak numeric infinity to `sellability_from_chain`. Preserve
   the existing finite valid count shape and thresholds; optional invalid public counts are
   null. T-012's weaker finite-positive-sells test remains distinct from the stronger
   current exit-evidence test. No simulator/HP taxes or holder counts are changed.
5. **Discovery and public schema.** Complete stubbed `new_pools` returns null for each of
   its three unavailable numeric figures; genuine finite zero and normal finite numbers/
   strings retain their values. Every full returned object in all acceptance cases,
   including assess verbose and compact outputs, liquidity and discovery, encodes with
   `json.dumps(..., allow_nan=False)`. Add a check that the declared MCP liquidity schema
   accepts the actual null price/volume/depth and normal numeric responses. Keep required
   fields, existing optional-key shape, discovery address handoff and partial-scan behavior
   unchanged. Strict JSON is necessary but insufficient: cap tests must also reject the
   currently finite 250,000/low result produced by a NaN/Infinity cap.
6. **Frozen tests and scope evidence.** Every existing risk, MCP, coverage-matrix,
   advertised-coverage, upstream-field and publication test stays unchanged and green,
   except the precisely bounded named change (a) below.
   Repeat the conflict search on the exact post-T-012 base, including every numeric helper
   caller and mapped reason reader. Existing-test changes permitted by T-021: only (a). T-012
   separately owns its named gap-atom test change; it is already in this base. Restore all
   monkeypatches in tests, and reject any unmatched fake fetch URL rather than falling back
   to transport. All functions in the new file are called by its main runner, and the
   workflow/offline-suite registration guard proves it runs.
7. **Deterministic benchmark and row-attribution gate.** Before the tests-first commit,
   after T-019 then T-013 then T-012 have merged, run the existing deterministic `--replay`
   once at the exact task base through the lead-authorized cache arrangement. It must exit
   zero, report zero misses and reproduce the committed benchmark outputs. A miss or base
   mismatch stops before implementation; no fill/rebaseline workaround. At head the replay
   again has zero misses and reproduces the base's committed outputs byte-identically. If
   any bytes/rows differ, stop with every changed field, row identity, verdict, score, driver,
   selected pair, depth and gap reason plus raw numeric-input attribution and request a named
   publication amendment. No generated files or publication are changed under this spec.
   Preserve risk bands, scope/coverage claims and publication decision thresholds; changed
   results are evidence, never grounds to move the bar. Do not run against the T-019
   executor's mutable cache or overlap benchmark runs.
8. **Contract and checks.** Tests-first SHA and red/green logs are retained; then implement
   only in scope, and run every configured offline step on the exact reviewed head, with
   no unexplained baseline regression. Level 3 fresh independent and red-team reviewers
   reproduce complete outputs with additional malformed scalars and validate strict
   encoding/schema plus zero/absence semantics. Show named acceptance failures for restored
   mutants: invalid-as-zero; `_num` permitting non-finite depth; malformed cap retaining
   stated depth; unknown volume contributing zero to turnover; filtering unavailable pools
   before claiming all-empty; and dropping optional null back to `_sig_round(None)` zero.
   Do not require the reviewer to trust helper-only output. Restore each mutant and confirm
   the final source/tree and checks; never merge the executor's own work or deploy without
   the existing Owner authorization.

## Acceptance-test names and fixture plan

The new file should expose individually named checks (equivalent subdivisions are permitted
if every case remains visible in the report and main runner):

- `test_market_depth_rejects_invalid_scalars_without_inventing_zero`
- `test_credible_depth_floor_and_anchor_caps_preserve_existing_measurements`
- `test_invalid_best_pair_cannot_outvote_a_valid_alternative`
- `test_complete_assessment_preserves_t012_traded_and_absence_controls`
- `test_mixed_zero_and_unavailable_depth_is_not_all_empty`
- `test_optional_market_prices_and_volumes_preserve_unavailable_values`
- `test_incomplete_volume_cannot_describe_the_whole_market_as_quiet`
- `test_market_counts_and_signed_change_are_finite_without_global_num_drift`
- `test_discovery_and_mcp_schema_accept_optional_nulls_and_strict_json`

Read-only fixtures: `tests/fixtures/ds_usdc.json` for complete mutated depth cases,
`hp_matic.json` for the clean simulator, `hp_retail_veryhigh.json` or the existing flagged
HP builder for real fatal control, `ds_weth.json` for ordinary low/rounding characterization,
`cg_weth_pools.json` and `gt_matic_polygon.json` for fallback side/address semantics.
Synthetic same-chain pairs explicitly name raw reserves, prices, sells and buys. Exercise
both-anchor marker, one-anchor cap, absent reserve-amount residual, underivable quote price,
GT finite arithmetic overflow, zero/unavailable mixtures, and valid alternative in both
orders. Every network path has a local stub; no API keys or real token calls are needed.

The preparation audit's full caller inventory and conflict extracts are retained as
private technical evidence. Repeat that search on the actual post-dependency base before
dispatch; no older contract needs an edit for the proposed boundary policy.
Particularly retain the missing-native-price assertion in
`test_price_is_the_asked_token_not_the_other_side`, which already accepts None, and the
explicit uncheckable-reserve behavior in `test_depth_counts_only_what_no_pool_creator_can_price`.

## Evidence required and stop rules

READY must include exact base/head SHAs and changed-file stat; acceptance tests-first commit
and red output; full NaN and Infinity before/after assess and liquidity inputs/outputs;
strict JSON results for all scalar families and full tools; genuine-zero/floor/cap controls;
both candidate orders; all-invalid/traded/untraded/fatal/mixed-scope outcomes; discovery/MCP
nullable agreement; aggregate volume/count evidence; frozen check results; restored mutant
results; and base/head zero-miss replay logs with output hashes. If the benchmark differs,
deliver a blocked row/field-attribution report rather than READY.

The preparation audit does not know whether any real cached benchmark row contains these
malformed values. Do not state that a published change is necessary without the exact-base
replay. Correctness changes may alter rows through selection, volume signals or true-gap
semantics, so the existing publication amendment gate applies even when all output values
are finite. Two review rounds; stop on missing scope, new upstream field, dependency
regression, unmatched replay URL or broader policy change. No module extraction or general
schema rewrite is authorized.

Threats: `float(True)`, `float(x or 0)`, unordered NaN comparisons, a non-finite computed cap
silently leaving finite stated depth, optional rounding inventing zero, partial observations
pretending every pool is empty, GT normalization hiding invalid provenance, and skipped test
registration. The task closes these measured numeric handoffs while preserving the existing
decision rules.

## Dated readiness amendment

2026-10-12: all four dependencies are independently reviewed, merged, deployed and verified.
T-012 is published as e657c32dcdc516c8d8c07f0a040527a4a69e2617; its actual deployment
38162750450 runs and passes all thirty-one offline steps, Worker deployment and tagged
production smoke. Tagged homepage, Agent text and health readbacks pass. Required master
jobs also pass. This exact published commit is the task base, not later lead bookkeeping;
its risk source blob is 6076480f13c71b20adc06fc10823fa7a14594fb6.

The read-only exact-base AST refresh inventories all 140 calls to the seventeen existing
numeric/scope helpers, 107 matching test-file functions including helpers, 93 actual
test functions and forty mapped-reason reader lines. These are search counts, not executed
test counts. The full extracts and caller/reason inventories are retained privately.
Missing-price selection, tiny prices, anchored reserve residuals, two-anchor infinity
marker, genuine zero, all-empty/unpriced distinctions, turnover aggregation, GT side
semantics, simulator adjudication, T-012 gaps and HTTP/MCP classifiers are read and remain
binding. The initial conclusion that no existing test change was needed missed one
conflicting mixed-depth assertion; the measured correction and sole exception are below.
In particular preserve
test_depth_counts_only_what_no_pool_creator_can_price,
test_a_fallback_pool_is_held_to_the_same_depth_rule,
test_an_empty_pool_does_not_speak_for_a_deep_one_we_cannot_price,
test_a_tiny_price_is_still_a_price, test_every_pool_empty_is_a_finding_not_a_gap,
test_unpriced_pools_are_not_empty_pools and
test_turnover_is_measured_over_the_token_not_one_pool, plus the merged T-012 acceptance.

The lead's own exact-base replay evaluates all 576 rows at 2026-09-21T02:00:00Z, misses
nothing and reproduces both committed raw output blobs byte-identically. All 6,741 cache
files and the recorded labeling log remain unchanged, with zero network calls, cache
writes or after-clock selections. The executor must independently repeat this prerequisite
on its own isolated cache copy before the first tests-only commit. The same no-fill,
no-row-drift stop rule and bounded scope remain binding. There is no permission to
silently rebaseline or regenerate public figures if numeric normalization changes a row.

## Dated arithmetic/zero clarification before acceptance

2026-10-12: the lead independently probes the exact published risk blob above. A
one-anchor Ethereum pool with positive reserve/price operands (quote reserve 1e-300,
target USD price 1e-300, native price 1, stated USD 100000) has computed cap and credited
depth both 0 through floating arithmetic underflow. A positive stated USD string 1e-400
also becomes credited zero during conversion. Both measurements are retained privately.
These are synthetic offline observations, not production frequency claims.

AC 2's existing nonzero-below-floor and true-zero contract covers these handoffs:
underflow to zero from a raw nonzero USD string or strictly positive required cap
operands is unavailable, rather than evidence of an empty pool. Include complete
assess/liquidity controls in the initial additive tests, and keep actual upstream zero,
signed numeric zero and genuine anchored zero unchanged. Valid representable tiny
prices retain their existing behavior without a new price floor. No transport/raw-JSON
decoder change, exact-arithmetic engine, threshold or other scope expansion is authorized.
All bounded-scope, old-test and benchmark stop gates remain in force, with the sole
existing-test exception registered below.

## Dated named change (a): old mixed-depth assertion

2026-10-12: tests-only 5e8a7fa runs to completion with 2067 passes and 1819 behavioral
failures before source changes. Scoped source 2091436 makes its immutable new acceptance
green (3814 passes, zero failures), but the unchanged old risk suite reports 1098 passes
and one failure. The failing check is the last mixed-depth block of
test_a_fork_pool_cannot_silence_a_drained_rug: zero plus unavailable on Ethereum is
required to emit "No liquidity left in any pool". That requirement contradicts AC 3.
The earlier conflict search missed this assertion; its inventory counts did not establish
that every behavior was compatible.

The lead independently reproduces complete assess/liquidity outputs on exact published
e657c32 and the frozen scoped source. With zero plus unavailable, the old engine claims
drained/high for both NO_DATA and clean HP. The scoped engine has null/unpriced depth and
no fatal/all-empty claim: NO_DATA remains high under the unchanged finalizer, while clean
HP is unknown with an explicit about-token liquidity gap. Two genuinely zero home pools
remain drained/high with either simulator control. All raw inputs and complete outputs
are retained privately. These are offline synthetic measurements, not occurrence counts.

Authorize one tests-only commit titled "T-021: named change (a) preserve the mixed-depth
gap". Change only the final mixed block and its immediately preceding comment in that
function: replace the false drained assertion with no-drained/no-empty-count plus an
explicit liquidity-gap check; add the same mixed fixture with clean hp_matic.json and
require unknown, null/unpriced depth and no fatal/all-empty claim. Keep the raw pair builder,
original mixed pairs, all other original assertions and all all-zero/fork/home-chain cases
unchanged. Demonstrate the amended block red against exact base e657c32 before checking
it against the scoped source. The first additive acceptance file remains byte-identical
to 5e8a7fa. No other old test/helper/fixture edit is authorized.

This aligns one old assertion with the already registered AC 3; it does not lower a risk
band, USD floor, finalizer rule, product gate or threshold. Scope is now exactly five files.
The head zero-miss/raw-row-drift stop and actual generated-test-count stop remain binding;
neither a benchmark rebaseline nor generated publication edits are authorized by (a).
The later explicit generator-only test-evidence amendment does not relax that row gate.

## Dated generator-only amendment (b)

2026-10-12: amended source b1eab7c has a zero-miss head replay identical to both base
raw output blobs for all 576 rows. All 6741 cache files, 1941 actual requests and the
real labeling log remain unchanged. All six prescribed mutants are caught. Actual
configured checks then finish with 31 of 32 passed; the sole red is the published-number
guard's real scorecard comparison, not a changed benchmark figure.

The executor retains the real publication failure and a private rendered diff. The lead
independently renders without any tracked write and compares all registered values on
the root/base engine and amended source. Every value is identical, all targets match,
and the maturity total remains 47. The only semantic scorecard difference is the risk
test-evidence count 1099 to 1106; MCP 80 and HTTP 596 are unchanged. Both raw committed
benchmark hashes also match. Windows working-tree CRLF hashes differ from Git blobs on
the root checkout; the proof distinguishes those explicitly and compares raw Git blobs.

Authorize real .github/scripts/regenerate-derived.sh regenerate on the executor source,
with no fake GitHub Actions environment. Inspect the complete diff and commit only this
generated docs/SCORECARD.md test-count row in its own generator-only commit. No benchmark
JSON/Markdown, cache, labeling log, public metric, threshold, scope claim, generator,
publication target, runtime source or existing test is changed by that commit. Restore
only date/recent-history-only docs/OWNER.md and pure line-ending docs/ROUNDS.md according
to merge.after, with their actual diffs retained. Any other semantic generated change
stops again for attribution; it is not pre-authorized.

Repeat the real guard green and complete 32-step suite. Independently prove the generated
row equals the real renderer, and separately disclose the expected OWNER recent-history
exception after the generated commit instead of claiming a raw global fixed point.
The scope is now exactly six files; initial additive acceptance remains byte-identical,
and named change (a) remains the sole old-test exception. Repeat/verify raw replay at the
final frozen head without modifying data. The original benchmark-drift stop remains
binding. Full fresh independent/red-team review and Linux preflight are still required.

## Dated draft amendment

2026-10-11: replace helper-only evidence with complete
offline NaN-low / Infinity-medium evidence; add missing nullable MCP scope, signed-change
and consumed-market-count validation, cap arithmetic and partial-empty handoff acceptance.
Order T-021 after T-019, T-013 and T-012 and reuse T-012's pre-registered rule without
widening it. Freeze all older tests except the later explicitly named mixed-depth change;
the initial additive acceptance remains immutable. Preserve the zero-miss and publication
row-attribution gates. Readiness is pending
the actual post-dependency base and renewed conflict/replay verification.
