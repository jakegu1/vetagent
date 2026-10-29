## Red-team review: T-065

Head `b04364d4334a6b04ebb808758995c664eef21cb4`. Base `28a08e894abbcacc815139202bab63ba510e55bb`. Reviewed the committed spec including A1 and the new page-serialization and derived-confirmation behavior in `bench/snapshot.py` and `bench/snapshot_readiness.py`.

What I tried: independently written, offline witnesses using exact committed source, real fetcher JSON parsing, fake HTTP and deterministic clocks, actual collection and main writing, inventory, and four real reader CLI calls. The focused probes passed 585 behavioral assertions. Source projections remained byte-exact; all 90 pre-existing function/class nodes in `tests/test_sellability_archive.py` remained AST-exact.

### What held up

- Twenty malformed-native cases covered overflowing exponents, non-finite nested values, lone surrogates in old scalar fields, nested keys/values, relationship identifiers and pool identifiers. A valid neighbor on the same page was rejected atomically in both row orders. Valid earlier/later pages survived, failure manifests remained strict readable JSON, and coverage stayed incomplete. A separate all-invalid run retained four readable failed-page records with no successful current pool rows.
- Valid Unicode, control characters, finite zero, null, booleans and nested native values retained exact output bytes and request/clock traces against the base. Existing bounded optional-quote capture remained unchanged.
- Five derived conclusions across two chains with different actual end pages and confirmation clocks inherited only their own listing proof. Failed/skipped initial diagnostics survived, and derived records gained no synthetic recovery-fetch clock. Inventory and CLI eligibility changed at each exact confirmation instant, including an equivalent timezone offset.
- Thirty-seven malformed or legacy proof variants stayed unknown despite usable older fetch clocks. Boolean/non-integer pages and invalid lower-page relationships were rejected. Ordinary recovery timestamps, other row kinds and the existing field census retained their prior behavior.
- The original UTF-8 writer exception and missing-manifest defect reproduced on the base. The base also reproduced premature availability through its older failed-fetch timestamp. The reviewed head closed both witnesses. Reader output remained bounded and aggregate-only, source/history bytes stayed unchanged, and all three replay/input/outcome flags remained false.

### Material findings

None reproduced within this focused scope.

### Minor notes

None. Complete runner, integration, build and CI evidence remain separate release gates; this verdict covers the focused new correctness seams.

RED-TEAM: none
