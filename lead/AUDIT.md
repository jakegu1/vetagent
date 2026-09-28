# Adoption audit (snapshot, 2026-09-28)

> Written by the lead during adoption. A snapshot, not a living document: it records what
> was true on the date above, with the command or file behind each fact. Audited at
> `origin/master` = `f6c7c06` (2026-09-28 08:48 UTC), in a scratch clone, so the Owner's
> checkout was not touched. The Owner's local `master` was at `76e7c03`, 66 commits behind,
> all of them bot commits (`git log master..origin/master --author=jakegu1` is empty). With
> the Owner's agreement it was fast-forwarded to `f6c7c06` before the adoption commit.

## Shape

- **What it is:** an MCP server and HTTP API that an AI agent calls before it buys a token,
  deployed as a Cloudflare Python Worker at `vetagent.dev` (`wrangler.jsonc`: `main:
  src/entry.py`, `python_workers`). Project summary: `docs/OWNER.md`, "The project in one
  paragraph".
- **Code:** `src/risk.py` (4382 lines, the engine), `src/entry.py` (1140, routes and
  telemetry), `src/mcp_server.py` (442), `src/pages.py` (388), `src/og_image.py` (608),
  `src/landing.html`. Tools in `tools/` (`owner.py`, `rounds.py`, `upstream_fields.py`);
  measurement in `bench/` (benchmark, publish_numbers, scorecard, snapshot archive).
- **Language and dependencies:** Python 3.12+ standard library only at runtime
  (`pyproject.toml`: `dependencies = []`); `workers-py` and `workers-runtime-sdk` as dev
  tools for deploys.
- **Tests:** 27 files `tests/test_*.py`, hand-rolled runners that print `PASS`/`FAIL` and
  exit non-zero on failure. Run them as scripts, not with pytest (pytest collects only a
  subset and reports green while the real suite is red).
- **Existing process documents:** `docs/DECISIONS.md` (decision record, enforced by
  `tests/test_decisions_enforcement.py`), `docs/BACKLOG.md` (W-items, shape-checked by
  `tests/test_backlog.py`), and three generated pages with currency tests:
  `docs/OWNER.md` (`tools/owner.py`), `docs/SCORECARD.md` (`bench/scorecard.py`),
  `docs/ROUNDS.md` (`tools/rounds.py`). Agent rules: `CLAUDE.md` (no `AGENTS.md`, no other
  agent instruction files). `.claude/settings.json` holds one PreToolUse hook
  (`.claude/hooks/no_untagged_probe.py`) that refuses untagged HTTP probes of production.

## Commands

| Purpose | Command | Source |
|---|---|---|
| Install | none for tests (standard library); `uv sync` only for deploy tooling | `pyproject.toml`, `deploy.yml` |
| Offline checks (what CI's `test` job runs) | 27 steps: `python -m compileall -q src tests`, 25 test files, `python bench/scorecard.py` | `.github/workflows/test.yml`, job `test` |
| Network tests (not in the offline job) | `python tests/test_upstream_contract.py`, `python tests/test_backfill.py` | `test.yml` jobs `upstream-contract`, `backfill-roundtrip` (soft) |
| Lint | none beyond the `compileall` syntax check | `test.yml` |
| Build / deploy | CI only: `uv run pywrangler deploy` on a push to `master` touching `src/**` | `.github/workflows/deploy.yml` |
| Order after an engine or benchmark change | `bench/run_benchmark.py`, `bench/publish_numbers.py --write`, `bench/scorecard.py --write`, the tests | `CLAUDE.md`, "The order that matters" |
| Regenerate derived pages | `bash .github/scripts/regenerate-derived.sh regenerate` | the script's header |

## Baseline

Recorded 2026-09-28 on `f6c7c06`, Windows, Python 3.13.4, every step of the offline `test`
job run in order without stopping at the first failure (18.9 s in total):

- **26 of 27 steps green.** Suite counts: `test_risk.py` 706 passed, `test_mcp.py` 80,
  `test_owner_page.py` 241, `test_http_telemetry.py` 163, `test_coverage_matrix.py` 124
  (4 not settled by the reference token), `test_advertised_coverage.py` 103,
  `test_usage_gate.py` 70, `test_sellability_archive.py` 60, `test_owner_powers.py` 57,
  `test_owner_power_recall.py` 57, the rest smaller; 0 failures in all of them.
- **1 red: `tests/test_published_numbers.py`.** Output: "docs/SCORECARD.md published
  pattern not found", for the pattern `unknown rate \(production, served answers\) \|
  [\d.]+ \| 5 \| ([\d.]+)`.
- **Side effect:** the run rewrites `docs/EXPERIMENT_C.md` with LF line endings on Windows
  (`core.autocrlf=true`; `git diff --ignore-cr-at-eol` is empty). Content is unchanged.

## CI

- Six workflows: `test.yml` (named `tests`), `deploy.yml`, `snapshot.yml`,
  `production.yml`, `usage.yml`, `zone-check.yml`.
- **`tests` has failed on every run since 2026-09-22 12:05 UTC: 31 runs, 0 green**
  (`gh run list --workflow=test.yml`). The last green run was 07:52 UTC the same day
  (`389ecbc`). Every failure is the same step: step 6 of 27, `test_published_numbers.py`.
  GitHub skips the steps after a failed one, so **steps 7 to 27 have not run on CI since
  then.** Locally, on `f6c7c06`, all 21 of them pass (baseline above); on CI's Ubuntu and
  Python 3.12 that is not yet observed.
- **Cause:** `bench/scorecard.py` has a pre-registered floor, `PRODUCTION_MIN_ROWS = 100`
  (pinned by `tests/test_scorecard_production.py`). Below it, the scorecard row reads
  "not measured (N answers in the window, need 100)". `bench/publish_numbers.py` computes
  the production rate from `bench/production/verdicts.json` whatever the sample size, and
  its `TARGETS` entry requires a number in that row. The production window fell below the
  floor with the production bot's commit `b051254`, and the row switched from a figure to
  "not measured". No code changed that day; the seam between two components did.
- `snapshot`, `production`: green on every recent run. `deploy`: last run 2026-09-22,
  green. `usage`: last run 2026-09-22, green.

## Git activity

- 546 commits on `master` since 2026-09-03: 329 by the Owner's account, 217 by three bots
  (`vetagent-snapshot[bot]`, `vetagent-derived[bot]`, `vetagent-production[bot]`).
- The last human commit is `bc88632` (2026-09-22 04:17 UTC). Since then only bots commit:
  snapshot runs about three times a day, the production probe once a day, each followed by
  a derived-pages commit.
- Work lands directly on `master`. One pull request ever (#1, merged 2026-09-03); no open
  pull requests or issues. Branches: `master`, and `fix/p0-honeypot-liquidity`, which was
  merged in #1 and is stale.
- The repository is public (`gh repo view`: `PUBLIC`).

## Work in progress

- No uncommitted changes in the Owner's checkout (`git status --porcelain` empty).
- `TODO`/`FIXME` markers: 2, both in `tests/test_http_telemetry.py`.
- Open backlog items are listed in `docs/BACKLOG.md` (Mine: W2, W3, W27, W28, W41, W47 to
  W51, W54, W55, W57, W59 open; W4, W6, W7, W17, W37 to W40 blocked. Yours: W5 blocked,
  W10 parked, W11 and W12 open).
- **Drift on the Owner's page:** `docs/OWNER.md` lists W11 ("Answer the 2026-09-18 gate")
  as overdue, while `docs/STRATEGY.md` §8 carries a `Resolved` line added in `f962aad`
  (2026-09-19). The backlog row was never closed.

## Risk map

1. **CI is blind past step 6** (see CI). Any new failure in steps 7 to 27 would be hidden
   behind the one known red.
2. **A deploy does not wait for the full test suite.** `deploy.yml` runs on a push to
   `master` touching `src/**` and runs only `test_risk.py` and `test_mcp.py`
   (`deploy.yml` lines 64 to 68). It does not depend on the `tests` workflow, so a red
   `tests` does not block a deploy. Merging a change under `src/` is deploying it.
3. **Deploy tooling is not pinned.** `uv.lock` and `pylock.toml` are gitignored
   (`.gitignore` lines 13 and 14), `deploy.yml` runs `uv sync` (line 76) after installing uv
   with `curl ... install.sh | sh` (line 72). Two deploys of the same commit can resolve
   different versions of `workers-py`.
4. **Largest and most-changed files:** `src/risk.py` (4382 lines, 99 human commits) and
   `tests/test_risk.py` (5843 lines). The engine is well covered (706 checks), but every
   change there moves the benchmark, the published numbers and the generated pages.
5. **Generated pages make every commit a possible red.** A test added inside `test_risk.py`,
   `test_mcp.py` or `test_http_telemetry.py` moves the count embedded in
   `docs/SCORECARD.md`; a new backlog row moves `docs/OWNER.md`. The fix is to regenerate
   (`bench/scorecard.py --write`, `tools/owner.py --write`), but the trigger is easy to miss.
6. **The benchmark moves with the date** (backlog W59): it replays cached upstream answers
   against today's clock, so verdicts drift with no engine change. Engine changes must be
   compared with a same-day run of the parent commit, never with the committed results.
7. **Secrets hygiene:** a regex scan of the tracked tree (excluding snapshot data, bytecode
   cache and fixtures) for token, key and private-key shapes found no secrets; its only
   hits were token contract addresses in `bench/production/keyprobe-2026-09-14.json`.
   History was not rescanned. Deploy credentials live in GitHub secrets
   (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, referenced in `deploy.yml`).

## What the adoption itself must respect (measured in a dry run)

The lead footprint was committed in a scratch clone at `f6c7c06` and all 27 offline steps
were run against it:

- English files, no percentages: no new failure (only the baseline red remains).
  `test_rounds.py`, `test_owner_page.py` and `test_decisions_enforcement.py` stay green with
  an extra commit.
- A Chinese `lead/OWNER.md` turns `test_english_only.py` red, **even untracked**: the test
  walks the working tree with `os.walk`, not `git ls-files`.
- A percentage written as digits followed by a percent sign in a tracked `lead/*.md` turns
  `test_number_coverage.py` red ("add to LIVE_CLAIM_FILES or FROZEN_LOG_FILES").

## Unknowns

- Whether steps 7 to 27 pass on CI's Ubuntu and Python 3.12 (observed only locally, on
  Windows and Python 3.13.4). The first green CI run after the fix settles it.
- Whether the lead folder should be public; decided by the Owner at adoption.
- Business work outside the repository is not visible here and is not audited.
