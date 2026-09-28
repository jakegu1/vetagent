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
| T-001 | 1 | `task/t-001-production-row-floor`, worktree `../vetagent-t-001` | implementing | executor subagent (lead session 1) | On READY: run `python lead/checks.py` on the head and the kit's `contract_check.py --base master`, then one fresh-context review. If the session died: read the branch's commits and continue from the spec. |

## Next up

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

- H-1: **approved 2026-09-28.** Push master once, after T-001 merges (adoption, W11 closure,
  T-001, and the bot merges in between). Fetch and merge origin first; never rebase.
- H-2: **approved and done 2026-09-28.** Backlog W11 closed as Done R23 (Level 0).
- H-3: **done 2026-09-28**, at the Owner's request ("你来建"): the SessionStart hook lives in
  `.claude/settings.local.json` (this project, this machine only; git-ignored by the Owner's
  global ignore file). It runs only in sessions whose project folder is this repository.

## Rotation

The rule fired on 2026-09-28: lead session 1 measured its context at 50 of 100 parts of the
window (the threshold in `lead/config.yml` is 0.4). Not rotated yet because T-001 is mid-flight
with an executor bound to this session. **Rotate at the next natural boundary: right after
T-001 merges and the H-1 push is done** (`lead-handoff`).

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

- 2026-09-28: H-2 done (Level 0): W11 marked Done R23; its orphaned `COST_OF_WAITING` entry
  removed from `tools/owner.py` (the rendered page is identical); `docs/OWNER.md` regenerated.
  Checks back at the baseline, 26 of 27.
- 2026-09-28: the Owner said "continue" and approved H-1 and H-2. Merged origin (production
  probe, still below the floor, CI red on the same step). T-001 dispatched to an executor in
  worktree `../vetagent-t-001`.
- 2026-09-28: adoption. Audit in `lead/AUDIT.md`. The Owner accepted every recommendation.
  Local master fast-forwarded to `f6c7c06` (66 bot commits). `lead/checks.py` added and watched
  failing on purpose (two mutants, both red). T-001 written, ready, not started. Adoption
  committed on master and not pushed (H-1).
