"""Compare two saved successful liquidity response objects, before.json then after.json.

Save a REST /liquidity JSON body or MCP result.structuredContent, not an envelope.
Amounts are USD estimates. checked_at is reply time and source data may be cached.
"""

import json
import math
import re
from datetime import datetime

from assessment_policy import BYTE_CAP, _Parser, _emit, _nonfinite, _unique_object


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


def compare(before, after):
    """Compare saved reply estimates only after validating their shared context."""
    readings = (before, after)
    if any(type(row) is not dict or row.get("status") != "ok" or "error" in row for row in readings):
        return _refused("unusable_response")
    if any("served_stale" in row for row in readings):
        return _refused("stale_response")
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
    times = []
    try:
        for row in readings:
            stamp = row.get("checked_at")
            if not isinstance(stamp, str) or len(stamp) > 40:
                return _refused("invalid_time")
            moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                return _refused("invalid_time")
            times.append(moment)
    except ValueError:
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


def _read(path):
    with open(path, "rb") as handle:
        raw = handle.read(BYTE_CAP + 1)
    if len(raw) > BYTE_CAP:
        raise ValueError("input_too_large")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)


def main(argv=None):
    parser = _Parser(prog="liquidity_compare", description=__doc__, allow_abbrev=False)
    parser.add_argument("before", help="Earlier successful liquidity response object")
    parser.add_argument("after", help="Later successful liquidity response object")
    args = parser.parse_args(argv)
    try:
        result = compare(_read(args.before), _read(args.after))
    except (OSError, ValueError, UnicodeError, RecursionError, OverflowError):
        _emit({"error": "input_refused"})
        return 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
