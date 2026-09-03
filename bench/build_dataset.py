"""build_dataset.py — 采样候选代币并用独立标注器打标。

用法：
    python bench/build_dataset.py --limit 40          # 试跑
    python bench/build_dataset.py --limit 300         # 正式构建

采样刻意分两路，避免只测到「一眼就知道好」的样本：
  头部  GeckoTerminal 各链 pools 分页 —— 偏健康
  长尾  DexScreener 关键词搜索       —— 偏垃圾/已死

标注在 labels.py 里，只用引擎不读的端点。产出 bench/dataset.json。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_json  # noqa: E402
from labels import GOPLUS_CHAIN_ID, GT_NETWORK, goplus_label, outcome_label  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")

# 长尾采样关键词：memecoin 命名高度同质，用这些词能捞到大量低质标的。
# 词表刻意做大——试跑时 50 个候选只标出 1 个 dead，样本量完全不够。
# 注意：这里**不按当前流动性筛选**。按「现在流动性很低」去捞已死代币会
# 更高效，但那等于按引擎的判据来选样本，完整信号那一栏的召回率会变得毫无意义。
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
    """DexScreener pair -> 统一候选结构。"""
    base = p.get("baseToken") or {}
    return {
        "address": base.get("address"),
        "symbol": base.get("symbol"),
        "chain": p.get("chainId"),
        "pool": p.get("pairAddress"),
        "source": "dexscreener_search",
    }


def collect_candidates(limit):
    """采样候选。返回去重后的列表，顺序确定（可复现）。"""
    out, seen = [], set()

    def add(c):
        if not c.get("address") or not c.get("pool") or not c.get("chain"):
            return
        if c["chain"] not in GT_NETWORK or c["chain"] not in GOPLUS_CHAIN_ID:
            return  # 只做 EVM：GoPlus 标注器不覆盖 Solana
        key = (c["chain"], c["address"].lower())
        if key in seen:
            return
        seen.add(key)
        out.append(c)

    # 头部：各链按分页取
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

    # 长尾：关键词搜索。全部词表都跑完，长尾才是 dead 样本的主要来源。
    for term in TAIL_TERMS:
        d = fetch_json("https://api.dexscreener.com/latest/dex/search?q=%s" % term,
                       role="label")
        for p in ((d or {}).get("pairs") or []):
            add(_norm_pair(p))

    return out


def label_one(c):
    """给一个候选打两套标签。返回 dict 或 None（两套都没标上）。"""
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
                    help="实际打标的候选数上限（标注成功的会更少）")
    args = ap.parse_args()

    print("采样候选中 ...")
    cands = collect_candidates(args.limit)
    cands = cands[: args.limit]
    print("候选 %d 个，开始打标（首次会慢，之后走缓存）" % len(cands))

    # 限流是按 host 各自计的，所以让不同 host 的请求并行——
    # 串行时每个候选要 ~5s（GT 2.1s + GoPlus 2.1s 排队），并行后收敛到单 host 的节流上限。
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
                print("  %s 打标异常: %s" % (c.get("symbol"), e))
                r = None
            if r:
                rows.append(r)
            if done % 20 == 0 or done == len(cands):
                print("  [%d/%d] 已标注 %d" % (done, len(cands), len(rows)), flush=True)

    from collections import Counter
    oc = Counter(r["outcome_label"] for r in rows if r["outcome_label"])
    gc = Counter(r["goplus_label"] for r in rows if r["goplus_label"])
    print("\n标注结果：")
    print("  outcome:", dict(oc))
    print("  goplus :", dict(gc))

    rows.sort(key=lambda r: (r["chain"], r["address"].lower()))  # 确定顺序
    with open(DATASET, "w", encoding="utf-8") as f:
        json.dump({"tokens": rows,
                   "counts": {"outcome": dict(oc), "goplus": dict(gc)}},
                  f, ensure_ascii=False, indent=1)
    print("\n已写入 %s（%d 条）" % (DATASET, len(rows)))


if __name__ == "__main__":
    main()
