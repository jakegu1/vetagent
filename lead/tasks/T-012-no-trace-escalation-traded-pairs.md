---
id: T-012
title: Stop the no-trace escalation from calling a traded token "nothing can be verified" (W49, narrow form)
status: in_review        # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: M                  # S | M (split anything larger)
depends_on: [T-011, T-019, T-013]   # T-019 is the base AC 7 measures on; T-013 first only because it edits the same file
decisions: [ADR-0001]
backlog: W49
---

## Context

**The escalation.** `_finalize` (`src/risk.py`, about line 786) turns an answer into `high` 70
with the critical signal "Nothing about this token can be verified" ("No market data source
could price it and its sellability could not be simulated. Every legitimate token clears at least
one of those.", about lines 868-875) when both critical dimensions (`liquidity`, `sellability`)
carry a gap about the token and `evidence.chain_searched` is set. Gaps that are ours (`_OUR_GAP`)
and the unbacked-depth gap `_UNBACKED_REASON` do not count (`not_absence`, about line 839; E21:
"An unverifiable market is not 'no trace'"). Pools that were costed and found empty
(`evidence.pools_all_empty`) count as the liquidity half: an observed absence.

**Where the liquidity gap is filed.** In `assess` (about lines 4020-4067), when pairs exist but
`_pick_best` finds no usable pool and the in-scope pools are not all empty, the gap is one of
`_UNBACKED_REASON`, `about the token: no pair with a sane price`, or `about the token: no source
reported pool depth` (no pool in `_home_scope(pairs, chain_hint, address)` states a credible
depth), beside the warn "No usable pool" / "Pairs exist but none could be costed."

**The defect (W49).** DexScreener lists pools that trade but carry `liquidity` and `priceUsd` as
null. Measured for this spec on 2026-10-08 at `4838fdd`, offline: `assess` replayed over
`bench/cache` (read only, no fetch) with the clock frozen at 2026-09-21T02:00Z and each uncached
`mark_missing` request answered "no record", which reproduces all 576 committed rows of
`bench/results.json` (0 differing in verdict, score or driver). The rows this task is about, as
committed:

- **WMAI** (bsc, alive, GoPlus `safe`): `high` 70, driver `no_liquidity`; gaps `no source reported
  pool depth` and the simulator's "no record". One in-scope pair: 10540 buys, 148 sells in h24.
- **fwARB** (ethereum, `centralized`): `high` 70, `no_liquidity`; the same two gaps. One pair: 214
  buys, 243 sells.
- **fwWETH** (ethereum, alive, `centralized`): `high` 70, `no_liquidity`; `no source reported pool
  depth` and a reverted buy (`simulation failed: execution reverted: "revert: HP: BUY_FAILED"`).
  30 pairs, every one with trades, 29 with at least one sell.
- **BURN** (base, `safe`): `high` 70, `no_liquidity`; the same two gaps as fwWETH. Its only
  in-scope pool comes from the GeckoTerminal fallback and states 0 buys, 0 sells, zero volume and a
  reserve of about 1.7e-12 USD.
- **USI** (base, `safe`): `high` 100, driver `honeypot`; `no source reported pool depth` alone.
  One pair: 4 buys, 2 sells.

WMAI, fwARB and fwWETH are escalated to `high` 70 with a sentence that is false of a token traded
thousands of times a day. WMAI and fwWETH are 2 of the 5 benchmark false positives. What was
missing was a stated depth, not every trace of a market, and only one source was asked for it
(`_load_pairs`, about line 3857, returns DexScreener's pairs whenever it lists any; that half is
W39, Out). E11 cites "a token with 174 buys and 104 sells" without naming it; its 30 uncosted pools
(the docstring of `test_unpriced_pools_are_not_empty_pools`) match fwWETH. That is an inference,
not a record: E35 must not state it as fact.

**The base this is measured on (T-011 and T-019).** WMAI's and fwARB's "no record" rests on a
honeypot.is request that `bench/cache` does not hold. Measured: each of the two rows makes exactly
one request with no cache entry, a `mark_missing` request to honeypot.is (BUSD has the same miss).
Answered "no record" (the committed reading) both rows are `high` 70; answered as a failed fetch
they are already `unknown` 40 at `4838fdd`, with no fix. T-011 makes the benchmark a replay with a
pinned clock: at its head, `python bench/run_benchmark.py --replay` misses 91 requests (86 of them
to honeypot.is), and a replay with any miss writes nothing and exits 4. In the dated benchmark mode
T-011 persists every final 4xx answer except 429 as a dated negative entry, so the zero-address
honeypot.is URL (which answers 400) can be recorded too. Filling the misses is T-019, "Fill the
frozen benchmark's cache misses once, and re-baseline the published benchmark on it" (Level 3): it
runs T-011's `--fill` for real once and commits the re-measured drift. The fill can change these
very rows: the 2026-10-07 investigation asked 13 "no record" tokens live, and 1 of 13 now answers.
So this task measures on T-019's committed results, and the five rows above are the expectation
from `4838fdd`, not the base: AC 7 has the executor list, on the T-019 base and before anything
changes, every row the amended rule reaches.

**Lead decisions (binding).**
1. Narrow form only, pre-registered here (amended by the lead on 2026-10-08): "no source reported
   pool depth" is not an absence of market when at least one in-scope pair reports h24 SELLS
   greater than 0 (not any txns). On that path the no-trace escalation must not fire; the token
   keeps its data gap and comes back `unknown`, never `low`. Nothing may move toward `low`. Why
   sells: a buys-only pool is the shape a honeypot produces, and keeping the escalation there is the
   conservative direction.
2. The gap's own sentence must be true: on that path the reason must not say "no source reported
   pool depth" as if every source had been asked; it says what was observed (pairs listed, none
   states a depth). Exact wording is the executor's, within E18 (the verdict matches the
   sentence).
3. Out: asking the fallback when DexScreener lists unpriced pairs (W39).
4. A `docs/DECISIONS.md` entry states the rule, written by the executor in the same branch, before
   the benchmark re-run commit.
5. Expected effect on the frozen benchmark (amended by the lead on 2026-10-08 under decision 1 as
   amended; from the 2026-10-07/08 replays at `4838fdd`, to be confirmed on the T-019 base, not a
   target): WMAI, fwARB, fwWETH move `high` to `unknown`; BURN unchanged; false positives 5 to 3
   of 162; false blocks, dead and unsafe rows unchanged. The binding pre-registration is the
   executor's list from the T-019 base (AC 7). Any row that moves and is not on that list is a
   finding the READY report must explain.
6. Cases 2 (known chain, no pair) and 4 (drained pool) of
   `test_the_escalation_must_know_where_it_looked` stay green: those must still escalate.

**Traded, as used below.** A pair is *traded* when its `txns.h24` reports `sells` as a finite
number above zero: decision 1's "h24 sells greater than 0". Buys do not count: a pair with buys and
no sells is untraded and keeps the escalation. Only pairs in `_home_scope(pairs, chain_hint,
address)` count. Measured at `4838fdd`: requiring a sell moves the same benchmark rows as any txns
would (sells: WMAI 148, fwARB 243, fwWETH on 29 of its 30 pairs; USI 2). The engine's own
adjudication test (`test_chain_activity_overrules_a_honeypot_verdict`, about line 595) treats buys
without sells as the trap signature; its own shape, 900 buys and 3 sells, counts as traded, and
both answers there say do not trade.

**Decision 5 against decision 1.** The first version of decision 5 (BURN, WMAI, fwARB, fwWETH;
unknown 122 to 126) was measured under the broad form, which excluded every `no source reported
pool depth` gap. Under the narrow rule BURN cannot move: its in-scope pool has no trade. The spec
writer's replay of the narrow rule at `4838fdd` (same harness, same clock) moves exactly WMAI, fwARB
and fwWETH (`high` 70 to `unknown` 40): `high` goes 75 to 72 and `unknown` 122 to 125. An
independent row-level recomputation agrees. The lead amended decision 5 to that set. The broad-form
BURN and +4 stay on record only as a figure measured under a rule that was not adopted. BURN is
unlabelled, so the false-positive figure is 5 to 3 of 162 either way. Those figures are at
`4838fdd`; the pre-registration that binds is the executor's list from the T-019 base (AC 7).

## Goal

A token whose in-scope pools are traded (Context), none of which states a depth, is no longer
escalated by the no-trace rule: it keeps a liquidity gap that says what was observed and comes back
`unknown` (or `high` only on a finding of its own, such as a honeypot flag). Every observed
absence (no pair, drained pools, untraded pools, buys-only pools included) escalates exactly as
today, and the benchmark and every published figure are re-measured in the project's order.

## Scope

**In:** the liquidity-gap branch in `assess` (a new reason for traded in-scope pools with no stated
depth); `_finalize`'s not-absence exclusion and the comment above it; one `_GAP_CLASSES` label in
`src/entry.py` so production telemetry names the new reason instead of `other`; `_DEPTH_GAPS` in
`bench/publish_numbers.py` so `_depth_row` classifies the new reason (it is called on the
oracle-tagged centralised rows, and raises on fwARB and fwWETH otherwise, so the regeneration
fails); the `/unknown` paragraph that states the rule; DECISIONS row E35; acceptance tests; named
change (a), atom comments included; the re-measurement on the filled replay and the regeneration.

**Out:**
- Asking the GeckoTerminal fallback when DexScreener lists unpriced pairs (`_load_pairs`): W39, with
  its own measure-first protocol. No new production request is added by this task.
- Admitting BSC's native `0x000...` as an anchor (`_ANCHORS`, about line 80): unmeasured, not here.
- The wording of the untraded reason (`no source reported pool depth` stays), the `no pair with a
  sane price` branch (0 benchmark rows carry it), dust reserves, the drained rule, the no-pair rule,
  `_OUR_GAP`, `_UNBACKED_REASON`, the chain-searched gate, `_what_was_unseen`, the `liquidity()`
  tool (it already answers `unpriced`), and the GeckoTerminal shim `_gt_to_pair` (about line 1601),
  including how it converts trade counts.
- LIBRA, TRUMP and KITE, the other three false positives: their `high` rests on honeypot holder
  evidence and E23 (frozen until W40). Relabelling any of them would be an instrument change.
- Any scorecard band, floor or threshold (invariant 10).
- `docs/BACKLOG.md` (the lead closes W49 after merge).
- Two hand-written passages of `docs/EXPERIMENT_C.md` that this task makes false and nothing
  regenerates. Leave both untouched, and name both as stale in the READY report; the lead rewrites
  both after the merge and before the push, and the Owner sees them in the push batch (text posted
  under the Owner's name):
  - the main body, about lines 108-113: "for four of those the engine found no costable pool at
    all, which for two became `high` rather than `unknown`. That last part is an engine bug";
  - the r/ethdev draft, about line 213: "4 of those had no pool the engine could cost, and for 2
    of them ... I think that is an engine bug, and it is open."

  Their counts "All 5" and "all 5" are guarded (`alive_thin_high_n`) and regenerate to 3. The words
  "four" and "two" and the digits in "4 of those" and "for 2 of them" are not guarded, so after the
  regeneration both passages contradict themselves. That is expected in this branch.
- `docs/DECISIONS.md` E33 ("every subset of six gap atoms, the empty one included, 64 rows"): it
  stays as written. `docs/DECISIONS.md` is a frozen log (`FROZEN_LOG_FILES` in
  `bench/publish_numbers.py`) that records the figure at its date; E35 may state the new count.
- T-011 and T-019, the fill and the re-baseline (Context): dependencies, not part of this task. No
  fetch-mode run (`python bench/run_benchmark.py` without `--replay`) and no `--fill` run here.
- Any call to `vetagent.dev` or to a live upstream; pushing or deploying (the Owner's yes; a push
  touching `src/` deploys to production).

## Files in scope

- `src/risk.py`: the liquidity-gap branch in `assess` (about lines 4020-4067), `_finalize`'s
  `not_absence` (about line 839) and its comment; a new reason constant beside `_UNBACKED_REASON`
  (about line 1224) if you choose one. Nothing else in the file changes.
- `src/entry.py`: one new entry in `_GAP_CLASSES` (about line 454).
- `src/pages.py`: the paragraph under "When the absence is the answer" (about line 262).
- `bench/publish_numbers.py`: `_DEPTH_GAPS` (about line 542) only.
- `docs/DECISIONS.md`: row E35 (or the next free E-number at the base) and the "table is at N
  rows" line. Nothing else.
- Acceptance tests: new test functions in `tests/test_risk.py` and `tests/test_http_telemetry.py`
  (both already steps of `test.yml`, so no workflow change and no new step for `lead/checks.py`).
- Measurement outputs, written only by the scripts, never by hand: `bench/results.json` and
  `bench/results.md` (`python bench/run_benchmark.py --replay`), and whatever
  `bash .github/scripts/regenerate-derived.sh regenerate` rewrites (expected: `README.md`,
  `src/landing.html`, `src/pages.py`, `src/entry.py`, `docs/EXPERIMENT_C.md`, `docs/SCORECARD.md`,
  `docs/OWNER.md`).
- **Named changes to existing tests** (from the conflict search). Only these; any other failing
  older test means BLOCKED:
  - **(a)** `tests/test_risk.py`, `test_every_data_gap_declares_which_of_three_things_it_is`
    (atoms about line 5504):
    - add one atom to `atoms`, `"traded, no depth": {"dimension": "liquidity", "source":
      "dexscreener", "reason": <the AC 1 reason, read from the engine, not typed>}`, with a comment
      saying it is W49's shape (pairs listed and traded, none states a depth);
    - re-word the comment on the existing `"no depth"` atom (about line 5516), which today calls
      itself "W49's shape". It becomes the untraded shape: sources answered, pools listed, none
      traded and none stated a depth. Keep its point that a mutant putting "No source can see this
      token" back as `_what_was_unseen`'s fallback survives the table without it; both atoms now
      reach that fallback.

    Nothing else in the test changes. The table grows from 6 atoms and 64 combinations to 7 and
    128, and every existing check must hold on all of them. Its own commit, after the fix, titled
    `T-012: named change (a)`.

## Acceptance criteria

1. **A traded token without a stated depth is not escalated.** Fixture (synthetic, the WMAI
   shape): DexScreener `latest/dex/tokens` lists one bsc pair naming the token as base, with no
   `liquidity` and no `priceUsd`, and `txns.h24` buys 10540, sells 148; the fallback answers
   `{"data": []}`; honeypot.is answers `risk.NO_DATA`; goplus None; rugcheck `risk.NO_DATA` (the
   stub of `test_the_escalation_must_know_where_it_looked`). With chain hint `bsc` and with no
   hint, `assess` returns `risk_level` `unknown`, no signal named "Nothing about this token can be
   verified", a `data_gaps` entry with dimension `liquidity`, and `next_action` `abstain`. The same
   holds (i) on ethereum with honeypot.is answering a reverted buy (`simulationSuccess` false,
   `simulationError` `execution reverted: "revert: HP: BUY_FAILED"`), the fwWETH shape; (ii) with
   three home-chain pairs of which only one is traded; (iii) with buys 0 and sells 3.
2. **Every observed absence still escalates.** With the AC 1 fixture changed only as stated, the
   answer is `high` with the escalation signal: (a) buys 0 and sells 0; (b) no `txns` key; (c) each
   count that is not a finite number above zero, on both sides at once: `None`, `"abc"`, `""`,
   `"nan"`, `"inf"`, `-5`, `True`; (d) the BUSD shape: the home pool states `liquidity.usd` 0 and
   `priceUsd` `"0.1"`, with buys 4 and sells 3 (a drained pool stays an absence whatever traded
   before); (e) trades only off the token's own chain: two ethereum pairs with no depth and no
   trades plus one pulsechain pair with no depth and 500 buys and 500 sells, with hint `ethereum`
   and with no hint; (f) buys 900 and sells 0 (a buys-only pool is untraded, decision 1).
   `test_the_escalation_must_know_where_it_looked` is unchanged and green, its cases 2 and 4
   included.
3. **Nothing moves toward low.** With the AC 1 pairs moved to ethereum and the clean simulation in
   `tests/fixtures/hp_matic.json`, the answer is `unknown`, never `low` or `medium`. With the same
   pairs and the flagged answer `test_chain_activity_overrules_a_honeypot_verdict` builds
   (`hp_flagged`: 90 of 3,689 tested holders failing), it is `high`, driver category `honeypot`.
4. **The gap says what was observed.** In every AC 1 variant the liquidity gap's reason is one and
   the same string, built by `risk._gap(risk._ABOUT_TOKEN, ...)`, holding no digit, saying that
   pairs are listed and none states a depth (words the executor's, within E18). It contains none of
   the phrases other readers classify by: `no source reported pool depth`, `no trading pair found`,
   `priced in an asset`, `no record`, `simulation failed`, `does not cover`, `upstream request
   failed`. In AC 2 (a), (b), (c), (e) and (f) the reason stays exactly `about the token: no source
   reported pool depth`. No AC 1 answer's `recommendation` contains `No source can see this token`
   or `could price it`.
5. **The instruments read the new reason.** (a) `entry._why_unknown` for an `unknown` answer whose
   gaps are the AC 1 liquidity gap and the engine's no-record sellability gap returns exactly
   `coverage|liquidity:<L>|sellability:no record`, where `<L>` is a new `_GAP_CLASSES` label of
   lowercase letters and spaces, not `other` and unlike every existing label; the untraded reason
   still records `liquidity:no depth`. (b) `publish_numbers._depth_row` returns `none` for a row with
   `liquidity_usd` None, driver `sellability` and the AC 1 reason in `gap_reasons`, and still raises
   for a row with no depth figure, not drained and no depth gap. Both checks take the reasons from
   the engine (an `assess` run on the AC 1 fixture, or the engine's own constant), never a typed
   copy.
6. **The record and the public page state the rule.**
   - (a) `docs/DECISIONS.md` gains row E35 (or the next free number, Notes: "At dispatch") in the
     risk-engine table, after the last row. It carries
     decision 1 in substance: the condition (no in-scope pool states a depth, and an in-scope pair
     reports h24 sells above zero, as Context defines traded; buys alone do not count); the
     effect (the escalation does not fire, the liquidity gap stays, the answer is `unknown`); and
     nothing moves toward `low`. It is dated, gives its why
     (W49, E11, E21), and has an "Enforced by" cell naming the AC 1 and AC 2 test functions. It
     may say the generated gap table now has seven atoms and 128 rows; it does not name fwWETH as
     E11's token. The "table is at N rows" line goes up by one (61 to 62 at `4838fdd`);
     `python tests/test_decisions_enforcement.py` passes; the E35 commit precedes the
     re-measurement commit.
   - (b) On `/unknown` (`src/pages.py`), the paragraph under "When the absence is the answer" no
     longer says every token that no source can price and no simulator can trade is `high`. It
     says that pools listed with sells in the last day, whose depth no source states, are not an
     absence, and that such a token comes back `unknown`. An acceptance check reads
     `pages.UNKNOWN_HTML` and requires that section (from its heading to the next) to contain the
     words `not an absence`. The new text holds no digit; names no `tests/test_advertised_coverage.py`
     `VOCABULARY` form (such as `sellability`, `sell simulation`, `sell test`) unless a denial or a
     chain scope precedes it within that guard's windows; and promises no rating for a retried
     answer (section 3b of the gap test).
7. **Measured on the filled replay, against the pre-registered expectation.** Every benchmark
   command here is `python bench/run_benchmark.py --replay` (T-011), against the main checkout's
   `bench/cache` (Notes), never two at once. The base is the head after T-019 (and T-013) merged.
   - **Precondition, before the tests-first commit.** At the base, the replay reports zero misses,
     exits 0 and leaves `git status --short` empty (it reproduces the committed `bench/results.json`
     and `bench/results.md`). A miss: stop BLOCKED with the miss list.
   - **The pre-registration, before the tests-first commit.** On the base, with a scratch harness
     over the replay (no change to `src/`), list every benchmark row the amended rule reaches: its
     liquidity gap is `about the token: no source reported pool depth` and at least one in-scope
     pair is traded (Context: h24 sells above zero). For each, give symbol, chain and its current
     verdict, score and driver. That list goes in the tests-first commit's message, and it IS the
     pre-registration: a listed row whose current `high` rests on the no-trace escalation is
     expected to move to `unknown`; every other row, listed or not, is expected not to change
     verdict. The list is fixed by that commit and is never edited after the run.
   - **After the fix:** the replay (zero misses, exit 0), then
     `bash .github/scripts/regenerate-derived.sh regenerate`, then every test. The re-measured
     `bench/results.json` and `bench/results.md` are one commit; the regenerated pages another.
     Deltas are against the base's committed `bench/results.json`. Figures in brackets are the
     values at `4838fdd`, which T-019 and T-013 shift.
   - **Expected list (decision 5 as amended; from the 2026-10-07/08 replays at `4838fdd`; to be
     confirmed on the T-019 base, not a target):** WMAI, fwARB and fwWETH move `high` 70 to
     `unknown` 40, driver `no_liquidity` to `sellability`. BURN stays `high` 70 (not reached: no
     in-scope sell). USI is reached and changes only its gap wording (its `high` is a honeypot
     finding). `high` -3 and `unknown` +3 (75 to 72, 122 to 125). `outcome.full.good.high`, a rate,
     goes from 5 of 162 to 3 of 162. False blocks, the `low` count, and the dead and unsafe cohorts'
     verdicts are unchanged. Where the executor's list differs from this one, the READY report says
     how and why (for example a row T-019's fill changed); the executor's list is what binds.
   - **Derived figures predicted** by applying those row moves to a copy of `bench/results.json`
     (`publish_numbers.figures()` keys, old -> new at `4838fdd`): `fp_n` 5 -> 3; `fp_pct` 3.1 -> 1.9;
     `alive_thin_high_n` 5 -> 3 (three `docs/EXPERIMENT_C.md` targets); `unknown_n` 122 -> 125;
     `unknown_pct` 21.2 -> 21.7; `unknown_simulator_n` 94 -> 97, its median unchanged;
     `centralized_high_n` 40 -> 38; `centralized_high_pct` 22.3 -> 21.2; `cent_none_high` 4 -> 2,
     `cent_none_unknown` 2 -> 4 and `cent_high_no_figure_n` 4 -> 2 (the `/method` centralised "No
     depth figure" row, its contract-only column unchanged); `goplus_fp_pct` 6.0 -> 5.7
     (GoPlus-`safe` rated high 21 -> 20 of 349; an aggregate of `results.json`, computed from the
     row moves rather than read from the copy); `unknown_unbacked_n` and every false-block key
     unchanged. On the scorecard: the false-positive line 4.0 -> 5.0 (3 of 162 is under the 0.02
     band edge), the benchmark-unknown line unchanged at 2.0, and the pass counts of
     `tests/test_risk.py` and `tests/test_http_telemetry.py` up by this task's new checks.

   The READY report lists every row whose verdict, score or driver changed and every published
   figure the regeneration moved (old -> new), and explains each by the rows that moved. A row that
   moves and is not on the executor's list, or a listed row expected to move that does not, is a
   finding in the READY report, never a reason to change the rule after the run (no widening to
   move BURN, no threshold on the count).
8. **Contract and checks.** The first commit adds only the acceptance tests, and its message
   carries AC 7's pre-registration list. At that commit they run
   without crashing (a missing engine name is reported as a failure, not a traceback) and are red on
   at least AC 1 (`high` with the escalation), AC 4 (reason `no source reported pool depth`), AC 5
   (a) (label `no depth`) and AC 6 (b). Then, each in its own commit: E35; the fix, whose message
   says what the red looked like; named change (a); the re-measurement; the regenerated pages. At
   the head, `python lead/checks.py` passes every step (the base's count; this task adds none),
   exits 0 and leaves the tree clean.

## Evidence required

- The AC 7 precondition, from the base: the replay's summary line (zero misses, exit 0),
  `git status --short` after it (empty), and the five Context rows (WMAI, fwARB, fwWETH, BURN, USI)
  as the base's `bench/results.json` holds them.
- The AC 7 pre-registration list, as the tests-first commit message carries it, and how it differs
  from the expected list, if at all.
- The tests-first commit's SHA, and the output of `python tests/test_risk.py` and
  `python tests/test_http_telemetry.py` on it: which new checks fail and why, and the exit status.
- At the head: both files (pass counts), `python lead/checks.py` (summary line and exit status),
  `git status --short` (empty), and `git log --oneline <base>..HEAD` showing the commit order of AC 8.
- One AC 1 answer as JSON, before (base) and after (head).
- The re-measurement: its command line, the zero-miss line, and a row diff against the base's
  `bench/results.json` (symbol, chain, verdict, score, driver, before -> after), plus
  `outcome.full.good.high`, the unknown count, `false_block` and the verdict distributions of the
  dead and unsafe cohorts, before and after.
- Every figure the regeneration moved (the `publish_numbers` report, old -> new), each traced to the
  rows that moved, and the two `docs/EXPERIMENT_C.md` passages under Out quoted as they read after
  the regeneration.
- Five mutants, each shown to turn a named acceptance check red: (a) the new reason left out of
  `not_absence`; (b) trades counted over every pair rather than the home scope; (c) the escalation
  suppressed whenever any in-scope trade exists (the BUSD shape then loses it); (d) `True` or
  `"inf"` read as a trade; (e) buys counted as a trade (AC 2 (f) then loses the escalation).
  Restore the file and clear `__pycache__` after each (`CLAUDE.md`: a stale `.pyc` makes a mutant
  lie).
- The final text of row E35 and of the `/unknown` paragraph.
- `git diff --stat <base>..HEAD`: only files in scope, the generated outputs above included.
- A scan of every hand-edited file for non-ASCII characters added by this task: none.

## Notes

**Threat model.** What must never happen:
(a) A token reaches `low` or `medium` through this change (invariant 1). The liquidity gap must stay
in the `liquidity` dimension so the fail-closed override still forces `unknown`.
(b) An observed absence loses the escalation: no pair (case 2), drained pools (case 4, and the BUSD
shape where pools state $0 after trading), untraded pools (BURN's shape), and buys-only pools
(the honeypot shape; AC 2 (f)).
(c) Trades on pools the engine already refused, such as fork-chain copies, excuse the token: the
count is taken over `_home_scope(...)`, the same scope the gap branch already computes, never over
`pairs`.
(d) A malformed sell count is read as a trade. Library defaults do this: `_num(True)` is 1.0 and
`_num("inf")` is infinity. Of the counts as the engine receives them, only a finite number above
zero counts; `None`, booleans, NaN, infinities, negatives and non-numeric strings do not. On the
DexScreener path the engine sees the raw JSON values, so all of these are refused there (AC 2 (c)).
On the GeckoTerminal path the shim (`_gt_to_pair`, about line 1601, Out) has already passed each
count through `_num`, so a boolean `true` arrives as 1.0 and cannot be told from one trade: an
accepted residual, beside the wash-sell one below. NaN, infinities and negatives still arrive as
such there and are refused.
(e) The new reason escapes the three declared kinds or hand-writes a prefix (E27; the guard below).
(f) Telemetry records anything but a fixed label (invariant 2): the new `_GAP_CLASSES` entry maps a
phrase to a constant word; no count, figure or upstream text.
(g) A published figure goes live before it is re-measured, or is edited by hand (invariant 4).
(h) The rule is adjusted after the run to fit an expectation (invariant 10's spirit; decision 5).
Realistic accidents: reading the best pair's `txns` (there is no best pair on this path); reading
`pairs` instead of the scope; the shim writes 0.0 for a count GeckoTerminal omits, so for fallback
pools "no count" and "zero" look alike and keep the escalation, which is the conservative
direction; a reason string that contains an earlier `_GAP_CLASSES` phrase and is classified as
that; a stale `__pycache__`; a replay run in a worktree with no `bench/cache` (it misses everything
and exits 4: stop at the AC 7 precondition).
Accepted residuals, stated so they are not mistaken for coverage (a minor note at most): an h24
sell count is cheap to fabricate, so one wash sell on a pool nobody prices turns this escalation's
`high` into `unknown`; the shim's boolean conversion above. Both answers say do not trade, and
`unknown` must never justify one. After a deploy (the Owner's yes), production answers on this path
move from `high` to `unknown`, so the production unknown line can rise: the honest direction, not
measured here.

**Pointers.** `_finalize` about line 786 (escalation about 835-875); `_UNBACKED_REASON` about line
1224 is the precedent for a not-absence reason; `_home_scope` about 1417; the gap branch in
`assess` about 4020-4067; `_what_was_unseen` about 1073 (the new reason falls to its last,
generic clause, as the untraded one does); `_GAP_CLASSES` in `src/entry.py` about line 454 (the
first phrase found wins); `_DEPTH_GAPS` and `_depth_row` in `bench/publish_numbers.py` about line
542; `_simulator_unknowns` there counts `simulator has no record` and `simulation failed`, which is
why AC 4 bars those phrases. One way that works (a hint, not a requirement): a module constant
built with `_gap(_ABOUT_TOKEN, ...)` beside `_UNBACKED_REASON`, added to `not_absence`, chosen at the
gap branch when any in-scope pair is traded. Prototyped by the spec writer in a scratch copy of
`src/risk.py` (no `/unknown` edit; under the earlier any-txns form of decision 1, so the prototype
counted buys too): `tests/test_risk.py` 706 of 706 (the AST guards included),
every other test file that imports `risk` unchanged, and with named change (a) applied all 128
combinations pass.

**The gap-reason guard.** `test_every_data_gap_declares_which_of_three_things_it_is` (about line
5346) fails on any reason not built by `_gap()` or `_failed()` and on any string literal that
hand-writes a prefix. A reason passed through the local name `reason` is accepted only when every
assignment to `reason` in `assess` contains `_gap(`, `_failed(` or `_UNBACKED_REASON`: a separate
statement `reason = <NEW_CONSTANT>` turns it red; the new constant inside the existing conditional
expression passes.

**The benchmark.** Only `python bench/run_benchmark.py --replay`, T-011's mode: it never calls an
upstream and never writes the cache, and with any miss it writes nothing and exits 4. `bench/cache/`
is git-ignored and exists only in the main checkout, so a worktree has none: link the worktree's
`bench/cache/` to the main checkout's, or point the fetcher's `CACHE_DIR` at it from a scratch
harness, as T-011's hints describe. Never run two benchmarks at once (they share `bench/cache/`).
Only ever `regenerate-derived.sh regenerate`. T-019 and T-013 merge first (`depends_on`), so the
fill's drift and T-013's rows (THQ, USDT0, RALLY, Surplus) are already in the base and the absolute
counts shift by their deltas; this task's deltas do not change (no row overlaps with T-013).

**Conflict search** (2026-10-08, at `4838fdd`; repeat with `git grep -n -e "<term>" -- tests/`).
Terms: `no source reported pool depth` (one hit: the `no depth` atom, `tests/test_risk.py` about
line 5519; named change (a) adds a sibling and re-words its comment); `Nothing about this token can
be verified` and `can be verified` (`tests/test_risk.py` about lines 383, 422, 505, 1441, 4699, all
on no-pair, drained, untraded, outage or Solana shapes; `tests/test_http_telemetry.py` about line
271, a synthetic answer); `_UNBACKED_REASON`, `not_absence`, `_OUR_GAP` (about 1637, 3168, 5412);
`chain_searched` (about 1483, 3034, 3733); `No usable pool`, `none could be costed`, `_DEPTH_GAPS`,
`_depth_row` (no test hits); `_GAP_CLASSES`, `no depth`, `_gap_tags`, `_why_unknown`, `_why_high`
(`tests/test_http_telemetry.py` about lines 159-300, fixed reasons that keep their labels); fixtures
holding a pair with no stated depth and trades (only pulsechain pairs in
`tests/fixtures/ds_matic.json`; every test that loads it hints or ranks to a chain whose pairs state
a depth); pair builders with an empty `liquidity`: about line 1231 (the `liquidity()` tool), about
line 1516 (zero trades), and `test_unpriced_pools_are_not_empty_pools` (about line 2256: three
ethereum pools, `liquidity` None, `priceUsd` "0.0001", 174 buys and 104 sells, AC 1's shape). That
last one sees the change, since its liquidity gap's reason becomes the new one, and stays green: the
simulator answers (`hp_matic.json`), so nothing escalates, and it asserts only that a liquidity gap
exists and no pool is called empty. The dust-reserve test (about line 1300; the simulator answers,
so no escalation). Tests pinning the moving figures (`5 of 162`, `122`, `40 of 179`, the rates, the
moving symbols and addresses): none. `test_the_row_count_is_honest` reads the "table is at N rows"
line, which AC 6 updates.

Readers of the `/unknown` paragraph, which the prototype did not touch. Each sees AC 6 (b)'s edit
and must stay green; no named change:
- `tests/test_advertised_coverage.py` scans every sentence of `src/pages.py` (`SURFACES`, about line
  66). `claims()` (about line 250) reads a `VOCABULARY` form as a claim on every chain it applies to,
  unless a denial word (`_DENIALS`) stands in the 90 characters before it or a chain is named near
  it. A denial after the noun does not count (`denied_before`, about line 229). The sell-simulation
  forms are covered only on ethereum, bsc and base, so an unqualified `sellability` turns
  `test_no_surface_claims_a_dimension_on_a_chain_we_do_not_cover` red.
- `tests/test_risk.py`, section 3b of the gap test (about line 5681): any `/unknown` sentence that
  mentions a retry and matches "stays", "still be" or "remains" before `unknown`, or "never" before
  `low`, fails.
- `tests/test_number_coverage.py`: `src/pages.py` is in `LIVE_CLAIM_FILES`, so a digit before a
  percent sign fails.
- `tests/test_http_telemetry.py` (about line 662) fetches `/unknown` for its status, title,
  canonical link, share card, structured data and sitemap entry, which a paragraph edit leaves
  alone.

Every test file that imports `risk` was also run against the prototype: none failed. Named change
(a) is the only change to an existing test.

**At dispatch (batch check, 2026-10-08).**
- **The E-number.** E35 is the next free number at `4838fdd`, but the lead may file rows of its
  own after earlier merges (T-013 and T-016 each leave a record to the lead). At dispatch the
  lead reads the last E-number and the "table is at N rows" line on the base. If E35 is taken,
  every "E35" in this spec means the next free number, and AC 6 (a)'s line goes up by one from
  the base's count.
- **The upstream contract.** If T-016 has merged, its offline check (every path
  `tools/upstream_fields.py` derives from `src/risk.py` has an entry in
  `tests/upstream_baseline.json`) is a step of `lead/checks.py`. The sells this task reads are
  expected to trace to a path the baseline already holds (`pairs.[].txns.h24.sells` is in it at
  `4838fdd`). If that check goes red, stop BLOCKED: a re-freeze is not in this task's scope.
- **Not in parallel.** This task edits `src/risk.py`, `tests/test_risk.py`,
  `tests/test_http_telemetry.py`, `src/entry.py`, `src/pages.py` and the regenerated pages
  (`docs/SCORECARD.md`, `docs/OWNER.md` and `src/landing.html` among them). T-011, T-019 and
  T-013 are ordered before it. Never run it in parallel with T-016 or T-017 (`src/risk.py`),
  T-018 (`src/risk.py`, both test files and `docs/SCORECARD.md`), T-014 (`docs/SCORECARD.md`,
  `docs/OWNER.md`) or T-015 (`src/landing.html`).

**Other.** Write files with the Write or Edit tool, never shell heredocs (`CLAUDE.md`); those tools
decode backslash-u escapes into real characters (`lead/PITFALLS.md`). No digit followed by a
percent sign in any `lead/` file. Scratch files go in your own subfolder of the session scratchpad;
the rest of it belongs to other agents. E14 asks for an adversarial review of scoring-path changes:
the Level 3 red-team is that review.

## Amendments

### Release queue preparation (2026-10-11; criteria unchanged)

This is the retained original narrow specification. T-011 is deployed; T-019 is in fresh
review and T-013 has not started. Dispatch only after both dependencies are reviewed,
merged and published. Repeat the conflict search on that exact base and confirm the next
free E-number and decision-table count there, as Notes already require. The pre-registered
list comes from that base before the tests-only commit; old absolute figures are historical
expectations, not targets. Existing bands, the finite-positive in-scope SELLS condition,
critical liquidity gap, immutable older acceptance and no-live-fetch rule remain binding.

### Exact published dispatch base (2026-10-12)

T-011, T-019 and T-013 are independently reviewed, merged, published and verified.
The exact base is 7f796e41a4436f3a55f526ebd5a8193a1a0cd883. T-013's frozen source
b99f2e7 is merged as 46fb2a6; actual deployment 38156203366 runs every offline,
deployment and tagged smoke step, and the lead's tagged public readback passes.
Exact-head Linux preflight 38155937648 passes required jobs and 219 observed
upstream checks, with no unobserved or collapsed path. Full combined checks pass
all thirty-one steps. The decision table is still at sixty-one rows; E35 is free.

The lead repeats the conflict search on this exact base. No older assertion change
is added to named change (a). Existing T-013 acceptance remains immutable. AC 7's
exact-base zero-miss raw-byte reproduction and full actual in-scope request-based
pre-registration remain prerequisites before the executor's tests-only commit.
The filled main cache has 6,741 entries and must remain unchanged. Only replay is
allowed, never a fill or live call. Root corrects the two named stale Experiment C
passages after the reviewed merge and before publication, from actual new rows.
All earlier rules, bands, publication evidence and accepted residuals are unchanged.
