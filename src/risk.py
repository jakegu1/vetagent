"""risk.py — VetAgent 核心风险引擎（纯 Python，可在 Pyodide/Worker 跑）。

被 entry.py（HTTP 路由）和 mcp_server.py（MCP 端点）共同引用，单一代码源。
"""

import asyncio
import json
from datetime import datetime, timezone

from workers import fetch as cf_fetch  # SDK 提供的 fetch

# --- 纯 Python 工具函数 ---


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


async def _fetch_json(url, retries=2):
    """抓取并解析 JSON，带指数退避重试（消除冷启动超时）。"""
    last = {}
    for attempt in range(retries + 1):
        try:
            resp = await cf_fetch(url, headers={"Accept": "application/json"})
            if resp.status == 200:
                data = await resp.text()
                if data:
                    return json.loads(data)
        except Exception:
            if attempt < retries:
                await asyncio.sleep(0.3 * (2 ** attempt))
    return last


def _fdv_or_zero(pair):
    liq = pair.get("liquidity") or {}
    v = liq.get("usd", 0)
    if not v:
        v = pair.get("reserveInUsd") or pair.get("fdv") or 0
    return _num(v)


def _looks_evm(address):
    return len(address) == 42 and address.startswith("0x")


def _looks_solana(address):
    if not address or not address.isalnum():
        return False
    if not 32 <= len(address) <= 44:
        return False
    return all(c not in "0OIl" for c in address)


def _sig(severity, name, message, category):
    return {"severity": severity, "name": name, "message": message, "category": category}


def _severity(level):
    return {"ok": 0, "info": 10, "warn": 30, "critical": 55, "fatal": 80}.get(level, 10)


def _finalize(address, signals, evidence):
    """汇总评分。fail-closed：无数据 → unknown，绝无默认乐观值。"""
    if not signals:
        # 一条信号都没有 = 完全无数据 → 必须 unknown，不能给任何仓位建议
        return {"address": address, "risk_level": "unknown", "risk_score": 0,
                "signals": [], "recommendation": "数据不足，无法判定风险。请核实地址与数据源。",
                "confidence": "low", "evidence": evidence}
    score = min(100, sum(_severity(s["severity"]) for s in signals))
    has_positive = any(s["severity"] in ("ok", "info") for s in signals)
    has_warn_or_worse = any(s["severity"] in ("warn", "critical", "fatal") for s in signals)
    if score >= 55:
        level = "high"
    elif score >= 25:
        level = "medium"
    elif has_warn_or_worse:
        level = "medium"  # 只有 warn 无 critical 但确实有风险信号
    elif has_positive:
        level = "low"
    else:
        level = "unknown"
    # 组合规则
    risk_factors = {s["category"] for s in signals if s["severity"] in ("critical", "fatal")}
    warn_factors = {s["category"] for s in signals if s["severity"] == "warn"}
    combo = []
    if "liquidity" in risk_factors and "freshness" in risk_factors:
        combo.append("很低流动性 + 极新池子")
    if "liquidity" in risk_factors and "cross_chain" in warn_factors:
        combo.append("很低流动性 + 单链")
    if "freshness" in risk_factors and "cross_chain" in warn_factors:
        combo.append("极新池子 + 单链")
    if combo:
        level = "high"
        evidence["risk_combo"] = combo
        signals.append(_sig("critical", "危险组合", "叠加: " + "；".join(combo), "combo"))
    critical = [s for s in signals if s["severity"] in ("critical", "fatal")]
    if level == "high" and not critical:
        level = "medium"
    info_ok = sum(1 for s in signals if s["severity"] in ("ok", "info"))
    definite = sum(1 for s in signals if s["severity"] in ("warn", "critical", "fatal"))
    total = len(signals)
    # confidence：信号越全越可靠；关键数据缺失时降级
    has_liquidity = any(s["category"] == "liquidity" for s in signals)
    confidence = "low" if total < 2 else ("high" if definite and total >= 3 and info_ok >= 1 and has_liquidity else "medium")
    evidence["confidence"] = confidence
    rec = ("高风险：不建议在没有深入审核的情况下大额买入。先核实合约/持有/审计。" if level == "high" else (
        "中等风险：谨慎为上，需进一步核实流动性、持币分布与合约权限后才考虑建仓。" if level == "medium" else (
        "低风险：流动性充足且无 honeypot/高税/失活信号，可正常评估。" if level == "low" else
        "数据不足，无法判定风险，建议二次核实地址与数据源。")))
    return {"address": address, "risk_level": level, "risk_score": score,
            "signals": signals, "recommendation": rec, "confidence": confidence, "evidence": evidence}


# --- 三个工具 ---


def _pick_best(pairs, chain_hint=None, target=None):
    """稳健选池：优先目标链，再匹配 base/quote 含目标地址，选流动性最大且价格合理。

    修复 P0-1：旧逻辑只按流动性最大选，会把稳定币跨链假池/pulsechain 错价池当主池。
    """
    target_l = (target or "").lower()
    def _valid(p):
        return _fdv_or_zero(p) > 0 and _num(p.get("priceUsd")) > 1e-9
    def _is_target(p):
        bt = ((p.get("baseToken") or {}).get("address") or "").lower()
        qt = ((p.get("quoteToken") or {}).get("address") or "").lower()
        if target_l:
            return bt == target_l or qt == target_l
        return True
    # 先按 chain_hint 过滤（如果有）
    chain_pool = [p for p in pairs if (p.get("chainId") or "").lower() == (chain_hint or "").lower()] if chain_hint else pairs
    candidates = [p for p in chain_pool if _valid(p)]
    # 优先目标的池
    target_pools = [p for p in candidates if _is_target(p)]
    pool = target_pools or candidates or pairs
    if not pool:
        return None
    return max(pool, key=lambda p: _fdv_or_zero(p))


async def assess(address, chain_hint=None):
    """核心：代币风险画像。fail-closed，地址校验前置。

    P0-2 修复：地址格式不合法直接抛错，绝不返回乐观建议。
    """
    # --- 输入校验前置 (P0-2) ---
    import re
    address = (address or "").strip().split("?")[0]
    if not address or not re.match(r"^0x[a-fA-F0-9]{40}$", address) and not _looks_solana(address):
        raise ValueError(f"无效的代币地址: {address!r}（EVM 需 0x+40hex，Solana 需 base58 32-44 位）")
    signals = []
    evidence = {}
    liquidity_source = "dexscreener"
    ds = await _fetch_json(f"https://api.dexscreener.com/latest/dex/tokens/{address}")
    pairs = ds.get("pairs", [])
    if not pairs:
        # 兜底：DexScreener 失败/限流时用 GeckoTerminal（同一 token 的池子）
        liquidity_source = "geckoterminal"
        gt = await _fetch_json(f"https://api.geckoterminal.com/api/v2/networks/eth/tokens/{address}/pools")
        gt_pools = gt.get("data", [])
        if gt_pools:
            # 转成统一结构（chainId 用 ethereum，与 chain_hint/DexScreener 一致）
            def _gt_to_pair(p):
                ga = p.get("attributes", {})
                return {
                    "dexId": "geckoterminal",
                    "chainId": "ethereum",  # 修正: GeckoTerminal 用 'eth'，统一为 'ethereum'
                    "liquidity": {"usd": float(ga.get("reserve_in_usd") or 0)},
                    "priceUsd": ga.get("base_token_price_usd"),
                    "pairCreatedAt": ga.get("pool_created_at"),
                    "volume": {"h24": float(ga.get("volume_usd", {}).get("h24") or 0)},
                    "baseToken": {"address": address},  # 让 _pick_best 能匹配目标地址
                    "quoteToken": {"address": ""},
                }
            pairs = [_gt_to_pair(p) for p in gt_pools]
    if pairs:
        # P0-1 修复：用稳健选池逻辑（目标链优先 + 匹配目标地址 + 流动性最大且价格合理）
        best = _pick_best(pairs, chain_hint=chain_hint, target=address)
        if best is None:
            signals.append(_sig("warn", "未找到有效流动性池", "无价格合理的流动性池，可能为新币或数据缺失", "no_liquidity"))
            return _finalize(address, signals, evidence)
        liq = _fdv_or_zero(best)
        evidence["best_pair"] = {"dex": best.get("dexId"), "chain": best.get("chainId"),
                                 "liquidity_usd": liq, "pair_created_at": best.get("pairCreatedAt"),
                                 "price_usd": best.get("priceUsd"),
                                 "volume_24h": _num((best.get("volume") or {}).get("h24"))}
        evidence["volume_h24"] = _num((best.get("volume") or {}).get("h24"))
        evidence["liquidity_source"] = liquidity_source
        if liq < 5000:
            signals.append(_sig("critical", "流动性极低", f"主交易对流动性仅 ${liq:,.0f}，rug/滑点风险极高", "liquidity"))
        elif liq < 50000:
            signals.append(_sig("warn", "流动性偏弱", f"主交易对流动性 ${liq:,.0f}", "liquidity"))
        else:
            signals.append(_sig("ok", "流动性充足", f"主交易对流动性 ${liq:,.0f}", "liquidity"))
        chains = {p.get("chainId") for p in pairs}
        evidence["chains"] = sorted(c for c in chains if c)
        if len(chains) <= 1:
            signals.append(_sig("warn", "单链代币", "仅存在于单个链，流动性难跨链验证", "cross_chain"))
        else:
            signals.append(_sig("ok", "多链流通", f"见于 {len(chains)} 条链", "cross_chain"))
    else:
        signals.append(_sig("warn", "未找到流动性", "DexScreener 未检索到该地址的交易对", "no_liquidity"))
    if _looks_evm(address):
        hp = await _fetch_json(f"https://api.honeypot.is/v2/IsHoneypot?address={address}")
        evidence["honeypot"] = hp
        summary = hp.get("simulationResult", {})
        if summary.get("isHoneypot", False):
            signals.append(_sig("fatal", "Honeypot 检测", "仿真检测出 honeypot：只能买不能卖需警惕", "honeypot"))
        else:
            sell_tax = _num(summary.get("sellTax"))
            if sell_tax and sell_tax > 20:
                signals.append(_sig("critical", "高卖方税", f"卖出税 {sell_tax:.0f}%，可能无法正常卖出", "sell_tax"))
            else:
                signals.append(_sig("ok", "非 Honeypot", "未检测到 honeypot 特征", "honeypot"))
    elif _looks_solana(address):
        rc = await _fetch_json(f"https://api.rugcheck.xyz/v1/tokens/{address}/report")
        evidence["rugcheck"] = rc
        rc_score = _num(rc.get("score"))
        if rc_score and rc_score >= 10000:
            signals.append(_sig("critical", "Rugcheck 高风险", f"rug 评分 {rc_score:,.0f}", "rugcheck"))
        elif rc_score and rc_score >= 5000:
            signals.append(_sig("warn", "Rugcheck 中风险", f"rug 评分 {rc_score:,.0f}", "rugcheck"))
        elif rc_score:
            signals.append(_sig("ok", "Rugcheck 通过", f"rug 评分 {rc_score:,.0f}，低于阈值", "rugcheck"))
        else:
            signals.append(_sig("info", "Rugcheck 无数据", "RugCheck 未返回该代币的风险报告", "rugcheck"))
    created = evidence.get("best_pair", {}).get("pair_created_at")
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - dt).days
            evidence["pair_age_days"] = age
            if age < 3:
                signals.append(_sig("critical", "极新交易对", f"主交易对仅 {age} 天，rug/跑路高发期", "freshness"))
            elif age < 30:
                signals.append(_sig("warn", "较新交易对", f"主交易对 {age} 天", "freshness"))
            else:
                signals.append(_sig("ok", "成熟交易对", f"交易对已存在 {age} 天", "freshness"))
        except Exception:
            pass

    # --- 生命周期信号（代币"还有没有生命"，区别于合约风险）---
    # P0-3 修复：只有在有真实流动性数据时才判断活跃度；无数据时不判"活跃"，避免自相矛盾。
    bp = evidence.get("best_pair") or {}
    liq = _num(bp.get("liquidity_usd"))
    vol = _num((evidence.get("volume_h24")))
    has_liq_data = bool(bp) and liq > 0
    if has_liq_data:
        turnover = (vol / liq) if liq and liq > 0 else 0
        evidence["turnover_24h"] = round(turnover, 4)
        age = evidence.get("pair_age_days")
        if turnover < 0.05 and age and age > 180:
            signals.append(_sig("warn", "流动性冷清(疑似失活)",
                                f"流动性 ${liq:,.0f} 但24h成交仅 ${vol:,.0f}（换手率 {turnover:.1%}），"
                                f"老池({age}天)代币可能已迁移/被弃用，流动性偏冷清", "lifecycle"))
        elif turnover < 0.10:
            signals.append(_sig("warn", "流动性冷清(疑似失活)",
                                f"流动性 ${liq:,.0f} 但24h成交仅 ${vol:,.0f}（换手率 {turnover:.1%}），"
                                f"代币可能已迁移/被弃用，流动性成为僵尸池", "lifecycle"))
        else:
            signals.append(_sig("ok", "代币有生命", f"换手率 {turnover:.1%}，流动性活跃", "lifecycle"))
    # 无流动性数据 → 不添加任何 lifecycle 信号（避免"未找到流动性"+"流动性活跃"自相矛盾）
    return _finalize(address, signals, evidence)


async def liquidity(address):
    """流动性快照。"""
    ds = await _fetch_json(f"https://api.dexscreener.com/latest/dex/tokens/{address}")
    pairs = ds.get("pairs", [])
    if not pairs:
        return {"address": address, "liquidity_usd": 0, "pairs": [], "note": "DexScreener 未检索到交易对"}
    best = max(pairs, key=lambda p: _fdv_or_zero(p))
    return {"address": address, "best_pair_chain": best.get("chainId"), "best_pair_dex": best.get("dexId"),
            "price_usd": best.get("priceUsd"), "liquidity_usd": _fdv_or_zero(best),
            "volume_24h_usd": _num((best.get("volume") or {}).get("h24")),
            "pairs_total": len(pairs),
            "chains": sorted({p.get("chainId") for p in pairs if p.get("chainId")})}


async def new_pools(chain="solana", limit=10):
    """扫描某链新池/热门池。"""
    new = (await _fetch_json(f"https://api.geckoterminal.com/api/v2/networks/{chain}/new_pools")).get("data", [])
    trending = (await _fetch_json(f"https://api.geckoterminal.com/api/v2/networks/{chain}/trending_pools")).get("data", [])
    merged = {}
    for p in new:
        pid = p.get("id")
        if pid:
            a = p.get("attributes", {})
            merged[pid] = {"kind": "new", "pool_id": pid, "name": a.get("name"),
                           "price_usd": a.get("base_token_price_usd"), "liquidity_usd": a.get("reserve_in_usd")}
    for p in trending:
        pid = p.get("id")
        if pid and pid not in merged:
            a = p.get("attributes", {})
            merged[pid] = {"kind": "trending", "pool_id": pid, "name": a.get("name"),
                           "price_usd": a.get("base_token_price_usd"), "liquidity_usd": a.get("reserve_in_usd")}
    return list(merged.values())[:limit]
