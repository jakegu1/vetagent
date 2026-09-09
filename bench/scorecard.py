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
import sys

# The summary prints a warning glyph, and a Windows console defaults to GBK, which cannot
# encode it -- so `python bench/scorecard.py --write` died on the owner's machine after
# printing the score but before writing the file. Reconfigure our own stdout rather than
# relying on the caller to set PYTHONIOENCODING.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - very old interpreters
    pass
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
    # None = measured, and rejected on the evidence. Not counted either way: scoring it
    # as "missing" would keep rewarding someone for building it, and scoring it as
    # "covered" would reward not building it. Both are wrong; the honest answer is that
    # this dimension turned out not to be one.
    #
    # Measured 2026-09-05 over 74 V2 pairs (totalSupply and the two burn sinks, read
    # straight off the pair): "LP is fully pullable" catches 4 of 8 confirmed-bad tokens
    # and fires on 22 of 38 confirmed-good ones. It discriminates worse than chance,
    # because most legitimate projects never burn LP -- they keep it to manage liquidity.
    # And burning does not imply safe: 4 of the 8 bad tokens had burned 95%+.
    # Building it would have added false positives and called it coverage.
    ("LP lock / burn", None),
    ("same-name token impersonation", True),   # shipped 2026-09-05, same-chain only:
                                               # a cross-chain rival cannot be verified
                                               # and can be manufactured by an attacker
    ("deployer history", False),
]

# Target distribution channels.
#
# These booleans are maintained by hand, not verified against anything -- the
# comment used to say they were checked against the registry, which was never true
# and is exactly the sort of claim this file exists to stop other people making.
# Anyone changing one is asserting they went and looked.
# The list was eight names picked early on. It is now twelve, because four more real
# channels exist and three of them have had a submission sitting in them since 09-07 --
# leaving them out kept the denominator flattering by accident. Widening it drops the
# score, which is the direction that cannot be self-serving; it would have been widened
# just the same if it had raised it.
#
# Binary on purpose: **submitted is not listed.** Six of these have an open submission
# and none of the six is reachable by a user yet, so all six are False. A pending queue
# is not distribution.
CHANNELS = [
    # Live, verified 2026-09-08 by opening each listing.
    ("Official MCP Registry", True),            # dev.vetagent/vetagent
    ("PulseMCP (auto-synced from registry)", True),
    ("Glama", True),                            # connector, "Ownership verified"
    ("Smithery", True),                         # "Published Sep 7, 2026"
    # Submitted and waiting. See docs/HANDOFF.md for the issue and PR numbers.
    ("mcp.so", False),                          # chatmcp/mcpso#3987
    # Live, verified 2026-09-09 by opening it: https://mcpservers.org/en/servers/vetagent-dev
    # (200, full description and endpoint), breadcrumb Home > Servers > Finance > VetAgent,
    # and findable by searching "vetagent" on their homepage.
    #
    # I first recorded this as NOT listed, and that was wrong. I guessed the slug from the
    # product name (/servers/vetagent), got a 404, checked /en/remote-mcp-servers, did not
    # find us, and reported an absence. The slug is derived from the DOMAIN --
    # `vetagent-dev` -- and /en/remote-mcp-servers turns out to be a curated subset rather
    # than the index of every remote server, which is what I assumed it was.
    #
    # So: I checked four places, found nothing, and reported "not on the site" instead of
    # "not where I looked". That is E11 -- an unobserved dimension impersonating an
    # observed absence -- committed by me, in a session spent fixing it in five other
    # places, and it took the owner to catch it. The lesson is the boring one: when
    # something is missing, the next question is whether I actually looked, and a guessed
    # URL is not looking.
    ("mcpservers.org", True),
    # None = measured inapplicable, excluded from the denominator. Same treatment, and the
    # same standard of evidence, as LP lock / burn above.
    #
    # PR #13873 was CLOSED on 2026-09-08 and the maintainer said why: remote servers are
    # being split out of this list into punkpeye/awesome-remote-mcp-servers, so this list
    # is now local/stdio servers by definition. VetAgent is a remote server. There is no
    # future in which this row can be True, and that is the maintainer's stated fact, not
    # our preference -- which is the exact line that separates this from the two rows
    # parked below.
    #
    # The restructure is deliberately score-neutral so it cannot be self-serving: this row
    # leaves the denominator and the remote row below splits into the two independent lists
    # it was wrongly collapsing, so the denominator stays at twelve and the score stays at
    # 4/12. It would have been done the same way if the arithmetic had gone the other way.
    ("awesome-mcp-servers (local/stdio only)", None),
    # Two different lists with nearly the same name, run by different people, each needing
    # its own PR -- one row for both was double-counting one opportunity and hiding the
    # other. punkpeye's is the one that matters: it is the split-out half of a 60k-star
    # list, and its CI independently verified our endpoint's `initialize` handshake and our
    # Glama connector before going green.
    ("awesome-remote-mcp-servers (jaw9c)", False),      # jaw9c#733, opened 09-07, mergeable
    ("awesome-remote-mcp-servers (punkpeye)", False),   # punkpeye#131, opened 09-09, CI pass
    ("Docker MCP registry", False),             # docker/mcp-registry#4954
    ("Cline marketplace", False),               # cline/mcp-marketplace#2471
    # Parked by the owner on 2026-09-08: both need an account only he can create, and he
    # has decided not to. They stay in the denominator on the same rule that governs
    # RISK_VECTORS -- a row leaves it when it has been **measured** to be worthless (see
    # LP lock / burn, `None`), never because we chose not to try. Dropping these two
    # would raise the score for giving up, which is the one direction a metric must
    # never move on its own. The work is done and waiting if that changes.
    ("Claude plugin directory", False),         # needs a free Console account
    ("OpenAI plugin directory", False),         # needs a verified identity (ID)
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
    applicable = [(n, ok) for n, ok in RISK_VECTORS if ok is not None]
    rejected = [n for n, ok in RISK_VECTORS if ok is None]
    covered = sum(1 for _, ok in applicable if ok)
    # A channel with `ok is None` has been measured inapplicable and leaves the denominator,
    # exactly as a rejected risk vector does. `if ok` alone would have counted None as a
    # miss and kept it in the denominator, which is the same as False -- so the exclusion
    # has to be filtered here, not just annotated in the table.
    channels = [(n, ok) for n, ok in CHANNELS if ok is not None]
    listed = sum(1 for _, ok in channels if ok)

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
    if rejected:
        print("  note: %d dimension(s) measured and rejected, excluded from the "
              "denominator: %s" % (len(rejected), ", ".join(rejected)))
    items.append(("Coverage", "risk dimensions covered", 20,
                  round(20.0 * covered / len(applicable), 1),
                  "%d / %d" % (covered, len(applicable))))

    # --- Credibility 20 ---
    items.append(("Credibility", "recall is measurable", 10,
                  10 if b.get("recall_measurable") else 0,
                  "dead samples: %s (need ≥20)" % b.get("dead_cohort", "?")))
    items.append(("Credibility", "days of snapshots", 10,
                  round(min(10.0, 10.0 * days / 180), 1),
                  "%d of 180 days" % days))

    # --- Distribution 15 ---
    items.append(("Distribution", "channels listed on", 10,
                  round(10.0 * listed / len(channels), 1),
                  "%d / %d" % (listed, len(channels))))
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
    # Three states, three glyphs. `None` means measured inapplicable and excluded from the
    # denominator, and it rendered as the same empty box as "not covered" -- so this
    # document showed LP lock / burn as an open gap for four days while the code was
    # excluding it, and would have shown a channel we can never be listed on as a channel
    # we simply have not reached. A row the arithmetic treats differently has to read
    # differently, or the page contradicts the score it is reporting.
    def cell(ok):
        if ok is None:
            return "➖ n/a"
        return "✅" if ok else "⬜"

    A("\n| Dimension | Covered |")
    A("|---|---|")
    for name, ok in RISK_VECTORS:
        A("| %s | %s |" % (name, cell(ok)))
    A("\n`➖ n/a` = measured and found not to be a dimension. Excluded from the "
      "denominator rather than counted as a gap, with the measurement in "
      "`bench/scorecard.py`.")

    A("\n## Distribution channels\n")
    A("| Channel | Listed |")
    A("|---|---|")
    for name, ok in CHANNELS:
        A("| %s | %s |" % (name, cell(ok)))
    A("\n`⬜` = not listed, and for six of these a submission is already open: **submitted "
      "is not listed.** `➖ n/a` = the channel cannot apply to this product, on the "
      "maintainer's own statement, so it leaves the denominator.")

    A("\n---\n")
    A("**What 100 looks like** (deliberately not trimmed to what we can reach): recall >90%")
    A("with false positives <2%, unknown <5%, every applicable dimension covered, "
      "a year or more of")
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
