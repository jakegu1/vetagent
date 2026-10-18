---
id: T-031
title: Route discovery through the existing configured on-chain providers
status: in_progress
level: 3
size: S
depends_on: [T-028, T-030]
decisions: [D8, E11]
backlog: W28
---

## Context and goal

Tagged production readback again cannot observe either discovery listing on Base or
Solana. The precise transport cause is not available in the current generic error.
A network-blocked reproduction through the real fetch path separately proves that
new_pools bypasses _onchain_sources: with a valid synthetic configured key, usable
keyed listings and keyless HTTP 429, only the keyless provider is called and discovery
fails. This is a reproduced routing defect, not proof of the current production key
configuration or the precise live refusal cause.

Use the already approved provider route and retain truthful listing completeness.
D8 already configures optional CoinGecko followed by keyless GeckoTerminal. Current
official Demo documentation confirms both network discovery endpoints and header
authentication: https://docs.coingecko.com/demo/reference/latest-pools-network and
https://docs.coingecko.com/demo/reference/trending-pools-network (read 2026-10-18).
No new provider, account, key, paid feature or permission is part of this task.

## Scope and conflict search

Files in scope: src/risk.py (new_pools only; a narrowly local discovery helper if
necessary), tests/test_mcp.py (additive imports/helpers/test functions only).
The lead alone may regenerate docs/SCORECARD.md in a separate derived-receipt commit.
Freeze every other production function and every pre-existing test/helper/input AST.
No fetch/cache policy, configuration, schema, benchmark, scoring, telemetry, permission,
dependency, fixture or legal-text change. The existing runner discovers added tests.

Searched all tests for new_pools, _onchain_sources, configure, CG_DEMO_KEY, request
headers, RuntimeError, exact discovery errors, stale disclosure and outputSchema.
Existing T-028 tests include exact generic error equality for malformed stub listings.
No older test change is authorized. Preserve that message when no fetch diagnostic
exists; actual fetch failures may append existing sanitized provider/status detail.
All risk/finite-market/MCP/HTTP discovery handoff expectations remain compatible.

## Acceptance criteria

1. For each of new and trending independently, try the existing configured keyed
   provider first and the keyless provider only if no usable listing was obtained.
   Accept a valid empty data list without consulting a second copy. No configured or
   unusable key means the original keyless-only route. Bound choices to the existing
   two providers per listing; retain existing global fetch retries, timeout and cache
   behavior. A provider failure never prevents trying the other listing.
2. Transport failure, error bodies and malformed JSON containers/rows all cause a
   fallback before classifying a listing as failed. Validate each provider response
   atomically with the existing parser. Discard rows preceding an invalid row from
   that failed response; never merge partial rows from it into a fallback or survivor.
   Exercise both fallback directions across listing kinds and all-provider failures.
3. Preserve the complete public answer contract: listing-based sources_ok/failed,
   ok/partial, error when neither listing was observed, empty/partial-empty meanings,
   deduplication, order, chain normalization, input limits, count/scanned, usable token
   addresses and stale disclosures. Provider redundancy is not extra market coverage.
   Characterize complete unkeyed answers against the parent at the same effective time.
4. Drive the actual _fetch_json/cf_fetch path as well as MCP/HTTP handlers under bounded
   local upstreams with external networking blocked. Synthetic key appears only in the
   keyed provider's header, never URLs, keyless headers, cache keys, output, errors,
   recorded telemetry or captured logs. Actual all-source fetch failures may append
   _failure_detail for the two known providers; no raw exception/body/URL is exposed.
   Existing generic errors remain exact when no safe detail exists.
5. Commit acceptance tests alone first and reproduce behavioral red for the bypass.
   Keep them frozen. Source fix is one finding commit with the observed red in its
   message. Mutants bypassing the keyed route, stopping at malformed keyed JSON and
   forwarding the key to the keyless host each cause meaningful acceptance failures.
   Preserve all assessment/liquidity/scoring production ASTs, so this task changes no
   numerical engine behavior or committed benchmark result.
6. Freeze a clean final head and run python lead/checks.py: all configured steps pass.
   The lead regenerates the correctness receipt before this final gate if counts move;
   never hand-edit it. Report real red/final outputs, immutable old/new ASTs, mutants,
   commits, scope, and request bounds in a signed private READY. The current full runner
   still reads live Ethereum RPC; only the added acceptance is network-isolated here.

## Threat model, review and delivery

A fallback may return malformed or stale data, a valid empty market must remain empty,
and two redundant providers must not impersonate two observed listing kinds. Never
expose a credential or reinterpret transport refusal as token evidence. Do not claim
the production cause or a permanent availability improvement from synthetic tests.
The lead will compare fresh tagged production observations after deployment, and will
report any surviving partial/unobserved source explicitly.

Use an isolated executor worktree. Fresh independent and adversarial reviews are
required, at most two rounds. No production probes, merge or push by the executor.
Public repository files remain English; all raw/runtime/review evidence stays private.
The Owner explicitly authorized this technical batch and direct deployment after
quality checks. The primary checkout and its unrelated edits must remain untouched.
