# Review: T-063 - Ready for scoped technical integration

Head: `25bfb4324467f739b41e131f9d0078ae726812c1`. Contract base: `91e71cbb496472096ff04087e3940b976d88af85`.
This is a fresh independent R2 functional review of the exact source and A1-A5.
R1's row-retention finding is reproduced and closed by the bounded capture fix.

The contract checker exits zero. The registered focused runner passes **980/0**;
all five added acceptance functions pass **174/0**. The independently executed
actual `python lead/checks.py` completes **45 of 45**, native exit **0**, in
**316.7 seconds**, using the real unchanged CI flags and a verified
non-Git temporary root. The author has a separate exact-source **45/45**, native
zero receipt; this review did not substitute it for the independent execution.

| AC | Result | Independently reproduced evidence |
|---|---|---|
| 1 | Pass | Native volume/tx and both quote keys are additive literal counts. Null, false, zero, empty/malformed-valued containers, future and unknown clocks remain presence, with no alias or usability inference. |
| 2 | Pass | Fake HTTP reaches the actual page producer, collector, writer, NDJSON, reader and real CLI. File/kind native counts agree; clocks, row totals, reasons, bounds and input bytes remain exact. |
| 3 | Pass | Finite JSON and valid Unicode values remain exact; missing/null have no capture status. Scalar/nested nonfinite values and lone UTF-8 surrogates become only null plus the fixed capture status. Every old raw field, schema and primary/quote price is retained; the input is immutable. |
| 4 | Pass | Distinct saved quote strings 3/5 reproduce 6/10 through the unchanged pure pricing seam. Original None/empty/zero/invalid primary semantics, legacy/null counts and all three false readiness flags hold. |
| 5 | Pass | Actual collector/writer/reader/CLI probes retain 27 rows from 24 quote cases plus three clock/presence controls, with zero malformed rows. Exact request order/count/options, old projection, source hashes, privacy, limits and strict clock/source/symlink guards hold. All required mutants are killed and restored. |
| 6 | Pass | Exact first acceptance against historical source/CLI gives four failed assertions; pre-quote source with the approved parser fixture gives nineteen. Exact named E tests-only source gives thirty-six. First/B/E are additions only; C/D are line-exact approved changes. All 85 old and all 88 earlier definitions, including the hand-written runner, remain source/AST exact. |
| 7 | Reviewer gate passed | Fresh functional and focused adversarial review has no material finding; independent and author exact-source full gates pass. All raw-source protections hold. The later related-batch integrated gate and release/runtime gates remain separate required steps. |

The independent adversarial set includes JSON numeric overflow in both directions,
nested nonfinite values, scalar/dictionary-key/dictionary-value lone surrogates,
valid Unicode and astral characters, finite numeric/container controls, missing,
null, literal presence and future/invalid-precision clocks. It is bounded at
24 input cases; it is not an unbounded fuzzing or universal row-width claim.
The existing line/file/total-size limits remain unchanged.

Mutants: omitted native tx causes **5** failed assertions; discarded quote causes
**19**; raw quote without containment causes **36**. Restored acceptance returns
**174/0**. Mutants are in memory; no repository source file is mutated.

All **1014 tracked raw files** remain byte-exact against the independent external
copies. All **145 old raw archive files**, the five frozen controls and their
static local import closure, and the **13 protected primary files** remain exact.
The old certificate is only a historical executed-source freeze reference.
No request to an upstream/production service, workflow trigger, push, scientific
window operation or permission change is performed by this review.

Rubric: spec **2**; scope **2**; correctness **2**; tests **2**; invariants **2**;
maintainability **2** = **12/12**.

Required changes: none. Optional follow-ups: none introduced by this R2.

**RED-TEAM: none.**

**VERDICT: PASS for the exact source and scoped technical integration.**
This verdict does not authorize publication or stand in for later integration,
Linux, locked-build, master or normal-snapshot evidence.
