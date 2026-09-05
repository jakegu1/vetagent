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
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OPPS = os.path.join(ROOT, "docs", "OPPORTUNITIES.md")

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


def test_strategy_gates_are_answered_when_they_fall_due():
    """A gate nobody is obliged to answer is not a gate.

    Found by external audit, which was asked in the audit brief to check exactly this and
    reported that the 2026-09-18 gate could not fail: the brief claimed OPPORTUNITIES.md
    and this test kept it live, and neither covered it. STRATEGY.md said "skipping one
    silently isn't allowed" and nothing enforced that sentence.

    A gate that is due must carry a "Resolved:" line in the same table row, stating what
    the measurement said and what was decided. Undecided is allowed; silent is not.
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
## ", start + 1)
    text = whole[start:end if end > 0 else len(whole)]
    rows = _GATE_ROW.findall(text)
    check("the gate table is still parseable", len(rows) >= 3, "%d rows" % len(rows))

    today = datetime.date.today()
    for date_str, name in rows:
        due = datetime.date.fromisoformat(date_str)
        line = [ln for ln in text.splitlines() if ln.startswith("| " + date_str)]
        resolved = any("Resolved:" in ln for ln in line)
        if due <= today:
            check("gate %s (%s) is due and carries a written conclusion"
                  % (date_str, name[:34]), resolved,
                  "add 'Resolved: <what the measurement said> -> <decision>' to its row")
        else:
            days = (due - today).days
            print("  ..    gate %s (%s) due in %d days" % (date_str, name[:34], days))


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
    test_strategy_gates_are_answered_when_they_fall_due()

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
