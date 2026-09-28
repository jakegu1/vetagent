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
   **A1** (`lead/config.yml`): spec, dispatch, review and decide; ask the Owner before every
   merge to master and every push, batched.
5. Run `python lead/checks.py` before every commit to master, lead bookkeeping included.
6. Check the rotation rule (`lead-handoff`). Update this file and commit.

## Standing notes

- **Open the session with this repository as the project folder** (not its parent), so that
  `CLAUDE.md`'s lead block, the untagged-probe hook in `.claude/settings.json` and the
  SessionStart hook in `.claude/settings.local.json` load. **The SessionStart hook works:** at
  the start of lead session 2 the first 80 lines of this file appeared on their own.
- **Autonomy is A1 again (H-7, 2026-09-29).** The lead specs, dispatches, reviews and decides
  on its own; every merge to master and every push waits for the Owner's yes. A2 needs five
  clean merges in a row (`method.md` §12); the streak is 1 (T-002). Any escaped defect demotes
  one level (tripwire Q1).
- **M1's clock is running** since run 36445100361 (2026-09-28 15:38 UTC, head `dc401b9`); still
  green on run 36455682835 (head `16e100e`). At each check-in, check
  `gh run list --workflow=test.yml`; any red run on master restarts it and stops new work until
  green (tripwire Q4).
- Pushing: fetch and merge origin first (never rebase), regenerate the derived pages
  (`merge.after` in `lead/config.yml`), run the checks, commit the regenerated pages if the
  merge moved them, check the commit messages for anything private, then push and watch CI.
  `git merge -F -` does not read a message from stdin here; write it to a file in the
  scratchpad and pass that file.
- The `vetagent` MCP server in `.mcp.json` points at production. It sends
  `x-mcp-client: vetagent-owner-editor` (read 2026-09-29), so its calls are filtered as ours;
  a lead session still has no reason to call its tools (invariant 7).

## In flight

| Task | Level | Branch / PR | Stage | Who | Next action |
|---|---|---|---|---|---|
| T-003 | 1 | `task/t-003-publish-numbers-report`, worktree `../vetagent-t-003`, based on `f400b60` | review passed: 12 of 12, VERDICT ✅ at `56105a7` (`lead/reviews/T-003.md`); head unchanged since | the Owner | Ask to merge (`--no-ff`) and push in one batch with T-004 once its reviews pass |
| T-004 | 3 | `task/t-004-deploy-runs-offline-suite`, worktree `../vetagent-t-004` | amendment round: READY at `521fc6c`; the executor is adding named change (a, b) and the two runner fixes (spec Amendments, `adc77cb`) | executor subagent | Collect READY; contract check and checks on the head; then an independent review and a red-team review in parallel. Its push deploys production (`deploy.yml` is in its own trigger): propose pushing the task branch first (tests on Linux, no deploy), then master |
| W5 experiment (the Owner's) | — | none; `bench/second_oracle.py` on master | the Owner reruns the 143 calls with the User-Agent fix | the Owner | Analyse `bench/second_oracle.json` (ignored, local only): count answers, errors (for example HTTP 400 for an invalid contract) and empty payloads separately; an all-null payload with `isScam: false` is no answer, not a safe verdict |

## Waiting on the Owner

- Nothing open. Pushing master (the three Level 0 merges and the lead's bookkeeping) waits for
  the batch with T-003 and T-004.
- (H-8 answered 2026-09-29: merge the three Level 0 branches locally, no push. Merged as
  `a8a758d`, `08915db`, `d592f8d`.)
- (H-7 answered 2026-09-29: yes; applied after the clean merge. Autonomy A1.)
- (H-6 done 2026-09-29: T-002 merged as `16e100e`; pushed `dc401b9..16e100e`; CI run
  36455682835 green; no deploy.)
- (H-5 answered 2026-09-29: yes to both items, as recommended. Item 1, the Level 0 fix, merged
  as `82acff3`; item 2 was T-002.)
- (H-4 answered 2026-09-28: stay at A0 for the next task; the lead proposes A1 again after one
  clean merge.)
- (H-1 done 2026-09-28: pushed `c954f43..dc401b9`; CI green on it.)

## Next up

No task is specced. Candidates below; at A1 the lead may spec and dispatch any of them, and the
merge and push wait for the Owner's yes. Items marked "Owner's call first" need the Owner before
a spec.

Suggested order (lead #2): the two follow-ups that finish T-002 and the deploy gate (T-004) are
in flight; after them, the Level 3 hardening of `regenerate-derived.sh` below.

- Candidate, Level 1, from T-003's review: when the scorecard's production row is in the form
  `bench/scorecard.py` is not printing, its two targets report `absent` and `pattern not found`,
  and the second gets the "restore the sentence" advice, wrong for a generated row; three
  surviving mutants (the owner-powers advice naming the wrong file, the advice for a key
  nothing computes, a single rewrite listed); a line matching both retracted-claim patterns is
  printed twice, so its count is untrue.
- Candidate, Level 1: `bench/second_oracle.py`'s report counts a call that errored as a token
  Quick Intel could not answer, so 143 blocked calls printed "0 of 122" and a zero rate. Report calls it
  could not make as not measured, apart from answers, and print no rate over zero answers.
- Candidate, Level 1: `_owner_power_figures()` raises on invalid JSON in
  `bench/owner_powers.json`, while the production readers treat an unreadable artifact as not
  measured. Same class as T-002.
- Candidate, Level 3 area (CI script): `regenerate-derived.sh` runs in the bots' mode with any
  argument other than `regenerate`, and that mode rewrites the clone's git identity, resets to
  origin and pushes. A typo on a laptop does all of that. Require the CI environment
  (`GITHUB_ACTIONS`) for that mode.
- Candidate, Level 3 area (CI script): `regenerate-derived.sh` sends each generator's output to
  `/dev/null`, so a failing bot run shows only `::error::publish_numbers.py failed`, not what
  is left to fix.
- Candidate, Owner's call first (public text): the `docs/EXPERIMENT_C.md` production sentences
  quote the live rate even below the scorecard's 100-answer floor, and compute it as
  `100*u/n` while the scorecard row now uses `(u/n)*100`; the two round differently on 314 of
  about two million (u, n) pairs (T-001 review, problem 4). Whether a below-floor rate belongs
  in that text is a public-claim decision.
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

Lead session 2 started 2026-09-29. The rule (`lead/config.yml`): rotate at about 0.4 of the
context window or 72 hours, at a natural boundary. Lead session 2's context size was not
measured (the lead has no reading of it); it reached a natural boundary after T-002 merged and
CI came back green, with nothing in flight, so a rotation there costs nothing but a new session. Lead session 1 rotated on 2026-09-28 at
50 of 100 parts of the window, after T-001 merged and CI came back green.

## Baseline

Before the lead kit, recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows,
Python 3.13.4, 19.0 s): 26 of 27 steps passed; the red one was `tests/test_published_numbers.py`.
After T-001 (`0a3098d`, 2026-09-28): 27 of 27. **Lead session 2 at `24a0a73` (2026-09-29):
27 of 27 in 19.0 s. After the Level 0 merge (`82acff3`): 27 of 27, and the run leaves the tree
clean. After T-002 (`16e100e`): 27 of 27, clean tree; `tests/test_published_numbers.py` 70 of
70. No failure is known.**
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
**On CI:** `tests` was red from 2026-09-22 12:05 UTC to 2026-09-28: 32 runs, every one failing
at the step "Published accuracy figures match the benchmark". Run 36445100361 on `dc401b9`
(2026-09-28 15:38 UTC) is green: job `test` 27 of 27 steps, none skipped, and
`upstream-contract` and `backfill-roundtrip` succeeded. Run 36455682835 on `16e100e`
(2026-09-28 17:05 UTC, the H-6 push) is green: `test`, `upstream-contract` and
`backfill-roundtrip` succeeded; `benchmark` was skipped, as on every push (it runs only on a
schedule or a manual dispatch). No deploy ran. After it, the latest run of each of the six
workflows had succeeded.
**No local side effect since `82acff3`:** `tests/test_number_coverage.py` restores
`docs/EXPERIMENT_C.md` byte for byte, and `python lead/checks.py` now exits 1 when a run
modifies a tracked file. If it lists one, find the step that wrote it; do not restore it by
hand and move on.

## Recent decisions

- 2026-09-29: T-002 merged as `16e100e` (`--no-ff`, the tests-first commit kept) after a fresh
  review, 12 of 12 (`lead/reviews/T-002.md`), and pushed with the Owner's yes (H-6). The merge
  was clean (checks 27 of 27 on master, CI green on the pushed head), so autonomy is back to A1
  as the Owner approved in advance (H-7). The post-merge regeneration again changed only
  date-driven lines and the recent-commit list; left to the bots (`merge.after`).
- 2026-09-29: the Owner answered H-5 as recommended: both items. The Level 0 fix merged as
  `82acff3` (guard `e54f2bb` watched red first, fix `f1156eb`). Its post-merge regeneration
  changed only the date-driven parts of `docs/OWNER.md` and its recent-commit list, which
  `tests/test_owner_page.py` excuses; not committed, because the bots regenerate on the UTC
  date and the two would conflict before the next push. `lead/config.yml` `merge.after` says so.
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

- 2026-09-29: W5 support. The Owner's first Quick Intel run (real key) got HTTP 403 on all
  143 calls: Cloudflare error 1010 bans Python's default User-Agent. Fixed by naming the
  script; the Owner's probe then got HTTP 200 and 400 from the gateway. With the Owner's yes
  (H-8), three Level 0 branches merged locally; checks 27 of 27 after fixing a digit-percent
  quote in this file that the checks caught before commit.
- 2026-09-29: H-6 and H-7 yes. T-002 merged (`16e100e`); checks 27 of 27 on master; pushed
  `dc401b9..16e100e` (12 commits, nothing under `src/`); CI run 36455682835 green; worktree and
  branch removed. Autonomy A1.
- 2026-09-29: T-002 READY at `0848ff3`; the lead reproduced CONTRACT HOLDS and 27 of 27. Fresh
  review: 12 of 12, VERDICT ✅, no required changes; four optional notes filed as candidates.
  Asked H-6 (merge and push) and H-7 (A1 after a clean merge).
- 2026-09-29: H-5 yes. Level 0 merged (`82acff3`); checks on master 27 of 27 with a clean tree.
  T-002 dispatched to an executor in worktree `../vetagent-t-002`.
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
