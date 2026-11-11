---
id: T-086
title: Validate sell evidence before assessment and retry substitution
status: in_progress
level: 3
size: S
base: d5a737b17f91c498c4cf2c1f8d9425d887670ef6
depends_on: [T-085]
---

The market substitution check already rejects incompatible simulator evidence.
The common scoring path can still report a normal sale with that evidence.

1. At the real REST and MCP entry points, explicit wrong token or chain, missing
   completion or buy/sell tax, and contradictory success/error cannot support
   a normal-sale signal or a low verdict. Missing optional identity fields in
   older responses do not by themselves invalidate a scoped request. Keep
   unavailable evidence distinct from a token that was observed to be unsafe.
2. Apply the same check to an eligible single retry, checking explicit venue
   evidence against the requested pool. A wrong or incomplete retry cannot
   overwrite the first simulation failure. A clean matching retry still works.
3. Keep the holder evidence and report a sellability gap when a successful
   single sale conflicts with reported siphoning, all sampled holders failing,
   or the existing adverse holder-share band. Keep the existing interpretation
   of a matching honeypot flag and correctly observed extreme taxes.
4. Replay primary and fallback market fixtures plus archived simulator cases.
   Run the registered offline suite and independent and adverse review.

Scope is src/risk.py and regression tests in the existing risk and HTTP test
suites, with separately generated test counts if needed. Reused simulator
fixtures must actually describe the requested token, chain and retry venue
in tests that expect a successful check. No new upstream or retry schedule.
Threats include wrong-asset caches, contradictory vendor evidence, partial
success payloads and a retry that returns the default venue instead.

Named fixture updates remove the archived subject only from tests deliberately
reusing simulator mechanics with a synthetic subject. Preserve assertions in
the retry, holder-share, contested seller, pool-ID, tiny-price, freshness,
namesake, keyed fallback, clean-score, outage, and reserve disclosure cases.
The dedicated Worker regressions retain explicit identity fields.
