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

> **Consolidation is overdue.** This table is at 54 rows against a stated ceiling of
> 40, as of 2026-09-05. The retirement rule above says every test-enforced entry that
> has never failed should collapse into one summary line at that point, because the
> test is the documentation. Recorded here rather than quietly ignored: the rule is
> either worth following or worth deleting, and leaving it silently breached is how a
> document stops being trusted.

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
| P5 | A discovery that suggests a different product gets **parked**, not adopted, until the gate it would preempt resolves | On 2026-09-04 one afternoon of research undermined distribution, SEO and the differentiator, then proposed repositioning — 14 days before the gate asking whether anyone uses this had come due. Measured facts constrain *how* to finish; they are not a licence to start something else | `test_gates_get_reviewed` + `docs/OPPORTUNITIES.md` | Active |
| P6 | Fixing defects is never a pivot | A tool returning wrong answers is not a signal to go do something else. It is the work | None | Active |
| E15 | A `chain_hint` we cannot match is **less** information than no hint, never more | It was lowercased and compared to DexScreener's chainId with no normalisation, so "eth" -- the id our own `_GT_NETWORK` table uses -- matched nothing, and the code fell back to every pair and took max liquidity with no canonical ranking. `chain_hint="eth"` priced USDC at \$0.000967 from a fork chain: P0-C reopened by the change that closed it, hidden because the fixture only ever passed "ethereum" | `test_a_chain_hint_we_cannot_match_is_less_information_not_more` | Active |
| E16 | A chain our simulator does not cover is **our** gap, phrased as ours | honeypot.is 404s for every Arbitrum and Polygon token. Reading that as evidence made a healthy Arbitrum token "unusual for anything with a real market", and an unindexed one **high** on a premise that is false where no simulator has ever run | `test_a_chain_the_simulator_does_not_cover_is_our_gap` | Active |
| E17 | Silencing a detection costs more than raising one | The honeypot override cleared at \$5k liquidity and 20 sells: a whitelist honeypot's own wallets buy that for gas. Now \$25k standing and 100 sells at 30%, far above the bar the same evidence needs merely to be *reported* -- reporting beside an open question is free, switching off an alarm is not | `test_overturning_a_honeypot_verdict_is_expensive` | Active |
| E18 | The verdict must match the sentence | "There is nothing to sell into at any price" scored 60 and came out `medium`, because the test asserted only "not low". Assertions that pin a severity literal stop noticing when the behaviour stops making sense; assert the property | `test_every_pool_empty_is_a_finding_not_a_gap` | Active |
| B11 | An oracle's flag counts only where the oracle could have been wrong | 27 of 28 tokens labelled `unsafe` had under \$1,000 of liquidity, and an independent simulator called 19 of them safe. The flag fires when the oracle's own sell simulation fails, which it does against any empty pool -- so the cohort was "drained pool" wearing the label "dangerous contract", and recall on it measured our liquidity checks. E11 inside the oracle | `HONEYPOT_TESTABLE_VOL_7D` in `labels.py` | Active |
| B12 | Published label definitions are **generated** from the code's constants | The report said dead needed a 90% drawdown (code: 80%), alive \$50k weekly volume (code: \$25k), safe 100 holders (code: 500). A benchmark whose stated method differs from its actual method is not a benchmark | definitions rendered from `labels.py` constants | Active |
| B13 | What the product publishes about its accuracy is generated and guarded | Site, README and `/llms.txt` claimed 199 tokens and 11.3% false positives while the benchmark said 558 and 3.5% -- in a product whose entire pitch is that its numbers can be checked | `test_published_numbers` + `bench/publish_numbers.py`, both in CI | Active |
| P7 | A decision gate must carry a **written conclusion** once it falls due | The 2026-09-18 gate was enforced by nothing; STRATEGY said skipping one silently was not allowed and no code agreed. The counting rule also passed on self-traffic -- one editor session plus one curl was two "clients" | `test_strategy_gates_are_answered_when_they_fall_due`, verified to go red on an overdue gate | Active |
| P8 | `low` means the exit was open when we looked, not that it cannot be closed | A contract can hold switchable tax, pausable transfers, a blacklist and removable liquidity and keep every one dormant while we check. The copy promised "check whether the token is a scam"; we deliver "check whether you could get back out" | wording in `_finalize` and STRATEGY §0 | Active |
| E19 | A finding may be **disclosed** without being **scored** | Owner powers (pause, blacklist, mutable tax) are what the audit's adversarial `low` token relies on, and a caller is entitled to know a contract holds them. But measured over 417 contracts they do not separate bad from good at the cohort size available -- and mintable runs the wrong way. Scoring an unvalidated threshold is how the false positives got in; saying nothing hides a fact the caller needs. So it is reported and the verdict does not move | `test_owner_powers` asserts the verdict is identical with and without the signal | Active |
| E20 | Selectors are **computed**, and a test recomputes them | A wrong 4-byte constant never matches, so the contract looks powerless and the tool reports that as reassurance. hashlib's `sha3_256` is not Keccak-256 -- one padding byte apart, and it would produce four plausible bytes matching nothing on any chain | `bench/keccak.py` + `test_owner_power_selectors_are_real` | Active |
| P4 | Snapshot new pools every day | Public sources only list live pools (199 sampled, 0 dead). **Rationale corrected 2026-09-05**: "can't be backfilled" was wrong for *discovery* and right for *state* -- see R1 | CI (`snapshot.yml`, daily schedule) | Active |
| R1 | Discovery is backfillable from chain history; contemporaneous state is not | P4 said this data "can't be backfilled". Half wrong: a Swap log names every pool that traded on any past day, so *which tokens existed* is recoverable for any date -- ten minutes of Base from 120 days ago yields 770 pools that provably traded, in about a second. What is not recoverable is what a pool *looked like* that day (price, reserves, buyer counts), which is the evidence for anything time-sensitive. So the daily job stays, and backfill supplies volume rather than replacing it | `bench/backfill.py` | Active |
| R2 | Harvest pools that **traded**, never contracts that were **deployed** | A factory log fires for every deployment and almost nothing ever trades. One historical day of Base creations: 231 contracts, GeckoTerminal knew 94, 13 produced any label, 0 were bad -- 6 of 197 ever cleared \$50k of weekly volume. A Swap log cannot fire for a token nobody traded, which is the filter GeckoTerminal's feed was applying for us | `bench/backfill.py` (`--mode traded` is the default) | Active |
| R3 | An unanswered upstream call must never become a fact about the chain | A rate-limited JSON-RPC call arrives *inside a 200 OK*, as a per-item `-32016` error. Dropping entries with no `result` turned "the node would not answer" into "this pool has no tokens", and a day whose first sampled window held 10,522 swaps was recorded as 0 pools traded. The same shape as `isHoneypot`, `pairCreatedAt` and the empty-set assertion: a refusal read as an absence | `rpc_batch` retries and prints what never answered | Active |
| R4 | An empty harvest is a failure, not a result | A broken refactor produced zero rows, the zero rows were written, and every later run skipped that day as "already harvested" -- the bug preserved itself. No day on these chains has ever had zero trades | `bench/backfill.py` writes nothing on an empty day | Active |
| B8 | Each sampling source gets a **quota**, never a place in a queue | Collecting sources in order and truncating to `--limit` is not a sampling design; it is whichever source runs first winning the set. At a 60% backfill share the truncation deleted every head-page token -- the healthy control group the false-positive rate is measured against -- and no number in the report would have moved | `SOURCE_QUOTA` + `_compose` in `build_dataset.py` | Active |
| B9 | The access log records **one run**, not all history | It unioned each run into the last, so "endpoints hit on this run" meant "ever hit", and the disjointness assertion tested against history. It then refused a valid run over an overlap that no longer existed. A guard that fires on the past teaches people to work around it | `persist_access_log` replaces | Active |
| B10 | The ablated column obeys fail-closed too | `ablate()` passed an empty gap list to `_finalize`, switching the rule off for the entire published column, so the benchmark graded itself under laxer rules than the engine | `ablate()` forwards sellability gaps | Active |
| E11 | An **observed** absence is a finding; an **unobserved** dimension is a gap. Neither may impersonate the other | Both directions cost us in one day. Filing "every pool is empty" as a gap made the engine answer `unknown` for the loudest thing it can find. Then treating an *uncosted* pool as an empty one made it announce "there is nothing to sell into at any price" about a token with 174 buys and 104 sells -- and delete the gap, so confidence went up | `test_unpriced_pools_are_not_empty_pools`, `_reported_liquidity` | Active |
| E12 | A token's home chain is decided **before** liquidity is | `_valid` drops empty pools, so ranking chains afterwards meant that once a token's real pools were drained, forks that inherited its address became the best tier by default. The USDC \$0.00097 mispricing, reachable again through exactly the drained tokens we had just added a check for | `_pick_best`, `test_liquidity_prefers_canonical_chain` | Active |
| E13 | Impersonation is judged **within one chain only** | Cross-chain rivals arrive with liquidity nobody here can verify and an attacker can manufacture: canonical ZORA was called "almost certainly not the token you meant" over a Solana pool claiming \$1,015,244,216. And a multichain token has a different address per chain, so its own deployments looked like impostors. Fired warn-or-critical on 81 of 207 tokens before the fix; `high|medium` on clean tokens fell from 57.4% to 34.9% after | `test_impersonation_only_compares_within_one_chain` | Active |
| E14 | Changes to the scoring path get an **adversarial** review before they are trusted | Two critical defects shipped in a commit whose 104 tests were green, and both were caught by review agents told to refute rather than confirm. The measured "improvement" I reported had been inflating `medium` across a third of the clean tokens, because I had measured only the `high` rate | None -- this is a working practice, not a test | Active |

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
