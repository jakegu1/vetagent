---
id: T-045
title: Preserve prospective enrollment and independently replayable paired evidence
status: ready
level: 3
size: M
backlog: W40 prerequisite only
design_base: cd58311
decisions: [B1, B2, B11]
---

## Goal, cost and stop rule

Implement the offline evidence contract that a later live W40 collector must satisfy.
Freeze candidate selection before outcomes, retain birth and observation clocks, and
make incomplete paired evidence auditable instead of losing unlabelled rows. This is
ordinary authorized engineering, not a new source or experiment-policy decision.
All commands and tests cost zero vendor requests. Stop at reviewed integration of
this core. It does not start a study, schedule live work, establish API capacity,
rebuild the benchmark or answer W40. The separate live-driver/runtime task remains
engineering work, not a calendar wait or an assumed Owner approval blocker.

Experiment C's publication dependency is already met. The original W40 conditions
remain T+24h from pool birth, at least USD 5,000 when labelled, a same-time engine
answer and reserve/timestamp evidence, a thirty-day readout and at least eighteen
unique unsafe tokens. Preserve missingness, actual skew and source independence;
do not invent an approved lateness tolerance or reinterpret first-seen as birth.

## Scope and conflict search

Exactly two implementation files, disjoint from T043 and T044:

1. New bench/w40_evidence.py: offline plan/enroll/ingest/report functions and CLI,
   using only stdlib and unchanged existing label helpers. No HTTP or engine runner.
2. tests/test_dataset_replayable.py: exactly seven named additive acceptance
   functions before main(), with helpers/imports nested inside them. Commit these
   additions alone first. Preserve every existing byte, assertion and runner.

Existing source searches found no prospective W40 collector. build_dataset.label_one
filters away unlabelled rows and lacks paired reserve/engine/timing evidence; do not
invoke it. snapshot preserves pool_created_at, seen_at and optional fetched_at;
these clocks are distinct. labels.goplus_label has a first-result fallback, so validate
the exact requested result before calling it. Preserve its recent-volume rule and
outcome helper's age behavior. The GT single-pool endpoint is also read by the engine;
retain role/endpoint overlap rather than hiding it or claiming independence.

The containing test file's existing dynamic main already runs every test_ function
through the unconditional ordinary CI step. No new registration or workflow change
is necessary. Existing stored-subset/replayability assertions, benchmark endpoint
intersection checks, oracle exclusion from production, T043/T044 tests and all
workflow/deploy guards remain exact. If another old assertion conflicts, stop for a
named lead amendment before changing it.

Out of scope: src/, labels.py, fetcher.py, build_dataset.py, benchmark runner, current
dataset/results/cache/access log, existing snapshots, public figures, any live HTTP,
engine execution, scheduler, source/key/package/paid plan, permissions, legal text,
label rules, bands, bars and benchmark rebaseline. No network call, even to production,
belongs in this executor task.

## Acceptance criteria

1. **Offline source-bound plan.** Default/help and all four commands make zero vendor,
   engine or GitHub calls. Bind source commit, rule/source hashes, schema and declared
   append-only archive prefix/file hashes. Verify raw row references before resolving
   identities. A plan is not_started; neither plan creation nor an old dataset or
   T044 receipt can start the thirty-day clock. Public outputs contain ordinals,
   fixed categories and hashes, never addresses, URLs, arbitrary upstream prose,
   credentials or raw engine answers.

2. **Prospective fixed enrollment.** Process declared source rows in original order
   with stable file/line/raw-byte references and a supplied prospective enrollment
   boundary. No labels, verdicts or later reserve values influence enrollment.
   Normalize only existing supported EVM chains/addresses. Derive target_at from
   pool_created_at plus twenty-four hours. Preserve seen_at, optional fetched_at,
   ingestion UTC and their availability/provenance independently. Invalid, naive,
   future or contradictory clocks are explicit gaps. A target already past at
   enrollment is missed_before_enrollment, never retroactively fresh. Deduplicate
   chain/token using the first enrolled pool; retain later source observations and
   counts without replacing that pool after a result. Count unsupported, duplicate,
   missed, invalid and bounded-cap omissions with fixed reasons.

3. **Bound paired evidence.** Ingest only packets for an already enrolled ordinal
   and exact plan/source. Preserve raw bytes/hashes and actual request/response times
   for at-label reserve, contemporaneous OHLCV, GoPlus and the frozen verbose engine
   answer/context. Bind enrolled pool, reserve pool, oracle token, engine-selected
   pool, engine source/hash and study context separately. Missing raw material is
   unavailable evidence; a mismatched hash/identity/parse is invalid evidence. Neither
   is reconstructed from a final verdict or current cache. Raw data require an
   explicitly supplied private directory outside every Git worktree and outside the
   safe output tree; CI must refuse raw retention before writes. No raw bytes leak
   through errors, report, console or safe manifests.

4. **Unchanged labels and availability.** Validate HTTP/API envelope and exact
   requested-result identity before replaying unchanged goplus_label. Retain its
   returned/null/error availability separately from HTTP and finite-field coverage.
   Obtain recent volume only through validated saved contemporaneous OHLCV and the
   unchanged existing helper; malformed, failed, empty or nonfinite series cannot
   become observed zero. Preserve B11 and all existing label/age conditions.
   Below-floor reserve, unobserved reserve, null label, engine unknown, 429, other
   refusal, timeout, invalid body, not_asked and interrupted intent stay distinct.
   Unknown never votes safe, unsafe or an observed negative.

5. **Observable timing and independence.** Report actual age/lateness at label and
   the reserve/oracle/engine time ranges and skew. Do not manufacture an exact or
   tolerated T+24h/simultaneous claim. Keep pool mismatches visible. Record nonempty
   normalized label and engine endpoint sets and their actual intersection. A missing
   set means independence_unobserved; an intersection means independence_failed.
   Sharing eligibility/selection data with the engine is separately disclosed and
   cannot silently erase an overlapping label endpoint. No B1 exception or benchmark
   accuracy conclusion is adopted.

6. **Bounded immutable persistence and readout.** Persist enrollment and receipt
   intents/commits incrementally with parent/raw hashes and an atomic small index.
   Refuse existing conflicting receipts, source drift, overlapping writers and live
   resume. An interrupted write preserves previous committed evidence and exposes
   uncertain intents; a repeat import cannot overwrite history. Before parsing,
   bound each input row at 64 KiB, each raw field at one MiB, each paired packet at
   four MiB and each safe report at one MiB. Bound one plan to ten thousand unique
   enrolled ordinals; this operational cap is not a provider allowance or scientific
   success bar. Disclose capped/unexamined source rows and no hidden truncation.
   Account for every enrolled ordinal and skipped/missed/unasked denominator, including
   zero denominators. Without separately supplied validated live-start evidence print
   not_started; before start plus thirty days print not_due. An imported start receipt
   is a declared external observation, never proof the core itself ran live work.
   Show the original eighteen-token target and qualified observed count without
   automatically declaring success, changing the benchmark or publishing a claim.

7. **Tests first and exact scope.** Add only the seven functions below. Use synthetic
   archive rows, raw packets, fake clock and isolated private temporary directories.
   No real network, sleep, engine execution or benchmark writes. Preserve the actual
   containing runner contract and every old byte. Demonstrate parent missing-module
   red, freeze tests thereafter, record exact source/command/native exit/log hashes,
   and at most three controlled mutants: birth replaced with first-seen, failed oracle
   promoted to unsafe, and overwriting a prior committed receipt. Protect dirty bytes;
   use controlled in-memory mutants or external copies and restore exact source.
   Focused checks precede one root-granted globally exclusive complete inventory.
   Fresh independent plus adversarial review and actual Linux checks precede merge/
   publication. A green offline core supplies no live/calendar observation.

## Named tests

- test_w40_plan_is_offline_source_bound_and_not_started
- test_w40_enrollment_uses_birth_utc_and_never_selects_after_results
- test_w40_paired_packet_preserves_raw_sources_times_and_identities
- test_w40_label_replay_preserves_existing_rules_and_observation_states
- test_w40_timing_and_endpoint_overlap_never_become_passes
- test_w40_partial_history_is_append_only_private_and_recoverable
- test_w40_readout_keeps_original_calendar_bar_and_every_denominator

## Later runtime gates, explicitly not delivered here

The actual T044 pilot/readout, bounded live scheduler/driver, working native engine
adapter, at-label source acquisition, cross-run durable restoration, explicit live
start and thirty elapsed days remain separate steps. The four daily snapshot passes
are discovery observations, not a T+24h timer. Existing parseable pool birth timestamps
are sufficient for queue engineering; missing per-row fetch timestamps remain gaps.
Only actual new spending/source rights, changed origin/eligibility/bars/independence
policy or publication under the Owner's name requires a new Owner decision. Do not
turn routine implementation or source parsing into an approval wait.

## Named fixture clarification

2026-10-19 (a): the executor's positive synthetic imports correctly encounter the
production raw-retention guard on a CI host, and the default local temporary folder
may itself be inside an unrelated Git worktree. Do not weaken the source guard or
change an assertion to accommodate either environment.

Permit only the nested Fixture.__enter__/__exit__ helper inside the first new
test_w40_plan_is_offline_source_bound_and_not_started function to temporarily patch
CI and GITHUB_ACTIONS to empty values for its synthetic fixture lifetime, restoring
both exact prior values in finally/exit. The existing explicit CI-refusal test must
still override those values to true and exercise the real rejection. This is bounded
test-environment simulation for fake raw packets, not permission to change workflow,
generator or real runtime environments to bypass a guard. Preserve every assertion,
input, old byte and all other acceptance-function bodies. Commit the named helper
adjustment alone with its original platform failure evidence. The normal CLI still
honors actual CI flags and refuses raw retention before writes.

For local execution use process-only TMP/TEMP in a real external non-Git temporary
folder, recording that path in private evidence rather than hardcoding it in the
repository. Linux uses its actual ordinary temporary directory. Neither platform
fact is evidence that private raw output may be nested in a Git or safe-output tree.

## Named first-review correction

2026-10-19 (b): independent and adversarial review of
b9a5178954ea9d0873c99229d0d1b25c42bafbff reproduced four evidence-integrity
classes despite its actual forty-two-step local gate passing. Hold that source.
Correct all four in one bounded second implementation round; preserve every
original policy, helper, source, floor, date, band and independence rule.

Commit acceptance regressions alone before repairs. Append exactly one new
self-contained nested block at the end of each of the following four existing
new acceptance functions. Preserve every earlier statement in its original order,
all other function bodies, all original module/main bytes, and all seven function
names. Record a mechanical byte/AST comparison after removing only these blocks.

1. test_w40_enrollment_uses_birth_utc_and_never_selects_after_results:
   exercise real plan -> enroll -> report and actual CLI with a valid row, a row
   whose chain is an array or object, and a later valid distinct row. Malformed
   bounded JSON is counted as invalid_row and processing continues; it cannot
   abort enrollment or lose the later valid row. Add the separate delayed-first-
   enrollment case with an earlier selection boundary, birth October 1, target
   October 2 and first immutable ingestion October 3. With no earlier bound
   enrollment intent, it is missed_before_enrollment. A caller's earlier boundary
   alone cannot establish prospective selection. Preserve both supplied clocks.

2. test_w40_paired_packet_preserves_raw_sources_times_and_identities:
   exercise ordinary import and actual CLI when a stage's declared state is an
   array or object. Classify the bounded malformed value as invalid evidence;
   preserve prior committed rows, known HTTP/timing evidence and explicit remaining
   gaps, with fixed safe diagnostics and no traceback or arbitrary prose. A
   malformed container must not reach hash/set membership as an unhashable value.

3. test_w40_label_replay_preserves_existing_rules_and_observation_states:
   reproduce the one-year-old candle and the declared historical before_timestamp
   query through raw -> normal import -> unchanged label helper -> safe report.
   Historical-only, pre-birth-inconsistent or historical-query-mismatched series
   cannot supply recent_volume_7d or qualify an otherwise uncorroborated honeypot
   flag as unsafe. Validate the actual requested daily series and the existing
   seven-day recent-volume window against its observed acquisition clocks and
   enrolled birth. Keep a contemporaneous positive control and the original
   helper's exact behavior. Do not alter labels.py, infer missing volume as zero,
   claim full time coverage from sparse candles, or introduce a freshness/skew
   tolerance or new label threshold. Preserve raw/time/query availability as gaps.

4. test_w40_timing_and_endpoint_overlap_never_become_passes:
   import timeout and transport_error with a valid request_at and response_at null,
   plus a known 429 with missing response time. Preserve each actual availability
   category, HTTP status and independently valid request clock; disclose the
   response clock as missing. An absent response time is not an invalid observed
   clock. Include actual invalid/reversed-clock controls, fail qualification
   closed, and never invent a response timestamp or simultaneous/skew pass.

The malformed identity/container, stale-volume, independent-clock and retrospective-
enrollment repairs each get a separate finding commit with its meaningful red in
the message. Keep all first-round evidence sealed; new evidence goes in a new
external round-two directory. Run focused checks and bounded meaningful mutants,
then request one exact-head globally exclusive full slot. A source-frozen/full-
pending handoff is acceptable while root owns that slot; do not call it READY.
One fresh combined second reviewer must reproduce all four closures, verify the
frozen contract and run the actual complete ordinary inventory before PASS.
Actual Linux checks precede publication. No source, scheduler, vendor request,
engine invocation or thirty-day calendar start is added by this repair.
