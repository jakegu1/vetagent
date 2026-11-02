---
id: T-070
title: Demonstrate fail-closed response routing for HTTP and MCP without sending requests
status: in_review
level: 2
size: S
base: f85102f9eae392ea3510bce7dfaddaf68b45e741
depends_on: [T-069_source_acceptance]
---

## Goal, cost and stop

An integrator can run one standard-library-only local example against HTTP/MCP response fixtures
and see rejection, review, continued evaluation, bounded retry advice or abstention. It reuses the
existing verdict/unknown guidance and never authorizes an order. Cost: one S slice and independent
functional review; stop at a response adapter/example, without HTTP client, retry loop or order SDK.

## Files and scope

- New `examples/assessment_policy.py` with `route_http(payload, http_status=200)` and
  `route_mcp(envelope, http_status=200)`; simple JSON-from-stdin CLI with --transport http/mcp.
- Add `test_a2_policy_*` functions to already registered `tests/test_mcp.py`.
- Edit only routing guidance and add a local example section in `docs/AGENT-INTEGRATION.md`.

No source engine/entry/MCP schema, telemetry, legal/privacy text, score, transport, dependency,
workflow, frozen file or gate changes. No other existing prose cleanup in this slice. Existing
public examples have stale/partial chain/source information; record it as a follow-up, not this
task's claim of updated full coverage. No new test file/CI step. Root owns task administration.

## Exact response policy

Each adapter returns only `action` (reject/manual_review/continue_evaluation/retry/abstain),
`retry_after_seconds` (positive integer or null), and `reason` (a fixed code).
HTTP status must be an exact int200; any error envelope/non-object abstains. MCP accepts one
object with a result dict and structuredContent dict only; top-level error, isError, missing
structuredContent or batch/list input abstains. Never parse model-oriented content text as a
fallback, retain address/signals/body in output, or evaluate strings/code.

- high -> reject, reason high_risk.
- medium -> manual_review, reason risk_requires_review.
- low -> continue_evaluation, reason checks_ran_without_fatal_signal. This is not safe_to_buy.
- unknown -> retry only for kind infrastructure/mixed AND next_action=retry AND exact non-bool
  integer retry_after_seconds in1..2147483647. Output the delay advice only, no sleep/request.
  coverage, contradictory fields, missing/invalid retry guidance -> abstain with fixed reason.
- Missing/unrecognized verdict, wrong types and malformed envelopes -> abstain.

checked_at/evidence_max_age_seconds remain existing response context. The adapter does not invent
freshness/SLO thresholds or infer provider health from missing fields. Documentation tells an
integrator to apply its own pre-registered freshness/workflow policy; no actual trading flow exists.
CLI cap1MiB, duplicate JSON keys refused, unknown CLI arguments/non-JSON/oversize inputs produce
safe fixed diagnostics and nonzero, never echo input. Valid abstention is an example result,
not a failed process. No input logging or credentials. Unknown with any score still follows unknown.

## Acceptance criteria (seven)

1. Acceptance tests are committed first alone, meaningful parent reds are retained, and all old
   tests/assertions remain unchanged. New functions run in the existing automatic MCP test runner.
2. Direct HTTP and MCP structuredContent fixtures produce the exact five actions above; medium
   requires review, low only continues evaluation, high rejects; no result contains trade permission.
3. Infrastructure/mixed unknown with valid delay advises retry; coverage, missing kind/action/delay,
   negative/zero/bool/float/huge delay and contradictory guidance abstain; neither transport retries.
4. HTTP errors including429, MCP error/isError, absent structuredContent, malformed/non-object
   inputs, batch envelopes, text-only answers and unknown verdicts fail closed without parsing text.
5. Malicious addresses, identity strings, URLs, free-form errors and sentinel credentials never
   reach adapter/CLI output. A patched network/sleep/subprocess boundary witnesses zero calls.
6. The real stdin CLI runs both transports offline and matches pure-function output; bounded malformed
   JSON/duplicates/size errors are safe. Docs contain these executable commands, no live placeholder
   executed automatically, and explain checked_at/evidence age, unknown retry/abstain and low limits.
7. Contract/checks: run `python -B tests/test_mcp.py`, then root-assigned exact-source full checks before
   implementation READY; independent functional review and integrated/applicable CI validation.
   No Worker deployment or production request is required for a local example. Root controls publication.

## Named tests and evidence

Add `test_a2_policy_http_and_mcp_actions`, `test_a2_policy_unknown_retry_or_abstain`,
`test_a2_policy_envelope_errors`, `test_a2_policy_private_data_and_no_network`,
`test_a2_policy_real_cli`. No old test changes are authorized. Tests for MCP outputSchema,
structuredContent/text equivalence, errors and unknown guidance remain original guards.
See the accepted A0 conflict census. READY carries exact commits, parent reds/head results/native exits,
named diffs/hashes, AC evidence, doc CLI outputs and any unexecuted gate. Do not sign own acceptance.

## Root accepted clarification and dispatch boundary

The A2 design and its response-routing clarification passed fresh functional/privacy
design review. Original design SHA256 is 4883593390f5bedf38510e5f2abebc15146a933318415b73da11dd5878d161d2;
the accepted pre-tests clarification SHA256 is 4480fa5293ec743c7f6e900a644c522905bd1ca327921638a2bcae080088080d.
This new task incorporates that clarification; it does not rewrite either original.

Validate only consumed envelope/status/verdict/unknown-guidance fields, not a full
assessment schema or unused score. Any present HTTP payload error or MCP top-level
error abstains even when null. MCP result/structuredContent must be dictionaries;
present result.isError must be exactly false. Never parse content text as a fallback.
Unknown overrides every score. A valid low response with a malformed unused score
may continue evaluation; describe this limited adapter accurately, never a trade.

Freeze the clarification's exact action/reason table in the first tests-only commit:
invalid envelope -> abstain/invalid_envelope; invalid verdict -> abstain/invalid_verdict;
high -> reject/high_risk; medium -> manual_review/risk_requires_review;
low -> continue_evaluation/checks_ran_without_fatal_signal;
valid infrastructure/mixed retry -> retry/infrastructure_retry_advised;
coverage unknown -> abstain/coverage_requires_abstention;
unknown unrecognized kind -> abstain/unknown_kind_unavailable;
recognized retry-capable unknown with invalid guidance -> abstain/retry_guidance_invalid.
Only retry carries a delay; all other delays are null. No new freshness/score threshold.

Root's current conflict search found no collision for the new example/action/reason
names in current tests/tools/docs. The executor must recheck the exact source and
extend only the named automatic MCP tests; all prior tests/assertions stay exact.
Keep the original no-requests/no-sleep/no-order boundary, fixed safe CLI diagnostics
and 1MiB cap. Do not change production, workflow, caller telemetry or frozen sources.

This spec is ready for later dispatch, not an active source/ref-write grant. Reuse
the existing A worktree only after root accepts T069's source and releases its
freeze. Root then assigns branch codex/t070-assessment-policy-example-20261102 and
an explicit tests-only/implementation window. No branch/commit/source writes or
heavy run may begin from this document alone. Root owns all administration,
integration, actual CI/builds and release; do not self-merge or publish.

## Actual dispatch and named test correction

After T069's exact source passed both actual45 gates, independent functional12/12
and separate privacy/adversarial review, root dispatched this task on the stated
f85102f base and named branch. Its original pre-dispatch restrictions above are
historical conditions, not a claim that dispatch is still pending.

Root permits one correction to the new test_a2_policy_real_cli only. A balanced
depth1100 array accepted by the actual parser is valid JSON and cannot remain in
the unconditional nonzero invalid-input list. Use a balanced depth32 representative
for exact CLI0/abstain/invalid_envelope/null; retain an unclosed deep array as safe
nonzero malformed input. Depth32 is a fixture, not a production threshold. Retain
the original balanced1100 runtime witness as diagnostic, without asserting every
interpreter accepts that depth. Native parser refusals remain sanitized/nonzero.

Commit this named correction alone as an acceptance test fix before implementation.
Preserve all other tests/inputs and original red/failed evidence. No custom depth
cap, new schema/freshness rule, request, order or scope expansion is authorized.

## Root-owned generated-scorecard dependency

The first actual author gate at e3bdbdd executes45 steps:44 pass, and the
published-number guard fails because the generated SCORECARD still records1432
MCP assertions while the new actual runner reports1591. Source and complete ref
protections pass. Preserve this original failed source and complete receipt.

Root adds exactly docs/SCORECARD.md to the named scope as unchanged-generator
output, solely updating that evidence count. The original generator's output
must differ only at this cell; scores, rules and other figures do not change.
The original failing guard must actually pass after generation. The separately
committed correction is a new source requiring new complete gates and source
bindings; no old failed plan/output is rewritten or reclassified as passed.
