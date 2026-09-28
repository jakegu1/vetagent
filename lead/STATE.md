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
4. Act on each row's next action. Then start the next ready task if WIP allows. Autonomy is
   **A0** (`lead/config.yml`): propose each step and wait for the Owner's yes.
5. Run `python lead/checks.py` before every commit to master, lead bookkeeping included.
6. Check the rotation rule (`lead-handoff`). Update this file and commit.

## Handoff notes for lead #2

- **Open the session with this repository as the project folder** (not its parent). Only then do
  `CLAUDE.md`'s lead block, the untagged-probe hook in `.claude/settings.json` and the
  SessionStart hook in `.claude/settings.local.json` load. Lead #1 ran from the parent folder.
  If this file appeared on its own at session start, the SessionStart hook works: say so to the
  Owner, because nobody has seen it fire yet.
- **Autonomy is A0, confirmed by the Owner (H-4).** Propose each step and wait for the
  Owner's yes. After the next task merges cleanly, propose restoring A1.
- **Suggested next proposal:** the second candidate below (`--write` exiting 0 on a stale entry
  it cannot rewrite, and `KeyError` when `verdicts.json` is absent). It is the class of silent
  failure that kept both bots green while `tests` was red for six days. Level 1.
- **M1's clock is running** since run 36445100361 (2026-09-28 15:38 UTC, head `dc401b9`).
  Check `gh run list --workflow=test.yml` at each check-in; any red run on master restarts it
  and stops new work until green (tripwire Q4).
- `master` has two unpushed lead commits (the handoff, and the H-4 answer). Push them with the
  next batch the Owner approves; fetch and merge origin first, never rebase.

## In flight

| Task | Level | Branch / PR | Stage | Who | Next action |
|---|---|---|---|---|---|
| — | | | | | No task in flight. |

## Next up

No task is specced. Candidates, each needing a spec (`lead-spec`) and, at A0, the Owner's yes:

- Candidate, Level 1: `bench/publish_numbers.py --write` rewrites `docs/EXPERIMENT_C.md` with LF
  line endings on Windows, so every local test run leaves a modified file; write it back with
  the line endings it had.
- Candidate, Level 1: `publish_numbers.scan()` raises `KeyError` on the `docs/EXPERIMENT_C.md`
  production targets when `bench/production/verdicts.json` is absent, although the code's
  comment says absent means unguarded (verified on disk by the T-001 reviewer); separately,
  `--write` exits 0 while a stale entry it cannot rewrite remains, which is why the bots stayed
  green while `tests` was red.
- Candidate, Owner's call first (public text): the `docs/EXPERIMENT_C.md` production sentences
  quote the live rate even below the scorecard's 100-answer floor, and compute it as
  `100*u/n` while the scorecard row now uses `(u/n)*100`; the two round differently on 314 of
  about two million (u, n) pairs (T-001 review, problem 4). Whether a below-floor rate belongs
  in that text is a public-claim decision.
- Candidate, Level 2 (Level 3 area: deploy workflow): a deploy does not wait for the full
  offline suite (`deploy.yml` runs only `test_risk.py` and `test_mcp.py`), so a red `tests`
  does not stop a deploy. Make the deploy run the same list or depend on it.
- Candidate, investigate first: deploy tooling is unpinned (`uv.lock` and `pylock.toml` are
  gitignored as build artifacts). Whether to commit a lock is a decision for
  `docs/DECISIONS.md`.
- Candidate, Level 0: `CLAUDE.md` says `.mcp.json` is untagged ("so `claude-code` is the
  owner"), but `.mcp.json` sends `x-mcp-client: vetagent-owner-editor`, as the probe hook's
  docstring also says. The note is stale; check which is true in the usage data before editing.

## Waiting on the Owner

- Nothing open.
- (H-4 answered 2026-09-28: stay at A0 for the next task; the lead proposes A1 again after one
  clean merge.)
- (H-1 done 2026-09-28: pushed `c954f43..dc401b9`; CI green on it.)

## Rotation

The rule fired on 2026-09-28: lead session 1 measured its context at 50 of 100 parts of the
window (the threshold in `lead/config.yml` is 0.4). It rotated at the natural boundary after
T-001 merged, the H-1 push landed and CI came back green.

## Baseline

Before the lead kit, recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows,
Python 3.13.4, 19.0 s): 26 of 27 steps passed; the red one was `tests/test_published_numbers.py`.
**After T-001 (`0a3098d`, 2026-09-28): 27 of 27. No failure is known.**
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
**On CI:** `tests` had been red since 2026-09-22 12:05 UTC. Run 36445100361 on `dc401b9`
(2026-09-28 15:38 UTC) is green: job `test` 27 of 27 steps succeeded, none skipped (steps 7 to
27 ran on CI for the first time since the red began), and `upstream-contract` and
`backfill-roundtrip` succeeded. No deploy ran (nothing under `src/` changed). Side effect of a
local run on Windows:
`docs/EXPERIMENT_C.md` is rewritten with LF line endings. Restore it with
`git checkout -- docs/EXPERIMENT_C.md` only after `git diff --ignore-cr-at-eol` on it shows nothing.

## Recent decisions

- 2026-09-28: the Owner answered H-4 as recommended: autonomy stays A0 for the next task, and
  the lead proposes A1 again after one clean merge.
- 2026-09-28: T-001 merged (`0a3098d`, `git merge --no-ff`, the tests-first commit kept):
  review 12 of 12, verdict pass (`lead/reviews/T-001.md`). Milestone M0 (loop proven) reached.
- 2026-09-28: tripwire Q1 fired. The lead's own commit `f38ce82` put a CJK quote into
  `lead/STATE.md`, which broke the English-only rule on master; it was committed without a
  checks run and found by the T-001 reviewer. Fixed in `5959a8b`. **Autonomy demoted A1 to
  A0** (`lead/config.yml`). H-1's explicit approval (merge and push T-001) still stands.
- 2026-09-28: adopted the lead workflow (`lead/decisions/0001-adopt-lead-workflow.md`): lead/
  public and English, local-branches, merge commits instead of squash; `docs/OWNER.md`,
  `docs/BACKLOG.md` and `docs/DECISIONS.md` stay the project's records.

## Lead history

| # | Session | From | To | Why it ended |
|---|---|---|---|---|
| 1 | Claude Code desktop, local (opened in the parent folder) | 2026-09-28 | 2026-09-28 | Rotation rule: context at 50 of 100 parts of the window |
| 2 | next session, opened in this repository | | | |

## Log (newest first; keep the last ~20 lines)

- 2026-09-28: H-1 push `c954f43..dc401b9`; CI run 36445100361 green (27 of 27 steps, both
  network jobs green, no deploy). M1 clock started. Lead #1 hands off to lead #2.

- 2026-09-28: T-001 merged as `0a3098d` after a fresh review (12 of 12). Post-merge
  regeneration changed only the recent-commit list in `docs/OWNER.md` (`9e81c01`; its checks
  ran just after that commit rather than before it: 27 of 27). Checks on master: 27 of 27.
- 2026-09-28: the T-001 reviewer found that the lead's `f38ce82` broke the English-only rule on
  master; fixed in `5959a8b`; tripwire Q1 demoted autonomy to A0.
- 2026-09-28: H-3 done at the Owner's request (SessionStart hook in `.claude/settings.local.json`).
  The rotation rule fired (context at 50 of 100 parts of the window).
- 2026-09-28: H-2 done (Level 0): W11 marked Done R23; its orphaned `COST_OF_WAITING` entry
  removed from `tools/owner.py` (the rendered page is identical); `docs/OWNER.md` regenerated.
- 2026-09-28: the Owner said "continue" and approved H-1 and H-2. Merged origin (production
  probe, still below the floor, CI red on the same step). T-001 dispatched to an executor in
  worktree `../vetagent-t-001`.
- 2026-09-28: adoption. Audit in `lead/AUDIT.md`. The Owner accepted every recommendation.
  Local master fast-forwarded to `f6c7c06` (66 bot commits). `lead/checks.py` added and watched
  failing on purpose (two mutants, both red). T-001 written. Adoption committed on master.
