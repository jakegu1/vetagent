---
id: T-010
title: Keep a half-answered gate in Needs you, and read gates from section 8 only
status: in_progress            # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 1                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: [T-009]
decisions: [ADR-0001]
backlog: none            # T-009's review optionals 3 and 4 and its executor note 2 (lead/reviews/T-009.md)
---

## Context

`tools/owner.py` generates `docs/OWNER.md`, the Owner's page. Since T-009, an unanswered gate
from 14 days before its date on is a row in "## Needs you, soonest first"
(`gates_coming_due()`), because from its date `tests/test_gates_get_reviewed.py` fails the build
until two things are true: (a) the gate's row in `docs/STRATEGY.md` section 8 carries a
conclusion (`gate_row_answered`), and (b) every entry of `docs/OPPORTUNITIES.md` parked until
that gate (`parked_until(date)`, read with the guard's `parse_entries`) is decided and moved
under "## Reviewed and closed".

Three defects remain, all found in T-009's review (`lead/reviews/T-009.md`):

1. **A half-answered gate leaves "Needs you".** `gates_coming_due()` skips any gate whose row is
   answered, even when (b) is not done. The real case is 2026-10-16: if the Owner writes the
   conclusion first, the row disappears from the page while O2, O8, O9 and O11 still turn the
   build red. This is the one day the page most needs to be right.
2. **The page and the guard find gate rows differently.** `gates()` matches any four-cell dated
   table row anywhere in `docs/STRATEGY.md`; the guard reads section 8 only (from
   `## 8. Decision gates` to the next line starting `## `). Today only section 8 matches, but a
   four-cell dated row elsewhere would show up as a gate, and since T-009 could appear in
   "Needs you" with a "fails the build" line the build does not back.
3. **Grammar with one entry.** With exactly one parked entry the "done" line reads "and O13, the
   entries ... are each decided".

## Goal

The page lists a gate in "Needs you" for exactly as long as the guard would fail the build on
it (from 14 days before its date), says which half is left, and reads its gates from the same
section the guard reads.

## Scope

**In:** `gates()`, `gates_coming_due()` and the text of a gate's row and subsection in
`tools/owner.py`; tests; regenerating `docs/OWNER.md`.

**Out:** `tests/test_gates_get_reviewed.py` (the guard is unchanged), `docs/STRATEGY.md`,
`docs/OPPORTUNITIES.md`, every other section of the page, every other file.

## Files in scope

- `tools/owner.py`
- `tests/test_owner_page.py`
- `docs/OWNER.md` (regenerated with `python tools/owner.py --write`, never edited by hand)
- **Named change to an existing test:** in `test_needs_you_has_no_answered_or_distant_gate`, the
  three "answered" cases (2026-10-02, 2026-10-16, 2026-10-17) pass `_opportunities(closed=(("O2",
  "2026-10-16"),))` instead of `opps`, so that the gate is fully answered there; the assertions,
  the two unanswered cases and the real-file check stay as they are. Its docstring may say
  "answered (row and entries)". Conflict search (2026-10-01) found no other test that this change
  contradicts: `test_a_gate_coming_due_is_in_needs_you` and `test_the_parked_entries_are_read_not_typed`
  use unanswered rows; `test_it_reads_the_real_gate_table` and
  `test_the_diagrams_are_generated_and_cannot_drift` use the real file, whose four gates are all
  in section 8; the synthetic STRATEGY helper (about line 481) already writes a section 8 heading.
  Any other older test failing means BLOCKED.

## Acceptance criteria

1. **Half-answered stays.** A gate within the window (14 days or less away, today, or past)
   whose row is answered but which still has parked entries is a row in "Needs you" and has its
   subsection. Its lines say the conclusion is written, and that what is left is the listed
   entries (by id, as `parked_until` reads them); "You know it is done when" names only the
   entries; "If you do nothing" keeps T-009's sentence (from the date,
   `tests/test_gates_get_reviewed.py` fails the build and so blocks every deploy). It does not
   repeat the instruction to write the conclusion.
2. **Entries done, row not.** A gate within the window with no parked entries left and an
   unanswered row is listed as T-009 lists it today, with "and nothing else: no entry ... is
   parked until this gate" or equivalent. Its text is unchanged except for AC 4.
3. **Fully answered leaves.** A gate whose row is answered and which has no parked entries is
   not in "Needs you", on any date. The gate table and timeline labels stay T-009's: an answered
   row reads "answered" whatever the entries (the labels are about the row).
4. **One entry reads as one.** With exactly one parked entry, the "done" line uses the singular
   ("O13, the entry ... parked until this gate, is decided and moved ..."); with two or more, the
   plural as today. Pinned by a test for one, two and four entries.
5. **Section 8 only.** `gates()` returns only rows inside section 8, bounded exactly as the
   guard bounds it (`## 8. Decision gates` to the next `\n## `). A synthetic STRATEGY with a
   four-cell dated row in section 9 and another above section 8 shows neither on the page (not
   in the gate table, the timeline or "Needs you"); without a section 8 heading, `gates()`
   returns no gates rather than every dated row in the file. On the real file the four gates are
   unchanged (2026-09-18, 2026-10-16, 2026-12-04, 2027-03-04).
6. **The page agrees with the guard.** For synthetic files and forced dates covering each
   combination (row answered or not; entries open or closed; 15 days away, 14, today, past), a
   gate is in "Needs you" from 14 days before its date on exactly when, run on its date or later,
   the guard's due-gate check or its parked-entry check would fail on it. Use the guard's
   `gate_row_answered` and `parse_entries`; do not restate either rule.
7. **No test turns red by itself later.** Assertions about future dates use synthetic files.
   No test depends on the 2026-10-16 row or its entries staying open: the Owner answers them on
   that date.
8. **Contract and checks.** The first commit adds the new tests and the named change alone, and
   at that commit they are red (AC 1's half-answered gate absent from "Needs you"; AC 4's
   singular missing; AC 5's stray rows shown). `docs/OWNER.md` is regenerated in its own commit
   after the fix. At the head, `python lead/checks.py` passes 29 of 29, exits 0 and leaves the
   tree clean.

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_owner_page.py` on it (the
  red lines).
- At the head: the same command (counts, exit 0), `python lead/checks.py` (summary and exit
  status), `git status --short` (empty).
- The rendered "Needs you" rows and subsections for the half-answered and the entries-done cases,
  from synthetic files on 2026-10-16.
- The diff of `docs/OWNER.md` at the head: nothing but date-driven lines and the recent-commit
  list, or an explained change.
- Three mutants the tests catch: `gates_coming_due` skipping every answered row again; `gates()`
  reading the whole file again; the singular branch removed.
- `git diff --stat <base>..HEAD`: only the three files in scope.

## Notes

- The bots regenerate `docs/OWNER.md` on the UTC date. Locally, regenerate with
  `python tools/owner.py --write` only; never run `regenerate-derived.sh` with any argument other
  than `regenerate`. If the local date is ahead of UTC, the regenerated page carries the local
  date; that is expected (T-009's review proved the page is determined by its stamped date).
- Write files with the Write or Edit tool, not shell heredocs (`CLAUDE.md`, first trap).
- Clear `__pycache__` after restoring a file during a mutant run (`CLAUDE.md`).
- Scratch files go in your own subfolder of the session scratchpad.
