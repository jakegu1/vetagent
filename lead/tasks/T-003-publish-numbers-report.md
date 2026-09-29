---
id: T-003
title: Make publish_numbers.py's report say what changed and what to do about what is left
status: done             # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 1                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: [T-002]
decisions: [ADR-0001]
backlog: none            # follow-ups from T-002's review and executor; no BACKLOG row
---

## Context

T-002 (`16e100e`, review in `lead/reviews/T-002.md`) made `bench/publish_numbers.py` report a
target with no measurement instead of raising, and made `--write` exit 0 exactly when check
mode would on the files it leaves. Its reviewer and executor found that the printed report no
longer matches what the script does. On master at `120fed3`, `main()` prints:

- **Under `--write`, only file names.** `Rewrote: <files>`, then check mode's report. Before
  T-002 it listed each stale figure's found and expected values, so a reader could see what
  moved; now nothing says which figure changed from what to what.
- **One heading and one piece of advice for every stale entry.** Check mode prints
  `<n> published figure(s) disagree with bench/results.json:`, one line per entry
  (`<file> found <x> expected <y> (<pattern>)`), then
  ``Run `python bench/publish_numbers.py --write`, then redeploy.``. That is wrong for every
  entry `--write` cannot fix: `expected not measured (<key>)` (no measurement to write),
  `found pattern not found` (the guarded sentence changed), `found file missing`, and
  `expected absent` (the scorecard is printing the other form of its production row; only
  `bench/scorecard.py --write` changes that). Several targets are not measured in
  `bench/results.json` at all (the production artifact, `bench/owner_powers.json`,
  `docs/SCORECARD.md`), so the heading's source is wrong for them too.
- **A heading with nothing under it.** When only unclaimed percentages remain, it prints
  `0 published figure(s) disagree with bench/results.json:` before returning 1.
- **A flag that does not exist.** The module docstring's usage says
  `python bench/publish_numbers.py --check`; argparse rejects `--check` and exits 2. Check mode
  is the script with no flag.
- **An untested promise.** T-002's reviewer found a surviving mutant: printing `Rewrote:` when
  nothing was rewritten passes every test (the T-001 symptom was an empty `Rewrote: ` line).

Nothing here changes an exit status. The bots discard this output
(`.github/scripts/regenerate-derived.sh` sends it to `/dev/null`); the readers are the people
and agents who run the script by hand, the way `CLAUDE.md` tells them to.

## Goal

A reader of the script's output can tell what `--write` changed, which remaining entries
`--write` could fix, and what to do about each entry it cannot fix; no line claims a source,
a count or a flag that is not true.

## Scope

**In:** the text `main()` prints in both modes; the module docstring's usage lines;
acceptance tests.

**Out:**
- Every exit status, in both modes (T-002 pinned them). Which checks run.
- `scan()`'s return values and the shape of its stale entries: `tests/test_published_numbers.py`
  (`judge()`, `check_write()` and the T-002 checks) and `tools/owner.py` depend on them. If
  `main()` needs more (for example the list of rewritten figures), add it without changing what
  existing callers receive.
- `.github/scripts/regenerate-derived.sh` (a Level 3 area; sending its output somewhere
  visible is a separate candidate).
- The failure text of `tests/test_published_numbers.py`'s own `main()`, which repeats the old
  advice; changing an existing test's text is not part of this task.
- `figures()`, `TARGETS`, and any published figure.

## Files in scope

- `bench/publish_numbers.py`
- Acceptance tests: `tests/test_published_numbers.py`. Add `check_*` functions (run by its
  `main()` and counted in its exit code); reuse the T-002 helpers there (`in_a_copy()`,
  `run_main()`, `stale_figure()`, `edit()`, `reword()`, `target()`). Do not add a new test file:
  a new `tests/test_*.py` must also be registered in `.github/workflows/test.yml`.
- **Named changes to existing tests:** none. Conflict search (2026-09-29, `git grep` over
  `tests/*.py` and `tests/fixtures/**` for `Rewrote`, `disagree`, `redeploy`, `--check`,
  `pattern not found`, `file missing`, `not measured`, `found `, `expected `, `run_main`,
  `returncode`): the T-002 checks read the output and require, and must keep finding:
  - `check_check_mode_names_what_is_not_measured`: for each production key, at least as many
    output lines as it has targets that contain `docs/EXPERIMENT_C.md`, `not measured` and the
    key; and no `Traceback`.
  - `check_write_fails_on_a_sentence_it_cannot_find`: a line containing `README.md` and
    `pattern not found`.
  - `check_write_fails_on_an_unclaimed_percentage`: a line containing `README.md` and the
    planted figure followed by a percent sign.
  `tests/test_number_coverage.py` runs the script in check mode and reads only its exit
  status. No other test reads the script's output.

## Acceptance criteria

Tests run the script against a temporary copy, as the T-002 checks do; they never write a
committed file.

1. **What `--write` changed.** For each figure `--write` rewrites, its output has one line
   naming the file, the value it found and the value it wrote. When it rewrites nothing, no line
   announces rewrites (no `Rewrote:` line, empty or not).
2. **Fixable and unfixable, told apart.** In check mode, with one figure `--write` can rewrite
   and one entry it cannot (a guarded sentence reworded so its pattern no longer matches), the
   rewritable figure is listed under text saying `--write` can rewrite it, together with the
   advice to run `--write`; the other entry is listed separately, under text saying `--write`
   cannot fix it. With only unfixable entries left (for example the production artifact
   absent), the advice to run `--write` does not appear.
3. **Advice per reason.** Each kind of unfixable entry present gets one line saying what to do:
   not measured (the measurement file its key comes from is absent or unusable); pattern not
   found (the guarded sentence changed: restore it, or update its `TARGETS` pattern); file
   missing; and the scorecard's other form (run
   `bash .github/scripts/regenerate-derived.sh regenerate`). No heading attributes every entry
   to `bench/results.json`.
4. **No empty sections.** No line reports a count of zero; in particular, with only an unclaimed
   percentage left, nothing says `0 published figure(s)`.
5. **The docstring's usage is true.** Every flag shown in the module docstring's usage lines is
   accepted by the script (`python bench/publish_numbers.py --help` lists it), and check mode is
   shown as the script with no flag.
6. **Nothing else moves.** The T-002 checks pass unchanged; exit statuses are unchanged in both
   modes; on the current tree both modes print `Everything published matches the benchmark.`
   and exit 0.
7. **Contract and checks.** The first commit adds only the acceptance tests, and they are red
   there. One fix commit per finding above that was red (criteria 1 to 5), each message saying
   what the red looked like; findings may share a commit only where one change fixes both, and
   the message says so. `python lead/checks.py` reports 27 of 27 steps passed, exit 0.

## Evidence required

- At the first commit: `python tests/test_published_numbers.py`, showing the new checks red and
  why.
- At the head: that file passing; the full output of `python lead/checks.py`; and the script's
  output, in a temporary copy, for three states: one rewritable figure under `--write`; one
  rewritable figure plus one reworded sentence in check mode; the production artifact absent in
  check mode.
- At least two mutants you tried and saw turn a new check red.

## Notes

- Level 1: output only, one file of code; every exit status stays pinned by T-002's checks.
- Suggested shape, not a requirement: classify each stale entry by its `found` and `want`
  (`pattern not found`, `file missing`, `ABSENT`, `not measured (...)`, else rewritable), print
  the rewritable ones and the rest in two blocks, and print one advice line per class present.
  For criterion 1, `scan(write=True)` already knows each entry it rewrote; expose that without
  changing the three values existing callers unpack.
- Keep each entry on one line with its file, as the T-002 checks read it.
- Mutants the reviewer will try: print `Rewrote:` unconditionally; print the `--write` advice
  unconditionally; drop the unfixable block's per-reason advice; restore `--check` in the
  docstring.
- Write any file containing a backslash or a backtick with an editor tool, not a shell heredoc
  (`CLAUDE.md`). English only. Run tests as scripts, not with pytest.

## Amendments

- **2026-09-29, named change (a), before the review.** The executor found a mutant that
  survives the acceptance tests: a heading over the "can rewrite" block that names
  `bench/results.json` again passes, because the heading check runs only in the state where
  every kind of unfixable entry is present, which has no rewritable block. Allowed change, in
  `tests/test_published_numbers.py`, `check_each_kind_of_entry_write_cannot_fix_gets_one_line_of_advice`:
  in its one-kind state (a rewritable figure plus a reworded sentence), also assert that no
  heading line contains `bench/results.json`. Nothing else in that file changes. Its own
  commit, titled `T-003: named change (a) ...`; the executor verified it in a scratch clone
  (111 of 111, and the mutant goes red).
