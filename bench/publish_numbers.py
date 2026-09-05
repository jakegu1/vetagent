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

    return {
        "n": "%d" % len(rows),
        "healthy_n": "%d" % len(alive),
        "fp_pct": "%.1f" % (100.0 * len(fp) / len(alive)) if alive else "0.0",
        "unknown_pct": "%.1f" % (100.0 * len(unknown) / len(rows)) if rows else "0.0",
        "dead_n": "%d" % len(dead),
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

    if not stale:
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
