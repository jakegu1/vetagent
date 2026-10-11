---
id: T-022
title: Pace scheduled snapshot requests using the verified slower interval
status: in_review
level: 3
size: S
depends_on: [T-020-source]
decisions: []
---

## Context

T-020 is published at 5bb391f and preserves observations before reporting incomplete
coverage. Actual manual run 38139242886 recorded 415 pool rows and eighteen remaining
gaps with HTTP 429 responses. That is a measured collection problem, not a quiet market.

A read-only GitHub runner experiment at dcb4b1a changed only the collector process's
GeckoTerminal request interval to 12.1 seconds. Run 38140061977 produced 672 pool rows,
forty manifest entries, thirty-seven successful pages, three observed listing ends,
forty HTTP 200 responses and zero coverage gaps. The saved manifest and pool identities
were independently counted, not inferred from the job's green status. Pool collection
took about eight minutes. Optional sellability ran afterwards and is not evidence about
pool completeness. One pass does not establish the backend cause or future availability.

Evidence: https://github.com/jakegu1/vetagent/actions/runs/38140061977.
Release base: c18de928ce0b4bc6c55fffdb0df873011793f1b8.

## Goal

Use the measured slower interval in scheduled pool collection while retaining original
recovery limits, data preservation, completeness checks and ordinary fetcher defaults.

## Scope

In: a snapshot-only CLI pacing option and its scheduled invocation; additive acceptance.
Out: fetcher implementation, risk engine, benchmark files, providers, API keys, spending,
cron changes, retry/deadline changes, coverage definitions, optional probe ordering,
permission files and product thresholds. The lead preserves experiment data separately.

## Files in scope

- bench/snapshot.py
- .github/workflows/snapshot.yml
- Acceptance tests: tests/test_sellability_archive.py (already registered; additive only)
- Lead records are maintained by the lead, outside the executor commits.

Conflict search: snapshot.main, snapshot.collect, collect(), --pages, --sellability,
Collect pools, _RATE and ArgumentParser were searched throughout tests/. Existing
main() callers and CLI helpers omit the new flag and must remain valid. The original
167 archive assertions, inputs and helper behavior remain unchanged. No named change
to an existing assertion or input is authorized. New tests/functions/imports are allowed.
This task shares no source or acceptance file with T-011.

## Acceptance criteria

1. **Validate before work.** --request-gap accepts finite numeric seconds at least 2.1.
   Unset preserves the current caller-specific default without changing it. Malformed,
   negative, zero, smaller-than-default, NaN and infinite values exit nonzero before
   fetching, creating the output directory, reading the archive or changing rate state.
   --help explains that the option applies only to pool collection.
2. **Exercise the real seam.** With --request-gap 12.1, main()'s real pool collection
   reaches fetcher.fetch_json and the real throttle against fake HTTP and a fake clock;
   consecutive GeckoTerminal starts obey that minimum gap. Test at least two requests.
   Initial and recovery requests both use the same configured host rate. Other host
   entries and ordinary fetch calls retain their previous defaults. No real network,
   sleep or production write is permitted in acceptance tests.
3. **Restore state.** The previous GeckoTerminal rate (including an absent entry) is
   restored after collection on success, incomplete coverage and exceptions. It is
   already restored before writing/probing. --check-coverage and --sellability-only
   do not alter collection pacing. Importing snapshot or omitting the option does not
   alter the shared fetcher configuration. Other host entries are never changed.
4. **Retain the guards.** The existing ninety-second recovery deadline, twelve-call cap,
   ten-second whole-attempt limit and original retry choices remain. A fake-clock
   recovery run with the slower interval still obeys those limits and reports any
   unobserved pages as gaps. Existing archive assertions remain green unchanged.
5. **Scheduled wiring.** Only the Collect pools invocation gains --request-gap 12.1.
   The four cron slots, twenty-five-minute job timeout, separate pool commit, optional
   sellability steps and final current-pass coverage failure remain unchanged. Test the
   actual workflow invocation, not just a comment containing the option. A complete
   reviewed manual run followed by an observed scheduled pass is release evidence
   maintained by the lead; neither can be replaced by an offline test or green job alone.
6. **Contract and checks.** First task commit adds only acceptance tests with an observed
   nonzero red before implementation. Original acceptance ASTs stay unchanged. Full
   python lead/checks.py passes against the thirty-step release baseline. Acceptance
   performs no real IO outside temporary directories and completes within ten seconds.

## Evidence required

- Base/head, tests-only red and fix commits, unchanged original acceptance ASTs.
- Offline CLI-to-throttle-to-fake-HTTP observations and restored state on each exit path.
- Slow-recovery fake-clock budget and coverage observations.
- Full check output and exit status, exact files changed and a clean worktree.
- Deliberately break workflow wiring, ignore the CLI interval and remove restoration;
  show additive acceptance rejects each, then restore the exact source.

## Notes and threat model

This protects irrecoverable observations. Plausible errors are a flag that never reaches
the actual throttle, a rate override leaking into optional or benchmark calls, a long
interval bypassing the recovery deadline, and a green workflow that hides incomplete
coverage. Keep the existing preservation and final-failure seam. Do not broaden HTTP
budgets to compensate for waiting. Do not claim that one healthy pass guarantees uptime.

The work costs one narrow patch, offline tests and fresh independent/red-team review;
there is no new recurring service or spending. Stop and report BLOCKED if meeting the
criteria requires changing a fetcher contract, coverage bar or existing acceptance input.

## Amendments

None.
