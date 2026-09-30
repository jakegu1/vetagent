---
id: T-008
title: Refuse snapshot-commit.sh outside GitHub Actions, and pin its push path
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: none            # T-006 round-1 red-team, minor note 5 (lead/reviews/T-006.md)
---

## Context

`.github/scripts/snapshot-commit.sh` commits and pushes what the snapshot collector wrote.
`snapshot.yml` calls it twice per pass on `ubuntu-latest`: `"pools"`, then `"sellability"` (with
`continue-on-error`). With any argument or none, it runs, in order: `git config user.name
"vetagent-snapshot[bot]"` and `user.email` (written into the repository's own config, which every
worktree of a clone shares); `git add bench/snapshots/`; if nothing is staged, a `::warning::` and
exit 0; otherwise `git commit` and up to five `git push` attempts, where each rejected push is
followed by `git pull --rebase --autostash origin "${GITHUB_REF_NAME}"` and `sleep $((attempt *
10))`.

So a local run, by a person or by an agent looking into the snapshot pipeline, rewrites the
clone's git identity (the Owner's next commits would be attributed to the bot), commits whatever
is staged under `bench/snapshots/`, and, when the branch tracks origin, pushes every local commit
without the Owner's yes. Pushing is a sign-off category, and a push touching `src/` also deploys.
T-006 closed this class for `regenerate-derived.sh` with a check that `GITHUB_ACTIONS` is exactly
`true`, and that check is proven on CI: snapshot run 36690932257 and production run 36718468014
(2026-09-30) passed through it and pushed. T-006's red-team (minor note 5) found the same hazard
here.

The retry path (a rejected push, rebased and retried) is the reason this script exists (its
header: "THE PUSH RETRIES, AND THAT IS THE POINT"), and no test runs it:
`tests/test_sellability_archive.py` only checks that the script's text contains `pull --rebase`,
`for attempt`, `::error::` and `LOST`.

GitHub sets `GITHUB_ACTIONS` to `true` for every step it runs, and to nothing else. A laptop does
not set it.

## Goal

Outside GitHub Actions the script refuses before its first git command. On GitHub Actions it
behaves exactly as before, and behavioural tests pin its three paths there: nothing new; a commit
and a push; a rejected push that is rebased and retried.

## Scope

**In:** a check at the top of `snapshot-commit.sh`, before the first git command, that exits 2
unless `GITHUB_ACTIONS` is exactly `true`, with an error that says why and says not to set the
variable by hand to get past it (the wording T-006 used for `regenerate-derived.sh`); the
script's header comment; behavioural tests that run the real script in scratch repositories,
added to `tests/test_bot_commits_stay_green.py` and reusing its harness (`_Scratch`, the bash
finder, the "not run here" rule and its failure on Actions, the canary on this repository).

**Out:** any other change to the script (its messages, retry count and sleeps stay as they are);
`snapshot.yml` and every other workflow; `regenerate-derived.sh`; T-006's existing checks in the
test file; documents (the lead updates `CLAUDE.md` and `lead/` after the merge).

## Files in scope

- `.github/scripts/snapshot-commit.sh`
- `tests/test_bot_commits_stay_green.py`: new test functions, called from `main()`. It is already
  a step of `test.yml`, so no workflow changes.
- **Named changes to existing tests:** none. Conflict search (2026-09-30):
  `tests/test_sellability_archive.py` (about lines 440 to 466) reads the script's text for
  `pull --rebase`, `for attempt`, `::error::` and `LOST`, and `snapshot.yml`'s step order; the
  existing checks in `tests/test_bot_commits_stay_green.py` (about line 173) scan workflow lines
  that name the script. Neither changes. Any other older test failing means BLOCKED.

## Acceptance criteria

1. **Refused outside GitHub Actions.** With `GITHUB_ACTIONS` unset, and separately set to `""`,
   `false`, `1`, `TRUE`, `" true"` and `"true "`, the script called with `pools` exits 2 with an
   error that says why; also with no argument, and with `sellability`, when it is unset. After
   each call, in the scratch repository: `user.name` and `user.email` are unchanged, a new file
   staged under `bench/snapshots/` is still staged and uncommitted, `HEAD` is unchanged, and the
   scratch origin has no new commit.
2. **Nothing new, on Actions.** With `GITHUB_ACTIONS=true`, `GITHUB_REF_NAME=master` and nothing
   new under `bench/snapshots/`: exit 0, the `::warning::no pools rows collected` line, no new
   commit, and the scratch origin unchanged.
3. **A commit and a push, on Actions.** With new rows under `bench/snapshots/`: exit 0; the
   scratch origin's `master` has exactly one new commit, authored by `vetagent-snapshot[bot]`, with
   the subject `Snapshot <UTC date> (pools): <days> days, <rows> rows total` and the counts the
   scratch files imply, touching only files under `bench/snapshots/`.
4. **Rejected, rebased and retried, on Actions.** When the scratch origin's `master` has moved
   ahead with an unrelated commit before the call: exit 0; the output says the first push was
   rejected and a later attempt pushed; the origin's `master` has both commits, with the snapshot
   commit on top. No real sleeping: for example, a stub `sleep` first on `PATH` in the scratch
   environment. The script's own sleeps do not change.
5. **The tests cannot reach this repository.** As in T-006: scratch repositories under the system
   temporary directory, a local bare repository as `origin`, every git command the script runs
   pinned to the scratch repository (`GIT_DIR` and `GIT_WORK_TREE`, or an equivalent that holds
   even if `cwd` were wrong), and the canary on this repository (its identity, `HEAD` and status)
   still holding after the new calls.
6. **Where bash is not usable,** the new checks say they were not run here, never count as passed,
   and on GitHub Actions make the file exit 1 (the rule T-006 set, unchanged).
7. **Contract and checks.** The first commit adds only the new tests, and at that commit they are
   red for AC 1 (the scratch identity rewritten, the staged file committed, the origin moved). At
   the head, `python lead/checks.py` passes 29 of 29, exits 0 and leaves the tree clean. The new
   checks' wall time on Windows is reported (target: under 10 seconds; the file's T-006 checks are
   already slow here).

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_bot_commits_stay_green.py` on
  it: which checks fail, and what the scratch repository and its origin looked like afterwards.
- At the head: the same command (all pass, with the counts, and no "not run here" line on this
  machine), then `python lead/checks.py` (summary line and exit status), `git status --short`
  (empty), and `git config user.name` in this repository (unchanged).
- The final diff of `snapshot-commit.sh`.
- Three mutants the tests catch: the check reading `GITHUB_ACTION` (singular, a different
  variable GitHub also sets); the check placed after `git config`; and the retry loop cut to one
  attempt. Restore and clear `__pycache__` after each.
- `git diff --stat <base>..HEAD`: only the two files in scope.
- A scan of the changed files for non-ASCII characters: none.

## Notes

**Threat model.** What must never happen: (a) outside GitHub Actions the script rewrites the
clone's identity, commits or pushes; (b) on GitHub Actions the snapshot bot stops committing or
pushing, which loses that pass's rows for good (upstream serves current state only; a day not
recorded never existed); (c) the new tests run the script against this repository, which would
commit here and push. Realistic accidents to defend against: running the script by hand to see
what it does; running it from a task worktree (the git config it writes is shared by every
worktree); a CI variable with a similar name; a value with different case or stray whitespace; a
test whose isolation depends on `cwd` alone.

- On CI the tests themselves run inside GitHub Actions with `GITHUB_ACTIONS=true` and
  `GITHUB_REF_NAME` set: the negative cases must remove the first, and every case sets the
  second explicitly. Create the scratch branch as `master` explicitly (`init.defaultBranch`
  differs between machines).
- The script uses `set -uo pipefail`; reference the variable as `${GITHUB_ACTIONS:-}`.
- The commit subject's date comes from `date -u +%F`. Near midnight UTC the test's own date may
  differ by one day; accept either.
- The deploy job runs every step of `test.yml`'s `test` job before it deploys, so a flaky or slow
  check here blocks deploys.
- Write files with the Write or Edit tool, not shell heredocs. The Write and Edit tools decode
  backslash-u escapes into real characters (`lead/PITFALLS.md`).
- Scratch files go in your own subfolder of the session scratchpad; the rest of it belongs to
  other agents.

## Amendments

None yet.
