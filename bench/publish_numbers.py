"""publish_numbers.py -- write the measured accuracy figures into what users read.

Usage:
    python bench/publish_numbers.py --check    # go red if anything is stale
    python bench/publish_numbers.py --write    # rewrite them from bench/results.json

Why this exists
---------------
The product's whole pitch is that it publishes its own accuracy, and the GEO thesis
underneath it is that a model will cite numbers it can check. An external audit found
those numbers three generations out of date in every place a reader meets them: the
README, the landing page and `/llms.txt` all said 199 tokens, an 11.3% false-positive
rate, 21.0% unknown and "recall not measurable", while `bench/results.md` said 558, 3.5%,
17.2% and a measured recall.

Publishing a checkable number is only worth something if it survives being checked. So
the figures are generated from `results.json` rather than typed, and `--check` runs in the
test suite: the moment the benchmark moves, the copy that has not been regenerated goes
red rather than quietly becoming a false claim.
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "results.json")

# Each entry: file, a regex with one capture group, and the key whose formatted value
# belongs in that group. The regex has to be specific enough that it cannot match prose
# that happens to contain a number.
TARGETS = [
    # docs/SCORECARD.md is generated too, and it went stale: it carried 4.3% while
    # README carried 3.7%, because a benchmark re-run regenerated one and not the other.
    # Two different values for the headline metric of a product whose whole claim is that
    # its numbers can be checked is the worst possible place to have a drift, and an
    # external audit found it before any of our own guards did. Adding it here means the
    # guard fails instead of a reader noticing.
    ("docs/SCORECARD.md", r"false positive rate \(healthy rated high\) \| [\d.]+ \| 10 \| ([\d.]+)%",
     "fp_pct"),
    ("docs/SCORECARD.md", r"unknown rate \| [\d.]+ \| 10 \| ([\d.]+)%", "unknown_pct"),
    ("README.md", r"a \*\*([\d.]+)% false positive rate\*\*", "fp_pct"),
    ("README.md", r"false positive rate\*\* on (\d+) healthy tokens", "healthy_n"),
    ("README.md", r"\*\*([\d.]+)% unknown rate\*\*", "unknown_pct"),
    ("src/landing.html", r"Measured on (\d+) tokens:", "n"),
    ("src/landing.html", r"were flagged high\. (\d+) of \d+ confirmed-dead", "dead_not_low_n"),
    ("src/landing.html", r"were flagged high\. \d+ of (\d+) confirmed-dead", "dead_n"),
    ("src/landing.html", r"tokens: ([\d.]+)% of healthy tokens were flagged high", "fp_pct"),
    ("src/landing.html", r"\(false positives\), ([\d.]+)% of answers were unknown", "unknown_pct"),
    ("src/landing.html", r"Measured over (\d+) tokens,", "n"),
    ("src/landing.html", r'<td>Healthy tokens flagged high</td><td class="num high">([\d.]+)%',
     "fp_pct"),
    ("src/landing.html",
     r'<td>Answers returned as <code>unknown</code></td><td class="num unk">([\d.]+)%',
     "unknown_pct"),
    # The audit brief quotes measured figures too. Section 1 and 3 were refreshed by hand
    # in R11 and section 7 was not, so the document whose entire job is to direct an
    # auditor's attention pointed at numbers that had moved -- and it was an auditor who
    # noticed. Bringing it under the same guard as everything else is the only version of
    # this fix that survives the next re-measurement.
    ("README.md", r"\*\*([\d.]+)%\*\* of legitimate centralised assets flagged high",
     "centralized_high_pct"),
    ("src/landing.html",
     r"<td>Centralised assets \(USDT, WBTC\u2026\) flagged high</td><td class=\"num low\">([\d.]+)%",
     "centralized_high_pct"),
    ("src/landing.html", r"<td>Dead tokens not rated low</td><td class=\"num low\">([\d.]+)%",
     "dead_not_low_pct"),
    ("src/landing.html", r"([\d.]+)% of legitimate centralised assets", "centralized_high_pct"),
    ("src/landing.html", r"(\d+) of \d+ confirmed-dead tokens were not rated low",
     "dead_not_low_n"),
    ("src/entry.py", r"Legitimate centralised assets flagged high \.+ ([\d.]+)%",
     "centralized_high_pct"),
    ("src/entry.py", r"Dead tokens not rated low \.+ ([\d.]+)%", "dead_not_low_pct"),
    # The "N of M" pairs, which drifted furthest of all: "95% (19 of 20)" was sitting four
    # lines below "n=576". A ratio is two numbers and both of them move.
    ("src/landing.html", r"(\d+) of \d+\. Read the caveat below", "dead_not_low_n"),
    ("src/landing.html", r"\d+ of (\d+)\. Read the caveat below", "dead_n"),
    ("src/entry.py", r"Dead tokens not rated low \.+ [\d.]+% \((\d+) of \d+\)",
     "dead_not_low_n"),
    ("src/entry.py", r"Dead tokens not rated low \.+ [\d.]+% \(\d+ of (\d+)\)", "dead_n"),
    ("README.md", r"Sampling has turned up (\d+) dead tokens in \d+", "dead_n"),
    ("README.md", r"Sampling has turned up \d+ dead tokens in (\d+)", "n"),
    # docs/EXPERIMENT_C.md is the text that goes to Hacker News and Reddit. A number
    # that drifts there is worse than one that drifts in the README: it is quoted in
    # public, by us, to an audience invited specifically to check it.
    ("docs/EXPERIMENT_C.md", r"\| \*\*([\d.]+)%\*\* \(7 of \d+\) \|", "fp_pct"),
    ("docs/EXPERIMENT_C.md", r"\| \*\*([\d.]+)%\*\* \(88 of \d+\) \|", "unknown_pct"),
    ("docs/EXPERIMENT_C.md", r"\| \*\*([\d.]+)%\*\* \(41 of \d+\) \|",
     "centralized_high_pct"),
    ("docs/EXPERIMENT_C.md", r"\| ([\d.]+)% \(26 of \d+\) \|", "dead_not_low_pct"),
    ("docs/EXPERIMENT_C.md", r"\| \*\*([\d.]+)%\*\* \(3 of \d+\) \|", "dead_high_pct"),
    ("docs/EXPERIMENT_C.md", r"we rate only ([\d.]+)%", "dead_high_pct_round"),
    ("docs/EXPERIMENT_C.md", r"([\d.]+)% dead-token recall", "dead_high_pct_round"),
    ("docs/AUDIT_BRIEF.md", r"false positives ([\d.]+)%", "fp_pct"),
    ("docs/AUDIT_BRIEF.md", r"unknown ([\d.]+)%", "unknown_pct"),
    ("docs/AUDIT_BRIEF.md", r"(\d+) dead samples", "dead_n"),
    ("src/entry.py", r"## Measured accuracy \(n=(\d+), published\)", "n"),
    ("src/entry.py", r"False positives \(healthy tokens flagged high\) \.+ ([\d.]+)%", "fp_pct"),
    ("src/entry.py", r"Answers returned as unknown \.+ ([\d.]+)%", "unknown_pct"),
]


def figures():
    """The numbers a reader is entitled to, straight from the last benchmark run."""
    with io.open(RESULTS, encoding="utf-8") as f:
        rows = json.load(f)["rows"]

    alive = [r for r in rows if r.get("outcome_label") == "alive"]
    dead = [r for r in rows if r.get("outcome_label") == "dead"]
    unknown = [r for r in rows if r["verdict"] == "unknown"]
    fp = [r for r in alive if r["verdict"] == "high"]

    centralized = [r for r in rows if r.get("goplus_label") == "centralized"]
    centralized_high = [r for r in centralized if r["verdict"] == "high"]
    return {
        "n": "%d" % len(rows),
        "healthy_n": "%d" % len(alive),
        "fp_pct": "%.1f" % (100.0 * len(fp) / len(alive)) if alive else "0.0",
        "unknown_pct": "%.1f" % (100.0 * len(unknown) / len(rows)) if rows else "0.0",
        "dead_n": "%d" % len(dead),
        # Every one of these was published and guarded by nothing, and every one of them
        # flattered: centralised-flagged-high read 6.7% against a measured 21.8%, and the
        # dead cohort was quoted as "95% (19 of 20)" four lines below "n=576".
        "centralized_n": "%d" % len(centralized),
        "centralized_high_pct": ("%.1f" % (100.0 * len(centralized_high) / len(centralized))
                                 if centralized else "0.0"),
        # The least flattering figure in the whole benchmark, and the one the Experiment
        # C post is built around: of the tokens that actually died, how many did we rate
        # high. It was quoted in three places and computed in none.
        "dead_high_pct_round": ("%.0f" % (100.0 * len([r for r in dead if r["verdict"] == "high"])
                                          / len(dead)) if dead else "0"),
        "dead_high_pct": ("%.1f" % (100.0 * len([r for r in dead if r["verdict"] == "high"])
                                    / len(dead)) if dead else "0.0"),
        "dead_not_low_pct": ("%.1f" % (100.0 * len([r for r in dead if r["verdict"] != "low"])
                                       / len(dead)) if dead else "0.0"),
        "dead_not_low_n": "%d" % len([r for r in dead if r["verdict"] != "low"]),
    }


def scan(write):
    vals = figures()
    stale, changed = [], []
    for rel, pattern, key in TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            stale.append((rel, pattern, "file missing", ""))
            continue
        text = io.open(path, encoding="utf-8").read()
        m = re.search(pattern, text)
        if not m:
            stale.append((rel, pattern, "pattern not found", vals[key]))
            continue
        if m.group(1) != vals[key]:
            stale.append((rel, pattern, m.group(1), vals[key]))
            if write:
                start, end = m.span(1)
                io.open(path, "w", encoding="utf-8", newline="").write(
                    text[:start] + vals[key] + text[end:])
                changed.append(rel)
    return vals, stale, changed


# Lines that are making an accuracy claim. Any percentage on one of these has to be
# owned by a TARGET, or it is a number nobody is checking.
# Numbers that are deliberately not tracked, each with a reason. An exemption list with
# reasons is honest; a looser regex would just hide the same thing.
_EXEMPT_CONTEXT = (
    "Rejected.",           # a historical measurement of a signal we removed (LP lock/burn)
    "What 100 looks like",  # the scorecard's aspiration block, not a measurement
    # Other vendors' published claims, quoted in the Experiment C post so that we are the
    # ones who already know the counterexamples rather than the ones corrected by a
    # commenter. They are their numbers, not ours, and must not track our benchmark.
    "Hypernative", "Forta", "Blockaid", "ChainAware", "HoneypotScan", "Solsniffer",
    # Measurements of things we chose NOT to ship, quoted as evidence against ourselves.
    "worse than chance",
    "0% of pausable",
    # The pool-match rate, which is computed in run_benchmark and not by this script.
    "same pool only",
)

_CLAIM_WORDS = ("false positive", "unknown", "centralised", "centralized",
                "flagged high", "not rated low", "confirmed-dead", "recall",
                "dead token")


def unclaimed_percentages():
    """Percentages on accuracy lines that no TARGET pattern captures.

    Adding a target for each number found by an audit fixes those four numbers and
    nothing else -- the next hand-written figure is unguarded again, which is exactly
    how these four got there. Four separate numbers drifted, all in the same direction,
    in the product whose single differentiator is that its numbers can be checked.

    So the check is inverted: instead of asking "does each guarded number match", it
    also asks "is every number guarded". A percentage on a line that is making an
    accuracy claim, in a file we publish, must be claimed by a TARGET.
    """
    by_file = {}
    for rel, pattern, key in TARGETS:
        by_file.setdefault(rel, []).append(pattern)

    out = []
    for rel, patterns in sorted(by_file.items()):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8") as f:
            text = f.read()
        claimed = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                claimed.add(m.group(1))
        for line in text.splitlines():
            low = line.lower()
            if not any(w in low for w in _CLAIM_WORDS):
                continue
            for m in re.finditer(r"([<>≤≥]?\s*)(\d+(?:\.\d+)?)%", line):
                # A number preceded by < or > is a TARGET, not a measurement -- "recall
                # >90%" is what we are aiming at, and it must not track results.json.
                if m.group(1).strip():
                    continue
                if m.group(2) in claimed:
                    continue
                if any(w in line for w in _EXEMPT_CONTEXT):
                    continue
                out.append((rel, m.group(2), line.strip()[:88]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite the published figures from results.json")
    args = ap.parse_args()

    if not os.path.exists(RESULTS):
        print("bench/results.json is missing -- run bench/run_benchmark.py first")
        return 2

    vals, stale, changed = scan(args.write)
    print("Measured: n=%s, false positives %s%% on %s healthy tokens, unknown %s%%"
          % (vals["n"], vals["fp_pct"], vals["healthy_n"], vals["unknown_pct"]))

    loose = unclaimed_percentages()
    if loose:
        print("\n%d published percentage(s) on accuracy lines that NO target claims:"
              % len(loose))
        for rel, pct, line in loose:
            print("  %-18s %s%%   %s" % (rel, pct, line))
        print("\nAdd a TARGETS entry, or stop publishing the number. An unguarded figure")
        print("is how the previous four drifted, all of them in the flattering direction.")

    if not stale and not loose:
        print("Everything published matches the benchmark.")
        return 0

    print("\n%d published figure(s) disagree with bench/results.json:" % len(stale))
    for rel, pattern, found, want in stale:
        print("  %-18s found %-8s expected %-8s  (%s)"
              % (rel, found, want, pattern[:44]))
    if args.write:
        print("\nRewrote: %s" % ", ".join(sorted(set(changed))))
        return 0
    print("\nRun `python bench/publish_numbers.py --write`, then redeploy.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
