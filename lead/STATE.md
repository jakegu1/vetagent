# Lead state (the baton)

> What is in flight right now. The lead updates this at every check-in and merge; a new lead
> session starts by reading it. Durable rules live in `AGENTS.md`, `lead/QUALITY.md` and
> `lead/decisions/`. Test for this file: could a stranger act on every row below?

Last updated: 2026-09-28 by lead session 1 (Claude Code desktop, local).

## Starting a lead session

1. Read this file, then `lead/config.yml`, the Needs-you section and the latest log of
   `lead/OWNER.md`, and `lead/tasks/README.md`.
2. `git fetch`, then compare `master` with `origin/master`. Bots push to master several times a
   day; when behind, merge (never rebase) before starting work.
3. Reconcile: for each in-flight row, check the real branch, worktree or subagent result, and
   CI (`gh run list --workflow=test.yml`). Fix this file if it drifted.
4. Act on each row's next action. Then start the next ready task if WIP allows.
5. Check the rotation rule (`lead-handoff`). Update this file and commit.

## In flight

| Task | Level | Branch / PR | Stage | Who | Next action |
|---|---|---|---|---|---|
| — | | | | | No task started. The Owner has no work in progress in the repository. |

## Next up

- **T-001** (ready, Level 1): judge the scorecard's production row by the scorecard's own
  measured/not-measured rule. Turns CI's `tests` green (27 of 27) and makes steps 7 to 27
  visible on CI again. Spec: `lead/tasks/T-001-production-row-floor.md`. Next action: dispatch
  an executor on `task/t-001-production-row-floor` in its own worktree (the Owner wants to see
  the loop run on this task first).
- Candidate, Level 1: `bench/publish_numbers.py --write` rewrites `docs/EXPERIMENT_C.md` with LF
  line endings on Windows, so every local test run leaves a modified file; write it back with
  the line endings it had.
- Candidate, Level 1: `publish_numbers.scan()` raises `KeyError` on production-keyed targets
  when `bench/production/verdicts.json` is absent, although its comment says absent means
  unguarded (verified in memory, 2026-09-28); separately, `--write` exits 0 while a stale entry
  it cannot rewrite remains, which is why the bots stayed green while `tests` was red.
- Candidate, Level 2 (Level 3 area: deploy workflow): a deploy does not wait for the full
  offline suite (`deploy.yml` runs only `test_risk.py` and `test_mcp.py`), so a red `tests`
  does not stop a deploy. Make the deploy run the same list or depend on it.
- Candidate, investigate first: deploy tooling is unpinned (`uv.lock` and `pylock.toml` are
  gitignored as build artifacts). Whether to commit a lock is a decision for
  `docs/DECISIONS.md`.

## Waiting on the Owner

- H-1: approve one push of master once T-001 has merged (adoption commit plus T-001).
- H-2: close backlog W11 (gate answered in `f962aad`, row still Open, so `docs/OWNER.md` shows
  it overdue).
- H-3 (optional): add the SessionStart hook from `lead/decisions/0001-adopt-lead-workflow.md`.

## Baseline (before the lead kit)

Recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows, Python 3.13.4,
19.0 s): **26 of 27 steps pass.**
Known failures that tasks don't own: `tests/test_published_numbers.py` ("docs/SCORECARD.md
published pattern not found" for the production row). T-001 owns it; after T-001 no failure
is known.
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
On CI, `tests` has been red since 2026-09-22 12:05 UTC, so steps 7 to 27 are unobserved there
since that time. Side effect of a local run on Windows: `docs/EXPERIMENT_C.md` is rewritten with
LF line endings. Restore it with `git checkout -- docs/EXPERIMENT_C.md` only after
`git diff --ignore-cr-at-eol docs/EXPERIMENT_C.md` shows nothing.

## Recent decisions

- 2026-09-28: adopted the lead workflow (`lead/decisions/0001-adopt-lead-workflow.md`): lead/
  public and English, local-branches, A1, merge commits instead of squash; `docs/OWNER.md`,
  `docs/BACKLOG.md` and `docs/DECISIONS.md` stay the project's records.

## Lead history

| # | Session | From | To | Why it ended |
|---|---|---|---|---|
| 1 | Claude Code desktop, local | 2026-09-28 | | |

## Log (newest first; keep the last ~20 lines)

- 2026-09-28: adoption. Audit in `lead/AUDIT.md`. The Owner accepted every recommendation.
  Local master fast-forwarded to `f6c7c06` (66 bot commits). `lead/checks.py` added and watched
  failing on purpose (two mutants, both red). T-001 written, ready, not started. Adoption
  committed on master and not pushed (H-1).
