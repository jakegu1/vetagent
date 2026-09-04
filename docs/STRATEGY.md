# VetAgent Operating Plan (STRATEGY.md)

> Version v1 · 2026-09-04 · Owner: Claude (accountable owner, appointed by Jake)
> This file is the plan we execute against. Every decision gate must be revisited and
> written up when it comes due. No silent drift.
> It records **judgements** and **bets**, not wishes. A judgement that turns out wrong
> gets written into "Overturned assumptions".
> This file is public on purpose. The same transparency that makes us publish our error
> rates applies to how we run the business.

---

## 0. For people who don't follow crypto: what this actually is

In one line: **before an AI buys a token for you, check whether the token is a scam.**

Three things you need to know:

1. **Anyone can launch a new token in 10 minutes**, with no permission and no audit.
   Thousands appear every day. Most are worthless, and a sizeable share are carefully
   built scams.
2. **The most common scam is the honeypot**: the contract lets you buy but not sell.
   Your balance looks fine on screen; the sell transaction fails. By the time you
   notice, the money is already unrecoverable.
3. **AI agents are starting to trade on their own.** A person hesitates, searches,
   asks a friend. An agent doesn't — it reads an address and calls buy.
   **There is no brake in that path.**

VetAgent is that brake. The agent calls it once before acting and gets a
`low/medium/high/unknown` verdict plus the specific reasons behind it.

**Why now**: agents trading on their own only became real recently. Before that, risk
checks were web pages for humans to read. What's needed now is an interface machines
call, and one an AI can discover and use directly (that is what the MCP protocol is for).

---

## 1. What we are actually selling

Not data. The upstream sources (DexScreener / honeypot.is / GoPlus / RugCheck) are
mostly free and public.

We sell three things, in order of importance:

| What we sell | What the customer is actually buying |
|---|---|
| **Judgement** | Not "here are 40 fields" but "should you touch this, and why". Four sources that contradict each other, collapsed into one actionable verdict |
| **Reliability** | Upstreams go down, rename fields, rate-limit. The customer is buying "I never have to deal with that" |
| **Credibility** | We publish our own recall and false-positive rates. **Nobody else in this category does** |

> Something I got wrong, on the record: I used to think "the underlying data is free and
> public, so there is no moat". That filter kills BuiltWith (read the page source, it's
> free), ScreenshotOne (Puppeteer is free and open source) and Ahrefs (Google Search
> Console is free and more authoritative) — all of them healthy businesses.
> **People pay not to have to do it themselves, not for exclusive data.** This has been
> demoted from a reason to kill the project to a positioning guide.

---

## 2. Who uses it

The "AI agent" is not the user. The user is **the person deploying the agent**.
Four types, ordered by willingness to pay:

| # | User | Pain | Willingness to pay |
|---|---|---|---|
| 1 | **Telegram / Discord trading-bot operators** | When their users get rugged, those users flame them, demand refunds, and leave. They carry the reputation damage and the payouts | **High**. They have revenue, liability, and direct losses |
| 2 | **Wallets / DEX front-ends** | Need a safety layer, don't want to build and maintain one | **High**, but long procurement cycles |
| 3 | **Developers and small teams building their own trading agents** | Don't want to write risk logic, and don't want to babysit four upstreams | Medium |
| 4 | **Individuals checking a token through Claude/ChatGPT** | Want to ask before they buy | Low. This is **distribution and word of mouth**, not revenue |

**Go after 1 and 3.** Type 4 stays free: it is where traffic and trust come from,
not revenue.

Type 1 is worth spelling out. There are thousands of these bots (Maestro, Banana Gun
and Unibot at the head, with a very long tail), they compete with each other, and
"we block scams for you" is a differentiator they can put in their own marketing.
**For a one-person product, 20 customers like that is a business.**

---

## 3. Where we actually are (the starting line, unvarnished)

- ✅ Engine runs, MCP endpoint live, landing page live
- ✅ 153 tests + CI + upstream contract tests (this one is the key: honeypot detection
     once **failed silently** — it read a field the upstream doesn't have and returned
     "safe" for every token. Without contract tests you never catch that)
- ✅ Accuracy benchmark v1 built; labelling sources and engine endpoints are
     **asserted disjoint at runtime**
- ⬜ Users: **0**
- ⬜ Revenue: **$0**
- ⬜ Not registered in any registry or directory
- ⬜ Landing page is Chinese-only
- ⬜ Historical snapshot collection not started ← **most urgent, see §4.1**

Cost floor: Cloudflare Workers $5/month + domain ~$12/year ≈ **$6/month**.
Break-even = **1 customer at $19/month**.

---

## 4. The moat: four layers, ordered by durability

### 4.1 Longitudinal outcome data (strongest, compounds, **time-sensitive**)

Snapshot the state of every new pool daily, and keep recording what happened to it.

Six months from now we will hold **data nobody can buy and nobody can backfill**:
what a pool looks like in the 7 days before it rugs. It can't be bought because it has
to be **collected live** — upstream APIs give you the current snapshot only, never the
historical state.

This is what moves VetAgent from restating other people's judgement to having its own.
It is also the only thing here where **a competitor who decides to build it today still
has to wait six months to catch up**.

> **Every day we delay is a day of data lost permanently.** It is the only item in this
> plan that can never be made up later.
> Cost: one cron job plus R2 storage, about half a day's work, under $1/month.

#### This isn't speculation — measurement forced the conclusion

Building benchmark v1, I wanted to measure directly whether the engine catches tokens
that have already rugged. **I could not collect a single dead sample.** Across 199
tokens, `dead = 0`.

The sampling wasn't badly written. **Every public data source lists only pools that are
still alive**: DexScreener search and GeckoTerminal's pool listings both rank by
liquidity and volume, so dead pools simply fall off the list. This is textbook
survivorship bias, and **no amount of money or compute fixes it — that data does not
exist on any public interface.**

So:

- "Are there observable warning signs before a rug" is a question that
  **no off-the-shelf data anywhere can answer today**
- The only way to get it: **record the pool while it is still alive, then come back
  later for the outcome**
- That takes time, and time **cannot be bought, accelerated, or backfilled**

Two things follow. Our accuracy benchmark is **currently unmeasurable** on the
"catches rugs" dimension (see §9 metrics, where it is honestly marked as not
measurable). And — **the snapshot archive isn't a nice-to-have; it is the only part of
this product that cannot be copied.** Any competitor deciding to build it today still
waits 6 months for the same thing.

### 4.2 Published accuracy (medium strength, but the only differentiator we can cash today)

Nobody in this category publishes their own recall and false-positive rates. We publish
both, and the methodology with them (independent labelling + ablation + runtime
disjointness assertion).

For a B2B customer this is the **only citable material** they have to justify the choice
to their boss. It can be copied — but whoever goes first keeps the authority of having
set the standard.

### 4.3 Distribution placement (weak, but pays off fastest)

Be present everywhere an agent can discover tools: the official MCP registry,
awesome-mcp-servers, Smithery, mcp.so, PulseMCP, Glama, the Claude connector directory.
One-time effort, long-term acquisition. Someone better at marketing will crowd us out,
so this can't be the only thing we lean on.

### 4.4 Boring reliability (most underrated)

Upstreams rename fields, rate-limit, and go down; we absorb it. This is the real moat
for businesses like BuiltWith and ScreenshotOne — not that it's technically hard, but
that **nobody else wants to keep managing it for years**. Our contract tests plus the
weekly benchmark are how this moat actually gets built.

---

## 5. Path to revenue and the revenue curve

### Pricing (v1 proposal)

| Tier | Price | For | What's included |
|---|---|---|---|
| Free | $0 | Type 4 users, trials | MCP endpoint, rate-limited, no SLA |
| Dev | $19/month | Type 3 | Higher limits, API key, email support |
| Bot | $99/month | Type 1 | High limits, webhook batching, status page, 24h incident response |
| Embedded | From $499/month | Type 2 | White label, SLA, dedicated limits, contract |

### Revenue curve: what has to be true, not what I guess

| Stage | MRR | What has to be true |
|---|---|---|
| First break | $19–99 | **1** paying customer. Proof that somebody will pay for this |
| Standing up | ~$1,000 | 20 on Bot, or 10 Bot + 1 Embedded |
| A real business | ~$3,000 | 3x the above, or 5 Embedded |

**Is 20 customers realistic?** There are thousands of trading bots competing in this
category. 20 is a small number. This isn't a question of whether it's possible, it's a
question of whether we've actually asked 20 people.

**Timescale**: the first paying customer is a 4–12 week thing, not a 4 day thing. The
first 3 months will most likely be $0 — those 3 months go into building distribution,
building trust, and accumulating data. That is normal, not a failure signal. The failure
signals are written into the decision gates in §8.

### Explicitly forbidden

**No referral fees, no order-flow revenue share, no paid ratings from token projects.**

This isn't about being high-minded. Our only asset is that nobody questions our motive
when we call a token dangerous. The moment revenue correlates in any way with calling
something low, that asset is worth zero, and it never comes back.

If we ever want to do it, full separation of interests and public disclosure come first.
The default answer is no.

---

## 6. Is this a passive-income tool

**No. And treating it as one is dangerous.**

Not because there's a lot of maintenance, but because of what this category is:

> **An unmaintained risk tool is worse than no tool at all.**
> It keeps confidently emitting answers, the answers are already wrong, and users are
> still acting on them.

We have already lived through this once: honeypot detection read the wrong field and
returned "safe" for **every** token, while everyone assumed it was working.

But the maintenance load itself is **small and automatable** — a configuration problem,
not a wall:

| Frequency | Task | Automation status |
|---|---|---|
| Every push | 153 tests | ✅ CI configured |
| Daily | New-pool snapshot collection | ⬜ To build (§4.1) |
| Weekly | Upstream contract tests + accuracy benchmark | ✅ Configured, notifies on red |
| On red | Human intervention | 0 normally, about half a day when something breaks |

**Steady state: 1–2 hours a month; 3–5 hours when an upstream changes.**

---

## 7. Roadmap: a series of cheap experiments, each with a decision rule

Principle: **if you can test it, don't research it.** The gate isn't "can this work"
(unanswerable), it's "how much money and how many days until reality answers".

### Experiment A — make it discoverable (this week, ~2 days, $0)
1. Push and deploy the current fixes (production is still running the version with
   broken honeypot detection)
2. Submit to the official MCP registry; open a PR against awesome-mcp-servers
3. List on Smithery / mcp.so / PulseMCP / Glama
4. English README and landing page

**Signal to read**: call volume and number of distinct callers within 14 days.
**Decision rule**: >0 callers that aren't us → continue. =0 → that's an exposure
problem, not a product problem; switch to Experiment C.

### Experiment B — start accumulating data (this week, ~0.5 days, <$1/month) ← most urgent
Snapshot new pools on each chain daily, revisit them periodically for the outcome,
write to R2. **No decision rule; this one is unconditional.** It's the only thing where
skipping today loses something permanently.

### Experiment C — turn accuracy into a talking point (next week, ~1 day, $0)
Post the benchmark results to r/ethdev, Hacker News, X, and the MCP community.
The headline is the differentiator: **"we published our own miss rate — nobody in this
category does"**.

**Signal to read**: discussion volume, calls originating from the posts, whether anyone
asks "can we use this".
**Decision rule**: anyone asks about commercial use unprompted → go straight to
Experiment D.

### Experiment D — ask 20 real people for money (weeks 3–4, ~2 days, $0)
Contact 20 Telegram/Discord trading-bot operators directly. No survey — one line:
*"What happens to you when your users get rugged? We have a pre-trade check, here's the
endpoint, $99/month, want to try it?"*

**Signal to read**: reply rate, how often "how much" comes up, number of trials.
**Decision rule**: ≥3 willing to trial → build the payment path. 0 replies → the
positioning is wrong; back to §2 and pick a different customer.

### Experiment E — put up a button people can pay through (week 4, ~1 day, $0)
Put up the pricing page and the Stripe link even if nobody has asked yet.
**Nobody clicking is also a signal**, and "wanted to pay, couldn't find where" is the
stupidest way to fail.

### After that (decided by results, not committed in advance)
- Holder concentration and LP locks on EVM (wire in GoPlus — but the benchmark needs a
  different independent labelling source before that lands)
- Same-name token collision detection ("the PEPE you asked about ranks 12th by
  liquidity among 47 tokens with that name")
- Predictive signals backed by outcome data (depends on Experiment B accumulating 3–6
  months)

---

## 8. Decision gates, and the standard we hold ourselves to

Every gate has to come back to this document with a written conclusion when it falls due.
Skipping one silently isn't allowed.

| Date | Gate | Test | Action |
|---|---|---|---|
| 2026-09-18 | Is anyone using it | ≥1 external caller within 14 days | Yes → continue; no → run only Experiment C, add no features |
| 2026-10-16 | Does anyone want to pay | ≥3 trial commitments in Experiment D | Yes → build payments; no → pick a different customer segment and run D again |
| 2026-12-04 | Is further investment worth it | MRR >$0 or >500 calls/day | Yes → continue per §7; no → move to low-maintenance mode |
| 2027-03-04 | Does the data asset hold up | Snapshot archive ≥6 months and trains a signal better than the current rules | Yes → that becomes the main product; no → keep the tool, drop the data narrative |

**The maintenance commitment.** We will never leave a risk tool running unmaintained.
A risk tool whose upstreams have drifted doesn't go quiet — it keeps answering, exactly
as confidently as before, and it is wrong precisely when someone is trusting it. That is
worse than having no tool at all. So the commitment runs in both directions:
**as long as VetAgent is online it is maintained, and if we ever stop maintaining it we
take it offline ourselves rather than let it rot.** The gates above decide how much we
invest. They never decide whether something still answering is still safe to trust —
that answer is fixed.

---

## 9. Metrics board (reviewed weekly, these five only)

1. **Distinct callers** (not call count — 100,000 calls from myself means nothing)
2. **Benchmark: miss rate, false-positive rate, unknown rate** (all three together)
3. **Upstream contract test status** (red = one detection dimension may already have
   failed silently)
4. **MRR**
5. **Days of snapshot archive** (the only direct measure of the moat)

---

## 10. How my plan differs from the existing one

The plan in the existing HANDOFF is a **product quality plan**, not a **business plan**.
Seven differences:

| # | Existing plan | My change | Why |
|---|---|---|---|
| 1 | No data collection | **Start daily snapshots immediately** | The only thing that is time-sensitive, compounds, and is lost permanently if we skip today |
| 2 | Implicitly aimed at individual agent users | Target **trading-bot operators** | People with revenue, payout liability, and direct losses are the ones who pay |
| 3 | No account of what monetisation does to the product | **Referral fees and order flow explicitly banned** | Once revenue correlates with calling something low, the only asset we have is worth zero |
| 4 | Benchmark = a quality gate | Benchmark = **a sales asset and an industry standard** | It is the only thing a B2B customer can cite to justify the choice |
| 5 | Chasing breadth across chains | **Depth first**, fewer chains | Two chains done properly beats eight done halfway |
| 6 | No exit conditions | **Four decision gates plus a maintenance commitment** | An unmaintained risk tool is a liability; we take it down ourselves rather than let it rot |
| 7 | Get it good, then charge | **Payment button up in week 4** | Nobody clicking is a signal; wanting to pay and not finding where is the stupidest failure |

---

## 11. Smarter angles (three optional lenses, not commitments)

1. **The product is memory, not a score.** Anyone can compute a current risk score;
   nobody has "what this pool looked like in the 30 days before it was drained."
   Move the core asset from scoring to history, and the MCP tool becomes a free front
   end whose reason to exist is legitimately collecting that data.
2. **Sell the moment of failure, not features.** Nobody wakes up wanting a token risk
   API. People need us after their bot buys a honeypot and their users are cursing them
   in the group chat. The copy has to hit that moment.
3. **Be the standard, not just a vendor.** Open-source the benchmark methodology as a
   public standard. If others adopt it, we are the reference implementation — authority
   bought very cheaply, no market share required.

---

## 12. Overturned assumptions

**Moved to [`DECISIONS.md`](DECISIONS.md)**; no second copy is kept here.
Write the same thing in two places and one of them eventually goes stale, with nobody
able to tell which one is right.

Only one stays here, because it's **a business judgement rather than an engineering
decision**:

| Date | Assumption | How it was overturned |
|---|---|---|
| 2026-09-04 | "The underlying data is free and public, so there is no moat" | That filter kills BuiltWith (free from the page source), ScreenshotOne (Puppeteer is open source) and Ahrefs (GSC is free and more authoritative) — all of them healthy businesses. **People pay not to have to do it themselves, not for exclusive data.** Demoted from a reason to kill the project to a positioning guide |
