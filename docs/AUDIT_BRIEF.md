# Audit Brief (AUDIT_BRIEF.md)

> For a reviewing model with read access to this repository. Written 2026-09-05 by the
> agent who did the work, which is a conflict of interest you should treat as one.
>
> **Give the auditor the whole folder.** This file is a reading order and an evidence
> standard, not a substitute for the repository. Everything here is checkable against
> primary sources, and where my account and the sources disagree, the sources are right.

---

## 0. Why this file is written the way it is

The owner's instruction was: audit everything, and do not repeat the previous agent's two
failure modes — **excessive pessimism** and **abandoning the project mid-way to chase
whatever the analysis just turned up**. Over a dozen half-finished projects were produced
that way.

You cannot fix that by asking a reviewer to be optimistic. An instruction to go easy
produces either suppressed doubt or flattery, and both are worse than pessimism: at least
pessimism is legible. What works is a **different evidentiary bar for different kinds of
claim**, applied symmetrically.

So this file asks for exactly two things:

1. **Defects: no bar at all.** Report every one you find, as harshly as you like. This is
   the most valuable thing you can do and the project's own history says so — see §4.
2. **Direction changes: a high, explicit bar.** Anything that would change what is being
   built, who it is for, or what it competes on must clear §5 before it is written as a
   recommendation.

The asymmetry is deliberate, and it is not a trick to protect the project. It reflects a
fact the project learned the hard way: *evidence good enough to raise an alarm is not
automatically good enough to silence one, or to redirect the work.*

---

## 1. Read in this order

Budget roughly this order of attention. The first three are the reasoning; everything
after is verification.

| # | Source | What it answers | Lines |
|---|---|---|---|
| 1 | `docs/STRATEGY.md` | Origin, vision, who it is for, moat, revenue, roadmap with decision rules | 372 |
| 2 | `docs/DECISIONS.md` | Every decision, its reason, **and what enforces it** | 169 |
| 3 | `docs/HANDOFF.md` | Current state, traps already hit, open decisions for the owner | 362 |
| 4 | `git log` (50 commits) | The reasoning at the moment of each change — 1,229 lines of message | — |
| 5 | `bench/results.md` | The accuracy benchmark, its method, and its stated limits | generated |
| 6 | `docs/SCORECARD.md` | Maturity score, per-line, regenerated from measurements | 92 |
| 7 | `docs/OPPORTUNITIES.md` | Ideas deliberately **parked**, each with a review date | 87 |
| 8 | `tests/` (6 files, 1,798 lines) | What is actually guaranteed rather than claimed | — |
| 9 | `src/` + `bench/` (4,361 lines) | The engine and the measurement harness | — |

**Do not skip `git log`.** Commit messages here carry the reasoning, the measurement that
motivated each change, and several admissions of error. They are the least sanitised record
in the repository. `git log -p` if you want the diff alongside.

### The single most useful thing about this repo

Almost every claim it makes about itself is checkable in one command:

```bash
python bench/run_benchmark.py     # accuracy, on 558 labelled tokens
python bench/scorecard.py         # maturity score, per line item
python tests/test_risk.py         # 122 assertions on the engine
python tests/test_mcp.py          # 54 on the protocol layer
python tests/test_upstream_contract.py   # hits live APIs; goes red when upstream changes
python tests/test_english_only.py        # no Chinese anywhere in the repo
python tests/test_gates_get_reviewed.py  # parked ideas have live review dates
```

**Run them before believing anything in this file.** If a number here does not reproduce,
the number here is wrong.

---

## 2. What the project is, in one paragraph

A pre-purchase safety check for AI agents, served over MCP at `https://vetagent.dev/mcp`.
Before an agent buys, holds or recommends a token, it calls `assess_token_risk` and gets a
verdict — `low` / `medium` / `high` / `unknown` — plus a recommendation written for an
agent to act on, instead of a pile of numbers to interpret. It sells shovels: it does not
trade, does not take referral fees, and does not give investment advice. The asset is that
nobody questions its motive when it calls a token dangerous (`DECISIONS.md` P1).

## 3. Where it actually stands

Maturity **53 / 100** by its own scorecard, which is designed so that pure engineering
caps out around 70 — the remaining 30 requires users, who do not exist yet.

| Dimension | Score | The honest reading |
|---|---|---|
| Correctness | 24.0 / 30 | 233 tests green across 6 files; false positives 3.5%; unknown 17.4% |
| Coverage | 16.4 / 20 | 9 of 11 risk dimensions; one measured and rejected on evidence |
| Credibility | 10.2 / 20 | Recall measurable at last (20 dead samples); snapshot archive 3 of 180 days |
| Distribution | 2.5 / 15 | 2 of 8 channels; external-caller count not measurable yet |
| Demand | 0.0 / 15 | **Zero users, zero revenue, zero inbound.** |

That last row is the whole risk of the project and it is not hidden anywhere. A decision
gate on **2026-09-18** asks whether even one external caller exists; `docs/OPPORTUNITIES.md`
and `tests/test_gates_get_reviewed.py` keep it live.

---

## 4. What the previous agent got wrong (so you can check whether it recurs)

Read this as a list of things to look for, not as absolution.

**Four silent defects, each returning a confident wrong answer:**

- Read `isHoneypot` from `simulationResult`, a key upstream does not have — so the
  honeypot check **always passed**.
- Parsed `pairCreatedAt` as ISO when it is epoch milliseconds; the exception was swallowed,
  so pair-age **never fired**.
- Selected liquidity without `_pick_best`, pricing USDC at **$0.00097** from a fork chain.
- A benchmark independence assertion compared against an empty set, so it **passed for
  weeks without testing anything**.

**Two criticals shipped in a single commit with 104 tests green**, both found the same day
by an adversarial review (72 agents told to refute rather than confirm):

- An uncosted pool (`"liquidity": null`) was read as an empty one, so the engine told a
  user "there is nothing to sell into at any price" about a token with 174 buys and 104
  sells that day — and *raised* confidence by deleting the data gap.
- Impersonation compared rivals across chains, so canonical ZORA was called "almost
  certainly not the token you meant" because a Solana pool claimed $1,015,244,216. That
  figure is unverifiable and manufacturable by anyone willing to open a pool under a
  target's ticker.

**The recurring shape**, which is now written up as `E1` in `DECISIONS.md`: *an observed
absence and an unobserved dimension are different things, and neither may impersonate the
other.* It has cost this project defects in both directions — reading "we could not check"
as "we checked and it is bad", and reading "nobody reported a number" as "the number is
zero". **Look for more instances. There probably are some.**

**And the behavioural failure the owner actually complained about:** on 2026-09-04 an
afternoon of market research undermined the distribution plan, the SEO plan and the
differentiator, then proposed repositioning the product — 14 days before the gate that
would have answered the underlying question empirically. That is the pattern that produced
a dozen abandoned projects. The countermeasure is §5.

---

## 5. The bar for a direction-changing recommendation

If you want to say the project should be repositioned, retargeted, or abandoned, the
recommendation must carry all five of these. This is not a filter to make criticism
inconvenient; it is the same standard the project applies to itself, and applying it has
killed three of the previous agent's own ideas in one day (§6).

1. **Name the decision gate it preempts.** `docs/OPPORTUNITIES.md` lists the open gates and
   dates. If your conclusion would be settled — either way — by a gate that resolves within
   90 days, say so, and say why waiting is worse than acting now.
2. **State the measurement that would falsify you.** Not "engagement seems low" but "if
   fewer than N external callers by date D, then X". If nothing could falsify it, it is a
   preference, and it should be labelled one.
3. **Cost it against the alternative of finishing.** The remaining engineering to a
   shippable v1 is small and mostly enumerated in `HANDOFF.md §9`. Compare against that,
   not against zero.
4. **Separate the defect from the discovery.** A tool returning wrong answers is not a
   signal to build a different tool; it is the work (`DECISIONS.md` P6). If your finding is
   "the engine is wrong about X", that belongs in §7, not here.
5. **Propose it as a parked line, not a pivot.** The rule that exists specifically to stop
   the failure mode (`DECISIONS.md` P5) is that a discovery suggesting a different product
   gets **parked with a review date**, not adopted. Write it in the form
   `docs/OPPORTUNITIES.md` uses.

**What this bar does not cover, and where you should be unsparing:** correctness, safety,
measurement validity, whether a test actually tests anything, whether a stated principle is
enforced by anything, whether a number in a document reproduces, and whether the tool would
mislead an agent about somebody's money. No bar. Go hard.

---

## 6. The working norm: measure before you conclude

The project's operating rule is that a claim about the product must be checkable, and the
check usually costs minutes. On the last working day this rule killed three of the agent's
own proposals and produced more value than the proposals would have:

- **LP lock/burn detection** looked like the obvious next feature — pulling the pool is the
  main EVM rug, and 33 of 43 confirmed-bad tokens are on the pair type where it is cheap to
  detect. Measured on 74 pairs: "LP is fully pullable" catches half the bad tokens and
  fires on **58% of the good ones**. Rejected. Building it would have added false positives
  and called it coverage.
- **Chain-history backfill via reserve events** was a genuinely different class of evidence
  and would have freed the price oracle. Measured: the free RPC caps `eth_getLogs` at
  10k–50k blocks regardless of filter, so one pool-year is ~1,580 calls. Not affordable.
  Reported as a dead end rather than a plan.
- **Using completed on-chain sells to answer sellability** when the simulator has no record.
  The evidence looked overwhelming — 72 of 97 unknown verdicts had 20+ completed sells,
  63 good and 0 bad, including WETH at 4,540 sells against $117.8M. Implemented, and the
  fail-closed test went red. It was right: a simulation tests whether **you** can sell, a
  completed trade shows **someone else** could, and a blacklist honeypot is built to make
  those look identical from outside.

If you propose a feature or a fix, the same standard applies to you. `bench/` is the
instrument; it is designed to be pointed at new questions.

**One warning about the instrument.** It has twice reported failures it caused itself: a
0.4s request spacing provoked upstream refusals that were then scored as the engine
declining to judge, and a probe collapsed `None`-from-a-429 into "no data" and nearly
produced the conclusion that a working method did not work. When a measurement says
something is absent, check that it was actually looked for.

---

## 7. What to report, and in what shape

A ranked list beats an essay. For each finding:

```
[severity] one-line claim
  file:line
  failure scenario   — concrete inputs or state that produce the wrong output
  how to verify      — the command, test, or query that settles it
  recommended action — fix now / park with a date / needs the owner's call
```

Rank by *what it costs someone holding the token*, not by how interesting it is.

Three things worth your attention that are known-open, so you can go deeper rather than
rediscover them:

- **`HANDOFF.md §9 item 1`** — the engine cannot see a price drawdown, and the data that
  would fix it is the same series the benchmark's outcome label is computed from.
  Capability against the ability to prove capability. Three routes are written down and
  none is chosen; the owner's call, and a good thing for you to have an opinion on.
- **The `dead` recall figure is 10% and that number is misleading.** `bench/results.md`
  explains why (`dead` is a market outcome, the engine scores a safety property, and half
  the dead cohort still holds over $7,000 of liquidity). Check whether that explanation is
  honest or self-serving. It was written by the agent whose number it flatters.
- **The bad cohort is 40 of 47 on one chain and 35 of 47 from one sampling source.** Stated
  in the report. Say how much it should discount the result.

---

## 8. Things that are deliberate, so you do not "fix" them

Each of these looks wrong at first glance and is load-bearing. Argue with them if you like —
but argue with the reason, which is in `DECISIONS.md`.

- **`unknown` is a first-class verdict, and the unknown rate is published next to recall.**
  A tool that answers unknown to everything has perfect recall and zero value; both numbers
  are reported so neither can be gamed alone (`B3`, `B4`).
- **GoPlus is deliberately kept out of the engine** even though it would cut the unknown
  rate immediately. It is the benchmark's held-out oracle; wiring it in voids the
  measurement. A test scans `src/` and goes red if its name appears (`B2`).
- **No referral fees, no order-flow revenue, no paid ratings** — permanently, not "for now"
  (`P1`).
- **Sampling sources get fixed quotas rather than queue position.** Collecting in order and
  truncating deleted the healthy control group without moving a single reported number
  (`B8`).
- **The maturity scorecard can go down**, and did — 52 to 42 mid-session when two test stubs
  went stale. A quality gate that only agrees with you is decoration.
- **A risk dimension can be marked "measured and rejected"** and leaves both numerator and
  denominator, with the exclusion printed on every run so it cannot become a quiet way to
  raise the score.

---

## 9. What would actually help most

In rough order, if your attention is finite:

1. **Find the next instance of `E1`** — an observed absence and an unobserved dimension
   swapped for each other. It has appeared four times. It is almost certainly still in
   there.
2. **Attack the benchmark, not the engine.** If the measurement is wrong, every number in
   every document is wrong. Specifically: is the independence assertion real, do the labels
   mean what they claim, and does the sample support the claims made from it.
3. **Say whether the 2026-09-18 gate is set up to give a real answer**, or whether it is
   arranged so that it cannot fail. It is the project's main honesty mechanism and it was
   written by the party it constrains.
4. **The engine's failure modes under adversarial input.** It is a security tool. Someone
   who wants a `low` verdict for their token can read the source.
5. Only then: features.

---

*If you conclude the project should stop, say so plainly — that is a legitimate finding and
§5 exists to make it well-founded, not to make it impossible. What §5 forbids is the thing
that has already happened a dozen times: an interesting discovery, an abandoned project,
and no measurement either way.*
