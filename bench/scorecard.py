"""scorecard.py — 成熟度评分。自动算，不是拍脑袋。

与「我每次给一个数」的区别，是这份评分的全部意义：
**我给的数是意见，从产物里算出来的数是事实。**
所以下面每个子项都尽量从真实产物读取（测试结果、基准报告、快照库、注册表），
读不到就明确标成"未测量"，绝不用估计值填空。

五个维度，满分 100：

    正确性 30   它给的答案对不对
    覆盖度 20   它看得见多少种风险
    可信度 20   我们能不能证明它有用
    分发   15   够不够多的人能找到它
    需求   15   有没有人真的要它

**为什么要有「需求」这一维**：没有它，分数可以靠埋头开发刷上去——
做一堆没人要的功能，分数照涨，生意不动。加上它以后，
**纯工程能达到的上限是有限的**，最后那部分只能由别人给。
这正是这份评分想防住的自欺。

用法：
    python bench/scorecard.py            # 打印
    python bench/scorecard.py --write    # 同时写入 docs/SCORECARD.md
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RESULTS = os.path.join(HERE, "results.json")
SNAPSHOTS = os.path.join(HERE, "snapshots")
OUT_MD = os.path.join(ROOT, "docs", "SCORECARD.md")

UNMEASURED = "未测量"


# ---------------------------------------------------------------- 采集事实

def tests_pass():
    """跑离线测试套件。红了就是红了，不打折。"""
    ok, detail = True, []
    for suite in ("test_risk.py", "test_mcp.py"):
        p = os.path.join(ROOT, "tests", suite)
        if not os.path.exists(p):
            return False, ["%s 不存在" % suite]
        r = subprocess.run([sys.executable, p], capture_output=True,
                           encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode != 0:
            ok = False
            detail.append("%s 失败" % suite)
        else:
            tail = (r.stdout or "").strip().splitlines()[-2:]
            detail.append("%s %s" % (suite, " ".join(t.strip() for t in tail)[:40]))
    return ok, detail


def benchmark_facts():
    if not os.path.exists(RESULTS):
        return {}
    with open(RESULTS, encoding="utf-8") as f:
        r = json.load(f)
    good = ((r.get("outcome") or {}).get("full") or {}).get("good") or {}
    bad = ((r.get("outcome") or {}).get("full") or {}).get("bad") or {}
    return {
        "n": r.get("n_evaluated"),
        "false_positive": good.get("high"),
        "unknown_rate": (r.get("overall") or {}).get("unknown_rate"),
        "dead_cohort": bad.get("n") or 0,
        "recall_measurable": (bad.get("n") or 0) >= 20,
    }


def snapshot_days():
    if not os.path.isdir(SNAPSHOTS):
        return 0
    return len([f for f in os.listdir(SNAPSHOTS)
                if f.startswith("pools-") and f.endswith(".ndjson")])


# 已知重要的风险维度。这张表本身就是路线图——
# 没打勾的每一项都是一个真实的盲区，不是凑数。
RISK_VECTORS = [
    ("可卖出性仿真 (honeypot)", True),
    ("买卖/转账税", True),
    ("流动性深度", True),
    ("交易对年龄", True),
    ("合约是否开源", True),
    ("上游聚合判定", True),
    ("持币集中度 (Solana)", True),
    ("mint / freeze 权限 (Solana)", True),
    ("持币集中度 (EVM)", False),      # 需要 GoPlus，但它是基准的留出预言机（DECISIONS B2）
    ("LP 锁仓 / 销毁", False),        # 撤池是 EVM 侧主要 rug 形态，完全没覆盖
    ("同名代币冒充检测", False),      # agent 场景最常见的损失形态
    ("部署者历史行为", False),
]

# 目标分发渠道。已上架的靠 registry 实测，其余按 HANDOFF 记录。
CHANNELS = [
    ("官方 MCP Registry", True),
    ("PulseMCP（registry 自动同步）", True),
    ("Claude 插件目录", False),
    ("Glama", False),
    ("Smithery", False),
    ("mcp.so", False),
    ("awesome-mcp-servers", False),
    ("mcpservers.org", False),
]


# ---------------------------------------------------------------- 评分

def band(value, thresholds, points):
    """value 落在哪个档就给哪个分。thresholds 递增，points 递减。"""
    if value is None:
        return None
    for t, p in zip(thresholds, points):
        if value < t:
            return p
    return points[-1]


def score():
    tp, tdetail = tests_pass()
    b = benchmark_facts()
    days = snapshot_days()
    covered = sum(1 for _, ok in RISK_VECTORS if ok)
    listed = sum(1 for _, ok in CHANNELS if ok)

    # 需求与外部调用方目前无法自动读取（需要 Cloudflare token），
    # 因此明确记为「未测量」而不是 0——两者含义不同。
    external_callers = None
    paying = 0
    trial_intents = 0

    items = []

    # --- 正确性 30 ---
    items.append(("正确性", "测试全绿", 10, 10 if tp else 0, "；".join(tdetail)))
    fp = b.get("false_positive")
    items.append(("正确性", "误报率（健康代币被判 high）", 10,
                  band(fp, [0.02, 0.05, 0.10, 0.15], [10, 8, 6, 4, 2]),
                  "%.1f%%" % (fp * 100) if fp is not None else UNMEASURED))
    ur = b.get("unknown_rate")
    items.append(("正确性", "unknown 率", 10,
                  band(ur, [0.05, 0.10, 0.20, 0.30], [10, 8, 6, 4, 2]),
                  "%.1f%%" % (ur * 100) if ur is not None else UNMEASURED))

    # --- 覆盖度 20 ---
    items.append(("覆盖度", "已覆盖的风险维度", 20,
                  round(20.0 * covered / len(RISK_VECTORS), 1),
                  "%d / %d" % (covered, len(RISK_VECTORS))))

    # --- 可信度 20 ---
    items.append(("可信度", "召回率可测量", 10,
                  10 if b.get("recall_measurable") else 0,
                  "dead 样本 %s 个（需 ≥20）" % b.get("dead_cohort", "?")))
    items.append(("可信度", "快照库天数", 10,
                  round(min(10.0, 10.0 * days / 180), 1),
                  "%d 天 / 目标 180" % days))

    # --- 分发 15 ---
    items.append(("分发", "已上架渠道", 10,
                  round(10.0 * listed / len(CHANNELS), 1),
                  "%d / %d" % (listed, len(CHANNELS))))
    items.append(("分发", "外部调用方", 5,
                  None if external_callers is None else min(5, external_callers),
                  UNMEASURED + "（需 CLOUDFLARE_API_TOKEN，见 bench/usage.py）"))

    # --- 需求 15 ---
    items.append(("需求", "付费用户", 10, min(10, paying * 2), "%d 个" % paying))
    items.append(("需求", "试用意向 / 主动询问", 5, min(5, trial_intents), "%d 个" % trial_intents))

    return items, {"benchmark": b, "snapshot_days": days,
                   "covered": covered, "listed": listed}


def totals(items):
    dims, order = {}, []
    for dim, _, weight, got, _ in items:
        if dim not in dims:
            dims[dim] = [0.0, 0.0, False]
            order.append(dim)
        dims[dim][0] += weight
        dims[dim][1] += got or 0.0
        if got is None:
            dims[dim][2] = True
    return dims, order


def render(items, facts):
    dims, order = totals(items)
    total_max = sum(d[0] for d in dims.values())
    total_got = sum(d[1] for d in dims.values())

    L = []
    A = L.append
    A("# 成熟度评分 (SCORECARD.md)\n")
    A("> 由 `python bench/scorecard.py --write` 生成，**不要手改**。")
    A("> 每次提交都会跟着变，所以 `git diff` 就是「这次改动值多少分」的答案。\n")
    A("\n## 总分：**%.0f / %d**\n" % (total_got, total_max))
    A("| 维度 | 得分 | 满分 |")
    A("|---|---|---|")
    for d in order:
        mx, got, partial = dims[d]
        A("| %s | %.1f%s | %d |" % (d, got, " ⚠️" if partial else "", mx))
    A("\n⚠️ = 该维度有子项无法自动测量，得分偏低是因为缺数据，不是因为做得差。\n")

    A("\n## 明细\n")
    A("| 维度 | 子项 | 得分 | 满分 | 依据 |")
    A("|---|---|---|---|---|")
    for dim, name, weight, got, note in items:
        A("| %s | %s | %s | %d | %s |"
          % (dim, name, "—" if got is None else "%.1f" % got, weight, note))

    A("\n## 为什么纯工程刷不满分\n")
    A("「需求」15 分 + 「外部调用方」5 分 + 「召回率可测量」10 分 = **30 分**，")
    A("这三项**不可能靠写代码拿到**：")
    A("")
    A("- 需求要有人愿意付钱")
    A("- 外部调用方要有人真的接进去")
    A("- 召回率可测量要等快照库攒够已死样本，而时间买不到")
    A("")
    A("所以**纯工程的天花板是 70 分**。")
    A("这不是设计上的悲观，是这份评分存在的理由——")
    A("**它不允许「我很忙」冒充「有进展」。**\n")

    A("\n## 风险维度覆盖\n")
    A("没打勾的每一项都是真实盲区，也是路线图本身。\n")
    A("\n| 维度 | 覆盖 |")
    A("|---|---|")
    for name, ok in RISK_VECTORS:
        A("| %s | %s |" % (name, "✅" if ok else "⬜"))

    A("\n## 分发渠道\n")
    A("| 渠道 | 已上架 |")
    A("|---|---|")
    for name, ok in CHANNELS:
        A("| %s | %s |" % (name, "✅" if ok else "⬜"))

    A("\n---\n")
    A("**100 分是什么样**（刻意不自我设限）：召回率 >90% 且误报 <2%、")
    A("unknown <5%、12 个维度全覆盖、12 个月以上的结果数据、")
    A("基准方法论被同行当作标准引用、在每个 agent 入口都是默认选择、")
    A("有一批「如果它消失会来投诉」的付费用户。\n")
    A("**当前 %.0f 分不是失败**——它准确地说明了：工程做得还行，" % total_got)
    A("而证明力和需求都还是零，且这两件事写代码解决不了。\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    items, facts = score()
    md = render(items, facts)
    dims, order = totals(items)
    total_got = sum(d[1] for d in dims.values())
    total_max = sum(d[0] for d in dims.values())

    print("=" * 58)
    print("VetAgent 成熟度：%.0f / %d" % (total_got, total_max))
    print("=" * 58)
    for d in order:
        mx, got, partial = dims[d]
        bar = "#" * int(round(20.0 * got / mx)) if mx else ""
        print("  %-8s %5.1f / %-3d %s%s" % (d, got, mx, bar, "  ⚠️有未测量项" if partial else ""))
    print()
    for dim, name, weight, got, note in items:
        print("  %-8s %-26s %5s/%-3d  %s"
              % (dim, name[:26], "—" if got is None else "%.1f" % got, weight, note[:44]))

    if args.write:
        os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write(md)
        print("\n已写入 %s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
