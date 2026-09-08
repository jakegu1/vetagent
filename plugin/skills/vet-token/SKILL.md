---
description: Check a crypto token for honeypots, extraction taxes, thin liquidity and rug risk before buying, holding, or recommending it. Use whenever a token address or ticker comes up in a context where money could move, and before answering "is this token safe".
---

# Vetting a token before acting on it

This plugin adds the `vetagent` MCP server. Call `assess_token_risk` **before** you buy,
hold, or recommend a token — not after — and pass `chain_hint` whenever you know the chain.

## The one rule that matters

The verdict has **four** values, not three: `low`, `medium`, `high`, and **`unknown`**.

**`unknown` is not `low`.** It means a critical check could not run — an upstream was
down, the sell simulation failed, no liquidity data came back. The server is deliberately
fail-closed: it refuses rather than guessing. Roughly one answer in seven is that refusal,
and that is the tool working.

Never use an `unknown` to justify a trade. Say what was missing — it is listed in
`evidence.data_gaps` — and stop there, or ask the user how they want to proceed.

`confidence` measures **how complete the input data was**, not how safe the token is.

## Reading the rest of the output

- `signals` carries the specific findings behind the verdict, each with a severity and a
  category. Quote the signals, not just the score — "closed source contract and 12% sell
  tax" is actionable; "risk score 64" is not.
- `low` means *no fatal signal fired in the checks that ran*. It does not mean safe. The
  server sees on-chain risk only: it cannot see team behaviour, social engineering, or a
  rug executed through governance.
- The server never sizes a position and this is not financial advice. Report what it
  found and let the person decide.

## The other two tools

- `get_token_liquidity(address, chain_hint?)` — liquidity for the primary pair, with an
  explicit `status` so "the upstream failed" stays distinguishable from "no pools exist".
- `find_new_hot_pools(chain?, limit?)` — discovery only. A pool appearing here is **not**
  a safety endorsement; run `assess_token_risk` on anything you surface from it.

## Same address, different chains

Ethereum forks such as PulseChain inherit contract addresses, so the same address exists
on several chains at wildly different prices. Pass `chain_hint` when you know it; without
it the server prefers canonical chains and may not pick the one the user means.

Full contract: <https://github.com/jakegu1/vetagent/blob/master/docs/AGENT-INTEGRATION.md>
