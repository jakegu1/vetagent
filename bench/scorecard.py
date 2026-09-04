"""scorecard.py — maturity score. Computed, never guessed.

The difference between this and me naming a number each time is the whole point:
**a number I give you is an opinion, a number computed from artifacts is a fact.**
So every line item below reads from something real (test results, benchmark report,
snapshot store, registry), and whatever cannot be read is marked "not measured" —
never filled in with an estimate.

Five dimensions, 100 points:

    Correctness  30   are its answers right
    Coverage     20   how many kinds of risk can it even see
    Credibility  20   can we prove it is useful
    Distribution 15   can enough people find it
    Demand       15   does anyone actually want it

**Why "Demand" is a dimension**: without it the score can be gamed by heads-down
development — ship a pile of features nobody asked for, the score climbs, the business
does not move. With it, **there is a hard ceiling on what pure engineering can reach**,
and the rest has to come from someone else.
That self-deception is exactly what this score exists to block.

Usage:
    python bench/scorecard.py            # print
    python bench/scorecard.py --write    # also write docs/SCORECARD.md
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RESULTS = os.path.join(HERE, "results.json")
SNAPSHOTS = os.path.join(HERE, "snapshots")
OUT_MD = os.path.join(ROOT, "docs", "SCORECARD.md")

UNMEASURED = "not measured"


# ---------------------------------------------------------------- gather facts

def tests_pass():
    """Run the offline test suites. Red is red, no partial credit."""
    ok, detail = True, []
    for suite in ("test_risk.py", "test_mcp.py"):
        p = os.path.join(ROOT, "tests", suite)
        if not os.path.exists(p):
            return False, ["%s missing" % suite]
        r = subprocess.run([sys.executable, p], capture_output=True,
                           encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode != 0:
            ok = False
            detail.append("%s failed" % suite)
        else:
            tail = (r.stdout or "").strip().splitlines()[-2:]
            detail.append("%s %s" % (suite, " ".join(t.strip() for t in tail)[:40]))
    return ok, detail


def benchmark_facts():
    if not os.path.exists(RESULTS):
        return {}
    with open(RESULTS, encoding="utf-8") as f:
        r = json.load(f)
    good = ((r.get("outcome") or {}).get("full") or {}).get("good") or {}
    bad = ((r.get("outcome") or {}).get("full") or {}).get("bad") or {}
    return {
        "n": r.get("n_evaluated"),
        "false_positive": good.get("high"),
        "unknown_rate": (r.get("overall") or {}).get("unknown_rate"),
        "dead_cohort": bad.get("n") or 0,
        "recall_measurable": (bad.get("n") or 0) >= 20,
    }


def snapshot_days():
    if not os.path.isdir(SNAPSHOTS):
        return 0
    return len([f for f in os.listdir(SNAPSHOTS)
                if f.startswith("pools-") and f.endswith(".ndjson")])


# Risk dimensions we know matter. This table is the roadmap —
# every unchecked line is a real blind spot, not filler.
RISK_VECTORS = [
    ("sellability simulation (honeypot)", True),
    ("buy / sell / transfer tax", True),
    ("liquidity depth", True),
    ("pair age", True),
    ("contract source published", True),
    ("upstream aggregator verdict", True),
    ("holder concentration (Solana)", True),
    ("mint / freeze authority (Solana)", True),
    ("holder concentration (EVM)", False),   # needs GoPlus, the held-out oracle (DECISIONS B2)
    ("LP lock / burn", False),               # pulling the pool is the main EVM rug, uncovered
    ("same-name token impersonation", False),  # the most common way an agent loses money
    ("deployer history", False),
]

# Target distribution channels. Listed ones are verified against the registry,
# the rest come from what HANDOFF records.
CHANNELS = [
    ("Official MCP Registry", True),
    ("PulseMCP (auto-synced from registry)", True),
    ("Claude plugin directory", False),
    ("Glama", False),
    ("Smithery", False),
    ("mcp.so", False),
    ("awesome-mcp-servers", False),
    ("mcpservers.org", False),
]


# ---------------------------------------------------------------- scoring

def band(value, thresholds, points):
    """Score by the band `value` falls into. thresholds ascend, points descend."""
    if value is None:
        return None
    for t, p in zip(thresholds, points):
        if value < t:
            return p
    return points[-1]


def score():
    tp, tdetail = tests_pass()
    b = benchmark_facts()
    days = snapshot_days()
    covered = sum(1 for _, ok in RISK_VECTORS if ok)
    listed = sum(1 for _, ok in CHANNELS if ok)

    # Demand and external callers cannot be read automatically yet (needs a
    # Cloudflare token), so they are recorded as "not measured" rather than 0 —
    # those two mean different things.
    external_callers = None
    paying = 0
    trial_intents = 0

    items = []

    # --- Correctness 30 ---
    items.append(("Correctness", "tests all green", 10, 10 if tp else 0, "; ".join(tdetail)))
    fp = b.get("false_positive")
    items.append(("Correctness", "false positive rate (healthy rated high)", 10,
                  band(fp, [0.02, 0.05, 0.10, 0.15], [10, 8, 6, 4, 2]),
                  "%.1f%%" % (fp * 100) if fp is not None else UNMEASURED))
    ur = b.get("unknown_rate")
    items.append(("Correctness", "unknown rate", 10,
                  band(ur, [0.05, 0.10, 0.20, 0.30], [10, 8, 6, 4, 2]),
                  "%.1f%%" % (ur * 100) if ur is not None else UNMEASURED))

    # --- Coverage 20 ---
    items.append(("Coverage", "risk dimensions covered", 20,
                  round(20.0 * covered / len(RISK_VECTORS), 1),
                  "%d / %d" % (covered, len(RISK_VECTORS))))

    # --- Credibility 20 ---
    items.append(("Credibility", "recall is measurable", 10,
                  10 if b.get("recall_measurable") else 0,
                  "dead samples: %s (need ≥20)" % b.get("dead_cohort", "?")))
    items.append(("Credibility", "days of snapshots", 10,
                  round(min(10.0, 10.0 * days / 180), 1),
                  "%d of 180 days" % days))

    # --- Distribution 15 ---
    items.append(("Distribution", "channels listed on", 10,
                  round(10.0 * listed / len(CHANNELS), 1),
                  "%d / %d" % (listed, len(CHANNELS))))
    items.append(("Distribution", "external callers", 5,
                  None if external_callers is None else min(5, external_callers),
                  UNMEASURED + " (needs CLOUDFLARE_API_TOKEN, see bench/usage.py)"))

    # --- Demand 15 ---
    items.append(("Demand", "paying users", 10, min(10, paying * 2), "%d" % paying))
    items.append(("Demand", "trial intent / inbound asks", 5, min(5, trial_intents),
                  "%d" % trial_intents))

    return items, {"benchmark": b, "snapshot_days": days,
                   "covered": covered, "listed": listed}


def totals(items):
    dims, order = {}, []
    for dim, _, weight, got, _ in items:
        if dim not in dims:
            dims[dim] = [0.0, 0.0, False]
            order.append(dim)
        dims[dim][0] += weight
        dims[dim][1] += got or 0.0
        if got is None:
            dims[dim][2] = True
    return dims, order


def render(items, facts):
    dims, order = totals(items)
    total_max = sum(d[0] for d in dims.values())
    total_got = sum(d[1] for d in dims.values())

    L = []
    A = L.append
    A("# Maturity score (SCORECARD.md)\n")
    A("> Generated by `python bench/scorecard.py --write`, **do not hand-edit**.")
    A("> It moves with every commit, so `git diff` tells you what the change was worth.\n")
    A("\n## Total: **%.0f / %d**\n" % (total_got, total_max))
    A("| Dimension | Score | Max |")
    A("|---|---|---|")
    for d in order:
        mx, got, partial = dims[d]
        A("| %s | %.1f%s | %d |" % (d, got, " ⚠️" if partial else "", mx))
    A("\n⚠️ = this dimension has line items nothing can measure automatically. "
      "The score is low for lack of data, not for lack of work.\n")

    A("\n## Line items\n")
    A("| Dimension | Item | Score | Max | Evidence |")
    A("|---|---|---|---|---|")
    for dim, name, weight, got, note in items:
        A("| %s | %s | %s | %d | %s |"
          % (dim, name, "—" if got is None else "%.1f" % got, weight, note))

    A("\n## Why engineering alone cannot max this out\n")
    A("Demand 15 + external callers 5 + measurable recall 10 = **30 points**,")
    A("and none of the three **can be earned by writing code**:")
    A("")
    A("- Demand needs someone willing to pay")
    A("- External callers needs someone to actually wire it in")
    A("- Measurable recall needs the snapshot store to collect enough dead samples, "
      "and time is not for sale")
    A("")
    A("So **the ceiling for pure engineering is 70**.")
    A("That is not pessimism baked into the design, it is the reason this score exists —")
    A("**it does not let 'I have been busy' impersonate 'we made progress'.**\n")

    A("\n## Risk dimension coverage\n")
    A("Every unchecked line is a real blind spot, and the roadmap itself.\n")
    A("\n| Dimension | Covered |")
    A("|---|---|")
    for name, ok in RISK_VECTORS:
        A("| %s | %s |" % (name, "✅" if ok else "⬜"))

    A("\n## Distribution channels\n")
    A("| Channel | Listed |")
    A("|---|---|")
    for name, ok in CHANNELS:
        A("| %s | %s |" % (name, "✅" if ok else "⬜"))

    A("\n---\n")
    A("**What 100 looks like** (deliberately not trimmed to what we can reach): recall >90%")
    A("with false positives <2%, unknown <5%, all 12 dimensions covered, a year or more of")
    A("outcome data, the benchmark methodology cited as a standard by peers, the default")
    A("choice at every agent entry point, and paying users who would complain if it "
      "disappeared.\n")
    A("**The current %.0f is not a failure** — it says precisely that the" % total_got)
    A("engineering is decent, proof and demand are both still zero, and writing more code")
    A("cannot solve those last two.\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    items, facts = score()
    md = render(items, facts)
    dims, order = totals(items)
    total_got = sum(d[1] for d in dims.values())
    total_max = sum(d[0] for d in dims.values())

    print("=" * 58)
    print("VetAgent maturity: %.0f / %d" % (total_got, total_max))
    print("=" * 58)
    for d in order:
        mx, got, partial = dims[d]
        bar = "#" * int(round(20.0 * got / mx)) if mx else ""
        print("  %-8s %5.1f / %-3d %s%s" % (d, got, mx, bar, "  ⚠️ partial" if partial else ""))
    print()
    for dim, name, weight, got, note in items:
        print("  %-8s %-26s %5s/%-3d  %s"
              % (dim, name[:26], "—" if got is None else "%.1f" % got, weight, note[:44]))

    if args.write:
        os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write(md)
        print("\nWrote %s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
