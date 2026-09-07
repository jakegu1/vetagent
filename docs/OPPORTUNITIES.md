# Parked Opportunities (OPPORTUNITIES.md)

> Ideas that are worth doing **later**, and the specific date each is allowed to be
> reconsidered. Nothing here may change what VetAgent is until its gate comes due.

## Why this file exists

On 2026-09-04, one afternoon of market research produced four findings that each
undermined a pillar of the plan — distribution, SEO, the differentiator — and ended with
a proposal to reposition the product. Every individual finding was backed by data. The
cumulative effect was to move the goalposts.

The worse part: STRATEGY.md sets decision gates precisely so that judgement waits for
evidence. Gate 2026-09-18 asks whether anyone outside is calling the service. On
2026-09-04, fourteen days before it came due and with the product never having been
given a chance to fail on its own terms, research was used to route around it.

That is the failure mode this file exists to block. Not the thinking — the thinking was
useful and the findings are real. What is blocked is **acting on a discovery by
redirecting the current project instead of parking it**.

## The rule

1. A discovery that suggests a different product, a different positioning, or a
   different customer goes **here**, not into STRATEGY.md.
2. Each entry names the **decision gate that must resolve first**. Until that date, the
   entry is inert. It is not a plan, a backlog item, or a hedge.
3. Measured facts that constrain *how* to finish the current work are different, and do
   belong in STRATEGY.md — as constraints, never as vetoes. "Search volume is small" is a
   reason to pick a different channel, not a reason to change products.
4. Fixing defects is never a pivot. A tool that returns wrong answers is not a signal to
   do something else; it is the work.
5. When a gate resolves, every entry blocked on it must be revisited and the outcome
   written down. `tests/test_gates_get_reviewed.py` fails once a gate date has passed
   with entries still unreviewed, so this cannot be quietly skipped.

---

## Parked

### O1 · Become the category's referee rather than its 18th scanner

**Blocked until: gate 2026-12-04** (is further investment in VetAgent worth it)

Build and publish a head-to-head benchmark of the commercial token-risk tools —
rugcheck.xyz, GoPlus, TokenSniffer, honeypot.is, ChainAware — on a common labelled set,
the way AV-Comparatives does for antivirus. Nobody has done this; searching turns up only
listicles and vendor pages. ChainAware advertises 90.1% accuracy and the methodology page
it cites returns 404.

Why it is parked rather than adopted: it is a **different product** with a different
customer. Adopting it now would abandon a tool that has not yet been given fourteen days
to find its first user. If VetAgent reaches 2026-12-04 without traction, this is the
strongest thing to do next, and much of the machinery — independent labelling, the
ablation method, the runtime disjointness assertion — already exists and carries over.

Evidence, collected 2026-09-04: no head-to-head test exists (verified by search);
AV-Comparatives sustains a business on exactly this premise; published academic labelling
methodology exists (arXiv 2201.07220, verified).

### O2 · Sell measurement to people with capital at risk, not to bot operators

**Blocked until: gate 2026-10-16** (does anyone want to pay)

GoPlus prices the same class of data at $199 / $399 / $799 / $1,899 / $3,499 per month,
roughly 35x above the $99 ceiling STRATEGY.md assumes. That suggests the buyer with real
budget is a listing desk, custodian or compliance function rather than a bot operator.

Parked because Experiment D has not run. The current plan says to ask twenty bot
operators for money. Changing the target segment before asking anyone is exactly the
substitution this file exists to prevent.

### O3 · Integration pull requests into open-source trading agents

**Not blocked — this is a distribution tactic for the current product, not a new one.**

Kept here only as a reminder that it outranks directory listings: measured MCP directory
traffic is about 0.17 organic visits per server per month, and the canonical awesome list
already carries roughly seventeen free token-safety MCP servers. Being inside someone's
code beats being on a shelf next to sixteen alternatives. Execute under STRATEGY.md
Experiment A; no gate required.

### O5 - The owner-power scan is blinder than its own headline says

**Not blocked** - this is a measurement over data now cached on disk, and it constrains a
decision already on the backlog (W1). It needs no gate; it needs someone to widen the
selector list from a source that is not the labelling oracle (W18).

`bench/owner_powers_measure.py` is committed and re-runnable, and on 250 contracts with
cached bytecode it measures recall against GoPlus's **per-flag fields** rather than the
derived cohort labels:

| GoPlus flag | it says | we find | recall | 95% CI |
|---|---|---|---|---|
| `is_mintable` | 156 | 81 | 51.9% | 44.1 - 59.6% |
| `transfer_pausable` | 19 | 7 | 36.8% | 19.1 - 59.0% |
| `is_blacklisted` | 19 | 5 | 26.3% | 11.8 - 48.8% |
| `slippage_modifiable` | 38 | 3 | 7.9% | 2.7 - 20.8% |

**Corrected 2026-09-07. The first version of this table was measured on the wrong 250
contracts and two of its four rows were badly wrong.** `fill_cache` took contracts in
dataset order, the dataset is 83% Base, and recall's denominator is the *positives* --
so it caught 3 of the 19 pausable contracts and 7 of the 19 blacklist ones. It reported
`transfer_pausable` 0.0% and `is_blacklisted` 14.3%, and this document concluded from
them that "on two of the four powers the scan is effectively blind". Zero of three has a
95% upper bound near 71%. It was compatible with finding most of them, and it did:
measured on all 19, across all three chains, pausable recall is **36.8%**.

The script now fetches flag-carrying contracts first, every denominator above is the
whole dataset rather than a sample, and every rate is printed with its interval so a
number resting on n=3 cannot look like one resting on n=156 again.

The conclusion survives the correction, on much better evidence and stated more
carefully: the scan misses roughly **half** the mintable contracts, **two thirds** of
the pausable ones, **three quarters** of the blacklist ones and **nine tenths** of the
tax-mutable ones. It is not blind. It is unreliable in a way that would be invisible to
anyone reading a checkbox, which is the same reason not to score it -- W1 stands.

**The audit's proposed additions do not fix it, and one of them would make things worse.**
Adding `isBlacklisted(address)`, `blacklist(address,bool)`, `blacklists(address)`,
`issue(uint256)` and the fee setters changes not one row of the recall table on this
sample - those functions do not appear in these contracts. Adding `enableTrading()` and
`openTrading()`, the pair the audit brute-forced as reproducing the original R12 table,
takes "can pause transfers" from 6 claims to **14, with GoPlus agreeing on none of
them**. Those selectors detect a launch gate, not a pause switch. That is good evidence
the original table was computed with selectors measuring a different property, which is
exactly why it could not be reproduced from the shipped list.

**What would settle it.** A selector corpus that is not GoPlus-derived - W18 - since
widening the list from the oracle's own labels would fix the recall and void the
benchmark (B2). Until then the honest position is that the instrument is too blind to
support either conclusion, and W1 says so.

---

## Reviewed and closed

### O4 - Pools that disagree about the price · **CLOSED 2026-09-06, same day it opened**

Parked in the morning with a gate: *do not build until we have counted how often the pool
we already pick is the wrong one.* Closed in the afternoon because that count was finally
run, and it found a live P0 rather than a feature.

The measurement separated two questions that had been treated as one:

| Question | Fires on | Verdict |
|---|---|---|
| Does SOME pool disagree with some other pool? | 30.9% of tokens | Noise. Dust pools quoting nonsense. Correctly not shipped |
| Does THE POOL WE PICKED disagree with its peers? | 0.61% at 10x, 0.30% at 100x | The bug. Shipped as a selection rule |

"A disagreement exists somewhere" and "the number we are about to publish is the outlier"
are different questions, and only the second is worth acting on.

**What it caught.** Production priced UNI at **$4,576,980**. The chosen pool claimed $44.4M
of liquidity and carried two buys and one sell in a day, against pools holding $19.5M with
real volume all quoting $6.99. Depth alone picked the liar. Fixed by rejecting candidates
that the rest of the token's own market contradicts by two orders of magnitude, then
ranking the survivors by depth as before.

**The lesson is about the gate, not the signal.** Parking the broad version was right, and
sizing E-7's guard to its measured 0-in-1,136 frequency was right. What was wrong was
writing down the experiment that would settle it and then not spending the twenty minutes
to run it. A parked opportunity with an unrun experiment is indistinguishable from a
forgotten one, and this one was hiding a P0 for the length of the delay.
