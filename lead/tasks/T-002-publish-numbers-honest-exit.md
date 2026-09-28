---
id: T-002
title: Make publish_numbers.py report what it could not do, instead of crashing or exiting 0
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 1                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: none            # found by the T-001 review; fixed on sight, no BACKLOG row
---

## Context

`bench/publish_numbers.py` guards every published figure (invariant 4 in `lead/QUALITY.md`).
It has two defects in how it reports failure. Both were found by the T-001 review
(`lead/reviews/T-001.md`, problems 2 and 3) and reproduced again by the lead at `24a0a73`.

1. **A missing measurement crashes the scan.** `figures()` leaves a key out when its
   measurement file is absent or unusable, on purpose: "absent means unguarded, not guarded
   against None" (the comment above `out["production_unknown_pct"]`), and
   `_owner_power_figures()` promises that "an unguarded number is reported as unguarded rather
   than silently passing". But `scan()` reads `vals[key]` directly, so the first target whose
   key is missing raises `KeyError` and nothing else is reported. Reproduced: with
   `bench/production/verdicts.json` moved away, `python bench/publish_numbers.py` exits 1 with a
   traceback ending in `KeyError: 'production_unknown_pct'`, raised in `scan()`.
   Targets exposed today:
   - seven `docs/EXPERIMENT_C.md` targets using the five production keys
     (`production_unknown_pct` twice, `production_to_md` twice, and `production_n`,
     `production_from`, `production_from_md` once each). All five keys go missing when the
     artifact is absent, unreadable or empty; the last four also go missing when it lacks its
     window dates (`_production_window()` returns `{}`).
   - one `src/pages.py` target keyed `power_pooled_oos_pct`, missing when
     `bench/owner_powers.json` is absent or holds a null for it (`figures()` drops keys whose
     value is `None`).
   The two `docs/SCORECARD.md` production targets are not affected: they use `ABSENT`.

2. **`--write` exits 0 with work left undone.** In `main()`, whenever anything is stale or an
   unclaimed percentage remains, `--write` prints `Rewrote: ...` and returns 0. That includes
   entries it cannot rewrite (`pattern not found`, `file missing`, a `docs/SCORECARD.md` row in
   the form the scorecard is not printing) and unclaimed percentages, which `--write` never
   fixes. The T-001 reviewer typed a below-floor figure row into `docs/SCORECARD.md`: `--write`
   listed both stale entries, printed an empty `Rewrote: ` and exited 0.
   The bots depend on this exit status. `.github/scripts/regenerate-derived.sh` runs
   `python bench/publish_numbers.py --write >/dev/null || { echo "::error::publish_numbers.py failed"; return 1; }`
   and then commits and pushes. From 2026-09-22 12:00 UTC to 2026-09-28 15:30 UTC all 24
   scheduled `snapshot` runs and all 7 `production` runs succeeded, while all 32 `tests` runs
   failed on `tests/test_published_numbers.py`, which calls this module's `scan()`.

Check mode (no `--write`) is not affected by defect 2: it already exits 1 on a stale entry, an
unclaimed percentage, a retracted claim or an undated competitor figure.

## Goal

A target with no measurement is reported as not measured, and the run fails, instead of
crashing. `python bench/publish_numbers.py --write` rewrites what it can, then exits 0 exactly
when a check-mode run on the files it leaves behind would exit 0, so a bot's regeneration step
fails where the guard fails.

## Scope

**In:** how `scan()` handles a target whose key `figures()` does not return; `main()`'s exit
status and report under `--write`; acceptance tests.

**Out:**
- `.github/scripts/regenerate-derived.sh` and every workflow (a Level 3 area). They already
  treat a non-zero exit as failure; nothing there needs to change.
- Which checks check mode runs, and its exit statuses (stale figures, unclaimed percentages,
  retracted claims, undated competitor figures, exit 2 when `bench/results.json` is missing).
- `figures()`'s return value: `tools/owner.py` and `tests/test_owner_page.py` consume it. Do not
  add placeholder values for missing keys.
- Line endings when `--write` rewrites a file on a Windows checkout.
- The wording of the `docs/EXPERIMENT_C.md` production sentences, and whether a rate below the
  scorecard's floor belongs in them (the Owner's call).
- Any published figure's value, and `bench/scorecard.py`.

## Files in scope

- `bench/publish_numbers.py`
- Acceptance tests: `tests/test_published_numbers.py`. Add `check_*` functions, which `main()`
  already runs and whose failures already set its exit code. Do not add a new test file: a new
  `tests/test_*.py` must also be registered as a step in `.github/workflows/test.yml`, or
  `tests/test_decisions_enforcement.py` fails.
- **Named changes to existing tests:** none. Conflict search (2026-09-29, `git grep` over
  `tests/*.py` and `tests/fixtures/**` for `scan(`, `publish_numbers.py`, `--write`, `Rewrote`,
  `Everything published`, `pattern not found`, `file missing`, `ABSENT`, `figures()`,
  `returncode`, `KeyError`, `_production_unknown_pct`, `_production_window`,
  `_owner_power_figures`, `production_n`, `not measured`): no test asserts `--write`'s exit
  status or its printed report, and none relies on the `KeyError`. Tests that touch the module
  and must pass unchanged:
  - `tests/test_published_numbers.py`: `judge()` points `publish_numbers.ROOT` at a temporary
    directory holding only `docs/SCORECARD.md` and keeps only that file's stale entries, so
    every other target is `file missing` there (checked before the key); `check_write()` runs
    `scan(write=True)` in that directory. Both must keep working.
  - `tests/test_number_coverage.py`: runs `python bench/publish_numbers.py` in check mode after
    mutating each number in the short draft of `docs/EXPERIMENT_C.md`, and requires a non-zero
    exit every time. It also requires every module-level name matching `*EXEMPT*`, `*TARGET*`,
    `*CLAIM*` or `*RETRACT*` to be used after its definition.
  - `tests/test_owner_page.py` (calls `figures()`), `tests/test_retracted_claim.py` and
    `tests/test_owner_power_recall.py` (import the module), and
    `tests/test_bot_commits_stay_green.py` (reads `regenerate-derived.sh`, which this task does
    not change).

## Acceptance criteria

Tests never write a committed file. Anything that writes (`scan(write=True)`, `main()` with
`--write`) runs against a temporary directory, by pointing `publish_numbers.ROOT` at it (and,
for the production artifact, `publish_numbers.HERE` and `scorecard.PRODUCTION`), as `judge()`
does. Every patched global is restored in a `finally`.

1. **The current tree is unaffected.** `python bench/publish_numbers.py` and
   `python bench/publish_numbers.py --write` each exit 0 and print
   `Everything published matches the benchmark.`, and `git diff --ignore-cr-at-eol --stat` is
   empty afterwards. `bash .github/scripts/regenerate-derived.sh regenerate` (the bots' path)
   exits 0.
2. **A missing production artifact is reported, not raised.** With
   `bench/production/verdicts.json` absent where the module reads it (a temporary directory; the
   committed file untouched), `scan(write=False)` returns without raising, and its stale list
   holds exactly one entry for each of the seven `docs/EXPERIMENT_C.md` targets that use the
   five production keys. Each entry's expected value says the figure is not measured and names
   the key; it is never `None` and never a number. The two `docs/SCORECARD.md` production
   targets behave as they do today.
3. **Any missing key, same rule.** When `figures()` returns no value for a key a target uses
   (for example, `figures` wrapped in memory to drop `power_pooled_oos_pct`), `scan()` reports
   each target using that key as not measured and does not raise, and `scan(write=True)` leaves
   those targets' text unchanged.
4. **Check mode names what is missing.** In criterion 2's state, check mode returns 1, and its
   output names each not-measured target's file and key, with no traceback.
5. **`--write` exits 0 only when nothing is left.** Against a temporary copy of the files
   `main()` reads:
   - (a) with one stale figure that `--write` can rewrite, `--write` rewrites it and returns 0,
     and a check-mode run afterwards returns 0;
   - (b) with that figure plus an entry `--write` cannot rewrite (a guarded sentence reworded so
     its pattern no longer matches), `--write` still rewrites the figure, returns non-zero, and
     names the entry it could not fix;
   - (c) with that figure plus a new unclaimed percentage on a line of a live-claim file,
     `--write` rewrites the figure, returns non-zero, and lists the unclaimed percentage;
   - (d) in criterion 2's state, `--write` returns non-zero and leaves the not-measured targets'
     text unchanged.

   The rule these illustrate: `--write` returns 0 exactly when check mode, run on the files
   `--write` leaves behind, would return 0.
6. **Contract and checks.** The first commit adds only the acceptance tests, and they are red
   there. Each defect is fixed in its own commit, whose message says what the red looked like
   (invariant 8). `python lead/checks.py` reports 27 of 27 steps passed at the head.

## Evidence required

- At the first commit: the output of `python tests/test_published_numbers.py`, showing which
  new checks fail and how. A check that meets the `KeyError` records it as a failure and lets
  the file's other checks run; it does not crash the file.
- After each fix commit: the same output, showing that fix's checks turning green.
- At the head: `python tests/test_published_numbers.py` passing; the full output of
  `python lead/checks.py`; for criterion 1, both commands' output, `git diff --ignore-cr-at-eol
  --stat` after them, and the exit status of `bash .github/scripts/regenerate-derived.sh
  regenerate` (restore any derived page it rewrote; do not commit them).
- At least two mutants you tried and saw turn a new check red, with the output.

## Notes

- Level 1, although it touches the guard over published figures: nothing is removed from the
  guard. Check mode keeps its behaviour and becomes the definition of success for `--write`.
  Raise to Level 2 if the diff grows beyond the files in scope.
- Why the bots stay safe: on the current tree `--write` exits 0 (criterion 1). After the change
  a bot fails only where `tests/test_published_numbers.py` already fails (a stale figure
  `--write` cannot rewrite, an unclaimed percentage) or where check mode already fails today (a
  retracted claim, an undated competitor figure). Then `regenerate-derived.sh` prints
  `::error::publish_numbers.py failed`, commits nothing and exits 1. That is the point: today it
  pushes and leaves `tests` red.
- Suggested shape, not a requirement: in `scan()`, test `key not in vals` before comparing and
  append `(rel, pattern, <what the text says>, "not measured (<key>)")`; in `main()`, after
  `scan(write=True)`, run the checks again on the rewritten files and return what check mode
  would. Keep the `Rewrote:` line for what was rewritten, and do not print it empty.
- Mutants the reviewer will try: restore the bare `vals[key]` lookup; make `--write` return 0
  again whenever it wrote something; make a not-measured entry's expected value `None`; let
  `--write` write a not-measured entry's expected value into the file.
- `HERE` is read at call time only by the two production readers (`_production_unknown_pct()`,
  `_production_window()`); `RESULTS` is fixed at import. `scorecard.PRODUCTION` is where
  `bench/scorecard.py` reads the same artifact.
- `main()` also calls `retracted()`, `unsourced_competitor_figures()` and
  `unclaimed_percentages()` over `LIVE_CLAIM_FILES`, `FROZEN_LOG_FILES` and a few more files,
  all relative to `ROOT`; `_owner_power_figures()` reads `bench/owner_powers.json` under `ROOT`.
  A temporary directory for criterion 5 needs copies of every file these read, or each missing
  file shows up as a finding of its own. Build the list from the module's own constants rather
  than typing it.
- If you mutate a file on disk, copy it first and restore it from the copy as bytes (a
  text-mode round trip turns CRLF into LF on a Windows checkout), then clear `__pycache__`
  (`find . -name __pycache__ -type d -not -path "./.git/*" -exec rm -rf {} +`).
- Write any file containing a backslash or a backtick with an editor tool, not through a shell
  heredoc (see `CLAUDE.md`).
- English only, including comments and tests (`tests/test_english_only.py`). Run tests as
  scripts (`python tests/<file>.py`), not with pytest.

## Amendments

None yet.
