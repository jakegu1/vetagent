# Review: Level 0, pin the bots' shell scripts to LF (`task/l0-sh-eol-lf`)

Written by lead #5 (from the T-008 red-team note 3 candidate). Reviewed by a fresh reviewer
subagent on 2026-10-01, in a `--no-local` scratch clone, head `b4815ce`, base `c57ed3c`.

## Reviewer's verdict (summary)

- Contract holds: `cd2e652` changes only `tests/test_bot_commits_stay_green.py` (+28, the new
  function and its call in `main()`); `b4815ce` adds only `.gitattributes`.
- Red at `cd2e652`: 167 passed, 3 failed (the two `eol: unspecified` checks, and the file's
  nested self-run failing on the same two). Green at the head: 170 of 170.
- `python lead/checks.py` at the head: 29 of 29, exit 0, tree clean.
- `git add --renormalize .` at the head left the tree clean: no index change anywhere.
- Mutants: `.gitattributes` removed from the commit, caught; `*.sh text` without `eol`, caught;
  a new `.sh` committed with CRLF, caught; `*.sh -text eol=lf`, survives (harmless: the `i/lf`
  check still catches a CRLF commit).
- Rubric 12 of 12. Required changes: none.

Optional: assert `git check-attr text` is `set` to kill the last mutant (low value). Side
effect: after the merge, this clone's working copies of `*.sh` become LF on the next checkout.

VERDICT: pass

## Lead decision

Merge under A2 (Level 0). The optional mutant is not taken: low value, and the CRLF case it
would guard is caught by the index check.
