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
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_json  # noqa: E402

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
    rows, seen_ids = [], set()
    for chain in chains:
        for kind, path, n_pages in (("new", "new_pools", pages),
                                    ("trending", "trending_pools", 1)):
            got = 0
            for page in range(1, n_pages + 1):
                url = ("https://api.geckoterminal.com/api/v2/networks/%s/%s?page=%d"
                       % (chain, path, page))
                # A snapshot has to be live; a cached copy would record the same pool
                # twice under two timestamps and silently corrupt the history.
                data = fetch_json(url, role="label", use_cache=False)
                if data is None:
                    if page == 1:
                        print("  %-8s %-9s fetch failed" % (chain, kind))
                    break
                pools = data.get("data") or []
                if not pools:
                    break  # past the last page
                for p in pools:
                    pid = p.get("id")
                    if not pid or (chain, pid, kind) in seen_ids:
                        continue
                    seen_ids.add((chain, pid, kind))
                    rows.append(_row(chain, kind, p, seen_at))
                    got += 1
            if got:
                print("  %-8s %-9s %d pools" % (chain, kind, got))
    return rows, seen_at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", default=",".join(DEFAULT_CHAINS))
    ap.add_argument("--pages", type=int, default=5,
                    help="pages of new_pools per chain (10 is the API maximum)")
    args = ap.parse_args()
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]

    os.makedirs(OUT_DIR, exist_ok=True)
    print("Collecting: %s" % ", ".join(chains))
    rows, seen_at = collect(chains, pages=args.pages)
    if not rows:
        print("Nothing collected — upstream is probably all down. Not writing a file.")
        return 1

    day = seen_at[:10]
    path = os.path.join(OUT_DIR, "pools-%s.ndjson" % day)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_days = len({fn[6:16] for fn in os.listdir(OUT_DIR)
                      if fn.startswith("pools-") and fn.endswith(".ndjson")})
    print("\n%d rows this run -> %s" % (len(rows), os.path.basename(path)))
    print("Snapshot archive: **%d days** deep — the moat's only direct measure" % total_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
