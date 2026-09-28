# ADR-0001: Run development with the lead workflow

- Status: accepted
- Date: 2026-09-28
- Decided by: the Owner, on the lead's recommendations (all accepted as proposed)
- Reversibility: two-way door. `git revert <the adoption commit>`, or delete `lead/`,
  `AGENTS.md` and the marked block at the end of `CLAUDE.md`. Nothing else changed.
- Review when: tripwire Q3 fires (the workflow costs the Owner more attention than it saves),
  or at the first weekly pass after M1.

## Context

- One person and AI sessions, working directly on `master`: 329 human commits since
  2026-09-03, one pull request ever, bots committing to `master` several times a day.
- CI's `tests` workflow had been red for six days on a seam between two components that no task
  owned, and GitHub's stop-at-first-failure had hidden 21 of its 27 steps meanwhile
  (`lead/AUDIT.md`).
- The same session that implemented a change also judged it. Nothing separated the two.
- The project already keeps strong records: `docs/DECISIONS.md` (enforced by
  `tests/test_decisions_enforcement.py`), `docs/BACKLOG.md` (shape-checked), and three generated
  pages with currency tests. The repository is public and English-only by test.
- The Owner asked for the development process to be reshaped with the lead kit.

## Options

| Option | Pros | Cons | Evidence |
|---|---|---|---|
| A. Adopt; `lead/` committed, English, engineering content only | Same conventions as the rest of the repository; the existing guards check `lead/` too; executors in worktrees and fresh sessions can read it; history | Process documents become public; the Owner's lead dashboard is in English | Dry run on `f6c7c06`: an English footprint without percentages adds no failure |
| B. Adopt; `lead/` local only (untracked) | Private | Only this machine sees it; no history; still has to be English, because `tests/test_english_only.py` walks untracked files | Dry run: an untracked Chinese `lead/OWNER.md` turned that test red |
| C. Do not adopt | No new process | CI red with no owner; no independent review | `gh run list --workflow=test.yml` |

## Decision

Option A. Where the kit's defaults differ from this project's conventions, the project wins:

| Kit default | In this project | Why |
|---|---|---|
| `lead/OWNER.md` in the Owner's language | English; Chinese in chat | The repository is English-only by test |
| `github-pr` mode | `local-branches`, no pull requests | PR comments posted by agents would appear under the Owner's GitHub account |
| Squash merge | `git merge --no-ff` | Keeps the tests-first commit, which the project requires to be red before the fix |
| ADRs in `lead/decisions/` for every decision, with backfilled history | Product and engineering decisions stay in `docs/DECISIONS.md`; `lead/decisions/` records only how work is run; no backfilled ADRs | `docs/DECISIONS.md` already records them with enforcement; a second copy is a new source of drift |
| `lead/OWNER.md` as the Owner's dashboard | `docs/OWNER.md` stays the project dashboard; `lead/OWNER.md` holds only the lead's needs-you items | One dashboard |
| Next-up items and specs as the backlog | `docs/BACKLOG.md` stays the list; a spec is written when an item starts and names its W-id | Its shape check and the generated owner page read it |
| One test command | `python lead/checks.py` runs every step of `test.yml`'s offline job without stopping at the first red | GitHub's early stop hid 21 steps for six days |

Autonomy starts at A1: the lead writes specs, dispatches executors and fresh reviewers and
decides; the Owner approves every merge to `master` and every push.

## Consequences

- **Easier:** one command shows the state of all 27 CI steps; every task has a written spec and
  an independent review before it reaches `master`; a fresh session can resume from
  `lead/STATE.md`.
- **Harder:** a small task now carries a short spec and a review (Level 1); the lead must keep
  `lead/STATE.md` current, and must not put owner-private material in it.
- **Must do now:** T-001 (the red CI step); H-1 to H-3 in `lead/OWNER.md`.
- **Watch:** `lead/*.md` must never carry a percentage written as digits and a percent sign
  (`tests/test_number_coverage.py` scans every tracked markdown file), and no file under `lead/`
  may contain CJK text.

## Optional: SessionStart hook

Only the Owner can add this, because agents may not edit their own permission files. Merge it
into `.claude/settings.json` inside `"hooks"`, next to the existing `"PreToolUse"` entry:

```json
"SessionStart": [
  {
    "matcher": "startup|resume|clear|compact",
    "hooks": [
      {
        "type": "command",
        "shell": "bash",
        "command": "f=\"${CLAUDE_PROJECT_DIR:-.}/lead/STATE.md\"; test -f \"$f\" && head -n 80 \"$f\" || true",
        "timeout": 10
      }
    ]
  }
]
```
