---
id: T-041
title: Measure discovery verdict attribution and deployment windows without caller identities
status: done
level: 3
size: M
depends_on: [T-028, T-039]
decisions: [E11, E30]
backlog: W27 and W28 observation prerequisites
---

## Context, cost and stop rule

The post-release usage workflow executes, but its per-caller verdict profile does not
group by tool. An ok verdict cannot be assigned to discovery when the same caller used
another tool. W28's remaining verification therefore needs a direct tool/status seam.
W27 asks whether unknown answers cluster after actual deployment. Analytics Engine
already records the required fields; no new telemetry is needed.

This bounded measurement protects attribution and prevents treating absent observations
as absence of an operational problem. Cost: one implementation, at most two review
rounds, one opt-in CI readout using existing credentials. Stop after a qualified report
or explicit unavailable evidence; never change the gate or add traffic to get an answer.

## Scope and conflict search

Exactly three implementation files:

- bench/operational_evidence.py (new): read-only, aggregate-only Analytics Engine and
  GitHub deployment evidence, plus a JSON report and an offline analysis interface.
- tests/test_usage_gate.py: append exactly three new test functions before main; all
  helpers/imports for them are local. Every original statement/test/runner stays frozen.
- .github/workflows/usage.yml: an optional boolean workflow_dispatch input and a
  separately conditioned operations-evidence job, standard ubuntu-24.04, pinned existing
  checkout/setup/upload actions. Existing usage job/steps, schedule, inputs and artifacts
  remain unchanged. The optional job has contents:read and actions:read only.

Conflict search covered usage query/rows_of/is_self/gate_verdict/caller_profile,
workflow registration, telemetry write order and deployment step names. The existing
usage test runner discovers all test_ functions, so no test.yml change is needed and
this task has no file overlap with T-040. No old test change is authorized.

Do not modify bench/usage.py, src/, the usage gate, caller classifications, country
rules, production telemetry, privacy text, scoring, benchmarks, datasets, packages,
permission files, deploy workflow or any schedule. Root owns final backlog and
generated-page reconciliation separately. Do not call the production service.

## Acceptance criteria

1. **Observed versus unavailable.** Use only existing CLOUDFLARE_API_TOKEN and
   CLOUDFLARE_ACCOUNT_ID in CI and the existing SQL API. HTTP/auth/transport errors,
   malformed/missing data, truncated rows and valid empty results are distinct states.
   No unavailable query becomes a successful zero. Sum _sample_interval and preserve
   sampled-row counts, explicitly labeling weighted counts rather than exact users.
   Validate returned aggregate schema and counts; no raw error body or secret is printed.
2. **Discovery attribution.** Obtain the successful actual Deploy to Cloudflare step
   completion for supplied release run 39055170209. Query only discovery rows since
   that completion, grouped directly by tool, verdict and self/other cohort. All known
   vetagent-* self labels remain self. Other traffic means attribution unknown, never
   a real user. The report states whether ok/partial was actually observed and on
   which bounded window, without deriving a usage-gate or demand verdict. Query or
   release-anchor failure keeps this verification unobserved.
3. **Deployment comparison.** Use a bounded GitHub deployment inventory and actual
   successful Deploy to Cloudflare step completion times, never workflow creation or
   update times. Where a strict actual version log timestamp is available it may be
   reported as a separate anchor; do not silently conflate them. Include at most ten
   deployments and explicitly state inventory limits/exclusions. Compare assess verdict
   aggregates in first [0,5) minutes and subsequent [5,60) minutes, truncating at the
   next observed upload or the capture clock. Missing upload evidence, incomplete
   windows, empty/low-volume data, sampling and potential unobserved transitions are
   stated. Results are descriptive associations, not a causal or no-effect verdict.
4. **Privacy and bounded execution.** Query output is limited to fixed tool/verdict
   enums, minute buckets, weighted counts, sampled rows, self/other category and public
   deployment metadata. Never output client/country/address/query text, account ID,
   credential, arbitrary upstream strings or raw GitHub logs. Use request timeouts,
   explicit inventory/query/row caps, no retries without bounds, no redirects carrying
   credentials, no shell interpolation and no writable production/API requests.
5. **Usable opt-in workflow.** The existing usage job is byte/semantically unchanged.
   The new job runs only for explicit manual true input, uses the existing secret names
   and GITHUB_TOKEN with read permissions, has a finite job timeout, and preserves its
   aggregate JSON even for a failed observation. An unavailable observation has a
   non-success process/job conclusion. Artifacts contain only the bounded aggregate
   JSON, with short retention; no new recurring job or paid runner. The CLI has a
   deterministic offline mode for fixture evaluation; default local use does not
   accidentally send a query without explicit live intent and credentials.
6. **Tests and complete contract.** Add exactly these three functions, with local
   helpers: test_operational_evidence_refuses_unobserved_queries_and_private_output,
   test_operational_evidence_binds_tool_status_and_actual_deployment_windows,
   test_operational_evidence_cli_and_opt_in_workflow_contract. They exercise real
   public functions/CLI with synthetic API replies and no network; include true/false
   self controls, mixed-tool misattribution, non-200/malformed/empty/truncated/sampled
   counts, missing/failed upload, overlap/censoring and all original gate controls.
   First commit is tests-only and visibly red. Keep findings in separate fix commits.
   Kill at most four meaningful mutants. All original test source and gate parameters
   remain frozen. Run the clean final configured suite only in root's exclusive slot;
   retain exact head/source/command/output hashes in READY.

## Source references and actual readout

Use current primary documentation for Analytics Engine SQL, aggregate sampling and
supported date functions. The existing interface is /analytics_engine/sql, not the
separate Analytics SQL product. Secret existence is not permission verification.
After independent and adversarial source approval and actual Linux checks, root may
push the scoped technical change and manually run this optional job on its exact head.
Only that actual aggregate artifact can close the observation parts of W27/W28; code
and a green test alone cannot. Empty windows leave W27 inconclusive.

## Threat model

Realistic errors are token permission refusal, a JSON error treated as an empty query,
sampled data described as exact users, assigning another tool's status to discovery,
using the end of a smoke workflow as deployment time, and leaking raw caller/credential
data through diagnostics. Preserve no-telemetry-change and no-gate-change boundaries.

## Amendments

None.
