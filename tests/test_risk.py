"""test_risk.py — 离线回归测试。

用真实上游响应快照（tests/fixtures/）驱动，不打网络，可在 CI 里跑。
每个用例都对应一个**真实发生过的线上缺陷**，用于防止回归。

运行：  python tests/test_risk.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import risk  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# 已知地址 -> fixture 文件
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
MATIC = "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
RETAIL = "0xb954d1ba6bb92123609fcfb724c68b810c668feb"   # honeypot.is: very_high
ALIGN = "0x50614cc8e44f7814549c223aa31db9296e58057c"    # honeypot.is: 仿真失败
TAXED = "0x1c48955a39952e74ef03a173de52958138cb92ab"    # 卖税 4.94% + 闭源
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"   # Solana，RugCheck 干净


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def install_stub(routes, default=None):
    """把 risk._fetch_json 换成查表，不打网络。

    routes: [(url 子串, 返回值)]，返回值为 None 代表**抓取失败**。
    """
    async def _stub(url, retries=2):
        for frag, payload in routes:
            if frag in url:
                return payload
        return default
    risk._fetch_json = _stub


# ---------------------------------------------------------------- 断言助手

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


def sig_categories(result):
    return {s["category"]: s["severity"] for s in result["signals"]}


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- 用例

def test_honeypot_key_is_read_from_the_right_object():
    """回归 P0-A：isHoneypot 在 honeypotResult 里，不在 simulationResult 里。

    旧代码读 simulationResult.isHoneypot（该键不存在），导致 honeypot 维度恒为 ok。
    """
    print("\n[P0-A] honeypot 键路径 + 上游聚合判定")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_retail_veryhigh.json")),
    ])
    r = run(risk.assess(RETAIL, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("very_high 代币不得判为 low", r["risk_level"] != "low", "得到 %s" % r["risk_level"])
    check("必须产生 upstream_risk 信号", "upstream_risk" in cats, str(cats))
    check("upstream_risk 必须是 critical",
          cats.get("upstream_risk") == "critical", str(cats.get("upstream_risk")))
    check("闭源必须被标记", cats.get("contract") == "warn", str(cats))
    check("evidence 保留上游 risk",
          r["evidence"]["honeypot"]["upstream_risk"] == "very_high", "")


def test_simulation_failure_is_fail_closed():
    """回归 P0-A2：仿真失败时旧代码输出 'ok / 非 Honeypot'。

    align 的 simulationError 是 'HP: BUY_FAILED'——买都买不进去，却被判为安全。
    """
    print("\n[P0-A2] 仿真失败必须 fail-closed")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_align_simfail.json")),
    ])
    r = run(risk.assess(ALIGN, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("不得出现 ok 的 honeypot 信号", cats.get("honeypot") != "ok", str(cats))
    check("必须产生 sellability 信号", "sellability" in cats, str(cats))
    check("sellability 必须 critical", cats.get("sellability") == "critical", str(cats))
    check("绝不判为 low", r["risk_level"] != "low", r["risk_level"])
    check("data_gaps 必须记录", bool(r["evidence"].get("data_gaps")), "")


def test_tax_and_closed_source():
    print("\n[P0-A3] 交易税 + 闭源")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_test_hightax.json")),
    ])
    r = run(risk.assess(TAXED, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("4.94% 卖税不该报极高税", cats.get("sell_tax") != "critical", str(cats))
    check("闭源必须 warn", cats.get("contract") == "warn", str(cats))
    check("上游 high 必须体现", cats.get("upstream_risk") == "warn", str(cats))
    check("不得判为 low", r["risk_level"] != "low", r["risk_level"])


def test_liquidity_picks_the_right_pool():
    """回归 P0-C：liquidity() 从未用过 _pick_best，把 USDC 报成 $0.00097。"""
    print("\n[P0-C] liquidity() 选池")
    install_stub([("dexscreener", _load("ds_usdc.json"))])
    r = run(risk.liquidity(USDC, chain_hint="ethereum"))
    check("status 为 ok", r.get("status") == "ok", str(r.get("status")))
    check("必须选 ethereum 而非 pulsechain",
          r.get("best_pair_chain") == "ethereum", str(r.get("best_pair_chain")))
    check("USDC 价格必须接近 $1", 0.9 <= r.get("price_usd", 0) <= 1.1,
          "得到 %s" % r.get("price_usd"))

    # 不给 chain_hint 时，中位价过滤也要挡住分叉链错价池
    r2 = run(risk.liquidity(USDC))
    check("无 chain_hint 时价格仍需合理", 0.5 <= r2.get("price_usd", 0) <= 2.0,
          "得到 %s" % r2.get("price_usd"))


def test_address_validation_on_every_entrypoint():
    """回归 P0-C2：liquidity() 此前完全没有地址校验。"""
    print("\n[P0-C2] 地址校验覆盖所有入口")
    install_stub([])
    for fn, label in ((risk.assess, "assess"), (risk.liquidity, "liquidity")):
        for bad in ("0xdeadbeef", "", "   ", "not-an-address", "0x" + "z" * 40):
            try:
                run(fn(bad))
                check("%s(%r) 必须抛错" % (label, bad), False, "没有抛错")
            except ValueError:
                check("%s(%r) 抛 ValueError" % (label, bad), True)
            except Exception as e:
                check("%s(%r) 抛 ValueError" % (label, bad), False, type(e).__name__)


def test_pair_age_works_on_integer_timestamps():
    """回归 P0-D：DexScreener 的 pairCreatedAt 是毫秒整数。

    旧代码对它调 .replace()，AttributeError 被 except 吞掉，
    主数据源上交易对年龄信号从未生效。
    """
    print("\n[P0-D] 交易对年龄（毫秒整数）")
    check("毫秒整数可解析", risk._pair_created_ms(1589841515000) == 1589841515000.0, "")
    check("秒整数自动升毫秒", risk._pair_created_ms(1589841515) == 1589841515000.0, "")
    check("ISO 字符串可解析",
          risk._pair_created_ms("2020-05-19T00:00:00Z") is not None, "")
    check("None 返回 None", risk._pair_created_ms(None) is None, "")
    check("布尔不被当数字", risk._pair_created_ms(True) is None, "")
    check("垃圾字符串返回 None", risk._pair_created_ms("not-a-date") is None, "")

    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_matic.json")),
    ])
    r = run(risk.assess(MATIC, chain_hint="ethereum"))
    check("必须算出交易对年龄", r["evidence"].get("pair_age_days", 0) > 1000,
          str(r["evidence"].get("pair_age_days")))
    check("必须产生 freshness 信号", "freshness" in sig_categories(r),
          str(sig_categories(r)))


def test_engine_output_is_english():
    """回归：引擎的**输出**曾经是中文。

    工具描述翻译过了，但真正被 agent 转述给终端用户的是 signals 和 recommendation。
    英文页面上显示中文结论只是难看；agent 把中文信号念给英文用户才是坏掉。

    只查 CJK，不查全部非 ASCII——破折号、引号是合法排版字符，
    一个会因为标点变红的测试迟早会被人关掉。
    """
    print("\n[i18n] 引擎输出必须是英文")

    def cjk(text):
        return [c for c in str(text) if "一" <= c <= "鿿"]

    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_retail_veryhigh.json")),
    ])
    r = run(risk.assess(RETAIL, chain_hint="ethereum"))
    bad = []
    for s in r["signals"]:
        if cjk(s["name"]) or cjk(s["message"]):
            bad.append(s["name"])
    check("signals 无中文", not bad, str(bad))
    check("recommendation 无中文", not cjk(r["recommendation"]), r["recommendation"][:40])

    # 失败路径的文案同样会被转述出去，一并检查
    install_stub([], default=None)
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    gaps = (r2["evidence"].get("data_gaps") or [])
    check("data_gaps 无中文",
          not any(cjk(g.get("reason", "")) for g in gaps), str(gaps)[:60])
    check("失败路径 recommendation 无中文",
          not cjk(r2["recommendation"]), r2["recommendation"][:40])

    try:
        risk.validate_address("0xdeadbeef")
    except ValueError as e:
        check("错误信息无中文", not cjk(str(e)), str(e)[:50])


def test_benchmark_oracle_stays_out_of_the_engine():
    """DECISIONS B2：GoPlus 是基准的留出预言机，引擎一旦读它，基准立刻失效。

    这条此前只是文档里的一句约定。约定会被善意地违反——
    「加个 GoPlus 就能补上 EVM 持币集中度」是一个非常合理的想法，
    而做这件事的人多半不会先去读基准的方法论。
    所以把它变成会让构建变红的东西。

    真要接入 GoPlus 时，正确顺序是：先给基准换一个新的独立标注源，
    再改引擎，最后删掉这个测试并在 DECISIONS.md 记录为什么。
    """
    print("\n[DECISIONS B2] 留出预言机不得进入引擎")
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
    forbidden = ("gopluslabs", "goplus")
    offenders = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(src_dir, fn), encoding="utf-8") as f:
            body = f.read().lower()
        for token in forbidden:
            if token in body:
                offenders.append("%s 含 %r" % (fn, token))
    check("src/ 中不得出现 GoPlus", not offenders, "；".join(offenders))


def test_upstream_failure_yields_unknown():
    """铁律：关键维度抓不到数据 → unknown，绝不 low。"""
    print("\n[铁律] 上游失败必须 unknown")
    # 全部数据源失败
    install_stub([], default=None)
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("全失败必须 unknown", r["risk_level"] == "unknown", r["risk_level"])
    check("confidence 必须 low", r["confidence"] == "low", r["confidence"])
    # 这条曾经检查中文词（"试探"/"建仓"）。输出翻成英文后那些词自然不存在，
    # 测试就变成了空过——**因为被检查的东西消失了而通过**，是最没用的一类测试。
    # 现在检查英文里的仓位/投资措辞。
    rec = r["recommendation"].lower()
    banned = ("position size", "buy a small", "small position", "invest",
              "we recommend buying", "safe to buy")
    hit = [w for w in banned if w in rec]
    check("建议里不得含仓位/投资指导", not hit, "命中: %s | %s" % (hit, r["recommendation"]))

    # 只有 honeypot 失败：可卖出性未知，也不允许 low
    install_stub([("dexscreener", _load("ds_weth.json")), ("honeypot.is", None)])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("可卖出性缺失时不得 low", r2["risk_level"] != "low", r2["risk_level"])
    check("必须记录 data_gaps", bool(r2["evidence"].get("data_gaps")), "")


def test_clean_token_stays_low():
    """反向保护：信号变多之后，健康代币不能被评分模型推成 high。"""
    print("\n[评分模型] 健康代币仍为 low")
    install_stub([
        ("dexscreener", _load("ds_weth.json")),
        ("honeypot.is", _load("hp_matic.json")),  # 干净：非 honeypot、零税、低风险
    ])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("WETH 应为 low", r["risk_level"] == "low", "得到 %s (score=%s) %s"
          % (r["risk_level"], r["risk_score"], sig_categories(r)))
    check("分数应当很低", r["risk_score"] < 35, str(r["risk_score"]))

    # 单链不应把干净代币推高
    only_warn = [risk._sig("ok", "a", "", "liquidity"),
                 risk._sig("warn", "b", "", "cross_chain")]
    check("仅 cross_chain warn 不应到 high", risk._score(only_warn) < 70,
          str(risk._score(only_warn)))
    # 但致命信号必须直接顶到 high
    fatal = [risk._sig("fatal", "hp", "", "honeypot")]
    check("fatal 必须 >= 70", risk._score(fatal) >= 70, str(risk._score(fatal)))


def test_output_is_compact():
    """evidence 默认精简；verbose 才给全量。浮点截断到 6 位有效数字。"""
    print("\n[体积] 输出精简")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_matic.json")),
    ])
    slim = run(risk.assess(MATIC, chain_hint="ethereum"))
    payload = json.dumps(slim, ensure_ascii=False)
    check("默认输出 < 1800 字节", len(payload) < 1800, "%d 字节" % len(payload))
    check("不得泄漏原始 reserves", "reserves0" not in payload, "")
    check("不得泄漏 taxDistribution", "taxDistribution" not in payload, "")
    check("浮点已截断",
          len(str(slim["evidence"]["best_pair"]["price_usd"]).split(".")[-1]) <= 8,
          str(slim["evidence"]["best_pair"]["price_usd"]))
    check("_sig_round 生效", risk._sig_round("0.000566716962961376896743") == 0.000566717,
          str(risk._sig_round("0.000566716962961376896743")))


def test_solana_rugcheck_signals():
    """回归：Solana 路径此前只读一个量纲错误的 raw score。

    BONK 的 raw score 是 101，拿它跟阈值 5000 比 —— 任何代币都无条件通过。
    而 rugged / mintAuthority / freezeAuthority / risks[] / topHolders
    就在同一个响应里，全被丢弃。freezeAuthority 是 Solana 版的 honeypot。
    """
    print("\n[Solana] RugCheck 信号")
    install_stub([("dexscreener", _load("ds_bonk.json")),
                  ("rugcheck", _load("rc_bonk.json"))])
    r = run(risk.assess(BONK))
    cats = sig_categories(r)
    check("干净代币权限已销毁应为 ok", cats.get("honeypot") == "ok", str(cats))
    check("必须给出持币集中度", "concentration" in cats, str(cats))
    check("evidence 记录归一化分",
          r["evidence"]["rugcheck"]["score_normalised"] == 7,
          str(r["evidence"]["rugcheck"].get("score_normalised")))
    check("归一化分 7 不应判高风险", cats.get("rugcheck") == "ok", str(cats))

    # 高危变体：freeze + mint 权限未销毁、top10 77%、danger 项
    install_stub([("dexscreener", _load("ds_bonk.json")),
                  ("rugcheck", _load("rc_dangerous.json"))])
    r2 = run(risk.assess(BONK))
    c2 = sig_categories(r2)
    check("冻结权限必须计入 honeypot 维度", c2.get("honeypot") == "critical", str(c2))
    check("增发权限必须标记", c2.get("contract") == "critical", str(c2))
    check("归一化分 68 必须判高", c2.get("rugcheck") == "critical", str(c2))
    check("持币集中 77% 必须 critical", c2.get("concentration") == "critical", str(c2))
    check("整体必须 high", r2["risk_level"] == "high",
          "%s score=%s" % (r2["risk_level"], r2["risk_score"]))


def test_new_pools_is_fail_closed():
    """回归：抓取失败时返回空数组，会让调用方以为『扫过了，没有新池』。"""
    print("\n[fail-closed] new_pools 抓取失败必须报错")
    install_stub([], default=None)
    try:
        run(risk.new_pools("solana"))
        check("上游全失败必须抛错", False, "返回了结果")
    except RuntimeError:
        check("上游全失败抛 RuntimeError", True)

    install_stub([], default={"data": []})
    out = run(risk.new_pools("solana"))
    check("可达但为空返回结构体", isinstance(out, dict), str(type(out)))
    check("count 为 0", out.get("count") == 0, str(out.get("count")))


def test_new_pools_input_guarding():
    print("\n[输入] new_pools 参数防护")
    install_stub([], default={"data": []})
    for bad in ("../etc", "sol ana", "a" * 40):
        try:
            run(risk.new_pools(bad))
            check("new_pools(%r) 必须抛错" % bad, False, "没有抛错")
        except ValueError:
            check("new_pools(%r) 抛 ValueError" % bad, True)
    try:
        run(risk.new_pools("solana", "abc"))
        check("非法 limit 必须抛错", False, "没有抛错")
    except ValueError:
        check("非法 limit 抛 ValueError", True)
    check("链名别名映射", risk._GT_NETWORK["polygon"] == "polygon_pos", "")
    check("ethereum -> eth", risk._GT_NETWORK["ethereum"] == "eth", "")


def test_geckoterminal_fallback_is_multichain():
    """回归 P0-E：兜底此前写死 eth，polygon 上的代币兜底失效。"""
    print("\n[P0-E] GeckoTerminal 兜底多链")
    seen = []

    async def _stub(url, retries=2):
        seen.append(url)
        if "dexscreener" in url:
            return {"pairs": []}
        if "polygon_pos" in url:
            return _load("gt_matic_polygon.json")
        return {"data": []}

    risk._fetch_json = _stub
    r = run(risk.liquidity("0x0000000000000000000000000000000000001010",
                           chain_hint="polygon"))
    check("polygon 兜底命中", r.get("status") == "ok", str(r))
    check("请求打到 polygon_pos", any("polygon_pos" in u for u in seen), str(seen))
    check("链名归一为 polygon", r.get("best_pair_chain") == "polygon",
          str(r.get("best_pair_chain")))


# ---------------------------------------------------------------- main

def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print("=" * 68)
    print("VetAgent 回归测试（离线，基于真实上游快照）")
    print("=" * 68)
    for t in tests:
        t()
    print("\n" + "=" * 68)
    print("通过 %d 项，失败 %d 项" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\n失败明细：")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
