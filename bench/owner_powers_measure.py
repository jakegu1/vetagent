"""owner_powers_measure.py — how much of an owner power the bytecode scan actually sees.

WHY THIS FILE EXISTS

W1 was closed as "the powers do not discriminate, so do not score them". An external
audit could not reproduce the measurement behind that conclusion, and it was right not
to be able to: no script was ever committed, none was committed-then-deleted
(`git log --diff-filter=D` over the range is empty), and no bytecode was cached
(`grep -l '"result": *"0x6' bench/cache/*.json` matched 0 of 4,845 files). It is the one
measurement in this repository that cannot be re-run, and it is a **negative** result
used to justify not building something. That is the worst possible combination.

The audit went further and showed the published table does not come from the shipped
selector list at all: recomputing the pausable row over the same cohorts gives 0/3/0/6%
against a published 11/5/3/9%, and brute-forcing what would reproduce the published
numbers lands on `enableTrading()` + `openTrading()` -- neither of which is in
`_OWNER_POWERS`.

TWO THINGS THIS SCRIPT DOES DIFFERENTLY

1. It caches the bytecode it fetches, so the next person can re-run it for free and get
   the same answer. A measurement nobody can repeat is an anecdote.

2. It measures against GoPlus's **per-flag fields** -- `is_blacklisted`,
   `transfer_pausable`, `slippage_modifiable`, `is_mintable` -- and not against the
   derived cohort labels. This is the part that invalidated the original conclusion.
   `goplus_label()` routes any token carrying one of those flags into `centralized`, so
   such a token can never appear in `safe`. "0% of the safe cohort has a blacklist" was
   not a finding about tokens; it was the label definition restated. Measured against the
   flags themselves, the question becomes answerable: of the contracts GoPlus says hold
   this power, how many does our scan find?

WHAT IT CANNOT SETTLE

Recall against GoPlus is not recall against reality -- GoPlus is itself an instrument
with its own misses, and it is the benchmark's held-out oracle (B2), so this must never
be wired into the engine. It bounds the scan's blindness from one direction only: a
power GoPlus sees and we miss is definitely a miss.

Usage:
    python bench/owner_powers_measure.py            # cached only, no network
    python bench/owner_powers_measure.py --fetch    # fill the cache, then measure
    python bench/owner_powers_measure.py --fetch --limit 100
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import risk  # noqa: E402
from keccak import selector  # noqa: E402

DATASET = os.path.join(HERE, "dataset.json")
CODE_CACHE = os.path.join(HERE, "cache_bytecode")

# Same public endpoints the engine uses. One eth_getCode per contract, cached forever --
# bytecode at an address does not change.
RPC = {
    "ethereum": "https://rpc.mevblocker.io",
    "base": "https://mainnet.base.org",
    "bsc": "https://bsc-dataseed.bnbchain.org",
}

# GoPlus's own per-flag fields, mapped to the power names _powers_from_code reports.
# Deliberately NOT the derived `centralized`/`safe` labels: those are computed FROM these
# flags, so measuring against them asks whether a definition is a definition.
FLAG_TO_POWER = {
    "transfer_pausable": "can pause transfers",
    "is_blacklisted": "can blacklist addresses",
    "slippage_modifiable": "can change the tax",
    "is_mintable": "can mint new supply",
}

# Selectors the audit found missing, computed rather than pinned. Reported separately so
# the effect of adding them is visible instead of silently folded into the headline.
CANDIDATE_EXTRA = {
    "can blacklist addresses": [
        "isBlacklisted(address)",        # the OpenZeppelin-style getter
        "blacklist(address,bool)",
        "blacklists(address)",
        "addBlackList(address)",
    ],
    "can change the tax": [
        "updateBuyFees(uint256,uint256,uint256)",
        "updateSellFees(uint256,uint256,uint256)",
        "setParams(uint256,uint256)",    # USDT's fee setter
        "setFees(uint256,uint256)",
    ],
    "can mint new supply": [
        "issue(uint256)",                # USDT's mint
    ],
    "can pause transfers": [
        "enableTrading()",
        "openTrading()",
    ],
}


def cache_path(chain, address):
    return os.path.join(CODE_CACHE, "%s_%s.json" % (chain, address.lower()))


def cached_code(chain, address):
    p = cache_path(chain, address)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("code")
    except Exception:                                        # noqa: BLE001
        return None


def fetch_code(chain, address, timeout=20):
    """One eth_getCode. Returns hex string, or None on any failure."""
    url = RPC.get(chain)
    if not url:
        return None
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                       "params": [address, "latest"]}).encode("utf-8")
    # A User-Agent is not optional: rpc.mevblocker.io answers 403 without one, which is
    # how the first run of this script cached zero of two hundred contracts.
    req = urllib.request.Request(
        url, data=body, headers={"content-type": "application/json",
                                 "user-agent": "vetagent-bench/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (json.loads(resp.read().decode("utf-8")) or {}).get("result")
    except Exception:                                        # noqa: BLE001
        return None


def wilson(hits, n, z=1.96):
    """95% Wilson interval for a proportion, as (low, high) percentages.

    Printed beside every recall figure because the small denominators here are the whole
    story: 0 of 3 and 0 of 19 are both "0.0%", and only one of them supports a claim.
    Wilson rather than normal-approximation because the counts are small and the
    proportions sit at the boundary, where the normal approximation gives intervals that
    include impossible values.
    """
    if not n:
        return (0.0, 100.0)
    p = float(hits) / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, centre - half) * 100.0, min(1.0, centre + half) * 100.0)


def load_tokens():
    with open(DATASET, encoding="utf-8") as f:
        return [t for t in (json.load(f).get("tokens") or [])
                if t.get("goplus_raw") and t.get("chain") in RPC]


def _flag_count(token):
    raw = token.get("goplus_raw") or {}
    return sum(1 for f in FLAG_TO_POWER if str(raw.get(f) or "0") == "1")


def fill_cache(tokens, limit):
    """Fetch the contracts that carry a power first, and every chain, not file order.

    The first 250 contracts this script cached were taken in dataset order. The dataset
    is 83% Base, so the cache was 83% Base -- and worse, recall's denominator is the
    POSITIVES, of which it caught 3 of 19 pausable and 7 of 19 blacklist. "Effectively
    blind on two of four powers" was then published on n=3. Zero of three has a 95%
    upper bound near 0.7: it is compatible with finding two thirds of them.

    A contract GoPlus flags is worth a hundred it does not, for this question. Ordering
    by flag count costs nothing and moves every denominator to the whole population.
    """
    os.makedirs(CODE_CACHE, exist_ok=True)
    uncached = [t for t in tokens if cached_code(t["chain"], t["address"]) is None]
    uncached.sort(key=lambda t: (-_flag_count(t), t["chain"]))
    todo = uncached[:limit]
    print("fetching bytecode for %d contracts (%d cached, %d still missing after this)"
          % (len(todo), len(tokens) - len(uncached), len(uncached) - len(todo)))
    got = 0
    for i, t in enumerate(todo, 1):
        code = fetch_code(t["chain"], t["address"])
        if code:
            with open(cache_path(t["chain"], t["address"]), "w", encoding="utf-8") as f:
                json.dump({"chain": t["chain"], "address": t["address"], "code": code}, f)
            got += 1
        if i % 25 == 0:
            print("  [%d/%d] %d cached" % (i, len(todo), got))
        time.sleep(0.12)
    print("cached %d of %d" % (got, len(todo)))


def measure(tokens, extra=False):
    """Per-power recall against GoPlus's own flags."""
    rows = []
    for t in tokens:
        code = cached_code(t["chain"], t["address"])
        if not code or len(code) < 10:
            continue
        info = risk._powers_from_code(code)
        if not info:
            continue
        found = set(info["powers"])
        if extra:
            body = code[2:].lower()
            for power, sigs in CANDIDATE_EXTRA.items():
                if any(selector(sig) in body for sig in sigs):
                    found.add(power)
        rows.append((t, found, info))
    return rows


def report(rows, title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print("contracts with cached bytecode: %d" % len(rows))
    if not rows:
        print("Nothing to measure. Run with --fetch first.")
        return
    proxies = [r for r in rows if r[2].get("is_proxy")]
    print("of which proxies (behaviour lives elsewhere, so a miss is expected): %d"
          % len(proxies))
    print()
    print("%-24s %-10s %-10s %-8s %s" % ("power (GoPlus flag)", "GoPlus says", "we find",
                                        "recall", "95% CI"))
    print("-" * 74)
    for flag, power in sorted(FLAG_TO_POWER.items()):
        have = [r for r in rows if str((r[0].get("goplus_raw") or {}).get(flag)) == "1"]
        hit = [r for r in have if power in r[1]]
        rate = (100.0 * len(hit) / len(have)) if have else 0.0
        lo, hi = wilson(len(hit), len(have))
        print("%-24s %-10d %-10d %5.1f%%   %4.1f%% - %4.1f%%"
              % (flag, len(have), len(hit), rate, lo, hi))
    print("  The interval is the point of this table. An earlier run of this script")
    print("  cached the first 250 contracts in dataset order, which is 83% Base, and")
    print("  caught 3 of the 19 pausable contracts. It reported 0.0% recall, and")
    print("  \"effectively blind on two of four powers\" was published from it. 0 of 3")
    print("  has a 95% upper bound near 71%: it is compatible with finding most of them.")
    print()
    # The other direction: how often do we claim a power GoPlus does not see?
    print("%-24s %-10s %-10s" % ("power", "we claim", "GoPlus agrees"))
    print("-" * 60)
    for flag, power in sorted(FLAG_TO_POWER.items()):
        ours = [r for r in rows if power in r[1]]
        agree = [r for r in ours
                 if str((r[0].get("goplus_raw") or {}).get(flag)) == "1"]
        print("%-24s %-10d %-10d" % (power, len(ours), len(agree)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch", action="store_true", help="fill the bytecode cache")
    ap.add_argument("--limit", type=int, default=600)
    args = ap.parse_args()

    tokens = load_tokens()
    print("dataset contracts on chains with an RPC: %d" % len(tokens))
    if args.fetch:
        fill_cache(tokens, args.limit)

    report(measure(tokens, extra=False), "SHIPPED selector list (src/risk.py)")
    report(measure(tokens, extra=True),
           "SHIPPED + the selectors the audit identified as missing")
    print("\nRecall against GoPlus is not recall against reality: GoPlus has its own")
    print("misses, and it is the held-out oracle (B2), so none of this may be wired into")
    print("the engine. It bounds the scan's blindness from one side -- a power GoPlus")
    print("sees and we do not is definitely a miss.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
