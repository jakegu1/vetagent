---
id: T-019
title: Fill the frozen benchmark's cache misses once, and re-baseline the published benchmark on it
status: in_review        # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: [T-011]      # never in parallel with T-014, T-015 or T-018 (Notes, Hints)
decisions: [ADR-0001]
backlog: W59             # the second half: running T-011's fill for real and re-measuring on it
---

## Context

T-011 makes the benchmark (`bench/run_benchmark.py`, the 576 tokens of `bench/dataset.json`) a
deterministic replay. While the benchmark runs, it pins the engine's clock to `BENCH_CLOCK`
(expected 2026-09-21T02:00:00Z), and it adds two options:

- **`--replay`** never touches the network. It serves every request from `bench/cache/`, answers
  a request with no entry as a failed fetch (None), and records that as a miss.
  - With no miss it writes `bench/results.json` and `bench/results.md` and exits 0.
  - With one miss or more it writes neither file and exits 4. It prints the number of missed
    requests, that number per host, and each distinct missed URL alone on its own line, so the
    printed lines starting with `https://` form a valid fill file.
- **`--fill FILE`** asks only the URLs listed in FILE, and only those with no cache entry: one
  `fetch_json(url, role="engine", retries=2, dated=True)` call per distinct URL, throttled as in
  fetch mode. It writes only dated entries:
  - a success, with `url`, `data` and `fetched_at`;
  - a final 4xx other than 429, as a negative entry with `url`, `status` and `fetched_at`
    (`not_found: true` is added only for a 404, and there is no `data` key);
  - nothing for a 5xx, a 429, a timeout or a connection error.

  It reports each URL as already recorded, stored answer, stored 4xx or not stored, with counts
  per host. It exits 0 when every listed URL has an entry afterwards, 6 when one does not, and
  5 on a bad file (before any network access).

A replay serves a negative entry the way the live call returned it: `NOT_FOUND` only for a 404
asked with `mark_missing`, None otherwise. The existing statuses stay: 1 (no dataset), 2
(independence overlap) and 3 (no labelling endpoints on record).

T-011 builds and tests the fill on fakes only and never runs it against a real upstream. At its
head, on the real cache, `--replay` exits 4 with 91 missed requests over 89 distinct URLs
(expected; T-011 AC 7(a)):
- honeypot.is: 86 requests over 84 URLs, all with `mark_missing`. 19 of these URLs are `&pair=`
  retries.
- GeckoTerminal: 5 requests over 5 URLs. These are the display-truncated pool ids that T-013
  fixes.

T-012 (AC 7) and T-013 (AC 6 step 1) both need a base where a replay misses nothing and
reproduces the committed results. This task builds that base. It runs the fill for real, once,
and re-baselines the published benchmark on what the fill recorded.

**What the committed measurement read for those URLs.** `bench/results.json` was last written by
`cfa42f6` (2026-09-21, 02:32 UTC) and `bench/results.md` by `4d86202`. Their missed URLs were
asked live during that run and never cached. T-011 reproduced both files byte for byte from the
cache at the pinned clock (T-011 Evidence item 1 and AC 7(b)). It did so by answering each
missed request the way the committed file records it. That gives each URL its **committed
reading**:

| Missed request | Committed reading |
|---|---|
| honeypot.is, with `mark_missing`, except the zero-address URL | "no record" (`NOT_FOUND`) |
| the zero-address honeypot.is URL (`address=` 0x followed by forty zeros, `chainID=1`) | failed fetch (None) |
| GeckoTerminal (every request) | failed fetch (None) |

**Measured on `4838fdd` by the spec writer (2026-10-08, read-only):**
- In the committed `results.json`:
  - 65 rows carry the gap "about the token: the sell simulator has no record of this token";
  - 2 rows carry "upstream request failed". These are BNB (bsc) and ETH (ethereum), whose
    address is the zero address;
  - 4 rows carry "upstream request failed: no distinct-seller count to settle a contested
    honeypot verdict": THQ, USDT0, Surplus (base) and RALLY (ethereum). ROBOTMONEY (base,
    `high` 100) is the fifth GeckoTerminal request.
- `bench/cache/` holds 6647 files, 85 MB. It is git-ignored, it exists only in the main
  checkout, and there is no other copy of it.
- At this commit, `publish_numbers.figures()` returns 116 keys. Its `TARGETS` write them into
  seven files:
  - `docs/EXPERIMENT_C.md` (122 patterns);
  - `src/pages.py` (81);
  - `src/landing.html` (34);
  - `src/entry.py` (14);
  - `README.md` (10);
  - `docs/SCORECARD.md` (5);
  - `docs/OWNER.md` (1).

  `docs/AUDIT_BRIEF.md` is a live claim file with no pattern.
- The dead cohort has three `high` rows: SYP, TSLA and GALE (all base, driver `honeypot`). None
  carries a gap, and their honeypot answers are cached. So the fill is not expected to move
  `dead_high_pct`. This is an inference, not a measurement; its one consequence is in the
  Notes, under `tests/test_owner_page.py`.

**Measured live by the 2026-10-07 investigation.** 13 of the "no record" tokens were asked
again, and 1 of 13 answered differently. CTM (bsc) now answers HTTP 200 with a successful
simulation, where the committed run read "no record". The zero-address URL answers 400
"Invalid Address" (T-011 Context); the fill stores that as a negative entry, which replays as
the same failed fetch. GeckoTerminal answered 404 to the truncated ids of THQ and USDT0; the
other three ids are unverified.

**Expected, not targeted:**
- CTM (bsc) leaves `unknown`.
- CTM (ethereum) has CTM (bsc)'s address and the same committed `engine_pool`, so it probably
  asks the same honeypot.is URL and moves with it. This is an inference, consistent with the
  first miss list (86 requests over 84 URLs leave one shared URL besides the zero-address one).
  The attribution harness (Notes) decides, not the shared address.
- CHIP (base) has one missed request, its `&pair=` retry. If that retry now answers with a
  sellable simulation, CHIP moves to `low` 0; otherwise it stays `unknown` 30 (T-011 Evidence
  item 5).
- Any other row that requested a missed URL can move with live drift that the sample did not
  see.

**Where a moved figure goes.** `bash .github/scripts/regenerate-derived.sh regenerate` runs four
generators to a fixed point: `bench/scorecard.py --write`, `bench/publish_numbers.py --write`,
`tools/owner.py --write` and `tools/rounds.py --write`. `publish_numbers.py` rewrites the seven
files listed above, three of them under `src/`. A push touching `src/` deploys to production,
so the push waits for the Owner's yes (`lead/config.yml`, `sign_off`), as every push does.

Nothing rewrites the hand-written sentences that quote a figure. These are the prose of
`docs/EXPERIMENT_C.md` around its patterns, and `docs/AUDIT_BRIEF.md`.

**The lead's binding decisions:**
- T-011 builds the fill and does not run it. This task runs it for real, once, on the replay's
  miss list.
- The steps, in order:
  1. On the merged T-011 base, run the replay and save its miss list.
  2. Run `--fill` on exactly that list: live, paced as the fetcher paces, with the URL count and
     every non-200 answer logged.
  3. Re-run the replay and show zero misses.
  4. Compare the new `bench/results.json` with the committed one, row by row.
- **The pre-registered rule for step 4, written before the run.** The engine has not changed.
  So every row whose verdict, score or driver moves must be explained by an upstream answer that
  changed between the committed run (2026-09-21 UTC) and the fill. For example, CTM on bsc now
  answers 200 where it answered 404. A moved row with no changed answer behind it is BLOCKED,
  not published. The READY report lists every moved row, with the URL whose answer changed.
- **If any published figure moves,** publish it through the project order: the replayed
  results, then `bash .github/scripts/regenerate-derived.sh regenerate`, then every test.
  - The commit message names each moved figure.
  - It says the move is upstream answers re-read at the pinned clock, not an engine change.
- **If nothing moves,** the task commits nothing under `bench/` except what the order requires,
  and the READY report says "no published figure moved".
- The executor works in the main checkout, on a task branch, because that is where the cache
  is. It never works on a worktree copy of `bench/cache`, and it never runs two benchmarks at
  once.
- No code change in `src/` or `bench/` is in scope. If the fill or the replay misbehaves, that
  is a T-011 defect: stop BLOCKED with the evidence.
- Out of scope: rewording the public reproduction recipe (parked), any engine fix, and any
  change to bands, floors or scorecard rules.
- Hand-written passages that quote a moved figure are listed in the READY report and not edited.
  The lead rewrites them before the push, and the Owner sees them in the push batch.

**Decided by the spec writer within those decisions, and confirmed by the lead on 2026-10-08.**
- **"What the order requires."** The replay's files are committed whenever they differ from the
  committed ones by any byte, even if no published figure moved. T-012 and T-013 need exactly
  that at their base: a zero-miss replay that leaves `git status --short` empty.
- **The alternation and its budget (AC 3).** T-011 anticipates that a changed first answer can
  lead the engine to a `&pair=` retry nobody asked before. So replay and fill alternate, with at
  most three fills in all.
- **One retry of an unstored URL.** A URL that a fill left unstored may be given to one later
  fill, at least an hour afterwards. An unstored URL has no recorded answer, so asking again does
  not choose between answers. This is a narrowing of T-011's "fetching no URL twice": a URL that
  has an entry is never asked again.

**What this hands T-012 and T-013.** At this task's merge, `--replay` misses nothing and
reproduces the committed results.
- T-013 (AC 6) then fills only its own five full-id URLs.
- T-012 (AC 7) pre-registers its row list on this base.
- Both read their figures "at `4838fdd`" as shifted by the rows this task moves. The READY
  report's moved-row table is what they read.
- T-012's WMAI and fwARB rest on honeypot.is "no record" answers that this fill asks again. If
  either answer changed, T-012's list changes, which its AC 7 already allows.

## Goal

When this task is done:
- In the main checkout, `python bench/run_benchmark.py --replay` misses nothing, exits 0, and
  leaves `bench/results.json` and `bench/results.md` unchanged, because those files were written
  by that replay.
- Every row that moved against the 2026-09-21 measurement is traced to an upstream answer that
  changed.
- Every published figure that moved is regenerated from the re-measured results, not typed.

## Scope

**In:**
- In the main checkout, on a task branch:
  - the first replay;
  - the fill on its miss list, alternating with replays under AC 3;
  - the final replay.
- AC 1's reproduction harness, the attribution harness (Notes), the row-by-row comparison and
  the figure comparison. These are scratch scripts and are never committed.
- Committing the replay's results files, running the regeneration script, committing what it
  moved, and running every test.
- The READY report's lists: moved rows, moved figures, hand-written passages.

**Out:**
- **Any change to code, tests or workflows:** `src/risk.py` and every other engine file,
  `bench/*.py`, `tools/`, `tests/` and `.github/`.
  - A replay or fill that misbehaves is a T-011 defect: stop BLOCKED with the evidence.
  - An engine that crashes on a new answer, or misreads one, is an engine defect: also BLOCKED.
- **A fetch-mode run** (`python bench/run_benchmark.py` with no argument). It asks every
  uncached URL again and writes into the cache outside any list.
- **Changing the cache by any route other than `--fill`.** Do not edit, delete or add a cache
  file by hand. Do not restore the copy except under AC 2.
- **Any request outside a `--fill` run**, and any request to production.
- **Hand-written passages that quote a moved figure.** They are listed (AC 5), not edited.
- **T-011's parked follow-ups:**
  - rewording the public reproduction recipe (follow-up 4);
  - `results.md` stating the pinned clock and the miss count (follow-up 3). That is a
    `write_markdown()` change, so it is code in `bench/`;
  - freezing each answer at its own fetch time (follow-up 1).
- **Bands, floors, scorecard rules, `TARGETS` patterns and exemptions.** These are sign-off items:
  fix the data, never the bar.
- **Other tasks' work.** T-013's five full-id GeckoTerminal URLs (T-013 fills its own list), and
  T-012's rule change.
- **Merging and pushing.** These belong to the lead, with the Owner's yes.

## Files in scope

- `bench/results.json` and `bench/results.md`, written only by the final `--replay`.
- The files that `bash .github/scripts/regenerate-derived.sh regenerate` writes, and only as it
  writes them:
  - `docs/SCORECARD.md`, `docs/OWNER.md`, `docs/ROUNDS.md` and `docs/EXPERIMENT_C.md`;
  - `README.md`;
  - `src/pages.py`, `src/landing.html` and `src/entry.py`.
- `bench/cache/` in the main checkout. It is git-ignored, so none of it is committed. Only the
  fill writes to it, and only dated entries for listed URLs.
- Acceptance tests: none. This task changes no code; AC 8 says what its first commit is instead.
- **Named changes to existing tests:** none. The conflict search is in the Notes. If an older
  test is red at the head and is not red, with the same failing checks, in the same-day base run
  (AC 8), stop BLOCKED.

## Acceptance criteria

1. **The base is the one T-011 measured, confirmed before any live request.**

   Set up:
   - Work in the main checkout, on a branch `task/t-019-benchmark-fill-and-rebaseline` made from
     `master` with a clean tree, and with no other benchmark running.
   - Clear `__pycache__` (`CLAUDE.md`).

   Then confirm, before any fill:
   - **T-011 is merged** into the base, and `python tests/test_benchmark_replay.py` passes there.
   - **The committed files are the ones the rule was written against.**
     `git log -1 --format=%h <base> -- bench/results.json` prints `cfa42f6`, and the same command
     for `bench/results.md` prints `4d86202`.
   - **The cache is protected.** Take a manifest of every file under `bench/cache/` (relative
     path, size, SHA-256), and copy the whole directory into your scratch folder.
   - **The first replay matches T-011.** `PYTHONIOENCODING=utf-8 python bench/run_benchmark.py
     --replay` exits 4, and:
     - its printed clock is `BENCH_CLOCK` as merged;
     - its count of rows whose best pair was created after that clock is 0;
     - its miss count, its per-host counts and its distinct URL lines equal what T-011 recorded
       for its AC 7(a) at merge (`lead/reviews/T-011.md` or its READY report). Expected: 91
       requests over 89 URLs; honeypot.is 86 over 84; GeckoTerminal 5 over 5;
     - a second manifest equals the first.
   - **The engine still reproduces the committed files.** AC 4's rule assumes an unchanged
     engine, and nothing above checks it: a replay with misses writes no file to compare. At this
     writing, T-016 and T-017 are `ready`, edit `src/risk.py` and have no ordering against this
     task; T-014 edits `bench/scorecard.py`, and T-018 rewrites `docs/SCORECARD.md`. So, before
     any fill, rebuild T-011's
     Evidence item 1 harness at the base, offline:
     - it answers each request with no cache entry by the Context table (a request the table
       does not cover, as a failed fetch), and records each substitution with its URL and the
       row being assessed (chain, address);
     - it leaves the clock to the base's own pin, and writes its outputs to scratch
       (`RESULTS_JSON` and `RESULTS_MD` redirected);
     - it replaces `urllib.request.urlopen` with one that records any call and raises. The
       fetcher catches that exception, so the record is what shows a request escaped: one
       recorded call is BLOCKED;
     - it runs alone, and a manifest taken afterwards equals the first.

     Then:
     - its two outputs equal `git show <base>:bench/results.json` and
       `git show <base>:bench/results.md`, compared with line endings normalized;
     - its substitution count equals the first replay's missed-request count, and its
       substituted URLs, as a set, equal the first replay's URL lines;
     - record `git log --oneline 4838fdd..<base> -- src/ bench/`.
   - **The first fill file is the replay's output.** Its URL lines (the printed lines starting
     with `https://`) are saved, unedited, as the first fill file.

   Any difference is BLOCKED before any fill, with the replay's output and, for the harness,
   its own.

2. **Each fill asks only its listed URLs, at most once each, and the rest of the cache stays
   byte-identical.**

   Run `PYTHONIOENCODING=utf-8 python bench/run_benchmark.py --fill <fill file>`. Send its
   output to a log, and record its exit status separately. Note its start and end times (UTC).
   - It exits 0 or 6. If it exits 5, the file is malformed: fix the file, not the tool (Notes).
   - **Only listed URLs gain files.** Compare a manifest taken afterwards with the one before.
     The only difference is added files, one for each URL the fill reported as stored answer or
     stored 4xx. Each is named for the first 40 hex characters of that URL's SHA-256, and its
     `url` field is that URL. No file is changed or removed.
   - **Each added file has T-011's dated shape:**
     - a stored answer has exactly `url`, `data` and `fetched_at`;
     - a stored 4xx has exactly `url`, `status` and `fetched_at`, plus `not_found: true` when
       `status` is 404;
     - in both, `fetched_at` lies between the fill's start and end (UTC).
   - **A stored 4xx is a 404, or a 400 on the zero-address URL.** T-011 stores every final 4xx
     except 429, and a URL with an entry is never asked again, so an access block (for example
     401 or 403) would be kept as the answer for good. A stored 4xx whose status is neither 404
     nor (for the zero-address URL only) 400 is BLOCKED before any later replay is used. Keep
     the entries, report each one's host, rows and status, and stop; the lead decides.
   - **The log is kept.** It holds the URL count per host and each outcome count per host. It
     also holds every non-200 answer with its status; for "not stored", it holds what the fill
     printed about that URL.

   If any file other than these was added, changed or removed:
   1. restore `bench/cache/` from the copy;
   2. check that the restored manifest equals the first one;
   3. stop BLOCKED. This is a T-011 defect.

3. **Replay and fill alternate until nothing is missed, within a fixed budget.**

   After each fill, run `--replay`, and take a manifest afterwards; it must be unchanged.
   - **If the replay misses nothing,** it exits 0 and writes both results files. Go on to AC 4.
   - **Otherwise,** its URL lines become the next fill file, under four rules fixed now:
     - At most three fill runs in the whole task.
     - Every URL in the file is one of two kinds:
       - a URL no fill has been given. This is a request first reached through a changed
         answer, such as a new `&pair=` retry;
       - a URL that exactly one earlier fill reported as not stored, where that fill ended at
         least one hour before.
     - A missed URL that already has a cache entry, or that two fills have already been given,
       is BLOCKED. Either the replay and the fill disagree about what is recorded, or the
       upstream will not answer.
     - Each replay's miss list is shorter than the one before it. If it is not, that is
       BLOCKED.
   - **A replay that still misses after the third fill** is BLOCKED, with its list.
   - **Never ask again for an answer you already have.** A URL with a cache entry is never
     requested again; the fill skips it by construction. No fill is ever run to get a different
     answer for a URL that has one.

4. **Every moved row is explained by an upstream answer that changed (pre-registered).**

   This rule was fixed before any fill: this spec was committed under `lead/tasks/` before
   dispatch. It does not change after the run. Compare the final replay's `bench/results.json`
   with the base's, row by row, keyed by chain and address.
   - **The rows are the same rows.** `n_evaluated` and the set of rows are identical. Otherwise
     BLOCKED.
   - **Changed answer.** Each URL a replay missed has its committed reading (the Context
     table). After the fill, the replay serves it as T-011 AC 3 says:
     - a stored answer, as its data;
     - a stored 404, as `NOT_FOUND` to a `mark_missing` call;
     - every other stored 4xx, as None.

     The URL's answer **changed** when what the replay now serves differs from its committed
     reading. That is:
     - any stored answer;
     - a stored 4xx other than 404, where the committed reading was "no record" (AC 2 stops the
       run on any such entry first; it is listed so the definition is complete);
     - a stored 404 asked with `mark_missing`, where the committed reading was a failed fetch.

     A stored answer and a stored 4xx are both entries; a stored 4xx is a **negative entry**.
     A URL first missed after a fill (AC 3) has no committed reading. It is listed, but it does
     not count as an explanation on its own.
   - **Attribution.** Attribute each missed URL to the rows that requested it, with the
     attribution harness in the Notes, run on the first state (AC 1's harness) and on the final
     state. Every missed URL is attributed to at least one row.
   - **The rule.** A row whose `verdict`, `score` or `driver` differs from the base is
     **moved**. Every moved row must have at least one attributed URL whose answer changed.
     - A URL linked to a row only by address does not explain that row's move.
     - A row that leaves `high` or becomes `low`, and whose only changed attributed answers are
       negative entries, is BLOCKED (threat (g)).
   - **Every other difference is BLOCKED too.** The engine is the one AC 1 checked, so a row
     with no changed answer behind it is identical in every field. A row with no changed answer
     behind it that differs in any field is BLOCKED, as a moved row is. Published figures read
     more than verdict, score and driver: `verdict_ablated` feeds `adversarial_high_ablated_pct`
     and `dead_not_low_ablated_pct`, `gap_reasons` feeds `unknown_simulator_n` and
     `unknown_unbacked_n`, and `has_data_gap` feeds `data_gap_rate`. A row with a changed answer
     behind it may differ in any field, and is listed.
   - **The `independence` section** of `results.json` is identical to the base's, otherwise
     BLOCKED. One exception: an `engine_endpoints` entry added or removed only by URLs in a miss
     list, each attributed by the harness to a row with a changed answer behind it (a changed
     answer can lead the engine to a request it never made before). `label_endpoints` is
     identical and `overlap` is empty in every case.
   - **No pair after the clock.** On the final replay, the run summary's count of rows whose
     best pair was created after `BENCH_CLOCK` is 0. Any other count is BLOCKED, with its rows:
     the engine reads such a pair's age as 0 or as no age at all (T-011 Notes).

   If anything in this AC is BLOCKED, stop and commit nothing:
   1. restore both results files to the base's version;
   2. leave the cache as the fills left it;
   3. report each row concerned, its differing fields (old and new values), and its attributed
      URLs.

5. **What moved is computed from the two files, and what nothing rewrites is listed.**
   - **Published figures.** In a scratch script, compute three things over the base's
     `bench/results.json` and over the re-measured one:
     - `publish_numbers.figures()`, with `publish_numbers.RESULTS` pointed at each copy;
     - `scorecard.benchmark_facts()`, with `scorecard.RESULTS` pointed at each copy;
     - the `## Total` line of `scorecard.render(*scorecard.score())`, with `scorecard.RESULTS`
       pointed at each copy (offline; `score()` runs three test suites).

     `figures()["maturity"]` comes from `docs/SCORECARD.md` (`_maturity()`), not from
     `results.json`, so the first computation returns the same total for both copies. The
     scorecard's bands can still move it (Notes, "The maturity total"). A different total is the
     moved figure `maturity`: commit 1 lists it, and the passage search below covers it.

     List every key whose value differs, old -> new. If nothing differs, the READY report says
     "no published figure moved".
   - **Nothing else moved.** After the regeneration (AC 6), `figures()` at the head differs
     from `figures()` over the base's copy (the first computation above, made before the
     regeneration) in exactly the listed keys. Any other difference is BLOCKED.
   - **Hand-written passages.** After the regeneration (AC 6), search for each moved key's old
     value with `git grep -n -w -F`. For a count of twenty or less, search for its English word
     too. Search the files in `publish_numbers.LIVE_CLAIM_FILES` and `lead/OWNER.md`.

     List every hit whose sentence quotes that figure: file, line and sentence. When unsure, list
     it. Edit none of them.

6. **Published through the project order, in one data commit and one page commit.**
   - **If nothing changed.** If the final replay left `git status --short` empty, nothing is
     committed. The READY report says so, and says "no published figure moved".
   - **Commit 1** is titled `T-019: re-measure the benchmark on the filled cache at the pinned
     clock`. It holds exactly `bench/results.json` and `bench/results.md`, as the final replay
     wrote them. Its message:
     - lists each moved row: symbol, chain, old and new verdict, score and driver, and the host
       and stored status of the changed answer behind it;
     - lists each moved figure, old -> new, or says "no published figure moved";
     - gives the fill dates (UTC, from `fetched_at`);
     - says that the moves are upstream answers re-read at the pinned clock `BENCH_CLOCK`, not an
       engine change.
   - **The red at commit 1.** Run `python lead/checks.py` at commit 1, with its output to a file
     and its exit status read on its own (`lead/PITFALLS.md`). If a figure moved, record the
     steps that turn red. Expected:
     - `tests/test_published_numbers.py`;
     - `tests/test_owner_page.py`, if a figure the Owner page shows moved.

     A step that is also red, with the same failing checks, in a base run made as AC 8 says
     and on the same day as this one, is named apart, as red for the calendar.

     Also record the output of `python bench/publish_numbers.py` (check mode).
   - **The regeneration.** Then run `bash .github/scripts/regenerate-derived.sh regenerate`,
     with its output to a file. It must reach a fixed point, and its exit status alone does not
     show that: after three passes that still move something, it prints a warning and exits 0.
     So all three hold:
     - it exits 0;
     - its output does not contain `still changing`;
     - a second `regenerate` run, before any file is restored or committed, leaves the hash of
       `git diff --binary` unchanged.

     Otherwise, for example because `publish_numbers.py --write` left a figure it cannot fix,
     stop BLOCKED with its output. Commit 1 stays on the branch.
   - **Commit 2** is titled `T-019: regenerate the pages the re-measurement moved`.
     - It holds what the script changed. The exception is a file whose only change is the
       generated date or the recent-commit list (`lead/config.yml`, `merge.after`): restore that
       file instead.
     - Its message says what the red at commit 1 looked like: the red steps, and the stale
       figures `publish_numbers.py` named.
     - Nothing in it is edited by hand. A reviewer who runs the script at commit 1 gets the same
       files with the same content, apart from those date lines.
     - If the script moved nothing, there is no commit 2.
   - **Then every test** (`python lead/checks.py`, AC 8).
   - **Only those files.** `git diff --name-only <base>..HEAD` lists no file other than
     `bench/results.json`, `bench/results.md`, and the files the script wrote (Files in scope).

7. **The hand-off holds at the head.** At the head, in the main checkout:
   - `PYTHONIOENCODING=utf-8 python bench/run_benchmark.py --replay` misses nothing and exits 0;
   - `git status --short` is empty afterwards;
   - the replay's count of rows with a best pair after the clock is 0;
   - a cache manifest equals the one taken after the last fill.

   This is the precondition that T-012's AC 7 and T-013's AC 6 step 1 read.

8. **Contract and checks.**

   **This task adds no code and no test.** So its first commit is commit 1 of AC 6, the data
   commit, or there is no commit at all. The tests-first contract still holds, in what it is for:
   - **What judges the work is fixed before the work.** AC 4's rule and AC 3's budget were
     committed in this spec before dispatch, and the first miss list is saved before the first
     fill (AC 1). The SHA of the spec's commit is evidence; it must precede the first fill.
   - **The guard is watched red before it goes green.** The guards that judge published figures
     already exist. They are seen red at commit 1 and green at commit 2, and commit 2's message
     says what the red looked like (invariant 8). If no figure moved, there is no red to show,
     and the READY report says so.
   - **How to read the kit's contract check.** The kit's `contract_check.py` reports BROKEN for a
     first commit that touches no test file. For this task that output is expected. The reviewer
     records it, and checks instead that commit 1 touches exactly `bench/results.json` and
     `bench/results.md`.

   **At the head:**
   - `python lead/checks.py` runs the same number of steps as at the base and leaves the tree
     clean. Every step passes and it exits 0, with one exception: a step red for the calendar
     alone (Notes, "Calendar"), which also makes the exit status nonzero. To tell which:
     - run the base's `python lead/checks.py` in a scratch clone at the base (it needs no
       cache), on the same machine and the same day as the head run (the dated checks read
       `datetime.date.today()`), each with its output to a file and its exit status read on its
       own;
     - a step red at the head counts as "as at the base" only if the same step is red in that
       base run with the same failing checks. Name each one, with its failing checks;
     - any other red step is BLOCKED. If the two runs fall on different days, run both again.
   - `python tests/test_benchmark_replay.py` passes.

## Evidence required

1. **The base (AC 1):**
   - the branch name, the base SHA and the T-011 merge commit;
   - the summary of `python tests/test_benchmark_replay.py` at the base;
   - the two `git log -1` lines;
   - the SHA of the commit that added this spec under `lead/tasks/`, and its time, which comes
     before the first fill;
   - the manifest summary (file count, total bytes), and where the copy is;
   - the first replay's summary (exit status, clock, after-clock count, miss counts per host, URL
     line count), set beside T-011's recorded figures;
   - AC 1's harness: its substitution count and URL set beside the first replay's, the
     normalized comparison with both committed files, the count of recorded `urlopen` calls (0),
     the manifest after it, and `git log --oneline 4838fdd..<base> -- src/ bench/`.
2. **Each fill (AC 2):**
   - the fill file's line count per host;
   - the start and end times (UTC) and the exit status;
   - the outcome counts per host;
   - every non-200 answer: host, the row or rows it belongs to, and its status (or "not stored",
     with what the fill printed);
   - every stored 4xx, checked against AC 2's status rule;
   - the manifest comparison (added, changed 0, removed 0) and the result of the shape check.
3. **Each later replay (AC 3):**
   - the same summary as the first replay;
   - for each later fill, its URLs and the rule under which each one qualified.
4. **The row comparison (AC 4):**
   - the counts of identical rows, rows that differ only outside verdict, score and driver
     (each with the changed answer behind it), and moved rows; and the count of rows that differ
     with no changed answer behind them, which is 0;
   - the moved-row table: symbol, chain, old -> new verdict, score and driver, and each
     attributed URL with its committed reading, stored outcome and `fetched_at`;
   - the attribution: the harness's rows for each URL on the first and the final state, its
     completeness check, and where the address cross-check disagrees with it;
   - the `independence` comparison, with any `engine_endpoints` entry added or removed and the
     URLs behind it;
   - for each row that leaves `unknown`, becomes `low` or leaves `high`, the stored answer's
     fields the engine read. For honeypot.is these are `simulationSuccess`, `simulationError`,
     `honeypotResult.isHoneypot` and the simulated taxes;
   - the URLs whose answer changed while their rows did not move.
5. **The figures (AC 5):**
   - the `figures()` and `benchmark_facts()` differences, and the `## Total` line for each copy,
     or "no published figure moved";
   - after the regeneration, the `figures()` comparison of the head with the base's copy;
   - a short summary, by section, of what changed in `bench/results.md`;
   - the list of hand-written passages.
6. **The commits (AC 6):**
   - the SHAs, `git show --stat` and full messages of commits 1 and 2;
   - at commit 1: the summary line, exit status and red steps of `python lead/checks.py`, and the
     check-mode output of `python bench/publish_numbers.py`;
   - both regeneration runs' output and exit status, and the two `git diff --binary` hashes;
   - `git diff --name-only <base>..HEAD`.
7. **The head (ACs 7 and 8):**
   - the replay summary;
   - `git status --short`, which is empty;
   - the final manifest comparison;
   - the summary line and exit status of `python lead/checks.py`, beside the same-day base run's
     (AC 8), with each red step and its failing checks in both;
   - the summary of `python tests/test_benchmark_replay.py`;
   - the output of `contract_check.py`, read as AC 8 says.
8. **Public text stays clean.** Commit messages name symbols and chains, not addresses or URLs,
   and carry no local path. URLs go in the READY report only.

## Notes

**Why Level 3, and why size S.**
- **Level 3:** this task changes published figures (`bench/results.*`, `docs/SCORECARD.md`, the
  /method page, `docs/EXPERIMENT_C.md`). It also writes, live and irreversibly, into the only
  copy of the cache.
- **Size S:** it adds no code. Its 8 criteria are steps and checks of one measurement.

**Threat model.** What must never happen, and its realistic causes:
- **(a) A published figure moves for a reason other than a changed upstream answer.**
  - Causes: the pinned clock is not applied; a negative entry is misread; state carries over
    between tokens; a stale `__pycache__` runs code other than the branch's; a replay reads a
    cache that a fill is still writing; an engine change merged into the base by another task.
  - Caught by AC 1's harness (the base's engine reproduces the committed files) and AC 4's rule
    (every row that differs in any field has a changed answer behind it).
- **(b) An answer is chosen rather than recorded.**
  - Causes: a URL is asked again after its answer was seen; a cache file is edited or deleted; a
    fetch-mode run; a fill run again "to see if it changes".
  - Prevented by AC 3's rules and the Out list.
- **(c) The only copy of the cache is damaged or lost.**
  - Causes: a fill overwrites an entry; a crash leaves a truncated file; `git clean -x` or `-X`
    in the main checkout, which delete ignored files; work done in a worktree.
  - Protected by AC 1's copy and manifests, and AC 2's restore rule.
- **(d) Figures written from a replay with misses, or from a partly filled cache.**
  - T-011's exit 4 writes nothing; AC 3 publishes only after a zero-miss replay; AC 7 checks the
    head.
- **(e) A figure typed by hand, a hand-written passage edited, or the script's output altered.**
  - ACs 5 and 6, including the reviewer's re-run of the script at commit 1.
- **(f) A code change hidden inside a data commit.**
  - AC 6's file list.
- **(g) A row rated less risky on a misread answer.** This is fail-open, against invariant 1.
  - Every row that leaves `unknown`, becomes `low` or leaves `high` shows the stored answer
    behind it (Evidence 4).
  - A negative entry must never be the answer that made a row less risky. A realistic cause is
    a wave of 401 or 403 answers from honeypot.is: stored for good, replayed as a failed fetch
    where the committed reading was "no record". WMAI and fwARB are `high` 70 on a "no record"
    answer, and a failed fetch excuses a token from the no-trace escalation.
  - Caught by AC 2 (a stored 4xx other than a 404, or a 400 on the zero-address URL, stops the
    run) and AC 4 (a row that leaves `high` or becomes `low` on negative entries alone is
    BLOCKED).
- **(h) A push before the lead rewrites the hand-written passages.** A live page would then
  state two values for one figure.
  - The push belongs to the lead, with the Owner's yes, batched with those rewrites.
- **(i) Two benchmarks sharing the cache at once.**
  - Nothing else runs in the main checkout during this task; T-012 and T-013 start only after
    the merge. AC 1's harness and the attribution harness are replays too: each runs alone,
    never beside a fill or another replay.
- **(j) An identifying record.**
  - The cache holds upstream answers about the dataset's public tokens, as it always has, and
    nothing about any caller.
  - Commit messages name symbols and chains (Evidence 8).
- **(k) A request to production, or to a new upstream.**
  - There is none. The fill reaches only the hosts on its list (expected: honeypot.is and
    GeckoTerminal), at the fetcher's own pacing, so no upstream's terms are newly engaged.

Out of the bar: an upstream answer that changes again after the fill. Its entry carries
`fetched_at`, and that is what a dated measurement is.

**Hints:**
- **Where you work.** The main checkout is the lead's checkout. The lead dispatches this task
  into it and does nothing else there until READY.
  - Run everything from the repository root.
  - Keep scratch files (manifests, logs, fill files, comparison scripts, the cache copy) in your
    own subfolder of the session scratchpad; the rest of it belongs to other agents.
  - Write scripts with the Write tool, not shell heredocs (`CLAUDE.md`).
  - Prefix runs that print non-ASCII with `PYTHONIOENCODING=utf-8`, because the console is GBK.
- **Exit statuses.** Never pipe a run into a condition: a pipeline's exit status is its last
  command's (`lead/PITFALLS.md`, 2026-10-02). Redirect output to a file, then read `$?`.
- **Fill file line endings.** If `--fill` exits 5 on a file cut from the replay's output, look
  for a stray carriage return. Fix the file, not the tool; exit 5 comes before any network
  access.
- **Timing.** The fetcher paces each host at about 2 seconds a request, so a fill of 89 URLs
  takes a few minutes. Replays are offline.
- **Attribution.** Attribute every missed URL with a scratch harness that calls
  `main(["--replay"])` with the engine fetcher wrapped. For each request whose URL is in any
  miss list, it records the row being assessed (chain, address). `RESULTS_JSON` and
  `RESULTS_MD` are redirected to scratch. It runs alone, never beside a fill or another replay.
  Run it on the first state (AC 1's harness does this) and on the final state. Address matching
  is only a cross-check.
  - Why not by address: three tokens share one address across two chains (CTM on bsc and
    ethereum, CHIP and ICP on base and ethereum). The honeypot.is URL takes its `chainID` from
    the chain of the pool the engine chose, not from the row's chain (`src/risk.py`, `hp_url`
    and `_SIMULATOR_CHAIN_IDS`), and the zero-address URL carries `chainID=1` for BNB on bsc.
    So an address match can tie CHIP (base)'s `&pair=` retry to CHIP (ethereum), which never
    asked it.
  - How to know the row: `main()` assesses tokens one at a time, in dataset order, so a wrapper
    around `risk.assess` can note the token. `install_engine_fetcher()` replaces
    `risk._fetch_json` inside `main()`, so wrap what that installed function calls, not
    `risk._fetch_json` itself.
- **Comparing with the committed files.** `core.autocrlf` is true in the main checkout, and
  `bench/results.md` is CRLF in the working tree. Judge "unchanged" through git
  (`git status --short`, `git diff --quiet`), and read the base's JSON with
  `git show <base>:bench/results.json`.
- **The replay writes its files in place.** On exit 0 it writes `bench/results.json` and
  `bench/results.md` itself (T-011 AC 4). Commit them from there, unedited.
- **Not in parallel (batch check, 2026-10-08).** The regeneration rewrites `docs/SCORECARD.md`,
  `docs/OWNER.md`, `docs/ROUNDS.md`, `src/pages.py`, `src/landing.html` and `src/entry.py`.
  T-014 regenerates the first three as well, T-018 rewrites `docs/SCORECARD.md`, and T-015 edits
  `src/landing.html`: never run this task in parallel with any of them. T-012 and T-013 start
  only after this task merges (threat (i)). T-016 and T-017 share no file with it (they edit
  `src/risk.py`, which this task only reads); one that merges before dispatch is in the base,
  and AC 1's harness is what shows the engine still reproduces the committed files.
- **How reviewers reproduce.** Reviewers work from the cache read-only. They run `--replay` at
  the head, in the main checkout, after the executor has finished. They read cache entries. They
  run the script at commit 1 in a scratch clone (it needs no cache). They never run `--fill`,
  and never a fetch-mode run.

**Conflict search (2026-10-08, at `4838fdd`).** This task changes no code, so the search is for
tests that read what a re-baselined `bench/results.json` moves. Each symbol below was run as
`git grep -n -e "<s>" -- 'tests/test_*.py' 'tests/fixtures/**'`, and every hit was read:
- `results.json`, `results.md`, `RESULTS`, `figures(`, `run_benchmark`, `scorecard.`,
  `SCORECARD`, `OWNER.md`, `EXPERIMENT_C`, `AUDIT_BRIEF`, `pages.py`, `landing.html`;
- benchmark values written as literals: `576`, `162`, `154`, `122`, `21.2`, `21.0`, `3.1`,
  `of 162`, `of 576`.

No test needs a change. These tests see the re-baseline:
- **`tests/test_published_numbers.py`.** Check mode compares every `TARGETS` figure with what
  `results.json` gives, and compares `docs/SCORECARD.md` with
  `scorecard.render(*scorecard.score())`. It is red at commit 1 for each moved figure and green
  after the regeneration: that is the watched red of AC 6. Its other checks build their stale
  values from `figures()` at run time ("one point above the measurement"), so no literal moves.
- **`tests/test_owner_page.py`.** It requires two things: `docs/OWNER.md` equals
  `owner.render()`, and the page shows `figures()` `n`, `fp_pct`, `unknown_pct` and
  `dead_high_pct`. It is red at commit 1 if one of those moved, and green after the
  regeneration.

  Its stale list holds 3.7, 11.3, 21.0, 17.2 and 6.7, each followed by a percent sign. The list
  skips a value equal to `fp_pct` or `unknown_pct`, so `unknown_n` 121 of 576 (which reads 21.0)
  is covered. Nothing skips `dead_high_pct`, though. If `dead_high_n` went from 3 of 30 to 2,
  `dead_high_pct` would read 6.7, and this check would go red with no generator able to fix it.
  That is BLOCKED, for the lead to amend. It is not expected (Context).
- **`tests/test_number_coverage.py`** is structural. Every surface is scanned, every
  percentage is claimed or exempt, and a spot mutation of the X/Mastodon draft writes its own
  values. A rewritten figure stays inside its pattern, and `bench/results*` is skipped by its
  prose scan. Unaffected.
- **`tests/test_scorecard_production.py`.** Its `scorecard.score()` reads the real
  `results.json`. But every assertion is on the production items, against fake artifacts, or on
  the Solana disclosure text. Unaffected.
- **`tests/test_dataset_replayable.py`** reads only `bench/dataset.json` and `bench/labels.py`.
  576 appears only in its docstring. Unaffected: the dataset does not change.
- **`tests/test_retracted_claim.py`** pins a corpus of phrasings against `publish_numbers`'
  retracted-claim scan, and holds no figure. Unaffected.
- **`tests/test_rounds.py`** requires `docs/ROUNDS.md` to equal `rounds.render()`. The open
  round's commits are listed only once it closes, so this task's commits do not move it.
- **`tests/test_english_only.py`** (which exempts `results.json` and scans `results.md`) and
  **`tests/test_no_private_identifiers.py`** (which scans every tracked file). New upstream text
  enters `results.json` only through `gap_reasons`, and `results.md` prints counts, not gap text.
  A red in either is BLOCKED, not an edit.
- **`tests/test_risk.py`** imports `run_benchmark` and calls `driving_category`. Its "576 EVM
  addresses ... lowercase" is a docstring. Unaffected.

  `bench/scorecard.py` copies the pass counts of `test_risk.py`, `test_mcp.py` and
  `test_http_telemetry.py` into `docs/SCORECARD.md`. No test changes here, so those counts do
  not move.
- **Unrelated literals.**
  - `tests/test_second_oracle.py` builds its own results file in a temporary directory. Its "no
    figure is left over" check looks for 576, 121 and 6.0 in that sandbox's output. Unaffected.
  - `tests/test_usage_gate.py` has a synthetic n of 576, and `tests/test_upstream_contract.py`
    counts 122 paths. Neither reads the benchmark.
- **`tests/test_benchmark_replay.py`** (T-011) uses fakes only. It runs at the base as a check
  of the tools (AC 1).
- **Calendar.** These checks go red by date alone, whatever this task does (`lead/STATE.md`,
  "Every check that can go red on the calendar alone"):
  - `tests/test_owner_page.py`'s corrections window, red from 2026-10-15 UTC unless a newer
    `CORRECTIONS` entry exists;
  - its page-age check (7 days) and newest-snapshot-age check (2 days). The bots keep both
    fresh on `master`, so they go red on a branch that receives no bot commits;
  - `tests/test_gates_get_reviewed.py`, red from 2026-10-16 until the Owner resolves that gate
    (H-13).

  This task starts only after T-011 (size M) merges, likely inside that window. AC 8's same-day
  base run is what separates these reds from one this task caused, at commit 1 (AC 6) and at
  the head.

**Also checked.** `bench/results.md` prints no gap reason and no upstream text: its symbols come
from the dataset through `risk._ascii_safe`, and its counts come from rows. A replay reads
`bench/access_log.json` for the independence assertion, as every run does (T-011 AC 4), and a
fill does not read it; neither writes it (`bench/run_benchmark.py` never writes it at
`4838fdd`, and T-011 AC 5 says so for the fill), so it stays out of the diff.

**The maturity total** (measured at `4838fdd`: 46, published in `docs/OWNER.md`, "Maturity
score", through a `TARGETS` pattern). `bench/scorecard.py` bands three benchmark figures with
`band()`: a value earns the points of the first threshold it is below, and each band step is
worth one point of the total before rounding.
- Unknown rate, thresholds 0.05, 0.10, 0.20 and 0.30: today 122 of 576. 115 of 576 or fewer, or
  173 or more, changes the band.
- False positives (healthy rated high), thresholds 0.02, 0.05, 0.10 and 0.15: today 5 of 162.
  3 of 162 or fewer, or 9 or more, changes the band.
- False blocks, the same thresholds: today 20 of 154. 15 of 154 or fewer, or 24 or more, changes
  the band.

The dead cohort's size, which decides "recall is measurable", comes from the dataset's labels
and cannot move here.

**For the lead to park (not this task):**
1. **A sentence in `bench/results.md` that T-011 made untrue.** The page says failed requests
   "are not cached, so each run re-rolls them" (`write_markdown()`). Under T-011, a replay
   re-rolls nothing, and the dated mode keeps a final 4xx. Changing it is code in `bench/` and
   a change to a published page; park it with T-011 follow-up 3.
2. **The order in `CLAUDE.md`.** "The order that matters" still starts with a fetch-mode run
   (T-011 follow-up 5).
3. **The cache copy.** The scratch copy of `bench/cache/` is the only record of the cache before
   the fill. Keep it until T-012 and T-013 are merged.

## Amendments

2026-10-11, lead session 7 - release-base and local-workspace clarification (a).

The original measured cache has been preserved, and T-016 plus T-020 are now published.
T-011's executor confirmed the actual branch pin still reproduces both old result files
on this release base. AC 1 must independently reconfirm that at the task's exact base;
its failure remains BLOCKED. No attribution rule, fill budget, threshold, output target,
status rule, or acceptance assertion is changed.

- Work in the original main checkout on a new codex/t019-benchmark-rebaseline branch
  created from the inspected published release after T-011 merges. Do not merge the old
  unpublished local master, which contains unrelated private bookkeeping.
- The pre-existing untracked .codex directory contains Owner-controlled permission
  material. Leave it untouched. Record its pre-task status and require that exact same
  exclusion at every clean-tree check. Tracked files and all other untracked paths must
  be clean; report the exclusion rather than claiming an empty raw git status.
- A second read-only cache copy now exists for T-011 verification. It does not replace
  this task's mandatory fresh pre-fill manifest and whole-directory backup of the real
  main-checkout cache. Retain both copies through the downstream tasks.
- The exact base's offline suite includes T-016 and T-011. Record its actual step count
  rather than assuming the older count. The same-day baseline comparison is unchanged.
- The spec and this clarification must be committed before the first live fill. The
  Owner has authorized reviewed technical merges and deployment pushes in STATE.md;
  no additional permission request is needed for this scoped technical release.
