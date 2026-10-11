"""fetcher.py — HTTP fetcher with a disk cache that records who fetched each URL.

Two jobs:
1. Caching — the benchmark has to be reproducible and re-runnable, and it must not
   burn through upstream free tiers.
2. **Provenance accounting** — record which endpoints the "engine" and the "labeler"
   each hit. The benchmark is only valid if those two sets are disjoint, so make that
   an assertable fact rather than a promise in a doc that will go stale.
"""

import hashlib
import http.client
import io
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
UA = "vetagent-benchmark/1.0 (+https://github.com/jakegu1/vetagent)"

# Who hit what. role is "engine" or "label".
_ACCESS_LOG = {"engine": set(), "label": set()}
_LOCK = threading.Lock()

# Benchmark-only accounting. Ordinary callers retain the existing cache policy.
_REPLAY_MISSES = []
_BENCH_WRITES = []


def cache_path(url):
    key = hashlib.sha256(url.encode()).hexdigest()[:40]
    return os.path.join(CACHE_DIR, key + ".json")


def read_cache_entry(url):
    try:
        with open(cache_path(url), encoding="utf-8") as f:
            entry = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or entry.get("url") != url:
        return None
    status = entry.get("status")
    if "data" in entry or (type(status) is int and 400 <= status < 500 and status != 429):
        return entry
    return None


def _write_cache_entry(url, entry, dated):
    try:
        with open(cache_path(url), "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
        if dated:
            with _LOCK:
                _BENCH_WRITES.append("status" in entry)
    except OSError:
        pass


def _fetched_at():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def reset_benchmark_stats():
    with _LOCK:
        _REPLAY_MISSES.clear()
        _BENCH_WRITES.clear()


def benchmark_stats():
    with _LOCK:
        misses = list(_REPLAY_MISSES)
        writes = list(_BENCH_WRITES)
    return {"replay": {"requests": len(misses),
                       "per_host": dict(sorted(Counter(urlsplit(u).netloc for u in misses).items())),
                       "urls": list(dict.fromkeys(misses))},
            "writes": {"entries": len(writes), "negative": sum(writes)}}

# Minimum gap between requests per host (seconds), set conservatively from each free tier
_RATE = {
    "api.geckoterminal.com": 2.1,   # free tier is ~30 req/min
    "api.gopluslabs.io": 2.1,       # free tier is ~30 req/min
    # 2.0s, not 0.4s. Measured 2026-09-05: of 101 unknown verdicts in a 558-token run,
    # 62 carried the gap reason "upstream request failed" -- our outage, not the token's.
    # Retrying twelve of them by hand at 2s spacing, nine answered immediately and the
    # other three were honest 404s. So the benchmark was manufacturing its own upstream
    # failures at 0.4s and then reporting them as the engine declining to judge.
    #
    # Two things were wrong with that, and the second is worse. It inflated the unknown
    # rate, which is merely embarrassing. And several of the answers it never waited for
    # were honeypotResult=true -- real detections, scored as unknown. A harness that
    # provokes refusals measures the harness.
    #
    # The cost is one slow run: successes are cached forever, so only cache misses pay.
    "api.honeypot.is": 2.0,
    "api.dexscreener.com": 0.25,    # ~300 req/min
    "api.rugcheck.xyz": 0.5,
}
_last_hit = {}
_rate_lock = threading.Lock()


# Mirrors risk.NO_DATA so the benchmark exercises the same code path as production.
NOT_FOUND = object()


def endpoint_of(url):
    """Normalize a URL into an "endpoint" id: host plus path with variable parts removed.

    Used for provenance accounting: what we care about is which API was read, not
    which token.
    """
    from urllib.parse import urlparse
    u = urlparse(url)
    parts = []
    for seg in u.path.strip("/").split("/"):
        if not seg:
            continue
        # Address, hash, and all-digit segments are the variable ones — use a placeholder
        if seg.startswith("0x") or len(seg) > 25 or seg.isdigit():
            parts.append("{id}")
        else:
            parts.append(seg)
    return "%s/%s" % (u.netloc, "/".join(parts))


def _throttle(url, deadline=None):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    gap = _RATE.get(host, 0.3)
    with _rate_lock:
        last = _last_hit.get(host, 0.0)
        wait = gap - (time.time() - last)
        if wait > 0:
            if deadline is not None and wait >= deadline - time.monotonic():
                return False
            time.sleep(wait)
        _last_hit[host] = time.time()
    return True


class _AttemptBudget:
    def __init__(self, timeout, deadline):
        self.end = time.monotonic() + timeout
        if deadline is not None:
            self.end = min(self.end, deadline)

    def remaining(self):
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("HTTP attempt deadline reached")
        return remaining


class _SnapshotResolver:
    """At most one pending DNS-only worker in this process, with no HTTP callback.

    getaddrinfo cannot be cancelled portably. A caller waits only for its budget;
    a timed-out lookup remains the sole pending worker until the OS finishes it.
    Its late result is discarded, never cached or turned into a late HTTP request.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._pending = None

    def resolve(self, host, port, budget):
        budget.remaining()
        key = (host, port)
        with self._lock:
            pending = self._pending
            if pending is None or pending["done"].is_set():
                pending = {"key": key, "done": threading.Event(),
                           "cancelled": threading.Event(), "value": None, "error": None}
                self._pending = pending

                def lookup():
                    try:
                        if pending["cancelled"].is_set() or time.monotonic() >= budget.end:
                            return
                        value = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
                        if not pending["cancelled"].is_set() and time.monotonic() < budget.end:
                            pending["value"] = value
                    except Exception:
                        if not pending["cancelled"].is_set() and time.monotonic() < budget.end:
                            pending["error"] = OSError("Snapshot DNS resolution unavailable")
                    finally:
                        pending["done"].set()

                threading.Thread(target=lookup, daemon=True, name="snapshot-dns").start()
            elif pending["key"] != key:
                raise TimeoutError("Snapshot resolver is occupied")
        if not pending["done"].wait(budget.remaining()):
            pending["cancelled"].set()
            raise TimeoutError("DNS attempt deadline reached")
        budget.remaining()
        if pending["error"] is not None:
            raise pending["error"]
        if pending["value"] is None:
            raise TimeoutError("DNS result unavailable within attempt deadline")
        return pending["value"]


_SNAPSHOT_RESOLVER = _SnapshotResolver()


def _snapshot_connection(address, budget, source_address=None):
    resolved = _SNAPSHOT_RESOLVER.resolve(*address, budget)
    error = OSError("No connection address available")
    for family, kind, protocol, _, destination in resolved:
        connection = None
        try:
            budget.remaining()
            connection = socket.socket(family, kind, protocol)
            connection.settimeout(budget.remaining())
            if source_address is not None:
                connection.bind(source_address)
            connection.connect(destination)
            budget.remaining()
            return connection
        except OSError as exc:
            error = exc
            if connection is not None:
                connection.close()
    raise error


class _DeadlineReader(io.RawIOBase):
    def __init__(self, file, connection, budget):
        self.file, self.connection, self.budget = file, connection, budget

    def readable(self):
        return True

    def readinto(self, target):
        try:
            self.connection.settimeout(self.budget.remaining())
            # read1 performs at most one raw read. Wrapping read()/readline() after
            # they return would let progressive headers and chunk framing run forever.
            data = self.file.read1(len(target))
            self.budget.remaining()
            target[:len(data)] = data
            return len(data)
        except OSError:
            # Close the socket file immediately, while letting the owning buffered
            # reader close this RawIOBase normally (avoids masking the timeout in flush).
            self.file.close()
            raise

    def close(self):
        try:
            self.file.close()
        finally:
            super().close()


class _DeadlineSocketFile:
    def __init__(self, connection, budget):
        self.connection, self.budget = connection, budget

    def makefile(self, mode):
        return io.BufferedReader(_DeadlineReader(
            self.connection.makefile(mode), self.connection, self.budget))


class _AbsoluteConnection:
    def __init__(self, *args, budget, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget = budget
        self._create_connection = lambda address, timeout, source: _snapshot_connection(
            address, budget, source)
        self.response_class = lambda connection, **kw: http.client.HTTPResponse(
            _DeadlineSocketFile(connection, budget), **kw)

    def send(self, data):
        if self.sock is None:
            self.connect()
        self.sock.settimeout(self.budget.remaining())
        super().send(data)
        self.budget.remaining()


class _AbsoluteHTTPConnection(_AbsoluteConnection, http.client.HTTPConnection):
    pass


class _AbsoluteHTTPSConnection(_AbsoluteConnection, http.client.HTTPSConnection):
    def connect(self):
        http.client.HTTPConnection.connect(self)
        # TCP/proxy setup and TLS consume the same attempt, rather than giving each
        # stage a fresh ten seconds. The stdlib TLS handshake uses this total timeout.
        self.sock.settimeout(self.budget.remaining())
        hostname = self._tunnel_host or self.host
        self.sock = self._context.wrap_socket(self.sock, server_hostname=hostname)
        self.budget.remaining()


class _AbsoluteHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, budget):
        super().__init__()
        self.budget = budget

    def http_open(self, req):
        return self.do_open(lambda host, **kw: _AbsoluteHTTPConnection(
            host, budget=self.budget, **kw), req)


class _AbsoluteHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, budget):
        super().__init__()
        self.budget = budget

    def https_open(self, req):
        return self.do_open(lambda host, **kw: _AbsoluteHTTPSConnection(
            host, budget=self.budget, **kw), req, context=self._context)


def _absolute_urlopen(req, timeout, budget):
    opener = urllib.request.build_opener(_AbsoluteHTTPHandler(budget), _AbsoluteHTTPSHandler(budget))
    return opener.open(req, timeout=timeout)


def fetch_json(url, role, retries=2, timeout=25, use_cache=True,
               mark_missing=False, write_cache=True, diagnostics=None, deadline=None,
               absolute_timeout=False, dated=False, replay=False):
    """Fetch JSON. role must be "engine" or "label", for provenance accounting.

    Returns a dict/list on success, None on a failed fetch — the same contract as
    risk._fetch_json, so the engine behaves identically when it runs the benchmark.
    Optional diagnostics contain only status, a fixed error category and attempt count.
    A monotonic deadline bounds live recovery calls, including throttle time.
    Snapshot-only absolute_timeout bounds the complete HTTP attempt and DNS wait;
    ordinary benchmark callers retain their existing urllib timeout/cache contract.
    Dated mode records fetched_at and final client errors, excluding rate limits.
    Replay reads entries only and records unobserved answers as failed fetches.
    """
    assert role in ("engine", "label"), role
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(status=None, error=None, attempts=0)
    with _LOCK:
        _ACCESS_LOG[role].add(endpoint_of(url))

    if not replay and (use_cache or write_cache):
        os.makedirs(CACHE_DIR, exist_ok=True)
    if use_cache or replay:
        blob = read_cache_entry(url)
        if blob is not None:
            if "data" in blob:
                return blob["data"]
            return NOT_FOUND if blob["status"] == 404 and mark_missing else None

    if replay:
        with _LOCK:
            _REPLAY_MISSES.append(url)
        return None

    data = None
    for attempt in range(retries + 1):
        try:
            if deadline is None:
                _throttle(url)
                attempt_timeout = timeout
            else:
                if (_throttle(url, deadline=deadline) is False
                        or deadline <= time.monotonic()):
                    if diagnostics is not None:
                        diagnostics.update(error="budget_exhausted")
                    break
                attempt_timeout = min(timeout, deadline - time.monotonic())
            if diagnostics is not None:
                diagnostics.update(status=None, error=None, attempts=attempt + 1)
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": UA})
            budget = _AttemptBudget(attempt_timeout, deadline) if absolute_timeout else None
            response = (_absolute_urlopen(req, attempt_timeout, budget) if budget is not None
                        else urllib.request.urlopen(req, timeout=attempt_timeout))
            with response as resp:
                if diagnostics is not None:
                    diagnostics["status"] = (resp.status if type(resp.status) is int
                                             and 100 <= resp.status <= 599 else None)
                if resp.status == 200:
                    body = resp.read().decode("utf-8", "replace")
                    if body:
                        data = json.loads(body)
                        if budget is not None:
                            budget.remaining()
                        break
                    if diagnostics is not None:
                        diagnostics["error"] = "empty_body"
                elif diagnostics is not None:
                    diagnostics["error"] = "http"
        except urllib.error.HTTPError as e:
            if absolute_timeout:
                e.close()
            if diagnostics is not None:
                diagnostics.update(status=e.code if type(e.code) is int
                                   and 100 <= e.code <= 599 else None, error="http")
            if e.code == 429 and attempt < retries:
                time.sleep(3.0 * (attempt + 1))
                continue
            if dated and write_cache and 400 <= e.code < 500 and e.code != 429:
                entry = {"url": url, "status": e.code, "fetched_at": _fetched_at()}
                if e.code == 404:
                    entry["not_found"] = True
                _write_cache_entry(url, entry, dated=True)
            if e.code == 404 and mark_missing:
                return NOT_FOUND   # upstream has no record; not the same as unreachable
            if 400 <= e.code < 500 and e.code != 429:
                break  # retrying a 4xx gets you nothing
        except (TimeoutError, urllib.error.URLError) as e:
            data = None
            if diagnostics is not None:
                timeout_error = isinstance(e, TimeoutError) or isinstance(
                    getattr(e, "reason", None), TimeoutError)
                exhausted = absolute_timeout and deadline is not None and time.monotonic() >= deadline
                diagnostics["error"] = ("budget_exhausted" if exhausted else
                                        "timeout" if timeout_error else "network")
        except ValueError:
            if diagnostics is not None:
                diagnostics["error"] = "invalid_json"
        except Exception:
            if diagnostics is not None:
                diagnostics["error"] = "request"
        if attempt < retries:
            time.sleep(0.8 * (2 ** attempt))

    # Ordinary callers cache only successes. Dated benchmark mode also keeps final 4xx.
    #
    # `use_cache=False` gated the READ and not the write, so a caller asking for live
    # state still deposited that response for everyone else. The snapshot's day-one
    # sellability probe does exactly that: it asks honeypot.is about a token minutes
    # after launch, and the benchmark's engine then reads the same URL with the cache
    # ON. A birth-moment answer would be served to a run measuring the engine today.
    if data is not None and write_cache:
        entry = {"url": url, "data": data}
        if dated:
            entry["fetched_at"] = _fetched_at()
        _write_cache_entry(url, entry, dated)
    return data


ACCESS_LOG_PATH = os.path.join(CACHE_DIR, "..", "access_log.json")


def note_endpoint(role, endpoint):
    """Record an endpoint a sibling process sampled from, so the guard can see it."""
    assert role in ("engine", "label"), role
    with _LOCK:
        _ACCESS_LOG[role].add(endpoint)


def persist_access_log():
    """Write this process's endpoint log to disk.

    The labeling runs in build_dataset.py and the engine runs in run_benchmark.py --
    two separate processes. The in-memory log is per-process, so the benchmark saw an
    empty label set and its disjointness assertion passed vacuously: engine n {} is
    always {}. A check that cannot fail is not a check. Persisting the label side is
    what makes the assertion real.
    """
    with _LOCK:
        blob = {k: sorted(v) for k, v in _ACCESS_LOG.items()}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ACCESS_LOG_PATH)), exist_ok=True)
        # Replaces, never merges.
        #
        # It used to union each run into whatever was already on disk, which quietly
        # turned "endpoints this run touched" into "endpoints any run has ever touched".
        # That is wrong twice over: the benchmark prints the list under the heading
        # "endpoints actually hit on this run", and the disjointness assertion tests
        # against it. When DexScreener /search was dropped as a sampling source and
        # picked up by the engine for impersonation, the stale label-side entry was still
        # there, and the benchmark refused to run -- correctly objecting to an overlap
        # that no longer existed. A guard that fires on history rather than on the
        # present teaches people to work around it.
        with open(ACCESS_LOG_PATH, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, indent=1)
    except (OSError, ValueError):
        pass


def load_persisted_access_log():
    """Merge the on-disk log into this process's view. Returns True if anything loaded."""
    try:
        with open(ACCESS_LOG_PATH, encoding="utf-8") as f:
            blob = json.load(f)
    except (OSError, ValueError):
        return False
    with _LOCK:
        for role in ("engine", "label"):
            _ACCESS_LOG[role].update(blob.get(role) or [])
    return True


def access_report():
    """Return (engine_endpoints, label_endpoints, overlap)."""
    with _LOCK:
        e = set(_ACCESS_LOG["engine"])
        l = set(_ACCESS_LOG["label"])
    return sorted(e), sorted(l), sorted(e & l)


def reset_access_log():
    with _LOCK:
        _ACCESS_LOG["engine"].clear()
        _ACCESS_LOG["label"].clear()
