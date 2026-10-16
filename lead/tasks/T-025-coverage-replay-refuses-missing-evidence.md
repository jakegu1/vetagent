---
id: T-025
title: Make coverage replay refuse an incomplete recording after engine error handling
status: ready
level: 3
size: S
depends_on: [T-024]
decisions: []
backlog: none
---

## Context

tests/test_coverage_matrix.py promises its replay never invents a missing response.
The callback raises AssertionError, but risk.assess catches ordinary upstream errors,
including that assertion. Removing one requested response from the saved Ethereum fixture
still returns a result. The lead's completed isolated proof removes each of its five URLs:
search, token-pairs and RPC removals return low without an upstream-failure gap; tokens
and honeypot removals return unknown. All five report actual missing requests and still
return instead of invalidating the recording. This is a test-instrument defect, not a
claim that the production engine should fail closed on every optional endpoint.

The base is 7ec4530b76a65c7f62da266870f9e28b295f919e. Its full baseline is 33/34 solely
because the old Oct-16 gate is due. T-024 separately corrects that Owner-approved date.
This task can be reviewed against that exact known baseline; integration after T-024
must pass the complete suite. Do not borrow unreviewed date changes into this branch.

## Goal and budget

A missing recording response invalidates replay reliably, including when the engine
catches the callback's exception and returns a plausible answer. Preserve complete
recordings' existing behavior and the meaning of recorded HTTP failures.
One file, zero external calls/spend, at most two review rounds. Stop on an older-test
conflict rather than changing fixtures, scoring or the advertised coverage matrix.

## Scope and conflict search

Only tests/test_coverage_matrix.py: replay adapter, _assess handoff, and additive tests
discovered by its existing automatic test runner. No other files or new test runner.
Search _replay, _assess, references, FIXTURES, risk.cf_fetch and all coverage-matrix readers.
Named changes to existing acceptance assertions: none. Existing test function ASTs,
observers, TOKENS, fixtures, scorecard/engine code and recorded dates remain unchanged.
The source helper changes are separate from the immutable tests-first commit.

No production API, fresh recording, cache/benchmark replay, data fill, provider, permission
or public-figure change. Do not edit the real fixture to create a mutant.

## Acceptance criteria

1. A complete real recording still replays through risk.assess. All original coverage
   assertions and the same unsettled cells remain valid; no coverage score is raised.
2. Remove each of the five actually requested Ethereum fixture responses independently
   using temporary copies and fresh per-case state. Every actual miss must make _assess
   fail clearly even where the engine catches the callback exception. No result is
   accepted from an incomplete replay. Report diagnostic context sufficient to identify
   the missing request; this test uses only already-public fixture inputs, never telemetry.
3. Prove the handoff with a private fake assessment that catches the replay callback's
   ordinary exception and returns a plausible result: replay must still reject the run.
   A valid recorded HTTP error or empty body is not an unrecorded URL. Keep the old adapter's
   behavior for known recorded statuses and bytes.
4. Unknown URL/missing response, normal success and an engine exception all leave
   risk.cf_fetch at its actual previous value. No external request is made; fixtures,
   raw archive, cache and production status remain unchanged.
5. The first commit adds additive acceptance tests alone and produces meaningful failures
   on the old handoff. The implementation is a separate commit. Existing tests and automatic
   discovery are frozen. Catch and restore private mutants that remove the final refusal
   and remove miss accounting, with actual failures and no stale relevant bytecode.
6. Final acceptance passes. The complete configured runner passes or matches only the
   recorded old-date baseline; no other failure is acceptable. Provide base/head SHAs,
   immutable tests/red/final outputs, safe mutation evidence, old-case preservation and
   exact one-file scope in a signed READY report. Integration after T-024 must be all green.

## Threat model

An accidental new endpoint, truncated fixture or stale recording must not masquerade
as a successfully measured coverage cell. Ordinary engine exception handling must not
hide a test failure. Guard the callback-to-assessment seam and restoration; preserve the
distinction between an observed upstream response and an unobserved fixture entry.
