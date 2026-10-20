"""T-052: offline real-engine clock seams; A1 isolates only fixture directories."""

import asyncio
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "bench"), str(ROOT / "src")]
import risk
import w40_evidence as core
import w40_native as native

TOKEN = "0x" + "1" * 40
POOL = "0x" + "a" * 40
CONTEXTS = (risk._BENCH_NOW, risk._STALE_HITS, risk._FETCH_FAILURES)
UNSET = object()


class FixedClock:
    def __init__(self, instant=None):
        self.instant = instant or datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
        self.elapsed = 100.0

    def utc(self):
        return self.instant

    def mono(self):
        return self.elapsed

    def advance(self, seconds):
        self.instant += timedelta(seconds=seconds)
        self.elapsed += seconds

    async def sleep(self, seconds):
        self.advance(seconds)
        await asyncio.sleep(0)


def state():
    return (risk.cf_fetch, risk._cache_get, risk._cache_put, risk._ONCHAIN,
            dict(risk._ONCHAIN), tuple(variable.get(UNSET) for variable in CONTEXTS),
            native._ACTIVE_SCOPE)


def assert_restored(case, before):
    after = state()
    for index in (0, 1, 2, 3):
        case.assertIs(after[index], before[index])
    case.assertEqual(after[4], before[4])
    for actual, expected in zip(after[5], before[5]):
        case.assertIs(actual, expected)
    case.assertEqual(after[6], before[6])


class OfflineFixture:
    """No physical I/O; A1's exact-root substitute is not runtime eligibility proof."""

    def __init__(self, case):
        self.case = case
        self.clock = FixedClock()
        self.initial = self.clock.utc()
        self.seen = []
        self.retired = 0
        self.engine_at = None
        self.engine_pin = None

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        self.environment = dict(os.environ)
        self.old_boundary = core._private_directory
        try:
            self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
            native.external(self.root)
            self.runtime = self.root / "runtime"
            self.private = self.root / "private"
            self.store = self.root / "store"
            for target in ("socket.create_connection", "socket.socket.connect",
                           "socket.socket.connect_ex", "socket.getaddrinfo",
                           "http.client.HTTPConnection.connect",
                           "http.client.HTTPSConnection.connect", "subprocess.Popen"):
                self.stack.enter_context(patch(target, side_effect=AssertionError("physical_io_forbidden")))
            self.worker = self.stack.enter_context(patch.object(
                native, "NativeWorker", side_effect=AssertionError("native_worker_forbidden")))
            # Exercise the real guards before source, enrollment, raw or journal writes.
            # Setting refusal flags never clears a real CI flag; patch.dict restores all bytes.
            with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}):
                with self.case.assertRaisesRegex(core.EvidenceError, "^raw_directory_refused$"):
                    core._private_directory(self.private, self.runtime)
                with self.case.assertRaisesRegex(native.NativeError, "^raw_directory_refused$"):
                    native.private_paths(self.runtime, self.private, self.store)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = native.main(["collect-one", "--store", str(self.store),
                        "--sources", str(self.root / "missing-sources"), "--ordinal", "1",
                        "--runtime", str(self.runtime), "--private-dir", str(self.private),
                        "--manifest", str(self.root / "missing-manifest"), "--live"])
                self.case.assertEqual(code, 2)
                self.case.assertEqual(json.loads(output.getvalue()), {"error": "raw_directory_refused"})
                self.case.assertEqual(list(self.root.iterdir()), [])
            self.case.assertEqual(dict(os.environ), self.environment)
            self.stack.enter_context(patch.object(core, "_private_directory", self.fixture_directory))
            return self
        except BaseException:
            self.stack.close()
            raise

    def fixture_directory(self, value, safe):
        # The only mocked function is limited to this fixture's exact disjoint roots.
        if Path(value) != self.private or Path(safe) not in (self.runtime, self.store):
            raise AssertionError("unexpected_fixture_directory")
        native.private_path(value, self.root, missing=True)
        native.private_path(safe, self.root, missing=True)
        path, safe = native.external(value), native.external(safe)
        if path != self.private or safe not in (self.runtime, self.store):
            raise AssertionError("unexpected_fixture_directory")
        native.private_path(path, self.root, missing=True)
        native.private_path(safe, self.root, missing=True)
        if path == safe or path in safe.parents or safe in path.parents:
            raise AssertionError("fixture_alias_or_overlap")
        return path

    def __exit__(self, *args):
        try:
            self.worker.assert_not_called()
        finally:
            self.stack.close()
        self.case.assertIs(core._private_directory, self.old_boundary)
        self.case.assertEqual(dict(os.environ), self.environment)

    @property
    def gt(self):
        return "https://api.geckoterminal.com/api/v2/networks/base/pools/" + POOL

    @property
    def ds(self):
        return "https://api.dexscreener.com/latest/dex/tokens/" + TOKEN

    @property
    def hp(self):
        return "https://api.honeypot.is/v2/IsHoneypot?address=" + TOKEN + "&chainID=8453"

    @property
    def oracle(self):
        return "https://api.gopluslabs.io/api/v1/token_security/8453?contract_addresses=" + TOKEN

    def enroll(self):
        row = {"chain": "base", "base_token": "base_" + TOKEN, "pool_address": POOL,
               "pool_created_at": "2026-10-01T00:00:00Z", "seen_at": "2026-10-01T01:00:00Z"}
        raw = native.dumps(row) + b"\n"
        source = self.root / "source.ndjson"
        source.write_bytes(raw)
        self.sources = [{"path": str(source), "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()}]
        value = core.plan("1" * 40, self.sources)
        core.enroll(value, self.sources, boundary="2026-10-01T02:00:00Z",
                    ingested_at="2026-10-01T02:00:00Z", output=self.store)

    def response(self, request):
        url = request["url"]
        if url == self.gt:
            return 200, {"data": {"id": "base_" + POOL,
                "attributes": {"address": POOL, "reserve_in_usd": "100000"}}}
        if url == self.gt + "/ohlcv/day?limit=1000":
            return 200, {"data": {"attributes": {"ohlcv_list": [[1790899200, 1, 1, 1, 1, 2000]]}}}
        if url == self.oracle:
            return 200, {"code": 1, "result": {TOKEN: {name: "0" for name in core.FLAGS}}}
        if url == self.ds:
            self.engine_at, self.engine_pin = self.clock.utc(), risk._clock_now()
            pair = {"chainId": "base", "dexId": "uniswap", "pairAddress": POOL,
                "baseToken": {"address": TOKEN, "symbol": "Q"},
                "quoteToken": {"address": "0x" + "2" * 40, "symbol": "R"},
                "priceUsd": "1", "priceNative": "1", "liquidity": {"usd": 100000},
                "volume": {"h24": 50000}, "txns": {"h24": {"buys": 100, "sells": 50}},
                "pairCreatedAt": int((self.initial - timedelta(days=31, seconds=-5)).timestamp() * 1000)}
            return 200, {"pairs": [pair]}
        if url == "https://mainnet.base.org" and request["method"] == "POST":
            self.case.assertEqual(json.loads(request["body"]), {"jsonrpc": "2.0", "id": 1,
                "method": "eth_getCode", "params": [TOKEN, "latest"]})
            return 200, {"jsonrpc": "2.0", "id": 1, "result": "0x6000"}
        if url == self.hp:
            return 404, {}  # Observed missing sell simulation must retain unknown.
        raise AssertionError("unmatched_fixture_request")

    def transport(self, request, **_kwargs):
        fixture = self

        class Worker:
            identity = None

            async def start(self):
                fixture.seen.append(request)
                self.status, body = fixture.response(request)
                self.raw = native.dumps(body)
                return {"utc": native.iso(fixture.clock.utc()), "monotonic": fixture.clock.mono()}

            async def headers(self):
                fixture.clock.advance(.25)
                return self.status

            async def body(self):
                fixture.clock.advance(.25)
                return self.raw

            async def retire(self):
                fixture.retired += 1
                return "exited"

        return Worker()


class NativeClockAcceptance(unittest.TestCase):
    def test_native_scope_datetime_and_real_engine_age(self):
        fixed = FixedClock(datetime(2026, 10, 2, 10,
                           tzinfo=timezone(timedelta(hours=5, minutes=30))))
        for clock in (None, fixed):
            with self.subTest(default=clock is None), OfflineFixture(self) as fixture:
                async def exercise():
                    before = state()
                    lower = datetime.now(timezone.utc)
                    expected = clock.utc() if clock else lower
                    async with native.adapter_scope(fixture.runtime, fixture.private,
                            token=TOKEN, chain="base", clock=clock, transport=fixture.transport) as adapter:
                        # The real age function exposes a float pin before any type assertion.
                        self.assertEqual(risk._age_days(int((expected - timedelta(days=10)).timestamp() * 1000)), 10)
                        pin = risk._clock_now()
                        self.assertIsInstance(pin, datetime)
                        self.assertIsNotNone(pin.tzinfo)
                        if clock:
                            self.assertIs(pin, expected)
                            self.assertIs(pin.tzinfo, expected.tzinfo)
                        else:
                            self.assertIsInstance(adapter.clock, native.Clock)
                            self.assertEqual(pin.utcoffset(), timedelta(0))
                            self.assertLessEqual(lower, pin)
                            self.assertLessEqual(pin, datetime.now(timezone.utc))
                        for days, age in ((-10, 10), (1, 0), (3, None)):
                            self.assertEqual(risk._age_days(int((pin + timedelta(days=days)).timestamp() * 1000)), age)
                        self.assertEqual(risk._minutes_since_rugcheck_indexed((pin - timedelta(minutes=90)).isoformat()), 90)
                        self.assertEqual(risk._minutes_since_rugcheck_indexed((pin + timedelta(minutes=1)).isoformat()), 0)
                        self.assertIsNone(risk._minutes_since_rugcheck_indexed((pin + timedelta(minutes=6)).isoformat()))
                        self.assertEqual(adapter.deadline - adapter.start["monotonic"], native.PACKET_SECONDS)
                    assert_restored(self, before)
                asyncio.run(exercise())

    def test_native_collect_one_datetime_real_assessment(self):
        with OfflineFixture(self) as fixture:
            fixture.enroll()
            async def exercise():
                before = state()
                result = await native.collect_one(fixture.store, fixture.sources, 1,
                    runtime=fixture.runtime, private_dir=fixture.private, live=True,
                    manifest=native.code_manifest(), clock=fixture.clock, transport=fixture.transport)
                assert_restored(self, before)
                return result
            result = asyncio.run(exercise())
            packet = native.read_prepared(fixture.runtime, fixture.private)
            self.assertEqual(packet["engine"]["state"], "observed")
            raw = base64.b64decode(packet["engine"]["raw"])
            self.assertEqual(raw, (fixture.private / "engine-answer.json").read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), packet["engine"]["sha256"])
            answer = json.loads(raw)
            self.assertTrue({"address", "risk_level", "risk_score", "signals", "evidence",
                             "checked_at", "recommendation"}.issubset(answer))
            self.assertEqual(answer["address"], TOKEN)
            self.assertEqual(answer["risk_level"], "unknown")
            self.assertIsInstance(answer["signals"], list)
            self.assertEqual(answer["evidence"]["best_pair"]["pair_address"], POOL)
            self.assertEqual(answer["evidence"]["pair_age_days"], 31)
            self.assertTrue(any(gap["dimension"] == "sellability" for gap in answer["evidence"]["data_gaps"]))
            self.assertGreater((fixture.engine_at - fixture.initial).total_seconds(), 5)
            self.assertIs(fixture.engine_pin, fixture.engine_at)
            self.assertEqual(packet["engine_context_at"], native.iso(fixture.engine_at))
            self.assertEqual([request["url"] for request in fixture.seen],
                [fixture.gt, fixture.gt + "/ohlcv/day?limit=1000", fixture.oracle,
                 fixture.ds, "https://mainnet.base.org", fixture.hp])
            self.assertEqual(packet["endpoints"]["label"],
                [fixture.gt, fixture.gt + "/ohlcv/day?limit=1000", fixture.oracle])
            self.assertEqual(packet["endpoints"]["eligibility"], [fixture.gt])
            self.assertEqual(set(packet["endpoints"]["engine"]),
                             {fixture.ds, "https://mainnet.base.org", fixture.hp})
            self.assertEqual(result["stages"], dict.fromkeys(("reserve", "ohlcv", "oracle", "engine"), "observed"))
            self.assertEqual((result["reserved"], result["attempted"], result["completed"],
                result["error"], result["unknown"], result["unfinished"], fixture.retired), (6, 6, 6, 1, 1, 0, 6))
            self.assertEqual((native.BODY_CAP, native.ATTEMPT_SECONDS, native.PACKET_SECONDS),
                             (256 * 1024, 30.0, 20 * 60.0))

    def test_native_clock_context_restores_after_failure_and_cancellation(self):
        original = state()
        for mode in ("normal", "failure", "cancellation"):
            with self.subTest(mode=mode), OfflineFixture(self) as fixture:
                async def exercise():
                    outer = datetime(2024, 1, 2, tzinfo=timezone.utc)
                    tokens = [variable.set(value) for variable, value in
                              zip(CONTEXTS, (outer, ["outer-stale"], ["outer-failure"]))]
                    onchain = dict(risk._ONCHAIN)
                    risk._ONCHAIN.update(key="offline-fixture", unusable=True)
                    before = state()
                    try:
                        try:
                            async with native.adapter_scope(fixture.runtime, fixture.private,
                                    token=TOKEN, chain="base", clock=fixture.clock,
                                    transport=fixture.transport) as adapter:
                                response = await risk.cf_fetch(fixture.ds)
                                self.assertEqual(risk._age_days(int((fixture.initial - timedelta(days=10)).timestamp() * 1000)), 10)
                                self.assertIs(risk._clock_now(), fixture.initial)
                                risk._STALE_HITS.get().append(("fixture", 90))
                                risk._FETCH_FAILURES.get().append(("fixture", "unavailable"))
                                risk._ONCHAIN.update(key=None, unusable=False)
                                if mode == "failure":
                                    raise RuntimeError("fixture_failure")
                                if mode == "cancellation":
                                    asyncio.current_task().cancel()
                                    await asyncio.sleep(0)
                                await response.text()
                        finally:
                            assert_restored(self, before)
                            self.assertIs(risk._clock_now(), outer)
                            self.assertEqual(risk._age_days(int((outer - timedelta(days=10)).timestamp() * 1000)), 10)
                            self.assertIsNone(adapter.active)
                            self.assertEqual(fixture.retired, 1)
                    finally:
                        risk._ONCHAIN.clear()
                        risk._ONCHAIN.update(onchain)
                        for variable, token in zip(CONTEXTS, tokens):
                            variable.reset(token)
                if mode == "normal":
                    asyncio.run(exercise())
                elif mode == "failure":
                    with self.assertRaisesRegex(RuntimeError, "^fixture_failure$"):
                        asyncio.run(exercise())
                else:
                    with self.assertRaises(asyncio.CancelledError):
                        asyncio.run(exercise())
                assert_restored(self, original)
        now = risk._clock_now()
        self.assertIsNone(risk._BENCH_NOW.get())
        self.assertIsInstance(now, datetime)
        self.assertLess(abs((now - datetime.now(timezone.utc)).total_seconds()), 2)
        self.assertEqual(risk._age_days(int((now - timedelta(days=10)).timestamp() * 1000)), 10)


if __name__ == "__main__":
    unittest.main()
