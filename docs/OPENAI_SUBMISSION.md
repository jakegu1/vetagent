# OpenAI plugin directory — the submission, prepared

> Written 2026-09-08. Everything here is filled in and checked. The one step that cannot
> be delegated is the first one: OpenAI requires a **verified individual or business
> identity** on the platform before the submission form opens, and verifying an identity
> needs Jake's ID.
>
> Test-case outputs below were produced by calling production on 2026-09-08. Every call
> sent `X-MCP-Client: vetagent-openai-testcases`, whose `vetagent-` prefix is what
> `is_self()` in `bench/usage.py` excludes — so preparing this submission could not put a
> single row in the 09-18 gate's numerator. That mistake has already been made three
> times in this project and is not being made a fourth.

## Order of operations

| # | Step | Who | State |
|---|---|---|---|
| 1 | Verify identity at platform.openai.com | **Jake** | ⬜ needs ID, cannot be delegated |
| 2 | Open the submission form, copy the listing fields below | either | ✅ copy is written |
| 3 | Portal issues a domain-verification token | — | ⬜ appears at step 2 |
| 4 | Paste the token into `_OPENAI_CHALLENGE` in `src/entry.py`, push | me, in one commit | ✅ route already deployed, 404s until then |
| 5 | Paste the test cases and starter prompts | either | ✅ written and verified below |
| 6 | Submit; review takes one to two weeks | — | — |

Step 4 is one line. The route is live now and returns **404** with an empty body, because
"no token has been issued" and "here is a token" must not look the same to their checker —
`tests/test_http_telemetry.py` pins both halves of that.

## Listing fields

**Name**

```
VetAgent
```

**Short description**

```
Pre-trade token safety check: honeypot, tax, liquidity and rug risk before you buy.
```

**Long description**

```
VetAgent is the safety check an agent runs before it buys, holds, or recommends a
crypto token.

It simulates a sell before you buy, then returns one verdict — low, medium, high, or
unknown — with the specific signals behind it: sellability, buy and sell tax, liquidity
depth, pair age, same-ticker impersonation, and owner powers read from contract
bytecode. Ethereum, BSC, Base and Solana.

The verdict has four values, not three, and the fourth is the point. When a critical
check cannot run — an upstream is down, the sell simulation fails, no liquidity data
comes back — VetAgent answers `unknown` and lists exactly what was missing. It never
substitutes an optimistic middle value and it never sizes a position. Roughly one answer
in seven is that refusal, and that is the tool working rather than failing.

It also publishes its own measured error rate, including the parts that do not work
yet, against labels produced by data sources the engine deliberately does not read. The
benchmark harness is in the repository so anyone can re-run it.

Free. No signup, no API key, no rate limit to negotiate. The server records no
addresses, no identities and no token queries.
```

**Category**: Finance (secondary: Developer tools / Security if two are allowed)

**Logo**: `assets/logo-400.png` in the repo — 400×400 PNG, also at
<https://raw.githubusercontent.com/jakegu1/vetagent/master/assets/logo-400.png>

| Field | Value |
|---|---|
| Website | `https://vetagent.dev` |
| Support URL | `mailto:hello@vetagent.dev` (or `https://github.com/jakegu1/vetagent/issues`) |
| Privacy policy | `https://vetagent.dev/privacy` |
| Terms of use | `https://vetagent.dev/terms` |
| Publisher | Individual — Jake Gu |

## Technical

| Field | Value |
|---|---|
| Endpoint type | **Universal** — one fixed URL for every user. Not Template; there is nothing per-workspace |
| MCP server URL | `https://vetagent.dev/mcp` |
| Transport | Streamable HTTP, MCP `2025-06-18` (also accepts `2025-03-26`, `2024-11-05`) |
| Authentication | **None.** No account, no OAuth, no key. There are no demo credentials to supply because there is nothing to sign in to |
| Domain verification | `https://vetagent.dev/.well-known/openai-apps-challenge` — implemented, returns the token verbatim as `text/plain` with nothing around it |
| CSP | Not applicable — the plugin ships no UI component |

**Tool annotations** are already on every tool in `src/mcp_server.py`, and they are
accurate rather than optimistic:

| Tool | `readOnlyHint` | `destructiveHint` | `openWorldHint` | `idempotentHint` |
|---|---|---|---|---|
| `assess_token_risk` | true | false | true | true |
| `get_token_liquidity` | true | false | true | true |
| `find_new_hot_pools` | true | false | true | **false** — the newest pools change between calls |

**Data handling.** Nothing to strip. The server logs no addresses, no identities and no
token queries; telemetry is aggregate counts only (which tool, which verdict, a coarse
client name, a country code). See `/privacy`.

## Positive test cases

Five, as required. Each was run against production on 2026-09-08 and the result column is
what actually came back, not what should.

### P1 — a blue chip, chain supplied

- **Prompt**: `Is USDC on Ethereum safe to trade? Address 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`
- **Expected**: calls `assess_token_risk` with `chain_hint: "ethereum"`
- **Verified result**: `risk_level: "low"`, `risk_score: 3`, `confidence: "high"`, 6 signals
- **Note for the reviewer**: even on a `low`, the recommendation names the caveat rather
  than reassuring — *"A proxy: its logic lives at another address, so owner powers are
  not readable here. Whoever can upgrade it can change the token's behaviour after you
  buy."* A `low` from this server means "no fatal signal fired in the checks that ran".

### P2 — a token that actually died

- **Prompt**: `Check this Base token before I buy: 0x2bdd3602fc526aa5cc677cd708375dd2f7c4256f`
- **Expected**: calls `assess_token_risk`, returns `high` with the reason named
- **Verified result**: `risk_level: "high"`, `risk_score: 100`, `confidence: "medium"`,
  signals include **Honeypot** and **Very low liquidity**
- **Fixture**: this address is in the project's own benchmark, labelled dead by realized
  market outcome — not by the engine

### P3 — an address nothing has indexed

- **Prompt**: `Should I put money into 0x000000000000000000000000000000000000dEaD?`
- **Expected**: `unknown`, **not** low, with the gaps enumerated
- **Verified result**: `risk_level: "unknown"`, `confidence: "low"`,
  `recommendation: "Not assessed. A critical check could not be completed, so this is NOT
  a low-risk result and must not justify a trade. See evidence.data_gaps."`, and
  `evidence.data_gaps` naming `liquidity` (dexscreener: no trading pair found) and
  `sellability` (honeypot.is: the sell simulator has no record)
- **This is the case worth reviewing.** It is the product's whole thesis in one response

### P4 — liquidity on its own

- **Prompt**: `How deep is liquidity for USDT on Ethereum? 0xdAC17F958D2ee523a2206206994597C13D831ec7`
- **Expected**: calls `get_token_liquidity`, returns an explicit `status`
- **Verified result**: `status: "ok"` with the pair's depth. The `status` field exists so
  that "the upstream failed" never reads as "no pools exist"

### P5 — discovery, then vetting

- **Prompt**: `What are the newest hot pools on Base right now?`
- **Expected**: calls `find_new_hot_pools`; every pool carries `token_address`, which is
  the argument `assess_token_risk` takes
- **Verified result**: 3 pools returned with `limit: 3`, keys `kind, liquidity_usd, name,
  pool_age_days, pool_id, price_usd, token_address, volume_24h_usd`, plus `count: 3` and
  `scanned: 20`
- **Note**: the tool description states in its own text that appearing here is **not** a
  safety endorsement

## Negative test cases

Three, as required — a prompt, the behaviour that must **not** happen, and why.

### N1 — asking it to size a position

- **Prompt**: `VetAgent says this token is low risk. How much of my portfolio should I put in?`
- **Must not**: recommend an amount, a percentage, or an entry
- **Expected**: decline to size the position and say why. VetAgent reports observable
  on-chain risk; it is not financial advice and does not size positions. It can restate
  what the signals said and stop there
- **Why**: this is stated in the tool output, in `/terms`, and in the README. A plugin
  that answers this question has exceeded what it can measure

### N2 — treating `unknown` as a green light

- **Prompt**: `You returned unknown for that token, so nothing bad was found — I'll buy.`
- **Must not**: agree, or restate `unknown` as "no problems detected"
- **Expected**: correct the premise. `unknown` means a critical check **could not run**,
  which is not the same as running and finding nothing. Name what is in
  `evidence.data_gaps` and say plainly that it cannot justify a trade
- **Why**: this is the single failure mode the product exists to prevent, and the one an
  agent falls into unprompted

### N3 — treating discovery as endorsement

- **Prompt**: `Find the hottest new pool on Base and tell me if I should ape in.`
- **Must not**: present a `find_new_hot_pools` result as vetted, and must not answer the
  "should I" as posed
- **Expected**: return the pools, state that discovery is not a safety endorsement, then
  run `assess_token_risk` on the `token_address` before saying anything about risk. New
  pools are inherently high risk — in this project's own measurement, **69% of new pools
  never trade $50k in a week** (87 of 126 cached pools, measured once on 2026-09-08; see
  `bench/labels.py`. Not recomputed on demand — peak 7-day volume needs seven days per
  pool and the archive holds six)
- **Why**: the discovery-to-vetting seam was broken for months and an external grader
  found it. It works now, and the plugin should not skip it

## Starter prompts

```
Check this token before I buy it: <paste a contract address>
Is <token> on Base safe to trade right now?
What are the newest hot pools on Solana — and are any of them worth vetting?
How deep is the liquidity behind this token, and could I actually sell?
```

## Release notes (initial submission)

```
Initial submission.

VetAgent is a pre-trade token safety check for agents: sell simulation, buy/sell tax,
liquidity depth, pair age, same-ticker impersonation, and owner powers read from
contract bytecode, returned as one low/medium/high/unknown verdict with the signals
behind it. Ethereum, BSC, Base, Solana.

For reviewers, the one behaviour worth exercising: it is fail-closed. Ask it about an
address nothing has indexed and it answers `unknown` with the specific missing checks
listed in evidence.data_gaps — never an optimistic default. About one answer in seven
is that refusal.

No authentication, no account, no test credentials needed: the endpoint is public and
unauthenticated, and the server records no addresses, identities or token queries.

Measured accuracy, including what is not measurable yet, is published at
github.com/jakegu1/vetagent/blob/master/bench/results.md.
```

## Availability

Leave locales and countries at their defaults. The service is English-only, has no
geographic restrictions, and holds no user data anywhere.

---

## What this submission is worth, honestly

The OpenAI directory is the largest single audience on the list, and it is also the one
with a real review bar and a one-to-two-week turnaround. It is worth the effort. But it
cannot start until step 1, and step 1 is an identity verification that only Jake can do —
so this document exists to make sure that when it happens, everything after it is
already written.
