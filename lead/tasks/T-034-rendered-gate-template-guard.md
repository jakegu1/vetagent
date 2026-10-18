---
id: T-034
title: Keep rendered templates and pasted instructions from answering a gate
status: done
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

### (a) Round-one delimiter shadowing, registered before correction

Both fresh reviewers and the lead reproduce a remaining AC 3/4 failure at af6eef8.
`Resolved: pending <3 &lt;!-- hidden finding -> hidden decision --&gt;` is falsely
answered by the helper, real due-gate check and Owner surfaces. Its literal-comment
control is refused. An unmatched `<3` or `<target` prefix can make a generic encoded
fragment consume the start of a later complete fragment, preventing its recognition.
The same cause can falsely reject a valid conclusion by exposing a hidden marker:
`Resolved: <3 commitments &lt;span title='Resolved: ignored'&gt; -> change segment`.
Keep both directions: hidden content cannot answer, and a valid visible first segment
cannot be rejected by a hidden marker after an otherwise supported literal prefix.

The original tests-only commit, all old cases, and all existing new acceptance inputs
and assertions remain frozen. First add only two named regression functions:
`test_gate_markup_recognition_resumes_after_unmatched_prefixes` in the guard runner,
and `test_shadowed_encoded_markup_stays_consistent_on_owner_surfaces` in the Owner
runner. Use a bounded literal/single-encoded prefix and comment/tag grid, covering
helper, actual due check, gate table, timeline and Needs you. Preserve successful
literal-text controls, segment boundaries, encoded-arrow/marker refusals and every
original expectation. Commit these additive tests alone and observe red on af6eef8
before repairing the recognizer. No existing fixture array may be expanded or weakened.

Repair only the already-authorized encoded-fragment constants/helper/comments. An
invalid generic candidate must not hide a later complete recognized fragment. Do not
globally decode text, change `_MARKUP`, `_ARROWS`, dates, thresholds, source documents,
or the Owner generator. A comment-only prepass is insufficient unless complete encoded
tags and hidden-marker controls also pass. Keep the failed round-one candidate and
reviews as evidence. Remove this repair in an isolated mutant and require the added
regressions to fail on both actual Python versions. Re-run the three affected runners,
one full ordinary and one inherited-denied configured inventory, compile and structural
frozen-case proof. A fresh combined independent/adversarial round-two review is required.

The generic file-level tests-first checker remains reported as BROKEN because this
legacy guard and its self-tests share a file. The named structural proof must establish
the original function/fixture freeze and the two additive-test commits; never describe
that generic result as passing or change the checker to hide it.

### (b) Blocking regression found by the combined final review

The round-two candidate 067c7ec still case-folds HTML entity names. That is not a
valid decoding rule: `&lt;` and `&LT;` decode to `<`, while `&Lt;` decodes to U+226A
and `&lT;` remains literal. A falsely recognized comment opener can still hide the
start of a later complete encoded fragment. The lead independently compares frozen
Git sources: `Resolved: <3 commitments &Lt;!-- invalid &lt;span title='Resolved:
ignored'&gt; --&gt; -> change segment` is answered at 6898b72 and wrongly refused at
af6eef8 and 067c7ec. The same prefix also allows a hidden comment arrow to answer a
pending row. This is a regression in the preserved visible-text/hidden-marker seam,
so it meets the explicit regression exception to the two-round bounce cap. It is
not authorization for another general parser or semantic review round.

Freeze both previous tests-only commits and every existing function/fixture/input/
assertion. Add only `test_gate_entity_name_case_cannot_shadow_complete_markup` and
Owner `test_entity_name_case_stays_consistent_on_owner_surfaces` first, in a separate
tests-only commit with actual red on 067c7ec. Cover the exact regression and hidden
arrow refusal through all actual shared-rule seams. Use a bounded grid distinguishing
valid literal/named/decimal/hexadecimal bracket aliases from the invalid mixed-case
named aliases at openers and closers; a non-bracket entity must never masquerade as
a bracket or prevent later complete markup recognition. Keep valid numeric x/hex
case variations and every previously accepted literal-text control.

Repair only encoded-recognition constants/compiler flags and their direct comments;
the 067c7ec helper body, `_MARKUP`, `_ARROWS`, `PINNED_GATES`, all source documents and
the Owner generator remain frozen. A delimiter recognized as an encoded bracket
must single-decode to that exact bracket. No global/recursive row decode. A mutant
restoring the incorrect named-entity case folding must fail the new tests on both
actual runtimes. Preserve the failed candidate and review evidence. Complete the
same affected-runner, old/new freeze, compile, ordinary/inherited-denied and local
integrity evidence bar; an independent reviewer rechecks this bounded regression
correction before integration. Optional new preferences remain follow-ups.

### (c) Preserve already-recognized raw markup as a whole

Before sealing the entity-name correction, the lead's bounded Git-byte probe finds
another demonstrated compatibility regression in the unmatched-origin repair. The
row `Resolved: <3 commitments <span title='Resolved: ignored &lt;b'> -> change
segment` is answered by original 6898b72 and af6eef8, but rejected by 067c7ec and
1d6663f. The span is complete existing raw markup: `_MARKUP.fullmatch` returns a
match in all four versions. Removing its inner encoded fragment first consumes its
closing bracket, exposing the otherwise hidden marker. This is an existing raw-tag
contract regression and falls within the same narrowly permitted cap exception.

Keep every prior test/fixture/input/assertion frozen. Add only guard function
`test_existing_raw_markup_is_not_split_by_encoded_candidates` and Owner function
`test_raw_markup_entities_preserve_hidden_marker_owner_seams`, in a new tests-only
commit, actually red on 1d6663f. Cover hidden-marker positions before/after embedded
named/decimal/hex bracket text in complete old raw tags, with ordinary valid raw
and encoded controls. Verify the old raw matcher itself recognizes the promised
raw-tag cases. Use the actual shared helper/due/Owner surfaces, not a second parser.

Only recognition constants/compiler flags/direct comments may implement the fix;
the helper body and `_MARKUP` remain frozen. Protect a complete existing raw fragment
as a whole before considering its internal encoded candidates. Do not globally
decode text or change what the old raw matcher recognizes. Removing that protection
must make the new regression fail on both actual runtimes. Preserve all previous
origin and entity-case regressions. No broader markup preference or parser rewrite.

Never edit tracked files while a configured runner is active. Retain any already
running old-head result as such; do not count it as final-source verification. Finish
the same final-source affected/compile/freeze/ordinary/inherited-denied evidence and
the independent bounded regression recheck required by amendment (b).

For avoidance of doubt, (c) does not supersede the frozen unmatched-prefix examples
in (a). The old raw matcher stays byte-identical; its broad wildcard match is not a
new precedence promise for an unmatched `<target ... &lt;span ...>` prefix. Preserve
both the complete quoted raw-tag cases in (c) and the complete inner encoded-fragment
cases in (a). The final bounded recheck must verify both without changing any input,
assertion or helper. No universal HTML equivalence is claimed.
