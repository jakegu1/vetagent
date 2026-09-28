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
| 2026-09-28 | Closing W11 in the owner's backlog table turned `tests/test_owner_page.py` red: its `COST_OF_WAITING` entry in `tools/owner.py` became an orphan | Closing an item in the "Yours" table also removes its `COST_OF_WAITING` entry (`OWNER_DUE` keeps closed items); check that `owner.render()` is unchanged |
| 2026-09-28 | The lead quoted the Owner's Chinese reply in `lead/STATE.md` and committed it (`f38ce82`) without running the checks; master went red on `tests/test_english_only.py`. The T-001 reviewer found it by merging the task into master in a scratch copy. Tripwire Q1 fired: autonomy A1 to A0 | Run `python lead/checks.py` before every commit to master, lead bookkeeping included; never quote the Owner's words in `lead/` files, paraphrase them in English |
| 2026-09-28 | A reviewer's final message, pasted verbatim, carried local paths, a CJK quote and a percentage written as digits, each of which a repository guard rejects | In `lead/reviews/`, rewrite those three things and say at the top that you did; change nothing else |
| 2026-09-29 | Executors and reviewers running in parallel share the session scratchpad; T-004's independent reviewer removed or overwrote same-named files another agent had left there (`mutants.py`, `a.txt`, a clone named `t004`) | Give each agent its own scratchpad subfolder by name in its prompt, and say that the rest of the scratchpad belongs to others |
| 2026-09-29 | The baton named `publish_numbers.py --write` as what rewrote `docs/EXPERIMENT_C.md` with LF on every run, and a candidate task was written around it. Running `tests/test_number_coverage.py` alone showed the real writer. Meanwhile `lead/checks.py` had listed the file after every run and everyone restored it by hand | Before a cause goes into the baton, run the suspected step alone and watch it reproduce. A warning printed on every run is a failure waiting to be made one: `lead/checks.py` now exits 1 when a run modifies a tracked file |
