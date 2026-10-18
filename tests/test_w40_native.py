"""Bounded, offline native acquisition acceptance; direct execution runs every case."""

import asyncio
import base64
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "bench"), str(ROOT / "src")]


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class Clock:
    def __init__(self, instant="2026-10-02T00:00:00Z"):
        self.instant = datetime.fromisoformat(instant.replace("Z", "+00:00"))
        self.elapsed = 100.0

    def utc(self):
        return self.instant

    def mono(self):
        return self.elapsed

    async def sleep(self, seconds):
        self.advance(seconds)
        await asyncio.sleep(0)

    def advance(self, seconds):
        self.elapsed += seconds
        self.instant += timedelta(seconds=seconds)


class Fixture:
    token = "0x" + "1" * 40
    pool = "0x" + "a" * 40

    def __enter__(self):
        self.environment = patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""})
        self.environment.__enter__()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        if any((p / ".git").exists() for p in (self.root,) + tuple(self.root.parents)):
            raise AssertionError("fixture_requires_external_temp")
        self.native = importlib.import_module("w40_native")
        self.core = importlib.import_module("w40_evidence")
        self.clock = Clock()
        self.store = self.root / "store"
        self.runtime = self.root / "runtime"
        self.private = self.root / "private"
        row = {"chain": "base", "base_token": "base_" + self.token,
               "pool_address": self.pool, "pool_created_at": "2026-10-01T00:00:00Z",
               "seen_at": "2026-10-01T01:00:00Z"}
        source = _json(row) + b"\n"
        path = self.root / "source.ndjson"
        path.write_bytes(source)
        self.sources = [{"path": str(path), "bytes": len(source),
                         "sha256": hashlib.sha256(source).hexdigest()}]
        self.plan = self.core.plan("1" * 40, self.sources)
        self.core.enroll(self.plan, self.sources, boundary="2026-10-01T02:00:00Z",
                         ingested_at="2026-10-01T02:00:00Z", output=self.store)
        self.seen = []
        self.reserve = 5000
        self.wrong_pool = False
        return self

    def __exit__(self, *args):
        try:
            self.temp.cleanup()
        finally:
            self.environment.__exit__(*args)

    @property
    def gt(self):
        return "https://api.geckoterminal.com/api/v2/networks/base/pools/" + self.pool

    @property
    def ds(self):
        return "https://api.dexscreener.com/latest/dex/tokens/" + self.token

    def body(self, request):
        self.seen.append(request)
        url = request["url"]
        if url == self.gt:
            pool = "0x" + "b" * 40 if self.wrong_pool else self.pool
            return {"data": {"id": "base_" + pool,
                             "attributes": {"address": pool, "reserve_in_usd": str(self.reserve)}}}
        if "/ohlcv/day?limit=1000" in url:
            return {"data": {"attributes": {"ohlcv_list": [[1790899200, 1, 1, 1, 1, 2000]]}}}
        if "token_security" in url:
            fields = {k: "0" for k in self.core.FLAGS}
            fields.update(is_honeypot="1", is_open_source="1", holder_count="600",
                          buy_tax="0", sell_tax="0", owner_address="", is_in_cex={"listed": "0"})
            return {"code": 1, "result": {self.token: fields}}
        return {"pairs": [], "jsonrpc": "2.0", "id": 1, "result": "0x6000"}

    def transport(self, request, **_kwargs):
        fixture = self

        class Worker:
            identity = None

            async def start(self):
                self.raw = _json(fixture.body(request))
                self.invocation = {"utc": fixture.native.iso(fixture.clock.utc()),
                                   "monotonic": fixture.clock.mono()}
                return self.invocation

            async def headers(self):
                fixture.clock.advance(0.01)
                return 200

            async def body(self):
                fixture.clock.advance(0.01)
                return self.raw

            async def retire(self):
                return "exited"

        return Worker()

    async def engine(self, address, chain_hint=None, verbose=False):
        risk = importlib.import_module("risk")
        if (address, chain_hint, verbose) != (self.token, "base", True):
            raise AssertionError("wrong_engine_call")
        body = await risk._fetch_json(self.ds)
        code, why = await risk._eth_get_code("https://mainnet.base.org", address)
        if body is None or code != "0x6000" or why is not None:
            raise AssertionError("broken_engine_seam")
        return {"address": address, "risk_level": "unknown", "signals": [],
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"best_pair": {"chain": "base", "pair_address": self.pool}}}

    def collect(self, **changes):
        kwargs = dict(runtime=self.runtime, private_dir=self.private, live=True,
                      manifest=self.native.code_manifest(), clock=self.clock,
                      transport=self.transport, engine=self.engine)
        kwargs.update(changes)
        return asyncio.run(self.native.collect_one(self.store, self.sources, 1, **kwargs))

    def packet(self):
        return self.native.read_prepared(self.runtime, self.private)

    def recover(self):
        return self.native.recover(self.store, self.sources, self.runtime,
                                   private_dir=self.private, now=self.native.iso(self.clock.utc()))


@contextlib.contextmanager
def server(body=b"{}", mode="normal", status=200):
    calls = []
    entered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.answer()

        def do_POST(self):
            self.answer()

        def answer(self):
            request = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            calls.append((self.command, self.path, dict(self.headers), request))
            entered.set()
            if mode == "headers":
                time.sleep(3)
            try:
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if mode == "body":
                    self.wfile.write(body[:1])
                    self.wfile.flush()
                    time.sleep(3)
                    self.wfile.write(body[1:])
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_port, calls, entered
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def run_cli(*arguments, env=None):
    return subprocess.run([sys.executable, "-B", str(ROOT / "bench/w40_native.py"),
                           *map(str, arguments)], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=25)


class NativeAcceptance(unittest.TestCase):
    def test_w40_native_default_binding_and_birth_due_are_offline(self):
        native = importlib.import_module("w40_native")
        with Fixture() as f, patch("subprocess.Popen", side_effect=AssertionError("spawn")), patch("socket.socket", side_effect=AssertionError("network")):
            self.assertEqual(native.main([]), 0)
            self.assertEqual(native.main(["--help"]), 0)
            view = native.plan(f.store, f.sources, 1, now="2026-10-01T23:59:59Z")
            self.assertEqual(view["state"], "not_due")
            self.assertEqual(view["target_at"], "2026-10-02T00:00:00Z")
            self.assertEqual(native.plan(f.store, f.sources, 1, now="2026-10-02T00:00:02Z")["lateness_seconds"], 2)
            with self.assertRaisesRegex(native.NativeError, "^live_required$"):
                f.collect(live=False)
            f.clock = Clock("2026-10-01T23:59:59Z")
            with self.assertRaisesRegex(native.NativeError, "^not_due$"):
                f.collect()
            self.assertFalse(f.runtime.exists())
            changed = dict(native.code_manifest(), engine_sha256="0" * 64)
            with self.assertRaisesRegex(native.NativeError, "^source_drift$"):
                f.collect(manifest=changed)
            f.clock = Clock()
            for ordinal in (0, True, 2):
                with self.assertRaises(native.NativeError):
                    native.plan(f.store, f.sources, ordinal, now=native.iso(f.clock.utc()))
            source = Path(f.sources[0]["path"])
            source.write_bytes(b"X" + source.read_bytes()[1:])
            with self.assertRaisesRegex(native.NativeError, "^source_hash_mismatch$"):
                native.plan(f.store, f.sources, 1, now=native.iso(f.clock.utc()))

    def test_w40_native_real_get_rpc_and_frozen_engine_context(self):
        native = importlib.import_module("w40_native")
        risk = importlib.import_module("risk")
        with Fixture() as f, server(_json({"pairs": [], "result": "0x6000"})) as (port, calls, _):
            original = {k: getattr(risk, k) for k in ("cf_fetch", "_cache_get", "_cache_put", "_fetch_json", "_eth_get_code", "assess", "_ONCHAIN")}
            onchain = dict(risk._ONCHAIN)
            tokens = [risk._BENCH_NOW.set(77), risk._STALE_HITS.set(["prior"]), risk._FETCH_FAILURES.set(["prior"])]
            before = (ROOT / "src/risk.py").read_bytes()
            async def exercise():
                async with native.adapter_scope(f.runtime, f.private, route=("127.0.0.1", port), token=f.token, chain="base") as adapter:
                    self.assertEqual(risk._ONCHAIN, {"key": None, "unusable": False})
                    self.assertIs(risk._ONCHAIN, original["_ONCHAIN"])
                    self.assertIs(risk._fetch_json, original["_fetch_json"])
                    self.assertIs(risk._eth_get_code, original["_eth_get_code"])
                    self.assertIs(risk.assess, original["assess"])
                    self.assertEqual(await risk._fetch_json(f.ds), {"pairs": [], "result": "0x6000"})
                    self.assertEqual(await risk._eth_get_code("https://mainnet.base.org", f.token), ("0x6000", None))
                    self.assertEqual(await risk._fetch_json(f.ds), {"pairs": [], "result": "0x6000"})
                    self.assertEqual(len(adapter.attempts), 2)
                self.assertEqual(risk._BENCH_NOW.get(), 77)
                self.assertEqual(risk._STALE_HITS.get(), ["prior"])
                self.assertEqual(risk._FETCH_FAILURES.get(), ["prior"])
                try:
                    async with native.adapter_scope(f.root / "other", f.root / "other-private", route=("127.0.0.1", port), token=f.token, chain="base"):
                        raise ValueError()
                except ValueError:
                    pass
            try:
                asyncio.run(exercise())
                self.assertEqual(len(calls), 2)
                self.assertEqual([c[0] for c in calls], ["GET", "POST"])
                self.assertEqual(calls[0][2]["Accept"], "application/json")
                self.assertEqual(json.loads(calls[1][3]), {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [f.token, "latest"]})
                for key, value in original.items():
                    self.assertIs(getattr(risk, key), value)
                self.assertEqual(risk._ONCHAIN, onchain)
                self.assertEqual((ROOT / "src/risk.py").read_bytes(), before)
            finally:
                for variable, token in zip((risk._BENCH_NOW, risk._STALE_HITS, risk._FETCH_FAILURES), tokens):
                    variable.reset(token)

    def test_w40_native_paired_sources_raw_times_and_independence(self):
        native = importlib.import_module("w40_native")
        with Fixture() as f:
            result = f.collect()
            packet = f.packet()
            self.assertEqual(result["state"], "prepared")
            self.assertEqual(len(f.seen), 5)
            self.assertEqual(packet["endpoints"]["label"][0], f.gt)
            self.assertEqual(packet["endpoints"]["eligibility"], [f.gt])
            self.assertIn("https://mainnet.base.org", packet["endpoints"]["engine"])
            self.assertTrue(all("before_timestamp" not in r["url"] for r in f.seen))
            for stage in ("reserve", "ohlcv", "oracle", "engine"):
                field = packet[stage]
                raw = base64.b64decode(field["raw"])
                self.assertEqual(field["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertLessEqual(field["request_at"], field["response_at"])
                self.assertEqual(field["state"], "observed")
            receipt = f.recover()
            self.assertEqual(receipt["state"], "imported")
            row = f.core.report(f.store, now=native.iso(f.clock.utc()))["rows"][0]
            self.assertEqual(row["receipt"]["engine"]["verdict"], "unknown")
            self.assertEqual(row["receipt"]["independence"]["state"], "independence_observed")
            self.assertIsNone(row["receipt"]["timing"]["tolerance"])
            with self.assertRaisesRegex(native.NativeError, "^existing_receipt$"):
                f.recover()
        for wrong, reserve in ((True, 999999), (False, 4999)):
            with Fixture() as f:
                f.wrong_pool, f.reserve = wrong, reserve
                f.collect()
                packet = f.packet()
                self.assertEqual(len(f.seen), 1)
                self.assertEqual(packet["oracle"]["state"], "not_asked")
                self.assertEqual(packet["engine"]["state"], "not_asked")
                self.assertEqual(packet["engine"]["reason"], "reserve_unobserved" if wrong else "reserve_below_floor")
        with Fixture() as f:
            async def overlap(address, chain_hint=None, verbose=False):
                risk = importlib.import_module("risk")
                await risk._fetch_json(f.gt)
                return await f.engine(address, chain_hint=chain_hint, verbose=verbose)
            f.collect(engine=overlap)
            f.recover()
            row = f.core.report(f.store, now=native.iso(f.clock.utc()))["rows"][0]
            self.assertEqual(row["receipt"]["independence"]["state"], "independence_failed")

    def test_w40_native_caps_pacing_deadline_and_cancellation(self):
        native = importlib.import_module("w40_native")
        risk = importlib.import_module("risk")
        with Fixture() as f:
            async def exercise():
                async with native.adapter_scope(f.runtime, f.private, clock=f.clock, transport=f.transport, token=f.token, chain="base") as adapter:
                    for _ in range(16):
                        response = await adapter.fetch(f.ds, headers={"Accept": "application/json"})
                        await response.text()
                    with self.assertRaisesRegex(native.NativeError, "^attempt_cap$"):
                        await adapter.fetch(f.ds)
                    starts = [a["invocation"]["monotonic"] for a in adapter.attempts]
                    self.assertTrue(all(b - a >= .25 - 1e-8 for a, b in zip(starts, starts[1:])))
                    self.assertEqual(len(list((f.private / "attempts").glob("*/body.bin"))), 16)
            asyncio.run(exercise())
            self.assertEqual(len(f.seen), 16)
        for mode in ("headers", "body"):
            with Fixture() as f, server(b"{" + b" " * 30 + b"}", mode=mode) as (port, calls, entered):
                original = risk.cf_fetch
                async def cancel():
                    async with native.adapter_scope(f.runtime, f.private, route=("127.0.0.1", port), token=f.token, chain="base") as adapter:
                        async def request():
                            response = await adapter.fetch(f.ds)
                            await response.text()
                        task = asyncio.create_task(request())
                        for _ in range(200):
                            if entered.is_set():
                                break
                            await asyncio.sleep(.01)
                        self.assertTrue(entered.is_set())
                        if mode == "body":
                            for _ in range(200):
                                if any(e["kind"] == "headers" for e in adapter.journal.events):
                                    break
                                await asyncio.sleep(.01)
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                        self.assertTrue(all(a["retirement"] == "exited" for a in adapter.attempts))
                        self.assertTrue(all(not native.identity_alive(a["identity"]) for a in adapter.attempts))
                        if mode == "body":
                            self.assertEqual(adapter.attempts[0]["status"], 200)
                started = time.monotonic()
                asyncio.run(cancel())
                self.assertLess(time.monotonic() - started, 2.5)
                self.assertEqual(len(calls), 1)
                self.assertIs(risk.cf_fetch, original)
        with Fixture() as f, server(b"{}", status=404) as (port, calls, _):
            async def discard():
                async with native.adapter_scope(f.runtime, f.private, route=("127.0.0.1", port), token=f.token, chain="base") as adapter:
                    self.assertIs(await risk._fetch_json(f.ds, mark_missing=True), risk.NO_DATA)
                self.assertEqual(adapter.attempts[0]["retirement"], "exited")
            asyncio.run(discard())
            self.assertEqual(len(calls), 1)
        for delay, expected in ((31, "permit_expired"), (86400, "permit_expired")):
            with Fixture() as f:
                class Policy:
                    def before_attempt(self, proposed):
                        f.clock.advance(delay)
                        return proposed
                    def observe(self, event):
                        return None
                f.collect(policy=Policy())
                self.assertEqual(len(f.seen), 0)
                self.assertEqual(f.packet()["reserve"]["reason"], expected)
        with Fixture() as f:
            class Refuse:
                def before_attempt(self, proposed):
                    return None
                def observe(self, event):
                    raise AssertionError("unreachable")
            f.collect(policy=Refuse())
            self.assertEqual(len(f.seen), 0)
        with Fixture() as f:
            class Broken:
                def before_attempt(self, proposed):
                    return proposed
                def observe(self, event):
                    raise ValueError()
            f.collect(policy=Broken())
            self.assertEqual(len(f.seen), 1)
            self.assertEqual(native.report(f.runtime)["state"], "start_uncertain")

    def test_w40_native_private_boundary_and_safe_failures(self):
        native = importlib.import_module("w40_native")
        with Fixture() as f:
            for directory in (ROOT / "private-native", f.store / "private", f.runtime / "private"):
                with self.assertRaisesRegex(native.NativeError, "^raw_directory_refused$"):
                    f.collect(private_dir=directory)
            with patch.dict(os.environ, {"CI": "true"}):
                with self.assertRaisesRegex(native.NativeError, "^raw_directory_refused$"):
                    f.collect()
            self.assertFalse(f.runtime.exists())
            forbidden = ["https://api.gopluslabs.io/api/v1/token_security/8453?contract_addresses=" + f.token,
                         "https://api.geckoterminal.com/api/v2/networks/base/pools/" + f.pool + "/ohlcv/day?limit=1000",
                         "https://user@api.dexscreener.com/latest/dex/tokens/" + f.token,
                         "http://api.dexscreener.com/latest/dex/tokens/" + f.token,
                         "https://api.dexscreener.com:444/latest/dex/tokens/" + f.token,
                         "https://api.coingecko.com/api/v3/onchain/networks/base/tokens/" + f.token + "/pools"]
            for url in forbidden:
                with self.assertRaisesRegex(native.NativeError, "^request_refused$"):
                    native.validate_request(url, role="engine", token=f.token, chain="base")
            for payload in ({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [f.token, "latest"]},
                            {"jsonrpc": "2.0", "id": 2, "method": "eth_getCode", "params": [f.token, "latest"]}):
                with self.assertRaisesRegex(native.NativeError, "^request_refused$"):
                    native.validate_request("https://mainnet.base.org", role="engine", token=f.token,
                                            chain="base", method="POST", body=json.dumps(payload),
                                            headers={"content-type": "application/json"})
            sentinel = hashlib.sha256(os.urandom(40)).hexdigest() + " private text"
            async def hostile(*_args, **_kwargs):
                return {"address": f.token, "risk_level": "unknown", "signals": [sentinel],
                        "evidence": {"best_pair": {"chain": "base", "pair_address": f.pool}}}
            f.collect(engine=hostile)
            safe = b"".join(p.read_bytes() for p in f.runtime.rglob("*") if p.is_file())
            self.assertNotIn(sentinel.encode(), safe)
            self.assertNotIn(f.token.encode(), safe)
            self.assertNotIn(str(f.root).encode(), safe)
            self.assertNotIn(b"https://", safe)
            self.assertLessEqual(len(_json(native.report(f.runtime))), 1024 * 1024)
            private = b"".join(p.read_bytes() for p in f.private.rglob("*") if p.is_file())
            self.assertIn(sentinel.encode(), private)
        for status, size in ((403, 2), (429, 2), (200, 256 * 1024 + 1)):
            with Fixture() as f, server(b" " * size, status=status) as (port, calls, _):
                async def exercise():
                    async with native.adapter_scope(f.runtime, f.private, route=("127.0.0.1", port), token=f.token, chain="base") as adapter:
                        try:
                            response = await adapter.fetch(f.ds)
                            await response.text()
                        except native.NativeError:
                            pass
                    self.assertEqual(adapter.attempts[0]["status"], status)
                    self.assertEqual(adapter.attempts[0]["state"], "http_refusal" if status == 403 else "http_429" if status == 429 else "invalid_body")
                asyncio.run(exercise())
                self.assertEqual(len(calls), 1)

    def test_w40_native_partial_acquisition_recovers_without_reask(self):
        native = importlib.import_module("w40_native")
        for checkpoint in ("before_ack", "native_entry"):
            with Fixture() as f, server(b"{}", mode="headers") as (port, calls, entered):
                config = {"store": str(f.store), "sources": f.sources,
                          "runtime": str(f.runtime), "private": str(f.private),
                          "port": port, "checkpoint": checkpoint,
                          "marker": str(f.root / "marker")}
                config_path = f.root / "config.json"
                config_path.write_bytes(_json(config))
                process = subprocess.Popen([sys.executable, "-B", str(Path(__file__)), "--fixture-parent", str(config_path)],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
                try:
                    limit = time.monotonic() + 10
                    while time.monotonic() < limit and not Path(config["marker"]).exists():
                        if process.poll() is not None:
                            break
                        time.sleep(.01)
                    self.assertTrue(Path(config["marker"]).exists())
                    identities = list(f.private.glob("attempts/*/identity.json"))
                    self.assertEqual(len(identities), 1)
                    identity = json.loads(identities[0].read_bytes())
                    self.assertTrue(native.identity_alive(identity))
                    process.kill()
                    process.wait(5)
                    limit = time.monotonic() + 5
                    while native.identity_alive(identity) and time.monotonic() < limit:
                        time.sleep(.01)
                    self.assertFalse(native.identity_alive(identity))
                    self.assertEqual(len(calls), 0 if checkpoint == "before_ack" else 1)
                    before = {p: p.read_bytes() for p in f.runtime.rglob("*.json")}
                    sources_path = f.root / "sources.json"
                    sources_path.write_bytes(_json(f.sources))
                    recovered = run_cli("recover", "--store", f.store, "--sources", sources_path,
                                        "--runtime", f.runtime, "--private-dir", f.private)
                    self.assertEqual(recovered.returncode, 0, recovered.stdout.decode())
                    self.assertEqual(json.loads(recovered.stdout)["state"], "imported")
                    self.assertEqual(len(calls), 0 if checkpoint == "before_ack" else 1)
                    self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))
                    again = run_cli("recover", "--store", f.store, "--sources", sources_path,
                                    "--runtime", f.runtime, "--private-dir", f.private)
                    self.assertNotEqual(again.returncode, 0)
                    self.assertEqual(len(calls), 0 if checkpoint == "before_ack" else 1)
                    with self.assertRaises(native.NativeError):
                        f.collect(runtime=f.root / "another", private_dir=f.root / "another-private")
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(5)
        with Fixture() as f:
            f.collect()
            original = native.Journal.append
            def fail_result(journal, kind, **fields):
                if kind == "import_result":
                    raise native.NativeError("persistence_failed")
                return original(journal, kind, **fields)
            with patch.object(native.Journal, "append", fail_result):
                self.assertEqual(f.recover()["state"], "imported")
            self.assertEqual(len(f.seen), 5)
            with self.assertRaisesRegex(native.NativeError, "^existing_receipt$"):
                f.recover()

    def test_w40_native_cli_and_existing_contract(self):
        native = importlib.import_module("w40_native")
        for arguments in ((), ("--help",), ("plan", "--help"), ("collect-one", "--help"), ("report", "--help"), ("recover", "--help")):
            result = run_cli(*arguments)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
        with Fixture() as f:
            sources = f.root / "sources.json"
            sources.write_bytes(_json(f.sources))
            manifest = f.root / "manifest.json"
            manifest.write_bytes(_json(native.code_manifest()))
            env = dict(os.environ, CI="true")
            result = run_cli("collect-one", "--live", "--store", f.store, "--sources", sources,
                             "--ordinal", "1", "--runtime", f.runtime, "--private-dir", f.private,
                             "--manifest", manifest, env=env)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout), {"error": "raw_directory_refused"})
            self.assertEqual(result.stderr, b"")
            self.assertFalse(f.runtime.exists())
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertIn("run: python tests/test_w40_native.py", workflow)
        self.assertNotIn("run_benchmark", (ROOT / "bench/w40_native.py").read_text())
        for relative, expected in native.FROZEN.items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest(), expected)


def fixture_parent(path):
    config = json.loads(Path(path).read_bytes())
    native = importlib.import_module("w40_native")
    async def checkpoint(name, _worker):
        if name == config["checkpoint"]:
            Path(config["marker"]).write_bytes(b"1")
            while True:
                await asyncio.sleep(.05)
    asyncio.run(native.collect_one(config["store"], config["sources"], 1,
        runtime=config["runtime"], private_dir=config["private"], live=True,
        manifest=native.code_manifest(), route=("127.0.0.1", config["port"]), hooks=checkpoint))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture-parent":
        fixture_parent(sys.argv[2])
    else:
        unittest.main()
