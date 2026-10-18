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

import contextlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))

import backfill  # noqa: E402

_FAILURES = []
_PASSED = 0
_UNOBSERVED = []
_ADAPTER = None
_LIVE_TESTS = {"test_decoded_pools_are_real_pools", "test_a_day_is_bracketed_by_its_own_boundaries"}
_HEX_DATA = re.compile(r"0x(?:[0-9a-fA-F]{2})*")
_HEX_QUANTITY = re.compile(r"0x[0-9a-fA-F]+")


class _ObservationError(Exception):
    """A wire observation could not be used. Never wrap an engine exception in this."""
    def __init__(self, kind, method, provider="none", status="none"):
        super().__init__(kind)
        self.labels = (kind, method, provider, str(status))


class _ObservationHTTPError(urllib.error.HTTPError):
    """Keep range-refusal ancestry for frozen logs_in_range, with no private URL/body."""
    def __init__(self, code, method, provider):
        super().__init__("", code, "observation unavailable", {}, None)
        self.labels = ("http", method, provider, str(code))


_OBSERVATION_ERRORS = (_ObservationError, _ObservationHTTPError)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError("", code, "redirect refused", {}, None)


class _ObservationRPC:
    """Test-owned acquisition budget, shared by the two live tests in one invocation.

    It replaces only their rpc_any seam. Collector code and its offline range controls
    retain their own behavior. The deadline bounds attempts/read timeouts, not platform
    DNS blocking; the live workflow also has a three-minute outer timeout.
    """
    def __init__(self):
        self.attempts = 0
        self.request_id = 0
        self.deadline = time.monotonic() + 60
        self.opener = urllib.request.build_opener(_NoRedirect())

    def _remaining(self, method, provider):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise _ObservationError("deadline", method, provider)
        return remaining

    def _read(self, response, method, provider, timeout):
        raw = bytearray()
        cap = 2 * 1024 * 1024
        while True:
            remaining = self._remaining(method, provider)
            # HTTPResponse's underlying socket supports updating the timeout between
            # bounded read1 calls. In-memory streams need no socket.
            sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if sock is not None:
                sock.settimeout(min(15, timeout, remaining))
            read = getattr(response, "read1", response.read)
            chunk = read(min(65536, cap - len(raw) + 1))
            self._remaining(method, provider)
            raw.extend(chunk)
            if len(raw) > cap:
                raise _ObservationError("oversize", method, provider)
            if not chunk:
                return bytes(raw)

    @staticmethod
    def _usable(method, value):
        def quantity(item):
            return isinstance(item, str) and _HEX_QUANTITY.fullmatch(item) is not None
        def data(item):
            return isinstance(item, str) and _HEX_DATA.fullmatch(item) is not None
        if method == "eth_blockNumber":
            return quantity(value)
        if method == "eth_getBlockByNumber":
            return isinstance(value, dict) and quantity(value.get("timestamp"))
        if method == "eth_call":
            # Empty/short valid DATA is observed contract evidence, not an outage.
            return data(value)
        if method == "eth_getLogs":
            if not isinstance(value, list):
                return False
            for log in value:
                if not isinstance(log, dict):
                    return False
                topics = log.get("topics")
                if not isinstance(topics, list) or len(topics) < 3:
                    return False
                if topics[0] not in (backfill.V2_TOPIC, backfill.V3_TOPIC):
                    return False
                if topics[0] == backfill.V3_TOPIC and len(topics) < 4:
                    return False
                if any(not data(t) or len(t) != 66 for t in topics):
                    return False
                body = log.get("data")
                if not data(body) or len(body) < 130:
                    return False
            return True
        raise ValueError("unexpected local RPC method")

    def __call__(self, urls, method, params, timeout=30):
        if tuple(urls) != tuple(backfill.CHAINS["base"]["rpc"]):
            raise ValueError("unexpected local provider configuration")
        self.request_id += 1
        request_id = self.request_id
        body = json.dumps({"jsonrpc": "2.0", "id": request_id,
                           "method": method, "params": params}).encode()
        last = None
        for index, url in enumerate(urls):
            provider = "primary" if index == 0 else "fallback"
            remaining = self._remaining(method, provider)
            if self.attempts >= 64:
                raise _ObservationError("attempt-budget", method, provider)
            self.attempts += 1
            req = urllib.request.Request(url, method="POST", data=body, headers=backfill._UA)
            try:
                with self.opener.open(req, timeout=min(15, timeout, remaining)) as response:
                    raw = self._read(response, method, provider, timeout)
            except urllib.error.HTTPError as exc:
                if method == "eth_getLogs" and exc.code in (413, 429):
                    raise _ObservationHTTPError(exc.code, method, provider) from None
                kind = "redirect" if 300 <= exc.code < 400 else "http"
                last = _ObservationError(kind, method, provider, exc.code)
                continue
            except (urllib.error.URLError, OSError):
                last = _ObservationError("transport", method, provider)
                continue
            except _ObservationError as exc:
                last = exc
                continue
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                last = _ObservationError("malformed-json", method, provider)
                continue
            if (not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0"
                    or type(payload.get("id")) is not int or payload["id"] != request_id
                    or (("result" in payload) == ("error" in payload))):
                last = _ObservationError("malformed-envelope", method, provider)
                continue
            if "error" in payload:
                error = payload["error"]
                kind = "rpc-refusal" if (isinstance(error, dict)
                                         and type(error.get("code")) is int) else "malformed-envelope"
                last = _ObservationError(kind, method, provider)
                continue
            if not self._usable(method, payload["result"]):
                last = _ObservationError("unusable-result", method, provider)
                continue
            return payload
        raise last


@contextlib.contextmanager
def _live_rpc():
    original = backfill.rpc_any
    backfill.rpc_any = _ADAPTER if _ADAPTER is not None else _ObservationRPC()
    try:
        yield
    finally:
        backfill.rpc_any = original


def _unobserved(name, error=None):
    labels = error.labels if error is not None else ("coverage", "none", "none", "none")
    _UNOBSERVED.append((name, labels))
    print("  UNOBSERVED %s class=%s method=%s provider=%s status=%s" % ((name,) + labels))


def _live_test(function):
    def run():
        with _live_rpc():
            return function()
    return run


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


@_live_test
def test_decoded_pools_are_real_pools():
    """The round trip: ask each decoded contract what it holds, and check it matches.

    This is the assertion the offline tests cannot make. They prove the decoder is
    self-consistent; only the chain can say whether it is correct.
    """
    print("\n[round trip] decoded pools answer to the tokens we decoded them with")
    chain = "base"
    cfg = backfill.CHAINS[chain]
    urls = cfg["rpc"]

    # Through `logs_in_range`, which is what harvest() uses. This asked for a fixed
    # 5,000-block range with a hand-rolled `rpc_any` until 2026-09-10, when Base's public
    # RPC began answering 413 to exactly that -- so the test went red while the collector
    # carried on, because the collector narrows the window and the test did not. Measured
    # that morning: 5,000 blocks 413, 2,000 blocks fine. A test that does not drive the
    # shipped path fails for reasons the product does not have.
    try:
        head = int(backfill.rpc_any(urls, "eth_blockNumber", [])["result"], 16)
        logs = backfill.logs_in_range(
            urls, head - 25000, head - 20000, [[backfill.V2_TOPIC, backfill.V3_TOPIC]],
            address=cfg["factories"], step=5000, floor=200, what="pool creations")
        r = {"result": logs}
    except _OBSERVATION_ERRORS as error:
        _unobserved("the sample range yielded launches to verify", error)
        _unobserved("every decoded pool holds exactly the tokens its log named", error)
        return

    decoded = []
    for log in r["result"]:
        d = backfill._decode(log, cfg["quotes"])
        if d:
            d["sides"] = {("0x" + t[-40:]).lower() for t in log["topics"][1:3]}
            decoded.append(d)

    if len(decoded) < 3:
        _unobserved("the sample range yielded launches to verify")
    else:
        check("the sample range yielded launches to verify", len(decoded) >= 3, str(len(decoded)))
    if not decoded:
        _unobserved("every decoded pool holds exactly the tokens its log named")
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
            except _OBSERVATION_ERRORS as error:
                _unobserved("token pair observation", error)
                unreachable = True
                break
            answers.append(res["result"] or "")
        if unreachable:
            continue        # the node would not answer; that says nothing either way

        # An address that answers but returns empty is NOT a pool -- which is precisely
        # what a wrong byte offset produces. Skipping those made this assertion pass by
        # ignoring exactly the failures it exists to catch.
        if any(len(a) < 66 for a in answers):
            checked += 1
            continue
        checked += 1
        held = {"0x" + a[-40:].lower() for a in answers}
        if held == d["sides"]:
            verified += 1
    if checked < 3:
        _unobserved("three complete token-pair observations")
    # A thin sample is a coverage gap, but cannot erase a contradiction already seen.
    if (checked and verified != checked) or (len(decoded) >= 3 and checked >= 3):
        check("every decoded pool holds exactly the tokens its log named",
              checked > 0 and verified == checked, "%d/%d verified" % (verified, checked))
    else:
        _unobserved("every decoded pool holds exactly the tokens its log named")


@_live_test
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
    except _OBSERVATION_ERRORS as error:
        _unobserved("the block found is at or before the boundary", error)
        _unobserved("and the very next block is after it -- so it is the last one, not merely one "
                    "of many", error)
        _unobserved("the boundary is within a minute of midnight UTC", error)
        return

    check("the block found is at or before the boundary", t0 <= start)
    check("and the very next block is after it -- so it is the last one, not merely one "
          "of many", t_next > start)
    check("the boundary is within a minute of midnight UTC", start - t0 < 60)


def test_a_refused_range_narrows_the_window_and_skips_no_blocks():
    """The narrowing is load-bearing and had no test until the day it started earning its keep.

    On 2026-09-10 Base's public RPC began refusing a 5,000-block factory query with HTTP
    413. The collector absorbed it -- that is what this loop is for -- but nothing in the
    repo checked that it absorbs it correctly, and "correctly" here has a specific meaning
    that was got wrong once: **narrowing the window must not shorten the range**. The swap
    sampler's first version broke out after one successful smaller request, so a busy window
    contributed a fraction of its blocks and the sample thinned exactly where trading was
    heaviest -- a rate limit recorded as a quiet market.

    Offline, with a stub node, because the invariant is about our loop and not about any
    node's current ceiling. The stub refuses anything wider than 1,000 blocks, which is the
    shape of what the real node started doing.
    """
    print(chr(10) + "[narrowing] a refused range costs a window, never a block")

    for mode in ("http_413", "http_429", "json_error"):
        seen_ranges = []

        def fake_rpc(urls, method, params, timeout=30):
            flt = params[0]
            lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
            seen_ranges.append((lo, hi))
            if hi - lo > 1000:
                if mode == "http_413":
                    raise urllib.error.HTTPError(urls[0], 413, "Payload Too Large", {}, None)
                if mode == "http_429":
                    raise urllib.error.HTTPError(urls[0], 429, "Too Many Requests", {}, None)
                return {"error": {"code": -32005, "message": "query returned too many"}}
            # One log per block, so coverage is countable rather than inferred.
            return {"result": [{"address": "0x%040x" % b, "blockNumber": hex(b)}
                               for b in range(lo, hi + 1)]}

        original = backfill.rpc_any
        backfill.rpc_any = fake_rpc
        try:
            logs = backfill.logs_in_range(["http://stub"], 100000, 108000, [["0xtopic"]],
                                          step=5000, floor=200, what="test")
        finally:
            backfill.rpc_any = original

        blocks = [int(l["blockNumber"], 16) for l in logs]
        want = list(range(100000, 108001))
        check("%s: every block in the range is read" % mode, sorted(blocks) == want,
              "got %d blocks, wanted %d; first gap near %s"
              % (len(blocks), len(want),
                 next((b for a, b in zip(sorted(blocks), sorted(blocks)[1:])
                       if b - a != 1), "none")))
        check("%s: no block is read twice" % mode, len(blocks) == len(set(blocks)),
              "%d logs, %d distinct" % (len(blocks), len(set(blocks))))
        accepted = [(a, b) for a, b in seen_ranges if b - a <= 1000]
        check("%s: it retried the same offset rather than skipping ahead" % mode,
              bool(accepted) and accepted[0][0] == 100000,
              "first accepted range was %s" % (str(accepted[0]) if accepted else "none"))

    # And a refusal it must NOT absorb: a 500 is not "too much data", so swallowing it
    # would turn a broken node into an empty day -- the substitution this project keeps
    # paying for.
    def always_500(urls, method, params, timeout=30):
        raise urllib.error.HTTPError(urls[0], 500, "Internal Server Error", {}, None)

    original = backfill.rpc_any
    backfill.rpc_any = always_500
    raised = None
    try:
        backfill.logs_in_range(["http://stub"], 0, 8000, [["0xt"]], step=5000)
    except urllib.error.HTTPError as e:
        raised = e.code
    except Exception as e:                                   # noqa: BLE001
        raised = type(e).__name__
    finally:
        backfill.rpc_any = original
    check("a 500 is raised, not absorbed as an empty range", raised == 500, repr(raised))

    # And a genuine refusal at the floor must raise rather than return a partial range.
    def always_413(urls, method, params, timeout=30):
        raise urllib.error.HTTPError(urls[0], 413, "Payload Too Large", {}, None)

    backfill.rpc_any = always_413
    raised = None
    try:
        backfill.logs_in_range(["http://stub"], 0, 8000, [["0xt"]], step=5000, floor=200)
    except urllib.error.HTTPError as e:
        raised = e.code
    finally:
        backfill.rpc_any = original
    check("refusal all the way down to the floor raises", raised == 413, repr(raised))


def main():
    global _ADAPTER
    arguments = sys.argv[1:]
    if arguments not in ([], ["--offline"]):
        print("  FAIL configuration class=configuration method=none provider=none status=none")
        return 2
    offline = bool(arguments)
    print("=" * 66)
    print("Backfill decoder tests")
    print("=" * 66)
    # Discovered, not listed. This was a hand-written tuple of four function names, and on
    # 2026-09-10 a fifth test was added to the file and silently did not run -- the file
    # reported "12 passed" with eleven of its own checks never executed. That is the exact
    # incident this repo already records: four hand-maintained runners skipping tests,
    # including CI's own step list. `tests/test_decisions_enforcement.py` now fails when any
    # test file's runner cannot reach one of its own test functions.
    live_observed = live_failed = live_unobserved = 0
    previous_adapter = _ADAPTER
    try:
        _ADAPTER = None if offline else _ObservationRPC()
        for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
            if offline and name in _LIVE_TESTS:
                continue
            before = (_PASSED, len(_FAILURES), len(_UNOBSERVED))
            try:
                fn()
            except Exception:  # noqa: BLE001 -- unexpected local faults are hard failures, never outages
                check("a test completed without a local failure", False,
                      "class=local method=none provider=none status=none")
            if name in _LIVE_TESTS:
                live_failed += len(_FAILURES) - before[1]
                live_observed += _PASSED - before[0] + len(_FAILURES) - before[1]
                live_unobserved += len(_UNOBSERVED) - before[2]
    except Exception:  # noqa: BLE001 -- setup/discovery faults are also sanitized hard failures
        check("the local test harness initialized and discovered its checks", False,
              "class=local method=none provider=none status=none")
    finally:
        _ADAPTER = previous_adapter
    print("\n" + "=" * 66)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    state = "not-run" if offline else (
        "red" if _FAILURES else "blind" if not live_observed else
        "partial" if live_unobserved else "observed")
    print("OBSERVATION_SUMMARY " + json.dumps({
        "observed_checks": _PASSED + len(_FAILURES), "passed_checks": _PASSED,
        "failed_checks": len(_FAILURES), "unobserved_checks": len(_UNOBSERVED),
        "live_observed_checks": live_observed, "live_failed_checks": live_failed,
        "live_unobserved_checks": live_unobserved, "live_state": state}, sort_keys=True))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
