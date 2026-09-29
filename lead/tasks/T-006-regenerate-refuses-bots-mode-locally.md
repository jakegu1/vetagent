---
id: T-006
title: Refuse regenerate-derived.sh's bots' mode outside GitHub Actions
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: none            # a lead candidate since 2026-09-28 (lead/PITFALLS.md); no BACKLOG row
---

## Context

`.github/scripts/regenerate-derived.sh` has two modes, chosen by its first argument:

- `regenerate`: run the four page generators to a fixed point and leave the files. This is the
  local mode; `CLAUDE.md`, `lead/config.yml` (`merge.after`) and the lead's merge checklist run it
  after every merge.
- any other non-empty argument: the bots' mode, used by `snapshot.yml` and `production.yml` on
  GitHub-hosted runners (`bash .github/scripts/regenerate-derived.sh "Snapshot $(date -u +%F)"`).
  In order, it runs `git config user.name` and `user.email` (the bot's identity, written into
  the repository's own config, which every worktree of a clone shares), fetches origin, stops
  with exit 0 if the checkout holds a commit origin does not have, and otherwise runs
  `git reset --hard origin/<ref>` (discarding every uncommitted change to a tracked file),
  regenerates, commits and pushes to origin.

No argument prints the usage and exits 2.

So on a laptop, one mistyped argument (`regenrate`, `Regenerate`, or the CI usage line copied
from the script's own header) rewrites the clone's git identity every time, so that the Owner's
next commits are attributed to `vetagent-derived[bot]`. When the checkout has no unpushed commit,
it also discards uncommitted work and pushes to origin without the Owner's yes, and pushing is a
sign-off category. Every document warns "only ever with the argument `regenerate`"
(`CLAUDE.md`, `lead/PITFALLS.md`, `lead/config.yml`); nothing enforces it.

GitHub sets the environment variable `GITHUB_ACTIONS` to `true` for every step it runs (GitHub's
documented default variables), and to nothing else. A laptop does not set it.

## Goal

Outside GitHub Actions the script can only regenerate files or print its usage: any other
argument is refused before it runs a single git command. On GitHub Actions the bots' mode works
exactly as before.

## Scope

**In:** a check in `regenerate-derived.sh`, placed after the `regenerate` and usage branches and
before the first git command, that refuses the bots' mode unless `GITHUB_ACTIONS` is exactly
`true`; the script's header comment; behavioural tests that run the real script in a scratch
repository.

**Out:** any other change to either mode; the workflows; `CLAUDE.md`, `lead/` and other documents
(the lead updates them after the merge); `offline_suite.py` and the deploy gate.

## Files in scope

- `.github/scripts/regenerate-derived.sh`
- Acceptance tests: `tests/test_bot_commits_stay_green.py` (new test functions, called from its
  `main()`; the existing checks stay as they are). It is already a step of `test.yml`, so the
  workflow does not change.
- **Named changes to existing tests:** none. The conflict search: `tests/test_bot_commits_stay_green.py`
  reads the script's text (the generators it runs, the `src/` refusal, `git reset --hard`,
  `rev-list --count`), and none of that changes; `tests/test_published_numbers.py` names the
  script's `regenerate` command as a remedy in its messages only; `snapshot.yml` and
  `production.yml` call it with a commit-subject prefix. Any other older test failing means
  BLOCKED.

## Acceptance criteria

1. **Refused outside GitHub Actions.** With `GITHUB_ACTIONS` unset, and separately set to `1`,
   `false` and the empty string, the script called with `regenrate`, with `Regenerate` and with
   `"Snapshot 2026-09-22"` exits 2 with an error that says why and names `regenerate`. After each
   call, in the scratch repository: `user.name` and `user.email` are unchanged, an uncommitted
   change to a tracked file is still there, `HEAD` is unchanged, and the scratch origin has no
   new commit.
2. **The bots still run on GitHub Actions.** With `GITHUB_ACTIONS=true` and a commit-subject
   argument, the call gets past the check: the bot identity is written into the scratch
   repository's config, the run ends as it does today (with stub generators that change nothing:
   "the derived pages are already current", exit 0), and the scratch origin has no new commit.
3. **The other two modes are unchanged.** No argument: usage, exit 2, nothing in the scratch
   repository changed. `regenerate` (with stub generators): exit 0, and no git identity, reset,
   commit or push.
4. **The tests cannot reach the real repository.** Every call runs in a scratch repository
   created under the system temporary directory, outside this repository, with a local bare
   repository as its `origin`. Every git command the script runs is pinned to it (`cwd`, plus
   `GIT_DIR` and `GIT_WORK_TREE`, or an equivalent that holds even if `cwd` were wrong), and the
   test asserts that `git rev-parse --show-toplevel` in the scratch directory is the scratch
   directory before the first call. The scratch repository sets its own identity and disables
   commit signing and hooks, so the machine's global git config changes nothing.
5. **Where bash is not usable, say so.** CI's Linux runner always has bash. On Windows the tests
   use Git for Windows' bash (found from `git`'s own install), never the `bash.exe` in the Windows
   system directory, which starts WSL. If no usable bash is found, the new checks print that they were not run here and why; they
   never count as passed.
6. **Contract and checks.** The first commit adds only the new tests, and at that commit they are
   red for AC 1 (the scratch identity rewritten, the uncommitted change gone). `python
   lead/checks.py` passes 28 of 28, exits 0 and leaves the tree clean. The new checks take under
   15 seconds on Windows.

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_bot_commits_stay_green.py`
  on it: which checks fail, and what the scratch repository looked like afterwards.
- At the head: the same command (all pass, with the count, and no "not run here" line on this
  machine), then `python lead/checks.py` (summary line and exit status), then
  `git status --short` (empty), and `git config user.name` in this repository (unchanged).
- The final diff of `regenerate-derived.sh`.
- Two mutants the tests catch: the check reading `GITHUB_ACTION` (singular, a different variable
  GitHub also sets) and the check placed after the first `git config`.
- `git diff --stat <base>..HEAD`: only the two files in scope.
- A scan of the changed files for non-ASCII characters: none.

## Notes

**Threat model.** What must never happen: (a) outside GitHub Actions, the script rewrites the
clone's identity, resets its working tree, commits or pushes; (b) on GitHub Actions, the bots
stop regenerating, which would leave master red after the next bot commit and restart milestone
M1 (7 green days, due 2026-10-05); (c) the new test itself runs the bots' mode against this
repository, which would reset it to origin and could push. Realistic accidents to defend
against: a typo or a case change in the argument; the CI usage line pasted from the header; a
run from a task worktree (the git config it would rewrite is shared by every worktree); a CI
environment variable with a similar name; a test whose scratch isolation depends on `cwd` alone.

- `snapshot.yml` and `production.yml` run on `ubuntu-latest`. A step's own `env:` block does not
  unset `GITHUB_ACTIONS`.
- The script uses `set -uo pipefail`; reference the variable as `${GITHUB_ACTIONS:-}`.
- On CI, the tests themselves run inside GitHub Actions with `GITHUB_ACTIONS=true` and
  `GITHUB_REF_NAME` set: the negative cases must remove the first and every case should set the
  second explicitly. Create the scratch branch as `master` explicitly (`init.defaultBranch`
  differs between machines).
- The deploy job runs every step of `test.yml`'s `test` job before it deploys
  (`.github/scripts/offline_suite.py`), so a flaky or slow check here blocks deploys.
- Write files with the Write or Edit tool, not shell heredocs. The Write and Edit tools decode
  backslash-u escapes into real characters (`lead/PITFALLS.md`).
- Scratch files go in your own subfolder of the session scratchpad; the rest of it belongs to
  other agents.

## Amendments

- **2026-09-30, round 1 lead decision** (`lead/reviews/T-006.md`): back to the executor for one
  round. Required: (1) on GitHub Actions (`GITHUB_ACTIONS` exactly `true`) a check that could not
  run makes the test file exit 1; off Actions it behaves as today; (2) the refusal checks also
  cover `" true"`, `"true "` and `"TRUE"`; (3) the canary's failure detail names the changed
  `user.*` keys, never their values. Named changes to `tests/test_bot_commits_stay_green.py`,
  each in its own commit: **(a)** a check that the file exits 1 on Actions and 0 off it when a
  group could not run (red first), then the summary change that turns it green; **(b)** the three
  near-miss values join the off-Actions values; **(c)** the canary's detail lists key names only.
  Nothing else in the test file changes.
