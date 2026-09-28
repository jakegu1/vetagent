# VetAgent · Owner dashboard (lead workflow)

> This page holds only what the lead needs from you. The project's own dashboard, with its
> deadlines and gates, is `docs/OWNER.md` (generated). Messages to you are in Chinese; files
> here are English because the repository is English-only. Maintained by the project lead (AI).
> Last updated: 2026-09-29

## Status in one line

CI is green on master and M1's 7-day clock is running. Lead #2 has checked in and proposes the
next two items (H-5); nothing starts until you say yes.

## Needs you

| ID | What | Why it's yours | Recommendation | Needed by |
|---|---|---|---|---|
| H-5 | Start two items. (1) Level 0, done by the lead: `python lead/checks.py` fails when a run modifies a tracked file, and the test that rewrites `docs/EXPERIMENT_C.md` with LF endings on Windows restores it byte for byte instead. (2) T-002, Level 1, executor plus a fresh review: `publish_numbers.py` reports a missing measurement instead of crashing, and `--write` fails when it leaves work undone (why the bots stayed green while `tests` was red). | Autonomy is A0: each step needs your yes | Yes to both. I come back for a separate yes to merge and push. If you don't answer, nothing starts | Now |

## Done / answered

| Item | Outcome | Recorded in |
|---|---|---|
| H-4 Autonomy after tripwire Q1 (2026-09-28) | Stay at A0 for the next task; the lead proposes A1 again after one clean merge | `lead/STATE.md`, `lead/config.yml` |
| T-001 (2026-09-28) | Merged as `0a3098d` after a fresh review, 12 of 12 | `lead/reviews/T-001.md` |
| H-3 SessionStart hook (2026-09-28) | Created by the lead at the Owner's request in `.claude/settings.local.json`: this project and this machine only, not committed. Works only in sessions opened with this repository as the project folder | `lead/STATE.md` |
| H-2 Close backlog W11 (2026-09-28) | Approved and done: Done R23; its orphaned `COST_OF_WAITING` entry removed; `docs/OWNER.md` regenerated | commit `23157f9` |
| H-1 Push after T-001 (2026-09-28) | Pushed `c954f43..dc401b9`; CI run 36445100361 green, no deploy | `lead/STATE.md` |
| Adoption questions (2026-09-28) | All accepted as recommended: milestone M1, invariants and sign-off list, autonomy A1, `lead/` public and English, local branches without pull requests, Chinese in chat | `lead/decisions/0001-adopt-lead-workflow.md` |

## Current tasks

| Task | Level | Status | Notes |
|---|---|---|---|
| T-002 | 1 | ready, waiting on H-5 | `lead/tasks/T-002-publish-numbers-honest-exit.md` |

## Milestones

| Milestone | Exit criteria | Status |
|---|---|---|
| M0 Loop proven | T-001 merged through the whole loop, checks green on master | **done 2026-09-28** |
| M1 CI green and staying green | `tests` green on every master run for 7 consecutive days | clock running since 2026-09-28 15:38 UTC; done on 2026-10-05 if no run goes red |

## Log (newest first)

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
