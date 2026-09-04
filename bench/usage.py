"""usage.py — 用量查询。回答决策门要判的那几个问题，不做虚荣指标。

为什么不是「一个数据分析后台」：
  我们现在需要回答的问题只有一个——**有没有外部调用方**（DECISIONS/STRATEGY 决策门 09-18）。
  「总调用次数」回答不了它：一万次全来自我自己，价值为零。
  所以这里只算三件事：有多少**不同的客户端**、有多少**不同的国家**、错误率多少。
  等真有流量了再谈后台。

用法：
    export CLOUDFLARE_API_TOKEN=...      # 需要 Account Analytics: Read 权限
    export CLOUDFLARE_ACCOUNT_ID=...
    python bench/usage.py [--days 14]

数据来源是 Cloudflare Analytics Engine（Worker 侧写入见 src/entry.py）。
**刻意不记录被查询的代币地址**——那是用户的查询意图。代价是我们不知道热门标的。
"""

import argparse
import json
import os
import subprocess
import sys

DATASET = "vetagent_calls"
API = "https://api.cloudflare.com/client/v4/accounts/%s/analytics_engine/sql"

# blob 的含义由 src/entry.py 的写入顺序决定，改一处必须改另一处
BLOB = {"method": "blob1", "tool": "blob2", "verdict": "blob3",
        "client": "blob4", "country": "blob5"}


def query(sql, account, token):
    r = subprocess.run(
        ["curl", "-s", "-m", "45", "-X", "POST", API % account,
         "-H", "Authorization: Bearer %s" % token,
         "--data-binary", sql],
        capture_output=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"_raw": (r.stdout or "")[:400]}


def rows_of(resp):
    if not isinstance(resp, dict):
        return None
    if "data" in resp:
        return resp["data"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        print("缺少 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID 环境变量。")
        print("token 需要 Account Analytics: Read 权限（和部署用的那个可以是同一个）。")
        return 2

    since = "INTERVAL '%d' DAY" % args.days
    print("=" * 62)
    print("VetAgent 用量 · 最近 %d 天" % args.days)
    print("=" * 62)

    total = query(
        "SELECT count() AS calls, sum(double2) AS errors, "
        "count(DISTINCT %s) AS clients, count(DISTINCT %s) AS countries "
        "FROM %s WHERE timestamp > now() - %s"
        % (BLOB["client"], BLOB["country"], DATASET, since), account, token)

    rows = rows_of(total)
    if rows is None:
        print("\n查询失败。原始响应：")
        print(json.dumps(total, ensure_ascii=False)[:600])
        print("\n常见原因：token 缺 Account Analytics: Read 权限；或 account id 不对。")
        return 1

    if not rows or int(float(rows[0].get("calls") or 0)) == 0:
        # 关键：区分「确实没人调用」和「写入根本没生效」。
        # 这两种情况都表现为 0 行，但含义完全相反，混为一谈会让决策门判错。
        print("\n0 条记录。这有两种可能，必须分清：")
        print("  a) 确实还没有人调用 —— 那么决策门 09-18 的答案是「没有外部调用方」")
        print("  b) 写入路径没生效 —— 那么这个 0 毫无意义")
        print("\n分辨方法：自己发一次调用，等 1-2 分钟再跑本脚本。")
        print("  curl -s -X POST https://vetagent.dev/mcp -H 'Content-Type: application/json' \\")
        print("    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' > /dev/null")
        print("  出现记录 = 写入正常，之前的 0 是真的没人用。")
        print("  仍然是 0 = 写入坏了，先修 src/entry.py 的 _record()。")
        return 0

    r = rows[0]
    calls = int(float(r.get("calls") or 0))
    errors = int(float(r.get("errors") or 0))
    clients = int(float(r.get("clients") or 0))
    countries = int(float(r.get("countries") or 0))

    print("\n总调用      : %d" % calls)
    print("错误        : %d (%.1f%%)" % (errors, 100.0 * errors / calls if calls else 0))
    print("不同客户端  : %d" % clients)
    print("不同国家    : %d" % countries)

    print("\n--- 决策门 09-18：有没有外部调用方 ---")
    if clients <= 1 and countries <= 1:
        print("  尚无证据。目前的流量看起来都来自同一处（很可能是我们自己）。")
        print("  → 按 STRATEGY 的规则：这是曝光问题，不是产品问题，转实验 C。")
    else:
        print("  有：%d 个客户端 / %d 个国家。→ 继续按路线图走。" % (clients, countries))

    for title, col in (("按工具", BLOB["tool"]), ("按客户端", BLOB["client"]),
                       ("按国家", BLOB["country"]), ("按结论", BLOB["verdict"])):
        resp = query(
            "SELECT %s AS k, count() AS n FROM %s WHERE timestamp > now() - %s "
            "GROUP BY k ORDER BY n DESC LIMIT 8" % (col, DATASET, since), account, token)
        rs = rows_of(resp) or []
        if rs:
            print("\n%s:" % title)
            for row in rs:
                print("  %-28s %s" % ((row.get("k") or "(空)")[:28], row.get("n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
