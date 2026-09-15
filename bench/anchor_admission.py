"""anchor_admission.py -- W43: re-measure anchor candidates under E21's unchanged rule.

Usage:
    python bench/anchor_admission.py        # live DexScreener, print, write bench/anchor_admission/<date>.json

The rule (src/risk.py, the comment above _ANCHORS; DECISIONS E21), set 2026-09-14 before any
candidate was measured: beyond natives, stablecoins and bridged majors, an asset is admitted
when, on its own chain, its pools whose OTHER side is already an anchor hold more than $10M,
read from live DexScreener (at most 30 pools returned, so the figure is a floor).

What the 2026-09-14 measurement left unwritten, and this file fixes BEFORE its first run: which
number "hold" is. DexScreener's stated `liquidity.usd` and the depth E21 credits (twice the
anchor side) differ -- the cached VIRTUAL pools state $9.26M and credit $8.18M, and the
refusal recorded $8.5M, which is neither. So an asset is admitted only if BOTH exceed $10M:
a measurement that straddles the bar keeps the refusal. The bar itself does not move.

A GeckoTerminal listing is read as a cross-check and printed; it decides nothing, because
the rule names DexScreener and GeckoTerminal carries no reserve amounts.

Admitted non-core anchors are re-read too, and reported, never removed by this script: the
rule is an admission rule, and dropping an anchor is a separate decision.
"""

import datetime
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import risk  # noqa: E402

BAR_USD = 10_000_000

# Refused 2026-09-14 (addresses read from bench/cache DexScreener pairs, where each appears
# under the symbol, 90-149 times). FDUSD on BSC is resolved live by symbol and printed.
REFUSED = [
    ("base", "VIRTUAL", "0x0b3e328455c4059eeb9e3f84b5543f74e24e7e1b"),
    ("base", "ADS", "0xb20a4bd059f5914a2f8b9c18881c637f79efb7df"),
    ("bsc", "NVDAB", "0x02fca66c1d1afb4e2a7884261eb00f63598a7436"),
]
ADMITTED = [
    ("ethereum", "PYUSD", "0x6c3ea9036406852006290770bedfcaba0e23a0e8"),
    ("ethereum", "RLUSD", "0x8292bb45bf1ee4d140127049757c2e0ff06317ed"),
    ("ethereum", "USDe", "0x4c9edd5852cd905f086c759e8383e09bff1e68b3"),
    ("ethereum", "SKY", "0x56072c95faa701256059aa122697b133aded9279"),
    ("ethereum", "crvUSD", "0xf939e0a03fb07f59a73314e73794be0e57ac1b4e"),
    ("ethereum", "wstETH", "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"),
    ("ethereum", "USDS", "0xdc035d45d973e3ec169d2276ddab16f1e407384f"),
    ("base", "AERO", "0x940181a94a35a4569e4529a3cdfb74e38fd98631"),
    ("bsc", "BTCB", "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c"),
]
GT_NETWORK = {"ethereum": "eth", "base": "base", "bsc": "bsc"}


def get(url):
    req = urllib.request.Request(url, headers={"user-agent": "vetagent-research/0.1",
                                               "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        out = {"transport_error": str(e)[:160]}
    time.sleep(1.2)
    return out


def resolve_fdusd_bsc():
    out = get("https://api.dexscreener.com/latest/dex/search?q=FDUSD")
    best = {}
    for p in out.get("pairs") or []:
        if p.get("chainId") != "bsc":
            continue
        for side in ("baseToken", "quoteToken"):
            t = p.get(side) or {}
            if t.get("symbol") == "FDUSD":
                a = t["address"].lower()
                best[a] = best.get(a, 0) + risk._num((p.get("liquidity") or {}).get("usd"))
    if not best:
        return None
    return max(best.items(), key=lambda kv: kv[1])[0]


def measure(chain, symbol, address):
    anchors = risk._ANCHORS[chain]
    ds = get("https://api.dexscreener.com/latest/dex/tokens/%s" % address)
    rec = {"chain": chain, "symbol": symbol, "address": address}
    if "transport_error" in ds:
        rec["error"] = ds["transport_error"]
        return rec
    pairs = ds.get("pairs") or []
    stated = credited = 0.0
    n_anchored = 0
    for p in pairs:
        if (p.get("chainId") or "").lower() != chain:
            continue
        base = ((p.get("baseToken") or {}).get("address") or "").lower()
        quote = ((p.get("quoteToken") or {}).get("address") or "").lower()
        other = quote if base == address else base if quote == address else None
        if other is None or other == address or other not in anchors:
            continue
        n_anchored += 1
        stated += risk._num((p.get("liquidity") or {}).get("usd"))
        credited += risk._reported_liquidity(p) or 0.0
    rec.update(pairs_returned=len(pairs), capped_at_30=len(pairs) >= 30,
               anchored_pools=n_anchored, anchored_stated_usd=round(stated),
               anchored_credited_usd=round(credited),
               passes=stated > BAR_USD and credited > BAR_USD)
    gt = get("https://api.geckoterminal.com/api/v2/networks/%s/tokens/%s/pools?page=1"
             % (GT_NETWORK[chain], address))
    gt_sum, gt_n = 0.0, 0
    for pool in (gt.get("data") or []):
        pair = risk._gt_to_pair(pool, address, GT_NETWORK[chain])
        base = (pair["baseToken"]["address"] or "").lower()
        quote = (pair["quoteToken"]["address"] or "").lower()
        other = quote if base == address else base if quote == address else None
        if other and other in anchors:
            gt_n += 1
            gt_sum += risk._num((pair.get("liquidity") or {}).get("usd"))
    rec.update(crosscheck_geckoterminal_anchored_pools=gt_n,
               crosscheck_geckoterminal_anchored_usd=round(gt_sum),
               crosscheck_error=gt.get("transport_error"))
    return rec


def main():
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    refused = list(REFUSED)
    fdusd = resolve_fdusd_bsc()
    if fdusd:
        refused.append(("bsc", "FDUSD", fdusd))
    else:
        print("FDUSD on BSC could not be resolved; not measured")
    out = {"day": day, "bar_usd": BAR_USD,
           "rule": "src/risk.py _ANCHORS comment; admission needs stated AND credited > bar",
           "refused_2026_09_14": [], "admitted_reread": []}
    for key, items in (("refused_2026_09_14", refused), ("admitted_reread", ADMITTED)):
        for chain, symbol, address in items:
            rec = measure(chain, symbol, address)
            out[key].append(rec)
            print("%-9s %-8s %-7s stated $%12s credited $%12s pools %s/%s capped=%s passes=%s  gt $%s"
                  % (key[:9], chain, symbol, format(rec.get("anchored_stated_usd", 0), ","),
                     format(rec.get("anchored_credited_usd", 0), ","), rec.get("anchored_pools"),
                     rec.get("pairs_returned"), rec.get("capped_at_30"), rec.get("passes"),
                     format(rec.get("crosscheck_geckoterminal_anchored_usd", 0), ",")))
    os.makedirs(os.path.join(HERE, "anchor_admission"), exist_ok=True)
    path = os.path.join(HERE, "anchor_admission", "%s.json" % day)
    json.dump(out, io.open(path, "w", encoding="utf-8"), indent=1)
    print("wrote %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
