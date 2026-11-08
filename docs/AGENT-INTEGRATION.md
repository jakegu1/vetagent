# 🤖 VetAgent — AI Agent Integration Guide

VetAgent is a **token risk intelligence MCP server** for AI agents. Before an agent buys, holds, or researches a crypto token, it can call VetAgent to get an **actionable risk verdict** (`low` / `medium` / `high` / `unknown`) — not a pile of numbers to re-interpret.

> **`unknown` is a verdict, not an error.** It means a critical check could not run. It is **not** a low-risk result and must never be used to justify a trade. The server is fail-closed on purpose: an agent acting on a confident wrong answer is worse than one that reads "I could not tell".

> ⚠️ Intelligence aid only. **Not investment advice.** Data comes from public on-chain/exchange sources. Liquidity figures are indicative (not true TAM of capital); honeypot check covers EVM only.

---

## 🔌 Remote MCP Endpoint (no local install)

> Building on this? **hello@vetagent.dev** reaches a person, and the maintainer will tell you before anything changes under you. The server counts calls but records no identities, so it can see that it is being used and never by whom &mdash; say who you are with `X-MCP-Client`, or an email, and an integration stops being anonymous traffic.

Connect directly over MCP-over-HTTP to the endpoint:

```
https://vetagent.dev/mcp
```

### Claude Desktop / Claude Code config
Add to your `claude_desktop_config.json` (or MCP config):
```json
{
  "mcpServers": {
    "vetagent": {
      "type": "http",
      "url": "https://vetagent.dev/mcp"
    }
  }
}
```

Any MCP client (Cursor, opencode, custom agent) works the same way.

---

## 🧰 Tools (3)

| Tool | What it does |
|---|---|
| **`assess_token_risk(address, chain_hint?)`** | Core. Aggregates multi-chain liquidity / contract safety (honeypot or rug check) / pool freshness into a structured risk verdict + agent recommendation. |
| **`get_token_liquidity(address)`** | Best-pair liquidity snapshot: price, 24h volume, cross-chain count. |
| **`find_new_hot_pools(chain, limit)`** | Scan a chain (default `solana`) for newest/hottest new pools for new-token discovery + risk. |

### Example: `assess_token_risk`
```json
{
  "address": "0x7D1A...",
  "risk_level": "medium",
  "risk_score": 36,
  "signals": [
    {"severity": "ok",   "name": "Liquidity is adequate", "category": "liquidity"},
    {"severity": "ok",   "name": "Buys and sells normally", "category": "honeypot"},
    {"severity": "ok",   "name": "Established pair", "category": "freshness"},
    {"severity": "warn", "name": "Contract is closed source", "category": "contract"}
  ],
  "recommendation": "Medium risk. Real signals fired but none are fatal. Review liquidity, holder distribution and contract permissions before deciding.",
  "confidence": "medium"
}
```

**Routing guidance for an agent:**

| `risk_level` | What it means | What the agent should do |
|---|---|---|
| `high` | A fatal or high-severity signal fired | Reject the automated path and surface the specific signals |
| `medium` | Real risk signals present, none fatal | Route to manual review |
| `low` | No fatal signal found across the checks that ran | Continue normal evaluation; this is not a safety guarantee or order permission |
| `unknown` | **A critical dimension could not be checked** | Retry only with valid infrastructure/mixed retry guidance; otherwise abstain. Never use it to justify a trade |

`confidence` measures **how complete the input data was**, not how safe the token is.
`evidence.data_gaps` lists exactly which checks could not run and why.

### Local response-routing example

`examples/assessment_policy.py` consumes existing JSON and returns only `action`, `reason` and
`retry_after_seconds`. It sends no request, waits for no retry, stores no input and places no
order. Every returned action is response-handling advice; none authorizes a trade.

These commands are fully local and need no token address or credentials:

```sh
echo '{"risk_level":"medium"}' | python -B examples/assessment_policy.py --transport http
echo '{"result":{"structuredContent":{"risk_level":"unknown","unknown_kind":"infrastructure","next_action":"retry","retry_after_seconds":30}}}' | python -B examples/assessment_policy.py --transport mcp
echo '{"risk_level":"low"}' | python -B examples/assessment_policy.py --transport http --http-status 429
```

The last example abstains because the transport status is not 200, even though the fixture body
claims low risk. The optional `--http-status` works for both HTTP and MCP; it accepts exactly
three ASCII decimal digits from 100 through 599. Its default 200 is a local fixture convenience.
Real integrations must supply the actual HTTP status through this option or the existing
`route_http(payload, http_status=200)` / `route_mcp(envelope, http_status=200)` Python parameter.
Every non-200 status abstains; the example does not infer retry advice from transport failures.
A present HTTP
payload error or MCP top-level error wins even when null. MCP uses only `structuredContent`,
requires dictionary result/content, and accepts a present `isError` only when exactly false.
It never parses text content as a fallback or handles a batch envelope as a single response.

An infrastructure/mixed unknown advises retry only when `next_action` is exactly `retry` and
the delay is an exact non-boolean integer from 1 through 2147483647. Coverage unknowns always
abstain. Missing kind or invalid/contradictory retry guidance also abstains, regardless of score.
Only retry advice carries a delay; all other results carry null. No sleep or retry is executed.

This adapter validates only consumed status, envelope, verdict and unknown-guidance fields.
It does not validate the complete assessment schema: for example, a low response with a malformed
unused score can still continue evaluation. `checked_at` and `evidence_max_age_seconds` remain
response context; an integrator must apply its own pre-registered freshness/workflow policy.
The example neither authenticates the response nor invents a freshness threshold or service goal.

The CLI reads at most one MiB of UTF-8 JSON. Duplicate keys, nonstandard NaN/Infinity literals,
malformed or oversized input and invalid arguments fail with a fixed diagnostic and nonzero exit,
without echoing input or credentials. Parser failures from deeply nested text are handled safely.
A parseable response that leads to abstention exits zero, including an unsupported envelope shape.

> VetAgent reports observable on-chain risk. It does not size positions, does not
> give financial advice, and cannot detect off-chain risk (team behaviour, social
> engineering, or a rug executed through governance). Never present its output as
> a recommendation to buy.

---

## 🌐 HTTP API (also callable without MCP)

```
GET /health
GET /assess/{address}
GET /liquidity/{address}
GET /new-pools?chain=solana&limit=10
```

---

## 📊 Data Sources
| Source | Covers |
|---|---|
| DexScreener + GeckoTerminal (fallback) | Multi-chain meme/new tokens, price, liquidity, pools |
| honeypot.is | Ethereum contract anti-scam (buy/sell tax simulation) |
| RugCheck | Solana rug risk score |

The engine uses **source resilience**: if DexScreener is unavailable, GeckoTerminal is used as fallback for liquidity.

---

## 🎯 Example Agent Prompts
- *"Assess token 0x7D1A... for risk and show me every signal that fired."*
- *"Scan the 5 newest Solana pools and flag any with rug risk."*
- *"Check liquidity depth of 0xC02... to estimate slippage risk."*

---

## 🔗 Links
- Live: **https://vetagent.dev**
- GitHub: [github.com/jakegu1/vetagent](https://github.com/jakegu1/vetagent)
