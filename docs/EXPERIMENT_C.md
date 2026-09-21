# Experiment C — the post

> Drafts for r/ethdev, Hacker News, X and the MCP community. Every number here is read
> off `bench/results.json` and guarded by `bench/publish_numbers.py`, so if the benchmark
> moves and this file does not, the build fails.
>
> **What changed from the plan.** STRATEGY §7 says the headline is *"we published our own
> miss rate — nobody in this category does."* Competitive research found the second half
> is false: Hypernative publishes 99.8% detection with <0.001% false positives, Forta
> >99% recall, Blockaid <0.0002% FP (their own figure, checked 2026-09-09; this read
> <0.002% for three days, ten times worse than they claim), ChainAware 90.1% accuracy,
> HoneypotScan 98%
> sensitivity / 97% specificity. What none of them publishes is a **method** — no
> dataset, no denominator, no definition of a positive, nothing anyone can re-run. So the
> claim is narrower and survives checking: *the numbers are reproducible, and the
> unflattering ones are published beside the flattering ones.*
>
> Do not lead with the GoPlus comparison. An earlier draft did. The −17.8pp separation it
> rested on was produced by OR-ing two label buckets this project's own code documents as
> unscoreable, and the "never fires on dead tokens" half is coupled to our own volume
> gate. It is withdrawn, and posting it would be the fastest way to lose the argument.

---

## The short version (X / Mastodon)

Posted on X from the owner's account on 2026-09-19, with his go-ahead (279 of 280 weighted
characters; checked twice against the repo before posting):

> Of 17 contracts a held-out scanner calls adversarial, my token-risk check for AI agents rates 10 high risk (58.8%). 15 of those pools hold under $1 of liquidity; contract signals alone: 17.6%.
>
> Rates and harness:
> https://dev.to/jakegu1/a-token-risk-check-for-ai-agents-that-publishes-its-own-error-rates-1iac
>
> My AI agent wrote and posted this for me.

---

## Hacker News

**Title:** Show HN: A token-risk check for AI agents that publishes its own error rates

**The number the title is actually about, first.** On 17 contracts an independent oracle
labels adversarial, the engine rates **58.8%** (10 of 17) high risk. Keep only the
contract signals and it is **17.6%**, with **35.3%** rated *low*. 15 of those 17
hold under a dollar of liquidity, so the full column is substantially measuring "is this
pool empty" rather than "is this contract hostile". Seventeen is a small cohort and I will
say so before you do; growing it is the top open item in the backlog.

That is the honest headline for a tool that claims to spot bad tokens, and it is not
flattering.

**On what other people publish, corrected.** An earlier draft of this post said nobody in
this category publishes an error rate. That is false and I got it wrong repeatedly before
a pre-publication review caught it:

- **Forta** ships labelled datasets on HuggingFace and a starter-kit README printing
  **59.4% average recall beside 88.6% average precision**, on 15,443 benign and 174
  malicious contracts with stated cross-validation (Forta's own figures, checked
  2026-09-09). That is the exact thing I claimed nobody does.
- **ChainAware** publishes a denominator — 45,904 of 50,948 — defines its positive, and
  states its own **9.9% miss rate**. (Forta's and ChainAware's figures are their own, on
  their own pages, checked 2026-09-09.)
- **Two academic groups** have already evaluated these scanners and released their data:
  arXiv 2309.04700 scores GoPlus at 60% detection on 11,943 labelled trapdoor tokens, and
  an ISSTA 2025 SoK (doi.org/10.1145/3728900) releases a labelled rug-pull dataset and
  measures which rug-pull types 13 detection tools catch.
- Among MCP servers, **Mindjack** publishes per-band sample sizes and a measured rate, and
  says its safest band still rugged about 35% of the time (its own published scorecard,
  checked 2026-09-09).

Hypernative (99.8% detection, <0.001% FP), Forta (>99% recall) and Blockaid (<0.0002% FP)
publish headline numbers with no method attached — those are each vendor's own figures,
checked 2026-09-09. So the surviving claim is narrower and I will state only that one:
**I do not know of another vendor that self-publishes its rates together with the harness
that produces them.** If you know of one, say so and I will link it.

Measured on 576 tokens across Ethereum, BSC and Base: the engine as of 2026-09-19, over
market data the harness cached mostly on 2026-09-04 to 09-07 (plus DexScreener's per-chain
listings, first asked on 2026-09-18):

| | full | contract signals only |
|---|---|---|
| Adversarial contracts rated high (n=17) | **58.8%** (10 of 17) | **17.6%** |
| Confirmed-dead tokens not rated low (n=30) | 86.7% (26 of 30) | **20.0%** |
| Confirmed-dead tokens rated high (n=30) | **10.0%** (3 of 30) | |
| Healthy tokens rated high — false positives (n=162) | **3.1%** (5 of 162) | |
| Liquid healthy tokens ($100k+) rated medium or high — false blocks (n=154) | **13.0%** (20 of 154) | |
| Answers returned as `unknown` (n=576) | **21.2%** (122 of 576) | |
| Tokens the oracle tags centralised, rated high (n=179) | **22.3%** (40 of 179) | |

**Read the second column before the first.** "Contract signals only" drops the liquidity,
market-depth, pool-age, lifecycle and impersonation checks. Where a number collapses under it, the number was substantially
detecting an empty pool. 86.7% becoming 20.0% is the clearest case, and my own report
calls the full figure "close to a tautology". I publish both because publishing only the
first would be the flattering half of a pair.

**The things in the report that argue against the tool:**

- **20 of 154 liquid, healthy tokens are refused.** The false-positive row counts only
  `high`, but an agent treats `medium` as do-not-trade too. Counted that way, on tokens
  that are alive or merely centralised and hold $100k or more, the rate is the false-block
  row above. 10 of the 20 are the upstream simulator's honeypot flag that my release rule
  does not clear: too many of the sampled holders failed to sell, too few were sampled, or
  the flag is about siphoning or blacklisted snipers rather than failed sells. That rule is
  new (decided 2026-09-18, in the engine 2026-09-19); before it this row was 30 of 154, and I chose it with these same 576
  tokens in view, so treat the drop as a fit until a fresh cohort confirms it.
- **The false-positive rate is measured where the engine can barely fail.** The healthy
  control has a median of $484,483 in the pool. Of the 146 tokens where the engine saw
  $10k or more of depth, **0** were rated high. All 5 false
  positives are among the 16 thin ones — and for four of those the engine found no
  costable pool at all, which for two became `high` rather than `unknown`. That last part
  is an engine bug, not a labelling artefact, and it is mine.
- **22.3% of centralised-tagged tokens rated high is not about USDT.** Of those 40, the 21
  with a liquidity figure are mostly abandoned pools holding cents -- 16 under a dollar,
  median $0.023 -- caught by the liquidity checks. Owner
  powers drive none of them — the engine is forbidden from scoring dormant capabilities.
  USDT itself comes back `low`. An earlier draft explained this row with a mechanism my
  own code forbids.
- **The two false-positive rates are not independent in the way I implied.** Against
  realised market outcome it is 3.1%; against the held-out contract oracle it is 6.0%.
  I previously called the second "circular". That was the wrong word: the oracle is held
  out and the build fails if the engine ever reads it. What is true is subtler and worse
  for me — both it and one of my upstreams simulate sells, so the correlation pushes that
  6.0% **down**, not up. At this sample size my own report calls the two indistinguishable.
- **The label and the verdict describe the same pool only 55% of the time.**
- **`unknown` is a design choice and also a dependency.** Fail-closed is real: a check that
  cannot run must never read as low risk. But 94 of the 122 unknowns are one free upstream
  either not having indexed the token or its simulation reverting, on tokens with a median
  of $120k in the pool. That is my supply chain, not the market's ambiguity. Another 25
  are tokens whose every pool is priced in an asset no independent market prices: the
  engine declines to believe a depth nobody can check.
- **Until 2026-09-15 it could be fooled for about two dollars.** An adversarial audit found
  three ways. A pool priced in a token its creator minted could claim any depth and buy a
  `low`. The same arithmetic let a $2.21 pool outrank the real Wormhole WETH on Solana,
  which the engine then called an impostor, in production. And twenty self-sells could
  overrule a honeypot verdict, because the check that counts distinct sellers never ran
  on the data source most tokens resolve through. All three are fixed, each with a test
  that failed first, and the table above is measured after the fixes. They cost
  something: 13 healthy tokens moved from low to medium on thinner verifiable depth, and
  17 more of the 576 answers became `unknown` -- and the same hole had a second door, the
  fallback data source, which I found and closed a day later.
- **Until 2026-09-18 the benchmark's USDT row was a copy of USDT.** DexScreener's token
  answer stops at 30 pairs, and for USDT's Ethereum address all 30 were PulseChain copies,
  priced at a thousandth of a cent. The engine judged a copy, and "USDT is rated low" rested
  on it; asked with no chain, the live service answered `medium`. A reviewer found it the day
  before this post. The engine now reads the token's own chain before it will judge a
  copy, and the row is USDT on Ethereum.
- **Zero Solana rows in the benchmark.** The product answers Solana, and the discovery tool
  defaults to it. The advertised flow — discover, then assess — defaults to the one chain
  with no measured error rate.
- **58% of the dataset is Base, and the 47 dead or adversarial tokens are 83% Base** (11 of
  the 17 adversarial ones). The skew is worst in the small cohorts that matter most.
- **One feature was measured and deleted.** LP lock/burn fired on 22 of 38 good tokens in a
  one-off check — worse than chance — so it was removed from the coverage denominator
  rather than shipped. That check was a spot measurement, not a benchmark run.

Free, no signup, MIT. `https://vetagent.dev/mcp` for MCP, or `GET /assess/<address>`.

**On reproducing it.** Labels are frozen in the tracked `bench/dataset.json`, the harness
is `bench/run_benchmark.py`, and it exits non-zero if the engine's endpoints and the
labelling endpoints ever intersect. Until 2026-09-09 that command did not work on a fresh
clone — it evaluated for twenty minutes and exited "Benchmark void" because a required
file was gitignored. That is fixed. The **figures** are the engine as of 2026-09-19, scored over upstream answers the
harness cached mostly on 2026-09-04 to 09-07 (it keeps every successful fetch). A fresh
clone re-fetches everything, so a re-run will not land on the same numbers. A reviewer
did exactly that on 2026-09-17 (UTC), cold, in 44 minutes: 60 of the 576 verdicts moved, and
replaying both runs' saved upstream answers through both engine versions showed that none
of the 60 came from code -- dead pools that one data source stopped listing, one-day
trading-activity thresholds, pools that moved, and a sell simulator that answered
differently. The reviewer registered tolerances while that run was still going, before it
had printed anything, and one published row fell outside them: false blocks went from 30
of 154 to 36 of 149, against a tolerance of 25 to 35. The centralised row had no tolerance
and moved further, from 40 of 179 rated high to 26. The registration says a miss is
printed here; it was missing when this went out on 2026-09-19 and was added the same day.
That run predates the rule that brought false blocks to 20, and the new rule has not had a
cold re-run yet. The registration and the run's output are in `bench/drift/2026-09-17/`.
Tell me if your drift is larger.

What "independent" does and does not mean here: the labels use none of the endpoints the
engine reads, and the build enforces that. The outcome oracle is independent of every
contract scanner. It is not independent of the market data the engine also reads — same
provider, different time slice.

I would rather have the method attacked than have a user find the hole. The weakest points
are listed above because I would rather be the one who found them.

---

## r/ethdev

For the owner to post himself (the browser tool cannot reach Reddit). Checked twice against
the repo on 2026-09-19. Read the subreddit's rules on AI-written and project posts first,
and paste into the Markdown editor.

**Title:** I benchmarked my own open-source pre-trade token-risk check: 58.8% of adversarial contracts rated high, 17.6% on contract signals alone (n=17). The harness is public; please attack the method

> *Disclosure: this post was written by the AI coding agent (Claude) that builds VetAgent with me; I'm posting it myself.*
>
> VetAgent is a free, MIT-licensed check an AI agent calls before it buys a token: sell simulation, taxes, liquidity depth, pair age and same-ticker impersonation, rolled into `low` / `medium` / `high` / `unknown`.
>
> **The number that matters, first.** On 17 contracts a held-out oracle labels adversarial, it rates 58.8% (10 of 17) high. Keep only contract signals (drop every market-side check: liquidity, pool age, lifecycle, impersonation and the rest) and it is 17.6% high, with 35.3% rated *low*. 15 of those 17 hold under a dollar of liquidity, so the full column is substantially detecting an empty pool, not a hostile contract. 11 of the 17 are on Base. n=17 is small; growing it is an open backlog item, held until after this post because a rebuild moves every published number.
>
> **Method**
>
> - 576 tokens on Ethereum, BSC and Base (58% Base), labels frozen in `bench/dataset.json`.
> - Two label sources whose endpoints the engine never calls (the harness exits non-zero if they intersect): GoPlus token-security flags for adversarial, GeckoTerminal price and volume history for dead and healthy. Neither is fully independent: GoPlus and one of the engine's upstreams both simulate sells, and the engine reads the same provider's current market data.
> - Re-run it with `python bench/run_benchmark.py` (about 45 minutes cold). Published figures are the engine as of 2026-09-19 over upstream answers cached mostly 09-04 to 09-07. That cache is not in the repo, so a fresh clone re-fetches and rows move by whole tokens. A reviewer's cold re-run on 2026-09-17 (UTC), with tolerances registered while it ran, changed 60 of 576 verdicts (none from code): false blocks went from 30 of 154 to 36 of 149, outside its 25-35 tolerance, and the centralised row from 40 of 179 rated high to 26. That run predates the rule below. The registration and its output are in `bench/drift/2026-09-17/`.
>
> **Numbers that argue against it**
>
> - Of 30 tokens that actually died, 10.0% (3 of 30) are rated high. 86.7% are not rated low, but that falls to 20.0% on contract signals only: mostly market-side checks seeing an empty pool.
> - False positives: 3.1% (5 of 162) against market outcome, 6.0% against the held-out contract oracle. The healthy control's median pool is $484,483, and all 5 are among the 16 thin (under $10k) or unpriced tokens. 4 of those had no pool the engine could cost, and for 2 of them the missing pool alone produced `high` where `unknown` was due -- I think that is an engine bug, and it is open.
> - 13.0% (20 of 154) of liquid ($100k+) tokens that are alive or merely centralised come back `medium` or `high`, which an unattended agent with no one to ask will likely refuse; another 21 come back `unknown`. A rule decided on 2026-09-18 and in the engine on 09-19 moved this from 30 to 20; I chose it with these same 576 tokens in view, so treat the drop as a fit until a fresh cohort confirms it.
> - 21.2% (122 of 576) of benchmark answers are `unknown` (fail-closed); the live service returned 49.6% of 445 answers from 2026-09-12 to 09-19, a figure that includes our own monitoring and demo traffic. 94 of the 122 benchmark unknowns are one free upstream not indexing the token or its simulation reverting.
> - Zero Solana rows, though the product answers Solana.
>
> What I'd most like attacked: is the oracle independent enough, can n=17 (or the 30-token dead cohort) support any claim, and is "contract signals only" the right ablation?
>
> Full write-up: https://dev.to/jakegu1/a-token-risk-check-for-ai-agents-that-publishes-its-own-error-rates-1iac
>
> Repo: https://github.com/jakegu1/vetagent

---

## MCP community / Discord

For the owner to post himself in an MCP community server's showcase channel (1,941
characters of Discord's 2,000). Checked twice against the repo on 2026-09-19. Read the
channel's rules on crypto and AI-written posts first.

> *Disclosure: written by the AI agent (Claude) that builds VetAgent with me.*
>
> **VetAgent**: a pre-trade token-risk check for agents, as a remote MCP server.
> `https://vetagent.dev/mcp`: free, no auth, no signup, MIT
> Tools: `assess_token_risk`, `get_token_liquidity`, `find_new_hot_pools`
>
> **Fail-closed:** if a critical check can't run, the answer is never `low` or `medium`: it is `unknown` (or `high` if what did run already condemns it), with `evidence.data_gaps` naming what was missing and, on `unknown`, `next_action` saying `retry` or `abstain`.
>
> **Published rates, unflattering first** (576 tokens on Ethereum/BSC/Base; engine as of 2026-09-19, market data mostly cached 09-04 to 09-07):
> - Contracts a held-out third-party scanner labels adversarial, rated high: **58.8%** (10 of 17); contract signals only: **17.6%**. 15 of the 17 hold under $1 of liquidity, and 7 of the 10 highs vanish on contract signals alone.
> - Confirmed-dead tokens rated high: **10.0%** (3 of 30).
> - Liquid ($100k+) tokens that are alive or merely centralised, rated medium or high: **13.0%** (20 of 154), plus 21 `unknown`. A rule shipped 2026-09-19 took it from 30 to 20; chosen with these same tokens in view, so unconfirmed until fresh tokens test it.
> - `unknown`: **21.2%** in the benchmark; 49.6% live (09-12 to 09-19, including our own monitoring and demo traffic). 94 of the 122 benchmark unknowns trace to one free upstream.
> - Healthy tokens rated high: **3.1%** (5 of 162) against market outcome, all 5 among the 16 where it saw under $10k; 6.0% against the held-out scanner.
> - Solana is served but has 0 benchmark rows, and `find_new_hot_pools` defaults to it.
>
> A cold re-run on 09-17 (before the new rule) moved 60 of 576 verdicts and put false blocks at 36 of 149, outside the 25-35 band registered while it ran.
> https://dev.to/jakegu1/a-token-risk-check-for-ai-agents-that-publishes-its-own-error-rates-1iac
> <https://github.com/jakegu1/vetagent>

---

## Notes for whoever posts this

- **Lead with the number the title promises.** That is recall on the adversarial cohort —
  58.8% full, 17.6% ablated, n=17 — and an earlier draft did not contain it at all, which
  a hostile pre-publication review called the sharpest single omission. Leading with a
  different unflattering number is not the same as leading with the relevant one.
- **Do not claim "nobody publishes error rates."** Several do. Claim reproducibility, and
  be ready to name Hypernative, Forta and Blockaid if challenged — being the person who
  already knows the counterexamples is stronger than being corrected.
- **Do not use the GoPlus comparison.** Withdrawn, see the header.
- **Expect the attack on n=17 and n=30, not on n=576.** These notes used to rehearse a
  defence of 576, which nobody will attack. The operative sample sizes are the dead cohort
  (30) and the adversarial cohort (17), small enough to be the first thing a careful
  reader questions. The post raises both before a reader can.
- Expect "your dataset is 58% Base". True, in the report, and agreeing immediately is the
  right response. An earlier draft of this post
  said 83%, which is the Base share of the 47 dead or adversarial tokens, not of all 576. Do not
  quote a number for a set twelve times larger than the one it was measured on, in a post
  whose entire argument is that our numbers can be checked.
- If anyone asks whether it is safe to depend on: it is a solo project, five upstream data sources,
  no SLA. Say so.
