"""build_dataset.py — sample candidate tokens and label them with independent labelers.

Usage:
    python bench/build_dataset.py --limit 40          # smoke run
    python bench/build_dataset.py --limit 300         # real build

Sampling runs down three paths, so the set is not just tokens that look fine at a glance:
  backfill bench/backfill, launches recovered from chain history months back -- already
           resolved into whatever they became, and available in any quantity today
  archive  bench/snapshots, pools that were new on an earlier day -- the contemporaneous
           record, one day per day, which is why backfill exists
  head     GeckoTerminal per-chain pool pages -- skews healthy, the control group

The labelers live in labels.py and only hit endpoints the engine never reads.
Writes bench/dataset.json.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backfill  # noqa: E402
from fetcher import fetch_json, note_endpoint, persist_access_log  # noqa: E402
from labels import GOPLUS_CHAIN_ID, GT_NETWORK, goplus_label, outcome_label  # noqa: E402

# GeckoTerminal network id -> our canonical chain name (snapshots store the GT id)
_GT_TO_CHAIN = {v: k for k, v in GT_NETWORK.items()}

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")
BACKFILL_DIR = os.path.join(HERE, "backfill")

HEAD_CHAINS = ["ethereum", "base", "bsc"]

# What share of --limit each source may claim.
#
# These are quotas, not priorities, and that distinction is the whole point. The first
# version of this just collected sources in order and truncated to --limit at the end,
# which is not a sampling design -- it is whichever source happens to run first winning
# the entire set. With backfill at 60% and the archive holding several hundred rows, the
# truncation cut every last head-page token, and the head pages are the healthy control
# group the false-positive rate is measured against. The benchmark would have reported a
# false-positive rate computed on almost no legitimate tokens, and reported it as though
# nothing had changed.
#
# A source that cannot fill its quota gives the remainder back to the others, so a day
# with no backfill on disk still produces a full set.
SOURCE_QUOTA = {
    "backfill": 0.40,   # resolved outcomes, in quantity, from chain history
    "snapshot": 0.30,   # the contemporaneous archive -- where the bad ones came from
    "head": 0.30,       # established tokens; the control group, deliberately boring
}


def _norm_pair(p):
    """DexScreener pair -> the common candidate shape."""
    base = p.get("baseToken") or {}
    return {
        "address": base.get("address"),
        "symbol": base.get("symbol"),
        "chain": p.get("chainId"),
        "pool": p.get("pairAddress"),
        "source": "dexscreener_search",
    }


def collect_candidates(limit):
    """Sample candidates. Returns a deduped list in a fixed order (reproducible)."""
    buckets = {"backfill": [], "snapshot": [], "head": []}
    seen = set()

    def adder(bucket):
        def add(c):
            if not c.get("address") or not c.get("pool") or not c.get("chain"):
                return
            if c["chain"] not in GT_NETWORK or c["chain"] not in GOPLUS_CHAIN_ID:
                return  # EVM only: the GoPlus labeler does not cover Solana
            key = (c["chain"], c["address"].lower())
            if key in seen:
                return
            seen.add(key)
            buckets[bucket].append(c)
        return add

    # Pools recovered from chain history. Every one of them traded on the day it was
    # sampled from, and has since finished being whatever it was going to be -- which is
    # the resolved outcome the labeller needs, available without waiting for it.
    _from_backfill(adder("backfill"), seen, limit)
    if buckets["backfill"]:
        # Backfill runs in its own process, so the endpoints it sampled from are not in
        # this process's access log. Declaring them here is what lets the benchmark's
        # disjointness assertion see a sampling source at all -- without it the guard
        # would be silent about the newest way candidates get into the set.
        for ep in backfill.sampling_endpoints():
            note_endpoint("label", ep)

    # Recently-launched, from the daily snapshot archive.
    #
    # This is the fix for the sampling problem that made recall unmeasurable. Live
    # listings yielded 1 bad token in 209, because they rank by liquidity and scams never
    # climb them. Brand-new pools raise that density about 40x (20% vs 0.5% in a spot
    # check), but a token minted an hour ago is too new for the labelling oracle -- 26 of
    # 36 came back with no GoPlus data at all.
    #
    # A pool that was new *yesterday* sits in the gap: old enough that GoPlus knows it,
    # young enough that a scam has not been delisted.
    _from_snapshots(adder("snapshot"), seen)

    # Head: page through each chain. Skews healthy on purpose -- this is the control
    # group, and a false-positive rate needs legitimate tokens to be computed against.
    head_add = adder("head")
    head_cap = int(limit * SOURCE_QUOTA["head"]) * 3   # over-collect, quota trims later
    for chain in HEAD_CHAINS:
        net = GT_NETWORK[chain]
        for page in range(1, 11):
            if len(buckets["head"]) >= head_cap:
                break
            d = fetch_json("https://api.geckoterminal.com/api/v2/networks/%s/pools?page=%d"
                           % (net, page), role="label")
            for p in ((d or {}).get("data") or []):
                a = p.get("attributes") or {}
                rel = p.get("relationships") or {}
                bt = ((rel.get("base_token") or {}).get("data") or {}).get("id", "")
                addr = bt.split("_", 1)[1] if "_" in bt else ""
                head_add({"address": addr,
                          "symbol": (a.get("name") or "").split("/")[0].strip(),
                          "chain": chain, "pool": a.get("address"), "source": "gt_pools"})

    # DexScreener keyword search used to be a fourth source. It was removed for two
    # reasons that happen to point the same way.
    #
    # It stopped earning its place: of the nine confirmed bad tokens in the labelled set,
    # eight came from the snapshot archive and one from the pool pages. Keyword search
    # contributed none -- it returns pairs that are currently indexed and trading, which
    # is the same survivorship problem the archive was built to escape.
    #
    # And the engine now needs that endpoint for impersonation detection. Sampling from
    # it would not make the labels circular -- labels come from OHLCV and GoPlus, not from
    # search -- but the disjointness assertion does not model that distinction, and
    # loosening a guard so it stops objecting to something we want to do is how guards
    # die. Dropping the weaker sampling source is the cheaper side of that trade.
    return _compose(buckets, limit)


def _compose(buckets, limit):
    """Fill each source's quota, then hand any shortfall to the sources that have more.

    Written as an explicit second pass rather than "collect and truncate" because the
    truncating version silently deleted a whole source, and it did so without changing
    any number in the report that would have given it away.
    """
    out, leftovers = [], {}
    for name, share in SOURCE_QUOTA.items():
        rows = buckets.get(name) or []
        want = int(limit * share)
        out.extend(rows[:want])
        leftovers[name] = rows[want:]

    for name in SOURCE_QUOTA:
        if len(out) >= limit:
            break
        out.extend(leftovers[name][:limit - len(out)])

    got = {}
    for c in out:
        key = c["source"].split("_")[0]
        got[key] = got.get(key, 0) + 1
    print("  sampled %d candidates: %s"
          % (len(out), ", ".join("%s=%d" % kv for kv in sorted(got.items()))))
    return out


def _from_backfill(add, seen, cap):
    """Add launches recovered from chain history by bench/backfill.py.

    Read round-robin across the day files rather than one file at a time. Reading in
    order would make a cap mean "the oldest day and nothing else", which quietly turns a
    request for a diverse sample into a request for one Tuesday in June -- and any
    market-wide event that day would then look like a property of tokens in general.
    """
    if cap <= 0 or not os.path.isdir(BACKFILL_DIR):
        return
    days = []
    for fn in sorted(os.listdir(BACKFILL_DIR)):
        if not (fn.startswith("pools-") and fn.endswith(".ndjson")):
            continue
        rows = []
        with open(os.path.join(BACKFILL_DIR, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if rows:
            days.append((fn[6:16], rows))
    if not days:
        return

    before = len(seen)
    for i in range(max(len(r) for _, r in days)):
        if len(seen) - before >= cap:
            break
        for stamp, rows in days:
            if i >= len(rows) or len(seen) - before >= cap:
                continue
            r = rows[i]
            bt = r.get("base_token") or ""
            addr = bt.split("_", 1)[1] if "_" in bt else ""
            if not addr.startswith("0x"):
                continue
            add({"address": addr,
                 "symbol": r.get("name") or "",
                 "chain": _GT_TO_CHAIN.get(r.get("chain"), r.get("chain")),
                 "pool": r.get("pool_address"),
                 "source": "backfill_%s" % stamp})
    print("  chain history contributed %d candidates across %d days"
          % (len(seen) - before, len(days)))


def _from_snapshots(add, seen):
    """Add tokens recorded by bench/snapshot.py on previous days."""
    snap_dir = os.path.join(HERE, "snapshots")
    if not os.path.isdir(snap_dir):
        return
    before = len(seen)
    days = []
    for fn in sorted(os.listdir(snap_dir)):
        if not (fn.startswith("pools-") and fn.endswith(".ndjson")):
            continue
        rows = []
        with open(os.path.join(snap_dir, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if rows:
            days.append((fn[6:16], rows))

    # Interleaved across days, not read day by day.
    #
    # The quota downstream takes a prefix of whatever this returns, so appending one
    # whole day before starting the next meant the archive's entire contribution came
    # from its oldest file. Every extra day the snapshot job collects would have been
    # invisible to the benchmark -- a daily job whose output silently stopped mattering
    # after the first day, which is the kind of thing that is only ever noticed by
    # someone wondering why a growing archive changes nothing.
    for i in range(max(len(r) for _, r in days) if days else 0):
        for stamp, rows in days:
            if i >= len(rows):
                continue
            r = rows[i]
            bt = r.get("base_token") or ""
            addr = bt.split("_", 1)[1] if "_" in bt else ""
            if not addr.startswith("0x"):
                continue  # EVM only; the GoPlus labeler does not cover Solana
            add({"address": addr,
                 "symbol": (r.get("name") or "").split("/")[0].strip(),
                 "chain": _GT_TO_CHAIN.get(r.get("chain"), r.get("chain")),
                 "pool": r.get("pool_address"),
                 "source": "snapshot_%s" % stamp})
    print("  snapshot archive contributed %d candidates across %d days"
          % (len(seen) - before, len(days)))


def label_one(c):
    """Apply both label sets to one candidate. Returns a dict, or None if neither stuck."""
    net = GT_NETWORK[c["chain"]]
    ohlcv = fetch_json(
        # limit=1000, not 180. A pool harvested from 300 days ago had its entire active
        # life outside a 180-day window, so the labeller saw a flat tail and called it
        # unlabelled -- the tokens furthest back, which are the ones whose outcome is
        # most certainly resolved, were the ones it could say least about.
        "https://api.geckoterminal.com/api/v2/networks/%s/pools/%s/ohlcv/day?limit=1000"
        % (net, c["pool"]), role="label")
    lst = (((ohlcv or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    o_label, o_facts = outcome_label(lst)

    gp = fetch_json("https://api.gopluslabs.io/api/v1/token_security/%s?contract_addresses=%s"
                    % (GOPLUS_CHAIN_ID[c["chain"]], c["address"]), role="label")
    # The recent-volume figure comes from OHLCV we already fetched, so no new endpoint
    # and no risk to the disjointness assertion. It exists to tell the contract oracle
    # whether its own honeypot simulation could have run at all.
    g_label, g_reasons, g_raw = goplus_label(
        gp, c["address"], recent_volume_7d=(o_facts or {}).get("recent_volume_7d"))

    if o_label is None and g_label is None:
        return None
    return {
        "address": c["address"], "symbol": c["symbol"], "chain": c["chain"],
        "pool": c["pool"], "sampled_from": c["source"],
        "outcome_label": o_label, "outcome_facts": o_facts,
        "goplus_label": g_label, "goplus_reasons": g_reasons, "goplus_raw": g_raw,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250,
                    help="cap on candidates actually labeled (fewer will come back labeled)")
    args = ap.parse_args()

    print("Sampling candidates ...")
    cands = collect_candidates(args.limit)
    cands = cands[: args.limit]
    print("%d candidates, labeling now (slow the first time, cached after)" % len(cands))

    # Rate limits are counted per host, so let requests to different hosts run in parallel --
    # serially each candidate costs ~5s (2.1s queued on GT + 2.1s on GoPlus); in parallel it
    # converges on the throttle ceiling of a single host.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(label_one, c): c for c in cands}
        for fut in as_completed(futs):
            done += 1
            c = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                print("  %s failed to label: %s" % (c.get("symbol"), e))
                r = None
            if r:
                rows.append(r)
            if done % 20 == 0 or done == len(cands):
                print("  [%d/%d] labeled %d" % (done, len(cands), len(rows)), flush=True)

    from collections import Counter
    oc = Counter(r["outcome_label"] for r in rows if r["outcome_label"])
    gc = Counter(r["goplus_label"] for r in rows if r["goplus_label"])
    print("\nLabeling results:")
    print("  outcome:", dict(oc))
    print("  goplus :", dict(gc))

    rows.sort(key=lambda r: (r["chain"], r["address"].lower()))  # fixed order
    with open(DATASET, "w", encoding="utf-8") as f:
        json.dump({"tokens": rows,
                   "counts": {"outcome": dict(oc), "goplus": dict(gc)}},
                  f, ensure_ascii=False, indent=1)

    # Hand the labeling side's endpoint list to run_benchmark.py, which runs in a
    # separate process. Without this its label set is empty, engine n {} is always {},
    # and the disjointness assertion passes without ever testing anything.
    persist_access_log()

    print("\nWrote %s (%d rows)" % (DATASET, len(rows)))


if __name__ == "__main__":
    main()
