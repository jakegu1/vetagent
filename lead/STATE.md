# Lead state (the baton)

> What is in flight right now. The lead updates this at every check-in and merge; a new lead
> session starts by reading it. Durable rules live in `AGENTS.md`, `lead/QUALITY.md` and
> `lead/decisions/`. Test for this file: could a stranger act on every row below?

Last updated: 2026-10-01 by lead session 5 after T-010 (Claude Code desktop, local, opened in
this repository).

## Starting a lead session

1. Read this file, then `lead/config.yml`, the Needs-you section and the latest log of
   `lead/OWNER.md`, and `lead/tasks/README.md`.
2. `git fetch`, then compare `master` with `origin/master`. Bots push to master several times a
   day; when behind, merge (never rebase) before starting work.
3. Reconcile: for each in-flight row, check the real branch, worktree or subagent result, and
   CI for all six workflows, not only `test.yml` (the command is in `CLAUDE.md`). Fix this file
   if it drifted.
4. Act on each row's next action. Then start the next ready task if WIP allows. Autonomy is
   **A2** (`lead/config.yml`): spec, dispatch, review and decide; merge Level 0 to 2 tasks after
   passing reviews and tell the Owner afterwards; ask the Owner before every Level 3 merge and
   every push, batched.
5. Run `python lead/checks.py` before every commit to master, lead bookkeeping included.
6. Check the rotation rule (`lead-handoff`). Update this file and commit.

## Standing notes

- **Open the session with this repository as the project folder** (not its parent), so that
  `CLAUDE.md`'s lead block, the untagged-probe hook in `.claude/settings.json` and the
  SessionStart hook in `.claude/settings.local.json` load. **The SessionStart hook works:** at
  the start of lead session 2 the first 80 lines of this file appeared on their own.
- **Autonomy is A2 (H-12, approved 2026-09-30).** The lead specs, dispatches, reviews and
  decides on its own, and merges Level 0 to 2 tasks into local `master` after passing reviews;
  each such merge is reported to the Owner afterwards. Level 3 merges and every push wait for
  the Owner's yes. Any escaped defect demotes one level (tripwire Q1), and the
  lead says so.
- **M1's clock is running** since run 36445100361 (2026-09-28 15:38 UTC, head `dc401b9`); still
  green on run 36754083925 (head `d033c90`, 2026-09-30 UTC, T-009's push). At each check-in, check
  `gh run list --workflow=test.yml`; any red run on master restarts it and stops new work until
  green (tripwire Q4).
- Pushing: fetch and merge origin first (never rebase), regenerate the derived pages
  (`merge.after` in `lead/config.yml`), run the checks, commit the regenerated pages if the
  merge moved them, check the commit messages for anything private, then push and watch CI.
  `git merge -F -` does not read a message from stdin here; write it to a file in the
  scratchpad and pass that file.
- The `vetagent` MCP server in `.mcp.json` points at production. It sends
  `x-mcp-client: vetagent-owner-editor` (read 2026-09-29), so its calls are filtered as ours;
  a lead session still has no reason to call its tools (invariant 7).

## In flight

| Task | Level | Branch / PR | Stage | Who | Next action |
|---|---|---|---|---|---|
| — | | | | | No task in flight. Local `master` is ahead of origin: the lead #4 handoff, the T-010 spec, the Level 0 `.gitattributes` merge (`426d8f4`) and T-010 (`47db199`); the push waits for the Owner (H-15). |

## Waiting on the Owner

- **H-15 (asked 2026-10-01): push** the local commits (lead #4's handoff, the T-010 spec,
  `426d8f4` Level 0, `47db199` T-010, this bookkeeping). Recommended: a preflight branch first
  (`test.yml` on Linux), then `master`; no deploy (nothing under `src/`). Scan outgoing messages
  for local paths, addresses and non-ASCII first.
- **H-13 (told 2026-09-30, needed by 2026-10-16; the Owner agreed to the plan): the 2026-10-16
  gate.** From 00:00 UTC that day `tests/test_gates_get_reviewed.py` is red, and so are `tests`
  and every deploy, until (a) the gate's row in `docs/STRATEGY.md` section 8 carries
  `Resolved: <what Experiment D measured> -> <decision>` and (b) O2, O8, O9 and O11 in
  `docs/OPPORTUNITIES.md` are decided and moved under "Reviewed and closed". The first bot run
  that day is `snapshot.yml` at 02:23 UTC. The plan: that morning the Owner gives the lead the
  result in one line, and the lead drafts both edits for the Owner's yes (the reading and the
  decisions are the Owner's). Nothing needed from the Owner before then. Since T-007 the
  conclusion needs an ASCII `->` with words on both sides, after `Resolved:`, in the gate's own
  row; a placeholder, U+2192, markup or the template pasted back is refused. Draft it that way,
  run `python tests/test_gates_get_reviewed.py` with the date forced to 2026-10-16 on the draft,
  and push it before 02:23 UTC (every push needs the Owner's yes).
- (H-14 done 2026-10-01, as recommended: T-007 merged as `3fb1d3d`, T-008 as `f1a767d`, then
  pushed after preflight run 36744394310 was green on Linux: `a5bcce5..26392ab`, `tests` run
  36744975640 green. T-009 merged by the lead under A2 as `235b20c`, pushed the same way after
  preflight run 36753548989 was green (the Owner page 379 of 379 on Linux, with the page's date a
  day ahead of UTC): `26392ab..d033c90`, `tests` run 36754083925 green. No deploy either time:
  nothing under `src/`. Both preflight branches deleted. Outgoing commit messages were scanned
  for local paths, addresses and non-ASCII: 27 and 13, clean.)
- (H-12 answered 2026-09-30: yes, as recommended. Autonomy A2, applied in `lead/config.yml`.)
- The Owner's own W5 steps (read Quick Intel's terms; the 17-call check on W3's adversarial
  cohort) are in `docs/BACKLOG.md` and `docs/OWNER.md`.
- (H-11 done 2026-09-30: merged T-005 as `0fa831a`, T-006 as `053fe0a`, the Level 0 branch as
  `b29c424`; checks 29 of 29. Preflight run 36669036422 green on Linux; pushed `d5bb216..3db4bf5`;
  `tests` run 36669385087 green; no deploy (nothing under `src/`). Preflight branch deleted.)
- (H-11 answered 2026-09-30: as recommended. Once T-006's round-2 re-review passes, merge
  T-005, T-006 and the Level 0 branch into local `master`, then push in two steps: the merged
  tree to a preflight branch first (`test.yml` on Linux, no deploy), then `master` once that is
  green. If T-006 does not pass, ask again before merging the other two alone.)
- (H-10 done 2026-09-29: merged origin (six bot commits), T-003 as `fec26df`, T-004 as
  `d0eb7e8`, the W5 row as `6c8b785` (its `docs/OWNER.md` conflict resolved by regenerating);
  checks 28 of 28. Preflight branch run 36557264402 green on Linux; pushed
  `8daa0f7..6c8b785` (50 commits); `tests` run 36557714268 green; `deploy` run 36557714265
  green: the gate reported "28 of 28 steps passed" in its log, then the deploy, the smoke test
  and IndexNow passed. Preflight branch deleted.)
- (H-9 answered 2026-09-29: update W5 with the method and the direction of the result, no
  figures, merged with T-003 and T-004. Figures derived from Quick Intel's answers stay out of
  this public repository, `lead/` included, until the Owner has read Quick Intel's terms.)
- (H-8 answered 2026-09-29: merge the three Level 0 branches locally, no push. Merged as
  `a8a758d`, `08915db`, `d592f8d`.)
- (H-7 answered 2026-09-29: yes; applied after the clean merge. Autonomy A1.)
- (H-6 done 2026-09-29: T-002 merged as `16e100e`; pushed `dc401b9..16e100e`; CI run
  36455682835 green; no deploy.)
- (H-5 answered 2026-09-29: yes to both items, as recommended. Item 1, the Level 0 fix, merged
  as `82acff3`; item 2 was T-002.)
- (H-4 answered 2026-09-28: stay at A0 for the next task; the lead proposes A1 again after one
  clean merge.)
- (H-1 done 2026-09-28: pushed `c954f43..dc401b9`; CI green on it.)

## Next up

No task is specced. Candidates below; at A2 the lead may spec, dispatch and (Levels 0 to 2, after
passing reviews) merge any of them; Level 3 merges and every push wait for the Owner's yes. Items
marked "Owner's call first" need the Owner before a spec.

**The dates, in order** (all measured or read on 2026-10-01):
1. **2026-10-05 15:38 UTC: M1 completes** if no `tests` run on `master` goes red; record it in
   `lead/QUALITY.md`'s milestone table and `lead/OWNER.md`.
2. **About 2026-10-05: the first weekly pass** (`lead-weekly`; none since the adoption on
   2026-09-28). Tripwire Q3 is over its threshold (H-12, H-13, H-14 in two days after H-5 to H-11
   in three); A2 took the Level 0 to 2 merges off the Owner.
3. **By 2026-10-14: a new correction** (below), or the build is red on 2026-10-15 UTC.
4. **2026-10-16: the gate** (H-13). The Owner's page lists it under "Needs you" from 2026-10-02.

**Every check that can go red on the calendar alone** (a scan of `tests/` for `date.today()`,
2026-10-01): the gates and their parked entries in `tests/test_gates_get_reviewed.py`
(2026-10-16, 2026-12-04, 2027-03-04); in `tests/test_owner_page.py` the corrections window
(below), the page's age (7 days) and the newest snapshot's age (2 days), the last two kept fresh
by the bots. `tests/test_coverage_matrix.py` only prints fixture ages. Re-scan when a test is
added.

**Dated: the corrections window.** `tests/test_owner_page.py` requires an entry in `CORRECTIONS`
(`tools/owner.py`) dated within 14 days. After T-009 the newest is 2026-09-30, so the test goes
red on **2026-10-15 UTC** unless a newer entry exists: by 2026-10-14, add a real correction, or a
dated "nothing to report" (the test's own words), on a branch and pushed. It went unwatched once:
the 2026-09-19 entry would have turned master red on 2026-10-04, one day before M1 completes.

**Dated, checked 2026-09-30:** on 2026-10-16 `tests/test_gates_get_reviewed.py` turns red unless
the gate's row carries a conclusion and O2, O8, O9 and O11 are decided (H-13, told to the Owner).
T-007 makes a placeholder conclusion red as well, so it must be written as
`Resolved: <what the measurement said> -> <decision>` with real words on both sides. Check on
2026-10-14 that H-13 is on track.

Suggested order (lead #4, for lead #5): the dates above first. Then, if cheap before 2026-10-16,
T-007's follow-ups (decoding HTML entities before the markup step is measured at 98 of 98 still
passing). Then the two test-only follow-ups on `tests/test_bot_commits_stay_green.py` (T-008's
surviving mutants; T-006's speed and failed-read items), one after the other, never in parallel
(same file). Then the T-004 node-property follow-up.

- Candidate, Level 3 area (the deploy gate), from T-004's round-2 re-review: a YAML node
  property (`&anchor` or `!tag`) before an unclosed quote still ends the job early in the
  runner and the guard's reader (a one-line fix is in `lead/reviews/T-004.md`, follow-up 1);
  test gaps: an unclosed value under `with:`, escaped and doubled quotes, and the reader's own
  refusal pinned to the named line; the guard's `if:` reader misses a double-quoted value
  continued at six spaces (deliberate-edit class).
- Candidate, test file only, from T-006's round-2 re-review: AC 6's 15 s bound on Windows is
  not met (median 15.2 s); run each near-miss value of `GITHUB_ACTIONS` with one argument
  instead of three (about 1.7 s), bring the file's own timing line over the child check, make
  `_what_moved` say that a failed read is a failed read, and bring the module docstring up to
  the Actions rule (`lead/reviews/T-006.md`, round 2 lead decision). T-008's independent review
  adds to the same file (do it after T-008 merges): the status canary shares the failed-read
  blind spot (a missing `.git` read twice compares equal); the docstring should cover T-008's
  runs; the whole file now takes about 25.7 s on Windows (was 13.2 s).
- Candidate, test file only, from T-008's reviews: four surviving mutants of
  `snapshot-commit.sh` (`lead/reviews/T-008.md`): the nothing-new branch without `exit 0`
  (require no `commit` or `push` in that call's git trace, already captured); a `[Tt]rue` match
  (add `True` to the refused values); the retry loop cut to two attempts (add a case where every
  push fails: exit 1, `LOST`, five attempts, sleeps 10 to 50); `date` without `-u` (run the
  calls on Actions under a `TZ` whose date differs from UTC's). Not in parallel with the T-006
  follow-up (same file).
- Candidate, test file only, T-010's review optionals (`lead/reviews/T-010.md`): a fixture with
  no `##` heading before a stray dated row (kills mutant M4, `gates()` reading from character 0
  when section 8 is missing); the AC 6 test combines the guard's two conditions itself, so a
  third one added to the guard would go unseen. Neither is live today.
- Candidate, Level 3 area (the gate guard), T-007's follow-ups (`lead/reviews/T-007.md`): "variant
  B", typing `Resolved:` and pasting the whole failure message after it, is still accepted
  (judging the text after each `Resolved:` up to the next one closes it, measured, not applied);
  the template with entity-escaped brackets is accepted (decode with `html.unescape` before the
  markup step, measured: 98 of 98 still pass); three surviving mutants of the markup step and the
  row lookup need self-tests. Before 2026-10-16 if cheap; none of them is live today.
- Candidate, Level 1, from T-003's review: when the scorecard's production row is in the form
  `bench/scorecard.py` is not printing, its two targets report `absent` and `pattern not found`,
  and the second gets the "restore the sentence" advice, wrong for a generated row; three
  surviving mutants (the owner-powers advice naming the wrong file, the advice for a key
  nothing computes, a single rewrite listed); a line matching both retracted-claim patterns is
  printed twice, so its count is untrue.
- Candidate, Level 1: `_owner_power_figures()` raises on invalid JSON in
  `bench/owner_powers.json`, while the production readers treat an unreadable artifact as not
  measured. Same class as T-002.
- Candidate, Level 3 area (CI script): `regenerate-derived.sh` sends each generator's output to
  `/dev/null`, so a failing bot run shows only `::error::publish_numbers.py failed`, not what
  is left to fix.
- Candidate, Owner's call first (public text): the `docs/EXPERIMENT_C.md` production sentences
  quote the live rate even below the scorecard's 100-answer floor, and compute it as
  `100*u/n` while the scorecard row now uses `(u/n)*100`; the two round differently on 314 of
  about two million (u, n) pairs (T-001 review, problem 4). Whether a below-floor rate belongs
  in that text is a public-claim decision.
- Candidate, investigate first: deploy tooling is unpinned (`uv.lock` and `pylock.toml` are
  gitignored as build artifacts). Whether to commit a lock is a decision for
  `docs/DECISIONS.md`.
- Candidate, check mode vs the suite: `unsourced_competitor_figures()` fails check mode (and,
  after T-002, `--write`), but no test in the suite runs it, so CI would not see an undated
  competitor figure. Decide whether a test should, or whether check mode should not.
- Taken by lead #4 and removed from this list: the `snapshot-commit.sh` guard (now T-008, with
  a behavioural test of its retry path). The stray line 123 in `tests/test_gates_get_reviewed.py`
  (a mangled-heredoc leftover, a comment) is removed inside T-007 in its own commit; a scan of the
  repository for the same shape found no other.

## Rotation

The rule (`lead/config.yml`): rotate at about 0.4 of the context window or 72 hours, at a
natural boundary. **The context can be measured:** the desktop app's `get_usage` session tool
(load it with ToolSearch, `mcp__ccd_session_mgmt__get_usage`, session "self") returns tokens used
and the window. Lead session 4 rotated on 2026-10-01 after H-14 at 549,497 of 1,000,000 tokens
(55 of 100 parts), measured; it had passed the threshold unnoticed while reviews were running,
so check it at each natural boundary rather than once. Lead session 3 rotated on 2026-09-30 and
session 2 on 2026-09-29 on estimates; session 1 on 2026-09-28 at 50 of 100 parts.

## Handoff notes for lead #5

- **Open the session in this repository's folder and type /lead.** Nothing is in flight:
  `master` is `d033c90` on origin (T-007, T-008 and T-009 pushed; `tests` green; no deploy) plus
  the handoff commit, which is local and goes out with the next approved push.
- **Your first job is the dates** in Next up: M1 on 2026-10-05, the first weekly pass, a new
  correction by 2026-10-14, the gate on 2026-10-16. Nothing needs the Owner before 2026-10-16
  except pushes.
- **Autonomy is A2** (H-12): merge Level 0 to 2 after passing reviews and tell the Owner
  afterwards; Level 3 merges and every push are the Owner's. H-14's approval is used up.
- **Before every push**, scan the outgoing commit messages for local paths, e-mail addresses and
  non-ASCII (lead #4 did it with a short script in its scratchpad, which is gone: rewrite it, and
  watch it find something in older history before trusting a clean result). Push a preflight
  branch first while M1 runs; `test.yml` runs on every branch, `deploy.yml` only on `master`
  pushes touching `src/**`, `pyproject.toml` or `wrangler.jsonc`.
- **Two traps that bit lead #4:** a bash heredoc with quotes and backticks in a review record
  (nothing ran, but use the Write or Edit tool for every record), and a correction sentence of
  its own that a reviewer found not quite true (a correction entry has to be true in every word;
  have it reviewed).
- **A local date ahead of UTC** (after 16:00 UTC here) makes regenerated pages carry tomorrow's
  local date. T-009's review proved the Owner page is fully determined by its stamped date, so
  such a page passes on CI; a change that is only the date and the recent-commit list is still
  left to the bots (`merge.after`).
- **W5 is the Owner's, and it can be run now.** `python bench/second_oracle.py --plan --set
  adversarial`, then `--run --set adversarial` with their key: 17 calls, about 34 s, written to
  `bench/second_oracle_adversarial.json` (git-ignored); it refuses to start over an existing file.
  `--report bench/second_oracle.json` re-reads the earlier answers with the new classes. Raw
  answers and any figure derived from them stay out of this repository until the Owner has read
  Quick Intel's terms (H-9). The script cannot see how much of the month's allowance is spent.
- **Resuming an interrupted executor:** the previous process can end mid-round (it did on
  2026-09-30). Check the task branch and worktree for commits before assuming nothing landed;
  T-006's round 2 was complete on its branch with no READY report.
- **Scratch clones:** use `git clone --no-local`. A reviewer's hardlinked local clone reached only
  170 of 651 commits once (cause not found; see the log).
- **Agents in parallel:** give each executor and reviewer its own scratchpad subfolder by name
  (`lead/PITFALLS.md`). The Write and Edit tools decode backslash-u escapes into real
  characters; scan `lead/` for non-ASCII control characters before committing.

## Baseline

Before the lead kit, recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows,
Python 3.13.4, 19.0 s): 26 of 27 steps passed; the red one was `tests/test_published_numbers.py`.
After T-001 (`0a3098d`, 2026-09-28): 27 of 27. **Lead session 2 at `24a0a73` (2026-09-29):
27 of 27 in 19.0 s. After the Level 0 merge (`82acff3`): 27 of 27, and the run leaves the tree
clean. After T-002 (`16e100e`): 27 of 27, clean tree; `tests/test_published_numbers.py` 70 of
70. After H-10 (`6c8b785`): 28 of 28 (T-004 added `tests/test_deploy_gate.py`, 125 of 125);
`tests/test_published_numbers.py` 111 of 111; about 55 s locally. No failure is known.**
**After T-009 (`235b20c`, 2026-10-01): 29 of 29 in 87.2 s, tree clean; `tests/test_owner_page.py`
379 of 379 (T-009; 3.1 s, was 0.7 s). On CI, preflight 36753548989 and `master` 36754083925 on
`d033c90`: `test`, `upstream-contract` and `backfill-roundtrip` green.**
**After H-14's merges (`f1a767d`, 2026-10-01): 29 of 29 in 96.1 s, tree clean;
`tests/test_gates_get_reviewed.py` 98 of 98 (T-007), `tests/test_bot_commits_stay_green.py` 164
of 164 in about 25 to 30 s on Windows (T-008; was 13.2 s).**
**After H-11 (`b29c424`, 2026-09-30): 29 of 29 in 63.0 s. T-005 added `tests/test_second_oracle.py` (216 of 216, 0.5 s); after T-006 `tests/test_bot_commits_stay_green.py` runs the real script in scratch repositories (118 of 118, 13.2 s on Windows).** On CI (Linux), preflight run 36669036422 and `master` run
36669385087 on `3db4bf5`: `test`, `upstream-contract` and `backfill-roundtrip` green; the
regeneration script's 29 calls took 0.4 s there, so T-006 costs the deploy gate almost nothing.
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
**On CI:** `tests` was red from 2026-09-22 12:05 UTC to 2026-09-28: 32 runs, every one failing
at the step "Published accuracy figures match the benchmark". Run 36445100361 on `dc401b9`
(2026-09-28 15:38 UTC) is green: job `test` 27 of 27 steps, none skipped, and
`upstream-contract` and `backfill-roundtrip` succeeded. Run 36455682835 on `16e100e`
(2026-09-28 17:05 UTC, the H-6 push) is green: `test`, `upstream-contract` and
`backfill-roundtrip` succeeded; `benchmark` was skipped, as on every push (it runs only on a
schedule or a manual dispatch). No deploy ran. On `6c8b785` (2026-09-29 10:47 UTC, the H-10
push): `tests` run 36557714268 green, and `deploy` run 36557714265 green, the first deploy since
2026-09-22 and the first to run the whole offline suite first: its gate step logged "28 steps
from job 'test'" and "28 of 28 steps passed in 25.2s" before `pywrangler deploy`, the smoke
test and IndexNow. After it, the latest run of each of the six workflows had succeeded.
**No local side effect since `82acff3`:** `tests/test_number_coverage.py` restores
`docs/EXPERIMENT_C.md` byte for byte, and `python lead/checks.py` now exits 1 when a run
modifies a tracked file. If it lists one, find the step that wrote it; do not restore it by
hand and move on.

## Recent decisions

- 2026-10-01: T-009 merged by the lead under A2 as `235b20c` after a fresh review (12 of 12, no
  required changes). The reviewer found one sentence of the lead's own correction text not quite
  true (only the table cell was bold); the lead fixed it on the branch before merging (`f53417b`,
  `78c9275`), without a second review: a text fix in the reviewer's own words. Pushed under the
  Owner's H-14.

- 2026-10-01: H-14 approved as recommended. T-007 merged as `3fb1d3d` and T-008 as `f1a767d`
  (`--no-ff`, the tests-first commits kept). The post-merge regeneration moved only date-driven
  lines and the recent-commit list of `docs/OWNER.md` (local date 2026-10-01, UTC still
  2026-09-30), so it was restored and left to the bots (`merge.after`).

- 2026-09-30: the Owner answered H-12 as recommended: autonomy A2. The lead now merges Level 0
  to 2 tasks after passing reviews and reports each merge afterwards; Level 3 merges and every
  push still wait for the Owner (`lead/config.yml`).

- 2026-09-30: lead #4 put a new finding ahead of lead #3's list: the gate guard that decides
  whether the build goes red on 2026-10-16 accepts a placeholder conclusion (T-007, Level 3,
  because it enforces a pre-registered rule). The rule it enforces is the form its own failure
  message already asks for (`<what the measurement said> -> <decision>`), so no gate, test or
  threshold changes and no sign-off is needed; the Owner is told the form in H-13. T-008 (lead
  #3's first item) runs beside it. T-009 waits for T-007 so the Owner page and the guard share one
  rule instead of two.

- 2026-09-30: H-11 done as recommended: T-005, T-006 and the Level 0 branch merged and pushed
  in two steps (a preflight branch, then `master`); no deploy. T-006's AC 6 (15 s on Windows)
  is recorded as unmet (median 15.2 s) and not moved: the overrun came from the lead's own
  round-1 decision, and a slower local suite is not a blocking class under the round cap.
- 2026-09-30: both tasks went back for one round although their first verdicts passed, because
  each lost points in the class it existed to close (T-005: a share over rows that could not
  answer it; T-006: a check that could not run still passing the CI step). Both lessons are in
  `lead/PITFALLS.md` as spec-writing rules.
- 2026-09-29: lead #3 reordered lead #2's list: T-005 first (it unblocked the Owner's W5 step,
  due 2026-10-16), T-006 beside it (a plausible accident with data loss and an unapproved push),
  and the deploy gate's node-property variant later (a contrived edit that `tests` catches).
- 2026-09-29: H-10 done as recommended: T-003, T-004 and the W5 row merged and pushed in two
  steps, a preflight branch first (Linux, no deploy), then `master` (tests and a deploy). The
  deploy now runs every offline step before it ships; `.github/scripts/offline_suite.py` and
  its guard join the Level 3 list in `lead/QUALITY.md`. The T-004 round-2 residuals are one
  follow-up candidate, per the round cap.
- 2026-09-29: T-002 merged as `16e100e` (`--no-ff`, the tests-first commit kept) after a fresh
  review, 12 of 12 (`lead/reviews/T-002.md`), and pushed with the Owner's yes (H-6). The merge
  was clean (checks 27 of 27 on master, CI green on the pushed head), so autonomy is back to A1
  as the Owner approved in advance (H-7). The post-merge regeneration again changed only
  date-driven lines and the recent-commit list; left to the bots (`merge.after`).
- 2026-09-29: the Owner answered H-5 as recommended: both items. The Level 0 fix merged as
  `82acff3` (guard `e54f2bb` watched red first, fix `f1156eb`). Its post-merge regeneration
  changed only the date-driven parts of `docs/OWNER.md` and its recent-commit list, which
  `tests/test_owner_page.py` excuses; not committed, because the bots regenerate on the UTC
  date and the two would conflict before the next push. `lead/config.yml` `merge.after` says so.
- 2026-09-29: T-002 specced at Level 1 (the `KeyError` and `--write`'s exit status together:
  same file, same area, one fix commit each). The line-ending side effect is a separate Level 0
  item, because its writer turned out to be a test, not `publish_numbers.py`. Both put to the
  Owner as H-5.
- 2026-09-28: the Owner answered H-4 as recommended: autonomy stays A0 for the next task, and
  the lead proposes A1 again after one clean merge.
- 2026-09-28: T-001 merged (`0a3098d`, `git merge --no-ff`, the tests-first commit kept):
  review 12 of 12, verdict pass (`lead/reviews/T-001.md`). Milestone M0 (loop proven) reached.
- 2026-09-28: tripwire Q1 fired. The lead's own commit `f38ce82` put a CJK quote into
  `lead/STATE.md`, which broke the English-only rule on master; it was committed without a
  checks run and found by the T-001 reviewer. Fixed in `5959a8b`. **Autonomy demoted A1 to
  A0** (`lead/config.yml`). H-1's explicit approval (merge and push T-001) still stands.
- 2026-09-28: adopted the lead workflow (`lead/decisions/0001-adopt-lead-workflow.md`): lead/
  public and English, local-branches, merge commits instead of squash; `docs/OWNER.md`,
  `docs/BACKLOG.md` and `docs/DECISIONS.md` stay the project's records.

## Lead history

| # | Session | From | To | Why it ended |
|---|---|---|---|---|
| 1 | Claude Code desktop, local (opened in the parent folder) | 2026-09-28 | 2026-09-28 | Rotation rule: context at 50 of 100 parts of the window |
| 2 | Claude Code desktop, local (opened in this repository) | 2026-09-29 | 2026-09-29 | Rotation rule at a natural boundary after H-10; context judged past the threshold (not measured) |
| 3 | Claude Code desktop, local (opened in this repository) | 2026-09-29 | 2026-09-30 | Rotation rule at a natural boundary after H-11; context judged past the threshold (not measured) |
| 4 | Claude Code desktop, local (opened in this repository) | 2026-09-30 | 2026-10-01 | Rotation rule at a natural boundary after H-14 (T-007, T-008, T-009 pushed, nothing in flight); context measured at 55 of 100 parts of the window |
| 5 | next session, opened in this repository | | | |

## Log (newest first; keep the last ~20 lines)

- 2026-10-01: lead #5 check-in. Merged origin (six bot commits, `dd2d987`); every workflow's
  latest run green; M1 still running. Specced T-010 (Level 1: T-009's follow-ups, the page
  dropping a gate whose row is answered while its parked entries still fail the build) and
  dispatched it to a worktree. Did the Level 0 `.gitattributes` item on a branch (test watched
  red: both scripts "eol: unspecified"); fresh review 12 of 12, merged under A2 as `426d8f4`
  (`lead/reviews/L0-sh-eol-lf.md`).
- 2026-10-01: T-010 READY at `40d77ba`; fresh review 12 of 12 (AC 1 reproduced on the real
  files with the 2026-10-16 row answered and O2, O8, O9, O11 open: the page and the guard agree);
  merged under A2 as `47db199`. Regeneration moved only the recent-commit list (left to the
  bots). Worktree and branch removed. Push asked of the Owner as H-15.

- 2026-10-01: T-009 pushed: preflight run 36753548989 green (the Owner page 379 of 379 on Linux
  with its date a day ahead of UTC); `master` `26392ab..d033c90`; `tests` run 36754083925 green;
  no deploy; preflight branch deleted. Lead #4 hands off to lead #5 (rotation rule: context
  measured at 549,497 of 1,000,000 tokens; natural boundary, nothing in flight).

- 2026-10-01: T-009 review 12 of 12 (11 mutants caught; 101 forced dates; Python 3.12 run; the
  page proven independent of the clock). The lead fixed one sentence of its own correction text,
  then merged T-009 as `235b20c` (A2). Checks on master 29 of 29; `tests/test_owner_page.py` 379
  of 379. Regeneration moved only the recent-commit list (left to the bots). Worktree and branch
  removed. Pushing through a preflight branch (H-14).

- 2026-10-01: T-009 READY at `3af074d` (363 passed; CONTRACT HOLDS; acceptance-test fix
  `e3f3204` accepted: a synthetic gate's name contained "tomorrow"). Its executor found that
  master goes red on 2026-10-04 UTC: the Owner page's corrections list must have an entry within
  14 days and the newest was 2026-09-19. Measured by the lead (green to 2026-10-03, red on
  10-04). Two real, unentered mistakes fit: the page's answered gate shown overdue, and T-007's
  false "watched red" claim. Amended into T-009 before review; the lead wrote the text.

- 2026-10-01: H-14 pushed. Preflight run 36744394310 green on Linux; `master` pushed
  `a5bcce5..26392ab`; `tests` run 36744975640 green (`test`, `upstream-contract`,
  `backfill-roundtrip`); no deploy. Preflight branch deleted. M1 still running.

- 2026-10-01: H-14 yes. Origin had nothing new. Merged T-007 (`3fb1d3d`) and T-008 (`f1a767d`)
  at their reviewed heads; checks on master 29 of 29, exit 0, tree clean. Next: T-009 dispatched
  from the bookkeeping commit; the batch pushed to `preflight/h-14` first.

- 2026-09-30: T-007 round 2 combined re-review: 12 of 12, pass, red-team none (50 markup texts,
  20 row-lookup scenarios, 15 mutants of round 2's code). Decision: merge. Both Level 3 tasks
  wait for the Owner: asked H-14 (merge both, push through a preflight branch, then T-009 the
  same way). T-009's spec amended before dispatch: the template on the Owner page goes in a code
  span (entity-escaped brackets are still accepted by the guard; a follow-up).

- 2026-09-30: T-008 red-team: none (15 of 19 mutants caught; 31 near-miss values and names, 18
  invocations, CRLF emulated, `GIT_*` decoys: all held). Both reviews pass; decision: merge,
  waiting for the Owner with T-007. Four surviving mutants and an LF pin filed as candidates.

- 2026-09-30: T-008 independent review 12 of 12, pass (`lead/reviews/T-008.md`); red-team
  pending. T-007 round 2 READY at `19e3c60` (98 passed; named changes (c), (d), (e) each red
  first, as shown); the lead decided its two residuals before the re-review (variant B a
  follow-up; a line separator in a row fails closed) and dispatched the combined re-review.

- 2026-09-30: T-007 round 1 reviews: independent 12 of 12, pass; red-team 2 material. The guard
  accepted its own template and message pasted back, and markup that never renders (an HTML
  comment's `-->` taken as the arrow); a leak of `check` in the self-test harness would hide
  every red. Also a second table's same-dated row could answer a gate, against AC 4. Back for
  round 2, the last (lead decision in `lead/reviews/T-007.md`). T-008 READY at `1f9fba8`
  (CONTRACT HOLDS; the new checks' Windows median 9.85 s against a 10 s target, over it in 4 of
  10 runs); its independent and red-team reviews dispatched.

- 2026-09-30: H-12 yes (as recommended): autonomy A2. The Owner also agreed to H-13's plan for
  2026-10-16.

- 2026-09-30: T-007 READY at `8e14f10` (tests-first `521dfa6`: 12 red at that commit, no
  traceback; fix `37a9f3f`; stray line `8e14f10`); the lead saw 29 of 29 claimed and the contract
  holding by hunks (the kit script says BROKEN because the guard and its self-tests share one
  file). The executor measured a residual the threat model names: U+2192 counted as the
  conclusion's arrow, so a placeholder placed before the action text was answered by the
  table's own arrows. Amended before review (ASCII arrow only; named changes (a) and (b)).

- 2026-09-30: lead #4 check-in. The latest run of each of the six workflows succeeded. Merged
  origin (five bot commits) as `c597846`; checks 29 of 29, tree clean. Checked the 2026-10-16
  item early and measured its guard: with today forced to 2026-10-16, a bare `Resolved:` and
  `Resolved: no` both pass `tests/test_gates_get_reviewed.py`, whose docstrings say an audit
  watched both turn it red (the check is a substring test since `1762bd3`). Wrote T-007 (that
  guard, Level 3) and T-008 (the `snapshot-commit.sh` guard, Level 3), committed as `de567c0`,
  dispatched both in parallel (no file in common). Wrote T-009 (Level 1, the Owner page shows
  the answered 2026-09-18 gate as 12 days overdue in bold; after T-007). Asked H-12 (A2) and
  told H-13 (what 2026-10-16 needs).

- 2026-09-30: lead #3 hands off to lead #4 (rotation rule, natural boundary, nothing in flight).
- 2026-09-30: H-11 done. Preflight run 36669036422 green on Linux; pushed `d5bb216..3db4bf5`
  (40 commits); `tests` run 36669385087 green; no deploy. Preflight branch deleted; the three
  worktrees and task branches removed.
- 2026-09-30: T-006 round 2 passed its combined re-review (pass, RED-TEAM none); AC 6's 15 s
  bound on Windows is not met (median 15.2 s) and is recorded, not moved (lead decision in
  `lead/reviews/T-006.md`). The Owner approved H-11 as recommended. Merged T-005 as `0fa831a`,
  T-006 as `053fe0a` and the Level 0 branch as `b29c424` (a third commit, `893892b`, says in
  `CLAUDE.md` that the script now refuses its bots' mode off CI). Regeneration moved only the
  recent-commit list (left to the bots). Checks on master: 29 of 29, exit 0, tree clean.
- 2026-09-30: the session was resumed after the Claude Code process ended mid-round. T-006's
  executor had committed all of round 2 (`613f5bd`, `2958fc2`, `5d89eba`, `91e5d72`, `7a1a81a`)
  and left a clean worktree, but no READY report; the lead verified CONTRACT HOLDS and 118 of
  118 on the test file and dispatched the combined re-review. This clone's `user.name` checked
  unchanged. Merged origin's four snapshot commits as `0c02090`.
- 2026-09-30: T-005 round 2 passed its fresh re-review (12 of 12); decision: merge in the batch.
  T-006 round 1 passed both reviews (independent 12 of 12, red-team none) and went back once
  anyway: both reviewers found that "not run here" still lets the CI step pass. Two spec lessons
  added to `lead/PITFALLS.md`. Level 0 branch gained the W5 command line (`dcf3dfc`).
  Observed, cause not found: a reviewer's first local clone of this repository reached only 170
  of 651 commits (a missing parent object); a second clone minutes later was complete, and the
  main checkout's `git fsck --connectivity-only` is clean. A hypothesis, not a finding: a
  concurrent automatic gc while agents committed in worktrees. `git clone --no-local` avoids
  the hardlinked objects.
- 2026-09-30: T-006 READY at `e46cddc` (tests-first `0d9b8f7`, red on all 15 refused calls:
  the scratch identity rewritten and its uncommitted change gone). The lead saw CONTRACT HOLDS
  and only the two files in scope. Independent and red-team reviews dispatched in parallel.
  Level 0 committed on its branch as `0c6be16`: the `CLAUDE.md` note about the editor's
  client name was stale since `82e2470` (checks 28 of 28).
- 2026-09-29: lead #3 check-in. Merged origin (two production-probe bot commits) as `b1ecff6`;
  checks 28 of 28, tree clean; the latest run of all six workflows green; M1 still running.
  Wrote T-005 (Level 2): the Owner's remaining W5 step cannot be run safely today, because
  `bench/second_oracle.py` cannot select the adversarial cohort, paces calls faster than the
  free tier allows, and would overwrite the only copy of the earlier answers. Dispatched it.
  Wrote T-006 (Level 3) and dispatched it in parallel (no file in common): the regeneration
  script's bots' mode refuses to run outside GitHub Actions. Reordered from lead #2's list on
  purpose: a mistyped argument there is a plausible accident that rewrites the clone's git
  identity, can discard uncommitted work and pushes; the deploy gate's node-property variant
  needs a contrived edit and `tests` catches it.
- 2026-09-29: lead #2 hands off to lead #3 (rotation rule, natural boundary, nothing in flight).
