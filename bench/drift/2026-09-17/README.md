# Cold fresh-clone re-run, 2026-09-17 (UTC)

A pre-publication reviewer re-ran `python bench/run_benchmark.py` cold, on a fresh `git clone`
of origin/master at bbb1ca7, from about 15:48 to 16:32 UTC on 2026-09-17 (44 minutes). The
files here are copied verbatim from that review; the local times inside them are UTC+8.

| file | what it is |
|---|---|
| `PREREG_fresh_clone_drift.md` | The reading rule, written at 15:55 UTC while the run was still going and before it had printed anything. Rule 2 sets a tolerance per figure and says a figure outside it is printed in the post. |
| `results.fresh-clone-2026-09-18.json` | The run's `bench/results.json`. |
| `drift_compare.py` | The comparison script. Its inputs were the published `bench/results.json` of commit 946fd65 (2026-09-15) and the file above. |
| `fresh_clone_drift_2026-09-18.txt` | Its output. |

One figure fell outside its tolerance: false blocks, 30 of 154 published against 36 of 149
fresh (tolerance 25 to 35). The centralised row had no tolerance and moved further, 40 of 179
rated high to 26. None of the 60 verdicts that moved came from code.

The rule 2 sentence reached `docs/EXPERIMENT_C.md` and the dev.to post on 2026-09-19, a
few hours after the post went out without it.

This run predates the 2026-09-19 rule (DECISIONS E23) that took false blocks to 20 of 154;
that rule has not had a cold re-run.
