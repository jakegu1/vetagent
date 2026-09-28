# Lead state (the baton)

> What is in flight right now. The lead updates this at every check-in and merge; a new lead
> session starts by reading it. Durable rules live in `AGENTS.md`, `lead/QUALITY.md` and
> `lead/decisions/`. Test for this file: could a stranger act on every row below?

Last updated: 2026-09-29 by lead session 2 (Claude Code desktop, local, opened in this repository).

## Starting a lead session

1. Read this file, then `lead/config.yml`, the Needs-you section and the latest log of
   `lead/OWNER.md`, and `lead/tasks/README.md`.
2. `git fetch`, then compare `master` with `origin/master`. Bots push to master several times a
   day; when behind, merge (never rebase) before starting work.
3. Reconcile: for each in-flight row, check the real branch, worktree or subagent result, and
   CI for all six workflows, not only `test.yml` (the command is in `CLAUDE.md`). Fix this file
   if it drifted.
4. Act on each row's next action. Then start the next ready task if WIP allows. Autonomy is
   **A0** (`lead/config.yml`): propose each step and wait for the Owner's yes.
5. Run `python lead/checks.py` before every commit to master, lead bookkeeping included.
6. Check the rotation rule (`lead-handoff`). Update this file and commit.

## Standing notes

- **Open the session with this repository as the project folder** (not its parent), so that
  `CLAUDE.md`'s lead block, the untagged-probe hook in `.claude/settings.json` and the
  SessionStart hook in `.claude/settings.local.json` load. **The SessionStart hook works:** at
  the start of lead session 2 the first 80 lines of this file appeared on their own.
- **Autonomy is A0, confirmed by the Owner (H-4).** Propose each step and wait for the Owner's
  yes. After the next task merges cleanly, propose restoring A1.
- **M1's clock is running** since run 36445100361 (2026-09-28 15:38 UTC, head `dc401b9`). At
  each check-in, check `gh run list --workflow=test.yml`; any red run on master restarts it and
  stops new work until green (tripwire Q4).
- `master` has two unpushed lead commits (the handoff, and the H-4 answer), plus whatever this
  session commits. Push them with the next batch the Owner approves; fetch and merge origin
  first, never rebase.
- The `vetagent` MCP server in `.mcp.json` points at production. It sends
  `x-mcp-client: vetagent-owner-editor` (read 2026-09-29), so its calls are filtered as ours;
  a lead session still has no reason to call its tools (invariant 7).

## In flight

| Task | Level | Branch / PR | Stage | Who | Next action |
|---|---|---|---|---|---|
| — | | | | | No task in flight. H-5 (below) asks the Owner to start the two items in Next up. |

## Waiting on the Owner

- **H-5 (asked 2026-09-29):** yes or no to the two items in Next up (the Level 0 fix, then
  T-002 through executor and review). Default if unanswered: nothing starts.
- (H-4 answered 2026-09-28: stay at A0 for the next task; the lead proposes A1 again after one
  clean merge.)
- (H-1 done 2026-09-28: pushed `c954f43..dc401b9`; CI green on it.)

## Next up

Both items wait on the Owner's yes (H-5 in `lead/OWNER.md`). Do the Level 0 item first, so the
T-002 worktree branches from a master whose checks leave the tree clean.

1. **Level 0, lead does it:** `tests/test_number_coverage.py` leaves `docs/EXPERIMENT_C.md`
   with LF line endings on a Windows checkout. Its W21 check mutates the real file in place and
   restores it from a text-mode read, which turns CRLF into LF. Measured 2026-09-29: running that
   file alone reproduces it; the content is unchanged (`git diff --ignore-cr-at-eol` is empty).
   Plan, two commits on a short branch merged with `--no-ff`: (a) `lead/checks.py` exits 1 when a
   run modifies a tracked file (today it only prints them), and is watched going red on this
   side effect; (b) the test restores the file from its original bytes, and checks go back to
   27 of 27 with a clean tree. Then drop the "restore `docs/EXPERIMENT_C.md`" step from
   `lead/config.yml` (`merge.after`) and the Baseline note below.
2. **T-002, Level 1, ready:** `lead/tasks/T-002-publish-numbers-honest-exit.md`. `scan()` raises
   `KeyError` when a measurement file is absent (reproduced at `24a0a73`), and `--write` exits 0
   with entries it cannot rewrite, which is why the bots stayed green while `tests` was red.
   Executor in its own worktree (`../vetagent-t-002`, branch `task/t-002-publish-numbers-honest-exit`),
   then one fresh-context review, then the Owner's yes to merge and push.

Candidates after that, each needing a spec and the Owner's yes:

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
- Candidate, check mode vs the suite: `unsourced_competitor_figures()` fails check mode (and,
  after T-002, `--write`), but no test in the suite runs it, so CI would not see an undated
  competitor figure. Decide whether a test should, or whether check mode should not.

## Rotation

Lead session 2 started 2026-09-29, fresh. The rule (`lead/config.yml`): rotate at about 0.4 of
the context window or 72 hours, at a natural boundary. Lead session 1 rotated on 2026-09-28 at
50 of 100 parts of the window, after T-001 merged and CI came back green.

## Baseline

Before the lead kit, recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows,
Python 3.13.4, 19.0 s): 26 of 27 steps passed; the red one was `tests/test_published_numbers.py`.
After T-001 (`0a3098d`, 2026-09-28): 27 of 27. **Lead session 2 at `24a0a73` (2026-09-29):
27 of 27 in 19.0 s. No failure is known.**
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
**On CI:** `tests` was red from 2026-09-22 12:05 UTC to 2026-09-28: 32 runs, every one failing
at the step "Published accuracy figures match the benchmark". Run 36445100361 on `dc401b9`
(2026-09-28 15:38 UTC) is green: job `test` 27 of 27 steps, none skipped, and
`upstream-contract` and `backfill-roundtrip` succeeded. On 2026-09-29 the latest run of each of
the six workflows had succeeded.
**Side effect of a local run on Windows (until the Level 0 item lands):** `docs/EXPERIMENT_C.md`
is rewritten with LF line endings by `tests/test_number_coverage.py`. Restore it with
`git checkout -- docs/EXPERIMENT_C.md` only after `git diff --ignore-cr-at-eol` on it shows
nothing.

## Recent decisions

- 2026-09-29: T-002 specced at Level 1 (the `KeyError` and `--write`'s exit status together:
  same file, same area, one fix commit each). The line-ending side effect is a separate Level 0
  item, because its writer turned out to be a test, not `publish_numbers.py`. Both put to the
  Owner as H-5.
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
| 2 | Claude Code desktop, local (opened in this repository) | 2026-09-29 | | |

## Log (newest first; keep the last ~20 lines)

- 2026-09-29: lead #2 check-in. Origin had nothing new; all six workflows' latest runs green;
  checks 27 of 27. Corrected a handoff candidate: the LF rewrite of `docs/EXPERIMENT_C.md` comes
  from `tests/test_number_coverage.py`, not from `publish_numbers.py --write`. Reproduced the
  `scan()` `KeyError`. Wrote T-002; asked H-5.
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
