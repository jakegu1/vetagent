---
id: T-029
title: Detect stale or incomplete snapshot evidence after observations are preserved
status: done
level: 3
size: M
depends_on: [T-020, T-022]
decisions: []
backlog: none
---

## Context and goal

The existing coverage command checks the latest manifest's coverage, not its age.
A complete old pass still passes when collection stops. Add an offline freshness and
latest-pass health monitor to the existing daily production observer after preservation.
This protects the archive's calendar-time value without changing collection cadence.

## Budget and scope

No spending, new provider/API traffic, schedule, sampling, recovery, score or archive edit.
Files in scope: bench/snapshot_health.py (new read-only monitor),
tests/test_sellability_archive.py (additive acceptance helpers/functions/imports only),
.github/workflows/production.yml (one monitor step after existing commit/generation).
No other source file, test, workflow, fixture, dependency or permission change.
The existing archive runner discovers test_ functions, so no test.yml change is needed.
Use private temporary archives for tests; preserve all old tests/inputs/discovery ASTs.

## Operational policy

Default maximum age is twelve hours: two nominal six-hour intervals, allowing the
already observed scheduler delays. This is an operational alarm, not a new maturity,
accuracy, demand or gate threshold. Four daily cron entries stay unchanged. Counts are
observed passes, including manual passes, never proof of four scheduled triggers.
This observer has GitHub's scheduler in common with collection, not independent uptime.

## Acceptance criteria

1. A pure report function and CLI read the archive without network or writes. The CLI
   accepts --archive-dir for private evidence and --max-age-hours (default 12), validating
   a finite positive duration. Use timezone-aware UTC now by default, with a pure-function
   clock argument for tests. Emit a machine-readable object with checked_at, status,
   latest_seen_at, latest_age_hours, observed_passes_24h, complete_passes_24h and current
   coverage/causes. No pool addresses, identities, request URLs or secrets in output.
2. Group manifests by actual observation instant. The newest pass controls health,
   using the existing snapshot._coverage semantics. A newer incomplete pass must win
   over an older complete pass; a truncated/malformed current manifest must not fall
   back to older good evidence. Missing/unreadable/malformed input or future evidence
   is unobserved, with unavailable measurements null rather than invented zero.
3. A complete pass aged exactly twelve hours is healthy; older is stale. Incomplete
   current coverage is incomplete. Healthy exits 0; stale/incomplete exits nonzero;
   unobserved exits a distinct nonzero code. No old complete pass, date-only filename,
   future timestamp, naive datetime, nonfinite age option or empty directory can claim
   current health. A valid observed empty 24-hour window may have zero pass counts.
4. Count distinct observed and complete passes in the inclusive last 24-hour window,
   preserving zero versus unavailable. Equivalent timestamps with different offsets
   represent one pass. Preserve all actual failure/coverage outcomes and the difference
   between listing exhaustion and fetch failure. Do not inspect or change pool files.
5. production.yml adds Check snapshot freshness and coverage after both existing
   observation Commit and Regenerate steps, with if: always() and a hard failure signal;
   it calls this monitor with the twelve-hour policy. Existing observation commands,
   commits, credentials, generator order and bot identity remain byte-for-byte intact.
   No continue-on-error or swallowed exit on the monitor. Pin ordering/condition in the
   added acceptance tests so an optional check cannot discard collected observations.
6. First commit contains acceptance additions alone, with controlled non-import red
   evidence for the absent monitor and unwired check. Freeze all tests afterwards.
   Prove stale-to-healthy, choose-old-good and swallowed-parse-failure mutants fail.
   New acceptance/control/mutation work blocks network and uses private archives.
   Full python lead/checks.py matches or improves the green 35-step baseline; disclose
   its old Ethereum RPC dependency. Signed READY includes exact SHA, contract, red,
   final, safe mutants, immutable old ASTs and three-file scope. No merge or push.

## Conflict search and threat model

Searched snapshot coverage/freshness/manifest symbols, archive runner discovery,
production workflow steps and tests/test_bot_commits_stay_green.py. No old acceptance
change is allowed. Reuse coverage, not a second looser definition of complete. A stale
green result and a newer failed pass are the target failures; unavailable evidence must
not become zero observations or healthy. The check runs after preservation, even if an
earlier observer step failed. No new public accuracy claim or live engine traffic.
Require fresh independent and adversarial review, with the project's two-round cap.

## Amendments

### 2026-10-18 round 1: preserve legacy history without masking current health

The real default archive contains timestamped legacy manifests without the modern pages
field. Independently reproduced: an old legacy pass makes the report unobserved even
beside a complete recent pass; removing only that old control restores healthy. The
latest committed pass itself has valid modern coverage. No historical data is corrupt
merely because it predates the current coverage schema.

The report's coverage scope is the latest pass and the inclusive last 24 hours. Parse
all input and validate/normalize all timestamps as before; malformed JSON, unreadable
input, missing/naive timestamps and future evidence must still fail closed. Apply the
existing _coverage validation only to passes in that scope. An invalid latest pass or
an invalid pass within the 24-hour counts stays unobserved, even if an older good pass
exists. If the only/latest pass is legacy, it is also unobserved. No relaxed _coverage,
archive rewrite, invented historic completeness, filename-only age filter or fallback.

When older passes are deliberately outside coverage evaluation, disclose their distinct
count in an optional older_passes_not_checked field (present only when positive), and
explain the scope in the module/CLI documentation. Ordinary report shapes stay intact.

Named additive acceptance changes only: add
test_snapshot_health_legacy_history_does_not_mask_current_pass and
test_snapshot_health_relevant_legacy_or_invalid_evidence_stays_unobserved to
tests/test_sellability_archive.py. Preserve every first-round node and input unchanged.
Commit these tests alone as T-029: named change (legacy archive compatibility), observe
red on the frozen source, then fix only the monitor in a separate finding commit.
Include actual default-archive CLI evidence at a fixed clock based on its latest pass,
plus unchanged archive hashes and a caught reintroduced-global-validation mutant.
Re-run the configured gate on the final clean head. Round 2 is one fresh combined
independent/adversarial review of this bar and regressions; no unrelated new fronts.
