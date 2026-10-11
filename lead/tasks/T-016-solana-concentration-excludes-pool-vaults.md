---
id: T-016
title: Stop counting a Solana token's own liquidity pool as a whale in holder concentration
status: done              # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 2                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []           # none; shares files with T-011 to T-015, T-017, T-018: never in parallel
decisions: [ADR-0001]
backlog: none            # found by the 2026-10-07 investigation; the lead files it beside DECISIONS E31 after the merge
---

## Context

On Solana the engine reads holder concentration out of the RugCheck report, in
`_rugcheck_signals` (`src/risk.py`, about line 3463). It sums `pct` over the first ten entries of
`topHolders` (about line 3513), records the sum as `evidence.rugcheck.top10_holder_pct` (about
line 3630) and grades it (about lines 3724-3736): 70 or more is `critical` "Holdings are highly
concentrated" with the sentence "A handful of wallets could crash the price.", 50 or more is
`warn`, anything else `ok`. It never asks whether a holder is a liquidity pool. The same report
says so: `knownAccounts` tags pool accounts with `"type": "AMM"`, and `markets[]` lists each pool
with its own account and its two vaults. Nothing in `src/risk.py` reads either field today.

**Measured 2026-10-07** on seven RugCheck reports saved during the investigation (all HTTP 200)
and replayed offline through the engine's own `_rugcheck_signals`. On two brand-new pump-style
mints first seen that day, the top holder was the token's own Pump Fun AMM pool vault, holding
99.9 and 99.8 of every 100 tokens. The engine said `critical`, "Top 10 addresses hold 100.0... A
handful of wallets could crash the price", while the ten largest holders outside pools held 0.08
and 0.19 of every 100. The false critical adds a second bad category, so the RugCheck half of the
answer scores 58 instead of 48 (`_score`, about line 735: plus 10 per extra category). With a
stubbed market half modelled on a fresh pump pair (Notes), the full answer is `high` / 78 today
and `unknown` / 68 without the false signal. On the other five mints a pool vault sits in the
top ten, and the share outside pools is 2.4 to 7.8 points (of 100) lower than today's figure,
without crossing a band.

`find_new_hot_pools` defaults to Solana, so a brand-new pump launch is the token this product
hands out most often, and on it the engine tells an agent that a few wallets can dump when the
"wallet" is the pool itself. The false sentence reaches the signals, the score and, when it is the
driver of an `unknown`, the "Separately," clause of the recommendation (`_finalize`, about line
934).

Why Level 2 and not 3 (the lead's decision; the executor confirms all three, see Evidence):
`concentration` is not a critical dimension (`_CRITICAL_DIMENSIONS`, about line 651); every
Solana answer carries a `sellability` coverage gap filed before any early return (E24), so
`_finalize` can never return `low` or `medium` on Solana; and `bench/results.json` has no Solana
row (base 334, ethereum 140, bsc 102), so no published benchmark figure can move.

A second, older defect sits on the same field. `tests/test_coverage_matrix.py`,
`_obs_holder_concentration` (about line 258), reads `rc.get("top_holder_pct")`, a key the engine
has never written; the engine writes `top10_holder_pct`. The clause is dead. It cannot simply be
renamed: when RugCheck sends no holder list the engine writes `0.0` (the sum of nothing), so the
renamed clause would call both Solana reference answers covered and turn the matrix red. That
`0.0` is itself the E11 confusion: "no holder list" reported as "the top ten hold nothing".

## Goal

On Solana, holder concentration is computed over holders that are not liquidity pool accounts,
and the answer says what it left out. A fresh pump launch whose pool holds nearly all supply no
longer gets a critical "a handful of wallets" signal. When the report does not let the engine
tell pools from holders, the reading is today's, worded so it claims no wallets, and nothing moves
toward a lower rating.

## Scope

**In:**
- The rule in `_rugcheck_signals` (a helper function beside it is fine): which holders are pool
  accounts (AC 2), the share outside them (AC 1, AC 2), the fallback when pools cannot be told
  apart (AC 3), the messages, and the evidence fields (AC 4). Bands (70 and 50), signal names,
  severities and the `concentration` category stay as they are.
- `top10_holder_pct` written as null, not `0.0`, when RugCheck sent no holder entries (AC 4), so
  the coverage matrix's dead key can be fixed without moving any cell (named change (a), AC 6).
- Re-freezing `tests/upstream_baseline.json`, because the engine will read new RugCheck paths
  and the upstream contract job fails on any unmeasured one (named change (b), AC 7).
- The new acceptance-test file, its synthetic fixture, and its step in `test.yml`.

**Out:**
- Naming locked supply. `LOCKER`-tagged holders (Streamflow, Printr Stake Pool) stay in the share
  and are not named. A lock ends and its supply returns; counting it is the conservative reading.
  Naming it is a wording improvement for another task. `CLOB`-tagged order-book vaults likewise
  stay in the share unnamed (AC 2's exception).
- Using DexScreener's pairs. `_rugcheck_signals` receives only the RugCheck body; the report's own
  `markets[]` is the "pool the engine already knows for this token" (Notes say why).
- The EVM port of the exclusion (the finding's step 4). It belongs to W6, a feature, not to this
  fix.
- The bands, any other signal, `_score`, `_finalize`, `_CRITICAL_DIMENSIONS`, the gap taxonomy.
  No new data gap and no new `_our_coverage_gap` call site (Notes say why).
- Fixing `write_baseline`'s collapse refusal under `--write` in `tests/test_upstream_contract.py`,
  and watching the `knownAccounts` tag's `type` field upstream. Both are parked as backlog rows by
  the lead (Notes, the upstream contract hazard).
- `bench/`, `docs/`, `src/pages.py`, `src/entry.py`, `src/mcp_server.py`, README. The lead files
  the DECISIONS and BACKLOG rows after the merge.
- Running `bench/run_benchmark.py`, `publish_numbers.py --write`, `scorecard.py --write` or
  `regenerate-derived.sh` (Notes say why). Calling `vetagent.dev` in any way.

## Files in scope

- `src/risk.py`: `_rugcheck_signals` and an optional helper beside it. Nothing else in the file.
- Acceptance tests: `tests/test_solana_pool_holders.py` (new) and
  `tests/fixtures/rc_pump_pool_vault.json` (new, synthetic; shape in Notes).
- `.github/workflows/test.yml`: one new step for the new test, in exactly the shape of its
  neighbours (a comment, `- name: ...`, `run: python tests/test_solana_pool_holders.py`), placed
  before the step named "The deploy runs every step of this job before it deploys".
- **Named changes to existing tests** (from the conflict search). Only these; any other failing
  older test means BLOCKED:
  - **(a)** `tests/test_coverage_matrix.py`, `_obs_holder_concentration`: `rc.get("top_holder_pct")`
    becomes `rc.get("top10_holder_pct")`, and the docstring says the engine writes null when
    RugCheck sent no holder list, which is what lets a number there mean "a reading came back".
    No other line of the file changes. In its own commit, titled
    `T-016: named change (a) coverage matrix reads the key the engine writes`, committed after
    the fix commit (the one that writes null), never before it: renamed while the engine still
    writes `0.0`, the matrix exits 1 on "holder concentration on solana" (measured on a scratch
    copy, 2026-10-08). At the (a) commit `python tests/test_coverage_matrix.py` exits 0.
  - **(b)** `tests/upstream_baseline.json`: re-frozen once, after the fix, with
    `python tests/test_upstream_contract.py --write`, under the rules of AC 7. In its own commit,
    titled `T-016: named change (b) re-freeze the upstream contract baseline`.
  - Existing tests that see the change and must stay green unchanged: `tests/test_risk.py`,
    `test_solana_rugcheck_signals` (`rc_dangerous.json` holders carry only `pct`, so AC 3 keeps its
    critical; `rc_bonk.json` has no pool among its holders, so its `ok` and its score of 0 stay),
    `test_a_coverage_gap_scores_nothing`, `test_solana_holder_distribution_absence_is_a_gap`,
    `test_a_missing_holder_list_is_our_coverage_not_a_fact_about_the_token`,
    `test_every_data_gap_declares_which_of_three_things_it_is`; `tests/test_decisions_enforcement.py`
    (requires the new step); `tests/test_deploy_gate.py` (reads `test.yml` and fails on a line its
    reader does not recognise); `tests/test_advertised_coverage.py` (does not scan `src/risk.py`).

## Acceptance criteria

1. **The pool is not a whale (pre-registered).** With `tests/fixtures/rc_pump_pool_vault.json`,
   `risk._rugcheck_signals` files exactly one `concentration` signal: `ok`, "Holdings are well
   distributed". Its message gives the share outside pools to one decimal place (0.1), the pool
   share as AC 2 defines it (99.9), and the pool's `knownAccounts` name ("Pump Fun AMM"), and does
   not contain "wallet". No signal named "Holdings are highly concentrated" is filed. `risk._score`
   over the signals that call files is 48; at the tests-first commit it is 58. These figures were
   recorded before the fix from the saved body; if one differs, report it, do not tune the fixture.
2. **Which holders are pool accounts.** A holder is a pool account when any of these holds:
   (i) `knownAccounts[holder.owner].type` or (ii) `knownAccounts[holder.address].type` is the
   string "AMM" (compared after upper-casing; never by `name`); (iii) `holder.owner` equals the
   `pubkey` of an entry of `markets`; (iv) `holder.address` equals the `liquidityA` or `liquidityB`
   of an entry of `markets`. One exception wins over all four: a holder whose `owner` or
   `address` has a `knownAccounts` entry whose `type` is a string other than "AMM" (`LOCKER`,
   `CREATOR`, `CLOB` or any other) is never a pool account. RugCheck lists Manifest order-book
   vaults in `markets` (Notes), so without it (iv) would drop them; counting them is the
   conservative reading. The share outside pools is the sum of `pct` over the first ten holders,
   in the order RugCheck sent them, that are not pool accounts. The pool share is the sum of `pct`
   over every pool account among all the holders RugCheck sent (up to 20), each holder counted
   once however many clauses match it. Tests, one per case: each of (i) to (iv) alone excludes
   the vault (the other evidence removed from the body); a holder tagged `LOCKER` (including one
   whose name contains "Pool", such as "Printr Stake Pool"), `CREATOR` or `CLOB` stays counted;
   a `CLOB`-tagged vault that is also the `liquidityA` of a `markets` entry with `marketType`
   "manifest" stays in the outside share; twenty holders with pool accounts at positions 2, 5 and
   15, one of them matched by two clauses: the outside share includes the 11th and 12th holders,
   and the message's pool share is the three pools' sum, each once (the `pct` values chosen so
   that summing only the first ten, or counting the double match twice, prints a different
   figure at one decimal place); and one case built on `rc_bonk.json`'s own `knownAccounts` and
   `markets` (the first market whose `pubkey` is tagged AMM there, chosen in code, with a
   constructed holder list) excludes that pool's vault.
3. **When pools cannot be told apart, nothing moves down (fail-closed).** When the report gives
   no pool evidence (no entry of `markets` is a dict with a string `pubkey`, `liquidityA` or
   `liquidityB`, and no `knownAccounts` value is a dict whose `type` upper-cases to "AMM"), or when
   any of the first ten holders carries neither an `owner` nor an `address` string, the reading is
   today's: the same share (first ten as sent), band, name and severity. Its message says that
   RugCheck did not identify which holders are liquidity pools, so the share may include the
   token's own pool, and does not contain "wallet". AC 2's clause tests are not fallbacks: an AMM
   tag with `markets` removed, or `markets` with the tags removed, is pool evidence. Tested at each
   band (critical, warn, ok), and once on `rc_pyusd.json`'s own `knownAccounts` (one `CREATOR`
   entry) and `markets` (null) with a constructed holder list: the fallback, with today's share,
   this wording, and `top10_outside_pools_pct` null. Malformed shapes do not raise and count as
   absent: `knownAccounts` as a list or a string, `markets` as a dict, non-dict entries, a
   non-string `type`, `owner` or `address`. `pct` is read exactly as `_num` (about line 148) reads
   it today, for both figures: a numeric string counts as its number; null, a non-numeric string
   or a list counts 0. Tested with one numeric-string case (its band is today's) and one
   non-numeric case. `rc_dangerous.json` still yields a `critical` concentration signal.
4. **The evidence carries both figures, and an absence is not a zero.**
   `evidence.rugcheck.top10_holder_pct` is today's figure (first ten as sent, four significant
   digits) and is null, not `0.0`, when RugCheck sent no holder entries. A new key
   `evidence.rugcheck.top10_outside_pools_pct` carries the AC 2 share at the same precision; it is
   null when RugCheck sent no holder entries and in every AC 3 case. No other key of
   `evidence.rugcheck` changes. With no holder list, every signal and data gap is as today (E31's
   coverage gap and its `info` signal). With `rc_bonk.json`, both keys are equal (38.46).
5. **The full answer, end to end.** Through `risk.assess` with the network replaced (the
   `install_stub` pattern in `tests/test_risk.py`), the fixture plus the DexScreener pair in Notes:
   `risk_level` is `high` or `unknown`, never `low` or `medium`; no `concentration` signal is
   `critical`; and removing the concentration signal from `signals` and re-scoring with
   `risk._score` gives the same `risk_score`. Pre-registered: `high` / 78 at the tests-first
   commit, `unknown` / 68 at the head. With `rc_bonk.json` and `ds_bonk.json`, the concentration
   signal is still `ok` and `risk_score` is still 0.
6. **The coverage matrix reads the real key and no cell moves (named change (a)).**
   `python tests/test_coverage_matrix.py` exits 0, and its lines containing ": scorecard says "
   are identical at the tests-first commit and at the head. With the engine mutated to write
   `0.0` again for a missing holder list, it exits 1 on "holder concentration on solana".
7. **The upstream contract still watches every path (named change (b)).** A check in the new
   test file, offline: every path `tools/upstream_fields.py` derives from `src/risk.py`, for each
   source, has an entry in `tests/upstream_baseline.json`, and the baseline has no path the engine
   no longer reads. It is red at the fix commit and green after the re-freeze. The re-freeze is
   accepted only if, against the committed baseline: (1) no path already in the baseline has its
   `key` cross 1.0 in either direction (one at 1.0 stays at 1.0, one below stays below); (2) no
   new path under `topHolders.[]` or `markets.[]` is frozen at `key` 1.0; (3) every RugCheck path
   new in this task was observed with at least one non-null type; (4) no path already in the
   baseline lost a non-null type it had; (5) no path's `value` fell by more than 0.4, the file's
   `VALUE_BAND`. A run that breaks any rule is not committed: discard it
   (`git checkout -- tests/upstream_baseline.json`) and run again at least an hour later (holder
   coverage moves over hours). If three runs all break a rule, stop: BLOCKED with their diffs.
   `python tests/test_upstream_contract.py` (live) then exits 0 once at the head.
8. **Contract and checks.** The first commit adds only `tests/test_solana_pool_holders.py` and its
   fixture; at that commit the file runs without a traceback and is red on at least AC 1, AC 2's
   four clauses, AC 3's wording and AC 4's null. The `test.yml` step comes after that commit
   (`tests/test_decisions_enforcement.py` is red until it lands). The fix commit's message says
   what the red looked like and that the benchmark cannot measure this change (it has no Solana
   row). Named changes (a) and (b) are each in their own commit as titled above, both after the
   fix commit. The new file makes no network call (it fails if `urllib.request.urlopen` is
   reached), writes nothing, and runs in under 10 seconds. At
   the head, `python lead/checks.py` passes every step (one more than the baseline in
   `lead/STATE.md` at dispatch), exits 0 and leaves the tree clean.

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_solana_pool_holders.py` on it:
  which checks fail, and the exit status.
- At the head: the same command (all pass, with the count); `python lead/checks.py` run on its own
  with output to a log (`lead/PITFALLS.md`, 2026-10-02): the summary line and the exit status;
  then `git status --short` (empty).
- AC 1 and AC 5's figures at both commits: the RugCheck-half score, and `risk_level` /
  `risk_score` / `driver` of the stubbed full answer.
- The three Level 2 facts, each by a command: `git grep -n "_rugcheck_signals(" -- src/` (one
  call, under `elif _looks_solana(address)` in `assess`); `python tests/test_risk.py` output for
  `test_solana_never_claims_a_sell_was_tested`; and the chain counts of `bench/results.json`
  (no Solana row). If any of the three does not hold, stop: BLOCKED, because the level is wrong.
- AC 6: the two outputs' ": scorecard says " lines diffed (empty diff), and the mutant's red.
- AC 7: for every `--write` run, kept or discarded, its output and the rule it broke, if any;
  for the kept one, `git diff --stat`, the list of paths added to the RugCheck section with their
  observed `key` and types, and every existing path whose entry changed, before and after, with
  each of the five rules checked against them; the live run's summary line.
- Mutants, each shown to turn the new file (or the matrix) red, restored after each with
  `__pycache__` cleared (`CLAUDE.md`): the exclusion matching `name` containing "Pool" instead of
  `type`; the outside share taken as the top ten minus pools (no refill); the non-AMM exception
  removed (the manifest vault leaves the share); the pool share summed over the first ten only;
  the AC 3 fallback dropping the signal or excluding nothing while claiming "outside liquidity
  pools"; `0.0` restored for a missing holder list (AC 6).
- `git diff --stat <base>..HEAD`: only files in scope. Added and changed lines contain no
  non-ASCII characters; pre-existing English punctuation remains unchanged (amendment c).

## Notes

- **Field names, confirmed 2026-10-07** on the seven saved reports and on `tests/fixtures/
  rc_bonk.json`. `topHolders[]` entries carry `address` (the token account), `owner` (who owns
  it), `pct` (a float, share of supply out of 100), `amount`, `decimals`, `insider`, `uiAmount`,
  `uiAmountString`; RugCheck sends up to 20. `knownAccounts` is an object keyed by account
  address, each value `{"name": ..., "type": ...}`; types seen: `AMM` (names include "Pump Fun AMM",
  "Pump Fun", "Meteora DLMM Pool", "Meteora DAMM v2 Pool", "Raydium CLMM Pool", "Orca AMM"),
  `LOCKER` ("Streamflow Vault", "Printr Stake Pool"), `CREATOR`, `CLOB` ("Manifest Market").
  `markets[]` entries carry `pubkey` (the pool), `marketType`, `mintA`, `mintB`, `liquidityA` and
  `liquidityB` (the two vault token accounts), `liquidityAAccount` and `liquidityBAccount` (objects
  with the vault's `owner`, `mint`, `amount`), `lp` and more. On a Pump Fun AMM pool the vault
  holder's `owner` is tagged, its `address` is not, and both match `markets[]` (`owner` is the
  pool's `pubkey`, `address` its `liquidityA`); Meteora DLMM vaults are tagged on both. In every
  saved report, each AMM-tagged holder among the top ten was also matched by `markets[]`, and no
  pool-matched holder carried a non-AMM tag, so AC 2's exception moves no replay figure below.
  Manifest order books appear in `markets[]` too (`marketType` "manifest", three in one saved
  report and one in another): their `liquidityA` and `liquidityB` and the vaults' owner are
  tagged `CLOB` "Manifest Market", the market's `pubkey` is untagged and is not the vaults'
  owner, so of the four clauses only (iv) reaches a Manifest vault, and the exception keeps it
  counted. Meteora DAMM v2 vaults are owned by one shared, untagged authority, not by the pool's
  `pubkey`, so (iii) misses them and (ii) and (iv) catch them. You may make at most
  three live RugCheck report reads to re-confirm this; commit nothing from them.
- **The fixture** (`tests/fixtures/rc_pump_pool_vault.json`, synthetic, invented base58-looking
  addresses, ASCII only): `mint` (ending in "pump"); `tokenProgram` and `token_extensions` copied
  from `rc_bonk.json`; `score` 2719, `score_normalised` 32 (at or above `_RUGCHECK_WARN_BAND`, so
  no time-dependent withholding); `rugged` false; `mintAuthority` and `freezeAuthority` null;
  `totalHolders` 22; `verification` null; `lockers` {}; `risks` one entry, name "Low Liquidity",
  level "danger"; `topHolders` 20 entries, the first with `owner` P, `address` V and `pct` 99.922,
  the rest small (the second 0.078, the others well under 0.001), with distinct owners and
  addresses; `knownAccounts` {P: Pump Fun AMM / AMM, a creator account: Creator / CREATOR, a third:
  Printr Stake Pool / LOCKER}; `markets` one entry {`pubkey` P, `marketType` "pump_fun_amm",
  `mintA` the mint, `mintB` the wrapped SOL mint, `liquidityA` V, `liquidityB` another address}.
  This reproduces the saved body's RugCheck half: 58 with today's code, 48 without the false
  signal (measured on both the saved body and this shape).
- **The DexScreener pair for AC 5** (the stub measured on 2026-10-07): one pair, `chainId`
  "solana", `dexId` "pumpswap", `baseToken.address` the fixture's mint, `quoteToken` wrapped SOL,
  `priceUsd` "0.00001", `liquidity.usd` 4000, `volume.h24` 3000 and `h1` 100, `txns.h24` 40 buys
  and 30 sells and `h1` 5 and 4, `priceChange.h24` 5, `pairCreatedAt` one day before now (epoch
  ms). With it the saved bodies gave `high` / 78 (driver liquidity; bad categories concentration,
  freshness, liquidity, rugcheck) today and `unknown` / 68 without the false signal. The fall is
  10 because the corroboration cap of 30 does not bind here; where five or more categories are
  bad, removing one changes nothing.
- **Replay of the rule on the seven saved bodies** (offline, the rule above, refill included):
  the two fresh mints read 100.0 and 99.98 today and 0.08 and 0.19 outside pools; the five others
  25.16 to 20.45, 30.94 to 26.46, 19.15 to 14.26, 17.61 to 15.21, 35.36 to 27.54, all `ok` before
  and after. On the tracked fixtures nothing moves: `rc_bonk.json` has no pool among its holders,
  `rc_dangerous.json` has holders without owner or address, and `rc_bern.json`, `rc_pyusd.json`
  and both Solana coverage-matrix recordings carry no holder list. These bodies are not in the
  repository and their figures are context, not acceptance targets.
- **Why the fallback keeps today's reading (the lead's choice between two options).** Filing a
  gap instead would remove the signal's score on exactly the tokens the engine cannot read, which
  is a move toward a lower rating; `concentration` is not a critical dimension, so the gap would
  fail nothing closed. It would also add an `_our_coverage_gap` call site, which
  `test_every_data_gap_declares_which_of_three_things_it_is` requires its sweep to reach, and the
  taxonomy has exactly three kinds (E27). And the case is rare: every real body with holders seen
  here carried both AMM tags and `markets` entries. So the reading stays and only its sentence
  changes, to say what was not checked rather than claim wallets. The trigger is the absence of
  pool evidence, not of `knownAccounts`: PYUSD's two recordings carry a `knownAccounts` with one
  `CREATOR` entry and a null `markets`, and on a fresh mint shaped like that, a measured "outside
  liquidity pools" share would be the pool vault reported as not a pool, the E11 confusion again.
- **Why `markets[]` and not DexScreener's pairs.** `_rugcheck_signals` is called with the RugCheck
  body alone; passing pairs in would add a seam and a signature change for no measured gain
  (`markets[]` matched every tagged vault seen), and `markets[]` also names vault addresses, which
  a DexScreener pair address does not.
- **Why null and not `0.0`.** "RugCheck sent no holder list" is an unobserved dimension (E31: our
  coverage), and `0.0` states an observed absence. Nothing in the repository reads the key except
  the dead observer (searched). A caller that reads the key as a number now gets null for those
  answers; that is the field becoming true, and the lead notes it with the DECISIONS row. It is
  what lets named change (a) move no cell.
- **The upstream contract hazard, and why (b) is in this task.** `tools/upstream_fields.py` derives
  every path the engine reads from `src/risk.py`; the reads this task adds (`knownAccounts`,
  `markets` and its `pubkey`, `liquidityA`, `liquidityB`, `topHolders[].owner` and `.address`, or
  whatever your code reads) become new RugCheck paths. `test.yml`'s `upstream-contract` job fails
  on any path missing from the baseline, on every push. `production.yml` then records the day as
  red in `bench/production/upstream_contract.json`, and
  `tests/test_upstream_contract_is_observed.py`, a step of the offline job and of the deploy gate,
  fails while any red day is in the record's 30-day history: one unre-frozen push would block
  deploys for a month. `lead/checks.py` cannot see the live job, which is why AC 7 adds the offline
  check. The re-freeze makes live requests to RugCheck, honeypot.is, DexScreener and GeckoTerminal
  (not `vetagent.dev`), takes a few minutes, refuses a partial run, and writes only that file;
  precedent `cfa42f6` re-froze it the same way when `detectedAt` was added. A bad freeze is a
  trap set for a later day, in both directions, and AC 7's five rules are its two halves. R1
  (`test_generated_field_contract`, about line 462) fails on sight for any path frozen at `key`
  1.0 that later arrives in fewer probes, so a path that varies must not be frozen at 1.0 on a
  day every probe happened to carry it: `topHolders.[].pct` sits at 0.75 today (USDC, USDT, PYUSD
  and WSOL carry no holder list), `risks.[]` at 0.6875, several honeypot.is and GeckoTerminal
  paths at 0.875; the new `topHolders.[]` paths follow `topHolders.[].pct`, and the new
  `markets.[]` paths sit below 1.0 on an ordinary day too (PYUSD's `markets` is null in both of
  its recordings). Top-level keys differ: RugCheck sends them in every probe, null or not
  (`topHolders` is at `key` 1.0 and `value` 0.75), so `knownAccounts` and `markets` at `key` 1.0
  are expected. R3 fails on sight for any type the baseline lacks, so a type lost at the
  freeze, or a new path frozen with none (RugCheck's holder lists come and go over hours, E31),
  is red the day it returns. The other half is a trough frozen in: a path that falls below 1.0,
  or loses its share, stops being watched. The script does not protect against either:
  `write_baseline` (about line 720) refuses when `_COLLAPSES` is non-empty, but `main` (about line
  805) returns `write_baseline()` before `test_generated_field_contract`, the only filler of that
  list, ever runs, so under `--write` the refusal never fires; only the partial-run refusal does.
  AC 7's rules are the only guard, which is why every run is checked by hand. The field tool
  does not follow a read keyed by a variable (`Fields.resolve`, about line 143): on a scratch copy
  with a plausible implementation (2026-10-08) it derived seven new RugCheck paths,
  `knownAccounts`, `markets`, `markets.[].pubkey`, `.liquidityA`, `.liquidityB`,
  `topHolders.[].owner` and `.address`, and none for the tag's `type`. That field is
  unwatched (a residual, stated): a rename there would leave (iii) and (iv) working, switch off
  AC 2's exception, and with `markets` gone too land in AC 3's fallback. Both the `--write`
  collapse-refusal defect in `tests/test_upstream_contract.py` and the unwatched `type` field are
  out of scope for this task: do not fix either; the lead parks each as a backlog row. The
  offline check also guards every task that edits `src/risk.py` and merges after this one (in
  this batch: T-011, T-012, T-013, T-017 and T-018): any of them that adds an upstream read turns
  that check red and needs a re-freeze under AC 7's rules before it merges. None of their scopes
  lists the baseline file, so for them that is BLOCKED and a spec amendment, never a quiet
  re-freeze.
- **Not in parallel (batch check, 2026-10-08).** `src/risk.py` is edited by T-011, T-012, T-013,
  T-017 and T-018, and `.github/workflows/test.yml` gains a step from T-011, T-014, T-015 and
  T-017, each before the same anchor step. Never run this task in parallel with any of them. No
  order between them is required: whichever lands first moves the other's base (line numbers,
  and the `lead/checks.py` step count AC 8 counts from the baseline at dispatch).
- **No benchmark run.** `_rugcheck_signals` runs only for Solana addresses and the benchmark has
  no Solana row, so a re-run could only measure upstream drift (T-011 makes it deterministic). No
  published number moves. After the deploy, some Solana answers move from `high` to `unknown`; the
  production verdict record measures live traffic and is not pre-registered here.
- **Residual, outside the bar:** supply that one liquidity provider places in a pool is that
  provider's to withdraw. That is a liquidity-provider risk, and "LP lock / burn" was measured and
  rejected as a dimension (`bench/scorecard.py`), not a concentration one.
- Tag names are third-party text read aloud: pass them through `_ascii_safe`, at most three
  distinct names. Do not touch the comment block that
  `test_the_settling_figures_in_the_engine_are_the_measured_ones` reads (from "A clean score from
  a mint this upstream has only just seen" to `age_minutes = ...`). The string "GoPlus" must not
  appear in `src/` (B2, `tests/test_risk.py`). Every data-gap reason goes through `_gap`.
- **Conflict search (2026-10-08), repeat with:** `git grep -n "_rugcheck_signals" -- tests/`;
  `git grep -n "top10_holder_pct\|top_holder_pct\|top10" -- .` (bench/cache excluded);
  `git grep -n -i "Top 10 addresses\|crash the price\|well distributed\|highly concentrated" -- .`
  (only `src/risk.py`); `git grep -n "concentration" -- tests/ bench/*.py tools/ src/`;
  `git grep -n "rc_bonk\|rc_dangerous\|rc_bern\|rc_pyusd" -- tests/` (each hit read);
  `git grep -n "topHolders\|knownAccounts\|liquidityA\|totalHolders" -- tests/ tools/ bench/*.py
  .github/`; `git grep -n -l -i "rugcheck" -- tests/`; `git grep -n "upstream_fields\|upstream_baseline"
  -- tests/ tools/ bench/ .github/ docs/`; `git grep -n -i "wallet" -- src/risk.py` (no other
  concentration message uses it); and `tools/upstream_fields.py` against
  `tests/upstream_baseline.json` (all four sources match today, 123 paths).
- Write files with the Write or Edit tool, not shell heredocs (`CLAUDE.md`). The Write and Edit
  tools decode backslash-u escapes into real characters (`lead/PITFALLS.md`). Scratch files go in
  your own subfolder of the session scratchpad; the rest of it belongs to other agents.

## Amendments

### (c) Preserve existing English punctuation (2026-10-11)

The original source already contains non-ASCII English punctuation: fifteen characters in
src/risk.py and one in tests/test_coverage_matrix.py. Requiring the entire changed files to
be ASCII would force unrelated edits outside the task's scope. Compare original and final
text, require every added or changed line to be ASCII, and retain the original punctuation.
The English-only project guard still applies to every repository file. This changes no
holder fixture, behavior, acceptance assertion, band or upstream-baseline requirement.
