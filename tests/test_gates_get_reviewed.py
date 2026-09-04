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
