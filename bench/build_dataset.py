"""build_dataset.py — sample candidate tokens and label them with independent labelers.

Usage:
    python bench/build_dataset.py --limit 40          # smoke run
    python bench/build_dataset.py --limit 300         # real build

Sampling deliberately runs down two paths, so the set is not just tokens that are
obviously fine at a glance:
  head  GeckoTerminal per-chain pool pages  -- skews healthy
  tail  DexScreener keyword search          -- skews junk / dead

The labelers live in labels.py and only hit endpoints the engine never reads.
Writes bench/dataset.json.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_json, persist_access_log  # noqa: E402
from labels import GOPLUS_CHAIN_ID, GT_NETWORK, goplus_label, outcome_label  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")

# Tail sampling keywords: memecoin naming is highly homogeneous, so these words drag in
# plenty of low-quality tokens.
# The list is deliberately large -- a smoke run of 50 candidates turned up exactly 1 dead,
# nowhere near enough samples.
# This **does not filter on current liquidity**. Fishing for dead tokens by "liquidity is
# low right now" would be more efficient, but that picks the samples by the engine's own
# criterion, which makes recall in the full-signal column meaningless.
TAIL_TERMS = [
    "inu", "pepe", "moon", "elon", "safe", "baby", "doge", "shib", "ai",
    "trump", "cat", "gold", "meta", "floki", "rocket", "chad", "wojak",
    "bonk", "wif", "grok", "x", "swap", "token", "coin", "finance", "protocol",
    "dao", "yield", "farm", "stake", "bull", "bear", "ape", "frog", "dog",
    "king", "queen", "star", "sun", "fire", "ice", "cyber", "quantum", "neuro",
    "agent", "bot", "gpt", "llm", "eth", "btc", "sol", "based", "degen",
]
HEAD_CHAINS = ["ethereum", "base", "bsc"]


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
    out, seen = [], set()

    def add(c):
        if not c.get("address") or not c.get("pool") or not c.get("chain"):
            return
        if c["chain"] not in GT_NETWORK or c["chain"] not in GOPLUS_CHAIN_ID:
            return  # EVM only: the GoPlus labeler does not cover Solana
        key = (c["chain"], c["address"].lower())
        if key in seen:
            return
        seen.add(key)
        out.append(c)

    # Head: page through each chain
    for chain in HEAD_CHAINS:
        net = GT_NETWORK[chain]
        for page in range(1, 11):
            if len(out) >= limit:
                break
            d = fetch_json("https://api.geckoterminal.com/api/v2/networks/%s/pools?page=%d"
                           % (net, page), role="label")
            for p in ((d or {}).get("data") or []):
                a = p.get("attributes") or {}
                rel = p.get("relationships") or {}
                bt = ((rel.get("base_token") or {}).get("data") or {}).get("id", "")
                addr = bt.split("_", 1)[1] if "_" in bt else ""
                add({"address": addr, "symbol": (a.get("name") or "").split("/")[0].strip(),
                     "chain": chain, "pool": a.get("address"), "source": "gt_pools"})

    # Tail: keyword search. Run every term -- the tail is where the dead samples come from.
    for term in TAIL_TERMS:
        d = fetch_json("https://api.dexscreener.com/latest/dex/search?q=%s" % term,
                       role="label")
        for p in ((d or {}).get("pairs") or []):
            add(_norm_pair(p))

    return out


def label_one(c):
    """Apply both label sets to one candidate. Returns a dict, or None if neither stuck."""
    net = GT_NETWORK[c["chain"]]
    ohlcv = fetch_json(
        "https://api.geckoterminal.com/api/v2/networks/%s/pools/%s/ohlcv/day?limit=180"
        % (net, c["pool"]), role="label")
    lst = (((ohlcv or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    o_label, o_facts = outcome_label(lst)

    gp = fetch_json("https://api.gopluslabs.io/api/v1/token_security/%s?contract_addresses=%s"
                    % (GOPLUS_CHAIN_ID[c["chain"]], c["address"]), role="label")
    g_label, g_reasons, g_raw = goplus_label(gp, c["address"])

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
    print("\nWrote %s (%d rows)" % (DATASET, len(rows)))


if __name__ == "__main__":
    main()
