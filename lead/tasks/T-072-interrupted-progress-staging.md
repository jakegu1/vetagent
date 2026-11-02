---
id: T-072
title: Retain bounded interrupted progress publication without trusting staging
status: source-accepted
level: 3
size: M
base: ab905c1218d2081a77eee0db0415096470450c7f
depends_on: [T-071_source_acceptance]
---

## Goal and incident boundary

The existing progress writer publishes progress.json through the fixed
progress.json.pending path. Interruption can leave that owned artifact, but the
two existing sidecar readers reject it before validating otherwise valid retired
evidence. Reproduce and prospectively correct that data-retention seam, preserving
the original safety, resource and committed-evidence rules.

Master CI41481523457 atab905c1 failed in the old cancellation test at the sidecar
name/type/size refusal, followed by cleanup_uncertain. The particular directory
was not retained: its exact file and historical cause remain unknown. A later
local single-test pass and the prior feature/full passes do not repair that
failure or establish its cause. Preserve that run; do not rerun it for green.

## Files, conflict search and stop

Executor files only: bench/w40_native.py and one additive
InterruptedProgressStagingTests class in tests/test_w40_native.py, before its
unchanged runner. Root owns task metadata, review publication and integration.

Conflict search atab905c1 finds ATTEMPT_SIDECARS, retired_observation and the
pending path only in bench/w40_native.py. The classification is consumed by
retired_observation and evidence_inventory; inventory equality already connects
seal, read_prepared and fresh offline recovery. No archive footprint calculator
or w40_archive module exists in this integrated source. Refresh consumers before
implementation; report any additional actual seam rather than assuming one.

Named old-test changes: none. Preserve all13 original methods, assertions,
helpers, order and runner as exact Git-normalized source segments. Only the
three new methods and their local fixture helpers may be added. No new test
file or workflow registration is needed; all46 configured commands remain.

Stop if implementation requires archive code, a changed source contract,
process-control/safety edit, larger allowance or weaker refusal. Do not broaden
this task. A separate test-readiness/phase-label finding stays parked.

Named new-test change A is authorized after tests-onlye5afcb8: the new fixture
retains attempt_end while deleting its mandatory commit. In the first and third
new methods, expect the existing evidence_mismatch refusal at inventory/seal,
preserving captured_prefix None, retired observations, exact staging bytes and
the original actual-CI raw_directory_refused branch. Do not weaken production or
continue read_prepared after seal refuses. In the third method's unknown-name
controls only, remove optional end.json, first prove that the staging baseline
still validates, then add the unknown name within the old actual15-entry cap.
If that baseline is invalid, report it rather than silently changing more inputs.
Commit only this named correction as
`T-072: named change (A missing-commit fixture contract)`; retain the first red and
two-error fixed-source result. All original13 test methods/helpers remain exact.

Named new-test change B addresses an independent material finding at87a5a70:
staging hardlinks were accepted. Add only a real same-volume synthetic hardlink
subcase to the third new method. Prove the valid baseline, alias identity and
link count2, then require both readers to refuse without changing fixture or
target bytes. Preserve its actual not-raised red before a separate minimal source
fix. The new staging must require reliable single-link metadata; absent/invalid
metadata refuses. Keep committed-file semantics and all old controls unchanged.
Use exact tests-only title `T-072: named change (B staging hardlink refusal)`.
The original reviewed source/finding remains retained, not retrospectively passed.

## Acceptance criteria

1. Keep the original15-name ATTEMPT_SIDECARS mapping and every original cap
   unchanged. Classify only progress.json.pending separately as optional opaque
   staging, at most ROW_CAP65,536 bytes. Committed and staging entries together
   remain at most15 per attempt. Preserve private_tree's actual570-entry limit,
   not589; BODY_CAP262,144 plus one overflow byte, PRIVATE_ALLOWANCE589,825,
   PACKET_CAP2,097,152, REPORT_CAP1,048,576,19 total attempts,16 engine attempts,
   256 dependencies and every other byte/storage/timing/policy bound stay exact.
   The prior per-attempt sidecar-cap sum1,179,649 cannot grow. Account for staging;
   do not borrow a new allowance or exclude it from actual entry/byte counts.
2. A fixed valid retired-evidence fixture without staging passes on the base.
   Adding only that staging artifact must actually raise invalid_evidence before
   the fix. Use synthetic identities/observations, deny real identity/transport/
   process operations and preserve the meaningful tests-only red. No missing-
   helper error alone establishes the regression.
3. After the fix, empty, partial/binary and complete JSON-looking staging bytes
   remain unchanged as regular non-link evidence in the owned directory. They
   supply no progress, body, status, timing, identity or success value. Plausible
   complete staging cannot replace missing/conflicting committed progress, end
   or commit. Leave captured_prefix and all committed validations unchanged.
4. Both readers apply the same one-name classification. evidence_inventory
   binds actual retained staging length/digest; the existing seal/read_prepared
   and bounded fresh offline recovery handoffs must preserve and compare it.
   Unchanged staging imports only under the ordinary contract. Changed/removed
   staging, or staging added after inventory, refuses before import/completion
   mutation and without re-asking. Retain all original bytes on success/refusal.
5. Regressions cover combined15/16 attempt entries, original570/571 tree entries,
   staging65,536/65,537 bytes and zero/partial cases. Unknown names, other pending
   names, links/reparse aliases, wrong types, oversize files and malformed or
   conflicting committed evidence still refuse, including with staging present.
6. Do not edit replace_private, the worker, process identity/spawn/retirement/
   cancellation/timeout, captured_prefix, code_manifest, FROZEN, registry/profiles,
   frozen source files, old Git objects/records or scientific rules. A small local
   data-only classifier/reference helper is permitted for the two readers. No
   archive dependency, new framework or public diagnostic payload is introduced.
7. Use exactly the finite additive test methods
   test_pending_progress_is_opaque_retained_evidence,
   test_pending_progress_handoff_binds_bytes_and_absence, and
   test_pending_progress_keeps_prior_limits_and_refusals. Commit them alone,
   preserve the actual intended red, then commit the finding-specific minimum fix.
8. Require exact-source author and independent complete46 checks, independent
   functional rubric at least10/12 with spec/invariants2, and focused data-integrity
   review with no material finding. Preserve previous failures and every named
   test invariant. Then require ordinary exact-head feature/master CI and two
   actual locked builds each; no skip, rerun, benchmark, vendor or risk probe.

## Risk, frozen sources and held work

The main risks are accidentally trusting complete staging as committed progress,
growing a bound through the mapping length, or losing an inventory handoff.
The preceding AC directly tests each risk. Unrecognized evidence remains refused;
critical missing observations remain unknown. No original artifact is removed,
rewritten or normalized to manufacture acceptance.

The six FROZEN inputs remain exact. The native module itself is not a FROZEN
input; the unchanged code_manifest binds its actual bytes. A new prospective
repair gets a new source identity and cannot reinterpret old-source claims.
The historical registry's two fixed profiles and old-source mismatch checks must
stay exact. New tests do not qualify historical execution or grant live use.

T047 is the separate held verified archive/seed/lock/allocation transaction. Its
candidate, incomplete mandatory security verdict and T049/T050 dependencies remain
isolated. This task neither reviews nor enables them, and does not replay the
interrupted safety investigation through another model or tool. No study,
enrollment, collection, scheduling, production/Vendor call or old scientific
operation is authorized. Normal snapshot trial stays held until publication gates
for the corrected source actually pass.
