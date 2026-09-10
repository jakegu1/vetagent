"""test_decisions_enforcement.py — the enforcement column has to be true.

DECISIONS.md's whole premise is in its own header: "docs rot, and they rot silently. So
every decision also has to answer: what is enforcing it?" The enforcement column names a
test, and a named test is called "**the strongest kind** -- the rule alarms on its own."

Nothing checked that those names existed.

An external audit found two that did not. E20 cited `test_owner_power_selectors_are_real`;
the real name is `test_selectors_are_real`. E12 cited
`test_liquidity_prefers_canonical_chain`; no such test has ever existed -- the coverage
lives inside `test_liquidity_picks_the_right_pool`. Both are naming drift rather than
missing coverage, which is precisely why nobody noticed: the rule was enforced, the
document just pointed at the wrong guard. A reader auditing the project would have gone
looking for a test that is not there and drawn their own conclusion.

R11 built a currency check for ROUNDS.md and a shape check for BACKLOG.md and left this
one unguarded -- the file whose entire point is enforcement was the file with none.

Run:  python tests/test_decisions_enforcement.py
"""

import io
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DECISIONS = os.path.join(ROOT, "docs", "DECISIONS.md")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

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


def defined_test_names():
    """Every test function defined anywhere under tests/."""
    names = set()
    for fn in sorted(os.listdir(TESTS_DIR)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(TESTS_DIR, fn), encoding="utf-8") as f:
            for m in re.finditer(r"^def (test_[A-Za-z0-9_]+)", f.read(), re.M):
                names.add(m.group(1))
    return names


def cited_test_names(text):
    """Every `test_...` cited anywhere in DECISIONS.md, with its row id."""
    out = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        row_id = cells[1] if len(cells) > 2 else "?"
        for m in re.finditer(r"`(test_[A-Za-z0-9_]+)`", line):
            out.append((row_id, m.group(1)))
    return out


def test_every_test_file_runs_in_ci():
    """A guard CI never invokes is a guard nobody will ever see fail.

    .github/workflows/test.yml names each suite in its own step. That is readable, and it
    means adding a test file is silently a no-op in CI until someone also edits the
    workflow. This project has already paid for that shape twice -- test_owner_powers.py
    ran a hand-maintained list of three functions, so a fourth passed by never executing;
    and CI was red from R11 for days with nobody looking.

    So the list is allowed to stay explicit, but it is no longer allowed to be incomplete.
    """
    print("\n[decisions] every test file is wired into CI")
    workflow = os.path.join(ROOT, ".github", "workflows", "test.yml")
    check("the workflow exists", os.path.exists(workflow), workflow)
    if not os.path.exists(workflow):
        return
    with open(workflow, encoding="utf-8") as f:
        ci = f.read()
    files = sorted(fn for fn in os.listdir(TESTS_DIR)
                   if fn.startswith("test_") and fn.endswith(".py"))
    orphans = [fn for fn in files if fn not in ci]
    check("no test file is missing from the workflow", not orphans, str(orphans))


def test_every_named_test_exists():
    """The strongest enforcement kind must actually be enforcing something."""
    print("\n[decisions] every test named in the enforcement column exists")
    with open(DECISIONS, encoding="utf-8") as f:
        text = f.read()
    defined = defined_test_names()
    # A row may legitimately name a whole test FILE rather than one function -- "the
    # sellability gap is covered by tests/test_owner_powers.py" is a real enforcement.
    # Accept either, and only fail when neither exists.
    defined |= {fn[:-3] for fn in os.listdir(TESTS_DIR) if fn.endswith(".py")}
    cited = cited_test_names(text)
    check("the file cites at least a dozen tests", len(cited) >= 12,
          "%d cited" % len(cited))
    missing = [(rid, n) for rid, n in cited if n not in defined]
    check("every cited test is defined under tests/", not missing,
          "; ".join("%s -> %s" % (rid, n) for rid, n in missing))


def test_the_row_count_is_honest():
    """The file states its own size, and that number drifted too.

    DECISIONS.md said 54 and BACKLOG.md W8 said 63; the real count was 55. A file that
    miscounts its own rows is weak evidence for every other number in it, and this one is
    trivially derivable.
    """
    print("\n[decisions] the stated row count matches the table")
    with open(DECISIONS, encoding="utf-8") as f:
        text = f.read()
    rows = [ln for ln in text.splitlines()
            if re.match(r"^\|\s*[A-Z]+\d+\s*\|", ln)]
    stated = re.search(r"table is at (\d+) rows", text)
    check("the file states its row count", bool(stated),
          "no 'table is at N rows' line")
    if stated:
        check("and the count is right",
              int(stated.group(1)) == len(rows),
              "states %s, actual %d" % (stated.group(1), len(rows)))


def test_no_test_function_is_unreachable_by_its_own_runner():
    """A test defined and never called is worse than no test: it reads as coverage.

    Every file here is its own runner -- `python tests/test_x.py` -- and a runner that names
    its tests by hand goes stale the moment somebody adds one. On 2026-09-10 a new test was
    added to `tests/test_backfill.py`, whose `main()` held a hand-written tuple of four
    function names. The file printed "12 passed, 0 failed" with eleven of its own checks
    never executed, and it was green in CI.

    This repo already records that incident once -- "four hand-maintained test runners were
    silently skipping tests, including CI's own step list" -- and the fix at the time was to
    repair the four. Repairing instances is not closing a class.

    So: a test file either uses the discovery idiom, or names every one of its own test
    functions inside `main()`. Static, because running twenty files to find out costs a
    minute and the answer is in the source.
    """
    print(chr(10) + "[enforcement] every test a file defines is a test that runs")
    tests_dir = os.path.join(ROOT, "tests")
    checked = 0
    for name in sorted(os.listdir(tests_dir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        src = io.open(os.path.join(tests_dir, name), encoding="utf-8").read()
        defined = set(re.findall(r"^def (test_[A-Za-z0-9_]+)", src, re.M))
        if not defined:
            continue                       # script-style file with no test functions
        checked += 1
        if re.search(r"startswith\(['\"]test_['\"]\)", src):
            continue                       # discovers its own tests
        body = src[src.index("def main("):] if "def main(" in src else src
        missing = sorted(f for f in defined if f not in body)
        check("%s: runner reaches all %d of its tests" % (name, len(defined)),
              not missing,
              "hand-listed runner is missing %s -- switch to the discovery idiom"
              % ", ".join(missing))
    check("test files with test functions were found", checked >= 15, str(checked))


def main():
    print("=" * 68)
    print("DECISIONS.md enforcement column")
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
