---
id: T-011
title: Make the benchmark a deterministic replay - a pinned clock, dated cache entries, a replay that never calls an upstream, and a fill limited to a list
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 2                 # 0 direct | 1 light | 2 standard | 3 high risk
size: M                  # S | M (split anything larger)
depends_on: []           # none; never in parallel with T-014 to T-018 (shared files, Notes)
decisions: [ADR-0001]
backlog: W59             # plus the uncached final 4xx answers, which W59 does not name
---

## Context

`bench/run_benchmark.py` scores the engine (`src/risk.py`) on the 576 tokens of the tracked
`bench/dataset.json`. It reads upstream answers through `bench/fetcher.py`'s disk cache,
`bench/cache/`, which `.gitignore` excludes: it exists only in the main checkout, holds 6647 files,
and the file times run from 2026-09-03 to 2026-09-18 (UTC). The run writes `bench/results.json`
and `bench/results.md`, the published measurement. `results.json` was last committed by `cfa42f6`
(2026-09-21, 02:32 UTC); `results.md` last changed at `4d86202`, and a run at the pinned instant
regenerates it byte-identically (measured, below). Two inputs of a run are not frozen, so the same
engine on the same cache gives different numbers on different days:

1. **The clock (W59).** `_liquidity_signals()` (about line 1720 of `src/risk.py`) calls
   `_age_days(best.get("pairCreatedAt"))` without `now`. `_age_days()` (about line 1570) then reads
   `datetime.now(timezone.utc)`. A pair's age decides the freshness signal: "Very new pair" under
   3 days, "Recently created pair" under 30, "Established pair" otherwise. As the calendar moves,
   cached pairs cross those lines. `_minutes_since_rugcheck_indexed()` (about line 3419) reads the
   wall clock the same way; it is Solana only, and no benchmark row is on Solana today.
2. **Answers that are never cached.** `fetch_json()` returns `NOT_FOUND` on a 404 to a
   `mark_missing` request (about line 125), before the cache write (about line 140). It also caches
   nothing that is not a success. So every such URL is asked live again on every run. The
   2026-10-07 investigation asked 13 of these "no record" tokens live: 1 of 13 (CTM, bsc) now
   answers 200 with a successful simulation.

**Measured by the spec writer on this base (2026-10-08).** These are offline replays: they import
the unchanged `bench/run_benchmark.py`, read `bench/cache` without ever fetching or writing it,
and send their outputs to a scratch folder. One live request is marked as such.

- **The misses.** A run makes 91 requests that find no cache entry, over 89 distinct URLs. 86
  requests over 84 URLs go to honeypot.is, all with `mark_missing`; 19 of those URLs are `&pair=`
  retries. 5 requests over 5 URLs go to GeckoTerminal, none with `mark_missing`. Those 5 are pool
  ids that `_distinct_sellers` display-truncates to end in `...`, a separate defect (T-013); the
  investigation measured GeckoTerminal answering 404 to two of them (THQ, USDT0). The counts are
  the same at every clock tried, and the same when every miss is answered as a failed fetch.
- **The zero-address URL answers 400 (one live request to honeypot.is, 2026-10-07 17:17 UTC).**
  The one honeypot.is URL for the zero address (`chainID=1`) is asked for two rows, BNB (bsc) and
  ETH (ethereum). It answers HTTP 400, "Invalid Address". Today's fetcher turns a 400 into a failed
  fetch, which is why both committed rows carry "upstream request failed". It is a final 4xx, so
  in the dated mode of this task it is recorded as a negative entry and replayed as the same
  failed fetch (AC 3).
- **Reproduction.** I ran `run_benchmark.main()` unchanged, with the engine's clock replaced by
  2026-09-21T02:00:00Z and each of the 91 missed requests answered the way the committed file's
  gap reasons record. A `mark_missing` request got "no record". The zero-address honeypot.is URL
  got a failed fetch, as did each GeckoTerminal request. The output is byte-identical to
  `bench/results.json` and `bench/results.md`. It is identical at each of ten instants tested
  from 2026-09-20T16:00Z to 2026-09-21T09:00Z, both ends included, and `results.json` differs at
  2026-09-20T15:00Z and at 2026-09-21T10:00Z. Ages only grow, so every instant between the two
  ends reproduces too. The investigation's simpler model answered every `mark_missing` miss as
  "no record". It matched verdict, score and driver on all 576 rows, but differed from the
  committed file in two rows' gap reasons: the two zero-address rows.
- **The clock moves 42 rows.** The same replay at the real clock (2026-10-07, 2026-10-08) differs
  from the committed file in 42 rows' verdict, score or driver. The outputs (both files) at
  2026-10-08 and 2026-11-17 are byte-identical to each other: the effect has saturated. The newest
  pair the engine chooses for any benchmark row was created 2026-09-07, so every chosen pair is now
  over 30 days old. **A test that compares two dates after early October cannot fail.**
- **Fail-closed misses move published figures.** Answering every miss as a failed fetch, the only
  honest reading of an answer nobody recorded, moves 4 rows at the pinned clock. Three `high` rows
  become `unknown`. Alive tokens rated `high` go from 5 of 162 to 4 of 162, and `unknown` from 122
  of 576 to 125 of 576. "unknown, our side" in `results.md` goes from 6 to 63. So a replay with
  misses must not write the published files, and this task cannot regenerate them.
- **CHIP (base).** W59 recorded it moving between `low` and `unknown`, cause not identified. It
  does not move with the clock: it is `unknown` 30, driver sellability, at 2026-09-20, 09-21, 09-22
  and 10-07. Its one uncached request is the honeypot.is `&pair=` retry. Answered "no record" or
  failed, the row is `unknown` 30; answered with a sellable simulation, it is `low` 0. It is
  `unknown` 30 in the committed file at `33e3b5f`, `4d86202` and `cfa42f6`, so the direction W59
  wrote ("`low` to `unknown`") is not confirmed by the committed history.
- No benchmark row's chosen pair was created after 2026-09-21T02:00:00Z.

The benchmark process has no runtime fetch: `cf_fetch` is None outside a Worker, so
`_eth_get_code` and the edge cache answer nothing. Every network access of a run therefore goes
through `fetch_json()`.

**The lead's binding decisions:**
- The clock is one pinned constant: the instant at which this engine reproduces the committed
  files.
- Production keeps the wall clock. The injected clock is unset by default, and only
  `run_benchmark.py` sets it.
- In the dated benchmark mode, every final 4xx answer except 429 (any status from 400 to 499
  other than 429) is persisted as a dated negative entry, and replayed as the same outcome the
  live call produced: `NOT_FOUND` for a 404 when the caller asked for `mark_missing`, the
  ordinary failure (None) otherwise. The default mode (the snapshot collector, production, and
  any caller not asking for dated mode) is unchanged.
- A replay mode never touches the network and reports every miss by count.
- The snapshot collector and every production path cache exactly what they cache today.
- No served answer and no published figure changes in this task.
- Freezing each answer at its own fetch time is a follow-up, not this task.
- The `--fill` tool is built in this task. Running it for real, and re-baselining the published
  benchmark on its output, is T-019 ("Fill the frozen benchmark's cache misses once, and
  re-baseline the published benchmark on it", Level 3), which depends on this task.
- A fresh clone (no `bench/cache`) measures today's upstream answers at the pinned clock. That is
  accepted; no criterion covers it (Notes).

This spec also dates the successes the benchmark writes in the same mode (AC 3), so that
follow-up 1 and T-013's dated cache-add have a fetch time to read. Nothing reads it in this task,
and no other caller's entries change.

**What this hands T-012 and T-013.** This task delivers the mechanism, not a filled cache. At its
head, on the real cache, `--replay` exits 4 and lists the 91 requests over 89 URLs above, and it
will on every run until a fill. The fill path (AC 5) is built and tested here on synthetic data,
but never run against a real upstream: it asks those URLs live, and an answer that changed since
September (1 of 13 sampled already has) moves published figures. Running it is T-019 (Level 3).
Because every final 4xx except 429 is recorded in dated mode (AC 3), a complete fill also records
the zero-address URL's 400, so zero misses is reachable without changing the engine.
A fill can surface new misses: a first answer that changed can lead the engine to a `&pair=`
retry nobody asked before. So T-019 alternates replay and fill, never asking again a URL that
has an entry (T-019 AC 3 allows one later retry of a URL a fill left unstored), until the list is empty or stops shrinking. T-013 (AC 6 step 1: at its base the replay misses
nothing, exits 0 and writes files byte-identical to the committed `bench/results.json` and
`bench/results.md`) and T-012 (AC 7, precondition: at its base the replay reports zero misses,
exits 0 and leaves `git status --short` empty) assume that state at their base. They depend on
T-019, not on this task alone, and each checks that precondition at its own base before any
change, against the results T-019 commits.

## Goal

Two benchmark runs over the same cache produce byte-identical results whatever day they run on. A
replay run never calls an upstream: it either reproduces the measurement from what is recorded,
or it refuses and lists what is not recorded. A fill fetches exactly a given list of URLs, once
each, and records each answer with its fetch time. Production keeps reading the wall clock.

## Scope

**In:**
- `src/risk.py`:
  - a context variable beside `_STALE_HITS` and `_FETCH_FAILURES` that holds a pinned instant and
    is unset by default;
  - one helper that returns that instant, or the wall clock when it is unset;
  - `_age_days()` (when no `now` is passed) and `_minutes_since_rugcheck_indexed()` read time
    through that helper.

  Nothing else in the engine changes.
- `bench/run_benchmark.py`:
  - a `BENCH_CLOCK` constant;
  - `main(argv=None)` with two options, `--replay` and `--fill FILE`, and one status for any other
    argument;
  - pinning and restoring the clock around the evaluation;
  - the run summary, the replay refusal and the fill report;
  - passing the dated flag in fetch mode and in the fill;
  - the module docstring's usage.
- `bench/fetcher.py`: dated entries in benchmark mode (a negative entry for a final 4xx other than
  429, and the fetch time on a success), reading negative entries back, a replay path that never
  reaches the network, and a record of replay misses.
- The new test file and its step in `.github/workflows/test.yml`.

**Out:**
- **Any run that can reach an upstream.** That is a fetch-mode run (`python bench/run_benchmark.py`
  with no argument) or a `--fill` run, against a real upstream or the main checkout's
  `bench/cache`. Either asks URLs live and writes into the only copy of the cache. No fetch step
  is allowed in this task: filling the misses moves published figures (above) and is T-019.
  Tests reach only fakes.
- **Published outputs.** `bench/results.json`, `bench/results.md`, `docs/`, `src/pages.py`,
  `README.md` and `CLAUDE.md` stay unchanged, and so do `write_markdown()` and the shape of
  `results.json`.
- **`checked_at`.** `_now_iso()` stays on the wall clock, because it says when an answer was made.
  `src/entry.py` and `src/mcp_server.py` are also unchanged.
- **Other fetcher callers.** `bench/snapshot.py`, `bench/build_dataset.py` and `bench/backfill.py`
  stay unchanged. Through `fetch_json()`'s defaults they get exactly today's behaviour, and their
  entries keep today's shape.
- **Other failures.** Persisting any failure other than a final 4xx (timeouts, connection errors,
  5xx, 429) is out, and so is writing any negative entry outside the dated mode.
- **Separate defects.** The display-truncated GeckoTerminal pool id (T-013), and asking
  honeypot.is about the zero address.
- **The weekly CI `benchmark` job** in `test.yml`, and every public instruction to run the
  benchmark, are unchanged (Notes: "Runs on a fresh clone").

## Files in scope

- `src/risk.py`
- `bench/run_benchmark.py`
- `bench/fetcher.py`
- `.github/workflows/test.yml`: one step in the `test` job. Copy the shape of its neighbours
  exactly: a comment, `- name: ...`, then `run: python tests/test_benchmark_replay.py`. Place it
  before the step named "The deploy runs every step of this job before it deploys".
- Acceptance tests: `tests/test_benchmark_replay.py` (new). Use synthetic data only, optionally
  as files under `tests/fixtures/benchmark_replay/` (new). Existing files under `tests/fixtures/`
  may be read, not changed.
- **Named changes to existing tests:** none. The conflict search (Notes) found no test that the
  change, done as specified, breaks. These existing tests will see it:
  - `tests/test_decisions_enforcement.py`, twice. `test_every_test_file_runs_in_ci` requires the
    new step in `test.yml`. `test_no_test_function_is_unreachable_by_its_own_runner` (about line
    134) fails unless the new file discovers its tests with `startswith("test_")` over its
    globals in `main()`, or names every test function there. Use the discovery idiom, as the
    neighbouring files do.
  - `tests/test_deploy_gate.py` reads `test.yml` and fails on a line it does not recognise.
  - `tests/test_risk.py` imports `run_benchmark` mid-file (`test_a_medium_names_what_fired`, about
    line 3412). Later in the same process it builds values from the wall clock: RugCheck
    `detectedAt` stamps (about lines 4145, 4184, 4255 and 5489), pools whose `pairCreatedAt` is
    the real now minus an age in days, expecting "Recently created pair" (about line 3692), and
    a pair created an hour after the real now (about line 1398). It also checks `checked_at`
    against the wall clock (about line 3478). All of these stay green only if the import pins
    nothing (AC 2). Its `test_a_future_timestamp_is_not_a_missing_age` passes `now` explicitly,
    which must still win.
  - `tests/test_sellability_archive.py` replaces `snapshot.fetch_json` with a fake taking `**kw`;
    `snapshot.py` is unchanged.

  Any other older test failing means BLOCKED.

## Acceptance criteria

1. **The engine reads a pinned instant when one is set, and the wall clock otherwise.** In
   `src/risk.py` a context variable, defined beside `_STALE_HITS` and `_FETCH_FAILURES` and unset
   (None) by default, holds an aware UTC `datetime`. One helper returns it when it is set and
   `datetime.now(timezone.utc)` otherwise. `_age_days(created, now=None)` uses the helper when
   `now` is not passed; an explicit `now` still wins. `_minutes_since_rugcheck_indexed()` uses the
   helper in place of its wall-clock read. `_begin_request()` does not touch the variable. Tests
   replace the engine's wall clock by swapping `risk`'s module global `datetime` for a subclass
   whose `now()` returns a chosen instant:
   - (a) With the variable set to T, a creation time 10 days and 1 hour before T gives age 10 under
     wall clocks T + 1 day and T + 41 days. A RugCheck stamp 5 minutes before T gives 5 minutes
     under both.
   - (b) Unset, the same calls follow the wall clock: ages 11 and 51.
   - (c) **The served path.** Through `risk.assess()`, with stubbed upstreams and nothing pinned, a
     pair created 10 days and 1 hour before the real now reads `pair_age_days` 10 and carries
     "Recently created pair".
   - (d) A scan of every file under `src/` finds no call that sets the variable.
2. **Only the benchmark pins, only while it runs, and every run states its clock.**
   `bench/run_benchmark.py` defines `BENCH_CLOCK`, an aware UTC `datetime`, equal to the instant
   Evidence item 1 confirms (expected 2026-09-21T02:00:00Z). A comment beside it says how it was
   chosen and the window measured.
   - **Arguments.** `main(argv=None)` accepts no argument (fetch mode), `--replay`, or
     `--fill FILE` (AC 5). Anything else exits with status 5, distinct from 1 to 4: an unknown
     argument, `--fill` without a file, or `--replay` together with `--fill`. It does so before the
     clock is pinned, and before anything is read, evaluated, fetched or written. Tests call
     `main(["--bogus"])` and `main(["--replay", "--fill", <path>])` and assert status 5, reading
     the code of a `SystemExit` if one is raised (argparse's own status is 2, which is already the
     "Benchmark invalid" refusal).
   - **The pin.** In fetch mode and in replay, `main()` pins the engine to `BENCH_CLOCK` before
     the first token is assessed, and every assessment in the run sees it. On every way out it
     restores the caller's previous value: a normal return; each existing refusal (exit statuses
     1, 2 and 3); the replay refusal (4); an exception escaping `main()`. Importing the module pins
     nothing. Tests: after `import run_benchmark`, and after `main()` has returned 0, returned 4
     and raised, the AC 1(c) check still reads the wall clock in the same process.
   - **The summary.** At its end, whatever its exit status, every run that evaluated tokens
     prints the pinned clock and the number of rows whose best pair was created after it: rows
     whose `evidence.best_pair.pair_created_at` parses, through `risk._pair_created_ms`, to an
     instant strictly after `BENCH_CLOCK`. (Within 2 days after it the engine reads such a pair as age 0,
     "Very new pair"; beyond that as no age, with no freshness signal and no gap.) Both values are
     available to the tests as data, so tests assert on numbers, not wording. Tests, on a
     synthetic dataset: a pair created 3 days after `BENCH_CLOCK` is counted and has no
     `pair_age_days`; one created 1 day after is counted and has `pair_age_days` 0; one created 10
     days before is not counted; a row whose pair has no `pairCreatedAt` is not counted.
3. **In benchmark mode every entry written is dated, a final 4xx is kept, and each is served back
   as it was answered.** `fetch_json()` takes `dated=False`.
   - With `dated` and `write_cache` both True, a success is written with `url`, `data` and
     `fetched_at`. A final 4xx answer (any status from 400 to 499 except 429), with or without
     `mark_missing`, is written to that URL's cache file as a negative entry: a JSON object with
     `url`, `status` (the status received) and `fetched_at`, plus `not_found: true` only when the
     status is 404, and no `data` key. `fetched_at` is UTC ISO 8601 ending in `Z`, taken from the
     wall clock at the fetch, never from the pinned instant.
   - With `dated` False (the default), no negative entry is ever written, and successes are cached
     exactly as today, with `url` and `data` and no other key. With `write_cache` False, nothing at
     all is written.
   - Nothing else is ever persisted: no timeout, connection error, 5xx or 429.
   - The call returns what it returns today. A later call for that URL with `use_cache=True`,
     whatever its `dated`, makes no network request and returns what the live answer returned to
     a call shaped like it: the data for a success; for a negative entry, `NOT_FOUND` only when
     the entry's status is 404 and the call has `mark_missing=True`, and None for every other
     negative entry or call shape.
   - The benchmark's engine fetcher passes `dated=True` in fetch mode. A fetch-mode run reports
     how many entries it wrote and how many of those were negative, printed and as data.

   Tests replace `urllib.request.urlopen`; there is no real network and no real sleeping. They
   cover each case above and both written shapes, plus two other callers' call shapes. They
   include a 400 answer in dated mode: it is written as a negative entry with `status: 400` and no
   `not_found` key, and served back as None both to a call with `mark_missing=True` and to one
   without. The shape `bench/build_dataset.py` uses (defaults) writes a success as exactly `url`
   and `data`, and writes nothing for a 404 or a 400. The snapshot collector's shape
   (`use_cache=False, write_cache=False, mark_missing=True`) returns `NOT_FOUND` on a 404 and
   leaves the cache directory unchanged, even with `dated=True`.
4. **A replay never calls an upstream, never writes the cache, and refuses when it missed.**
   `python bench/run_benchmark.py --replay`, or `main(["--replay"])`, assesses every token with no
   network call: a test makes `urllib.request.urlopen` raise, and the run must never reach it. It
   does no throttling and no sleeping. It leaves the cache directory exactly as it found it, with
   nothing added, changed or removed.
   - A cached success is served as in fetch mode, and a negative entry as in AC 3.
   - A request that finds no entry is answered as a failed fetch (None), never as "no record",
     whatever its `mark_missing`. It is recorded as a miss.
   - The independence assertion runs as today, with engine endpoints recorded for hits and misses
     alike.
   - At its end it prints the number of requests that missed, that number per host, and each
     distinct missed URL once, alone on its own line, so that the printed lines starting with
     `https://` form a valid `--fill` file (AC 5). The counts and the URL list are available to the
     tests as data.
   - **With one miss or more,** it evaluates every token first, so the count is complete. After
     the existing independence checks, whose statuses are unchanged, it writes neither
     `results.json` nor `results.md` and exits 4.
   - **With no miss,** it says so, writes both files byte-identical to what a fetch-mode run over
     the same answers writes, and exits 0.
   - With no argument, the run is today's fetch-mode run plus ACs 2 and 3.

   Tests use a synthetic dataset of at least three tokens:
   - A fetch-mode run against a fake upstream fills a temporary cache; a replay over that cache
     then exits 0 with byte-identical files.
   - With one entry removed, the replay exits 4, reports one miss under its host with its URL, and
     leaves both output paths untouched.
5. **A fill fetches exactly the URLs it is given, once each, and writes nothing else.**
   `python bench/run_benchmark.py --fill FILE`, or `main(["--fill", FILE])`. `FILE` is UTF-8 text
   with one URL per line; blank lines are ignored.
   - Before any network access it refuses with status 5 if `FILE` cannot be read, holds no URL,
     or holds a line that is not one `https://` URL with no whitespace.
   - It evaluates no token. It writes neither results file nor the access log.
   - For each distinct URL, in file order: if the cache already has an entry for it (the file
     `fetch_json()` would read), it makes no request. Otherwise it makes exactly one
     `fetch_json(url, role="engine", retries=2, dated=True)` call, throttled as in fetch mode. A
     URL listed twice is fetched once. A URL that is not listed is never requested.
   - Its only writes are AC 3's dated entries, for listed URLs.
   - It reports each URL's outcome, read from the cache afterwards: already recorded, stored
     answer, stored 4xx, or not stored. It reports the count of each per host, printed and as
     data. It exits 0 when every listed URL has an entry afterwards, and 6 when at least one does
     not.

   Tests use a fake `urlopen` that answers per URL: 200, 404, 500 and a timeout. The file lists
   those four, one URL already in the cache, and one duplicate. The tests assert four things:
   - requests reach only the listed URLs without an entry: one request for the 200 and the 404,
     and three each for the 500 and the timeout (one call with its two retries);
   - the cache gains exactly the dated 200 and 404 entries;
   - the outcome counts are right, and the exit status is 6;
   - the round trip works: the URL lines printed by a replay that missed, written to a file and
     given to `--fill` against a fake upstream, make the next replay exit 0.
6. **Two dates 40 days apart give the same results (W59's test), and the test can fail.** Build a
   synthetic cache with one token whose pair was created 10 days before `BENCH_CLOCK` and whose
   verdict or score depends on that age. Replay it twice, with the engine's wall clock replaced by
   `BENCH_CLOCK` + 1 day and then `BENCH_CLOCK` + 41 days. `results.json` and `results.md` are
   byte-identical between the two runs. In the same test, the control: that token assessed through
   `risk.assess()` with nothing pinned, under the same two wall clocks, gives a different verdict
   or score. The test fails if the control does not differ.
7. **The committed measurement is reproduced, not changed** (local: the real cache is not on CI).
   These figures are expectations measured on the base, not targets. Report a different count with
   its cause. If (b) does not reproduce at any instant, that is BLOCKED (lead decision). From the
   task head, with the fetcher's cache directory pointed at the main checkout's `bench/cache` and
   outputs redirected to a scratch folder:
   - (a) `--replay` exits 4 and reports 91 missed requests over 89 distinct URLs: honeypot.is 86
     requests over 84 URLs, GeckoTerminal 5 over 5. It prints 89 URL lines. The cache is
     unchanged.
   - (b) The reproduction harness of Evidence item 1 gives files byte-identical to the committed
     `bench/results.json` and `bench/results.md`, both at the machine's wall clock and with the
     engine's wall clock replaced by 2027-01-15.
   - (c) With the pin disabled in the harness, so the engine's instant stays unset, the same
     harness at today's clock differs from the committed file in 42 rows' verdict, score or
     driver.
   - (d) `git diff --quiet <base>..HEAD -- bench/results.json bench/results.md docs/ src/pages.py
     README.md` exits 0.
8. **Contract and checks.** The first commit adds only the acceptance tests and their fixtures. At
   that commit they run against the unchanged code without a traceback: a missing name or
   argument is reported as a failure. They are red on at least ACs 1(a), 2 (status 5 and the
   summary count), 3, 4, 5 and 6. At the head, `tests/test_benchmark_replay.py` meets four
   conditions:
   - it makes no network call, and fails if `urllib.request.urlopen` is reached outside its fakes;
   - it never sleeps for real;
   - it writes only under a temporary directory;
   - it runs in under 10 seconds.

   `python lead/checks.py` passes every step, one more than on the base, exits 0 and leaves the
   tree clean.

## Evidence required

1. **First, before pinning: the instant.** Write a scratch harness and never commit it. It imports
   the branch's `run_benchmark` and points the fetcher's cache directory at the main checkout's
   `bench/cache` (read-only; replay only), with `RESULTS_JSON` and `RESULTS_MD` redirected to
   scratch. It answers only the requests that find no cache entry, meaning no file named for the
   first 40 hex characters of the URL's SHA-256, as `fetch_json()` names them. It answers them the
   way the committed file records them: a `mark_missing` request as "no record"; the zero-address
   honeypot.is URL (the address is 0x followed by forty zeros) as a failed fetch; every other miss
   as a failed fetch.
   It records each such request's endpoint with `note_endpoint("engine", ...)` and counts the
   substitutions (expected 91). It must not replace the engine's clock: the clock comes from the
   branch. Report:
   - the instant pinned;
   - `cmp` against both committed files;
   - the window of whole hours that reproduce;
   - the substitution count.
2. The tests-first commit: its SHA, and the output of `python tests/test_benchmark_replay.py` on it
   (which checks fail, and why).
3. At the head:
   - `python tests/test_benchmark_replay.py`: the counts and the run time;
   - `python lead/checks.py`: the summary line and the exit status;
   - `git status --short`: empty.
4. AC 7 (a) to (d): the commands and their output. For (a), the per-host counts and the exit
   status; the URL list may be summarised by host.
5. **CHIP (base), measured on the branch.** Assess it alone at `BENCH_CLOCK`, and again pinned to
   2026-09-20, 2026-09-22 and 2026-10-07. Answer its one uncached request (the honeypot.is
   `&pair=` retry) three ways: "no record", failed, and a sellable simulation (synthetic, for
   example CHIP's own cached ethereum answer). Pre-registered expectation: `unknown` 30 at every
   clock with the first two answers, `low` 0 with the third. Then name the cause in one sentence.
   The W59 row will be corrected from this sentence.
6. Six mutants, each shown red on the self-test that catches it:
   - (i) the helper ignores the pinned instant;
   - (ii) `BENCH_CLOCK` pinned at import, or not restored when `main()` raises;
   - (iii) a replay miss on a `mark_missing` request answered as "no record";
   - (iv) a negative entry served as `NOT_FOUND` to a call without `mark_missing`;
   - (v) a replay with misses writing its output files;
   - (vi) the fill requesting a URL that already has an entry, or a listed URL twice.

   Restore the file after each and clear `__pycache__` (`CLAUDE.md`: a stale `.pyc` makes a mutant
   lie).
7. `git diff --stat <base>..HEAD`: only files in scope.
8. A scan of the added lines of `git diff <base>..HEAD`, plus the new test file and fixtures in
   full, for non-ASCII characters: none. (The three code files in scope already carry non-ASCII
   on lines this task does not touch: `src/risk.py` on 15 lines, `bench/run_benchmark.py` on 25,
   `bench/fetcher.py` on 5, each from line 1.)

## Notes

**Settled by the lead (2026-10-08).**
1. **Which final answers are persisted: every final 4xx except 429, in dated mode only.** The
   fetcher already treats 400 to 499 other than 429 as final and does not retry them; it retries a
   429. This is what lets T-019 reach zero misses on this dataset: the zero-address honeypot.is URL
   answers 400 (measured, Context), and its negative entry replays as the failed fetch the
   committed file records ("upstream request failed"). The 5 GeckoTerminal misses are
   display-truncated pool ids, two of them measured 404, so a fill is expected to record them too.
   AC 3 carries the rule; its 400 test case and mutant (iv) (unchanged) cover the served-back side.
2. **Runs on a fresh clone measure today's answers at a September clock: accepted.** No criterion
   changes. Two places run the benchmark without this cache:
   - the weekly CI `benchmark` job (`test.yml`, schedule and manual runs only), which builds a
     fresh dataset and runs `run_benchmark.py` in fetch mode;
   - the public recipe, which tells strangers to clone and run `python bench/run_benchmark.py`:
     the /method page (`src/pages.py`, about line 367, "re-measures against live upstreams"),
     `README.md` (about line 145), `docs/EXPERIMENT_C.md` (about line 208) and
     `docs/AUDIT_BRIEF.md` (about line 67).

   A fresh clone has no `bench/cache`, so after this task such a run combines today's live answers
   with ages computed at `BENCH_CLOCK`. A best pair created more than 2 days after that instant gets
   no age, so no freshness signal and no gap. One created within 2 days reads "Very new pair". AC 2
   prints how many such rows there are, so the loss is visible in the output, but the figures stay
   degraded. The job's own comment says its figures are not published. The recipe's output is not
   published either, but a stranger compares it with the published page.

   Rewording the public recipe is follow-up 4, parked by the lead as a backlog row and out of
   scope here. `src/pages.py`, `README.md` and `docs/` stay unchanged in this task.

**Not in parallel (batch check, 2026-10-08).** This task edits `src/risk.py` and
`.github/workflows/test.yml`. T-012, T-013 and T-019 depend on it and start after its merge.
Five tasks have no order against it and share a file: T-016 and T-017 edit both files, T-018
(after T-017, not before 2026-10-17) edits `src/risk.py`, and T-014 and T-015 each add a
`test.yml` step before the same anchor step. Never run any of them in parallel with this task.
Whichever lands first moves the other's base: AC 8's step count is counted from the base at
dispatch, and line numbers in `src/risk.py` drift (the function names hold).

**Risks.** Level 2 per the lead: the engine change is an injection point that changes no served
answer. The reason it could be Level 3 is closed by ACs 1(c), 1(d) and 2, and the mutants above
must show them failing. The fill is a path that writes into the only copy of the cache when it is
run; this task builds and tests it on temporary directories and never runs it for real. What must
never happen:
- **(a) A served answer computed at a pinned clock.** A pool created more than 2 days after the
  pinned instant reads as no age: no freshness signal and no gap. A brand-new pool would lose its
  "Very new pair" critical signal, which fails open on the highest-risk window. Realistic causes:
  pinning at import, a missed restore, a setter in `src/`, or a changed default.
- **(b)** A replay with misses writing moved figures into `bench/results.*`, from where
  `regenerate-derived.sh` would publish them.
- **(c)** An unrecorded answer replayed as "no record": an unobserved absence impersonating an
  observed one (E11). It moves 2 rows' gap reasons even when no verdict moves.
- **(d)** A negative entry read as data, or as `NOT_FOUND` by a caller that did not ask for it,
  or a negative entry for a status other than 404 read as `NOT_FOUND` by any caller.
- **(e)** A change to what the snapshot collector, the dataset builder or production caches, or to
  the shape of their entries.
- **(f)** Writes into the main checkout's `bench/cache`, the only copy, during this task.
- **(g)** A test that cannot fail. Real dates after early October cannot fail, and neither can a
  fixture whose verdict the clock does not move.
- **(h)** A fill that requests a URL it was not given, requests one twice, or writes anything other
  than the entries for its listed URLs.

**Hints:**
- **The cache is not in the worktree.** `bench/cache/` is git-ignored, so the executor's worktree
  has none. Point the fetcher's module-level `CACHE_DIR` at the main checkout's `bench/cache` from
  a scratch harness, and only ever in replay. `fetch_json()` and the access-log functions read
  `CACHE_DIR` and `ACCESS_LOG_PATH` at call time, so tests can redirect both to a temporary
  directory, along with `run_benchmark.DATASET`, `RESULTS_JSON` and `RESULTS_MD`. Replays are
  read-only and quick, but run them one at a time anyway (`CLAUDE.md`: never two benchmarks at
  once).
- **How the clock reaches each token.** `asyncio.run()` copies the current context into its task,
  so a value pinned in `main()` before the loop reaches every `assess()`. Reset it with the token
  `ContextVar.set()` returns, in a `finally`. `_begin_request()` resets the other two context
  variables at the start of every `assess()`; the clock must not join them.
- **Reading the wall clock.** The helper reads `datetime.now(timezone.utc)` through `risk`'s module
  global `datetime`, which is what lets tests replace it (ACs 1 and 6). The replays in Context did
  exactly that.
- **State the tests must save and restore.** `install_engine_fetcher()` replaces
  `risk._fetch_json` and never restores it, and `fetcher._ACCESS_LOG` accumulates across runs in
  one process. Tests that call `main()` must save and restore the first and reset the second.
- **Sleeping.** `_throttle()` sleeps up to 2.1 s per host and retries back off with
  `time.sleep()`. Fetch-mode and fill tests must replace both; replay must not reach them.
- **Status codes.** `main()` returns 1, 2 and 3 today. This task adds 4 (replay missed), 5 (bad
  arguments or fill file) and 6 (fill left a URL unrecorded). argparse exits 2 on an unknown
  argument by default, so an argparse-based parser needs its error path overridden.
- **Comments in `src/risk.py`.** `tests/test_http_telemetry.py` (about line 515) requires every
  `https://` host written there to be named on the privacy page, so write no URL, even in a
  comment. `tests/test_owner_power_recall.py` scans the file for fraction words ("about a third
  of ...") and percentages, so write neither. `tests/test_risk.py` (about line 4121) reads the
  comment block that ends at `age_minutes = _minutes_since_rugcheck_indexed`, so leave that
  block and that line's text as they are. The AST scan of data gaps (about line 5372) means:
  add no data gap.
- **Where the acceptance tests go.** Put them in the new file, not in `tests/test_risk.py`,
  `tests/test_mcp.py` or `tests/test_http_telemetry.py`: `bench/scorecard.py` copies those three
  files' pass counts into `docs/SCORECARD.md`, so a check added there moves a derived page.
- **Writing files.** Use the Write or Edit tool, not shell heredocs, for anything with backslashes
  (`CLAUDE.md`). Those tools decode backslash-u escapes into real characters (`lead/PITFALLS.md`).
- **Scratch.** Scratch files go in your own subfolder of the session scratchpad; the rest of it
  belongs to other agents.
- **Upstream statuses.** Measured: the zero-address honeypot.is URL answers 400 (2026-10-07), and
  GeckoTerminal answers 404 to the truncated pool ids of THQ and USDT0 (investigation,
  2026-10-07). Unverified: the other three truncated ids.

**Conflict search (2026-10-08).** Each line below was run as
`git grep -n -e "<s>" -- 'tests/test_*.py' 'tests/fixtures/**'`, and every hit was read.
- **Fetcher and benchmark harness:**
  - `fetcher`, `fetch_json` (stubs of `risk._fetch_json` in `test_risk.py` and `test_mcp.py`;
    they replace the engine's fetch and are unaffected);
  - `NOT_FOUND` (`test_sellability_archive.py`, through `snapshot.NOT_FOUND`, unchanged);
  - `mark_missing`, `write_cache`, `use_cache` (the archive test asserts `use_cache` is False on
    the snapshot call);
  - `CACHE_DIR`, `run_benchmark` (the import above; no test calls `main()`),
    `install_engine_fetcher`, `bench/cache` (exempted by `test_english_only.py`), `results.json`;
  - `access_log`, `ACCESS_LOG`, `endpoint_of`, `note_endpoint`, `access_report` (no hits).
- **Engine clock and freshness:**
  - `_age_days` (`test_risk.py`, explicit `now`; `test_coverage_matrix.py` has its own local
    function of that name);
  - `risk.datetime` (no hits), `datetime.now` (the wall-clock tests named above),
    `_minutes_since_rugcheck_indexed` (the comment-block reader);
  - `_STALE_HITS` (`test_risk.py` sets it, unrelated), `_FETCH_FAILURES`, `ContextVar`,
    `contextvars`;
  - `pair_age_days`, "Recently created pair", "Established pair", "Very new pair",
    `pairCreatedAt` (fixed timestamps from 2020 and 2025, all "Established" under the wall clock
    and so unchanged; the wall-clock-relative pairs, about lines 1398 and 3692, keep the wall
    clock);
  - `_now_iso`, `checked_at`, `freshness`.
- **Test runners:** `startswith`, `def main(` (`test_decisions_enforcement.py` reads every test
  file's runner; named above).
- **Names this spec introduces:** `replay`, `--fill`, `fetched_at`, `dated`, `BENCH_CLOCK` (no
  colliding hits; `dated` appears only in prose in `test_owner_page.py`); `not_found` (hits are
  the liquidity tool's `status` value in `test_risk.py`, unrelated: no test reads a cache file).
- **Tests reading `src/risk.py` as text:** `"risk.py"`, `ast.parse`, `inspect.getsource`.

Also checked:
- `git grep` over `bench/` and `tools/` for code that reads `bench/cache` files: the only reader
  is `fetch_json()` itself (`blob.get("data")`, about line 104), so an added `fetched_at` key is
  invisible to it, and nothing expects every entry to carry `data`.
- The other `fetch_json()` callers and their shapes: `bench/build_dataset.py` (about lines 139,
  290 and 300, defaults), `bench/backfill.py` (about line 467, defaults), `bench/snapshot.py`
  (about line 148, `use_cache=False` with `write_cache` defaulting to True, and about line 371,
  `use_cache=False, write_cache=False, mark_missing=True`). With `dated` False they are unchanged.
- `docs/DECISIONS.md`: no recorded decision about bench-cache 404s.
- The baseline at the base commit: `tests/test_risk.py` 706 passed, `tests/test_http_telemetry.py`
  163 passed, `tests/test_sellability_archive.py` 60 passed, `tests/test_owner_power_recall.py`
  all passed.

**Follow-ups for the lead to park:**
1. **Freeze each answer at its own fetch time.** This is the more honest semantics, but it would
   move published figures with no engine change: the cached pairs' ages at their fetch dates
   differ from their ages at the pinned instant by up to 18 days. Entries written after this task
   carry `fetched_at`; the 6647 older ones have only file times.
2. **T-019, "Fill the frozen benchmark's cache misses once, and re-baseline the published
   benchmark on it" (Level 3; depends on this task; T-012 and T-013 depend on it).** Replay at
   `BENCH_CLOCK`, give its URL lines to `--fill` once against the main checkout's cache, replay
   again, and fill only new misses, never a URL that has an entry (T-019 AC 3), until the list is empty or stops
   shrinking. With the clock pinned, every row that then moves against the committed file is live
   drift, to be reported as its own figure before anything is published, and the re-measured
   results are committed. Expected from the 2026-10-07 live sample: some "no record" rows now
   answer (1 of 13 sampled).
3. `results.md` stating the pinned clock and the replay's miss count, which changes a published
   page; this goes with T-019.
4. The public recipe (the /method page, `README.md`, `docs/EXPERIMENT_C.md`,
   `docs/AUDIT_BRIEF.md`) naming `--replay` and saying what a cold run measures at a pinned clock
   (Notes, settled item 2). These are published pages; the lead parks this as a backlog row.
5. `CLAUDE.md` "The order that matters" naming `--replay` for re-measurement, and the W59 row
   corrected with the CHIP cause (lead bookkeeping).

## Amendments

### (a) Release-base and evidence-sequence clarification (2026-10-11)

Dispatch from c18de92 after the independently reviewed T-016 merge and published T-020
repair. The dispatch baseline has thirty offline steps; the archive acceptance has 167
passing checks. Preserve the snapshot-only absolute HTTP limits, bounded recovery, safe
diagnostics and ordinary fetcher behavior. No original acceptance assertion changes.

Evidence item 1's words "before pinning" and "clock comes from the branch" describe two
different stages. Before implementation, the disposable historical-confirmation harness
may replace risk's wall-clock class only in its own process to establish the candidate
instant and whole-hour reproduction window, with no source/cache writes or network calls.
At the head, the final reproduction harness uses the actual branch's BENCH_CLOCK pin and
must not replace the clock helper or set its context variable itself. Its simulated wall
clocks remain as AC 7 requires. This clarifies evidence order; no expected figure, fixture,
production-clock rule, acceptance threshold or output requirement changes.
