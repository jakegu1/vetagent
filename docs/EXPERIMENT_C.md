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

> I built a token-risk API for AI agents and published its error rate, including the
> number that makes it look worst.
>
> On contracts an independent oracle calls adversarial, we rate 64.7% high. Strip the
> liquidity signals and it is 17.6%. The cohort is 17 tokens and 15 of them hold under a
> dollar, so read both columns.
>
> 4.3% false positives, on a control with a median of $636,653 in the pool. 15.3% of
> answers are a refusal.
>
> Method, dataset and harness — run it yourself: github.com/jakegu1/vetagent

---

## Hacker News

**Title:** I published my crypto risk API's error rate, including the number that makes it look worst

**The number the title is actually about, first.** On 17 contracts an independent oracle
labels adversarial, the engine rates **64.7%** (11 of 17) high risk. Strip out the
liquidity signals and it is **17.6%**, with **35.3%** rated *low*. Fifteen of those 17
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
- **Two academic groups** have already benchmarked these scanners on released datasets:
  arXiv 2309.04700 scores GoPlus at 60% detection on 11,943 labelled trapdoor tokens, and
  the ISSTA 2025 SoK (arXiv 2403.16082) puts 14 scanners against a public 2,360-instance
  set.
- Among MCP servers, **Mindjack** publishes per-band sample sizes and a measured rate, and
  says its safest band still rugged about 35% of the time (its own published scorecard,
  checked 2026-09-09).

Hypernative (99.8% detection, <0.001% FP), Forta (>99% recall) and Blockaid (<0.0002% FP)
publish headline numbers with no method attached — those are each vendor's own figures,
checked 2026-09-09. So the surviving claim is narrower and I will state only that one:
**I do not know of another vendor that self-publishes its rates together with the harness
that produces them.** If you know of one, say so and I will link it.

Measured on 576 tokens across Ethereum, BSC and Base, 2026-09-07:

| | full | signals stripped |
|---|---|---|
| Adversarial contracts rated high (n=17) | **64.7%** (11 of 17) | **17.6%** |
| Confirmed-dead tokens not rated low (n=30) | 86.7% (26 of 30) | **20.0%** |
| Confirmed-dead tokens rated high (n=30) | **10.0%** (3 of 30) | |
| Healthy tokens rated high — false positives (n=162) | **4.3%** (7 of 162) | |
| Answers returned as `unknown` (n=576) | **15.3%** (88 of 576) | |
| Tokens the oracle tags centralised, rated high (n=179) | **22.9%** (41 of 179) | |

**Read the second column before the first.** "Signals stripped" removes the liquidity and
market-depth checks. Where a number collapses under it, the number was substantially
detecting an empty pool. 86.7% becoming 20.0% is the clearest case, and my own report
calls the full figure "close to a tautology". I publish both because publishing only the
first would be the flattering half of a pair.

**The things in the report that argue against the tool:**

- **The false-positive rate is measured where the engine can barely fail.** The healthy
  control has a median of $636,653 in the pool. Of the 150 tokens where the engine saw
  $10k or more of depth, **0** were rated high. All 7 false positives are among the 12
  thin ones — and for four of those the engine found no costable pool at all, which for
  two became `high` rather than `unknown`. That last part is an engine bug, not a
  labelling artefact, and it is mine.
- **22.9% of centralised-tagged tokens rated high is not about USDT.** Almost all 41 are
  abandoned pools holding cents, median $0.023, caught by the liquidity checks. Owner
  powers drive none of them — the engine is forbidden from scoring dormant capabilities.
  USDT itself comes back `low`. An earlier draft explained this row with a mechanism my
  own code forbids.
- **The two false-positive rates are not independent in the way I implied.** Against
  realised market outcome it is 4.3%; against the held-out contract oracle it is 7.4%.
  I previously called the second "circular". That was the wrong word: the oracle is held
  out and the build fails if the engine ever reads it. What is true is subtler and worse
  for me — both it and one of my upstreams simulate sells, so the correlation pushes that
  7.4% **down**, not up. At this sample size my own report calls the two indistinguishable.
- **The label and the verdict describe the same pool only 57% of the time.**
- **`unknown` is a design choice and also a dependency.** Fail-closed is real: a check that
  cannot run must never read as low risk. But 85 of the 88 unknowns are one free upstream
  either not having indexed the token or its simulation reverting, on tokens with a median
  of $225k in the pool. That is my supply chain, not the market's ambiguity.
- **Zero Solana rows in the benchmark.** The product answers Solana, and the discovery tool
  defaults to it. The advertised flow — discover, then assess — defaults to the one chain
  with no measured error rate.
- **58% of the dataset is Base, and the adversarial cohort is 83% Base.** The skew is worst
  exactly where the set is smallest.
- **One feature was measured and deleted.** LP lock/burn fired on 22 of 38 good tokens in a
  one-off check — worse than chance — so it was removed from the coverage denominator
  rather than shipped. That check was a spot measurement, not a benchmark run.

Free, no signup, MIT. `https://vetagent.dev/mcp` for MCP, or `GET /assess/<address>`.

**On reproducing it.** Labels are frozen in the tracked `bench/dataset.json`, the harness
is `bench/run_benchmark.py`, and it exits non-zero if the engine's endpoints and the
labelling endpoints ever intersect. Until 2026-09-09 that command did not work on a fresh
clone — it evaluated for twenty minutes and exited "Benchmark void" because a required
file was gitignored. That is fixed. The **figures** are a snapshot against live upstreams
on 2026-09-07, so a re-run today will not land on the same decimals; tell me if the drift
is large.

What "independent" does and does not mean here: the labels use none of the endpoints the
engine reads, and the build enforces that. The outcome oracle is independent of every
contract scanner. It is not independent of the market data the engine also reads — same
provider, different time slice.

I would rather have the method attacked than have a user find the hole. The weakest points
are listed above because I would rather be the one who found them.

---

## r/ethdev

**Title:** Published the false-positive rate for my token-risk checker — 4.3%, plus the
numbers that make it look bad

Short version: I built a pre-trade token safety check for AI agents (MCP server + plain
HTTP), and I published the benchmark instead of a marketing number.

576 tokens on Ethereum, BSC and Base:

- 4.3% false positives on healthy tokens
- 15.3% of answers are `unknown` — a critical check could not run, so it refuses rather
  than guessing
- 22.9% of the tokens GoPlus tags as centralised are rated high. Almost all of those
  are abandoned pools holding cents -- 17 of the 22 with a liquidity figure are under a
  dollar, median $0.023 -- and the drivers are liquidity, drained and honeypot checks,
  never owner powers, which `_owner_power_signal` is forbidden from scoring. USDT itself
  is rated low on Base and BSC and medium on Ethereum; WBTC is medium
- only 10% of tokens that actually died are rated high, and the 86.7% "not rated low"
  beside it falls to 20.0% once the liquidity signals are stripped — that row was
  largely detecting an empty pool rather than a bad contract

The last two are the honest failure modes. Centralised stablecoins really do hold the
powers we flag, and "this project died" is a market outcome while the engine scores a
safety property — they overlap and are not the same thing.

What it actually checks: sell simulation (can you get out), buy/sell tax, liquidity
depth, pair age, same-ticker impersonation, and owner powers read from bytecode. What it
deliberately does not do: score dormant owner powers, because measured against an
independent oracle the scan finds 37% of the contracts that can pause transfers, 26% of
those that can blacklist and 8% of those that can change the tax. Scoring a check that
misses most of what it looks for is how false positives get in.

The method is reproducible and the numbers are a dated snapshot (2026-09-07, live
upstreams), not a constant — `python bench/run_benchmark.py` re-measures rather than
replays, and the disagreements are listed by token so you can check them one at a time.

github.com/jakegu1/vetagent

---

## MCP community / Discord

VetAgent is an MCP server for pre-trade token risk — `https://vetagent.dev/mcp`, free, no
auth, no signup. Three tools: `assess_token_risk`, `get_token_liquidity`,
`find_new_hot_pools`.

The thing that might interest this group is not the tool, it is the benchmark. It
publishes its own false-positive rate (4.3%), unknown rate (15.3%) and the cases where it
disagrees with the labelling oracle, with the harness in the repo so anyone can re-run
it. I could not find another server in this category that publishes a reproducible error
rate, and I looked.

One design note relevant to anyone building agent-facing tools: when a check cannot run,
it returns `unknown` and says so in the recommendation text, rather than defaulting to
"low risk". 15.3% of answers are that refusal. An agent reading a confident wrong answer
is worse than an agent reading "I could not tell", and most scanners in this space return
a score no matter what.

github.com/jakegu1/vetagent

---

## Notes for whoever posts this

- **Lead with the number the title promises.** That is recall on the adversarial cohort —
  64.7% full, 17.6% ablated, n=17 — and an earlier draft did not contain it at all, which
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
  said 83%, which is the adversarial cohort's Base share — 47 tokens, not 576. Do not
  quote a number for a set twelve times larger than the one it was measured on, in a post
  whose entire argument is that our numbers can be checked.
- If anyone asks whether it is safe to depend on: it is a solo project, four upstreams,
  no SLA. Say so.
