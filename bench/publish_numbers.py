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
    ("src/landing.html", r"[Mm]easured over (\d+) tokens,", "n"),
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
    ("docs/EXPERIMENT_C.md", r"GoPlus's labels it is ([\d.]+)%", "goplus_fp_pct"),
    ("docs/EXPERIMENT_C.md", r"same pool only ([\d.]+)% of the time", "pool_match_pct"),
    ("docs/EXPERIMENT_C.md", r"\*\*([\d.]+)% of the dataset is Base",
     "base_share_pct"),
    ("docs/EXPERIMENT_C.md", r"adversarial cohort is ([\d.]+)% Base", "bad_base_share_pct"),
    ("docs/EXPERIMENT_C.md", r"dataset is ([\d.]+)% Base\" and", "base_share_pct"),
    # The landing page carried three stale counts in PROSE -- "20 confirmed-dead
    # tokens", "2 of those 20", "about five tokens" -- while the percentages beside them
    # were current, because the guard only checked percentages. A bare integer drifts
    # exactly as easily and reads exactly as authoritative.
    ("src/landing.html", r"<td>Dead tokens rated <em>high</em></td><td class=\"num high\">([\d.]+)%",
     "dead_high_pct"),
    ("src/landing.html", r"(\d+) of \d+\. Our worst number", "dead_high_n"),
    ("src/landing.html", r"\d+ of (\d+)\. Our worst number", "dead_n"),
    ("src/landing.html", r"a cohort of (\d+) confirmed-dead tokens", "dead_n"),
    ("src/landing.html", r"Only (\d+) of those \d+ are rated", "dead_high_n"),
    ("src/landing.html", r"Only \d+ of those (\d+) are rated", "dead_n"),
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
        data = json.load(f)
    rows = data["rows"]
    comp = (data.get("composition") or {}).get("all") or {"n": 0, "chain": {}}
    bad = (data.get("composition") or {}).get("bad") or {"n": 0, "chain": {}}
    goplus_good = (((data.get("goplus") or {}).get("full") or {}).get("good") or {})
    pool_both = [r for r in rows if r.get("engine_pool") and r.get("labelled_pool")]
    pool_same = [r for r in pool_both
                 if str(r["engine_pool"]).lower() == str(r["labelled_pool"]).lower()]

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
        "dead_high_n": "%d" % len([r for r in dead if r["verdict"] == "high"]),
        # Everything below was quoted in the Experiment C post and computed nowhere. The
        # exercise of making them computable found one of them wrong: the post said
        # "83% of the dataset is Base" twice. The dataset is 58% Base. 83% is the
        # ADVERSARIAL COHORT, which is 47 tokens, not 576 -- a real weakness of the
        # sampling, misattributed to a set twelve times larger.
        "goplus_fp_pct": "%.1f" % (100.0 * goplus_good.get("high", 0.0)),
        "base_share_pct": ("%.0f" % (100.0 * comp["chain"].get("base", 0) / comp["n"])
                           if comp.get("n") else "0"),
        "bad_base_share_pct": ("%.0f" % (100.0 * bad["chain"].get("base", 0) / bad["n"])
                               if bad.get("n") else "0"),
        "bad_n": "%d" % bad.get("n", 0),
        "pool_match_pct": ("%.0f" % (100.0 * len(pool_same) / len(pool_both))
                           if pool_both else "0"),
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
    "37% of the contracts",   # owner-power recall, measured by bench/owner_powers_measure.py
    # The pool-match rate, which is computed in run_benchmark and not by this script.
    "same pool only",
)

# Files a reader takes as this tool's CURRENT accuracy claim. Every percentage in one of
# these must be computed from results.json, exempt by name, or written as a target (<, >).
#
# Keyword gating used to decide what counted as a claim: a percentage was only checked if
# its line contained one of nine phrases. An audit walked straight through it with four
# mutations -- a percentage on a line without a keyword, "flags 12.3% of healthy tokens",
# a stale count with no percent sign, and anything on a line containing "Rejected."
# A guard with a keyword list is a guard with a documented bypass.
LIVE_CLAIM_FILES = ("README.md", "src/landing.html", "src/entry.py",
                    "docs/AUDIT_BRIEF.md", "docs/EXPERIMENT_C.md", "docs/SCORECARD.md")

# Logs are frozen ON PURPOSE and are excluded ON PURPOSE, not by oversight. ROUNDS.md is
# generated from commit messages; DECISIONS, HANDOFF, BACKLOG, OPPORTUNITIES and STRATEGY
# record what was believed and measured at a date, including numbers later withdrawn. A
# guard that rewrote those would erase the corrections this project is built on.
FROZEN_LOG_FILES = ("docs/ROUNDS.md", "docs/DECISIONS.md", "docs/HANDOFF.md",
                    "docs/BACKLOG.md", "docs/OPPORTUNITIES.md", "docs/STRATEGY.md")

# (file, exact substring that must appear on the line) -- scoped to one file each, so an
# exemption written for one sentence cannot silently cover a new number somewhere else.
# "Rejected." as a bare global substring exempted every line that happened to contain it.
_EXEMPT_LINES = (
    ("docs/AUDIT_BRIEF.md", "Rejected."),
    # Other vendors' published claims, quoted on our own landing page so that we are the
    # ones who already know the counterexamples. The page used to say "nobody else in
    # this category does", which is false and takes a commenter one minute to disprove.
    ("src/landing.html", "Hypernative"),
    ("src/landing.html", "Forta"),
    ("docs/EXPERIMENT_C.md", "Hypernative"),
    ("docs/EXPERIMENT_C.md", "Blockaid"),
    ("docs/EXPERIMENT_C.md", "sensitivity /"),
    ("docs/EXPERIMENT_C.md", "LP lock/burn detection fires on"),
    ("docs/EXPERIMENT_C.md", "the scan finds"),      # owner-power recall, see below
    ("docs/EXPERIMENT_C.md", "those that can blacklist"),
    ("docs/SCORECARD.md", "What 100 looks like"),
)

# Percentages inside a <style> block are CSS, not claims.
_CSS = re.compile(r"<style[^>]*>.*?</style>", re.S | re.I)


def unclaimed_percentages():
    """Every percentage in a live-claim file that no TARGET computes.

    Adding a target for each number an audit finds fixes those numbers and nothing else:
    the next hand-written figure is unguarded again, which is exactly how four of them
    got there. So the check is inverted -- not "does each guarded number match" but "is
    every number guarded".

    Two things this catches that the keyword-gated version did not, both found the day it
    was written: the Experiment C post said "83% of the dataset is Base" twice, when the
    dataset is 58% Base and 83% is the 47-token adversarial cohort; and the owner-power
    recall figures in the same post were measured on 250 Base contracts holding 3 of the
    19 pausable ones.
    """
    by_file = {}
    for rel, pattern, key in TARGETS:
        by_file.setdefault(rel, []).append(pattern)

    out = []
    for rel in LIVE_CLAIM_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            out.append((rel, "-", "LIVE CLAIM FILE IS MISSING"))
            continue
        with io.open(path, encoding="utf-8") as f:
            text = _CSS.sub("", f.read())
        claimed = set()
        for pat in by_file.get(rel, []):
            for m in re.finditer(pat, text):
                claimed.add(m.group(1))
        exempt = tuple(sub for f, sub in _EXEMPT_LINES if f == rel)
        for line in text.splitlines():
            for m in re.finditer(r"([<>\u2264\u2265~]?\s*)(\d+(?:\.\d+)?)%", line):
                # "recall >90%" is what we aim at; it must not track results.json.
                if m.group(1).strip():
                    continue
                if m.group(2) in claimed:
                    continue
                if any(sub in line for sub in exempt):
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
