"""test_upstream_contract.py — 上游 API 契约测试（会真实联网）。

存在的理由：VetAgent 最严重的一次线上缺陷是
「代码从 simulationResult 里读 isHoneypot，而上游把它放在 honeypotResult 里」——
读了一个上游根本不存在的键，返回 None，被当成 False，
于是 honeypot 检测**恒为通过**，而所有离线测试都发现不了。

这个文件断言的是：我们依赖的每一条 JSON 路径，在真实上游响应里确实存在。
它会因为第三方故障而变红，这是有意为之——上游改了字段就该立刻知道。

运行：  python tests/test_upstream_contract.py
"""

import json
import subprocess
import sys

TIMEOUT = "30"
UA = "vetagent-contract-test"

# 稳定的参照代币
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
    """检查一条 JSON 路径是否存在（值可以是 null，但键必须在）。"""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def test_dexscreener():
    print("\n[上游] DexScreener /latest/dex/tokens")
    d = get("https://api.dexscreener.com/latest/dex/tokens/%s" % WETH)
    pairs = d.get("pairs") or []
    check("返回 pairs 数组", bool(pairs), "拿到 %d 个" % len(pairs))
    if not pairs:
        return
    p = pairs[0]
    for key in ("chainId", "dexId", "baseToken", "quoteToken", "priceUsd",
                "volume", "liquidity", "pairCreatedAt"):
        check("pair 含 %s" % key, key in p, str(sorted(p.keys())))
    check("baseToken.address 存在", path_exists(p, "baseToken", "address"), "")
    check("liquidity.usd 存在", path_exists(p, "liquidity", "usd"), "")
    check("volume.h24 存在", path_exists(p, "volume", "h24"), "")
    # 这一条正是 P0-D：代码曾假设它是 ISO 字符串
    check("pairCreatedAt 是数字（毫秒）",
          isinstance(p.get("pairCreatedAt"), (int, float)),
          "实际类型 %s" % type(p.get("pairCreatedAt")).__name__)


def test_honeypot_is():
    print("\n[上游] honeypot.is /v2/IsHoneypot")
    d = get("https://api.honeypot.is/v2/IsHoneypot?address=%s" % WETH)
    check("返回非空", bool(d), "")
    if not d:
        return
    # ---- 核心回归：isHoneypot 的真实位置 ----
    check("honeypotResult.isHoneypot 存在",
          path_exists(d, "honeypotResult", "isHoneypot"),
          "顶层键: %s" % sorted(d.keys()))
    sim = d.get("simulationResult") or {}
    check("simulationResult 里【没有】isHoneypot（读错位置会恒为 False）",
          "isHoneypot" not in sim, "simulationResult 键: %s" % sorted(sim.keys()))
    # ---- 我们依赖的其余字段 ----
    for key in ("summary", "simulationSuccess", "simulationResult", "contractCode", "token"):
        check("顶层含 %s" % key, key in d, str(sorted(d.keys())))
    check("summary.risk 存在", path_exists(d, "summary", "risk"), "")
    check("summary.flags 是数组",
          isinstance((d.get("summary") or {}).get("flags"), list), "")
    for key in ("buyTax", "sellTax", "transferTax"):
        check("simulationResult 含 %s" % key, key in sim, str(sorted(sim.keys())))
    check("contractCode.openSource 存在",
          path_exists(d, "contractCode", "openSource"), "")
    check("token.totalHolders 存在", path_exists(d, "token", "totalHolders"), "")

    risk_val = (d.get("summary") or {}).get("risk")
    check("summary.risk 取值在已知枚举内",
          risk_val in ("low", "medium", "high", "very_high", "unknown", None),
          "实际 %r" % risk_val)


def test_geckoterminal():
    print("\n[上游] GeckoTerminal")
    d = get("https://api.geckoterminal.com/api/v2/networks/eth/tokens/%s/pools" % WETH)
    pools = d.get("data") or []
    check("tokens/{a}/pools 返回 data", bool(pools), "拿到 %d 个" % len(pools))
    if pools:
        a = (pools[0].get("attributes") or {})
        for key in ("reserve_in_usd", "pool_created_at", "volume_usd", "name"):
            check("pool 属性含 %s" % key, key in a, str(sorted(a.keys()))[:200])
        # base_token_price_usd 经常是 null，价格需从这两个字段推导
        check("价格可推导（base_token_price_quote_token + quote_token_price_usd）",
              "base_token_price_quote_token" in a and "quote_token_price_usd" in a,
              str(sorted(a.keys()))[:200])
        check("pool_created_at 是 ISO 字符串",
              isinstance(a.get("pool_created_at"), str),
              "实际 %r" % a.get("pool_created_at"))

    n = get("https://api.geckoterminal.com/api/v2/networks/solana/new_pools")
    check("new_pools 返回 data", bool(n.get("data")), "")
    t = get("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools")
    check("trending_pools 返回 data", bool(t.get("data")), "")


def test_rugcheck():
    print("\n[上游] RugCheck (Solana)")
    d = get("https://api.rugcheck.xyz/v1/tokens/%s/report" % BONK)
    if not d:
        check("RugCheck 可达", False, "无响应——Solana 路径将退化为 unknown")
        return
    check("RugCheck 可达", True)
    check("含 score 字段", "score" in d, str(sorted(d.keys()))[:200])
    check("risks 是数组或缺失",
          d.get("risks") is None or isinstance(d.get("risks"), list), "")


def main():
    print("=" * 68)
    print("VetAgent 上游契约测试（真实联网）")
    print("=" * 68)
    for fn in (test_dexscreener, test_honeypot_is, test_geckoterminal, test_rugcheck):
        fn()
    print("\n" + "=" * 68)
    print("通过 %d 项，失败 %d 项" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\n失败明细（上游可能已变更字段，需同步修改 risk.py）：")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
