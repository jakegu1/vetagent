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
import os
import subprocess
import time
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



def test_simulator_chain_coverage():
    """The chains we believe the sell simulator covers are the ones it actually covers.

    `src/risk.py` hardcodes three, and uses that list to decide whether a 404 is a fact
    about the token or a gap in our own coverage. If honeypot.is adds a chain and the list
    does not, the engine goes on declining to check it forever and blaming its own
    coverage -- politely, and wrongly. If it drops one, the engine starts telling users a
    healthy token has no record anywhere.

    Both directions are checked. A hardcoded list that nothing compares against the world
    is a belief, not a fact.
    """
    print("\n[coverage] honeypot.is supports exactly the chains we think it does")
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "src"))
    import risk  # noqa: E402

    # A real, liquid token on each chain the tool advertises as a chain_hint.
    PROBE = {
        "ethereum": (1, "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        "bsc": (56, "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
        "base": (8453, "0x4200000000000000000000000000000000000006"),
        "arbitrum": (42161, "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"),
        "polygon": (137, "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"),
        "optimism": (10, "0x4200000000000000000000000000000000000006"),
        "avalanche": (43114, "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"),
    }

    answers = {}
    for name, (cid, addr) in PROBE.items():
        body = get("https://api.honeypot.is/v2/IsHoneypot?address=%s&chainID=%d"
                   % (addr, cid))
        answers[name] = bool(body and "honeypotResult" in body)
        time.sleep(2.0)

    reachable = [n for n, ok in answers.items() if ok]
    check("at least the three we rely on answer",
          all(answers.get(n) for n in ("ethereum", "bsc", "base")),
          str(answers))

    believed = set(risk._SIMULATOR_CHAIN_IDS)
    actual = set(reachable)
    check("nothing we rely on has been dropped", believed <= actual,
          "we believe %s, it answers %s" % (sorted(believed), sorted(actual)))
    check("nothing new is being refused for no reason", actual <= believed,
          "it now also answers %s -- add it to _SIMULATOR_CHAIN_IDS"
          % sorted(actual - believed))

    # The ids themselves have to be right, or we would be asking about the wrong chain.
    for name, (cid, _addr) in PROBE.items():
        if name in risk._SIMULATOR_CHAIN_IDS:
            check("%s maps to chain id %d" % (name, cid),
                  risk._SIMULATOR_CHAIN_IDS[name] == cid,
                  str(risk._SIMULATOR_CHAIN_IDS.get(name)))

def main():
    print("=" * 68)
    print("VetAgent upstream contract tests (live network)")
    print("=" * 68)
    for fn in (test_dexscreener, test_honeypot_is, test_geckoterminal, test_rugcheck,
               test_simulator_chain_coverage):
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
