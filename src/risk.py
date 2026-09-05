"""risk.py — VetAgent's core risk engine (pure Python, runs under Pyodide/Workers).

Shared by entry.py (HTTP routing) and mcp_server.py (MCP endpoint); one source of truth.

The rule the whole design bends to — fail closed:
  no data -> return unknown, or an explicit "could not verify" signal.
  Never an optimistic middle value, never a position suggestion with nothing to go on.
"""

import asyncio
import json
import re
from datetime import datetime, timezone

try:  # Workers runtime
    from workers import fetch as cf_fetch
except ImportError:  # local tests / non-Worker runtime (tests monkeypatch _fetch_json)
    cf_fetch = None


# ---------------------------------------------------------------- helpers

_EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# Chain names from DexScreener/chain_hint -> GeckoTerminal network ids
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
# Reverse: GeckoTerminal network id -> our canonical chain name
_GT_TO_CHAIN = {"eth": "ethereum", "polygon_pos": "polygon", "avax": "avalanche"}

# How canonical a chain is; lower is more trustworthy.
# This is a safety property, not a preference: Ethereum forks like pulsechain
# **inherit the same contract address**, so USDC's address has pools there too,
# quoted at a completely wrong $0.00097. Of the 30 pools DexScreener returns for
# USDC, 29 are on pulsechain — voting by count (a median price) is guaranteed to
# be dragged to the fork, so rank by how canonical the chain is instead.
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
    """Truncate to N significant digits. Upstream sends 66 decimals, pure token waste."""
    v = _num(x)
    if v == 0:
        return 0.0
    try:
        return float("%.*g" % (digits, v))
    except (TypeError, ValueError):
        return v


# How long a cached upstream response counts as fresh, and how long it may still be
# served after a fetch fails. Measured problem: roughly a third of production calls came
# back "unavailable" while all three upstreams answered HTTP 200 in under a second from
# outside. The likely cause is per-IP rate limiting at the upstream, and Cloudflare
# Workers share egress addresses across every customer on the platform — so we get
# throttled by traffic that is not ours, and no amount of retrying fixes it.
#
# Caching is the actual fix: it collapses repeated lookups of the same token into one
# upstream call. Serving a stale copy when the fetch fails does not violate fail-closed:
# fail-closed forbids *guessing*, and a four-minute-old price is a measurement, not a
# guess. What it does require is saying so, which is why staleness lands in evidence.
_FRESH_SECONDS = 60
_STALE_OK_SECONDS = 900

_STALE_HITS = []  # (url, age_seconds) recorded during one request, drained by assess()


async def _cache_get(url):
    """Return (data, age_seconds) from the edge cache, or (None, None)."""
    try:
        from js import Date, Request, caches
        cache = caches.default
        hit = await cache.match(Request.new(url))
        if not hit:
            return None, None
        body = await hit.text()
        blob = json.loads(body)
        age = (Date.now() / 1000.0) - float(blob.get("_at") or 0)
        return blob.get("_data"), age
    except Exception:  # noqa: BLE001
        return None, None


async def _cache_put(url, data):
    try:
        from js import Date, Request, Response as JsResponse, caches
        from pyodide.ffi import to_js
        from js import Object
        payload = json.dumps({"_at": Date.now() / 1000.0, "_data": data})
        headers = to_js({"content-type": "application/json",
                         "cache-control": "max-age=%d" % _STALE_OK_SECONDS},
                        dict_converter=Object.fromEntries)
        init = to_js({"headers": headers}, dict_converter=Object.fromEntries)
        await caches.default.put(Request.new(url), JsResponse.new(payload, init))
    except Exception:  # noqa: BLE001
        pass


# Returned instead of None when upstream answered 404: it is not that we could not
# reach the service, it is that the service has no record of this token. Third time
# today the same distinction has mattered, which is how you know it is the right one.
NO_DATA = object()


async def _fetch_json(url, retries=2, timeout=8, mark_missing=False):
    """Fetch and parse JSON.

    A dict means success. None means the **fetch failed** (network error, non-200,
    empty body, unparseable). Callers must tell None (no data) apart from {} or an
    empty list (data arrived, there genuinely is nothing) — fail-closed rests on it.

    Cache behaviour: a copy newer than _FRESH_SECONDS is returned without touching the
    upstream at all. If every attempt fails, a copy up to _STALE_OK_SECONDS old is
    served instead of None, and its age is recorded in _STALE_HITS so the caller can
    disclose it. Returning real data four minutes old beats refusing to answer.
    """
    cached, age = await _cache_get(url)
    if cached is not None and age is not None and age <= _FRESH_SECONDS:
        return cached

    for attempt in range(retries + 1):
        try:
            resp = await asyncio.wait_for(
                cf_fetch(url, headers={"Accept": "application/json"}), timeout=timeout)
            if mark_missing and resp.status == 404:
                return NO_DATA
            if resp.status == 200:
                body = await asyncio.wait_for(resp.text(), timeout=timeout)
                if body:
                    data = json.loads(body)
                    await _cache_put(url, data)
                    return data
        except Exception:  # timeout, network, parse error: all count as a failed fetch
            pass
        if attempt < retries:
            await asyncio.sleep(0.3 * (2 ** attempt))

    if cached is not None and age is not None and age <= _STALE_OK_SECONDS:
        _STALE_HITS.append((url, int(age)))
        return cached
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
    """Validate first. An invalid address raises ValueError, never a hopeful verdict."""
    address = (address or "").strip().split("?")[0]
    if not address or (not _looks_evm(address) and not _looks_solana(address)):
        raise ValueError(
            "Invalid token address: %r (EVM needs 0x + 40 hex chars, Solana needs base58 32-44 chars)" % address)
    return address


def _sig(severity, name, message, category):
    return {"severity": severity, "name": name, "message": message, "category": category}


# ---------------------------------------------------------------- scoring model

# Base score for a single signal
_SEVERITY_BASE = {"ok": 0, "info": 5, "warn": 30, "critical": 60, "fatal": 100}

# Category weights, ranked by what hitting one actually costs you: can't sell = your
# principal goes to zero, liquidity gone = a steep haircut, one chain = barely a risk.
_CATEGORY_WEIGHT = {
    "honeypot": 1.0,        # you can buy it, you can't sell it
    "sellability": 1.0,     # can't verify it is sellable
    "sell_tax": 0.9,
    "upstream_risk": 0.8,   # honeypot.is / RugCheck aggregate verdict
    "rugcheck": 0.8,
    "liquidity": 0.8,
    "no_liquidity": 0.8,
    "contract": 0.6,        # closed source / proxy contract
    "freshness": 0.5,
    "lifecycle": 0.4,
    "impersonation": 0.9,   # right ticker, wrong contract
    "concentration": 0.7,   # holder concentration
    "cross_chain": 0.2,     # one chain is not itself a risk, so keep this near zero
}

# Dimensions whose absence is disqualifying: miss one and the answer must be unknown.
# Other signals must never add up to "low" in its place.
_CRITICAL_DIMENSIONS = ("liquidity", "sellability")


def _score(signals):
    """Worst signal dominates, corroboration adds a little. Not a naive sum.

    A naive sum means more signals scores higher, so adding a couple of dimensions
    pushes ordinary tokens into high. Instead: max(weighted signal), plus 10 for each
    additional independent warn-or-worse category, capped at 30.
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
    """Roll everything up. Fail closed: a missing critical dimension means unknown,
    never an optimistic default.
    """
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

    # Fail-closed override: with a critical dimension missing, nobody gets the
    # reassurance of a low/medium rating.
    missing = {g.get("dimension") for g in data_gaps}
    missing_critical = missing & set(_CRITICAL_DIMENSIONS)
    if missing_critical and level in ("low", "medium"):
        level = "unknown"

    # Losing *every* critical dimension is sometimes an answer rather than an unknown —
    # but only when the gaps are about the token, not about us.
    #
    # Two very different situations both leave every critical dimension empty:
    #   our upstreams failed        -> the token may be perfectly fine and we cannot see
    #   the token has no trace      -> no pool exists anywhere, nothing can be simulated
    # Rating the first one "high" would smear legitimate tokens for our own outage, so
    # the two are told apart by why the gap exists, not by how many there are.
    #
    # Measured on 9 confirmed honeypots: none were ever rated low, which is the property
    # that matters, but 7 of 9 came back "unknown" rather than "high", and 5 of those
    # only because no liquidity data existed. The tool was declining to answer, not
    # detecting anything. A token that no market data source can price and no simulator
    # can trade is not a question mark: every legitimate token clears at least one of
    # those two. Saying so is strictly more conservative than "unknown", and more useful
    # — the absence of any verifiable trace *is* the finding.
    ours = ("upstream request failed",)
    token_side = [g for g in data_gaps
                  if g.get("dimension") in _CRITICAL_DIMENSIONS
                  and not str(g.get("reason", "")).startswith(ours)]
    token_side_dims = {g.get("dimension") for g in token_side}
    # Pools that were costed and found empty is *stronger* evidence than a gap, not
    # weaker. Recording it as a signal instead of a gap removed the liquidity dimension
    # from this test and quietly downgraded the archetypal drained rug from high to
    # unknown -- the exact token this escalation was written for.
    if evidence.get("pools_all_empty"):
        token_side_dims.add("liquidity")
    if token_side_dims >= set(_CRITICAL_DIMENSIONS):
        level = "high"
        score = max(score, 70)
        signals.append(_sig(
            "critical", "Nothing about this token can be verified",
            "No market data source could price it and its sellability could not be "
            "simulated. Every legitimate token clears at least one of those.",
            "no_liquidity"))

    total = len(signals)
    has_liquidity = any(s["category"] in ("liquidity", "no_liquidity") for s in signals)
    has_sellability = any(s["category"] in ("honeypot", "sellability", "rugcheck")
                          for s in signals)
    # confidence measures **how complete the data is**, not how risky the token is
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


# ---------------------------------------------------------------- pool selection

def _pair_liquidity(pair):
    """Depth in USD, with an unreported depth counted as zero.

    Fine for ranking pools, where a pool of unknown depth should not win. NOT fine for
    concluding anything about the token -- use _reported_liquidity for that.
    """
    v = _reported_liquidity(pair)
    return 0.0 if v is None else v


def _reported_liquidity(pair):
    """Depth in USD, or None when no source actually stated one.

    The distinction this draws is the whole difference between an observation and a
    guess. DexScreener returns "liquidity": null for pairs it has not costed -- 303 of
    the 3,909 pairs in this project's own benchmark cache, and for six tokens *every*
    pair is like that. Collapsing that to 0.0 was invisible while the number was only
    used to rank pools, because an unranked pool and an empty pool both deserve to lose.

    It stopped being invisible when a caller asked "is every pool empty" and used the
    answer to tell a user the exit was closed. One of those six tokens had 174 buys and
    104 sells that same day.
    """
    liq = pair.get("liquidity") or {}
    for v in (liq.get("usd"), pair.get("reserveInUsd")):
        if v is not None and v != "":
            return _num(v)
    return None


def _pick_best(pairs, chain_hint=None, target=None):
    """Pick a pool defensively: target chain first -> must contain the target address
    -> sane price -> deepest liquidity.

    Picking on liquidity alone lands on a mispriced pool on a fork chain
    (USDC resolves to a pulsechain pool quoting $0.00097).
    """
    target_l = (target or "").lower()

    def _valid(p):
        # Liquidity is mandatory; price is sanity-checked only when it **is present**
        # (GeckoTerminal's base_token_price_usd is often null, and a valid pool must
        # not be discarded over that).
        #
        # The floor is zero, not a small number. It used to be 1e-12, which quietly
        # excluded a whole class of token rather than a class of error: supply and price
        # are reciprocal, so a coin minted in quadrillions trades at 1e-22 while holding
        # real liquidity. hPERPS sat at $293 across 5 buys and a sell, priced 5.5e-24,
        # and was discarded as unpriceable -- so the engine returned "unknown" for a
        # token it could see in full detail.
        #
        # The floor was not protecting anything either. It was added against the
        # pulsechain mispricing, where USDC resolved to $0.00097 -- nine orders of
        # magnitude above 1e-12, so the floor never touched that case. What actually
        # fixed it was ranking by how canonical the chain is, further down. A price
        # above zero is a price; only zero says nothing.
        if _pair_liquidity(p) <= 0:
            return False
        price = p.get("priceUsd")
        return True if price in (None, "") else _num(price) > 0

    def _is_target(p):
        bt = ((p.get("baseToken") or {}).get("address") or "").lower()
        qt = ((p.get("quoteToken") or {}).get("address") or "").lower()
        return (bt == target_l or qt == target_l) if target_l else True

    if not pairs:
        return None
    hint = (chain_hint or "").lower()

    # Which chain this token belongs to is decided BEFORE liquidity is considered, over
    # every pair that names it -- drained pools included.
    #
    # Deciding it afterwards was the bug. _valid drops any pool holding nothing, so once
    # a token's real pools were emptied, the only survivors were the pools on forked
    # chains that inherited its address, and those became the best tier by default. The
    # engine would then report a pulsechain pool's depth and price as fact for a token
    # whose actual exit was closed -- the same mispricing that put USDC at $0.00097, made
    # reachable again by the exact tokens the drained-pool check exists for.
    home = [p for p in pairs if _is_target(p)] or list(pairs)
    if hint:
        on_hint = [p for p in home if (p.get("chainId") or "").lower() == hint]
        # Only ignore the hint when the token genuinely does not appear on that chain.
        # Falling back because its pools happen to be empty is how a fork chain wins.
        scoped = on_hint or home
    else:
        best_rank = min(_CHAIN_RANK.get((p.get("chainId") or "").lower(),
                                        _UNKNOWN_CHAIN_RANK) for p in home)
        scoped = [p for p in home
                  if _CHAIN_RANK.get((p.get("chainId") or "").lower(),
                                     _UNKNOWN_CHAIN_RANK) == best_rank]

    pool = [p for p in scoped if _valid(p)]
    if not pool:
        return None      # the token's own chain has nothing usable; say so, do not roam
    return max(pool, key=_pair_liquidity)


def _pair_created_ms(value):
    """DexScreener sends an **integer in milliseconds**, GeckoTerminal an ISO string.

    The old code handled only ISO; calling .replace() on an int raised AttributeError,
    which an `except Exception: pass` swallowed — the pair-age signal never once fired
    on our primary data source.
    """
    if value in (None, "", 0):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v > 1e11 else v * 1000  # seconds -> milliseconds
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
    """GeckoTerminal's base_token_price_usd is often null, but the price is derivable:
    base_token_price_quote_token × quote_token_price_usd.
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
        # None, not 0.0, when GeckoTerminal did not state a reserve -- see
        # _reported_liquidity. A missing number must not arrive downstream as a measured
        # zero.
        "liquidity": {"usd": (None if a.get("reserve_in_usd") in (None, "")
                              else _num(a.get("reserve_in_usd")))},
        "priceUsd": _gt_base_price(a),
        "pairCreatedAt": a.get("pool_created_at"),
        "volume": {"h24": _num((a.get("volume_usd") or {}).get("h24"))},
        # The symbol comes along, because a consumer that needs it has no other source.
        # Without it _impersonation_signals found "" and returned, so the check was
        # silently skipped for every token that fell through to GeckoTerminal -- no
        # signal, no evidence, no gap, indistinguishable from having run and found
        # nothing. That is the isHoneypot bug's exact shape: read a key the producer
        # never writes, swallow the miss. And it skipped the thinly-indexed tokens,
        # which are the ones most likely to be impostors.
        "baseToken": {"address": address,
                      "symbol": (a.get("name") or "").split("/")[0].strip()},
        "quoteToken": {"address": ""},
    }


# ---------------------------------------------------------------- building signals

def _liquidity_signals(best, pairs, signals, evidence):
    liq = _pair_liquidity(best)
    vol = _num((best.get("volume") or {}).get("h24"))
    # Buy/sell counts come free in the same response and are the only direct evidence we
    # have about whether people can actually get out. _honeypot_signals reads them back.
    txns = ((best.get("txns") or {}).get("h24") or {})
    evidence["best_pair"] = {
        "dex": best.get("dexId"), "chain": best.get("chainId"),
        "liquidity_usd": _sig_round(liq), "price_usd": _sig_round(best.get("priceUsd")),
        "volume_24h_usd": _sig_round(vol), "pair_created_at": best.get("pairCreatedAt"),
        "buys_24h": txns.get("buys"), "sells_24h": txns.get("sells"),
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

    # Lifecycle: "is the contract safe" and "does anyone still trade this" differ
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


async def _impersonation_signals(address, pairs, signals, evidence,
                                 chain_hint=None):
    """Is this the token people mean when they say this ticker?

    The loss an agent is most likely to take is not an exotic exploit. It is buying the
    wrong contract with the right name: a fresh token deployed as "PEPE" alongside the
    one everybody means. Nothing in a contract scan catches that, because the impostor's
    contract is often perfectly ordinary -- it is honest code for a dishonest identity.

    The test is comparative, not absolute. A ticker being shared proves nothing; USDC is
    a legitimate token on a dozen chains. What matters is being dwarfed: if something
    else answering to this ticker holds orders of magnitude more liquidity, then this is
    not the one people mean, and an agent that resolved a name to this address resolved
    it wrong.

    Deliberately not flagged: the same address on another chain, which is the same token
    bridged, and any token that is itself the largest under its ticker.
    """
    symbol = ""
    for p in pairs:
        base = p.get("baseToken") or {}
        if (base.get("address") or "").lower() == address.lower():
            symbol = (base.get("symbol") or "").strip()
            break
    if not symbol or len(symbol) < 2:
        return

    # Our own side, measured the way the engine measures every other pool: through
    # _pick_best, which applies the chain-canonicality and price sanity checks. Taking a
    # raw max over pairs measured a different quantity from the one the verdict is based
    # on, and the two can disagree.
    ours = _pick_best(pairs, chain_hint=chain_hint, target=address)
    mine = _reported_liquidity(ours) if ours is not None else None
    if mine is None or mine <= 0:
        return  # we cannot size our own side, so we cannot say anything is dwarfing it
    home = (ours.get("chainId") or "").lower()

    found = await _fetch_json(
        "https://api.dexscreener.com/latest/dex/search?q=%s" % symbol.replace(" ", "%20"))
    if found is None:
        return  # no claim either way; absence of the check is not evidence of safety

    # Rivals are graded on the same chain only, and on the same evidence standard.
    #
    # Both restrictions were bought with false positives. The first version accepted any
    # pool the search returned, on any chain, at whatever liquidity it claimed, with none
    # of the checks _pick_best applies to our own side. Canonical ZORA on Base was then
    # called "almost certainly not the token you meant" because a Solana pool listed
    # under the same ticker reported $1,015,244,216 -- a number nobody verified, from a
    # venue nobody asked about, and one an attacker can manufacture at will by standing
    # up a pool under a target's ticker. Measured over the 207-token benchmark, the check
    # fired warn-or-critical on 81 tokens labelled safe or alive.
    #
    # Same-chain also fixes the honest half of that. A token deployed on several chains
    # has a different address on each, so its own other deployments looked like rivals --
    # the canonical version of a multichain asset was competing with itself.
    #
    # What is lost: an impostor on chain A shadowing a famous token on chain B. That is a
    # real pattern, but it cannot be told apart from bridged deployments and unpriced
    # foreign venues with this data, and a check that cannot tell them apart is one that
    # cries wolf on the canonical asset.
    by_addr = {}
    for p in (found.get("pairs") or []):
        base = p.get("baseToken") or {}
        addr = (base.get("address") or "").lower()
        if not addr or addr == address.lower():
            continue
        if (base.get("symbol") or "").strip().lower() != symbol.lower():
            continue
        if (p.get("chainId") or "").lower() != home:
            continue
        by_addr.setdefault(addr, []).append(p)

    rivals = {}
    for addr, their_pairs in by_addr.items():
        best = _pick_best(their_pairs, chain_hint=home, target=addr)
        liq = _reported_liquidity(best) if best is not None else None
        if liq is None or liq <= 0:
            continue
        # Deliberately NOT corroborated against volume, though that was tried.
        #
        # The idea was that a pool nobody trades cannot be evidence of where a name's
        # value sits, so a claimed reserve should have to be backed by turnover. It
        # rejected the wrong thing. The genuine AAPLon impostor is caught by comparing
        # against a $3,366,238 pool that trades $0.01 a day -- because the token it
        # shadows is a tokenised equity, and low turnover against deep liquidity is what
        # that asset class looks like, not what a fake looks like. The rule silently
        # deleted a confirmed true positive to prevent a false one that same-chain
        # filtering had already prevented.
        rivals[addr] = liq

    if not rivals:
        return

    top_addr, top_liq = max(rivals.items(), key=lambda kv: kv[1])
    evidence["same_symbol"] = {
        "symbol": symbol,
        "other_contracts": len(rivals),
        "chain": home,
        "largest_rival_liquidity_usd": _sig_round(top_liq),
        "this_token_liquidity_usd": _sig_round(mine),
    }

    ratio = top_liq / mine
    if ratio >= 1000:
        signals.append(_sig(
            "critical", "Almost certainly not the token you meant",
            "Another contract with the ticker %s holds $%s against this one's $%s. "
            "At that gap this is not the token the name refers to." %
            (symbol, format(top_liq, ",.0f"), format(mine, ",.0f")), "impersonation"))
    elif ratio >= 50:
        signals.append(_sig(
            "warn", "A much larger token shares this ticker",
            "%d other contracts use the ticker %s, and the largest holds $%s against "
            "this one's $%s. Confirm the address is the one you intended." %
            (len(rivals), symbol, format(top_liq, ",.0f"), format(mine, ",.0f")),
            "impersonation"))
    elif len(rivals) >= 3:
        signals.append(_sig(
            "info", "Ticker is shared with other contracts",
            "%d other contracts use the ticker %s. This one is not dwarfed by them, but "
            "the name alone does not identify a token." % (len(rivals), symbol),
            "impersonation"))


def _honeypot_signals(hp, signals, evidence, data_gaps):
    """Read honeypot.is.

    The old code read isHoneypot out of simulationResult — a key upstream does not
    have (the real one is honeypotResult.isHoneypot), so the honeypot dimension was
    permanently "ok". It also discarded summary.risk, flags and contractCode, all of
    which were already in the response we had fetched.
    """
    if hp is NO_DATA:
        # The simulator answered, and its answer is that it has never seen this token.
        # That is evidence about the token, not an outage on our side -- 15 of 25 sampled
        # unknown verdicts were this case. Filing it under "upstream request failed"
        # excused it from the no-trace escalation in _finalize, which is precisely the
        # rule written for a token nothing can verify.
        data_gaps.append({"dimension": "sellability", "source": "honeypot.is",
                          "reason": "the sell simulator has no record of this token"})
        signals.append(_sig(
            "warn", "No simulator has traded this token",
            "The sell-simulation service has no record of this token at all. That is "
            "unusual for anything with a real market and means sellability could not be "
            "checked.", "sellability"))
        return

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
        # Before relaying a honeypot verdict, check it against what the chain shows.
        #
        # A honeypot means sells fail. Measured: honeypot.is returned isHoneypot=true,
        # simulationSuccess=true and sellTax=0 for tokens with tens of thousands of
        # completed sells in 24h — AKE had 59,031. Thirteen of twenty false positives in
        # the benchmark traced to relaying that flag unexamined.
        #
        # This is the first place the engine actually adjudicates rather than restating
        # an upstream, and it is the product's whole premise: four sources that disagree,
        # collapsed into one verdict. A simulator saying "you cannot sell" loses to a
        # chain showing that thousands of people just did. The verdict is downgraded
        # rather than dropped: something is wrong with this token, we just know it is not
        # that nobody can exit.
        bp = evidence.get("best_pair") or {}
        sells, buys = _num(bp.get("sells_24h")), _num(bp.get("buys_24h"))
        # The pool also has to still be there. One token in the benchmark showed 458
        # completed sells against $0 of remaining liquidity: people got out, and then
        # the pool was drained behind them. Past sells say nothing about whether you
        # can exit now, and this override is a claim about now.
        pool_alive = _num(bp.get("liquidity_usd")) >= 5000
        sells_work = pool_alive and sells >= 20 and sells >= 0.15 * (buys + 1)
        if sells_work:
            signals.append(_sig(
                "warn", "Upstream calls this a honeypot, the chain disagrees",
                "honeypot.is reports a honeypot, but %s sells completed against %s buys "
                "in the last 24h. Sells are demonstrably going through, so this is more "
                "likely a simulator false positive than a trap — treat the token as "
                "unclear rather than fatal."
                % (format(sells, ",.0f"), format(buys, ",.0f")), "honeypot"))
            evidence["honeypot"]["contradicted_by_chain"] = {
                "sells_24h": bp.get("sells_24h"), "buys_24h": bp.get("buys_24h")}
        else:
            signals.append(_sig("fatal", "Honeypot",
                                "Simulation confirms it: you can buy, you cannot sell.",
                                "honeypot"))
    elif sim_ok is False or is_hp is None:
        err = hp.get("simulationError") or "unknown reason"
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

    # Upstream aggregate verdict (previously thrown away entirely)
    up = (summary.get("risk") or "").lower()
    flag_txt = "; ".join(flags) if flags else "none"
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
    """Read RugCheck (Solana).

    The old code read only the raw `score` and compared it against 5000/10000 — the
    units are simply wrong: BONK's raw score is 101, so every normal token passed
    unconditionally. The field to use is score_normalised (0-100), and rugged,
    mintAuthority, freezeAuthority, risks[] and topHolders all sit in that same
    response and were all dropped. freezeAuthority is the Solana honeypot: holders
    can be frozen, which amounts to not being able to sell.
    """
    if rc is None:
        data_gaps.append({"dimension": "sellability", "source": "rugcheck",
                          "reason": "upstream request failed"})
        signals.append(_sig("warn", "Contract safety unverified",
                            "RugCheck did not respond, so rug risk could not be assessed.", "sellability"))
        return

    # An empty response and "a report exists and it scores 0" must not collapse together
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

    # Retained mint and freeze authority.
    #
    # This is the same mistake the benchmark labeler made twice and had corrected there,
    # and it was never carried across to the engine: privileged functions are not by
    # themselves evidence of a scam. Circle's USDC on Solana holds both authorities by
    # design — freeze is how a regulated issuer complies with sanctions, mint is how it
    # issues against reserves — and the engine rated it high risk at score 80 on exactly
    # those two signals while RugCheck itself scored it 1/100.
    #
    # An anonymous token keeping these authorities is a real danger. A widely held,
    # reputable one keeping them is how it is built. RugCheck's own normalised score
    # already prices in the difference, so the authorities are graded against how
    # established the token is rather than in isolation.
    established = (_num(rc.get("totalHolders")) >= 100_000
                   or bool(rc.get("verification"))
                   or normalised <= 5)
    freeze, mint = rc.get("freezeAuthority"), rc.get("mintAuthority")
    if freeze or mint:
        held = " and ".join(n for n, v in (("freeze", freeze), ("mint", mint)) if v)
        if established:
            signals.append(_sig(
                "info", "Issuer retains admin authority",
                "The issuer still holds %s authority. Common for regulated or "
                "custodial assets (Circle's USDC holds both); treat as centralisation "
                "risk, not evidence of a scam." % held, "contract"))
        else:
            signals.append(_sig(
                "critical", "Anonymous issuer retains admin authority",
                "%s authority was never revoked on a token with no established holder "
                "base. Freeze authority can lock your balance, which is equivalent to "
                "being unable to sell; mint authority can dilute you without limit."
                % held.capitalize(), "honeypot" if freeze else "contract"))
    else:
        signals.append(_sig("ok", "Authorities revoked",
                            "Both mint and freeze authority have been given up.", "honeypot"))

    # Every entry in risks[] already feeds score_normalised, so emitting one signal per
    # entry double-counts and convicts a legitimate token by association — BONK, whose
    # normalised score is 7, ends up medium. So: warn-level entries only become
    # explanatory text on the main signal, and only danger-level entries get promoted to
    # their own signal, because the aggregate score can underrate a veto item like an
    # unrevoked freeze authority.
    names = [r.get("name") for r in risks if r.get("name")]
    detail = ("; ".join(names[:4])) if names else "no risk items"
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

    # Holder concentration: the strongest single predictor of a rug, and the data is
    # already sitting in this same response
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


# ---------------------------------------------------------------- the three tools

async def _load_pairs(address, chain_hint):
    """Load pairs. Returns (pairs, source); pairs is None when both sources failed."""
    ds = await _fetch_json("https://api.dexscreener.com/latest/dex/tokens/%s" % address)
    if ds is not None:
        pairs = ds.get("pairs") or []
        if pairs:
            return pairs, "dexscreener"
    # Fallback: GeckoTerminal. Network comes from chain_hint; eth is no longer hardcoded.
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
        return None, None  # fetch failed, not "there really are no pools"
    return [], "dexscreener"


# evidence fields kept in slim mode
_SLIM_EVIDENCE_KEYS = (
    "best_pair", "chains", "pair_age_days", "turnover_24h", "honeypot",
    "rugcheck", "liquidity_source", "confidence", "data_gaps", "served_stale",
    "pools_all_empty",
    "same_symbol",
)


async def assess(address, chain_hint=None, verbose=False):
    """The core call: a token's risk profile. Fail closed, address validated up front."""
    address = validate_address(address)
    del _STALE_HITS[:]          # per-request; drained into evidence at the end
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
            # Two different things reach here, and only one of them is ignorance.
            #
            # If every pool that exists holds nothing, we are not missing data -- we have
            # complete data, and it says the exit is closed. Recording that as a gap made
            # the engine answer "unknown" for the drained tokens, which is the one state
            # it should be loudest about: 8 of the 10 confirmed-unsafe tokens in the
            # benchmark came back unknown, and this was why. Fail-closed means an
            # unobserved dimension cannot buy reassurance. It never meant an observed
            # absence should be filed as a question.
            #
            # This is a sellability finding, not a depth one. Depth is how much slippage
            # you take; zero across every venue is whether you get out at all.
            # Only pools that actually stated a depth can testify about depth.
            # _pair_liquidity reports an unstated depth as 0.0, which is right for
            # ranking and catastrophic here: it would let "nobody costed these pools"
            # masquerade as "these pools are empty", and this branch turns that into a
            # sentence about the user's money.
            stated = [v for v in (_reported_liquidity(p) for p in pairs) if v is not None]
            if stated and max(stated) <= 0:
                evidence["pools_all_empty"] = len(stated)
                signals.append(_sig(
                    "critical", "No liquidity left in any pool",
                    "%d pool%s report their depth and every one of them is empty. "
                    "There is nothing to sell into at any price."
                    % (len(stated), "" if len(stated) == 1 else "s"), "sellability"))
            else:
                reason = ("no pair with a sane price" if stated
                          else "no source reported pool depth")
                data_gaps.append({"dimension": "liquidity", "source": source,
                                  "reason": reason})
                signals.append(_sig("warn", "No usable pool",
                                    "Pairs exist but none could be costed.",
                                    "no_liquidity"))
        else:
            _liquidity_signals(best, pairs, signals, evidence)
            await _impersonation_signals(address, pairs, signals, evidence,
                                         chain_hint=chain_hint)

    if _looks_evm(address):
        _honeypot_signals(
            await _fetch_json("https://api.honeypot.is/v2/IsHoneypot?address=%s" % address,
                              mark_missing=True),
            signals, evidence, data_gaps)
    elif _looks_solana(address):
        _rugcheck_signals(
            await _fetch_json("https://api.rugcheck.xyz/v1/tokens/%s/report" % address),
            signals, evidence, data_gaps)

    # If any upstream was down and we answered from cache, say so. Serving stale data
    # is defensible; serving it silently is not.
    if _STALE_HITS:
        evidence["served_stale"] = [
            {"source": u.split("/")[2], "age_seconds": a} for u, a in _STALE_HITS]
        signals.append(_sig(
            "info", "Answered partly from cache",
            "An upstream was unreachable, so up to %d seconds old data was used."
            % max(a for _, a in _STALE_HITS), "freshness"))

    result = _finalize(address, signals, evidence, data_gaps)
    if not verbose:
        # Slim by default: an agent has no use for raw fields like reserves, txHash
        # or taxDistribution.
        result["evidence"] = {k: v for k, v in result["evidence"].items()
                              if k in _SLIM_EVIDENCE_KEYS}
    return result


async def liquidity(address, chain_hint=None):
    """Liquidity snapshot. Same validation and pool-picking logic as assess."""
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
    """Scan a chain for new and trending pools."""
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
            continue  # this endpoint failed
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
        # Fail closed: a failed fetch is not the same as no new pools. Returning an
        # empty array would tell the caller "we scanned, there was nothing there".
        raise RuntimeError("GeckoTerminal request failed; could not scan new pools on %s" % chain)
    return {"chain": chain, "network": net, "count": len(merged),
            "pools": list(merged.values())[:limit]}
