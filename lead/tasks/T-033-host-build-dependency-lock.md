---
id: T-033
title: Lock host Python build dependencies and verify credential-free Linux builds
status: in_progress
level: 3
size: M
depends_on: [T-032]
decisions: [D1, D2]
backlog: Engineering inventory
---

## Context and goal

The deploy installs an unversioned uv installer and resolves unversioned development
SDK requirements on each clean runner. `uv.lock` is explicitly ignored. The last
successful deployed toolchain used uv 0.13.1, workers-py 1.17.8 and
workers-runtime-sdk 1.9.4. Published wheel metadata and the actual deploy log were
checked, rather than assuming that local ignored artifacts represented a lock.

Lock this host-Python resolution without changing the Worker engine, Python target,
compatibility date, Node input or provider. Add an actual credential-free Linux
pywrangler build on branches so packaging can fail before production promotion.
The separate Node/Pyodide resolution is explicitly outside this first task; do not
describe the whole build as reproducible until that following task is verified.

## Scope and conflict search

- `pyproject.toml`: pin only the two existing development SDK requirements to the
  deployed versions above. Keep production dependencies and project metadata.
- `.gitignore`: stop ignoring only `uv.lock`; keep virtual environments, installed
  packages, vendor/build output, pylock and all secret exclusions unchanged.
- `uv.lock`: generate with uv 0.13.1 against public PyPI, including transitive
  versions and distribution hashes. No local paths, credentials or private index.
- `.github/workflows/deploy.yml`: pin uv installation to version 0.13.1, run
  `uv sync --locked` and `uv run --locked pywrangler deploy`, and add uv.lock to
  deploy path triggers. Preserve credentials, offline-before-deploy and smoke gates.
  A versioned binary Python uv package is acceptable; an unversioned installer is not.
- `.github/workflows/test.yml`: one new offline test registration; a separate
  credential-free Linux `build` job using the existing full-history checkout,
  Python 3.12 and Node 22, the same uv pin and locked sync/run, and
  `pywrangler deploy --dry-run`. It must not upload a version or call production.
  Preserve all existing jobs and their conditions. Build runs on branch pushes.
  Retain the generated public-package `pylock.toml` as a build artifact for the
  following runtime-lock task; do not upload installed packages, secrets or probes.
- `tests/test_build_dependency_lock.py`: new offline acceptance guard and synthetic
  negative controls. It must not install packages or access network.
- `docs/HANDOFF.md`: only the directly corresponding host setup/deploy commands and
  lock update instructions. Keep the D1 pywrangler-only rule explicit in commands.

Seven source/document files. Refresh conflict search against the actual dispatch
base, especially test_deploy_gate and offline_suite. No existing test inputs or
assertions change. No action-major or runner-image migration in this task. No npm
or runtime lock, Worker compatibility flag, dependency addition, benchmark or raw
measurement changes. The lead owns metadata and generated pages.

## Acceptance criteria

1. The first commit adds only the new tests and demonstrates the actual unpinned
   parent fails. Freeze new test inputs/assertions after that commit. Use separate
   source commits for host dependency locking and credential-free build coverage,
   each with its meaningful observed red stated in the commit message.
2. The actual TOML files are parsed with stdlib tomllib. Both direct requirements
   have exact deployed pins; the committed uv lock contains them and resolves their
   transitive host dependencies to versions and hashed public distributions. A
   missing lock, ignored lock, missing/mismatched direct SDK or unhashed resolved
   external distribution is refused with an actionable message. Delegate resolver
   semantics to actual uv; do not invent a second general dependency resolver.
3. All host sync/run commands in the actual deploy and new build job use the pinned
   uv and `--locked`. A stale/missing lock must error, not silently regenerate.
   Mutation controls for dropping the lock, removing a direct pin, dropping
   `--locked` and returning to an unversioned uv installation turn the guard red.
4. Run actual uv 0.13.1 `lock --check` and `sync --locked` in a clean isolated host
   environment. Record selected versions. Keep the committed lock bytes unchanged
   after repeat checks and sync. Do not run Pyodide setup on Windows or reuse a
   platform-specific virtual environment across runtimes/worktrees.
5. The separate Linux build has no secrets environment or credentials condition,
   and a real branch CI run executes locked sync and pywrangler dry-run successfully.
   Its success is packaging evidence only; actual deploy and runtime smoke remain
   required. Any no-secrets dry-run unexpectedly requesting credentials, uploading
   or modifying tracked files is a failure to repair, not a skipped passing build.
6. Existing deploy offline-list/condition/history and bot commit tests pass with
   unchanged assertions. One new required offline registration increases the actual
   suite count by one. The full configured suite, compile check and acceptance
   contract pass; affected offline tests run on actual Python 3.12 and 3.13.
7. Fresh independent and adversarial reviews verify actual lock contents, the
   negative controls and workflow command ordering. The lead performs branch Linux
   preflight before the approved production push, then verifies actual deployment,
   runtime import/smoke and subsequent bot checks. No production claims from dry-run.

## Evidence and threat model

Retain commands, actual versions, parent red, selected-version output, lock hashes,
clean status and fixed negative-control outcomes privately. Shared reports contain
only safe aggregate evidence and immutable source references, never local paths or
credentials. Protect existing work before any mutant. Test both Python versions
without runtime-dependent AST dump constants.

Protect against a clean runner silently picking new host SDK/transitive versions,
and a credentials-skipped workflow being mistaken for build validation. Keep the
existing authoritative pywrangler packaging and production smoke path. This adds no
paid service, new runtime provider or legal policy. A broader dependency upgrade or
an unexplained changed runtime requires a separate finding/spec.

## Stop rule and amendments

If the deployed SDK versions cannot resolve or build on the actual supported Linux
runner, preserve the failing evidence and report the exact constraint before
substituting a new version. No silent upgrade and no changing the engine to satisfy
packaging.

### Amendment (a): overlap implementation with frozen-prerequisite review

Implementation may start in an isolated branch from T-032's frozen source after
its executor's complete ordinary/denied gates and frozen-acceptance proof pass.
T-032 no longer writes the shared workflow at that point. This permits useful host
build work while its fresh reviews finish. T-032's approval remains a hard integration
and release dependency; do not integrate or publish the dependent build changes if
the prerequisite is bounced. Reconcile any later prerequisite correction by merge,
never by rewriting the tests-first history. Record the exact dispatch base and this
amendment before the first T-033 acceptance commit. No test or review bar changes.
