# Decision Log (DECISIONS.md)

> This is not a changelog. **One line per decision**, unless what it cost is worth the space.

## How to use this file

**The bar for inclusion (only one)**: *would someone who doesn't know this hit a trap?*
Yes → it goes here. No → it belongs in a commit message, not here.

**Why not put every "why" into docs**: docs rot, and they rot silently.
So every decision also has to answer: **what is enforcing it?**

| Enforcement | What it means |
|---|---|
| Test name | Breaking it turns CI red. **The strongest kind** — the rule alarms on its own |
| CI | Guaranteed by a workflow |
| Runtime | An assertion in the code; violating it fails outright |
| None | Just written down. A human can ignore it. **This is a TODO, not a destination** |

> **The goal of this file is for the "None" column to disappear.**
> An important decision still sitting at "None" means we haven't actually implemented it,
> only recorded it.

**Retirement rule**: an entry whose status becomes `Reversed` collapses to one line pointing at
whatever replaced it; the original text is not kept.
Once the table passes 40 rows, merge every test-enforced entry that has never failed into a
single summary line — they no longer need prose, the test is the documentation.

**What does not belong here**: why a specific piece of code is written the way it is
(→ a comment next to that code), why a specific change was made
(→ the commit message, which is immutable and sits against the diff),
current progress and open work (→ HANDOFF.md), business judgement (→ STRATEGY.md).

---

## Decisions

| # | Decision | Why | Enforced by | Status |
|---|---|---|---|---|
| **Risk engine** |
| E1 | Read the honeypot flag from `honeypotResult.isHoneypot` | Upstream `simulationResult` has no such key, so reading it is always False → every token comes back "safe" | `test_honeypot_key_is_read_from_the_right_object` + `test_honeypot_is` | Active |
| E2 | Simulation failure → `critical`, not a pass | Treating "can't buy in" as "nothing wrong" is the most dangerous call we can make | `test_simulation_failure_is_fail_closed` | Active |
| E3 | `_fetch_json` returns `None` on failure, never `{}` | Callers have to tell "the fetch failed" apart from "there genuinely is nothing"; fail-closed depends on it | `test_upstream_failure_yields_unknown` | Active |
| E4 | Missing data on a critical dimension → `unknown` | A risk tool guessing wrong is worse than one saying it doesn't know | `test_upstream_failure_yields_unknown` | Active |
| E5 | Score = worst signal dominates plus a capped corroboration bonus, not a sum | Under a sum, more signals means a higher score; add a few dimensions and normal tokens get pushed to high | `test_clean_token_stays_low` | Active |
| E6 | `confidence` measures data completeness, not how risky something is | The original had it backwards: the more complete the data, the lower the confidence | `test_upstream_failure_yields_unknown` | Active |
| E7 | With no `chain_hint`, converge on the canonical chain rather than the median price | Fork chains like pulsechain inherit contract addresses; 29 of USDC's 30 pools sit there, so voting by pool count is guaranteed to be dragged off | `test_liquidity_picks_the_right_pool` | Active |
| E8 | Parse `pairCreatedAt` as an integer number of milliseconds | Upstream sends an int; the old code called `.replace()`, the error was swallowed, and the age signal never once fired | `test_pair_age_works_on_integer_timestamps` + `test_dexscreener` | Active |
| E9 | On Solana use `score_normalised`, and read mint/freeze authority and holder concentration | The original compared the raw score against a threshold of 5000 — BONK's raw score is 101, so every token passed unconditionally | `test_solana_rugcheck_signals` | Active |
| E10 | `evidence` is trimmed by default; only `verbose` returns everything | In MCP, tokens are money | `test_output_is_compact` | Active |
| **MCP protocol** |
| M1 | JSON-RPC errors go at the top level, not inside `result` | A spec-compliant client reads `result.error` as success | `test_errors_are_top_level` | Active |
| M2 | Hand-written MCP endpoint instead of the official SDK | The official package needs pydantic's C extension, which Pyodide can't install (tried it) | None | Active |
| M3 | Tool interface is English-only and every tool has a `title` | The description is the **only** manual the calling model gets; Chinese blocks adoption abroad outright | `test_tools_list_shape` | Active |
| M4 | The description must spell out that `unknown` ≠ low risk | A model that doesn't understand unknown treats it as low, which is the most dangerous misread | `test_tools_list_shape` | Active |
| **Deployment and operations** |
| D1 | Always `pywrangler deploy`; bare `wrangler` is banned | Bare wrangler builds fine and passes dry-run, then dies at startup in production with `ModuleNotFoundError` — it doesn't vendor workers-py | CI (`deploy.yml`) | Active |
| D2 | Deploys run in CI, not on anyone's laptop | pywrangler won't run on Windows, and the ability to ship must not be tied to one machine | CI (`deploy.yml`) | Active |
| D3 | Every deploy is followed by a smoke test against production | "Deploy succeeded, product broken" has already happened to this project once | CI (`deploy.yml`) | Active |
| D4 | MCP Registry uses **domain verification**, not a GitHub account | `io.github.<someone>/` ties the product's identity to a personal account, and a namespace can't be changed afterwards — only abandoned and redone | None | Active |
| D5 | MIT license | The landing page already claimed MIT; this makes the claim true. Plugin distribution requires open source anyway | None | Active |
| **Benchmark** |
| B1 | Labeller endpoints and engine endpoints **must not overlap** | Otherwise we measure whether the engine can restate its upstream — a high score that means nothing | Runtime (`run_benchmark.py` exits non-zero on any overlap) | Active |
| B2 | GoPlus is deliberately kept out of the engine | It is the benchmark's held-out oracle; wire it in and the benchmark is void | `test_benchmark_oracle_stays_out_of_the_engine` | Active |
| B3 | The ablation column must be reported alongside | A dead pool has liquidity ≈ 0, so calling it high on that basis is close to a tautology | None | Active |
| B4 | The `unknown` rate must be reported next to recall | A tool that answers unknown to everything has perfect recall and zero value | None | Active |
| B5 | Privileged contract functions ≠ dangerous | See L1 below | None | Active |
| B6 | Exclude `hidden_owner` and `honeypot_with_same_creator` | See L2 below | None | Active |
| B7 | Guardrail high-reputation assets; rather leave them unlabelled | See L3 below | None | Active |
| **Product and business** |
| P1 | **No referral fees, no order-flow revenue share, no paid ratings from projects** | The only asset is that nobody questions our motive when we call a token dangerous. The moment revenue correlates with calling something low, that asset is worth zero and never recovers | None | Active |
| P2 | Target trading-bot operators, not retail users | People with revenue and liability for losses are the ones who pay | None | Active |
| P3 | If we stop maintaining this, we **take it offline ourselves** | An unmaintained risk tool keeps confidently emitting wrong answers; that is a liability, not an asset | None | Active |
| P4 | Snapshot new pools every day | Public sources only list live pools (199 sampled, 0 dead); this data can't be bought and can't be backfilled | CI (`snapshot.yml`, daily schedule) | Active |

---

## Four expensive failures

Only these are worth writing at length — **every one of them looked completely normal**,
and that is exactly how this product is most likely to die.

### L1 · Treating "the contract has privileged functions" as dangerous

The first benchmark labeller marked pausable, blacklistable and mintable contracts as unsafe,
and **USDT, WBTC and LDO all came out labelled as scams**.

Those privileges are how centralised assets are designed; they are not a rug. Scoring against
that standard **forces the engine to call blue chips high risk** — a benchmark calibrated wrong
actively steers the product in the wrong direction.
**A miscalibrated benchmark is worse than no benchmark.**

→ Split out into a separate `centralized` bucket, counted neither good nor bad, used only to
watch whether the engine flags everything high indiscriminately.

### L2 · Using guilt-by-association fields as evidence

Fixing the first version wasn't enough. `hidden_owner` (false-positives on legitimate
upgradeable proxies) and `honeypot_with_same_creator` ("this deployer once deployed a flagged
contract") then flagged **AAVE, YFI, PAXG, SNT and USDT on Base** as dangerous.

The second field is the clearest case: large issuers and deployment factories ship thousands of
contracts, and scams inevitably slip in among them.
**That is guilt by association, not a property of this token.**

### L3 · Assuming one risk tool can score another

**GoPlus marks the real Status (SNT) as `is_honeypot: 1`.**
Even the fields that are supposed to be deterministic produce false positives.

→ Which means: **use a risk tool as ground truth and your ceiling is its own accuracy.**
The only real benchmark is what actually happened afterwards. When a high-reputation
asset draws a hostile flag, exclude it rather than mislabel it.

### L4 · Assuming recall could simply be measured

We tried to measure whether already-rugged tokens get caught: **199 samples, 0 dead**.

The sampler isn't bad — DexScreener search and GeckoTerminal listings both sort by
liquidity, so **dead pools drop off the list entirely**. Survivorship bias, and neither
money nor compute gets around it: that data does not exist on public endpoints at all.

→ This proves two things at once: the benchmark is **not measurable for now** on the "catches
rugs" dimension (label that honestly, don't invent numbers), and **P4's snapshot archive is the
only way out** — every day we put it off is a day of data lost for good.

---

## TODO: turn "None" into something

These rely on a human remembering them, and should become things that alarm on their own.
Ordered by value:

1. ~~**B2** (GoPlus must not reach the engine)~~ → **Done 2026-09-04**.
   `test_benchmark_oracle_stays_out_of_the_engine` scans `src/` and turns red the moment
   it shows up, and we checked in reverse that it really does fail — a guard test that
   can't fail is no guard at all.
2. **B3 / B4** (ablation column and unknown rate must be reported) → make `run_benchmark.py`
   exit non-zero when either is missing.
3. ~~**P4** (daily snapshot)~~ → **Done 2026-09-04**. `snapshot.yml` collects and commits
   automatically at 02:23 UTC daily; it warns when nothing was collected — "no new data" is a
   fault, not a quiet pass.
4. **D4 / D5** (domain namespace, MIT) → one-time decisions; no enforcement needed,
   "None" is fine here.

---

*Every decision has a matching commit in `git log`, where the full reasoning lives.
This table only answers what, why, and what is guarding it — it doesn't repeat the process.*
