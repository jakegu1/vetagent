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
    score = min(100, sum(_severity(s["severity"]) for s in signals))
    has_positive = any(s["severity"] in ("ok", "info") for s in signals)
    if not signals and not has_positive:
        level = "unknown"
    elif score >= 55:
        level = "high"
    elif score >= 25:
        level = "medium"
    elif has_positive:
        level = "low"
    else:
        level = "unknown"
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
    confidence = "low" if total == 0 else ("high" if definite and total >= 3 and info_ok >= 1 else ("medium" if total >= 2 else "low"))
    evidence["confidence"] = confidence
    rec = ("高风险：不建议在没有深入审核的情况下大额买入。先核实合约/持有/审计。" if level == "high" else (
        "中等风险：可小额试探，但务必控制仓位、设置止损。关注流动性退出与新池老化。" if level == "medium" else (
        "低风险：流动性充足且无 honeypot/高税信号，可正常评估。" if level == "low" else "信息不足以判定，建议二次核实合约与流动性。")))
    return {"address": address, "risk_level": level, "risk_score": score,
            "signals": signals, "recommendation": rec, "confidence": confidence, "evidence": evidence}


# --- 三个工具 ---


async def assess(address, chain_hint=None):
    """核心：代币风险画像。"""
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
            # 转成统一结构
            best_gt = max(gt_pools, key=lambda p: float((p.get("attributes", {}).get("reserve_in_usd") or 0) or 0) if (p.get("attributes", {}).get("reserve_in_usd") or 0) else 0)
            ga = best_gt.get("attributes", {})
            pairs = [{
                "dexId": "geckoterminal",
                "chainId": "eth",
                "liquidity": {"usd": float(ga.get("reserve_in_usd") or 0)},
                "priceUsd": ga.get("base_token_price_usd"),
                "pairCreatedAt": ga.get("pool_created_at"),
                "volume": {"h24": float(ga.get("volume_usd", {}).get("h24") or 0)},
            }]
    if pairs:
        best = max(pairs, key=lambda p: _fdv_or_zero(p))
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
    # 关键洞察：合约干净≠代币有生命。MATIC 案例——老牌币、61万持币，但主池仅$23.6万、
    # 24h成交$2万，是被弃用/迁移后的"僵尸流动性"。纯链上数据能推演出这个"失活"信号。
    bp = evidence.get("best_pair") or {}
    liq = _num(bp.get("liquidity_usd"))
    vol = _num((evidence.get("volume_h24")))
    # 换手率 = 24h成交 / 流动性（衡量流动性活不活跃）
    turnover = (vol / liq) if liq and liq > 0 else 0
    evidence["turnover_24h"] = round(turnover, 4)
    age = evidence.get("pair_age_days")
    if liq and liq >= 50000 and turnover < 0.10:
        # 有相当流动性但换手极低 → 流动性充裕却冷清 → 可能被弃用/失活
        signals.append(_sig("warn", "流动性冷清(疑似失活)",
                            f"流动性 ${liq:,.0f} 但24h成交仅 ${vol:,.0f}（换手率 {turnover:.1%}），"
                            f"代币可能已迁移/被弃用，流动性成为僵尸池", "lifecycle"))
    elif liq and liq < 50000 and turnover < 0.05 and age and age > 180:
        # 老池子 + 低流动性 + 极低换手 → 也在失活
        signals.append(_sig("info", "流动性偏冷", 
                            f"24h换手率 {turnover:.1%}，老池({age}天)流动性偏弱，注意活跃度", "lifecycle"))
    else:
        signals.append(_sig("ok", "代币有生命", f"换手率 {turnover:.1%}，流动性活跃", "lifecycle"))
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
