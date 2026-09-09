"""Every owner-power recall figure in the source must match the file it was measured into.

WHY THIS FILE EXISTS

`src/risk.py` told readers the bytecode scan "finds 41 of 133, or 31%. Per power it is worse
-- 5% for a mutable tax, 20% for a blacklist, 25% for a pause switch, 38% for mint." Those
numbers came from a run over 120 contracts. The committed instrument had been measuring 559
for nine days and printing 37% / 26% / 52% / 8% -- a different figure for every power, one of
them off by a factor of four in the flattering direction.

The launch post was corrected. `src/risk.py` was not, in three places, including the comment
attached to the `scan_is_incomplete` field whose entire job is to tell a caller how blind
the scan is. That is this project's most expensive habit written down twice: correcting a
claim where you noticed it is not correcting the claim, and a number that is written rather
than generated will drift.

Two reasons no existing guard caught it:

1. `src/risk.py` is not in `LIVE_CLAIM_FILES`, so `bench/publish_numbers.py` never scanned
   it. That is defensible on its own -- the file holds twenty-four percentages, most of them
   thresholds in code -- but it was never *stated*, and silence is how five surfaces went
   unscanned before W21.

2. W21's own coverage test, `test_every_outward_surface_is_scanned`, defines a surface as a
   tracked `.md` or `.html` file. Every `.py` file in the repository is invisible to it. The
   test written to answer "is every surface covered by something" could not see the file
   that computes the thing being claimed. `test_a_source_file_carrying_claims_is_covered`
   below is the narrow fix; the general one is that this test now exists and is named in the
   docstring it guards, so the pointer and the check are the same edit.

Run: python tests/test_owner_power_recall.py
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import risk  # noqa: E402

MEASURED = os.path.join(ROOT, "bench", "owner_powers.json")
RISK = os.path.join(ROOT, "src", "risk.py")

# Both files, because reading one was not enough. This guard was written to catch a stale
# recall figure in src/risk.py and it did -- and within the hour the identical error, mint
# named as the worst power when pause is lower, was written into tests/test_owner_powers.py,
# one file over, where nothing looked. An external audit found it.
CLAIM_FILES = (
    os.path.join("src", "risk.py"),
    os.path.join("tests", "test_owner_powers.py"),
)

# A recall claim spelled out in words carries no digits, so a guard that looks for
# percentages cannot see it. Both strings the product EMITS TO A CALLER said "about a third"
# -- 41.4% arithmetic, still there after the measurement moved to 62.5%, thirty lines below a
# docstring that said 62.5%. So a fraction word is allowed only on a line that also carries
# the figure it is approximating.
# The quantity AND its object, because the first version matched ordinals. It fired on "a
# fifth power" and would have fired on "a third pinned constant" -- both in src/risk.py, both
# counting things rather than claiming a proportion. What makes a recall claim is the "of the
# powers" / "of them" / "of the ones that exist" that follows.
_FRACTION_WORDS = re.compile(
    r"(?:about|roughly|around|only|barely|nearly|almost)?\s*"
    r"(?:a\s+(?:third|quarter|half)|most|two\s+thirds|three\s+quarters)"
    r"\s+of\s+(?:the|them|what|those|its|these)", re.I)
_POWER_CONTEXT = re.compile(r"power|selector|scan\b|recall", re.I)

# A line that RECORDS a corrected phrase is not the phrase. The same distinction
# publish_numbers.RETRACTED_CLAIMS makes, and for the same reason: this project's comments
# quote the wording they replaced, on purpose, because the incident is the part that is
# remembered. Three of these checks failed on their first run against nothing but their own
# changelog.
_RECORD_MARKER = re.compile(
    r"used to|still said|no longer|was wrong|has never|instead of|survived|walked straight"
    r"|drift|superseded|would have|fired on|matched|W18 added|said four|replaced", re.I)

_PASSED = 0
_FAILURES = []
_UNCHECKED = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def unchecked(name, why):
    _UNCHECKED.append((name, why))
    print("  ----  %s  (not checked here: %s)" % (name, why))


def _measured():
    with io.open(MEASURED, encoding="utf-8") as f:
        return json.load(f)


def test_the_measurement_file_exists_and_is_dated():
    print("\n[recall] the generated source exists")
    if not os.path.exists(MEASURED):
        check("bench/owner_powers.json exists", False,
              "run: python bench/selector_mine.py --write")
        return
    d = _measured()
    check("bench/owner_powers.json exists", True)
    check("it is dated", bool(d.get("measured")), str(d.get("measured")))
    check("it names the command that regenerates it",
          "selector_mine.py" in (d.get("generated_by") or ""), str(d.get("generated_by")))
    # The trading gate has no oracle field. Its recall must be null, never 0 -- writing a
    # zero into the artifact other files quote from is how an unobserved dimension becomes
    # an observed absence with a citation.
    gate = (d.get("powers") or {}).get("can halt trading") or {}
    check("the trading gate's recall is null, not zero",
          "mined_pct" in gate and gate["mined_pct"] is None, repr(gate.get("mined_pct")))


def test_the_pinned_list_matches_what_was_measured():
    """The table describes a list. If the list changed, the table is about something else."""
    print("\n[recall] the pinned list is the one that was measured")
    if not os.path.exists(MEASURED):
        unchecked("the pinned list matches", "no measurement file")
        return
    powers = (_measured().get("powers") or {})
    check("every measured power is pinned in the engine",
          set(powers) == set(risk._OWNER_POWERS),
          "difference: %s" % sorted(set(powers) ^ set(risk._OWNER_POWERS)))
    for power, row in sorted(powers.items()):
        pinned = len(risk._OWNER_POWERS.get(power) or ())
        check("%s: %d selectors pinned, %s measured"
              % (power, pinned, row.get("selectors_pinned")),
              pinned == row.get("selectors_pinned"),
              "regenerate with: python bench/selector_mine.py --write")


def test_every_recall_figure_in_the_source_matches():
    """The table and the prose in src/risk.py, against the file they were measured into.

    Both, not one. The table was generated and the prose was typed, which is exactly the
    pairing that drifts: the generated half gets regenerated and the sentence beside it
    keeps the old number, and the sentence is the part a reader believes.
    """
    print("\n[recall] every figure quoted in src/risk.py")
    if not os.path.exists(MEASURED):
        unchecked("figures in src/risk.py match", "no measurement file")
        return
    d = _measured()
    powers = d.get("powers") or {}
    by_flag = {row.get("oracle_flag"): row for row in powers.values()
               if row.get("oracle_flag")}
    pooled = d.get("pooled") or {}
    src = io.open(RISK, encoding="utf-8").read()

    # The generated table: "#   slippage_modifiable  38   7.9%   89.5%"
    rows = re.findall(r"^#\s+([a-z_]+)\s+(\d+)\s+([\d.]+)%\s+([\d.]+)%", src, re.M)
    check("the recall table was found in src/risk.py", len(rows) >= 5,
          "found %d rows" % len(rows))
    for flag, n, before, after in rows:
        if flag == "pooled":
            want = pooled
            label = "pooled"
        elif flag in by_flag:
            want = by_flag[flag]
            label = flag
        else:
            check("table row names a measured flag: %s" % flag, False,
                  "not in owner_powers.json")
            continue
        got_n = want.get("n") if flag == "pooled" else want.get("oracle_says")
        check("%s: n=%s" % (label, n), int(n) == got_n, "measured %s" % got_n)
        check("%s: before=%s%%" % (label, before),
              before == want.get("shipped_pct"), "measured %s" % want.get("shipped_pct"))
        check("%s: after=%s%%" % (label, after),
              after == want.get("mined_pct"), "measured %s" % want.get("mined_pct"))

    # The prose. Each of these is a sentence a reader takes as the current claim.
    prose = [
        (r"finds ([\d.]+)% of the powers", pooled.get("mined_pct"), "pooled, after"),
        (r"up from ([\d.]+)% before W18", pooled.get("shipped_pct"), "pooled, before"),
        (r"went from ([\d.]+)% to [\d.]+%",
         (by_flag.get("slippage_modifiable") or {}).get("shipped_pct"), "tax, before"),
        (r"went from [\d.]+% to ([\d.]+)%",
         (by_flag.get("slippage_modifiable") or {}).get("mined_pct"), "tax, after"),
        (r"mint, at ([\d.]+)%",
         (by_flag.get("is_mintable") or {}).get("mined_pct"), "mint, after"),
        (r"still true at ([\d.]+)% pooled recall", pooled.get("mined_pct"),
         "the payload comment"),
    ]
    for pattern, want, label in prose:
        m = re.search(pattern, src, re.I)
        if not m:
            check("prose figure present: %s" % label, False,
                  "no line in src/risk.py matches %s" % pattern)
            continue
        check("prose %s says %s%%" % (label, m.group(1)), m.group(1) == want,
              "measured %s" % want)

    # Every OTHER file that quotes a per-power recall figure, checked against the same
    # source. Any percentage sitting beside the word "scan" or "recall" in one of these has
    # to be a figure the measurement actually produced -- which is how the mint-versus-pause
    # error in tests/test_owner_powers.py would have been caught an hour earlier.
    legit = set()
    for row in list(by_flag.values()) + [pooled]:
        for k in ("shipped_pct", "mined_pct", "pausable_pause_only_pct",
                  "pausable_with_gates_pct"):
            if row.get(k):
                legit.add(row[k])
    for rel in CLAIM_FILES[1:]:
        lines = io.open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines()
        bad = []
        for i, line in enumerate(lines):
            if not re.search(r"\b(?:scan|recall)\b", line, re.I):
                continue
            window = " ".join(lines[max(0, i - 1):i + 3])
            for m in re.finditer(r"(\d+(?:\.\d+)?)%", window):
                if m.group(1) not in legit:
                    bad.append("%s:%d  %s%%" % (rel, i + 1, m.group(1)))
        check("%s: every recall percentage is one the measurement produced" % rel,
              not bad, " | ".join(sorted(set(bad))))

    # The docstring calls one figure the lowest in the table. Which flag that is may move
    # on the next re-measure, so the check is that whatever IS lowest is the figure quoted
    # -- not that a particular power keeps the title. Written this way after the first run
    # of this test caught the docstring naming mint at 55.1% as the worst while pause sat
    # at 52.6%, which is the error this file exists to catch, made in the same edit.
    scored = [r for r in by_flag.values() if r.get("mined_pct")]
    worst = min(scored, key=lambda r: float(r["mined_pct"]))
    m = re.search(r"lowest figure in the table is \w+ at ([\d.]+)%", src)
    check("the docstring quotes the measured lowest figure",
          bool(m) and m.group(1) == worst["mined_pct"],
          "lowest is %s at %s%%, docstring says %s"
          % (worst.get("oracle_flag"), worst.get("mined_pct"),
             m.group(1) if m else "nothing"))


def test_the_pinned_literal_matches_the_measurement():
    """`_SCAN_RECALL_PCT` is the figure the product says out loud. It must not be a guess.

    The Worker cannot read bench/owner_powers.json, so the number a caller is told has to be
    a literal in src/risk.py. That is fine as long as something fails when it stops being
    true, which is this.
    """
    print("\n[recall] the literal the product emits to a caller")
    if not os.path.exists(MEASURED):
        unchecked("the pinned literal matches", "no measurement file")
        return
    want = (_measured().get("pooled") or {}).get("mined_pct")
    check("_SCAN_RECALL_PCT is %s" % want, risk._SCAN_RECALL_PCT == want,
          "pinned %s, measured %s" % (risk._SCAN_RECALL_PCT, want))

    # And it has to reach the caller, not merely exist. Both emitted strings are checked by
    # driving the real functions rather than by grepping for the constant.
    rec = risk._low_recommendation(
        {"owner_powers": {"powers": [], "found_none": True, "is_proxy": False}})
    check("the low recommendation quotes it", "%s%%" % want in rec, rec[-160:])
    signals, evidence = [], {}
    risk._owner_power_signal(
        {"powers": [], "found_none": True, "is_proxy": False}, signals, evidence)
    text = " ".join(sg.get("message", "") for sg in signals)
    check("the found_none signal quotes it", "%s%%" % want in text, text[:200])


def test_the_caller_facing_power_list_is_generated():
    """Every enumeration of the powers must come from the list, not from memory.

    Three caller-facing strings spelled out "pause, blacklist, mutable-tax and mint". W18
    added a fifth power and all three still said four. A fourth enumeration listed "removable
    liquidity", which this scan has never looked for at all -- a hand-typed list of what the
    code contains, wrong on both directions at once.
    """
    print("\n[recall] the power enumeration comes from the list")
    listed = risk._power_list()
    for power in risk._OWNER_POWERS:
        short = power[4:] if power.startswith("can ") else power
        check("the caller-facing list names %s" % short, short in listed, listed)

    lines = io.open(RISK, encoding="utf-8").read().splitlines()
    for stale in ("pause, blacklist, mutable-tax and mint", "removable liquidity"):
        live = []
        for i, line in enumerate(lines):
            if stale not in line:
                continue
            window = " ".join(lines[max(0, i - 3):i + 4])
            if _RECORD_MARKER.search(window):
                continue          # the comment that records having removed it
            live.append("risk.py:%d" % (i + 1))
        check("no hand-typed enumeration survives: %r" % stale, not live,
              "use _power_list() instead -- at %s" % ", ".join(live))


def test_no_recall_claim_is_spelled_out_in_words():
    """A fraction in words is a claim a percentage-shaped guard cannot read."""
    print("\n[recall] no claim hides from the guard by avoiding digits")
    for rel in CLAIM_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            unchecked("%s scanned for worded claims" % rel, "file missing")
            continue
        bad = []
        lines = io.open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            if not _FRACTION_WORDS.search(line):
                continue
            window = " ".join(lines[max(0, i - 2):i + 3])
            if not _POWER_CONTEXT.search(window):
                continue                      # a fraction about something else entirely
            if re.search(r"\d+(?:\.\d+)?%", line):
                continue                      # accompanied by the figure it approximates
            if _RECORD_MARKER.search(window):
                continue                      # a record of the phrasing, not a use of it
            bad.append("%s:%d  %s" % (rel, i + 1, line.strip()[:80]))
        check("%s: no worded recall claim without its figure" % rel, not bad,
              " | ".join(bad))


def test_a_source_file_carrying_claims_is_covered():
    """W21's coverage test cannot see a `.py` file. This is the half of that hole I can close.

    `test_every_outward_surface_is_scanned` filters on `.md` and `.html`, so no Python file
    can ever be reported as an unscanned surface -- which is why three copies of a
    superseded recall figure sat in `src/risk.py` while every guard read green.

    Closing it in general means either adding `src/risk.py` to `LIVE_CLAIM_FILES`, which
    needs about twenty exemptions for thresholds that are not claims, or naming the claims
    that matter and checking them. This does the second for the recall figures and STATES
    that it does not do the first, so the remaining gap is written down rather than implied.
    """
    print("\n[recall] the surface this file covers, and what it does not")
    import publish_numbers as pn

    check("src/risk.py is still outside LIVE_CLAIM_FILES, as this test assumes",
          "src/risk.py" not in pn.LIVE_CLAIM_FILES,
          "it is in the list now -- this test's premise changed, re-read it")
    unchecked("every percentage in src/risk.py",
              "24 of them are code thresholds and dated one-off observations; only the "
              "owner-power recall figures are checked here, and W21's coverage test still "
              "cannot see any .py file at all")


def main():
    print("=" * 70)
    print("Owner-power recall figures match bench/owner_powers.json")
    print("=" * 70)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 70)
    print("%d passed, %d failed, %d not checked here"
          % (_PASSED, len(_FAILURES), len(_UNCHECKED)))
    for name, why in _UNCHECKED:
        print("  ----  %s  (%s)" % (name, why))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
