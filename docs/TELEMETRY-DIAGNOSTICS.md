# Offline telemetry diagnostics

Run the local composer on an existing anonymous aggregate bundle. It does not query Analytics,
read credentials, issue product requests or evaluate the adoption or production score gates.
Use a new output filename on each run; existing files, input aliases and prior failure outputs
are refused. Input, parse and argument errors emit only fixed codes, never input text or paths.

```sh
python -B bench/telemetry_diagnostics.py --input tests/fixtures/telemetry_diagnostics_v1.json --output REPORT.json
```

The committed fixture is synthetic. It demonstrates sampled events, a valid empty reply and
unqueried selections. It is not a current usage, customer or service-quality observation.

## Input

The exact top-level keys are `schema`, `storage_schema`, `captured_at`, `aggregates`. Schema is
`telemetry-diagnostics-input-v1` and storage_schema is `legacy-v1`. The declared captured_at is
a whole-second UTC ISO timestamp ending in Z; it is not independent acquisition or freshness
evidence. The composer cannot authenticate the producer or recover missing historical data.

Each aggregate has exactly `tool`, `cohort`, `start`, `end`, `reply`. Selection enums come from
the existing operational reader: assessment/discovery tools and self/other cohorts. Each
selection can appear only once. Its positive window must end by captured_at and stay within
the existing bounded lookback. Different windows and cohorts are never pooled.

The reply is the existing `http_status`/`body` envelope for
`operational_evidence.aggregate_reply`. Its fixed rows contain tool, cohort, verdict, minute,
weighted_count, sampled_rows and max_sample_interval. The original parser validates enum
membership, duplicate cells, time buckets, weights, row limits and response failures unchanged.
The input byte limit is one MiB, and duplicate JSON keys, nonfinite numbers and malformed or
deeply nested JSON are refused. The direct Python `diagnose(bundle)` API applies the same finite
JSON and metadata boundary and raises a fixed-code ValueError for an invalid bundle.

## Interpretation

The fixed report schema is `telemetry-diagnostics-report-v1`, with captured_at, state, sorted
results, capabilities, production_gate_evaluated and interpretation. Its captured_at is still
only the input declaration. Query states preserve observed, empty, HTTP/transport error,
redirect, malformed and truncated. A missing selection has not_queried and null counts.
A successful empty query has empty and zero counts. A failed query has null counts and its
failure state; a healthy neighboring selection remains visible.

Weighted event estimates and stored rows are distinct. The stored rows' maximum sample
interval is retained, without inventing a uniform sample weight, an effective sample size,
exact user counts or population confidence bounds. Query-time and write-time sampling can
both matter. A row is a recorded event, which is not always a whole network request.

Legacy chain and request_latency dimensions are not_recorded. Reason breakdown, error rate,
liquidity-tool observations and caller identity are not_queried by this format. Anonymous
diagnostics do not support caller identity. Client self-description cannot prove a customer.
No latency percentile, error rate, chain zero, production unknown rate or service objective
is reconstructed from these missing dimensions.

The report's state is observed when at least one selection is supplied and every supplied
query is observed or empty; unobserved when none is supplied; partial when a supplied query
fails. The CLI creates a report for valid partial/unobserved inputs and exits nonzero so the
failure remains reviewable. Observed exits zero even though unrelated dimensions remain
unqueried. Invalid input and output failures emit a fixed diagnostic and exit nonzero. A write
failure can leave a partial new file; retain it and choose a new path instead of overwriting it.

None of these process exits constitutes readiness, adoption, source authenticity, production
availability or evidence that an unqueried dimension was absent. The original usage rules,
production denominator, source freezes and scorecard are unchanged.

## Verification

The additive `test_a1_telemetry_*` tests run through the existing registered suite:

```sh
python -B tests/test_usage_gate.py
```

They exercise the actual offline CLI, file preservation, existing aggregate validation and
malicious input while network and subprocess operations are blocked inside the CLI process.
The parent test harness starts that process solely to test the command-line seam.
