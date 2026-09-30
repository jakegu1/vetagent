---
id: T-007
title: Make the gate guard require a written conclusion, as its docstrings say it does
status: in_progress      # draft | ready | in_progress | in_review | changes_requested | done | dropped
level: 3                 # 0 direct | 1 light | 2 standard | 3 high risk
size: S                  # S | M (split anything larger)
depends_on: []
decisions: [ADR-0001]
backlog: none            # found by lead #4 on 2026-09-30; no BACKLOG row
---

## Context

`docs/STRATEGY.md` section 8 is a table of pre-registered decision gates. Its prose: "Every gate
has to come back to this document with a written conclusion when it falls due. Skipping one
silently isn't allowed." `tests/test_gates_get_reviewed.py`, function
`test_strategy_gates_are_answered_when_they_fall_due()`, enforces it: for each row of that table
whose date is today or earlier, the row must carry `Resolved:`. Its failure message asks for
`Resolved: <what the measurement said> -> <decision>`. The file is a step of `test.yml`'s `test`
job, and the deploy runs every step of that job before it ships
(`.github/scripts/offline_suite.py`, T-004), so a red here also blocks every deploy.

The check is `resolved = any("Resolved:" in ln for ln in line)`, unchanged since `1762bd3`
(2026-09-05). The function's docstring (about line 108) and the comment over `PINNED_GATES`
(about line 33) say an external audit watched three escapes turn it red: no Resolved line, a bare
`Resolved:`, and `Resolved: no`. Those sentences were added on 2026-09-07 and 2026-09-10, after the
check was written.

**Measured by the lead on 2026-09-30,** with today forced to 2026-10-16 and a scratch copy of
`docs/STRATEGY.md` whose 2026-10-16 row carried each candidate: no Resolved text: red; a bare
`**Resolved:**`: **green**; `**Resolved:** no`: **green**; a real conclusion: green. Two of the
three refusals the docstrings describe do not happen, and never did with this code.

The next gate falls due on **2026-10-16** ("Does anyone want to pay"). On that day a placeholder
written to get CI green again (`Resolved:`, `Resolved: TBD`, `Resolved: pending`) would pass, and
the gate would be skipped silently, which is what the guard exists to prevent.

The same file carries a stray line 123, `## ", start + 1)`: the second half of line 122, left
behind when an old heredoc turned a backslash-n into a real newline (`CLAUDE.md`, first trap) and
the first half was repaired by hand. It is a comment, so it changes nothing at runtime. A scan of
the repository for the same shape (a line repeating the text after a backslash-n on the line
before it) found no other instance.

## Goal

Once a gate is due, the guard is green only if the gate's own row carries a written conclusion
after `Resolved:`, in the form its failure message asks for. A bare, placeholder or one-word
resolution is red. What the file says was watched is true, and the file shows it on every run.

## Scope

**In:**
- The rule, as one module-level function `gate_row_answered(row)` in
  `tests/test_gates_get_reviewed.py`: it takes the text of one gate row and returns `True` when the
  text after the row's first `Resolved:` contains an arrow (`->`, or the Unicode arrow U+2192 that
  the table's action column uses) with at least one letter or digit on each side of that arrow,
  both sides lying after `Resolved:`. Markdown emphasis (`*`, `_`), backticks, pipes and
  whitespace are not content. Undecided is allowed ("... -> undecided"); silent is not. The
  due-gate check calls this function; nothing else in the file restates the rule. Its name and
  signature are part of this spec because T-009 will call it.
- Self-tests of the guard in the same file, run by `main()` on every run (it discovers `test_*`
  functions by name), that drive the guard's own due-gate code path, not a copy of its logic.
- The function's docstring and the comment over `PINNED_GATES`, corrected to say what the code
  does.
- The stray line 123, removed in its own commit.

**Out:**
- The parked-entry half of the file (`parse_entries`, the `docs/OPPORTUNITIES.md` checks in
  `main()`), `test_no_gate_can_quietly_disappear`, and the values in `PINNED_GATES`.
- `docs/STRATEGY.md` and every other file. Changing a gate, its test, its action or the table is
  the Owner's sign-off.
- `tools/owner.py` (T-009 does the Owner page).

## Files in scope

- `tests/test_gates_get_reviewed.py` (the guard and its self-tests; already a step of `test.yml`,
  so no workflow changes).
- **Named changes to existing tests:** the due-gate check itself, which is the subject of this task;
  nothing else. Conflict search (2026-09-30): the file is run by `test.yml` (line 54), by
  `lead/checks.py` and by the deploy gate (`offline_suite.py` reads `test.yml`); it is named in
  `docs/AUDIT_BRIEF.md`, `docs/BACKLOG.md` (W11, done), `docs/DECISIONS.md` (P5),
  `docs/OPPORTUNITIES.md` (rule 5) and `lead/` files, none of which asserts the refusals; no test
  imports it. The only due gate today is 2026-09-18, whose row reads
  `**Resolved:** ... were ours -> continue per ...`, which the new rule must accept (AC 3). Any
  other older test failing means BLOCKED.

## Acceptance criteria

1. **Refused.** With today forced to 2026-10-16 and a synthetic gate table whose 2026-10-16 row
   has the real row's shape (date, question, test, and an action cell that itself contains U+2192
   arrows, as the real one does: "Yes <U+2192> build payments; no <U+2192> pick a different
   customer segment and run D again"), each of these, placed after the action text, makes the
   check fail for that gate: no `Resolved:` at all; `Resolved:`; `**Resolved:**`;
   `Resolved: no`; `Resolved: TBD`; `Resolved: pending`; `Resolved: -> continue` (nothing before
   the arrow); `Resolved: 2 commitments ->` (nothing after it); `**Resolved:** ** -> **` (only
   markup).
2. **Accepted.** With the same forced date and table:
   `Resolved: 0 trial commitments -> pick a different segment and run D again`; the same with
   U+2192 as the arrow; `**Resolved:** D got 1 commitment -> undecided, revisit 2026-10-23`.
3. **The real table.** With the real `docs/STRATEGY.md` and the real date, the due-gate check is
   green; and every row of the real table that carries `Resolved:` is accepted by
   `gate_row_answered` (today, the 2026-09-18 row). Nothing asserts the state of a real row that is
   not yet resolved: the Owner will resolve the 2026-10-16 row on its date, and no self-test may
   turn red when that happens.
4. **Only its own row counts.** A `Resolved: x -> y` in another gate's row, or on a line below the
   table, does not answer the 2026-10-16 gate. A gate that is not yet due is not a failure, with or
   without a Resolved text.
5. **One rule.** `gate_row_answered` is the only place the rule is written, and the due-gate check
   calls it. The self-tests in ACs 1, 2 and 4 go through the due-gate check (they may call the
   function directly as well).
6. **The self-tests don't leak.** Their deliberate reds are not failures of the file: with the real
   data today, `python tests/test_gates_get_reviewed.py` exits 0 and prints its pass count. A
   genuine failure is never hidden: with the guard broken by any of the three mutants under
   "Evidence required", the file exits 1.
7. **The words match the code.** The due-gate check's docstring and the comment over
   `PINNED_GATES` no longer claim a refusal the code does not make: they say that until this task
   a bare and a `no` resolution passed (measured 2026-09-30), and that both are refused since.
8. **Contract and checks.** The first commit adds only the self-tests. At that commit they run
   against the unchanged guard without crashing, and are red on at least the bare, `no`, `TBD`,
   `pending` and markup-only cases of AC 1 (a missing `gate_row_answered` is reported as a failure,
   not a traceback). The stray line 123 goes in its own commit, titled
   `T-007: remove a stray line left by a mangled heredoc`. At the head, `python lead/checks.py`
   passes 29 of 29, exits 0 and leaves the tree clean.

## Evidence required

- The tests-first commit's SHA and the output of `python tests/test_gates_get_reviewed.py` on it:
  which self-tests fail, and the exit status.
- At the head: the same command (exit 0, the counts), `python lead/checks.py` (summary line and
  exit status), and `git status --short` (empty).
- The final diff of the due-gate check, `gate_row_answered` and the two corrected comments.
- Three mutants, each shown to make the file exit 1, with the self-test that catches it: (a) the
  rule reverted to `"Resolved:" in row`; (b) an arrow accepted anywhere in the row rather than
  after `Resolved:` (the action cell's own arrows then answer `Resolved: no`); (c) the check
  looking for the conclusion anywhere in the section rather than in the gate's own row. Restore
  the file and clear `__pycache__` after each (`CLAUDE.md`: a stale `.pyc` makes a mutant lie).
- `git diff --stat <base>..HEAD`: only the one file.
- A scan of the changed lines for non-ASCII characters: list any you intended (for example U+2192
  in test data); nothing else.

## Notes

**Threat model.** What must never happen: (a) a due gate goes green on an empty, placeholder or
one-word resolution; (b) the build goes red before 2026-10-16 because the new rule rejects the
2026-09-18 resolution, which would restart milestone M1 (seven green days, due 2026-10-05) and
block deploys; (c) a self-test turns red on its own later, for example when the Owner writes the
2026-10-16 conclusion, or when the real date passes a gate; (d) the self-tests leak their
deliberate reds into the file's result, or swallow a real red; (e) the self-tests write into the
repository. Realistic accidents to defend against: someone on 2026-10-16 writing a placeholder to
unblock a deploy; the arrows already in the action cell being taken for the conclusion's; a
Resolved text in another row; a conclusion made only of markup; a stale `__pycache__`. Out of the
bar (a minor note at most): deliberate gaming such as `Resolved: x -> y`.

- The file runs as a script (`python tests/test_gates_get_reviewed.py`), so its module is
  `__main__`. It reads `docs/STRATEGY.md` through the module global `STRATEGY` and the date through
  `datetime.date.today()`. One way to write self-tests that work unchanged on both the old and the
  fixed guard: write the synthetic table to a file under the system temporary directory, point the
  module's `STRATEGY` at it, and replace the module's `datetime` with a shim whose `date.today()`
  returns the forced date (keep `fromisoformat` working), restoring both afterwards in a
  `finally`. If you choose this, the fix must keep reading both through those module globals.
  Save and restore `_FAILURES` and `_PASSED` around each inner call.
- The failure message of the due-gate check stays as it is: it already names the form.
- Write files with the Write or Edit tool, not shell heredocs (this task exists partly because of
  one). The Write and Edit tools decode backslash-u escapes into real characters
  (`lead/PITFALLS.md`): write U+2192 in code as `chr(0x2192)` or as the character itself.
- Scratch files go in your own subfolder of the session scratchpad; the rest of it belongs to
  other agents.

## Amendments

- **2026-09-30, lead decision on the first READY (`8e14f10`), before review.** The executor
  measured a residual that the threat model names ("the arrows already in the action cell being
  taken for the conclusion's"): because U+2192 counts as the conclusion's arrow, `Resolved: TBD`
  placed before the action text, or in the test cell, is accepted, answered by the table's own
  pre-registered U+2192 arrows. AC 2's U+2192 case, written by the lead, opened it. Decision:
  **the conclusion's arrow is the ASCII `->` only; U+2192 never counts**, so the table's own
  arrows cannot answer anything wherever a placeholder is put. A conclusion written with U+2192
  is refused, visibly, and the failure message says why. Required, each in its own commit:
  1. **Named change (a)** to the self-tests: AC 2's U+2192 case moves to the refused cases (in
     every self-test that judges it, including the direct calls).
  2. **Named change (b)** to the self-tests: three new refused cases: `Resolved: TBD` at the start
     of the action cell, before its text; `Resolved: TBD` in the test cell; and `Resolved: no`
     after the action text in a row whose test cell carries an ASCII `->` (so that an arrow
     accepted anywhere in the row stays a caught mutant).
  3. The fix: `_ARROWS` holds `->` only; the failure message keeps its words and adds that the
     arrow is an ASCII `->` and the table's own arrows do not count; the docstring of
     `gate_row_answered` and the comment over `_ARROWS` say why U+2192 does not count.

  ACs 1 and 2 read accordingly: U+2192 as the conclusion's arrow is refused. **Decided, not to be
  reopened:** AC 3 reads every real row that carries `Resolved:`, due or not, so a placeholder
  written early on a future gate's row turns the file red; that is the direction this guard
  fails in on purpose. A colon outside the bold (`**Resolved**:`) is refused, visibly; the
  failure message names the form. Bar for the review: mutants (a), (b) and (c) under "Evidence
  required" still make the file exit 1, and so does U+2192 put back into `_ARROWS`.
- **2026-09-30, round 1 lead decision** (`lead/reviews/T-007.md`): back for round 2, the last.
  The red-team found that the guard accepted its own template and message pasted back, and
  markup that never renders (an HTML comment's `-->` was taken as the arrow), and that a leak of
  `check` in the self-test harness would hide every red; a second table's row with the same date
  could answer a gate, against AC 4. Required: markup removed before judging, and the failure
  message's parenthetical no longer writes the arrow; the leave-no-trace self-test records a leak
  directly; each gate judged by its own matched row. **Named changes (c), (d) and (e)** to the
  self-tests, each in its own commit, are listed in the lead decision; nothing else in the
  self-tests changes.
