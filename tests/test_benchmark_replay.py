"""T-011: a pinned benchmark clock, dated answers and network-free replay.

All upstreams and identities here are synthetic; all writes use temporary paths.
Run: python tests/test_benchmark_replay.py
"""

import ast
import asyncio
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.error
from collections import Counter
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "bench"))
import run_benchmark as bench  # noqa: E402
import fetcher  # noqa: E402
import risk  # noqa: E402

T = datetime(2026, 9, 21, 2, tzinfo=timezone.utc)
ADDRESS = "0x" + "a1" * 20
_PASSED = 0
_FAILURES = []


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  " + name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def require_clock():
    found = hasattr(risk, "_BENCH_NOW") and hasattr(risk, "_clock_now")
    check("AC1 pinned clock context and helper exist", found)
    return found


def wall(instant):
    class Wall(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant if tz else instant.replace(tzinfo=None)
    return Wall


def cache_path(url):
    return Path(fetcher.CACHE_DIR) / (hashlib.sha256(url.encode()).hexdigest()[:40] + ".json")


def save_cache(url, **entry):
    path = cache_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(url=url, **entry)), encoding="utf-8")


def tree_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@contextlib.contextmanager
def sandbox(tokens=None):
    saved_fetch = risk._fetch_json
    saved_log = {k: set(v) for k, v in fetcher._ACCESS_LOG.items()}
    saved_last = dict(fetcher._last_hit)
    saved_onchain = dict(risk._ONCHAIN)
    with tempfile.TemporaryDirectory(prefix="vetagent-replay-") as temp:
        temp = Path(temp)
        cache = temp / "cache"
        cache.mkdir()
        dataset = temp / "dataset.json"
        dataset.write_text(json.dumps({"tokens": tokens or []}), encoding="utf-8")
        access = temp / "access_log.json"
        access.write_text(json.dumps({"engine": [], "label": ["oracle.invalid/labels"]}), encoding="utf-8")
        with patch.object(fetcher, "CACHE_DIR", str(cache)), patch.object(fetcher, "ACCESS_LOG_PATH", str(access)), patch.object(bench, "DATASET", str(dataset)), patch.object(bench, "RESULTS_JSON", str(temp / "results.json")), patch.object(bench, "RESULTS_MD", str(temp / "results.md")):
            fetcher.reset_access_log()
            risk._ONCHAIN.update(key=None, unusable=False)
            try:
                yield temp
            finally:
                risk._fetch_json = saved_fetch
                fetcher._ACCESS_LOG.clear()
                fetcher._ACCESS_LOG.update(saved_log)
                fetcher._last_hit.clear()
                fetcher._last_hit.update(saved_last)
                risk._ONCHAIN.clear()
                risk._ONCHAIN.update(saved_onchain)


class Response:
    status = 200

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode()


def answer(data=None, status=200):
    def opener(request, **_kw):
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "synthetic", {}, None)
        return Response(data)
    return opener


@contextlib.contextmanager
def fake_upstream(opener):
    with patch("urllib.request.urlopen", side_effect=opener) as network, patch.object(fetcher, "_throttle", return_value=True), patch("time.sleep", return_value=None):
        yield network


def call_main(argv):
    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            status = bench.main(argv)
    except SystemExit as exc:
        status = exc.code
    except TypeError as exc:
        check("AC2 main accepts explicit argument lists", False, str(exc))
        return None, {}, capture.getvalue()
    return status, copy.deepcopy(getattr(bench, "LAST_RUN", {})), capture.getvalue()


def synthetic_tokens(n=3):
    return [{"address": "0x" + ("%040x" % (i + 1001)), "symbol": "SYN%d" % i,
             "chain": "ethereum", "outcome_label": "alive", "goplus_label": "safe"}
            for i in range(n)]


def synthetic_assessor(created=None, calls=None):
    async def assess(address, *_args, **_kw):
        if calls is not None:
            calls.append((address, risk._BENCH_NOW.get() if hasattr(risk, "_BENCH_NOW") else None))
        url = "https://synthetic.invalid/token/" + address
        result = await risk._fetch_json(url, mark_missing=True)
        best = {"pair_address": "synthetic-pool", "liquidity_usd": 100000}
        if created and address in created:
            stamp = created[address]
            best["pair_created_at"] = stamp
            age = risk._age_days(stamp)
        else:
            age = None
        evidence = {"best_pair": best, "data_gaps": []}
        if age is not None:
            evidence["pair_age_days"] = age
        if result is None:
            evidence["data_gaps"].append({"dimension": "sellability", "reason": "upstream request failed"})
        return {"risk_level": "unknown" if result is None else "low", "risk_score": 0,
                "confidence": "high", "signals": [], "evidence": evidence}
    return assess


def served(created):
    pair = {"chainId": "ethereum", "dexId": "uniswap", "pairAddress": "0x" + "b2" * 20,
            "baseToken": {"address": ADDRESS, "symbol": "SYN"},
            "quoteToken": {"address": "0x" + "c3" * 20, "symbol": "QUOTE"},
            "priceUsd": "1", "liquidity": {"usd": 200000}, "volume": {"h24": 50000},
            "txns": {"h24": {"buys": 100, "sells": 100}}, "pairCreatedAt": created}
    hp = {"simulationSuccess": True, "honeypotResult": {"isHoneypot": False},
          "simulationResult": {"buyTax": 0, "sellTax": 0, "transferTax": 0},
          "summary": {"risk": "low", "riskLevel": 1, "flags": []}}
    async def fetch(url, **_kw):
        if "dex/tokens" in url:
            return {"pairs": [pair]}
        if "dex/search" in url:
            return {"pairs": []}
        if "token-pairs" in url:
            return [pair]
        if "honeypot.is" in url:
            return hp
        return {"data": []}
    with patch.object(risk, "_fetch_json", fetch):
        return asyncio.run(risk.assess(ADDRESS, chain_hint="ethereum", verbose=True))


def test_ac1_pinned_helpers_and_explicit_now():
    if not require_clock():
        return
    created = int((T - timedelta(days=10, hours=1)).timestamp() * 1000)
    stamp = (T - timedelta(minutes=5)).isoformat()
    token = risk._BENCH_NOW.set(T)
    try:
        for days in (1, 41):
            with patch.object(risk, "datetime", wall(T + timedelta(days=days))):
                check("AC1(a) age ignores wall clock +%d" % days, risk._age_days(created) == 10)
                check("AC1(a) RugCheck ignores wall clock +%d" % days,
                      risk._minutes_since_rugcheck_indexed(stamp) == 5)
                check("AC1 explicit now still wins +%d" % days,
                      risk._age_days(created, now=T + timedelta(days=days)) == days + 10)
                risk._begin_request()
                check("AC1 request start preserves pin +%d" % days, risk._BENCH_NOW.get() == T)
    finally:
        risk._BENCH_NOW.reset(token)
    token = risk._BENCH_NOW.set(None)
    try:
        for days in (1, 41):
            with patch.object(risk, "datetime", wall(T + timedelta(days=days))):
                check("AC1(b) unset age follows wall +%d" % days,
                      risk._age_days(created) == days + 10)
                check("AC1(b) unset RugCheck follows wall +%d" % days,
                      risk._minutes_since_rugcheck_indexed(stamp) == days * 1440 + 5)
    finally:
        risk._BENCH_NOW.reset(token)


def test_ac1_served_path_and_no_source_setter():
    now = datetime.now(timezone.utc)
    created = int((now - timedelta(days=10, hours=1)).timestamp() * 1000)
    result = served(created)
    check("AC1(c) served pair uses current wall clock", result["evidence"].get("pair_age_days") == 10)
    check("AC1(c) served freshness is recent",
          any(s["name"] == "Recently created pair" for s in result["signals"]))
    setters = []
    for path in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "set" and isinstance(node.func.value, ast.Name) and node.func.value.id == "_BENCH_NOW":
                setters.append((path.name, node.lineno))
    check("AC1(d) no engine path sets the benchmark context", not setters, str(setters))


def test_ac2_invalid_arguments_are_status_five_before_io():
    with sandbox() as temp:
        for argv in (["--bogus"], ["--fill"], ["--replay", "--fill", str(temp / "missing")], ["--replay", "extra"]):
            with patch("builtins.open", side_effect=AssertionError("argument refusal read a file")), patch.object(risk, "assess", side_effect=AssertionError("argument refusal evaluated")), patch.object(bench, "install_engine_fetcher", side_effect=AssertionError("argument refusal installed fetcher")):
                status, _summary, _output = call_main(argv)
            check("AC2 invalid arguments return 5: %r" % argv, status == 5, str(status))


def test_ac2_summary_counts_future_pairs_and_restores_clock():
    if not require_clock():
        return
    check("AC2 branch constant is aware UTC", getattr(bench, "BENCH_CLOCK", None) == T)
    check("AC2 importing benchmark pins nothing", risk._BENCH_NOW.get() is None)
    tokens = synthetic_tokens(4)
    created = {tokens[0]["address"]: int((T + timedelta(days=3)).timestamp() * 1000),
               tokens[1]["address"]: int((T + timedelta(days=1)).timestamp() * 1000),
               tokens[2]["address"]: int((T - timedelta(days=10)).timestamp() * 1000)}
    calls = []
    observed = []
    original = synthetic_assessor(created, calls)
    async def assess(*args, **kw):
        result = await original(*args, **kw)
        observed.append(result)
        return result
    with sandbox(tokens), patch.object(risk, "assess", assess), fake_upstream(answer({"observed": True})):
        previous = T - timedelta(days=100)
        pin = risk._BENCH_NOW.set(previous)
        try:
            status, summary, output = call_main([])
            check("AC2 fetch mode exits zero", status == 0)
            check("AC2 all assessments see branch pin", len(calls) == 4 and all(p == T for _a, p in calls))
            check("AC2 caller previous context restored", risk._BENCH_NOW.get() == previous)
            check("AC2 summary exposes pinned clock", summary.get("clock") == "2026-09-21T02:00:00Z", str(summary))
            check("AC2 summary counts both future pairs", summary.get("pairs_after_clock") == 2, str(summary))
            check("AC2 summary prints clock", "2026-09-21T02:00:00Z" in output)
            check("AC2 three-day future pair has no age", "pair_age_days" not in observed[0]["evidence"])
            check("AC2 one-day future pair is zero days old", observed[1]["evidence"].get("pair_age_days") == 0)
            check("AC2 earlier pair remains ten days old", observed[2]["evidence"].get("pair_age_days") == 10)
            check("AC2 missing creation value has no age", "pair_age_days" not in observed[3]["evidence"])
        finally:
            risk._BENCH_NOW.reset(pin)


def test_ac2_context_restored_on_refusals_and_exception():
    if not require_clock():
        return
    tokens = synthetic_tokens()
    previous = T - timedelta(days=100)
    pin = risk._BENCH_NOW.set(previous)
    try:
        with sandbox(tokens) as temp, patch.object(risk, "assess", synthetic_assessor()), fake_upstream(answer({"ok": True})):
            for target, expected in (("missing", 1), ("empty", 1), ("no-labels", 3), ("overlap", 2), ("miss", 4)):
                Path(bench.DATASET).write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
                Path(fetcher.ACCESS_LOG_PATH).write_text(json.dumps({"engine": [], "label": ["oracle.invalid/labels"]}), encoding="utf-8")
                fetcher.reset_access_log()
                if target == "missing":
                    Path(bench.DATASET).unlink()
                elif target == "empty":
                    Path(bench.DATASET).write_text('{"tokens": []}', encoding="utf-8")
                elif target == "no-labels":
                    Path(fetcher.ACCESS_LOG_PATH).unlink()
                elif target == "overlap":
                    Path(fetcher.ACCESS_LOG_PATH).write_text(json.dumps({"label": [fetcher.endpoint_of("https://synthetic.invalid/token/" + tokens[0]["address"])]}), encoding="utf-8")
                if target == "miss":
                    for path in Path(fetcher.CACHE_DIR).glob("*.json"):
                        path.unlink()
                status, summary, output = call_main(["--replay"] if target == "miss" else [])
                check("AC2 refusal %s retains status %d" % (target, expected), status == expected, str(status))
                check("AC2 refusal %s restores caller context" % target, risk._BENCH_NOW.get() == previous)
                if expected in (2, 3, 4):
                    check("AC2 refusal %s still reports branch clock" % target,
                          summary.get("clock") == "2026-09-21T02:00:00Z" and "2026-09-21T02:00:00Z" in output)
            Path(bench.DATASET).write_text("not JSON", encoding="utf-8")
            try:
                bench.main([])
            except ValueError:
                check("AC2 malformed dataset exception escapes", True)
            else:
                check("AC2 malformed dataset exception escapes", False)
            check("AC2 exception restores caller context", risk._BENCH_NOW.get() == previous)
    finally:
        risk._BENCH_NOW.reset(pin)
    check("AC2 after restored context pin remains unset", risk._BENCH_NOW.get() is None)
    now = datetime.now(timezone.utc)
    result = served(int((now - timedelta(days=10, hours=1)).timestamp() * 1000))
    check("AC2 served path after normal, refusal and exception keeps wall clock",
          result["evidence"].get("pair_age_days") == 10)


def test_ac3_dated_success_and_all_final_client_statuses():
    with sandbox():
        for status in [200] + [s for s in range(400, 500) if s != 429]:
            url = "https://synthetic.invalid/status/%d" % status
            before = datetime.now(timezone.utc)
            with fake_upstream(answer({"success": True}, status)) as network:
                try:
                    got = fetcher.fetch_json(url, role="engine", dated=True, mark_missing=True)
                except TypeError as exc:
                    check("AC3 fetcher accepts dated mode", False, str(exc))
                    return
            after = datetime.now(timezone.utc)
            check("AC3 status %d uses one final attempt" % status, network.call_count == 1)
            entry = json.loads(cache_path(url).read_text(encoding="utf-8")) if cache_path(url).exists() else {}
            keys = {"url", "data", "fetched_at"} if status == 200 else {"url", "status", "fetched_at"} | ({"not_found"} if status == 404 else set())
            check("AC3 status %d writes exactly dated shape" % status, set(entry) == keys, str(entry))
            stamp = entry.get("fetched_at", "")
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else T
            check("AC3 status %d is dated at wall clock" % status,
                  stamp.endswith("Z") and before <= parsed <= after and parsed != T, stamp)
            check("AC3 status %d keeps live return shape" % status,
                  got == {"success": True} if status == 200 else (got is fetcher.NOT_FOUND if status == 404 else got is None))
            if status != 200:
                check("AC3 negative status received is kept %d" % status, entry.get("status") == status)
        for status in (200, 400, 404):
            url = "https://synthetic.invalid/status/%d" % status
            for mark in (False, True):
                for dated in (False, True):
                    with patch("urllib.request.urlopen", side_effect=AssertionError("cache read went live")), patch.object(fetcher, "_throttle", side_effect=AssertionError("cache read throttled")):
                        got = fetcher.fetch_json(url, role="engine", mark_missing=mark, dated=dated)
                    check("AC3 cached %d mark=%s dated=%s has caller-shaped answer" % (status, mark, dated),
                          got == {"success": True} if status == 200 else (got is fetcher.NOT_FOUND if status == 404 and mark else got is None))


def test_ac3_defaults_no_cache_and_transient_failures():
    with sandbox():
        for status in (200, 404, 400):
            url = "https://synthetic.invalid/default/%d" % status
            with fake_upstream(answer({"ordinary": True}, status)):
                got = fetcher.fetch_json(url, role="label")
            entry = json.loads(cache_path(url).read_text(encoding="utf-8")) if cache_path(url).exists() else None
            check("AC3 builder default %d preserves cache shape" % status,
                  entry == {"url": url, "data": {"ordinary": True}} if status == 200 else entry is None)
            check("AC3 builder default %d preserves return" % status,
                  got == {"ordinary": True} if status == 200 else got is None)
        for dated in (False, True):
            for status in (200, 404, 400):
                url = "https://synthetic.invalid/snapshot/%s/%d" % (dated, status)
                before = tree_bytes(Path(fetcher.CACHE_DIR))
                with fake_upstream(answer({"live": True}, status)):
                    try:
                        got = fetcher.fetch_json(url, role="engine", use_cache=False, write_cache=False, mark_missing=True, dated=dated)
                    except TypeError as exc:
                        check("AC3 dated live-only shape exists", False, str(exc))
                        return
                check("AC3 snapshot %d dated=%s writes nothing" % (status, dated),
                      tree_bytes(Path(fetcher.CACHE_DIR)) == before)
                check("AC3 snapshot %d dated=%s keeps answer" % (status, dated),
                      got == {"live": True} if status == 200 else (got is fetcher.NOT_FOUND if status == 404 else got is None))
        cases = [(429, answer(status=429)), (500, answer(status=500)),
                 ("timeout", lambda *_a, **_kw: (_ for _ in ()).throw(TimeoutError("synthetic"))),
                 ("connection", lambda *_a, **_kw: (_ for _ in ()).throw(urllib.error.URLError("synthetic")))]
        for label, opener in cases:
            url = "https://synthetic.invalid/transient/" + str(label)
            with fake_upstream(opener) as network:
                got = fetcher.fetch_json(url, role="engine", dated=True)
            check("AC3 transient %s retries twice" % label, network.call_count == 3)
            check("AC3 transient %s returns failure and is not persisted" % label,
                  got is None and not cache_path(url).exists())


def test_ac3_benchmark_fetch_mode_reports_entries_written():
    tokens = synthetic_tokens()
    with sandbox(tokens), patch.object(risk, "assess", synthetic_assessor()), fake_upstream(lambda request, **kw: answer({"ok": True}, 404 if tokens[1]["address"] in request.full_url else 200)(request, **kw)):
        status, summary, output = call_main([])
        check("AC3 fetch run exits zero", status == 0)
        check("AC3 fetch run counts three dated entries", summary.get("writes") == {"entries": 3, "negative": 1}, str(summary))
        check("AC3 fetch run prints entry and negative counts", "3" in output and "1" in output)
        entries = [json.loads(p.read_text(encoding="utf-8")) for p in Path(fetcher.CACHE_DIR).glob("*.json")]
        check("AC3 engine fetcher requests dated entries", len(entries) == 3 and all("fetched_at" in p for p in entries))


def test_ac4_replay_roundtrip_and_complete_miss_refusal():
    tokens = synthetic_tokens()
    with sandbox(tokens) as temp, patch.object(risk, "assess", synthetic_assessor()):
        with fake_upstream(answer({"recorded": True})):
            status, _summary, _output = call_main([])
        check("AC4 synthetic fetch fills three-token cache", status == 0 and len(list(Path(fetcher.CACHE_DIR).glob("*.json"))) == 3)
        outputs = {p: Path(p).read_bytes() if Path(p).exists() else b"missing" for p in (bench.RESULTS_JSON, bench.RESULTS_MD)}
        before = tree_bytes(Path(fetcher.CACHE_DIR))
        fetcher.reset_access_log()
        with patch.object(fetcher, "_throttle", side_effect=AssertionError("replay throttled")):
            status, summary, output = call_main(["--replay"])
        check("AC4 complete replay exits zero", status == 0)
        check("AC4 complete replay misses zero", summary.get("replay", {}).get("requests") == 0, str(summary))
        check("AC4 complete replay leaves cache byte-identical", tree_bytes(Path(fetcher.CACHE_DIR)) == before)
        check("AC4 replay outputs equal fetch outputs", all(Path(p).read_bytes() == data for p, data in outputs.items()))
        url = "https://synthetic.invalid/token/" + tokens[1]["address"]
        if cache_path(url).exists():
            cache_path(url).unlink()
        before = tree_bytes(Path(fetcher.CACHE_DIR))
        Path(bench.RESULTS_JSON).write_bytes(b"existing-json")
        Path(bench.RESULTS_MD).write_bytes(b"existing-md")
        fetcher.reset_access_log()
        with patch.object(fetcher, "_throttle", side_effect=AssertionError("replay miss throttled")):
            status, summary, output = call_main(["--replay"])
        check("AC4 incomplete replay refuses with 4", status == 4, str(status))
        misses = summary.get("replay", {})
        check("AC4 one miss reports exact request, host and URL",
              misses == {"requests": 1, "per_host": {"synthetic.invalid": 1}, "urls": [url]}, str(misses))
        check("AC4 URL lines are a fill file", [s for s in output.splitlines() if s.startswith("https://")] == [url], output)
        check("AC4 incomplete replay assesses all three tokens", summary.get("evaluated") == 3, str(summary))
        check("AC4 incomplete replay leaves both output paths untouched",
              Path(bench.RESULTS_JSON).read_bytes() == b"existing-json" and Path(bench.RESULTS_MD).read_bytes() == b"existing-md")
        check("AC4 incomplete replay leaves cache untouched", tree_bytes(Path(fetcher.CACHE_DIR)) == before)
        check("AC4 provenance records hit and miss endpoint",
              fetcher.endpoint_of(url) in fetcher.access_report()[0])


def test_ac4_fetcher_misses_are_failures_and_count_duplicates():
    with sandbox():
        url = "https://synthetic.invalid/missing"
        for mark in (False, True):
            try:
                got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=mark)
            except TypeError as exc:
                check("AC4 fetcher supports replay", False, str(exc))
                return
            check("AC4 missing mark=%s is failure, not absence" % mark, got is None)
        report = fetcher.benchmark_stats()
        check("AC4 repeated requests count twice and URL once",
              report["replay"] == {"requests": 2, "per_host": {"synthetic.invalid": 2}, "urls": [url]}, str(report))
        check("AC4 miss creates no entry", not list(Path(fetcher.CACHE_DIR).iterdir()))


def test_ac5_invalid_files_refuse_before_network_or_cache():
    with sandbox() as temp:
        bad = ["", "  \n\n", "http://synthetic.invalid/a\n", "https://synthetic.invalid/a extra\n", "https:///a\n", "https://synthetic.invalid/a\nnot-a-url\n"]
        for index, text in enumerate(bad):
            path = temp / ("bad%d.txt" % index)
            path.write_text(text, encoding="utf-8")
            before = tree_bytes(temp)
            with patch.object(risk, "assess", side_effect=AssertionError("fill evaluated token")), patch.object(fetcher, "fetch_json", side_effect=AssertionError("bad file fetched")):
                status, _summary, _output = call_main(["--fill", str(path)])
            check("AC5 bad fill file %d returns 5" % index, status == 5, str(status))
            check("AC5 bad fill file %d writes nothing" % index, before == tree_bytes(temp))
        status, _summary, _output = call_main(["--fill", str(temp / "nonexistent")])
        check("AC5 unreadable fill file returns 5", status == 5, str(status))


def test_ac5_fill_is_allowlisted_deduplicated_and_dated():
    urls = ["https://fill.invalid/" + p for p in ("success", "missing", "server", "timeout", "already")]
    with sandbox() as temp:
        save_cache(urls[4], data={"old": True})
        original = tree_bytes(Path(fetcher.CACHE_DIR))
        file = temp / "fill.txt"
        file.write_text("\n" + "\n".join(urls + [urls[0]]) + "\n\n", encoding="utf-8")
        requests = []
        def opener(request, **kw):
            requests.append(request.full_url)
            if request.full_url == urls[0]:
                return Response({"new": True})
            if request.full_url == urls[1]:
                raise urllib.error.HTTPError(request.full_url, 404, "synthetic", {}, None)
            if request.full_url == urls[2]:
                raise urllib.error.HTTPError(request.full_url, 500, "synthetic", {}, None)
            if request.full_url == urls[3]:
                raise TimeoutError("synthetic")
            raise AssertionError("fill requested unapproved URL")
        untouched = {str(p): p.read_bytes() for p in (Path(bench.DATASET), Path(fetcher.ACCESS_LOG_PATH))}
        with patch.object(risk, "assess", side_effect=AssertionError("fill evaluated token")), fake_upstream(opener):
            status, summary, output = call_main(["--fill", str(file)])
        check("AC5 partial fill exits six", status == 6, str(status))
        check("AC5 exactly one call plus two retries on transient failures",
              Counter(requests) == Counter({urls[0]: 1, urls[1]: 1, urls[2]: 3, urls[3]: 3}), str(requests))
        check("AC5 file order preserved", requests == [urls[0], urls[1], urls[2], urls[2], urls[2], urls[3], urls[3], urls[3]], str(requests))
        entries = tree_bytes(Path(fetcher.CACHE_DIR))
        new_keys = set(entries) - set(original)
        check("AC5 only two listed cache entries added",
              new_keys == {cache_path(urls[0]).name, cache_path(urls[1]).name}, str(new_keys))
        check("AC5 pre-existing entry unchanged", all(entries.get(p) == data for p, data in original.items()))
        check("AC5 only dated answers added",
              all("fetched_at" in json.loads(entries[p]) for p in new_keys))
        expected_outcomes = ["stored answer", "stored 4xx", "not stored", "not stored", "already recorded"]
        fill = summary.get("fill", {})
        check("AC5 exposes each ordered URL outcome",
              fill.get("outcomes") == [{"url": u, "outcome": o} for u, o in zip(urls, expected_outcomes)], str(fill))
        check("AC5 reports per-host outcome counts",
              fill.get("per_host") == {"fill.invalid": {"stored answer": 1, "stored 4xx": 1, "not stored": 2, "already recorded": 1}}, str(fill))
        check("AC5 prints every URL outcome", all(u in output and o in output for u, o in zip(urls, expected_outcomes)))
        check("AC5 neither output file is written", not Path(bench.RESULTS_JSON).exists() and not Path(bench.RESULTS_MD).exists())
        check("AC5 dataset and access log untouched", all(Path(p).read_bytes() == data for p, data in untouched.items()))


def test_ac5_replay_url_lines_fill_then_replay_without_misses():
    tokens = synthetic_tokens()
    with sandbox(tokens) as temp, patch.object(risk, "assess", synthetic_assessor()):
        status, _summary, output = call_main(["--replay"])
        check("AC5 initial empty-cache replay refuses", status == 4)
        lines = [s for s in output.splitlines() if s.startswith("https://")]
        file = temp / "fill.txt"
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with fake_upstream(answer({"filled": True})):
            status, _summary, _output = call_main(["--fill", str(file)])
        check("AC5 printed URL list fills successfully", status == 0 and len(lines) == 3)
        fetcher.reset_access_log()
        status, summary, _output = call_main(["--replay"])
        check("AC5 replay after fill has zero misses and exits zero",
              status == 0 and summary.get("replay", {}).get("requests") == 0, str(summary))


def test_ac6_forty_day_replay_is_identical_and_unpinned_control_moves():
    available = hasattr(risk, "_BENCH_NOW") and hasattr(risk, "_clock_now")
    check("AC6 replay clock injection exists", available)
    if not available:
        return
    created = int((T - timedelta(days=10)).timestamp() * 1000)
    controls = []
    for days in (1, 41):
        with patch.object(risk, "datetime", wall(T + timedelta(days=days))):
            result = served(created)
        controls.append((result["risk_level"], result["risk_score"]))
    check("AC6 unpinned served control differs across forty days", controls[0] != controls[1], str(controls))
    token = {"address": ADDRESS, "symbol": "SYN", "chain": "ethereum", "outcome_label": "alive", "goplus_label": "safe"}
    outputs = []
    with sandbox([token]):
        real_assess = risk.assess
        requests = []
        async def capture_assess(address, chain, **kw):
            return await real_assess(address, chain, **kw)
        pair = {"chainId": "ethereum", "dexId": "uniswap", "pairAddress": "0x" + "b2" * 20,
                "baseToken": {"address": ADDRESS, "symbol": "SYN"}, "quoteToken": {"address": "0x" + "c3" * 20, "symbol": "QUOTE"},
                "priceUsd": "1", "liquidity": {"usd": 200000}, "volume": {"h24": 50000},
                "txns": {"h24": {"buys": 100, "sells": 100}}, "pairCreatedAt": created}
        def opener(request, **_kw):
            requests.append(request.full_url)
            if "dex/tokens" in request.full_url:
                return Response({"pairs": [pair]})
            if "dex/search" in request.full_url:
                return Response({"pairs": []})
            if "token-pairs" in request.full_url:
                return Response([pair])
            if "honeypot.is" in request.full_url:
                return Response({"simulationSuccess": True, "honeypotResult": {"isHoneypot": False}, "simulationResult": {"buyTax": 0, "sellTax": 0, "transferTax": 0}, "summary": {"risk": "low", "riskLevel": 1, "flags": []}})
            return Response({"data": []})
        with patch.object(risk, "assess", capture_assess), fake_upstream(opener):
            status, _summary, _output = call_main([])
        check("AC6 complete synthetic cache established", status == 0 and bool(requests))
        for days in (1, 41):
            fetcher.reset_access_log()
            with patch.object(risk, "datetime", wall(T + timedelta(days=days))), patch.object(fetcher, "_throttle", side_effect=AssertionError("replay throttled")):
                status, _summary, _output = call_main(["--replay"])
            check("AC6 replay on wall +%d exits zero" % days, status == 0)
            outputs.append((Path(bench.RESULTS_JSON).read_bytes(), Path(bench.RESULTS_MD).read_bytes()))
        check("AC6 both output files are byte-identical forty days apart", outputs[0] == outputs[1])
    now = datetime.now(timezone.utc)
    result = served(int((now - timedelta(days=10, hours=1)).timestamp() * 1000))
    check("AC6 replay does not leave a served clock pinned", result["evidence"].get("pair_age_days") == 10)


def test_amendment_b_fill_and_replay_agree_on_cache_usability():
    invalid = [
        ("truncated", lambda url: '{"url": '),
        ("null", lambda url: "null"),
        ("array", lambda url: "[]"),
        ("string", lambda url: '"not an entry"'),
        ("number", lambda url: "42"),
        ("missing-answer", lambda url: json.dumps({"url": url})),
        ("missing-url", lambda url: json.dumps({"data": {"old": True}})),
        ("wrong-url-data", lambda url: json.dumps({"url": url + "-other", "data": {"old": True}})),
        ("wrong-url-status", lambda url: json.dumps({"url": url + "-other", "status": 404})),
        ("string-status", lambda url: json.dumps({"url": url, "status": "404"})),
        ("float-status", lambda url: json.dumps({"url": url, "status": 404.0})),
        ("boolean-status", lambda url: json.dumps({"url": url, "status": True})),
        ("rate-limit", lambda url: json.dumps({"url": url, "status": 429})),
        ("server-error", lambda url: json.dumps({"url": url, "status": 500})),
    ]
    with sandbox() as temp:
        for label, body in invalid:
            url = "https://integrity.invalid/" + label
            cache_path(url).write_text(body(url), encoding="utf-8")
            fetcher.reset_benchmark_stats()
            try:
                got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
            except Exception as exc:
                check("AC5(b) unusable %s replay does not raise" % label, False, str(exc))
                got = "raised"
            check("AC5(b) unusable %s is a replay failure" % label, got is None)
            check("AC5(b) unusable %s is counted as missed" % label,
                  fetcher.benchmark_stats()["replay"] == {"requests": 1, "per_host": {"integrity.invalid": 1}, "urls": [url]})
            file = temp / "fill.txt"
            file.write_text(url + "\n", encoding="utf-8")
            with fake_upstream(answer({"repaired": True})) as network, patch.object(bench, "fetch_json", wraps=bench.fetch_json) as fetch_call:
                status, summary, _output = call_main(["--fill", str(file)])
            check("AC5(b) unusable %s fill succeeds after repair" % label, status == 0)
            check("AC5(b) unusable %s makes one normal fetch call" % label,
                  fetch_call.call_count == 1 and fetch_call.call_args == ((url,), {"role": "engine", "retries": 2, "dated": True}))
            check("AC5(b) unusable %s makes one fake HTTP request" % label, network.call_count == 1)
            check("AC5(b) unusable %s is reported as a stored answer" % label,
                  summary.get("fill", {}).get("outcomes") == [{"url": url, "outcome": "stored answer"}])
            fetcher.reset_benchmark_stats()
            try:
                got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
            except Exception as exc:
                check("AC5(b) repaired %s replay does not raise" % label, False, str(exc))
                got = None
            check("AC5(b) repaired %s replays the observed answer" % label, got == {"repaired": True})
            check("AC5(b) repaired %s has no replay miss" % label,
                  fetcher.benchmark_stats()["replay"]["requests"] == 0)
        valid = [{"data": {"old": True}}, {"status": 400}, {"status": 404, "not_found": True}]
        for index, entry in enumerate(valid):
            url = "https://integrity.invalid/valid/%d" % index
            save_cache(url, **entry)
            original = cache_path(url).read_bytes()
            file = temp / "fill.txt"
            file.write_text(url + "\n", encoding="utf-8")
            with patch.object(bench, "fetch_json", side_effect=AssertionError("usable cache must not be fetched")):
                status, summary, _output = call_main(["--fill", str(file)])
            check("AC5(b) valid entry %d is already recorded" % index,
                  status == 0 and summary.get("fill", {}).get("outcomes") == [{"url": url, "outcome": "already recorded"}])
            check("AC5(b) valid entry %d remains byte-identical" % index, cache_path(url).read_bytes() == original)
            fetcher.reset_benchmark_stats()
            got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
            check("AC5(b) valid entry %d replays without a miss" % index,
                  fetcher.benchmark_stats()["replay"]["requests"] == 0 and
                  (got == {"old": True} if index == 0 else (got is fetcher.NOT_FOUND if index == 2 else got is None)))


def test_amendment_b_interrupted_writer_then_normal_repair_and_replay():
    url = "https://integrity.invalid/interrupted"
    with sandbox() as temp:
        file = temp / "fill.txt"
        file.write_text(url + "\n", encoding="utf-8")
        original_dump = json.dump
        def interrupted_dump(entry, stream, **kw):
            if Path(stream.name) == cache_path(url):
                stream.write('{"url": ')
                raise OSError("synthetic interrupted writer")
            return original_dump(entry, stream, **kw)
        with fake_upstream(answer({"first": True})) as network, patch("json.dump", side_effect=interrupted_dump):
            status, summary, _output = call_main(["--fill", str(file)])
        check("AC5(b) interrupted writer makes one fake request", network.call_count == 1)
        check("AC5(b) interrupted writer is not stored and exits six",
              status == 6 and summary.get("fill", {}).get("outcomes") == [{"url": url, "outcome": "not stored"}])
        check("AC5(b) interrupted writer leaves actual truncated bytes",
              cache_path(url).read_bytes() == b'{"url": ')
        fetcher.reset_benchmark_stats()
        got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
        check("AC5(b) interrupted entry remains an observed replay miss",
              got is None and fetcher.benchmark_stats()["replay"]["requests"] == 1)
        with fake_upstream(answer({"second": True})) as network, patch.object(bench, "fetch_json", wraps=bench.fetch_json) as fetch_call:
            status, summary, _output = call_main(["--fill", str(file)])
        check("AC5(b) later fill makes one normal fetch and one fake request",
              network.call_count == 1 and fetch_call.call_count == 1)
        check("AC5(b) later fill reports the repaired answer and exits zero",
              status == 0 and summary.get("fill", {}).get("outcomes") == [{"url": url, "outcome": "stored answer"}])
        fetcher.reset_benchmark_stats()
        got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
        check("AC5(b) later successful record replays without a miss",
              got == {"second": True} and fetcher.benchmark_stats()["replay"]["requests"] == 0)


def test_amendment_b_persistently_unreadable_or_unusable_cache_stays_incomplete():
    with sandbox() as temp:
        for label in ("write-interrupted", "read-unavailable"):
            url = "https://integrity.invalid/" + label
            cache_path(url).write_text("{", encoding="utf-8")
            file = temp / "fill.txt"
            file.write_text(url + "\n", encoding="utf-8")
            original_open = open
            original_dump = json.dump
            def read_failure(path, mode="r", *args, **kw):
                if str(path) == str(cache_path(url)) and "r" in mode:
                    raise PermissionError("synthetic unreadable entry")
                return original_open(path, mode, *args, **kw)
            def write_failure(entry, stream, **kw):
                if Path(stream.name) == cache_path(url):
                    stream.write("{")
                    raise OSError("synthetic interrupted writer")
                return original_dump(entry, stream, **kw)
            failure = patch("builtins.open", side_effect=read_failure) if label == "read-unavailable" else patch("json.dump", side_effect=write_failure)
            with failure, fake_upstream(answer({"attempted": True})) as network, patch.object(bench, "fetch_json", wraps=bench.fetch_json) as fetch_call:
                status, summary, _output = call_main(["--fill", str(file)])
                check("AC5(b) persistent %s attempted one normal fetch" % label,
                      fetch_call.call_count == 1 and network.call_count == 1)
                check("AC5(b) persistent %s reports not stored and exits six" % label,
                      status == 6 and summary.get("fill", {}).get("outcomes") == [{"url": url, "outcome": "not stored"}])
                fetcher.reset_benchmark_stats()
                got = fetcher.fetch_json(url, role="engine", replay=True, mark_missing=True)
                check("AC5(b) persistent %s agrees with replay miss" % label,
                      got is None and fetcher.benchmark_stats()["replay"]["requests"] == 1)


def main():
    started = time.monotonic()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print("T-011 benchmark replay acceptance (offline, synthetic)")
    with patch("urllib.request.urlopen", side_effect=AssertionError("network outside a fake")), patch("time.sleep", side_effect=AssertionError("real sleep forbidden")):
        for test in tests:
            print("\n[" + test.__name__ + "]")
            try:
                test()
            except Exception as exc:
                check(test.__name__ + ": must not raise", False, type(exc).__name__ + ": " + str(exc))
    elapsed = time.monotonic() - started
    check("AC8 acceptance runs in under ten seconds", elapsed < 10, "%.3fs" % elapsed)
    print("\n%d passed, %d failed in %.3fs" % (_PASSED, len(_FAILURES), elapsed))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
