---
id: T-069
route: A
slice: A1
title: Report bounded offline telemetry capabilities without inventing missing dimensions
status: in_review
level: 3
size: M
base: e3ec46ad8e4c485243fe20a606ac263564d350f0
depends_on: []
---

## Context, benefit, cost and stop

Existing `bench/operational_evidence.py` already validates fixed anonymous assessment/discovery
aggregates and sample weights. Reuse it instead of rebuilding a live collector. Old six-blob
rows cannot answer chain or latency questions. This slice gives an operator a deterministic
offline report that separates usable counts, actual query failures and missing dimensions.
Cost: one M slice and fresh functional/privacy adversarial reviews. Stop at this report; do
not add a live mode, dashboards, new queries or more fields to reach a sample-size target.

## Scope and exact files

1. New `bench/telemetry_diagnostics.py`: standard-library-only offline CLI/composer.
2. Add tests only to already registered `tests/test_usage_gate.py`.
3. New synthetic `tests/fixtures/telemetry_diagnostics_v1.json`.
4. New English `docs/TELEMETRY-DIAGNOSTICS.md`: format, commands, states and limitations.

No existing assertion or fixture may change. No new test file/CI registration is required.
Root assigns the permanent T-number and task/index/STATE administration separately. No changes
to entry/risk/MCP sources, usage.py, operational_evidence.py, scorecard, any production artifact,
collector/research source, data, source pin, dependency, generator, workflow or deployment file.

## Input and output contract

Input JSON has exactly `schema`, `storage_schema`, `captured_at`, `aggregates`. Schema is the exact
string `telemetry-diagnostics-input-v1`; storage_schema is exactly `legacy-v1`. This is the input's
assertion of a legacy source, not independent proof of its producer; unsupported versions refuse.
captured_at is a valid whole-second UTC ISO timestamp with Z.
aggregates is a list of at most four objects, each with exactly `tool`, `cohort`, `start`, `end`,
`reply`. Tool/cohort use existing operational_evidence.TOOLS/COHORTS only. Each selection appears
once, `start < end <= captured_at`, and no window exceeds90 days. Times use the same exact UTC
format. reply is the existing HTTP-status/body envelope consumed by aggregate_reply; unknown
envelope content is never reflected in output. A declared selection with a failed query is
still present and retains its failure, not omitted. Input cap1MiB, row cap the existing512.
Refuse duplicate JSON keys, bool-as-number, oversized input and malformed/deep JSON safely.

`diagnose(bundle)` returns a new safe fixed-key report, version `telemetry-diagnostics-report-v1`,
containing `captured_at`, `state`, `results`, `capabilities`, `production_gate_evaluated:false`,
`interpretation:"descriptive; not customer, readiness, or service-quality evidence"`.
Results have one cell for each of the four fixed tool/cohort selections in sorted order:

- For a supplied valid selection, call existing `aggregate_reply` without modification and
  project only its validated rows/count fields, plus the normalized start/end. Preserve its
  observed/empty/http_error/transport_error/redirect/malformed/truncated states. Do not retain
  response body, arbitrary error values, caller/country, paths or unknown keys.
- An absent selection is `not_queried` with null counts, never empty or zero.
- Keep `weighted_count`, `sampled_rows`, `sampled` and per-row `max_sample_interval`; never
  sum distinct windows or label weighted events as exact calls/users/customers. `_sample_interval`
  is represented by the existing aggregate's weight facts, not a newly invented uniform weight.
- capabilities: chain and request_latency are `not_recorded` for legacy input; reason_breakdown,
  error_rate, liquidity_tool and caller_identity are `not_queried` by this input contract.
  caller_identity also states `unsupported_by_anonymous_diagnostics`. Do not infer reason absence,
  errors, p95, chain zero, production unknown rate, adoption verdict or a new SLO.

Top state is `observed` if all supplied selections validate as observed/empty and at least one
selection is supplied; `unobserved` if none supplied; `partial` if any supplied query fails.
CLI: `python -B bench/telemetry_diagnostics.py --input INPUT --output NEW_OUTPUT` only. No default
network, credentials, SQL, probe, fetch or live flag. Report exits0 for observed,1 otherwise;
argument/input/output failure produces a fixed-code safe diagnostic and nonzero, never raw JSON,
exception, path or input text. Refuse to overwrite an existing output or alias the input; preserve
input and prior failure files. Serialization is deterministic ASCII-safe JSON with finite numbers.

## Acceptance criteria (eight)

1. New tests fail meaningfully on the parent before implementation (missing composer/CLI or
   incorrect behavior, no import collection crash). First commit contains only acceptance tests
   and synthetic fixture. Test names start `test_a1_telemetry_`; all old tests remain byte-exact.
2. Reused valid weighted data preserves weighted events6, stored rows2, max interval3; an actual
   empty200 returns zero, missing selection null/not_queried. Mixed windows are never pooled.
3. HTTP401/403/500, redirect, transport failure, malformed body, unknown fields in aggregate rows,
   duplicate cells, bad counts and truncation retain distinct unavailable states and null counts.
   Changing failed replies to empty is a caught mutant, not an acceptable simplification.
4. Missing/invalid schema, duplicate keys, future/invalid/overlong windows, duplicate selections,
   booleans, NaN/Inf, rows beyond the existing cap and file size beyond1MiB are refused. A broken
   count relationship is caught through the existing parser seam, not merely a copied fixture.
5. Legacy numeric-zero ambiguity cannot produce a duration or chain measurement. Every report
   states not_recorded for those dimensions and not_queried for unsupported dimensions. No score,
   customer count, adoption verdict, latency point estimate or SLO appears.
6. Malicious strings in all input/response fields and sentinel environment credentials never appear
   in JSON/stdout/stderr. Patch socket/subprocess/urllib entrypoints to fail if invoked; both pure
   and subprocess CLI paths do no network or child process work. Test default invocation too.
7. Real CLI on the synthetic fixture creates deterministic equal bytes at two different new paths,
   refuses existing output/input alias, retains an observed failure result and input hashes, and
   exits according to the stated availability contract. Unqueried dimensions alone are not failure.
8. Contract and checks: additive tests execute through the real existing runner; all original
   behavior/source/gates remain exact. Author runs `python -B tests/test_usage_gate.py`; obtains
   a root-assigned exact-source slot for `python lead/checks.py` before implementation READY.
   Fresh independent functional and separate privacy adversarial review, integrated full gates,
   actual applicable CI/build evidence and normal publication verification are root responsibilities.
   A1 has no Worker change; do not invent a Worker deployment or new production sample.

## Named tests and evidence

Add `test_a1_telemetry_weighted_empty_missing`, `test_a1_telemetry_query_failures`,
`test_a1_telemetry_invalid_contract`, `test_a1_telemetry_legacy_dimensions`,
`test_a1_telemetry_private_input_and_offline_boundary`, `test_a1_telemetry_cli_preserves_files`.
These extend the automatic `test_*` enumeration in `test_usage_gate.main` (line857 at base). Existing
operational_evidence tests and their exact old workflow hash remain unchanged. No old test
expectation is authorized to change; see TEST-CONFLICTS.md for the larger consumer census.

READY needs exact base/tests-only/head and named files, parent red and head commands/native
exit/stdout/stderr paths, fixture/output/input SHA256, AC-to-evidence map, negative/mutant results,
unrun dimensions, and root heavy-slot receipt/full-gate evidence. Use the accepted shared compressed
retention workflow for applicable source preservation; do not create whole-tree copies. No author
review verdict, publishing claim or new approval from silence.

## Level3 threat model

Untrusted older aggregates may contain private labels/errors and malformed weights. The report
must not reflect them or turn refusal into a zero. A helper import, CLI default or credentialed
environment must not trigger an online read. Real file inputs and failures must survive. Schema
validation and serialization use explicit fields; no raw exception, content hash or input repr.
The report is descriptive and cannot qualify users, trades or the frozen scientific/demand gates.

## Root dispatch clarifications (before the tests-only commit)

The accepted original A1 spec SHA256 is 67ae219438485fe93032edee15f1191761ba1ba66894b938edbd23eb39d64533. This task is the offline A1 slice only. captured_at is an input-declared timestamp, not independently proved acquisition, freshness or production evidence. Valid normalized times and finite permitted numeric values can appear in output; privacy checks forbid arbitrary free-text reflection, not all input-derived values. Exercise default/unknown CLI arguments, error paths and input/output names using distinct malicious sentinels; preserve fixed diagnostics and the original no-network requirement. These clarify existing ACs without adding online queries, source authentication, clocks, a new threshold or changing any old test.

The executor first adds only the named acceptance tests and fixture. Root owns public task-index/STATE/spec integration separately; do not commit administrative files in that tests-only commit. After focused green, report the exact source head and tests-first chain for a root-assigned observed full-gate slot before author READY. Do not run a heavy gate without that assignment. Only root can integrate, push or deploy. Future production telemetry/caller changes and T047/T049/T050/T068 remain out of scope.
