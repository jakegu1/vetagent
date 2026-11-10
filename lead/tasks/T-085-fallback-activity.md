---
id: T-085
title: Choose an established venue when fallback depth and activity conflict
status: ready
level: 3
size: S
base: c9af3cdc2bd7054349f8e1ea012eaf8372cd0783
depends_on: [T-084]
---

## Context and goal

Archived discovery snapshots for Arbitrum USDC and BSC USDT contain a new pool
with an outsized USD estimate and very few distinct sellers, next to an older
venue with much stronger observed trading. The current GeckoTerminal ranking
keeps the new pool when the older pool's counterparty is outside the anchor
table. Prefer a representative venue in this narrow case. The snapshots
record a subset of venues and do not establish the on-chain reserve split.

## Scope

`src/risk.py`, `tests/test_risk.py`, and a reduced snapshot-derived fixture
`tests/fixtures/gt_fallback_activity.json`. No changed old assertions after
searching the risk and MCP tests for pool selection, fallback, reserve markers
and sellability. Existing test-count generation may be refreshed if required.
No production or supplier requests, release, score or benchmark threshold
changes, anchor expansion, Solana ranking changes, or public claim changes.

## Acceptance

1. Replay Arbitrum USDC and BSC USDT from the same archived observations with
   fixed collection clocks. With DexScreener empty, the liquidity tool returns
   the established venue's own estimate and keeps the reserve caveat.
2. Apply the exception only to the existing T-084 identity and provenance
   scope, after the two-anchor rule has no qualifying alternative. Require
   the depth leader to be under 3 days old with at most one observed distinct
   seller, and the alternative to be at least 30 days old with at least
   20 observed sells and 10 distinct sellers. Distinct sellers cannot exceed
   sells. Require at least USD 50,000 each in the alternative's stated depth
   and 24-hour volume. The leader's estimate and the alternative's traded
   volume must lead their respective comparisons by at least 100 times, with
   both observed target prices within a ratio of 1.05. Prefer the highest
   traded volume among eligible alternatives, then stated depth.
3. No fallback promotion on missing, inconsistent or insufficient age,
   volume, seller, depth, price or identity inputs. Preserve DexScreener
   ranking, verified reserve evidence, non-anchor and non-EVM behavior, and
   the earlier two-anchor priority. Use addresses, not pool names.
4. The risk tool continues to require independently clean sell evidence to
   use a representative venue. Keep original evidence when the simulation
   was unavailable or adverse. A controlled clean-sell fixture checks the
   age and reserve caveat from the selected venue. Do not change requests,
   retries, timing, reserve verification, or contested-sell adjudication.
5. Commit tests first with a meaningful red result. Re-run the risk and MCP
   suites, the offline project checks, and the archived full-batch replay.
   Independently review functionality and adverse cases before acceptance.

## Evidence and risk

Report full response replay separately from reconstructed discovery data and
synthetic simulation. A new pool can price its counterparty implausibly, or
a rival can manufacture trading activity. Use valid same-chain identities,
comparable target prices, elapsed time and both activity readings to limit
the ranking exception. A supplier estimate and an activity count establish
neither reserves nor sellability. Keep the existing fail-closed risk path.

## Amendments

Independent review reproduced malformed upstream ages returning an MCP error,
negative ages acting as established pools, and future creation or contradictory
leader seller counts qualifying the new comparison. A zero distinct-seller
count must agree with a zero sell count. A future timestamp can still trigger
the existing freshness warning within clock skew, but cannot support the new
replacement. Reject invalid creation values without throwing. The established
alternative also keeps the existing requirement to exceed the leader's sell
count, so a high observed sell count on the leader remains a reason to abstain.
Named change in `test_t085_fallback_activity_requires_extreme_disagreement`:
add these cases without changing the first-commit expectations.

Adverse review reproduced a successful fresh-address simulation accompanied
by failed holder sells. Treat recorded holder failures or siphoning as adverse
for the existing market-substitution gate. Preserve the original venue and
the holder evidence without changing the risk adjudication policy. Named
change in `test_t085_archived_fallback_activity_through_mcp`: add a separate
contradictory simulator response to the BSC replay.

Named change in `test_t085_fallback_activity_requires_extreme_disagreement`:
check volume priority and the depth tiebreak among multiple established rivals.
A reported zero volume with nonzero sells cannot establish a weak leader.
Retain the observed zero-volume, zero-sell case, which appears in the archive.
