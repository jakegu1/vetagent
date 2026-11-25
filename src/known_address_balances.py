"""Read an ERC-20 supply and fixed addresses at one rechecked block."""
import asyncio
import json
import re

CHAIN_IDS = {"ethereum": 1, "bsc": 56, "base": 8453}
ZERO = "0x" + "0" * 40
DEAD = "0x" + "0" * 36 + "dead"
_QUANTITY = re.compile(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})")
_WORD = re.compile(r"0x[0-9a-fA-F]{64}")


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON-RPC member")
    return result


async def _read(fetch, url, request_id, method, params):
    if fetch is None:
        return None
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    try:
        async with asyncio.timeout(4):
            # workerd accepts manual redirects. Reject 3xx before parsing or following them.
            response = await fetch(url, method="POST", body=json.dumps(payload), redirect="manual",
                                   headers={"content-type": "application/json"})
            if response.status != 200:
                return None
            reply = json.loads(await response.text(), object_pairs_hook=_unique_object)
    except Exception:  # This optional reading must leave the liquidity result usable.
        return None
    if (not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0"
            or type(reply.get("id")) is not int or reply["id"] != request_id
            or "error" in reply):
        return None
    return reply.get("result")


def _quantity(value):
    return int(value, 16) if isinstance(value, str) and _QUANTITY.fullmatch(value) else None


def _uint256(value):
    return int(value, 16) if isinstance(value, str) and _WORD.fullmatch(value) else None


def _block(value):
    if not isinstance(value, dict):
        return None
    number, block_hash = _quantity(value.get("number")), value.get("hash")
    if (number is not None and isinstance(block_hash, str)
            and _WORD.fullmatch(block_hash) and int(block_hash, 16) != 0):
        return number, block_hash.lower()
    return None


def _pool_token(value):
    if isinstance(value, str) and _WORD.fullmatch(value) and value[2:26] == "0" * 24:
        return "0x" + value[-40:].lower()
    return None


def _percent(balance, supply):
    scale = 1_000_000
    scaled = balance * 100 * scale
    if 0 < scaled < supply:
        return "<0.000001"
    units, remainder = divmod(scaled, supply)
    whole, fraction = divmod(units + (remainder * 2 >= supply), scale)
    return "%d.%06d" % (whole, fraction)


def unavailable(reading, reason):
    return dict(reading, status="unavailable", reason=reason)


def _balance(address, raw, supply):
    if raw is None:
        return unavailable({"address": address}, "balance_unavailable")
    return {"status": "ok", "address": address, "balance_raw": str(raw), "supply_percent": _percent(raw, supply)}


async def observe(fetch, url, reading, pool_tokens, pool_reason):
    """At most nine individual calls. Every eth_call uses the same block number."""
    chain = await _read(fetch, url, 1, "eth_chainId", [])
    chain_id = _quantity(chain)
    if chain_id is None:
        return unavailable(reading, "rpc_chain_unavailable")
    if chain_id != CHAIN_IDS[reading["chain"]]:
        return unavailable(reading, "rpc_chain_mismatch")
    start = _block(await _read(fetch, url, 2, "eth_getBlockByNumber", ["latest", False]))
    if start is None:
        return unavailable(reading, "block_unavailable")
    block_number, block_hash = start
    block_tag = hex(block_number)
    token = reading["address"]
    pool = reading["pool_id"]

    async def call(request_id, contract, data):
        return await _read(fetch, url, request_id, "eth_call", [{"to": contract, "data": data}, block_tag])

    async def balance_of(request_id, address):
        return _uint256(await call(request_id, token, "0x70a08231" + address[2:].rjust(64, "0")))

    async def pool_balance():
        left, right = await asyncio.gather(call(6, pool, "0x0dfe1681"), call(7, pool, "0xd21220a7"))
        sides = {_pool_token(left), _pool_token(right)}
        if None in sides:
            return None, "pool_tokens_unavailable"
        if sides != pool_tokens:
            return None, "pool_tokens_mismatch"
        return await balance_of(8, pool), None

    calls = [call(3, token, "0x18160ddd"), balance_of(4, ZERO), balance_of(5, DEAD)]
    if pool_tokens:
        calls.append(pool_balance())
    supply_word, zero_raw, dead_raw, *pool_result = await asyncio.gather(*calls)
    pool_raw, pool_reason = pool_result[0] if pool_result else (None, pool_reason)
    end = _block(await _read(fetch, url, 9, "eth_getBlockByNumber", [block_tag, False]))
    if end is None:
        return unavailable(reading, "block_unconfirmed")
    if end != start:
        return unavailable(reading, "block_changed")
    supply = _uint256(supply_word)
    if not supply:
        return unavailable(reading, "invalid_total_supply")
    amounts = (pool_raw, zero_raw, dead_raw)
    if sum(n for n in amounts if n is not None) > supply:
        return unavailable(reading, "balances_exceed_supply")
    if all(n is None for n in amounts):
        reading = unavailable(reading, "balances_unavailable")
    else:
        reading = dict(reading, status="ok" if all(n is not None for n in amounts) else "partial")
    # The pool is a distinct named address only after its two tokens are confirmed.
    pool_reading = (unavailable({"address": pool}, pool_reason) if pool_tokens and pool_reason else
                    _balance(pool, pool_raw, supply) if pool_tokens else unavailable({}, pool_reason))
    return dict(reading, block_number=str(block_number), block_hash=block_hash, total_supply_raw=str(supply),
                balances={"pool": pool_reading, "zero": _balance(ZERO, zero_raw, supply),
                          "dead": _balance(DEAD, dead_raw, supply)})
