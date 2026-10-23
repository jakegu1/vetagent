---
id: T-058
title: Preserve bounded per-probe upstream refusal diagnostics
status: done
level: 3
size: M
depends_on: [T-023, T-037]
---

## Context and goal

The live monitor compresses unsuccessful requests into a source and final HTTP
status. It loses which fixed probe failed, intermediate attempts, transport
failure and the reason class of a Vendor rejection. Historical source-only
counts cannot identify a past failed input or establish a root cause. Preserve
actionable, bounded diagnostics without exposing addresses, URLs or error prose.
Keep every existing probe and the pre-registered coverage/observation rules.

This costs one source repair, two bounded review rounds at most and ordinary
configured gates. Stop when rejection classes and transport outcomes survive
the monitor/status seam and actual source CI has been inspected. Vendor recovery
is a separate observation, not proof that a historical cause was repaired.

## Scope and files

- `tests/test_upstream_contract.py`: fetch diagnostics and status/console output.
- Additive acceptance in registered `tests/test_upstream_contract_is_observed.py`.
- Governance status/review only after source approval.

No production code, new provider, probe removal/substitution, new retry, changed
timeout/pacing, scientific enrollment, baseline re-freeze, workflow or permissions.
Search all fetch/measure/write_status callers and status readers before editing.
Existing assertions and decision thresholds are frozen; any required expectation
change must be named in a spec amendment before editing it.

## Acceptance criteria

1. Each recorded probe gets a stable safe reference based on its fixed input
   position/purpose, not an address, URL, identity or their hash. Multiple attempts
   remain attached to that probe. Duplicate input used for another test retains
   its distinct purpose. Existing `record=False` expected-negative requests stay
   excluded from blindness while their classification remains distinguishable.
2. Preserve each attempt's HTTP status, native transport exit, usable-body flag
   and a fixed reason enum. Demonstrate HTTP400 with recognized error bodies,
   unknown/rejecting bodies, HTTP429 followed by200, HTTP200 malformed/empty body,
   nonzero native exit with a parseable partial body, and actual healthy200.
   Transport failure never becomes usable evidence. A failed request's risk
   fields remain unobserved. Unknown text is not guessed into token absence.
3. Public diagnostics contain no request input, URL, raw body, Vendor error prose,
   secret, or hash of an address. Classify only a small explicit whitelist and
   use `vendor_rejected`/`unclassified` otherwise. Bound probe/attempt counts and
   serialized record size without silently dropping excess records.
4. Diagnostics survive fetch -> monitor -> status JSON and concise console
   output. Retain legacy status/history semantics and source aggregate counts;
   preserve all configured probes, source distinctions, retries and pacing.
   Existing readers accept the additive field. A status-only old record remains
   explicitly insufficient to reconstruct a historical failure.
5. Acceptance uses deterministic fake transport with no Vendor calls, tests the
   status handoff, and catches meaningful mutants deleting attempt evidence,
   leaking error prose or accepting native failure as a healthy response.
6. Tests are committed alone first and reproduce the parent defect. Contract,
   focused acceptance and actual configured complete runner pass at an exact
   frozen head with raw before/after bytes; parent serializes heavy host gates.
   Fresh independent and red-team review, actual source Linux CI and normal
   post-integration/publication checks are required before deployment.

## Evidence and threat model

READY supplies tests/fix SHAs, parent red, focused/mutant evidence, stable probe
mapping and boundedness/privacy proof. Preserve old failures and all scientific
Artifacts. The lead alone makes capped real requests and inspects actual CI.
Threats include misattributed retries, Vendor prose leaking an input or secret,
partial curl output voting as healthy, and a repaired instrument being mistaken
for proof of a repaired Vendor incident. No reduced coverage or green-by-retry.

## Amendments

2026-10-23 A1, before acceptance: the conflict search identifies the exact count
in `test_freeze_acceptance_uses_the_existing_offline_registration`. Permit its
named assertion to change from twelve functions to the explicit new total
(thirteen if one new acceptance function is added). Keep the original discovered
functions and assert the new named acceptance is discovered. Add a normal
`test_` acceptance function; do not hide it behind a separately maintained runner.
No other original assertion is relaxed. Baseline comparison bands and schema
guards retain their original semantics; diagnostic status fields are additive.

2026-10-23 A2, round-one red-team finding M1: an HTTP200 GeckoTerminal body with
`status.error_code` set is a known Vendor error envelope (already recognized by
`risk._is_error_body`), but the new monitor accepts it as usable. A synthetic
monitor-to-status replay counts eight such refusals as eight usable bodies and
raises a false field-removal alarm. This breaks AC2/4, not a new inference bar.
Add named acceptance for this nested envelope under the existing new diagnostic
test, red against8c469b7, then fix the general error-envelope classifier. Cover
zero and string error-code values and absent/null nested error code according
to the existing engine predicate; retain genuine healthy envelopes. Keep error
prose out of output and nested refusals unobserved. All original probe, timeout,
pacing and coverage expressions stay exact. Freeze the new cases before the
fix. Round two is a combined independent and adversarial re-review of this
class plus regressions; do not broaden into unrelated source work.
