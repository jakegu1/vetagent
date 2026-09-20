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
PRODUCTION = os.path.join(HERE, "production")

UNMEASURED = "not measured"


# ---------------------------------------------------------------- gather facts

def tests_pass():
    """Run the offline test suites. Red is red, no partial credit."""
    ok, detail = True, []
    # test_http_telemetry.py joined on 2026-09-14: it is where the rate limiter and the
    # batch cap are tested. A fixed tuple, not test.yml's list -- test_published_numbers.py
    # regenerates this score, so running it from here would recurse.
    for suite in ("test_risk.py", "test_mcp.py", "test_http_telemetry.py"):
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
        "false_block": r.get("false_block") or {},
        "unknown_rate": (r.get("overall") or {}).get("unknown_rate"),
        "dead_cohort": bad.get("n") or 0,
        "recall_measurable": (bad.get("n") or 0) >= 20,
    }


def newest_snapshot_date():
    """The date of the newest archive file -- the clock production artifacts are judged by.

    Not today's date: the scorecard is regenerated and diffed by a test, and a score that
    moves with the wall clock reddens by itself (the owner page did, every midnight).
    """
    if not os.path.isdir(SNAPSHOTS):
        return None
    dates = sorted(f[len("pools-"):-len(".ndjson")] for f in os.listdir(SNAPSHOTS)
                   if f.startswith("pools-") and f.endswith(".ndjson"))
    return dates[-1] if dates else None


# How old a committed production artifact may be, in days before the newest snapshot, and
# still count. Pre-registered with the items that read it (2026-09-14): a production figure
# nobody refreshed is not a measurement of production.
PRODUCTION_MAX_AGE_DAYS = 7
PRODUCTION_MIN_ROWS = 100


def _production_artifact(name, date_field):
    """(data, why_not) for bench/production/<name>. Never calls a network: the score is
    regenerated inside a test, so it reads only what was committed."""
    import datetime
    path = os.path.join(PRODUCTION, name)
    if not os.path.exists(path):
        return None, "no bench/production/%s yet" % name
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, "bench/production/%s unreadable" % name
    newest = newest_snapshot_date()
    stamp = str(data.get(date_field) or "")[:10]
    try:
        age = (datetime.date.fromisoformat(newest) - datetime.date.fromisoformat(stamp)).days
    except (TypeError, ValueError):
        return None, "bench/production/%s has no usable %s" % (name, date_field)
    if age > PRODUCTION_MAX_AGE_DAYS:
        return None, "bench/production/%s is %d days older than the archive" % (name, age)
    return data, None


def snapshot_days():
    if not os.path.isdir(SNAPSHOTS):
        return 0
    return len([f for f in os.listdir(SNAPSHOTS)
                if f.startswith("pools-") and f.endswith(".ndjson")])


# Chains the product advertises as valid `chain_hint` values, in the order /api lists
# them. This is the second axis of the coverage table below, and it exists because the
# first version of that table had only one: rows like "sellability simulation (honeypot,
# EVM)" carried a `True` while the simulator reached three of these eight chains. The
# comment two lines under it said so -- "The simulator covers ethereum, bsc and base" --
# and the row was marked covered anyway. Four advertised chains had nothing testing
# whether a holder can sell, and the scorecard called the dimension done.
#
# Advertised, not supported: a chain earns a column here by being offered to a caller,
# never by being covered. That is the whole point of the axis -- if the list shrank to
# what we cover, the table would score 100% by definition and say nothing.
ADVERTISED_CHAINS = ("ethereum", "bsc", "base", "arbitrum", "polygon",
                     "optimism", "avalanche", "solana")
_EVM = tuple(c for c in ADVERTISED_CHAINS if c != "solana")


# Risk dimensions we know matter, as (dimension, applies on, covered on).
# This table is the roadmap -- every empty cell is a real blind spot, not filler.
#
#   applies on  = the advertised chains where the dimension is a real question. A chain
#                 outside it is `n/a` and leaves the denominator, on the same rule that
#                 governs a rejected row: measured inapplicable, never "we skipped it".
#   covered on  = the subset we actually check. Everything in `applies on` and not in
#                 `covered on` is an open gap, and `tests/test_coverage_matrix.py` runs a
#                 real token on that chain to check the engine agrees.
#   applies on = None means the dimension itself was measured and rejected (see LP lock
#                 / burn). Excluded from the denominator either way.
#
# This is a **claim**, maintained by hand, and it is deliberately not derived from
# `src/risk.py`: the matrix test compares it against what the engine does, and a claim
# generated from the thing it is checking would agree with it always and mean nothing.
RISK_VECTORS = [
    # The sell simulator answers for three of the eight chains we advertise and HTTP 400
    # "Invalid chain" for the rest (`risk._SIMULATOR_CHAIN_IDS`, verified against the API
    # 2026-09-06). On the other five nothing tests whether a holder can sell.
    ("sellability simulation", ADVERTISED_CHAINS, ("ethereum", "bsc", "base")),
    # honeypot.is reports the three taxes from the same simulation, so they reach exactly
    # as far. Solana's Token-2022 transfer fee is read from RugCheck and is a transfer
    # tax in the same sense -- E25/E26 -- so it counts here.
    ("buy / sell / transfer tax", ADVERTISED_CHAINS,
     ("ethereum", "bsc", "base", "solana")),
    # DexScreener and GeckoTerminal cover all eight, and `_ANCHORS` has an entry for each,
    # so depth is counted in independently priced reserves everywhere we advertise.
    ("liquidity depth", ADVERTISED_CHAINS, ADVERTISED_CHAINS),
    ("pair age", ADVERTISED_CHAINS, ADVERTISED_CHAINS),
    # Whether the source is published is an EVM question; a Solana mint has no verified
    # source in this sense, and RugCheck reports none. Read from honeypot.is's
    # `contractCode`, so it stops where the simulator stops.
    ("contract source published", _EVM, ("ethereum", "bsc", "base")),
    # honeypot.is `summary.risk` on its three, RugCheck's score on Solana.
    ("upstream aggregator verdict", ADVERTISED_CHAINS,
     ("ethereum", "bsc", "base", "solana")),
    # Covered nowhere, for two different reasons that used to be two rows. On EVM it needs
    # GoPlus, the held-out oracle (DECISIONS B2).
    #
    # On Solana the reason stated here was wrong, and the row was right anyway. It read
    # "the upstream stopped feeding it", from four live mints on 2026-09-19 that all
    # returned topHolders: null. Re-measured 2026-09-20 over 64 mints x 8 sweeps, 109
    # minutes, 576 requests and zero non-200: RugCheck sends a holder list for 24 of 64 --
    # 14 of 18 established mints, 10 of 20 trending, and 0 of 26 it had just detected --
    # in every sweep, with no mint changing state over those 109 minutes. Twelve hours
    # later the same day it read 0 of 16 -- still all HTTP 200 -- so the level moves too,
    # and "the upstream stopped feeding it" was wrong about the mechanism rather than
    # about the moment. Coverage is per-mint at an instant and oscillates underneath
    # (DECISIONS E31).
    #
    # The row stays empty, because a dimension that answers for some tokens and not others
    # is not one this product can advertise, and the chains column is what the public
    # surfaces are checked against by `test_no_surface_claims_a_dimension_on_a_chain_we_do
    # _not_cover`. Marking Solana covered would license a claim that is false for 40 of 64
    # mints and for every mint younger than about an hour -- which is exactly the token an
    # agent is most likely to be asking about. Conservative in the same direction, on a
    # premise that is now measured instead of inferred: 37.5% is not 0%, and the honest
    # word for it is intermittent, not gone.
    ("holder concentration", ADVERTISED_CHAINS, ()),
    # A Solana concept. The EVM equivalent -- owner powers in the bytecode -- is disclosed
    # and never scored, and is not a row here; it is advertised on /api as its own line and
    # is a gap in this table rather than in the product. Noted, not fixed, in this pass.
    ("mint / freeze authority", ("solana",), ("solana",)),
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
    ("LP lock / burn", None, None),
    # Shipped 2026-09-05, same-chain only: a cross-chain rival cannot be verified and can
    # be manufactured by an attacker. Runs off the DexScreener search, so it reaches every
    # advertised chain.
    ("same-name token impersonation", ADVERTISED_CHAINS, ADVERTISED_CHAINS),
    ("deployer history", ADVERTISED_CHAINS, ()),
]


def coverage_cells():
    """(covered, applicable, rejected dimension names) counted in chain x dimension cells.

    Counted per cell rather than per row because a row was the unit that let four chains
    hide inside one `True`.
    """
    covered = applicable = 0
    rejected = []
    for name, applies, on in RISK_VECTORS:
        if applies is None:
            rejected.append(name)
            continue
        applicable += len(applies)
        covered += len([c for c in on if c in applies])
    return covered, applicable, rejected


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
    covered, applicable, rejected = coverage_cells()
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
    #
    # Every benchmark-derived row below is EVM-only. bench/dataset.json is 576 tokens on
    # base, ethereum and bsc and **zero on Solana** -- the labeller (GoPlus, held out under
    # B2) does not cover it, so the builder drops every Solana candidate. The 2026-09-19
    # Solana changes (E24-E26) therefore moved none of these numbers, and that is the
    # instrument's blind spot rather than evidence of safety. Solana is the chain
    # `find_new_hot_pools` defaults to, and it has no measured error rate at all.
    #
    # Rebalanced 2026-09-14 after an adversarial audit and a judged redesign. Six items at 5
    # each instead of three at 10, and every change lowered the score the day it landed
    # (55 -> 44), with each rule fixed before its value was looked at:
    #
    # - tests 10 -> 5. The same day, every test was green while production served 313 calls
    #   in 100 s past a limiter the tests said worked. Author-written tests are evidence,
    #   and capped as evidence.
    # - false blocks, new: liquid healthy tokens rated medium or high. A superset of the
    #   false positive, so it is graded on the false-positive ladder -- never more leniently
    #   than its subset.
    # - unknown rate split in two. The benchmark reads cached upstreams and cannot see the
    #   429s that make production answers unknown; production is read from a committed
    #   artifact, on the benchmark's own bands.
    # - production guards, new: the rate limiter and the batch cap observed working on the
    #   deployed service, not in a test.
    #
    # The two production items are "not measured" until their artifacts exist -- the
    # convention external callers already follows. The engineering ceiling stays 70.
    items.append(("Correctness", "tests all green", 5, 5 if tp else 0, "; ".join(tdetail)))
    fp = b.get("false_positive")
    fp_pts = band(fp, [0.02, 0.05, 0.10, 0.15], [10, 8, 6, 4, 2])
    items.append(("Correctness", "false positive rate (healthy rated high)", 5,
                  None if fp_pts is None else fp_pts * 0.5,
                  "%.1f%%" % (fp * 100) if fp is not None else UNMEASURED))
    fb = b.get("false_block") or {}
    fb_rate = fb.get("rate")
    fb_pts = band(fb_rate, [0.02, 0.05, 0.10, 0.15], [10, 8, 6, 4, 2])
    items.append(("Correctness", "false-block rate (liquid healthy rated medium or high)", 5,
                  None if fb_pts is None else fb_pts * 0.5,
                  ("%.1f%% (%d of %d)" % (fb_rate * 100, fb.get("blocked", 0), fb.get("n", 0))
                   if fb_rate is not None else UNMEASURED)))
    ur = b.get("unknown_rate")
    ur_pts = band(ur, [0.05, 0.10, 0.20, 0.30], [10, 8, 6, 4, 2])
    items.append(("Correctness", "unknown rate (benchmark, cached upstreams)", 5,
                  None if ur_pts is None else ur_pts * 0.5,
                  "%.1f%%" % (ur * 100) if ur is not None else UNMEASURED))

    verdicts, why = _production_artifact("verdicts.json", "window_end")
    counts = (verdicts or {}).get("counts") or {}
    n_prod = sum(int(counts.get(k, 0)) for k in ("low", "medium", "high", "unknown"))
    if verdicts is not None and n_prod < PRODUCTION_MIN_ROWS:
        verdicts, why = None, "%d answers in the window, need %d" % (n_prod, PRODUCTION_MIN_ROWS)
    if verdicts is None:
        items.append(("Correctness", "unknown rate (production, served answers)", 5, None,
                      UNMEASURED + " (%s)" % why))
    else:
        pur = int(counts.get("unknown", 0)) / float(n_prod)
        items.append(("Correctness", "unknown rate (production, served answers)", 5,
                      band(pur, [0.05, 0.10, 0.20, 0.30], [10, 8, 6, 4, 2]) * 0.5,
                      "%.1f%% of %d, %s to %s" % (pur * 100, n_prod,
                                                  verdicts.get("window_start", "?")[:10],
                                                  verdicts.get("window_end", "?")[:10])))

    probe, why = _production_artifact("guards-probe.json", "probed_at")
    if probe is None or not ((probe.get("flood") or {}).get("ran")
                             or (probe.get("batch_cap") or {}).get("ran")):
        items.append(("Correctness", "production guards observed live", 5, None,
                      UNMEASURED + " (%s)" % (why or "the probe did not run")))
    else:
        flood, cap = probe.get("flood") or {}, probe.get("batch_cap") or {}
        got = ((2.5 if flood.get("ran") and flood.get("calls_until_429") else 0.0)
               + (2.5 if cap.get("ran") and cap.get("http_status") == 400 else 0.0))
        items.append(("Correctness", "production guards observed live", 5, got,
                      "429 after %s calls; batch of %s -> HTTP %s; service %s on %s"
                      % (flood.get("calls_until_429") or "none of 75",
                         cap.get("messages", "?"), cap.get("http_status", "not probed"),
                         str(probe.get("checked_out_sha") or "?")[:7],
                         str(probe.get("probed_at", "?"))[:10])))

    # --- Coverage 20 ---
    if rejected:
        print("  note: %d dimension(s) measured and rejected, excluded from the "
              "denominator: %s" % (len(rejected), ", ".join(rejected)))
    # Per chain x dimension cell, not per dimension: the row was the unit that hid four
    # uncovered chains inside one `True`, so the row cannot be the unit that scores it.
    items.append(("Coverage", "risk dimensions covered, per advertised chain", 20,
                  round(20.0 * covered / applicable, 1),
                  "%d / %d chain-dimension cells" % (covered, applicable)))

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
    A("> Every Correctness row below is **EVM-only**: the benchmark is 576 tokens on base,")
    A("> ethereum and bsc and zero on Solana, because the held-out labeller does not cover")
    A("> Solana. Solana is the chain the discovery tool defaults to, and it has no measured")
    A("> error rate at all — including after the 2026-09-19 changes (DECISIONS E24-E26),")
    A("> which moved none of these numbers because the instrument cannot see that chain.\n")
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
    A("Every empty cell is a real blind spot, and the roadmap itself. One column per "
      "chain this tool **advertises**, because a dimension is not covered until it is "
      "covered where a caller is invited to ask.\n")
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

    # Short chain headings: the table is eight columns wide and the full names push it
    # into a horizontal scrollbar on a phone, where the right-hand chains -- the four the
    # sell simulator misses -- are exactly the ones that would scroll out of sight.
    _ABBR = {"ethereum": "eth", "avalanche": "avax", "optimism": "op",
             "arbitrum": "arb", "polygon": "poly", "solana": "sol"}
    A("\n| Dimension | %s |"
      % " | ".join(_ABBR.get(c, c) for c in ADVERTISED_CHAINS))
    A("|---|%s" % ("---|" * len(ADVERTISED_CHAINS)))
    for name, applies, on in RISK_VECTORS:
        if applies is None:
            row = ["➖"] * len(ADVERTISED_CHAINS)
        else:
            row = [cell(c in on) if c in applies else "➖" for c in ADVERTISED_CHAINS]
        A("| %s | %s |" % (name, " | ".join(row)))
    A("\n`✅` covered · `⬜` advertised and not covered · `➖` not a "
      "question on that chain, or a dimension measured and found not to be one. `➖` "
      "leaves the denominator rather than counting as a gap, with the measurement in "
      "`bench/scorecard.py`; `⬜` counts against the score on every chain it is empty "
      "on. `tests/test_coverage_matrix.py` runs a real token per chain and fails if the "
      "engine disagrees with a cell here.")

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
    A("with false positives and false blocks <2%, unknown <5% in the benchmark and in "
      "production, the abuse guards seen working on the live service, every applicable "
      "dimension covered, a year or more of")
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
