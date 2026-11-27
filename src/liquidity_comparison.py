"""Pure comparison rules shared by the local CLI and client-carried MCP observations."""

import json
import math
import re
from datetime import datetime, timedelta



_CHAINS = ("ethereum", "bsc", "base", "polygon", "arbitrum", "optimism", "avalanche", "solana")
_SOURCES = ("dexscreener", "geckoterminal", "coingecko")
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MARKET_ID_PATTERN = r"^0x[0-9a-fA-F]{40}(?:-0x[0-9a-fA-F]{40}){2}$"
MARKET_ID_VENUES = ("curve", "balancer")


def _identity(chain, value, *, pool=False):
    if not isinstance(value, str):
        return None
    if chain != "solana":
        pattern = r"0x(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})" if pool else r"0x[0-9a-fA-F]{40}"
        return value.lower() if re.fullmatch(pattern, value) else None
    if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", value):
        return None
    decoded = 0
    for char in value:
        decoded = decoded * 58 + _BASE58.index(char)
    byte_count = (decoded.bit_length() + 7) // 8 + len(value) - len(value.lstrip("1"))
    return value if byte_count == 32 else None


def market_id_parts(value):
    """Recognize the observed three-component format, without yielding a pool address."""
    if not isinstance(value, str) or not re.fullmatch(MARKET_ID_PATTERN, value):
        return None
    parts = tuple(value.lower().split("-"))
    if len(set(parts)) != 3 or "0x" + "0" * 40 in parts:
        return None
    return parts


def _market_identity(row):
    chain = row.get("best_pair_chain")
    if "best_pair_market_id" not in row:
        return _identity(chain, row.get("best_pair_address"), pool=True)
    # Seven-field market observations issued before Balancer support were all Curve.
    dex = row.get("best_pair_dex", "curve")
    if (chain != "ethereum" or row.get("source") != "dexscreener" or "best_pair_address" in row
            or dex not in MARKET_ID_VENUES):
        return None
    parts = market_id_parts(row["best_pair_market_id"])
    if parts is not None and _identity(chain, row.get("address")) in parts[1:]:
        return (dex, "-".join(parts))
    return None


def _refused(reason):
    return {"status": "not_comparable", "reason": reason}


def _usable_status(row):
    if type(row) is not dict or "error" in row:
        return False
    if row.get("status") == "ok":
        return True
    amount = row.get("liquidity_usd")
    return row.get("status") == "drained" and type(amount) in (int, float) and amount == 0


def _different_network(row):
    selection = row.get("network_selection")
    return isinstance(selection, dict) and selection.get("status") == "different"


def _moment(stamp):
    if (not isinstance(stamp, str) or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
            stamp) is None or stamp.endswith("-00:00")):
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compare_replies(before, after):
    """Validate reply time, market identity and amounts before subtraction."""
    readings = (before, after)
    if not all(_usable_status(row) for row in readings):
        return _refused("unusable_response")
    if any("served_stale" in row for row in readings):
        return _refused("stale_response")
    if any(_different_network(row) for row in readings):
        return _refused("different_network")
    sources = [row.get("source") for row in readings]
    if any(source not in _SOURCES for source in sources):
        return _refused("invalid_source")
    if sources[0] != sources[1]:
        return _refused("different_source")
    identities = []
    for row in readings:
        chain = row.get("best_pair_chain")
        address = _identity(chain, row.get("address"))
        pool = _market_identity(row)
        if chain not in _CHAINS or address is None or pool is None:
            return _refused("invalid_identity")
        identities.append((chain, address, pool))
    if identities[0] != identities[1]:
        return _refused("different_pool")
    times = [_moment(row.get("checked_at")) for row in readings]
    if any(moment is None for moment in times):
        return _refused("invalid_time")
    if times[1] <= times[0]:
        return _refused("invalid_order")
    amounts = [row.get("liquidity_usd") for row in readings]
    try:
        if any(type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0
               for amount in amounts):
            return _refused("invalid_amount")
        change = amounts[1] - amounts[0]
        if not math.isfinite(change):
            return _refused("invalid_amount")
    except OverflowError:
        return _refused("invalid_amount")
    return {"status": "compared", "before_usd": amounts[0], "after_usd": amounts[1], "change_usd": change}


CONTEXT_LIMIT = 8
CONTEXT_BYTE_CAP = 8192
OBSERVATION_FIELDS = ("status", "address", "best_pair_chain", "best_pair_address", "source",
                      "checked_at", "liquidity_usd")
MARKET_OBSERVATION_FIELDS = tuple("best_pair_market_id" if field == "best_pair_address" else field
                                  for field in OBSERVATION_FIELDS)


def _observation_fields(row):
    if "best_pair_market_id" not in row:
        return OBSERVATION_FIELDS
    if row.get("best_pair_dex") == "balancer":
        return (*MARKET_OBSERVATION_FIELDS, "best_pair_dex")
    return MARKET_OBSERVATION_FIELDS


def _compact_observation(row):
    return {field: row[field] for field in _observation_fields(row)}


def _unpriced_market(row):
    return (type(row) is dict and "error" not in row and row.get("status") == "unpriced"
            and row.get("best_pair_dex") == "balancer" and "best_pair_market_id" in row
            and "liquidity_usd" in row and row["liquidity_usd"] is None)


def _reading_reason(row):
    unpriced = _unpriced_market(row)
    if not (_usable_status(row) or unpriced):
        return "unusable_response"
    if "served_stale" in row:
        return "stale_response"
    if _different_network(row):
        return "different_network"
    if row.get("source") not in _SOURCES:
        return "invalid_source"
    chain = row.get("best_pair_chain")
    if (chain not in _CHAINS or _identity(chain, row.get("address")) is None
            or _market_identity(row) is None):
        return "invalid_identity"
    if _moment(row.get("checked_at")) is None:
        return "invalid_time"
    if unpriced:
        return None
    amount = row.get("liquidity_usd")
    try:
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            return "invalid_amount"
    except OverflowError:
        return "invalid_amount"
    return None


def validate_context(context):
    """Reject malformed client state before fetching; never echo its contents in errors."""
    if type(context) is not list or len(context) > CONTEXT_LIMIT:
        raise ValueError("comparison_context must be a list of at most 8 compact observations")
    for row in context:
        if type(row) is not dict or set(row) != set(_observation_fields(row)) or _reading_reason(row):
            raise ValueError("comparison_context contains invalid observations")
    try:
        size = len(json.dumps(context, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("comparison_context contains invalid observations") from None
    if size > CONTEXT_BYTE_CAP:
        raise ValueError("comparison_context exceeds 8192 bytes")
    return [_compact_observation(row) for row in context]


def _key(row):
    chain = row["best_pair_chain"]
    return (chain, _identity(chain, row["address"]), _market_identity(row), row["source"])


def _timestamp_precision(stamp):
    fraction = re.search(r"\.([0-9]+)", stamp)
    digits = len(fraction[1]) if fraction else 0
    return timedelta(microseconds=10 ** (6 - digits))


def _market_time(row):
    stamp = row["checked_at"]
    retrieved = _moment(row.get("market_retrieved_at"))
    if retrieved is not None and retrieved - _moment(stamp) < _timestamp_precision(stamp):
        return retrieved
    return None


def _established_repeat(current, baseline, retrieved):
    return (retrieved is not None and retrieved < _moment(baseline["checked_at"])
            and _key(baseline) == _key(current) and baseline["status"] == current["status"]
            and baseline["liquidity_usd"] == current["liquidity_usd"])


def _newer_market_retrieval(retrieved, baseline):
    # Records may give the reply time only to the second. Require the new
    # retrieval to follow the baseline's entire reported clock tick.
    stamp = baseline["checked_at"]
    return retrieved - _moment(stamp) >= _timestamp_precision(stamp)


def compare(before, after):
    """Compare two saved replies, using market retrieval evidence when supplied."""
    result = _compare_replies(before, after)
    if result["status"] == "compared":
        if "market_retrieved_at" in before and _market_time(before) is None:
            return _refused("market_time_unconfirmed")
        if "market_retrieved_at" in after:
            retrieved = _market_time(after)
            if retrieved is None:
                return _refused("market_time_unconfirmed")
            if not _newer_market_retrieval(retrieved, before):
                return _refused("no_new_market_data")
    elif (result["reason"] == "invalid_order" and "market_retrieved_at" in after
            and _moment(before["checked_at"]) == _moment(after["checked_at"])
            and _reading_reason(before) is None and _reading_reason(after) is None
            and _established_repeat(after, before, _market_time(after))):
        return _refused("no_new_market_data")
    return result


def with_context(current, context, *, requested):
    """Use only the current fetch and bounded caller state; retain no server history."""
    answer = dict(current)
    reason = _reading_reason(current)
    retain_current = reason is None
    comparison = _refused(reason or "no_previous_observation")
    comparison["baseline_origin"] = "client_observation"
    if reason is None:
        unpriced = _unpriced_market(current)
        if unpriced:
            comparison["reason"] = "no_usd_estimate"
        tracked = "market_retrieved_at" in current
        retrieved = _market_time(current)
        now = _moment(current["checked_at"])
        current_key = _key(current)
        target = current_key[:2]
        same_target = [row for row in context if _key(row)[:2] == target]
        prior = [row for row in same_target if _moment(row["checked_at"]) < now]
        tied_current = [row for row in same_target if _moment(row["checked_at"]) == now]
        candidates = [(row, _compare_replies(row, current)) for row in prior]
        comparable = [(row, result) for row, result in candidates if result["status"] == "compared"]
        if tracked and tied_current:
            repeated = all(_established_repeat(current, row, retrieved) for row in tied_current)
            comparison["reason"] = "no_new_market_data" if repeated else "invalid_order"
            retain_current = False
        elif tracked and retrieved is None:
            comparison["reason"] = "market_time_unconfirmed"
            retain_current = False
        elif prior:
            latest = max(prior, key=lambda row: _moment(row["checked_at"]))
            matching = [(row, result) for row, result in candidates if _key(row) == current_key]
            latest_match = max(matching, key=lambda item: _moment(item[0]["checked_at"]), default=None)
            # A timestamp tie across pools cannot establish which selection was latest.
            tied = [row for row in prior if _moment(row["checked_at"]) == _moment(latest["checked_at"])]
            pools = {_key(row)[2] for row in tied}
            comparison["pool_transition"] = {
                "status": ("ambiguous" if len(pools) > 1 else
                           "unchanged" if _key(latest)[2] == current_key[2] else "changed"),
                "previous_checked_at": latest["checked_at"],
            }
            if "best_pair_market_id" in latest:
                comparison["pool_transition"]["previous_market_id"] = latest["best_pair_market_id"]
                if "best_pair_dex" in latest:
                    comparison["pool_transition"]["previous_market_dex"] = latest["best_pair_dex"]
            else:
                comparison["pool_transition"]["previous_pool_address"] = latest["best_pair_address"]
            if (retrieved is not None and latest_match and (unpriced or _unpriced_market(latest_match[0]))
                    and not _newer_market_retrieval(retrieved, latest_match[0])):
                comparison["reason"] = "no_new_market_data"
                retain_current = False
            elif comparable:
                baseline, result = max(comparable, key=lambda item: _moment(item[0]["checked_at"]))
                stamp = baseline["checked_at"]
                if retrieved is not None and not _newer_market_retrieval(retrieved, baseline):
                    comparison["reason"] = "no_new_market_data"
                    retain_current = False
                else:
                    comparison.update(result)
                    comparison.pop("reason", None)
                    comparison.update(before_checked_at=stamp, after_checked_at=current["checked_at"],
                        baseline_is_latest_observation=all(_key(row) == _key(baseline) for row in tied)
                            and _moment(stamp) == _moment(latest["checked_at"]))
            elif not unpriced:
                comparison["reason"] = "different_pool" if _key(latest)[2] != current_key[2] else "different_source"
                # A matching pool/provider with an invalid delta is not a source change.
                if latest_match:
                    row, result = latest_match
                    comparison["reason"] = "no_previous_usd_observation" if _unpriced_market(row) else result["reason"]
        elif same_target:
            comparison["reason"] = "invalid_order"
        nonprior = len(same_target) - len(prior)
        if nonprior:
            comparison["nonprior_observations"] = nonprior

    # Keep the last USD estimate and the last unpriced reading together when a
    # recently observed market competes for space with older markets.
    def reply_time(row):
        return _moment(row["checked_at"])

    retained = {}
    for row in context + ([_compact_observation(current)] if retain_current else []):
        market = retained.setdefault(_key(row), {})
        kind = _unpriced_market(row)
        if kind not in market or reply_time(row) > reply_time(market[kind]):
            market[kind] = row
    by_market = sorted(retained.values(), key=lambda market: max(map(reply_time, market.values())))
    rows = [row for market in by_market for row in sorted(market.values(), key=reply_time)]
    evicted = max(0, len(rows) - CONTEXT_LIMIT)
    if evicted:
        comparison["context_evicted"] = evicted
    answer["comparison_context"] = sorted(rows[-CONTEXT_LIMIT:], key=reply_time)
    if requested:
        answer["comparison"] = comparison
    return answer
