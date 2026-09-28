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
import traceback
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


# ------------------------------------ a figure with no measurement, and what --write returns
#
# T-002. figures() leaves a key out when the measurement behind it is absent or unusable, on
# purpose: "absent means unguarded, not guarded against None". scan() read vals[key]
# directly, so with bench/production/verdicts.json moved away the first docs/EXPERIMENT_C.md
# production target raised KeyError and nothing after it was reported. And --write returned
# 0 whenever anything had been stale, including entries it could not rewrite and unclaimed
# percentages it never rewrites, while .github/scripts/regenerate-derived.sh trusts that
# status before it commits and pushes: from 2026-09-22 to 2026-09-28 every scheduled bot run
# succeeded while every `tests` run failed on this file.
#
# The rule: a target with no measurement is reported as not measured, and the run fails;
# --write returns 0 exactly when check mode, run on the files it leaves behind, returns 0.
# Each check below works in a temporary copy of the files publish_numbers.main() reads
# (in_a_copy), so no committed file is written, and turns an exception into a recorded
# failure (recorded), so the checks after it still run.

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENT_C = "docs/EXPERIMENT_C.md"
# The keys figures() takes from bench/production/verdicts.json. All five go missing when the
# artifact is absent, unreadable or empty; the last four also when it has no window dates.
PRODUCTION_KEYS = ("production_unknown_pct", "production_n", "production_from",
                   "production_from_md", "production_to_md")


def raised():
    """The exception being handled, in one line: `raised KeyError: 'production_n'`."""
    return "raised " + traceback.format_exception_only(*sys.exc_info()[:2])[-1].strip()


def recorded(fn):
    """A check that meets an exception records one failure instead of stopping the file."""
    def run():
        try:
            fn()
        except Exception:
            check("%s ran to the end" % fn.__name__, False, raised())
    run.__name__ = fn.__name__
    return run


def files_main_reads():
    """Every file publish_numbers.main() reads under ROOT, from the module's own lists: each
    target's file, LIVE_CLAIM_FILES and FROZEN_LOG_FILES (every file main() hands to
    retracted() and unsourced_competitor_figures() is in one of the two), and
    bench/owner_powers.json, which _owner_power_figures() reads by a name no list holds."""
    return sorted({rel for rel, _, _ in publish_numbers.TARGETS}
                  | set(publish_numbers.LIVE_CLAIM_FILES)
                  | set(publish_numbers.FROZEN_LOG_FILES)
                  | {"bench/owner_powers.json"})


def in_a_copy(fn, artifact=True):
    """fn(tmp), where tmp is a temporary copy of files_main_reads() and publish_numbers.ROOT
    points at it, with publish_numbers.HERE and scorecard.PRODUCTION at its bench/ and
    bench/production/, the two places bench/production/verdicts.json is read from. The
    committed artifact is copied there when `artifact` is true, and is absent otherwise.
    bench/results.json is read where it is (publish_numbers.RESULTS is fixed at import) and
    never written. Every patched global is restored and the copy removed, whatever fn does."""
    tmp = tempfile.mkdtemp()
    saved = (publish_numbers.ROOT, publish_numbers.HERE, scorecard.PRODUCTION)
    try:
        for rel in files_main_reads():
            if os.path.exists(os.path.join(REPO, rel)):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                shutil.copyfile(os.path.join(REPO, rel), os.path.join(tmp, rel))
        production = os.path.join(tmp, "bench", "production")
        os.makedirs(production, exist_ok=True)
        if artifact:
            shutil.copyfile(os.path.join(REPO, "bench", "production", "verdicts.json"),
                            os.path.join(production, "verdicts.json"))
        publish_numbers.ROOT = tmp
        publish_numbers.HERE = os.path.join(tmp, "bench")
        scorecard.PRODUCTION = production
        return fn(tmp)
    finally:
        publish_numbers.ROOT, publish_numbers.HERE, scorecard.PRODUCTION = saved
        shutil.rmtree(tmp, ignore_errors=True)


def run_main(*argv):
    """(status, output) of publish_numbers.main() with these arguments, run in this process.
    If it raises, the status is the exception in one line and the output ends with the
    traceback."""
    saved, out = sys.argv, io.StringIO()
    sys.argv = ["publish_numbers.py"] + list(argv)
    try:
        with redirect_stdout(out):
            status = publish_numbers.main()
    except Exception:
        return raised(), out.getvalue() + traceback.format_exc()
    finally:
        sys.argv = saved
    return status, out.getvalue()


def scan_entries(write):
    """(the stale entries of publish_numbers.scan(write), None), or (None, the exception)."""
    try:
        return publish_numbers.scan(write=write)[1], None
    except Exception:
        return None, raised()


def tail(out, n=6):
    """The last lines of an output, for a failure's detail."""
    return " | ".join([line.strip() for line in out.splitlines() if line.strip()][-n:])


def target(rel, key):
    """The first TARGETS entry for `key` in `rel`."""
    found = [t for t in publish_numbers.TARGETS if t[0] == rel and t[2] == key]
    if not found:
        raise AssertionError("no target for %s in %s" % (key, rel))
    return found[0]


def production_targets():
    """The docs/EXPERIMENT_C.md targets on the five production keys."""
    return [t for t in publish_numbers.TARGETS
            if t[0] == EXPERIMENT_C and t[2] in PRODUCTION_KEYS]


def label(t):
    """A target, named in a check: its key and the start of its pattern."""
    return "%s (%s...)" % (t[2], t[1][:28])


def entries(stale, t):
    """scan()'s stale entries, (file, pattern, found, expected), for target t."""
    return [s for s in stale or [] if (s[0], s[1]) == (t[0], t[1])]


def not_measured(got, key):
    """Exactly one entry, whose expected value says the figure is not measured and names its
    key: a string, so never None, and never a number."""
    return (len(got) == 1 and isinstance(got[0][3], str) and "not measured" in got[0][3]
            and re.search(r"\b%s\b" % re.escape(key), got[0][3]) is not None)


def published(tmp, t):
    """What the copy says in target t's capture group; None where its pattern no longer
    matches."""
    with io.open(os.path.join(tmp, t[0]), encoding="utf-8") as f:
        m = re.search(t[1], f.read())
    return m.group(1) if m else None


def edit(tmp, rel, change):
    """Rewrite one file of the copy as change(text)."""
    path = os.path.join(tmp, rel)
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(change(text))


def stale_figure(tmp):
    """Make one figure stale in the copy, of the kind --write rewrites: README.md's
    false-positive rate, one point above the measurement. Returns the target and the
    measured value."""
    t = target("README.md", "fp_pct")
    right = publish_numbers.figures()["fp_pct"]

    def change(text):
        m = re.search(t[1], text)
        return text[:m.start(1)] + "%.1f" % (float(right) + 1) + text[m.end(1):]
    edit(tmp, t[0], change)
    return t, right


def reword(t, text):
    """Target t's sentence with a word put before its number, so that its pattern no longer
    matches and --write has nothing to rewrite."""
    m = re.search(t[1], text)
    return text[:m.start(1)] + "about " + text[m.start(1):]


def set_production_row(tmp, row):
    """docs/SCORECARD.md's production row in the copy, replaced by `row`, as judge() does."""
    def change(text):
        lines = text.splitlines()
        at = [i for i, line in enumerate(lines) if line.startswith(PRODUCTION_ROW)]
        if len(at) != 1:
            raise AssertionError("docs/SCORECARD.md has %d production rows, not 1" % len(at))
        lines[at[0]] = row
        return "\n".join(lines) + "\n"
    edit(tmp, "docs/SCORECARD.md", change)


def agrees_with_check_mode(status):
    """The rule: --write returns 0 exactly when check mode, on the files it left, returns 0."""
    after, out = run_main()
    check("--write returns 0 exactly when check mode on the files it left returns 0",
          isinstance(status, int) and isinstance(after, int) and (status == 0) == (after == 0),
          "--write returned %r, check mode %r: %s" % (status, after, tail(out)))


@recorded
def check_the_current_tree_passes_in_both_modes():
    print("\n[check mode and --write] the current tree, in a copy of every file main() reads")

    def run(tmp):
        def contents():
            out = {}
            for rel in files_main_reads():
                if os.path.exists(os.path.join(tmp, rel)):
                    with io.open(os.path.join(tmp, rel), "rb") as f:
                        out[rel] = f.read()
            return out
        before = contents()
        for mode, argv in (("check mode", ()), ("--write", ("--write",))):
            status, out = run_main(*argv)
            check("%s returns 0 and prints `Everything published matches the benchmark.`" % mode,
                  status == 0 and "Everything published matches the benchmark." in out,
                  "returned %r: %s" % (status, tail(out)))
        after = contents()
        check("--write leaves every file as it was, byte for byte",
              after == before, ", ".join(sorted(r for r in before if after.get(r) != before[r])))
    in_a_copy(run)


@recorded
def check_a_missing_production_artifact_is_reported():
    print("\n[not measured] bench/production/verdicts.json absent where the module reads it")
    targets = production_targets()
    check("docs/EXPERIMENT_C.md has 7 targets on the 5 production keys",
          len(targets) == 7 and set(t[2] for t in targets) == set(PRODUCTION_KEYS),
          "%d targets on %s" % (len(targets), sorted(set(t[2] for t in targets))))
    keys = set(publish_numbers.figures())

    def run(tmp):
        dropped = keys - set(publish_numbers.figures())
        check("figures() leaves out exactly the 5 production keys, with no placeholder",
              dropped == set(PRODUCTION_KEYS), "left out %s" % sorted(dropped))
        stale, err = scan_entries(write=False)
        check("scan(write=False) returns without raising", err is None, err)
        for t in targets:
            check("one entry for %s, expected `not measured`, naming the key" % label(t),
                  not_measured(entries(stale, t), t[2]), err or "got %r" % entries(stale, t))
        # The two docs/SCORECARD.md production targets use ABSENT and a reason, not a missing
        # key, and keep the rule they have today: the row bench/scorecard.py writes for a
        # missing artifact passes, and a figure row fails on the form that must be absent.
        why = scorecard.production_verdicts()[2]
        rows = [t for t in publish_numbers.TARGETS if t[0] == "docs/SCORECARD.md"
                and t[2] in ("scorecard_production_pct", "scorecard_production_why")]
        set_production_row(tmp, not_measured_row(why))
        stale, err = scan_entries(write=False)
        got = [s for t in rows for s in entries(stale, t)]
        check("docs/SCORECARD.md `not measured (%s)` is accepted, as today" % why,
              len(rows) == 2 and err is None and not got, err or "got %r" % got)
        set_production_row(tmp, figure_row(verdicts(20, 200)))
        stale, err = scan_entries(write=False)
        got = {t[2]: [s[3] for s in entries(stale, t)] for t in rows}
        check("docs/SCORECARD.md with a figure row: expected absent, and the reason, as today",
              err is None and got == {"scorecard_production_pct": [publish_numbers.ABSENT],
                                      "scorecard_production_why": [why]},
              err or "got %r" % got)
    in_a_copy(run, artifact=False)


@recorded
def check_any_missing_key_is_reported():
    key = "power_pooled_oos_pct"
    print("\n[not measured] figures() wrapped in memory to drop %s" % key)
    targets = [t for t in publish_numbers.TARGETS if t[2] == key]
    check("a target uses %s" % key, bool(targets), "none: pick a key that a target uses")
    real = publish_numbers.figures

    def run(tmp):
        before = [published(tmp, t) for t in targets]
        stale, err = scan_entries(write=False)
        check("scan(write=False) returns without raising", err is None, err)
        for t in targets:
            check("one entry for %s in %s, expected `not measured`, naming the key"
                  % (label(t), t[0]),
                  not_measured(entries(stale, t), key), err or "got %r" % entries(stale, t))
        stale, err = scan_entries(write=True)
        after = [published(tmp, t) for t in targets]
        check("scan(write=True) returns without raising and leaves the text of each as it was",
              err is None and None not in before and after == before,
              err or "the text said %r and says %r" % (before, after))

    publish_numbers.figures = lambda: {k: v for k, v in real().items() if k != key}
    try:
        in_a_copy(run)
    finally:
        publish_numbers.figures = real


@recorded
def check_check_mode_names_what_is_not_measured():
    print("\n[not measured] check mode, with bench/production/verdicts.json absent")

    def run(tmp):
        status, out = run_main()
        check("check mode returns 1, with no traceback",
              status == 1 and "Traceback" not in out, "returned %r: %s" % (status, tail(out)))
        for key in PRODUCTION_KEYS:
            n = len([t for t in production_targets() if t[2] == key])
            named = [line for line in out.splitlines() if EXPERIMENT_C in line
                     and "not measured" in line and re.search(r"\b%s\b" % key, line)]
            check("the output names %s and %s for each of its %d target(s)"
                  % (EXPERIMENT_C, key, n), n > 0 and len(named) >= n,
                  "%d line(s) name them" % len(named))
    in_a_copy(run, artifact=False)


@recorded
def check_write_returns_0_when_it_fixed_everything():
    print("\n[--write] one stale figure, which --write can rewrite")

    def run(tmp):
        t, right = stale_figure(tmp)
        status, out = run_main("--write")
        check("--write returns 0", status == 0, "returned %r: %s" % (status, tail(out)))
        check("--write rewrote %s's figure to the measured %s" % (t[0], right),
              published(tmp, t) == right, "the text says %r" % published(tmp, t))
        after, out = run_main()
        check("check mode afterwards returns 0", after == 0,
              "returned %r: %s" % (after, tail(out)))
    in_a_copy(run)


@recorded
def check_write_fails_on_a_sentence_it_cannot_find():
    print("\n[--write] that figure, plus a guarded sentence reworded so its pattern no longer "
          "matches")

    def run(tmp):
        t, right = stale_figure(tmp)
        s = target("README.md", "adversarial_n")
        edit(tmp, s[0], lambda text: reword(s, text))
        check("the reworded sentence no longer matches its pattern", published(tmp, s) is None,
              "it still reads %r" % published(tmp, s))
        status, out = run_main("--write")
        check("--write still rewrites the figure", published(tmp, t) == right,
              "the text says %r" % published(tmp, t))
        check("--write returns non-zero", isinstance(status, int) and status != 0,
              "returned %r: %s" % (status, tail(out)))
        named = [line for line in out.splitlines()
                 if s[0] in line and "pattern not found" in line]
        check("--write names the entry it could not fix", bool(named), tail(out))
        agrees_with_check_mode(status)
    in_a_copy(run)


@recorded
def check_write_fails_on_an_unclaimed_percentage():
    print("\n[--write] that figure, plus a new unclaimed percentage in a live-claim file")
    rel = "README.md"

    def run(tmp):
        t, right = stale_figure(tmp)
        with io.open(os.path.join(tmp, rel), encoding="utf-8") as f:
            original = f.read()
        pct = next(v for v in ("97.3", "96.4", "95.7", "94.6") if v not in original)
        # Three line breaks first: the scan reads two lines either side of a figure, and the
        # new line must not borrow a citation or a vendor's name from its neighbours.
        edit(tmp, rel, lambda text: text + "\n\n\nAn unguarded figure: %s%% of nothing.\n" % pct)
        loose = [(r, p) for r, p, _ in publish_numbers.unclaimed_percentages()]
        check("%s%% is unclaimed in %s before --write" % (pct, rel), (rel, pct) in loose,
              "unclaimed: %r" % loose)
        status, out = run_main("--write")
        check("--write still rewrites the figure", published(tmp, t) == right,
              "the text says %r" % published(tmp, t))
        check("--write returns non-zero", isinstance(status, int) and status != 0,
              "returned %r: %s" % (status, tail(out)))
        listed = [line for line in out.splitlines() if rel in line and pct + "%" in line]
        check("--write lists the unclaimed %s%%" % pct, bool(listed), tail(out))
        agrees_with_check_mode(status)
    in_a_copy(run)


@recorded
def check_write_fails_with_no_production_artifact():
    print("\n[--write] with bench/production/verdicts.json absent")
    targets = production_targets()

    def run(tmp):
        before = [published(tmp, t) for t in targets]
        status, out = run_main("--write")
        check("--write returns non-zero", isinstance(status, int) and status != 0,
              "returned %r: %s" % (status, tail(out)))
        for t, was in zip(targets, before):
            now = published(tmp, t)
            check("--write, run to the end, leaves the text at %s as it was" % label(t),
                  isinstance(status, int) and was is not None and now == was,
                  "returned %r; the text said %r and says %r" % (status, was, now))
        agrees_with_check_mode(status)
    in_a_copy(run, artifact=False)


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
