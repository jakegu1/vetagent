# Pre-registered reading of the fresh-clone benchmark run

Written 2026-09-17 23:55 (UTC+8), while `python bench/run_benchmark.py` was still running cold on a
fresh `git clone` of origin/master bbb1ca7. Nothing from that run had been printed yet (stdout is
buffered to the log, which was 0 bytes at 23:51). Published figures being compared against:
`bench/results.json` from commit 946fd65 (2026-09-15).

## What the post claims about reproduction
"Until 2026-09-09 that command did not work on a fresh clone ... That is fixed. The figures are a
snapshot against live upstreams ..., so a re-run today will not land on the same decimals; tell me
if the drift is large."

## Rule
1. **Runs at all.** Exit code 0, a results file is written, and the independence overlap is empty.
   If not: the sentence "That is fixed" is false today. Action: remove or correct that sentence
   before posting. This alone does not postpone the post.
2. **Drift, counted in tokens, not decimals** (same 576 tokens, so this is upstream drift, not
   sampling error):
   - false positives (alive rated high): published 5 of 162. Within drift if 2 to 8.
   - unknown: published 122 of 576 (21.2%). Within drift if 105 to 139 (18.2% to 24.1%).
   - adversarial rated high: published 10 of 17. Within drift if 8 to 12.
   - false blocks: published 30 of 154. Within drift if 25 to 35.
   Inside every band: the post's "dated snapshot" framing holds; no text change.
   Outside any band: add one dated sentence to the post giving the fresh-clone figure next to the
   published one. Still not a reason to postpone -- the post already asks readers to report drift,
   and reporting it first is the post's own method.
3. **Unknowns our side vs token side.** If the run's "unknown, our side" count exceeds 30 (published
   6), the drift is this machine being throttled, not the engine; record it as such and do not
   count it under rule 2.
4. **Wall-clock.** Record how long a cold run takes. If over 60 minutes, the post should say so,
   because a reader who starts it expecting twenty minutes will conclude it hangs.

Would I have written the same bands if I expected the answer to be bad? Yes: they are set from the
published counts before any output existed, and the only consequence of falling outside them is a
sentence, not a verdict change.
