"""snapshot.py — 每日快照采集器。护城河的第一块砖。

为什么这件事必须**今天**开始，而不是等产品成熟：

上游 API（DexScreener / GeckoTerminal）只提供**当前状态**，不提供历史状态查询。
「这个池子在被抽干前 7 天长什么样」这个问题，只能靠实时采集来回答——
今天没采，这一天的数据就永久不存在了，任何预算都补不回来。

半年后这份数据能回答一个现在谁都答不了的问题：
**rug 之前有没有可观测的前兆。** 那是 VetAgent 从「转述别人的判断」
变成「有自己的判断」的唯一路径，也是竞争对手今天决定要做、
也必须再等半年才能追上的东西。

用法：
    python bench/snapshot.py                  # 采一次，追加到 snapshots/
    python bench/snapshot.py --chains eth,base,bsc,solana

建议每天跑一次（cron / GitHub Actions / Cloudflare cron 均可）。
输出是 NDJSON，一行一个池子，按日期分文件，方便日后直接灌进任何存储。
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

DEFAULT_CHAINS = ["eth", "base", "bsc", "solana"]

# 每个池子记录的字段。刻意记「原始可观测量」而不是我们当下的评分——
# 评分规则会变，原始量不会。将来想用新规则重算历史，必须有原始量才行。
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


def collect(chains):
    seen_at = datetime.now(timezone.utc).isoformat()
    rows, seen_ids = [], set()
    for chain in chains:
        for kind, path in (("new", "new_pools"), ("trending", "trending_pools")):
            data = fetch_json(
                "https://api.geckoterminal.com/api/v2/networks/%s/%s" % (chain, path),
                role="label", use_cache=False)   # 快照必须取实时值，不能走缓存
            if data is None:
                print("  %-8s %-9s 抓取失败" % (chain, kind))
                continue
            pools = data.get("data") or []
            n = 0
            for p in pools:
                pid = p.get("id")
                if not pid or (chain, pid, kind) in seen_ids:
                    continue
                seen_ids.add((chain, pid, kind))
                rows.append(_row(chain, kind, p, seen_at))
                n += 1
            print("  %-8s %-9s %d 个池" % (chain, kind, n))
    return rows, seen_at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", default=",".join(DEFAULT_CHAINS))
    args = ap.parse_args()
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]

    os.makedirs(OUT_DIR, exist_ok=True)
    print("采集中：%s" % ", ".join(chains))
    rows, seen_at = collect(chains)
    if not rows:
        print("没有采到任何数据——上游可能全挂了。这次不写文件。")
        return 1

    day = seen_at[:10]
    path = os.path.join(OUT_DIR, "pools-%s.ndjson" % day)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_days = len({fn[6:16] for fn in os.listdir(OUT_DIR)
                      if fn.startswith("pools-") and fn.endswith(".ndjson")})
    print("\n本次 %d 行 -> %s" % (len(rows), os.path.basename(path)))
    print("快照库已积累 **%d 天**（这是护城河的唯一直接度量）" % total_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
