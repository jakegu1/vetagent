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

In one line: **before an AI buys a token for you, check whether you could get back out.**

> That wording is deliberate and it used to read "check whether the token is a scam". An external audit pointed out we cannot deliver the second one and should not imply it: a contract can hold the power to switch on a tax, pause transfers, blacklist an address or pull its liquidity, and keep every one of those dormant while our checks run. What we do establish is that the exit was open when we looked, which is the failure that actually empties wallets today and is worth saying accurately rather than grandly.

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

Not data. The upstream sources (DexScreener / GeckoTerminal / honeypot.is / RugCheck)
are mostly free and public.

> **Corrected 2026-09-06.** This line read "DexScreener / honeypot.is / GoPlus / RugCheck"
> for three days. GoPlus is **not** an upstream and never has been — `tests/test_risk.py`
> fails the build if the string appears anywhere in `src/`, because DECISIONS B2 reserves
> it as the benchmark's held-out labelling oracle. An external competitive review took
> this file at its word, and every conclusion it drew about "adjudicating better over the
> same signals GoPlus reads" was built on it. We read liquidity depth GoPlus never reads;
> GoPlus reads contract state we never see. That is a different input set, not a better
> reading of a shared one. For a product whose only real claim is that its numbers can be
> checked, publishing a wrong dependency list is the fastest available way to lose the
> argument.

We sell three things, in order of importance:

| What we sell | What the customer is actually buying |
|---|---|
| **Judgement** | Not "here are 40 fields" but "should you touch this, and why". Four sources that contradict each other, collapsed into one actionable verdict |
| **Reliability** | Upstreams go down, rename fields, rate-limit. The customer is buying "I never have to deal with that" |
| **Credibility** | We publish our own error rates **including the unflattering ones**, with the harness that reproduces them. Several tools in this category publish a headline number &mdash; Hypernative 99.8% detection, Forta >99% recall, Blockaid <0.0002% false positives (each vendor's own published figure, checked 2026-09-09) &mdash; and **none of them publishes a method you can re-run**. That is the claim. "Nobody else publishes a rate" is not, and stood here for two days after it was retracted from three other surfaces |

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
- ✅ Full test suite + CI + upstream contract tests (this one is the key: honeypot detection
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

> **Corrected 2026-09-09.** This paragraph claimed that "a competitor who decides to build
> it today still has to wait six months to catch up", and §4.2 called the archive "the only
> part of this product that cannot be copied". **We publish it.** `snapshot.yml` commits
> `bench/snapshots/*.ndjson` to the public repository four times a day: 10 tracked files,
> 12 MB, 10,938 rows, already cloneable in thirty seconds and still arriving.
>
> The half that survives is the one that matters technically: **nobody can backfill it.**
> Upstream APIs return the current snapshot only, so a competitor starting today gets
> today onward and can never reconstruct 2026-09-03. The half that is false is
> *exclusivity* — they do not have to start their own clock, they can fork ours.
>
> That is a real decision, not a wording problem, and it is the owner's: **W25**. Either
> keep publishing and drop the exclusivity claim entirely — the archive becomes a
> credibility and reproducibility asset, which is a defensible position and arguably the
> better one for a product whose pitch is checkability — or move it to R2, which §4.1
> already budgets, and publish the collector plus a rolling sample. Every day of delay
> adds another day of a supposedly exclusive series to forks and archives permanently, so
> the cost of not deciding is the one cost here that cannot be undone.

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
this product that cannot be *backfilled*.** A competitor starting today gets today
onward and can never reconstruct 2026-09-03, because upstream returns the current
snapshot only.

It *can* be copied, though, because we publish it four times a day — see the correction
in §4.1 and the decision waiting in **W25**. This sentence read "cannot be copied" for
six days while the workflow that falsifies it ran on schedule beneath it.

### 4.2 Published accuracy (medium strength, but the only differentiator we can cash today)

Several tools in this category publish a headline accuracy number. **What none of them
publishes is a method you can re-run** — we publish both the rates and the harness that
produces them (independent labelling + ablation + runtime disjointness assertion), so the
numbers can be checked rather than believed.

> **Corrected 2026-09-09, and this is the fifth time.** This line read "Nobody in this
> category publishes their own recall and false-positive rates" — false, and disproved by
> §1 of this same file ninety-nine lines above, which names three vendors that do. It
> survived the guard added the same morning because that guard's pattern required the word
> "else" and this phrasing omits it. Fixed the line and widened the pattern; the guard now
> keys on the claim's two false halves — a universal subject plus a denial about *rates* —
> instead of one wording, while still allowing the accurate "no method you can re-run".

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
| Every push | the full suite | ✅ CI configured |
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
| 2026-09-18 | Is anyone using it | `gate_verdict()` in `bench/usage.py`, frozen 2026-09-07: not ours; named a tool; **received a real verdict**; **came back on a second day**; **asked about more than one thing**; and one non-owner country if the name could be ours | Yes → continue; no → run only Experiment C, add no features |
| 2026-10-16 | Does anyone want to pay | ≥3 trial commitments in Experiment D | Yes → build payments; no → pick a different customer segment and run D again |
| 2026-12-04 | Is further investment worth it | MRR >$0 or >500 calls/day | Yes → continue per §7; no → move to low-maintenance mode |
| 2027-03-04 | Does the data asset hold up | Snapshot archive ≥6 months and trains a signal better than the current rules | Yes → that becomes the main product; no → keep the tool, drop the data narrative |

> **The 2026-09-18 test was tightened on 2026-09-07, eleven days before it came due,
> and the reasoning is recorded here rather than left in a diff.** It read "≥1 external
> caller". That is satisfiable by noise: this endpoint is public, unauthenticated and
> listed in the official MCP registry, so directory health-checkers and crawlers hit it
> from foreign IPs, and a crawler is neither a self-client nor in the owner's country --
> every filter `bench/usage.py` applies waves it straight through. The gate would have
> come back "yes, someone is using it" on a robot, and bought another round of building
> on the strength of it. That is the expensive direction to fail in.
>
> Repeat use is the cheapest property noise does not have. Three calls across two days is
> still a very low bar -- one person trying the tool, leaving, and coming back -- but it
> is not one a crawler clears by accident. `qualifying_callers()` in `bench/usage.py`
> measures exactly this, so the gate and its instrument agree.
>
> **Corrected a second time on 2026-09-07, after running it.** The first tightening --
> three calls on two days -- was written from the armchair and the data killed it
> immediately. The first real run reported **47 external callers** and printed "keep
> following the roadmap". Reading the same output properly:
>
> - 3,314 requests, of which **3,193 carry no tool name at all** (96.3%). Those are
>   `initialize` and `tools/list` handshakes. Only 118 requests called a tool.
> - Twenty of the forty-seven "callers" have prober, scan, audit, watch, witness,
>   observatory, index, archive, registry, census or stats **in their own names**:
>   sentineloracle, mcpbeat, rokmcp-collector, mcpscan, sasame-mcp-audit, mcpwatch,
>   mcpwitness, mcp-observatory, endpointaudit, teppi-probe, wellknownbot,
>   rootz-mcp-registry-prober, mcp-schema-archive, mcpgrade-probe, x402-observatory,
>   mcp-stats-prober, mcplookup.com-probe, pod-directory-probe, and others.
> - The volume rule would not have caught any of them. sentineloracle made **1,259
>   requests**. Volume is the one thing a crawler has in abundance.
> - The country filter has never excluded a single row: Analytics Engine reports every
>   request as country `??`, so it has been inert since it was written.
>
> Registering in the official MCP registry buys an audience of directory crawlers, and
> they arrive first. The discriminator that survives contact with them is not how often a
> client connects but **whether it ever asked the tool a question**. Connecting is not
> using.
>
> This is the third counting rule for one gate. The first two were both wrong in the same
> direction -- too easy to pass -- and each was written before any data existed. The rule
> is still being tightened rather than loosened, and it is still being changed before the
> date rather than after seeing whether it would have said yes.

> Changing a pre-registered test before it falls due is exactly the drift this document
> forbids, which is why it is dated, argued and left in place rather than quietly edited.
> It moves the bar **up**, not down.

> **Corrected a fourth time on 2026-09-07, and then frozen in code.** An external audit
> read the instrument's own output rather than its prose and found it printing:
>
>     YES: sasame-mcp-audit    13 calls, verdicts "(none) x13"
>     YES: rokmcp-collector     3 calls, 1 per day, find_new_hot_pools only
>     YES: vetagent-r16-verify  1 call
>     -> STRATEGY: keep following the roadmap.
>
> The third line is the developer's own verification call, made eight minutes earlier
> while deploying. `SELF_CLIENTS` was an exact-match set of two strings and this name was
> not in it. The gate built to detect strangers recommended another round of building on
> the strength of our own test traffic, a scanner that never received a verdict, and a
> collector on a daily timer.
>
> Three further premises in the paragraphs above were false:
>
> - **`mozilla` is our own landing page.** Its 42 calls — read for four days as the one
>   candidate that might be real use — come from the demo button in `src/landing.html`,
>   which POSTs `tools/call` from the browser and therefore arrives under the browser's
>   User-Agent. A click on our own page is interest, not adoption. It now names itself
>   and has its own bucket, where it serves as Experiment C's metric instead.
> - **Country was never unavailable.** "Analytics Engine reports every request as country
>   `??`" is written twice above and it is not what happened. `request.cf` is a JsProxy of
>   a plain JS object — attribute access, no `.get` — so `(cf or {}).get("country")` threw
>   `AttributeError` on every request ever served and a bare `except` returned `??`. The
>   discriminator that separates the owner's own traffic from a stranger's was in the
>   schema, already judged acceptable to record, and available the whole time. This is the
>   third occasion in this project where the answer was already on disk.
> - **`clientInfo` labels the handshake, not the call.** No `Mcp-Session-Id` is issued, so
>   the `tools/call` POST is a different request in a different context and the contextvar
>   set during `initialize` is gone. R15's claim that this "de-mushes 370 requests" holds
>   only for rows `tool_callers()` discards. Callers now name themselves with an
>   `X-MCP-Client` header, which travels on every request and needs no session.
>
> **This is the fourth counting rule for one gate, and each was written after seeing what
> the previous one produced, on a 14-day window that slides under the reader's feet.** A
> rule chosen after seeing the answer is not a test, however honest the intent. So this
> one is not prose: it is `gate_verdict()` in `bench/usage.py`, five conditions, pinned by
> `tests/test_usage_gate.py` against every bucket the real traffic has produced — and
> against a synthetic caller that must still pass, because a gate that cannot pass is a
> decision already made rather than a test. It is read **once, on 2026-09-18**, and it is
> not adjusted after a run. If it is wrong, it is wrong on the record.
>
> It moves the bar up again. Not ours; named a tool; received at least one real verdict;
> came back on a second day; asked about more than one thing; and — for a client whose
> name cannot be told from ours — one request from a country that is not the owner's. The
> accepted cost is stated rather than hidden: a genuine user who only ever checks scam
> tokens sees `high` every time and this rule says no.
>
> **Experiment C runs inside this gate's window, on purpose, and here is why that is not
> cheating.** The audit argued C should wait until after 09-18, because it sends curious
> people to the landing page and their clicks would be read as adoption. That was correct
> about the instrument as it stood and is no longer possible: the demo button names itself
> `vetagent-landing-demo`, which is `vetagent-*`, which is ours by construction. C's
> click-through cannot enter this gate's numerator; it is reported on its own line as C's
> own metric.
>
> The deeper reason is that this gate does not decide whether to run C. Read the action
> column: **no** means "run only Experiment C, add no features". C happens either way. The
> gate decides whether to add features, and running C early changes nothing about that —
> no features are added before 09-18 in either branch. Delaying C by eleven days would buy
> no information and cost eleven days of the only activity that could produce a user.
>
> What would be cheating is reading a promoted week as an organic one, so it is recorded
> here instead: **the 14-day window ending 2026-09-18 contains Experiment C.** If the gate
> comes back yes, that yes is from a promoted week, and it says people who were told about
> the tool came back on a second day and asked it about more than one token. That is a
> real answer to a real question. It is not the same answer as "strangers found it", and
> the difference belongs in the record rather than in a footnote afterwards.

> **2026-09-08: the rule was not touched, the evidence base was.** The frozen rule ran on
> the full 14-day window and returned **YES** on exactly two clients — `mozilla` (47 calls,
> 4 days) and `curl` (26 calls, 3 days, verdicts high/low/medium/ok/unavailable/unknown,
> which is the shape of our own smoke-test sequence). Those are precisely the two buckets
> that `a03f430` and `b078d65` emptied the previous afternoon: until 12:35 UTC on 09-07,
> our CI was recorded as `curl` and our own landing page as `mozilla`. Thirteen of the
> window's fourteen days were written by the unfixed instrument.
>
> That is not a finding that the callers were ours. It is a finding that the run **cannot
> say**, which is this project's oldest defect appearing for the fifth time: an
> unattributable row is a gap, and it is not allowed to impersonate either answer. So
> `gate_window()` floors gate evidence at the fix, and the run now prints how many tool
> calls it set aside. The rule itself — `gate_verdict()`, frozen 2026-09-07 — is
> unchanged and untouched.
>
> **Which way it cuts, stated before the next run:** the floor removes rows, so it makes
> YES harder, and it discards any genuine caller from 09-04 to 09-07 along with our own
> traffic. That cost is accepted because the alternative is worse in both directions — a
> pre-fix row can hide a real caller inside our own traffic exactly as easily as it can
> invent one. The change would have been made on a NO just as fast.
>
> **What the fixed instrument sees, measured the same day over the full 14 days: NO.**
> Of the window's 170 tool calls, **138 predate the fix and are set aside**; 32 are
> attributable and 8 of those belong to a client that is not ours. `mozilla` disappears
> completely — every one of its 47 calls was written before 09-07 12:35, which settles
> what it was. `curl` survives at 2 calls on one day with a single verdict, so it is
> marked NEAR: something real, and not a pass.
>
> So the contaminated window's YES is withdrawn and **the standing answer is NO —
> Experiment C only, no new features.** The gate is still read once on 09-18; this is the
> reading it would give today, recorded now so that a later YES has something to be
> different from.

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
