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
| — | Nothing open. | | | |

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
| T-001 | 1 | ready | Fixes CI's only red step; the first run of the loop |

## Milestones

| Milestone | Exit criteria | Status |
|---|---|---|
| M0 Loop proven | T-001 merged through the whole loop, checks green on master | open |
| M1 CI green and staying green | `tests` green on every master run for 7 consecutive days | clock not started (starts with the first push after T-001) |

## Log (newest first)

- **2026-09-28** · lead · Adopted the project into the lead workflow. Nothing pushed.
