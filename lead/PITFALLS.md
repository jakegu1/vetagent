# Pitfalls in this project

Lessons that cost a review round, a day or a surprise, each with the rule it produced. The lead
adds a row when it happens; the weekly pass turns repeated rows into rules in `QUALITY.md` or
the spec template. General lessons from earlier projects are in the lead kit's `pitfalls.md`;
this project's older lessons are in `CLAUDE.md`.

| Date | What happened | Rule |
|---|---|---|
| 2026-09-28 | CI's `tests` stopped at step 6 of 27 on every run for six days, so steps 7 to 27 went unobserved while "one known red" was the whole report | Judge a task with `python lead/checks.py`, which runs every step; read a red CI run as "unknown past this step" |
| 2026-09-28 | In the adoption dry run, a percentage written as digits and a percent sign in a tracked `lead/*.md` turned `tests/test_number_coverage.py` red | In `lead/` files, write rates as "k of n" |
| 2026-09-28 | `tests/test_english_only.py` walks the working tree, so even an untracked Chinese file under `lead/` turned it red | Files under `lead/` are English; Chinese goes in chat only |
| 2026-09-28 | `.github/scripts/regenerate-derived.sh` with any argument other than `regenerate` resets to `origin`, commits and pushes (its CI mode) | Locally, only ever run `bash .github/scripts/regenerate-derived.sh regenerate` |
