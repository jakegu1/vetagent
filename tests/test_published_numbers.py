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
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))

import publish_numbers  # noqa: E402



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

    if not stale and not loose and not scorecard_stale:
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
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
