---
id: T-074
title: Scope usage reports to observed storage domains
status: ready
level: 3
size: M
base: lead_adoption_commit_pinned_in_dispatch
depends_on: [T-069, T-072]
decisions: [preserve_existing_usage_rule_and_no_new_collection]
---
## Goal, value and stop

The existing usage consumer reports old/new/unknown domains without converting anonymous
groups, missing metadata or empty filtered lists into a current adoption conclusion. It keeps
the old instrument callable on its unchanged eligible legacy inputs and preserves the production
score calculation. This is useful repair/preparation of a current consumer, not standalone P0.
Cost: one bounded reporting slice and independent review; stop before collection, new codec,
SDK, account access or speculative v2 decoder. No new Owner schema/privacy choice is needed
to prepare this code; root's normal implementation/release authority remains required.

## Files in scope: three

1. `bench/usage.py`, domain projection/metadata and all interactive CLI branches only.
2. `tests/test_usage_gate.py`, additive U01-U20 acceptance cases and the two named SQL-fixture
   metadata additions named below; no old assertion/value change.
3. New `docs/TELEMETRY-CONTRACT.md`, technical legacy/current-domain semantics and the explicit
   not-enabled candidate; no public legal/privacy wording or new metric/adoption claim.

No entry/risk/MCP/writer/config/workflow, gate parameter, production function, new test file,
source-freeze or data change. test_usage_gate is not among the three generated scorecard
suite-count inputs; do not edit SCORECARD absent a concrete generated dependency returned to root.

## Acceptance criteria: eight

1. Tests first alone. Add automatic `test_a3_usage_summary_and_early_returns`,
   `test_a3_usage_main_domain_matrix`, `test_a3_usage_secondary_states`,
   `test_a3_usage_reconciliation_and_tail`, `test_a3_usage_frozen_inputs_and_query_budget`.
   Actual main() is driven by stub replies/credentials/argv, never live query(); retain
   meaningful parent reds for wrong current NO/zero/strategy output and request counts.
2. Implement the exact normalized domains and per-query metadata in the normative matrix below.
   Validate projected marker before filtering/formatting; missing alias is malformed, unknown
   raw marker is unsupported without reflection. Q1 domain survives handshake-only, empty
   legacy tools and self filtering. Keep old public return shapes plus None failure semantics;
   optional domain_out is local, not global state. Original valid legacy values/results stay.
3. U01-U11 cover every primary domain, summary/cardinality/zero-return and historical-rule
   branch. No v2 cardinality/user/country0 or current STRATEGY directive; no raw failure JSON
   or auto-probe instruction. Historical legacy rule remains reachable, exact and explicitly
   scoped; a mixed/v2/unknown domain cannot supply or negate customer evidence.
4. U12-U18 keep failed/malformed/empty/not_queried/capped distinct for every secondary consumer.
   Never use `prof or {}`, `len(ext or [])`, `rows_of(...) or []` or equivalent to manufacture
   absence from failure. Valid neighboring sections remain visible; native exit matches the
   specified0/1/2 contract. Profile skipped for zero eligible tools is not queried evidence.
5. U19-U20 reconcile legacy named/self/no-client, v2, unsupported and residual/cap uncertainty
   over the correct gate window. V2/residual is not declared self. Final connected-client,
   landing-demo, country correction and five breakdown sections follow their exact domain
   contract; no blanket new-country promise, exact unique-customer or whole-ingress claim.
6. Record exact ordered query() traces:0 without credentials;1 on interactive primary
   empty/failure/missing alias;10 without eligible legacy tools;11 with them; profile consumes
   the existing slot only. Keep all original limits/timeouts, no retries or extra metadata
   query. Production mode remains original3queries (or1 if primary fails), byte-exact function.
7. Freeze literal old rule/source/parameters/floor/production exclusion and100/7/bands.
   Original fixture values/assertions and automatic main stay exact except the two named
   alias additions. No hash renewal substituted for the U-matrix or a new decision rule.
   Docs distinguish prepared reporter from enabled schema; no Analytics acquisition is implied.
8. **Contract and checks.** Root-assigned base contract check, focused usage guard and later
   exact-source full/applicable CI, fresh functional/privacy review and integrated validation
   before root release. READY contains actual reds/exits/traces/scoped diffs and failures;
   no author self-acceptance, unassigned tests/heavy/API reads, push or deployment.

## Evidence and DoR

The normative matrix below is the exact behavior/fixture table. Keep all original deciding functions
reachable; old static string guards are not replaced, and new actual-main assertions test the
seam they cannot see. Root prepares bounded SQL qualification under a separate exact read plan;
unqualified provider replies fail closed. It is a technical experiment, not an Owner SDK choice.
This spec is design-ready for independent review, not implementation-dispatched here.

## Root adoption and execution boundaries

The lead adopts the bounded existing-consumer slice after independent functional
and privacy design review. The new server writer and standalone codec remain
out of scope. Root dispatch pins the commit containing this task as the tests-first
base, not its parent; the code basis is published9b83558481ae54afd5fc4e9b59c9cb27caa0e3d6.
No new test command or workflow change is needed: the existing automatic usage
runner remains registered. Preserve T069/T070 APIs and all original test runners.

The first executor phase ends at TESTS_AND_SQL_READY: acceptance tests alone,
meaningful unchanged-parent reds, preserved old tests, and exact proposed SQL for
Q1-Q11. Do not implement source changes until the lead accepts those exact SQL
projections. Use only fixed local stub replies and dummy credentials. Any unmocked
network operation must refuse; do not query account, product or providers. No
subprocess/native/full benchmark, full gate, collection, probe, push or deployment
is authorized by that phase. Later full acceptance still needs a separately
reviewed incident-admission binding and exact source slot. Retained T073 failures
and quarantines are not cleared by this task or its source branch.

The approved domain projection expression is exactly:

```sql
if(blob7 = '', 'legacy-v1', if(blob7 = 'calls-v2-io', 'calls-v2-io', 'unsupported'))
```

Use it as storage_schema in all designated projections. Restrict legacy Q2/Q3/Q4
with blob7 = '' before the original ranking and limits. Do not reflect raw blob7.
The lead has separately checked this expression on existing aggregate data; this
does not qualify the complete report or a real new-format positive. Preserve all
original per-slot time/weight/order/limit expressions except exact changes stated
in the normative matrix. Root must accept the complete new SQL before source fixes.
Production production_verdicts, its three queries and its failure behavior stay exact.

### Exact named existing-test changes

Only the following later changes are permitted, in separate correctly prefixed
T-074: named change commits. The first acceptance-test commit adds new tests only.

- NC1-A: test_connecting_is_not_using in tests/test_usage_gate.py: add
  storage_schema: legacy-v1 to each synthetic SQL reply row, without changing
  names, calls, days, tools, ambiguity, assertions or helper behavior.
- NC1-B: test_the_evidence_base_is_never_silent: add the same alias only to its
  nonempty successful reply with n260. Preserve failure None, valid-empty0,
  successful260 and all existing evidence_base_lines assertions.

No other old assertion, helper, function or automatic runner is editable. An
unexpected conflict is a concrete BLOCKED result for the lead, not permission to
change a test. Protect original production_verdicts, gate_verdict, RULE_TEXT,
GATE_FROZEN, ATTRIBUTION_FIXED, OWNER_COUNTRIES, AMBIGUOUS_CLIENTS, is_self and
gate_window byte-for-byte. Characterize their exact existing values and source.

### Threat model and completion evidence

Failures, malformed/missing schema, truncation, unsupported versions, handshakes,
self filtering and empty tool lists must not turn into customer absence, a current
adoption verdict or an invented identity. Provider error text and unsupported
markers must not be printed. Known valid neighboring sections remain visible.
The two version domains must not pool client/cardinality/country meanings, and
interactive raw counts must not replace the frozen weighted production rule.

READY requires tests-only/fix/named-change SHAs, actual parent RED and candidate
GREEN originals, exact query traces and fixed source-preservation evidence,
contract output, independently reproduced functional/privacy review and later
actual source/integrated/full/CI evidence. No missing stage is a pass. The new
retention scheme uses shared compressed source baselines and small manifests,
not permanent whole-source copies. No T047/T049/T050/T068, old research source,
window, label, threshold, receipt, caller rule or permission change is authorized.

## Normative query, domain and CLI matrix

# Normative query -> domain -> CLI transition (F2)

Applies to the current interactive `bench/usage.py` at9b, not the frozen production-verdict
writer mode. No extra live query is added. This is a proposed reporting contract, unimplemented
and untested. No account query or CLI was executed in this design.

## Domains, metadata and original function compatibility

Normalize physical suffix only in a root-qualified projection: old absent/empty b7 ->
`legacy-v1`; exact new marker -> `calls-v2-io`; every other marker -> `unsupported` without
retaining its raw value. A **missing projected storage_schema alias is malformed**, never
legacy. Actual old-column behavior is unqualified; root's finite qualification is separate.

Each query has request-local metadata before client/self/empty filtering:
`query_id`, declared window kind/bounds, state(observed/empty/failed/malformed/truncated),
normalized domain presence/counts when supplied, and cap/coverage caveats. Do not replace Q1
metadata with a later empty tool/profile list. Q1's full raw window detects v2 even for only
initialize/ping/notifications. Keep gate/pre-floor windows separate from the raw window.

Keep original callable signatures compatible through an optional keyword-only `domain_out`
request-local dictionary, keyed by query ID; no global side channel. Main passes it, direct
historical tests may omit it. Capture metadata first, then retain original legacy filtering.
external_callers/tool_callers return list or None on failed/malformed; caller_profile dict or
None; unattributable_calls legacy count including0 or None. A failed query is not []/{}/0.
Missing alias is rejected regardless of whether domain_out was requested. Original frozen
gate_verdict/RULE_TEXT/GATE_FROZEN/ATTRIBUTION_FIXED/OWNER_COUNTRIES/AMBIGUOUS_CLIENTS/is_self/
gate_window and production_verdicts remain byte-exact. No new cutoff/floor or threshold.

## Every existing interactive request slot

Same query() transport/call budget/timeout, no retry or new schema-discovery request. Projection
changes must be bound to exact SQL by root before implementation, keeping the original time,
eligibility, limit and weight expressions unless the explicit domain restriction below applies.
SQL dialect/old-column behavior is a finite qualification, not assumed by these documents.

| Slot and existing source | Projection/domain metadata, before filtering | Exact CLI consumer / failure behavior |
| --- | --- | --- |
| Q1 main:679 raw-window summary | Group existing count(), sum(double2), distinct client-label and country expressions by fixed storage_schema; <=3 normalized groups. Record domains from all positive groups, including handshakes. Keep raw count/error totals separate from weighted gate counts | Replace Total calls with provider-reported event count, not requests/users; errors are recorded event flags, not availability. Distinct client/country numbers are **legacy-only declared-label cardinalities**, never summed across versions or reported for v2. If failed/missing alias/malformed: fixed diagnostic, all totals unknown, exit1 after this sole query; no raw response print |
| Q2 external_callers:200 raw window | Restrict to legacy before the original grouping/order/LIMIT500, project alias, record state/cap before original own/country filtering. Do not let v2 groups displace legacy rows in the old limit | Display legacy connection labels only, labeled self-description and raw-window scope, never unique customers or all-version connected clients. Failure -> unavailable section, not len(None or [])=0 |
| Q3 tool_callers:243 gate_window(since) | Restrict to legacy before original grouping/LIMIT200; retain domain metadata before client-empty/self/tool filtering. Preserve original legacy n/days/tools/ambiguity results. Missing alias -> None/malformed | Only its eligible legacy list may feed the historical rule. Empty list cannot erase Q1 v2 presence; capped list is a bounded subset with a warning, not complete caller coverage |
| Q4 caller_profile:296 gate window, only if Q3 eligible list nonempty | Restrict to legacy before original client-list/time/verdict/country/method grouping/LIMIT1000, require alias, preserve source fields and existing country handling. State and cap remain separate | Profile failure -> no historical result, no current NO. Valid empty result stays empty observed evidence, not query-failed. Profile skipped when Q3 empty is not_queried, not an observed current0 |
| Q5 unattributable_calls:164 pre-floor complement | Keep original timestamp complement/tool/weight expression, group by fixed storage_schema. Return only recognized legacy count to the old helper; retain v2/unsupported pre-floor counts separately, never guessed legacy | Prefix evidence_base_lines with `Legacy-domain attribution-floor evidence only`. Failed/malformed -> helper(None), not0; extra domains stay separate. Do not reinterpret all new anonymous rows as pre-fix/self traffic |
| Q6 main:806 gate-window tool reconciliation | Same original nonempty/non-?/non-__ tool predicate and sum(_sample_interval), now fixed groups: legacy_named_nonself, legacy_self, legacy_no_client, v2, unsupported. All branches derived from fixed domain/cohort predicates, no new identity field | Show recognized categories separately. Compare legacy_named_nonself with sum(Q3 legacy attributed n); residual is capped/inconsistent/unexplained, **not automatically ours**. v2 is anonymous, not self. Failed/malformed -> reconciliation unknown; do not coerce to0 or emit the old only-self explanation |
| Q7 main:843 loop `By tool` | Existing raw-window count(), group by schema plus tool; same LIMIT8 across returned groups. Metadata/cap retained; no schema group is a unique request | Show version-scoped top event-tool labels; mark limited scope. Never infer whole chain/request coverage |
| Q8 loop `By client` | Same slot, schema plus client grouping and cap. No new query; v2 values discarded from identity presentation before formatting | Legacy declared-label context only; v2 identity not_recorded. No v2 blank/own bucket counted/displayed as a distinct client, and no all-version unique-client summary |
| Q9 loop `By country` | Same slot, schema plus country grouping and cap | Legacy country context only, with old pre-fix unknown caveat. V2 country not_recorded; replace `rows from today carry a country`, never show current0 countries |
| Q10 loop `By verdict` | Same slot, schema plus verdict, original count(), same cap | Version-scoped event verdict/status counts only. This is not the production score calculation; do not substitute its raw counts for sample weights |
| Q11 loop `Why unknown` | Same slot, schema plus reason, original count(), same cap | Version-scoped bounded reason context; unknown/malformed/query failure is not empty/no-reason. New-format values must satisfy its finite grammar; never print a raw provider error or opaque unsupported marker |

Full main's existing final loop is five executions of the same query call site, not one.
Q2/Q3/Q4 legacy restriction preserves legacy ranking inputs; Q1 supplies all-version presence.
Q5/Q6 explicitly reconcile separate domains rather than adding another counting rule.
Q7-Q11 may return only a top subset; no per-version completeness or absent-category conclusion.

## Request count / exit contract, not newly executed evidence

| Mode/path | query() count and order | Exit / meaning |
| --- | --- | --- |
| Missing credentials |0 |2, unchanged; no metric/query claim |
| --write-verdicts, primary succeeds |3 original production queries in original order | Existing behavior unchanged, including absent breakdowns on reason-query failure; no interactive domain instrumentation |
| --write-verdicts, primary fails |1 |1, unchanged |
| Interactive Q1 valid-empty |1 |0, descriptive empty query only; no probe command or nobody-uses/write-broken conclusion |
| Interactive Q1 failed/malformed/missing projected marker |1 |1, fixed unavailable diagnostic, no raw response; no other requests |
| Nonempty report with eligible legacy tools |11: Q1,Q2,Q3,Q4,Q5,Q6,Q7..Q11 |0 if all observed/empty and schema known; otherwise1 for a failed/malformed/truncated/unsupported section. Every failure stays explicit |
| Nonempty report without eligible legacy tools (including v2-only handshakes) |10: Q1,Q2,Q3,Q5,Q6,Q7..Q11 | Same exit policy; Q4 skipped, not an extra fallback query |

Existing zero-row native0 remains a successful empty read, not positive collection health.
Intentional v2 identity not_recorded does not itself make exit1; unsupported/missing metadata
is a partial/invalid result. Do not rerun a query to obtain a preferred domain or fill a gap.

## Complete domain / branch matrix and acceptance fixtures

`current_adoption_conclusion` is **not_evaluated** in every row. The unchanged historical
rule may still print its exact YES/NEAR/NO lines, under the explicitly labeled legacy segment,
when its legacy inputs are observed. No `-> NO/YES. STRATEGY` / no-features / distribution-not-
product instruction is emitted from this new mixed-era report. Actual D remains separate.

| Fixture / Q1 domain | Total and unique/country headings | Historical rule / early branch | Reconciliation and final explanation |
| --- | --- | --- | --- |
| U01 legacy-only, eligible callers | Known event totals; legacy label/country cardinality only | Call original gate_verdict(tools,prof) with exactly original eligible legacy inputs; label its window and floor, not a new roadmap decision | Legacy self/no-client/residual categories; final client/country explicitly legacy, no blanket new-country promise |
| U02 legacy-only, handshakes or pre-floor-only | Same scoped summary | Eligible list may be empty: original rule on observed eligible empty legacy segment may be NO, labeled as such. Never current adoption/STRATEGY NO; Q4 skipped | Floor/complement and connected/tool windows stay distinct; no claim no external person used it |
| U03 v2-only, tool rows | Event totals/error flags; current identity/country not_recorded, no cardinality0 | No legacy segment to evaluate; no current NO;10queries | V2 weights shown as anonymous, not self/unattributed legacy. No final named-caller/country claim |
| U04 v2-only, **handshake-only** | Q1 still proves v2-domain presence before tool filtering | Empty Q3 does not reset domain; Q4 skipped; no zero/nobody-used/NO branch;10queries | Handshake events are not tool-use; missing identity remains not_recorded even with nonzero traffic |
| U05 mixed legacy+v2, legacy eligible | All-version event totals separate; only legacy cardinalities, explicitly non-comparable current identity | Historical rule only legacy; no pooling days/verdicts/names with v2;11queries | Separate v2 cohort and legacy residual; old only-self prose removed |
| U06 mixed, zero eligible legacy tools | Same scoped totals | Never `NO. No attributable client... -> STRATEGY`; eligible legacy segment only may be empty, not evidence for current identity;10queries | V2 may contain real tool events; do not call them ours or merely connected |
| U07 valid-empty (data:[] or qualified zero groups) | Observed empty event result; identity and collection completeness unknown, not0 users/countries | Single-query early return0; no curl/probe instructions, no write-path diagnosis and no adoption verdict | No reconciliation or later summaries were queried; say not_queried |
| U08 Q1 query-failed | Null totals/identity; fixed query_failed, no raw JSON/body | Single-query return1; no historical/current result | All later sections not_queried |
| U09 Q1 missing projected marker alias | Malformed, null totals; never guess legacy based on old-looking fields | Single-query return1; no historical/current result | All later sections not_queried |
| U10 unsupported-only marker | Known event counts in unsupported domain, identity/semantics unavailable; raw marker never echoed | No legacy result or current NO; normal10-query schedule, partial exit1 | Unsupported weights cannot be called ours, legacy, v2 or valid new schema |
| U11 legacy/v2 plus unsupported | Known groups and unsupported counts separated; no all-domain unique claim | Only fully valid legacy inputs may yield labeled legacy result; current scope unavailable, partial exit1 | Unsupported contribution separately unknown; no complete reconciliation claim |

Every row retains Q1 metadata through the zero/empty/self filters and final output. Q1's
empty state means no query records in this window; it cannot determine collection completeness
or natural demand. No synthetic request is recommended to turn empty into nonempty.

## Secondary failure, truncation and reconciliation fixtures

| Fixture | Required branch/output, using the same request budget |
| --- | --- |
| U12 Q3 failed/missing marker | tools=None plus its failed/malformed metadata; Q4 skipped; historical result unavailable, not NO; Q1 domain retained; partial exit1 |
| U13 Q4 failed/missing marker | prof=None, never prof or {}; do not invoke frozen gate on fabricated empty profile; partial exit1, all valid other sections remain visible |
| U14 Q2 failed | Legacy connections unknown, never len(ext or [])=0. Does not erase valid Q3/Q4 legacy subset evidence; overall partial1 |
| U15 Q5 failed/missing marker | evidence_base_lines(None) under legacy qualifier; floor count unknown, no silent0; do not assert full eligible coverage |
| U16 Q6 failed/missing marker | Reconciliation unavailable, not0 gap, no only-self explanation; valid sections retained, partial1 |
| U17 any Q7..Q11 failed | That breakdown unavailable, no `rows_of(resp) or []` absence claim; other breakdowns visible, partial1 |
| U18 secondary missing projected marker in a nonempty old-shaped row | Malformed at that query, not inferred legacy. Valid empty reply remains empty. Never feed unqualified metadata to a gate or unique/country count |
| U19 legacy self + legacy no-client + v2 + unsupported + attributed legacy | Print each category. Residual=recognized legacy_named_nonself minus Q3 attributed; if not reconcilable/capped/different snapshots, label unresolved. Never assign v2/no-client/unsupported/residual to self |
| U20 limit reached / inconsistency | State cap/unknown coverage at original500/200/1000/8 bounds; no silent exhaustive distinct-caller/breakdown claim. Keep historical rule function exact on its explicitly bounded observed legacy subset, current conclusion unevaluated; no new threshold or retries |

The final landing-demo paragraph can only describe the unchanged named legacy demo profile;
the v2 merged self bucket is not a click count. The final connected-client list is legacy
raw-window context, never all current clients. Original unknown-country correction remains a
historical explanation, followed by the explicit new-format country-not-recorded statement.

## Preserve what is frozen; change only the report meaning that actually changed

The original rule text/function/parameters/floor, original historical fixtures, production
seven-day denominator and only-CI exclusion are not rewritten or hash-renewed. Domain metadata
and each branch above demonstrate the actual transition; a header notice alone is insufficient.
Keep original function calls reachable from main on the legacy branch, including the literal
gate_verdict(tools, prof), tool_callers and external_callers source guards. No dead-code bypass.

Only two old SQL fixtures need added projected metadata (see the exact named changes above);
their old values and assertions stay. New U01-U20 fixtures exercise actual future main output,
ordered query() calls and native returns with stubbed replies, not merely search for strings.
These are acceptance requirements. None was executed in this design revision.

## Amendments

### NC2: capped report evidence must explicitly return partial1

The first tests-only stage leaves all original assertions intact and produces
meaningful parent failures. Its four existing U20 cap fixtures check warning
text and ordered query slots but omit the required native return value. This
would let a future implementation describe incomplete evidence while returning
success. The original first RED remains retained; it is not rerun or relabeled.

Permit exactly one new assertion in test_a3_usage_reconciliation_and_tail,
inside the existing for slot, bound loop after name = "U20-%s" % slot and
_t074_show(name, result), before the existing cap-warning check:

```python
check("T074 %s returns partial1 for capped evidence" % name,
      result["value"] == 1, str(result["value"]))
```

Do not add or change a fixture, input, vector, helper, old check, order or runner.
The assertion applies to the existing Q2/Q3/Q4/Q8 cap cases. Their saved actual
parent traces return0, which supports a meaningful RED premise; it is not an
execution of this added assertion. Commit this change alone with the exact
T-074: named change (NC2 cap partial exit) prefix and retain one new actual parent
RED in a separate evidence directory. Count it against the original first-stage
focused limit; do not reset that ledger or replace its first result.

The lead separately accepts the proposed Q1-Q11 SQL for implementation after
independent static review, preserving their exact templates and stated deltas.
Q6 cohort classification is scoped to the valid canonical labels produced by
the existing writer; synthetic noncanonical labels do not establish historical
incidence or authorize changing the frozen caller normalization. No new SQL
execution or full-provider/dialect qualification is claimed. Before any later
source fix, this exact NC2 correction and its actual RED must be reviewed by
the lead. All previous full/heavy, collection and source-domain holds remain.

