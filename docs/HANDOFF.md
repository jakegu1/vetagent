# 🤝 VetAgent — Handoff (HANDOFF.md)

> Product + technical handoff for the AI coding agent taking over (Claude Code).
> Product owner: Jianyi (Jia's chief AI lead) — you own **implementation**, I own **overall planning, direction, and quality**. We work together; this is not a chain of command.
> Goal: pick this up with **zero context loss** — what to work on, which traps are known, which principles hold, and who to ask for resources.

---

> **Read [`DECISIONS.md`](DECISIONS.md) first** — that is where "why it is this way" lives, and what enforces each rule.
> This file only answers "what state is it in, what will bite you, what's next". It does not repeat the reasoning.

## 0. Roles first (the most important thing to get straight)

- **I am the product/project owner** (Jianyi): direction, priorities, quality, the moat, and backing your call when you have a better idea.
- **You are the dev agent** (Claude Code): **coding, deploying, fixing, testing**. You can **push back and improve** on my direction — I actively want that.
- **Jake is the boss**: final call plus resources (domain, Cloudflare, GitHub, servers).

**Working principles we agreed on (please follow them):**
1. **Assume it is broken until proven otherwise.** "Implemented" is not "working". Verify with real calls and tests. This is a risk product, and **false positives and false negatives are both fatal** — stay conservative.
2. **Propose better approaches.** If you spot a hole in my plan, a smarter design, or a hidden cost, **say so** instead of quietly executing a worse plan.
3. **When asking Jake or me for support, spell out the options.** Domain, Cloudflare quota, GitHub, servers are all coordinated by Jake. Say what you need; don't sit on it and don't buy anything on your own.
4. **fail-closed is absolute.** When a risk tool cannot get data it returns `unknown` — **never** an optimistic middle value or a position-sizing suggestion.
5. **Separate fact from judgment.** Measured data is a hard constraint; your inferences are risk flags, not a veto on direction.
6. **Quality > quantity.** One sharp thing, not a shotgun.

---

## 1. What the product is (one sentence)

**VetAgent — a "pre-purchase safety check" for AI agents.** Before an agent buys, holds, or researches a token, it calls this and gets an **actionable verdict** (`low`/`medium`/`high`/`unknown`) plus a recommendation written for agents, instead of being handed a pile of numbers to interpret.

This is not a tool for trading yourself, it **sells shovels** — keeping people and teams who want AI-driven crypto decisions out of the obvious holes. **The money comes from trust and distribution, not from the market.**

## 2. Production (what is actually live)

| Item | Value |
|---|---|
| Production URL | **https://vetagent.dev** (Cloudflare Worker: no ICP filing, automatic HTTPS, global CDN)|
| Fallback URL | https://vetagent.jake-gu95.workers.dev |
| MCP endpoint | **https://vetagent.dev/mcp** (streamable-http, verified against the official FastMCP client)|
| Landing page | https://vetagent.dev/ (VetAgent branding, SEO/GEO, JSON-LD)|
| Source repo | **github.com/jakegu1/vetagent** (Worker version, main line of development)|
| Docs repo | github.com/jakegu1/crypto-agent-risk (China-server version + ops docs)|
| Cloudflare domain | veteagent.dev (zone id 371490a6e5d239a023df9667bfe811b7)|
| Account ID | 3976e6f6f8237d5aa08543efa0e78887 |

> ⚠️ **Credential safety**: the Cloudflare API token lives in `.git-credentials` or comes from Jake, and **must never be committed to GitHub**. Deploy with the env vars `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (see §6).

## 3. Stack & architecture

**Path: `~/projects/vetagent-worker/` (on the server)**

```
src/
  entry.py       — Worker entrypoint (class must be named Default) + HTTP routing
  risk.py        — risk engine (pure Python, no heavy deps): assess / liquidity / new_pools
  mcp_server.py  — hand-rolled streamable-http MCP endpoint (JSON-RPC)
  landing.html   — landing page
docs/
  server.json    — official MCP registry manifest
  AGENT-INTEGRATION.md — integration guide written for agents
pyproject.toml   — uv project, deps=[], dev=[workers-py, workers-runtime-sdk]
wrangler.jsonc   — Cloudflare config (routes: vetagent.dev custom_domain)
```

**Key technical decisions (do not casually reverse these):**
- **Pure Python + the Workers built-in `fetch()`**, not httpx — Pyodide has compatibility risk with httpx's dependencies, and `fetch()` is what Cloudflare recommends.
- **Hand-rolled MCP endpoint**, not the official `mcp` package — that package needs `pydantic`'s C extension, which **will not install** on Cloudflare Python Workers (tested). The hand-rolled JSON-RPC turns out to be compatible with the official client anyway.
- **Modular**: entry (routing) / risk (engine) / mcp_server (protocol) — one source of truth, no duplication.

## 4. Traps already hit (remember these, don't step in them again)

| # | Trap | Fix |
|---|---|---|
| 1 | The Worker entry class **must be named `Default`**, otherwise you get "no fetch handler" | fixed class name `class Default(WorkerEntrypoint)` |
| 2 | `request.url` is a **string**, not an object | use `from urllib.parse import urlparse` |
| 3 | Needs `uv >= 0.12.3` | already on 0.12.9; `uv self update` |
| 4 | Use `pywrangler`, not bare `wrangler` (it bundles the deps)| `.venv/bin/pywrangler dev/deploy` |
| 5 | The first request after a cold start can time out | `_fetch_json` already retries with exponential backoff (2 attempts)|
| 6 | The official `mcp` package will not install on Pyodide | hand-rolled MCP endpoint |
| 7 | git push through the proxy hangs (HTTP408); direct is more reliable | `git -c http.proxy= -c https.proxy= push` |
| 8 | GeckoTerminal uses `eth`, chain_hint/DexScreener use `ethereum` | one chain-name mapping (fallback branch fixed)|
| 9 | Relative imports fail | use absolute `import risk`, not `from . import` |
| 10 | **pywrangler does not run on Windows** — it wants to build an emscripten pyodide venv, which Windows does not support | deploy from CI (`.github/workflows/deploy.yml`); in a pinch use WSL: `XDG_CONFIG_HOME=/mnt/c/Users/<you>/AppData/Roaming/xdg.config uv run pywrangler deploy` to reuse the OAuth session Windows already has |
| 11 | Bare `wrangler deploy` builds fine but the **deployed Worker crashes on startup** — `ModuleNotFoundError: No module named 'workers'`, because it does not vendor workers-py | always `uv run pywrangler deploy`. A passing dry-run **does not mean** it runs; it never checks runtime imports |
| 12 | `git pull origin master` while on another branch merges master into the current branch, leaving local master stale | before deploying, compare with `git rev-parse --short master origin/master` — don't ship against old code |

## 5. Unfinished / next priorities

### ⚠️ Correction to last round's "done" list (2026-09-03)

The previous version said "☑ Done: P0 fixes (pool selection / input validation / fail-closed / no signal → unknown)".
**That record was wrong.** Testing found:

| Claimed fixed | Reality |
|---|---|
| Pool selection | Only applied to `assess()`; `liquidity()` was untouched — production reported USDC at $0.00097 |
| Input validation | Same story: `liquidity()` validated nothing |
| No signal → unknown | The `unknown` branch was unreachable; with every data source down it returned medium |
| Honeypot detection | **Never worked**: it read `simulationResult.isHoneypot`, but upstream puts it under `honeypotResult`. Missing key → None → False → a constant "ok / not a honeypot" |

The root cause was not carelessness, it was **no tests**. When "Verified" only means someone
manually ran two or three addresses, missing a code path is inevitable, not bad luck.

**Hence the first discipline introduced this round:**

> Any commit claiming to have fixed something must come with a matching test case,
> and that case must be red before the fix. Every case under `tests/` maps to a defect that really happened in production.

```bash
python tests/test_risk.py              # 71 cases, offline, real upstream snapshots
python tests/test_mcp.py               # 41 cases, MCP protocol conformance
python tests/test_upstream_contract.py # 41 cases, live network, checks upstream JSON paths
```

The third one matters most: **only a contract test could have caught the honeypot bug** —
it was reading a key upstream does not have, and no mock test can find that.
CI is set up (`.github/workflows/test.yml`); if either of the first two suites is red, no merge.

**☑ Actually shipped this round**: honeypot key-path fix + wiring in upstream summary.risk/flags/contractCode,
fail-closed when simulation fails, validation and pool selection added to `liquidity()`, forked-chain pool-selection
guard, pair-age fix, scoring model changed to "worst signal dominates", Solana path rewritten (score_normalised +
authorities + holder concentration), MCP protocol conformance (top-level error / batch / 405 / CORS / version
negotiation / structuredContent / annotations), 153 tests + CI, position-sizing advice removed from the docs.

**🔴 Top priority: accuracy benchmark**

Run a batch of known rugs and known-good tokens through it and publish **recall and false-positive rate**.

The reasons have not changed (it is the only way a risk product earns trust, and nobody else does it), but there is a harder one now:
**we just proved we can let an entire detection dimension fail silently for six months while everything looked fine.**
Without a benchmark, the next one is again found by accident. The benchmark is this product's regression test.

Suggested approach (ordered by feasibility):
1. Positives: historical tokens that honeypot.is rated `very_high` and RugCheck marked `rugged=true`
2. Negatives: top-500 CoinGecko tokens by market cap that have a DEX pool
3. Metrics: recall (share of fatal risks missed), false-positive rate (share of normal tokens called high),
   and the **unknown rate** — whether that number is honest decides directly whether the product can be trusted
4. Write the results into the README and update them with every release

**🟡 Known gaps (ordered by rug-prevention value / effort)**

| Gap | Notes |
|---|---|
| Holder concentration on EVM | Solana already has it (RugCheck topHolders), EVM does not. Needs GoPlus `token_security` (free, no key), which also returns mint/blacklist/mutable-tax permissions and LP locks in the same call |
| LP locked/burned | Pulling liquidity is the main rug shape on EVM, and it is currently not covered at all |
| Same-name token collisions | The most common loss in agent scenarios is not buying a honeypot, it is **buying the impostor**. The data source is already there (DexScreener search); not built |
| Caching | Every call hits 2-4 upstreams with no cache. A 30-60s TTL on popular tokens would noticeably cut latency and rate-limit exposure |
| Rate limiting / abuse protection | Public unauthenticated endpoint, no rate limit of any kind |
| Observability | No logs, no metrics; a production problem can only be chased by manual repro |

**🔵 Things Jake has to decide** (see §7): see "Open decisions" below.

## 6. How to deploy (on the server)

```bash
cd ~/projects/vetagent-worker
# sync deps
.venv/bin/pywrangler dev --port 8787            # local test
# deploy (credentials via env vars, never written into git)
export CLOUDFLARE_API_TOKEN=<from Jake>
export CLOUDFLARE_ACCOUNT_ID=3976e6f6f8237d5aa08543efa0e78887
.venv/bin/pywrangler deploy
```
- In local dev, dexscreener may return nothing because the proxy is flaky (**the production edge connects fine**, so verify against production).
- Watch call volume: `npx wrangler tail vetagent --format json`

### 🖥️ Developing on your own machine (Jake's box)
1. `git clone https://github.com/jakegu1/vetagent.git && cd vetagent`
2. Install `uv` (>=0.12.3): `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. `uv sync` (installs workers-py + workers-runtime-sdk)
4. **Cloudflare credentials**: ask Jake for `CLOUDFLARE_API_TOKEN` (set it as a local env var only, **never write it into git**). Create one in the Cloudflare dashboard → My Profile → API Tokens (scope it to `Workers: Edit` + `Account: Read`, nothing more). Or just `npx wrangler login` (OAuth, safest).
5. `npx wrangler dev` to test locally; `npx wrangler deploy` to ship.

> Two options: `wrangler login` OAuth (safest, no token to hand around) and an API token (stable across networks). On a remote server the API token is more reliable; for local development prefer OAuth.

## 7. Asking Jake / Jianyi for resources

Say what you need and Jake will sort it out:
- **Cloudflare** ($5/month Workers, nowhere near the cap)
- **Domain** (vetagent.dev is bought, zone ID in the table above)
- **GitHub** (jakegu1 account)
- **Server** (124.222.120.49, already running the China-hosted crypto-agent-risk)

## 8. Key reference files
- `docs/server.json` — MCP registry format
- `docs/AGENT-INTEGRATION.md` — integration docs for agents
- `reference/projects.md` (on the Hermes side, not in this repo) — project status at a glance

---

## 9. Open decisions (Jake's call)

1. **Whether to push and deploy this round's fixes.** Branch `fix/p0-honeypot-liquidity`, committed locally,
   153 tests green. Production is still running the build where honeypot detection does nothing.

2. **Infrastructure identifiers in a public repo.** The Cloudflare Account ID
   (`3976e6f6...`) and Zone ID (`371490a6...`) in the §2 table are committed to a **public repo**.
   Neither is a secret and neither alone lets anyone act on the account, but they are useful material for targeted social engineering or phishing.
   Suggest moving them to a private note and leaving a single "ask Jake" line in the repo. Confirmed: git history contains **no**
   token or credential file.

3. **Landing page language.** Chinese only right now. The tool itself has no language attachment,
   and a Chinese page cuts out the overwhelming majority of potential users. Suggest an English version (or both).

4. **Distribution.** Not yet registered in the official MCP registry (`docs/server.json` is ready but was never submitted).
   Not listed on awesome-mcp-servers, Smithery, mcp.so, PulseMCP, or Glama.
   All of these are one-time work with long-lived acquisition.

## 10. Three things for whoever picks this up next

1. **Run the tests before you touch code.** `python tests/test_risk.py` should be 71/71.
   If it is red, someone broke a path that once produced a real defect.

2. **A red upstream contract test is not necessarily your fault.** It hits live APIs, so a third party renaming a field turns it red.
   Check whether upstream changed first, then update `risk.py` to match — that is exactly why it exists.

3. **fail-closed is the one thing in this product that cannot be traded away.** Any time you are about to write
   "default to X when the data isn't there", stop. The right answer is always `unknown` plus an entry in `data_gaps`.
   A risk tool that honestly says "I don't know" is worth something; one that guesses wrong is not.

---

## 11. Distribution: done / waiting on you

### ✅ Done (2026-09-04)

| Channel | Status | Notes |
|---|---|---|
| **Official MCP Registry** | live as `dev.vetagent/vetagent` v0.2.0 | Uses **domain verification** rather than a GitHub account, so the namespace hangs off the product domain, not a personal account |
| **PulseMCP** | automatic | It pulls from the official registry, nothing to submit separately |

**How to republish** (when the version changes):

```bash
# Private key is at C:\Users\86277\.vetagent-secrets\key.pem — outside the repo, never commit it
PRIV="$(openssl pkey -in ~/.vetagent-secrets/key.pem -noout -text | grep -A3 'priv:' | tail -n +2 | tr -d ' :\n')"
mcp-publisher login http --domain vetagent.dev --private-key "$PRIV"
cd docs && mcp-publisher publish
```

The Worker serves the public key at `/.well-known/mcp-registry-auth` (see `src/entry.py`).
**Lose the private key and you can never publish another version under that namespace** — keep a copy in the password manager,
and as a GitHub Secret (`MCP_REGISTRY_KEY`) so CI can publish automatically.

### ⬜ Needs Jake in person (all require signing up, which I cannot do for him)

| Channel | Entry point | What it needs |
|---|---|---|
| **Claude plugin directory** | https://platform.claude.com/plugins/submit | A Console account (free, whoever signs up is Owner), then the repo URL `github.com/jakegu1/vetagent`. Everything on the repo side is ready: `.claude-plugin/plugin.json`, `.mcp.json`, LICENSE, public repo |
| **Glama** | https://glama.ai/mcp/servers | GitHub OAuth, needs write access to this repo |
| **Smithery** | https://smithery.ai/new | Smithery account + API key (once the key is in hand, publishing is a command away) |
| **mcp.so** | https://mcp.so/submit?type=remote-server | Site email/password account (note: **that site has password reset turned off**, so put it in the password manager) |
| **awesome-mcp-servers** | https://github.com/punkpeye/awesome-mcp-servers | GitHub PR. ⚠️ Their bot will not pass the check until you are **listed on Glama**, so do Glama first, then open the PR |

### Every candidate channel (exhaustive, ordered by "will an agent actually find us here")

The ordering is not by channel size, it is by **whether our users would reach the tool through it**.
A directory with a million visits whose users are all humans in a browser is worth close to zero in an agent scenario.

**Tier 1 — agents really do discover tools here**

| Channel | Who | Status | Notes |
|---|---|---|---|
| Official MCP Registry | me | ✅ live | The de facto standard; several downstream directories sync from it |
| PulseMCP | — | ✅ automatic | Pulls from the official registry |
| Claude plugin directory | **Jake** | ⬜ | A Console account is all it takes, repo side is fully ready |
| Cline MCP Marketplace | me (GitHub PR) | ⬜ | Large Cline user base, and it is an agent scenario |
| Cursor Directory | **Jake** | ⬜ | Needs an account |
| Continue Hub | **Jake** | ⬜ | Needs an account |

**Tier 2 — human developers pick tools here**

| Channel | Who | Status | Notes |
|---|---|---|---|
| Glama | **Jake** | ⬜ | GitHub OAuth. **Must come first**: the awesome list's bot requires it |
| awesome-mcp-servers (punkpeye) | me (PR) | ⬜ | Blocked on Glama |
| Smithery | **Jake** | ⬜ | Once the API key is in hand I can publish from the command line |
| mcp.so | **Jake** | ⬜ | Site account, **password reset is turned off**, so store it in the password manager |
| mcpservers.org (wong2) | **Jake** | ⬜ | Email only, no account needed |
| MCP Market / OpenTools / mcp-get | **Jake** | ⬜ | Long tail, diminishing returns, whenever there is time |

**Tier 3 — framework ecosystems (aimed at developers building their own agents)**

The tool registries for LangChain / LlamaIndex / CrewAI / Vercel AI SDK.
All of them are a PR or a doc listing and I can do them, but **wait until someone is actually using this** —
doing it now means writing integration docs nobody reads for a product with zero users.

**Tier 4 — content and community (experiment C)**

Show HN, r/ethdev, r/mcp, r/LocalLLaMA, the crypto dev crowd on X, a long Dev.to post.
One fixed angle: **"we published our own false-positive rate, and nobody else in this category does"**.
No feature lists — nobody shares a feature list, people share a counterintuitive number.

### Three routes that are not on the standard list but may be worth more

1. **Open PRs against other people's open-source trading agents to wire the safety check in.**
   A directory waits to be found; this walks straight into the code. GitHub is full of open-source trading bots,
   and a "call vetagent before buying" PR against a few of them — one merge
   beats sitting in ten directories. **I can do this; the cost is half an hour per PR.**

2. **Open-source the benchmark methodology as a public standard.**
   If others adopt it, we are the reference implementation. Authority bought at almost no cost, no market share required.
   The leverage here beats any directory, because what it changes is **our position in this category**, not our exposure.

3. **GEO, not SEO.** Already done (`/llms.txt`, FAQPage structured data, quotable concrete numbers).
   Our users do not Google, they ask a model. Models cite **numbers you can check**, not adjectives —
   which makes the table reading "false-positive rate 11.3%, recall not measurable" the most persuasive thing on the site.

> One line for every submission: **read-only analysis tool, executes no trades, gives no investment advice**.
> That is not just compliance wording — it is the product's actual boundary, and the same reason §5 bans referral kickbacks.
