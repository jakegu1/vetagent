---
id: T-068
title: Compare target-token prices without losing finite consensus
status: ready
level: 3
size: M
depends_on: [T-021, T-065, T-066]
backlog: existing finite market-input and selected-pool correctness
---

## Context, benefit, cost and stop

Two offline ordinary-correctness witnesses reproduce on the published source.
On two unranked chains, quote-side pools' base priceUsd values can invent a
disagreement for equal target prices or conceal genuinely different target prices.
The existing pricing adapter already derives the requested token's price; the
unranked conflict helper does not use it. Separately, statistics.median can overflow
when adding two large finite middle values, disabling outlier removal even though
the median and all admitted individual prices are representable.

Protect target-price correctness, existing uncertainty and the current selection
rule. Cost one bounded task, two finding-specific fixes after frozen tests, fresh
functional/adversarial reviews and complete source/master/deployment gates.
Stop after these demonstrated seams. Historical real incidence is unmeasured.

## Scope

- src/risk.py: only unranked target-price conflict and finite consensus midpoint.
- tests/test_finite_price_conflict.py: additive acceptance functions/helpers only.
- tests/test_finite_market_measurements.py: additive acceptance functions only if
  its existing test harness is a better fit for the median seam.
- Lead-owned task/index/state/review metadata is separate.

No old acceptance/helper edits; no workflow, dependency, upstream, score-band,
100x comparison, three-price quorum, chain rank, independent-depth, scientific
source/protocol/archive, T047/T049/T050 or permission changes. No new calls,
fill, benchmark rebuild/enrollment or published measurement changes.

## Acceptance criteria

1. The actual assess path compares finite positive prices for the requested
   target, including base, quote and mixed orientation. Pass that target through
   the actual helper call. Missing/zero/invalid/underflowing/overflowing native
   conversion cannot vote or impersonate another token's price. Preserve no-target
   legacy helper behavior if any existing callers require it.
2. Retain the existing narrow gate: at least two unranked chains, at least two
   usable prices, reported-liquidity admission and strict greater-than100 conflict.
   Ranked/single-chain controls and truthful low/high evidence remain unchanged.
   Do not apply conflict scoring to additional chain classes or change its weight.
3. Add complete load/pick/assess/compact/MCP witnesses in both pool orders for
   equal target prices with different base prices, unequal target prices with
   equal base prices, mixed orientation, missing conversion and ranked controls.
   Check gaps/signals/scores and finite structured/text/schema agreement, with
   the earlier helper admission and strict100/101 boundaries preserved.
4. Even-length positive finite consensus computes a finite midpoint when the
   exact mean of the two middle values is representable, preserving the ordinary
   median result and odd-length behavior. Do not rescale all prices, round away
   a strict boundary or lower the three-price quorum. Keep unpriced candidates
   and the existing fallback semantics. Cover reversed orders, duplicates,
   largest-finite neighbors, subnormal controls and strict100/101 deviation.
5. Exercise actual _pick_best, assess/compact/MCP and liquidity outputs for four
   prices1,1e308,1e308,1e308 with the minority pool deepest. It must not select the
   contradicted minority due to arithmetic overflow. Preserve strict JSON, chain,
   target orientation, score policy and ordinary finite controls.
6. Commit tests first, alone, retaining meaningful parent reds. One implementation
   commit per finding and a commit message describing its red. Freeze old tests
   and new acceptance after that commit; unexpected conflicts mean BLOCKED.
   Fresh functional and adversarial review, meaningful removed-target/overflow
   mutants, independent full configured45 and root full gates are mandatory.
   Retain all raw failure/success evidence with shared compressed source baseline
   manifests instead of permanent whole-tree backups. No CI flags are cleared.

## Conflict search and evidence

Conflict search covered all tests/callers for _unranked_price_conflict, _price_of_target,
_drop_price_outliers, statistics.median, price_disagreement, _PRICE_DISAGREEMENT_FACTOR,
_MAX_PRICE_DEVIATION, _MIN_POOLS_FOR_CONSENSUS and both registered numeric runners.
Named existing-test changes: NONE. Existing finite market, finite price conflict
and Unicode underflow runners pass3814,1973 and2242 assertions respectively.
The existing deepest-pool consensus and narrow two-chain guards remain exact.

The actual initial falsifier records six failed intentions and eight controls,
two input orders and complete request adapters, not an external incident.
Pre/post fixtures and source digests, all required raw commands, test commit and
runtime finding commits must bind the same exact source reviewed and released.
For cached comparison, use only a separately bounded same-clock read-only replay,
never new provider calls or silently accepting missing inputs as measurements.

## Threat model

Ordinary upstream pool orientation and finite floating-point extremes must not
turn an unobserved target price into a confident number, invent or silence an
existing price warning, or let overflow disable selection defense. Keep all
scientific and security-review holds exact. No review of the interrupted T047
investigation is included or authorized by this task.
