"""test_upstream_contract.py — upstream API contract tests (hits the real network).

Why this exists: VetAgent's worst production bug was reading isHoneypot out of
simulationResult when upstream actually puts it in honeypotResult — we read a key
that does not exist upstream, got None, treated it as False, and so the honeypot
check **always passed**. No offline test could have caught it.

What this file asserts: every JSON path we depend on really is present in a live
upstream response. It goes red when a third party has an outage, and that is
deliberate — if upstream renames a field we want to know immediately.

Run:  python tests/test_upstream_contract.py
"""

import json
import subprocess
import sys

TIMEOUT = "30"
UA = "vetagent-contract-test"

# Stable reference tokens
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def get(url):
    r = subprocess.run(["curl", "-s", "-m", TIMEOUT, "-A", UA, url],
                       capture_output=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def path_exists(obj, *keys):
    """Check that a JSON path exists (the value may be null, but the key must be there)."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def test_dexscreener():
    print("\n[upstream] DexScreener /latest/dex/tokens")
    d = get("https://api.dexscreener.com/latest/dex/tokens/%s" % WETH)
    pairs = d.get("pairs") or []
    check("returns a pairs array", bool(pairs), "got %d" % len(pairs))
    if not pairs:
        return
    p = pairs[0]
    for key in ("chainId", "dexId", "baseToken", "quoteToken", "priceUsd",
                "volume", "liquidity", "pairCreatedAt"):
        check("pair has %s" % key, key in p, str(sorted(p.keys())))
    check("baseToken.address present", path_exists(p, "baseToken", "address"), "")
    check("liquidity.usd present", path_exists(p, "liquidity", "usd"), "")
    check("volume.h24 present", path_exists(p, "volume", "h24"), "")
    # This is exactly P0-D: the code used to assume this was an ISO string
    check("pairCreatedAt is a number (milliseconds)",
          isinstance(p.get("pairCreatedAt"), (int, float)),
          "actual type %s" % type(p.get("pairCreatedAt")).__name__)


def test_honeypot_is():
    print("\n[upstream] honeypot.is /v2/IsHoneypot")
    d = get("https://api.honeypot.is/v2/IsHoneypot?address=%s" % WETH)
    check("response is non-empty", bool(d), "")
    if not d:
        return
    # ---- The core regression: where isHoneypot actually lives ----
    check("honeypotResult.isHoneypot present",
          path_exists(d, "honeypotResult", "isHoneypot"),
          "top-level keys: %s" % sorted(d.keys()))
    sim = d.get("simulationResult") or {}
    check("simulationResult does NOT have isHoneypot (wrong place reads False forever)",
          "isHoneypot" not in sim, "simulationResult keys: %s" % sorted(sim.keys()))
    # ---- The rest of the fields we depend on ----
    for key in ("summary", "simulationSuccess", "simulationResult", "contractCode", "token"):
        check("top level has %s" % key, key in d, str(sorted(d.keys())))
    check("summary.risk present", path_exists(d, "summary", "risk"), "")
    check("summary.flags is an array",
          isinstance((d.get("summary") or {}).get("flags"), list), "")
    for key in ("buyTax", "sellTax", "transferTax"):
        check("simulationResult has %s" % key, key in sim, str(sorted(sim.keys())))
    check("contractCode.openSource present",
          path_exists(d, "contractCode", "openSource"), "")
    check("token.totalHolders present", path_exists(d, "token", "totalHolders"), "")

    risk_val = (d.get("summary") or {}).get("risk")
    check("summary.risk is one of the known values",
          risk_val in ("low", "medium", "high", "very_high", "unknown", None),
          "actual %r" % risk_val)


def test_geckoterminal():
    print("\n[upstream] GeckoTerminal")
    d = get("https://api.geckoterminal.com/api/v2/networks/eth/tokens/%s/pools" % WETH)
    pools = d.get("data") or []
    check("tokens/{a}/pools returns data", bool(pools), "got %d" % len(pools))
    if pools:
        a = (pools[0].get("attributes") or {})
        for key in ("reserve_in_usd", "pool_created_at", "volume_usd", "name"):
            check("pool attributes have %s" % key, key in a, str(sorted(a.keys()))[:200])
        # base_token_price_usd is null more often than not; derive price from these two
        check("price is derivable (base_token_price_quote_token + quote_token_price_usd)",
              "base_token_price_quote_token" in a and "quote_token_price_usd" in a,
              str(sorted(a.keys()))[:200])
        check("pool_created_at is an ISO string",
              isinstance(a.get("pool_created_at"), str),
              "actual %r" % a.get("pool_created_at"))

    n = get("https://api.geckoterminal.com/api/v2/networks/solana/new_pools")
    check("new_pools returns data", bool(n.get("data")), "")
    t = get("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools")
    check("trending_pools returns data", bool(t.get("data")), "")


def test_rugcheck():
    print("\n[upstream] RugCheck (Solana)")
    d = get("https://api.rugcheck.xyz/v1/tokens/%s/report" % BONK)
    if not d:
        check("RugCheck reachable", False, "no response; Solana degrades to unknown")
        return
    check("RugCheck reachable", True)
    check("has a score field", "score" in d, str(sorted(d.keys()))[:200])
    check("risks is an array or absent",
          d.get("risks") is None or isinstance(d.get("risks"), list), "")


def main():
    print("=" * 68)
    print("VetAgent upstream contract tests (live network)")
    print("=" * 68)
    for fn in (test_dexscreener, test_honeypot_is, test_geckoterminal, test_rugcheck):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures (upstream may have changed a field; risk.py has to change too):")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
