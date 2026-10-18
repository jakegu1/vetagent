"""T-032: inclusive log windows preserve every block and reject invalid configuration.

All node replies are bounded fakes. No chain, archive or benchmark is read or written.
Run: python tests/test_backfill_range_contract.py
"""
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import backfill  # noqa: E402

URLS = ["http://range-fixture.invalid", "http://other-fixture.invalid"]
TOPICS = [["topic-a", "topic-b"], None, "topic-index"]
PASSED, FAILURES, EXECUTED = 0, [], []


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
        print("  PASS " + name)
    else:
        FAILURES.append((name, str(detail)))
        print("  FAIL %s: %s" % (name, detail))


def row(block):
    return {"blockNumber": hex(block), "logIndex": "0x0", "identity": "block-%d" % block}


class Node:
    """One unique log per accepted block; a canary bounds even a regressed loop."""

    def __init__(self, mode="json_32005", ceiling=None, always=False, empty=False, budget=24):
        self.mode, self.ceiling, self.always, self.empty = mode, ceiling, always, empty
        self.budget, self.requests, self.ranges, self.accepted = budget, [], [], []
        self.last_error = None

    def __call__(self, urls, method, params, timeout=30):
        if len(self.requests) >= self.budget:
            raise AssertionError("canary stopped repeated RPC after %d requests" % self.budget)
        self.requests.append((urls, method, params, timeout))
        flt = params[0]
        lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
        self.ranges.append((lo, hi))
        if self.always or (self.ceiling is not None and hi - lo > self.ceiling):
            if self.mode.startswith("http_"):
                self.last_error = urllib.error.HTTPError(
                    urls[0], int(self.mode[5:]), "synthetic refusal", {}, None)
                raise self.last_error
            return {"error": {"code": -int(self.mode[5:]), "message": "synthetic range refusal"}}
        self.accepted.append((lo, hi))
        assert hi - lo <= 32, "fake refuses to allocate an unbounded log response"
        return {"result": [] if self.empty else [row(block) for block in range(lo, hi + 1)]}


def acquire(node, lo, hi, **configuration):
    result, error = None, None
    with patch.object(backfill, "rpc_any", node):
        try:
            result = backfill.logs_in_range(URLS, lo, hi, TOPICS, **configuration)
        except Exception as exc:  # noqa: BLE001 -- capture canary and propagation evidence
            error = exc
    return result, error


def receipt(name, node, error):
    print("  RECEIPT %s: requested=%s accepted=%s error=%s" % (
        name, node.ranges, node.accepted,
        "%s: %s" % (type(error).__name__, error) if error else None))


def shape(name, node, address=None):
    expected_keys = {"fromBlock", "toBlock", "topics"}
    if address is not None:
        expected_keys.add("address")
    valid = bool(node.requests)
    for urls, method, params, timeout in node.requests:
        valid = valid and urls is URLS and method == "eth_getLogs" and timeout == 30
        valid = valid and isinstance(params, list) and len(params) == 1
        flt = params[0]
        valid = valid and set(flt) == expected_keys and flt["topics"] is TOPICS
        valid = valid and (address is None or flt["address"] is address)
        valid = valid and all(flt[key] == hex(int(flt[key], 16))
                              for key in ("fromBlock", "toBlock"))
    check(name + " preserves exact RPC/filter shape", valid, node.ranges)


def coverage(name, lo, hi, step, expected, **configuration):
    node = Node(**configuration)
    result, error = acquire(node, lo, hi, step=step, floor=0)
    receipt(name, node, error)
    check(name + " completes within the canary", error is None, repr(error))
    check(name + " returns exact ordered inclusive logs", result == [row(b) for b in range(lo, hi + 1)], result)
    blocks = [item["blockNumber"] for item in result or []]
    check(name + " never duplicates a log", len(blocks) == len(set(blocks)), blocks)
    check(name + " retains delta windows", node.accepted == expected, node.accepted)
    check(name + " never exceeds either bound",
          bool(node.ranges) and all(lo <= a <= b <= hi for a, b in node.ranges), node.ranges)
    shape(name, node)


def test_inclusive_coverage_for_singletons_and_window_partitions():
    cases = (
        ("default singleton", 10, 10, None, [(10, 10)]),
        ("explicit singleton", 10, 10, 1, [(10, 10)]),
        ("zero singleton", 10, 10, 0, [(10, 10)]),
        ("default range", 10, 14, None, [(10, 14)]),
        ("terminal singleton", 10, 12, 1, [(10, 11), (12, 12)]),
        ("exact windows", 10, 15, 2, [(10, 12), (13, 15)]),
        ("uneven windows", 10, 14, 2, [(10, 12), (13, 14)]),
        ("zero delta", 10, 12, 0, [(10, 10), (11, 11), (12, 12)]),
        ("oversized delta", 10, 12, 50, [(10, 12)]),
        ("zero origin", 0, 2, 1, [(0, 1), (2, 2)]),
        ("shifted large blocks", 26000000, 26000004, 1,
         [(26000000, 26000001), (26000002, 26000003), (26000004, 26000004)]),
    )
    for name, lo, hi, step, expected in cases:
        coverage(name, lo, hi, step, expected)


def test_inverted_ranges_remain_empty_without_rpc():
    for configuration in ({}, {"step": 1}, {"step": -1, "floor": -1},
                          {"step": "unused", "floor": None}):
        node = Node(budget=1)
        result, error = acquire(node, 11, 10, **configuration)
        check("inverted %r remains empty" % configuration, result == [] and error is None, repr(error))
        check("inverted %r never calls RPC" % configuration, not node.requests, node.ranges)


def test_refusals_narrow_at_the_same_offset_through_a_terminal_singleton():
    for mode in ("http_413", "http_429", "json_32005", "json_32602"):
        node = Node(mode=mode, ceiling=1)
        result, error = acquire(node, 10, 16, step=6, floor=0)
        receipt(mode, node, error)
        check(mode + " completes after narrowing", error is None, repr(error))
        check(mode + " preserves exact ordered coverage", result == [row(b) for b in range(10, 17)], result)
        check(mode + " retries the unread offset and reaches the terminal singleton",
              node.ranges == [(10, 16), (10, 13), (10, 11), (12, 13), (14, 15), (16, 16)], node.ranges)
        check(mode + " never repeats an accepted block",
              node.accepted == [(10, 11), (12, 13), (14, 15), (16, 16)], node.accepted)
        check(mode + " keeps all requests in bounds",
              all(10 <= a <= b <= 16 for a, b in node.ranges), node.ranges)
        shape(mode, node)


def test_narrowing_can_reach_valid_zero_delta():
    for mode in ("http_413", "http_429", "json_32005", "json_32602"):
        node = Node(mode=mode, ceiling=0)
        result, error = acquire(node, 10, 12, step=2, floor=0)
        receipt(mode + " zero delta", node, error)
        check(mode + " zero delta completes", error is None, repr(error))
        check(mode + " zero delta reads all three blocks", result == [row(b) for b in range(10, 13)], result)
        check(mode + " zero delta keeps the original delta-halving arithmetic",
              node.ranges == [(10, 12), (10, 11), (10, 10), (11, 11), (12, 12)], node.ranges)


def test_request_shape_is_preserved_for_omitted_scalar_and_list_addresses():
    for address in (None, "fixture-factory", ["fixture-factory-a", "fixture-factory-b"]):
        node = Node()
        result, error = acquire(node, 10, 13, address=address, step=1, floor=200)
        name = "address %r" % address
        check(name + " existing window behavior is unchanged", error is None and result == [row(b) for b in range(10, 14)], repr(error))
        check(name + " step one still means two blocks", node.ranges == [(10, 11), (12, 13)], node.ranges)
        shape(name, node, address)


def test_nonrange_http_errors_propagate_without_retry_or_empty_success():
    for mode in ("http_400", "http_500"):
        node = Node(mode=mode, always=True)
        result, error = acquire(node, 10, 18, step=8, floor=0)
        receipt(mode, node, error)
        check(mode + " propagates the same HTTPError", error is node.last_error and isinstance(error, urllib.error.HTTPError), repr(error))
        check(mode + " retains its status", getattr(error, "code", None) == int(mode[5:]), repr(error))
        check(mode + " never retries", node.ranges == [(10, 18)], node.ranges)
        check(mode + " cannot become empty success", result is None, result)


def test_refusal_at_the_floor_propagates_without_partial_or_empty_success():
    for mode in ("http_413", "http_429", "json_32005", "json_32602"):
        for step, floor, expected in ((8, 2, [(10, 18), (10, 14), (10, 12)]),
                                      (1, 0, [(10, 11), (10, 10)]),
                                      (0, 0, [(10, 10)])):
            node = Node(mode=mode, always=True)
            result, error = acquire(node, 10, 18, step=step, floor=floor, what="range fixture")
            name = "%s floor=%s step=%s" % (mode, floor, step)
            receipt(name, node, error)
            check(name + " refuses at the existing floor", node.ranges == expected, node.ranges)
            check(name + " never becomes successful empty history", result is None and error is not None, result)
            if mode.startswith("http_"):
                check(name + " preserves HTTP propagation", error is node.last_error and isinstance(error, urllib.error.HTTPError), repr(error))
            else:
                payload = {"code": -int(mode[5:]), "message": "synthetic range refusal"}
                message = "%s refused a %d-block range of range fixture: %s" % (URLS[0], floor, payload)
                check(name + " preserves the JSON refusal diagnostic", type(error) is RuntimeError and str(error) == message, repr(error))


def test_successful_empty_observations_still_cover_the_requested_range():
    for lo, hi, step, expected in ((10, 15, 1, [(10, 11), (12, 13), (14, 15)]),
                                   (10, 12, 1, [(10, 11), (12, 12)]),
                                   (10, 10, None, [(10, 10)])):
        node = Node(empty=True)
        result, error = acquire(node, lo, hi, step=step)
        name = "empty [%d,%d]" % (lo, hi)
        receipt(name, node, error)
        check(name + " remains a successful empty result", result == [] and error is None, repr(error))
        check(name + " was observed across every requested block", node.accepted == expected, node.accepted)


def test_negative_configuration_is_rejected_before_rpc():
    # On the parent, step -1 repeats (10, 9); floor -1 repeats refused (10, 10).
    # The eight-call canary proves those loops without ever allowing the test to hang.
    for parameter, configuration, refusing in (
            ("step", {"step": -1, "floor": 1}, False),
            ("floor", {"step": 1, "floor": -1}, True)):
        node = Node(always=refusing, empty=True, budget=8)
        result, error = acquire(node, 10, 12, **configuration)
        receipt("negative " + parameter, node, error)
        check("negative " + parameter + " raises ValueError", type(error) is ValueError, repr(error))
        check("negative " + parameter + " names the invalid parameter", isinstance(error, ValueError) and parameter in str(error), repr(error))
        check("negative " + parameter + " fails before RPC", not node.requests and result is None, node.ranges)


def test_noninteger_configuration_is_rejected_before_rpc_including_singletons():
    invalid = (-2, -0.5, 0.0, 1.0, "1", True, False, [], {}, float("inf"), float("nan"))
    for parameter in ("step", "floor"):
        for value in invalid + ((None,) if parameter == "floor" else ()):
            for lo, hi in ((10, 12), (10, 10)):
                configuration = {"step": 1, "floor": 0, parameter: value}
                node = Node(empty=True, budget=8)
                result, error = acquire(node, lo, hi, **configuration)
                name = "%s=%r [%d,%d]" % (parameter, value, lo, hi)
                check(name + " raises ValueError", type(error) is ValueError, repr(error))
                check(name + " names the invalid parameter", isinstance(error, ValueError) and parameter in str(error), repr(error))
                check(name + " is rejected before RPC", not node.requests and result is None, node.ranges)


def main():
    for name, fn in sorted((name, fn) for name, fn in globals().items() if name.startswith("test_")):
        EXECUTED.append(name)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 -- unexpected failures cannot hide later functions
            check(name + " completes", False, "%s: %s" % (type(exc).__name__, exc))
    print("Executed: " + ", ".join(EXECUTED))
    print("%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
