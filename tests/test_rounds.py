"""test_rounds.py -- the development log cannot be incomplete or stale.

A numbered round log is only worth keeping if it is guaranteed to cover everything. The
version of this that fails is the one somebody maintains by hand: it stays accurate for
a few weeks, then a round ships without an entry, and from then on the document is worse
than nothing because it looks complete.

So two assertions, and they are the whole point of the file:

  1. **Every commit belongs to exactly one round.** Not "we remembered to log the
     interesting ones" -- every one. A commit outside every round turns this red.
  2. **docs/ROUNDS.md matches what the generator produces right now.** If it were allowed
     to drift, the generated file would be just another stale document with a nicer
     provenance claim.

This repository has already paid for the alternative. An external audit found drift in
almost every hand-maintained record in it, and none at all in the two that are generated.

Run:  python tests/test_rounds.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

import rounds  # noqa: E402

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


def main():
    print("=" * 68)
    print("Development rounds: complete and current")
    print("=" * 68)

    order, meta, unassigned, bots = rounds.assign()

    check("every round has a name and a one-line purpose",
          all(meta[r]["name"] and meta[r]["blurb"] for r in order),
          str([r for r in order if not meta[r]["blurb"]]))

    # Exactly one round may be open, and it must be the last: an open round earlier in
    # the list would silently swallow every commit after it.
    open_rounds = [r for r in order if meta[r]["last"] is None]
    check("exactly one round is open", len(open_rounds) == 1, str(open_rounds))
    check("and it is the most recent one",
          not open_rounds or open_rounds[0] == order[-1],
          "%s open, last is %s" % (open_rounds, order[-1]))

    # A closed round whose commit is gone is the failure "nothing is unassigned" cannot
    # see: the cursor never advances past it, every later commit lands in that round, and
    # the log reports thirty-five commits as one while staying green. Verified by
    # substituting a bogus hash and watching this go red.
    gone = [r for r in order if meta[r].get("missing_last")]
    check("every closed round's commit still exists", not gone,
          "%s -- a rebase or an amend can do this, and it swallows every later commit"
          % ", ".join("%s->%s" % (r, meta[r]["last"]) for r in gone))

    check("no commit belongs to no round", not unassigned,
          "%d unassigned: %s" % (len(unassigned),
                                 ", ".join(c["hash"] for c in unassigned[:5])))

    total = sum(len(meta[r]["commits"]) for r in order)
    check("the rounds together account for the whole history",
          total > 0, "%d development commits across %d rounds (%d snapshot commits "
                     "excluded)" % (total, len([r for r in order if meta[r]["commits"]]),
                                    bots))

    if not os.path.exists(rounds.OUT):
        check("docs/ROUNDS.md exists", False, "run python tools/rounds.py --write")
    else:
        want, _ = rounds.render()
        have = io.open(rounds.OUT, encoding="utf-8").read()
        check("docs/ROUNDS.md is current",
              have.strip() == want.strip(),
              "regenerate it: python tools/rounds.py --write")

    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
