---
id: T-083
title: Preserve recognized chain hints and existing stale-cache behavior on upstream failures
status: ready
level: 3
size: M
base: 588d14b021c740cd856eac37696cab126be0c014
depends_on: []
---

## Goal, cost and stop

Two offline MCP handoff reproductions identify implementation gaps. An accepted
bnb alias is canonicalized elsewhere but not when selecting fallback networks;
an unrelated first-network throttle can prevent querying the intended BSC network.
An upstream error envelope delivered with HTTP200 returns before the already
permitted stale-cache fallback, while the same failure delivered as HTTP429 uses
that cache and discloses its age. Correct those seams without new data sources,
requests, retry loops, thresholds or a longer cache lifetime.

Benefit: recover usable existing market evidence in these demonstrated cases.
Cost: two minimal finding commits, focused tests and independent review followed
by the existing complete gates. Stop after these two defects; do not redesign the
fetcher, tune a benchmark or build acceptance infrastructure. No production
frequency, false-block improvement or customer outcome has yet been measured.

## Files and conflicts

- src/risk.py: _load_pairs fallback network selection and _fetch_json error-body
  exit only, plus directly relevant comments.
- tests/test_risk.py: additive test_t083_* functions/helpers in its existing
  automatic runner. Exercise the actual MCP route where needed by importing the
  existing server; do not edit tests/test_mcp.py (another task owns it).

Root owns task/index/state administration. No existing assertion or fixture may
change. Existing test_an_error_body_is_not_data,
test_every_tool_discloses_stale_data,
test_a_chain_hint_we_cannot_match_is_less_information_not_more,
test_an_unrecognised_chain_hint_is_not_a_chain and
test_a_fork_pool_cannot_silence_a_drained_rug remain intact. Existing
test_t031_real_cache_policy_and_disclosure_survive_provider_failover in the MCP
suite remains a cross-component regression, unmodified. No new test file/CI step.

## Acceptance criteria

1. Commit only new tests first; retain meaningful independent reds for both defects
   on the parent. Implement each finding in its own subsequent commit. Restore
   all patched process/module/cache state after each test. Do not change old tests.
2. Reuse _canonical_chain for recognized fallback hints. bnb/binance/arb/op/matic
   and already supported spellings/case/whitespace select the same first fallback
   network as the corresponding canonical chain. A hinted BSC response is reached
   without first querying Ethereum. An unknown or absent hint keeps the existing
   discovery order; an observed home-chain override and fork defense still win.
3. An error envelope recognized by the existing _is_error_body is never returned
   as data or written into cache. Terminate that failed attempt and reach the
   existing eligible-cache branch without adding a retry or sleep. An eligible
   300-second cached body and its original age are preserved just as for HTTP429;
   the existing age<=900 boundary is unchanged. Missing/expired cache returns None.
4. Preserve request count/order outside the recognized hint correction. Fresh
   cache still avoids upstream reads; success still caches data; mark_missing404
   still returns NO_DATA even with stale cache. Preserve failure accounting,
   provenance, no-data/empty distinctions, timeout and retry settings. Error text
   and credentials must not enter public responses or test summaries.
5. Exercise actual get_token_liquidity MCP routing with synthetic responses and an
   existing local fixture: canonical/alias outcomes agree; transport/body-error
   outcomes agree when cache is eligible; unavailable stays unavailable when it is
   not. Also exercise assess with market recovery and a missing critical sell
   check: recovered market evidence must not turn missing sellability into low.
   Stale evidence still limits confidence and is disclosed. Tests deny networking;
   no Vendor request or production probe is part of source validation.
6. Keep all risk weights, bands, critical dimensions, published figures, labels,
   benchmark clock, historical source contracts, W40/W57 originals and all frozen
   study results unchanged. No new compatibility claim for historical native V1.
7. Run focused risk and existing MCP regressions, then Root-assigned serialized
   configured full gates. Fresh functional review and a separate ordinary
   adversarial review must independently reproduce the behavior and boundaries.
   Root owns integration, exact-head CI/locked builds and normal deployment.

## Evidence and threat model

READY includes exact base/tests/finding SHAs, named diff, parent red/new green
native exits, recorded synthetic request counts, boundary results and unexecuted
dimensions. Existing benchmark replay may be run once for a private paired
regression readout only if inputs are present: no cache fill, original outputs
unchanged, existing clock and endpoint independence preserved, replay misses
retained. The published benchmark is not updated by this task.

The realistic adverse cases are stale-cache extension, error documents becoming
data, wrong-chain reads, failure becoming observed absence, and usable liquidity
incorrectly satisfying a missing critical sell check. Existing invariants and
explicit negative tests cover these without a new validation controller. Preserve
all evidence with the existing compressed retention method, not full-tree copies.
