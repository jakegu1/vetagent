---
id: T-034
title: Keep rendered templates and pasted instructions from answering a gate
status: ready
level: 3
size: S
depends_on: []
decisions: []
backlog: T-007 round-two follow-up
---

## Context and goal

The gate guard accepts an HTML-escaped copy of its own template and a `Resolved:`
prefix followed by its complete failure instruction. Its literal template is already
refused. This parked finding was reproduced against the current implementation.
Make these forms remain unanswered in the real due-gate check and the Owner page,
without changing any experiment date, threshold or required outcome.

## Technical policy and compatibility boundary

Recognize complete markup fragments with literal or single-encoded angle brackets.
Decode entities only to recognize and remove markup; leave all other text raw. Match
whole comments before generic bracketed fragments. Preserve `_MARKUP` and `_ARROWS`
byte-for-byte. Do not globally or recursively decode a row.

After markup removal, evaluate only the segment after the first visible literal
`Resolved:` and before the next visible literal `Resolved:`. Preserve the existing
alphanumeric-content and literal ASCII `->` predicates on that segment. A hidden
marker inside removed markup is not a segment boundary. A valid first segment
continues to qualify when a second marker follows it.

This reserves a visible literal `Resolved:` as a segment delimiter. The previously
accepted `Resolved: the log printed 'Resolved:' twice -> inspect the log` is now
refused because its first segment has no arrow. Pin that specific refusal. No current
conclusion or old pinned positive uses this form; do not claim universal compatibility.

Encoded ASCII arrows, an encoded first marker and literal/entity-encoded U+2192 still
do not qualify. An encoded colon in later prose and double-escaped brackets retain
their old raw-text behavior. This is a syntax guard, not a semantic verdict on evidence.

## Scope and tests-first contract

- `tests/test_gates_get_reviewed.py`: additive acceptance fixtures/tests first; then
  only necessary imports, encoded-markup recognition constants, `gate_row_answered`
  and its directly corresponding comments/docstring. Keep its name and signature.
- `tests/test_owner_page.py`: one additive shared-rule seam test using the existing
  synthetic source and render helpers. No generator or production source edits.
- Both runners are already required. No workflow registration is needed.
- No old test changes: preserve existing test-function ASTs, fixtures, inputs and
  assertions. Keep `_MARKUP`, `_ARROWS` and `PINNED_GATES` unchanged.
- Add these new test names rather than expanding old fixture arrays:
  `test_gate_rejects_encoded_templates_and_prefixed_instructions`,
  `test_gate_first_segment_preserves_literal_marker_and_arrow_rules`,
  `test_gate_encoded_markup_cannot_borrow_a_comment_arrow`, and Owner test
  `test_template_gate_answers_stay_open_on_owner_surfaces`.
- The first commit contains only acceptance tests/fixtures and is actually red on
  its parent. Freeze those inputs/assertions after that commit. Implement the one
  finding separately, with its observed red in the commit message.

Refresh the conflict search on the actual dispatch base. Preserve the old fixture
and test contracts structurally; any AST comparison must itself work on both Python
3.12 and 3.13 rather than assuming their default dump serialization is identical.

## Acceptance criteria

1. Derive the template and full failure instruction from the actual emitted guard
   message. Refuse named, decimal, hexadecimal, leading-zero/case-varied and mixed
   delimiter single-encoded template forms. Refuse literal or emphasized `Resolved:`
   followed by that complete instruction. Exercise the helper and the real due-gate
   check on synthetic rows, without copying their predicate into the test.
2. Refuse a bare/pending first segment followed by a qualifying second segment, and
   a first finding whose decision arrow occurs only after the second marker. Keep
   a valid first segment accepted with either a bare or valid second segment. Pin
   the quoted-marker compatibility refusal described above.
3. Literal and single-encoded comments cannot supply arrows or hidden boundaries.
   Preserve `<3 commitments -> ...`, `<target -> ...`, the old bold positive, and
   their existing raw/entity-text controls. Encoded ASCII arrows, encoded first
   markers, U+2192 and markup joining `-` to `>` remain refused. Every old case is
   unchanged. Test whole-comment-first recognition explicitly.
4. The actual `owner.gates()` shared-helper seam agrees. At fixed synthetic dates,
   rejected forms stay unresolved in gate table, timeline and Needs you even after
   their parked entries are closed. Valid controls read answered and leave Needs
   you when entries close. Do not implement a second parsing rule in the page.
5. All nine existing deadline tests pass, including the Oct 16/19/20/21 boundary.
   No strategy, opportunities, real conclusion, threshold, public input, production
   source or `PINNED_GATES` change. No customer result is created.
6. Isolated mutants separately removing encoded recognition, first-segment isolation
   and whole-comment-first recognition turn the new acceptance tests red. Global
   row decoding is caught by literal-arrow/marker preservation cases. Protect any
   disk work byte-for-byte and prevent stale bytecode from masking a mutant.
7. Run all three affected runners and the complete configured suite on the final
   head. Verify the affected tests on actual Python 3.12 and 3.13, compile source,
   and report the tests-first/frozen-acceptance contract. Fresh independent and
   adversarial reviews precede the lead's merge and release checks.

## Consumers and commands

`tools/owner.py::gate_guard()` loads this file once and `gates()` calls the shared
`gate_row_answered(line) is True`. Importing it must not run checks. Existing Owner
stand-in-helper, half-answer, countdown and section-scope tests remain unchanged.
`tests/test_experiment_d_deadline.py` loads the real guard and its self-tests.

Run `python tests/test_gates_get_reviewed.py`, `python tests/test_owner_page.py`,
`python tests/test_experiment_d_deadline.py`, and `python lead/checks.py`.
Use the actual hand-written runners. No benchmark, upstream call or production
probe is required. The lead handles generated pages and publication separately.

## Cost and stop rule

Two existing files, one finding, no running cost. Stop and report an exact case if
an old pinned expectation cannot be preserved within this scope. Do not weaken an
assertion, add semantic word-count rules, change a pre-registered gate, or redirect
the pending experiment. Preparation covered a bounded fixed grid and found one
early comment-recognition candidate insufficient; that failed candidate is retained
as evidence, not described as a successful implementation.

## Amendments

None.
