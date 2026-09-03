# VetAgent

**A pre-trade safety check for AI agents.** Before an agent buys, holds, or recommends
a token, it calls VetAgent and gets an actionable verdict — `low` / `medium` / `high` /
`unknown` — plus the specific signals behind it, instead of a wall of numbers to interpret.

Remote MCP endpoint: **`https://vetagent.dev/mcp`** · Landing page: **https://vetagent.dev**

```jsonc
// assess_token_risk("0x…", chain_hint="ethereum")
{
  "risk_level": "medium",
  "risk_score": 36,
  "confidence": "high",
  "signals": [
    {"severity": "ok",   "name": "流动性充足", "category": "liquidity"},
    {"severity": "ok",   "name": "可正常买卖", "category": "honeypot"},
    {"severity": "warn", "name": "合约闭源",   "category": "contract"}
  ],
  "recommendation": "中等风险：需人工核实流动性、持币分布与合约权限后再决定。"
}
```

---

## `unknown` is not `low`

This is the single most important thing to know about the output.

VetAgent is **fail-closed**. When a check cannot run — an upstream is down, a
buy/sell simulation fails, no liquidity data comes back — it returns `unknown` and
lists exactly what was missing in `evidence.data_gaps`. It never substitutes an
optimistic middle value, and it never sizes a position for you.

`confidence` measures **how complete the input data was**, not how safe the token is.

A risk tool that honestly says "I don't know" is useful. One that guesses is not.

---

## Tools

| Tool | What it does |
|---|---|
| `assess_token_risk(address, chain_hint?, verbose?)` | Full risk profile: sellability simulation, liquidity depth, pair age, holder concentration, contract permissions, upstream aggregate verdicts |
| `get_token_liquidity(address, chain_hint?)` | Liquidity snapshot for the primary pair, with an explicit `status` so "upstream failed" is distinguishable from "no pools exist" |
| `find_new_hot_pools(chain?, limit?)` | Newest / hottest pools on a chain. Discovery only — **not a safety endorsement** |

Pass `chain_hint` whenever you know it. Ethereum forks such as PulseChain inherit
contract addresses, so the same address exists on multiple chains with wildly
different prices; the hint removes that ambiguity. (Without it, VetAgent prefers
canonical chains — see `_CHAIN_RANK` in `src/risk.py`.)

Full agent-facing contract: [`docs/AGENT-INTEGRATION.md`](docs/AGENT-INTEGRATION.md).

---

## Accuracy benchmark

Most token-risk tools publish a feature list. We publish **measured recall and false
positive rates**, regenerated on a schedule, against labels produced by data sources
**the engine does not read**.

→ **[`bench/results.md`](bench/results.md)** — current numbers, method, and known limits.

Why it is built this way:

- **Independent labels.** If the benchmark labelled tokens using honeypot.is — which
  the engine reads — it would only measure whether VetAgent can relay honeypot.is.
  Labels come from realized market outcome (price/volume history) and from GoPlus,
  which is deliberately held out of the engine.
- **A runtime assertion, not a promise.** The benchmark records every endpoint each
  side touched and **fails the run** if the two sets intersect. A circular benchmark
  is worse than none, so it is made structurally impossible rather than documented.
- **An ablation column.** A token that already collapsed has ~zero liquidity today, so
  flagging it is close to tautological. Results are therefore reported twice: with all
  signals, and with liquidity/lifecycle signals removed. The gap is what the engine
  actually contributes beyond the obvious.
- **`unknown` rate reported alongside recall.** A tool that answers `unknown` to
  everything has perfect recall and zero value.

```bash
python bench/build_dataset.py --limit 250   # sample + label (independent sources)
python bench/run_benchmark.py               # score the local engine, write results.md
```

---

## Tests

```bash
python tests/test_risk.py               # engine regressions, offline, real upstream snapshots
python tests/test_mcp.py                # MCP protocol conformance
python tests/test_upstream_contract.py  # live: asserts the JSON paths we depend on still exist
```

Every case in `tests/` is pinned to a defect that actually reached production.

The contract test earns its keep: VetAgent's worst bug was reading
`simulationResult.isHoneypot` when honeypot.is puts that flag in `honeypotResult`.
The key did not exist, the lookup returned `None`, it was read as `False`, and the
honeypot check silently passed **every token it was ever asked about**. No mocked test
could have caught that — only one that calls the real API and asserts the shape.

**Rule for this repo:** a commit that claims to fix something ships with a test that
was red before it.

---

## Architecture

Cloudflare Python Worker, no heavy dependencies.

```
src/
  entry.py        HTTP routing (entry class must be named Default)
  risk.py         risk engine — assess / liquidity / new_pools
  mcp_server.py   hand-written streamable-http MCP endpoint (JSON-RPC 2.0)
  landing.html    landing page
bench/            accuracy benchmark (independent labels + ablation)
tests/            regression, protocol, and upstream-contract suites
docs/             agent integration guide, handoff, MCP registry manifest
```

The MCP endpoint is hand-written rather than using the official `mcp` package: that
package pulls in `pydantic`'s C extensions, which do not install on Cloudflare Python
Workers. Plain JSON-RPC turned out to be smaller and fully client-compatible.

## Data sources

| Source | Used for |
|---|---|
| DexScreener | pairs, price, liquidity, volume, pair age |
| GeckoTerminal | liquidity fallback, new/trending pools |
| honeypot.is | EVM buy/sell simulation, taxes, aggregate risk, contract openness |
| RugCheck | Solana rug score, mint/freeze authority, holder concentration |

GoPlus is **not** used by the engine — it is reserved as the benchmark's held-out
oracle. Adding it to the engine requires giving the benchmark a new independent
labeller first, or the accuracy numbers stop meaning anything.

## Where things are written down

Four documents, one job each. If something is in two of them, one of them is wrong.

| Document | Answers |
|---|---|
| `README.md` (this file) | What is this, how do I call it |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Why is it built this way, and **what enforces each rule** |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Where things stand, what breaks, what to do next |
| [`docs/STRATEGY.md`](docs/STRATEGY.md) | Who pays, what the moat is, when to shut it down |

Why a change was made lives in the commit message, which is immutable and attached
to the diff. Why a line of code looks odd lives in a comment next to that line.
Neither gets copied into a document, because a copy rots without anyone noticing.

## Scope

VetAgent reports **observable on-chain risk**. It is not financial advice, it does not
size positions, and it cannot see off-chain risk — team behaviour, social engineering,
or a rug executed through governance. Treat `low` as "no fatal signal found in the
checks that ran", never as "safe to buy".

## License

Not yet chosen — see `docs/HANDOFF.md`.
