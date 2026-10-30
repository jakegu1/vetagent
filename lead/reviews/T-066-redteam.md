## Red-team review: T-066

Head `f0f680704a28398c8f85ad720a724687acd565bc`; base
`8d7c47659ae0aa3c72307cba0b4060b9f385a7df`; additive acceptance
`cb9baa81c1f6a30ef3cc5de1f23c02de6235df5d`.

Scope: the packed-size acquisition and unavailable-measurement path in
`tests/test_archive_budget.py`, against
`lead/tasks/T-066-packed-archive-budget.md`. This is a focused correctness
red-team review. The complete suite and publication gates remain separate.

### What held up

- A separate tiny native Git fixture measured the same pack/index KiB quantity
  from normal and linked checkouts. An unrelated current directory, conflicting
  inherited Git routing/config variables, metadata and newly loose objects did
  not change the selected packed portion. Empty and loose-only stores remained
  distinct. A real native garbage warning with successful statistics preserved
  the reading and exposed no diagnostic text.
- Independent reordered/CRLF statistics, missing/duplicate/malformed values,
  undecodable output, failed commands, missing/unusable Git and timeouts kept
  unavailable readings distinct from zero. The actual gate rejected unavailable
  readings and retained literal warning/budget boundaries at 160/200 MiB,
  including values immediately below and above them.
- The helper issued one fixed read-only `git -C ROOT count-objects -v` argv,
  without a shell, with captured streams and a finite timeout. It removed
  inherited `GIT_*` variables, retained CI flags and did not change the caller's
  environment or print arbitrary stdout, stderr or exception messages.
- Text and AST comparisons showed the tests-only commit preserved every old
  function. The implementation commit preserved every old/new function outside
  the exact named changes. The original numeric gate body, constants
  `200/0.8/90`, runner and B15 decision row remained exact.
- All five frozen additive acceptance functions passed 201 assertions. The
  additive parent reproduced 90 failed assertions without an exception. In-memory
  zero-reading and unavailable-as-zero mutants caused 88 and 81 failed
  assertions respectively, without changing any acceptance function. Separate
  focused checks passed all 34 groups and all seven direct gate controls.

Immutable source inspection commands were
`git show <commit>:tests/test_archive_budget.py`,
`git show <head>:lead/tasks/T-066-packed-archive-budget.md` and
`git diff <base> <head> -- tests/test_archive_budget.py`. Native fixture setup
used only owned temporary repositories; packing never touched the source object
database. Before/after seals preserved selected primary bytes, immutable source
blobs and source Git refs. No repository files were edited by this reviewer.

### Material findings

None reproduced.

### Minor notes

None requiring a change. This review does not certify a fully repacked clone,
server allocation, complete-suite result, CI/build result or release readiness.

RED-TEAM: none
