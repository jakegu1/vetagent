"""Pure comparison rules shared by the local CLI and client-carried MCP observations."""

import json
import math
import re
from datetime import datetime, timedelta



_CHAINS = ("ethereum", "bsc", "base", "polygon", "arbitrum", "optimism", "avalanche", "solana")
_SOURCES = ("dexscreener", "geckoterminal", "coingecko")
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


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
        pool = _identity(chain, row.get("best_pair_address"), pool=True)
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


def _reading_reason(row):
    if not _usable_status(row):
        return "unusable_response"
    if "served_stale" in row:
        return "stale_response"
    if _different_network(row):
        return "different_network"
    if row.get("source") not in _SOURCES:
        return "invalid_source"
    chain = row.get("best_pair_chain")
    if (chain not in _CHAINS or _identity(chain, row.get("address")) is None
            or _identity(chain, row.get("best_pair_address"), pool=True) is None):
        return "invalid_identity"
    if _moment(row.get("checked_at")) is None:
        return "invalid_time"
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
        if type(row) is not dict or set(row) != set(OBSERVATION_FIELDS) or _reading_reason(row):
            raise ValueError("comparison_context contains invalid observations")
    try:
        size = len(json.dumps(context, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("comparison_context contains invalid observations") from None
    if size > CONTEXT_BYTE_CAP:
        raise ValueError("comparison_context exceeds 8192 bytes")
    return [{field: row[field] for field in OBSERVATION_FIELDS} for row in context]


def _key(row):
    chain = row["best_pair_chain"]
    return (chain, _identity(chain, row["address"]),
            _identity(chain, row["best_pair_address"], pool=True), row["source"])


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
        tracked = "market_retrieved_at" in current
        retrieved = _market_time(current)
        now = _moment(current["checked_at"])
        target = _key(current)[:2]
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
            # A timestamp tie across pools cannot establish which selection was latest.
            tied = [row for row in prior if _moment(row["checked_at"]) == _moment(latest["checked_at"])]
            pools = {_key(row)[2] for row in tied}
            comparison["pool_transition"] = {
                "status": ("ambiguous" if len(pools) > 1 else
                           "unchanged" if _key(latest)[2] == _key(current)[2] else "changed"),
                "previous_pool_address": latest["best_pair_address"],
                "previous_checked_at": latest["checked_at"],
            }
            if comparable:
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
            else:
                comparison["reason"] = "different_pool" if _key(latest)[2] != _key(current)[2] else "different_source"
                # A matching pool/provider with an invalid delta is not a source change.
                matching = [(row, result) for row, result in candidates if _key(row) == _key(current)]
                if matching:
                    comparison["reason"] = max(matching, key=lambda item: _moment(item[0]["checked_at"]))[1]["reason"]
        elif same_target:
            comparison["reason"] = "invalid_order"
        nonprior = len(same_target) - len(prior)
        if nonprior:
            comparison["nonprior_observations"] = nonprior

    # Retain the newest observation per pool/provider, then the newest eight keys.
    retained = {}
    for row in context + ([{field: current[field] for field in OBSERVATION_FIELDS}] if retain_current else []):
        key = _key(row)
        if key not in retained or _moment(row["checked_at"]) > _moment(retained[key]["checked_at"]):
            retained[key] = row
    rows = sorted(retained.values(), key=lambda row: _moment(row["checked_at"]))
    evicted = max(0, len(rows) - CONTEXT_LIMIT)
    if evicted:
        comparison["context_evicted"] = evicted
    answer["comparison_context"] = rows[-CONTEXT_LIMIT:]
    if requested:
        answer["comparison"] = comparison
    return answer
