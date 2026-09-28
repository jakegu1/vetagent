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
| H-1 | Approve one push of master once T-001 has merged: the adoption commit plus T-001 | Every push is yours (A1), and this one publishes `lead/` in the public repository | Yes, push both together, so the first CI run on the pushed head is the one that should turn green. Default: nothing is pushed | When T-001 passes review |
| H-2 | Close backlog W11 ("Answer the 2026-09-18 gate") | It is your row, in your table of `docs/BACKLOG.md` | Yes. The gate was answered in `f962aad` (the `Resolved` line in `docs/STRATEGY.md` §8), but the row is still Open, so `docs/OWNER.md` shows it overdue. The lead marks it done and regenerates the page (Level 0). Default: left as is | Any time |
| H-3 | Optional: a SessionStart hook that shows `lead/STATE.md` at every session start | Agents may not edit their own permission files | Paste the snippet in `lead/decisions/0001-adopt-lead-workflow.md` into `.claude/settings.json`. Default: not added | When convenient |

## Done / answered

| Item | Outcome | Recorded in |
|---|---|---|
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
