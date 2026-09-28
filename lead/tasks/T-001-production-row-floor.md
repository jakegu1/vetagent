---
id: T-001
title: Judge the scorecard's production row by the scorecard's own measured/not-measured rule
status: in_review        # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 1                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]    # and docs/DECISIONS.md D7 (the production score rules)
backlog: none            # a baseline CI failure, fixed on sight; do not add a BACKLOG row
---

## Context

CI's `tests` workflow has failed on every run since 2026-09-22 12:05 UTC (31 runs by
2026-09-28), always at step 6 of 27, `python tests/test_published_numbers.py`. GitHub skips
the steps after a failed one, so steps 7 to 27 have not run on CI since. Baseline and
evidence: `lead/AUDIT.md`, `lead/STATE.md`.

The failure is a seam between two components, not a code change on that day:

- `bench/scorecard.py` writes the row "unknown rate (production, served answers)" in
  `docs/SCORECARD.md` under rules fixed before the first reading (DECISIONS.md D7, pinned by
  `tests/test_scorecard_production.py`): an artifact that is absent, unreadable, older than
  7 days relative to the newest snapshot (`PRODUCTION_MAX_AGE_DAYS`, via
  `_production_artifact()`), or holding fewer than `PRODUCTION_MIN_ROWS = 100` answers is
  written as `not measured (<reason>)` and scores nothing. Otherwise the row carries a figure,
  shaped `<rate>% of <n>, <start> to <end>`.
- `bench/publish_numbers.py` has a `TARGETS` entry for that row (added in `c1d4136`,
  2026-09-14) whose regex requires the figure shape. Its value comes from
  `_production_unknown_pct()`, which reads `bench/production/verdicts.json` and ignores both
  the floor and the freshness rule.
- When the production bot's commit `b051254` moved the 7-day window below 100 answers, the
  scorecard correctly switched the row to `not measured (<n> answers in the window, need
  100)`, and `scan()` reported `docs/SCORECARD.md  pattern not found`. The committed artifact
  is still below the floor as of 2026-09-28.

`python bench/publish_numbers.py --write` cannot repair this (there is no figure to rewrite),
and `python bench/scorecard.py --write` regenerates the same `not measured` row, so the red
cannot be cleared by regenerating. Fixing the data or moving the floor is not an option: the
floor is a pre-registered rule (Owner sign-off).

## Goal

The guard expects a figure in that row exactly when `bench/scorecard.py` would print one, and
expects `not measured` otherwise, using the scorecard's own rule rather than a copy of it.
`tests/test_published_numbers.py` passes on the current tree and still fails whenever the row
disagrees with the artifact, in every regime.

## Scope

**In:** how `bench/publish_numbers.py` judges the `docs/SCORECARD.md` production row; exposing
the scorecard's existing measured/not-measured decision so the guard can call it; acceptance
tests.

**Out:**
- The floor value, the 7-day freshness rule and their tests (`tests/test_scorecard_production.py`).
  Changing either is an Owner sign-off.
- The `docs/EXPERIMENT_C.md` production sentences and their `TARGETS` entries (they quote the
  rate together with its n and window; whether a below-floor rate belongs in that text is a
  separate question for the Owner).
- `scan()` raising `KeyError` for production-keyed targets when `verdicts.json` is absent
  (verified in memory on 2026-09-28; a follow-up candidate, not this task).
- `publish_numbers.py --write` exiting 0 while a stale entry it cannot rewrite remains (a
  follow-up candidate).
- Any published figure's value, the production probe, the bots, `docs/BACKLOG.md`.

## Files in scope

- `bench/publish_numbers.py`
- `bench/scorecard.py`: only to expose the existing decision for reuse (for example a small
  function returning the verdicts data or the not-measured reason). **No behaviour change:**
  `python bench/scorecard.py` prints the same table before and after, and
  `tests/test_scorecard_production.py` passes unchanged.
- Acceptance tests: `tests/test_published_numbers.py` (add check functions that `main()` runs
  and that set its exit code). Do not add a new test file: a new `tests/test_*.py` must also be
  registered as a step in `.github/workflows/test.yml`, or `tests/test_decisions_enforcement.py`
  fails.
- **Named changes to existing tests:** none. Conflict search (2026-09-28,
  `git grep` over `tests/*.py` and `tests/fixtures/**`): no test references
  `production_unknown_pct`, `_production_unknown_pct`, `_production_window`, `production_n` or
  `PRODUCTION_MIN_ROWS`. Tests that import the modules in scope, and must stay green unchanged:
  - `tests/test_scorecard_production.py` pins the scorecard's production rules.
  - `tests/test_number_coverage.py`: (1) every module-level name in `bench/publish_numbers.py`
    matching `*EXEMPT*`, `*TARGET*`, `*CLAIM*` or `*RETRACT*` must be referenced after its
    definition, so a new constant with such a name must be used; (2) its W21 check mutates each
    number in the short draft of `docs/EXPERIMENT_C.md` and requires `bench/publish_numbers.py`
    to exit non-zero every time.
  - `tests/test_owner_page.py` (calls `publish_numbers.figures()`), `tests/test_retracted_claim.py`
    and `tests/test_owner_power_recall.py` (import the module).

## Acceptance criteria

Regimes are defined by the scorecard's own rule. "Rejected" means `publish_numbers.scan(write=False)`
returns a stale entry for `docs/SCORECARD.md`; "accepted" means it returns none for that file.
Tests build synthetic artifacts in a temporary directory, the way `tests/test_scorecard_production.py`
does with `_items_with()`, and never touch the committed files.

1. **Current tree:** `python tests/test_published_numbers.py` exits 0 and prints `PASS`.
2. **Below the floor** (fresh artifact, n = floor - 1): a row reading
   `not measured (<n> answers in the window, need <floor>)` with the artifact's n and the
   scorecard's floor is accepted; the same row with a different n, or with a different floor,
   is rejected; a row carrying a figure (`<rate>% of <n>, ...`) is rejected.
3. **At the floor** (fresh artifact, n = floor exactly): a row with the correct figure is
   accepted; a row whose rate differs from the artifact's is rejected; a `not measured (...)`
   row is rejected.
4. **Stale artifact** (at least the floor in answers, `window_end` more than 7 days before the
   newest snapshot date): a `not measured (...)` row is accepted; a row carrying a figure is
   rejected.
5. **One rule, one source:** the guard's regime follows `bench/scorecard.py` at call time. With
   `scorecard.PRODUCTION_MIN_ROWS` patched in memory to a value at or below the artifact's n,
   the row is judged as measured (criterion 3's behaviour); restored, it is judged as below the
   floor. `tests/test_scorecard_production.py` passes unchanged.
6. **`--write` below the floor:** on the current tree, `python bench/publish_numbers.py --write`
   leaves `docs/SCORECARD.md` unchanged (compare ignoring line endings; on Windows the same run
   rewrites `docs/EXPERIMENT_C.md` with LF, which is a known side effect, not a change).
7. **Contract and checks.** The first commit on the branch adds only the acceptance tests.
   `python lead/checks.py` reports 27 of 27 steps passed (baseline: 26 of 27, the one red being
   this task's).

## Evidence required

- At the first commit: the output of `python tests/test_published_numbers.py`, showing which
  new checks fail and why (the red, which the fix commit's message must also describe, per the
  project rule "one finding, one commit, and a test that is red before the fix").
- At the head: `python tests/test_published_numbers.py` passing, and the full output of
  `python lead/checks.py`.
- `python bench/scorecard.py` before and after, showing the same production row and total.
- For criterion 6: `git diff --ignore-cr-at-eol --stat` after the `--write` run.
- At least two mutants you tried and saw turn a new check red, with the command output.

## Notes

- Why Level 1 although it touches a guard over a published figure: the row stays
  double-guarded. `tests/test_published_numbers.py` also compares the whole of
  `docs/SCORECARD.md` with `bench/scorecard.py`'s output, so a wrong figure typed into the row
  is caught even if this target were weakened. Raise to Level 2 if the diff grows beyond the
  files in scope.
- Suggested shape, not a requirement: let `publish_numbers` ask `scorecard` for its decision
  (reuse `_production_artifact("verdicts.json", "window_end")` plus the floor) and pick the
  expected form of the row from it. Do not implement the rule by dropping the
  `production_unknown_pct` key from `figures()`: `scan()` then raises `KeyError` on the
  `docs/EXPERIMENT_C.md` targets that use the same key.
- Mutants the reviewer will try: flip the floor comparison (`<` to `<=`); make the production
  row's check always pass; read the floor from a literal instead of `scorecard`. Each must turn
  at least one acceptance check red.
- Mutating a file on disk and restoring it: copy it first and restore from the copy, then clear
  `__pycache__` (`find . -name __pycache__ -type d -not -path "./.git/*" -exec rm -rf {} +`),
  or the next run imports a stale `.pyc`. Never restore with `git checkout <file>` while it
  holds uncommitted work.
- Write any file containing a backslash or a backtick with an editor tool, not through a shell
  heredoc (see `CLAUDE.md`).
- The repository is English-only (`tests/test_english_only.py`), including comments and tests.
- Run tests as scripts (`python tests/<file>.py`), not with pytest.

## Amendments

None yet.
