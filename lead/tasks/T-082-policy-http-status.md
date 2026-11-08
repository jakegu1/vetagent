---
id: T-082
title: Preserve an explicitly supplied HTTP status in the offline policy CLI
status: ready
level: 1
size: S
base: 588d14b021c740cd856eac37696cab126be0c014
depends_on: []
---

## Goal and boundary

The Python routing functions already reject non-200 HTTP responses, but the CLI
cannot carry the transport status into either HTTP or MCP routing. Let an
integrator supply that status without writing a separate adapter. This closes a
demonstrated example handoff gap; it is not a production unknown-rate or customer
outcome measurement. Cost: one small additive option and existing-runner tests.
Stop at this interface; no network client, retry loop, order permission, telemetry,
new validation framework, freshness policy or risk-engine change.

## Files

- examples/assessment_policy.py
- tests/test_mcp.py (additive named tests only)
- docs/AGENT-INTEGRATION.md (local CLI status guidance only)

Root owns task administration. All original tests and Python routing APIs remain
unchanged. No historical research, provider, source pin, workflow or score changes.

## Acceptance

1. Add tests first alone, with a meaningful old-source failure: --http-status is
   rejected by the old CLI, so it cannot return the existing non-200 routing
   decision. Retain the red command and native exit; do not edit frozen new tests
   after implementation starts without a named Root correction.
2. Add optional --http-status. Default 200 preserves all existing fixture commands.
   An explicit three-digit ASCII decimal status in 100..599 is accepted and passed
   to the selected existing route function. For both HTTP and MCP, 200 matches the
   existing behavior; 201, 204, 400, 429 and 503 abstain/invalid_envelope/null even
   when the body contains low or valid retry guidance. No non-200 response can
   advise retry or continue_evaluation through this example.
3. Noninteger, signed, Unicode-digit, out-of-range, missing and private arbitrary
   argument values produce the existing arguments_refused/nonzero safe failure.
   No raw argument/input reaches stdout/stderr. Preserve the one-MiB input cap,
   duplicate-key refusal and offline/no-sleep/no-request behavior.
4. Documentation gives a runnable local non-200 example and explains that default
   200 is a fixture convenience: real integrations supply the actual status, via
   the CLI option or the existing Python parameter. Unknown remains unknown, low
   only continues evaluation, and no output authorizes an order.
5. Reuse existing automatic tests/test_mcp.py enumeration and its subprocess helper.
   Author focused checks and configured full checks, fresh independent review,
   integrated full checks and normal applicable CI remain required. No production
   Worker upload or new snapshot collection is needed for example-only changes.

## Conflict search and evidence

Existing test_a2_policy_real_cli and test_a2_policy_private_data_and_no_network
exercise default commands, unknown arguments and the private-output boundary.
Their assertions and fixtures stay byte-exact. Add test_a4_cli_http_status_handoff
and test_a4_cli_http_status_invalid_arguments in that same registered file.
Pure route_http/route_mcp tests stay unchanged; this task changes only CLI plumbing.

READY: base/tests-only/fix SHAs, exact file diff, old red/new green native exits,
CLI output for both transports, unchanged old assertions, source-preserving full
check result and unexecuted dimensions. Use existing compressed retention; keep
only small task logs and source hashes. Root assigns serialized full execution.
