---
id: T-013
title: Look up Uniswap V4 pools by their full id, not the 48-character display string
status: in_review        # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: M                  # S | M (split anything larger)
depends_on: [T-011, T-019]   # T-011 builds --replay and --fill; T-019 runs the fill and re-baselines
decisions: [ADR-0001]
backlog: none            # NEW, found by the 2026-10-07 investigation; related to E27 and W58; no BACKLOG row yet
---

## Context

When honeypot.is calls a token a honeypot while the chain shows sells clearing on a live pool,
the engine settles the dispute by counting **distinct sellers** in the last 24 hours (the
wash-trading guard, `test_overturning_a_honeypot_verdict_needs_distinct_sellers`; DECISIONS E23
for the holder-share release). DexScreener does not report that count, so `_distinct_sellers`
(`src/risk.py`, about line 2583) asks GeckoTerminal for the picked pool, through
`_onchain_sources("networks/%s/pools/%s" % (net, _urlq(pool)))` (keyed CoinGecko first when a
key is configured, then keyless GeckoTerminal). It asks whenever honeypot.is says `isHoneypot`
true and the pair carries no seller count, E23's fatal holder-share band included. With no
count, `_honeypot_signals` (contested branch, about line 2805) files `upstream request failed:
no distinct-seller count to settle a contested honeypot verdict` and the warn "Honeypot verdict
contested, not settled", whose message ends "Retrying shortly may settle it." The verdict is
`unknown`.

The pool id it asks with is not the pool's id. `_liquidity_signals` (about line 1691) stores
`evidence["best_pair"]["pair_address"] = _ascii_safe(best.get("pairAddress") or
best.get("pool_id"), 48)`. `_ascii_safe` (about line 495) is the display sanitizer for upstream
text: past `limit` characters it cuts and appends `...`. A Uniswap V4 pool id is 66 characters
(`0x` + 64 hex), so it becomes its first 48 characters plus `...`, and `_distinct_sellers` reads
that display string back. `_urlq` leaves `.` unescaped, so the request goes to
`.../networks/<net>/pools/0x<46 hex>...`. GeckoTerminal answers 404 for that (investigation,
2026-10-07, tried for THQ and USDT0), the answer is not a dict, the count stays `None`, and the
verdict is `unknown` on every call: the same truncated id goes out on every retry. E27 defines
`upstream request failed` as ours and temporary, "a retry is the cure"; here no retry can be.

The honeypot.is `&pair=` retry in `assess` (about lines 4144 to 4152) reads the same rendered
string. It checks only `startswith("0x")` and a length of 42, and interpolates the value with
no escaping. `_ascii_safe` keeps `&`, `#` and `?`. **Measured offline for this spec
(2026-10-08):** on a failed simulation, a `pairAddress` of `0x` + 38 hex + `&x` is sent as
`...&pair=0x<38 hex>&x`, adding a parameter to the honeypot.is request, and `0x` + 39 hex + `g`
is sent as well. The lead's decision for this task (the raw pool id, validated, for every
upstream lookup) covers this lookup too.

**Measured for this spec (2026-10-08, offline, stubbed fetch, scratch only):** a contested
honeypot on a 66-character pool requests `https://api.geckoterminal.com/api/v2/networks/eth/pools/`
followed by 46 hex digits and `...`, and returns `unknown` 30 with that gap and the retry
sentence. The same token on a 42-character checksummed pool requests the id unchanged, case
kept, and returns `medium` 30.

**In the benchmark** (`bench/results.json` at `4838fdd`): 88 of 576 rows carry an `engine_pool`
ending in `...`. Every row with the distinct-seller gap is one of them: THQ, USDT0 and Surplus
(base) and RALLY (ethereum), all `unknown`. A fifth V4 row, ROBOTMONEY (base), makes the same
failing lookup and is `high` 100 on E23's fatal band (195 of 623 tested holders), where the count
is never read. The investigation replayed the benchmark at the frozen clock with the full-id
counts it read live on 2026-10-07 (THQ 24, USDT0 36, Surplus 117, RALLY 29): THQ, USDT0 and RALLY
`unknown` to `medium`, Surplus `unknown` to `low` (released by E23 at 4 of 688), unknown 122 to 118
of 576, false positives and false blocks unchanged. Not re-measured for this spec.

**Why it needs T-011 and T-019.** Neither the truncated nor the full-id lookup for these five
pools is in `bench/cache/` at `4838fdd` (checked: none of the 6,647 cached URLs contains `...`,
and none is one of the five full-id URLs). `bench/fetcher.py` caches successes only, so today the
truncated 404 is re-asked live on every run (T-019's fill may store it as a dated 404 entry),
and after the fix the full-id answers would be read live on whatever
day the benchmark runs. T-011 makes the benchmark a replay with a pinned clock that lists cache
misses instead of fetching, and builds `--fill FILE`, which fetches exactly a listed set of URLs,
once each, as dated entries. T-019 ("Fill the frozen benchmark's cache misses once, and
re-baseline the published benchmark on it") runs that fill once and commits the re-baselined
results, so at this task's base a replay has no miss. The five full-id answers then enter the
cache once, dated, through `--fill` on exactly those URLs (AC 6).

**Case matters for the cache.** The 49 seller lookups and the 368 `&pair=` retries already in
`bench/cache/` all carry `0x` + 40 hex ids, most of them checksummed (mixed case), and the cache
key is the exact URL. A fix that changed the case of the id would change URLs that work today.

## Goal

A contested honeypot verdict on a Uniswap V4 pool asks GeckoTerminal about the pool by its full
id, so it settles under the existing rules instead of coming back `unknown` with a retry
instruction no retry can satisfy. No upstream request carries a string that is not a pool id.
Nothing else in the answer changes, and the benchmark movement is measured on the frozen replay
and published in the project's order.

## Scope

**In:**
- `src/risk.py`: one validation, applied to the raw upstream pool id before any lookup. The seller
  lookup sends the raw id only when it is `0x` followed by exactly 40 or exactly 64 hexadecimal
  digits, upper or lower case, exactly as upstream gave it. The `&pair=` retry sends it only when
  it is `0x` + exactly 40 hex digits, exactly as given. The rendered `pair_address` stays what it
  is today. The shape is fixed in "Files in scope". The two comments named in AC 5 are corrected.
- `tests/test_risk.py`: the acceptance tests, and named change (a).
- The benchmark replay with one dated cache-add through T-011's `--fill` (AC 6), and the pages
  `regenerate-derived.sh regenerate` rewrites from it (AC 7).

**Out:**
- Re-filing a GeckoTerminal 404 on a pool lookup as `about the token` (lead decision: a 404 for a
  brand-new pool may be indexing lag, so it is not obviously permanent). The gap taxonomy, the
  contested gap's wording and the sentence "Retrying shortly may settle it." stay as they are. They
  stop appearing for these rows because the lookup now succeeds.
- Showing the full id in the answer. The verbose `pair_address` keeps its 48-character rendering,
  so the benchmark's `engine_pool` and the published pool-agreement figure do not move (follow-up
  1 in Notes).
- Sending a V4 id in the honeypot.is `&pair=` retry. It stays limited to `0x` + 40 hex: whether
  honeypot.is accepts a V4 pool id is unmeasured, and sending one would add a request.
- `find_new_hot_pools`' `pool_id` rendering (follow-up 2).
- E23's cuts, the $5,000 / 20 sells / 15 ratio floor and the 10-distinct-seller bar. They are
  frozen, and changing them needs the Owner's sign-off.
- `bench/fetcher.py`, `bench/run_benchmark.py` and T-011's mechanism. If the cache-add needs a
  change there, that is BLOCKED.
- T-019's fill of the base's misses. This task fills only its own five URLs (AC 6).
- `tools/owner.py`'s 2026-09-14 correction-log entry ("It condemned real tokens for our own
  outage ... THQ 28"), and `docs/OWNER.md`, which is generated from it. They stay unchanged: the
  entry names no rate limit, and its point, that the failure was ours and not the token's, holds
  for THQ and Surplus too (a defect of ours rather than a rate limit).
- `docs/BACKLOG.md` and `docs/DECISIONS.md`. The lead records the item after the merge.
- Any call to `vetagent.dev`. Nothing here needs production.

## Files in scope

- `src/risk.py`, only these places:
  - one new module-level validation helper, placed beside `_urlq` (about line 543);
  - `_distinct_sellers` (about line 2583), whose shape becomes
    `_distinct_sellers(hp, evidence, pool_id=None)`. When `pool_id` is given (not None), only it
    is validated and, if valid, used. When it is None, the validated
    `evidence["best_pair"]["pair_address"]` is used, which keeps the direct call in
    `test_a_keyed_fallback_escapes_the_shared_egress_limit` (about line 3557: a valid lowercase
    42-character id, count read through the keyed source) working unchanged;
  - in `assess` (about line 3953), only what carries the picked pair's raw id from where
    `_liquidity_signals` is called (about line 4069) to the `&pair=` retry and the
    `_distinct_sellers` call (about lines 4144 to 4158);
  - `_liquidity_signals` (about line 1674): its `pair_address` rendering stays byte for byte; it
    may return the raw id to `assess`;
  - the comment over the contested branch in `_honeypot_signals` (about line 2795), and the
    comment over the slim `pair_address` pop at the end of `assess` (about line 4218).

  The raw id is never stored in `evidence`, in a new context variable or in any module state.
  Keep the request built through `_onchain_sources("networks/%s/pools/%s" % ...)`, and keep the
  response read at `data.attributes.transactions.h24.sellers`: `tools/upstream_fields.py`
  derives the upstream-contract test's tables from those two.
- Acceptance tests: new `test_*` functions in `tests/test_risk.py`. `main()` discovers them by
  name, and the file is already a step of `test.yml`, so no workflow changes.
- Generated, never edited by hand: `bench/results.json` and `bench/results.md` (and
  `bench/access_log.json` if the run rewrites it) from AC 6's final replay; then whatever
  `bash .github/scripts/regenerate-derived.sh regenerate` rewrites. Expected: `README.md`,
  `docs/EXPERIMENT_C.md`, `docs/SCORECARD.md`, `docs/OWNER.md`, `src/entry.py`,
  `src/landing.html`, `src/pages.py`. Do not commit a file whose only change is its date or
  its recent-commit list: the bots regenerate those on the UTC date.
- **Named changes to existing tests** (from the conflict search). Only these; any other failing
  older test means BLOCKED:
  - **(a)** `tests/test_risk.py`, `test_a_seller_count_nobody_took_cannot_overturn_a_honeypot`:
    comment only. In the comment above the check "nor high on our own outage: it is unknown"
    (about lines 2943 to 2946), the sentence "They were condemned because GeckoTerminal answered
    429 that minute." is replaced by the measured account in AC 5. No check name, stub, input or
    assertion changes. It goes in its own commit, titled `T-013: named change (a)`.

## Acceptance criteria

1. **The full id reaches the lookup, byte for byte.** Take a stubbed assessment (`risk._fetch_json`
   replaced, every URL recorded, no network) of a contested honeypot. Build it like
   `test_a_seller_count_nobody_took_cannot_overturn_a_honeypot`: an ethereum pair at $60,000 with
   100 buys and 40 sells, and honeypot.is `isHoneypot` true with holder share 36 of 400, which
   E23 neither releases nor makes fatal. Give the DexScreener pair a 66-character `pairAddress`
   (`0x` + 64 lowercase hex). The stub answers DexScreener's token request with the pair,
   honeypot.is with that answer, and None to every other URL unless a criterion says otherwise.
   "The seller path" below means: honeypot.is says `isHoneypot` true and the pair carries no
   seller count, E23's fatal band included. Then:
   - the seller lookup requests exactly
     `https://api.geckoterminal.com/api/v2/networks/eth/pools/<the 66-character id>`;
   - with a CoinGecko key configured (`risk.configure`, the key the keyed-fallback test uses,
     restored in a `finally` as that test does), the first lookup is exactly
     `https://api.coingecko.com/api/v3/onchain/networks/eth/pools/<the id>`;
   - no URL requested during the assessment contains `...`;
   - with a 42-character checksummed (mixed-case) `pairAddress`, both lookup URLs carry the id
     exactly as given. On a failed simulation the honeypot.is retry URL ends with `&pair=` and
     that id, exactly as given. With the 66-character id no `&pair=` request is made, as today;
   - the request count does not change: at most one seller request per source on the seller path,
     and none off it (`isHoneypot` not true, or a seller count already present).
2. **A contested V4 verdict settles under the existing rules.** Use the same stub and the
   66-character id. GeckoTerminal answers
   `{"data": {"attributes": {"transactions": {"h24": {"sellers": N}}}}}` only when the URL ends
   with the full id, and None for anything else, the way the real service answers:
   - N = 30: `risk_level` is `medium`. The honeypot signal is the `warn` "Upstream calls this a
     honeypot, the chain disagrees". No `data_gaps` reason contains `distinct-seller`, no signal
     message contains `Retrying shortly`, and `evidence.best_pair.sellers_24h` is 30;
   - N = 3: `high`, with the `fatal` "Honeypot" signal (fewer than 10 distinct sellers settle
     nothing);
   - holder share 4 of 688, answer built the way `hp_with` builds it in
     `test_a_honeypot_flag_is_read_by_its_holder_share`, and N = 117: the flag is released to
     `info` under E23, with the numbers in the sentence and
     `contradicted_by_chain.released_by_holder_share` true, as for a 42-character pool. The
     verdict is not `unknown`;
   - holder share 195 of 623 and N = 500: `high`, `fatal`, whatever the count;
   - every lookup answering None: `unknown`, with today's contested gap (it starts
     `upstream request failed` and contains `distinct-seller`), never `low` or `medium`.
3. **A string that is not a pool id is never sent.** Use each of these as `pairAddress`:
   - `0x` + 63 hex digits, and `0x` + 65 hex digits;
   - `0x` + 39 hex digits + `g`; `0x` + 38 hex digits + `&x`; `0x` + 20 hex digits + `_` + 19 hex
     digits; `0x` + 39 hex digits + the Arabic-Indic digit one, U+0661 (in the test,
     `chr(0x0661)`);
   - the 51-character display form of a 66-character id (its first 48 characters + `...`);
   - `0x` + 40 hex digits + `/../tokens`;
   - `0x` + 40 hex digits followed by each of `?`, `#`, a space, and a newline; and a space
     followed by `0x` + 40 hex digits;
   - `0x` + 4,000 hex digits;
   - the empty string, and the key missing.

   For each, two runs of the AC 1 stub:
   - on the seller path, with the stub answering
     `{"data": {"attributes": {"transactions": {"h24": {"sellers": 30}}}}}` to **every** URL
     containing `/pools/` (so a malformed id that is sent comes back `medium`): no URL containing
     `/pools/` is requested, and the verdict is `unknown` with today's contested gap, never `low`
     or `medium`;
   - on a failed simulation (honeypot.is answering `simulationSuccess` false with a `BUY_FAILED`
     error, as the `&pair=` retry test about line 941 builds it): no request contains `&pair=`.
4. **The answer is unchanged apart from the verdict.** These checks pin today's behaviour, so they
   are green at the tests-first commit and must stay green. Run them for the 66-character id on
   the contested path (N = 30) and on a clean simulation (`isHoneypot` false):
   - the verbose `evidence.best_pair.pair_address` is the id's first 48 characters followed by
     `...`. For the 42-character checksummed id it is the id itself;
   - the verbose `best_pair` keys are exactly today's ten: `buys_24h`, `chain`, `dex`,
     `liquidity_usd`, `pair_address`, `pair_created_at`, `price_usd`, `sellers_24h`, `sells_24h`,
     `volume_24h_usd`. The slim keys are the same nine without `pair_address`;
   - the full 66-character id appears nowhere in `json.dumps` of the verbose answer or of the
     slim answer, and in no `data_gaps` reason.
5. **The words match the code.** At the head:
   - `git grep -n "429 that minute" -- src tests` prints nothing. Both the comment over the
     contested branch and named change (a) now say what was measured: THQ's and Surplus's picked
     pools are Uniswap V4 pools, and until T-013 their seller lookup sent a truncated id.
     GeckoTerminal answered THQ's truncated id with 404 (2026-10-07). So for THQ no retry could
     have settled it, whatever the rate limit did;
   - `git grep -n "42 characters that matter" src/risk.py` prints nothing. The comment over the
     slim pop says what the field holds;
   - `git grep -c "Retrying shortly may settle it" src/risk.py` prints 1, unchanged.
6. **Measured on the frozen benchmark, with one dated cache-add.** Run against the main
   checkout's `bench/cache/` (Notes), on the task branch, with no other benchmark running. From
   a worktree, run each command below as `main([...])` from the scratch harness Notes describe.
   - *Prerequisites, each confirmed before any change; any one missing is BLOCKED:*
     - T-011 merged: `--replay` with its pinned clock, no network, every miss listed; and
       `--fill FILE`, which fetches exactly the listed URLs, once each, into `bench/cache/` and
       nowhere else, as dated entries;
     - T-019 merged, so the base's `bench/results.json` and `bench/results.md` were written by a
       replay at T-011's pinned clock with no miss.
   1. *Precondition.* At the base, `python bench/run_benchmark.py --replay` misses nothing,
      exits 0 and writes files byte-identical to the committed `bench/results.json` and
      `bench/results.md`. Any miss, or any byte of difference, is BLOCKED before any change.
   2. *Replay at the fix commit.* `--replay` misses exactly the five GeckoTerminal single-pool
      URLs carrying the full 66-character ids of THQ, USDT0, ROBOTMONEY and Surplus (base) and
      RALLY (eth), and exits 4. Any other miss means a URL changed that should not have: BLOCKED,
      and nothing is fetched.
   3. *One cache-add.* Write exactly those five URLs to a scratch file, one per line, and run
      `python bench/run_benchmark.py --fill <that file>` once, at the fix commit, before any
      measurement is committed. It is a live, paced fetch of five URLs and no other. Log, from
      the fill's report and the entries it wrote, each URL's token, HTTP status, h24 `sellers`
      value and `fetched_at`.
   4. *End states, fixed now.*
      - Every answer is HTTP 200 and the fill exits 0: replay again, with no miss and exit 0,
        and commit `bench/results.json` and `bench/results.md` from that replay. The commit
        message gives the cache-add's UTC date (the entries carry it as `fetched_at`; the
        results files do not show it), so a reader can see which seller counts are newer than
        the dataset.
      - Any other answer: stop. BLOCKED, naming the token and the status. Nothing from this AC is
        committed. A final 4xx other than 429 (a 404 included) has been stored by the fill as a
        dated negative entry (T-011); a 429, a 5xx or a timeout is not stored, and the fill exits
        6. Either way, leave the cache as the fill left it, edit no cache file by hand, run no
        second fill, and report the entry.
      - A count of 10 or more gives the expectation below, whatever its value. A count under 10
        sends that row to `high` (the wash-trading shape). A 200 with no count leaves the row
        `unknown` with today's gap. Each is committed as measured and explained in the READY
        report.
      - Never fetch again, on this day or another, to get a different answer. Never change a
        threshold, and never move the frozen clock.
   5. *Pre-registered expectation, row by row against the base's `bench/results.json` (an
      expectation, not a target):*
      - THQ, USDT0 and RALLY go from `unknown` to `medium`. Surplus goes from `unknown` to `low`,
        released under E23 at 4 of 688 holders. Each of the four loses its distinct-seller gap.
      - ROBOTMONEY stays `high` 100.
      - Every other row is identical in `verdict`, `score`, `driver`, `gap_reasons`,
        `verdict_ablated` and `score_ablated`, and `engine_pool` is identical on every row.
      - Unknown falls by exactly 4; false positives and false blocks do not change (at `4838fdd`:
        122 to 118 of 576, 5 of 162, 20 of 154).
      - No row that is `high` at the base is anything else at the head.
      - The READY report explains any row that moves and is not named here. A move that cannot
        be explained is BLOCKED.
7. **Published in the project's order.** After AC 6, run
   `bash .github/scripts/regenerate-derived.sh regenerate` (that argument only) to its fixed
   point, then every test. These moves are pre-registered relative to the base's committed pages
   (from the investigation's replay; the figures in brackets are those at `4838fdd`; to confirm,
   not targets). If AC 6's decision rule ends a row differently, each move is matched to the rows
   as measured instead:
   - Unknown falls by 4 wherever it is published: `README.md`, `docs/EXPERIMENT_C.md`,
     `docs/SCORECARD.md`, `docs/OWNER.md`, `src/entry.py`, `src/landing.html` and
     `src/pages.py` (122 to 118 of 576; the one-decimal rate 21.2 to 20.5).
   - The false-block cohort's unknown count falls by 1 (`docs/EXPERIMENT_C.md`; 21 to 20).
   - In `src/pages.py`'s paragraph on the tokens holding $100,000 or more (246 at `4838fdd`):
     - low +1, unknown -2, medium or high +1 (156, 53, 37 to 157, 51, 38);
     - on contract signals only, the same moves (176, 53, 17 to 177, 51, 18);
     - honeypot-driven +1 over a denominator +1 (13 of 37 to 14 of 38).
   - `docs/SCORECARD.md`'s Correctness row: `test_risk.py`'s pass count becomes the head count
     from AC 8 (`bench/scorecard.py`, `tests_pass()`, about line 56); its score stays 5.0.
   - The scorecard total does not change while the benchmark unknown rate stays in the band it
     is in at the base (at `4838fdd`, 20 to 30, worth 2.0 points, and 118 of 576 stays in it). If
     the move crosses a band edge, the READY report names the new band and points; the bands do
     not change.

   No other published figure moves. `python bench/publish_numbers.py` (without `--write`)
   reports nothing stale. The unknown figure is the only change to `src/entry.py`.
8. **Contract and checks.**
   - The first commit adds only the acceptance tests. At that commit they run without crashing.
     These checks fail: AC 1's full-id, keyed-first and no-`...` checks; AC 2's first three
     cases; AC 3's no-request and verdict checks for every non-empty string; and AC 3's `&pair=`
     checks for the three 42-character strings (ending `g`, ending `&x`, and the one with `_`).
     Every other check passes, AC 4's included.
   - Named change (a) goes in its own commit. The fix commit's message says what the red looked
     like.
   - At the head, `python tests/test_risk.py` passes every check (the base's count, 706 at
     `4838fdd`, plus the new ones). `python lead/checks.py` passes every step, or matches the
     baseline in `lead/STATE.md` at dispatch, and exits 0. `git status --short` is then empty.

## Evidence required

- The tests-first commit: its SHA, and the output of `python tests/test_risk.py` on it (which new
  checks fail and which pass, and the exit status). The failing AC 1 check should show the
  truncated URL, and the failing AC 3 `&pair=` check the injected `&x`.
- At the head: the same command (all pass, with the count); `python lead/checks.py` (summary line
  and exit status), then `git status --short` (empty).
- The upstream contract is unchanged: this command prints the same line at the base and at the
  head (line numbers are left out on purpose, since any edit above a read shifts them):
  `python -c "import json, sys; sys.path.insert(0, 'tools'); import upstream_fields as u; f = u.build(); print(json.dumps({'paths': {s: sorted(p) for s, p in f.table().items()}, 'urls': f.urls()}, sort_keys=True))"`
- AC 6, step by step:
  - the prerequisites, each with where it comes from (the T-011 and T-019 merge commits);
  - the precondition replay: no miss, exit 0, and the byte comparison;
  - the miss list at the fix commit;
  - the fill file, the `--fill` command, its report and exit status, and the cache-add log,
    giving for each URL the token, the HTTP status, the h24 `sellers` value and `fetched_at`;
  - the final replay: no miss, exit 0;
  - a row diff against the base: every row whose `verdict`, `score`, `driver`, `gap_reasons`,
    `verdict_ablated`, `score_ablated` or `engine_pool` differs, before and after, then the
    totals.
- AC 7: `git diff --stat` of the regeneration commit, the report of
  `python bench/publish_numbers.py`, and each moved figure matched to AC 7's list.
- Six mutants, each shown red and then restored, with `__pycache__` cleared after each
  (`CLAUDE.md`: a stale `.pyc` makes a mutant lie). Name the check that catches each one:
  - (a) the lookup reads the rendered `pair_address` again;
  - (b) the id is lowercased before the lookup;
  - (c) the validation is dropped, so any string is sent;
  - (d) the rendering is raised to show the full id (`_ascii_safe(..., 66)`);
  - (e) the `&pair=` condition goes back to `startswith("0x")` and a length of 42;
  - (f) the validation written with `re.match` and a pattern ending in `$` (it accepts a
    trailing newline).
- `git diff --stat <base>..HEAD`: only files in scope.
- A scan of every changed file for non-ASCII characters: none.

## Notes

**Why the base is T-019's, and why ACs 6 and 7 are relative (lead decision, 2026-10-08: no
split; T-013 stays one task of size M).**
- Measured on T-011's draft: its head replay misses 91 requests (honeypot.is 86 over 84 URLs,
  GeckoTerminal 5 over 5), and a replay with any miss writes nothing and exits 4.
- T-019 runs T-011's `--fill` once on those misses and re-baselines the published benchmark.
  Under T-011's rule (every final 4xx except 429 kept as a dated negative entry), the lead
  expects the base replay to miss nothing; AC 6 step 1 checks it, and any miss there is BLOCKED.
- T-019 runs at a commit without this task, so the five full-id URLs are not in its fill and
  this task's movement does not land inside the fill's drift.
- A fill brings live drift (1 of 13 sampled "no record" tokens now answer), so absolute figures
  measured at `4838fdd` need not describe the base. ACs 6 and 7 are therefore stated relative to
  the base, with the `4838fdd` figures in brackets.
- This task fills only its own five URLs, through `--fill` on an explicit list, at the fix
  commit, before measuring (AC 6 step 3).

**Threat model.** What must never happen, and from which realistic causes:
- (a) **A token that traps its holders moves toward `low` or `medium` on a count for the wrong
  pool, or for a string that is not a pool id; or a lookup carries text that changes what is
  asked.** `pairAddress` is upstream text: it can be malformed or hostile (path characters such
  as `/` or `..`, query characters such as `&`, whitespace, 4,000 characters), or a
  display-truncated form. Today `0x` + 38 hex + `&x` reaches honeypot.is as an extra parameter
  (measured, Context). Defence: only `0x` + 40 or 64 hex is ever sent to the seller lookup, and
  only `0x` + 40 hex to the `&pair=` retry, as given, under the network `_GT_NETWORK` already
  maps (AC 1, AC 3).
- (b) **A token rated `high` today reaches `low`.** The change only fills `sellers_24h` where it
  was `None` on the seller path. E23's fatal band and the under-10-sellers rule decide before
  any release, and a token with no count stays `unknown`. AC 2's fatal case checks this, and so
  does AC 6's row diff, where no `high` row may move. **The red-team must check that no V4 token
  rated `high` today can reach `low` through this change** (lead decision).
  - Residual, not this task's: a V4 hook can block chosen holders while ten or more funded
    wallets of the deployer sell. That is the residual E23 already records for every pool (its
    W40 proposal). It is now reachable on V4 pools, as it already was on V2 and V3 pools.
- (c) **The fail-closed path weakens.** A string that cannot be looked up, or a lookup that
  fails, must still give `unknown` with today's gap (AC 2, AC 3).
- (d) **The benchmark drifts silently.** Lowercasing or re-encoding the id would change the URL
  of every cached seller lookup and `&pair=` retry (most are checksummed). The replay would then
  miss them, and a fetch would replace a September answer with today's. AC 1's byte-for-byte
  checks and AC 6's five-URL miss list are the guard.
- (e) **The answer grows or leaks the id.** The raw id stays out of the answer (output budget;
  the slim answer drops pool ids on purpose), out of every gap reason, out of every log and out
  of telemetry (invariant 2). `_note_failure` records host and status only, and `src/entry.py`
  reduces gap reasons to fixed classes; neither changes (AC 4).
- (f) **A published figure moves without warning, or without its guard.** Every move is
  pre-registered in AC 7. `engine_pool`, and with it the pool-agreement figure, must not move
  (AC 4, AC 6).
- (g) **Production traffic grows.** The request count on every path stays as it is (AC 1). In
  production the seller path makes the same one or two requests as today, now with an id the
  upstream can answer.
- Realistic accidents:
  - a lowercase-only pattern such as `^0x[0-9a-f]{40}$` (as first proposed in the
    investigation). It rejects the checksummed ids, which then lose their count and fall to
    `unknown`;
  - `re.match` with a pattern ending in `$`, which accepts a trailing newline; `int(s, 16)`,
    which accepts surrounding whitespace, underscores and non-ASCII digits; `str.isalnum` or a
    Unicode digit class, which accept non-ASCII digits. Use a full match on an explicit ASCII
    class. AC 3's newline, space, `_` and U+0661 cases catch these;
  - lowercasing the id before the lookup;
  - raising `_ascii_safe`'s limit to 66. That fixes the lookup but changes the rendered value,
    `engine_pool` on 88 rows, and the published pool-agreement figure;
  - carrying the raw id in a private evidence key or a context variable, which then leaks into an
    answer or outlives the request;
  - a stale `__pycache__` during mutants;
  - a worktree with an empty `bench/cache/`, which makes the replay miss everything. Stop at
    AC 6 step 1, and never give such a miss list to `--fill`.

**What T-011 provides.** The pinned clock `BENCH_CLOCK`; `--replay`, which makes no request,
lists every miss by host and URL (the lines starting with `https://` form a valid fill file), and
writes nothing and exits 4 when anything is missed; `--fill FILE`, which fetches exactly the
listed URLs without an entry, once each, paced as fetch mode paces, writes only dated entries
(a success with `fetched_at`; a final 4xx other than 429 as a dated negative entry), reports
each URL's outcome, and exits 0 when every listed URL has an entry and 6 otherwise. Use what
exists under the names T-011 gives it (its spec in `lead/tasks/`, and
`python bench/run_benchmark.py --help`). Do not fetch by other means: no hand-written cache
files, and no edits to `bench/fetcher.py` or `bench/run_benchmark.py`.

**The cache lives in one place.**
- `bench/cache/` is git-ignored and exists only in the main checkout (about 6,600 entries at
  `4838fdd`, more after T-019's fill).
  A worktree has none. Point the runs at the main checkout's `bench/cache/`: set the fetcher's
  module-level `CACHE_DIR` to it from a scratch harness, as T-011's hints describe, or link the
  worktree's `bench/cache/` to it. It is ignored either way, so it never enters the diff.
- The reviewer reproduces AC 6 against the same cache, so the five entries must land there.
- Never run two benchmarks at once (`CLAUDE.md`). They share the cache and race.

**How the tests can be written.** Use `install_stub` / a recording `_stub` with `default=None`,
`check()`, and `test_*` function names, all as the neighbouring tests do. Use synthetic ids
(`"0x" + "ab" * 32`, a hand-written checksummed 42-character id), not the benchmark's real
pools. The stub that answers only for the full id copies GeckoTerminal's real behaviour; with a
routing stub that matches substrings (`"networks/eth/pools/"`), every existing test passes on the
truncated id too, which is why none of them noticed. Build the CoinGecko key case with
`risk.configure(types_ns(CG_DEMO_KEY=...))` and restore it in `finally`. `types_ns` is a
module-level helper in the same file. Build the failed simulation from `hp_matic.json` with
`simulationSuccess` false, as the `&pair=` retry test does.

**Comments in `src/risk.py`.** `tests/test_http_telemetry.py` (about line 515) requires every
`https://` host written in the file to be named on the privacy page, so write no URL, even in a
comment. `tests/test_owner_power_recall.py` scans the file for fraction phrases and percentages,
so write neither.

**Facts checked for this spec (2026-10-08):**
- read in `src/risk.py`: every place named in "Files in scope", `_ascii_safe`'s kept
  characters, `_urlq`'s safe set, and the `&pair=` retry's condition and unescaped interpolation;
- offline, stubbed: the red in Context; the `&pair=` injection; the seller lookup on the fatal
  band; under AC 3's stub, today's `medium` for every non-empty AC 3 string and `unknown` for the
  empty string and the missing key; the E23 release at 4 of 688 with 117 sellers on a
  42-character pool; today's ten verbose and nine slim `best_pair` keys;
- `int(s, 16)` accepts U+0661, an inner `_` and a leading space; `re.match` with `$` accepts a
  trailing newline;
- in `bench/results.json`: 88 truncated `engine_pool` values, 436 of 42 characters, all hex; the
  four distinct-seller gaps;
- in `bench/cache/`: none of the five lookups cached, under either id; no cached URL with `...`;
  49 of 49 cached seller lookups and 368 of 368 cached `&pair=` values are `0x` + 40 hex;
- `tests/test_risk.py` passes 706 of 706 today;
- the published-figure list in AC 7, computed read-only by applying the investigation's replay
  rows to a scratch copy of `bench/results.json` and diffing `publish_numbers.figures()`;
- `bench/scorecard.py`'s band for the benchmark unknown rate (under 20: 3.0 points; 20 to 30:
  2.0).

**Unverified:**
- the investigation's live counts and the 404 on truncated ids (no network was used for this
  spec); the 404 for Surplus's truncated id is inferred from the same truncation;
- whether the keyed CoinGecko onchain endpoint accepts a 66-character id. In production it is
  tried first; a non-dict answer falls through to keyless GeckoTerminal, so a refusal costs one
  call;
- ROBOTMONEY's full-id answer. Its verdict cannot move either way.

**Conflict search (repeat with `git grep -n -F -e "<symbol>" -- 'tests/test_*.py'
'tests/fixtures/**'`).**
- Symbols searched: `_distinct_sellers`, `pair_address`, `_ascii_safe`, `sellers_24h`,
  `contested_unsettled`, `Honeypot verdict contested`, `Retrying shortly`, `distinct-seller`,
  `contested`, `/pools/`, `pairAddress`, `&pair=`, `_sim_failed`, `hp_pair`, `engine_pool`,
  `labelled_pool`, `pool_match`, `_urlq`, `_onchain_sources`, `_liquidity_signals`, `best_pair`,
  `released_by_holder_share`, `contradicted_by_chain`, `pool_id`, `unknown_pct`, `unknown_n`,
  `false_block_unknown`, `deep_unknown`, `deep_blocked`, `deep_low`, `429 that minute`, `THQ`,
  `tests_pass`, and the figure strings `21.2` and `122`.
- Findings:
  - **Stay green unchanged.** Every pair an `assess` test picks has a `0x` + 40 hex id
    (`"0x" + "ce" * 20` and the like, `"0x%s%038x"`, or a fixture's 42-character pair), or is on
    Solana, which never reaches honeypot.is. So these stay green unchanged: the holder-share,
    overturning, nobody-took, keyed-fallback, key-validation (a direct `_honeypot_signals`
    call with `sellers_24h` None), GeckoTerminal-path and `&pair=` retry tests (about lines
    941, 2652, 2787, 2887, 3311, 3496, 3627 and 3901).
  - **Fixtures with longer ids.** `ds_weth.json` (66 and 128 characters), `ds_matic.json` and
    `ds_usdc.json` (66) hold V4-length ids. Only `ds_usdc.json` picks one (measured with
    `_pick_best`), and it is used only by the `liquidity()` and `_pick_best` tests (about lines
    165 and 2486), which reach neither lookup.
  - **Test at about line 3557.** It calls `_distinct_sellers` directly with a 42-character id
    in `pair_address`; hence the `pool_id=None` default in "Files in scope".
  - **Upstream contract.** `tests/test_upstream_contract.py` lists the single-pool endpoint
    (about line 142). It runs in the network job; its URL templates come from `http` string
    constants, and its field paths from `tools/upstream_fields.py`, compared as path sets
    (`test_generated_field_contract`). Hence the evidence item.
  - **Figure tests.** `tests/test_owner_page.py` (about line 122) and
    `tests/test_published_numbers.py` read figures from `bench/results.json`, which AC 7 keeps
    consistent. No test hard-codes 21.2 or 122 as a benchmark figure.
  - **Test counts on a page.** `bench/scorecard.py` `tests_pass()` copies `test_risk.py`'s pass
    count into `docs/SCORECARD.md`; the tests stub `tests_pass`, so nothing goes red, but the
    regenerated row moves (pre-registered in AC 7).
  - **Nothing affected.** No test reads `engine_pool`, `labelled_pool` or the pool-agreement
    figure. The `pool_id` hits (`tests/test_sellability_archive.py`, and `tests/test_risk.py`
    about line 4459) concern the snapshot schema and `find_new_hot_pools`.
  - **The only named change.** The THQ attribution in the comment at about line 2945 is named
    change (a).

**Follow-ups for the lead to park (not this task):**
1. **The pool-agreement figure undercounts.** The benchmark's `engine_pool` is the rendered
   `pair_address`, so a 66-character id never equals a full `labelled_pool`. 26 of the 88
   truncated rows have a labelled pool with the same 48-character prefix, so they are inferred
   to be the same pool. The published pool-agreement figure (288 of 524 in
   `bench/results.md`; the "same pool" share in `docs/EXPERIMENT_C.md`) therefore undercounts.
   With full ids it would read 314 of 524. Changing that moves a published figure, and needs its
   own task.
2. **`find_new_hot_pools` truncates V4 pool ids too.** It renders `pool_id` as
   `_ascii_safe(pid, 64)` (`new_pools`, about line 4361). A chain-prefixed V4 id (`base_` + 66)
   is 71 characters, so it is cut. Display only. T-017 works in that function.
3. **The cache-add mixes dates.** The four rows' counts are read on the fetch date, while the
   rest of their evidence dates from the dataset's fetch. The verdict compares the count only
   with 10, so this moves nothing while each count stays at 10 or more. A benchmark-only signal
   sentence can still read oddly: the investigation's Surplus row said "78 sells from 117
   distinct sellers". `bench/results.md` does not list entries added after the dataset date.
   T-011's follow-up on per-response clocks covers this.

**Other notes:**
- Same file (`src/risk.py`) as T-011, T-012, T-016, T-017 and T-018. T-018 also adds checks to
  `tests/test_risk.py` and rewrites `docs/SCORECARD.md`; T-014 regenerates `docs/SCORECARD.md`
  and `docs/OWNER.md`, and T-015 edits `src/landing.html`, all of which AC 7 regenerates too.
  T-011 and T-019 merge before this task, and T-012 waits for it. Do not run any of the others
  in parallel with it, nor T-019, which shares the cache (batch check, 2026-10-08).
- Level 3: an independent review and a red-team. The merge waits for the Owner's yes, and so
  does the push, which deploys `src/` (`lead/config.yml`).
- Write files with the Write or Edit tool, never through a shell heredoc. Both tools decode
  backslash-u escapes into real characters (`lead/PITFALLS.md`), so write none: U+0661 goes in
  the test as `chr(0x0661)`. Scratch files go in your own subfolder of the session scratchpad;
  the rest of it belongs to other agents.

## Amendments

### Release dispatch preparation (2026-10-11; criteria unchanged)

The lead retains the original prepared specification as a curated task, not a merge of
unrelated local history. T-011 and T-016 are deployed. T-019's frozen data-only head is
393346f and remains in independent and red-team review: do not begin this task until its
reviewed rebaseline is merged and published. Use that subsequent integrated published
head as the exact task base, and record its SHA before any acceptance commit or live fill.

The refreshed conflict search covers the symbols in Notes, existing risk tests and
fixtures, and the T-016 contract and holder suites. At published 86a8111, risk.py and
test_risk.py have no diff from fefe6d1; no additional older-test change is authorized.
The single named comment correction (a), the original full-id validation, disclosure,
request-count rules, five-URL miss list, one-fill decision rule and all bands still bind.

T-022's published pacing controls are opt-in to pool collection. They do not authorize
any different benchmark fetch, retry, cache shape or clock. The executor must independently
reproduce the zero-miss, byte-identical base on the protected main cache before starting,
then use only the five actual full-id misses for the one permitted dated fill. Preserve
T-019's original cache backup and its measured row changes through this task and T-012.

### Exact published dispatch base (2026-10-11; criteria unchanged)

The exact task base is a19c3dc0b5ac288b4b37966876a095f6616e0ca4. It contains
T-011's reviewed replay, T-016's holder correction, T-019's approved rebaseline and
T-022's opt-in collection pacing. T-019 source 393346f passes independent review at
12/12 and red-team review with no material finding, and is merged as e93169a. The lead's
combined immutable replay has zero misses and reproduces both committed outputs byte
for byte. Full integrated checks pass thirty-one steps. Exact-head Linux preflight
38150722554 passes required jobs and 219 observed upstream checks, with no unobserved
or collapsed path. Published deployment 38150990382 actually runs and passes its
offline suite, deployment and tagged smoke checks; generated homepage and Agent text
are read back successfully. The executor must reproduce its own base prerequisite.

The protected filled base now has 120 unknown rows out of 576. This is a measurement,
not a changed target: all AC 6 and AC 7 moves are still relative to this base and to the
actual single five-URL fill. The old September figures in brackets remain historical.
No threshold, fill retry, miss-list allowance or older-test change is added.

### Named baseline clarification: ASCII evidence (2026-10-11)

The Evidence line asking for no non-ASCII character in any changed file is already
false on the exact published base. The lead independently compared Git blobs at
a19c3dc and frozen source b99f2e7. Non-ASCII character counts are identical before
and after: README 23, benchmark JSON 0, benchmark Markdown 18, Experiment C 22,
generated Owner page 36, scorecard 119, entry 13, landing 49, pages 0, risk 15,
and risk tests 9. The complete character multisets are unchanged, and every
added and removed diff line is ASCII. Existing English punctuation is retained.

For this evidence item, report the literal whole-file conflict and prove that
no new or changed line contains non-ASCII text. The repository's English-only
guard still runs. Rewriting pre-existing punctuation or immutable older tests
is not authorized. This clarification changes no acceptance assertion, source
behavior, figure, benchmark rule, risk threshold, or review gate.

