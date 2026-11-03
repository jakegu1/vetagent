# Usage report storage domains

This document describes the existing usage consumer's reporting boundary. The server writer
is unchanged. The candidate `calls-v2-io` writer, collection format and standalone decoder are
not enabled by this reporter. Historical data has not been rewritten or anonymized. Preparing
this consumer does not establish deployed new-format data, acquisition completeness, new
timing measurements or full provider SQL qualification.

## Projected domains and local evidence

Interactive queries use this fixed projection as `storage_schema`:

```sql
if(blob7 = '', 'legacy-v1', if(blob7 = 'calls-v2-io', 'calls-v2-io', 'unsupported'))
```

An absent projected alias is malformed, never inferred legacy. Unrecognized projected
markers are reduced to `unsupported`; their raw values are not displayed. The physical
old-column behavior and complete provider query execution need separate qualification.
Q2, Q3 and Q4 restrict `blob7 = ''` before the original grouping, ranking and limits.
Their returned nonlegacy rows are malformed rather than eligible legacy evidence.

`external_callers`, `tool_callers`, `caller_profile` and `unattributable_calls` accept an
optional keyword-only `domain_out` dictionary. It belongs to one invocation, with entries
keyed by query ID. Metadata records the declared window, observed/empty/failed/malformed/
truncated state, normalized positive-group counts, returned group count and cap caveat before
self, country, empty-client or tool filtering. Q1 metadata includes handshake events and
survives later empty lists. A skipped profile is explicitly `not_queried`.

Valid legacy calls retain their original list/dictionary/integer shapes. Failed or malformed
replies return `None`, including profile failure. An observed empty list remains distinct.
Aggregates must be finite nonnegative numeric values. A valid zero event result ends after
Q1 and says nothing about people, natural demand or whether collection is complete.

## Query scopes and presentation

| Slots | Evidence scope | Reporting constraint |
| --- | --- | --- |
| Q1 | Original raw time window, grouped by domain | Provider event counts and recorded error flags; distinct labels/countries only within legacy, never pooled identities or availability |
| Q2 | Legacy raw-window connection labels, original limit 500 | Self-description after original filters, not unique customers or all current clients |
| Q3 | Legacy weighted tool groups after the unchanged attribution floor, limit 200 | Original eligible legacy caller inputs only |
| Q4 | Legacy profiles in the same gate window, limit 1000, only when Q3 has eligible tools | Failure cannot become a fabricated empty profile or a negative result |
| Q5 | Original weighted pre-floor complement, grouped by domain | Original evidence-base wording is prefixed as legacy-only; v2/unsupported contributions stay separate |
| Q6 | Original weighted gate-window tool predicate | Separate legacy named nonself, self, no-client, v2 and unsupported groups; compare only legacy named nonself with Q3 |
| Q7-Q11 | Raw-window top event-tool/client/country/verdict/reason groups, original combined limit 8 each | Version-scoped bounded context, not complete per-version, request or whole-ingress coverage |

Q6 uses the accepted SQL cohort predicates on the actual writer's canonical label domain.
It does not introduce SQL case/whitespace normalization or a new identity rule. A residual
can reflect caps, inconsistent groups or separate query snapshots; it is unresolved and is
never assigned to self. V2 anonymous events and no-client rows are not self evidence.

Each section displays its own failure, malformed, empty, not-queried or capped state. Valid
neighboring sections remain visible. Reaching a limit is incomplete coverage even when later
filters discard every row. V2 client/country values are excluded from identity presentation;
these dimensions are `not_recorded`, including handshake-only and capped reports. Unsupported
breakdown values are not displayed. V2 tool/status labels use finite candidate vocabularies;
reason display accepts only the bound finite heads, drivers, gap dimensions/classes and
provider HTTP status words, with `other` for any invalid component. No raw provider error
body is printed. The legacy unknown-country correction is historical, not a promise that
new rows carry a country. A legacy named demo profile cannot be inferred from a v2 bucket.

## Historical instrument and execution boundary

The original historical rule remains callable with unchanged eligible legacy inputs, its
original source, attribution floor, fixed parameters and ambiguity/self handling. Its
YES/NEAR/NO lines are labeled as a legacy segment, including a bounded subset when capped.
No legacy domain or unavailable caller/profile evidence means no historical evaluation.
Current adoption is always `not_evaluated`; the interactive report issues no new strategy
directive. Legacy label cardinalities do not measure current people or customers.

Request order, transport and timeout are unchanged: no credentials means zero requests;
Q1 empty/failure means one; nonempty reporting uses ten slots without eligible legacy tools
or eleven with their existing profile slot. There is no retry, fallback probe or metadata
request. Interactive exit is 2 for missing credentials, 1 for a failed, malformed, capped
or unsupported report section, and otherwise 0. Success describes the returned evidence
only. The production verdict function and its three weighted seven-day queries, only-CI
exclusion, floors and bands are unchanged and use their original separate exit behavior.

Focused synthetic verification does not establish independent source acceptance, complete
SQL runtime qualification, full checks, CI, production collection or publication readiness.
