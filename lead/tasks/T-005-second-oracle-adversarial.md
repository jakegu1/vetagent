---
id: T-005
title: Make second_oracle.py ready for the Owner's W5 check on the adversarial cohort
status: done             # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 2                 # 0 direct | 1 light | 2 standard | 3 high risk
size: M                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: W5              # for W3, which W5 is a prerequisite of
---

## Context

W5 (a second, independent sell-simulation source) is the Owner's item in `docs/OWNER.md`, due
2026-10-16. `bench/second_oracle.py` asks Quick Intel, with the Owner's free-tier key, about two
sets of benchmark tokens: the disputed set (GoPlus `safe`, engine `high`) and the engine's
`unknown` verdicts. Those answers are held locally in `bench/second_oracle.json`, which
`.gitignore` excludes. Quick Intel's terms are unread, so no raw answer and no figure derived from
one may enter this repository (the Owner's decision H-9, 2026-09-29, recorded in `lead/STATE.md`).

What W5 still needs is one measurement the Owner will run: ask Quick Intel about the adversarial
cohort W3 rests on, the rows of `bench/results.json` whose `goplus_label` is `unsafe`. The script
cannot do that today, and running it as it stands would do harm:

1. **No way to select the cohort.** `load_sets()` returns the disputed and unknown sets only, and
   `run()` always asks both.
2. **It paces too fast.** `run()` sleeps 0.25 s between calls. The free tier allows about one call
   a second: the first real run on 2026-09-29 was rate limited on about every other call, and those
   rows had to be asked again by hand. The Owner's monthly allowance is small, so a rate-limited
   call is a call lost.
3. **It would destroy the earlier answers.** `run()` writes `bench/second_oracle.json`
   unconditionally, once, at the end. A second run overwrites the only copy of the first run's
   answers (the file is git-ignored, so git holds no copy), and an interrupted run keeps nothing.
4. **It counts calls it could not make as answers it did not get.** `report()` counts a call that
   errored as a token Quick Intel "could not answer". On 2026-09-29 all 143 calls were blocked
   before they reached Quick Intel, and the report printed "0 of 122" with a zero rate, as if Quick
   Intel had answered and said nothing (the comment above `USER_AGENT` tells that story).
5. **It does not say what an answer contains.** An answer may be a static audit with no sell
   simulation, or a sell simulation that Quick Intel cached long before the call. The lead had to
   classify the 2026-09-29 answers by hand, in chat. The report should do it, so that the Owner
   can read the result of the cohort check without anyone's help.
6. **A row on a chain with no entry in `CHAIN` is skipped silently**, so it vanishes from every
   count. No benchmark row is on such a chain today (`base`, `ethereum`, `bsc` only); if one ever
   is, the report must say so.

## Goal

The Owner runs one command that asks Quick Intel about exactly the adversarial cohort, paced so
the free tier does not rate-limit it, without touching the earlier answers, and reads a report
that keeps apart the calls that could not be made, the answers without a sell simulation, and the
sell simulations with their dates.

## Scope

**In:** a third set, `adversarial`, for `--plan` and `--run`; pacing; output-file safety and
per-call persistence; the time each row was asked; answer classification; a report that keeps
not-measured rows out of every denominator; a `--report PATH` mode that reads a saved file
without spending calls; the docstring's USAGE section; the ignore rule for the new output file;
the new test file and its step in `test.yml`.

**Out:**
- Any real call to Quick Intel. Agents have no key and need none: the tests replace the network.
- Copying anything from `bench/second_oracle.json` into a tracked file, a fixture, a commit
  message or a report. You may run `--report bench/second_oracle.json` once, locally, to see that
  it does not crash on the real shape; report only that it ran and its exit status, never its
  output.
- Retrying rate-limited calls, merging result files, or skipping tokens asked before.
- Anything under `src/`. B2: this is a labeller's tool, and the engine must never import it.
- `docs/`: the lead updates the W5 row after the merge.

## Files in scope

- `bench/second_oracle.py`
- `.gitignore` (the W5 rule only)
- `.github/workflows/test.yml`: one new step for the new test, in exactly the shape of its
  neighbours (a comment, `- name: ...`, `run: python tests/test_second_oracle.py`), placed before
  the step named "The deploy runs every step of this job before it deploys".
- Acceptance tests: `tests/test_second_oracle.py` (new), and fixtures under
  `tests/fixtures/second_oracle/` if you prefer files to inline data (synthetic only).
- **Named changes to existing tests:** none. The conflict search found no test that imports or
  names `second_oracle`. Three existing tests will see the new files:
  - `tests/test_decisions_enforcement.py` requires the new step in `test.yml`;
  - `tests/test_deploy_gate.py` reads the real `test.yml` and fails on a line its reader does not
    recognise, so copy the neighbouring steps' shape exactly;
  - `tests/test_english_only.py` walks the working tree, ignored files included, so the output
    files must stay ASCII: keep `json.dump`'s default `ensure_ascii=True`.
  Any other older test failing means BLOCKED.

## Acceptance criteria

1. **Selection.** `python bench/second_oracle.py --plan --set adversarial` prints how many rows
   the adversarial cohort has (rows of `bench/results.json` whose `goplus_label` is `unsafe`),
   needs no key and makes no call. `--run --set adversarial` asks about exactly those rows, each
   once, and no other row. Without `--set`, `--plan` and `--run` select what they select today
   (disputed, then unknown). No count is hard-coded: a test builds its own results file.
2. **Pacing.** Consecutive calls start at least `PACE_SECONDS` apart, a module constant equal to
   2.0. A test replaces the clock and `sleep` (no real waiting) and checks every gap.
3. **The earlier answers are safe.** Each selection has a fixed default output file:
   `bench/second_oracle.json` without `--set`, as today, and a different file under `bench/` for
   `--set adversarial`. `--run` refuses to start when its output file already exists: exit status
   2, a message naming the file, and no call made. No call is made before both the key check and
   this check pass. Git ignores every default output file: a test runs `git check-ignore` on each.
4. **Every call is kept and every row is accounted for.** The output file is rewritten after
   every call, so when the Nth call raises (a test makes it raise `KeyboardInterrupt`) the file
   holds the rows before it. Each row records when it was asked (UTC, epoch milliseconds or ISO
   8601) beside today's fields. A row whose chain has no entry in `CHAIN` is recorded with an
   error saying so, no call is made for it, and it counts as not measured.
5. **Classification.** The report puts each row in exactly one class:
   - *not measured*: the call errored, or the payload is not a dict holding a
     `tokenDynamicDetails` dict;
   - *no sell simulation*: `tokenDynamicDetails.sell_Tax` is null;
   - *sell simulated*: otherwise. Its simulation date is `tokenDynamicDetails.lastUpdatedTimestamp`
     (epoch milliseconds, UTC); its age is the time the row was asked minus that date, in days.
     When either time is missing, the report says the date or the age is unknown, never 0 days.

   `is_Honeypot` is read only for *sell simulated* rows. A *no sell simulation* row is never
   counted as a honeypot or as sellable, whatever that field holds.
6. **The report keeps what was not measured out of the denominators.** For each set present it
   prints the number of rows asked and the count in each class, the not-measured rows apart with
   their reasons. No rate or percentage is printed over zero measured rows. For the adversarial
   and disputed sets it also prints one line per token: chain, symbol, the engine's verdict, the
   class, and for *sell simulated* rows the simulation date, the age, `is_Honeypot`, `buy_Tax` and
   `sell_Tax`. A token symbol the console cannot encode does not crash it (the Owner's Windows
   console is GBK; a test prints to an ASCII-only stream). `report()` also returns the per-set
   counts as data, so tests assert on numbers, not on wording.
7. **`--report PATH`** prints the report from a saved results file, including today's shape
   (rows that record no asked time), needs no key and makes no call. `--run` prints the same
   report when it finishes.
8. **Contract, checks, no network.** The first commit adds only the acceptance tests.
   `tests/test_second_oracle.py` makes no network call (it fails if `urllib.request.urlopen` is
   reached), never sleeps for real, writes only under a temporary directory, and runs in under 5
   seconds. `python lead/checks.py` passes every step (29 with the new one), exits 0, and leaves
   the tree clean.

## Evidence required

- The tests-first commit: its SHA, and the output of `python tests/test_second_oracle.py` on it
  (which checks fail, and why).
- At the head: `python tests/test_second_oracle.py` (all pass, with the count); `python
  lead/checks.py` (the summary line and the exit status), then `git status --short` (empty).
- `python bench/second_oracle.py --plan --set adversarial` (benchmark data only; it is ours).
- The report printed from a synthetic file that covers every class and edge in AC 5 (synthetic
  data only).
- `git check-ignore -v` on each default output file.
- `python bench/second_oracle.py --report bench/second_oracle.json`: the exit status only.
- Two mutants the tests catch, for example the pace set back to 0.25 s and the adversarial
  selection writing to `bench/second_oracle.json`.
- `git diff --stat <base>..HEAD`: only files in scope.
- A scan of every changed file for non-ASCII characters: none.

## Notes

- Keep `USER_AGENT` as it is: Cloudflare in front of the API bans Python's default User-Agent
  (the comment above it). Keep `--max-calls` as a hard ceiling.
- The answer's shape (schema only, from Quick Intel's API): a dict with `tokenDetails`,
  `tokenDynamicDetails`, `quickiAudit` and other keys. `tokenDynamicDetails` holds
  `lastUpdatedTimestamp` (an integer, epoch milliseconds), `is_Honeypot` (bool), `buy_Tax`,
  `sell_Tax` and `transfer_Tax` (strings, or null when there was no simulation), and more. In a
  static audit only answer `buy_Tax` and `sell_Tax` are both null. Write synthetic fixtures in this
  shape with invented values.
- Tests must redirect every output path to a temporary directory (replace the module's path
  constants); nothing may be written under `bench/`.
- CI runs Python 3.12 on Linux; the Owner runs Python 3.13 on Windows.
- The Write and Edit tools decode backslash-u escapes in their input into real characters
  (`lead/PITFALLS.md`): write any such character in code as `chr(...)`.
- Scratch files go in your own subfolder of the session scratchpad; the rest of it belongs to
  other agents.

## Amendments

- **2026-09-30, round 1 lead decision** (`lead/reviews/T-005.md`): back to the executor for one
  round. Required: (1) the honeypot share is taken over the sell-simulated rows that state
  `is_Honeypot`, none is printed when none states it, and `report()` returns each printed share's
  numerator and denominator; (2) a saved file with a recorded selection and no rows reports each
  selected set as never asked. Named changes to `tests/test_second_oracle.py`, each in its own
  commit before its fix: **(a)** a mixed set (6 not measured, 2 with no sell simulation, 3 sell
  simulated: `is_Honeypot` true, false and unstated) returns the sell-simulated share as 3 of 5
  and the honeypot share as 1 of 2, and a set whose simulations all leave `is_Honeypot` unstated
  has no honeypot share; **(b)** a file recording a selection of 17 adversarial rows and holding
  none returns that set with 17 selected, 0 rows and 17 not asked, and the printed report says
  so. Nothing else in the test file changes.
