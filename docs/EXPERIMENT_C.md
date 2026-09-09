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

> I built a token-risk API for AI agents and published its error rate. Including the
> parts that look bad.
>
> 4.3% false positives. 15.3% of answers are "unknown". 22.9% of legitimate centralised
> assets like USDT get flagged high. On the tokens that actually died, we rate only 10%
> as high risk.
>
> Full method, dataset and harness — run it yourself: github.com/jakegu1/vetagent

---

## Hacker News

**Title:** I published the error rate of my crypto risk API, including the bad numbers

Every token-safety scanner tells you a token is risky. None of them tells you how often
they are wrong, in a way you can check.

A few publish a number. Hypernative says 99.8% of hacks detected with under 0.001% false
positives. Forta says >99% recall. Blockaid says <0.0002% FP. (Each is that vendor's
own published figure, checked 2026-09-09.) None of them publishes a
dataset, a denominator, a definition of what counts as a positive, or a method anyone can
re-run. I went looking specifically for one and did not find it. Solsniffer's own pricing
FAQ asks "How accurate is the analysis?" and answers "battle-tested" — on a product with
a $997/month tier.

So here is mine, measured on 576 tokens across Ethereum, BSC and Base, with the harness
in the repo:

| | |
|---|---|
| False positives (healthy tokens rated high) | **4.3%** (7 of 162) |
| Answers returned as `unknown` | **15.3%** (88 of 576) |
| Tokens GoPlus tags centralised, rated high (mostly dust pools, not USDT) | **22.9%** (41 of 179) |
| Confirmed-dead tokens NOT rated low | 86.7% (26 of 30) |
| Confirmed-dead tokens rated **high** | **10.0%** (3 of 30) |

That last row is the one I would leave out if I were selling something. A tool for
spotting bad tokens rates 10% of the tokens that actually died as high risk.

**Things in the report that argue against the tool:**

- **The false-positive rate depends on who you ask.** Measured against realised market
  outcome — an oracle causally independent of any contract scanner — it is 4.3%. Measured
  against GoPlus's labels it is 7.4%, and that number is *circular*, because GoPlus is
  also this benchmark's labeller. Both are printed, with the circular one named as
  circular.
- **The label and the verdict describe the same pool only 57% of the time.** The dataset
  labels one sampled pool; the engine independently picks its own. So some share of those
  "false positives" are two answers to two different questions.
- **The adversarial cohort is 17 tokens, and 16 of them hold under a dollar.** Any recall
  figure computed on it is measuring whether we flag empty pools.
- **One feature was measured and deleted.** LP lock/burn detection fires on 58% of good
  tokens — worse than chance — so it was removed from our own coverage denominator rather
  than shipped as a checkbox.
- **58% of the dataset is Base, and the adversarial cohort is 83% Base.** Sampling reaches
  what three sources could reach, not the market — and the skew is worst exactly where the
  set is smallest.

The design decision underneath all of it: when a critical check cannot run, the answer is
`unknown`, never "low risk". That is why 15.3% of answers are a refusal. For a human
that is an annoyance; for an agent about to spend money it is the only safe default, and
it is the number a vendor optimising for a demo would bury.

Free, no signup, MIT. `https://vetagent.dev/mcp` for MCP, or `GET /assess/<address>`.
Repo: github.com/jakegu1/vetagent. The **method** is reproducible: labels are frozen in
the tracked `bench/dataset.json`, the harness is `bench/run_benchmark.py`, and it exits
non-zero if the engine's endpoints and the labelling endpoints ever intersect. The
**figures** are a snapshot measured on 2026-09-07 against live upstreams, so a re-run
today will not land on the same decimals -- expect drift, and tell me if it is large.

I would genuinely like the method attacked. The report names its own weakest points
because I would rather find them than have a user find them.

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
- only 10% of tokens that actually died are rated high

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

- **Lead with the unflattering number**, not the flattering one. 10% dead-token recall
  and 22.9% on centralised assets are the credibility, and burying them is the one move
  that makes the whole post worthless.
- **Do not claim "nobody publishes error rates."** Several do. Claim reproducibility, and
  be ready to name Hypernative, Forta and Blockaid if challenged — being the person who
  already knows the counterexamples is stronger than being corrected.
- **Do not use the GoPlus comparison.** Withdrawn, see the header.
- Expect "your dataset is 58% Base" and "n=576 is small". Both are true, both are in the
  report, and agreeing immediately is the right response. An earlier draft of this post
  said 83%, which is the adversarial cohort's Base share — 47 tokens, not 576. Do not
  quote a number for a set twelve times larger than the one it was measured on, in a post
  whose entire argument is that our numbers can be checked.
- If anyone asks whether it is safe to depend on: it is a solo project, four upstreams,
  no SLA. Say so.
