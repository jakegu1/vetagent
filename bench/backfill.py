"""backfill.py -- recover pool launches from any past day, straight from chain history.

Usage:
    python bench/backfill.py --days 30                  # the 30 days ending a week ago
    python bench/backfill.py --date 2026-06-07          # one specific day
    python bench/backfill.py --days 60 --chains base    # one chain

Why this exists
---------------
The snapshot archive (bench/snapshot.py) solved the sampling problem: live listings rank
by liquidity, scams never climb them, and a set sampled that way had 1 bad token in 209.
Recording brand-new pools daily fixes the density, but it buys the dataset at one day per
day. Waiting three weeks for a cohort large enough to state a recall figure is not a
research schedule, it is a queue.

It is also fragile in a way that only showed up once we relied on it. Two consecutive
builds of the same dataset returned 9 confirmed-bad tokens and then 2, because what gets
sampled depends on what happens to be listed on the morning you ask. A benchmark whose
denominator moves under it cannot support a claim.

Chain history does not move. Every pool ever created is still in the logs of the factory
that created it, addressable by block range, and a block range is a date. So instead of
waiting for tomorrow's launches we can read any past Tuesday -- and a pool launched three
months ago has already finished being whatever it was going to be, which is exactly the
resolved outcome the labeller needs.

What this is not
----------------
Not a replacement for bench/snapshot.py. Backfill sees only what a factory event records,
and it sees it as it is now, not as it looked on the day. The snapshot keeps the
contemporaneous view -- price, reserves, buyer counts at first sight -- which is the
evidence for anything time-sensitive. Backfill supplies volume; the archive supplies the
moment. They are gitignored and committed respectively for the same reason: a backfill is
re-derivable from the chain, a snapshot is not.
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

from fetcher import fetch_json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "backfill")

# keccak("PairCreated(address,address,address,uint256)")     -- Uniswap V2 and its forks
V2_TOPIC = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
# keccak("PoolCreated(address,address,uint24,int24,address)") -- Uniswap V3 and its forks
V3_TOPIC = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"

# keccak("Swap(...)") for the two pool families. Harvesting these instead of creations
# is the difference between a sample worth labelling and one that is mostly nothing.
#
# Measured: one historical day of Base creations gave 231 contracts, of which
# GeckoTerminal had heard of 94, 13 produced any label at all, and none were bad. A
# factory log fires for every deployment, and almost every deployment is a token nobody
# ever traded -- an address, a name, and no history for a labeller to read.
#
# A Swap log cannot fire for a token nobody traded. Ten minutes of Base from the same
# period yields 7,365 swaps across 770 distinct pools, every one of them a pool with a
# real trade in it, in about a second. That is the filter GeckoTerminal's new_pools feed
# was applying for us, recovered from the chain and therefore available for any past day.
V2_SWAP = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
V3_SWAP = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

# Endpoints were chosen by probing, not by reputation: most free RPCs either cap
# eth_getLogs at 50 blocks (useless -- a day is thousands) or refuse the method outright.
# These answered a multi-thousand-block range carrying a factory filter.
#
# More than one per chain where one exists, because the failure that actually happens is
# not an endpoint being down. It is 429 from asking a free node for a day of history at
# full speed -- self-inflicted, and it arrives exactly when the harvest is going well.
#
# BSC is absent on purpose. Every free BSC endpoint tried returned "limit exceeded" for
# eth_getLogs at every range down to 500 blocks, so BSC history needs a keyed provider.
# Two chains that work beat three where one quietly returns nothing.
CHAINS = {
    "eth": {
        "rpc": ["https://rpc.mevblocker.io",
                "https://eth.api.onfinality.io/public"],
        "block_seconds": 12,
        # 150 blocks of Ethereum carries ~3,500 swaps; 300 blocks of Base carries ~7,400
        # but arrives in a fifth of the time. Sized per chain so the first request is
        # usually the only one -- the 413 backoff below works, but every halving is a
        # round trip whose result gets thrown away.
        "swap_window": 120,
        "factories": ["0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",   # Uniswap V2
                      "0x1F98431c8aD98523631AE4a59f267346ea31F984"],  # Uniswap V3
        "quotes": {"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",      # WETH
                   "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",      # USDC
                   "0xdac17f958d2ee523a2206206994597c13d831ec7",      # USDT
                   "0x6b175474e89094c44da98b954eedeac495271d0f"},     # DAI
    },
    "base": {
        "rpc": ["https://mainnet.base.org", "https://base.drpc.org"],
        "block_seconds": 2,
        "swap_window": 300,
        "factories": ["0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",   # Uniswap V2
                      "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"],  # Uniswap V3
        "quotes": {"0x4200000000000000000000000000000000000006",      # WETH
                   "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",      # USDC
                   "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca",      # USDbC
                   "0x50c5725949a6f0c72e6c4a641f24049a917db0cb"},     # DAI
    },
}

_UA = {"Content-Type": "application/json",
       "User-Agent": "Mozilla/5.0 (vetagent-bench)",
       "Accept": "application/json"}


def rpc(url, method, params, timeout=30, retries=3):
    """One JSON-RPC call, backing off when a free node says we are asking too fast.

    429 is not an error here in any useful sense -- it is the node's rate limiter doing
    its job, and the only correct response is to wait. Letting it propagate meant a
    harvest that was working well would kill itself partway through a day and leave that
    day unwritten.
    """
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, method="POST", data=body.encode(), headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def rpc_any(urls, method, params, timeout=30):
    """The same call against the first endpoint that will serve it.

    Range refusals (413, and the -32005/-32602 family) are deliberately NOT retried
    elsewhere: they are a statement about the request, not the endpoint, so failing over
    would just ask a second node the same impossible question. Those go back to the
    caller, which narrows the window instead.
    """
    last = None
    for i, url in enumerate(urls):
        try:
            return rpc(url, method, params, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 413:
                raise
            last = e
        except Exception as e:          # noqa: BLE001 -- timeout, DNS, TLS
            last = e
    raise last


def _post_batch(urls, body, timeout):
    """POST one batch to the first endpoint that returns a JSON array."""
    for url in urls:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, method="POST",
                                             data=body.encode(), headers=_UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    payload = json.loads(r.read())
                if isinstance(payload, list):
                    return payload
                return payload          # an error object; the caller narrows the chunk
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except Exception:            # noqa: BLE001 -- timeout, TLS, DNS
                break
    return None


def rpc_batch(urls, calls, timeout=60, chunk=10, pace=0.5, passes=4):
    """Many JSON-RPC calls in few HTTP requests. Results are positional; None = unknown.

    Resolving one day of pools is ~800 eth_calls. Sent one at a time, a free node answers
    the burst with 429, each 429 costs a retry and a sleep, and a day took twelve minutes
    and usually died before writing anything -- the harvest rate-limited itself and then
    served the sentence. Batching is what makes it a minute instead.

    Three things this has to get right, all of which it got wrong first:

    1. Nodes cap batch size and disagree about the cap. mainnet.base.org allows ten and
       answers an eleventh with a single error OBJECT instead of an array. So the chunk
       halves on refusal and retries the same offset.

    2. **A rate-limited call comes back inside a 200 OK, as a per-item error.** Not an
       HTTP 429 -- a normal array where individual entries read
       {"code": -32016, "message": "over rate limit"} instead of carrying a result.
       Skipping entries with no "result" therefore silently converted "the node would not
       answer" into "this pool has no tokens", and the harvest reported 0 pools traded for
       a day whose first sampled window alone held 10,522 swaps. Refusals are now retried
       across several passes, and whatever never answers is counted and printed. An
       unanswered call must never become a fact about the chain.

    3. Results come back keyed by id and NOT necessarily in order, so they are placed by
       id, never zipped -- zipping would attribute one pool's tokens to another.
    """
    out = [None] * len(calls)
    todo = list(range(len(calls)))

    for attempt in range(passes):
        if not todo:
            break
        if attempt:
            time.sleep(2.0 * attempt)        # the node asked us to slow down; oblige
        still, i = [], 0
        while i < len(todo):
            idxs = todo[i:i + chunk]
            body = json.dumps([{"jsonrpc": "2.0", "id": k,
                                "method": calls[k][0], "params": calls[k][1]}
                               for k in idxs])
            payload = _post_batch(urls, body, timeout)

            if not isinstance(payload, list):
                if chunk > 1:
                    chunk = max(1, chunk // 2)   # the node's ceiling; same offset again
                    continue
                still.extend(idxs)
                i += len(idxs)
                continue

            answered = set()
            for item in payload:
                k = item.get("id")
                if isinstance(k, int) and 0 <= k < len(out) and "result" in item:
                    out[k] = item["result"]
                    answered.add(k)
            still.extend(k for k in idxs if k not in answered)
            i += len(idxs)
            if pace:
                time.sleep(pace)
        todo = still

    if todo:
        print("      %d of %d calls never answered -- recorded as unknown, not as absent"
              % (len(todo), len(calls)), flush=True)
    return out


def _timestamp_of(urls, block):
    b = rpc_any(urls, "eth_getBlockByNumber", [hex(block), False]).get("result") or {}
    return int(b["timestamp"], 16)


def block_at(urls, target, head, block_seconds):
    """Last block at or before a unix timestamp.

    Seeded from the head block and the chain's nominal block time rather than bisecting
    blindly: Base is 50M blocks deep, so a blind search costs ~26 round trips per
    boundary and two boundaries per day. Seeding lands within a few hours and converges
    in about six. The estimate only has to be close -- correctness comes from the
    bisection that follows, not from the block time being right.
    """
    head_ts = _timestamp_of(urls, head)
    guess = max(1, head - int((head_ts - target) / block_seconds))
    lo, hi = max(1, int(guess * 0.97)), min(head, int(guess * 1.03) + 1)
    # Widen until the target is genuinely bracketed. A chain that changed block time
    # mid-life can put it well outside a 3% window, and a search on an unbracketed range
    # returns an endpoint instead of failing, which would silently harvest the wrong day.
    while lo > 1 and _timestamp_of(urls, lo) > target:
        lo = max(1, lo - (hi - lo) * 2)
    while hi < head and _timestamp_of(urls, hi) < target:
        hi = min(head, hi + (hi - lo) * 2)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _timestamp_of(urls, mid) <= target:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _decode(log, quotes):
    """A factory log -> {base token, pool}, or None if it is not a token launch.

    Pairs of two quote assets (WETH against USDC and friends) are infrastructure, not
    launches, and a pair of two unknown tokens has no side we can price. Requiring
    exactly one non-quote side keeps the ones where "the token" is unambiguous.
    """
    topics = log.get("topics") or []
    if len(topics) < 3:
        return None
    sides = [("0x" + t[-40:]).lower() for t in topics[1:3]]
    data = log.get("data", "0x")[2:]
    if topics[0] == V2_TOPIC:
        pool = data[24:64]          # pair address is the first word
    else:
        pool = data[64 + 24:128]    # V3 puts tickSpacing first, pool second
    base = [s for s in sides if s not in quotes]
    if len(base) != 1 or len(pool) != 40:
        return None
    return {"base": base[0], "pool": ("0x" + pool).lower()}


def _symbols(urls, addresses):
    """Best-effort symbol() for readability in reports. Never fatal."""
    addrs = list(dict.fromkeys(addresses))
    res = rpc_batch(urls, [("eth_call", [{"to": a, "data": "0x95d89b41"}, "latest"])
                           for a in addrs])
    out = {}
    for addr, hexs in zip(addrs, res):
        if not hexs:
            continue
        h = hexs[2:]
        try:
            if len(h) >= 128:            # ABI string: offset, length, then the bytes
                n = int(h[64:128], 16)
                raw = bytes.fromhex(h[128:128 + n * 2])
            else:                        # some older tokens return a bare bytes32
                raw = bytes.fromhex(h).rstrip(b"\x00")
            sym = raw.decode("utf-8", "replace").strip()
        except ValueError:
            continue
        if sym:
            out[addr] = sym
    return out


def harvest(chain, day, want_symbols=True):
    """Every token launch the tracked factories recorded on one UTC day."""
    cfg = CHAINS[chain]
    urls = cfg["rpc"]
    start = int(datetime.datetime(day.year, day.month, day.day,
                                  tzinfo=datetime.timezone.utc).timestamp())
    head = int(rpc_any(urls, "eth_blockNumber", [])["result"], 16)
    b0 = block_at(urls, start, head, cfg["block_seconds"])
    b1 = block_at(urls, start + 86400, head, cfg["block_seconds"])

    rows, cur, step = [], b0, 5000
    while cur < b1:
        end = min(cur + step, b1)
        try:
            r = rpc_any(urls, "eth_getLogs", [{"fromBlock": hex(cur), "toBlock": hex(end),
                                              "address": cfg["factories"],
                                              "topics": [[V2_TOPIC, V3_TOPIC]]}])
        except urllib.error.HTTPError as e:
            # A node can refuse a range at the HTTP layer instead of the JSON-RPC one:
            # 413 when the response would be too large, 429 when we are asking too fast.
            # Both mean "smaller window", the same as the -32005 below, and both used to
            # escape as an exception that failed the whole day. A busy day produces more
            # logs per block, so this fired precisely on the days worth harvesting.
            if e.code not in (413, 429) or step <= 200:
                raise
            step //= 2
            continue
        if "error" in r:
            if step <= 200:
                raise RuntimeError("%s refused a %d-block range: %s"
                                   % (urls[0], step, r["error"]))
            step //= 2          # narrow the window, never skip the blocks
            continue
        for log in r["result"]:
            d = _decode(log, cfg["quotes"])
            if d:
                rows.append(d)
        cur = end + 1

    syms = _symbols(urls, [r["base"] for r in rows]) if want_symbols and rows else {}
    stamp = day.isoformat()
    return [{
        "seen_at": stamp + "T00:00:00+00:00",
        "chain": chain,
        "kind": "backfill",
        "pool_id": "%s_%s" % (chain, r["pool"]),
        "pool_address": r["pool"],
        "name": syms.get(r["base"], ""),
        "base_token": "%s_%s" % (chain, r["base"]),
        "quote_token": None,
        "pool_created_at": stamp + "T00:00:00Z",
    } for r in rows]


# The one endpoint this file uses that is not a chain RPC. Declared so build_dataset.py
# can hand it to the benchmark's disjointness assertion: sampling from an endpoint the
# engine also reads is what makes a benchmark circular, and a guard that never hears
# about a sampling source cannot object to it. The engine reads
# networks/{net}/tokens/{id}/pools, which is a different path -- but "different, I
# checked once" is exactly the kind of claim that rots, so it gets asserted instead.
_MULTI_URL = "https://api.geckoterminal.com/api/v2/networks/%s/pools/multi/%s"
_GT_PAGE = 30


def sampling_endpoints():
    """The endpoints this file samples from, in the benchmark's own normalised form.

    Derived from the URL _resolve_pools actually builds rather than written out by hand.
    A hand-written copy was already wrong on its first day -- it guessed the chain
    segment would normalise to a placeholder when it does not -- and a declaration that
    can drift from the code is worse than none, because the guard reads it as truth.
    """
    from fetcher import endpoint_of
    return sorted({endpoint_of(_MULTI_URL % (chain, "0x0")) for chain in CHAINS})


def _resolve_pools(chain, pools):
    """Pool address -> {base token, name}, via GeckoTerminal in pages of 30.

    Replaces two eth_calls per pool. Not for speed -- for arithmetic: free chain RPCs
    meter per call, and 250 pools is 500 calls, which mainnet.base.org answers with
    per-item "over rate limit" errors until almost nothing resolves. One harvested day
    got 19 pools out of 250 that way. GeckoTerminal answers thirty pools per request, so
    the same day costs nine.

    It also removes the quote-asset guessing entirely. Deciding which side of a pair is
    "the token" needed a hand-maintained list of numeraires per chain, which is a list
    that silently goes stale; GeckoTerminal states which side is the base token, and any
    pool it has never heard of is one the labeller could not have labelled anyway.
    """
    out = {}
    for i in range(0, len(pools), _GT_PAGE):
        page = pools[i:i + _GT_PAGE]
        d = fetch_json(_MULTI_URL % (chain, ",".join(page)), role="label")
        if d is None:
            continue          # unknown, not empty -- these pools are simply skipped
        for p in (d.get("data") or []):
            a = p.get("attributes") or {}
            rel = p.get("relationships") or {}
            bt = ((rel.get("base_token") or {}).get("data") or {}).get("id") or ""
            addr = bt.split("_", 1)[1] if "_" in bt else ""
            pool = (a.get("address") or "").lower()
            if addr and pool:
                out[pool] = {"base": addr.lower(),
                             "name": (a.get("name") or "").split("/")[0].strip()}
    return out


def harvest_traded(chain, day, windows=4, window_blocks=None, max_pools=250,
                   want_symbols=True):
    """Pools with a real trade on one past UTC day.

    Sampled in several windows spread across the day rather than one continuous stretch,
    because a single stretch is a single market mood. An hour when one launch is being
    farmed looks nothing like the hour after it, and a benchmark built from one of those
    hours would be measuring the hour.
    """
    cfg = CHAINS[chain]
    urls = cfg["rpc"]
    start = int(datetime.datetime(day.year, day.month, day.day,
                                  tzinfo=datetime.timezone.utc).timestamp())
    head = int(rpc_any(urls, "eth_blockNumber", [])["result"], 16)
    b0 = block_at(urls, start, head, cfg["block_seconds"])
    b1 = block_at(urls, start + 86400, head, cfg["block_seconds"])

    if window_blocks is None:
        window_blocks = cfg.get("swap_window", 300)
    stride = max(1, (b1 - b0) // max(1, windows))
    seen = {}
    for i in range(windows):
        lo = b0 + i * stride
        hi = min(lo + window_blocks, b1)
        if lo >= b1:
            break
        # Narrowing on refusal must not also shorten the window. The first version broke
        # out of the loop after one successful smaller request, so a busy window -- the
        # only kind that ever gets refused -- silently contributed a fraction of its
        # blocks, and the sample quietly thinned exactly where trading was heaviest.
        step, cur = hi - lo, lo
        while cur < hi:
            end = min(cur + step, hi)
            try:
                r = rpc_any(urls, "eth_getLogs", [{"fromBlock": hex(cur),
                                                   "toBlock": hex(end),
                                                   "topics": [[V2_SWAP, V3_SWAP]]}])
            except urllib.error.HTTPError as e:
                if e.code not in (413, 429) or step <= 20:
                    raise
                step //= 2
                continue
            if "error" in r:
                if step <= 20:
                    raise RuntimeError("%s refused %d blocks of swaps: %s"
                                       % (urls[0], step, r["error"]))
                step //= 2
                continue
            for log in r["result"]:
                addr = (log.get("address") or "").lower()
                if addr:
                    seen[addr] = seen.get(addr, 0) + 1
            cur = end + 1

    # Cap the work. Six windows of Base turn up several thousand distinct pools, and
    # each one costs two eth_calls to resolve plus one for its symbol -- so an uncapped
    # day spends ten thousand requests to produce more candidates than the labeller can
    # get through anyway. The labeller is the narrow part of this pipeline, not discovery.
    #
    # Selected by address rather than by swap count. Ranking by activity would quietly
    # bias the sample toward pools that were busiest, and "was busy, then died" is the
    # exact cohort this is here to find -- so ordering by the one property that has
    # nothing to do with the outcome keeps it deterministic without steering it.
    # Cap the work. Four windows of Base turn up a couple of thousand distinct pools,
    # more than the labeller can get through in a day, and the labeller is the narrow
    # part of this pipeline rather than discovery.
    #
    # Selected by address, not by swap count. Ranking by activity would bias the sample
    # toward the pools that were busiest, and "was busy, then died" is the exact cohort
    # this exists to find -- so ordering on the one property unrelated to the outcome
    # keeps it deterministic without steering it.
    candidates = sorted(seen)[:max_pools]
    resolved = _resolve_pools(chain, candidates)

    stamp = day.isoformat()
    rows = [{
        "seen_at": stamp + "T00:00:00+00:00",
        "chain": chain,
        "kind": "traded",
        "pool_id": "%s_%s" % (chain, pool),
        "pool_address": pool,
        "name": info["name"],
        "base_token": "%s_%s" % (chain, info["base"]),
        "quote_token": None,
        "swaps_sampled": seen.get(pool, 0),
        "pool_created_at": None,
    } for pool, info in sorted(resolved.items())]

    if seen:
        counts = sorted((r["swaps_sampled"] for r in rows), reverse=True)
        print("      %d pools traded in the sampled windows, %d of %d sampled resolved%s"
              % (len(seen), len(rows), len(candidates),
                 ", busiest saw %d swaps" % counts[0] if counts else ""), flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="a single UTC day, YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=14,
                    help="how many days to walk back (ignored when --date is given)")
    ap.add_argument("--end-offset", type=int, default=7,
                    help="stop this many days before today. A token needs time to become "
                         "whatever it was going to be; a pool from yesterday has no "
                         "outcome yet and only adds unlabelled rows.")
    ap.add_argument("--chains", default=",".join(CHAINS))
    ap.add_argument("--mode", choices=("traded", "launched"), default="traded",
                    help="traded: pools with a real swap that day (the useful one). "
                         "launched: every contract a factory created that day, which is "
                         "mostly tokens nobody ever traded -- kept because it is the "
                         "honest denominator when asking how many launches survive.")
    ap.add_argument("--no-symbols", action="store_true")
    args = ap.parse_args()

    chains = [c.strip() for c in args.chains.split(",") if c.strip() in CHAINS]
    if args.date:
        days = [datetime.date.fromisoformat(args.date)]
    else:
        end = datetime.date.today() - datetime.timedelta(days=args.end_offset)
        days = [end - datetime.timedelta(days=i) for i in range(args.days)]

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for chain in chains:
        for day in days:
            suffix = "" if args.mode == "traded" else "-launched"
            path = os.path.join(OUT_DIR, "pools-%s-%s%s.ndjson"
                                % (day.isoformat(), chain, suffix))
            if os.path.exists(path) and os.path.getsize(path) > 0:
                print("  %s %s  already harvested" % (chain, day))
                continue
            try:
                if args.mode == "traded":
                    rows = harvest_traded(chain, day, want_symbols=not args.no_symbols)
                else:
                    rows = harvest(chain, day, want_symbols=not args.no_symbols)
            except Exception as e:                       # noqa: BLE001
                print("  %s %s  FAILED: %s" % (chain, day, str(e)[:120]))
                continue
            # An empty result is not written, and so is not remembered as done.
            #
            # This bit me within an hour of writing it. A refactor broke the harvest, it
            # produced zero rows, the zero rows were written to disk, and every later run
            # skipped that day as "already harvested" -- the bug preserved itself. No day
            # on these chains has ever had zero trades, so zero always means something
            # went wrong upstream or in here, and the only safe reading is to try again.
            if not rows:
                print("  %s %s  nothing came back -- not caching this day" % (chain, day))
                continue
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            total += len(rows)
            print("  %s %s  %4d %s" % (chain, day, len(rows),
                                         "pools traded" if args.mode == "traded"
                                         else "launches"), flush=True)

    print("")
    print("%d rows written to %s" % (total, OUT_DIR))
    print("Run `python bench/build_dataset.py` to label them.")


if __name__ == "__main__":
    sys.exit(main())
