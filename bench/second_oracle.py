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
rate is a usability problem (one query in six goes unanswered), not a safety hole.

A CLAIM RETRACTED, 2026-09-07

An earlier version of this file said the 42 BUY_FAILED unknowns were on-chain reverts
that a second simulator would reproduce identically, and put the recovery ceiling at
9.5%. That was wrong, and an auditor caught it using data already in this repository.

Of the 45 BUY_FAILED/SETUP_FAILED tokens, 18 carry a market-outcome label and 16 of them
are alive: crvUSD holding $97.6M, USDG $20M, SPR $11.1M, XAUt $1.7M, all trading daily.
A buy that genuinely reverts on chain does not describe a token with $20M of depth and
continuous volume. Both lines sat in the same commit -- "17 have outcome labels, only 2
dead" and "a second simulator reproduces them identically" -- and only the second was
reasoned from, because it came from a subagent while the first was my own measurement.

Diagnosed since: honeypot.is picks its own pair and reverts on it. For USDG it chose
0xa38Cd437... while our chosen pool held $20,030,126. Passing our pair turns XAUt from
BUY_FAILED into a clean simulation with honeypot=False. Where the pool sits on a DEX it
cannot simulate at all (Curve, Aerodrome) it still cannot answer -- a coverage limit, not
a fact about the token.

So the recovery ceiling is not 9.5%, a second simulator with different venue coverage
would help, and any argument that leaned on this to dismiss the engine role was leaning
on something false. What still stands against that role is the licence question and the
zero marginal chain coverage; neither of them needed this claim.

A RELATED CLAIM, ALSO WRONG

I said the fee-on-transfer hypothesis was free to test from cached honeypot.is responses.
It is not. Across 1,104 cached responses every simulation failure is flattened to
"HP: BUY_FAILED", and INSUFFICIENT_OUTPUT_AMOUNT appears in only 10 -- all of them in
`honeypotResult.honeypotReason` for tokens already flagged, never in the
`simulationError` of a BUY_FAILED case. Nothing on disk separates fee-on-transfer from
any other buy failure.

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

# One output file per selection, so that no run can write over another's answers, and --run
# refuses to start when its own exists. Git ignores both (W5): a raw answer does not enter
# the repository until the owner has read Quick Intel's terms.
OUT = os.path.join(HERE, "second_oracle.json")
OUT_ADVERSARIAL = os.path.join(HERE, "second_oracle_adversarial.json")

# Each save writes the whole file to this copy beside it, then renames the copy over it, so
# an interrupt in the middle of a write leaves the previous version whole. Git ignores it too.
PARTIAL = ".partial"

# Quick Intel's honeypot endpoint runs a real transaction simulation -- their docs:
# "Based on the simulation results, the buy, sell, and transfer taxes of that token are
# calculated". That is what makes it an independent second judge rather than another
# static scanner agreeing with the first one for the same reason.
API = "https://api.quickintel.io/v1/getquickiauditfull"

# Their chain names differ from DexScreener's.
CHAIN = {"ethereum": "eth", "bsc": "bsc", "base": "base"}

# Name ourselves. Cloudflare in front of the API bans Python's default User-Agent
# ("Python-urllib/3.x") with HTTP 403 "error code: 1010" before a request reaches Quick
# Intel's gateway, so the key is never even checked. The first run with a real key, on
# 2026-09-29, came back 403 on all 143 calls for exactly that reason, and the report printed
# "0 of 122 (0%)" as if Quick Intel had answered nothing. Measured the same day with a fake
# key: the default User-Agent gets 403/1010; this one gets 401 Unauthorized from the gateway.
USER_AGENT = "vetagent-benchmark/1.0"

# The free API Testing tier is 200 calls/month. Refuse to exceed it by accident: an
# overrun on a free tier is how you lose the free tier.
FREE_TIER_MONTHLY = 200

# Consecutive calls start at least this far apart. The free tier allows about one call a
# second: the first real run, on 2026-09-29, slept 0.25 s between calls and was rate limited
# on about every other one, and each of those was a call of the month's allowance spent for
# nothing and asked again by hand.
PACE_SECONDS = 2.0


def _disputed(row):
    return row.get("goplus_label") == "safe" and row.get("verdict") == "high"


def _unknown(row):
    return row.get("verdict") == "unknown"


def _adversarial(row):
    return row.get("goplus_label") == "unsafe"


# What --plan and --run ask about, set by set, in asking order. Without --set: the two sets
# this script was written for. --set adversarial: the rows GoPlus labels `unsafe`, the cohort
# W3 rests on, which neither of those two covers.
SELECTIONS = {
    None: (("disputed", _disputed), ("unknown", _unknown)),
    "adversarial": (("adversarial", _adversarial),),
}

ABOUT = {
    "disputed": "the published false-positive rate is made of these",
    "unknown": "measures the engine role directly",
    "adversarial": "GoPlus labels them `unsafe`: the cohort W3 rests on",
}


def output_path(which=None):
    """A selection's fixed output file, read from the constants when called."""
    return {None: OUT, "adversarial": OUT_ADVERSARIAL}[which]


def _results_rows():
    with open(RESULTS, encoding="utf-8") as f:
        return json.load(f)["rows"]


def select(which=None, rows=None):
    """[(set name, its rows of bench/results.json)] for a selection, in asking order."""
    rows = _results_rows() if rows is None else rows
    return [(name, [r for r in rows if keep(r)]) for name, keep in SELECTIONS[which]]


def _say(text="", stream=None):
    """print(), except that a character the console cannot encode is escaped, not fatal.

    The Owner's Windows console is GBK, and a token symbol outside it would otherwise raise
    UnicodeEncodeError halfway through a report, after the calls were spent."""
    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        text = text.encode(encoding, "backslashreplace").decode(encoding)
    except LookupError:
        text = text.encode("ascii", "backslashreplace").decode("ascii")
    stream.write(text + "\n")


def _duration(seconds):
    return "%d s" % round(seconds) if seconds < 120 else "%d min" % round(seconds / 60.0)


def plan(which=None):
    """What a run would ask about and what it would cost. Costs nothing, needs no key."""
    everything = _results_rows()
    sets = select(which, everything)
    for name, rows in sets:
        _say("%-11s %4d tokens -- %s" % (name.upper(), len(rows), ABOUT[name]))
        if name == "disputed":
            adjudicable = [r for r in rows if r.get("driver") == "honeypot"]
            _say("%17s of which simulator-adjudicable (driver=honeypot): %d"
                 % ("", len(adjudicable)))
            _say("%17s the other %d fire on impersonation/liquidity, which no sell"
                 % ("", len(rows) - len(adjudicable)))
            _say("%17s simulation can settle -- do not pay expecting an answer on them" % "")
        unnamed = [r for r in rows if not CHAIN.get(r.get("chain"))]
        if unnamed:
            _say("%17s %d on a chain with no entry in CHAIN (%s): no call is made for them"
                 % ("", len(unnamed), ", ".join(sorted(set(str(r.get("chain"))
                                                           for r in unnamed)))))
    calls = sum(1 for _, rows in sets for r in rows if CHAIN.get(r.get("chain")))
    spare = FREE_TIER_MONTHLY - calls
    _say()
    _say("TOTAL       %4d calls, one every %.1f s: about %s"
         % (calls, PACE_SECONDS, _duration(calls * PACE_SECONDS)))
    _say("free API Testing tier: %d calls/month -> %s" % (
        FREE_TIER_MONTHLY,
        "fits, %d to spare" % spare if spare >= 0 else "does not fit: %d over" % -spare))
    _say("  (what this month has already spent is not known here)")
    if which is None:
        months = -(-len(everything) // FREE_TIER_MONTHLY)
        _say()
        _say("Full second-oracle labelling of all %d tokens would be %d calls:"
             % (len(everything), len(everything)))
        _say("  %d month%s of the free tier, or one month of Starter at $79.99."
             % (months, "" if months == 1 else "s"))
        _say("  Worth doing only if these %d calls show the disagreement is real." % calls)
    path = output_path(which)
    _say()
    _say("--run writes %s%s" % (path, " -- it exists, so --run refuses to start until it is"
                                      " moved" if os.path.exists(path) else ""))
    return 0


def fetch(address, chain, key):
    """One Quick Intel audit. Returns (payload, error)."""
    body = json.dumps({"chain": chain, "tokenAddress": address}).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"content-type": "application/json", "X-QKNTL-KEY": key,
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "http %d" % e.code
    except Exception as e:                                    # noqa: BLE001
        return None, type(e).__name__


def _pace(last_start):
    """Wait until PACE_SECONDS after the previous call started; return this call's start."""
    if last_start is not None:
        while True:
            wait = last_start + PACE_SECONDS - time.monotonic()
            if wait <= 0:
                break
            time.sleep(max(wait, 0.01))
    return time.monotonic()


def _refuse(path):
    _say("Refusing to start: %s already exists." % path)
    _say("It holds an earlier run's answers, and nothing else keeps a copy: git ignores it.")
    _say("Move or rename it to keep it, or delete it if it holds nothing worth keeping, then")
    _say("run again. This script never writes over it.")
    return 2


def _saved_row(set_name, row, payload, err):
    """One row of the output file, in today's fields."""
    return {"address": row.get("address"), "symbol": row.get("symbol"),
            "chain": row.get("chain"), "set": set_name,
            "our_verdict": row.get("verdict"), "our_driver": row.get("driver"),
            "goplus": row.get("goplus_label"), "outcome": row.get("outcome_label"),
            "quickintel": payload, "error": err}


def _save(path, which, selected, rows, first=False):
    """Write every row so far. The first write creates the file and fails if it exists; every
    later one goes through a copy renamed over the file, so an interrupt mid-write leaves the
    previous version whole."""
    doc = {"n": len(rows), "selection": which or "default", "selected": selected,
           "results": rows}
    if first:
        with open(path, "x", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        return
    with open(path + PARTIAL, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    os.replace(path + PARTIAL, path)


def run(max_calls, which=None):
    """Ask Quick Intel about a selection, saving after every call. Needs the key."""
    key = os.environ.get("QUICKINTEL_API_KEY")
    if not key:
        _say("Set QUICKINTEL_API_KEY. Apply for the free API Testing tier at")
        _say("https://quickintel.io/developers -- 200 calls/month, approval required.")
        return 2
    path = output_path(which)
    if os.path.exists(path):
        return _refuse(path)

    sets = select(which)
    selected = dict((name, len(rows)) for name, rows in sets)
    todo = [(name, row) for name, rows in sets for row in rows]
    try:
        _save(path, which, selected, [], first=True)
    except FileExistsError:
        return _refuse(path)

    calls = min(sum(1 for _, r in todo if CHAIN.get(r.get("chain"))), max(max_calls, 0))
    _say("Asking Quick Intel about %d rows (%s): %d calls, one every %.1f s, about %s."
         % (len(todo), ", ".join("%s %d" % kv for kv in selected.items()), calls,
            PACE_SECONDS, _duration(calls * PACE_SECONDS)))
    _say("Each answer is saved to %s as it arrives." % path)
    out, made, saved, last = [], 0, 0, None
    try:
        for set_name, row in todo:
            chain = CHAIN.get(row.get("chain"))
            if chain is None:
                continue
            if made >= max_calls:
                _say("--max-calls %d reached: the rows after this are not asked." % max_calls)
                break
            last = _pace(last)
            payload, err = fetch(row.get("address"), chain, key)
            made += 1
            out.append(_saved_row(set_name, row, payload, err))
            if made % 10 == 0:
                _say("  [%d/%d calls]" % (made, calls))
            _save(path, which, selected, out)
            saved = len(out)
    except KeyboardInterrupt:
        _say()
        _say("Interrupted: %s holds the %d rows saved before it; the rest were not asked."
             % (path, saved))
        return 130
    _say("Wrote %s: %d rows, %d calls." % (path, len(out), made))
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                      help="print the call budget and exit; costs nothing, needs no key")
    mode.add_argument("--run", action="store_true", help="spend calls")
    ap.add_argument("--set", choices=sorted(k for k in SELECTIONS if k),
                    help="for --plan and --run: this set instead of the disputed and "
                         "unknown sets. adversarial: the rows GoPlus labels unsafe")
    ap.add_argument("--max-calls", type=int, default=FREE_TIER_MONTHLY,
                    help="hard ceiling; defaults to the free tier's monthly allowance")
    args = ap.parse_args(argv)
    if args.run:
        return run(args.max_calls, args.set)
    return plan(args.set)


if __name__ == "__main__":
    sys.exit(main())
