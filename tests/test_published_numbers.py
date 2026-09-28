"""test_published_numbers.py -- what we publish must equal what we measured.

The product's pitch is that it publishes its own accuracy, and the reason that is worth
anything is that a reader can check it. An external audit found those figures three
generations stale in every place a reader meets them: the README, the landing page and
`/llms.txt` all said 199 tokens, 11.3% false positives, 21.0% unknown and "recall not
measurable", while the benchmark said 558, 3.5%, 17.2% and a measured recall.

Nothing tied them together, so they drifted the moment the benchmark improved -- and they
drifted in the flattering direction only by accident. A claim that cannot survive being
checked is worse than no claim, because the whole strategy rests on models citing numbers
they can verify.

Run:  python tests/test_published_numbers.py
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))

import publish_numbers  # noqa: E402
import scorecard  # noqa: E402

SCORECARD_MD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "docs", "SCORECARD.md")

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


# ------------------------------------------------- docs/SCORECARD.md's production row
#
# bench/scorecard.py writes this row in one of two forms, by rules fixed before the first
# reading (DECISIONS.md D7, pinned by tests/test_scorecard_production.py): a figure,
# `<rate>% of <n>, <start> to <end>`, when bench/production/verdicts.json is at most 7 days
# older than the newest snapshot and holds at least PRODUCTION_MIN_ROWS answers; otherwise
# `not measured (<reason>)`. The guard knew only the figure. When b051254 moved the window
# below the floor, the scorecard was right, this test went red, and CI stopped at step 6 of
# 27 on every run from 2026-09-22 -- with no figure for --write to rewrite, and nothing for
# `scorecard.py --write` to change. These checks judge the row in every regime, against
# synthetic artifacts in a temporary directory; the committed files are never written.

PRODUCTION_ROW = "| Correctness | unknown rate (production, served answers) |"
NEWEST = "2026-09-20"        # the newest snapshot date the synthetic artifacts are judged by
OLD_WINDOW = {"start": "2026-09-04T06:40:00Z", "end": "2026-09-11T06:40:00Z"}  # 9 days before


def verdicts(unknown, total, start="2026-09-12T06:40:00Z", end="2026-09-19T06:40:00Z"):
    """A bench/production/verdicts.json, in the shape tests/test_scorecard_production.py uses."""
    return {"window_start": start, "window_end": end,
            "counts": {"low": total - unknown, "medium": 0, "high": 0, "unknown": unknown}}


def rate_of(v):
    """The artifact's unknown rate as bench/scorecard.py prints it: (unknown / n) * 100."""
    c = v["counts"]
    return "%.1f" % (c["unknown"] / float(sum(c.values())) * 100)


def figure_row(v, rate=None):
    """The row carrying a figure, at the artifact's own rate unless another is given. The
    score cell follows the benchmark's bands so the row reads like a real one; the guard
    reads the evidence cell."""
    rate = rate or rate_of(v)
    points = next((p for below, p in ((5, 5.0), (10, 4.0), (20, 3.0), (30, 2.0))
                   if float(rate) < below), 1.0)
    return "%s %.1f | 5 | %s%% of %d, %s to %s |" % (
        PRODUCTION_ROW, points, rate, sum(v["counts"].values()),
        v["window_start"][:10], v["window_end"][:10])


def not_measured_row(why):
    return "%s — | 5 | not measured (%s) |" % (PRODUCTION_ROW, why)


def judge(rows, v, newest=NEWEST, write=False):
    """docs/SCORECARD.md's stale entries from publish_numbers.scan(write), and the file's text
    after that scan, with the production row replaced by `rows` (None keeps the committed
    row) and bench/production/verdicts.json replaced by `v`.

    Both go into a temporary directory -- the committed scorecard with that one line swapped,
    and the artifact where bench/scorecard.py reads it, the way
    tests/test_scorecard_production.py's _items_with() builds its inputs -- so no committed
    file is ever written, not even by --write.
    """
    with io.open(SCORECARD_MD, encoding="utf-8") as f:
        lines = f.read().splitlines()
    at = [i for i, line in enumerate(lines) if line.startswith(PRODUCTION_ROW)]
    if len(at) != 1:
        raise AssertionError("docs/SCORECARD.md has %d production rows, not 1" % len(at))
    if rows is not None:
        lines[at[0]:at[0] + 1] = [rows] if isinstance(rows, str) else list(rows)
    tmp = tempfile.mkdtemp()
    saved = (publish_numbers.ROOT, scorecard.PRODUCTION, scorecard.newest_snapshot_date)
    try:
        os.makedirs(os.path.join(tmp, "docs"))
        os.makedirs(os.path.join(tmp, "production"))
        md = os.path.join(tmp, "docs", "SCORECARD.md")
        with io.open(md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with io.open(os.path.join(tmp, "production", "verdicts.json"), "w",
                     encoding="utf-8") as f:
            json.dump(v, f)
        publish_numbers.ROOT = tmp
        scorecard.PRODUCTION = os.path.join(tmp, "production")
        scorecard.newest_snapshot_date = lambda: newest
        _, stale, _ = publish_numbers.scan(write=write)
        with io.open(md, encoding="utf-8") as f:
            return [s for s in stale if s[0] == "docs/SCORECARD.md"], f.read()
    finally:
        publish_numbers.ROOT, scorecard.PRODUCTION, scorecard.newest_snapshot_date = saved
        shutil.rmtree(tmp, ignore_errors=True)


def expect(name, rows, v, accepted, newest=NEWEST):
    """Accepted: scan() returns no stale entry for docs/SCORECARD.md. Rejected: at least one."""
    stale, _ = judge(rows, v, newest)
    check(name, not stale if accepted else bool(stale),
          "scan() found: %s" % ("; ".join("%s, expected %s" % (s[2], s[3]) for s in stale)
                                or "nothing stale"))


def written(v, newest=NEWEST):
    """The production row bench/scorecard.py writes for artifact `v`: its own render, with the
    artifact in a temporary directory and its three test suites stubbed, as _items_with()
    does in tests/test_scorecard_production.py."""
    tmp = tempfile.mkdtemp()
    saved = (scorecard.PRODUCTION, scorecard.newest_snapshot_date, scorecard.tests_pass)
    try:
        with io.open(os.path.join(tmp, "verdicts.json"), "w", encoding="utf-8") as f:
            json.dump(v, f)
        scorecard.PRODUCTION = tmp
        scorecard.newest_snapshot_date = lambda: newest
        scorecard.tests_pass = lambda: (True, ["stubbed"])
        with redirect_stdout(io.StringIO()):        # score() prints a note on every call
            md = scorecard.render(*scorecard.score())
    finally:
        scorecard.PRODUCTION, scorecard.newest_snapshot_date, scorecard.tests_pass = saved
        shutil.rmtree(tmp, ignore_errors=True)
    rows = [line for line in md.splitlines() if line.startswith(PRODUCTION_ROW)]
    if len(rows) != 1:
        raise AssertionError("bench/scorecard.py rendered %d production rows" % len(rows))
    return rows[0]


def check_below_the_floor():
    floor = scorecard.PRODUCTION_MIN_ROWS
    n = floor - 1
    v = verdicts(n // 10, n)
    right = not_measured_row("%d answers in the window, need %d" % (n, floor))
    print("\n[production row] below the floor: %d answers on a fresh artifact, floor %d"
          % (n, floor))
    expect("`not measured (%d answers in the window, need %d)` is accepted" % (n, floor),
           right, v, True)
    expect("the same row with a different n is rejected",
           not_measured_row("%d answers in the window, need %d" % (n - 1, floor)), v, False)
    expect("the same row with a different floor is rejected",
           not_measured_row("%d answers in the window, need %d" % (n, floor + 1)), v, False)
    expect("a row carrying the artifact's own figure is rejected", figure_row(v), v, False)
    expect("and so is that figure beside the right `not measured` row",
           [right, figure_row(v)], v, False)


def check_at_the_floor():
    floor = scorecard.PRODUCTION_MIN_ROWS
    v = verdicts(floor // 10, floor)
    print("\n[production row] at the floor: exactly %d answers on a fresh artifact" % floor)
    expect("the artifact's figure (%s%% of %d) is accepted" % (rate_of(v), floor),
           figure_row(v), v, True)
    expect("a figure with a different rate is rejected",
           figure_row(v, rate="%.1f" % (float(rate_of(v)) + 1)), v, False)
    expect("`not measured (%d answers in the window, need %d)` is rejected" % (floor, floor),
           not_measured_row("%d answers in the window, need %d" % (floor, floor)), v, False)


def check_a_stale_artifact():
    floor = scorecard.PRODUCTION_MIN_ROWS
    v = verdicts(3 * floor // 10, 2 * floor, **OLD_WINDOW)
    why = "bench/production/verdicts.json is 9 days older than the archive"
    print("\n[production row] a stale artifact: %d answers, window_end 9 days before the "
          "newest snapshot" % (2 * floor))
    expect("`not measured (%s)` is accepted" % why, not_measured_row(why), v, True)
    expect("a row carrying the artifact's own figure is rejected", figure_row(v), v, False)


def check_the_floor_is_read_from_the_scorecard():
    floor = scorecard.PRODUCTION_MIN_ROWS
    n = floor - 1
    v = verdicts(n // 10, n)
    below = not_measured_row("%d answers in the window, need %d" % (n, floor))
    print("\n[production row] one rule, one source: scorecard.PRODUCTION_MIN_ROWS patched "
          "in memory")
    scorecard.PRODUCTION_MIN_ROWS = n
    try:
        expect("patched to %d: the artifact's figure is accepted" % n, figure_row(v), v, True)
        expect("patched to %d: a figure with a different rate is rejected" % n,
               figure_row(v, rate="%.1f" % (float(rate_of(v)) + 1)), v, False)
        expect("patched to %d: the `not measured` row is rejected" % n, below, v, False)
    finally:
        scorecard.PRODUCTION_MIN_ROWS = floor
    expect("restored to %d: the `not measured` row is accepted" % floor, below, v, True)
    expect("restored to %d: the figure is rejected" % floor, figure_row(v), v, False)


def check_the_row_the_scorecard_writes_passes():
    """The seam itself: whatever bench/scorecard.py writes for an artifact, the guard accepts.

    46 of 160 is exactly 28.75%. The scorecard computes (46 / 160.0) * 100, which is
    28.749999999999996 and prints 28.7; 100.0 * 46 / 160, the order
    publish_numbers._production_unknown_pct() uses, is 28.75 and prints 28.8. A guard that
    computes the rate its own way rejects the scorecard's row. Any multiple of 46 of 160
    divides to the same double, so the case is scaled past the floor.
    """
    floor = scorecard.PRODUCTION_MIN_ROWS
    k = -(-floor // 160)
    print("\n[production row] the row bench/scorecard.py writes passes the guard")
    for label, v in (("below the floor", verdicts((floor - 1) // 10, floor - 1)),
                     ("at the floor", verdicts(floor // 10, floor)),
                     ("stale", verdicts(3 * floor // 10, 2 * floor, **OLD_WINDOW)),
                     ("%d of %d" % (46 * k, 160 * k), verdicts(46 * k, 160 * k))):
        row = written(v)
        expect("%s: %s" % (label, row[len(PRODUCTION_ROW):].strip(" |")), row, v, True)
    v = verdicts(46 * k, 160 * k)
    other = "%.1f" % (float(re.search(r"\| ([\d.]+)% of", written(v)).group(1)) + 0.1)
    expect("%d of %d: the same figure at %s%%, 0.1 above the scorecard's, is rejected"
           % (46 * k, 160 * k, other), figure_row(v, rate=other), v, False)


def check_write():
    print("\n[production row] python bench/publish_numbers.py --write, in a copy")
    with io.open(os.path.join(scorecard.PRODUCTION, "verdicts.json"), encoding="utf-8") as f:
        committed = json.load(f)
    with io.open(SCORECARD_MD, encoding="utf-8") as f:
        before = f.read().splitlines()
    _, after = judge(None, committed, scorecard.newest_snapshot_date(), write=True)
    check("the current tree: --write leaves docs/SCORECARD.md unchanged",
          after.splitlines() == before,
          str([line for line in after.splitlines() if line.startswith(PRODUCTION_ROW)]))
    floor = scorecard.PRODUCTION_MIN_ROWS
    v = verdicts((floor - 1) // 10, floor - 1)
    _, after = judge(figure_row(v), v, write=True)
    check("below the floor: --write leaves a figure row for the scorecard to rewrite",
          figure_row(v) in after.splitlines(),
          str([line for line in after.splitlines() if line.startswith(PRODUCTION_ROW)]))
    v = verdicts(floor // 10, floor)
    _, after = judge(figure_row(v, rate="%.1f" % (float(rate_of(v)) + 1)), v, write=True)
    check("at the floor: --write corrects a wrong rate to the artifact's %s%%" % rate_of(v),
          "| 5 | %s%% of %d, " % (rate_of(v), floor) in after,
          str([line for line in after.splitlines() if line.startswith(PRODUCTION_ROW)]))


def main():
    print("=" * 66)
    print("Published accuracy figures match the benchmark")
    print("=" * 66)

    if not os.path.exists(publish_numbers.RESULTS):
        print("bench/results.json missing -- run bench/run_benchmark.py first")
        return 1

    # W23. The maturity total's only source is docs/SCORECARD.md, which is generated and
    # was guarded by nobody -- so a stale scorecard made every copy of the total agree on
    # a number that had stopped being true, and this very script reported success.
    #
    # Not hypothetical: when this check was added the committed file said "test_risk.py
    # 272 passed" against a real 277, "test_mcp.py 73" against 80, and "6 of 180 days" of
    # archive against 7. The total still rounded to 55, which is luck, not design.
    #
    # tests/test_rounds.py has applied exactly this to docs/ROUNDS.md for weeks. The
    # scorecard, the more load-bearing of the two, never got it.
    #
    # Text mode on both sides: the committed file is CRLF under git autocrlf and the
    # generator writes LF, so a bytes comparison would fail everywhere and get deleted.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "bench"))
    import scorecard
    want = scorecard.render(*scorecard.score())
    with io.open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "docs", "SCORECARD.md"), encoding="utf-8") as f:
        have = f.read()
    scorecard_stale = have.strip() != want.strip()
    if scorecard_stale:
        print("\ndocs/SCORECARD.md is NOT what bench/scorecard.py produces.")
        print("The maturity total is read from that file, so every copy of it is")
        print("currently agreeing with a number the generator no longer computes.")
        print("Regenerate: python bench/scorecard.py --write")

    vals, stale, _ = publish_numbers.scan(write=False)
    print("benchmark says: n=%s, false positives %s%% on %s healthy tokens, "
          "unknown %s%%, dead %s"
          % (vals["n"], vals["fp_pct"], vals["healthy_n"], vals["unknown_pct"],
             vals["dead_n"]))

    # Not just "does each guarded number match" but "is every number guarded". Four
    # published figures had drifted with nothing watching them, all four in the
    # flattering direction, in the product whose one differentiator is that its numbers
    # can be checked. Adding a target per number an audit happens to find fixes those
    # four and leaves the fifth wide open -- which is how these four got there.
    loose = publish_numbers.unclaimed_percentages()

    # The production row in every regime the scorecard's rule defines. Run after the scan
    # above, because each check patches module state for one scan and then restores it.
    for _, fn in sorted((k, f) for k, f in globals().items() if k.startswith("check_")):
        fn()
    print("\nproduction row: %d passed, %d failed" % (_PASSED, len(_FAILURES)))

    if not stale and not loose and not scorecard_stale and not _FAILURES:
        print("\nevery published figure matches, and every published figure is guarded")
        print("PASS")
        return 0

    if loose:
        print("\n%d published percentage(s) that no target claims:\n" % len(loose))
        for rel, pct, line in loose:
            print("  %-18s %s%%" % (rel, pct))
            print("      %s" % line)
        print("\nAdd a TARGETS entry, or stop publishing the number.")

    if stale:
        print("\n%d published figure(s) disagree:\n" % len(stale))
        for rel, pattern, found, want in stale:
            print("  %-18s published %-8s measured %-8s" % (rel, found, want))
            print("      %s" % pattern[:70])
        print("\nRun `python bench/publish_numbers.py --write`, then redeploy.")

    if _FAILURES:
        print("\n%d production-row check(s) failed:" % len(_FAILURES))
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
