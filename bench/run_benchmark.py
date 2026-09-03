"""run_benchmark.py — 用独立标注集评测本地引擎，产出可复现的准确率报告。

用法：
    python bench/run_benchmark.py

做四件事：

1. **跑引擎**。直接调 src/risk.py 里的 assess()，把它的 _fetch_json 换成带缓存的
   取数器（role="engine"）。测的是仓库里的代码，不是线上部署，所以能进 CI。

2. **独立性断言**。引擎访问过的端点集合与标注器的必须不相交。相交就直接判定
   基准失效并退出非零——这条是整份报告可信度的地基，不能只写在文档里。

3. **消融分析**。已经死掉的池子现在流动性≈0，引擎靠「流动性极低」这一条就能判 high，
   接近同义反复。所以除了完整成绩，另外报一份**只保留合约安全类信号**的成绩
   （剔除流动性/活跃度/新鲜度/跨链）。两个数字的差距，就是这个工具在
   「显而易见的事情」之外真正提供的信息量。

4. **信号归因**。统计每个正确判定是被哪一类信号驱动的。如果 100% 来自
   upstream_risk，那说明引擎只是在转述 honeypot.is，自身没有增量。
"""

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import risk  # noqa: E402
from fetcher import access_report, fetch_json  # noqa: E402

DATASET = os.path.join(HERE, "dataset.json")
RESULTS_JSON = os.path.join(HERE, "results.json")
RESULTS_MD = os.path.join(HERE, "results.md")

# 合约安全类信号：与「当前流动性还剩多少」无关的那些
CONTRACT_CATEGORIES = {
    "honeypot", "sellability", "sell_tax", "upstream_risk",
    "rugcheck", "contract", "concentration",
}


def install_engine_fetcher():
    """把引擎的取数换成带缓存、带来源记账的版本。"""
    async def _fetch(url, retries=2, timeout=8):
        return fetch_json(url, role="engine", retries=1)
    risk._fetch_json = _fetch


def ablate(address, signals):
    """只留合约安全类信号，重新走一遍定级，看引擎还剩多少判断力。"""
    kept = [s for s in signals if s["category"] in CONTRACT_CATEGORIES]
    if not kept:
        return "unknown", 0
    r = risk._finalize(address, kept, {}, [])
    return r["risk_level"], r["risk_score"]


def driving_category(signals):
    """找出决定了这次判定的那条信号所属的类别。"""
    if not signals:
        return None
    ranked = sorted(
        signals,
        key=lambda s: risk._SEVERITY_BASE.get(s["severity"], 0)
        * risk._CATEGORY_WEIGHT.get(s["category"], 0.5),
        reverse=True)
    top = ranked[0]
    return top["category"] if top["severity"] != "ok" else None


def evaluate(rows, label_key, bad_value, good_value):
    """对一套标签算指标。

    strict  = 只把 high 算作「拦下了」
    lenient = high 或 medium 都算「提示了风险」（产品语义上 medium 要求人工复核）
    """
    bad = [r for r in rows if r.get(label_key) == bad_value]
    good = [r for r in rows if r.get(label_key) == good_value]

    def rate(sub, pred):
        return (sum(1 for r in sub if pred(r)) / len(sub)) if sub else None

    def block(sub, verdict_field, score_field):
        return {
            "n": len(sub),
            "high": rate(sub, lambda r: r[verdict_field] == "high"),
            "high_or_medium": rate(sub, lambda r: r[verdict_field] in ("high", "medium")),
            "low": rate(sub, lambda r: r[verdict_field] == "low"),
            "unknown": rate(sub, lambda r: r[verdict_field] == "unknown"),
            "mean_score": (sum(r[score_field] for r in sub) / len(sub)) if sub else None,
        }

    out = {
        "bad_label": bad_value, "good_label": good_value,
        "full": {"bad": block(bad, "verdict", "score"),
                 "good": block(good, "verdict", "score")},
        "contract_only": {"bad": block(bad, "verdict_ablated", "score_ablated"),
                          "good": block(good, "verdict_ablated", "score_ablated")},
        "driving_categories_on_bad": dict(
            Counter(r["driver"] for r in bad if r.get("driver")).most_common()),
    }
    return out


def centralized_view(rows):
    """「有特权函数但无对抗特征」这一档——USDT / WBTC / LDO 属于此类。

    这一档**不计好坏**，只用来看引擎会不会把中心化资产无差别打成高危。
    大量判 high 说明阈值太钝，会在真实使用中制造刺耳的误报。
    """
    sub = [r for r in rows if r.get("goplus_label") == "centralized"]
    if not sub:
        return {"n": 0}
    dist = Counter(r["verdict"] for r in sub)
    return {
        "n": len(sub),
        "verdict_distribution": dict(dist),
        "high_rate": dist.get("high", 0) / len(sub),
        "examples": [{"symbol": r.get("symbol"), "chain": r["chain"],
                      "verdict": r["verdict"], "driver": r.get("driver")}
                     for r in sub[:10]],
    }


def collect_disagreements(rows):
    """标注与引擎不一致的样本。漏报排在前面——它们才是真正的缺陷线索。"""
    out = []
    for r in rows:
        for key, bad, good in (("outcome_label", "dead", "alive"),
                               ("goplus_label", "unsafe", "safe")):
            lab = r.get(key)
            if lab == bad and r["verdict"] == "low":
                kind = "漏报"
            elif lab == good and r["verdict"] == "high":
                kind = "误报"
            else:
                continue
            out.append({"kind": kind, "label": "%s=%s" % (key.split("_")[0], lab),
                        "address": r["address"], "symbol": r.get("symbol"),
                        "chain": r["chain"], "verdict": r["verdict"],
                        "verdict_ablated": r["verdict_ablated"], "driver": r.get("driver")})
    out.sort(key=lambda d: 0 if d["kind"] == "漏报" else 1)
    return out


def _pct(v):
    return "—" if v is None else "%.1f%%" % (v * 100)


def _num(v):
    return "—" if v is None else "%.1f" % v


def main():
    if not os.path.exists(DATASET):
        print("找不到 %s，请先跑 python bench/build_dataset.py" % DATASET)
        return 1
    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    tokens = data.get("tokens") or []
    if not tokens:
        print("数据集为空")
        return 1

    install_engine_fetcher()
    import asyncio

    rows = []
    print("评测 %d 个标的 ..." % len(tokens))
    for i, t in enumerate(tokens, 1):
        try:
            res = asyncio.run(risk.assess(t["address"], t["chain"]))
        except Exception as e:  # noqa: BLE001
            print("  %s 评测异常: %s" % (t.get("symbol"), e))
            continue
        sigs = res.get("signals") or []
        ab_level, ab_score = ablate(t["address"], sigs)
        rows.append({
            "address": t["address"], "symbol": t.get("symbol"), "chain": t["chain"],
            "outcome_label": t.get("outcome_label"), "goplus_label": t.get("goplus_label"),
            "verdict": res.get("risk_level"), "score": res.get("risk_score"),
            "confidence": res.get("confidence"),
            "verdict_ablated": ab_level, "score_ablated": ab_score,
            "driver": driving_category(sigs),
            "categories": sorted({s["category"] for s in sigs}),
            "has_data_gap": bool((res.get("evidence") or {}).get("data_gaps")),
        })
        if i % 20 == 0 or i == len(tokens):
            print("  [%d/%d]" % (i, len(tokens)))

    # ---- 独立性断言：整份报告的地基 ----
    engine_eps, label_eps, overlap = access_report()
    if overlap:
        print("\n基准失效：引擎与标注器访问了相同端点 —— 这会让结果变成循环论证")
        for e in overlap:
            print("   重叠端点:", e)
        return 2

    report = {
        "n_evaluated": len(rows),
        "independence": {"engine_endpoints": engine_eps,
                         "label_endpoints": label_eps, "overlap": overlap},
        "overall": {
            "verdict_distribution": dict(Counter(r["verdict"] for r in rows)),
            "unknown_rate": sum(1 for r in rows if r["verdict"] == "unknown") / len(rows),
            "data_gap_rate": sum(1 for r in rows if r["has_data_gap"]) / len(rows),
        },
        "outcome": evaluate(rows, "outcome_label", "dead", "alive"),
        "goplus": evaluate(rows, "goplus_label", "unsafe", "safe"),
        "centralized": centralized_view(rows),
        "disagreements": collect_disagreements(rows),
        "rows": rows,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    write_markdown(report)
    print("\n已写入 %s 和 %s" % (RESULTS_JSON, RESULTS_MD))

    o = report["outcome"]["full"]["bad"]
    print("\n速览：")
    print("  已死代币被判 high 的比例      : %s (n=%d)" % (_pct(o["high"]), o["n"]))
    print("  剔除流动性信号后仍判 high     : %s"
          % _pct(report["outcome"]["contract_only"]["bad"]["high"]))
    print("  正常代币被误判 high 的比例    : %s (n=%d)"
          % (_pct(report["outcome"]["full"]["good"]["high"]),
             report["outcome"]["full"]["good"]["n"]))
    print("  unknown 率                    : %s" % _pct(report["overall"]["unknown_rate"]))
    return 0


def write_markdown(rep):
    L = []
    A = L.append
    A("# VetAgent 准确率基准\n")
    A("> 本文件由 `python bench/run_benchmark.py` 生成，不要手改。\n")
    A("样本量 **%d**。这是 v1，样本偏小，请把它当作"
      "「有没有明显失效」的体检，而不是精确的统计结论。\n" % rep["n_evaluated"])

    A("\n## 方法\n")
    A("标注**不使用引擎读取的任何端点**，否则测的是「引擎能不能转述上游」。\n")
    A("\n| | 标注依据 | 引擎是否读取 |")
    A("|---|---|---|")
    A("| `outcome` | GeckoTerminal 日线 OHLCV 历史（价格 + 成交量） | 否，引擎只看当前快照 |")
    A("| `goplus` | GoPlus token_security | 否，刻意保留作标注器 |")
    A("\n**运行时断言**：引擎访问端点 ∩ 标注器访问端点 = ∅，"
      "不满足时基准直接判定失效并退出非零。本次运行结果：**通过**。\n")
    A("\n<details><summary>本次实际访问的端点</summary>\n")
    A("\n引擎：\n")
    for e in rep["independence"]["engine_endpoints"]:
        A("- `%s`" % e)
    A("\n标注器：\n")
    for e in rep["independence"]["label_endpoints"]:
        A("- `%s`" % e)
    A("\n</details>\n")

    A("\n### 标签定义\n")
    A("- **dead**：曾有真实成交（峰值 7 日量 ≥ $50k），后价格自峰值回撤 ≥ 90% "
      "**且**近 7 日量塌到峰值 5% 以下。只跌不算死，只是没量也不算死。\n")
    A("- **alive**：≥ 90 天历史，回撤 ≤ 70%，近 7 日量 ≥ 峰值的 10% 且 ≥ $50k。\n")
    A("- **unsafe**：GoPlus 命中 honeypot / 可暂停 / 黑名单 / 税率可改 / "
      "可收回所有权 / owner 可改余额 / 可增发且 owner 未放弃 / 买卖税 >10%。\n")
    A("- **safe**：以上全不命中，且开源、持有者 ≥ 100。\n")
    A("\n中间地带一律不标注——宁可样本少，不要标签脏。\n")

    ov = rep["overall"]
    A("\n## 总体\n")
    A("| 指标 | 值 |")
    A("|---|---|")
    A("| 判定分布 | %s |" % ", ".join("%s=%d" % kv for kv in sorted(ov["verdict_distribution"].items())))
    A("| unknown 率 | %s |" % _pct(ov["unknown_rate"]))
    A("| 存在数据缺口的比例 | %s |" % _pct(ov["data_gap_rate"]))
    A("\n> unknown 率必须和召回率一起看。一个对所有东西都答 unknown 的工具"
      "召回率完美，但毫无用处。\n")

    for key, title, bad_name, good_name in (
            ("outcome", "结果论标注（已死 vs 存活）", "已死", "存活"),
            ("goplus", "GoPlus 留出预言机（危险 vs 安全）", "危险", "安全")):
        r = rep[key]
        A("\n## %s\n" % title)
        for view, vtitle, note in (
                ("full", "完整信号", ""),
                ("contract_only", "仅合约安全类信号（消融）",
                 "剔除流动性/活跃度/新鲜度/跨链后重算。"
                 "这一栏才是引擎在「显而易见的事情」之外的真实判断力。")):
            b, g = r[view]["bad"], r[view]["good"]
            A("\n### %s\n" % vtitle)
            if note:
                A("%s\n" % note)
            A("\n| | n | 判 high | 判 high 或 medium | 判 low | 判 unknown | 平均分 |")
            A("|---|---|---|---|---|---|---|")
            A("| **%s** | %d | %s | %s | %s | %s | %s |" % (
                bad_name, b["n"], _pct(b["high"]), _pct(b["high_or_medium"]),
                _pct(b["low"]), _pct(b["unknown"]), _num(b["mean_score"])))
            A("| **%s** | %d | %s | %s | %s | %s | %s |" % (
                good_name, g["n"], _pct(g["high"]), _pct(g["high_or_medium"]),
                _pct(g["low"]), _pct(g["unknown"]), _num(g["mean_score"])))
        drv = r.get("driving_categories_on_bad") or {}
        if drv:
            A("\n**%s样本上，是哪类信号做出的判定：** %s\n"
              % (bad_name, "、".join("`%s` %d" % kv for kv in drv.items())))
            A("\n> 若这里高度集中在 `upstream_risk`，说明引擎主要在转述 honeypot.is，"
              "自身增量有限。\n")

    cen = rep.get("centralized") or {}
    if cen.get("n"):
        A("\n## 中心化资产对照组（不计好坏）\n")
        A("有特权函数（可暂停/黑名单/可增发）但**无对抗特征**的代币，"
          "USDT、WBTC、LDO 都属于此类。这些特权是中心化资产的设计，不是 rug。\n")
        A("\n这一档只用来回答一个问题：**引擎会不会把它们无差别打成高危。**"
          "大量判 high 说明阈值太钝，会在真实使用里制造刺耳的误报。\n")
        A("\n| 样本数 | 判 high 比例 | 判定分布 |")
        A("|---|---|---|")
        A("| %d | %s | %s |" % (
            cen["n"], _pct(cen["high_rate"]),
            ", ".join("%s=%d" % kv for kv in sorted(cen["verdict_distribution"].items()))))
        if cen.get("examples"):
            A("\n样例：%s\n" % "、".join(
                "%s(%s)" % (e["symbol"] or "?", e["verdict"]) for e in cen["examples"]))

    dis = rep.get("disagreements") or []
    if dis:
        A("\n## 分歧样本（需人工复核）\n")
        A("标注和引擎判断不一致的样本。**漏报**（标注说危险、引擎说 low）优先看，"
          "每一条都可能是一个真实缺陷；**误报**（标注说安全、引擎说 high）"
          "同样要看，误报会直接摧毁用户信任。\n")
        A("\n| 类型 | 代币 | 链 | 标注 | 引擎判定 | 消融后 | 驱动信号 |")
        A("|---|---|---|---|---|---|---|")
        for d in dis[:20]:
            A("| %s | `%s` | %s | %s | %s | %s | %s |" % (
                d["kind"], (d["symbol"] or d["address"][:10]), d["chain"],
                d["label"], d["verdict"], d["verdict_ablated"], d["driver"] or "—"))
        if len(dis) > 20:
            A("\n（另有 %d 条，见 `results.json`）\n" % (len(dis) - 20))

    A("\n## 这份基准测不到什么\n")
    A("1. **测不到「事前预警」。** 引擎评估的是当前状态，而 `dead` 标签是事后的。"
      "一个已经死掉的池子现在流动性≈0，判 high 接近同义反复——消融那一栏就是为此存在的。"
      "要真正回答「买之前它会不会警告我」，需要按时间点回放历史状态，"
      "而上游安全 API 不提供历史查询。\n")
    A("2. **`dead` ≠ 诈骗。** 正经项目也会死。这个标签回答的是"
      "「现在还能不能安全退出」。\n")
    A("3. **GoPlus 与 honeypot.is 可能相关。** 两者都做买卖仿真，"
      "所以 `goplus` 一栏的成绩会偏高。`outcome` 一栏没有这个问题。\n")
    A("4. **样本偏差。** 头部样本来自各链池子排行（偏健康），"
      "长尾样本来自关键词搜索（偏垃圾），不是真实调用分布的无偏抽样。\n")

    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
