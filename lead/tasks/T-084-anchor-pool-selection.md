---
id: T-084
title: Select a representative anchor market on reserve-less fallback
status: ready
level: 3
size: S
base: 88fbbdc222680bc6cfe987b51a14fe81aef6a028
depends_on: [T-026, T-030, T-083]
---

## Context and goal

In the 2026-11-10 public WETH integration sample, a six-hour-old LEEPH/WETH pool
was selected on the GeckoTerminal fallback because it had the largest stated
USD reserve. The estimate priced nearly all of the depth in LEEPH. The WETH
price was ordinary, so price outlier rejection could not distinguish this pool
from active WETH venues. The age of the selected pool alone drove medium risk.
Keep depth as the default and prefer a corroborated anchor venue in this
specific unverified comparison.

## Scope

`src/risk.py`, `tests/test_risk.py`, and a reduced public GeckoTerminal fixture
`tests/fixtures/gt_weth_anchor_pools.json`. No changes to existing acceptance
assertions identified by the conflict search for pool ranking, reserve markers,
price comparisons, GeckoTerminal fallback or honeypot adjudication. Derived
test counts may be regenerated if the existing suite requires it. No requests,
score thresholds, public claims, telemetry or historical research changes.

## Acceptance

1. Both MCP tools resolve the public WETH sample to the WETH/USDC pool when
   the fallback is exercised. The same replay stops scoring the unrelated
   new pool's age, with unchanged positive simulation evidence. Retain the
   reserve-not-checked marker and use the selected pool's own reported fields.
2. Only reconsider a reserve-not-checkable GeckoTerminal depth winner when
   the requested address is a known anchor on that chain, and the other
   known address is outside the anchor table. An alternative must be an
   already eligible GeckoTerminal pool on that chain between two distinct
   anchors including the target. Both target prices must be observed and
   within the existing price disagreement factor. Its observed 24h volume
   and sell count must both exceed the winner's. Require a positive distinct
   seller reading on the alternative no larger than its sell count; this
   avoids changing the seller-lookup request path by introducing a gap.
   Among alternatives choose highest volume, then effective depth.
3. No comparable alternative, missing or invalid ranking inputs, a verified
   depth winner, non-anchor targets and ordinary DexScreener ranking retain
   the previous selection. An alternate chain, unrelated pool, same token
   on both sides or anchor ticker with a different address cannot qualify.
4. Missing sellability remains unknown, and independently observed severe
   sell restrictions remain high. Changing the selected market does not
   certify a reserve, change the rule for contested honeypot evidence, or
   add a request/retry path.
5. Keep tests-first evidence; run the offline project checks and reproduce
   the original vs corrected MCP result on the same full captured WETH pool
   response with a fixed clock. Independent review and adversarial review.

## Evidence and risks

Use the reduced upstream fixture in regression tests; the full captured public
response is for a one-off, local replay. Never assert live execution, reserve
verification, or a new accuracy benchmark from the offline replay. Try wrong
chains, namesakes, one-sided evidence, missing/invalid fields and a truly bad
sell result. Preserve the default where the cross-pool comparison is not
supported by observations.


## Amendments

2026-11-10: The tests-first fully confiscatory sell-tax case remains red after changing only
the market rank: using the new pool's trades can downgrade the adverse result.
Keep the original depth winner as the simulator retry and honeypot comparison
pool when the representative venue changes. Any honeypot comparison evidence
on that path must identify its pool separately. Add a named test in
`test_t084_weth_fallback_main_pool_through_mcp` for the unchanged retry target
after a failed simulation and for the comparison pool on a positive flag.
This preserves the existing adjudication policy, instead of introducing a
WETH-specific tax or score rule.

2026-11-10 independent review: require consistent raw GeckoTerminal chain and
identity evidence on both venues before applying the exception. Limit the new
comparison to EVM token addresses. The pool resource id and both relationship
ids must name the queried network, the token addresses and pool id must be
valid, and a separately reported pool address must agree with its resource id.
Reject reused pool IDs for the comparison. Keep previous ranking on these
unqualified inputs. Add a named regression in `test_t084_raw_fallback_identity`
that drives both MCP tools with wrong-network, malformed and duplicate rows.

Independent adverse review also found a dust-reserve challenger could outrank
a still-funded venue on historical volume, an undated pool could remove
observed age, and a fully confiscatory simulated sell tax with an inconsistent false
honeypot boolean could fall from high to medium after dropping the original
market's age points. Require a challenger to meet the existing USD 5,000
live-market floor and have an observed creation time. For assessment, apply
the representative substitution only after an observed clean sell simulation:
successful and not flagged, with observed zero taxes, no critical sellability
gap and no adverse upstream risk signal. For all other assessment results,
keep the original market evidence and signals. This supersedes the prior
conditional comparison-pool output field; the two tools may show different
market evidence when the assessment is unverified or adverse. Keep retry,
adjudication and other signals on the original market. Add named assertions in
`test_t084_raw_fallback_identity` and
`test_t084_weth_fallback_main_pool_through_mcp` for these observed cases.

