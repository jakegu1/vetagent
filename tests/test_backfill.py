"""test_backfill.py -- the log decoder is right about which 20 bytes are the pool.

Why this file exists, specifically
----------------------------------
Reading a pool address out of a factory log is byte-offset arithmetic against an ABI
layout, and V2 and V3 do not share a layout: V2 puts the pair in the first word of data,
V3 puts tickSpacing there and the pool in the second. Get that wrong and nothing raises.
The harvest still writes thousands of rows, every one of them a plausible-looking 20-byte
address that belongs to nobody, and the labeller simply returns nothing for all of them.
The visible symptom would be "backfill has poor yield" -- a wrong conclusion about the
method, drawn from a bug in the parser, which is the most expensive kind of wrong.

This project has already paid for that lesson three times: isHoneypot read from a key
that upstream does not have, so the honeypot check always passed; pairCreatedAt parsed as
ISO when it is epoch milliseconds, so pair age never fired; liquidity picked without
_pick_best, so USDC priced at $0.00097. Each was silent, each returned a confident wrong
answer, and none could have survived a round trip to the source.

So the real assertion here is a round trip. Take pools the decoder found, ask the chain
what token0 and token1 those contracts actually hold, and require the answer to match the
log we decoded them from. A contract that answers correctly is the pool; nothing else
would be.

Run:  python tests/test_backfill.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))

import backfill  # noqa: E402

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def _word(hex_no_prefix, i):
    return hex_no_prefix[i * 64:(i + 1) * 64]


def _topic(addr):
    return "0x" + "0" * 24 + addr[2:].lower()


def test_decode_offsets_offline():
    """V2 and V3 put the pool in different words. Hand-built logs, exact expectations."""
    print("\n[decode] the two ABI layouts")
    weth = "0x4200000000000000000000000000000000000006"
    token = "0x1111111111111111111111111111111111111111"
    pool = "0x2222222222222222222222222222222222222222"
    quotes = {weth}

    v2 = {"topics": [backfill.V2_TOPIC, _topic(weth), _topic(token)],
          "data": "0x" + "0" * 24 + pool[2:] + "0" * 64}
    got = backfill._decode(v2, quotes)
    check("V2 takes the pair from the first data word",
          got == {"base": token, "pool": pool}, str(got))

    # V3: tickSpacing occupies word 0, the pool is word 1.
    v3 = {"topics": [backfill.V3_TOPIC, _topic(token), _topic(weth), "0x" + "0" * 61 + "bb8"],
          "data": "0x" + "0" * 64 + "0" * 24 + pool[2:]}
    got = backfill._decode(v3, quotes)
    check("V3 skips tickSpacing and takes the second word",
          got == {"base": token, "pool": pool}, str(got))

    # If V3 were decoded with the V2 offset it would return the tickSpacing word as an
    # address -- all zeroes here. Assert we are not doing that.
    check("V3 is not decoded at the V2 offset",
          got["pool"] != "0x" + "0" * 40, got["pool"])


def test_pairs_of_quote_assets_are_not_launches():
    """WETH/USDC is plumbing. A pair with no identifiable token has no token to score."""
    print("\n[decode] what counts as a launch")
    weth = "0x4200000000000000000000000000000000000006"
    usdc = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    a = "0x1111111111111111111111111111111111111111"
    b = "0x3333333333333333333333333333333333333333"
    pool = "0x2222222222222222222222222222222222222222"
    quotes = {weth, usdc}

    def v2(t0, t1):
        return {"topics": [backfill.V2_TOPIC, _topic(t0), _topic(t1)],
                "data": "0x" + "0" * 24 + pool[2:] + "0" * 64}

    check("two quote assets are skipped", backfill._decode(v2(weth, usdc), quotes) is None)
    check("two unknown tokens are skipped", backfill._decode(v2(a, b), quotes) is None)
    check("one quote and one token is a launch",
          (backfill._decode(v2(weth, a), quotes) or {}).get("base") == a)
    check("a truncated log does not raise",
          backfill._decode({"topics": [backfill.V2_TOPIC], "data": "0x"}, quotes) is None)


def test_decoded_pools_are_real_pools():
    """The round trip: ask each decoded contract what it holds, and check it matches.

    This is the assertion the offline tests cannot make. They prove the decoder is
    self-consistent; only the chain can say whether it is correct.
    """
    print("\n[round trip] decoded pools answer to the tokens we decoded them with")
    chain = "base"
    cfg = backfill.CHAINS[chain]
    urls = cfg["rpc"]

    try:
        head = int(backfill.rpc_any(urls, "eth_blockNumber", [])["result"], 16)
        r = backfill.rpc_any(urls, "eth_getLogs", [{
            "fromBlock": hex(head - 25000), "toBlock": hex(head - 20000),
            "address": cfg["factories"],
            "topics": [[backfill.V2_TOPIC, backfill.V3_TOPIC]]}])
    except Exception as e:  # noqa: BLE001
        check("base RPC reachable", False, str(e)[:90])
        return
    if "error" in r:
        check("base RPC served the log range", False, str(r["error"])[:90])
        return

    decoded = []
    for log in r["result"]:
        d = backfill._decode(log, cfg["quotes"])
        if d:
            d["sides"] = {("0x" + t[-40:]).lower() for t in log["topics"][1:3]}
            decoded.append(d)

    check("the sample range yielded launches to verify", len(decoded) >= 3, str(len(decoded)))
    if not decoded:
        return

    verified = 0
    checked = 0
    for d in decoded[:6]:
        answers, unreachable = [], False
        for selector in ("0x0dfe1681", "0xd21220a7"):      # token0(), token1()
            try:
                res = backfill.rpc_any(urls, "eth_call",
                                       [{"to": d["pool"], "data": selector}, "latest"],
                                       timeout=15)
            except Exception:                               # noqa: BLE001
                unreachable = True
                break
            if "result" not in res:
                unreachable = True                          # including a rate-limit item
                break
            answers.append(res["result"] or "")
        if unreachable:
            continue        # the node would not answer; that says nothing either way

        # An address that answers but returns empty is NOT a pool -- which is precisely
        # what a wrong byte offset produces. Skipping those made this assertion pass by
        # ignoring exactly the failures it exists to catch.
        if any(len(a) < 66 for a in answers):
            checked += 1
            print("      %s does not answer token0/token1 -- not a pool" % d["pool"])
            continue
        checked += 1
        held = {"0x" + a[-40:].lower() for a in answers}
        if held == d["sides"]:
            verified += 1
        else:
            print("      mismatch at %s: chain says %s, log said %s"
                  % (d["pool"], sorted(held), sorted(d["sides"])))

    check("every decoded pool holds exactly the tokens its log named",
          checked > 0 and verified == checked, "%d/%d verified" % (verified, checked))


def test_a_day_is_bracketed_by_its_own_boundaries():
    """block_at must land inside the day it was asked for, not near it.

    An unbracketed binary search returns an endpoint of its own search window rather
    than failing, so a seed that misses would silently harvest the wrong date -- and
    every row would still look perfectly well-formed.
    """
    print("\n[block_at] boundaries land inside the requested day")
    import datetime
    cfg = backfill.CHAINS["base"]
    urls = cfg["rpc"]
    day = datetime.date.today() - datetime.timedelta(days=45)
    start = int(datetime.datetime(day.year, day.month, day.day,
                                  tzinfo=datetime.timezone.utc).timestamp())
    try:
        head = int(backfill.rpc_any(urls, "eth_blockNumber", [])["result"], 16)
        b0 = backfill.block_at(urls, start, head, cfg["block_seconds"])
        t0 = backfill._timestamp_of(urls, b0)
        t_next = backfill._timestamp_of(urls, b0 + 1)
    except Exception as e:  # noqa: BLE001
        check("base RPC reachable for block_at", False, str(e)[:90])
        return

    check("the block found is at or before the boundary", t0 <= start, "%d vs %d" % (t0, start))
    check("and the very next block is after it -- so it is the last one, not merely one "
          "of many", t_next > start, "%d vs %d" % (t_next, start))
    check("the boundary is within a minute of midnight UTC", start - t0 < 60,
          "%ds early" % (start - t0))


def main():
    print("=" * 66)
    print("Backfill decoder tests")
    print("=" * 66)
    for fn in (test_decode_offsets_offline,
               test_pairs_of_quote_assets_are_not_launches,
               test_decoded_pools_are_real_pools,
               test_a_day_is_bracketed_by_its_own_boundaries):
        fn()
    print("\n" + "=" * 66)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
