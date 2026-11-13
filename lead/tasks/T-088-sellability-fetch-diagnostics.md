---
id: T-088
title: Retain the final sellability fetch diagnostics
status: ready
level: 1
size: S
base: 2b14c3cf537ec7b5a07fea1903e88bef6ef343b5
depends_on: []
---

The day-one sellability collector receives the final HTTP status, bounded
error category and number of attempts from the fetcher. Its archive drops
those fields, so a later reader has only the coarse outcome.

Scope: `bench/snapshot.py` and the existing registered
`tests/test_sellability_archive.py`. No changes to request selection, retry
budgets, classifications, existing records, runtime routes or workflows.
Search found no existing assertion to change.

1. Store the final status, category and attempt count in optional
   `fetch_diagnostics`. Distinguish a final 404, a 404 after a retry,
   a transport failure, an invalid JSON response and a received JSON null.
2. Keep the diagnostics on invalid-payload fallback, with only fixed error
   names and bounded numbers. Absent diagnostics stay absent. No raw body,
   URL or free-text error enters the new field.
3. Keep archive prefixes, timing, reader compatibility and attempt accounting.
   The two new tests must fail on the old source and pass on the fixed source.
   Run the configured offline checks and obtain an independent review.
