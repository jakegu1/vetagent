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

### O4 - Pools that disagree about the price, as a signal in its own right

**Found while fixing E-7 (2026-09-06). Deliberately NOT shipped with it.**

E-7 asked for a price sanity check where the chain-rank table cannot help. Measuring the
same comparison without the rank restriction turned up something larger:

    693  tokens with two or more priced, costed pools in scope
    214  (30.9%)  some pair of pools disagrees by more than 100x
     31  (4.5%)   ...still true when both pools do $50k/day and 50+ trades

MATIC's own test fixture carries a spread of $0.0882 to $1,345,090 between pools on
Ethereum. Two pools of one token priced fifteen million times apart cannot both be right,
and the deepest-pool-wins rule silently picks one and reports it as the price.

**Why it is parked rather than built.** The measurement above says how often it *fires*,
which is not the same as how often it is *right*. A dust pool quoting nonsense is not
evidence about a token, and the difference between "a broken pool exists" and "the price
we are about to report is wrong" is precisely what has not been measured. Shipping a
signal at a 4.5% firing rate on that basis is how false positives get built.

**What would settle it.** Take the pools that fire, ask GeckoTerminal's OHLCV endpoint for
each one's independent price, and count how often the deepest pool -- the one we report --
is the outlier rather than the dissenter. If the pool we already pick is nearly always
right, this is noise and the entry closes. If it is wrong in a meaningful share of cases,
it is a real defect in the primary number this tool reports, and it outranks most of what
is on the roadmap.

**Gate**: do not build until that count exists. Estimated cost: one pass over the cached
disagreeing tokens, no new data source.

---

## Reviewed and closed

*(Nothing yet. When a gate resolves, entries move here with the decision and the date.)*
