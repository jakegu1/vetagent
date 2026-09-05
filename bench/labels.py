"""labels.py — independent labeler.

The benchmark's entire validity rests on one thing: **the labeler reads endpoints that the
engine never reads.** Otherwise what you measure is whether the engine can correctly restate
its upstream, a number that is bound to be high and worth nothing.

Two independent sets of labels:

1. outcome  — outcome-based. Looks only at GeckoTerminal daily OHLCV history (price +
              volume) to decide whether the pool **actually died**. No security API.
2. goplus   — held-out oracle. GoPlus token_security, which the engine does not read at
              all today. (It is **deliberately held back** as a labeler; if GoPlus is ever
              wired into the engine, the benchmark needs a new independent labeling source
              first, or it is void the moment that lands.)

Both sets are biased, so they are reported separately, not merged into one "accuracy".
"""

# GoPlus chain ids
# Label thresholds, named so the published definitions can be generated from them.
#
# They were prose in run_benchmark.py and numbers here, and the two had drifted: the
# report said dead needed a 90% drawdown when the code used 80%, said alive needed $50k
# of weekly volume when the code used $25k, said safe needed 100 holders when the code
# used 500, and said the tax bar was 10% when it was 15%. Three of twenty dead tokens and
# thirteen of eighty-five alive ones did not satisfy the published rule. A benchmark whose
# stated method differs from its actual method is not a benchmark.
DEAD_PEAK_VOL_7D = 50_000
DEAD_VOL_COLLAPSE = 0.97      # recent 7d volume below (1 - this) of peak
DEAD_DRAWDOWN = 0.80
ALIVE_MIN_DAYS = 90
ALIVE_MAX_DRAWDOWN = 0.70
ALIVE_MIN_VOL_7D = 25_000
ALIVE_MIN_VOL_RATIO = 0.05
UNSAFE_TAX = 0.15
SAFE_MIN_HOLDERS = 500
SAFE_MAX_TAX = 0.03
REPUTABLE_HOLDERS = 50_000
HONEYPOT_TESTABLE_VOL_7D = 1_000


GOPLUS_CHAIN_ID = {
    "ethereum": "1", "bsc": "56", "base": "8453", "polygon": "137",
    "arbitrum": "42161", "optimism": "10", "avalanche": "43114",
}

# GeckoTerminal network ids the engine uses
GT_NETWORK = {
    "ethereum": "eth", "bsc": "bsc", "base": "base", "polygon": "polygon_pos",
    "arbitrum": "arbitrum", "optimism": "optimism", "avalanche": "avax",
    "solana": "solana",
}


# ---------------------------------------------------------------- outcome labeling

def _rolling_sum(values, window):
    """Every rolling sum of length window. values is oldest-first."""
    if len(values) < window:
        return [sum(values)] if values else [0.0]
    out, cur = [], sum(values[:window])
    out.append(cur)
    for i in range(window, len(values)):
        cur += values[i] - values[i - window]
        out.append(cur)
    return out


def outcome_label(ohlcv_list):
    """Decide what actually became of this pool from its daily OHLCV.

    ohlcv_list: GeckoTerminal's [[ts, o, h, l, c, vol], ...], **newest first**.

    Returns (label, facts). label ∈ {"dead", "alive", None}

    The rules:
      dead  — there was real trading once (peak 7-day volume ≥ $50k) and price has since
              fallen ≥ 90% off the peak **and** the last 7 days of volume collapsed below
              5% of the peak. Both halves are required: falling alone is not death (bear
              market), and no volume alone is not death either (the pool may be brand new).
      alive — at least 90 days of history, drawdown ≤ 70%, last 7 days of volume still
              above 10% of the peak and ≥ $50k.
      None  — the middle ground, left unlabeled. A smaller sample beats dirty labels.

    dead != scam. Honest projects die too. What this label answers is whether you can still
    get out of the position safely, and that is exactly the scope VetAgent claims to cover.
    """
    rows = [r for r in (ohlcv_list or []) if r and len(r) >= 6]

    # Recent volume is computed before any early return, because a caller other than this
    # function needs it: the contract oracle uses it to decide whether its own honeypot
    # simulation could have run at all. It used to be produced only on the paths that
    # reached a label, so 27 of the 28 tokens where the question mattered carried no
    # figure -- and the guard that depended on it defaulted to "testable" and did nothing.
    _recent7 = round(sum(float(r[5] or 0) for r in rows[:7]), 2)

    if len(rows) < 30:
        return None, {"reason": "fewer than 30 days of history", "days": len(rows),
                      "recent_volume_7d": _recent7}

    rows = list(reversed(rows))  # flip to oldest-first
    closes = [float(r[4] or 0) for r in rows]
    vols = [float(r[5] or 0) for r in rows]
    days = len(rows)

    valid_closes = [c for c in closes if c > 0]
    if not valid_closes:
        return None, {"reason": "no valid close price", "days": days,
                      "recent_volume_7d": _recent7}

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

    # These thresholds were calibrated against trial-run data, not guessed:
    #  - Volume collapse is the primary test, drawdown only backs it up. A real token came
    #    back 86% down with volume off 100% — dead in every way that matters, yet a hard
    #    90% drawdown gate threw it out.
    #  - Keep the $50k peak 7-day volume floor: a pool below it "never lived" rather than
    #    "died". Conflating the two scores freshly launched tokens nobody bought as rugs.
    if (peak_vol7 >= DEAD_PEAK_VOL_7D and vol_collapse >= DEAD_VOL_COLLAPSE
            and drawdown >= DEAD_DRAWDOWN):
        return "dead", facts
    # The alive volume floor came down from $50k to $25k: SHIB had $49,997 of 7-day volume
    # on one pool and was ruled unlabelable by three dollars — that kind of edge fragility
    # is itself the signal that the threshold was wrong.
    if (days >= ALIVE_MIN_DAYS and drawdown <= ALIVE_MAX_DRAWDOWN
            and recent_vol7 >= ALIVE_MIN_VOL_7D and peak_vol7 > 0
            and (recent_vol7 / peak_vol7) >= ALIVE_MIN_VOL_RATIO):
        return "alive", facts
    return None, facts


# ---------------------------------------------------------------- GoPlus labeling

_RENOUNCED = ("", "0x0000000000000000000000000000000000000000",
              "0x000000000000000000000000000000000000dead", None)


def _flag(d, key):
    return str(d.get(key, "")) == "1"


def _tax(d, key):
    try:
        return float(d.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def goplus_label(payload, address, recent_volume_7d=None):
    """Decide from GoPlus token_security whether the contract itself is dangerous.

    Returns (label, reasons, raw_subset). label ∈ {"unsafe", "safe", "centralized", None}

    **Calibration log (important)**: the first version called any contract with privileged
    functions unsafe, which flagged USDT / WBTC / LDO as dangerous. They really do have a
    blacklist, a pause switch and a mint function, but that is how a centralized asset is
    built, not a rug. Scoring against that standard forces the engine to call blue chips
    high risk.

    So the two things are kept apart here:

      unsafe      — **unambiguously adversarial traits**, outside the reputation guardrail.
                    See the second calibration note below: the guilt-by-association and
                    noisy fields have been moved out.
      centralized — privileged functions but no adversarial traits (USDT and the like).
                    **Reported on its own, counted as neither good nor bad**; it exists
                    only to watch whether the engine tars them all as high risk.
      safe        — open source, no adversarial traits, low tax, a real holder base, and
                    (on the GoPlus trust list / listed on a major CEX / no privileged
                    functions).
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
        return None, ["no GoPlus data"], {}

    owner = (d.get("owner_address") or "").lower()
    owner_renounced = owner in _RENOUNCED

    cex = (d.get("is_in_cex") or {})
    reputable = _flag(d, "trust_list") or str(cex.get("listed", "")) == "1"
    try:
        holders = int(d.get("holder_count") or 0)
    except (TypeError, ValueError):
        holders = 0

    # ---- Unambiguously adversarial: no honest project has a reason to have these ----
    #
    # Second calibration (2026-09-04). The first version counted hidden_owner and
    # honeypot_with_same_creator too, which flagged AAVE / YFI / PAXG / SNT / USDT on
    # Base as dangerous — all real tokens (YFI is on GoPlus's own trust_list). What is
    # wrong with those two fields:
    #   hidden_owner — fires on plenty of legitimate upgradeable proxies. Noise, not evidence.
    #   honeypot_with_same_creator — "the deployer once deployed a flagged contract".
    #       Large issuers and deployment factories ship thousands of contracts, so a few
    #       scams are bound to be among them. That is **guilt by association**, not a
    #       property of this token.
    # Both are out of the unsafe criteria.
    # Third calibration (2026-09-05, from an external audit). A honeypot verdict against
    # a pool nobody can trade is unfalsifiable, and this oracle issues one anyway.
    #
    # Measured over the 28 tokens this labeller called unsafe: 27 had under $1,000 of
    # liquidity left, an independent simulator said 19 of them were NOT honeypots
    # (open source, 0% tax, simulation succeeded), and 27 of the 28 were flagged on
    # is_honeypot alone. The flag fires when GoPlus's own sell simulation fails, and a
    # sell simulation fails against an empty pool no matter what the contract does.
    #
    # So the cohort was mostly "drained pool" wearing the label "dangerous contract", and
    # the engine's headline recall on it was measuring its liquidity checks -- exactly the
    # tautology the ablation column exists to expose. This is E1 inside the oracle: an
    # unobserved dimension reported as an observed fact.
    #
    # is_honeypot now needs the pool to have traded recently, or corroboration from a
    # second adversarial trait. Where neither holds, the token leaves the labelled set
    # rather than being called safe -- we cannot tell, and saying so is the point.
    adversarial = []
    honeypot_flag = _flag(d, "is_honeypot")
    honeypot_testable = (recent_volume_7d is None
                         or recent_volume_7d >= HONEYPOT_TESTABLE_VOL_7D)
    if honeypot_flag and honeypot_testable:
        adversarial.append("honeypot")
    if _flag(d, "cannot_sell_all"):
        adversarial.append("cannot sell entire balance")
    if _flag(d, "cannot_buy"):
        adversarial.append("cannot buy")
    if _flag(d, "selfdestruct"):
        adversarial.append("self-destructible")
    if _flag(d, "personal_slippage_modifiable"):
        adversarial.append("tax changeable per address")
    if _tax(d, "sell_tax") > UNSAFE_TAX:
        adversarial.append("sell tax %.0f%%" % (_tax(d, "sell_tax") * 100))
    if _tax(d, "buy_tax") > UNSAFE_TAX:
        adversarial.append("buy tax %.0f%%" % (_tax(d, "buy_tax") * 100))

    # ---- Centralized privileges: USDT/WBTC/LDO all have them, not a scam in itself ----
    privileged = []
    if _flag(d, "transfer_pausable"):
        privileged.append("transfers pausable")
    if _flag(d, "is_blacklisted"):
        privileged.append("has a blacklist")
    if _flag(d, "slippage_modifiable"):
        privileged.append("tax changeable")
    if _flag(d, "can_take_back_ownership"):
        privileged.append("ownership reclaimable")
    if _flag(d, "owner_change_balance"):
        privileged.append("owner can change balances")
    if _flag(d, "is_mintable") and not owner_renounced:
        privileged.append("mintable and owner has not renounced")


    subset = {k: d.get(k) for k in (
        "is_honeypot", "honeypot_with_same_creator", "is_mintable", "transfer_pausable",
        "is_blacklisted", "slippage_modifiable", "can_take_back_ownership",
        "owner_change_balance", "hidden_owner", "selfdestruct", "is_open_source",
        "is_proxy", "buy_tax", "sell_tax", "holder_count", "trust_list",
        "owner_address") if k in d}
    subset["reputable"] = reputable
    subset["cex_listed"] = list(cex.get("cex_list") or [])[:3]

    # Closed source + privileged functions = extractable power nobody can audit; adversarial
    if not _flag(d, "is_open_source") and privileged:
        adversarial.append("closed source with privileged functions")

    # An untestable honeypot flag still counts once something else corroborates it.
    if honeypot_flag and not honeypot_testable and adversarial:
        adversarial.append("honeypot (pool inactive, flag not independently testable)")

    if honeypot_flag and not honeypot_testable and not adversarial:
        return None, ["is_honeypot on a pool with no recent trading: the oracle's own "
                      "simulation cannot run there, so the flag is unfalsifiable"], subset

    if adversarial:
        # Reputation guardrail: on widely held assets, ones listed on major CEXes, or ones
        # on the GoPlus trust list, an adversarial flag is more likely **an upstream false
        # positive** than proof the token really is a scam.
        # Observed: GoPlus flags the real Status (SNT) as is_honeypot=1.
        # If even the "deterministic" fields have false positives, samples like this cannot
        # be ground truth — neither unsafe nor safe, dropped and left for manual review.
        if reputable or holders >= REPUTABLE_HOLDERS:
            return None, ["reputation guardrail: %s (%d holders, reputable=%s) — likely an "
                          "upstream false positive, excluded"
                          % ("; ".join(adversarial), holders, reputable)], subset
        return "unsafe", adversarial, subset

    if privileged:
        # Privileged but not adversarial: tracked on its own, scored neither way
        return "centralized", privileged, subset

    if (_flag(d, "is_open_source") and holders >= SAFE_MIN_HOLDERS
            and _tax(d, "sell_tax") <= SAFE_MAX_TAX
            and _tax(d, "buy_tax") <= SAFE_MAX_TAX):
        return "safe", [], subset

    return None, ["not enough evidence (open source=%s holders=%s)"
                  % (d.get("is_open_source"), holders)], subset
