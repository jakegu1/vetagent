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

    vals, stale, _ = publish_numbers.scan(write=False)
    print("benchmark says: n=%s, false positives %s%% on %s healthy tokens, "
          "unknown %s%%, dead %s"
          % (vals["n"], vals["fp_pct"], vals["healthy_n"], vals["unknown_pct"],
             vals["dead_n"]))

    if not stale:
        print("\nevery published figure matches")
        print("PASS")
        return 0

    print("\n%d published figure(s) disagree:\n" % len(stale))
    for rel, pattern, found, want in stale:
        print("  %-18s published %-8s measured %-8s" % (rel, found, want))
        print("      %s" % pattern[:70])
    print("\nRun `python bench/publish_numbers.py --write`, then redeploy.")
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
