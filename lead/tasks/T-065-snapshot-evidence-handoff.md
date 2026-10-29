---
id: T-065
title: Preserve writable snapshot pages and truthful confirmation availability
status: done
level: 3
size: M
depends_on: [T-061, T-062, T-063, T-064]
backlog: W7 prospective input evidence integrity
---

## Context, benefit, cost and stop

The previous related source batch is published at bdd6e69. Its normal scheduled
producer-to-reader trial qualified; it did not establish full engine replay.
New fully offline collector-to-writer-to-reader witnesses expose two additional
seams. A recovered lower empty page changes higher failed/skipped pages into
past_end_of_listing, but the reader can use an earlier failed fetch timestamp
for that later conclusion. Separately, accepted native fields can serialize as
non-finite JSON or fail UTF-8 encoding before the coverage manifest is written.
Neither witness proves an incident in the historical archive.

Benefit: keep future snapshot evidence readable and prevent hindsight in the
as-of availability census. Cost: one bounded related batch, two finding-specific
fix commits after one tests-only contract, fresh functional/adversarial reviews,
and the existing complete publication gates. Stop after these two seams and
their real offline handoffs. Do not create an engine-input validator, new study,
new collector, archive migration or general diagnostic framework.

## Scope and files

- bench/snapshot.py: preserve the actual confirmed-end observation time and
  validate complete prospective pool rows at the existing page acceptance boundary.
- bench/snapshot_readiness.py: use confirmation availability for past-end rows.
- tests/test_sellability_archive.py: additive functions only; its existing auto
  discovery already invokes new test_ functions. No workflow/runner change.

Lead-owned task/index/state/review metadata is separate. Historical archives,
scientific executed sources/evidence, src/, fetcher.py, workflows, dependencies,
permissions, public claims, decision rules and T047/T049/T050 remain out of scope.

## Conflict search

Search covered collect, _fetch_pool_page, _row, _observation_time, _coverage,
_check_coverage, _last_pass, past_end_of_listing, confirmed_end_page,
recovery_fetched_at, invalid_payload, malformed_rows and field_presence across
the existing tests and consumers. Existing recovery tests assert page/outcome,
not the entire metadata key set. Existing exact quote-field projection tests
concern otherwise writable pages and must remain byte/AST exact. Readiness
field_presence stays unchanged: the new proof time is not a census expansion.
Named changes to old tests: NONE. Unexpected old-test conflict means BLOCKED.

## Acceptance criteria

1. A future past_end_of_listing record retains confirmed_end_page and adds
   confirmed_end_fetched_at, copied from the actual lower page end-of-listing
   fetch observation. Both initial and recovered end proofs use their existing
   clock; no new clock read, request, retry, sleep, budget or sampling policy.
   Preserve every prior field, initial diagnostics, outcomes and row counts.
   Do not pretend the higher page was fetched or set recovery_fetched_at on it.
2. For runs with outcome=past_end_of_listing, the reader uses only a strict
   confirmed_end_fetched_at and a structurally valid confirmed_end_page below
   the positive integer page. Booleans are not page numbers. Missing/invalid
   proof metadata stays unknown even if fetched_at or recovery_fetched_at is
   present. Do not reconstruct or rewrite old proof times. Other row kinds and
   ordinary actual recovery_fetched_at semantics remain unchanged.
3. Exercise actual collect/main/write/read/CLI with fake HTTP and clocks: two
   initial failed pages followed by a recovered empty first page, including a
   skipped later page. Before confirmation, neither derived final conclusion is
   eligible; at the exact confirmation instant both are eligible. Cover a
   second listing/chain with its distinct proof clock, equivalent offsets,
   missing/naive/malformed clocks, wrong types and legacy rows. Preserve all
   three false replay/full-input/independent-outcome flags and bounded output.
4. Before a page is accepted, all generated pool rows must be serializable as
   finite JSON and encodable in UTF-8 using the actual writer policy. A page
   containing an unrepresentable old native field is invalid_payload, never an
   accepted observation or listing end. Reuse the existing bounded recovery
   and explicit failure-manifest paths. No null substitution or normalization
   of old fields, no raw content/URL/exception in diagnostics. Existing bounded
   optional quote capture remains unchanged. Well-formed rows remain exact.
5. Exercise real parsed JSON with an overflowing numeric exponent, escaped lone
   surrogate and nested non-finite native fields, then the real main writer.
   Preserve valid earlier/later pages and their original fields, retain an
   explicit failed-page manifest, return incomplete coverage, and produce only
   strict readable NDJSON. Include a bad page with a valid neighbor: atomic
   page rejection is explicit, never complete coverage. Valid Unicode, finite
   zero/null values and ordinary listings retain old fetch traces and raw
   values. Historical files are unchanged. No network or assessment occurs.
6. Tests are committed first and fail on the original source for the intended
   two defects. Keep one runtime fix commit per finding, recording the observed
   red in each message. Every old test/helper remains unchanged. Author and
   fresh reviewer run the actual complete runner with isolated non-Git TEMP;
   tracked raw bytes must stay exact. Fresh functional and adversarial reviews
   must pass. Kill at least one clock-fallback mutant and one removed-page-
   validation mutant with the additive tests. Normal integration, generation,
   full checks, actual source CI/builds and publication follow existing gates.

## Threat model and evidence

Accidental upstream JSON values and ordinary delayed recovery must not turn an
unobserved fact into an available one, poison the NDJSON stream, or lose the
coverage manifest. Page-atomic rejection follows the existing malformed-page
contract; it is a visible gap, not reduced coverage claimed as complete. Record
only fixed diagnostic categories and aggregate proof counts. Keep prior files
and old failed receipts unchanged. No blocked security investigation is replayed.

READY evidence: exact base/tests/fix/head identities, meaningful red results,
valid and invalid collector-to-reader traces, CLI/source preservation, all AC
evidence, complete runner receipt and contract verification. Independent review
produces its own evidence and scores the existing rubric. Do not infer actual
historical prevalence, production success or replay readiness from these tests.

## Amendments

### A1 - 2026-10-29: preserve the runs-only fixture's absent-kind diagnostic

The first tests-only contract95b8029 has one incorrect expected diagnostic list
in test_snapshot_end_confirmation_strict_proof_metadata_and_legacy_rows. Its
fixture intentionally contains only runs, so the unchanged inventory correctly
reports source_kind_absent as well as unknown_observation_time. Permit exactly
one named test change: replace the expected list[unknown_observation_time] with
the exact ordered list[unknown_observation_time, source_kind_absent]. Preserve
all inputs, row/count assertions, other assertions and all old tests. Commit
this separately as T-065: named change (runs-only absent-kind expectation).
The original red remains retained. This corrects the new test's premise; it
does not weaken a runtime guard or authorize any other test change.
