---
id: T-004
title: Run the whole offline suite before every deploy
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: M                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: none            # a lead candidate since the adoption audit; no BACKLOG row
---

## Context

`deploy.yml` ships production on a push to `master` that touches `src/**`, `pyproject.toml`,
`wrangler.jsonc` or `.github/workflows/deploy.yml` itself, and on a manual dispatch. Before
`pywrangler deploy` it runs two test files by hand (step "Regression tests":
`python tests/test_risk.py` and `python tests/test_mcp.py`). The `tests` workflow's offline
job runs 27 steps. The two workflows start side by side on the same push, and the deploy does
not wait for `tests`. So a push to `src/` that breaks any of the other 25 steps deploys anyway.
Several of those 25 guard what production says and records: nothing identifying is recorded
(`tests/test_http_telemetry.py`), published figures on the landing page and `/llms.txt` match
the benchmark (`tests/test_published_numbers.py`, `tests/test_number_coverage.py`), advertised
coverage is true (`tests/test_advertised_coverage.py`), nothing private is published
(`tests/test_no_private_identifiers.py`). Invariants 2, 4 and 6 in `lead/QUALITY.md` are
therefore enforced before merge only by whoever looks at `tests`, and not at all before a
deploy.

`lead/checks.py` already runs every step of that offline job, read from
`.github/workflows/test.yml` at run time (never typed), in order, without stopping at the
first red, and fails closed: exit 2 when it finds no steps, a red step for a `run:` it cannot
parse, exit 1 when any step fails or the run modified a tracked file. It lives in `lead/`, the
lead workflow's footprint (ADR-0001: small and reversible), so the product's deploy should not
depend on it where it is.

Two facts the design has to respect:
- `test.yml` checks out with `fetch-depth: 0` because `tools/rounds.py` reads the whole history
  and `score_at()` runs `git show <commit>:docs/SCORECARD.md`; "the default depth of 1 made
  test_rounds.py fail on every push from R11 onwards" (its comment). `deploy.yml` checks out at
  the default depth.
- Every step of the offline job is stdlib Python (`test.yml` installs nothing) on Python 3.12.

## Goal

A deploy runs only after every step of `test.yml`'s offline `test` job has passed on the
commit being deployed, from the one step list in `test.yml`; if any step fails, or the step
list cannot be read, nothing is deployed.

## Scope

**In:**
- Move the runner from `lead/checks.py` to `.github/scripts/offline_suite.py` (product-owned),
  unchanged in behaviour. `lead/checks.py` stays as a thin wrapper with the same command line,
  output and exit statuses (`lead/config.yml` and the lead kit call it).
- `deploy.yml`: check out with full history; replace the hand-typed "Regression tests" step
  with one that runs `python .github/scripts/offline_suite.py`, before any step that installs
  deploy tooling or deploys, under the same condition as the deploy.
- A guard test for the above, registered as one new step in `test.yml`'s `test` job.

**Out:**
- The network jobs (`upstream-contract`, `backfill-roundtrip`) and the weekly `benchmark` job
  stay out of the gate: a third party's outage must not block a deploy (the same reasoning as
  the blue-chip canary in `deploy.yml`).
- Every other step of `deploy.yml`: credentials check, uv, `pywrangler deploy`, the smoke
  test, IndexNow. Their tests (`tests/test_http_telemetry.py`, `tests/test_usage_gate.py`,
  `tests/test_bot_commits_stay_green.py`) must pass unchanged.
- The `tests` workflow's triggers and existing steps; the bots; `regenerate-derived.sh`.
- An override for emergencies (see Notes). No `continue-on-error`, no `|| true`, no skip input.
- Waiting on the `tests` workflow's run instead (`workflow_run`): rejected for this task, see
  Notes.

## Files in scope

- `.github/scripts/offline_suite.py` (new; the runner, moved with `git mv` from `lead/checks.py`
  so history follows it)
- `lead/checks.py` (the wrapper)
- `.github/workflows/deploy.yml` (the checkout and the test step only)
- `.github/workflows/test.yml` (one new step running the new test file; nothing else)
- Acceptance tests: `tests/test_deploy_gate.py` (new)
- **Named changes to existing tests:** none. Conflict search (2026-09-29, `git grep` over
  `tests/*.py` and `tests/fixtures/**` for `deploy.yml`, `checks.py`, `Regression tests`,
  `fetch-depth`, `offline`, `.github/scripts`): `tests/test_http_telemetry.py` reads
  `deploy.yml`'s IndexNow key and its flood step; `tests/test_usage_gate.py` reads the smoke
  test's curls; `tests/test_bot_commits_stay_green.py` reads every workflow, skips `deploy.yml`
  in its regeneration check, and scans `.github/scripts/*.sh` for `git push` (a `.py` script
  is not matched); `tests/test_decisions_enforcement.py` requires every `tests/test_*.py` to be
  named in `test.yml` (hence the new step). None reads the test step or the checkout.

## Acceptance criteria

1. **One list, read at run time.** `python .github/scripts/offline_suite.py` runs exactly the
   `run:` steps of `test.yml`'s `test` job, in file order (28 once the new step exists), with
   the behaviour `lead/checks.py` has today: every step runs even after a red one; one line per
   step; exit 0 only if every step passed and no tracked file was modified; exit 2 when the job
   or its steps cannot be found; an unparseable `run:` is a red step.
2. **The wrapper is the same tool.** `python lead/checks.py` gives the same output and exit
   status as the runner, on the current tree and on a red one (for example with a failing step
   in a temporary copy of the workflow).
3. **Fails closed, shown on synthetic workflows.** With the runner pointed at a temporary
   workflow file: a failing step makes it exit non-zero and the steps after it still run; a
   workflow with no `test` job, or with no steps, exits 2; an unsupported `run:` is red. The
   test must not depend on the real suite passing.
4. **The deploy is gated.** In `deploy.yml`'s deploy job: the checkout has `fetch-depth: 0`; a
   step runs `python .github/scripts/offline_suite.py`; it comes after the checkout and Python
   setup and before the steps that install uv, sync dependencies and run `pywrangler deploy`;
   its condition is the one the deploy step has (so the deploy cannot run while the gate is
   skipped); nothing lets it fail without failing the job (`continue-on-error`, `|| true`,
   `set +e`, an `if:` that runs later steps after a failure).
5. **No second list.** `deploy.yml` names no `tests/test_*.py` file of its own.
6. **Nothing else in the deploy moves.** Apart from the checkout's depth and the replaced test
   step, `deploy.yml` is unchanged (show `git diff` of it). The existing tests that read
   `deploy.yml` pass unchanged.
7. **Contract and checks.** The first commit adds only `tests/test_deploy_gate.py`, and is red
   there (run it directly: it is not yet a step in `test.yml`, so at that commit
   `tests/test_decisions_enforcement.py` is also red for the unregistered file; that red is
   expected and is cleared by the commit that adds the step). The contract checker counts only
   `tests/` as test files, so the `test.yml` step goes in a later commit. The move, the
   wrapper, the step and the `deploy.yml` change follow in their own commits, each message
   saying what the red looked like. `python lead/checks.py` passes every step (28 of 28),
   exit 0.

## Evidence required

- At the first commit: `python tests/test_deploy_gate.py`, red, and why.
- At the head: that file passing; `python lead/checks.py` and
  `python .github/scripts/offline_suite.py` on the current tree (both outputs, identical apart
  from timings, exit 0); both on a red copy (the same exit status, non-zero).
- `git diff <base> -- .github/workflows/deploy.yml` in full.
- At least three mutants you tried and saw turn a check red, including: the gate step moved
  after `pywrangler deploy`; `continue-on-error: true` on it; the checkout depth reverted.
- Say plainly that the new gate can only be observed running on CI by the deploy that pushing
  this change triggers (see Notes); you cannot run `deploy.yml` locally.

## Notes

- **Threat model.** What must never happen: production is deployed from a commit on which an
  offline step fails. Realistic causes to close: a hand-typed list in `deploy.yml` drifting
  from `test.yml` (today: 2 of 27); a shallow checkout making history-reading steps fail, and
  the pressure that creates to drop them from the gate; a runner that finds no steps and
  passes vacuously; the gate skipped by a condition while the deploy step runs; a failure
  swallowed (`continue-on-error`, `|| true`); the gate placed after the deploy; the gate
  depending on the lead kit, so that removing `lead/` breaks or silently removes it. The
  guard's defence is `tests/test_deploy_gate.py` reading `deploy.yml` and `test.yml`, plus the
  runner's own fail-closed exits.
- **Pushing this change deploys production.** `deploy.yml` is in its own `paths` trigger, so
  the push that carries this change runs the deploy job: the new gate on CI for the first
  time, then `pywrangler deploy` of the unchanged `src/`, then the smoke test's production
  calls, all tagged `vetagent-ci-smoke`. If the gate is red there, nothing deploys and
  production keeps its current version. The Owner approves that push knowing this.
- **Calendar-driven steps.** Some offline steps go red with time rather than with code
  (`tests/test_gates_get_reviewed.py` when a parked item is overdue; `tests/test_owner_page.py`
  when the page is more than 7 days old). With the gate, such a red also blocks deploys until
  it is fixed, which is the same rule `tests` already applies to `master`. No override in this
  task; if one is ever wanted, it is a manual dispatch input with a written reason, decided
  separately.
- **Why not wait on the `tests` run (`workflow_run`) instead.** It runs the deploy workflow file
  from the default branch rather than the pushed commit, loses the `paths` filter (every push
  would deploy, or a hand-written diff would decide), and ties the deploy to the network jobs'
  outcome. Running the same list inside the deploy job keeps one trigger and one list.
- Cost: the suite takes about 20 to 30 seconds locally; expect about a minute more per deploy.
- `lead/checks.py`'s docstring history (why it exists, the 2026-09-29 tracked-file rule) moves
  with the runner; the wrapper's docstring points to it.
- Write any file containing a backslash or a backtick with an editor tool, not a shell heredoc
  (`CLAUDE.md`). English only. Run tests as scripts, not with pytest.

## Amendments

None yet.
