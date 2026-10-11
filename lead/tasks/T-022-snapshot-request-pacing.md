---
id: T-022
title: Pace scheduled snapshot requests using the verified slower interval
status: changes_requested
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
Out: fetcher implementation except amendment (a), risk engine, benchmark files, providers, API keys, spending,
cron changes, retry/deadline changes, coverage definitions, optional probe ordering,
permission files and product thresholds. The lead preserves experiment data separately.

## Files in scope

- bench/snapshot.py
- bench/fetcher.py (only the opt-in pacing seam authorized in amendment (a))
- .github/workflows/snapshot.yml
- Acceptance tests: tests/test_sellability_archive.py (already registered; additive only)
- Lead records are maintained by the lead, outside the executor commits.

Conflict search: snapshot.main, snapshot.collect, collect(), --pages, --sellability,
Collect pools, _RATE and ArgumentParser were searched throughout tests/. Existing
main() callers and CLI helpers omit the new flag and must remain valid. The original
167 archive assertions, inputs and helper behavior remain unchanged. No named change
to an existing assertion or input is authorized. New tests/functions/imports are allowed.
The original scope shares no source or acceptance file with T-011. Amendment (a) adds
fetcher.py only after T-011's source is frozen; do not run overlapping source edits.

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

### (a) Preserve the minimum gap despite connection setup delays

Round-1 independent and red-team probes at e1e2b83 reproduce the same AC 2 defect through
the real main -> collect -> fetch_json -> throttle -> stdlib HTTP path. An eight-second
first DNS lookup or TLS setup followed by immediate setup produces HTTP send starts at
8.0, 12.1 and 24.2 seconds. The first actual gap is 4.1 seconds although the option
promises at least 12.1. The run returns 0. Rate restoration and collection budgets pass.
This is a measured seam defect; do not redefine a request start or lower AC 2.

Authorize a narrow, opt-in fetcher pacing seam for this collection scope. Conservatively
anchoring the next request's pacing to the previous attempt's completion is acceptable:
it keeps waiting outside the original ten-second whole-attempt IO budget, and guarantees
that variable DNS, connect, TLS, headers and body durations cannot shorten the gap.
Default callers, cached/replay calls, other hosts and optional probes retain their current
behavior. Temporary pacing configuration and any completion anchor are restored on all
exit paths before writing or optional work. Recovery still uses its ninety-second
monotonic deadline, twelve-call cap and original retry choices. No timeout extension,
provider change, cache change, transport rewrite or extra production probe is authorized.

Add acceptance functions/helpers only in a separate tests-only named-change commit before
the source fix. All original 252 assertions, inputs and helper ASTs remain unchanged.
Observe a behavioral red on e1e2b83 rather than an import or unknown-keyword failure.
Exercise consecutive real stdlib HTTP sends with variable DNS/TLS setup, successful and
failed attempts, retries and recovery. Include mixed setup, ten-second IO cutoffs,
remaining-deadline refusal, ordinary calls after restoration and an interrupted exit.
Use fake clocks and fake sockets only; no network, real sleeps or writes outside temp.
The complete acceptance remains under ten seconds. Deliberately bypass the new anchoring
and show that the additive tests fail; restore the exact source afterwards.

T-011's frozen e120fe5 is being reviewed separately. Do not edit that task's worktree,
cache/replay implementation or source history; integration will merge its reviewed head
and resolve only the named pacing seam, followed by the full suite. Both must retain
their independently observed red histories. Round 2 uses one combined reviewer for this
named defect, retained-budget/default-behavior regressions and original acceptance. All
settled round-1 criteria stand. Actual deployed manual and scheduled coverage gates
remain pending and cannot be replaced by the healthy branch experiment.
