---
id: T-004
title: Run the whole offline suite before every deploy
status: done             # draft | ready | in_progress | in_review | changes_requested | done | dropped
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

- **2026-09-29, before the reviews: two fail-open gaps in the moved runner are fixed in this
  task.** The executor measured both at `521fc6c`. They are the threat model's own class (a
  gate that passes having run less than the list), so they are in scope although the spec said
  to move the runner unchanged:
  1. A comment line at the jobs' indentation (two spaces) inside the `test` job ends the
     runner's reading of the job: with one such comment, YAML sees 28 steps and the runner
     reads 6, so the gate would pass and deploy while `tests` is red.
  2. `run: python a.py && python b.py` runs `a.py` with the rest as arguments and reports ok;
     the second command never runs.

  Allowed changes:
  - **Runner** (`.github/scripts/offline_suite.py`): the job ends only at the next job id (a
    line with exactly two spaces of indentation followed by a name and a colon), never at a
    comment or a blank line; a `run:` whose command contains a shell operator (`&&`, `||`, `;`,
    `|`, a backtick, `$(`, `>`, `<`) is an unsupported step, reported red, and the run exits
    non-zero. Each fix in its own commit, message saying what the red looked like.
  - **Named change (a)**, `tests/test_deploy_gate.py`, the synthetic-workflow checks: add a
    case with a comment at two-space indentation between two steps of the `test` job; the
    runner must run the steps after the comment.
  - **Named change (b)**, same file: add cases where a `run:` joins two commands with `&&`
    and with `;`; each is reported red as unsupported, the run exits non-zero, and the other
    steps still run.
  - Named changes (a) and (b) go in one commit titled `T-004: named change (a, b) ...`, made
    before the two runner fixes, so that commit shows both new cases red.

  Decided, not required: the runner treating a failing `git status` as "no tracked file
  changed" (pre-existing; the deploy job's checkout is always a repository). Moving the guard
  step first in `test.yml` (rejected: a red guard would hide the rest of the `tests` job on
  CI). Linux: the gate is observed on CI only after a push; the lead plans the push order.

- **2026-09-29, second amendment, still before the reviews: close the class, not the next
  instance.** At `09f3803` the executor measured three more shapes the runner reads as fewer
  commands than GitHub runs: a step whose first key is `run:` (`- run: python ...`, skipped; if
  the guard's own step is written so, the gate passes 27 of 27 without running the guard); a
  flow-style step (`- { name: x, run: ... }`); and a plain `run:` value continued on the next,
  more indented line. Adding one shape at a time leaves the next one open. The rule instead:
  **after `steps:` in the `test` job, the runner goes red on any line it does not recognise.**
  Recognised: blank lines and comments; a step start (`- ` followed by one of the step keys);
  a step key at the step's indentation (`name`, `id`, `if`, `uses`, `with`, `env`, `run`,
  `shell`, `working-directory`, `continue-on-error`, `timeout-minutes`); `key: value` lines
  nested under `with:` or `env:`; the lines of a `run: |` or `run: >` block. Anything else,
  including a line more indented than a single-line `run:` value, is red and named.

  Allowed changes:
  - **Named change (c)**, `tests/test_deploy_gate.py`, the synthetic-workflow checks: a job
    whose steps are written `- run: python ...` has them run (including a guard-like step
    written so); a flow-style step is red, named, and the run exits non-zero; a plain `run:`
    value continued on the next line is red, named, and the run exits non-zero; the real
    `test.yml` has no unrecognised line and still reads 28 commands. One commit titled
    `T-004: named change (c) ...`, made before the runner changes, showing the new cases red.
  - **Runner**: accept `- run:`; go red on unrecognised lines after `steps:` as above. One
    commit per change, each message saying what the red looked like.
  - The lone `&` the previous round added to the operator set stays: it joins commands too.

  Bar for the reviews: the three shapes red before and green after (or red by design, for the
  two that must be refused); mutants "skip `- run:` steps" and "ignore unrecognised lines" each
  turn the guard red; the real `test.yml` reads 28 commands with nothing unrecognised;
  `python lead/checks.py` 28 of 28, exit 0; contract holds with named changes (a, b) and (c)
  listed as allowed; nothing outside the five files in scope changes.

- **2026-09-29, round 2 after the reviews** (independent pass 11 of 12; red-team 2 material).
  The lead decision, with its threat model, required fixes and bar, is in
  `lead/reviews/T-004.md` under "Round 1 · lead decision". It allows named changes to
  `tests/test_deploy_gate.py`, each in its own commit titled `T-004: named change (<letter>) ...`
  and made before the code it tests: **(d)** the wrapper check says "not checked here" when
  `lead/` is absent; **(e)** the guard reads a multi-line `deploy.yml` value whole and matches
  status functions without regard to case; **(f)** the new refusal cases (unclosed quote or
  bracket, folded `run:`, unapplied step keys, `uses:` outside the allowlist, stray line-break
  characters, every operator, a job key after `steps:`, a bad line under `with:`/`env:`), plus,
  if trivial, the same Python version in both workflows. The runner changes the decision lists
  are allowed in `.github/scripts/offline_suite.py`.
