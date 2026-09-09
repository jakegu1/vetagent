"""The snapshot archive stays public in git until a measured, pre-registered threshold.

DECISIONS B15. The archive is committed to a public repository four times a day, and that
was decided on numbers rather than argued: `.git` was 5.8 MB packed after six days, growing
0.95 MB/day, which reaches 200 MB in about 205 days. Publishing buys reproducibility -- a
hostile review of the launch post had just found a stranger could not reproduce our figures
at all -- and moving the archive to R2 would make W7's future "would it have warned you"
claim unverifiable by anyone outside the project.

So the move to R2 is not cancelled. It is **triggered**, and this is the trigger. A plan to
do something "when the repo gets big" is a wish; a test that fails on the day is a date.

Two properties this deliberately has:

**It measures the packed repository, not the working tree.** `du -sh bench/snapshots` says
12 MB and `.git` says 5.8 MB, and the second is what a person cloning this actually pays.
This project once filed a storage ticket off the working-tree number and was wrong by 18x.

**It warns before it fails.** Crossing the threshold is not an emergency -- it is a day of
work that should be scheduled, so the run goes yellow at 80% and red at 100%.

Run: python tests/test_archive_budget.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The number in DECISIONS B15. Changing it here changes the decision, so it must be
# changed there too -- and the test below fails if the two disagree.
BUDGET_MB = 200
WARN_AT = 0.8
RETAIN_DAYS = 90

_PASSED = 0
_FAILURES = []
_WARNINGS = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def packed_mb():
    """What the server stores, which is what a cloner pays -- not the working tree."""
    total = 0
    git_dir = os.path.join(ROOT, ".git")
    for root, _, files in os.walk(git_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return total / 1048576.0


def test_the_repository_is_inside_its_budget():
    print("\n[B15] the archive's cost to a cloner")
    mb = packed_mb()
    print("       .git is %.1f MB of a %d MB budget (%.0f%%)"
          % (mb, BUDGET_MB, 100.0 * mb / BUDGET_MB))

    check("the packed repository is under budget", mb < BUDGET_MB,
          "%.1f MB >= %d MB -- DECISIONS B15 says move snapshots older than %d days to "
          "R2 now and keep a rolling window in git" % (mb, BUDGET_MB, RETAIN_DAYS))

    if BUDGET_MB * WARN_AT <= mb < BUDGET_MB:
        _WARNINGS.append(
            "%.1f MB is past %.0f%% of the budget. B15's move to R2 is close: schedule it "
            "rather than waiting for a red build." % (mb, WARN_AT * 100))
        print("  WARN  approaching the budget: %s" % _WARNINGS[-1])


def test_the_decision_says_the_same_number():
    """A threshold in a test and a different one in the decision is two decisions."""
    print("\n[B15] the test and the decision agree")
    path = os.path.join(ROOT, "docs", "DECISIONS.md")
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    row = [l for l in text.splitlines() if l.startswith("| B15 |")]
    check("B15 exists in DECISIONS.md", bool(row))
    if not row:
        return
    check("it states the same budget", "%d MB" % BUDGET_MB in row[0],
          "test says %d MB; the row does not" % BUDGET_MB)
    check("it states the same retention", "%d" % RETAIN_DAYS in row[0],
          "test retains %d days; the row does not say so" % RETAIN_DAYS)
    check("it names this test as the enforcement", "test_archive_budget" in row[0],
          "a decision whose enforcement is nobody is a wish")


def main():
    print("=" * 68)
    print("B15: the archive stays public until a measured threshold")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for w in _WARNINGS:
        print("  WARN  %s" % w)
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
