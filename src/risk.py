"""risk.py — VetAgent 核心风险引擎（纯 Python，可在 Pyodide/Worker 跑）。

被 entry.py（HTTP 路由）和 mcp_server.py（MCP 端点）共同引用，单一代码源。

设计铁律 —— fail-closed：
  拿不到数据 → 返回 unknown 或明确的"无法验证"信号，
  绝不返回乐观的中间值，绝不在无数据时给出仓位建议。
"""

import asyncio
import json
import re
from datetime import datetime, timezone

try:  # Worker 运行时
    from workers import fetch as cf_fetch
except ImportError:  # 本地测试 / 非 Worker 运行时（tests 会 monkeypatch _fetch_json）
    cf_fetch = None


# ---------------------------------------------------------------- 基础工具

_EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# DexScreener/chain_hint 的链名 -> GeckoTerminal 的 network id
_GT_NETWORK = {
    "ethereum": "eth", "eth": "eth",
    "bsc": "bsc", "binance": "bsc",
    "polygon": "polygon_pos", "polygon_pos": "polygon_pos", "matic": "polygon_pos",
    "base": "base",
    "arbitrum": "arbitrum", "arbitrum_one": "arbitrum",
    "optimism": "optimism",
    "avalanche": "avax", "avax": "avax",
    "solana": "solana",
}
# 反向：GeckoTerminal network id -> 统一链名
_GT_TO_CHAIN = {"eth": "ethereum", "polygon_pos": "polygon", "avax": "avalanche"}

# 链的"规范性"排序，越小越可信。
# 关键安全属性：pulsechain 这类以太坊分叉链会**继承同一个合约地址**，
# 于是 USDC 的地址在分叉链上也有池子，而且报价完全错误（$0.00097）。
# 实测 DexScreener 对 USDC 返回的 30 个池子里有 29 个在 pulsechain——
# 按数量投票（中位价）必然被分叉链带偏，只能按链的规范性优先。
_CHAIN_RANK = {
    "ethereum": 0, "solana": 0,
    "bsc": 1, "base": 1, "arbitrum": 1, "polygon": 1, "optimism": 1, "avalanche": 1,
    "sui": 2, "ton": 2, "tron": 2, "sei": 2, "blast": 2, "linea": 2,
    "scroll": 2, "mantle": 2, "zksync": 2, "cronos": 2, "celo": 2, "fantom": 2,
}
_UNKNOWN_CHAIN_RANK = 9


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _sig_round(x, digits=6):
    """截断到 N 位有效数字。上游会返回 66 位小数，纯浪费 token。"""
    v = _num(x)
    if v == 0:
        return 0.0
    try:
        return float("%.*g" % (digits, v))
    except (TypeError, ValueError):
        return v


async def _fetch_json(url, retries=2, timeout=8):
    """抓取并解析 JSON。

    返回 dict 表示成功；返回 None 表示**抓取失败**（网络错误/非200/空响应/解析失败）。
    调用方必须区分 None（拿不到数据）和 {}/空列表（拿到了但确实没内容）——
    这是 fail-closed 的前提。
    """
    for attempt in range(retries + 1):
        try:
            resp = await asyncio.wait_for(
                cf_fetch(url, headers={"Accept": "application/json"}), timeout=timeout)
            if resp.status == 200:
                body = await asyncio.wait_for(resp.text(), timeout=timeout)
                if body:
                    return json.loads(body)
        except Exception:  # 超时/网络/解析失败一律视为抓取失败
            pass
        if attempt < retries:
            await asyncio.sleep(0.3 * (2 ** attempt))
    return None


def _looks_evm(address):
    return bool(_EVM_RE.match(address or ""))


def _looks_solana(address):
    if not address or not address.isalnum():
        return False
    if not 32 <= len(address) <= 44:
        return False
    return all(c not in "0OIl" for c in address)


def validate_address(address):
    """地址校验前置。不合法直接抛 ValueError，绝不返回乐观建议。"""
    address = (address or "").strip().split("?")[0]
    if not address or (not _looks_evm(address) and not _looks_solana(address)):
        raise ValueError(
            "Invalid token address: %r (EVM needs 0x + 40 hex chars, Solana needs base58 32-44 chars)" % address)
    return address


def _sig(severity, name, message, category):
    return {"severity": severity, "name": name, "message": message, "category": category}


# ---------------------------------------------------------------- 评分模型

# 单条信号的基础分
_SEVERITY_BASE = {"ok": 0, "info": 5, "warn": 30, "critical": 60, "fatal": 100}

# 类别权重：按"踩中后的实际损失"排序。
# 卖不出去 = 本金归零；流动性枯竭 = 大幅折价；单链 = 几乎不构成独立风险。
_CATEGORY_WEIGHT = {
    "honeypot": 1.0,        # 买了卖不掉
    "sellability": 1.0,     # 可卖出性无法验证
    "sell_tax": 0.9,
    "upstream_risk": 0.8,   # honeypot.is / RugCheck 的聚合判定
    "rugcheck": 0.8,
    "liquidity": 0.8,
    "no_liquidity": 0.8,
    "contract": 0.6,        # 闭源 / 代理合约
    "freshness": 0.5,
    "lifecycle": 0.4,
    "concentration": 0.7,   # 持币集中度
    "cross_chain": 0.2,     # 单链本身不是风险，权重压到很低
}

# 缺失即致命的维度：拿不到就必须 unknown，不能靠其它信号凑出 low
_CRITICAL_DIMENSIONS = ("liquidity", "sellability")


def _score(signals):
    """最坏信号主导 + 佐证加成，而不是朴素求和。

    朴素求和的问题：信号越多分越高，加几个新维度就会把正常币推成 high。
    这里改成 max(加权单项) + 每多一个独立的 warn+ 类别 +10（最多 +30）。
    """
    if not signals:
        return 0
    weighted = [
        _SEVERITY_BASE.get(s["severity"], 5) * _CATEGORY_WEIGHT.get(s["category"], 0.5)
        for s in signals
    ]
    worst = max(weighted)
    bad_categories = {s["category"] for s in signals
                      if s["severity"] in ("warn", "critical", "fatal")}
    corroboration = min(30, 10 * max(0, len(bad_categories) - 1))
    return int(min(100, round(worst + corroboration)))


def _finalize(address, signals, evidence, data_gaps):
    """汇总。fail-closed：关键维度缺数据 → unknown，绝无默认乐观值。"""
    result = {"address": address, "signals": signals, "evidence": evidence}
    if data_gaps:
        evidence["data_gaps"] = data_gaps

    if not signals:
        result.update(risk_level="unknown", risk_score=0, confidence="low",
                      recommendation="Not enough data to judge. Verify the address and retry; do not act on this result.")
        return result

    score = _score(signals)
    worst = max((s["severity"] for s in signals), key=lambda s: _SEVERITY_BASE.get(s, 0))

    if worst == "fatal" or score >= 70:
        level = "high"
    elif score >= 35:
        level = "medium"
    elif any(s["severity"] in ("warn", "critical") for s in signals):
        level = "medium"
    else:
        level = "low"

    # fail-closed 覆盖：关键维度拿不到数据时，不允许给出 low/medium 的安全感。
    missing_critical = [g for g in data_gaps if g.get("dimension") in _CRITICAL_DIMENSIONS]
    if missing_critical and level in ("low", "medium"):
        level = "unknown"

    total = len(signals)
    has_liquidity = any(s["category"] in ("liquidity", "no_liquidity") for s in signals)
    has_sellability = any(s["category"] in ("honeypot", "sellability", "rugcheck")
                          for s in signals)
    # confidence 衡量的是**数据完整度**，不是风险高低
    if data_gaps or total < 2:
        confidence = "low"
    elif has_liquidity and has_sellability and total >= 4:
        confidence = "high"
    else:
        confidence = "medium"
    evidence["confidence"] = confidence

    result.update(
        risk_level=level, risk_score=score, confidence=confidence,
        recommendation={
            "high": "High risk. A fatal or high-severity signal fired - see signals for the specific reason. Do not proceed without review.",
            "medium": "Medium risk. Real signals fired but none are fatal. Review liquidity, holder distribution and contract permissions before deciding.",
            "low": "Low risk - meaning no fatal signal appeared in the checks that ran. This is not the same as safe to buy, and covers on-chain risk only.",
            "unknown": "Not assessed. A critical check could not be completed, so this is NOT a low-risk result and must not justify a trade. See evidence.data_gaps.",
        }[level])
    return result


# ---------------------------------------------------------------- 选池

def _pair_liquidity(pair):
    liq = pair.get("liquidity") or {}
    v = liq.get("usd", 0)
    if not v:
        v = pair.get("reserveInUsd") or 0
    return _num(v)


def _pick_best(pairs, chain_hint=None, target=None):
    """稳健选池：目标链优先 → 必须含目标地址 → 价格合理 → 流动性最大。

    只按流动性最大选会选中跨链分叉上的错价池
    （USDC 会被选到 pulsechain 的池子，报价 $0.00097）。
    """
    target_l = (target or "").lower()

    def _valid(p):
        # 流动性是硬要求；价格只在**存在**时才做合理性检查
        # （GeckoTerminal 的 base_token_price_usd 常为 null，不能因此丢弃有效池）。
        if _pair_liquidity(p) <= 0:
            return False
        price = p.get("priceUsd")
        return True if price in (None, "") else _num(price) > 1e-12

    def _is_target(p):
        bt = ((p.get("baseToken") or {}).get("address") or "").lower()
        qt = ((p.get("quoteToken") or {}).get("address") or "").lower()
        return (bt == target_l or qt == target_l) if target_l else True

    if not pairs:
        return None
    hint = (chain_hint or "").lower()
    scoped = [p for p in pairs if (p.get("chainId") or "").lower() == hint] if hint else pairs
    candidates = [p for p in scoped if _valid(p)] or [p for p in pairs if _valid(p)]
    target_pools = [p for p in candidates if _is_target(p)]
    pool = target_pools or candidates
    if not pool:
        return None

    # 无 chain_hint 时：先按链的规范性收敛，再在同档内比流动性。
    # 这样 pulsechain 上继承地址的错价池不会盖过以太坊主网的真池，
    # 哪怕它在数量和名义流动性上都占优。
    if not hint:
        best_rank = min(_CHAIN_RANK.get((p.get("chainId") or "").lower(), _UNKNOWN_CHAIN_RANK)
                        for p in pool)
        pool = [p for p in pool
                if _CHAIN_RANK.get((p.get("chainId") or "").lower(),
                                   _UNKNOWN_CHAIN_RANK) == best_rank] or pool
    return max(pool, key=_pair_liquidity)


def _pair_created_ms(value):
    """DexScreener 给的是**毫秒整数**，GeckoTerminal 给的是 ISO 字符串。

    旧代码只处理 ISO，对 int 调用 .replace() 抛 AttributeError 后被
    `except Exception: pass` 吞掉 —— 主数据源上交易对年龄信号从未生效过。
    """
    if value in (None, "", 0):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v > 1e11 else v * 1000  # 秒 -> 毫秒
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            v = float(s)
            return v if v > 1e11 else v * 1000
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp() * 1000
        except (ValueError, OverflowError):
            return None
    return None


def _age_days(created_value, now=None):
    ms = _pair_created_ms(created_value)
    if ms is None:
        return None
    now = now or datetime.now(timezone.utc)
    days = (now.timestamp() * 1000 - ms) / 86400000.0
    return int(days) if days >= 0 else None


def _gt_base_price(a):
    """GeckoTerminal 的 base_token_price_usd 经常是 null，但价格是可推导的：
    base_token_price_quote_token × quote_token_price_usd。
    """
    price = a.get("base_token_price_usd")
    if price not in (None, "", "0"):
        return price
    bq = _num(a.get("base_token_price_quote_token"))
    qu = _num(a.get("quote_token_price_usd"))
    return bq * qu if bq and qu else None


def _gt_to_pair(p, address, network):
    a = p.get("attributes") or {}
    return {
        "dexId": "geckoterminal",
        "chainId": _GT_TO_CHAIN.get(network, network),
        "liquidity": {"usd": _num(a.get("reserve_in_usd"))},
        "priceUsd": _gt_base_price(a),
        "pairCreatedAt": a.get("pool_created_at"),
        "volume": {"h24": _num((a.get("volume_usd") or {}).get("h24"))},
        "baseToken": {"address": address},
        "quoteToken": {"address": ""},
    }


# ---------------------------------------------------------------- 信号构建

def _liquidity_signals(best, pairs, signals, evidence):
    liq = _pair_liquidity(best)
    vol = _num((best.get("volume") or {}).get("h24"))
    evidence["best_pair"] = {
        "dex": best.get("dexId"), "chain": best.get("chainId"),
        "liquidity_usd": _sig_round(liq), "price_usd": _sig_round(best.get("priceUsd")),
        "volume_24h_usd": _sig_round(vol), "pair_created_at": best.get("pairCreatedAt"),
    }
    if liq < 5000:
        signals.append(_sig("critical", "Very low liquidity",
                            "Main pair holds only $%s. High rug and slippage risk." % format(liq, ",.0f"),
                            "liquidity"))
    elif liq < 50000:
        signals.append(_sig("warn", "Thin liquidity",
                            "Main pair holds $%s." % format(liq, ",.0f"), "liquidity"))
    else:
        signals.append(_sig("ok", "Liquidity is adequate",
                            "Main pair holds $%s." % format(liq, ",.0f"), "liquidity"))

    chains = sorted({p.get("chainId") for p in pairs if p.get("chainId")})
    evidence["chains"] = chains
    if len(chains) > 1:
        signals.append(_sig("ok", "Trades on multiple chains", "Found on %d chains." % len(chains), "cross_chain"))

    age = _age_days(best.get("pairCreatedAt"))
    if age is not None:
        evidence["pair_age_days"] = age
        if age < 3:
            signals.append(_sig("critical", "Very new pair",
                                "Main pair is only %d days old, the highest-risk window for a rug." % age, "freshness"))
        elif age < 30:
            signals.append(_sig("warn", "Recently created pair", "Main pair is %d days old." % age, "freshness"))
        else:
            signals.append(_sig("ok", "Established pair", "Main pair has existed for %d days." % age, "freshness"))

    # 生命周期：区分"合约安全"与"代币还有没有人交易"
    if liq > 0:
        turnover = vol / liq
        evidence["turnover_24h"] = _sig_round(turnover, 4)
        if turnover < 0.02 and (age or 0) > 180:
            signals.append(_sig("warn", "Looks abandoned",
                                "$%s of liquidity but only $%s traded in 24h (%.1f%% turnover). "
                                "An old pool this quiet usually means the token migrated or was abandoned."
                                % (format(liq, ",.0f"), format(vol, ",.0f"), turnover * 100),
                                "lifecycle"))
        elif turnover < 0.02:
            signals.append(_sig("warn", "Very little trading",
                                "Turnover is only %.1f%%. Exiting at size may be difficult." % (turnover * 100),
                                "lifecycle"))


def _honeypot_signals(hp, signals, evidence, data_gaps):
    """honeypot.is 解读。

    旧代码从 simulationResult 里读 isHoneypot —— 那个键在上游根本不存在
    （真值在 honeypotResult.isHoneypot），导致 honeypot 维度恒为 "ok"。
    同时 summary.risk / flags / contractCode 这些已抓到的字段全被丢弃。
    """
    if hp is None:
        data_gaps.append({"dimension": "sellability", "source": "honeypot.is",
                          "reason": "upstream request failed"})
        signals.append(_sig("warn", "Sellability unverified",
                            "The sell-simulation service did not respond, so we could not confirm this token can be sold.", "sellability"))
        return

    summary = hp.get("summary") or {}
    sim_ok = hp.get("simulationSuccess")
    hp_result = hp.get("honeypotResult") or {}
    sim = hp.get("simulationResult") or {}
    is_hp = hp_result.get("isHoneypot")
    flags = [f.get("flag") for f in (summary.get("flags") or []) if isinstance(f, dict)]

    evidence["honeypot"] = {
        "is_honeypot": is_hp,
        "simulation_success": sim_ok,
        "simulation_error": hp.get("simulationError"),
        "upstream_risk": summary.get("risk"),
        "upstream_risk_level": summary.get("riskLevel"),
        "flags": flags,
        "buy_tax": sim.get("buyTax"), "sell_tax": sim.get("sellTax"),
        "transfer_tax": sim.get("transferTax"),
        "open_source": (hp.get("contractCode") or {}).get("openSource"),
        "is_proxy": (hp.get("contractCode") or {}).get("isProxy"),
        "holders": (hp.get("token") or {}).get("totalHolders"),
    }

    if is_hp is True:
        signals.append(_sig("fatal", "Honeypot", "Simulation confirms it: you can buy, you cannot sell.", "honeypot"))
    elif sim_ok is False or is_hp is None:
        err = hp.get("simulationError") or "未知原因"
        data_gaps.append({"dimension": "sellability", "source": "honeypot.is",
                          "reason": "simulation failed: %s" % err})
        signals.append(_sig("critical", "Sellability unverified",
                            "Buy/sell simulation failed (%s), so we cannot confirm this token can be sold." % err, "sellability"))
    else:
        sell_tax, buy_tax = _num(sim.get("sellTax")), _num(sim.get("buyTax"))
        transfer_tax = _num(sim.get("transferTax"))
        worst_tax = max(sell_tax, buy_tax, transfer_tax)
        if worst_tax > 20:
            signals.append(_sig("critical", "Extreme transaction tax",
                                "buy %.1f%% / sell %.1f%% / transfer %.1f%%"
                                % (buy_tax, sell_tax, transfer_tax), "sell_tax"))
        elif worst_tax > 5:
            signals.append(_sig("warn", "Elevated transaction tax",
                                "buy %.1f%% / sell %.1f%%" % (buy_tax, sell_tax), "sell_tax"))
        else:
            signals.append(_sig("ok", "Buys and sells normally",
                                "Simulation passed. Buy %.1f%% / sell %.1f%% tax." % (buy_tax, sell_tax),
                                "honeypot"))

    # 上游聚合判定（此前被完全丢弃）
    up = (summary.get("risk") or "").lower()
    flag_txt = "；".join(flags) if flags else "无"
    level_txt = summary.get("riskLevel")
    if up == "very_high":
        signals.append(_sig("critical", "Upstream scanner rates this very high risk",
                            "honeypot.is riskLevel=%s, flags: %s" % (level_txt, flag_txt), "upstream_risk"))
    elif up == "high":
        signals.append(_sig("warn", "Upstream scanner rates this high risk",
                            "honeypot.is riskLevel=%s, flags: %s" % (level_txt, flag_txt), "upstream_risk"))
    elif up == "medium":
        signals.append(_sig("warn", "Upstream scanner rates this medium risk",
                            "honeypot.is riskLevel=%s, flags: %s" % (level_txt, flag_txt), "upstream_risk"))
    elif up == "low":
        signals.append(_sig("ok", "Upstream scanner rates this low risk",
                            "honeypot.is riskLevel=%s" % level_txt, "upstream_risk"))

    if (hp.get("contractCode") or {}).get("openSource") is False:
        signals.append(_sig("warn", "Contract is closed source",
                            "Source is not published, so hidden logic (minting, blacklists, adjustable tax) cannot be ruled out.", "contract"))


def _rugcheck_signals(rc, signals, evidence, data_gaps):
    """RugCheck 解读（Solana）。

    旧代码只读了一个 raw `score`，还拿它跟 5000/10000 比——量纲完全不对：
    BONK 的 raw score 是 101，任何正常代币都会无条件通过。
    真正该用的是 score_normalised(0-100)，而 rugged / mintAuthority /
    freezeAuthority / risks[] / topHolders 这些字段同一个响应里就有，全被丢了。
    其中 freezeAuthority 是 Solana 版的 honeypot——持有者可被冻结，等同卖不出去。
    """
    if rc is None:
        data_gaps.append({"dimension": "sellability", "source": "rugcheck",
                          "reason": "upstream request failed"})
        signals.append(_sig("warn", "Contract safety unverified",
                            "RugCheck did not respond, so rug risk could not be assessed.", "sellability"))
        return

    # 空响应 vs 「有报告且评分为 0」必须区分开
    if not rc.get("mint") and not rc.get("token") and rc.get("score") is None:
        data_gaps.append({"dimension": "sellability", "source": "rugcheck",
                          "reason": "no risk report returned"})
        signals.append(_sig("warn", "No RugCheck report",
                            "RugCheck returned no risk report for this token.", "sellability"))
        return

    risks = [r for r in (rc.get("risks") or []) if isinstance(r, dict)]
    top_holders = [h for h in (rc.get("topHolders") or []) if isinstance(h, dict)]
    top10 = sum(_num(h.get("pct")) for h in top_holders[:10])
    normalised = _num(rc.get("score_normalised"))

    evidence["rugcheck"] = {
        "rugged": rc.get("rugged"),
        "score_normalised": rc.get("score_normalised"),
        "score_raw": rc.get("score"),
        "mint_authority": rc.get("mintAuthority"),
        "freeze_authority": rc.get("freezeAuthority"),
        "total_holders": rc.get("totalHolders"),
        "top10_holder_pct": _sig_round(top10, 4),
        "lockers": len(rc.get("lockers") or {}),
        "risks": [{"name": r.get("name"), "level": r.get("level")} for r in risks],
    }

    if rc.get("rugged") is True:
        signals.append(_sig("fatal", "Already rugged",
                            "RugCheck has flagged this token as rugged.", "rugcheck"))

    # freezeAuthority 存在 = 官方可冻结你的余额 = Solana 版 honeypot
    if rc.get("freezeAuthority"):
        signals.append(_sig("critical", "Freeze authority still active",
                            "freezeAuthority was never revoked. Holder balances can be frozen, which is equivalent to being unable to sell.",
                            "honeypot"))
    if rc.get("mintAuthority"):
        signals.append(_sig("critical", "Mint authority still active",
                            "mintAuthority was never revoked. Supply can be inflated without limit.", "contract"))
    if not rc.get("freezeAuthority") and not rc.get("mintAuthority"):
        signals.append(_sig("ok", "Authorities revoked",
                            "Both mint and freeze authority have been given up.", "honeypot"))

    # risks[] 里的每一项已经计入 score_normalised，不能再各发一条信号——
    # 那是重复计分，会把 BONK 这种归一化分只有 7 的正经代币误伤成 medium。
    # 处理方式：warn 级只作为主信号的说明文字；danger 级才单独升一条，
    # 因为聚合分有可能低估"冻结权限未销毁"这类一票否决项。
    names = [r.get("name") for r in risks if r.get("name")]
    detail = ("；".join(names[:4])) if names else "无风险项"
    if normalised >= 50:
        signals.append(_sig("critical", "RugCheck rates this high risk",
                            "Normalised risk score %.0f/100 (%s)." % (normalised, detail), "rugcheck"))
    elif normalised >= 20:
        signals.append(_sig("warn", "RugCheck rates this medium risk",
                            "Normalised risk score %.0f/100 (%s)." % (normalised, detail), "rugcheck"))
    else:
        signals.append(_sig("ok", "RugCheck passed",
                            "Normalised risk score %.0f/100 (%s)." % (normalised, detail), "rugcheck"))

    danger = [r.get("name") for r in risks if (r.get("level") or "").lower() == "danger"]
    if danger:
        signals.append(_sig("critical", "RugCheck danger flags",
                            "; ".join(n for n in danger if n), "rugcheck"))

    # 持币集中度：单一 rug 预测力最强的信号，数据同一响应里就有
    if top_holders:
        if top10 >= 70:
            signals.append(_sig("critical", "Holdings are highly concentrated",
                                "Top 10 addresses hold %.1f%%. A handful of wallets could crash the price." % top10, "concentration"))
        elif top10 >= 50:
            signals.append(_sig("warn", "Holdings are concentrated",
                                "Top 10 addresses hold %.1f%%." % top10, "concentration"))
        else:
            signals.append(_sig("ok", "Holdings are well distributed",
                                "Top 10 addresses hold %.1f%%." % top10, "concentration"))


# ---------------------------------------------------------------- 三个工具

async def _load_pairs(address, chain_hint):
    """取交易对。返回 (pairs, source)；pairs 为 None 表示两个数据源都失败。"""
    ds = await _fetch_json("https://api.dexscreener.com/latest/dex/tokens/%s" % address)
    if ds is not None:
        pairs = ds.get("pairs") or []
        if pairs:
            return pairs, "dexscreener"
    # 兜底：GeckoTerminal。按 chain_hint 选网络，不再写死 eth。
    networks = []
    if chain_hint:
        n = _GT_NETWORK.get(chain_hint.strip().lower())
        if n:
            networks.append(n)
    if not networks:
        networks = ["solana"] if _looks_solana(address) else ["eth", "base", "bsc", "polygon_pos"]
    for net in networks:
        gt = await _fetch_json(
            "https://api.geckoterminal.com/api/v2/networks/%s/tokens/%s/pools" % (net, address))
        if gt is None:
            continue
        pools = gt.get("data") or []
        if pools:
            return [_gt_to_pair(p, address, net) for p in pools], "geckoterminal"
    if ds is None:
        return None, None  # 抓取失败，不是"确实没有池子"
    return [], "dexscreener"


# 精简模式下保留的 evidence 字段
_SLIM_EVIDENCE_KEYS = (
    "best_pair", "chains", "pair_age_days", "turnover_24h", "honeypot",
    "rugcheck", "liquidity_source", "confidence", "data_gaps",
)


async def assess(address, chain_hint=None, verbose=False):
    """核心：代币风险画像。fail-closed，地址校验前置。"""
    address = validate_address(address)
    signals, evidence, data_gaps = [], {}, []

    pairs, source = await _load_pairs(address, chain_hint)
    if pairs is None:
        data_gaps.append({"dimension": "liquidity", "source": "dexscreener+geckoterminal",
                          "reason": "upstream request failed"})
        signals.append(_sig("warn", "Liquidity data unavailable",
                            "Both market data sources failed, so liquidity could not be assessed.", "no_liquidity"))
    elif not pairs:
        data_gaps.append({"dimension": "liquidity", "source": source,
                          "reason": "no trading pair found"})
        signals.append(_sig("warn", "No trading pair found",
                            "No pair was found for this address. It may be brand new, or the address may be wrong.",
                            "no_liquidity"))
    else:
        evidence["liquidity_source"] = source
        best = _pick_best(pairs, chain_hint=chain_hint, target=address)
        if best is None:
            data_gaps.append({"dimension": "liquidity", "source": source,
                              "reason": "no pair with a sane price"})
            signals.append(_sig("warn", "No usable pool",
                                "Pairs exist but none had a sane price.", "no_liquidity"))
        else:
            _liquidity_signals(best, pairs, signals, evidence)

    if _looks_evm(address):
        _honeypot_signals(
            await _fetch_json("https://api.honeypot.is/v2/IsHoneypot?address=%s" % address),
            signals, evidence, data_gaps)
    elif _looks_solana(address):
        _rugcheck_signals(
            await _fetch_json("https://api.rugcheck.xyz/v1/tokens/%s/report" % address),
            signals, evidence, data_gaps)

    result = _finalize(address, signals, evidence, data_gaps)
    if not verbose:
        # 默认精简：agent 用不上 reserves/txHash/taxDistribution 这类原始字段
        result["evidence"] = {k: v for k, v in result["evidence"].items()
                              if k in _SLIM_EVIDENCE_KEYS}
    return result


async def liquidity(address, chain_hint=None):
    """流动性快照。与 assess 共用同一套校验与选池逻辑。"""
    address = validate_address(address)
    pairs, source = await _load_pairs(address, chain_hint)
    if pairs is None:
        return {"address": address, "status": "unavailable",
                "note": "Market data request failed. This does NOT mean the token has no liquidity."}
    if not pairs:
        return {"address": address, "status": "not_found", "liquidity_usd": 0,
                "pairs_total": 0, "note": "No trading pair found for this address."}
    best = _pick_best(pairs, chain_hint=chain_hint, target=address)
    if best is None:
        return {"address": address, "status": "not_found", "liquidity_usd": 0,
                "pairs_total": len(pairs), "note": "Pairs exist but none had a sane price."}
    return {
        "address": address, "status": "ok", "source": source,
        "best_pair_chain": best.get("chainId"), "best_pair_dex": best.get("dexId"),
        "price_usd": _sig_round(best.get("priceUsd")),
        "liquidity_usd": _sig_round(_pair_liquidity(best)),
        "volume_24h_usd": _sig_round(_num((best.get("volume") or {}).get("h24"))),
        "pairs_total": len(pairs),
        "chains": sorted({p.get("chainId") for p in pairs if p.get("chainId")}),
    }


async def new_pools(chain="solana", limit=10):
    """扫描某链新池/热门池。"""
    chain = (chain or "solana").strip().lower()
    net = _GT_NETWORK.get(chain, chain)
    if not re.match(r"^[a-z0-9_\-]{1,32}$", net):
        raise ValueError("Invalid chain name: %r" % chain)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValueError("Invalid limit: %r" % limit)
    limit = max(1, min(50, limit))

    merged = {}
    reachable = False
    for kind, path in (("new", "new_pools"), ("trending", "trending_pools")):
        data = await _fetch_json(
            "https://api.geckoterminal.com/api/v2/networks/%s/%s" % (net, path))
        if data is None:
            continue  # 该端点抓取失败
        reachable = True
        for p in (data.get("data") or []):
            pid = p.get("id")
            if not pid or pid in merged:
                continue
            a = p.get("attributes") or {}
            merged[pid] = {
                "kind": kind, "pool_id": pid, "name": a.get("name"),
                "price_usd": _sig_round(a.get("base_token_price_usd")),
                "liquidity_usd": _sig_round(a.get("reserve_in_usd")),
                "volume_24h_usd": _sig_round((a.get("volume_usd") or {}).get("h24")),
                "pool_age_days": _age_days(a.get("pool_created_at")),
            }
    if not reachable:
        # fail-closed：抓不到 ≠ 没有新池，不能返回空数组让调用方以为「扫过了，没东西」
        raise RuntimeError("GeckoTerminal request failed; could not scan new pools on %s" % chain)
    return {"chain": chain, "network": net, "count": len(merged),
            "pools": list(merged.values())[:limit]}
