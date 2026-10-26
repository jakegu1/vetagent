## Red-team review: T-064

Head `97e71dd973164e2af2eab2f88957b53afccbf4ab`. Contract base
`f763a51500275cdfe1aad08989c3d5a8b11ae39c`.

What I tried: fixed-schema and private-field rejection; mixed observed/missing
native evidence; callback failure and restoration; bounded status reads and read
errors; actual generated ZIP/finalize/finish/capacity/interruption/terminal and
admission seams in both live namespaces; registered-test reachability; unchanged
legacy transport/deadline behavior; three controlled in-memory mutants.

### What held up

- The registered coverage-probe file passes all19 tests. The registered W57 file
  passes its ten T064 tests, and six separately selected original methods pass.
  The original methods cover transport deadlines, the source-freeze literal,
  slow-phase missingness, strict completion, late responses and interrupted
  finalization. These are bounded checks, not a complete-project gate.
- Actual generated ZIP bytes survive the ordinary finalizers, fake Artifact
  service, finish receipt and allowlisted summary. The committed tests reject a
  stale transport digest and altered/missing terminal admission member. Capacity
  fallback preserves the original scientific files, unverified tail and ZIP;
  status survives fresh-process readback. Original overflow and failed status
  persistence remain failures.
- Unknown/private fields, bool counters, nonfinite timing, unknown native keys,
  and mismatched counter-family totals reject. Invalid/duplicate capture records
  omit the aggregate, preserve the original transport tuple and request count,
  and restore the prior hook. Unsafe/oversized status documents and a synthetic
  permission-denied read produce the fixed status-unavailable failure.
- Exactly three in-memory mutants each install at one asserted source match and
  make the relevant committed added test fail: permitting an unknown private
  field; dropping the member in session finalize; and labeling capacity fallback
  recorded. No runtime or acceptance source was edited. All1018 tracked raw-file
  hashes match their pre-run values, and the checkout remains clean.
- Static old-test comparison finds only the preregistered P literal change among
  the old coverage/W57 test methods. Its canonical probe hash independently
  matches the committed fixed literal. Workflow, runner, production source and
  fixtures are unchanged in the reviewed range.

### Material findings

**M1. Mixed missing-native evidence disables required usable-body consistency.**
Location: `bench/rugcheck_w57_ci.py:226`, `_validate_diagnostics`.

Trigger: a supplied or restored aggregate combines actual native-zero successes
with a legacy attempt whose native evidence is unavailable. A malformed aggregate
can undercount usable bodies while keeping every family total and bound valid.
The validator checks equality with reason.ok only when the entire unavailable
bucket is zero.

Reproduction: begin with `_new_diagnostics("pilot")`. Set the RugCheck source to
opportunities6, attempted6, not_attempted0 and usable_body0. Set its HTTP counters
to200=5/no_http=1, reasons to ok5/unclassified1, and native counters to0=5/
unavailable1; retain all other counters at zero. `_validate_diagnostics` accepts
it. Passing it to the actual result constructor and decoding the actual generated
ZIP preserves that object in both protocols. The consumed ZIP SHA-256 values are
`8a1f539e77e6cb439a09c02f1afb48e9a992965e9fbc690b9f8f6f863decfc2b`
and `5973e88ccb4b57deeb6c7ad22f519d4597087cbb8a2a4fb60fe7a152d1ba3921`.

Impact: at most one of the five ok reasons can lack native evidence, so at least
four require usable-body evidence. Accepting zero violates AC4's inconsistent
aggregate rejection and the transport/body contract. This is a diagnostic
integrity failure; this review did not demonstrate changed scientific rows,
requests, verdicts or privacy leakage. The normal accumulator was not observed
to generate this malformed object.

Fix: enforce the lower bound `usable_body >= reason.ok - native_exit.unavailable`
alongside the existing upper bounds and complete-evidence equality. Add write and
actual-ZIP read rejection cases for this mixed-evidence object, retaining valid
mixed native/legacy aggregates and all legacy scientific behavior.

### Minor notes

1. An additional terminal-result witness with a valid diagnostic member and an
   unverified tail retains the member but omits the tail from the local closure
   rebuild. The resulting digest differs; close-index correctly fails with
   `admission_dependency` in both namespaces. The original fake Artifact remains
   intact and no stale pin is weakened. Static comparison shows the pre-existing
   closure rebuild also omitted that optional tail. This is a fail-closed existing
   boundary, not a demonstrated T064 release regression; no historical source
   execution is claimed here.
2. This pass did not run complete45, Linux CI, locked builds, native controls,
   network requests or a scientific operation. It does not attest those release
   gates or reinterpret any known complete-gate baseline failure as a task pass.
   This reviewer exercised only mutation classes d/e/f; a/b/c belong to the
   separately assigned functional review.

RED-TEAM: 1 material
