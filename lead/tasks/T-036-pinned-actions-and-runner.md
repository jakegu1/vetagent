---
id: T-036
title: Pin supported Node 24 actions and the verified Ubuntu runner generation
status: draft
level: 3
size: M
depends_on: [T-033, T-035]
decisions: [D2]
backlog: Engineering inventory
---

## Context and goal

The six workflows still use first-party actions implemented on retired Node 20 and
float on ubuntu-latest. Official GitHub notices say Node 20 is removed and the latest
image starts moving to Ubuntu 26.04 on Oct 19. Actual preflight 39097068303 ran on
ubuntu-24.04. Pin that currently verified OS generation while upgrading the action
implementations to their verified stable Node 24 releases. This avoids an untested
OS migration during dependency/release hardening; it does not imply Ubuntu 26 fails.

The JavaScript action runtime differs from the project's Node 22 build input.
Preserve that input, Python 3.12, locked package versions and Worker compatibility.

## Verified inputs and readiness

Read-only official release and commit-object metadata captured Oct 18 confirms:

| Action | Stable release | Commit |
|---|---|---|
| actions/checkout | v7.0.1 | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| actions/setup-python | v7.0.0 | 5fda3b95a4ea91299a34e894583c3862153e4b97 |
| actions/setup-node | v7.1.0 | 949feb2413d6458794dcd2491c4babbbce0c15c1 |
| actions/upload-artifact | v7.0.2 | cf430e030ddbb5b0abf93d22962f4752f3646cd9 |

Their action.yml runtime declarations all specify node24. Reverify exact source
metadata at dispatch; do not replace a pin with latest based on a package name.
Promote after both preceding package-lock tasks have actual Linux build evidence.

Primary references:
- https://github.blog/changelog/2026-09-23-node-20-is-no-longer-available-in-github-actions/
- https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/
- https://github.com/actions/runner-images/issues/14748

## Scope and tests-first contract

All six existing workflow YAML files, limited to their `uses` action references and
`runs-on` labels, plus the new offline acceptance registration in test.yml:
deploy.yml, production.yml, snapshot.yml, test.yml, usage.yml and zone.yml.
Use full commit SHAs with release comments and explicit ubuntu-24.04. The seventh
file is new `tests/test_workflow_runtime_pins.py`, registered exactly once.

First commit adds only new offline acceptance, runs red against the floating/old
actual workflow set and freezes its cases/assertions. Keep all existing tests and
synthetic action-version examples unchanged. Source commits separate Node 24 action
pins and runner-image pins. No other YAML key/value, trigger, cadence, permission,
secret, timeout, checkout depth, continue-on-error, artifact path, script or package
version changes. The lead owns metadata, generated pages and publication.

## Acceptance criteria

1. Every actual first-party action reference in all six files matches the verified
   full SHA and has no moving major/latest tag. Each job, including the no-secrets
   build and optional jobs, has explicit ubuntu-24.04. Test the actual set of workflow
   files, so adding a new unguarded workflow fails until intentionally covered.
2. Offline synthetic controls for one old action pin, a moving major tag, one
   ubuntu-latest label, a missing job pin and a hidden extra workflow each fail.
   Known valid action/runner forms pass. Do not scan or mutate raw snapshot data.
3. The workflow diff contains only the permitted action/runner changes and one new
   required registration. Job semantics, scheduler cadence, upload inputs, history
   depth and all conditions remain structurally unchanged. Existing deployment,
   offline parser and bot-push guards pass without altered assertions.
4. Complete configured checks, compile and the tests-first contract pass; affected
   tests run on actual Python 3.12 and 3.13. The ordinary suite adds exactly one
   required step. Fresh independent and adversarial reviews verify pins, mutation
   controls and unchanged workflow semantics before branch publication.
5. An actual exact-head branch Linux run executes the entire required suite and
   locked no-secrets Worker build on the pinned runner with the new actions. Artifact
   upload/download succeeds. A missing credential deployment skip is not evidence.
6. After the authorized promotion, actual deploy executes Worker upload and smoke.
   Trigger the existing production observer and verify preservation, generation and
   snapshot health in order; retain its bot commits and verify following bot CI.
   This exercises checkout credentials and artifact behavior across the action major
   upgrade, rather than relying only on static workflow tests.

## Threat model, evidence and stop rule

Protect against retired action runtimes, moving tags and an unobserved OS change,
while preserving the release gates, bot identity and existing auth scope. Retain
official source metadata, exact before/after workflow semantics, negative controls,
actual run/step results and source head. Never print credentials or private identifiers.

If an action major breaks an existing documented input or bot push, preserve the
actual failure and propose a named bounded amendment. Do not weaken a gate, increase
permissions, bypass credentials or silently fall back to a floating reference.
Ubuntu 26 validation is a separate deliberate future upgrade, not a prerequisite
for stabilizing today's measured supported image.

## Amendments

None; prerequisite evidence is pending, so this task is not dispatched.
