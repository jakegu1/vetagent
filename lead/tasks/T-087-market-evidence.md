---
id: T-087
title: Require market ownership and distinguish invalid listings from empty markets
status: ready
level: 3
size: S
depends_on: [T-086]
---

Token-market retrieval can use an unrelated pool or turn a malformed upstream
success response into a confirmed market absence.

1. REST and MCP only use pools that explicitly belong to the requested token,
   including per-chain completion and both fallback hosts. Solana token
   addresses retain case. CoinGecko and GeckoTerminal relationships must
   identify the token on the requested network.
2. A valid empty listing or supported not-found response counts as observed
   absence. Invalid list envelopes, unrelated-only listings and malformed rows
   cannot establish absence or crash an assessment. Preserve usable target
   rows from a mixed listing, and use eligible alternate sources where needed.
3. Verify normal, unavailable, confirmed empty and mixed/foreign cases through
   real REST and MCP, with archived clean controls and full offline checks.

Scope is src/risk.py and existing risk and HTTP tests, with generated counts.
The discovery listing has a separate contract. Preserve reserved balance
qualification, canonical chain ranking, request limits and known empty semantics.
Threats include wrong token listings, wrong-network relationships and invalid
success envelopes that resemble absence.

Named fixture change: give the synthetic GeckoTerminal venue in
test_the_override_can_fire_on_the_geckoterminal_path explicit Ethereum token
relationships. Keep all trade-count and honeypot adjudication assertions.
