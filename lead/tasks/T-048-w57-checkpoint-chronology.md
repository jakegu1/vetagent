---
id: T-048
title: Select W57 checkpoints by verified chronology rather than opaque Artifact ID
status: ready
level: 3
size: M
depends_on: [T-043]
backlog: W57
design_base: 4037ecaeb3eb89f7e1d812a28e6ba066ba699acc
---

## Context, goal, cost and stop rule

An actual successful schedule tick selected an earlier terminal pilot because
its numeric Artifact ID exceeded that of the later active study. The exact
same selection assumption can bypass the active-study start guard and truncate
reconstruction. Preserve the original scientific protocol while repairing one
control-plane selection class. Expected cost is one bounded implementation and
two fresh reviews; stop on ambiguous history or failed validation. No Vendor
request is part of executor acceptance tests.

## Exact scope

1. bench/rugcheck_w57_ci.py: bounded metadata chronology validation/selection,
   consumed by prepare and reconstruct. Preserve all source-change, terminal,
   provenance, digest, parent, cohort, request/time and history-budget checks.
2. tests/test_rugcheck_w57_ci.py: tests first, one additive new unittest class
   containing the three named regression methods, inserted immediately before
   the existing main guard. Preserve every existing helper, method, assertion,
   statement and main guard byte-for-byte. Keep its ordinary existing CI
   registration; no new test runner or workflow step is needed.

Out of scope: rugcheck_coverage_probe.py, workflow files, engine, source/risk
policy, stored observations, old Artifacts, cache, production deployment,
scientific thresholds or duration, study migration/rebinding, automatic restart,
new upstream, credentials, permissions, costs and outreach.

## Conflict search and compatible adapter contract

The driver is used only by tests/test_rugcheck_w57_ci.py for these functions.
Current numeric sorting occurs only in prepare (line 316) and reconstruct
(line 799). Three existing test upload helpers supply id/name/expired/provenance
without GitHub's created_at field:

- MemoryArtifacts.publish;
- the nested publish helper in
  test_readout_discloses_groups_field_denominators_and_unattempted_gaps;
- the nested publish helper in
  test_cli_interruption_preserves_a_restorable_partial_checkpoint.

Prefer an explicit adapter contract: list() returns validated metadata in
oldest-to-newest checkpoint chronology. Implement strict metadata validation and
chronological sort in the actual GitHubArtifacts.list() port; prepare must not
re-sort it by opaque ID, and reconstruct walks chronological result candidates
in reverse. Existing MemoryArtifacts.list() already returns insertion/publication
order, so its original fixtures satisfy that contract without new metadata or
any old test edit. New tests must exercise the actual GitHubArtifacts.list/load/
decode seam with API-shaped metadata, including adversarial raw API/page/ID
orders. Never substitute a bespoke already-ordered fake for the chronology
behavior under test.

No production fallback to numeric ID is permitted. The production list port must
validate required GitHub metadata. No validation branch may exempt a synthetic
repository, test environment or missing-field production response. If the chosen
implementation requires an old fixture schema change, obtain root's explicit
named fixture-only amendment before acceptance implementation; this draft
authorizes no such edit. No changes to assertion expectations, old source hashes
or existing guards are authorized. The existing adapter page/download test must
retain its five-page and two-download expectations.

## Acceptance criteria

1. **Actual escaped class, default tick and active guard.** Add
   test_checkpoint_chronology_ignores_nonmonotonic_artifact_ids. Through the real
   list/load/decode/prepare seam with synthetic bounded transports, reproduce the
   real four-checkpoint chronology: older pilot result has a larger ID than the
   later active start. Tick must select the latest active study and original due
   slot without recruiting, resetting the original clock or changing population.
   An explicit other pilot/start while active must still refuse. Reverse input
   list/page order and ID order without changing this result. A newer intent
   with a smaller ID must retain the original lost_checkpoint/no-replay behavior.
   Record the pre-fix failing assertion and native exit before the source fix.

2. **Validated bounded chronology.** Add
   test_checkpoint_chronology_fails_closed_on_invalid_or_ambiguous_metadata.
   Validate positive unique IDs, usable immutable UTC created_at metadata and
   the provenance needed for an equal-time same-run result/intent tie in the
   actual GitHub list adapter. Missing,
   malformed, conflicting or genuinely ambiguous chronology must stop before
   Vendor calls; never fall back to numeric ID or silently drop the record that
   might be newest. An equal-time completed result from its own same run may
   supersede that run's intent; conflicting equal-time candidates from distinct
   runs must fail closed unless a verified existing chain unambiguously orders
   them within the original budget. Retain original five metadata pages, two
   checkpoint downloads/tick, twelve reads and all ZIP/state/time ceilings.

3. **Latest valid reconstruction, unchanged chain.** Add
   test_checkpoint_reconstruction_keeps_later_lower_id_generations. Construct at
   least two valid same-study generations whose later checkpoint has a lower
   Artifact ID. Reconstruct the later complete chain, retain all earlier and
   later rows once, and keep original group/field denominators and censoring.
   Include an older different-study pilot with a larger ID. A bad latest digest,
   parent, cohort, provenance or source must refuse; never silently downgrade to
   an older partial successful report. Keep the original 195-result bound and
   existing read budget. Characterize unchanged pilot/start/tick/report behavior.

4. **Scientific freeze preserved.** In the new chronology method, start from an
   actual-shape original active checkpoint, then pass a new current driver hash.
   Prepare must emit checkpoint/status source_changed, preserve original
   state.source/cohort/start/end/chunks, and make zero Vendor requests. No
   collection is permitted from this state. Keep lost-intent and terminal
   handling unchanged. This test does not create an actual terminal receipt and
   does not authorize reusing or resetting the old study.

5. **Tests first and frozen contract.** Commit only the additive new class and
   its three named methods before the unchanged existing main guard. Demonstrate relevant original
   numeric-order mutants fail the new tests; at most three deliberate mutants,
   with byte-exact external backup/restoration. Do not change old assertions to
   obtain green. Keep one finding/source-fix commit for this chronology class.

6. **Source-specific quality and real operational gate.** Run the existing W57
   test runner and relevant workflow-registration/English/enforcement guards,
   then one root-granted exclusive complete configured inventory on the final
   frozen head. Fresh independent and adversarial review must verify actual
   source-specific evidence. Root merges normal bot changes, regenerates derived
   pages in explicit regenerate mode and verifies actual Linux/master CI before
   publication is claimed. Root then observes one actual repaired-source cron
   tick creating an original-study source_changed terminal with zero Vendor
   calls and verifies/export its actual parent chain. This last runtime gate is
   root-owned after publication and must remain pending until actually observed.

## Threat model and release notes

Opaque nonmonotonic IDs, API list/page order, same-second uploads, newer orphan
intents, malformed metadata and unrelated study terminal results must not cause
duplicate Vendor work, an overlapping active study, silent history truncation or
mistaken scientific completeness. Retain trusted default-branch/run provenance
and safe console diagnostics; raw errors/URLs/identities remain private artifacts.

Changing the driver hash intentionally prevents continuing the old frozen study.
Do not whitelist the old source or claim the repair retroactively validates the
missing interval. A later explicit new pilot and new study can follow the actual
old-study terminal under the same original rule. No automatic new study is part
of this repair. Waiting for actual cron/terminal is a calendar dependency; rule
or provider changes would remain an Owner decision.

## READY evidence

Exact tests-first and repaired SHAs; red/green command, native exit and failing
assertion; old-assertion/fixture delta check; focused and full actual log hashes;
all applicable inventory steps; source/probe/workflow invariants; bounded
nonmonotonic/tie/invalid/intent/reconstruct/source_changed fixtures; source-specific
review verdicts. Root's later actual scheduled terminal is separately bound to
run ID, event, checkout SHA, ZIP/manifest hashes, exact original state source,
exact new manifest context source, same old cohort/clocks/parent, zero additional
rows/requests and genuine terminal status. Preserve original study artifacts.

## Lead adoption and controlled active-source replacement

The lead adopts this mechanical repair under the current technical continuation
authorization. The active-source freeze still prohibits changing a study's
stored source, whitelist, cohort, clock or observations. This named correction
permits replacing only the reviewed driver implementation so its existing
source_changed guard can retire the original study on a real scheduled entry.
Do not migrate or continue its observations under the new hash. Publication
and an actual zero-vendor terminal receipt are separate gates. If the ordinary
guard cannot produce that receipt, stop and preserve evidence rather than
manufacturing termination, extending the window or starting another study.

The production adapter's ordered-list contract is explicit; preserve every old
test byte through that compatible port boundary. No fixture-only amendment or
numeric-ID fallback is adopted. The initial implementation base is 4037eca;
the configured complete inventory there is forty-three steps, with T046's
independent addition integrated serially later. No worker upload is needed.

## Named new-regression expectation correction

2026-10-19: the acceptance-only commit 87d46e7 demonstrates all three intended
chronology reds. The first source repair exposes two incorrect expectations in
that new class; no original test expectation is wrong or changed. The original
start has slots=[] rather than an observed slot zero, so a first tick at slot
seven must preserve all missing slots zero through six. In the new chronology
method only, replace list(range(1, 7)) with list(range(7)).

In the new reconstruction method's damaged-latest cases only, instrument the
actual service.load with a wraps spy and assert its first attempted checkpoint
is the latest, retaining every existing StudyError assertion. An invalid run
provenance must refuse before downloading any ZIP, so assert zero ZIP downloads
for that case. For the remaining damaged-latest cases retain the existing first
ZIP-is-latest assertion. Do not force a download across a provenance refusal or
weaken either guard. Preserve every other new and original assertion, helper,
method, main and fixture. Commit only these named acceptance corrections before
the one-finding source fix; retain the original three-test red and first repair
run as historical evidence rather than rewriting them.

## Named malformed-listing versus observed-absence regression

2026-10-19 (b): a lead-owned offline probe at held 647c12b injects a one-row
Artifact listing containing a non-object, an object missing name, or an object
whose name is null. All three return idle/no_state rather than refusing. The
matching-name filter discards an unclassifiable record before the strict
chronology validator can see it. That is an original AC2 metadata gap, not
observed absence. The source-specific full run, if already active, must finish
untouched and remain held-source evidence only.

Permit one self-contained append-only block at the end of the new
test_checkpoint_chronology_fails_closed_on_invalid_or_ambiguous_metadata method.
Keep every other original and new assertion, helper, method and main exact,
including the named expectation corrections above. Through the actual production
list/prepare port with synthetic listing transport, all three malformed-row
representatives must raise StudyError before any checkpoint download or Vendor
call. An explicitly empty exhausted listing still returns idle/no_state. Preserve
the original valid-unrelated-name paging fixture and its five-page bound.

Commit only the appended regression with its actual red, then one separate
same-finding driver repair. Validate that each raw listing row has an object and
a usable string name before classifying matching versus explicitly unrelated
Artifacts. Unclassifiable/malformed metadata is unavailable, never an empty
history. Do not introduce numeric-ID fallback, alter source/history/scientific
guards, change original fixtures or increase any page/read/download budget.
Freeze a new exact head and obtain its own full gate before fresh reviews;
retain the earlier prepared seal and actual full log without relabeling them.
