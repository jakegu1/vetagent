---
id: T-009
title: Show answered gates as answered, and put a gate that is coming due in Needs you
status: done             # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 1                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: [T-007]      # calls gate_row_answered, which T-007 adds; dispatch after T-007 merges
decisions: [ADR-0001]
backlog: none            # found by lead #4 on 2026-09-30; no BACKLOG row
---

## Context

`tools/owner.py` generates `docs/OWNER.md`, the page the Owner reads first ("What you need to
know"). Two of its sections are about the decision gates in `docs/STRATEGY.md` section 8.

**An answered gate is shown as overdue.** The gate table under "## The dates that decide things"
(built in `render()`, about line 632) and the timeline chart (`mermaid_gate_timeline()`, about
line 425) label every gate with `_when(_days(date, today))`, which says `**N days OVERDUE**` for
any date in the past. The 2026-09-18 gate was answered (its row carries a `Resolved:`
conclusion), and the page generated on 2026-09-30 shows it as "**12 days OVERDUE**" in the table
and "Is anyone using it - 12 days OVERDUE" in the chart. The same will happen to every gate after
its date, answered or not, so the one alarm that matters on a gate's day looks like the ones that
do not.

**A gate coming due is not in "Needs you".** "## Needs you, soonest first" lists the Owner's
backlog items (`## Yours` in `docs/BACKLOG.md`, dated by `OWNER_DUE`) and `EXTRA_ACTIONS`. A gate
is not in it, although only the Owner can read it and decide, and from the gate's date
`tests/test_gates_get_reviewed.py` fails the build (and so every deploy, which runs that test
first) until (a) the gate's row carries a conclusion and (b) every entry in
`docs/OPPORTUNITIES.md` parked until that gate is decided and moved under "## Reviewed and
closed". For 2026-10-16 those entries are O2, O8, O9 and O11. Nothing on the Owner's page says
any of this.

T-007 adds `gate_row_answered(row)` to `tests/test_gates_get_reviewed.py`: the one rule for
whether a gate row carries a conclusion (`Resolved:` followed by `<what the measurement said> ->
<decision>`). This task uses that rule; it does not write a second one.

## Goal

On the Owner's page, an answered gate reads as answered; an unanswered gate keeps its countdown
or its OVERDUE; and an unanswered gate that is 14 days or less from its date, on it, or past it
is a row in "Needs you" that says what to write, which parked entries to decide, and what
happens to the build if nothing is done.

## Scope

**In:** the gate labels in the gate table and the timeline chart; gate rows in "Needs you" and
their subsections; reading the parked-entry ids out of `docs/OPPORTUNITIES.md`; tests;
regenerating `docs/OWNER.md`.

**Out:** `docs/STRATEGY.md`, `docs/OPPORTUNITIES.md`, `docs/BACKLOG.md`, `tests/test_gates_get_reviewed.py`
(T-007's, unchanged here), the other sections of the page, `OWNER_DUE`, `COST_OF_WAITING` and
`EXTRA_ACTIONS` (a gate row carries its own generated cost line, so none of those tables gains
an entry), and every other file.

## Files in scope

- `tools/owner.py`
- `tests/test_owner_page.py` (new test functions; `main()` already discovers `test_*` by name)
- `docs/OWNER.md` (regenerated with `python tools/owner.py --write`, never edited by hand)
- **Named changes to existing tests:** none. Conflict search (2026-09-30), each still holding
  after this change: `test_the_page_is_current` renders with the page's own stamped date, so a
  gate entering "Needs you" on a date is not drift; `test_every_owner_item_says_what_waiting_costs`
  fails on `_not stated` anywhere on the page, so a gate row must render its own "If you do
  nothing" line, and its orphan check covers `COST_OF_WAITING` keys only;
  `test_a_cost_of_waiting_is_a_consequence_not_a_restatement` iterates `COST_OF_WAITING` only;
  `test_the_diagrams_are_generated_and_cannot_drift` requires every gate on the timeline with
  its real date; `test_no_jargon_reaches_the_owner_undefined` requires each listed specialist word
  used on the page to be in `GLOSSARY` ("gate" already is); `test_it_reads_the_real_gate_table`
  requires `gates()` to read `docs/STRATEGY.md`. Any other older test failing means BLOCKED.

## Acceptance criteria

1. **Answered reads as answered.** For a gate whose row `gate_row_answered` accepts, the gate
   table's "When" cell and its timeline label say it is answered (the word is yours, for example
   "answered"), with no "OVERDUE", "TODAY", "tomorrow" or "in N days". With the real files and
   the real date, the 2026-09-18 gate reads this way in both places.
2. **Unanswered keeps its countdown.** For a gate the rule does not accept (including a bare
   `Resolved:`), both places show exactly what `_when` shows today: OVERDUE after its date, TODAY,
   tomorrow, in N days.
3. **A gate coming due is in Needs you.** An unanswered gate whose date is 14 days or less away,
   today, or past appears as a row in the "Needs you" table, sorted by date with the other rows,
   and gets its own subsection whose lines say: what to do (read the gate's question and write
   its conclusion); "You know it is done when": its row in `docs/STRATEGY.md` section 8 carries
   `Resolved: <what the measurement said> -> <decision>`, and each listed entry of
   `docs/OPPORTUNITIES.md` is decided and moved under "## Reviewed and closed"; and "If you do
   nothing": a sentence of at least 45 characters, ending with a full stop, saying that from that
   date `tests/test_gates_get_reviewed.py` fails the build and so blocks every deploy.
4. **Not otherwise.** An answered gate, or one more than 14 days away, is not in "Needs you".
5. **The ids are read, not typed.** The listed entry ids are those parked in `docs/OPPORTUNITIES.md`
   above "## Reviewed and closed" whose "Blocked until: gate <date>" is that gate's date; a
   synthetic file with a different set changes the list. A gate with no parked entries says so.
6. **One rule.** Whether a gate is answered is decided by T-007's `gate_row_answered`, called
   from `tools/owner.py`. If you restate the rule instead, a test must fail whenever the two
   disagree, on the real table and on every row in T-007's acceptance criteria 1 and 2.
7. **No test turns red by itself later.** Assertions about future dates use synthetic gate tables
   and synthetic parked entries; real-file assertions are limited to what stays true (the
   2026-09-18 gate is answered). In particular, no test may depend on the 2026-10-16 row staying
   unanswered: the Owner answers it on that date.
8. **Contract and checks.** The first commit adds only the new tests, and at that commit they are
   red (the 2026-09-18 gate labelled OVERDUE; no gate row in "Needs you"). `docs/OWNER.md` is
   regenerated in its own commit after the fix. At the head, `python lead/checks.py` passes
   29 of 29, exits 0 and leaves the tree clean.

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_owner_page.py` on it.
- At the head: the same command (counts, exit 0), `python lead/checks.py` (summary and exit
  status), `git status --short` (empty).
- `python tools/owner.py` output (or the regenerated page) for three forced dates, 2026-10-01,
  2026-10-02 and 2026-10-17, against synthetic files where needed, showing where a gate enters
  "Needs you" and how an answered and an unanswered past gate read.
- The diff of `docs/OWNER.md` at the head: the 2026-09-18 labels, and nothing else that is not
  date-driven.
- Two mutants the tests catch: the window cut from 14 days to 13; the answered check replaced by
  `"Resolved:" in row`.
- `git diff --stat <base>..HEAD`: only the three files in scope.

## Notes

- The bots regenerate `docs/OWNER.md` on the UTC date (`regenerate-derived.sh`, bots' mode, on
  GitHub Actions only). Locally, regenerate with `python tools/owner.py --write` only; never run
  `regenerate-derived.sh` with any argument other than `regenerate`.
- `tools/owner.py` already imports other modules by path (`open_round()` imports `rounds`,
  `numbers()` imports `publish_numbers`). The bots run it from the repository root on Linux.
- Write files with the Write or Edit tool, not shell heredocs (`CLAUDE.md`, first trap).
- Scratch files go in your own subfolder of the session scratchpad; the rest of it belongs to
  other agents.

## Amendments

- **2026-09-30, before dispatch** (T-007's round-2 re-review, minor note 1,
  `lead/reviews/T-007.md`): T-007's guard removes HTML entities without decoding them, so
  `Resolved: &lt;what the measurement said&gt; -> &lt;decision&gt;` written with entity-escaped
  brackets is accepted as a conclusion, and it renders as the template. So on the Owner page the
  template in AC 3's "You know it is done when" line is written **inside a code span** (backticks),
  never with `&lt;` or `&gt;`, and a test pins that the rendered page carries it that way. Added
  to AC 3; everything else stands.
- **2026-10-01, lead decision on the first READY (`3af074d`), before review.** The executor
  found, and the lead measured, that `test_the_page_admits_recent_mistakes` turns red on
  2026-10-04 (UTC on CI): the newest entry in `CORRECTIONS` is dated 2026-09-19 and the window is
  14 days. That would break milestone M1 one day before it completes and block every deploy.
  Two real mistakes told to the Owner in that window were never entered: the Owner page showing
  the answered 2026-09-18 gate as overdue (this task's own finding), and the gate guard's claim
  that a bare and a "no" resolution had been watched turning it red (T-007). **Added to scope:**
  both entries, at the top of `CORRECTIONS` (newest first, dated 2026-09-30, the date they were
  found; not 2026-10-01, which is still in the future on CI in UTC), in their own commit, with
  the text the lead supplied; shown red first by running the existing test with the date forced
  to 2026-10-04, and green after; then `docs/OWNER.md` regenerated again. No test changes. The
  acceptance-test fix `e3f3204` (a synthetic gate renamed from "Gate due tomorrow", a name that
  made the AC 1 label check impossible for any implementation; no date, text or assertion
  changed, the same 26 checks red at both commits) is accepted by the lead. Decided, not in
  scope: an answered gate whose parked entries are still open leaves "Needs you" (executor note
  2); a follow-up.
