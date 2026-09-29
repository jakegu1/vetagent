# Quality: gates, ceremony and milestones

> Thresholds change only with an ADR in `lead/decisions/`. The method behind these rules is in
> the lead kit's `method.md`. Product and engineering decisions are recorded in
> `docs/DECISIONS.md`, as before; this file is only about how work is run.

## Project rules (invariants)

Rules that no task may break. Reviewers score "invariants" against this list. Each one existed
before the lead kit; the source is given so a reviewer can check it.

1. **Fail closed.** A critical check that could not run makes the verdict `unknown`, never
   `low` (`CLAUDE.md`, "Things that are deliberate").
2. **Nothing identifying is recorded.** No token addresses, no identities, no queries in logs or
   telemetry (`wrangler.jsonc`; `tests/test_http_telemetry.py`).
3. **GoPlus is the benchmark's held-out oracle**, never an upstream in `src/` (DECISIONS B2;
   `tests/test_risk.py`).
4. **Published numbers are generated from measurements and guarded.** Measure, then publish, in
   the order in `CLAUDE.md` ("The order that matters"); a number nothing guards is not published
   (`tests/test_published_numbers.py`, `tests/test_number_coverage.py`).
5. **English only** in the repository, lead files included (`tests/test_english_only.py`).
6. **Nothing owner-private in this public repository:** no people, servers, local paths, account
   steps, strategy, gate readings or usage numbers, and no private identifiers
   (`tests/test_no_private_identifiers.py`). Business work stays outside the repository.
7. **Production is probed only under a `vetagent-*` client name** (`x-mcp-client` header),
   never bare (`CLAUDE.md`; `.claude/hooks/no_untagged_probe.py` enforces it for shell
   commands). Do not call MCP tools pointed at production from a session unless their client
   name is tagged `vetagent-*`: an untagged call enters the usage gate as a stranger.
8. **One finding, one commit, and a test that is red before the fix;** the fix commit's message
   says what the red looked like (`CLAUDE.md`, "How work is done here").
9. **Nothing already pushed is rebased or amended;** pull by merge. `tools/rounds.py` pins round
   commits by SHA and `tests/test_rounds.py` catches a rewrite.
10. **Pre-registered gates, floors, bands and thresholds** change only with the Owner's
    sign-off: fix the data, never the bar.
11. Secrets never appear in code, commits, logs or chat.
12. Checks (`python lead/checks.py`) pass, or match the baseline in `lead/STATE.md`, before
    READY and after every merge.

## Ceremony levels

| Level | For | Spec | Review |
|---|---|---|---|
| 0 Direct | Docs, config, typos, no behaviour change | A STATE log line | Green checks |
| 1 Light | Small low-risk change (about 150 changed lines or fewer, one area) | Short | One fresh-context review |
| 2 Standard | Normal feature or fix, core logic | Full Definition of Ready | Independent review with the rubric |
| 3 High risk | See the list below; anything in a sign-off category | Full, plus a threat model | Independent + red-team; Owner sign-off where required |

Level 3 in this project:
- verdict logic in `src/risk.py` where a mistake can rate a dangerous token `low` (sellability,
  honeypot, liquidity, the fail-closed paths);
- telemetry, or anything that could start recording addresses, identities or queries
  (`src/entry.py`);
- changing a published figure or public claim, or removing the only guard over one (README,
  landing page, `/llms.txt`, `docs/EXPERIMENT_C.md`, `docs/SCORECARD.md`);
- deploy and CI workflows, the step runner the deploy runs before it ships
  (`.github/scripts/offline_suite.py`) and its guard (`tests/test_deploy_gate.py`), secrets,
  the rate limiter;
- adding or changing an upstream data source (its terms are legal text);
- the usage gate and every pre-registered rule;
- anything that changes what this public repository exposes.

Pick the lowest level that manages the risk.

## Definition of Ready (Levels 2 and 3; Level 1 needs goal, ACs and files)

- [ ] Context, goal, scope in and out
- [ ] Files in scope, and the backlog W-id if the work has one
- [ ] Numbered, testable acceptance criteria
- [ ] Conflict search done; each affected existing test named as a named change
- [ ] Evidence required for READY
- [ ] Level, size (S or M; split anything larger), risk notes, dependencies
- [ ] A new `tests/test_*.py` is registered as a step in `.github/workflows/test.yml`
      (`tests/test_decisions_enforcement.py` fails otherwise)

## Definition of Done

- [ ] Acceptance tests committed first; contract holds
- [ ] All ACs met, with evidence reproduced by the reviewer
- [ ] Checks green (or at the baseline) on the task head and again after merge
- [ ] Derived pages regenerated after merge (`bash .github/scripts/regenerate-derived.sh
      regenerate`) and committed separately if they changed
- [ ] Review passed (rubric at least 10 of 12, spec = 2, invariants = 2); red-team "none" for
      Level 3
- [ ] Spec status `done`; STATE, OWNER and the task index updated

## Review rubric

| Item | 0 | 1 | 2 |
|---|---|---|---|
| Spec conformance | ACs missing | Minor gaps | All ACs met with evidence |
| Scope discipline | Unrelated changes | Small justified extras | Only files in scope |
| Correctness | Bugs found | Edge cases unclear | No defects under probing |
| Test quality | Tests don't test | Happy path only | Tests fail on broken code; edges covered |
| Invariants | A rule broken | Borderline | All project rules hold |
| Maintainability | Hard to follow | Acceptable | Clear, consistent with the codebase |

## Milestones

| Milestone | Exit criteria (measurable) | Calendar clock? |
|---|---|---|
| M0 Loop proven | T-001 merged through the whole loop: spec, executor in its own worktree, fresh-context review, merge commit, `python lead/checks.py` green on master | No |
| M1 CI green and staying green | The `tests` workflow is green on every run on master for 7 consecutive days (`gh run list --workflow=test.yml`) | Yes: starts with the first push after T-001 merges |
| Product gates | Owned by `docs/STRATEGY.md` §8 and shown in `docs/OWNER.md`; not restated here | Theirs |

For every criterion that needs calendar time, the weekly pass confirms that the clock is
running.

## Tripwires

| ID | Signal | Threshold | Action |
|---|---|---|---|
| Q1 | Escaped defect (found after merge) | Any | Demote autonomy one level; add a pitfall |
| Q2 | Review rounds per task | More than 2 on two tasks in a row | Review spec quality in the weekly pass |
| Q3 | Owner interruptions | More than 2 per week | Find what the lead could have decided itself |
| Q4 | Checks red on master, locally or on CI (`gh run list --workflow=test.yml`) | Any | Stop new work until green; a red CI is read as "unknown past this step", not as one failure |
