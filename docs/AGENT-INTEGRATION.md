# 🤖 VetAgent — AI Agent Integration Guide

VetAgent is a **token risk intelligence MCP server** for AI agents. Before an agent buys, holds, or researches a crypto token, it can call VetAgent to get an **actionable risk verdict** (`low` / `medium` / `high` / `unknown`) — not a pile of numbers to re-interpret.

> **`unknown` is a verdict, not an error.** It means a critical check could not run. It is **not** a low-risk result and must never be used to justify a trade. The server is fail-closed on purpose: an agent acting on a confident wrong answer is worse than one that reads "I could not tell".

> ⚠️ Intelligence aid only. **Not investment advice.** Data comes from public on-chain/exchange sources. Liquidity figures are indicative (not true TAM of capital); sell simulations cover Ethereum, BSC and Base.

VetAgent reports liquidity across eight chains. On Ethereum, BSC and Base, it reports
available sell-simulation and tax evidence and whether the simulation matches the
displayed pool. On Solana it checks token authorities and liquidity. An unavailable
sell check is disclosed.

---

## 🔌 Remote MCP Endpoint (no local install)

> Building on this? **hello@vetagent.dev** reaches a person, and the maintainer will tell you before anything changes under you. The server counts calls but records no identities, so it can see that it is being used and never by whom &mdash; say who you are with `X-MCP-Client`, or an email, and an integration stops being anonymous traffic.

Connect directly over MCP-over-HTTP to the endpoint:

```
https://vetagent.dev/mcp
```

### Claude Code

```bash
claude mcp add --transport http vetagent https://vetagent.dev/mcp
```

### Claude Desktop

Open **Customize → Connectors**, choose **Add custom connector**, and enter
`https://vetagent.dev/mcp`. Choose **No sign in** if asked, then enable the connector
in your conversation. An organization owner may need to add it first in a managed
workspace. See [Claude's remote connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

### Cursor

Add this to your project's `.cursor/mcp.json`, merging with existing servers:

```json
{
  "mcpServers": {
    "vetagent": {
      "url": "https://vetagent.dev/mcp"
    }
  }
}
```

### Plain HTTP

The same engine answers without an MCP client. Include the chain when you know it:

```bash
curl 'https://vetagent.dev/assess/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2?chain_hint=ethereum'
```

---

## 🧰 Tools (3)

| Tool | What it does |
|---|---|
| **`assess_token_risk(address, chain_hint?)`** | Core. Aggregates multi-chain liquidity / contract safety (honeypot or rug check) / pool freshness into a structured risk verdict + agent recommendation. |
| **`get_token_liquidity(address)`** | Best-pair liquidity snapshot: price, 24h volume, cross-chain count. |
| **`find_new_hot_pools(chain, limit, listing)`** | Scan a chain (default `solana`); `listing` defaults to `mixed`, or select `trending` for active-pool discovery. |

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

### Passing discovery results to assessment

For active-pool queries, select the existing trending listing before applying the limit:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"find_new_hot_pools","arguments":{"chain":"base","limit":10,"listing":"trending"}}}
```

HTTP uses the same option: `GET /new-pools?chain=base&limit=10&listing=trending`.
Omitted or explicit `mixed` keeps the original new-first merged result and response fields.
`trending` fetches only that listing and adds `listing: "trending"`; `scanned` counts its
distinct pools before the limit. Its `ok` means that selected list was observed, including
an empty list. A failed selected listing is an error, never a substitution with new pools.
Mixed `ok` still means both listings answered; `partial` means only one did.
Inspect `pool_age_days`, current `liquidity_usd` and `volume_24h_usd`; missing values are
unknown. Trending, age and one liquidity observation do not establish sustained funding,
exit availability or safety. Discovery adds no assessment or ranking.

Each usable `find_new_hot_pools` row includes `assessment_args`, containing exactly
`address` and the canonical `chain_hint` of the selected discovery network. Pass this
object unchanged as the arguments to `assess_token_risk`, preserving the selected
chain preference. The hint is not a strict chain lock: if the market source only sees
another chain, the engine may report that observed chain. For example, a synthetic Base row
can supply:

```json
{"address": "0x1111111111111111111111111111111111111111", "chain_hint": "base"}
```

`assessment_args` is absent when the base token address is invalid, missing, or belongs
to the wrong address family, or the selected network has no supported assessment chain. Do not guess from the pool name or
ID, and do not silently fall back to an address-only assessment. Discovery itself makes
no assessment call. Before using the answer for the discovered target, require returned
`evidence.chain_searched` to match `assessment_args.chain_hint`. Assessment may select a
different primary pool; it does not certify the exact discovered pool or authorize a trade.

After checking that the discovered row has `assessment_args`, use the existing local
adapter to enforce the returned-chain check:

```python
from examples.assessment_policy import route_mcp

args = discovered_row["assessment_args"]
request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": "assess_token_risk", "arguments": args}}
# Send request with your existing MCP transport and retain its actual status and envelope.
advice = route_mcp(response_envelope, actual_http_status, expected_chain=args["chain_hint"])
```

### Consuming permission evidence

The `assess_token_risk` output schema in `tools/list` describes the optional
`evidence.owner_powers` object. It can be absent, including on non-EVM assessments;
other evidence remains available. Compact and verbose responses carry the same
permission observations.

A synthetic bytecode match can produce this object:

```json
{
  "evidence_basis": "bytecode_selector_match",
  "matched_selectors": {"can mint new supply": ["d5391393"]},
  "current_authority": "not_checked",
  "powers": ["can mint new supply"],
  "found_none": false,
  "scan_is_incomplete": true,
  "is_proxy": false,
  "selectors_dispatched": 1,
  "bytecode_bytes": 6
}
```

`d5391393` is the selector for `MINTER_ROLE()`, a role getter. The legacy label
`can mint new supply` and the `bytecode_selector_match` basis describe code indicators,
not verified callable actions or present control. `matched_selectors` maps existing
labels to unique lowercase eight-hex selectors. `current_authority: "not_checked"`
means authority, activation and reachability were not observed. Do not turn these
labels into a claim that someone can currently exercise the named power.

`found_none: true` means an incomplete scan found no mapped selector; it does not prove
that permissions are absent. `is_proxy: true` flags a proxy-wrapper indicator, and any
wrapper matches do not establish the implementation's permissions. The scanner does
not follow that indicator to audit the implementation.

A failed RPC observation instead produces, for example:

```json
{"unavailable": "rpc error response", "current_authority": "not_checked"}
```

This is a failed observation, not a completed no-match scan. Success fields can be
absent; do not fill them with empty matches or infer a successful permission check.
Continue to consume the returned verdict and signals; an informational signal can
contribute to the existing score.

### Market and simulation pool correspondence

`evidence.pool_link` is `same`, `different`, or `unknown` in both assessment modes.
It compares the final displayed market with the venue declared by the simulator response
the engine retained. It does not assert a successful simulation, safety, or an exit for a
particular wallet or amount. A failed simulation can still identify its venue; read
`evidence.honeypot.simulation_success` separately.

With `verbose=true`, `evidence.pool_link_details` distinguishes the market, the source's
reported chain/pool, and the chain/pool actually sent in the request. `policy_chain` is the
existing engine's validation and coverage context, not an observed chain. Missing facts
are null. Unknown reasons describe missing, invalid or conflicting identity; they do not
change the risk verdict or add a scoring gap. Chain conflicts take precedence over pool
conflicts, rejected identity, missing market/simulation, and missing or invalid identifiers.

The default simulator call lets its upstream choose a pool. A later explicit retry can ask
for another pool, but that request does not prove the response identified it. `adopted_response`
names the retained default or retry response; the optional `retry` object records a retry
even when it was rejected. A rejected retry cannot replace the original response's identity.
After a clean sale, the existing market logic may promote a different displayed pool: the
correspondence compares against that final market, not the earlier depth winner. For example,
a retry can report the requested pool while `pool_link` is `different` from the final market.

Comparisons use complete validated identities before display truncation. EVM hex case does
not distinguish identities; conflicting aliases or absent chain declarations never prove
`same`, and requested/hinted identity does not fill a missing source declaration. Display
IDs retain the 48-character limit plus an ellipsis. Equal truncated strings are not enough
to establish exact identity across responses.

`get_token_liquidity` adds `best_pair_address` only when an `ok` result has a selected pool
ID. `source` is the data provider; `best_pair_dex` is the trading venue. This tool does not
call a simulator or return a simulation correspondence. Its selection can differ from an
assessment's conservative market when sell evidence is missing; compare the disclosed
context without treating a liquidity snapshot as simulated exit depth.

### Reported single-sale quantity limit

Both assessment modes may include `evidence.max_sell`, attributed to the adopted
Honeypot.is simulation with `scope: "simulated_transaction"`. Its `amount` is an exact
nonnegative uint256 decimal string and `unit` is `token_smallest_unit`: the smallest units
of the assessed token, not the other asset in the pair. Compare intended raw quantities
using integer arithmetic, without converting the string to a floating-point number.
For a token with eight decimals, `"996"` represents 0.00000996 tokens. An intended raw
quantity of 997 exceeds that reported cap; a smaller quantity is not an execution guarantee.

The fact is omitted without a displayed market. It retains `pool_link`: `different` or
`unknown` does not establish a limit for the displayed market. It can coexist with
honeypot warnings and does not change the risk
verdict. Missing, invalid or unreported quantities are omitted, never interpreted as
unlimited. The upstream's display amount and paired-asset quantities are not substituted.
See the [Honeypot.is simulation result](https://docs.honeypot.is/ishoneypot#simulation-result).

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

Retry at most once. The caller owns the attempt history: for a response received after that
retry, pass `retry_attempted=True` to `route_http` or `route_mcp`, or use the CLI flag
`--retry-attempted`. Another otherwise valid retry recommendation becomes `abstain` with
reason `retry_budget_exhausted` and a null delay. A completed low, medium or high response
keeps its ordinary action; coverage unknowns and invalid guidance keep their existing reasons.

This command handles a second unknown response without making another request:

```sh
echo '{"risk_level":"unknown","unknown_kind":"infrastructure","next_action":"retry","retry_after_seconds":60}' | python -B examples/assessment_policy.py --transport http --http-status 200 --retry-attempted
```

The Python context is keyword-only and accepts exactly `True` or `False`; other values yield
`abstain` with reason `invalid_retry_context`. Existing transport and envelope errors take
priority. Omitting the context preserves existing behavior, including positional `http_status`.
A `retry_attempted` field inside assessment JSON is ignored: only the caller argument or CLI
flag supplies history. The adapter does not track attempts, store state, or perform retries.

This adapter validates only consumed status, envelope, verdict, unknown-guidance fields and
caller-supplied retry context.
When `expected_chain` is provided, it also requires an evidence object with a valid,
exactly matching `chain_searched`. The keyword-only context accepts the canonical names
`ethereum`, `bsc`, `base`, `polygon`, `arbitrum`, `optimism`, `avalanche` and `solana`.
Aliases, case changes and other values abstain with `invalid_expected_chain`; missing or
invalid observed context yields `chain_context_unavailable`, and a different supported
chain yields `assessment_chain_mismatch`. These results never carry a retry delay.
The CLI uses the same policy through `--expected-chain base`. Omitting the context (or
passing `None` in Python) preserves existing routing. Existing transport/envelope errors
take priority, and the caller-owned retry budget still applies to matching-chain responses.
An `expected_chain` field in response JSON does not supply caller context.
It does not validate the complete assessment schema: for example, a low response with a malformed
unused score can still continue evaluation. `checked_at` and `evidence_max_age_seconds` remain
response context; an integrator must apply its own pre-registered freshness/workflow policy.
`checked_at` is when the answer was created. `evidence_max_age_seconds` is a request-level
upper bound on local cache residence observed when JSON is returned from cache to request
logic and usable cached bytecode is reused during the request. JSON later rejected or
replaced still counts; this is not the
precise age of only the finally adopted evidence. Positive fractions round up to whole
seconds; negative clock skew counts as zero. Bytecode can have a longer cache TTL than
market responses. Zero means no positive local cache residence was recorded, not that
every upstream observation is live. This is not the age of every market field, an indexer's
observation or a block, and does not prove current executability. For example, a 59-second
cached JSON response identifying the wrong token is rejected and live GeckoTerminal data
supplies the final pool: the field still reports 59, which does not mean the final pool
fields are 59 seconds old. Fresh-cache reuse alone does not imply an outage or lower
confidence; existing `served_stale` disclosures still identify fallback data returned
because an upstream did not answer.
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
| honeypot.is | Sell-simulation and tax evidence on Ethereum, BSC and Base |
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
