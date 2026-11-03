---
id: T-076
title: Keep unobserved simulator chain probes out of unsupported votes
status: in_progress
design_status: adopted
level: 2
size: S
base: b72b18653db8bd5b05debc87eec0ed25c1704693
code_basis: b72b18653db8bd5b05debc87eec0ed25c1704693
depends_on: []
---

## Context, goal and dispatch boundary

The preceding feature CI failed in chain-reliance assertions after transport-failed
attempts were treated as unsupported votes. Its raw result remains failed in the
release ledger. This task corrects that reproducible classification seam offline.
The executor must use the literal metadata-adoption commit supplied by the lead,
which contains this spec and preserves the code basis above.

A future chain probe that cannot testify must contribute unknown/blindness, never a vote
that a chain is unsupported. Exact observed Invalid chain evidence still votes unsupported;
usable responses missing the required structural field still fail. This is a correction
to the existing E11/E30 observation instrument, not a change to the support roster or bar.

Level2/S is adequate: one bounded classification/status seam in two existing files, with
fresh independent functional review and configured full checks later. The table-driven
acceptance exceeds a light edit. There is no verdict/source/provider/workflow/privacy
schema expansion requiring a new Level3 workstream. Stop at the corrected monitor seam;
supplier recovery and normal release remain Root's separately qualified responsibilities.

## Scope and files

1. tests/test_upstream_contract.py: fetch's chain-only record=False observation policy,
   simulator-chain comparison, and directly relevant comments. Keep the return API
   body-or-None, _attempt_reason, diagnostic schema/version and status writer APIs.
2. tests/test_upstream_contract_is_observed.py: bounded synthetic acceptance in the
   already registered runner; four new automatic tests and one helper described below.
3. Root-only administration after adoption: this task, task index, STATE/OWNER/review
   records. No private paths, business-gate readings or Owner-only recommendations enter public files.

No src/risk.py or _SIMULATOR_CHAIN_IDS change; no frozen registry/profile/evidence,
baseline/source/hash refresh, old result/history rewrite, supplier/endpoint/roster
addition/removal, retry/timeout/pacing/request-order change, new runner/test file,
workflow/continue-on-error/threshold/gate change, network/CI/API/automation call,
benchmark/research/recruitment, T047/T049/T050 work, public claim, push or deployment.
Do not use retries of failed CI to erase its result.

## Normative behavior

Use only the current invocation's fixed diagnostic row and its safe attempt enums;
never parse logged error prose or infer observations from a previous run. The existing
_attempt_reason whitelist remains authoritative.

- A usable body wins, exactly when fetch already returns it. The chain is supported
  when the usable response contains honeypotResult. A usable response lacking that
  field is an observed schema failure, not unknown or a confirmed Invalid chain.
- If fetch returns None but at least one attempt has reason invalid_chain, that probe
  observed unsupported. HTTP400, native success and the exact known message are already
  required by the existing classifier. A negative followed by transport failures remains
  observed negative; a later usable response takes precedence. Do not return early on
  invalid_chain: the existing attempt sequence still runs until a usable body or attempt3.
- None without either usable evidence or any valid invalid_chain is unknown. This
  includes transport/native failures, rate limits, unknown vendor refusals, malformed
  and empty bodies, and partial native-failed responses. Append exactly one _UNOBSERVED
  entry for that fixed probe; do not append one per attempt.
- Preserve version1 and the existing keys/reason enums. For chain-only record=False,
  preserve counts_for_blindness=False for usable responses and confirmed negative
  observations; change it to True only for the unknown case. Ordinary record=True
  callers keep their policy. Every attempt stays in diagnostics, including failed ones.
  The existing healthy/refusal fixture remains version1 with honeypot.is
  {probes:16, usable:12, blind:0, blindness_excluded:7}. No historical v1 row is upgraded
  or reinterpreted. These aggregate buckets are not mutually exclusive: usable can
  overlap blindness_excluded. Exclusion does not mean the supplier is fully covered.

Chain comparison must retain the existing three assertion families:
(1) required ethereum/bsc/base have no observed non-support/schema absence;
(2) nothing believed supported has observed non-support/schema absence;
(3) observed supported names are included in the believed set.
Unknown names are outside the deciding observed subset, not false and not true. Do not
drop required assertions wholesale on a partial run. A believed name outside the fixed
probe roster still fails the existing dropped-coverage obligation rather than being
invented as unknown. Add an explicit structural presence failure for any usable chain
response missing honeypotResult, including a formerly unsupported chain. Keep the existing
structural/type rules in the generated monitor unchanged.

Static chain-ID comparisons execute for every relied-on fixed chain even if all seven
chain probes are unknown. Move their responsibility ahead of/outside the all-none early
return; never let an outage hide an incorrect ID. All confirmed negatives must still be
evaluated even if no usable body was returned. Chain conclusions/logs use fixed chain
names, probe references, booleans/null/enums and scalar IDs only.

write_status retains red > blind > collapsed > green priority and its existing history
format. A partial chain outage with no other failure is blind/native0 under existing
E30 policy; a genuine contract/ID failure remains red/native1 even with unknown probes.
Do not claim all-supplier coverage from native0. Unknown chain entries flow through the
unchanged source-day history and five-day persistence guard; no new threshold.

## Acceptance criteria

1. **Observation partition (group1, 12 fixed maps).** Healthy, one/multiple unknown,
   all unknown, and the seven explicit failure classes in the fixed case inventory below
   distinguish supported / confirmed unsupported / unknown / observed schema absence.
   Reproduce the saved failure's shape with synthetic fixed chains-03 transport attempts:
   no false dropped/reliance failures, exactly one blind probe, and both healthy peers
   retained. All-unknown is seven unknown probes, never seven unsupported chains.
2. **Hard failures (group2, 9 fixed maps).** Exact negative on a required chain, all
   exact negatives, new supported chain, valid200 missing expected field on required
   and previously unsupported probes, wrong static ID with healthy/all-unknown traffic,
   observed negative plus neighboring outage, and a believed chain absent from the fixed
   probe roster remain loud. Retain all old
   negative/refusal/freeze/R1/R3/type/collapse families and original assertions.
3. **Attempts (group3, 7 fixed maps).** Negative before/after transport, recovered
   positive after failure/negative, ordinary usable-body early success and 429 recovery
   retain the full original ordered request trace. Exactly seven fixed chain purposes,
   up to3 attempts each, the existing30s timeout/UA,3s or20s retries and2s chain gaps.
   No new network call, extra retry or early negative return.
4. **Handoff and compatibility (group4, 4 fixed replays).** Actual main -> fetch ->
   chain comparison -> write_status -> existing _load/history/persistence reader
   preserves blindness, red priority, source_counts and v1 shape. Existing49-probe
   fixture and70-request sequence remain exact. Unknown rows are not falsely excluded.
   Capture no address, URL, raw body/error text/input hash; retain49-probe/3-attempt/
   65536-byte overflow guards and absence of diagnostics in historical history rows.
   Baseline, committed status, frozen artifacts and source outside the two files stay exact.
5. **Contract and checks.** Tests first, meaningful parent red before fix, only named
   amendments below, followed by focused and then Root-scheduled configured checks,
   fresh independent source/functional review, contract check and ordinary applicable
   release gates. No check is run by this design. Implementation READY requires actual
   commands/native exits/raw evidence and source seals, not this proposed plan.

## Fixed acceptance placement and named changes

Add exactly these four discovered functions, using one bounded
_chain_observation_scenario helper with fixed purpose maps and fresh isolated module/state:

- test_chain_probe_observations_do_not_turn_missing_answers_into_unsupported
- test_chain_probe_observed_negatives_and_schema_changes_remain_hard_failures
- test_chain_probe_attempt_recovery_keeps_the_fixed_schedule
- test_chain_probe_diagnostics_preserve_truth_through_status

NC1: tests/test_upstream_contract_is_observed.py,
test_freeze_acceptance_uses_the_existing_offline_registration:
the exact automatic-function count changes13 ->17; retain the old diagnostic callable
and assert all four new named tests are callable. Keep the single workflow registration.

Explicit non-amendment: the actual existing function is
test_upstream_refusal_diagnostics_survive_the_real_monitor_and_status_handoff.
The requested shorthand test_probe_diagnostics_survive_the_real_monitor_and_status_handoff
does not exist at this basis. Keep its version1,49 probes,70 requests, all refusal/nested
cases, six RugCheck unknowns and every existing aggregate/assertion exactly as written,
including honeypot blindness_excluded7. New unknown-chain expectations belong in group4.
No other pre-existing assertion change is authorized; an unexpected old failure is BLOCKED.

## Proposed tests-first execution and evidence (not run)

Root first adopts/pins and freezes a quiet source. Acceptance commits touch only the
registered offline test file: add the helper/four tests, record semantic parent reds,
and perform NC1 as its explicitly named tests-only amendment before the source fix.
If NC1's temporary registration red appears, retain it separately; it is not the
meaningful semantic red. Freeze all acceptance inputs/assertions before implementation.

The future helper uses fake subprocess.run and fake sleeps, fatal socket/create_connection/
_owner_rpc_open fallbacks, a private temporary status file and immutable pre/post bytes.
Run only the real chain function via discovered main (stub unrelated monitor test
functions) while exercising real fetch/status/reader code. Synthetic body categories stay
in test memory; public receipts project enums/scalars only. No live source/API/import is
executed in this design. Future execution is permitted only by Root's explicit dispatch.

Proposed focused command: python -B tests/test_upstream_contract_is_observed.py.
Existing seam guards to verify without modification: python -B
tests/test_rugcheck_coverage_probe.py and python -B tests/test_owner_power_evidence_split.py.
Root then schedules the applicable exact-source python lead/checks.py, syntax/contract
and fixed-point generation requirements under current preservation/admission rules.
Do not independently start full, live upstream tests, builds, CI or generation.

READY evidence: frozen literal base/head/test commits; unchanged old test functions and
NC1 exact diff; semantic reds and fix greens; all32 fixed case invocations with native
exit, safe observations/failure families, ordered safe request-purpose/attempt traces
and sleep totals; unknown-to-status-to-persistence proof (existing five/six day boundary);
unchanged original49/70 fixture; privacy/bounds/byte preservation; focused/full/independent
reports and failures explicitly separated. No expected green substitutes for measured output.

## Risks and unknown dimensions

Saved HTTP000/native28 proves a transport timeout outcome, not its remote/network root
cause or current supplier support. This design has no fresh runtime verification. Only
seven fixed EVM probes are covered; no new provider, token, chain, location or production
risk assessment is measured. Legacy status-only rows cannot reconstruct old per-probe
causes; existing v1 rows with preset exclusions cannot retrospectively prove coverage.
Do not edit the saved failure, baseline, historical JSON, support list or scientific bar.

The literal dispatch base and source-preservation window are recorded by the lead. T047,
T049 and T050 remain held. The A feature release remains held on the retained CI failure.


## Root adoption amendment and fixed case inventory

Before the first acceptance commit, the lead adds B08 to cover the already normative
unprobed-believed-chain obligation explicitly. This changes the proposed case count
from31 to32, with the same four discovered test functions and automatic count17.
No executed result or old acceptance assertion is changed. The original31-case
design remains an immutable input. All other design behavior is adopted as written.

Use fixed chain order ethereum,bsc,base,arbitrum,polygon,optimism,avalanche and
fixed references chains-01 through chains-07. Input categories: S=usable positive;
N=native0 HTTP400 exact known Invalid chain; U=HTTP000 native28; R=HTTP429;
V=unknown vendor refusal; M=malformed200; E=empty200; P=native23 partial200;
I=native28 with negative-looking body; O=OSError; A=usable200 lacking expected field.
Only N is an observed unsupported result. Other failure categories are unknown.

| Group | Fixed case | Purpose |
|---|---|---|
| 1 | A00-healthy | healthy |
| 1 | A01-base-transport | base transport |
| 1 | A02-base-and-arbitrum-unobserved | base and arbitrum unobserved |
| 1 | A03-all-unobserved | all unobserved |
| 1 | A04-unsupported-position-unobserved | unsupported position unobserved |
| 1 | A05-base-R | base R |
| 1 | A06-base-V | base V |
| 1 | A07-base-M | base M |
| 1 | A08-base-E | base E |
| 1 | A09-base-P | base P |
| 1 | A10-base-I | base I |
| 1 | A11-base-O | base O |
| 2 | B00-required-confirmed-negative | required confirmed negative |
| 2 | B01-all-confirmed-negative | all confirmed negative |
| 2 | B02-new-supported-chain | new supported chain |
| 2 | B03-required-observed-schema-absence | required observed schema absence |
| 2 | B04-nonrequired-observed-schema-absence | nonrequired observed schema absence |
| 2 | B05-wrong-static-id-healthy | wrong static id healthy |
| 2 | B06-wrong-static-id-all-unobserved | wrong static id all unobserved |
| 2 | B07-confirmed-negative-with-neighbor-outage | confirmed negative with neighbor outage |
| 2 | B08-believed-chain-outside-fixed-probe-roster | believed chain outside fixed probe roster |
| 3 | C00-negative-transport-transport | negative transport transport |
| 3 | C01-transport-negative-transport | transport negative transport |
| 3 | C02-transport-transport-negative | transport transport negative |
| 3 | C03-recovered-positive | recovered positive |
| 3 | C04-negative-recovered-positive | negative recovered positive |
| 3 | C05-existing-positive-early-return | existing positive early return |
| 3 | C06-rate-limit-recovered-positive | rate limit recovered positive |
| 4 | D00-v1-healthy-handoff | v1 healthy handoff |
| 4 | D01-v1-unknown-handoff | v1 unknown handoff |
| 4 | D02-v1-all-unknown-persistence | v1 all unknown persistence |
| 4 | D03-v1-red-before-blind | v1 red before blind |

B08 retains the healthy response map but adds unprobed_test_chain:777 to the
test-only believed mapping. It must preserve the dropped-coverage failure, red
status and native1; it is not an upstream request, new supported chain or source edit.
