"""Every number a stranger can read is either guarded, or exempt for a stated reason.

W21. `publish_numbers.py` checks that guarded numbers still *match*. It never checked that
the guard *covers* anything, so the coverage was whatever somebody remembered to add. Two
consequences, both found by mutating all 87 percentages on the live surfaces one at a time
and seeing which survived:

**Five outward surfaces were never scanned at all.** `LIVE_CLAIM_FILES` was the six files
that existed the day the guard was written. R19 created an app-store submission, a plugin
README, a plugin skill and an install guide, and the guard did not know they existed. A
file list frozen on its authoring day stops covering the project the moment it grows.

**Every number inside a markdown blockquote was silently unguarded**, because the
blockquote marker `>` is indistinguishable from a "greater than" and the guard skips
comparisons on purpose ("recall >90%" is an aim, not a measurement). The X / Mastodon
draft is one long blockquote, so the shortest, most-copied version of the launch post was
the least protected thing in the repository.

This test is the standing version of that sweep. It does not re-mutate on every run --
that costs a subprocess per number -- it asserts the two structural properties that made
the holes possible, plus a spot mutation on the surface that matters most.

Run: python tests/test_number_coverage.py
"""

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import publish_numbers as pn  # noqa: E402

_PASSED = 0
_FAILURES = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def test_every_outward_surface_is_scanned():
    """A file a stranger reads our numbers from must be in the scanned list."""
    print("\n[W21] every surface a stranger reads is scanned")
    # Three ways a number can be covered, and the test accepts all three: a TARGETS
    # regex on a live surface, a frozen log that records what was believed at a date, or
    # generation plus a regeneration check. What it refuses is a fourth: nothing.
    scanned = (set(pn.LIVE_CLAIM_FILES) | set(pn.FROZEN_LOG_FILES)
               | set(pn.GENERATED_FILES))

    # Anything tracked, human-readable, and carrying a percentage is a surface.
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    unscanned = []
    for rel in out.splitlines():
        if not rel.endswith((".md", ".html")) or rel in scanned:
            continue
        if rel.startswith(("bench/snapshots/", "bench/results")):
            continue          # generated data, not prose a reader meets
        path = os.path.join(ROOT, rel)
        try:
            text = io.open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if re.search(r"\d+(?:\.\d+)?%", text):
            unscanned.append(rel)

    check("no tracked prose surface carries a percentage unscanned", not unscanned,
          "add to LIVE_CLAIM_FILES or FROZEN_LOG_FILES: %s" % ", ".join(unscanned))


def test_no_exemption_list_is_defined_and_never_used():
    """An exemption nobody consults reads exactly like an exemption that works.

    `_EXEMPT_CONTEXT` sat in bench/publish_numbers.py with eight reasoned entries and a
    comment about how honest an exemption list with reasons is, and nothing anywhere called
    it. `_EXEMPT_LINES` had superseded it and the loser stayed. One of its entries was a
    stale owner-power recall figure, so a reader checking why that number was allowed found
    a deliberate-looking answer from a guard that did not run.

    Same shape as the four hand-maintained test runners that were silently skipping tests,
    and as the counting rule that was committed, described as the instrument, and never
    called. So: any module-level name in publish_numbers.py that looks like an exemption or
    a target list must appear somewhere other than its own definition.
    """
    print(chr(10) + "[W21] every exemption list is actually consulted")
    src = io.open(os.path.join(ROOT, "bench", "publish_numbers.py"),
                  encoding="utf-8").read()
    names = re.findall(r"^([A-Z_]*(?:EXEMPT|TARGET|CLAIM|RETRACT)[A-Z_]*)\s*=", src, re.M)
    check("exemption-shaped names were found", len(names) >= 3, str(names))
    for name in sorted(set(names)):
        uses = len(re.findall(r"\b%s\b" % re.escape(name), src)) - 1
        check("%s is used %d time(s) after being defined" % (name, uses), uses >= 1,
              "defined and never referenced -- wire it up or delete it")


def test_a_blockquote_does_not_hide_a_number():
    """`> 4.3%` is a quoted measurement; `>90%` is an aim. The guard must tell them apart."""
    print("\n[W21] a markdown blockquote is not a comparison operator")
    src = io.open(os.path.join(ROOT, "bench", "publish_numbers.py"),
                  encoding="utf-8").read()
    body = src.split("def unclaimed_percentages(")[-1].split("\ndef ")[0]
    check("the scan strips a leading blockquote marker before testing for an operator",
          re.search(r'sub\(r"\^\\s\*>\+\\s\*"', body) is not None,
          "without this every figure in the X / Mastodon draft is unguarded")


def test_the_shortest_draft_is_actually_guarded():
    """The most-copied version of the post, mutated for real -- four subprocesses.

    Spot-checked rather than swept: this is the surface where an unguarded number does
    the most damage per character, and it is the one that was completely unprotected.
    """
    print("\n[W21] the X / Mastodon draft, mutated number by number")
    rel = "docs/EXPERIMENT_C.md"
    path = os.path.join(ROOT, rel)
    orig = io.open(path, encoding="utf-8").read()
    try:
        a = orig.index("## The short version")
        b = orig.index("## Hacker News")
    except ValueError:
        check("the short version exists", False, "section headings moved")
        return

    nums = list(re.finditer(r"(\d+(?:\.\d+)?)%", orig[a:b]))
    check("the draft has numbers to guard", len(nums) >= 3, "%d found" % len(nums))

    caught = 0
    try:
        for m in nums:
            off = a + m.start(1)
            val = orig[off:off + len(m.group(1))]
            mutated = orig[:off] + ("9.9" if val != "9.9" else "8.8") + orig[off + len(val):]
            io.open(path, "w", encoding="utf-8", newline="").write(mutated)
            r = subprocess.run([sys.executable, "bench/publish_numbers.py"],
                               cwd=ROOT, capture_output=True, encoding="utf-8",
                               errors="replace")
            if r.returncode != 0:
                caught += 1
            else:
                print("       MISSED %s%% -- unguarded in the shortest draft" % val)
    finally:
        io.open(path, "w", encoding="utf-8", newline="").write(orig)

    check("every number in it fails the build when changed", caught == len(nums),
          "%d of %d caught" % (caught, len(nums)))


def main():
    print("=" * 68)
    print("W21: the number guard covers what a stranger actually reads")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
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
