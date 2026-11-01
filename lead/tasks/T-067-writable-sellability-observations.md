---
id: T-067
title: Preserve writable sellability observations and explicit payload failures
status: ready
level: 3
size: M
depends_on: [T-062, T-065, T-066]
backlog: W7 prospective snapshot evidence integrity
---

## Context, benefit, cost and stop

Offline actual main witnesses reproduce three seams on the published source.
A projected sellTax parsed from JSON1e400 becomes Infinity in the archive while
the writer reports success. A lone surrogate raises during writing and drops an
already acquired valid later row. A wrong-type simulationResult raises while
projecting the second reply, before even the valid first reply is preserved.
These are synthetic witnesses; historical incidence is not established.

Protect the accumulating snapshot asset and truthful failure/absence distinctions.
Cost one related bounded task, additive frozen tests, one fix per demonstrated
finding class, fresh functional/adversarial review and existing publication gates.
Stop at safe row admission, explicit failed observation and ordinary main handoff.
No new schema-wide engine validator, provider, collection, budget or research.

## Scope and files

- bench/snapshot.py: future sellability projection/admission/write and main status.
- tests/test_sellability_archive.py: additive functions/helpers only, auto-discovered
  through the existing configured runner. No workflow or runner change.
- Lead-owned task/index/state/review metadata is separate.

No historical row rewriting or archive migration; scientific executed sources,
T047/T049/T050, src/, fetcher.py, sampling/attempt caps, request order, rate,
timeout, retries, clock reads, dependencies and permission files are unchanged.

## Acceptance criteria

1. A received non-object reply, non-object nonempty projection branch used with
   .get, or unrepresentable projected JSON/UTF8 field produces an explicit
   future failure observation instead of raising, pretending absence or writing
   non-finite JSON. Preserve the request metadata and actual existing timing.
   answered=false, outcome=invalid_payload and one fixed bounded diagnostic may
   identify this class; do not store raw body, exception, URL or identity in logs.
   Raw invalid values must not be normalized into usable risk facts. Do not turn
   a returned malformed response into no_record or unreachable. Existing
   _probed_already attempt accounting must count the actual received failure
   without marking it answered or changing the cap or prior categories.
2. Every ordinary successful, no_record, unreachable and writable legacy row
   retains all existing native values, field spellings and timing byte semantics.
   Valid Unicode, JSON null, finite zero and nested finite data remain admissible.
   Preserve the existing permissive writable raw-field contract; this is not new
   field-level risk schema validation. Unsupported malformed projection branches
   cannot interrupt earlier/later acquired rows. No new HTTP, retry, clock read,
   pacing or hidden replay. Existing request/clock traces remain exact.
3. The actual writer emits only strict UTF8 finite JSON rows. Preserve the
   append prefix and each valid predecessor/successor around a rejected payload.
   Keep an explicit failure record; silently skipping a bad request is forbidden.
   The writer returns nonzero for a batch containing invalid_payload. Real main
   --sellability-only and normal pool collection propagate that result after
   preserving pool/run coverage and all writable sellability observations.
   A genuine disk I/O failure still fails honestly; no atomic/fsync claims added.
4. Add actual fetch/probe/write/readiness and main witnesses for parsed exponent
   overflow, nested non-finite fields, escaped lone surrogate, top-level and
   projection-branch wrong types with valid neighbors. Include both main modes,
   existing byte prefixes, finite/Unicode/null controls and bounded aggregate
   output. A strict reader must not see malformed lines; failure observations
   remain failures, not usable sellability facts. Keep all false replay/full-engine/
   independent-outcome flags and exact original clock semantics.
5. Tests first and alone, meaningful parent red retained; additive tests freeze.
   Keep old tests/helpers byte/AST unchanged. One finding per runtime fix commit
   with its observed red in the message. Unexpected old conflicts mean BLOCKED.
   Fresh functional and separate focused adversarial review and meaningful
   payload-validation/status-propagation mutants required. Author/independent
   complete configured45 and integrated full gates must pass, then normal CI,
   two actual locked builds and publication. No flags cleared or bars lowered.

## Conflict search and evidence

Conflict search covered probe_sellability, _write_sellability, _probed_already, main, outcome,
answered, schema2, raw projection, timing, no_record, unreachable, invalid_payload,
write/readiness handoffs across every existing caller and test. Named changes to
existing tests: NONE. The original eight focused projection/clock/writer/main
functions pass145 assertions with no failures. Existing schema2 exact projection
tests include writable legacy and invalid-timing records and must remain exact.
Test clocks or writer-only invalid-timing rows must retain
their old writable behavior; invalid timing is not unrepresentable JSON.

Actual witnesses: finite control success; overflow main exits0 with one malformed
middle row; surrogate main raises after writing one good row and loses the later
good row; wrong mapping main raises on request2 before any acquired row is written.
All preserve earlier on-disk prefix; all offline, no provider/risk traffic.

Retain exact source pins, tests-first red/green raw outputs, failed attempts and
review originals. Use the new shared raw-SHA gzip source manifests, not permanent
whole-tree backups. Declared disposable fixture dirs are not review evidence.

## Threat model

Ordinary upstream JSON, UTF8 edge cases and malformed reply shape must not corrupt
the append stream, lose neighboring acquired observations, publish false success
or equate a failed check with observed absence. Do not repair historical scientific
evidence or bypass the held mandatory T047 security review.
