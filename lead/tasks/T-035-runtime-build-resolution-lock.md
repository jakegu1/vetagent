---
id: T-035
title: Lock the existing Node and Pyodide package resolutions before deployment
status: in_progress
level: 3
size: M
depends_on: [T-033]
decisions: [D1, D2]
backlog: Engineering inventory
---

## Context and goal

T-033 locks the host Python build environment. It does not constrain pywrangler's
`npx --yes wrangler` selection or the separately compiled `pylock.toml` consumed by
Pyodide packaging. The last successful deployment used Wrangler 4.151.1 and runtime
SDK 1.9.4. Inspection of that exact published workers-py source confirms the command
and that an existing runtime lock constrains the next compile without `--upgrade`.

Use those existing tools and public packages, with committed transitive locks and
pre-upload drift checks. Keep the engine, compatibility date/flags, Python/Node
inputs, production dependencies, providers and runtime behavior unchanged. Locking
package resolution is not a claim of bit-for-bit bundle or platform-runtime identity.

## Readiness prerequisite

Promote to ready only after T-033's actual no-secrets Linux build succeeds and its
generated runtime lock is retrieved and inspected. Confirm it selects SDK 1.9.4 and
matches the deployed source wheel. Retain the exact build run/head/hash provenance.
If it differs, preserve the observation and amend the spec before choosing a version;
do not silently promote the latest resolver result or edit a lock by guesswork.

This prerequisite is now observed: actual branch run 39101343947 at frozen T-033
source 2b03cbc038393b6ba535fd2fb3c1dc7edb4e30b2 passes its required test job and
credential-free Linux build. The public-python-runtime-lock artifact is retrieved;
its pylock.toml SHA-256 is
1d4e5ceb928c16b36ed5afd945d567e480535b1d55a677930e1969f59095ec90.
It contains only workers-runtime-sdk 1.9.4, requires Python >=3.13.2, and references
the public wheel SHA-256
2bd6f5788fd6fdd38ff677e37c93fd92b37ff3a3ab33b43b7ed84ba50688a647,
matching the separately inspected deployed SDK wheel. Artifact/run provenance is
verified separately from the file bytes. T-033's fresh source reviews and approved
integration are still required before dispatch from its integrated base.

## Scope and conflict search

- New root `package.json` and `package-lock.json`: private project, exact dev-only
  wrangler 4.151.1 and transitive integrity hashes. No application dependency or
  install script. Generate with the actual supported Node/npm on public npm registry.
- New root `pylock.toml`: the inspected actual Linux target lock, with runtime SDK
  1.9.4, public distribution URL/hash and its actual target metadata. No host-lock
  export masquerading as a Pyodide resolution, local path or private index.
- `.gitignore`: stop ignoring only pylock; preserve installed/vendor/build/secret
  exclusions and T-033's host lock tracking.
- `.github/workflows/deploy.yml` and `.github/workflows/test.yml`: add `npm ci` before
  pywrangler and verify its local Wrangler version without fetching a fallback.
  Use locked host commands for explicit pywrangler sync; assert uv.lock, pylock and
  npm lock bytes remain unchanged before real upload and after dry-run. Include the
  new lock/manifests in deploy path triggers. Preserve required offline and smoke
  gates, existing job conditions and the no-secrets build's lack of credentials.
  A fixed two-entry build matrix is allowed to prove two independent clean Linux
  checkouts without duplicating the entire offline test job. Keep the matrix bounded
  at two, retain needs: test and its workflow_run exclusion, and verify both actual
  packaging jobs. Do not share their project/vendor environments.
  Capture lock-byte hashes before installation/sync and compare them before upload
  and after dry-run; a normalized git diff alone is not a byte-preservation check.
- `tests/test_build_dependency_lock.py`: additive offline acceptance only, preserving
  every T-033 test/input/assertion. Reuse its existing registration; no new test file.
- `docs/HANDOFF.md`: directly corresponding locked setup/sync/deploy and deliberate
  lock-update instructions, with the actual scope/limits. Keep pywrangler authoritative.

Eight files. Refresh workflow and SDK command conflict searches at dispatch. First
commit only adds genuinely failing acceptance cases for the missing runtime/Node
locks and drift check. No late input/assertion edits without named amendment. Source
fix commits separate Node resolution and target-runtime resolution findings.

## Acceptance criteria

1. Actual package JSON/TOML parses, selects exactly the verified versions, has public
   registry URLs and integrity hashes, and contains no project publish/install hook,
   local credential/path or newly added runtime dependency. Missing locks, a floating
   direct version or a missing distribution hash fail meaningful offline acceptance.
2. On the actual Linux runner, `npm ci` supplies the local pinned binary and a
   no-install version check confirms Wrangler 4.151.1. pywrangler resolves that local
   package. A cold second install preserves both npm and Python lock bytes; no
   unqualified installer is substituted for npm ci.
3. Explicit locked-host pywrangler sync runs before production upload. A drift in any
   committed lock fails before upload, not afterward. The deploy command remains
   locked-host pywrangler deploy; the branch build remains pywrangler dry-run. No
   `--upgrade`, credential bypass, engine rewrite or direct bare-wrangler deployment.
   Compare actual bytes, including a newline-only drift control. Take the checksum
   baseline before installation/sync, so a preparatory rewrite cannot become the
   accepted baseline. Retain the existing tracked-file diff as a separate guard.
4. Actual target sync installs SDK 1.9.4 from the inspected public distribution.
   Existing pylock constrains resolution and remains byte-identical through two clean
   Linux checkouts' sync/dry-run sequences. Record tool and selected runtime-package
   versions and hashes. A changing lock is investigated, never silently reset in CI.
5. Synthetic controls deleting a lock, floating Wrangler, removing npm ci, bypassing
   local binary verification, removing the pre-upload drift guard and enabling runtime
   upgrade each make the new acceptance red. Old host-lock tests stay unchanged.
6. Full configured checks and compile pass; affected tests run on actual Python 3.12
   and 3.13. Fresh independent and adversarial reviews verify lock provenance,
   reachable commands, negative controls and unchanged production source. The lead
   requires real branch Linux build before the authorized production deploy, then
   actual import/smoke checks and following bot CI.

## Threat model, evidence and limits

Prevent host locking from being misrepresented as locking a separate target package
resolution, or a post-upload diff from being called a deployment guard. Installed
packages and generated bundles remain ignored. Retain actual CI logs and the
distribution/lock provenance privately; no raw provider data, secrets or local paths
in shared files. Do not run a benchmark or change published measurements.

The SDK can download platform interpreters selected by its existing compatibility
configuration. This task freezes the selected tool/package resolutions; it does not
pin the hosted runner's OS image or claim a reproducible platform runtime. The
separate action/runner task addresses the former. If the supported SDK cannot enforce
the stated unchanged target lock before upload, report that exact constraint and
propose a bounded amendment before bypassing its packaging path.

## Amendments

The actual T-033 Linux artifact satisfies the runtime-lock readiness prerequisite.
This task is ready but waits for T-033's fresh reviews and approved integration.
