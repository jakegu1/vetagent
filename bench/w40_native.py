"""One bounded native paired observation; default, plan and recovery are offline.

Raw configuration and HTTP material belong to an explicitly external private directory.
The separate safe acquisition journal contains only fixed states, clocks and hashes.
This module installs no recurring work and makes no study or capacity decision.
"""

import argparse
import asyncio
import base64
import contextlib
import copy
import ctypes
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import w40_evidence as core

BODY_CAP = 256 * 1024
PACKET_CAP = 2 * 1024 * 1024
ROW_CAP = 64 * 1024
REPORT_CAP = 1024 * 1024
ATTEMPT_SECONDS = 30.0
PACKET_SECONDS = 20 * 60.0
PRIVATE_ALLOWANCE = 2 * BODY_CAP + 1 + ROW_CAP
_ACTIVE_SCOPE = False
FROZEN = {
    "bench/goplus_quota_probe.py": "3ec1e7688240fbd705b386ee7680758e6606bb9354938e994927a440e6e4b8f4",
    "bench/w40_evidence.py": "2e312e319229402088f6f1aaf15e53460d41a56468d6dd7d249c4123734e140d",
    "src/risk.py": "67b52bd3f7610aa98d6ed5f94457e875d16b489f633be54d170453e313dd8d2d",
    "bench/labels.py": "ebbb4585c9cd829dcd1fbd374a8147918fcc742e525909a326a357f9246ae75c",
    "docs/BACKLOG.md": "0f0febb99e8cb2a7c0b14fba1affcf689b7ba40fc18af641e6478f1d267b3e1a",
    "tests/test_dataset_replayable.py": "db43e79361584716a6f48bd40cd1225ffc2d6c344391cedcb2d5e4fa9e44e1ab",
}
HOST_CODES = {"api.geckoterminal.com": "gt", "api.gopluslabs.io": "gp",
              "api.dexscreener.com": "ds", "api.honeypot.is": "hp",
              "rpc.mevblocker.io": "rpc_eth", "mainnet.base.org": "rpc_base",
              "bsc-dataseed.bnbchain.org": "rpc_bsc"}
GAPS = {"gt": 12.1, "gp": 2.1, "ds": .25, "hp": 2.0,
        "rpc_eth": 1.0, "rpc_base": 1.0, "rpc_bsc": 1.0}
KINDS = {"claim", "attempt_intent", "native_invocation", "headers", "attempt_end",
         "child_retired", "packet_prepared", "import_result"}
FIXED = {"prepared", "imported", "not_started", "not_due", "due", "observed",
         "not_asked", "not_invoked", "uncertain", "exited", "start_uncertain",
         "interrupted_intent", "transport_error", "timeout", "invalid_body",
         "http_429", "http_refusal", "http_failure", "reserve", "ohlcv", "oracle",
         "engine", "reserve_unobserved", "reserve_below_floor", "interrupted",
         "permit_expired", "policy_refused", "policy_failure", "attempt_cap",
         "packet_deadline", "clock_failure", "request_refused", "cleanup_uncertain",
         "persistence_failed", "source_drift", "acquisition_stopped", "missing_raw",
         "engine_error", "invalid_evidence", "standalone", "native", *KINDS,
         *HOST_CODES.values()}


class NativeError(Exception):
    """Only a fixed diagnostic leaves the native boundary."""


def fail(code):
    raise NativeError(code)


def dumps(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        fail("invalid_body")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, cap):
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(cap + 1)
        if len(data) > cap:
            fail("input_limit")
        return data
    except OSError:
        fail("input_unavailable")


def parse(raw, cap=REPORT_CAP):
    try:
        return core._json(raw, cap)
    except core.EvidenceError:
        fail("invalid_body")


def write_new(path, raw):
    try:
        with Path(path).open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        fail("persistence_failed")


def replace_private(path, value):
    """Only worker progress is mutable; committed bodies and safe events are not."""
    temporary = Path(str(path) + ".pending")
    try:
        with temporary.open("wb") as handle:
            handle.write(dumps(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        fail("persistence_failed")


def allocate(path, size):
    try:
        with Path(path).open("xb") as handle:
            block = b"\0" * min(size, ROW_CAP)
            remaining = size
            while remaining:
                count = min(remaining, len(block))
                handle.write(block[:count])
                remaining -= count
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        fail("persistence_failed")


def iso(value):
    try:
        if not isinstance(value, datetime) or value.tzinfo is None:
            fail("clock_failure")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError):
        fail("clock_failure")


class Clock:
    def utc(self):
        return datetime.now(timezone.utc)

    def mono(self):
        return time.monotonic()

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


def code_manifest():
    """Check canonical frozen source and bind the actual checkout bytes as well."""
    actual = {}
    for number, (relative, expected) in enumerate(FROZEN.items()):
        raw = read(ROOT / relative, 2 * REPORT_CAP)
        if sha(raw.replace(b"\r\n", b"\n")) != expected:
            fail("source_drift")
        actual["source_%d_sha256" % number] = sha(raw)
    actual.update(core._bindings())
    actual["native_sha256"] = sha(read(Path(__file__), REPORT_CAP))
    return actual


def engine_bindings(risk):
    """A matching source file does not excuse replaced runtime engine functions."""
    path = ROOT / "src/risk.py"
    if Path(risk.__file__).resolve() != path.resolve():
        fail("source_drift")
    defaults = {"_fetch_json": (2, 8, False, None), "_eth_get_code": None, "assess": (None, False)}
    for name, expected_defaults in defaults.items():
        function = getattr(risk, name, None)
        code = getattr(function, "__code__", None)
        if (code is None or Path(code.co_filename).resolve() != path.resolve()
                or function.__defaults__ != expected_defaults or function.__kwdefaults__ is not None
                or function.__closure__ is not None):
            fail("source_drift")
        compiled = compile(read(path, REPORT_CAP), code.co_filename, "exec")
        expected = next((item for item in compiled.co_consts if hasattr(item, "co_name") and item.co_name == name), None)
        if code != expected:
            fail("source_drift")
    if risk._CHAIN_RPC != {"ethereum": "https://rpc.mevblocker.io", "base": "https://mainnet.base.org", "bsc": "https://bsc-dataseed.bnbchain.org"}:
        fail("source_drift")


def external(path):
    try:
        result = Path(path).resolve()
        if any((p / ".git").exists() for p in (result,) + tuple(result.parents)):
            fail("raw_directory_refused")
        return result
    except (OSError, TypeError, ValueError):
        fail("raw_directory_refused")


def private_paths(runtime, private_dir, store=None):
    runtime = external(runtime)
    try:
        private = core._private_directory(private_dir, runtime)
        if store is not None:
            core._private_directory(private, store)
    except core.EvidenceError:
        fail("raw_directory_refused")
    return runtime, private


def bound_store(store, sources, ordinal):
    try:
        directory, value, _index, events, orphans = core._history(store)
        core._validate_plan(value, sources)
        complete = any(e.get("kind") == "enrollment_complete" for e in events)
        receipts = {e.get("ordinal") for e in events if e.get("kind") == "receipt"}
        if (not complete or orphans or (directory / ".writer").exists()
                or any(e.get("kind") == "intent" and e.get("ordinal") not in receipts for e in events)):
            fail("incomplete_history")
        record = next((e["record"] for e in events if e.get("kind") == "enrollment"
                       and type(ordinal) is int and e["record"]["ordinal"] == ordinal), None)
        if record is None:
            fail("ordinal_not_enrolled")
        identity = core._resolve(record, value, sources)
        return directory, value, record, identity, events
    except core.EvidenceError as exc:
        # Core errors are already fixed categories; never relay arbitrary exceptions.
        allowed = {"source_hash_mismatch", "source_drift", "existing_receipt",
                   "incomplete_history", "ordinal_not_enrolled", "source_reference_mismatch"}
        fail(str(exc) if str(exc) in allowed else "invalid_store")


def plan(store, sources, ordinal, *, now):
    manifest = code_manifest()
    _directory, value, record, _identity, _events = bound_store(store, sources, ordinal)
    try:
        instant = core._time(now)
        target = core._time(record["target_at"])
    except core.EvidenceError:
        fail("invalid_clock")
    return {"state": "not_due" if instant < target else "due", "ordinal": ordinal,
            "plan_sha256": value["plan_sha256"], "source_ref": record["source_ref"],
            "target_at": record["target_at"], "observed_at": iso(instant),
            "lateness_seconds": (instant - target).total_seconds(), "manifest": manifest}


def producer_claims(directory, value, events):
    """A completion file is evidence only when bound to the actual core receipt."""
    claims = directory / "native-claims"
    if not claims.exists():
        return {}
    records = {e["record"]["ordinal"]: e["record"] for e in events if e.get("kind") == "enrollment"}
    receipts = {e["ordinal"]: e["receipt"] for e in events if e.get("kind") == "receipt"}
    names = set()
    try:
        for path in claims.iterdir():
            if not path.is_file() or not re.fullmatch(r"\d{8}\.(?:json|done)", path.name) or len(names) >= 2 * core.COHORT_CAP:
                fail("history_corrupt")
            names.add(path.name)
    except OSError:
        fail("history_corrupt")
    if any(name.endswith(".done") and name[:-5] + ".json" not in names for name in names):
        fail("history_corrupt")
    result, code_hash = {}, sha(dumps(code_manifest()))
    for name in sorted(name for name in names if name.endswith(".json")):
        ordinal = int(name[:8])
        raw = read(claims / name, ROW_CAP)
        claim = parse(raw, ROW_CAP)
        record, receipt = records.get(ordinal), receipts.get(ordinal)
        if (not isinstance(claim, dict) or record is None
                or set(claim) != {"ordinal", "plan_sha256", "source_ref", "code_sha256", "claim_sha256"}
                or type(claim.get("ordinal")) is not int or claim["ordinal"] != ordinal
                or claim["plan_sha256"] != value["plan_sha256"] or claim["source_ref"] != record["source_ref"]
                or claim["code_sha256"] != code_hash or not core._hex(claim["claim_sha256"])):
            fail("history_corrupt")
        expected = None
        if receipt is not None:
            if (receipt.get("ordinal") != ordinal or receipt.get("source_ref") != record["source_ref"]
                    or not core._hex(receipt.get("packet_sha256"))):
                fail("history_corrupt")
            expected = {"ordinal": ordinal, "plan_sha256": value["plan_sha256"],
                        "claim_sha256": sha(raw), "receipt_sha256": sha(dumps(receipt)),
                        "packet_sha256": receipt["packet_sha256"]}
        marker = claims / (name[:-5] + ".done")
        completed = marker.exists()
        if completed and (expected is None or parse(read(marker, ROW_CAP), ROW_CAP) != expected):
            fail("history_corrupt")
        result[ordinal] = {"claim": claim, "receipt": receipt, "done": completed, "marker": expected}
    return result


def safe(value):
    if value is None or type(value) is bool:
        return True
    if type(value) in (int, float):
        return math.isfinite(value) and abs(value) < 10 ** 16
    if isinstance(value, str):
        return (value in FIXED or re.fullmatch(r"[0-9a-f]{64}", value) is not None
                or re.fullmatch(r"\d{4}-\d\d-\d\d(?:T\d\d:\d\d:\d\d(?:\.\d{1,6})?Z)?", value) is not None)
    if isinstance(value, list):
        return len(value) <= 256 and all(safe(v) for v in value)
    if isinstance(value, dict):
        return len(value) <= 64 and all(isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k)
                                      and safe(v) for k, v in value.items())
    return False


class Journal:
    def __init__(self, directory, binding=None):
        self.directory = Path(directory)
        self.events = []
        self.head = "0" * 64
        if binding is not None:
            try:
                self.directory.mkdir(parents=True, exist_ok=False)
                (self.directory / "events").mkdir()
            except OSError:
                fail("existing_claim")
            self.binding = binding
        else:
            self.binding = None
            try:
                entries = sorted((self.directory / "events").iterdir())
            except OSError:
                fail("history_corrupt")
            if not 1 <= len(entries) <= 256:
                fail("history_corrupt")
            for sequence, entry in enumerate(entries, 1):
                if entry.name != "%04d.json" % sequence:
                    fail("history_corrupt")
                raw = read(entry, ROW_CAP)
                event = parse(raw, ROW_CAP)
                if (not isinstance(event, dict) or set(event) != {"sequence", "parent_sha256", "binding", "payload"}
                        or event["sequence"] != sequence or event["parent_sha256"] != self.head
                        or not safe(event["payload"]) or event["payload"].get("kind") not in KINDS):
                    fail("history_corrupt")
                if self.binding is None:
                    self.binding = event["binding"]
                if not safe(event["binding"]) or event["binding"] != self.binding:
                    fail("history_corrupt")
                self.events.append(event["payload"])
                self.head = sha(raw)
            if self.events[0]["kind"] != "claim":
                fail("history_corrupt")

    def append(self, kind, **fields):
        payload = dict(fields, kind=kind)
        if kind not in KINDS or not safe(payload) or not safe(self.binding):
            fail("unsafe_output")
        if len(self.events) >= 256:
            fail("history_limit")
        event = {"sequence": len(self.events) + 1, "parent_sha256": self.head,
                 "binding": self.binding, "payload": payload}
        raw = dumps(event)
        if len(raw) > ROW_CAP:
            fail("history_limit")
        write_new(self.directory / "events" / ("%04d.json" % event["sequence"]), raw)
        self.events.append(payload)
        self.head = sha(raw)
        return {"journal_sequence": len(self.events), "journal_sha256": self.head}


def validate_request(url, *, role, token, chain, method="GET", body=None, headers=None):
    """Role-specific frozen request grammar; no caller URL reaches native I/O unchecked."""
    if (not isinstance(url, str) or len(url) > 4096 or role not in ("reserve", "ohlcv", "oracle", "engine")
            or core._address(token) != token or chain not in core.labels.GOPLUS_CHAIN_ID
            or method not in ("GET", "POST")):
        fail("request_refused")
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=8, strict_parsing=True) if parsed.query else {}
        if (parsed.scheme != "https" or parsed.hostname not in HOST_CODES or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment or "\\" in url
                or any(ord(c) < 33 or ord(c) > 126 for c in url)):
            fail("request_refused")
    except (ValueError, UnicodeError):
        fail("request_refused")
    headers = {} if headers is None else headers
    if not isinstance(headers, dict) or len(headers) > 2:
        fail("request_refused")
    if method == "GET":
        if body is not None or headers not in ({}, {"Accept": "application/json"}):
            fail("request_refused")
    else:
        if headers != {"content-type": "application/json"} or role != "engine":
            fail("request_refused")
        if not isinstance(body, str) or len(body.encode("utf-8")) > 1024:
            fail("request_refused")
        try:
            payload = core._json(body.encode(), 1024)
        except core.EvidenceError:
            fail("request_refused")
        if (not isinstance(payload, dict) or type(payload.get("id")) is not int
                or payload != {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [token, "latest"]}):
            fail("request_refused")
    path, host = parsed.path, parsed.hostname
    network = core.labels.GT_NETWORK[chain]
    pool_match = re.fullmatch(r"/api/v2/networks/" + re.escape(network) + r"/pools/(0x(?:[0-9a-f]{40}|[0-9a-f]{64}))", path)
    daily_match = re.fullmatch(r"/api/v2/networks/" + re.escape(network) + r"/pools/(0x(?:[0-9a-f]{40}|[0-9a-f]{64}))/ohlcv/day", path)
    allowed = False
    if role == "reserve":
        allowed = host == "api.geckoterminal.com" and bool(pool_match) and not query
    elif role == "ohlcv":
        allowed = host == "api.geckoterminal.com" and bool(daily_match) and query == {"limit": ["1000"]}
    elif role == "oracle":
        allowed = (host == "api.gopluslabs.io" and path == "/api/v1/token_security/" + core.labels.GOPLUS_CHAIN_ID[chain]
                   and query == {"contract_addresses": [token]})
    elif method == "POST":
        allowed = host in core.RPC_ROOT_HOSTS and path in ("", "/") and not query
    elif host == "api.dexscreener.com":
        pair_paths = {"/token-pairs/v1/" + known + "/" + token for known in core.labels.GOPLUS_CHAIN_ID}
        allowed = ((path == "/latest/dex/tokens/" + token or path in pair_paths) and not query
                   or path == "/latest/dex/search" and set(query) == {"q"} and len(query["q"]) == 1
                   and 0 < len(query["q"][0]) <= 128)
    elif host == "api.geckoterminal.com":
        known_networks = {core.labels.GT_NETWORK[known] for known in core.labels.GOPLUS_CHAIN_ID}
        pattern = r"/api/v2/networks/(?:" + "|".join(re.escape(net) for net in sorted(known_networks)) + r")/pools/0x(?:[0-9a-f]{40}|[0-9a-f]{64})"
        token_paths = {"/api/v2/networks/" + net + "/tokens/" + token + "/pools" for net in known_networks}
        allowed = (re.fullmatch(pattern, path) is not None or path in token_paths) and not query
    elif host == "api.honeypot.is":
        allowed = (path == "/v2/IsHoneypot" and set(query) in ({"address", "chainID"}, {"address", "chainID", "pair"})
                   and query.get("address") == [token] and query.get("chainID") in (["1"], ["56"], ["8453"])
                   and ("pair" not in query or len(query["pair"]) == 1 and core._pool(query["pair"][0]) is not None))
    if not allowed or role != "engine" and method != "GET":
        fail("request_refused")
    return {"url": url, "method": method, "body": body, "headers": dict(headers),
            "role": role, "host": HOST_CODES[host], "token": token, "chain": chain}


def _windows_api():
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    api.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    api.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    return api


def creation_identity(pid):
    if sys.platform == "win32":
        api = _windows_api()
        handle = api.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            fail("cleanup_uncertain")
        try:
            times = [ctypes.c_uint64() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)):
                fail("cleanup_uncertain")
            return str(times[0].value)
        finally:
            api.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        try:
            fields = Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()
            return fields[19]
        except (OSError, IndexError):
            fail("cleanup_uncertain")
    fail("containment_unavailable")


def identity_alive(identity):
    """PID reuse is not identity; inaccessible identity is an explicit safe-stop."""
    if not isinstance(identity, dict) or type(identity.get("pid")) is not int or not isinstance(identity.get("creation"), str):
        fail("cleanup_uncertain")
    pid = identity["pid"]
    if sys.platform == "win32":
        api = _windows_api()
        handle = api.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            fail("cleanup_uncertain")
        try:
            if api.WaitForSingleObject(handle, 0) == 0:
                return False
            times = [ctypes.c_uint64() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)):
                fail("cleanup_uncertain")
            return str(times[0].value) == identity["creation"]
        finally:
            api.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        try:
            text = Path("/proc/%d/stat" % pid).read_text()
        except FileNotFoundError:
            return False
        except OSError:
            fail("cleanup_uncertain")
        try:
            fields = text.rsplit(")", 1)[1].split()
            return fields[0] != "Z" and fields[19] == identity["creation"]
        except IndexError:
            fail("cleanup_uncertain")
    fail("containment_unavailable")


class Job:
    def __init__(self, process):
        self.handle = None
        if sys.platform != "win32":
            return
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                        ("active", wintypes.DWORD), ("affinity", ctypes.c_size_t),
                        ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        self.api = _windows_api()
        self.handle = self.api.CreateJobObjectW(None, None)
        information, flags, assigned = Extended(), wintypes.DWORD(), wintypes.BOOL()
        information.basic.flags = 0x2000
        if (not self.handle or not self.api.SetHandleInformation(self.handle, 1, 0)
                or not self.api.GetHandleInformation(self.handle, ctypes.byref(flags)) or flags.value & 1
                or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(information), ctypes.sizeof(information))
                or not self.api.AssignProcessToJobObject(self.handle, int(process._handle))
                or not self.api.IsProcessInJob(int(process._handle), self.handle, ctypes.byref(assigned)) or not assigned.value):
            self.close()
            fail("containment_unavailable")

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _parent_death(expected):
    if sys.platform.startswith("linux"):
        library = ctypes.CDLL(None, use_errno=True)
        if os.getppid() != expected or library.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            fail("containment_unavailable")
        actual = ctypes.c_int()
        if library.prctl(2, ctypes.byref(actual), 0, 0, 0) != 0 or actual.value != signal.SIGKILL or os.getppid() != expected:
            fail("containment_unavailable")
    elif sys.platform != "win32":
        fail("containment_unavailable")


def _child(path):
    """Internal disarmed worker. stdin EOF before acknowledgement cannot open a socket."""
    configuration = parse(read(path, ROW_CAP), ROW_CAP)
    directory = Path(path).parent
    parent = configuration["parent"]
    _parent_death(parent)
    lifetime = configuration["permit"]["request_deadline"] - time.monotonic() - .25
    if not 0 < lifetime <= ATTEMPT_SECONDS:
        return 2
    watchdog = threading.Timer(lifetime, os._exit, args=(3,))
    watchdog.daemon = True
    watchdog.start()
    request = configuration["request"]
    validate_request(request["url"], role=request["role"], token=request["token"], chain=request["chain"],
                     method=request["method"], body=request["body"], headers=request["headers"])
    identity = {"pid": os.getpid(), "creation": creation_identity(os.getpid()),
                "token": configuration["nonce"], "parent": parent}
    write_new(directory / "identity.json", dumps(identity))
    write_new(directory / "ready.json", dumps({"identity_sha256": sha(dumps(identity))}))
    line = sys.stdin.buffer.readline(128)
    if line != ("arm " + configuration["nonce"] + "\n").encode():
        return 0
    if sys.platform.startswith("linux") and os.getppid() != parent:
        return 0
    permit = configuration["permit"]
    sample_utc, sample_mono = datetime.now(timezone.utc), time.monotonic()
    if (iso(sample_utc)[:10] != permit["reserved_date"] or sample_mono >= permit["expires_mono"]
            or sample_mono + ATTEMPT_SECONDS > permit["packet_deadline"]):
        write_new(directory / "end.json", dumps({"state": "not_invoked", "reason": "permit_expired", "bytes": 0}))
        return 0
    parsed = urlsplit(request["url"])
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    route = configuration.get("route")
    connection = None
    try:
        remaining = max(.01, permit["request_deadline"] - time.monotonic() - .5)
        if route is None:
            connection = http.client.HTTPSConnection(parsed.hostname, timeout=remaining)
        else:
            if (not isinstance(route, list) or len(route) != 2 or route[0] != "127.0.0.1"
                    or type(route[1]) is not int or not 1 <= route[1] <= 65535):
                fail("request_refused")
            connection = http.client.HTTPConnection(route[0], route[1], timeout=remaining)
        body = request["body"].encode() if request["body"] is not None else None
        # No blocking persistence stands between this sample and native entry.
        # If hard death loses its later proof, arming remains terminal start_uncertain.
        entry_utc, entry_mono = datetime.now(timezone.utc), time.monotonic()
        if iso(entry_utc)[:10] != permit["reserved_date"] or entry_mono >= permit["expires_mono"]:
            write_new(directory / "end.json", dumps({"state": "not_invoked", "reason": "permit_expired", "bytes": 0}))
            return 0
        try:
            connection.request(request["method"], target, body=body, headers=request["headers"])
        finally:
            write_new(directory / "invocation.json", dumps({"utc": iso(entry_utc), "monotonic": entry_mono,
                "permit_sha256": configuration["permit_sha256"]}))
        write_new(directory / "sent.json", dumps({"state": "observed"}))
        response = connection.getresponse()
        header = {"status": response.status, "headers": response.getheaders(),
                  "utc": iso(datetime.now(timezone.utc)), "monotonic": time.monotonic()}
        raw_header = dumps(header)
        if len(raw_header) > ROW_CAP:
            fail("invalid_body")
        write_new(directory / "headers.json", raw_header)
        if sys.stdin.buffer.readline(128) != ("body " + configuration["nonce"] + "\n").encode():
            return 0
        size, digest = 0, hashlib.sha256()
        with (directory / "body.bin").open("r+b") as handle:
            while size <= BODY_CAP:
                if time.monotonic() >= permit["request_deadline"] - .5:
                    fail("timeout")
                raw = response.read1(min(16384, BODY_CAP + 1 - size))
                if not raw:
                    break
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
                size += len(raw)
                digest.update(raw)
                replace_private(directory / "progress.json", {"bytes": size, "sha256": digest.hexdigest()})
                if size > BODY_CAP:
                    break
        if size <= BODY_CAP and response.length not in (None, 0):
            fail("transport_error")
        write_new(directory / "end.json", dumps({"state": "invalid_body" if size > BODY_CAP else "observed",
                                                "bytes": size, "sha256": digest.hexdigest(),
                                                "utc": iso(datetime.now(timezone.utc))}))
    except BaseException:
        if not (directory / "end.json").exists():
            write_new(directory / "end.json", dumps({"state": "transport_error", "bytes": 0}))
    finally:
        if connection:
            connection.close()
    return 0


class NativeWorker:
    def __init__(self, request, *, directory, permit, permit_sha256, route=None, hooks=None, recheck=None, **_kwargs):
        self.directory, self.permit, self.hooks = Path(directory), permit, hooks
        self.identity, self.process, self.job = None, None, None
        self.recheck = recheck
        self.body_acknowledged = False
        self.configuration = {"request": request, "permit": permit, "permit_sha256": permit_sha256,
                              "parent": os.getpid(), "nonce": uuid.uuid4().hex,
                              "route": list(route) if route is not None else None}

    async def wait_file(self, name):
        while not (self.directory / name).exists():
            if self.process.poll() is not None:
                fail("transport_error")
            if time.monotonic() >= self.permit["request_deadline"] - .5:
                fail("timeout")
            await asyncio.sleep(.005)
        return parse(read(self.directory / name, ROW_CAP), ROW_CAP)

    async def start(self):
        write_new(self.directory / "request.json", dumps(self.configuration))
        self.process = subprocess.Popen([sys.executable, "-B", str(Path(__file__)), "--native-child", str(self.directory / "request.json")],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.identity = {"pid": self.process.pid, "creation": creation_identity(self.process.pid),
                         "token": self.configuration["nonce"], "parent": os.getpid()}
        write_new(self.directory / "creation.json", dumps(self.identity))
        self.job = Job(self.process)
        ready = await self.wait_file("ready.json")
        observed_identity = parse(read(self.directory / "identity.json", ROW_CAP), ROW_CAP)
        if (observed_identity != self.identity or not identity_alive(self.identity)
                or ready != {"identity_sha256": sha(dumps(self.identity))}):
            fail("containment_unavailable")
        if self.hooks:
            await self.hooks("before_ack", self)
        if self.recheck:
            self.recheck(self.permit)
        write_new(self.directory / "arming.json", dumps({"permit_sha256": self.configuration["permit_sha256"]}))
        if self.recheck:
            self.recheck(self.permit)
        self.process.stdin.write(("arm " + self.configuration["nonce"] + "\n").encode())
        self.process.stdin.flush()
        invocation = await self.wait_file("invocation.json")
        # Sent confirmation distinguishes request invocation from process creation.
        await self.wait_file("sent.json")
        if self.hooks:
            await self.hooks("native_entry", self)
        return invocation

    async def headers(self):
        result = await self.wait_file("headers.json")
        if type(result.get("status")) is not int or not 100 <= result["status"] <= 599:
            fail("invalid_body")
        self.header_sample = {"utc": result["utc"], "monotonic": result["monotonic"]}
        return result["status"]

    async def body(self):
        if not self.body_acknowledged:
            self.process.stdin.write(("body " + self.configuration["nonce"] + "\n").encode())
            self.process.stdin.flush()
            self.body_acknowledged = True
        result = await self.wait_file("end.json")
        if result.get("state") != "observed":
            fail(result["state"] if result.get("state") in ("timeout", "invalid_body") else "transport_error")
        size = result.get("bytes")
        if type(size) is not int or not 0 <= size <= BODY_CAP:
            fail("invalid_body")
        with (self.directory / "body.bin").open("rb") as handle:
            raw = handle.read(size)
        if len(raw) != size or sha(raw) != result.get("sha256"):
            fail("invalid_evidence")
        self.body_sample = {"utc": result["utc"]}
        return raw

    async def retire(self):
        if self.process is None:
            return "exited"
        try:
            if self.process.poll() is None:
                self.process.kill()
            deadline = time.monotonic() + .4
            while self.process.poll() is None and time.monotonic() < deadline:
                await asyncio.sleep(.005)
            if self.process.poll() is None:
                fail("cleanup_uncertain")
            if self.identity is not None and identity_alive(self.identity):
                fail("cleanup_uncertain")
            return "exited"
        finally:
            if self.job:
                self.job.close()
            if self.process.stdin:
                self.process.stdin.close()

    def snapshot(self):
        """Read the last flushed bounded prefix only after mechanical retirement."""
        return captured_prefix(self.directory)


def captured_prefix(directory):
    for name in ("end.json", "progress.json"):
        path = directory / name
        if not path.exists():
            continue
        state = parse(read(path, ROW_CAP), ROW_CAP)
        size = state.get("bytes")
        if type(size) is not int or not 0 <= size <= BODY_CAP + 1 or not core._hex(state.get("sha256")):
            continue
        try:
            with (directory / "body.bin").open("rb") as handle:
                raw = handle.read(size)
        except OSError:
            fail("input_unavailable")
        if len(raw) != size or sha(raw) != state["sha256"]:
            fail("invalid_evidence")
        return raw
    return None


class Response:
    def __init__(self, adapter, attempt):
        self.adapter, self.attempt = adapter, attempt
        self.status = attempt["status"]
        self.raw = None

    async def text(self):
        if self.raw is not None:
            return self.raw.decode("utf-8")
        attempt = self.attempt
        try:
            raw = await attempt["worker"].body()
            if not isinstance(raw, bytes) or len(raw) > BODY_CAP:
                fail("invalid_body")
            with (attempt["directory"] / "body.bin").open("r+b") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            raw.decode("utf-8")
            attempt.update(raw=raw, state=("observed" if self.status == 200 else
                "http_429" if self.status == 429 else "http_refusal" if 300 <= self.status < 500 else "http_failure"))
            attempt["response_at"] = getattr(attempt["worker"], "body_sample", {}).get("utc", self.adapter.sample()["utc"])
            self.raw = raw
            await self.adapter.finish(attempt)
            return raw.decode("utf-8")
        except asyncio.CancelledError:
            attempt["state"] = "interrupted_intent"
            await self.adapter.finish(attempt)
            raise
        except BaseException as exc:
            attempt["state"] = (str(exc) if isinstance(exc, NativeError) and str(exc) in ("invalid_body", "timeout")
                                else "transport_error")
            await self.adapter.finish(attempt)
            fail(attempt["state"])


class Admission:
    def before_attempt(self, proposed):
        return proposed

    def observe(self, _event):
        return None


class Adapter:
    def __init__(self, journal, private, *, token, chain, clock=None, transport=None,
                 route=None, policy=None, hooks=None):
        self.journal, self.private = journal, Path(private)
        self.token, self.chain, self.clock = token, chain, clock or Clock()
        self.transport, self.route, self.policy, self.hooks = transport or NativeWorker, route, policy or Admission(), hooks
        self.start = self.sample()
        self.deadline = self.start["monotonic"] + PACKET_SECONDS
        self.last_clock = self.start
        self.last_start, self.attempts, self.active = {}, [], None
        self.endpoints = {"label": [], "engine": [], "eligibility": []}
        self.cache = {}
        self.cache_events = []
        self.stopped, self.start_uncertain = False, False
        self.stop_reason = None
        self.transition, self.finishing = asyncio.Lock(), asyncio.Lock()
        (self.private / "attempts").mkdir(exist_ok=True)
        (self.private / "dependencies").mkdir(exist_ok=True)

    def sample(self):
        try:
            utc, monotonic = self.clock.utc(), self.clock.mono()
            if type(monotonic) not in (int, float) or not math.isfinite(monotonic) or monotonic < 0:
                fail("clock_failure")
            return {"utc": iso(utc), "monotonic": float(monotonic)}
        except BaseException:
            fail("clock_failure")

    def recheck(self, permit):
        current = self.sample()
        if (current["monotonic"] < self.last_clock["monotonic"]
                or core._time(current["utc"]) < core._time(self.last_clock["utc"])):
            self.stopped = True
            fail("clock_failure")
        self.last_clock = current
        if current["utc"][:10] != permit["reserved_date"] or current["monotonic"] >= permit["expires_mono"]:
            fail("permit_expired")
        if current["monotonic"] + ATTEMPT_SECONDS > min(permit["packet_deadline"], permit["external_deadline"]):
            fail("packet_deadline")
        if code_manifest() != self.manifest:
            self.stopped = True
            fail("source_drift")
        return current

    def observe(self, kind, attempt, **fields):
        event = dict(kind=kind, attempt=attempt["number"], permit_sha256=attempt["permit_sha256"], **fields)
        self.journal.append(kind, **{k: v for k, v in event.items() if k != "kind"})
        try:
            self.policy.observe(MappingProxyType(event))
        except BaseException:
            self.stopped = self.start_uncertain = True
            fail("policy_failure")

    async def fetch(self, url, *, method="GET", body=None, headers=None, role="engine"):
        async with self.transition:
            return await self._fetch(url, method=method, body=body, headers=headers, role=role)

    async def _fetch(self, url, *, method="GET", body=None, headers=None, role="engine"):
        if self.active is not None:
            await self.finish(self.active)
        if self.stopped:
            fail("acquisition_stopped")
        try:
            request = validate_request(url, role=role, token=self.token, chain=self.chain, method=method, body=body, headers=headers)
        except NativeError:
            self.stopped = True
            self.stop_reason = "request_refused"
            fail("request_refused")
        if role == "engine":
            self.endpoints["engine"].append(url)
        else:
            self.endpoints["label"].append(url)
            if role == "reserve":
                self.endpoints["eligibility"].append(url)
        count = sum(a["role"] == "engine" for a in self.attempts)
        if len(self.attempts) >= 19 or role == "engine" and count >= 16 or role != "engine" and len(self.attempts) - count >= 3:
            self.stopped = True
            self.stop_reason = "attempt_cap"
            fail("attempt_cap")
        current = self.sample()
        number = len(self.attempts) + 1
        directory = self.private / "attempts" / ("%02d" % number)
        try:
            directory.mkdir()
        except OSError:
            fail("persistence_failed")
        intent = self.journal.append("attempt_intent", attempt=number, role=role, host=request["host"],
                                     utc=current["utc"], monotonic=current["monotonic"],
                                     allowance_seconds=ATTEMPT_SECONDS, private_bytes=PRIVATE_ALLOWANCE)
        attempt = {"number": number, "role": role, "request": request, "directory": directory,
                   "state": "not_invoked", "reason": "interrupted", "invocation": None,
                   "status": None, "raw": None, "worker": None, "identity": None, "retirement": None,
                   "ended": False, "permit_sha256": "0" * 64}
        self.attempts.append(attempt)
        self.active = attempt
        try:
            allocate(directory / "body.bin", BODY_CAP + 1)
            allocate(directory / "metadata-reserve.bin", ROW_CAP)
            write_new(directory / "metadata.json", dumps(request))
            proposed = dict(intent, role=role, host=request["host"], ordinal=self.journal.binding["ordinal"],
                plan_sha256=self.journal.binding["plan_sha256"], code_sha256=sha(dumps(self.manifest)),
                attempt=number, attempt_id=sha(dumps(dict(intent, ordinal=self.journal.binding["ordinal"]))),
                reserved_date=current["utc"][:10], expires_mono=current["monotonic"] + ATTEMPT_SECONDS,
                request_deadline=current["monotonic"] + ATTEMPT_SECONDS,
                packet_deadline=self.deadline, external_deadline=self.deadline,
                allowance_seconds=ATTEMPT_SECONDS, private_bytes=PRIVATE_ALLOWANCE)
            try:
                supplied = self.policy.before_attempt(MappingProxyType(dict(proposed)))
            except BaseException:
                fail("policy_failure")
            if supplied is None:
                fail("policy_refused")
            permit = dict(supplied)
            if set(permit) != set(proposed):
                fail("policy_refused")
            for key in proposed:
                if key in ("expires_mono", "packet_deadline", "external_deadline"):
                    if type(permit[key]) not in (int, float) or not math.isfinite(permit[key]) or permit[key] > proposed[key]:
                        fail("policy_refused")
                elif permit[key] != proposed[key]:
                    fail("policy_refused")
            attempt["permit_sha256"] = sha(dumps(permit))
            write_new(directory / "permit.json", dumps(permit))
            self.recheck(permit)
            gap = GAPS[request["host"]]
            wait = self.last_start.get(request["host"], -math.inf) + gap - self.clock.mono()
            if wait > 0:
                await self.clock.sleep(wait)
            self.recheck(permit)
            worker = self.transport(request, directory=directory, permit=permit,
                permit_sha256=attempt["permit_sha256"], route=self.route, hooks=self.hooks, recheck=self.recheck)
            attempt["worker"] = worker
            invocation = await worker.start()
            attempt["identity"] = worker.identity
            attempt["invocation"] = invocation
            self.last_start[request["host"]] = invocation["monotonic"]
            self.observe("native_invocation", attempt, utc=invocation["utc"], monotonic=invocation["monotonic"])
            attempt["status"] = await worker.headers()
            status = attempt["status"]
            if type(status) is not int or not 100 <= status <= 599:
                fail("invalid_body")
            sample = getattr(worker, "header_sample", None) or self.sample()
            attempt["headers_at"] = sample["utc"]
            self.observe("headers", attempt, status=status, utc=sample["utc"], monotonic=sample["monotonic"])
            if status in (401, 403):
                self.stopped = True
                self.stop_reason = "http_refusal"
            return Response(self, attempt)
        except asyncio.CancelledError:
            attempt.update(state="interrupted_intent", reason="interrupted")
            await self.finish(attempt)
            raise
        except BaseException as exc:
            code = str(exc) if isinstance(exc, NativeError) and str(exc) in FIXED else "transport_error"
            attempt.update(state="not_invoked" if attempt["invocation"] is None else "transport_error", reason=code)
            if code in ("source_drift", "clock_failure", "persistence_failed", "cleanup_uncertain", "policy_failure",
                        "policy_refused", "permit_expired", "packet_deadline", "attempt_cap"):
                self.stopped = True
                self.stop_reason = code
            await self.finish(attempt)
            fail(code)

    async def finish(self, attempt):
        async with self.finishing:
            return await self._finish(attempt)

    async def _finish(self, attempt):
        if attempt["ended"]:
            return
        worker = attempt["worker"]
        try:
            retirement = await worker.retire() if worker else "exited"
            if retirement != "exited":
                fail("cleanup_uncertain")
            attempt["retirement"] = retirement
            if worker is not None:
                attempt["identity"] = worker.identity
                if attempt["raw"] is None and hasattr(worker, "snapshot"):
                    attempt["raw"] = worker.snapshot()
            if attempt["status"] is not None and attempt["state"] == "not_invoked":
                attempt["state"] = ("http_429" if attempt["status"] == 429 else
                    "http_refusal" if 300 <= attempt["status"] < 500 else "interrupted_intent")
            if attempt["invocation"] is None and (attempt["directory"] / "invocation.json").exists():
                attempt["invocation"] = parse(read(attempt["directory"] / "invocation.json", ROW_CAP), ROW_CAP)
                self.last_start[attempt["request"]["host"]] = attempt["invocation"]["monotonic"]
                self.observe("native_invocation", attempt, utc=attempt["invocation"]["utc"], monotonic=attempt["invocation"]["monotonic"])
            if (attempt["invocation"] is None and (attempt["directory"] / "arming.json").exists()
                    and not (attempt["directory"] / "end.json").exists()):
                self.stopped = self.start_uncertain = True
                self.stop_reason = "start_uncertain"
            raw = attempt["raw"]
            sample = self.sample()
            fields = dict(state=attempt["state"], reason=attempt["reason"], utc=sample["utc"],
                          status=attempt["status"], body_sha256=sha(raw) if raw is not None else None,
                          body_bytes=len(raw) if raw is not None else 0,
                          response_at=attempt.get("response_at", attempt.get("headers_at")))
            write_new(attempt["directory"] / "commit.json", dumps(fields))
            self.observe("attempt_end", attempt, **fields)
            self.observe("child_retired", attempt, state="exited",
                         identity_sha256=sha(dumps(attempt["identity"])) if attempt["identity"] is not None else None)
        except BaseException:
            self.stopped = True
            if worker is not None:
                # A failed observer cannot prevent mechanical child retirement.
                await worker.retire()
            if not self.start_uncertain:
                fail("cleanup_uncertain")
        finally:
            attempt["ended"] = True
            if self.active is attempt:
                self.active = None

    async def cache_get(self, url):
        endpoint = url
        if url.startswith("https://bytecode.vetagent.internal/"):
            import risk
            parts = urlsplit(url).path.strip("/").split("/")
            if len(parts) != 2 or parts[1] != self.token or parts[0] not in risk._CHAIN_RPC:
                self.stopped = True
                fail("request_refused")
            endpoint = risk._CHAIN_RPC[parts[0]]
        if endpoint is not None:
            self.endpoints["engine"].append(endpoint)
        cached = self.cache.get(url)
        age = self.clock.mono() - cached[1] if cached else None
        self.cache_event({"kind": "get", "url": url, "endpoint": endpoint,
                          "age_seconds": age, "at": self.sample()["utc"]})
        return (copy.deepcopy(cached[0]), age) if cached else (None, None)

    async def cache_put(self, url, data, ttl=None):
        self.cache[url] = (copy.deepcopy(data), self.clock.mono())
        self.cache_event({"kind": "put", "url": url, "ttl": ttl, "at": self.sample()["utc"]})

    def cache_event(self, event):
        if len(self.cache_events) >= 256:
            self.stopped = True
            fail("history_limit")
        try:
            write_new(self.private / "dependencies" / ("%04d.json" % (len(self.cache_events) + 1)), dumps(event))
        except NativeError:
            self.stopped = True
            raise
        self.cache_events.append(event)


@contextlib.asynccontextmanager
async def adapter_scope(runtime, private_dir, *, token, chain, clock=None, transport=None,
                        route=None, policy=None, hooks=None, _journal=None):
    """Patch only seven approved process ports and restore their exact prior state."""
    global _ACTIVE_SCOPE
    if _ACTIVE_SCOPE:
        fail("scope_busy")
    runtime, private = private_paths(runtime, private_dir)
    import importlib
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    risk = importlib.import_module("risk")
    manifest = code_manifest()
    engine_bindings(risk)
    if _journal is None:
        if private.exists():
            fail("existing_claim")
        private.mkdir(parents=True)
        binding = {"ordinal": 0, "plan_sha256": "0" * 64, "code_sha256": sha(dumps(manifest))}
        journal = Journal(runtime, binding)
        journal.append("claim", state="standalone", utc=iso((clock or Clock()).utc()), manifest=manifest)
    else:
        journal = _journal
    adapter = Adapter(journal, private, token=token, chain=chain, clock=clock,
                      transport=transport, route=route, policy=policy, hooks=hooks)
    adapter.manifest = manifest
    old = (risk.cf_fetch, risk._cache_get, risk._cache_put)
    onchain, contents = risk._ONCHAIN, dict(risk._ONCHAIN)
    contexts = (risk._BENCH_NOW, risk._STALE_HITS, risk._FETCH_FAILURES)
    tokens = [variable.set(value) for variable, value in zip(contexts, (adapter.clock.utc().timestamp(), [], []))]
    risk.cf_fetch, risk._cache_get, risk._cache_put = adapter.fetch, adapter.cache_get, adapter.cache_put
    onchain.clear()
    onchain.update(key=None, unusable=False)
    _ACTIVE_SCOPE = True
    try:
        yield adapter
    finally:
        try:
            if adapter.active is not None:
                await adapter.finish(adapter.active)
            write_new(private / "cache-history.json", dumps(adapter.cache_events))
        finally:
            risk.cf_fetch, risk._cache_get, risk._cache_put = old
            onchain.clear()
            onchain.update(contents)
            for variable, token_value in zip(contexts, tokens):
                variable.reset(token_value)
            _ACTIVE_SCOPE = False


def not_asked(reason="interrupted"):
    return {"state": "not_asked", "reason": reason}


def stage_from_attempt(attempt):
    raw = attempt.get("raw")
    invocation = attempt.get("invocation")
    result = {"state": attempt["state"], "reason": attempt["reason"], "http_status": attempt["status"],
              "request_at": invocation["utc"] if invocation else None,
              "response_at": attempt.get("response_at", attempt.get("headers_at"))}
    if result["state"] == "not_invoked":
        result["state"] = "not_asked"
    if raw is not None:
        result.update(raw=base64.b64encode(raw).decode("ascii"), sha256=sha(raw))
    return result


async def acquire_stage(adapter, url, role):
    before = len(adapter.attempts)
    try:
        response = await adapter.fetch(url, role=role, headers={"Accept": "application/json"})
        await response.text()
        attempt = adapter.attempts[-1]
        attempt.setdefault("response_at", adapter.sample()["utc"])
        return stage_from_attempt(attempt)
    except NativeError as exc:
        if len(adapter.attempts) > before:
            return stage_from_attempt(adapter.attempts[-1])
        return not_asked(str(exc) if str(exc) in FIXED else "acquisition_stopped")


def base_packet(value, record, identity):
    chain, token, pool = identity
    return {"schema": 1, "plan_sha256": value["plan_sha256"], "ordinal": record["ordinal"],
            "source_ref": record["source_ref"], "chain": chain, "token": token, "pool": pool,
            "engine_source_commit": value["source_commit"], "engine_sha256": value["engine_sha256"],
            "engine_context_at": None, "reserve": not_asked(), "ohlcv": not_asked(),
            "oracle": not_asked(), "engine": not_asked(),
            "endpoints": {"label": [], "engine": [], "eligibility": []}}


def seal(journal, private, packet, *, state="prepared"):
    # The packet carries bounded hashes of all native sidecars, not copies of engine bodies.
    attempts = []
    for intent in (e for e in journal.events if e["kind"] == "attempt_intent"):
        directory = private / "attempts" / ("%02d" % intent["attempt"])
        item = {"attempt": intent["attempt"], "role": intent["role"], "host": intent["host"]}
        for name, key in (("metadata.json", "request_sha256"), ("permit.json", "permit_sha256"),
                          ("identity.json", "identity_sha256"), ("headers.json", "headers_sha256"),
                          ("commit.json", "commit_sha256"), ("progress.json", "progress_sha256")):
            path = directory / name
            item[key] = sha(read(path, ROW_CAP)) if path.exists() else None
        attempts.append(item)
    dependencies = sorted((private / "dependencies").glob("*.json"))
    packet["native_provenance"] = {"code_sha256": journal.binding["code_sha256"],
        "journal_sha256": journal.head, "attempts": attempts,
        "dependencies_sha256": sha(dumps([sha(read(path, ROW_CAP)) for path in dependencies]))}
    raw = dumps(packet)
    if len(raw) > PACKET_CAP:
        fail("packet_limit")
    path = private / "prepared.bin"
    if not path.exists():
        allocate(path, PACKET_CAP)
    try:
        with path.open("r+b") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        fail("persistence_failed")
    independence = core._independence(packet)
    journal.append("packet_prepared", packet_sha256=sha(raw), packet_bytes=len(raw), state=state,
                   stop_reason=packet.get("native_stop_reason"),
                   stages={k: packet[k]["state"] for k in ("reserve", "ohlcv", "oracle", "engine")},
                   unknown=int(packet["engine"].get("state") != "observed" or
                       parse(base64.b64decode(packet["engine"]["raw"]), BODY_CAP).get("risk_level") == "unknown"),
                   overlap=len(independence["overlap"]))
    return report(journal.directory)


def collect_one(store, sources, ordinal, *, runtime, private_dir, live=False,
                manifest=None, clock=None, transport=None, route=None, policy=None, hooks=None, engine=None):
    """Refuse invalid/offline work synchronously, before even allocating an event loop."""
    if not live:
        fail("live_required")
    private_paths(runtime, private_dir, store)
    if manifest != code_manifest():
        fail("source_drift")
    view = plan(store, sources, ordinal, now=iso((clock or Clock()).utc()))
    if view["state"] != "due":
        fail("not_due")
    return _collect_one(store, sources, ordinal, runtime=runtime, private_dir=private_dir,
        live=live, manifest=manifest, clock=clock, transport=transport, route=route,
        policy=policy, hooks=hooks, engine=engine)


async def _collect_one(store, sources, ordinal, *, runtime, private_dir, live=False,
                      manifest=None, clock=None, transport=None, route=None, policy=None, hooks=None, engine=None):
    """Acquire and seal exactly one packet. Offline recover performs the separate import."""
    if not live:
        fail("live_required")
    runtime, private = private_paths(runtime, private_dir, store)
    actual = code_manifest()
    if manifest != actual:
        fail("source_drift")
    clock = clock or Clock()
    view = plan(store, sources, ordinal, now=iso(clock.utc()))
    if view["state"] != "due":
        fail("not_due")
    directory, value, record, identity, events = bound_store(store, sources, ordinal)
    if any(e.get("kind") in ("intent", "receipt") and e.get("ordinal") == ordinal for e in events):
        fail("existing_receipt")
    claims = directory / "native-claims"
    if any(not item["done"] for item in producer_claims(directory, value, events).values()):
        fail("existing_claim")
    if runtime.exists() or private.exists():
        fail("existing_claim")
    packet = base_packet(value, record, identity)
    binding = {"ordinal": ordinal, "plan_sha256": value["plan_sha256"],
               "source_ref": record["source_ref"], "code_sha256": sha(dumps(actual))}
    journal = Journal(runtime, binding)
    try:
        private.mkdir(parents=True, exist_ok=False)
        claims.mkdir(exist_ok=True)
    except OSError:
        fail("persistence_failed")
    configuration = {"keyless": True, "empty_cache": True, "cache_initial_entries": 0,
                     "native_transport": transport is None, "fixture_route": route is not None,
                     "frozen_assess": engine is None, "configured_at": iso(clock.utc())}
    context = {"packet": packet, "manifest": actual, "configuration": configuration}
    raw_context = dumps(context)
    write_new(private / "context.json", raw_context)
    journal.append("claim", utc=iso(clock.utc()), manifest=actual, context_sha256=sha(raw_context), state="native")
    write_new(claims / ("%08d.json" % ordinal), dumps(dict(binding, claim_sha256=journal.head)))
    allocate(private / "prepared.bin", PACKET_CAP)
    chain, token, pool = identity
    gt = "https://api.geckoterminal.com/api/v2/networks/%s/pools/%s" % (core.labels.GT_NETWORK[chain], pool)
    async with adapter_scope(runtime, private, token=token, chain=chain, clock=clock, transport=transport,
                             route=route, policy=policy, hooks=hooks, _journal=journal) as adapter:
        packet["reserve"] = await acquire_stage(adapter, gt, "reserve")
        number, valid = None, False
        try:
            field = packet["reserve"]
            if field["state"] == "observed" and field["http_status"] == 200:
                data = parse(base64.b64decode(field["raw"]), BODY_CAP)["data"]
                attributes = data["attributes"]
                number = core._number(attributes.get("reserve_in_usd"))
                valid = data.get("id") == core.labels.GT_NETWORK[chain] + "_" + pool and core._pool(attributes.get("address")) == pool and number is not None
        except (NativeError, TypeError, KeyError, ValueError):
            pass
        if not valid or number < core.RULES["reserve_usd"]:
            reason = "reserve_unobserved" if not valid else "reserve_below_floor"
            for name in ("ohlcv", "oracle", "engine"):
                packet[name] = not_asked(reason)
        else:
            packet["ohlcv"] = await acquire_stage(adapter, gt + "/ohlcv/day?limit=1000", "ohlcv")
            oracle = "https://api.gopluslabs.io/api/v1/token_security/%s?contract_addresses=%s" % (core.labels.GOPLUS_CHAIN_ID[chain], token)
            packet["oracle"] = await acquire_stage(adapter, oracle, "oracle")
            if not adapter.stopped:
                if str(ROOT / "src") not in sys.path:
                    sys.path.insert(0, str(ROOT / "src"))
                import risk
                started = iso(clock.utc())
                packet["engine_context_at"] = started
                risk._BENCH_NOW.set(clock.utc().timestamp())
                try:
                    answer = await asyncio.wait_for((engine or risk.assess)(token, chain_hint=chain, verbose=True),
                        timeout=max(.001, adapter.deadline - clock.mono()))
                    raw = dumps(answer)
                    if len(raw) > BODY_CAP:
                        fail("invalid_body")
                    write_new(private / "engine-answer.json", raw)
                    packet["engine"] = {"state": "observed", "http_status": 200, "request_at": started,
                        "response_at": iso(clock.utc()), "raw": base64.b64encode(raw).decode(), "sha256": sha(raw)}
                except asyncio.CancelledError:
                    packet["engine"] = not_asked("interrupted")
                    raise
                except BaseException:
                    packet["engine"] = not_asked("engine_error")
            else:
                packet["engine"] = not_asked("acquisition_stopped")
        packet["endpoints"] = adapter.endpoints
    packet["native_stop_reason"] = adapter.stop_reason
    return seal(journal, private, packet, state="start_uncertain" if adapter.start_uncertain else "prepared")


def report(runtime):
    journal = Journal(runtime)
    intents = [e for e in journal.events if e["kind"] == "attempt_intent"]
    invocation = [e for e in journal.events if e["kind"] == "native_invocation"]
    ends = [e for e in journal.events if e["kind"] == "attempt_end"]
    prepared = next((e for e in reversed(journal.events) if e["kind"] == "packet_prepared"), None)
    imported = any(e["kind"] == "import_result" for e in journal.events)
    stages = prepared["stages"] if prepared else {k: "not_asked" for k in ("reserve", "ohlcv", "oracle", "engine")}
    result = {"state": "imported" if imported else prepared["state"] if prepared else "uncertain",
              "ordinal": journal.binding["ordinal"], "plan_sha256": journal.binding["plan_sha256"],
              "journal_sha256": journal.head, "reserved": len(intents), "attempted": len(invocation),
              "completed": sum(e["body_sha256"] is not None for e in ends),
              "error": sum(e["state"] not in ("observed", "not_invoked") for e in ends),
              "not_invoked": sum(e["state"] == "not_invoked" for e in ends),
              "unfinished": len(intents) - len(ends), "not_asked": sum(v == "not_asked" for v in stages.values()),
              "unknown": prepared["unknown"] if prepared else 1, "overlap": prepared["overlap"] if prepared else 0,
              "stages": stages, "first_invocation": invocation[0] if invocation else None,
              "stop_reason": prepared.get("stop_reason") if prepared else None,
              "started_at": journal.events[0].get("utc"),
              "last_observed_at": next((e["utc"] for e in reversed(journal.events) if "utc" in e), None)}
    if not safe(result) or len(dumps(result)) > REPORT_CAP:
        fail("unsafe_output")
    return result


def read_prepared(runtime, private_dir):
    journal = Journal(runtime)
    prepared = next((e for e in journal.events if e["kind"] == "packet_prepared"), None)
    if prepared is None:
        fail("packet_unprepared")
    size = prepared["packet_bytes"]
    if type(size) is not int or not 0 < size <= PACKET_CAP:
        fail("packet_limit")
    try:
        with (Path(private_dir) / "prepared.bin").open("rb") as handle:
            raw = handle.read(size)
    except OSError:
        fail("input_unavailable")
    if len(raw) != size or sha(raw) != prepared["packet_sha256"]:
        fail("packet_mismatch")
    return parse(raw, PACKET_CAP)


def _recover_partial(journal, private):
    claim = journal.events[0]
    context_raw = read(private / "context.json", PACKET_CAP)
    if sha(context_raw) != claim.get("context_sha256"):
        fail("history_corrupt")
    context = parse(context_raw, PACKET_CAP)
    if context["manifest"] != code_manifest():
        fail("source_drift")
    packet = context["packet"]
    uncertain = False
    dependency_dir = private / "dependencies"
    dependencies = sorted(dependency_dir.glob("*.json")) if dependency_dir.exists() else []
    if len(dependencies) > 256:
        fail("history_corrupt")
    for sequence, dependency_path in enumerate(dependencies, 1):
        if dependency_path.name != "%04d.json" % sequence:
            fail("history_corrupt")
        dependency = parse(read(dependency_path, ROW_CAP), ROW_CAP)
        if dependency.get("kind") == "get":
            endpoint = dependency.get("endpoint")
            if not isinstance(endpoint, str) or len(endpoint) > 4096:
                fail("history_corrupt")
            packet["endpoints"]["engine"].append(endpoint)
    for intent in [e for e in list(journal.events) if e["kind"] == "attempt_intent"]:
        number, role = intent["attempt"], intent["role"]
        directory = private / "attempts" / ("%02d" % number)
        identity_path = directory / "identity.json"
        if not identity_path.exists():
            identity_path = directory / "creation.json"
        if not identity_path.exists():
            # Absence of a PID cannot prove that a possibly spawned child retired.
            fail("cleanup_uncertain")
        identity = parse(read(identity_path, ROW_CAP), ROW_CAP)
        if identity_alive(identity):
            fail("cleanup_uncertain")
        metadata = parse(read(directory / "metadata.json", ROW_CAP), ROW_CAP)
        url = metadata["url"]
        packet["endpoints"]["engine" if role == "engine" else "label"].append(url)
        if role == "reserve":
            packet["endpoints"]["eligibility"].append(url)
        entry = directory / "invocation.json"
        invocation = parse(read(entry, ROW_CAP), ROW_CAP) if entry.exists() else None
        arming = (directory / "arming.json").exists()
        uncertain |= arming and invocation is None
        attempt = {"state": "interrupted_intent", "reason": "interrupted", "status": None,
                   "raw": None, "invocation": invocation}
        if (directory / "headers.json").exists():
            headers = parse(read(directory / "headers.json", ROW_CAP), ROW_CAP)
            attempt.update(status=headers["status"], headers_at=headers["utc"])
        commit_path = directory / "commit.json"
        if commit_path.exists():
            committed = parse(read(commit_path, ROW_CAP), ROW_CAP)
            size = committed["body_bytes"]
            if size:
                with (directory / "body.bin").open("rb") as handle:
                    raw = handle.read(size)
                if len(raw) != size or sha(raw) != committed["body_sha256"]:
                    fail("history_corrupt")
                attempt["raw"] = raw
            attempt.update(state=committed["state"], reason=committed["reason"],
                           response_at=committed.get("response_at", committed["utc"]))
        else:
            attempt["raw"] = captured_prefix(directory)
            ending = directory / "end.json"
            if ending.exists():
                ended = parse(read(ending, ROW_CAP), ROW_CAP)
                if ended.get("state") == "observed" and attempt["raw"] is not None and attempt["status"] is not None:
                    attempt.update(state=("observed" if attempt["status"] == 200 else
                        "http_429" if attempt["status"] == 429 else
                        "http_refusal" if 300 <= attempt["status"] < 500 else "http_failure"),
                        response_at=ended.get("utc"))
        if role != "engine":
            packet[role] = stage_from_attempt(attempt)
        if not any(e["kind"] == "child_retired" and e["attempt"] == number for e in journal.events):
            permit_path = directory / "permit.json"
            permit_hash = sha(read(permit_path, ROW_CAP)) if permit_path.exists() else "0" * 64
            if invocation and not any(e["kind"] == "native_invocation" and e["attempt"] == number for e in journal.events):
                journal.append("native_invocation", attempt=number, permit_sha256=permit_hash,
                               utc=invocation["utc"], monotonic=invocation["monotonic"])
            journal.append("child_retired", attempt=number, permit_sha256=permit_hash,
                           identity_sha256=sha(dumps(identity)), state="exited")
    return seal(journal, private, packet, state="start_uncertain" if uncertain else "prepared")


def recover(store, sources, runtime, *, private_dir, now=None):
    runtime, private = private_paths(runtime, private_dir, store)
    journal = Journal(runtime)
    ordinal = journal.binding["ordinal"]
    directory, value, record, _identity, events = bound_store(store, sources, ordinal)
    if value["plan_sha256"] != journal.binding["plan_sha256"] or record["source_ref"] != journal.binding["source_ref"]:
        fail("history_corrupt")
    if journal.events[0].get("manifest") != code_manifest():
        fail("source_drift")
    first_hash = sha(read(runtime / "events" / "0001.json", ROW_CAP))
    expected_claim = dict(journal.binding, claim_sha256=first_hash)
    actual_claim = parse(read(directory / "native-claims" / ("%08d.json" % ordinal), ROW_CAP), ROW_CAP)
    if actual_claim != expected_claim:
        fail("conflicting_claim")
    claims = producer_claims(directory, value, events)
    own = claims.get(ordinal)
    if own is None:
        fail("conflicting_claim")
    existing = own["receipt"]
    if own["done"]:
        fail("existing_receipt")
    if not any(e["kind"] == "packet_prepared" for e in journal.events):
        if existing is not None:
            fail("packet_unprepared")
        _recover_partial(journal, private)
    for intent in (e for e in journal.events if e["kind"] == "attempt_intent"):
        retirement = next((e for e in journal.events if e["kind"] == "child_retired"
                           and e["attempt"] == intent["attempt"] and e["state"] == "exited"), None)
        if retirement is None:
            fail("cleanup_uncertain")
        attempt_dir = private / "attempts" / ("%02d" % intent["attempt"])
        identity_path = attempt_dir / "identity.json"
        if not identity_path.exists():
            identity_path = attempt_dir / "creation.json"
        if retirement["identity_sha256"] is not None:
            identity = parse(read(identity_path, ROW_CAP), ROW_CAP)
            if sha(dumps(identity)) != retirement["identity_sha256"] or identity_alive(identity):
                fail("cleanup_uncertain")
        elif identity_path.exists() or (attempt_dir / "request.json").exists():
            fail("cleanup_uncertain")
    packet = read_prepared(runtime, private)
    raw = dumps(packet)
    digest = sha(raw)
    producer_results = [e for e in journal.events if e["kind"] == "import_result"]
    if (len(producer_results) > 1 or any(e.get("state") != "imported" or e.get("packet_sha256") != digest for e in producer_results)
            or producer_results and existing is None):
        fail("history_corrupt")
    if existing is not None:
        if existing.get("packet_sha256") != digest:
            fail("packet_mismatch")
        receipt = existing
    else:
        try:
            receipt = core.ingest(store, sources, raw, private_dir=private / "core-import", imported_at=now or iso(Clock().utc()))
        except core.EvidenceError as exc:
            fail(str(exc) if str(exc) in ("existing_receipt", "incomplete_history") else "import_failed")
    # This readback is authoritative even if the producer died after the real core write.
    _d, current_plan, _r, _i, actual_events = bound_store(store, sources, ordinal)
    current_claims = producer_claims(directory, current_plan, actual_events)
    completed = current_claims[ordinal]
    if completed["receipt"] != receipt or receipt.get("packet_sha256") != digest:
        fail("import_uncertain")
    if not producer_results:
        try:
            journal.append("import_result", state="imported", packet_sha256=digest)
        except NativeError:
            # Do not clear an orphan or repair a native journal after a failed write.
            # A clean independently verified readback may still finish the done marker.
            Journal(runtime)
    marker = directory / "native-claims" / ("%08d.done" % ordinal)
    try:
        write_new(marker, dumps(completed["marker"]))
    except NativeError:
        # Concurrent identical producer completion is harmless; partial/conflict is not.
        verified = producer_claims(directory, current_plan, actual_events)[ordinal]
        if not verified["done"]:
            fail("import_uncertain")
    return {"state": "imported", "ordinal": ordinal, "packet_sha256": receipt["packet_sha256"]}


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        fail("invalid_arguments")


def main(argv=None):
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    for name in ("plan", "collect-one", "recover", "report"):
        command = commands.add_parser(name)
        if name != "report":
            command.add_argument("--store", required=True)
            command.add_argument("--sources", required=True)
        if name in ("plan", "collect-one"):
            command.add_argument("--ordinal", type=int, required=True)
        if name != "plan":
            command.add_argument("--runtime", required=True)
        if name in ("collect-one", "recover"):
            command.add_argument("--private-dir", required=True)
        if name == "collect-one":
            command.add_argument("--live", action="store_true")
            command.add_argument("--manifest", required=True)
    try:
        args = parser.parse_args(argv)
        if args.command is None:
            parser.print_help()
            return 0
        if args.command == "report":
            result = report(args.runtime)
        else:
            if args.command == "collect-one":
                # Real CI refusal precedes any file or source read and all writes.
                private_paths(args.runtime, args.private_dir, args.store)
            sources = parse(read(args.sources, REPORT_CAP))
            if args.command == "plan":
                result = plan(args.store, sources, args.ordinal, now=iso(Clock().utc()))
            elif args.command == "recover":
                result = recover(args.store, sources, args.runtime, private_dir=args.private_dir)
            else:
                manifest = parse(read(args.manifest, ROW_CAP), ROW_CAP)
                result = asyncio.run(collect_one(args.store, sources, args.ordinal, runtime=args.runtime,
                    private_dir=args.private_dir, live=args.live, manifest=manifest))
        print(dumps(result).decode())
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except BaseException as exc:
        codes = {"raw_directory_refused", "live_required", "not_due", "source_drift", "source_hash_mismatch",
                 "existing_receipt", "existing_claim", "incomplete_history", "cleanup_uncertain", "packet_mismatch",
                 "invalid_arguments", "input_unavailable", "invalid_store", "history_corrupt", "import_failed"}
        code = str(exc) if isinstance(exc, NativeError) and str(exc) in codes else "operation_failed"
        print(dumps({"error": code}).decode())
        return 2


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--native-child":
        try:
            child_exit = _child(sys.argv[2])
        except BaseException:
            child_exit = 2
        raise SystemExit(child_exit)
    raise SystemExit(main())
