---
id: T-036
title: Pin supported Node 24 actions and the verified Ubuntu runner generation
status: in_progress
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
deploy.yml, production.yml, snapshot.yml, test.yml, usage.yml and zone-check.yml.
Use full commit SHAs with release comments and explicit ubuntu-24.04. The seventh
file is new `tests/test_workflow_runtime_pins.py`, registered exactly once.

The permanent new test guards action identities/pins, runner labels and the covered
workflow set. Prove the unchanged remaining workflow semantics against the dispatch
base in independent structural evidence. Do not embed a hash of every unrelated
workflow command/key into the permanent pin test: deliberate later task changes
must still be possible without weakening the action/runner checks. Existing guards
continue to own deployment order, offline inventory and bot behavior.

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

Actual T-033 source run 39101343947 and corrected T-035 source run 39106159784
satisfy the Linux-evidence readiness requirement. The latter executes two independent
clean Ubuntu 24.04 builds at 52363a3 with local Wrangler 4.151.1, successful stock
target sync, before/after byte checks and downloaded runtime-lock artifacts matching
the inspected target file. The lead binds both job/artifact/source records separately.
This is packaging evidence, not production promotion or a standalone installed-SDK
metadata readback. Dispatch still waits for T-035's fresh reviews, approved integration
and complete integrated gate. No T-036 implementation has started.

The actual sixth workflow is zone-check.yml; the draft's zone.yml was a scope-name
typo. The corrected scope is still exactly six existing workflows and one new test.

Both fresh T-035 reviews now approve its exact source, retained in merge f8ee485.
The successful scheduled snapshot and following bot CI are retained before that
merge. Actual generation completes and the uninterrupted combined gate passes
38/38 in 138.8 seconds at 2026-10-18 07:42 UTC. A prior overlapping generation/check
attempt remains excluded despite its actual zero exit. Dispatch uses the lead's
subsequent clean bookkeeping head, not either old preparation source.

Fresh exact official metadata for all four pins and their node24 declarations was
reverified with sixteen bounded GETs. A read-only same-interpreter compatibility
probe finds no required edit to existing assertions or fixtures. The new permanent
pin test must remain limited to workflow set, action identity and runner policy.

### Named amendment (a): account for refused step syntax

Before branch publication, the fresh adversarial reviewer reproduces a coverage
gap in the frozen policy at c37fd41 and 93fc49a. A single-quoted or double-quoted
uses key, a flow-map action step, or an unclosed quoted key is recorded in the
existing step reader's refused list, with no enumerated uses value. The new policy
skips that step and reports no error. The lead independently reproduces all four
shapes at the exact frozen candidate. This is a validator coverage failure, not
an observed production incident or a claim that GitHub accepts every malformed form.

Permit only the following additional changes to the new acceptance file:

1. A separate tests-only commit adds one named regression function and any solely
   new fixtures it needs for the four refused-step shapes above. Preserve every
   original test function, fixture, input and assertion from c37fd41. Run it red
   on the frozen helper on both actual Python versions before the fix.
2. A subsequent named test-fix commit may change only workflow_errors to reject
   the existing reader's refused-step evidence before deciding that an absent
   uses key means a run-only step. Do not change that reader, its old tests, any
   original assertion, any action/runner policy constant or any workflow source.
3. Keep known-valid workflows, actual six-file source and future ordinary added
   steps/soft-fail removal accepted. No command hashes, whole-workflow freezing,
   general YAML parser, new dependency or permission change is authorized.

Freeze the additive regression after its tests-only commit. Prove all other new
definitions and original acceptance inputs exact, and demonstrate a removed-refusal
mutant red. Preserve the original full-run results as old-candidate evidence only;
run the complete ordinary and inherited-denied inventories again on the corrected
frozen source, sequentially. Publication remains blocked until a bounded fresh
combined final review approves the corrected source; actual Linux/build/deploy and
observer evidence remain subsequent release gates. This is the second review round.
