---
id: T-078
title: Exercise the existing rate limiter through a reusable canary connection
status: ready
level: 3
size: S
depends_on: [T-068]
backlog: existing deployment and observation reliability
---

## Context and goal

The price repair passes the complete configured source gates and exact-head CI.
It is uploaded, but the deployment's flood check has not observed a429. The
existing shell loop opens a new curl process for every invalid-input request.
Those connections can reach different edge locations. The actual _EdgeCounter
uses caches.default, whose contents are local to a data center; it is not the
previously rejected native rate-limit binding. Split traffic therefore cannot
establish that the counter should have tripped. A successful single-call
diagnostic establishes neither working cumulative counting nor a broken limiter.

Exercise the same canary predicate with connection reuse and bounded diagnostics.
Keep the original failed deployment and its unobserved rate-limit dimension.
Primary reference: https://developers.cloudflare.com/workers/runtime-apis/cache/

## Scope and conflict search

Runtime constants, _EdgeCounter, _limit_state, client identity, IP hashing, public
claims, SDKs, locks, providers and all historical/security holds stay unchanged.
No global-quota feature, new runner, validation controller or manual live flood.
Only the existing normal deployment canary may make its fixed invalid requests.

Files: .github/workflows/deploy.yml (existing flood block only),
tests/test_deploy_gate.py (additive tests and explicit main registration), and
tests/test_http_telemetry.py (named NC1: clarify the existing
test_the_deploy_flood_cannot_fail_on_a_minute_boundary docstring/label to state
its single-location precondition; preserve both existing assertions).
The existing125-request minimum and cf-ray checks remain. All offline-before-
upload, credential, lock, smoke and checkout conditions remain unchanged.

## Acceptance criteria

1. Tests are committed first. An owned loopback HTTP/1.1 model routes separate
   connections round-robin across three locations and counts by location/window.
   Running the actual old flood block must reproduce a failure with a healthy
   counter and no429. It must not call production, a provider, or the risk engine.
2. The production flood remains at most125 sequential invalid MCP tool calls,
   with its existing self-client tag and payload. One curl process reuses its
   HTTP/1.1 connection; no proxy/IP override, retries, additional endpoint or
   parallel request is introduced. A fixed pacing and whole-operation deadline
   keep the attempt below60seconds; timeouts and partial results remain failures.
3. Success still requires a real HTTP429, now also accompanied by the existing
   x-vetagent-ratelimit: limited header. HTTP200/ok alone, open states, missing
   headers, unexpected statuses and transport failures cannot pass. A healthy
   local model passes; a never-limiting model and misleading429/header mismatch
   fail. This is enforcement evidence, not a precise/global quota measurement.
4. Diagnostics contain only bounded status/state/connection/location counts.
   No IP, full cf-ray, body, address, query, credentials or arbitrary error text
   is logged. Retain failed/unobserved classifications; do not call them zero.
5. Tests execute the workflow block rather than mirroring it. They establish
   actual connection reuse, finite request count and negative cases. Local
   pacing/deadline acceleration, if needed, is confined to named test substitutions
   with exact match counts; the model's clock preserves the production window
   relationship. No existing test body is weakened or silently unregistered.
6. Fresh functional and ordinary adverse reviews pass. Run one complete final
   merged-source gate with retained source admission; reuse unchanged evidence
   and budgets. Preserve all47 configured commands, native16/clock3, raw snapshots
   and the Owner's original checkout. New exact-head CI and the normal deployment
   must pass; a failed live canary remains held, with no blind redeployment loop.

## Evidence and cost boundary

Retain actual parent red, test/fix commits, raw exits, loopback connection and
status aggregates, unchanged-body proof and independently reproduced evidence.
Keep all successful source/CI evidence from T068; its production source is frozen.
This is a small existing-instrument repair, not a new assurance workstream.
One source correction, one final complete gate and the existing release path;
new structural findings are reported separately rather than growing this task.

## Threat model

Never turn absent observation into enforcement, accept a WAF/upstream429 as the
Worker counter's response, send a valid token to a provider, leak caller data,
or relax a failing deployment predicate. Connection reuse improves locality;
it does not prove worldwide consistency or guarantee cache persistence.
