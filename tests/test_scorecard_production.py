"""test_scorecard_production.py -- the two score items only production can answer.

On 2026-09-14 every test was green while the live service served 313 calls past a rate
limiter that never limited, and the benchmark's unknown rate (cached upstreams) was half
what a live hour measured. The scorecard gained two items that read committed artifacts
written by .github/workflows/production.yml. Their rules were fixed before any artifact
existed, and these checks pin them so a first unwelcome reading cannot quietly move them:

- absent, stale (more than 7 days older than the newest snapshot) or thin (fewer than 100
  answers) is "not measured", never a score;
- a flood that drew no 429 scores nothing for the limiter, and a batch that was served
  scores nothing for the cap;
- production unknown uses the benchmark's own bands.

Run:  python tests/test_scorecard_production.py
"""

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "bench"))

import scorecard  # noqa: E402

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


def _items_with(artifacts, newest="2026-09-20"):
    """Score with a fake production directory and a fake newest snapshot date."""
    tmp = tempfile.mkdtemp()
    try:
        for name, data in artifacts.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                json.dump(data, f)
        saved = (scorecard.PRODUCTION, scorecard.newest_snapshot_date, scorecard.tests_pass)
        scorecard.PRODUCTION = tmp
        scorecard.newest_snapshot_date = lambda: newest
        scorecard.tests_pass = lambda: (True, ["stubbed"])
        try:
            items, _ = scorecard.score()
        finally:
            scorecard.PRODUCTION, scorecard.newest_snapshot_date, scorecard.tests_pass = saved
        return {name: (weight, got, note) for _dim, name, weight, got, note in items}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


UNKNOWN = "unknown rate (production, served answers)"
GUARDS = "production guards observed live"


def verdicts(unknown, total, end="2026-09-19T06:40:00Z"):
    rest = total - unknown
    return {"window_start": "2026-09-12T06:40:00Z", "window_end": end,
            "counts": {"low": rest, "medium": 0, "high": 0, "unknown": unknown}}


def guards(calls_until_429=64, status=400, at="2026-09-19T06:40:00Z"):
    return {"probed_at": at, "flood": {"ran": True, "calls": calls_until_429 or 75,
                                       "calls_until_429": calls_until_429},
            "batch_cap": {"ran": True, "messages": 11, "http_status": status}}


def test_absent_stale_and_thin_are_not_measured():
    print("\n[score] no artifact, an old one, or too few answers: not measured")
    it = _items_with({})
    check("no verdicts file is not measured", it[UNKNOWN][1] is None, str(it[UNKNOWN]))
    check("no guards file is not measured", it[GUARDS][1] is None, str(it[GUARDS]))
    it = _items_with({"verdicts.json": verdicts(10, 500, end="2026-09-01T00:00:00Z"),
                      "guards-probe.json": guards(at="2026-09-01T00:00:00Z")})
    check("a verdict count older than 7 days is not measured", it[UNKNOWN][1] is None,
          str(it[UNKNOWN]))
    check("a guard probe older than 7 days is not measured", it[GUARDS][1] is None,
          str(it[GUARDS]))
    it = _items_with({"verdicts.json": verdicts(0, 99)})
    check("99 answers is not a production figure", it[UNKNOWN][1] is None, str(it[UNKNOWN]))


def test_production_unknown_uses_the_benchmark_bands():
    print("\n[score] production unknown on the benchmark's bands")
    for unknown, total, want in ((0, 200, 5.0), (19, 200, 4.0), (50, 200, 2.0), (60, 200, 1.0)):
        it = _items_with({"verdicts.json": verdicts(unknown, total)})
        check("%d of %d unknown scores %.1f" % (unknown, total, want),
              it[UNKNOWN][1] == want, str(it[UNKNOWN]))


def test_a_guard_seen_failing_scores_nothing():
    print("\n[score] a limiter that never limited, or a cap that served, earns nothing")
    it = _items_with({"guards-probe.json": guards()})
    check("both guards seen working score 5", it[GUARDS][1] == 5.0, str(it[GUARDS]))
    it = _items_with({"guards-probe.json": guards(calls_until_429=None)})
    check("75 calls with no 429 leaves only the cap", it[GUARDS][1] == 2.5, str(it[GUARDS]))
    it = _items_with({"guards-probe.json": guards(calls_until_429=None, status=200)})
    check("both seen failing score 0, measured", it[GUARDS][1] == 0.0, str(it[GUARDS]))


def test_an_open_dimension_is_stated_as_open():
    """The gaps have to be said out loud, not merely left unclaimed.

    The over-claiming half of this test is gone: it was a list of seven exact sentences,
    it could not see README.md:92 saying "holder concentration" in different words, and it
    had no entry at all for the EVM half of that dimension. It is replaced by a rule in
    tests/test_advertised_coverage.py -- every capability noun maps to a RISK_VECTORS row,
    and an unqualified one claims every advertised chain.

    What a rule cannot do is notice silence. Deleting a false claim and saying nothing is
    also a way to mislead, and it is the cheaper way out of a failing guard, so the
    disclosures stay pinned here by hand.
    """
    print("\n[coverage] the open gaps are stated where a reader looks for them")
    for rel, needle in (("src/landing.html", "does not test sellability on\n  Solana"),
                        ("src/entry.py", "Does not test sellability on\nSolana"),
                        ("docs/SCORECARD.md",
                         "| sellability simulation | \u2705 | \u2705 | \u2705 | \u2b1c")):
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        check("%s says the Solana sell test is an open gap" % rel, needle in text, needle)

    # Solana was named on both pages while the four EVM chains the simulator never reached
    # were not, which is the same omission the scorecard row made: a gap disclosed for the
    # chain someone happened to be thinking about reads as a complete list of the gaps.
    for rel in ("src/landing.html", "src/entry.py"):
        text = " ".join(open(os.path.join(ROOT, rel), encoding="utf-8").read().split())
        for chain in ("polygon", "arbitrum", "optimism", "avalanche"):
            check("%s names %s among the chains with no sell test" % (rel, chain),
                  chain in text.lower(), "the sell simulator does not reach it either")


def main():
    print("=" * 68)
    print("Scorecard: what only production can answer")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
