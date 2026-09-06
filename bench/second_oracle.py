"""second_oracle.py — buy the two answers that decide whether a second judge is worth paying for.

WHAT THIS IS FOR

VetAgent has one sell simulator (honeypot.is) and one labelling oracle (GoPlus). Both are
single points of failure, and an external audit found the second one is worse than that:

    The headline false-positive rate IS the GoPlus disagreement rate.

21 of 349 GoPlus-"safe" tokens are rated `high` by the engine, and that 6.0% is published
as the false-positive rate. It is circular. If GoPlus's labels are sound the head-to-head
claim collapses; if they are not, those 21 may be TRUE positives and the published rate has
no denominator anyone should believe. One oracle cannot referee a dispute it is party to.

So the question is not "should we buy Quick Intel." It is "what would a genuinely
independent third judge tell us, and what is the smallest amount of it we need to buy."

THE ANSWER IS 121 CALLS, NOT 576

Two decisive sets, both fitting inside Quick Intel's FREE 200-call/month API Testing tier:

  DISPUTED (21) — the tokens the false-positive rate is made of. Only 12 are driven by
      `honeypot`, and only those 12 are adjudicable by a simulator; the other 9 fire on
      impersonation and liquidity, which no sell simulation can settle. Worth knowing
      before paying: the decisive subset is 12 tokens, not 21, and not 576.

  UNKNOWN (100) — every token the engine declines to answer. 55 because honeypot.is has no
      record, 42 because its simulation failed outright, 2 our own fault. This measures the
      ENGINE role directly: how many unknowns does a second simulator actually recover?

Labelling the whole 576-token set as a second oracle costs 576 calls — three months of the
free tier, or one month of Starter at $79.99. That is worth doing only AFTER these 121
calls show the disagreement is real.

WHAT WE ALREADY KNOW WITHOUT SPENDING ANYTHING

The unknowns do not appear to be hiding danger. Among those with a market outcome,
`simulation failed` is 2 dead of 17 (12%) and `no record` is 0 of 6, against a 16% base
rate across the labelled set. Small n, so this is directional — but it means the unknown
rate is a usability problem (one query in six goes unanswered), not a safety hole. Anyone
arguing for the paid tier on safety grounds has to beat that number first.

B2 COMPLIANCE

This lives in bench/, never in src/. A labelling oracle the engine can read is not an
oracle. `tests/test_upstream_contract.py` asserts engine endpoints and labeller endpoints
are disjoint at runtime, and this script must never be imported from the engine.

USAGE

    python bench/second_oracle.py --plan          # costs nothing, needs no key
    QUICKINTEL_API_KEY=... python bench/second_oracle.py --run --max-calls 121
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.json")
OUT = os.path.join(HERE, "second_oracle.json")

# Quick Intel's honeypot endpoint runs a real transaction simulation -- their docs:
# "Based on the simulation results, the buy, sell, and transfer taxes of that token are
# calculated". That is what makes it an independent second judge rather than another
# static scanner agreeing with the first one for the same reason.
API = "https://api.quickintel.io/v1/getquickiauditfull"

# Their chain names differ from DexScreener's.
CHAIN = {"ethereum": "eth", "bsc": "bsc", "base": "base"}

# The free API Testing tier is 200 calls/month. Refuse to exceed it by accident: an
# overrun on a free tier is how you lose the free tier.
FREE_TIER_MONTHLY = 200


def load_sets():
    """The two sets worth spending calls on, and nothing else."""
    with open(RESULTS, encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    disputed = [r for r in rows
                if r.get("goplus_label") == "safe" and r.get("verdict") == "high"]
    unknown = [r for r in rows if r.get("verdict") == "unknown"]
    return disputed, unknown


def plan():
    disputed, unknown = load_sets()
    adjudicable = [r for r in disputed if r.get("driver") == "honeypot"]
    print("DISPUTED  %3d tokens -- the 6.0%% false-positive rate is made of these"
          % len(disputed))
    print("            of which simulator-adjudicable (driver=honeypot): %d"
          % len(adjudicable))
    print("            the other %d fire on impersonation/liquidity, which no sell"
          % (len(disputed) - len(adjudicable)))
    print("            simulation can settle -- do not pay expecting an answer on them")
    print("UNKNOWN   %3d tokens -- measures the engine role directly" % len(unknown))
    print()
    print("TOTAL     %3d calls" % (len(disputed) + len(unknown)))
    print("free API Testing tier: %d calls/month -> fits, %d to spare"
          % (FREE_TIER_MONTHLY, FREE_TIER_MONTHLY - len(disputed) - len(unknown)))
    print()
    print("Full second-oracle labelling of all 576 tokens would be 576 calls:")
    print("  three months of the free tier, or one month of Starter at $79.99.")
    print("  Worth doing only if these 121 calls show the disagreement is real.")
    return 0


def fetch(address, chain, key):
    """One Quick Intel audit. Returns (payload, error)."""
    body = json.dumps({"chain": chain, "tokenAddress": address}).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"content-type": "application/json", "X-QKNTL-KEY": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "http %d" % e.code
    except Exception as e:                                    # noqa: BLE001
        return None, type(e).__name__


def run(max_calls):
    key = os.environ.get("QUICKINTEL_API_KEY")
    if not key:
        print("Set QUICKINTEL_API_KEY. Apply for the free API Testing tier at")
        print("https://quickintel.io/developers -- 200 calls/month, approval required.")
        return 2

    disputed, unknown = load_sets()
    todo = ([dict(r, _set="disputed") for r in disputed]
            + [dict(r, _set="unknown") for r in unknown])[:max_calls]

    out = []
    for i, row in enumerate(todo, 1):
        chain = CHAIN.get(row["chain"])
        if not chain:
            continue
        payload, err = fetch(row["address"], chain, key)
        out.append({"address": row["address"], "symbol": row.get("symbol"),
                    "chain": row["chain"], "set": row["_set"],
                    "our_verdict": row.get("verdict"), "our_driver": row.get("driver"),
                    "goplus": row.get("goplus_label"),
                    "outcome": row.get("outcome_label"),
                    "quickintel": payload, "error": err})
        if i % 10 == 0:
            print("  [%d/%d]" % (i, len(todo)))
        time.sleep(0.25)          # 5 calls/sec ceiling even on paid tiers

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"n": len(out), "results": out}, f, indent=2)
    print("\nWrote %s (%d calls)" % (OUT, len(out)))
    report(out)
    return 0


def report(out):
    """The two numbers this whole exercise exists to produce."""
    unknown = [r for r in out if r["set"] == "unknown"]
    answered = [r for r in unknown if r.get("quickintel") and not r.get("error")]
    print("\n--- ENGINE ROLE ---")
    print("unknowns a second simulator could answer: %d of %d (%.0f%%)"
          % (len(answered), len(unknown),
             100.0 * len(answered) / max(len(unknown), 1)))
    print("  -> if this is low, $79.99/month buys very little and the unknown rate")
    print("     is not a data-source problem.")

    disputed = [r for r in out if r["set"] == "disputed"
                and r.get("our_driver") == "honeypot"]
    print("\n--- ORACLE ROLE ---")
    print("simulator-adjudicable disputes checked: %d" % len(disputed))
    print("  Read each by hand. If Quick Intel agrees with US against GoPlus, the")
    print("  published false-positive rate is overstated and those were true")
    print("  positives. If it agrees with GoPlus, the rate is real and the")
    print("  head-to-head framing has to go. Either answer is worth having;")
    print("  the current position is that we do not know which.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", action="store_true",
                    help="print the call budget and exit; costs nothing, needs no key")
    ap.add_argument("--run", action="store_true", help="spend calls")
    ap.add_argument("--max-calls", type=int, default=FREE_TIER_MONTHLY,
                    help="hard ceiling; defaults to the free tier's monthly allowance")
    args = ap.parse_args()
    if args.run:
        return run(args.max_calls)
    return plan()


if __name__ == "__main__":
    sys.exit(main())
