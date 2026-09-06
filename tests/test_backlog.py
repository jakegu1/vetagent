"""test_backlog.py -- an item without a way to verify it is a wish, not a task.

The backlog is the one document here that is still maintained by hand, so it gets the
strictest shape check. What makes it worth having is a single rule: every open item names
the command, test or measurement that will say whether it worked.

That rule is not decoration. Three plausible features were killed by measurement in one
day -- LP-burn detection fired on 58% of good tokens, reserve-event backfill turned out to
cost 1,580 RPC calls per pool-year, and using market activity to settle sellability traded
away the one attack the check exists to catch. A plan would have shipped all three.

Also checked: ids are unique and never reused, `Done` items name a round that actually
exists in tools/rounds.py, and `Blocked` items say what blocks them. A closed item keeps
its number, because "we looked and decided not to" is the most useful thing a backlog can
tell whoever comes next.

Run:  python tests/test_backlog.py
"""

import io
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BACKLOG = os.path.join(ROOT, "docs", "BACKLOG.md")
sys.path.insert(0, os.path.join(ROOT, "tools"))

_FAILURES = []
_PASSED = 0

_ROW = re.compile(r"^\|\s*(W\d+)\s*\|(.+)$", re.M)


# What counts as naming a verification.
#
# The rule used to be `len(verify) < 25` -- a character count. Measured against its own
# stated purpose it ran backwards:
#
#     "we will know it when we see it, probably soon enough"  52 chars, verifies
#                                                             nothing          -> PASSED
#     "`pytest -k owner`"                                     17 chars, an
#                                                             actual command   -> REJECTED
#
# So the guard rewarded vagueness for being wordy and rejected the most precise answer
# available for being short. A backlog item's verification is supposed to be the thing
# somebody else can run; length is not even a proxy for that.
#
# The replacement asks for one of the three shapes a real verification takes: something
# runnable in backticks, a path to the file that does it, or a number to hit. It is not
# clever and it is not complete -- "`ls`" would pass -- but every shape it accepts is
# checkable by a reader, and the shape it rejects is prose.
_VERIFIABLE = re.compile(
    r"`[^`]+`"              # a command or symbol in backticks
    r"|\.py\b|\.md\b|\.yml\b"    # a file that carries the check
    r"|\d+\s*%"             # a target rate
    r"|\b\d[\d,]*\b",        # a target count
)


def names_a_verification(text):
    """Whether a backlog row says something a reader could actually go and check."""
    return bool(_VERIFIABLE.search(text or ""))


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def test_the_verification_rule_measures_verification():
    """The old rule was anti-correlated with what it claimed to measure.

    Found by external audit, which tested it directly rather than reading it. `len(verify)
    < 25` accepted a 52-character sentence that verifies nothing and rejected a
    17-character shell command that verifies something. A guard whose failures and passes
    run opposite to its purpose is worse than no guard, because it certifies the thing it
    was meant to catch.
    """
    print("\n[backlog] the rule accepts checkable things and rejects prose")
    for text in ("`pytest -k owner`",
                 "`python bench/usage.py --days 14`",
                 "tests/test_risk.py goes green",
                 "false positive rate below 5%",
                 "at least 3 trial commitments"):
        check("accepts %r" % text[:38], names_a_verification(text), "rejected")
    for text in ("we will know it when we see it, probably soon enough",
                 "it should be obvious once the work is finished",
                 "when it feels right",
                 ""):
        check("rejects %r" % text[:38], not names_a_verification(text), "accepted")


def main():
    print("=" * 68)
    print("Backlog: every open item can be verified")
    print("=" * 68)

    # Discovered, not listed. Fourth runner in this repository to hide a test from
    # itself by naming its checks by hand.
    for _, _fn in sorted((k, v) for k, v in globals().items()
                         if k.startswith("test_")):
        _fn()

    if not os.path.exists(BACKLOG):
        print("docs/BACKLOG.md is missing -- the queue has no home.")
        return 1
    text = io.open(BACKLOG, encoding="utf-8").read()

    rows = []
    for wid, rest in _ROW.findall(text):
        cells = [c.strip() for c in rest.split("|")]
        rows.append({"id": wid, "cells": cells, "raw": rest})

    check("the backlog has items", bool(rows), "no W-numbered rows found")
    if not rows:
        return 1

    ids = [r["id"] for r in rows]
    check("ids are unique", len(ids) == len(set(ids)),
          str([i for i in ids if ids.count(i) > 1]))

    nums = sorted(int(i[1:]) for i in ids)
    check("ids run without gaps, so none was quietly dropped",
          nums == list(range(1, len(nums) + 1)),
          "have %s" % nums)


    import rounds  # noqa: E402
    known_rounds = {r[0] for r in rounds.ROUNDS}

    no_verify, bad_round, no_blocker = [], [], []
    states = {"open": 0, "blocked": 0, "done": 0, "rejected": 0}
    for r in rows:
        # Closed items live in a two-column table: id | item | outcome.
        if len(r["cells"]) < 4:
            outcome = " ".join(r["cells"])
            if "Rejected" in outcome:
                states["rejected"] += 1
            elif "Done" in outcome:
                states["done"] += 1
                # Closed rows cite a round too, and it is checked here as well -- a
                # closed item pointing at a round that does not exist is the same broken
                # link as an open one.
                m = re.search(r"Done\s+(R\d+)", outcome)
                if not m or m.group(1) not in known_rounds:
                    bad_round.append("%s -> closed row cites %s"
                                     % (r["id"], m.group(1) if m else "no round"))
            continue

        state = r["cells"][3] if len(r["cells"]) > 3 else ""
        verify = r["cells"][2] if len(r["cells"]) > 2 else ""

        if state.startswith("Open"):
            states["open"] += 1
            if not names_a_verification(verify):
                no_verify.append("%s (%r)" % (r["id"], verify[:40]))
        elif state.startswith("Blocked"):
            states["blocked"] += 1
            if "lock" not in verify.lower() and "Blocked" not in verify:
                no_blocker.append(r["id"])
        elif state.startswith("Done"):
            states["done"] += 1
            m = re.search(r"Done\s+(R\d+)", state)
            if not m or m.group(1) not in known_rounds:
                bad_round.append("%s -> %s" % (r["id"], state))

    check("every open item names how it will be verified", not no_verify,
          "; ".join(no_verify))
    check("every blocked item names its blocker", not no_blocker,
          "; ".join(no_blocker))
    check("every done item cites a round that exists", not bad_round,
          "; ".join(bad_round))

    print("\n  open %d, blocked %d, done %d, rejected %d"
          % (states["open"], states["blocked"], states["done"], states["rejected"]))

    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
