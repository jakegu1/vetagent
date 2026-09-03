"""vetagent Worker — Cloudflare Python Workers 入口。

正确入口：定义 WorkerEntrypoint 子类，实现 async def fetch(self, request)。
用 SDK 的 `fetch` 顶层函数抓上游（不是自己定义 fetch，避免歧义）。
"""

import json
import re
from datetime import datetime, timezone

from workers import WorkerEntrypoint, Response, fetch as cf_fetch  # SDK 提供的 fetch 函数
from urllib.parse import urlparse

# --- 纯 Python 风险引擎 (可移植，无重依赖) ---


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


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
    # confidence
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


async def assess(address, chain_hint=None):
    """核心评估：聚合多源，输出风险画像。用 SDK fetch 抓上游。"""
    signals = []
    evidence = {}
    # DexScreener
    try:
        resp = await cf_fetch(f"https://api.dexscreener.com/latest/dex/tokens/{address}",
                              headers={"Accept": "application/json"})
        ds = json.loads(await resp.text()) if resp.status == 200 else {}
    except Exception:
        ds = {}
    pairs = ds.get("pairs", [])
    if pairs:
        best = max(pairs, key=lambda p: _fdv_or_zero(p))
        liq = _fdv_or_zero(best)
        evidence["best_pair"] = {"dex": best.get("dexId"), "chain": best.get("chainId"),
                                 "liquidity_usd": liq, "pair_created_at": best.get("pairCreatedAt"),
                                 "price_usd": best.get("priceUsd")}
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
    # Honeypot / RugCheck
    if _looks_evm(address):
        try:
            resp = await cf_fetch(f"https://api.honeypot.is/v2/IsHoneypot?address={address}",
                                  headers={"Accept": "application/json"})
            hp = json.loads(await resp.text()) if resp.status == 200 else {}
        except Exception:
            hp = {}
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
        try:
            resp = await cf_fetch(f"https://api.rugcheck.xyz/v1/tokens/{address}/report",
                                  headers={"Accept": "application/json"})
            rc = json.loads(await resp.text()) if resp.status == 200 else {}
        except Exception:
            rc = {}
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
    # freshness
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
    return _finalize(address, signals, evidence)


class Default(WorkerEntrypoint):
    """Worker 入口。注意：Cloudflare 要求入口类名必须是 Default。"""

    async def fetch(self, request):
        parsed = urlparse(request.url)
        path = parsed.path
        if path in ("/", ""):
            return Response("VetAgent - token risk intelligence for AI agents. Use /assess/{address} or MCP at /mcp",
                            headers={"content-type": "text/plain"}, status=200)
        if path == "/health":
            return Response(json.dumps({"status": "ok", "service": "vetagent", "mcp_tools": 3}),
                            headers={"content-type": "application/json"}, status=200)
        if path.startswith("/assess/"):
            address = path.split("/assess/")[1].split("?")[0]
            r = await assess(address)
            return Response(json.dumps(r, ensure_ascii=False),
                            headers={"content-type": "application/json"}, status=200)
        return Response(json.dumps({"detail": "Not Found"}),
                        headers={"content-type": "application/json"}, status=404)
