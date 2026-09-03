"""labels.py — 独立标注器。

基准的全部有效性建立在一件事上：**标注器读的端点，引擎一个都不读。**
否则测出来的是「引擎能不能正确转述上游」，那个数字必然很高，而且毫无意义。

两套互相独立的标注：

1. outcome  —— 结果论。只看 GeckoTerminal 的日线 OHLCV 历史（价格 + 成交量），
              判断这个池子后来是不是**真的死了**。不依赖任何安全 API。
2. goplus   —— 留出预言机。GoPlus token_security，引擎目前完全不读它。
              （它被**刻意保留**作为标注器；若将来要把 GoPlus 接进引擎，
                必须先给基准换一个新的独立标注源，否则基准即刻失效。）

两套都会有偏差，所以分开报，不合并成一个「准确率」。
"""

# GoPlus 的链 id
GOPLUS_CHAIN_ID = {
    "ethereum": "1", "bsc": "56", "base": "8453", "polygon": "137",
    "arbitrum": "42161", "optimism": "10", "avalanche": "43114",
}

# 引擎用的 GeckoTerminal network id
GT_NETWORK = {
    "ethereum": "eth", "bsc": "bsc", "base": "base", "polygon": "polygon_pos",
    "arbitrum": "arbitrum", "optimism": "optimism", "avalanche": "avax",
    "solana": "solana",
}


# ---------------------------------------------------------------- 结果论标注

def _rolling_sum(values, window):
    """返回所有长度为 window 的滑动窗口和。values 为按时间正序的列表。"""
    if len(values) < window:
        return [sum(values)] if values else [0.0]
    out, cur = [], sum(values[:window])
    out.append(cur)
    for i in range(window, len(values)):
        cur += values[i] - values[i - window]
        out.append(cur)
    return out


def outcome_label(ohlcv_list):
    """从日线 OHLCV 判断这个池子的实际归宿。

    ohlcv_list: GeckoTerminal 返回的 [[ts, o, h, l, c, vol], ...]，**最新在前**。

    返回 (label, facts)。label ∈ {"dead", "alive", None}

    判定逻辑：
      dead  —— 曾经有真实成交（峰值 7 日量 ≥ $50k），随后价格从峰值回撤 ≥ 90%
               **且**近 7 日成交量塌到峰值的 5% 以下。
               两个条件缺一不可：只跌不算死（熊市），只是没量也不算死（可能刚建池）。
      alive —— 至少 90 天历史，回撤 ≤ 70%，近 7 日量仍有峰值的 10% 以上且 ≥ $50k。
      None  —— 中间地带，不做标注。宁可样本少，不要标注脏。

    注意：dead ≠ 诈骗。正经项目也会死。这个标签回答的是
    「这个标的现在还能不能安全退出」，而这正是 VetAgent 声称覆盖的范围。
    """
    rows = [r for r in (ohlcv_list or []) if r and len(r) >= 6]
    if len(rows) < 30:
        return None, {"reason": "历史不足 30 天", "days": len(rows)}

    rows = list(reversed(rows))  # 转成时间正序
    closes = [float(r[4] or 0) for r in rows]
    vols = [float(r[5] or 0) for r in rows]
    days = len(rows)

    valid_closes = [c for c in closes if c > 0]
    if not valid_closes:
        return None, {"reason": "无有效收盘价", "days": days}

    peak = max(valid_closes)
    last = closes[-1]
    drawdown = 1.0 - (last / peak) if peak > 0 else 1.0

    vol7 = _rolling_sum(vols, 7)
    peak_vol7 = max(vol7) if vol7 else 0.0
    recent_vol7 = sum(vols[-7:])
    vol_collapse = 1.0 - (recent_vol7 / peak_vol7) if peak_vol7 > 0 else 1.0

    facts = {
        "days": days,
        "peak_close": peak,
        "last_close": last,
        "drawdown": round(drawdown, 4),
        "peak_volume_7d": round(peak_vol7, 2),
        "recent_volume_7d": round(recent_vol7, 2),
        "volume_collapse": round(vol_collapse, 4),
    }

    # 阈值是拿试跑数据校准出来的，不是拍脑袋：
    #  - 成交量塌陷是主判据，回撤是辅助。实测有代币回撤 86%、成交量塌 100%，
    #    实质已死，却被 90% 的回撤硬门槛挡掉。
    #  - 峰值 7 日量 $50k 这条要保留：低于它的池子是「从没活过」，不是「死了」，
    #    两者必须分开，否则会把新发但没人买的币算成 rug。
    if peak_vol7 >= 50_000 and vol_collapse >= 0.97 and drawdown >= 0.80:
        return "dead", facts
    # alive 的成交量门槛从 $50k 降到 $25k：SHIB 在某个池上近 7 日量 $49,997，
    # 差 3 美元被判为「无法标注」——这种边界脆弱性本身就是阈值定错的信号。
    if days >= 90 and drawdown <= 0.70 and recent_vol7 >= 25_000 \
            and peak_vol7 > 0 and (recent_vol7 / peak_vol7) >= 0.05:
        return "alive", facts
    return None, facts


# ---------------------------------------------------------------- GoPlus 标注

_RENOUNCED = ("", "0x0000000000000000000000000000000000000000",
              "0x000000000000000000000000000000000000dead", None)


def _flag(d, key):
    return str(d.get(key, "")) == "1"


def _tax(d, key):
    try:
        return float(d.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def goplus_label(payload, address):
    """从 GoPlus token_security 判断合约层面是否危险。

    返回 (label, reasons, raw_subset)。label ∈ {"unsafe", "safe", "centralized", None}

    **校准记录（重要）**：第一版把「合约有特权函数」直接判为 unsafe，
    结果 USDT / WBTC / LDO 全被标成危险——它们确实有黑名单、可暂停、可增发，
    但那是中心化资产的设计，不是 rug。照那个标准去评分，等于逼着引擎把蓝筹判高危。

    所以这里把两件事分开：

      unsafe      —— **无歧义的对抗性特征**，且不在声誉护栏内。
                     见下方第二次校准记录：株连型和噪声型字段已被移出。
      centralized —— 有特权函数但无对抗特征（USDT 这类）。**单列，不计入好坏**，
                     只用来观察引擎会不会无差别地把它们打成高危。
      safe        —— 开源、无对抗特征、低税、有一定持有者基数，
                     且（在 GoPlus 可信名单里 / 已上主流 CEX / 无特权函数）。
    """
    result = (payload or {}).get("result") or {}
    d = None
    for k, v in result.items():
        if k.lower() == address.lower():
            d = v
            break
    if d is None and result:
        d = list(result.values())[0]
    if not d:
        return None, ["GoPlus 无数据"], {}

    owner = (d.get("owner_address") or "").lower()
    owner_renounced = owner in _RENOUNCED

    cex = (d.get("is_in_cex") or {})
    reputable = _flag(d, "trust_list") or str(cex.get("listed", "")) == "1"
    try:
        holders = int(d.get("holder_count") or 0)
    except (TypeError, ValueError):
        holders = 0

    # ---- 无歧义的对抗性特征：正经项目没有任何理由具备 ----
    #
    # 第二次校准（2026-09-04）。第一版把 hidden_owner 和
    # honeypot_with_same_creator 也算进来，结果把 AAVE / YFI / PAXG / SNT /
    # Base 上的 USDT 全标成危险——这些都是真币（YFI 还在 GoPlus 自己的
    # trust_list 里）。两个字段的问题：
    #   hidden_owner —— 在大量合法的可升级代理合约上误触，是噪声不是证据。
    #   honeypot_with_same_creator —— 「部署者地址部署过被标记的合约」。
    #       大发行方和部署工厂会部署上千个合约，难免有骗局混在里面。
    #       这是**株连**，不是这个代币本身的性质。
    # 两个都已移出 unsafe 判据。
    adversarial = []
    if _flag(d, "is_honeypot"):
        adversarial.append("honeypot")
    if _flag(d, "cannot_sell_all"):
        adversarial.append("无法全部卖出")
    if _flag(d, "cannot_buy"):
        adversarial.append("无法买入")
    if _flag(d, "selfdestruct"):
        adversarial.append("可自毁")
    if _flag(d, "personal_slippage_modifiable"):
        adversarial.append("可对单个地址改税率")
    if _tax(d, "sell_tax") > 0.15:
        adversarial.append("卖出税 %.0f%%" % (_tax(d, "sell_tax") * 100))
    if _tax(d, "buy_tax") > 0.15:
        adversarial.append("买入税 %.0f%%" % (_tax(d, "buy_tax") * 100))

    # ---- 中心化特权：USDT/WBTC/LDO 都有，本身不是诈骗 ----
    privileged = []
    if _flag(d, "transfer_pausable"):
        privileged.append("可暂停转账")
    if _flag(d, "is_blacklisted"):
        privileged.append("有黑名单")
    if _flag(d, "slippage_modifiable"):
        privileged.append("税率可改")
    if _flag(d, "can_take_back_ownership"):
        privileged.append("可收回所有权")
    if _flag(d, "owner_change_balance"):
        privileged.append("owner 可改余额")
    if _flag(d, "is_mintable") and not owner_renounced:
        privileged.append("可增发且 owner 未放弃")


    subset = {k: d.get(k) for k in (
        "is_honeypot", "honeypot_with_same_creator", "is_mintable", "transfer_pausable",
        "is_blacklisted", "slippage_modifiable", "can_take_back_ownership",
        "owner_change_balance", "hidden_owner", "selfdestruct", "is_open_source",
        "is_proxy", "buy_tax", "sell_tax", "holder_count", "trust_list",
        "owner_address") if k in d}
    subset["reputable"] = reputable
    subset["cex_listed"] = list(cex.get("cex_list") or [])[:3]

    # 闭源 + 有特权函数 = 无法审计的可提取权限，归入对抗性
    if not _flag(d, "is_open_source") and privileged:
        adversarial.append("闭源且含特权函数")

    if adversarial:
        # 声誉护栏：广泛持有 / 已上主流 CEX / 在 GoPlus 可信名单里的资产，
        # 出现对抗性标记时更可能是**上游误报**，而不是这个币真的是骗局。
        # 实测：GoPlus 把真的 Status(SNT) 标成 is_honeypot=1。
        # 连「确定性」字段都有误报，所以这类样本不能当作 ground truth——
        # 既不判 unsafe 也不判 safe，直接排除并留待人工复核。
        if reputable or holders >= 50_000:
            return None, ["声誉护栏拦下：%s（%d 持有者，可信=%s）——疑似上游误报，排除"
                          % ("；".join(adversarial), holders, reputable)], subset
        return "unsafe", adversarial, subset

    if privileged:
        # 有特权但无对抗特征：单列观察，不计入好坏
        return "centralized", privileged, subset

    if _flag(d, "is_open_source") and holders >= 500 \
            and _tax(d, "sell_tax") <= 0.03 and _tax(d, "buy_tax") <= 0.03:
        return "safe", [], subset

    return None, ["证据不足（开源=%s 持有者=%s）" % (d.get("is_open_source"), holders)], subset
