"""test_owner_page.py -- the owner's page has to be true on the day it is read.

`docs/OWNER.md` exists because the person paying for this project said, in plain terms,
that they could not tell what needed them, by when, or what any of it meant. It is the
one page in this repository written for someone who is not going to read the code.

That makes staleness worse here than anywhere else. A wrong deadline on the page whose
whole job is to carry deadlines is not a documentation bug; it is the page actively doing
the opposite of its purpose. So it is generated from the files that own each fact --
STRATEGY's gate table, BACKLOG's "Yours" section, SCORECARD's total, results.json -- and
this file fails the build the moment the generated text and the committed file disagree.

The second check is the one that matters more and is easy to forget: **every accuracy
number on the page must equal the benchmark's.** `publish_numbers.py` guards the files a
stranger reads. This page is what the owner reads, and it is the page they would quote.

Run:  python tests/test_owner_page.py
"""

import io
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import owner  # noqa: E402
import publish_numbers  # noqa: E402

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


def _committed():
    p = os.path.join(ROOT, "docs", "OWNER.md")
    if not os.path.exists(p):
        return None
    return io.open(p, encoding="utf-8").read()


def test_the_page_is_current():
    """Generated and committed must agree, apart from the date it was generated on."""
    print("\n[owner] the page says what the sources say")
    have = _committed()
    check("docs/OWNER.md exists", have is not None,
          "run: python tools/owner.py --write")
    if have is None:
        return
    want = owner.render()
    strip = lambda t: re.sub(r"^> Generated .*$", "", t, flags=re.M)   # noqa: E731
    check("it is current", strip(have).strip() == strip(want).strip(),
          "regenerate it: python tools/owner.py --write")


def test_every_number_on_it_is_the_measured_one():
    """This is the page the owner would quote. It cannot carry a stale figure."""
    print("\n[owner] the numbers are the benchmark's, not last month's")
    have = _committed() or ""
    vals = publish_numbers.figures()
    for key, label in (("n", "tokens measured"),
                       ("fp_pct", "false positives"),
                       ("unknown_pct", "unknown rate"),
                       ("dead_high_pct", "dead rated high")):
        check("%s (%s) appears" % (label, vals[key]), vals[key] in have,
              "expected %s somewhere on the page" % vals[key])

    # The trap this guards: an older figure left behind next to the new one.
    for stale in ("3.7%", "11.3%", "21.0%", "17.2%", "6.7%"):
        if stale.rstrip("%") in (vals["fp_pct"], vals["unknown_pct"]):
            continue
        check("no stale %s" % stale, stale not in have)


def test_every_owner_item_has_a_reason_for_its_date():
    """A deadline with no reason is a guess, and the owner cannot argue with a guess."""
    print("\n[owner] each date says why it is that date")
    ids = {i["id"] for i in owner.yours()}
    missing = sorted(i for i in ids if i not in owner.OWNER_DUE)
    check("every open 'Yours' item is dated or explicitly undated", not missing,
          "add to OWNER_DUE in tools/owner.py: %s" % missing)
    for wid, (due, reason) in owner.OWNER_DUE.items():
        check("%s gives a reason" % wid, bool(reason and reason.strip()), wid)


def test_it_reads_the_real_gate_table():
    """If STRATEGY's dates move, this page moves. It does not keep its own copy."""
    print("\n[owner] the dates come from STRATEGY, not from a second list")
    gates = owner.gates()
    check("the gate table parsed", len(gates) >= 4, str(len(gates)))
    check("the 09-18 gate is in it",
          any(g["date"] == "2026-09-18" for g in gates), str(gates))
    src = io.open(os.path.join(ROOT, "tools", "owner.py"), encoding="utf-8").read()
    body = src.split("def gates(")[-1].split("def ")[0]
    check("it is parsed out of STRATEGY.md", "docs/STRATEGY.md" in body)


def main():
    print("=" * 68)
    print("Owner page: the one document written for someone not reading code")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
