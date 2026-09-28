# VetAgent · Owner dashboard (lead workflow)

> This page holds only what the lead needs from you. The project's own dashboard, with its
> deadlines and gates, is `docs/OWNER.md` (generated). Messages to you are in Chinese; files
> here are English because the repository is English-only. Maintained by the project lead (AI).
> Last updated: 2026-09-28

## Status in one line

Adopted on 2026-09-28. CI `tests` has been red since 2026-09-22 on one known step; T-001 fixes
it and is ready to run.

## Needs you

| ID | What | Why it's yours | Recommendation (also the default) | Needed by |
|---|---|---|---|---|
| H-4 | Autonomy after tripwire Q1: stay at A0, or restore A1 | Autonomy is yours to set | Stay at A0 for the next task, and the lead proposes A1 again after one clean merge. Reply "restore A1" to restore it now. Default: A0 | Before the next task starts |

## Done / answered

| Item | Outcome | Recorded in |
|---|---|---|
| H-3 SessionStart hook (2026-09-28) | Created by the lead at the Owner's request in `.claude/settings.local.json`: this project and this machine only, not committed. Works only in sessions opened with this repository as the project folder | `lead/STATE.md` |
| H-2 Close backlog W11 (2026-09-28) | Approved and done: Done R23; its orphaned `COST_OF_WAITING` entry removed; `docs/OWNER.md` regenerated | commit `23157f9` |
| H-1 Push after T-001 (2026-09-28) | Approved: one push once T-001 has merged (adoption, W11, T-001) | `lead/STATE.md` |
| Adoption questions (2026-09-28) | All accepted as recommended: milestone M1, invariants and sign-off list, autonomy A1, `lead/` public and English, local branches without pull requests, Chinese in chat | `lead/decisions/0001-adopt-lead-workflow.md` |

## Current tasks

| Task | Level | Status | Notes |
|---|---|---|---|
| T-001 | 1 | in review | Implemented tests-first; 27 of 27 checks reproduced by the lead; a fresh reviewer is checking it |

## Milestones

| Milestone | Exit criteria | Status |
|---|---|---|
| M0 Loop proven | T-001 merged through the whole loop, checks green on master | open |
| M1 CI green and staying green | `tests` green on every master run for 7 consecutive days | clock not started (starts with the first push after T-001) |

## Log (newest first)

- **2026-09-28** · lead · My own bookkeeping commit broke the English-only rule on master
  (a quoted Chinese phrase in `lead/STATE.md`, committed without running the checks). The T-001
  reviewer caught it before anything was pushed. Fixed; autonomy demoted A1 to A0 by rule Q1.
- **2026-09-28** · lead · Adopted the project into the lead workflow. Nothing pushed.
