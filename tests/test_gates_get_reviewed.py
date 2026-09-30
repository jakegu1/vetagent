"""test_gates_get_reviewed.py — parked ideas must be revisited when their gate comes due.

This guards a failure that already happened once. On 2026-09-04 a round of market
research produced findings that each undermined part of the plan, and the response was to
propose repositioning the product — fourteen days before the gate that asks whether
anyone is using it had come due. The tool had never been given a chance to fail on its
own terms.

The fix has two halves and this file is the second one:

  1. docs/OPPORTUNITIES.md parks a discovery instead of letting it redirect the project,
     and names the gate that must resolve before it can be reconsidered.
  2. This test fails once that date has passed with the entry still parked, so
     "revisit it later" cannot quietly become "never".

Parking without a forced review is just a nicer word for dropping something. The point is
not to suppress the idea — it is to make the decision happen on schedule rather than on
impulse.

Run:  python tests/test_gates_get_reviewed.py
"""

import datetime
import io
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OPPS = os.path.join(ROOT, "docs", "OPPORTUNITIES.md")

# The gates that must exist, pinned here so removing one is itself a failure.
#
# An external audit forced today = 2026-09-19 in a scratch copy and tried to escape the
# overdue gate. This comment used to say three escapes were refused: no Resolved line, a
# bare "Resolved:", and "Resolved: no". Only the first ever was. The due-gate check
# looked for the word and nothing after it, so until T-007 a bare and a "no" resolution
# both passed, as did any placeholder (measured 2026-09-30, today forced to 2026-10-16).
# Both are refused since: gate_row_answered() wants a finding, an ASCII arrow and a
# decision, and the self-tests below show those refusals on every run. Two escapes
# worked, and would again without this list:
#
#     deleting the 2026-09-18 row entirely      -> GREEN
#     changing its date to 2027-09-18           -> GREEN
#
# So a lazy answer and a removed question were both open, and this list closes the
# second: a table row can quietly disappear during an edit and nothing would notice.
# test_rounds.py already pins every commit; this file pinned nothing.
#
# Changing this list is allowed. Doing it silently is not -- it now requires a commit
# that says which gate was moved and why.
PINNED_GATES = [
    ("2026-09-18", "Is anyone using it"),
    ("2026-10-16", "Does anyone want to pay"),
    ("2026-12-04", "Is further investment worth it"),
    ("2027-03-04", "Does the data asset hold up"),
]

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def parse_entries(text):
    """Return [(heading, gate_date_or_None, is_unblocked)] for each ### entry."""
    out = []
    # Only look above the "Reviewed and closed" section; entries below it are done.
    live = text.split("## Reviewed and closed")[0]
    blocks = re.split(r"\n### ", live)
    for b in blocks[1:]:
        heading = b.splitlines()[0].strip()
        m = re.search(r"\*\*Blocked until:\s*gate\s*(\d{4}-\d{2}-\d{2})", b)
        unblocked = "**Not blocked" in b
        out.append((heading, m.group(1) if m else None, unblocked))
    return out



STRATEGY = os.path.join(ROOT, "docs", "STRATEGY.md")

# Dates in the STRATEGY §8 gate table, matched off the table itself so a gate cannot be
# added there without also becoming enforceable here.
_GATE_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|", re.M)

# The arrow between a finding and a decision: the ASCII "->" that the due-gate check's
# failure message asks for, and nothing else. U+2192 does not count because the table's
# own pre-registered action text is written with it ("Yes <U+2192> build payments; no
# <U+2192> ..."), so a placeholder put before that text, or in the test cell, would be
# answered by the table's arrows rather than by a conclusion. Measured on 8e14f10, while
# U+2192 still counted: "Resolved: TBD" at the start of the 2026-10-16 row's action cell
# passed, and so did "Resolved: TBD" in its test cell. The protection relies on the action
# text keeping U+2192: rewritten with ASCII arrows, it would answer those placeholders
# again.
_ARROWS = ("->",)

# Markup a reader never sees: HTML comments, tags and entities. gate_row_answered removes
# it before judging, so "<what the measurement said> -> <decision>", "<br> -> <br>" and
# "&nbsp; -> &nbsp;" have nothing on either side of the arrow, and an HTML comment's
# closing "-->" is not an arrow (round 1 red-team, M1). A tag starts with a letter or "/"
# and does not end in "-", so "<3 commitments -> ..." and an arrow before ">" survive.
_MARKUP = re.compile(r"<!--.*?-->|<[A-Za-z/](?:[^<>]*[^<>-])?>|&#?\w+;")


def gate_row_answered(row):
    """True when a gate row carries a written conclusion. The one statement of the rule.

    The conclusion is the text after the row's first "Resolved:". It must hold an ASCII
    arrow, "->", with at least one letter or digit on each side of it, both sides within
    that text: "Resolved: <what the measurement said> -> <decision>". U+2192 is not the
    conclusion's arrow: the table's own action text uses it, so a placeholder put before
    that text, or in the test cell, would be answered by the table's pre-registered arrows
    (measured on 8e14f10, while it counted). A conclusion written with U+2192 is refused,
    and the failure message says why. HTML comments, tags and entities are removed from
    the row first (_MARKUP): a reader never sees them, so the failure message's own
    template "<what the measurement said> -> <decision>" is not a conclusion, and a
    comment's closing "-->" is not an arrow. Markdown emphasis, backticks, pipes and
    whitespace are not content, so a bare "Resolved:", a one-word "Resolved: no",
    "Resolved: TBD", "Resolved: -> continue" and "**Resolved:** ** -> **" are all refused.
    Undecided is an answer ("... -> undecided"); silence is not.

    The due-gate check below calls it. Keep its name and signature: T-009 relies on them.
    """
    row = _MARKUP.sub(" ", row)
    _, found, conclusion = row.partition("Resolved:")
    content = [i for i, ch in enumerate(conclusion) if ch.isalnum()]
    if not found or not content:
        return False
    # An arrow lying between the first letter or digit and the last one has content on
    # both sides of it.
    between = conclusion[content[0] + 1:content[-1]]
    return any(arrow in between for arrow in _ARROWS)


def test_strategy_gates_are_answered_when_they_fall_due():
    """A gate nobody is obliged to answer is not a gate.

    Found by external audit, which was asked in the audit brief to check exactly this and
    reported that the 2026-09-18 gate could not fail: the brief claimed OPPORTUNITIES.md
    and this test kept it live, and neither covered it. STRATEGY.md said "skipping one
    silently isn't allowed" and nothing enforced that sentence.

    A gate that is due must carry a written conclusion in its own table row, stating what
    the measurement said and what was decided: "Resolved: <finding> -> <decision>", as
    gate_row_answered() defines it. Undecided is allowed; silent is not.

    The counting rule that would answer this gate was broken at the other end. It read
    "more than one client or more than one country", and this repository ships a
    .mcp.json pointing the owner's own editor at production, so one editor session plus
    one curl from anywhere came to two "clients": two self-generated data points about
    to answer "is anyone using it" with yes. Forcing a written conclusion is only half
    of the fix. The instrument that produces the conclusion is pinned separately, in
    tests/test_usage_gate.py.

    This docstring used to say the check was watched failing before it was trusted: with
    today forced to 2026-09-19, no Resolved line turned it red, so did a bare
    "Resolved:", and so did "Resolved: no". Only the first ever did. The check looked for
    the word and nothing after it, so until T-007 a bare and a "no" resolution both
    passed, as did any placeholder (measured 2026-09-30, today forced to 2026-10-16).
    Both are refused since, and the refusals are no longer prose: the self-tests below
    run this function against a synthetic table on every run, and the file fails if one
    of those escapes goes green.
    """
    print("\n[gates] STRATEGY decision gates are answered on time")
    whole = io.open(STRATEGY, encoding="utf-8").read()
    # Only the section 8 table. Other tables in STRATEGY.md also begin rows with a date,
    # and matching those made this report a gate that does not exist as overdue -- a
    # false alarm is how a guard gets switched off.
    start = whole.find("## 8. Decision gates")
    if start < 0:
        check("STRATEGY.md still has a decision-gate section", False, "heading missing")
        return
    end = whole.find("\n## ", start + 1)
    text = whole[start:end if end > 0 else len(whole)]
    rows = list(_GATE_ROW.finditer(text))
    check("the gate table is still parseable", len(rows) >= 3, "%d rows" % len(rows))

    today = datetime.date.today()
    for match in rows:
        date_str, name = match.groups()
        due = datetime.date.fromisoformat(date_str)
        # The gate's own row: the line its match starts, up to the next newline. Not every
        # line that starts "| " and the date: a second table's row could answer the gate,
        # and a row spaced "|2026-10-16 |" was judged by no line at all.
        stop = text.find("\n", match.start())
        resolved = gate_row_answered(text[match.start():stop if stop >= 0 else len(text)])
        if due <= today:
            check("gate %s (%s) is due and carries a written conclusion"
                  % (date_str, name[:34]), resolved,
                  "add 'Resolved: <what the measurement said> -> <decision>' to its row "
                  "(the arrow is an ASCII hyphen followed by a greater-than sign; the "
                  "table's own U+2192 arrows do not count)")
        else:
            days = (due - today).days
            print("  ..    gate %s (%s) due in %d days" % (date_str, name[:34], days))


def test_no_gate_can_quietly_disappear():
    """Deleting a gate row, or pushing its date out, must fail the build.

    Verified by the audit that found it: with today forced to 2026-09-19, deleting the
    2026-09-18 row turned CI green, and so did moving its date to 2027-09-18. Both are
    the gate answering "no question was ever asked", which is worse than answering badly.
    """
    print("\n[gates] the set of gates is pinned, not merely present")
    with io.open(STRATEGY, encoding="utf-8") as f:
        text = f.read()
    rows = dict(_GATE_ROW.findall(text))
    for date, name in PINNED_GATES:
        check("gate %s (%s) is still in the table" % (date, name),
              date in rows, "row missing -- deleting a gate needs an argument")
        if date in rows:
            check("  ...and still asks the same question",
                  name.lower() in rows[date].lower(),
                  "table says %r, pinned as %r" % (rows[date], name))


# ---------------------------------------------------------------------------------------
# Self-tests of the due-gate check. main() discovers and runs them like every test_
# function in this file.
#
# This file used to say that the check had been watched refusing a bare "Resolved:" and
# "Resolved: no". Measured on 2026-09-30, it passed both. A refusal that is only written
# down can stay untrue for weeks, so these run the real check -- not a copy of its rule --
# against a synthetic gate table with today forced to the day a gate falls due, and read
# what it decided, on every run. What the check records inside a self-test never reaches
# this file's result; only each self-test's own PASS or FAIL does (_run_due_gate_check).

_GATE_DAY = datetime.date(2026, 10, 16)      # the day the 2026-10-16 gate falls due
_DAY_BEFORE = datetime.date(2026, 10, 15)
_RIGHT_ARROW = chr(0x2192)                   # the arrow the table's action column uses

# A synthetic section 8 in the real rows' shape: date, question, test, and an action cell
# with arrows of its own. "{a}" becomes U+2192 and "{ge}" U+2265.
_SYNTHETIC_ROWS = (
    ("2026-09-18", "Is anyone using it", "`gate_verdict()` in `bench/usage.py`",
     "Yes {a} continue; no {a} run only Experiment C, add no features."),
    ("2026-10-16", "Does anyone want to pay", "{ge}3 trial commitments in Experiment D",
     "Yes {a} build payments; no {a} pick a different customer segment and run D again"),
    ("2026-12-04", "Is further investment worth it", "MRR >$0 or >500 calls/day",
     "Yes {a} continue per section 7; no {a} move to low-maintenance mode"),
    ("2027-03-04", "Does the data asset hold up",
     "Snapshot archive {ge}6 months and trains a signal better than the current rules",
     "Yes {a} that becomes the main product; no {a} keep the tool, drop the data narrative"),
)
# The real 2026-09-18 row is resolved, so the synthetic one is too unless a test says not.
_SYNTHETIC_0918 = "**Resolved:** no stranger received a verdict -> continue per section 7"

# Placed after the 2026-10-16 row's action text, none of these answers the gate...
_NOT_A_CONCLUSION = (
    "",                                  # no Resolved text at all
    "Resolved:",
    "**Resolved:**",
    "Resolved: no",
    "Resolved: TBD",
    "Resolved: pending",
    "Resolved: -> continue",             # nothing before the arrow
    "Resolved: 2 commitments ->",        # nothing after it
    "**Resolved:** ** -> **",            # only markup
    "Resolved: 0 trial commitments %s pick a different segment and run D again"
    % _RIGHT_ARROW,                      # U+2192, the table's own arrow, never counts
)
# ...and each of these does. Undecided is an answer; silence is not.
_A_CONCLUSION = (
    "Resolved: 0 trial commitments -> pick a different segment and run D again",
    "**Resolved:** D got 1 commitment -> undecided, revisit 2026-10-23",
)
_ABSENT = object()


def _synthetic_strategy(resolutions=None, below="", later_section=""):
    """A STRATEGY.md with a section 8 gate table, then a section 9.

    `resolutions` maps a gate's date to the text placed after its row's action text,
    `below` is a line under the table inside section 8, and `later_section` a line in
    section 9.
    """
    texts = {"2026-09-18": _SYNTHETIC_0918}
    texts.update(resolutions or {})
    lines = ["# Strategy (synthetic, written by a self-test)", "",
             "## 8. Decision gates, and the standard we hold ourselves to", "",
             "Every gate has to come back to this document with a written conclusion "
             "when it falls due.", "",
             "| Date | Gate | Test | Action |",
             "|---|---|---|---|"]
    for date_str, gate, test, action in _SYNTHETIC_ROWS:
        cell = action.format(a=_RIGHT_ARROW)
        if texts.get(date_str):
            cell += " " + texts[date_str]
        lines.append("| %s | %s | %s | %s |"
                     % (date_str, gate, test.format(ge=chr(0x2265)), cell))
    lines += ["", below, "", "## 9. Metrics board", "", later_section, ""]
    return "\n".join(lines)


class _ForcedClock(object):
    """Stands in for the datetime module: date.today() returns `day`, the rest is real."""

    def __init__(self, module, day):
        class date(module.date):
            @classmethod
            def today(cls):
                return cls(day.year, day.month, day.day)
        self.date = date
        self._module = module

    def __getattr__(self, name):
        return getattr(self._module, name)


def _run_due_gate_check(strategy_text, day, rule=None):
    """Run the real due-gate check on `strategy_text`, with today forced to `day`.

    Returns (verdicts, error, scratch): every check it made, as (name, passed, detail);
    the exception it raised, as text, or None; and the scratch directory it read from,
    which is gone by then. `rule`, when given, stands in for gate_row_answered for the run.

    Nothing leaks either way. STRATEGY, datetime, check, gate_row_answered, _FAILURES,
    _PASSED and stdout are put back before this returns, so a deliberate red inside is
    never a failure of this file and a real one recorded before it is never lost. The
    synthetic table is written under the system temporary directory, never into the
    repository.
    """
    g = globals()
    names = ("STRATEGY", "datetime", "check", "gate_row_answered", "_PASSED")
    saved = dict((n, g[n]) for n in names if n in g)
    failures, stdout = list(_FAILURES), sys.stdout
    verdicts, error, scratch = [], None, None
    try:
        scratch = tempfile.mkdtemp(prefix="gate-selftest-")
        path = os.path.join(scratch, "STRATEGY.md")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(strategy_text)
        g["STRATEGY"] = path
        g["datetime"] = _ForcedClock(saved["datetime"], day)
        g["check"] = lambda name, ok, detail="": verdicts.append((name, bool(ok), detail))
        if rule is not None:
            g["gate_row_answered"] = rule
        sys.stdout = io.StringIO()
        test_strategy_gates_are_answered_when_they_fall_due()
    except Exception as e:              # reported by the caller as a FAIL, never dropped
        error = "%s: %s" % (type(e).__name__, e)
    finally:
        sys.stdout = stdout
        for n in names:
            if n in saved:
                g[n] = saved[n]
            else:
                g.pop(n, None)
        _FAILURES[:] = failures
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    return verdicts, error, scratch


def _verdict(verdicts, date_str):
    """What the check said about one gate: [True], [False], or [] if it did not judge it."""
    return [v[1] for v in verdicts if v[0].startswith("gate %s " % date_str)]


def _said(verdict, error):
    if error:
        return "the due-gate check raised %s" % error
    return {(): "the due-gate check did not judge it",
            (True,): "the due-gate check passed it",
            (False,): "the due-gate check refused it"}.get(
                tuple(verdict), "the due-gate check judged it %r" % (verdict,))


def _shown(text):
    return ascii(text) if text else "no Resolved text at all"


def _inside(path, root):
    path, root = (os.path.normcase(os.path.realpath(p)) for p in (path, root))
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:                  # on different drives
        return False


def test_guard_refuses_a_due_gate_without_a_conclusion():
    """T-007, AC 1: once a gate is due, its own row must carry a written conclusion.

    The 2026-10-16 row keeps an action cell with two arrows of its own, as the real one
    does, so a check that took any arrow in the row for the conclusion's would pass all
    of these.
    """
    print("\n[gates] self-test: a due gate without a written conclusion is refused")
    for text in _NOT_A_CONCLUSION:
        verdicts, error, _ = _run_due_gate_check(
            _synthetic_strategy({"2026-10-16": text}), _GATE_DAY)
        verdict = _verdict(verdicts, "2026-10-16")
        check("refused on its due date: %s" % _shown(text),
              verdict == [False] and error is None, _said(verdict, error))


# Placeholders that the table's own arrows used to answer while U+2192 counted as the
# conclusion's arrow (measured on 8e14f10). Each is a test cell and an action cell for the
# 2026-10-16 row; the action text keeps its own pre-registered U+2192 arrows. The last puts
# an ASCII "->" in the test cell, before "Resolved:", so that a rule taking an arrow from
# anywhere in the row would answer it.
_ROW_1016 = [r for r in _SYNTHETIC_ROWS if r[0] == "2026-10-16"][0]
_TEST_1016 = _ROW_1016[2].format(ge=chr(0x2265))
_ACTION_1016 = _ROW_1016[3].format(a=_RIGHT_ARROW)
_PLACED_ELSEWHERE = (
    ("'Resolved: TBD' at the start of the action cell",
     _TEST_1016, "Resolved: TBD. " + _ACTION_1016),
    ("'Resolved: TBD' in the test cell",
     _TEST_1016 + " Resolved: TBD", _ACTION_1016),
    ("'Resolved: no' after the action text, with an ASCII arrow in the test cell",
     "%s3 trial commitments -> a yes" % chr(0x2265), _ACTION_1016 + " Resolved: no"),
)


def _with_1016_cells(test, action):
    """(STRATEGY.md text, the 2026-10-16 row) for the synthetic table with that row's test
    and action cells replaced."""
    lines = _synthetic_strategy().split("\n")
    at = [i for i, ln in enumerate(lines) if ln.startswith("| 2026-10-16 ")][0]
    lines[at] = "| 2026-10-16 | %s | %s | %s |" % (_ROW_1016[1], test, action)
    return "\n".join(lines), lines[at]


def test_guard_refuses_what_the_tables_own_arrows_answered():
    """T-007, named change (b): placeholders the table's own arrows used to answer.

    While U+2192 counted as the conclusion's arrow, "Resolved: TBD" at the start of the
    action cell, or in the test cell, was answered by the action text's own
    pre-registered arrows (measured on 8e14f10). Each case is judged through the
    due-gate check on its due date, and by gate_row_answered directly.
    """
    print("\n[gates] self-test: the table's own arrows answer no placeholder")
    rule = globals().get("gate_row_answered")
    for label, test, action in _PLACED_ELSEWHERE:
        strategy, row = _with_1016_cells(test, action)
        verdicts, error, _ = _run_due_gate_check(strategy, _GATE_DAY)
        verdict = _verdict(verdicts, "2026-10-16")
        check("refused on its due date: %s" % label,
              verdict == [False] and error is None, _said(verdict, error))
        got = rule(row) if callable(rule) else "gate_row_answered is not defined"
        check("gate_row_answered is False for %s" % label, got is False,
              "returned %r" % (got,))


# Named change (c), after the round 1 red-team (M1): the guard's own words, and markup a
# reader never sees, are not a conclusion. The failure message and the template it quotes
# are taken from the text the due-gate check emits, so the cases and the message cannot
# drift apart. These texts go after the 2026-10-16 row's action text.
_MARKUP_REFUSED = (
    "Resolved: <what Experiment D measured> -> <decision>",
    "Resolved: <!-- note --> pending",
    "Resolved: <br> -> <br>",
    "Resolved: &nbsp; -> &nbsp;",
    "Resolved: 2026-10-16",              # a lone hyphen is not an arrow
)
_MARKUP_ACCEPTED = (
    "Resolved: <3 commitments -> pick a different segment",
    "Resolved: 0 commitments -> <b>no</b>, pick a different segment",
)


def _emitted_message():
    """The failure message the due-gate check emits for an unanswered due gate, or ""."""
    verdicts, error, _ = _run_due_gate_check(_synthetic_strategy(), _GATE_DAY)
    said = [v[2] for v in verdicts if v[0].startswith("gate 2026-10-16 ") and not v[1]]
    return said[0] if said and error is None else ""


def _arrow_note():
    """The parenthetical of that message, which says what the arrow is, or ""."""
    message = _emitted_message()
    return message[message.find("("):] if "(" in message else ""


def test_guard_refuses_its_own_words_and_markup():
    """T-007, named change (c): the guard's own words and markup are not a conclusion.

    Found by the round 1 red-team (M1): the template the failure message prints, the whole
    message pasted back, and markup a reader never sees all answered a due gate: tags and
    entities between letters, and an HTML comment, whose closing "-->" was taken for the
    arrow. Each case is judged through the due-gate check on its due date and by
    gate_row_answered directly.
    """
    print("\n[gates] self-test: the guard's own words and markup are not a conclusion")
    message = _emitted_message()
    check("the due-gate check emits a message that quotes its template",
          message.count("'") >= 2, "emitted %r" % (message,))
    if message.count("'") < 2:
        return
    template = message.split("'")[1]

    def after(text):
        return _TEST_1016, _ACTION_1016 + " " + text

    cases = ([("the failure message's template, %s" % ascii(template), after(template), False),
              ("the whole failure message", after(message), False),
              ("'**Resolved:** <!-- TODO -->' at the start of the action cell",
               (_TEST_1016, "**Resolved:** <!-- TODO --> " + _ACTION_1016), False)]
             + [(ascii(t), after(t), False) for t in _MARKUP_REFUSED]
             + [(ascii(t), after(t), True) for t in _MARKUP_ACCEPTED])
    rule = globals().get("gate_row_answered")
    for label, (test, action), answered in cases:
        strategy, row = _with_1016_cells(test, action)
        verdicts, error, _ = _run_due_gate_check(strategy, _GATE_DAY)
        verdict = _verdict(verdicts, "2026-10-16")
        check("%s on its due date: %s" % ("accepted" if answered else "refused", label),
              verdict == [answered] and error is None, _said(verdict, error))
        got = rule(row) if callable(rule) else "gate_row_answered is not defined"
        check("gate_row_answered is %s for %s" % (answered, label), got is answered,
              "returned %r" % (got,))


def test_guard_accepts_a_written_conclusion():
    """T-007, AC 2: a finding, an arrow and a decision answer a due gate."""
    print("\n[gates] self-test: a due gate with a written conclusion passes")
    for text in _A_CONCLUSION:
        verdicts, error, _ = _run_due_gate_check(
            _synthetic_strategy({"2026-10-16": text}), _GATE_DAY)
        verdict = _verdict(verdicts, "2026-10-16")
        check("accepted on its due date: %s" % _shown(text),
              verdict == [True] and error is None, _said(verdict, error))


def test_guard_counts_only_the_gates_own_row():
    """T-007, AC 4: a conclusion anywhere else does not answer a gate, and a gate that is
    not yet due is not a failure, with or without a Resolved text."""
    print("\n[gates] self-test: only a gate's own row answers it, and only once it is due")
    elsewhere = (
        ("in an earlier gate's row", _synthetic_strategy({"2026-09-18": "Resolved: x -> y"})),
        ("in a later gate's row", _synthetic_strategy({"2026-12-04": "Resolved: x -> y"})),
        ("on a line below the table",
         _synthetic_strategy(below="Gate 2026-10-16. Resolved: x -> y")),
        ("in a row with its date in another section",
         _synthetic_strategy(later_section="| 2026-10-16 | Resolved: x -> y |")),
    )
    for where, text in elsewhere:
        verdicts, error, _ = _run_due_gate_check(text, _GATE_DAY)
        verdict = _verdict(verdicts, "2026-10-16")
        check("a conclusion %s does not answer the 2026-10-16 gate" % where,
              verdict == [False] and error is None, _said(verdict, error))
    not_due = (
        ("2026-12-04", _GATE_DAY, "without a Resolved text", _synthetic_strategy()),
        ("2027-03-04", _GATE_DAY, "with a bare Resolved:",
         _synthetic_strategy({"2027-03-04": "Resolved:"})),
        ("2026-10-16", _DAY_BEFORE, "the day before, without a Resolved text",
         _synthetic_strategy()),
    )
    for date_str, day, how, text in not_due:
        verdicts, error, _ = _run_due_gate_check(text, day)
        verdict = _verdict(verdicts, date_str)
        check("gate %s is no failure before it is due, %s" % (date_str, how),
              False not in verdict and error is None, _said(verdict, error))


def _verdict_of(verdicts, date_str, question):
    """The check's verdicts on the gate with this date and this question: two rows of
    section 8 may share a date."""
    head = "gate %s (%s)" % (date_str, question[:34])
    return [v[1] for v in verdicts if v[0].startswith(head)]


def _respaced(text, prefix):
    """(`text` with the 2026-10-16 row's first cell written as `prefix`, that row)."""
    lines = text.split("\n")
    at = [i for i, ln in enumerate(lines) if ln.startswith("| 2026-10-16 |")][0]
    lines[at] = prefix + lines[at][len("| 2026-10-16 |"):]
    return "\n".join(lines), lines[at]


def test_guard_judges_each_gate_by_its_own_row():
    """T-007, named change (e): a gate is judged by its own row, however it is spaced.

    Found by the round 1 red-team (minor 1) and the independent review (optional 3): the
    check judged every line of section 8 that starts with "| " and the date, so a second
    table's row with that date could answer the gate, and a gate row spaced
    "|2026-10-16 |" or "|  2026-10-16 |" was found by the table's pattern but judged by
    no line at all.
    """
    print("\n[gates] self-test: a gate is judged by its own row")
    question = _ROW_1016[1]
    rule = globals().get("gate_row_answered")
    second_table = "\n".join([
        "| Date | Note |", "|---|---|",
        "| 2026-10-16 | Resolved: 0 commitments -> pick a different segment |"])
    strategy = _synthetic_strategy(below=second_table)
    verdicts, error, _ = _run_due_gate_check(strategy, _GATE_DAY)
    verdict = _verdict_of(verdicts, "2026-10-16", question)
    check("a second table's row in section 8 does not answer the unanswered gate",
          verdict == [False] and error is None, _said(verdict, error))
    row = [ln for ln in strategy.split("\n")
           if ln.startswith("| 2026-10-16 | %s |" % question)][0]
    got = rule(row) if callable(rule) else "gate_row_answered is not defined"
    check("gate_row_answered is False for that unanswered gate row", got is False,
          "returned %r" % (got,))
    for prefix in ("|2026-10-16 |", "|  2026-10-16 |"):
        for text, answered in ((_A_CONCLUSION[0], True), ("", False)):
            strategy, row = _respaced(_synthetic_strategy({"2026-10-16": text}), prefix)
            verdicts, error, _ = _run_due_gate_check(strategy, _GATE_DAY)
            verdict = _verdict_of(verdicts, "2026-10-16", question)
            label = "a gate row written %s, %s" % (
                ascii(prefix), "with a conclusion" if answered else "without one")
            check("%s on its due date: %s" % ("accepted" if answered else "refused", label),
                  verdict == [answered] and error is None, _said(verdict, error))
            got = rule(row) if callable(rule) else "gate_row_answered is not defined"
            check("gate_row_answered is %s for %s" % (answered, label), got is answered,
                  "returned %r" % (got,))


def test_guard_takes_its_verdict_from_gate_row_answered():
    """T-007, AC 5: the rule is written once, in gate_row_answered, and the check uses it.

    With a stand-in for gate_row_answered the check has to follow it both ways: pass a row
    with no Resolved text when the stand-in says yes, and refuse a written conclusion when
    it says no. A check that kept a rule of its own would disagree with it once.
    """
    print("\n[gates] self-test: the due-gate check's verdict is gate_row_answered's")
    for answer, text in ((True, ""), (False, _A_CONCLUSION[0])):
        verdicts, error, _ = _run_due_gate_check(
            _synthetic_strategy({"2026-10-16": text}), _GATE_DAY,
            rule=lambda row, answer=answer: answer)
        verdict = _verdict(verdicts, "2026-10-16")
        check("a stand-in rule saying %s %s the gate: %s"
              % (answer, "passes" if answer else "refuses", _shown(text)),
              verdict == [answer] and error is None, _said(verdict, error))


def test_guard_rule_called_directly():
    """gate_row_answered on the same rows, called directly: T-009 calls it by name."""
    print("\n[gates] self-test: gate_row_answered called directly")
    rule = globals().get("gate_row_answered")
    check("gate_row_answered exists", callable(rule), "not defined in this file")
    if not callable(rule):
        return
    cases = [(t, False) for t in _NOT_A_CONCLUSION] + [(t, True) for t in _A_CONCLUSION]
    for text, want in cases:
        row = [ln for ln in _synthetic_strategy({"2026-10-16": text}).splitlines()
               if ln.startswith("| 2026-10-16 ")][0]
        got = rule(row)
        check("gate_row_answered is %s for %s" % (want, _shown(text)), got is want,
              "returned %r" % (got,))


def test_guard_accepts_the_conclusions_in_the_real_table():
    """T-007, AC 3: every real gate row that carries Resolved: is accepted by the rule.

    It reads docs/STRATEGY.md and not today's date, and only the rows that already carry
    Resolved:, so a gate still open asserts nothing here: the 2026-10-16 gate being
    resolved on its day, or the real date passing a gate, cannot turn this red.
    """
    print("\n[gates] self-test: the conclusions already in the real table are accepted")
    rule = globals().get("gate_row_answered")
    check("gate_row_answered exists", callable(rule), "not defined in this file")
    if not callable(rule):
        return
    whole = io.open(STRATEGY, encoding="utf-8").read()
    start = whole.find("## 8. Decision gates")
    end = whole.find("\n## ", start + 1)
    section = whole[start:end if end > 0 else len(whole)] if start >= 0 else ""
    rows = [ln for ln in section.splitlines()
            if _GATE_ROW.match(ln) and "Resolved:" in ln]
    check("the real gate table has a resolved row to read", bool(rows),
          "no row of section 8 carries Resolved:")
    for ln in rows:
        check("the real %s row is accepted" % _GATE_ROW.match(ln).group(1),
              rule(ln) is True, "its Resolved text is not a written conclusion "
              + _arrow_note())


def test_guard_self_tests_leave_no_trace():
    """T-007, AC 6: a deliberate red inside a self-test is not a failure of this file.

    Runs a gate that must be refused, with a stand-in rule, then checks that every global
    the run replaced is back, that a failure recorded before it is still recorded, and
    that the synthetic table was written outside the repository and removed. A leak is
    also written straight into _FAILURES, not through check(): if check() is the global
    that leaked, a report through it would be lost with every later red (round 1
    red-team, M2).
    """
    print("\n[gates] self-test: a self-test's deliberate red stays inside it")
    g = globals()
    names = ("STRATEGY", "datetime", "check", "gate_row_answered", "_PASSED")
    before = dict((n, g.get(n, _ABSENT)) for n in names)
    stdout = sys.stdout
    earlier = ("a failure recorded before the run", "")
    _FAILURES.append(earlier)
    try:
        verdicts, error, scratch = _run_due_gate_check(
            _synthetic_strategy(), _GATE_DAY, rule=lambda row: False)
        kept = bool(_FAILURES) and _FAILURES[-1] is earlier
    finally:
        _FAILURES[:] = [f for f in _FAILURES if f is not earlier]
    moved = [n for n in names if g.get(n, _ABSENT) is not before[n]]
    leaked = moved + ([] if sys.stdout is stdout else ["stdout"])
    if leaked:                           # recorded directly: check() may be what leaked
        _FAILURES.append(("a self-test left %s replaced" % ", ".join(leaked), ""))
        print("  FAIL  a self-test left %s replaced" % ", ".join(leaked))
    verdict = _verdict(verdicts, "2026-10-16")
    check("the run inside it was a real red", verdict == [False] and error is None,
          _said(verdict, error))
    check("every global it replaced is back", not moved and sys.stdout is stdout,
          "not restored: %s" % ", ".join(moved or ["stdout"]))
    check("a failure recorded before it is still recorded", kept,
          "_FAILURES was not restored")
    check("its synthetic table was outside the repository, and is gone",
          bool(scratch) and not _inside(scratch, ROOT) and not os.path.exists(scratch),
          "created: %s, inside the repository: %s, still there: %s"
          % (bool(scratch), bool(scratch) and _inside(scratch, ROOT),
             bool(scratch) and os.path.exists(scratch)))


def main():
    print("=" * 68)
    print("Parked opportunities: are any overdue for review?")
    print("=" * 68)

    if not os.path.exists(OPPS):
        print("docs/OPPORTUNITIES.md is missing — the parking rule has no home.")
        return 1
    with open(OPPS, encoding="utf-8") as f:
        text = f.read()

    entries = parse_entries(text)
    check("at least one entry is parked or explicitly unblocked", bool(entries),
          "no ### entries found")

    # The STRATEGY gates are the ones that can stop the project, so they are checked
    # here too. They were not, which is how the 2026-09-18 gate came to be unenforced
    # while the audit brief claimed this file kept it live.
    #
    # Discovered, not listed. This runner named one function explicitly, so a second
    # check added to this file passed by never executing -- the third hand-maintained
    # runner in this repository to do exactly that, after test_owner_powers.py and CI's
    # own step list. A guard that does not run reports PASS by silence.
    for _, _fn in sorted((k, v) for k, v in globals().items()
                         if k.startswith("test_")):
        _fn()

    today = datetime.date.today()
    overdue = []
    for heading, gate, unblocked in entries:
        if unblocked:
            check("%s declares itself unblocked" % heading[:44], True)
            continue
        if gate is None:
            check("%s names a gate" % heading[:44], False,
                  "every parked entry must say which gate unblocks it")
            continue
        due = datetime.date.fromisoformat(gate)
        if due <= today:
            overdue.append((heading, gate))
            check("%s gate %s not yet due" % (heading[:36], gate), False,
                  "gate has passed; decide it and move the entry to 'Reviewed and closed'")
        else:
            check("%s parked until %s (%d days)" % (heading[:36], gate, (due - today).days),
                  True)

    print()
    if overdue:
        print("%d parked entr%s overdue for a decision:" %
              (len(overdue), "y is" if len(overdue) == 1 else "ies are"))
        for heading, gate in overdue:
            print("  - %s (gate %s)" % (heading, gate))
        print("\nDecide each one, write the outcome into docs/OPPORTUNITIES.md under")
        print("'Reviewed and closed', and this goes green again. Leaving it parked past")
        print("its own date is how a deferral turns into a silent drop.")

    print("\n%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
