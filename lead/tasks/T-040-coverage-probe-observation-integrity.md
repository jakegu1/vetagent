---
id: T-040
title: Keep failed requests and invalid ages out of coverage-probe observations
status: done
level: 3
size: M
depends_on: [T-039]
decisions: [E11, E31, E32]
backlog: W54 and W57 measurement prerequisites
---

## Context and bounded workstream

The Owner authorizes autonomous technical batches, fresh reviews, merges, pushes and
deployment after quality verification. The 21 remaining backlog rows include W54's
multi-day holder-coverage study and W57's longer score study. Their instrument currently
discards ISO timestamp offsets and marks nonempty JSON error responses as usable.
Starting a longer run on that instrument would preserve false observations for longer.

This task protects experiment validity, costs one bounded implementation and at most
two review rounds, and stops after its deterministic contract and integrated checks
pass. It does not launch a long study, change a decision bar or change the engine.

## Goal and scope

The existing probe must distinguish observed upstream fields from a failed or malformed
request, and recruit only mints actually indexed within the existing age window.
Historical report input must not bypass the same observation boundary.

Only these three implementation files are in scope:

- bench/rugcheck_coverage_probe.py: timestamp parsing, fresh-cohort eligibility,
  acquisition observation classification and report filtering needed for this contract.
- tests/test_rugcheck_coverage_probe.py: additive, network-free acceptance tests (new).
- .github/workflows/test.yml: one unconditional offline test-job step invoking the new
  acceptance file. Preserve every old step, condition, command, action, runner and job.

No src file, scoring, gap taxonomy, threshold, dataset, baseline, recorded JSONL,
benchmark result, oracle, provider, package, credential or permission change. No network
call in an acceptance test and no new public output containing private data. Root owns
generated pages and backlog bookkeeping separately after reviewed integration.

## Conflict search and existing contract

Searched rugcheck_coverage_probe, age_minutes, recruit_fresh, observe, report,
_score_verdict and _leaves_and_returns across tests, bench and workflows. The only
existing caller under tests is tests/test_risk.py::_settling_figures, consumed by
test_the_settling_figures_in_the_engine_are_the_measured_ones. All existing source,
inputs and assertions in that file remain frozen. Existing tests enforce registration
of every test file and preservation of the entire offline job before deployment.
No existing test change is authorized. Report a conflict before editing an old test.

## Acceptance criteria

1. **Real UTC age.** Equivalent Z, UTC and positive/negative explicit-offset timestamps
   have equal ages relative to an aware UTC now; fractional seconds are respected.
   Existing timezone-naive timestamp input remains explicitly treated as UTC. Invalid
   timestamps and future index times cannot join the existing fresh cohort. Recruitment
   and retrospective score-cohort classification enforce the same nonnegative window.
   Do not alter the existing 10-minute, 40-mint, 3-oscillation or score-band constants.
2. **HTTP and body separation.** Acquisition retains the HTTP status, timestamp and
   sample identity for refused, transport-failed, empty and malformed responses. A
   non-200 response cannot become body=ok even when its JSON looks like a valid report.
   HTTP 200 empty/scalar/list/error-only bodies are not successful report observations.
   A valid report that supplies no holder list remains a successful observation of
   missing holder coverage; do not require holders in order to observe their absence.
   Boolean, nonnumeric, nonfinite and negative scores cannot produce a valid score band
   or a clean-score conclusion. Keep the raw field distinguishable as unavailable or
   malformed evidence; retain separately valid holder observations on the same report.
   Existing valid numeric bands and their boundaries remain unchanged.
3. **Historical seam.** report() independently excludes non-200 and unusable rows even
   if an old input claims body=ok. A mixed file reports unavailable requests separately
   and computes holder/score changes only from valid observations; an all-unusable file
   cannot exit as a successful study. Immediate retries need a usable matching primary
   row; unavailable observations cannot supply a missing-holder vote or denominator.
4. **Preserved valid behavior.** Synthetic valid holder-present, holder-absent, genuine
   score-change and immediate-retry cases still appear in the report. The committed
   historical six-hour reference bytes, engine thresholds, current risk answers and
   original risk-test assertions remain unchanged and pass. Do not reinterpret or
   replace historical published study outcomes in this implementation.
5. **Meaningful tests.** Add characterization and red-before-fix controls for offset
   truncation, future membership, JSON 429/503 and HTTP 200 error-only bodies, old
   body=ok refusal rows, all-unusable input and valid absence controls. Restore any
   mutation from an external byte-exact copy; demonstrate at most four targeted mutants
   are killed, including both an acquisition and a report-filter bypass.
6. **Contract, registration and checks.** First commit adds only the acceptance file;
   run it red on the parent and retain exact stdout/exit. Then keep each corrected
   finding in a separate implementation commit whose message describes its red.
   Acceptance tests remain frozen. Register the test by a separate scoped change.
   Run the actual full configured inventory once on the clean final source, with root's
   exclusive full-suite slot, and preserve a source/command/exit evidence manifest.

## Threat model and evidence

Realistic failures are JSON refusals from public upstreams, timezone-qualified index
times, stale JSONL produced by an older probe, and missing optional holder lists.
The dangerous outcome is an unobserved request counted as evidence or a false fresh
cohort, leading to an unjustified policy change. No production policy change is allowed.
Emit a READY report with base/tests/fix SHAs, file scope, red and green outputs, complete
check inventory, targeted mutation results, historical source hashes and limitations.
All private reports live outside the repository. Actual long-run availability remains
unmeasured until a separately reviewed pilot and observation plan run.

## Amendments

2026-10-19, pre-tests amendment (a): the same bounded falsification observes boolean,
NaN, infinite and negative scores entering bands, and strings/objects raising in band().
AC2 explicitly includes field-level validity. Before the first acceptance commit, add
synthetic valid-boundary and invalid-score controls, including a usable holder report
whose score is unreadable. No existing test or production threshold change is allowed.

2026-10-19, round-one bounce (b): the real producer appends to an existing file and
restarts sweep numbering. A retry following an unavailable primary can therefore
borrow a usable row from an earlier run. AC3 requires pairing against its own preceding
primary envelope in request order, including an intervening failed primary, before
validating observation usability. Do not search past that envelope for older evidence.
Keep valid current-run pairs and the historical reference unchanged. Before changing
the implementation, add only the named acceptance method
test_unobserved_primary_does_not_borrow_an_older_restarted_sweep, with an actual
two-session append/restart regression and a valid-pair control; preserve every existing
acceptance method byte for byte. Commit the new red test alone, then the matching fix.
No broader run-lifecycle redesign or new study is authorized here. Round two is one
fresh combined independent and adversarial review of the complete final source.
