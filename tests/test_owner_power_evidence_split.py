"""Recorded owner-power evidence and current RPC observation have separate contracts.

Only synthetic responses reach the live monitor in this offline acceptance suite.
Run: python tests/test_owner_power_evidence_split.py
"""

import ast
import contextlib
import copy
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/owner_powers_eth_26216600.json"
FIXTURE_SHA256 = "f7d3e06858bc7b9dafd9d2967e903ec8fde2907d4a0e5d1887391adcabe2d62c"
PROVIDERS = ("https://rpc.mevblocker.io", "https://eth.api.onfinality.io/public")
CASES = (
    ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7"),
    ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
)
# Synthetic PUSH4 dispatchers, independent of the historical recording.
CODES = {"USDT": "0x63f3bdc22850638456cb595000",
         "USDC": "0x635c60da1b00", "WETH": "0x63a9059cbb00"}
FROZEN_FUNCTIONS = {
    "check": "13591030745af358efdd9d19c1ac66024aa9639a76efc78c58b1901412710505",
    "test_selectors_are_real": "972d0f2e1c0b05fe16bba13d64baac639bd044c88c62945601855a3513112ab1",
    "test_disclosure_never_moves_the_verdict": "a13a39e6d0f8a117be33bdf140d759970a4a0b647cc8eea35931498e1073b38e",
    "test_minimal_and_slot_proxies_are_recognised": "e6d6ca4f8503079defcc61ab4abe2426b2cdc160dc70276582894c477a7e088b",
    "test_a_power_is_matched_on_what_the_contract_dispatches": "b54c7bda413da990aa9cc0e645acbf8204e3b596ae897546e3e45a7c6d527b78",
    "test_a_forwarder_with_no_dispatcher_is_never_called_clean": "c6f1420417e84e8a7d56cbc96ebdda383c5d44ac5c058c68cd48164949e2ce13",
    "test_bytecode_is_cached_as_advertised": "647e644c5d7c3afb577c6dde59de11589f72133db557a4a4f8fd71bba0cf5d5b",
    "test_selector_rejects_a_signature_it_cannot_compute": "28c7a0e9f604395161f78e08fbba667ab5c5246fae784ff9a732555851fb64b2",
    "main": "c4d27946a02ce9f0f26646f3e0a04c3f407d4645cf6e9c41168f8ef01952a646",
}


def load(name):
    spec = importlib.util.spec_from_file_location("split_" + name, ROOT / "tests" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def denied(*args, **kwargs):
    raise AssertionError("external network forbidden in acceptance")


def envelopes(calls, codes=None):
    codes = CODES if codes is None else codes
    by_address = {address: name for name, address in CASES}
    return [{"jsonrpc": "2.0", "id": call["id"],
             "result": "0x1" if call["method"] == "eth_chainId"
             else codes[by_address[call["params"][0]]]}
            for call in calls]


class Response:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class EvidenceSplit(unittest.TestCase):
    def owner(self):
        return load("test_owner_powers")

    def loader(self, owner):
        fn = getattr(owner, "_load_owner_power_fixture", None)
        self.assertTrue(callable(fn), "strict historical fixture loader is missing")
        return fn

    def monitor(self):
        monitor = load("test_upstream_contract")
        self.assertTrue(callable(getattr(monitor, "test_owner_power_rpc_contract", None)),
                        "separate discovered current RPC monitor is missing")
        return monitor

    def run_live(self, scenario, main=False, history=None):
        monitor = self.monitor()
        requests = []
        out = io.StringIO()

        def http(request, timeout):
            self.assertEqual(request.get_method(), "POST")
            self.assertIn(request.full_url, PROVIDERS)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 20)
            calls = json.loads(request.data)
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(c.get("jsonrpc") == "2.0" for c in calls))
            self.assertTrue(all(type(c.get("id")) is int for c in calls))
            self.assertEqual(len({c["id"] for c in calls}), 4)
            chain = [c for c in calls if c["method"] == "eth_chainId"]
            self.assertEqual(len(chain), 1)
            self.assertEqual(chain[0]["params"], [])
            code = [c for c in calls if c["method"] == "eth_getCode"]
            self.assertEqual([c["params"] for c in code], [[a, "latest"] for _, a in CASES])
            requests.append((request.full_url, calls))
            self.assertLessEqual(len(requests), 4)
            self.assertLessEqual(sum(u == request.full_url for u, _ in requests), 2)
            result = scenario(calls, request.full_url)
            if isinstance(result, BaseException):
                raise result
            if isinstance(result, Response):
                return result
            return Response(json.dumps(result).encode())

        with tempfile.TemporaryDirectory(prefix="owner-rpc-acceptance-") as temp:
            status_path = Path(temp) / "status.json"
            if history is not None:
                status_path.write_text(json.dumps({"history": history}), encoding="utf-8")
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(out))
                stack.enter_context(mock.patch.object(monitor, "_owner_rpc_open", http))
                stack.enter_context(mock.patch.object(socket, "create_connection", denied))
                stack.enter_context(mock.patch.object(subprocess, "run", denied))
                if main:
                    for name in list(vars(monitor)):
                        if name.startswith("test_") and name != "test_owner_power_rpc_contract":
                            stack.enter_context(mock.patch.object(monitor, name, lambda: None))
                    stack.enter_context(mock.patch.object(sys, "argv", ["monitor", "--status-json", str(status_path)]))
                    result = monitor.main()
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                else:
                    monitor.test_owner_power_rpc_contract()
                    result, status = None, None
        return {"module": monitor, "requests": requests, "stdout": out.getvalue(),
                "failures": list(monitor._FAILURES), "blind": list(monitor._UNOBSERVED),
                "passed": monitor._PASSED, "status": status, "result": result}

    def assert_safe(self, receipt):
        text = receipt["stdout"] + repr(receipt["failures"]) + repr(receipt["blind"])
        for _, address in CASES:
            self.assertNotIn(address.lower(), text.lower())
        for code in CODES.values():
            self.assertNotIn(code, text)
        self.assertNotIn("PRIVATE_UPSTREAM_DETAIL", text)

    def test_original_controls_run_without_transport(self):
        owner = self.owner()
        sys.path.insert(0, str(ROOT / "bench"))
        import backfill
        with mock.patch.object(backfill, "rpc_batch", side_effect=AssertionError("RPC denied")), \
                mock.patch.object(urllib.request, "urlopen", denied), \
                mock.patch.object(subprocess, "run", denied), contextlib.redirect_stdout(io.StringIO()) as out:
            owner.test_a_real_contract_reads_correctly()
        self.assertEqual(owner._FAILURES, [], "recorded controls still depend on live transport")
        self.assertEqual(owner._PASSED, 6)
        self.assertIn("historical", out.getvalue().lower())
        self.assertNotIn("[live]", out.getvalue())

    def test_original_control_tail_cases_and_unrelated_functions_are_frozen(self):
        source = (ROOT / "tests/test_owner_powers.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name, digest in FROZEN_FUNCTIONS.items():
            self.assertEqual(hashlib.sha256(ast.dump(functions[name], include_attributes=False).encode()).hexdigest(), digest, name)
        target = functions["test_a_real_contract_reads_correctly"]
        cases = next(n for n in target.body if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "CASES")
        self.assertEqual(hashlib.sha256(ast.get_source_segment(source, cases).encode()).hexdigest(),
                         "5c82f9fce851a79b07a70818c64c1487062a7d58b14b8d78278ced6cc98b804e")
        tail = source[source.index("    for (name, _addr, expect, is_proxy), code in zip(CASES, codes):"):]
        tail = tail[:tail.index("\n\n\ndef test_minimal")]
        self.assertEqual(hashlib.sha256(tail.encode()).hexdigest(),
                         "94ca906f1341e4f5309bb0c27ed3b0e0aa38d8e0a85bdbf91d0e80cbc69a0b95")

    def test_exact_recording_accepts_lf_and_crlf_without_refresh(self):
        owner = self.owner()
        loader = self.loader(owner)
        raw = FIXTURE.read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(lf).hexdigest(), FIXTURE_SHA256)
        self.assertEqual(owner._OWNER_POWER_FIXTURE_SHA256, FIXTURE_SHA256)
        with tempfile.TemporaryDirectory(prefix="owner-fixture-") as temp, \
                mock.patch.object(urllib.request, "urlopen", denied), mock.patch.object(subprocess, "run", denied):
            for serialized in (lf, lf.replace(b"\n", b"\r\n")):
                path = Path(temp) / "recording.json"
                path.write_bytes(serialized)
                codes = loader(path)
                self.assertEqual(codes, [r["code"] for r in json.loads(lf)["records"]])
            with self.assertRaises((OSError, ValueError)):
                loader(Path(temp) / "absent.json")
            for corrupt in (lf + b" ", lf.replace(b"\n", b"\r", 1), lf[:-1], b"{", b"null"):
                path.write_bytes(corrupt)
                with self.assertRaises(ValueError):
                    loader(path)

    def test_fixture_schema_provenance_and_each_decoded_code_are_checked(self):
        owner = self.owner()
        loader = self.loader(owner)
        original = json.loads(FIXTURE.read_bytes())
        mutations = [
            lambda d: d.update(chain_id=True), lambda d: d.update(chain_id=8453),
            lambda d: d.update(chain="base"), lambda d: d.update(source_url="https://invalid.example"),
            lambda d: d.update(captured_utc="2030-01-01T00:00:00Z"),
            lambda d: d.update(block_hash_rechecked=False), lambda d: d.update(block_selection="latest"),
            lambda d: d["block"].update(number=1), lambda d: d["block"].update(hash="0x" + "0" * 64),
            lambda d: d["block"].update(timestamp=1),
            lambda d: d["records"].reverse(), lambda d: d["records"].pop(),
            lambda d: d["records"].append(copy.deepcopy(d["records"][0])),
            lambda d: d["records"][0].update(address=CASES[1][1]),
            lambda d: d["records"][0].update(request_id=11),
            lambda d: d["records"][0].update(block_parameter="latest"),
            lambda d: d["records"][0].update(method="eth_call"),
            lambda d: d["records"][0].update(expected_powers=[]),
            lambda d: d["records"][1].update(expected_is_proxy=False),
            lambda d: d["records"][0].update(code="0x"),
            lambda d: d["records"][0].update(code="0xgg"),
            lambda d: d["records"][0].update(code="0x123"),
            lambda d: d["records"][0].update(code_sha256="0" * 64),
            lambda d: d["records"][0].update(bytecode_bytes=1),
            lambda d: d["http_receipts"].pop(),
            lambda d: d["http_receipts"][3].update(http_status="500"),
            lambda d: d["http_receipts"][3].update(endpoint="https://invalid.example"),
        ]
        with tempfile.TemporaryDirectory(prefix="owner-schema-") as temp, \
                mock.patch.object(urllib.request, "urlopen", denied), mock.patch.object(subprocess, "run", denied):
            path = Path(temp) / "fixture.json"
            for index, mutate in enumerate(mutations):
                damaged = copy.deepcopy(original)
                mutate(damaged)
                raw = (json.dumps(damaged) + "\n").encode()
                path.write_bytes(raw)
                # Bypass only the outer checksum to exercise independent schema guards.
                with self.subTest(mutation=index), mock.patch.object(owner, "_OWNER_POWER_FIXTURE_SHA256", hashlib.sha256(raw).hexdigest()):
                    with self.assertRaises(ValueError):
                        loader(path)
            raw = FIXTURE.read_bytes().replace(b'"chain_id": 1', b'"chain_id": 1, "chain_id": 1')
            path.write_bytes(raw)
            with mock.patch.object(owner, "_OWNER_POWER_FIXTURE_SHA256", hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()):
                with self.assertRaises(ValueError):
                    loader(path)

    def test_current_controls_map_reordered_ids_and_identify_provider(self):
        receipt = self.run_live(lambda calls, url: list(reversed(envelopes(calls))))
        self.assertFalse(receipt["failures"])
        self.assertFalse(receipt["blind"])
        self.assertGreaterEqual(receipt["passed"], 10)
        self.assertEqual(len(receipt["requests"]), 1)
        self.assertIn("mevblocker", receipt["stdout"].lower())
        self.assertIn("latest", receipt["stdout"].lower())
        self.assert_safe(receipt)

    def test_unobserved_response_grid_never_testifies_about_missing_contracts(self):
        def malformed(calls, kind):
            rows = envelopes(calls)
            if kind == "missing":
                rows.pop()
            elif kind == "duplicate":
                rows[-1] = copy.deepcopy(rows[-2])
            elif kind == "unmatched":
                for row in rows:
                    row["id"] += 1000
            elif kind == "boolean":
                rows[0]["id"] = True
            elif kind == "rpc error":
                rows[-1].pop("result")
                rows[-1]["error"] = {"code": -1, "message": "PRIVATE_UPSTREAM_DETAIL"}
            elif kind == "both result and error":
                rows[-1]["error"] = {"message": "PRIVATE_UPSTREAM_DETAIL"}
            elif kind == "wrong envelope":
                for row in rows:
                    row["jsonrpc"] = "1.0"
            elif kind == "missing result":
                rows[-1].pop("result")
            return rows
        scenarios = {"transport": lambda c, u: urllib.error.URLError("PRIVATE_UPSTREAM_DETAIL"),
                     "non-200": lambda c, u: Response(b"PRIVATE_UPSTREAM_DETAIL", 429),
                     "invalid JSON": lambda c, u: Response(b"PRIVATE_UPSTREAM_DETAIL"),
                     "empty JSON": lambda c, u: [], "object": lambda c, u: {},
                     "null": lambda c, u: None}
        scenarios.update({kind: (lambda c, u, k=kind: malformed(c, k)) for kind in (
            "missing", "duplicate", "unmatched", "boolean", "rpc error",
            "both result and error", "wrong envelope", "missing result")})
        for name, scenario in scenarios.items():
            with self.subTest(response=name):
                receipt = self.run_live(scenario)
                self.assertFalse(receipt["failures"])
                self.assertEqual({s for s, _ in receipt["blind"]}, {"ethereum-rpc"})
                self.assertNotIn("WETH proxy detection", receipt["stdout"])
                self.assert_safe(receipt)

    def test_matched_bad_code_is_observed_failure_and_never_a_clean_contract(self):
        for bad in (None, "", "0x", 17, True, "0x123", "0xzz", "PRIVATE_UPSTREAM_DETAIL"):
            with self.subTest(code=type(bad).__name__):
                receipt = self.run_live(lambda c, u: envelopes(c, dict(CODES, USDT=bad)))
                self.assertTrue(receipt["failures"])
                self.assertFalse(receipt["blind"])
                self.assert_safe(receipt)

    def test_wrong_chain_powers_proxy_and_weth_controls_fail(self):
        def wrong_chain(calls, url):
            rows = envelopes(calls)
            rows[0]["result"] = "0x2105"
            return rows
        for name, scenario in (
                ("chain", wrong_chain),
                ("USDT powers", lambda c, u: envelopes(c, dict(CODES, USDT=CODES["WETH"]))),
                ("USDC proxy", lambda c, u: envelopes(c, dict(CODES, USDC=CODES["WETH"]))),
                ("WETH powers", lambda c, u: envelopes(c, dict(CODES, WETH=CODES["USDT"])) )):
            with self.subTest(control=name):
                receipt = self.run_live(scenario)
                self.assertTrue(receipt["failures"])
                self.assert_safe(receipt)

    def test_fallback_does_not_erase_observed_failure_or_claim_primary_uptime(self):
        def fallback(calls, url):
            return (urllib.error.URLError("PRIVATE_UPSTREAM_DETAIL") if url == PROVIDERS[0]
                    else envelopes(calls))
        receipt = self.run_live(fallback)
        self.assertFalse(receipt["failures"])
        self.assertFalse(receipt["blind"])
        self.assertEqual([u for u, _ in receipt["requests"]], list(PROVIDERS))
        self.assertIn("onfinality", receipt["stdout"].lower())
        self.assertIn("unobserved", receipt["stdout"].lower())
        self.assertIn("production-primary", receipt["stdout"].lower())
        receipt = self.run_live(lambda c, u: envelopes(c, dict(CODES, USDT=CODES["WETH"]))
                                if u == PROVIDERS[0] else envelopes(c))
        self.assertTrue(receipt["failures"], "fallback erased an already observed power failure")
        self.assert_safe(receipt)

    def test_main_status_and_durable_observer_keep_combined_red_and_blind(self):
        def partial(calls, url):
            if url == PROVIDERS[1]:
                return urllib.error.URLError("PRIVATE_UPSTREAM_DETAIL")
            rows = envelopes(calls, dict(CODES, USDT=CODES["WETH"]))
            rows.pop()
            return rows
        receipt = self.run_live(partial, main=True)
        self.assertEqual(receipt["result"], 1)
        self.assertTrue(receipt["requests"], "normal main did not discover the RPC function")
        self.assertEqual(receipt["status"]["status"], "red")
        self.assertEqual(receipt["status"]["unobserved_sources"], ["ethereum-rpc"])
        self.assertTrue(receipt["status"]["failures"])
        self.assert_safe(receipt)
        today = datetime.datetime.now(datetime.timezone.utc).date()
        history = [{"date": (today - datetime.timedelta(days=day)).isoformat(),
                    "status": "blind", "unobserved_sources": ["ethereum-rpc"], "collapsed_paths": []}
                   for day in range(5, 0, -1)]
        blind = self.run_live(lambda c, u: urllib.error.URLError("refused"), main=True, history=history)
        self.assertEqual(blind["status"]["status"], "blind")
        self.assertEqual(len(blind["status"]["history"]), 6)
        observer = load("test_upstream_contract_is_observed")
        with tempfile.TemporaryDirectory(prefix="owner-rpc-observer-") as temp:
            path = Path(temp) / "status.json"
            path.write_text(json.dumps(blind["status"]), encoding="utf-8")
            with mock.patch.object(observer, "STATUS", str(path)), contextlib.redirect_stdout(io.StringIO()):
                observer.test_no_upstream_has_been_unobserved_for_a_week()
        self.assertTrue(any("ethereum-rpc" in name for name, _ in observer._FAILURES))

    def test_recorded_controls_detect_missing_power_proxy_and_weth_mutants(self):
        for kind in ("power", "proxy", "weth"):
            owner = self.owner()
            import backfill
            real = owner.risk._powers_from_code
            original = json.loads(FIXTURE.read_bytes())["records"]

            def mutant(code):
                info = real(code)
                if info is None:
                    return info
                if kind == "power" and code == original[0]["code"]:
                    info["powers"] = []
                elif kind == "proxy" and code == original[1]["code"]:
                    info["is_proxy"] = False
                elif kind == "weth" and code == original[2]["code"]:
                    info["powers"] = ["can blacklist addresses"]
                return info
            with mock.patch.object(owner.risk, "_powers_from_code", mutant), \
                    mock.patch.object(backfill, "rpc_batch", return_value=[r["code"] for r in original]), \
                    mock.patch.object(urllib.request, "urlopen", denied), \
                    mock.patch.object(subprocess, "run", denied), contextlib.redirect_stdout(io.StringIO()):
                owner.test_a_real_contract_reads_correctly()
            self.assertTrue(owner._FAILURES, kind + " mutant escaped the original controls")

    def test_single_offline_workflow_registration(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("run: python tests/test_owner_power_evidence_split.py"), 1)

    def test_redirects_cannot_send_an_extra_request_or_escape_the_provider(self):
        from email.message import Message
        import urllib.response
        monitor = self.monitor()
        real_build = urllib.request.build_opener
        for location in ("https://invalid.example/rpc", PROVIDERS[1]):
            wire = []

            class Wire(urllib.request.HTTPSHandler):
                def https_open(self, request):
                    wire.append(request.full_url)
                    headers = Message()
                    headers["Location"] = location
                    response = urllib.response.addinfourl(
                        io.BytesIO(b"[]"), headers, request.full_url,
                        302 if len(wire) == 1 else 200)
                    response.msg = "Found" if len(wire) == 1 else "OK"
                    return response

            def local_opener(*handlers):
                return real_build(*handlers, Wire())

            # Retain the real handler chain and redirect processing with a fake wire.
            # No global opener is installed, and both possible transports stay local.
            with self.subTest(location=location), \
                    mock.patch.object(urllib.request, "build_opener", local_opener), \
                    mock.patch.object(urllib.request, "urlopen", lambda request, timeout: local_opener().open(request, timeout=timeout)), \
                    mock.patch.object(socket, "create_connection", denied), \
                    mock.patch.object(subprocess, "run", denied):
                body, why = monitor._owner_rpc_post(PROVIDERS[0], [])
                self.assertEqual(wire, [PROVIDERS[0]], "redirect sent an extra request or escaped the provider")
                self.assertIsNone(body)
                self.assertTrue(why)


    def test_mixed_line_endings_are_neither_allowed_recording_form(self):
        owner = self.owner()
        loader = self.loader(owner)
        lf = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        mixed = (lf.replace(b"\n", b"\r\n", 1), crlf.replace(b"\r\n", b"\n", 1))
        with tempfile.TemporaryDirectory(prefix="owner-mixed-line-forms-") as temp, \
                mock.patch.object(urllib.request, "urlopen", denied), \
                mock.patch.object(subprocess, "run", denied):
            path = Path(temp) / "recording.json"
            for direction, raw in zip(("one CRLF among LF", "one LF among CRLF"), mixed):
                with self.subTest(direction=direction):
                    self.assertNotEqual(raw, lf)
                    self.assertNotEqual(raw, crlf)
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError):
                        loader(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
