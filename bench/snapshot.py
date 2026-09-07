"""snapshot.py — daily snapshot collector. First brick in the moat.

Why this has to start **today** instead of waiting for the product to mature:

The upstream APIs (DexScreener / GeckoTerminal) only serve **current state** — there is no
historical query. "What did this pool look like in the 7 days before it got drained" can
only be answered by collecting in real time. A day we don't collect is a day that no longer
exists, and no amount of budget buys it back.

In six months this data answers a question nobody can answer today:
**do rugs have observable warning signs beforehand.** That is the only path from VetAgent
relaying someone else's judgment to having a judgment of its own, and it is the thing a
competitor who decides to build it today still has to wait six months to catch up on.

Usage:
    python bench/snapshot.py                  # collect once, append to snapshots/
    python bench/snapshot.py --chains eth,base --pages 3

Scheduled four times a day in .github/workflows/snapshot.yml. Depth cannot be
accelerated, but width can, and a pool that launches and dies between two daily passes
would otherwise never be recorded at all.
Output is NDJSON, one pool per line, one file per date, so it can be loaded straight into
any store later.
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import NOT_FOUND, fetch_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "snapshots")

# Chains to sweep. Unreachable ones are skipped without failing the run, so adding a
# speculative network costs one wasted request rather than a broken snapshot.
DEFAULT_CHAINS = ["eth", "base", "bsc", "solana", "arbitrum", "polygon_pos",
                  "avax", "optimism"]

# Fields recorded per pool. Deliberately the raw observables rather than today's scores —
# scoring rules change, raw numbers don't. Rescoring history under new rules later is only
# possible if the raw numbers are there.
def _row(chain, kind, p, seen_at):
    a = p.get("attributes") or {}
    rel = p.get("relationships") or {}
    base = ((rel.get("base_token") or {}).get("data") or {}).get("id", "")
    quote = ((rel.get("quote_token") or {}).get("data") or {}).get("id", "")
    tx = a.get("transactions") or {}
    h24 = tx.get("h24") or {}
    return {
        "seen_at": seen_at,
        "chain": chain,
        "kind": kind,                       # new / trending
        "pool_id": p.get("id"),
        "pool_address": a.get("address"),
        "name": a.get("name"),
        "base_token": base,
        "quote_token": quote,
        "pool_created_at": a.get("pool_created_at"),
        "price_usd": a.get("base_token_price_usd"),
        "price_quote": a.get("base_token_price_quote_token"),
        "reserve_usd": a.get("reserve_in_usd"),
        "fdv_usd": a.get("fdv_usd"),
        "market_cap_usd": a.get("market_cap_usd"),
        "volume_h24": (a.get("volume_usd") or {}).get("h24"),
        "volume_h1": (a.get("volume_usd") or {}).get("h1"),
        "price_change_h24": (a.get("price_change_percentage") or {}).get("h24"),
        "buys_h24": h24.get("buys"),
        "sells_h24": h24.get("sells"),
        "buyers_h24": h24.get("buyers"),
        "sellers_h24": h24.get("sellers"),

        # The seven flat fields above are four of the eighteen bucket-slots this response
        # carries. GeckoTerminal returns `transactions`, `volume_usd` and
        # `price_change_percentage` each as a six-bucket dict -- m5, m15, m30, h1, h6,
        # h24 -- confirmed in 5,276 of 5,276 cached pool objects with no variation. We
        # were storing h24 (and one h1) and discarding the rest of a payload already
        # fetched, already parsed and already paid for.
        #
        # `transactions` is the one that matters, because it is the one that expires.
        # `volume_usd` and `price_change_percentage` are substantially recoverable after
        # the fact from the OHLCV endpoints this repo already queries in
        # build_dataset.py. Buys, sells, buyers and sellers appear in NO historical
        # endpoint anywhere -- 5 discarded buckets x 4 counts = 20 numbers per pool per
        # pass that no amount of money buys back in 2027. The other two are stored
        # anyway: the marginal cost is bytes in a file that git deltas to nothing.
        #
        # Kept verbatim, spelled as the upstream spells them, rather than flattened into
        # twenty more keys. A future reader wants to be able to compare a row against a
        # live API response without a translation table.
        "tx": a.get("transactions"),
        "volume": a.get("volume_usd"),
        "price_change": a.get("price_change_percentage"),

        # The venue. A launchpad pool, a Uniswap V4 hook pool and a plain V2 pair are
        # different populations with different death rates, so this is a first-order
        # prior on everything the archive is being collected to answer. It is in every
        # response and nothing in this repository has ever read it -- and it is the
        # single field that would have shown, on day one, that the sell simulator cannot
        # answer for V4 pools, instead of that arriving as unexplained nulls.
        "dex": ((rel.get("dex") or {}).get("data") or {}).get("id"),

        # What this row means, for whoever reads it in 2027 after the fields have moved.
        "schema": 2,
    }


def collect(chains, pages=5):
    """Collect one snapshot.

    Two things are worth separating when asking whether this can go faster.

    **Depth cannot be bought.** A day not recorded never existed, and no budget
    reconstructs it. That part is fixed.

    **Width can.** The dead cohort the benchmark needs grows with pools recorded x days
    elapsed x rug rate, so recording more pools per pass is a multiplier available
    immediately. Three of them stack: new_pools paginates to 10 pages (200 per chain, not
    the 20 a single page returns), more chains can be listed, and the workflow can run
    several times a day — pools that appear and die between two daily passes are simply
    never seen otherwise.

    trending_pools stays on page one deliberately: it is a ranked list of what is already
    large, and paging deeper through it collects more of what we already have plenty of.
    The scarce sample is the freshly launched pool, and that only lives in new_pools.

    The binding constraint is GeckoTerminal's rate limit, roughly 30 requests a minute,
    which the fetcher already throttles to. Pages are capped rather than maximised so a
    scheduled run finishes in minutes and leaves headroom for the benchmark's own calls.
    """
    seen_at = datetime.now(timezone.utc).isoformat()
    rows, seen_ids, manifest = [], set(), []
    for chain in chains:
        for kind, path, n_pages in (("new", "new_pools", pages),
                                    ("trending", "trending_pools", 1)):
            got, misses = 0, 0
            for page in range(1, n_pages + 1):
                url = ("https://api.geckoterminal.com/api/v2/networks/%s/%s?page=%d"
                       % (chain, path, page))
                # A snapshot has to be live; a cached copy would record the same pool
                # twice under two timestamps and silently corrupt the history.
                data = fetch_json(url, role="label", use_cache=False)
                if data is None:
                    # A failed fetch and an exhausted listing took the SAME `break`, so
                    # "base recorded 40 pools this pass" could mean "Base was quiet" or
                    # "page 3 timed out and we stopped". Downstream those are identical,
                    # and no later analysis can separate them -- the information was
                    # never written down. Recorded now, per page, in the manifest.
                    #
                    # And recording it immediately proved the `break` was wrong too. The
                    # first CI pass with a manifest reported NINE failed page fetches
                    # across all eight chains, five of them on page 1 -- which under the
                    # old rule meant those chain/kind combinations collected nothing at
                    # all, silently. It also explains the daily row counts that looked
                    # like market variance (160 / 664 / 2252 / 1468 / 359) and were
                    # partly fetch-failure variance.
                    #
                    # Pages are independent listings, so a failed one is a hole, not an
                    # ending. Back off, take the next page, and only give up on this
                    # chain after two misses -- past that it is a rate limit rather than
                    # a blip, and hammering it makes things worse for the next chain.
                    manifest.append({"seen_at": seen_at, "chain": chain, "kind": kind,
                                     "page": page, "outcome": "fetch_failed", "rows": 0})
                    misses += 1
                    print("  %-8s %-9s page %d failed" % (chain, kind, page))
                    if misses >= 2:
                        break
                    time.sleep(3.0 * misses)
                    continue
                pools = data.get("data") or []
                page_rows = 0
                if not pools:
                    manifest.append({"seen_at": seen_at, "chain": chain, "kind": kind,
                                     "page": page, "outcome": "end_of_listing",
                                     "rows": 0})
                    break  # past the last page
                for p in pools:
                    pid = p.get("id")
                    if not pid or (chain, pid, kind) in seen_ids:
                        continue
                    seen_ids.add((chain, pid, kind))
                    rows.append(_row(chain, kind, p, seen_at))
                    got += 1
                    page_rows += 1
                manifest.append({"seen_at": seen_at, "chain": chain, "kind": kind,
                                 "page": page, "outcome": "ok", "rows": page_rows})
            if got:
                print("  %-8s %-9s %d pools" % (chain, kind, got))
    return rows, seen_at, manifest


# honeypot.is covers three chains, under GeckoTerminal's names for them. Verified in
# src/risk.py against the API; every other chain answers HTTP 400 "Invalid chain".
_SIM_CHAIN_ID = {"eth": 1, "bsc": 56, "base": 8453}


def _address_of(token_id, chain):
    """GeckoTerminal ids are chain-prefixed: `base_0x1313...`, not `0x1313...`.

    The first run of this probe passed the whole id to honeypot.is as an address and got
    six nulls back, which is the shape of a data-collection bug that would have looked
    like "brand-new tokens are not indexed yet" for four months before anyone checked.
    """
    t = str(token_id or "").strip().lower()
    if t.startswith(chain + "_"):
        t = t[len(chain) + 1:]
    return t if t.startswith("0x") and len(t) == 42 else ""


# How many times to ask honeypot.is about one token before giving up on it. An answered
# token is never asked again; an unanswered one is retried across later passes, because
# indexing lag is real and a single miss is not evidence of anything.
_MAX_ATTEMPTS = 3


def _round_robin_by_chain(rows):
    """Interleave an already-ranked list so each chain takes turns.

    Preserves the ranking within a chain, so the best candidate on each is still reached
    first -- it only stops one prolific chain consuming the whole budget.
    """
    order, buckets = [], {}
    for r in rows:
        buckets.setdefault(r.get("chain"), []).append(r)
    chains = list(buckets)
    i = 0
    while any(buckets[c] for c in chains):
        c = chains[i % len(chains)]
        if buckets[c]:
            order.append(buckets[c].pop(0))
        i += 1
    return order


def _unsimulatable(row):
    """1 if honeypot.is structurally cannot answer for this pool, 0 otherwise.

    A Uniswap V4 "pool address" is a 32-byte pool id (66 characters), not a pair contract.
    honeypot.is simulates against a pair, so it has nothing to work with.
    """
    return 1 if len(str(row.get("pool_address") or "")) > 42 else 0


def _neg_time(row):
    """Sort key that puts the most recently created pool first."""
    t = str(row.get("pool_created_at") or "")
    return tuple(-ord(c) for c in t) if t else (0,)


def _probed_already():
    """What the archive already knows about each (chain, token) it has asked about.

    Returns {(chain, token): attempts}, and the caller skips a token once honeypot.is has
    actually ANSWERED about it or we have asked _MAX_ATTEMPTS times without one.

    The first version returned a flat set of every token ever asked about, answered or
    not, so a single unanswered attempt blacklisted a token permanently. That is not a
    small waste: honeypot.is cannot simulate Uniswap V4 pools at all, the probe sorts
    youngest-first which is exactly where V4 launches concentrate, and a measured 79% of
    V4-only picks came back with no answer. So roughly a third of a hard-capped budget
    was being spent to permanently exclude tokens -- and the exclusion was strongest on
    the newest venue, which is the population the archive most needs.

    Retrying is not free either, and a token honeypot.is has never indexed after several
    days is usually one it never will (11 of the 14 oldest V4-only tokens still 404 four
    days on). Hence a cap rather than an unbounded retry.
    """
    attempts, answered = {}, set()
    for fn in sorted(os.listdir(OUT_DIR)) if os.path.isdir(OUT_DIR) else []:
        if not (fn.startswith("sellability-") and fn.endswith(".ndjson")):
            continue
        with io.open(os.path.join(OUT_DIR, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                key = (o.get("chain"), str(o.get("token") or "").lower())
                # An attempt that never reached honeypot.is is not evidence about the
                # token and must not count against its budget.
                if o.get("outcome") != "unreachable":
                    attempts[key] = attempts.get(key, 0) + 1
                elif key not in attempts:
                    attempts[key] = 0
                if o.get("answered"):
                    answered.add(key)
    return {k: (_MAX_ATTEMPTS if k in answered else n) for k, n in attempts.items()}


def probe_sellability(rows, seen_at, limit):
    """Ask, of the newest tokens seen this pass, whether they can be sold *today*.

    This is the one thing in the archive that cannot be recovered later, and it is the
    exact thing the product claims to detect.

    Price, reserves and trade counts at time t are irrecoverable too, and they are
    already recorded. Contract bytecode is not: it stays on chain and can be fetched in
    six months. But a **sell simulation** needs a live pool with liquidity in it. Once a
    token is dead there is nothing to simulate against, so "could you have got out on day
    one" is answerable only by having asked on day one.

    Why that matters more than more pool rows: every headline this project publishes
    rests on an adversarial cohort of 17 tokens, and the reason it is 17 is that
    confirmed-bad tokens are found by looking backwards, at which point they can no
    longer be tested. Asking on the day, every day, is the only way that cohort grows
    without bound -- and in four months it produces something the benchmark cannot
    currently answer at all: *does a day-one sellability verdict predict death?*

    Raw upstream fields only, never our score (DECISIONS P4). Scoring rules change; the
    simulator's own answer does not, and a future rule can be replayed over it.
    """
    if limit <= 0:
        return []
    done = _probed_already()
    fresh = [r for r in rows
             if r.get("kind") == "new" and r.get("chain") in _SIM_CHAIN_ID
             and r.get("base_token")]
    # Answerable venues first, then youngest -- and then shared out across chains.
    #
    # Youngest-first alone was the whole rule, and it aimed the budget straight at
    # Uniswap V4 launches, which honeypot.is cannot simulate: it wants a pair address and
    # a V4 pool is a 32-byte pool id with no pair. Those come back unanswered 79% of the
    # time. Deprioritised rather than skipped -- the other 21% do answer.
    #
    # Sorting by age alone had a second and larger cost, and it took the `outcome` field
    # to see it. BSC launches new pools faster than the other two chains combined, so
    # youngest-first handed it the ENTIRE budget: one CI pass spent all 25 requests on
    # BSC and answered none. Measured across the first 53 probes:
    #
    #     base   3 ok,  0 no_record   100%
    #     eth    2 ok,  0 no_record   100%
    #     bsc    0 ok, 48 no_record     0%
    #
    # honeypot.is simply does not index new BSC tokens on this timescale. So 48 of 53
    # requests bought nothing, and the two chains that answer every time were starved.
    # Round-robin rather than dropping BSC or weighting by the measured rate: 53 samples
    # is thin, coverage can change, and a fixed share bounds the waste at a third while
    # leaving the door open. `_MAX_ATTEMPTS` already caps what any one token can burn.
    fresh.sort(key=lambda r: (_unsimulatable(r), _neg_time(r)))
    fresh = _round_robin_by_chain(fresh)

    out, asked = [], set()
    for r in fresh:
        if len(out) >= limit:
            break
        chain = r["chain"]
        token = _address_of(r["base_token"], chain)
        if (not token or (chain, token) in asked
                or done.get((chain, token), 0) >= _MAX_ATTEMPTS):
            continue
        asked.add((chain, token))
        url = ("https://api.honeypot.is/v2/IsHoneypot?address=%s&chainID=%d"
               % (token, _SIM_CHAIN_ID[chain]))
        # role="engine": honeypot.is is an engine upstream, not a labelling oracle, and
        # the provenance accounting that keeps the benchmark honest depends on that
        # staying true. use_cache=False for the same reason the pool rows are live -- a
        # cached body would record one moment under two timestamps.
        # write_cache=False as well as use_cache=False. Reading live is only half of it:
        # this probe deliberately asks about tokens minutes old, and depositing that
        # answer in the shared cache would let a benchmark run days later score the
        # engine against a birth-moment response.
        hp = fetch_json(url, role="engine", use_cache=False, write_cache=False,
                        mark_missing=True)
        # `answered: false` merged four different facts into one boolean: honeypot.is has
        # no record of this token, honeypot.is refused us, our request timed out, and the
        # venue is one it structurally cannot read. Those mean opposite things -- the
        # first is a fact about the TOKEN, the rest are facts about US -- and collapsing
        # them is the exact defect this project keeps re-committing (E11: an observed
        # absence is a finding, an unobserved dimension is a gap, and neither may
        # impersonate the other).
        #
        # It matters here more than usual. A cohort assembled in 2027 from rows where
        # `answered` is false cannot tell "honeypot.is had never indexed it" from "our
        # runner was rate-limited", and the second is correlated with nothing while the
        # first is correlated with being brand new -- which is the whole population.
        missing = hp is NOT_FOUND
        if missing:
            hp = None
        outcome = ("ok" if hp is not None
                   else "no_record" if missing
                   else "unreachable")
        sim = (hp or {}).get("simulationResult") or {}
        res = (hp or {}).get("honeypotResult") or {}
        hold = (hp or {}).get("holderAnalysis") or {}
        code = (hp or {}).get("contractCode") or {}
        tok = (hp or {}).get("token") or {}
        out.append({
            "seen_at": seen_at,
            "chain": chain,
            "token": token,
            "pool_address": r.get("pool_address"),
            "pool_created_at": r.get("pool_created_at"),
            "reserve_usd": r.get("reserve_usd"),
            "answered": hp is not None,
            # ok / no_record / unreachable -- see the comment where this is computed.
            "outcome": outcome,
            # Raw upstream fields, spelled as honeypot.is spells them.
            "simulationSuccess": (hp or {}).get("simulationSuccess"),
            "simulationError": (hp or {}).get("simulationError"),
            "isHoneypot": res.get("isHoneypot"),
            "honeypotReason": res.get("honeypotReason"),
            "buyTax": sim.get("buyTax"),
            "sellTax": sim.get("sellTax"),
            "transferTax": sim.get("transferTax"),
            "flags": (hp or {}).get("flags"),

            # honeypot.is returns thirteen top-level branches and the first version of
            # this kept five. Every one of these came back in the same response, already
            # parsed, on a call we had already paid for -- and this is the one endpoint
            # in the archive whose answer genuinely expires, so a field dropped here is
            # dropped for good.
            #
            # holderAnalysis is the densest of them: `failed` and `siphoned` are counts
            # of real holders who tried to sell and could not. That is close to the label
            # this whole archive exists to manufacture, observed directly rather than
            # inferred from a price chart four months later.
            "holderAnalysis": hold or None,
            "contractCode": code or None,
            "totalHolders": tok.get("totalHolders"),
            "buyGas": sim.get("buyGas"),
            "sellGas": sim.get("sellGas"),
            "pair": (hp or {}).get("pair"),
            # Top-level `flags` is [] on every response checked -- the real ones live in
            # `summary`, together with honeypot.is's own risk and riskLevel. The first
            # version recorded the empty list and dropped all three.
            "summary": (hp or {}).get("summary"),
            "pairAddress": (hp or {}).get("pairAddress"),
            "router": (hp or {}).get("router"),
            "unsimulatable_venue": bool(_unsimulatable(r)),
            "schema": 2,
        })
    return out


def _last_pass():
    """The rows written by the most recent collection pass, and its timestamp.

    Re-collecting from GeckoTerminal just to have candidates to probe would double the
    upstream cost of every pass and, worse, probe a DIFFERENT set of pools than the one
    the archive recorded -- so the day-one simulation would not correspond to the day-one
    row it is meant to annotate. The rows are already on disk; read them.
    """
    files = sorted(fn for fn in os.listdir(OUT_DIR)
                   if fn.startswith("pools-") and fn.endswith(".ndjson"))
    if not files:
        return [], ""
    rows = []
    with io.open(os.path.join(OUT_DIR, files[-1]), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    if not rows:
        return [], ""
    latest = max(str(r.get("seen_at") or "") for r in rows)
    return [r for r in rows if str(r.get("seen_at") or "") == latest], latest


def _write_sellability(sell, seen_at):
    """Append sellability rows for one pass. Returns a process exit code."""
    if not sell:
        print("sellability: nothing to record")
        return 0
    path = os.path.join(OUT_DIR, "sellability-%s.ndjson" % seen_at[:10])
    with io.open(path, "a", encoding="utf-8", newline="") as f:
        for r in sell:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    answered = sum(1 for r in sell if r.get("answered"))
    hp = sum(1 for r in sell if r.get("isHoneypot"))
    print("sellability: asked %d, answered %d, honeypot %d -> %s"
          % (len(sell), answered, hp, os.path.basename(path)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", default=",".join(DEFAULT_CHAINS))
    ap.add_argument("--pages", type=int, default=5,
                    help="pages of new_pools per chain (10 is the API maximum)")
    ap.add_argument("--sellability-only", type=int, default=0, dest="sellability_only",
                    help="skip pool collection; sell-simulate N tokens from the most "
                         "recent pass already on disk. Lets the workflow commit the "
                         "irreplaceable pool rows BEFORE running the optional probe, so "
                         "a honeypot.is outage cannot take the pass down with it.")
    ap.add_argument("--sellability", type=int, default=25,
                    help="how many brand-new tokens to sell-simulate this pass "
                         "(0 disables). The only observable here that cannot be "
                         "recovered later: a dead token cannot be simulated.")
    args = ap.parse_args()
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]

    os.makedirs(OUT_DIR, exist_ok=True)

    if args.sellability_only:
        rows, seen_at = _last_pass()
        if not rows:
            print("No pool rows on disk to probe. Run the collector first.")
            return 1
        print("Probing the most recent pass: %d rows at %s" % (len(rows), seen_at))
        return _write_sellability(probe_sellability(rows, seen_at, args.sellability_only),
                                  seen_at)

    print("Collecting: %s" % ", ".join(chains))
    rows, seen_at, manifest = collect(chains, pages=args.pages)
    if not rows:
        print("Nothing collected — upstream is probably all down. Not writing a file.")
        return 1

    day = seen_at[:10]
    if manifest:
        mpath = os.path.join(OUT_DIR, "runs-%s.ndjson" % day)
        with io.open(mpath, "a", encoding="utf-8", newline="") as f:
            for m in manifest:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        failed = [m for m in manifest if m["outcome"] == "fetch_failed"]
        if failed:
            print("::warning::%d page fetches failed this pass: %s"
                  % (len(failed),
                     ", ".join(sorted({"%s/%s" % (m["chain"], m["kind"])
                                       for m in failed}))))
    path = os.path.join(OUT_DIR, "pools-%s.ndjson" % day)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    _write_sellability(probe_sellability(rows, seen_at, args.sellability), seen_at)

    total_days = len({fn[6:16] for fn in os.listdir(OUT_DIR)
                      if fn.startswith("pools-") and fn.endswith(".ndjson")})
    print("\n%d rows this run -> %s" % (len(rows), os.path.basename(path)))
    print("Snapshot archive: **%d days** deep — the moat's only direct measure" % total_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
