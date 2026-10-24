---
id: T-063
title: Preserve and inventory native pool fields across the snapshot handoff
status: in_progress
level: 3
size: M
depends_on: [T-061, T-062]
backlog: W7 input evidence preparation
---

## Context, benefit, cost and stop

The real pool writer stores the upstream volume and transaction dictionaries as
volume and tx. The readiness inventory currently selects volume_usd and
transactions, so its literal-key census omits the stored native dictionaries.
An offline actual-producer-to-reader fixture reproduces the omission. Timestamp
eligibility is a separate calculation and is not implicated by that witness.

The same writer retains base_token_price_quote_token as price_quote but discards
quote_token_price_usd. Two otherwise identical synthetic responses with distinct
quote prices become identical archive rows, although the unchanged engine's
_gt_base_price uses those values when its primary price is missing. This proves
prospective information loss, not a historical verdict defect. Existing archive
readings and their limitations stay private; no historical value is invented.

This related batch repairs the producer-to-inventory seam with two small source
findings and two tests-first fix commits. It protects already acquired fields
without a new request, upstream, score or scientific policy. Stop if the work
needs a frozen scientific file, fetch adapter, workflow, risk-engine change,
historical archive rewrite or new diagnostic framework. The lead resolves any
scope expansion before it is implemented.

## Source and authorization boundary

Base source a6cd369 passes the actual integrated complete45 gate. T061/T062 have
their required source reviews; actual source Linux/build/publication remains
queued. The active study's executed source and five controls/import closure
remain immutable. This task is wholly outside that closure.

The Owner authorizes the related technical continuation. No push or real-source
CI occurs while the current study is active or before its qualified original
report, complete preservation and owned stop. The latest release order also
requires the separately specified post-window diagnostic repair before source
publication and the first normal scheduled snapshot trial. This task alone
does not satisfy those later gates or start another research run.

## Files in scope

- bench/snapshot_readiness.py: extend only the literal pool-field inventory and
  its explanation, preserving existing keys and all other reader behavior.
- bench/snapshot.py: _row retains the additional raw quote_token_price_usd field;
  no fetch, selection, transformation, schema-version or other field change.
- tests/test_sellability_archive.py: additive registered acceptance functions
  and only their explicit invocation in main. Preserve every old function,
  helper, assertion and existing invocation unchanged.

The lead owns task/index/state/review metadata separately. Do not edit src/,
fetcher.py, workflow files, the five active-study sources, any actual archive,
permission files or earlier sealed evidence.

## Conflict search and named changes

Actual searches cover _row, _fetch_pool_page, field_presence, FIELDS, schema,
volume_usd, transactions, volume, tx, price_quote and quote_token_price_usd.
The existing well-formed pool test does not forbid additional raw fields.
The strict T062 prior-field projection and schema assertions concern sellability
rows; these must remain exact. Readiness fixes only top-level output schema in
the existing privacy test; no existing test pins the entire pool-field key set.

No old test or expectation is authorized to change. Keep old upstream-spelling
inventory keys as independent literal-key counts; do not silently remove them or
populate them by alias. New native fields are additive. If an unexpected existing
contract actually conflicts, return the concrete red to the lead first.

## Acceptance criteria

1. Inventory the actual native pool keys volume and tx, and the complementary
   price_quote and quote_token_price_usd keys. Retain all existing field_presence
   keys as independent literal counts. Match exact membership in each parsed
   row, including null, zero, false and empty containers; absence is not presence.
   Preserve the existing all-parsed-rows scope, including future/unknown-time
   rows. Do not turn key presence into non-null, numeric validity, as-of eligible
   field coverage, engine usability or replay readiness.
2. Reproduce the real writer-to-NDJSON-to-inventory seam. A fake successful
   _fetch_pool_page produces the actual _row fields and real response clock;
   write its rows through the existing writer, then inventory the exact bytes.
   Native volume/tx presence must appear at file and kind levels. Upstream-only
   spellings in a separate fixture never create native presence by alias.
   Include absent/null/malformed-valued keys and valid/future/unknown clocks.
   Existing row/time totals, reasons, bounds and source bytes remain unchanged.
3. The pool writer prospectively retains quote_token_price_usd exactly as
   returned, including missing-as-null and malformed JSON values. Every existing
   raw field and value, price_usd, price_quote and schema=2 remain unchanged.
   No computed replacement price is written, and no old archive row is edited.
4. Two otherwise identical fake responses with primary base price absent,
   price_quote=2 and quote prices3/5 remain distinguishable after real write/read.
   Map only these saved raw inputs back to the unchanged pure _gt_base_price
   seam and reproduce6/10. Preserve the original None/empty/zero/invalid-price
   behavior; this is an input-preservation witness, not a full historical engine
   replay or observed token verdict. New and legacy/null rows retain honest
   literal field counts and unknown/full-input flags.
5. The actual collector/writer/reader/CLI handoff uses fake HTTP and isolated
   temporary output only. Prove unchanged fetch URL/kwargs/order/count, retries,
   cache behavior, raw old-field projection and row retention. The real CLI
   emits only fixed aggregate keys/counts, never fixture identity/value/URL/path
   or arbitrary exception text. Preserve strict clocks, source-stability/size/
   symlink guards, all current limits, timing semantics and all three false
   replay/independence/full-engine flags. Kill one omitted-native-field mutant
   and one discarded-quote-value mutant, then restore verified source bytes.
6. Keep two clear tests-first finding histories: first additive native-inventory
   acceptance alone, meaningful parent red, minimal field-inventory fix; then
   additive quote-preservation acceptance alone, meaningful parent red, minimal
   raw-field fix. Each fix message states its observed red. Old acceptance and
   hand-written runner invocations remain exact except adding the named new
   functions. The lead contract checker, focused runner and syntax checks pass.
7. Fresh independent functional and focused adversarial reviews approve the
   exact final source with no material finding. Author and independent actual
   complete45 gates, then related-batch integrated complete45, must pass with
   unchanged source bytes and real CI flags. Serialize heavy Windows runs and
   use a verified non-Git temporary root. Recheck the frozen five/import closure,
   old raw archive bytes and protected primary. Real source Linux/two locked
   builds/master publication/normal-snapshot trial remain later required gates;
   do not push, trigger a workflow or make a Vendor/production request here.

## Threat model and READY evidence

Threats: a mock uses the reader's imagined spelling rather than the real writer;
aliases fabricate an unrecorded value; null/presence becomes a usable feature;
retaining a quote replaces the primary or changes engine scoring; a seam test
skips the actual serializer; real requests contaminate the active study; raw
values leak into diagnostics; a new key quietly drops prior information.

Provide both tests-only/fix SHAs and parent reds, old-definition byte/AST proof,
actual producer/writer/reader/CLI fake-network witness, exact output source
hashes, mutant failures/restoration, focused/contract/native complete45 receipts,
and independent exact-source verdicts. Existing actual archive measurements
remain private and dated; do not claim that existing historical verdicts changed.

## Amendments

### A1: register the second tests-only addition before dispatching it

The kit's contract checker treats any edit to an already changed acceptance file
after its first tests-only commit as a named change, even an additive second
finding's test. The planned two finding histories therefore need an explicit
registration, not a weaker test contract.

Named change B permits a second tests-only commit titled
`T-063: named change (B) quote-preservation acceptance`. It may append only
`test_snapshot_pool_quote_raw_value_preserved` and
`test_snapshot_pool_quote_writer_reader_cli_handoff`, their narrowly scoped
synthetic fixtures/helpers if needed, and only their new runner invocations.
Every old definition/assertion and every first-finding acceptance definition
must remain byte/AST exact; no old call is removed or reordered. Parent red,
then a separate minimal quote-field source fix, remain required. If different
names or another prior expectation must change, get the lead's amendment first.

### A2: keep the new inventory fixture compatible with the planned writer key

The first finding's new tests-only commit9c25888 assumes six fixture quote keys
at kind level. The real writer row has no such key before the second finding;
the authorized second fix adds it even when null, so the correct literal total
then becomes seven. This is a newly authored fixture premise, not a production
defect or permission to change pre-existing acceptance.

Named change C permits exactly that new assertion's expected quote count to
change from6 to `6 + int('quote_token_price_usd' in saved[0])`, based only on the
independently retained synthetic writer row. Do not derive the expectation from
inventory output, drop the assertion, remove the new key from the real writer
seam, or change any other expectation. Commit it alone as a tests-only named
change C after retaining the original parent red. The separate second finding's
tests must still require exact quote retention and3/5 differentiation and catch
a discarded-quote mutant. Every pre-existing definition remains byte/AST exact.

### A3: supply the native parser in the new writer-seam clock fixture

The newly added quote writer/reader seam replaces snapshot.datetime with a Clock
that implements now but omits fromisoformat. The real coverage path needs that
native parser, so it returns manifest_invalid even though every raw quote field
is preserved. Keep the original failed synthetic run as a fixture failure.

Named change D permits only adding
`fromisoformat = staticmethod(datetime.fromisoformat)` to that new Clock fixture.
Retain every input and assertion, including the successful-main exit assertion;
no production coverage or clock change is authorized. Commit the fixture repair
alone as a tests-only named change D. With the corrected fixture, replay the
actual pre-quote parent _row in an isolated in-memory namespace and verify that
the new quote acceptance still fails for its real missing-field defect. The
repaired-source focused run must pass. All old definitions remain exact.
