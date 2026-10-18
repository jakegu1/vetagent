"""T-038: actual backfill CLI/acquisition classification, using bounded fake transport.

No upstream, archive, benchmark or generated document is read or written by these cases.
Run: python tests/test_backfill_observation_contract.py
"""
import ast
import contextlib
import datetime
from email.message import Message
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import urllib.response

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/test_backfill.py"
WORKFLOW = ROOT / ".github/workflows/test.yml"
OFFLINE = ("test_decode_offsets_offline", "test_pairs_of_quote_assets_are_not_launches",
           "test_a_refused_range_narrows_the_window_and_skips_no_blocks")
LIVE = ("test_decoded_pools_are_real_pools", "test_a_day_is_bracketed_by_its_own_boundaries")
FROZEN = {
    "check": "519849f67be3e43ceabded871816570ab70446e7d1204a92f59ccc938220be5f",
    "_word": "393b3bc13fcb90c989ff6f1b082f522c5a3dfef6ed93f90e73640a4390e9cb6c",
    "_topic": "e60fa9e38a74ecc66708e26625d7fe75e91f4920c33aa1d5596f93729e6ff4dc",
    "test_decode_offsets_offline": "6fb852a2148d4e39d1e603d3f037114b4ff599719e12fb5f24d3dfd82e4a14ac",
    "test_pairs_of_quote_assets_are_not_launches": "81b3be5434b8fa562720a03f1cff936e05791b0e902098a18579ed4365537fdd",
    "test_a_refused_range_narrows_the_window_and_skips_no_blocks": "716b4a1641ec7f04767a4de75fde7bc4d2e5bb0e997a9eb9b0ee8ac657a883c4",
}
SENTINEL = "T038_PRIVATE_SENTINEL"
CAP = 2 * 1024 * 1024
RECEIPTS = []


def _no_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
        raise AssertionError("T038 acceptance prohibits network operations")


sys.addaudithook(_no_network)


def _address(number):
    return "0x%040x" % number


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Stream:
    """A bounded response stream plus a socket timeout recorder; never a real socket."""
    def __init__(self, raw, node, timeout):
        self.raw_bytes, self.offset, self.node = raw, 0, node
        self.timeout = timeout
        self.raw = types.SimpleNamespace(_sock=self)

    def settimeout(self, value):
        self.timeout = value
        self.node.read_timeouts.append((self.node.clock.now, value))

    def read(self, amount=-1):
        self.node.unbounded_read |= amount is None or amount < 0
        if amount is None or amount < 0:
            amount = len(self.raw_bytes)
        self.node.read_sizes.append(amount)
        self.node.read_timeout_safe &= 0 < self.timeout <= min(15, 60 - self.node.clock.now)
        cost = 8 if self.node.mode == "deadline_read" else 0
        if cost > self.timeout:
            self.node.clock.now += self.timeout
            raise TimeoutError(SENTINEL)
        self.node.clock.now += cost
        out = self.raw_bytes[self.offset:self.offset + amount]
        self.offset += len(out)
        self.node.read_bytes += len(out)
        self.node.max_response_bytes = max(self.node.max_response_bytes, self.offset)
        return out

    def read1(self, amount=-1):
        return self.read(amount)

    def close(self):
        pass


class Node:
    """Finite fake RPC replies, preserving the actual request and engine seams."""
    def __init__(self, backfill, mode="healthy", candidates=3):
        self.backfill, self.mode, self.candidates = backfill, mode, candidates
        self.clock = Clock()
        self.attempts, self.providers, self.timeouts = 0, [], []
        self.read_sizes, self.read_timeouts = [], []
        self.read_bytes, self.max_response_bytes, self.unbounded_read, self.read_timeout_safe = 0, 0, False, True
        self.urls = backfill.CHAINS["base"]["rpc"]
        self.provider_ok, self.methods = True, []
        self.ranges, self.accepted = [], []
        self.decode_calls, self.boundary_calls = 0, 0
        day = datetime.date.today() - datetime.timedelta(days=45)
        self.start = int(datetime.datetime(day.year, day.month, day.day,
                                          tzinfo=datetime.timezone.utc).timestamp())
        self.head = 5000000
        self.boundary = self.head - 45 * 43200
        self.quote = next(q for q in backfill.CHAINS["base"]["quotes"] if q.endswith("0006"))
        self.pools = {_address(200 + i): _address(100 + i) for i in range(candidates)}

    def _result(self, method, params):
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getBlockByNumber":
            return {"timestamp": hex(self.start + (int(params[0], 16) - self.boundary) * 2)}
        if method == "eth_getLogs":
            flt = params[0]
            lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
            self.ranges.append((lo, hi))
            if self.mode in ("range413", "range429") and hi - lo > 1000:
                return None
            self.accepted.append((lo, hi))
            if len(self.accepted) != 1:
                return []
            return [{"topics": [self.backfill.V3_TOPIC, "0x" + "0" * 24 + token[2:],
                                "0x" + "0" * 24 + self.quote[2:], "0x" + "0" * 64],
                     "data": "0x" + "0" * 64 + "0" * 24 + pool[2:],
                     "blockNumber": hex(lo + i)}
                    for i, (pool, token) in enumerate(self.pools.items())]
        if method == "eth_call":
            pool, selector = params[0]["to"], params[0]["data"]
            if self.mode in ("pair_gap", "mixed_bad_gap", "thin_bad_gap"):
                gap = _address(202 if self.mode == "pair_gap" else 201)
                if pool == gap:
                    raise urllib.error.HTTPError("", 500, SENTINEL, {}, None)
            if self.mode == "call_empty" or pool not in self.pools:
                return "0x"
            if self.mode == "call_short":
                return "0x01"
            token = self.quote if selector == "0x0dfe1681" else self.pools[pool]
            if self.mode == "call_wrong" or (self.mode in ("mixed_bad_gap", "thin_bad_gap") and pool == _address(200)):
                token = _address(999)
            return "0x" + "0" * 24 + token[2:]
        raise AssertionError("unexpected fake method")

    def response(self, request):
        self.attempts += 1
        if self.attempts > 90:
            raise AssertionError("fake attempt canary")
        provider = "primary" if request.full_url == self.urls[0] else "fallback"
        self.provider_ok &= request.full_url in self.urls
        self.providers.append(provider)
        self.timeouts.append((self.clock.now, request.timeout))
        if self.mode == "deadline_open":
            self.clock.now += min(10, request.timeout)
        call = json.loads(request.data.decode())
        method, params = call["method"], call["params"]
        self.methods.append(method)
        headers = Message()
        status = 200
        if self.mode == "redirect":
            status = 302
            headers["Location"] = "https://redirect.invalid/" + SENTINEL
            raw = b""
        else:
            if self.mode.startswith("http"):
                raise urllib.error.HTTPError(request.full_url, int(self.mode[4:]), SENTINEL, {}, None)
            if self.mode == "transport":
                raise urllib.error.URLError(SENTINEL)
            if self.mode == "fallback_budget" and provider == "primary":
                raise urllib.error.HTTPError(request.full_url, 500, SENTINEL, {}, None)
            result = self._result(method, params)
            if self.mode in ("range413", "range429") and method == "eth_getLogs" and result is None:
                raise urllib.error.HTTPError(request.full_url, int(self.mode[5:]), SENTINEL, {}, None)
            payload = {"jsonrpc": "2.0", "id": call["id"], "result": result}
            if self.mode == "rpc35":
                payload = {"jsonrpc": "2.0", "id": call["id"], "error": {"code": 35, "message": SENTINEL}}
            if self.mode == "malformed_logs" and method == "eth_getLogs":
                payload["result"] = [{"topics": [False], "data": SENTINEL}]
            if self.mode == "malformed_timestamp" and method == "eth_getBlockByNumber":
                payload["result"] = {"timestamp": SENTINEL}
            if self.mode.startswith("id_"):
                payload["id"] = {"id_bool": True, "id_float": float(call["id"]),
                                 "id_string": str(call["id"]), "id_wrong": call["id"] + 1}[self.mode]
            if self.mode == "missing_id":
                del payload["id"]
            if self.mode == "wrong_version":
                payload["jsonrpc"] = "1.0"
            if self.mode == "both_keys":
                payload["error"] = {"code": 35, "message": SENTINEL}
            if self.mode == "neither_key":
                del payload["result"]
            if self.mode == "non_object":
                payload = [payload]
            if self.mode == "wrong_head" and method == "eth_blockNumber":
                payload["result"] = False
            raw = json.dumps(payload).encode()
            if self.mode == "malformed_json":
                raw = (SENTINEL + "{").encode()
            if ((self.mode in ("cap_exact", "deadline_read") and self.attempts == 1)
                    or (self.mode in ("cap_over", "cap_over_length") and method == "eth_blockNumber")):
                wanted = CAP + (1 if self.mode.startswith("cap_over") else 0)
                raw += b" " * (wanted - len(raw))
                if self.mode == "cap_over_length":
                    headers["Content-Length"] = "1"
        stream = Stream(raw, self, request.timeout)
        response = urllib.response.addinfourl(stream, headers, request.full_url, status)
        response.msg = "synthetic"
        return response

    def receipt(self):
        return {"attempts": self.attempts, "providers": self.providers, "provider_ok": self.provider_ok,
                "timeouts": self.timeouts, "read_sizes": self.read_sizes, "read_timeouts": self.read_timeouts,
                "read_bytes": self.read_bytes, "unbounded_read": self.unbounded_read,
                "max_response_bytes": self.max_response_bytes,
                "read_timeout_safe": self.read_timeout_safe, "elapsed": self.clock.now,
                "methods": self.methods, "decode_calls": self.decode_calls,
                "boundary_calls": self.boundary_calls, "ranges": self.ranges, "accepted": self.accepted}


def exercise(mode="healthy", candidates=3, args=(), canaries=False, fault=None, mutant=None):
    """Compile actual source fresh, inject only transport/faults, execute actual CLI suffix."""
    source = TARGET.read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    assert source.count(marker) == 1
    before, after = source.split(marker)
    namespace = {"__file__": str(TARGET), "__name__": "t038_actual_source"}
    exec(compile(before, str(TARGET), "exec"), namespace)
    backfill = namespace["backfill"]
    node = Node(backfill, mode, candidates)
    calls = []
    original_rpc = backfill.rpc_any
    original_decode, original_boundary = backfill._decode, backfill.block_at
    def counted_decode(*values):
        node.decode_calls += 1
        return original_decode(*values)
    def counted_boundary(*values):
        node.boundary_calls += 1
        result = original_boundary(*values)
        return result + {"before": 1, "next": -1, "midnight": -40}.get(fault, 0)
    real_build = urllib.request.build_opener
    class HTTP(urllib.request.HTTPHandler):
        def http_open(self, request):
            return node.response(request)
    class HTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request):
            return node.response(request)
    def build(*handlers):
        return real_build(*handlers, HTTP(), HTTPS())
    def legacy_open(request, timeout=30):
        return build().open(request, timeout=timeout)
    if fault in ("decoder_RuntimeError", "decoder_ValueError", "decoder_AssertionError",
                 "boundary_RuntimeError", "boundary_ValueError", "boundary_AssertionError"):
        kind, exception = fault.split("_")
        error = {"RuntimeError": RuntimeError, "ValueError": ValueError, "AssertionError": AssertionError}[exception]
        target_name = LIVE[0] if kind == "decoder" else LIVE[1]
        original_test = namespace[target_name]
        def raise_engine(*values):
            raise error(SENTINEL)
        def fault_test():
            attribute = "_decode" if kind == "decoder" else "block_at"
            with patch.object(backfill, attribute, raise_engine):
                original_test()
        namespace[target_name] = fault_test
    if canaries:
        for name in OFFLINE + LIVE:
            original_test = namespace[name]
            def called(name=name, function=original_test):
                calls.append(name)
                if name in OFFLINE:
                    return function()
            namespace[name] = called
        def future_canary():
            calls.append("test_future_offline_canary")
        namespace["test_future_offline_canary"] = future_canary
    if fault == "harness":
        def broken_canary():
            raise RuntimeError(SENTINEL)
        namespace["test_future_offline_canary"] = broken_canary
    if mutant == "v3":
        raw = (ROOT / "bench/backfill.py").read_text(encoding="utf-8")
        n = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == "_decode")
        function = ast.get_source_segment(raw, n)
        old = "data[64 + 24:128]"
        assert function.count(old) == 1
        exec(compile(function.replace(old, "data[24:64]"), "<t038-offset-mutant>", "exec"), backfill.__dict__)
    output = io.StringIO()
    exit_code, escaped = None, None
    try:
        with patch.object(sys, "argv", [str(TARGET)] + list(args)), \
             patch.object(time, "monotonic", node.clock.monotonic), \
             patch.object(time, "sleep", node.clock.sleep), \
             patch.object(urllib.request, "build_opener", build), \
             patch.object(urllib.request, "urlopen", legacy_open), \
             patch.object(backfill, "_decode", backfill._decode if mutant == "v3" else counted_decode), \
             patch.object(backfill, "block_at", counted_boundary), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            namespace["__name__"] = "__main__"
            try:
                exec(compile(marker + after, str(TARGET), "exec"), namespace)
            except SystemExit as exc:
                exit_code = exc.code
            except Exception as exc:  # noqa: BLE001 -- record an escaped local harness fault, not outage
                exit_code, escaped = 1, type(exc).__name__
    finally:
        backfill._decode, backfill.block_at = original_decode, original_boundary
    summary = None
    for line in output.getvalue().splitlines():
        if line.startswith("OBSERVATION_SUMMARY "):
            summary = json.loads(line.partition(" ")[2])
    receipt = {"mode": mode, "candidates": candidates, "exit": exit_code, "escaped": escaped,
               "summary": summary, "calls": calls, "node": node.receipt(),
               "restored": backfill.rpc_any is original_rpc,
               "private_sentinel_leaked": SENTINEL in output.getvalue(),
               "all_passed_claim": "all passed" in output.getvalue().lower(),
               "old_tally": re.findall(r"(\d+) passed, (\d+) failed", output.getvalue())}
    safe_receipt = {k: v for k, v in receipt.items() if k != "node"}
    safe_receipt["acquisition"] = {key: receipt["node"][key] for key in (
        "attempts", "provider_ok", "read_bytes", "max_response_bytes", "unbounded_read", "read_timeout_safe", "elapsed")}
    RECEIPTS.append(safe_receipt)
    return receipt


def child_exercise(args):
    script = ("import importlib.util,json; "
              "s=importlib.util.spec_from_file_location('t038_child',%r); "
              "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
              "print(json.dumps(m.exercise(args=%r,canaries=True)))") % (str(Path(__file__)), tuple(args))
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True,
                            encoding="utf-8", timeout=20)
    assert result.returncode == 0, "CLI fixture child failed before its behavioral assertions"
    return json.loads(result.stdout)


class BackfillObservationTests(unittest.TestCase):
    def outcome(self, receipt, state, failed=False, unobserved=False):
        self.assertIsNone(receipt["escaped"], "unexpected exception escaped actual main")
        self.assertEqual(receipt["exit"], 1 if failed else 0, "actual CLI exit disagrees with facts")
        self.assertIsNotNone(receipt["summary"], "actual CLI must report explicit observation counts")
        summary = receipt["summary"]
        self.assertEqual(summary["live_state"], state)
        self.assertEqual(summary["failed_checks"] > 0, failed)
        self.assertEqual(summary["unobserved_checks"] > 0, unobserved)
        self.assertEqual(summary["observed_checks"], summary["passed_checks"] + summary["failed_checks"])
        self.assertTrue(receipt["restored"], "live rpc_any seam leaked")
        self.assertFalse(receipt["private_sentinel_leaked"], "private wire/exception sentinel leaked")
        self.assertFalse(receipt["all_passed_claim"] and unobserved, "blindness reported all passed")

    def test_original_eighteen_offline_checks_are_characterized(self):
        source = TARGET.read_text(encoding="utf-8")
        actual = {n.name: hashlib.sha256(ast.get_source_segment(source, n).encode()).hexdigest()
                  for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in FROZEN}
        self.assertEqual(actual, FROZEN)
        receipt = child_exercise(())
        self.assertEqual(receipt["old_tally"], [["18", "0"]])
        self.assertEqual(receipt["exit"], 0)
        self.assertEqual(receipt["node"]["attempts"], 0)

    def test_frozen_offline_checks_and_default_cli_discovery(self):
        offline = child_exercise(("--offline",))
        self.assertEqual(offline["old_tally"], [["18", "0"]])
        self.assertEqual(set(offline["calls"]), set(OFFLINE) | {"test_future_offline_canary"})
        self.assertEqual(len(offline["calls"]), 4)
        self.assertEqual(offline["node"]["attempts"], 0)
        self.outcome(offline, "not-run")
        default = child_exercise(())
        self.assertEqual(set(default["calls"]), set(OFFLINE + LIVE) | {"test_future_offline_canary"})
        self.assertEqual(len(default["calls"]), 6)
        self.assertEqual(default["exit"], 0)
        unknown = child_exercise(("--unrecognized",))
        self.assertNotEqual(unknown["exit"], 0)
        self.assertEqual(unknown["calls"], [])

    def test_unavailable_transport_envelopes_and_strict_ids_are_gaps(self):
        modes = ("http400", "http429", "http500", "transport", "rpc35", "malformed_json",
                 "non_object", "id_bool", "id_float", "id_string", "id_wrong", "missing_id",
                 "wrong_version", "both_keys", "neither_key", "wrong_head",
                 "malformed_logs", "malformed_timestamp")
        for mode in modes:
            with self.subTest(mode=mode):
                receipt = exercise(mode)
                self.outcome(receipt, "partial" if mode in ("malformed_timestamp", "malformed_logs") else "blind", unobserved=True)
                if mode not in ("malformed_timestamp", "malformed_logs"):
                    self.assertEqual(receipt["summary"]["live_observed_checks"], 0)
                self.assertLessEqual(receipt["node"]["attempts"], 64)

    def test_round_trip_floor_and_observed_contradictions_cannot_hide(self):
        good = exercise()
        self.outcome(good, "observed")
        self.assertGreater(good["node"]["decode_calls"], 0)
        self.assertGreater(good["node"]["boundary_calls"], 0)
        for number in (0, 1, 2):
            with self.subTest(sample=number):
                receipt = exercise(candidates=number)
                self.outcome(receipt, "partial", unobserved=True)
                self.assertLess(receipt["summary"]["live_observed_checks"], good["summary"]["live_observed_checks"])
        self.outcome(exercise("pair_gap"), "partial", unobserved=True)
        for mode in ("call_empty", "call_short", "call_wrong"):
            with self.subTest(contradiction=mode):
                self.outcome(exercise(mode), "red", failed=True)
        self.outcome(exercise("mixed_bad_gap"), "red", failed=True, unobserved=True)
        self.outcome(exercise("thin_bad_gap", candidates=2), "red", failed=True, unobserved=True)
        self.outcome(exercise(mutant="v3"), "red", failed=True)

    def test_boundary_predicates_and_engine_faults_remain_hard_failures(self):
        for fault in ("before", "next", "midnight"):
            with self.subTest(boundary=fault):
                self.outcome(exercise(fault=fault), "red", failed=True)
        for kind in ("decoder", "boundary"):
            for error in ("RuntimeError", "ValueError", "AssertionError"):
                with self.subTest(local=kind + error):
                    self.outcome(exercise(fault=kind + "_" + error), "red", failed=True)
        self.outcome(exercise("http400", fault="harness"), "red", failed=True, unobserved=True)

    def test_real_opener_refuses_redirects_and_bounded_stream_reads(self):
        redirect = exercise("redirect")
        self.outcome(redirect, "blind", unobserved=True)
        self.assertTrue(redirect["node"]["provider_ok"], "redirect escaped the existing providers")
        self.assertLessEqual(redirect["node"]["attempts"], 4)
        exact = exercise("cap_exact")
        self.outcome(exact, "observed")
        self.assertFalse(exact["node"]["unbounded_read"])
        self.assertTrue(all(0 < size <= CAP + 1 for size in exact["node"]["read_sizes"]))
        self.assertEqual(exact["node"]["max_response_bytes"], CAP)
        for mode in ("cap_over", "cap_over_length"):
            oversize = exercise(mode)
            self.outcome(oversize, "blind", unobserved=True)
            self.assertFalse(oversize["node"]["unbounded_read"])
            self.assertEqual(oversize["node"]["max_response_bytes"], CAP + 1)

    def test_shared_attempt_and_deadline_budgets_and_read_timeouts(self):
        attempts = exercise("fallback_budget")
        self.outcome(attempts, "partial", unobserved=True)
        self.assertEqual(attempts["node"]["attempts"], 64)
        self.assertEqual(attempts["node"]["providers"], ["primary", "fallback"] * 32)
        for mode in ("deadline_open", "deadline_read"):
            with self.subTest(deadline=mode):
                receipt = exercise(mode)
                self.outcome(receipt, "blind", unobserved=True)
                self.assertLessEqual(receipt["node"]["elapsed"], 60)
                self.assertLessEqual(receipt["node"]["attempts"], 6)
                self.assertTrue(all(0 < timeout <= min(15, 60 - start)
                                    for start, timeout in receipt["node"]["timeouts"]))
                self.assertTrue(receipt["node"]["read_timeout_safe"])
                if mode == "deadline_read":
                    self.assertTrue(receipt["node"]["read_timeouts"], "remaining time never applied to actual stream")

    def test_http_narrowing_preserves_the_shipped_range_path(self):
        for mode in ("range413", "range429"):
            with self.subTest(mode=mode):
                receipt = exercise(mode)
                self.outcome(receipt, "observed")
                ranges, accepted = receipt["node"]["ranges"], receipt["node"]["accepted"]
                self.assertEqual(ranges[0], (4975000, 4980000))
                blocks = [b for lo, hi in accepted for b in range(lo, hi + 1)]
                self.assertEqual(blocks, list(range(4975000, 4980001)))
                self.assertEqual(accepted[0][0], ranges[0][0])

    def test_workflow_requires_the_offline_paths_and_hardens_only_live_classification(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        genuine = exercise("call_wrong")
        self.assertEqual(genuine["exit"], 1, "observed bad pairs did not fail actual CLI")
        body = text.split("  backfill-roundtrip:", 1)[1].split("\n  benchmark:", 1)[0]
        with self.subTest(enforcement="hard live job"):
            self.assertNotIn("continue-on-error:", body, "genuine CLI failure is still soft-failed")
        with self.subTest(enforcement="outer bound"):
            self.assertRegex(body, r"(?m)^    timeout-minutes: 3$")
        required = text.split("  test:", 1)[1].split("\n  build:", 1)[0]
        for command in ("python tests/test_backfill.py --offline",
                        "python tests/test_backfill_observation_contract.py"):
            with self.subTest(required=command):
                self.assertEqual(required.count("run: " + command), 1)
        self.assertEqual(body.count("run: python tests/test_backfill.py"), 1)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    for row in RECEIPTS:
        print("CASE " + json.dumps(row, sort_keys=True))
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
