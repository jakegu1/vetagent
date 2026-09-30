# VetAgent · Owner dashboard (lead workflow)

> This page holds only what the lead needs from you. The project's own dashboard, with its
> deadlines and gates, is `docs/OWNER.md` (generated). Messages to you are in Chinese; files
> here are English because the repository is English-only. Maintained by the project lead (AI).
> Last updated: 2026-09-30

## Status in one line

All six workflows are green and M1's 7-day clock keeps running (done 2026-10-05 if nothing goes
red). Two fixes are with executors (T-007, T-008), a third waits for the first (T-009). One
question for you now (H-12) and one date to keep (H-13, 2026-10-16).

## Needs you

| ID | What | Why it's yours | Recommendation | Needed by |
|---|---|---|---|---|
| H-12 | Move the lead to autonomy A2: it merges Level 0 to 2 tasks after passing reviews without asking; Level 3 merges and every push still come to you | Autonomy is your setting (`lead/config.yml`) | Yes: five clean merges in a row (T-002 to T-006), which is the bar; it removes about half of the approvals you have been asked for. Default if no answer: stay at A1 | Any time |
| H-13 | On 2026-10-16, write the gate's conclusion in `docs/STRATEGY.md` section 8 as `Resolved: <what Experiment D measured> -> <decision>`, and decide O2, O8, O9 and O11 in `docs/OPPORTUNITIES.md` | The gate's reading and the product decisions are yours | Give the lead the result in one line that morning; it drafts both edits for your yes. Otherwise the build is red, and every deploy blocked, from 00:00 UTC that day until both are done | 2026-10-16, before 02:23 UTC (the first bot run) |

## Done / answered

| Item | Outcome | Recorded in |
|---|---|---|
| H-11 Merge T-005, T-006 and the Level 0 branch; push in two steps (2026-09-30) | Approved as recommended; merged as `0fa831a`, `053fe0a`, `b29c424`; checks 29 of 29; preflight green on Linux; pushed `d5bb216..3db4bf5`; `tests` green; no deploy | `lead/STATE.md` |
| T-006 (2026-09-30) | Merged as `053fe0a`: round 2 combined re-review pass, red-team none; its 15 s Windows time bound is not met (median 15.2 s), recorded rather than moved | `lead/reviews/T-006.md` |
| T-005 (2026-09-30) | Merged as `0fa831a`: round 2 re-review 12 of 12 | `lead/reviews/T-005.md` |
| H-10 Merge T-003, T-004, the W5 row; push in two steps (2026-09-29) | Preflight on Linux green; pushed `8daa0f7..6c8b785`; tests and deploy green; the gate ran 28 of 28 on CI | `lead/STATE.md` |
| T-004 (2026-09-29) | Merged as `d0eb7e8`: round 2 combined re-review 11 of 12, red-team none | `lead/reviews/T-004.md` |
| T-003 (2026-09-29) | Merged as `fec26df` after a fresh review, 12 of 12 | `lead/reviews/T-003.md` |
| H-9 Update W5 after the Quick Intel run (2026-09-29) | Method and direction only, no figures, on a branch for the next merge | `docs/BACKLOG.md` (branch `task/l0-backlog-w5`) |
| H-8 Merge three Level 0 fixes locally (2026-09-29) | Merged, not pushed: the `CLAUDE.md` manual order, the ignore rule for Quick Intel's raw answers, the benchmark script's User-Agent | `lead/STATE.md` |
| H-7 Autonomy after a clean merge (2026-09-29) | Yes; applied once T-002's merge was clean. Autonomy A1 | `lead/config.yml`, `lead/STATE.md` |
| H-6 Merge T-002 and push (2026-09-29) | Merged as `16e100e`; pushed `dc401b9..16e100e`; CI run 36455682835 green; no deploy | `lead/STATE.md` |
| T-002 (2026-09-29) | Merged as `16e100e` after a fresh review, 12 of 12 | `lead/reviews/T-002.md` |
| H-5 Start the Level 0 fix and T-002 (2026-09-29) | Yes to both, as recommended. The Level 0 fix merged locally as `82acff3`; T-002 dispatched | `lead/STATE.md` |
| H-4 Autonomy after tripwire Q1 (2026-09-28) | Stay at A0 for the next task; the lead proposes A1 again after one clean merge | `lead/STATE.md`, `lead/config.yml` |
| T-001 (2026-09-28) | Merged as `0a3098d` after a fresh review, 12 of 12 | `lead/reviews/T-001.md` |
| H-3 SessionStart hook (2026-09-28) | Created by the lead at the Owner's request in `.claude/settings.local.json`: this project and this machine only, not committed. Works only in sessions opened with this repository as the project folder | `lead/STATE.md` |
| H-2 Close backlog W11 (2026-09-28) | Approved and done: Done R23; its orphaned `COST_OF_WAITING` entry removed; `docs/OWNER.md` regenerated | commit `23157f9` |
| H-1 Push after T-001 (2026-09-28) | Pushed `c954f43..dc401b9`; CI run 36445100361 green, no deploy | `lead/STATE.md` |
| Adoption questions (2026-09-28) | All accepted as recommended: milestone M1, invariants and sign-off list, autonomy A1, `lead/` public and English, local branches without pull requests, Chinese in chat | `lead/decisions/0001-adopt-lead-workflow.md` |

## Current tasks

| Task | Level | Status | Notes |
|---|---|---|---|
| T-007 | 3 | executing | The check that forces a written conclusion on a gate's date accepts an empty or placeholder one (measured with the date forced to 2026-10-16); after this it will not |
| T-008 | 3 | executing | `snapshot-commit.sh`, run by hand, would rewrite this clone's git identity and push; after this it refuses off GitHub Actions |
| T-009 | 1 | ready, after T-007 | Your page (`docs/OWNER.md`) shows the answered 2026-09-18 gate as "12 days OVERDUE"; after this an answered gate reads as answered, and a gate 14 days out appears in "Needs you" |

## Milestones

| Milestone | Exit criteria | Status |
|---|---|---|
| M0 Loop proven | T-001 merged through the whole loop, checks green on master | **done 2026-09-28** |
| M1 CI green and staying green | `tests` green on every master run for 7 consecutive days | clock running since 2026-09-28 15:38 UTC, still green after the H-10 push; done on 2026-10-05 if no run goes red |

## Log (newest first)

- **2026-09-30** · lead · Lead #4 checked in: all six workflows green, origin merged, checks 29 of
  29. Found that the guard for the 2026-10-16 gate accepts an empty conclusion (T-007) and that
  your page shows the answered 2026-09-18 gate as overdue (T-009); started T-007 and T-008. Asked
  H-12 (A2) and wrote down what 2026-10-16 needs from you (H-13).

- **2026-09-30** · lead · Lead rotated to #4 at a clean boundary. Nothing for you to do: open a
  new conversation in this repository's folder and type /lead when you want to continue. The
  next lead's first question will be whether to move to autonomy A2 (five clean merges in a row).
- **2026-09-30** · lead · H-11 done: pushed after a green preflight on Linux; `tests` green on
  `master`, nothing deployed.
- **2026-09-30** · lead · You approved H-11. T-005 (your W5 check on the adversarial cohort can
  now be run safely: `python bench/second_oracle.py --plan --set adversarial`, then `--run`
  with your key) and T-006 (the regeneration script refuses its bots' mode off GitHub Actions)
  are merged with the Level 0 fixes; checks 29 of 29. Pushing in two steps.
- **2026-09-29** · lead · Lead rotated to #3 at a clean boundary. Nothing for you to do: open a
  new conversation in this repository's folder and type /lead when you want to continue.
- **2026-09-29** · lead · H-10 done: T-003, T-004 and the W5 row merged and pushed. The first
  deploy since 2026-09-22 ran all 28 offline steps before shipping, then passed its smoke test.
- **2026-09-29** · lead · You approved H-6 and H-7. T-002 merged and pushed; CI green on the
  pushed head, nothing deployed. Autonomy back to A1.
- **2026-09-29** · lead · T-002 passed a fresh review, 12 of 12, with no required changes. Asked
  H-6 (merge and push) and H-7 (A1 after a clean merge).
- **2026-09-29** · lead · You approved H-5. The Level 0 fix is merged locally: a check run that
  modifies a tracked file now fails, and the test that caused it restores its file exactly.
  T-002 is with an executor. Nothing pushed.
- **2026-09-29** · lead · Lead #2 checked in: the SessionStart hook works, nothing new on
  origin, all six workflows green, checks 27 of 27. Corrected one handoff note (the line-ending
  side effect comes from a test, not from `publish_numbers.py`). Asked H-5.
- **2026-09-28** · lead · Pushed; CI green on all 27 steps. Lead rotated to #2 (context at 50
  of 100 parts of the window). Open the next session in this repository's folder and type /lead.
- **2026-09-28** · lead · T-001 merged after a fresh review (12 of 12); checks 27 of 27 on
  master. M0 reached.
- **2026-09-28** · lead · My own bookkeeping commit broke the English-only rule on master
  (a quoted Chinese phrase in `lead/STATE.md`, committed without running the checks). The T-001
  reviewer caught it before anything was pushed. Fixed; autonomy demoted A1 to A0 by rule Q1.
- **2026-09-28** · lead · Adopted the project into the lead workflow. Nothing pushed.
