# T065 first normal scheduled snapshot: operational acceptance

VERDICT: PASS for this single normal producer-to-writer-to-reader trial.

The first existing scheduled run after publication was [40942209360](https://github.com/jakegu1/vetagent/actions/runs/40942209360), created at 2026-10-29T19:40:29Z. It used published commit `6fe4440a0c6e4b702c773b228a18ce030cc635c9`, event `schedule`, attempt 1. The bounded eight-run index includes the preceding pre-release anchor 40843156417; the later run was not substituted for the first eligible run.

## Evidence reproduced

- The actual Git checkout command and its following full SHA occur inside the pinned checkout step's recorded time. The six collection, preservation, regeneration and coverage commands match the immutable workflow and their actual step times. Native job and ZIP log labels are retained verbatim.
- Complete commit metadata establishes `6fe4440 -> ea1fc83 -> 6174d09 -> 5d17896`. The pool and sellability push ranges are present in the corresponding log groups; the derived commit time, parent and successful push confirmation are bound to its actual command group. Only the expected archive and derived-page paths changed, so all eight retained source/workflow/parser components remain the published bytes.
- Git blob SHA-1 and saved SHA-256 checks bind before/after bytes. Exact original prefixes are preserved. The additions are 658 pool rows, 40 coverage rows and 25 sellability rows, independently matching commit additions and collector aggregates. Strict JSON/UTF-8 parsing accepts every appended row. Coverage contains 37 successful page observations and three observed listing ends, with no recorded gap in this pass.
- All 658 pool rows retain literal `volume`, `tx`, `price_quote` and `quote_token_price_usd` fields. Seventeen `price_quote` nulls remain null. All 25 sellability rows retain valid fetch clocks within the actual collection step: 11 `answered=true` and 14 `answered=false`/`no_record`. The latter are unavailable simulator records, not successful sell simulations.
- The unmodified saved strict reader ran offline in native subprocesses with network activity denied. At 2026-10-29T19:48:37Z it classifies all 25 sellability rows as future and none as eligible; at 2026-10-29T19:49:38Z all 25 become eligible. Both inventories complete with no malformed rows or unknown timing. Every source and archive byte remains unchanged.
- Following normal [bot CI 40943568008](https://github.com/jakegu1/vetagent/actions/runs/40943568008) checks out actual derived head `5d17896044d897760f1547e957445348bba596e1`. All 45 configured offline test commands execute successfully in order. Build, upstream-contract, backfill-roundtrip and benchmark jobs are explicitly skipped; this run supplies zero new locked builds.

## Limits and retained failures

This is a single observed operational handoff. No `past_end_of_listing` or `invalid_payload` record occurred, so the run does not empirically exercise the two repaired exceptional paths. Native field presence and acquisition availability do not validate full engine inputs, independent outcomes, continuous coverage or replay readiness. Historical science conclusions remain unchanged and inconclusive; held tasks remain held.

Four local evidence-helper refusals are retained: a display-only regex error, a grouped-untracked-file counting assumption, overlapping whole-second step metadata, and an incorrect assumed reader field name. Corrections affected only private evidence helpers. Actual source, records, cutoffs and acceptance rules did not change; successful existing captures were reused only after byte equality. No extra GitHub request was made to repair them.

The review used 14 unique GitHub GETs, 258,417 compressed log bytes and 2,205,692 expanded log bytes, below the fixed caps. It dispatched no run, made no upstream or production risk request, changed no source or Git ref, ran no heavy local suite, and left the protected checkouts unchanged.
