"""Bounded offline seed and immutable archive views; no study or vendor runner."""
import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

ROW_CAP = 64 * 1024
REPORT_CAP = 1024 * 1024
MANIFEST_CAP = 8 * REPORT_CAP
INCREMENT_CAP = 64 * REPORT_CAP
SEED_CAP = 1024 * REPORT_CAP
STUDY_CAP = 16 * SEED_CAP
TERMINAL_RESERVE = 8 * REPORT_CAP
FILE_CAP = 8 * REPORT_CAP
SOURCE_CAP = 128
REFRESH_SECONDS = 60.0
REQUEST_SECONDS = 10.0
SEED_SECONDS = 1200.0
OWNERS = {"bootstrap", "seed", "refresh", "chunks", "runtime", "native", "terminal", "scheduler"}
AREAS = {"control", "source", "raw", "safe", "code", "seed"}
_FROZEN_SOURCES = {"bench/goplus_quota_probe.py", "bench/w40_evidence.py", "src/risk.py",
                   "bench/labels.py", "docs/BACKLOG.md", "tests/test_dataset_replayable.py"}
_GATE_SOURCES = {"source_quality": _FROZEN_SOURCES | {"bench/w40_native.py", "bench/w40_archive.py",
                 "bench/w40_local.py", "tools/w40-local.ps1"},
                 "native_control": _FROZEN_SOURCES | {"bench/w40_native.py"},
                 "quota_pilot": {"bench/goplus_quota_probe.py"}}
STATES = {"not_started", "configuration_required", "accepted", "gap", "terminal", "stopped", "stop_unknown"}
REASONS = {"configuration_required", "ci_refused", "source_drift", "private_path_refused", "invalid_arguments",
           "invalid_binding", "writer_busy", "invalid_lease", "history_corrupt", "storage_refused", "disk_failure",
           "reservation_used", "invalid_inventory", "cleanup_uncertain", "requested", "invalid_clock",
           "clock_continuity_unproven", "source_permission", "source_corrupt", "source_unavailable", "slot_consumed",
           "daily_cap", "request_cap", "deadline", "candidate_limit", "seed_limit", "seed_unavailable",
           "prefix_changed", "invalid_response", "not_live", "stopped", "containment_unavailable", "source_incomplete"}
_LEASES = {}
_NATIVE = None


class ArchiveError(Exception):
    """Only fixed categories cross the private boundary."""


class FrozenDict(dict):
    """JSON-compatible recursively immutable contract data."""
    def _refuse(self, *_args, **_kwargs):
        fail("invalid_binding")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _refuse


def _freeze(value):
    if isinstance(value, dict):
        return FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def fail(reason):
    raise ArchiveError(reason if reason in REASONS else "source_corrupt")


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        fail("source_corrupt")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_value(value, length=64):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{%d}" % length, value) is not None


def parsed(raw, cap=REPORT_CAP):
    if len(raw) > cap:
        fail("source_corrupt")
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=lambda _value: fail("source_corrupt"),
                           object_pairs_hook=_unique)
        stack = [(value, 0)]
        while stack:
            item, depth = stack.pop()
            if depth > 32:
                fail("source_corrupt")
            if isinstance(item, dict):
                stack.extend((x, depth + 1) for x in item.values())
            elif isinstance(item, list):
                stack.extend((x, depth + 1) for x in item)
        return value
    except (ValueError, UnicodeError, RecursionError, TypeError):
        fail("source_corrupt")


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            fail("source_corrupt")
        result[key] = value
    return result


def private(path, *, missing=False):
    try:
        path = Path(os.path.abspath(os.fspath(path)))
        for ancestor in reversed((path, *path.parents)):
            try:
                info = ancestor.lstat()
            except FileNotFoundError:
                if not missing:
                    fail("private_path_refused")
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                fail("private_path_refused")
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                fail("private_path_refused")
            if not stat.S_ISDIR(info.st_mode) and ancestor != path:
                fail("private_path_refused")
            if stat.S_ISDIR(info.st_mode) and (ancestor / ".git").exists():
                fail("private_path_refused")
        return path
    except (OSError, TypeError, ValueError):
        fail("private_path_refused")


def under(root, relative, *, missing=False):
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or relative.startswith("/") or any(x in ("", ".", "..") for x in relative.split("/"))):
        fail("private_path_refused")
    path = private(Path(root) / relative, missing=missing)
    # private(path) just validated the root and every ancestor as well.
    if not path.is_relative_to(Path(os.path.abspath(os.fspath(root)))):
        fail("private_path_refused")
    return path


def read(path, cap):
    try:
        blocks, size = [], 0
        with private(path).open("rb") as handle:
            while True:
                block = handle.read(min(ROW_CAP, cap + 1 - size))
                if not block:
                    return b"".join(blocks)
                size += len(block)
                if size > cap:
                    fail("source_corrupt")
                blocks.append(block)
    except OSError:
        fail("source_unavailable")


def file_hash(path, *, check=None):
    return _hash_regular(private(path), check=check)


def _hash_regular(path, *, check=None):
    """Hash immediately after the caller validated this exact private path."""
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("rb") as handle:
            while True:
                if check:
                    check()
                block = handle.read(ROW_CAP)
                if not block:
                    break
                size += len(block)
                digest.update(block)
        return size, digest.hexdigest()
    except OSError:
        fail("source_unavailable")


def write_new(path, raw):
    try:
        path = private(path, missing=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if read(path, max(len(raw), 1)) != raw:
            fail("disk_failure")
    except OSError:
        fail("disk_failure")


def ci_guard():
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        fail("ci_refused")


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        fail("invalid_clock")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class Clock:
    def utc(self):
        return datetime.now(timezone.utc)

    def mono(self):
        return time.monotonic()

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class FrozenBinding:
    __slots__ = ("config_path", "config_pin", "manifest_pin", "config", "manifest", "roots", "identity")

    def __init__(self, config_path, config_pin, manifest_pin, config, manifest):
        object.__setattr__(self, "config_path", config_path)
        object.__setattr__(self, "config_pin", config_pin)
        object.__setattr__(self, "manifest_pin", manifest_pin)
        object.__setattr__(self, "config", MappingProxyType(_freeze(config)))
        object.__setattr__(self, "manifest", MappingProxyType(_freeze(manifest)))
        object.__setattr__(self, "roots", MappingProxyType({k: Path(v) for k, v in config["roots"].items()}))
        object.__setattr__(self, "identity", sha(encoded(dict(study=config["study_id_sha256"], config=config_pin, code=manifest_pin))))

    def __setattr__(self, _key, _value):
        fail("invalid_binding")


def verify_install(config_path, *, expected_config_sha256, expected_manifest_sha256, component):
    if component not in ("archive", "runtime", "scheduler") or not all(hex_value(x) for x in (expected_config_sha256, expected_manifest_sha256)):
        fail("source_drift")
    config_path = private(config_path)
    raw = read(config_path, REPORT_CAP)
    if sha(raw) != expected_config_sha256:
        fail("source_drift")
    config = parsed(raw)
    keys = {"schema", "study_id_sha256", "executable_commit", "code_manifest_sha256", "manifest", "roots",
            "archive_origin", "seed", "task", "quality_gates"}
    if (not isinstance(config, dict) or set(config) != keys or config["schema"] != "w40-install-v1"
            or config["code_manifest_sha256"] != expected_manifest_sha256
            or not hex_value(config["study_id_sha256"]) or not hex_value(config["executable_commit"], 40)
            or not isinstance(config["roots"], dict) or set(config["roots"]) != AREAS):
        fail("source_drift")
    roots = {k: private(v) for k, v in config["roots"].items()}
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a) for k, a in roots.items() for j, b in roots.items() if k < j):
        fail("private_path_refused")
    origin = config["archive_origin"]
    if (not isinstance(origin, dict) or set(origin) != {"owner", "repo", "ref", "api_version", "verification_sha256"}
            or any(not isinstance(origin[k], str) or not re.fullmatch("[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", origin[k]) for k in ("owner", "repo"))
            or origin["ref"] != "refs/heads/master" or origin["api_version"] != "2026-03-10" or not hex_value(origin["verification_sha256"])):
        fail("source_drift")
    seed_value = config["seed"]
    if (not isinstance(seed_value, dict) or set(seed_value) != {"manifest", "manifest_sha256", "receipt", "receipt_sha256"}
            or not all(hex_value(seed_value[k]) for k in ("manifest_sha256", "receipt_sha256"))
            or seed_value["receipt_sha256"] != origin["verification_sha256"]):
        fail("source_drift")
    for field in ("manifest", "receipt"):
        under(roots["seed"], seed_value[field], missing=True)
    if config["task"] != {"task_path": "\\VetAgent\\W40\\", "name": "W40-" + config["study_id_sha256"]} or not isinstance(config["quality_gates"], list):
        fail("source_drift")
    manifest_raw = read(private(config["manifest"]), MANIFEST_CAP)
    if sha(manifest_raw) != expected_manifest_sha256:
        fail("source_drift")
    manifest = parsed(manifest_raw, MANIFEST_CAP)
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "files", "interpreter", "powershell"} or manifest["schema"] != "w40-code-v1":
        fail("source_drift")
    seen = set()
    for record in manifest["files"]:
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"} or record["path"] in seen:
            fail("source_drift")
        seen.add(record["path"])
        if _hash_regular(under(roots["code"], record["path"])) != (record["bytes"], record["sha256"]):
            fail("source_drift")
    if "bench/w40_archive.py" not in seen or Path(__file__).resolve() != (roots["code"] / "bench/w40_archive.py").resolve():
        fail("source_drift")
    interpreter = manifest["interpreter"]
    if not isinstance(interpreter, dict) or set(interpreter) != {"path", "sha256", "prefix", "base_prefix", "origins", "pyvenv_cfg"}:
        fail("source_drift")
    executable = private(interpreter["path"])
    if (executable != Path(sys.executable).resolve() or sha(read(executable, INCREMENT_CAP)) != interpreter["sha256"]
            or private(interpreter["prefix"]) != Path(sys.prefix).resolve()
            or private(interpreter["base_prefix"]) != Path(sys.base_prefix).resolve()):
        fail("source_drift")
    cfg = interpreter["pyvenv_cfg"]
    if cfg is None:
        prefix = private(interpreter["prefix"])
        if (prefix != private(interpreter["base_prefix"]) or not sys.flags.no_user_site
                or under(prefix, "pyvenv.cfg", missing=True).exists()
                or Path(getattr(sys, "_base_executable", sys.executable)).resolve() != executable
                or not prefix.is_relative_to(roots["code"])):
            fail("source_drift")
        # A direct base has no venv redirector/config to bind. Its complete
        # installed interpreter/stdlib/DLL tree must instead be in the already
        # verified code closure, including every actual loaded stdlib origin.
        for path in prefix.rglob("*"):
            info = path.lstat()
            if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024
                    or path.name == ".git" or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
                fail("source_drift")
            if stat.S_ISREG(info.st_mode) and path.relative_to(roots["code"]).as_posix() not in seen:
                fail("source_drift")
        for name, module in tuple(sys.modules.items()):
            if name.split(".", 1)[0] in sys.stdlib_module_names and getattr(module, "__file__", None):
                path = private(module.__file__)
                if not path.is_relative_to(prefix) or path.relative_to(roots["code"]).as_posix() not in seen:
                    fail("source_drift")
    else:
        if not isinstance(cfg, dict) or set(cfg) != {"path", "sha256"}:
            fail("source_drift")
        cfg_raw = read(private(cfg["path"]), ROW_CAP)
        if (sha(cfg_raw) != cfg["sha256"] or b"include-system-site-packages = false" not in cfg_raw.lower()
                or private(cfg["path"]) != Path(sys.prefix).resolve() / "pyvenv.cfg"):
            fail("source_drift")
    sites = [Path(sys.prefix) / "Lib/site-packages", *Path(sys.prefix).glob("lib/python*/site-packages")]
    if any(any(private(site).iterdir()) for site in sites if site.exists()):
        fail("source_drift")
    for record in interpreter["origins"]:
        path = private(record["path"])
        if sha(read(path, MANIFEST_CAP)) != record["sha256"]:
            fail("source_drift")
        loaded = sys.modules.get(record["module"])
        if loaded is not None and getattr(loaded, "__file__", None) and Path(loaded.__file__).resolve() != path:
            fail("source_drift")
    if manifest["powershell"] is not None:
        powershell = manifest["powershell"]
        if not isinstance(powershell, dict) or set(powershell) != {"path", "sha256"} or sha(read(private(powershell["path"]), INCREMENT_CAP)) != powershell["sha256"]:
            fail("source_drift")
    binding = FrozenBinding(config_path, expected_config_sha256, expected_manifest_sha256, config, manifest)
    _prior_gates(binding)
    return binding


def _prior_gates(binding, *, complete=False):
    """Verify only backward-bound attestations, never infer runtime credit."""
    try:
        refs = binding.config["quality_gates"]
        if len(refs) > 3 or complete and len(refs) != 3:
            fail("source_drift")
        seen = set()
        manifest = {record["path"]: record for record in binding.manifest["files"]}
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {"kind", "path", "sha256"}
                    or ref["kind"] not in _GATE_SOURCES or ref["kind"] in seen
                    or ref["path"] != "quality-gates/" + ref["kind"] + ".json" or not hex_value(ref["sha256"])):
                fail("source_drift")
            kind = ref["kind"]
            seen.add(kind)
            raw = read(under(binding.roots["control"], ref["path"]), ROW_CAP)
            value = parsed(raw, ROW_CAP)
            if (sha(raw) != ref["sha256"] or encoded(value) != raw or not isinstance(value, dict)
                    or set(value) != {"schema", "kind", "source_commit", "source_files", "evidence", "result"}
                    or value["schema"] != "w40-prior-gate-v1" or value["kind"] != kind
                    or not hex_value(value["source_commit"], 40)
                    or kind == "source_quality" and value["source_commit"] != binding.config["executable_commit"]):
                fail("source_drift")
            files = value["source_files"]
            if not isinstance(files, list) or len(files) != len(_GATE_SOURCES[kind]):
                fail("source_drift")
            paths = []
            for record in files:
                if (not isinstance(record, dict) or set(record) != {"path", "canonical_sha256"}
                        or record["path"] not in _GATE_SOURCES[kind] or not hex_value(record["canonical_sha256"])
                        or record["path"] not in manifest):
                    fail("source_drift")
                path = under(binding.roots["code"], record["path"])
                actual = read(path, MANIFEST_CAP)
                bound = manifest[record["path"]]
                if ((len(actual), sha(actual)) != (bound["bytes"], bound["sha256"])
                        or sha(actual.replace(b"\r\n", b"\n")) != record["canonical_sha256"]):
                    fail("source_drift")
                paths.append(record["path"])
            if paths != sorted(_GATE_SOURCES[kind]):
                fail("source_drift")
            evidence = value["evidence"]
            if (not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}
                    or evidence["path"] != "quality-gates/evidence/" + kind + ".json"
                    or not hex_value(evidence["sha256"])
                    or sha(read(under(binding.roots["control"], evidence["path"]), REPORT_CAP)) != evidence["sha256"]):
                fail("source_drift")
            result = value["result"]
            if not isinstance(result, dict):
                fail("source_drift")
            if kind == "source_quality":
                if (set(result) != {"passed", "offline_steps", "linux_steps", "master_steps", "locked_builds", "independent", "redteam"}
                        or result["passed"] is not True or type(result["locked_builds"]) is not int or result["locked_builds"] != 2
                        or result["independent"] != "pass" or result["redteam"] != "none"
                        or any(type(result[key]) is not int or result[key] < 47 for key in ("offline_steps", "linux_steps", "master_steps"))
                        or not result["offline_steps"] == result["linux_steps"] == result["master_steps"]):
                    fail("source_drift")
            elif kind == "quota_pilot":
                if (set(result) != {"completed", "native_exit", "availability"} or result["completed"] is not True
                        or type(result["native_exit"]) is not int or result["native_exit"] not in (0, 1)
                        or type(result["availability"]) is not bool):
                    fail("source_drift")
            elif (set(result) != {"seam_verified", "native_exit", "labels", "scientific_start"}
                    or result["seam_verified"] is not True or type(result["native_exit"]) is not int or result["native_exit"] != 0
                    or type(result["labels"]) is not int or result["labels"] != 0 or result["scientific_start"] is not False):
                fail("source_drift")
        if complete and (seen != set(_GATE_SOURCES) or binding.manifest["powershell"] is None):
            fail("source_drift")
    except (ArchiveError, KeyError, TypeError, ValueError, AttributeError, OSError):
        fail("source_drift")


def verify_live(binding) -> None:
    """Read-only production admission; synthetic fixtures convey no host authority."""
    try:
        guard(binding)
        current = verify_install(binding.config_path, expected_config_sha256=binding.config_pin,
                                 expected_manifest_sha256=binding.manifest_pin, component="archive")
        _prior_gates(current, complete=True)
    except (ArchiveError, KeyError, TypeError, ValueError, AttributeError, OSError):
        fail("source_drift")


def guard(binding, *, mutate=False):
    if mutate:
        ci_guard()
    if not isinstance(binding, FrozenBinding):
        fail("invalid_binding")
    if (sha(read(binding.config_path, REPORT_CAP)) != binding.config_pin
            or sha(read(private(binding.config["manifest"]), MANIFEST_CAP)) != binding.manifest_pin):
        fail("source_drift")
    for root in binding.roots.values():
        private(root)


class WriterLease:
    def __init__(self, binding, handle):
        self.binding, self.handle, self.pid, self.thread = binding, handle, os.getpid(), threading.get_ident()
        self.active = True


def lease_guard(binding, lease):
    guard(binding, mutate=True)
    if (type(lease) is not WriterLease or not lease.active or lease.binding is not binding
            or lease.pid != os.getpid() or lease.thread != threading.get_ident()
            or _LEASES.get(str(binding.roots["control"])) is not lease):
        fail("invalid_lease")


@contextlib.contextmanager
def study_writer(binding):
    guard(binding, mutate=True)
    key = str(binding.roots["control"])
    if key in _LEASES:
        fail("writer_busy")
    handle = None
    try:
        handle = under(binding.roots["control"], "writer.lock").open("r+b")
        os.set_inheritable(handle.fileno(), False)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if handle:
            handle.close()
        fail("writer_busy")
    lease = WriterLease(binding, handle)
    _LEASES[key] = lease
    try:
        yield lease
    finally:
        lease.active = False
        _LEASES.pop(key, None)
        handle.close()


def journal(binding, name):
    directory = under(binding.roots["control"], name, missing=True)
    if not directory.exists():
        return []
    result, previous = [], "0" * 64
    files = sorted(directory.iterdir())
    for number, path in enumerate(files, 1):
        if path.name != "%08d.json" % number:
            fail("history_corrupt")
        raw = read(path, ROW_CAP)
        value = parsed(raw, ROW_CAP)
        if (set(value) != {"schema", "sequence", "previous", "binding", "kind", "value"}
                or value["schema"] != "w40-ledger-v1" or value["sequence"] != number
                or value["previous"] != previous or value["binding"] != binding.identity):
            fail("history_corrupt")
        previous = sha(raw)
        result.append(dict(value, digest=previous))
    return result


def append(binding, lease, name, kind, value):
    lease_guard(binding, lease)
    records = journal(binding, name)
    raw = encoded(dict(schema="w40-ledger-v1", sequence=len(records) + 1,
                       previous=records[-1]["digest"] if records else "0" * 64,
                       binding=binding.identity, kind=kind, value=value))
    if len(raw) > ROW_CAP:
        fail("storage_refused")
    path = under(binding.roots["control"], name + "/%08d.json" % (len(records) + 1), missing=True)
    write_new(path, raw)
    return sha(raw)


def measured(binding, *, hashes=False, areas=None):
    result = []
    areas = AREAS if areas is None else set(areas)
    if areas - AREAS:
        fail("invalid_inventory")
    for area, root in sorted(binding.roots.items()):
        if area not in areas:
            continue
        for path in sorted(root.rglob("*")):
            private(path)
            if path.is_file():
                value = dict(area=area, path=path.relative_to(root).as_posix(), bytes=path.stat().st_size)
                if hashes:
                    # The installed empty lock is already held by this process.
                    # Windows rejects even an EOF read across its locked byte.
                    # Its fixed zero-length inventory is still fully charged.
                    if area == "control" and value["path"] == "writer.lock":
                        if value["bytes"] != 0:
                            fail("history_corrupt")
                        value["sha256"] = sha(b"")
                    else:
                        value["sha256"] = _hash_regular(path)[1]
                result.append(value)
    for label, path in (("config", binding.config_path), ("manifest", Path(binding.config["manifest"]))):
        if "code" in areas and not any(path.is_relative_to(root) for root in binding.roots.values()):
            value = dict(area="code", path="@" + label, bytes=path.stat().st_size)
            if hashes:
                value["sha256"] = file_hash(path)[1]
            result.append(value)
    return result


def allocation_state(binding):
    tickets, receipts = {}, {}
    for record in journal(binding, "allocation"):
        value = record["value"]
        if record["kind"] == "reservation":
            identity = value["reservation_id"]
            if identity in tickets:
                fail("history_corrupt")
            tickets[identity] = value
        elif record["kind"] == "settlement":
            identity = value["reservation_id"]
            if identity not in tickets or identity in receipts or value["ticket_sha256"] != sha(encoded(tickets[identity])):
                fail("history_corrupt")
            receipts[identity] = dict(value, receipt_sha256=record["digest"])
        else:
            fail("history_corrupt")
    retained = sum(x["bytes"] for x in measured(binding))
    pending = sum(sum(x["ceilings"].values()) for key, x in tickets.items() if key not in receipts)
    return tickets, receipts, retained, pending


def reserve(binding, lease, *, reservation_id, owner, ceilings):
    lease_guard(binding, lease)
    if (not hex_value(reservation_id) or owner not in OWNERS or not isinstance(ceilings, dict)
            or not ceilings or set(ceilings) - AREAS or any(type(x) is not int or x < 0 for x in ceilings.values())):
        fail("storage_refused")
    tickets, receipts, retained, pending = allocation_state(binding)
    if reservation_id in tickets:
        fail("reservation_used")
    amount = sum(ceilings.values())
    if retained + pending + amount + TERMINAL_RESERVE > STUDY_CAP:
        fail("storage_refused")
    volumes = {}
    for outstanding in [ceilings, *(value["ceilings"] for key, value in tickets.items() if key not in receipts)]:
        for area, size in outstanding.items():
            root = binding.roots[area]
            volume = root.stat().st_dev
            total, _root = volumes.get(volume, (0, root))
            volumes[volume] = (total + size, root)
    root = binding.roots["control"]
    volume = root.stat().st_dev
    total, _root = volumes.get(volume, (0, root))
    volumes[volume] = (total + TERMINAL_RESERVE, root)
    for size, root in volumes.values():
        if shutil.disk_usage(root).free < size:
            fail("storage_refused")
    baseline = measured(binding, hashes=True)
    baseline_raw = encoded(baseline)
    if len(baseline_raw) > MANIFEST_CAP:
        fail("storage_refused")
    baseline_ref = "allocation-baselines/" + reservation_id + ".json"
    ticket = dict(schema="w40-allocation-ticket-v1", study_id_sha256=binding.config["study_id_sha256"],
                  config_sha256=binding.config_pin, code_manifest_sha256=binding.manifest_pin,
                  reservation_id=reservation_id, owner=owner, ceilings=dict(ceilings),
                  baseline=baseline_ref, baseline_sha256=sha(baseline_raw),
                  prior_head=(journal(binding, "allocation")[-1]["digest"] if tickets or receipts else "0" * 64))
    write_new(under(binding.roots["control"], baseline_ref, missing=True), baseline_raw)
    append(binding, lease, "allocation", "reservation", ticket)
    return MappingProxyType(_freeze(ticket))


def inventory(binding):
    return measured(binding, hashes=True)


def _inventory_reference(binding, value):
    if (not isinstance(value, dict) or set(value) != {"area", "path", "bytes", "sha256"}
            or value["area"] not in AREAS or not isinstance(value["path"], str)
            or type(value["bytes"]) is not int or value["bytes"] < 0 or not hex_value(value["sha256"])):
        fail("invalid_inventory")
    if value["area"] == "code" and value["path"] in ("@config", "@manifest"):
        return private(binding.config_path if value["path"] == "@config" else binding.config["manifest"])
    return under(binding.roots[value["area"]], value["path"])


def _verify_inventory_entry(binding, value):
    path = _inventory_reference(binding, value)
    if value["area"] == "control" and value["path"] == "writer.lock":
        if path.stat().st_size != 0 or (value["bytes"], value["sha256"]) != (0, sha(b"")):
            fail("invalid_inventory")
    elif _hash_regular(path) != (value["bytes"], value["sha256"]):
        fail("invalid_inventory")


def settle(binding, lease, ticket, *, inventory):
    lease_guard(binding, lease)
    ticket = dict(ticket)
    tickets, receipts, retained, pending = allocation_state(binding)
    identity = ticket.get("reservation_id")
    if tickets.get(identity) != ticket or identity in receipts:
        fail("invalid_inventory")
    if not isinstance(inventory, list):
        fail("invalid_inventory")
    seen = set()
    for entry in inventory:
        _verify_inventory_entry(binding, entry)
        if (entry["area"], entry["path"]) in seen:
            fail("invalid_inventory")
        seen.add((entry["area"], entry["path"]))
    actual = measured(binding)
    if {(entry["area"], entry["path"], entry["bytes"]) for entry in actual} != {
            (entry["area"], entry["path"], entry["bytes"]) for entry in inventory}:
        fail("invalid_inventory")
    baseline_raw = read(under(binding.roots["control"], ticket["baseline"]), MANIFEST_CAP)
    if sha(baseline_raw) != ticket["baseline_sha256"]:
        fail("invalid_inventory")
    baseline = parsed(baseline_raw, MANIFEST_CAP)
    for entry in baseline:
        _verify_inventory_entry(binding, entry)
    old_sizes = {area: sum(x["bytes"] for x in baseline if x["area"] == area) for area in AREAS}
    current = measured(binding)
    for area in AREAS:
        growth = sum(x["bytes"] for x in current if x["area"] == area) - old_sizes[area]
        if growth > ticket["ceilings"].get(area, 0):
            fail("storage_refused")
    for entry in inventory:
        if entry["area"] in {"control", "source", "raw", "safe"} and entry["path"].split("/")[-1] == "creation.json":
            identity_value = parsed(read(_inventory_reference(binding, entry), ROW_CAP), ROW_CAP)
            if (not isinstance(identity_value, dict) or set(identity_value) != {"pid", "creation", "token", "parent"}
                    or type(identity_value["pid"]) is not int or identity_value["pid"] <= 0
                    or type(identity_value["parent"]) is not int or identity_value["parent"] <= 0
                    or not isinstance(identity_value["creation"], str) or not identity_value["creation"].isdigit()
                    or not hex_value(identity_value["token"], 32)):
                fail("cleanup_uncertain")
            try:
                alive = _native(binding).identity_alive(identity_value)
            except Exception:
                fail("cleanup_uncertain")
            if alive:
                fail("cleanup_uncertain")
    for record in journal(binding, "archive"):
        value = record["value"]
        if record["kind"] == "attempt" and value["transaction_id"] == identity:
            attempt = under(binding.roots["source"], value["directory"])
            _verify_retired(binding, attempt)
    raw = encoded(inventory)
    if len(raw) > MANIFEST_CAP:
        fail("storage_refused")
    reference = "allocation-inventories/" + identity + ".json"
    write_new(under(binding.roots["control"], reference, missing=True), raw)
    value = dict(schema="w40-allocation-receipt-v1", reservation_id=identity, ticket_sha256=sha(encoded(ticket)),
                 inventory=reference, inventory_sha256=sha(raw), retained_bytes=retained,
                 released_bytes=max(0, sum(ticket["ceilings"].values()) - max(0, retained - sum(x["bytes"] for x in baseline))))
    digest = append(binding, lease, "allocation", "settlement", value)
    return dict(value, receipt_sha256=digest)


def verify_inventory(binding, receipt):
    raw = read(under(binding.roots["control"], receipt["inventory"]), MANIFEST_CAP)
    if sha(raw) != receipt["inventory_sha256"]:
        fail("invalid_inventory")
    seen = set()
    for value in parsed(raw, MANIFEST_CAP):
        _verify_inventory_entry(binding, value)
        key = value["area"], value["path"]
        if key in seen:
            fail("invalid_inventory")
        seen.add(key)


def stop_state(binding):
    guard(binding)
    path = under(binding.roots["control"], "stop-request.json", missing=True)
    if not path.exists():
        return {"state": "not_started", "reason": None}
    try:
        value = parsed(read(path, ROW_CAP), ROW_CAP)
        if set(value) != {"schema", "binding", "reason"} or value["schema"] != "w40-stop-v1" or value["binding"] != binding.identity or value["reason"] not in REASONS:
            fail("history_corrupt")
        return {"state": "stopped", "reason": value["reason"]}
    except ArchiveError:
        return {"state": "stop_unknown", "reason": "cleanup_uncertain"}


def request_stop(binding, *, reason):
    guard(binding, mutate=True)
    if reason not in REASONS:
        fail("invalid_arguments")
    prior = stop_state(binding)
    if prior["state"] != "not_started":
        return prior
    raw = encoded(dict(schema="w40-stop-v1", binding=binding.identity, reason=reason))
    path = under(binding.roots["control"], "stop-request.json", missing=True)
    try:
        write_new(path, raw)
    except ArchiveError:
        if not path.exists():
            fail("disk_failure")
    return stop_state(binding)


def _native(binding):
    global _NATIVE
    guard(binding)
    # Recheck the pinned import bytes before executing an acquisition module.
    # The binding's earlier verification is not evidence of unchanged disk bytes.
    for record in binding.manifest["files"]:
        if _hash_regular(under(binding.roots["code"], record["path"])) != (record["bytes"], record["sha256"]):
            fail("source_drift")
    path = under(binding.roots["code"], "bench/w40_native.py")
    if _NATIVE is None:
        bench = str(path.parent)
        for name in ("w40_evidence", "labels"):
            loaded = sys.modules.get(name)
            if loaded is not None and Path(loaded.__file__).resolve().parent != path.parent:
                fail("source_drift")
        if bench not in sys.path:
            sys.path.insert(0, bench)
        spec = importlib.util.spec_from_file_location("w40_archive_native", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _NATIVE = module
    elif Path(_NATIVE.__file__).resolve() != path:
        fail("source_drift")
    return _NATIVE


def _snapshot(clock):
    try:
        wall, mono = clock.utc(), clock.mono()
        if type(mono) not in (int, float) or not math.isfinite(mono) or mono < 0:
            fail("invalid_clock")
        return {"utc": utc(wall), "mono": float(mono)}
    except (AttributeError, ValueError, TypeError, OverflowError):
        fail("invalid_clock")


def _check(binding, clock, start, deadline, *, allowance=0, date=None):
    guard(binding)
    if stop_state(binding)["state"] != "not_started":
        fail("stopped")
    sample = _snapshot(clock)
    if sample["mono"] < start["mono"] or sample["utc"] < start["utc"]:
        fail("invalid_clock")
    wall = datetime.fromisoformat(sample["utc"].replace("Z", "+00:00"))
    midnight = wall.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if sample["mono"] + allowance > deadline or date is not None and sample["utc"][:10] != date or (midnight - wall).total_seconds() < allowance:
        fail("deadline")
    return sample


def _archive_state(binding):
    claims, results, attempts = {}, {}, []
    for record in journal(binding, "archive"):
        kind, value = record["kind"], record["value"]
        identity = value.get("transaction_id")
        if kind == "claim":
            if not hex_value(identity) or identity in claims:
                fail("history_corrupt")
            claims[identity] = dict(value, claim_sha256=record["digest"])
        elif kind == "attempt":
            if identity not in claims or identity in results:
                fail("history_corrupt")
            attempts.append(value)
        elif kind == "result":
            if identity not in claims or identity in results or value["state"] not in ("accepted", "gap", "terminal"):
                fail("history_corrupt")
            results[identity] = dict(value, transaction_receipt_sha256=record["digest"])
        else:
            fail("history_corrupt")
    return claims, results, attempts


def _verify_retired(binding, directory):
    private(directory)
    retired_path = directory / "retired.json"
    if not retired_path.exists():
        fail("cleanup_uncertain")
    retired = parsed(read(retired_path, ROW_CAP), ROW_CAP)
    if set(retired) != {"state", "identity_sha256"} or retired["state"] != "exited":
        fail("cleanup_uncertain")
    identity_path = directory / "creation.json"
    if identity_path.exists():
        identity = parsed(read(identity_path, ROW_CAP), ROW_CAP)
        if sha(encoded(identity)) != retired["identity_sha256"] or _native(binding).identity_alive(identity):
            fail("cleanup_uncertain")
    elif retired["identity_sha256"] is not None or (directory / "request.json").exists():
        fail("cleanup_uncertain")
    return retired


def _source_result(binding, lease, transaction, state, reason, *, view=None, examined=0, unexamined=0, partial=0):
    value = dict(schema="w40-source-result-v1", transaction_id=transaction, state=state, reason=reason,
                 view_sha256=view, examined=examined, unexamined=unexamined, partial=partial)
    digest = append(binding, lease, "archive", "result", value)
    return dict(value, transaction_receipt_sha256=digest, allocation_receipt_sha256=None)


def _public_result(result, receipt=None):
    keys = ("schema", "state", "reason", "view_sha256", "examined", "unexamined", "partial", "transaction_receipt_sha256")
    value = {key: result.get(key) for key in keys}
    value["allocation_receipt_sha256"] = receipt["receipt_sha256"] if receipt else None
    return value


def _visible_views(binding):
    claims, results, _attempts = _archive_state(binding)
    _tickets, receipts, _retained, _pending = allocation_state(binding)
    views, previous = [], None
    for identity, result in results.items():
        if result["state"] != "accepted" or identity not in receipts:
            continue
        verify_inventory(binding, receipts[identity])
        digest = result["view_sha256"]
        raw = read(under(binding.roots["source"], "views/" + digest + ".json"), MANIFEST_CAP)
        value = parsed(raw, MANIFEST_CAP)
        unhashed = dict(value)
        unhashed.pop("view_sha256", None)
        if (sha(encoded(unhashed)) != digest or value["view_sha256"] != digest
                or value["schema"] != "w40-source-view-v1" or value["sequence"] != len(views) + 1
                or value["previous_view_sha256"] != previous or value["config_sha256"] != binding.config_pin
                or value["code_manifest_sha256"] != binding.manifest_pin
                or value["study_id_sha256"] != binding.config["study_id_sha256"]
                or value["claim_sha256"] != claims[identity]["claim_sha256"]):
            fail("history_corrupt")
        for entry in value["catalog"]:
            blob = under(binding.roots["source"], entry["object"])
            if file_hash(blob) != (entry["bytes"], entry["sha256"]):
                fail("source_corrupt")
            digest1 = hashlib.sha1(b"blob " + str(entry["bytes"]).encode() + b"\0")
            with blob.open("rb") as handle:
                while block := handle.read(ROW_CAP):
                    digest1.update(block)
            if digest1.hexdigest() != entry["blob_sha1"]:
                fail("source_corrupt")
            for chunk in entry["chunks"]:
                if file_hash(under(binding.roots["source"], chunk["object"])) != (chunk["bytes"], chunk["sha256"]):
                    fail("source_corrupt")
        views.append(_freeze(value))
        previous = digest
    return views


def accepted_view(binding):
    guard(binding)
    views = _visible_views(binding)
    return views[-1] if views else None


def _scan(path, *, check=None):
    offset, number = 0, 0
    with private(path).open("rb") as handle:
        while True:
            if check:
                check()
            start = offset
            raw = handle.readline(ROW_CAP)
            if not raw:
                return
            size, digest = len(raw), hashlib.sha256(raw)
            offset += len(raw)
            oversized = len(raw) > ROW_CAP
            stored = raw if not oversized else None
            while raw[-1:] != b"\n":
                block = handle.readline(ROW_CAP)
                if not block:
                    yield dict(line=number + 1, offset=start, bytes=size, sha256=digest.hexdigest(),
                               raw=None, finding="partial", complete=False)
                    return
                offset += len(block)
                size += len(block)
                digest.update(block)
                oversized, stored, raw = True, None, block
            number += 1
            finding = "row_cap" if oversized else None
            if not oversized:
                try:
                    if not isinstance(parsed(stored, ROW_CAP), dict):
                        finding = "invalid_row"
                except ArchiveError:
                    finding = "invalid_row"
            yield dict(line=number, offset=start, bytes=size, sha256=digest.hexdigest(), raw=stored,
                       finding=finding, complete=True)


def iter_complete_rows(binding, view, *, after_view_sha256=None):
    guard(binding)
    views = _visible_views(binding)
    identities = [x["view_sha256"] for x in views]
    if not isinstance(view, dict) or view not in views or after_view_sha256 is not None and after_view_sha256 not in identities:
        fail("source_corrupt")
    last = identities.index(view["view_sha256"])
    first = identities.index(after_view_sha256) + 1 if after_view_sha256 is not None else 0
    if first > last + 1:
        fail("source_corrupt")
    old_counts = {}
    for position, current in enumerate(views[:last + 1]):
        for entry in current["catalog"]:
            prior = old_counts.get(entry["path"], 0)
            if position >= first:
                for row in _scan(under(binding.roots["source"], entry["object"])):
                    if row["complete"] and row["line"] > prior:
                        value = {key: row[key] for key in ("line", "offset", "bytes", "sha256", "raw", "finding")}
                        value.update(view_sha256=current["view_sha256"], path=entry["path"], blob_sha1=entry["blob_sha1"],
                                     chunk_sha256=entry["prefix_sha256"])
                        yield value
            old_counts[entry["path"]] = entry["complete_lines"]


def _pool_path(path):
    if not isinstance(path, str) or re.fullmatch(r"bench/snapshots/pools-\d{4}-\d{2}-\d{2}\.ndjson", path) is None:
        fail("source_corrupt")
    try:
        datetime.strptime(path[len("bench/snapshots/pools-"):-len(".ndjson")], "%Y-%m-%d")
    except ValueError:
        fail("source_corrupt")
    return path


def _catalog(catalog, *, seed_input=False):
    if not isinstance(catalog, list) or not 1 <= len(catalog) <= SOURCE_CAP:
        fail("source_incomplete" if not catalog else "candidate_limit")
    seen, previous = set(), None
    for value in catalog:
        expected = {"path", "mode", "type", "sha", "bytes", "sha256", "object"} if seed_input else {"path", "mode", "type", "sha", "bytes"}
        if not isinstance(value, dict) or set(value) != expected:
            fail("source_corrupt")
        path = _pool_path(value["path"])
        if path in seen or previous is not None and path.encode() <= previous.encode():
            fail("source_corrupt")
        seen.add(path)
        previous = path
        if value["mode"] != "100644" or value["type"] != "blob" or not hex_value(value["sha"], 40) or type(value["bytes"]) is not int or value["bytes"] < 0:
            fail("source_corrupt")
        if seed_input and (not hex_value(value["sha256"]) or value["bytes"] > FILE_CAP):
            fail("seed_limit")
    return catalog


def _framed_object(raw, identity, kind):
    if not hex_value(identity, 40) or hashlib.sha1(raw).hexdigest() != identity:
        fail("source_corrupt")
    head, separator, body = raw.partition(b"\0")
    if not separator or head != kind.encode() + b" " + str(len(body)).encode():
        fail("source_corrupt")
    return body


def _git_tree(body):
    result = []
    while body:
        header, separator, tail = body.partition(b"\0")
        if not separator or len(tail) < 20:
            fail("source_corrupt")
        try:
            mode, name = header.decode("utf-8").split(" ", 1)
        except (UnicodeError, ValueError):
            fail("source_corrupt")
        if not name or "/" in name or "\\" in name or name in (".", "..") or any(x["path"] == name for x in result):
            fail("source_corrupt")
        result.append(dict(path=name, mode="040000" if mode == "40000" else mode,
                           type="tree" if mode == "40000" else "blob" if mode == "100644" else "other", sha=tail[:20].hex()))
        body = tail[20:]
    return result


def _seed_input(binding):
    config = binding.config["seed"]
    raw = read(under(binding.roots["seed"], config["manifest"]), MANIFEST_CAP)
    receipt_raw = read(under(binding.roots["seed"], config["receipt"]), MANIFEST_CAP)
    if sha(raw) != config["manifest_sha256"] or sha(receipt_raw) != config["receipt_sha256"]:
        fail("seed_unavailable")
    catalog, receipt = parsed(raw, MANIFEST_CAP), parsed(receipt_raw, MANIFEST_CAP)
    if (set(catalog) != {"schema", "archive_commit", "tree_chain", "catalog"} or catalog["schema"] != "w40-seed-v1"
            or set(receipt) != {"schema", "archive_commit", "tree_chain", "catalog_sha256", "objects"}
            or receipt["schema"] != "w40-origin-v1" or receipt["archive_commit"] != catalog["archive_commit"]
            or receipt["tree_chain"] != catalog["tree_chain"] or receipt["catalog_sha256"] != sha(raw)
            or not hex_value(catalog["archive_commit"], 40) or len(catalog["tree_chain"]) != 3):
        fail("seed_unavailable")
    entries = _catalog(catalog["catalog"], seed_input=True)
    objects = {}
    for proof in receipt["objects"]:
        if set(proof) != {"id", "object", "bytes", "sha256"} or proof["id"] in objects:
            fail("seed_unavailable")
        framed = read(under(binding.roots["seed"], proof["object"]), REPORT_CAP)
        if (len(framed), sha(framed)) != (proof["bytes"], proof["sha256"]):
            fail("seed_unavailable")
        objects[proof["id"]] = framed
    try:
        commit = _framed_object(objects[catalog["archive_commit"]], catalog["archive_commit"], "commit")
        if commit.split(b"\n", 1)[0] != b"tree " + catalog["tree_chain"][0].encode():
            fail("seed_unavailable")
        trees = [_git_tree(_framed_object(objects[identity], identity, "tree")) for identity in catalog["tree_chain"]]
        for tree, name, expected in ((trees[0], "bench", catalog["tree_chain"][1]), (trees[1], "snapshots", catalog["tree_chain"][2])):
            item = next((x for x in tree if x["path"] == name), None)
            if item != dict(path=name, mode="040000", type="tree", sha=expected):
                fail("seed_unavailable")
        actual = {x["path"]: x for x in trees[2] if re.fullmatch(r"pools-\d{4}-\d{2}-\d{2}\.ndjson", x["path"])}
        if len(actual) != len(entries) or any(actual.get(x["path"].split("/")[-1]) != dict(path=x["path"].split("/")[-1], mode="100644", type="blob", sha=x["sha"]) for x in entries):
            fail("seed_unavailable")
    except (KeyError, TypeError, AttributeError):
        fail("seed_unavailable")
    return catalog


def _copy_object(source, target, *, count, check):
    target = private(target, missing=True)
    if target.exists():
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        left = count
        with private(source).open("rb") as incoming, target.open("xb") as outgoing:
            while left:
                check()
                block = incoming.read(min(ROW_CAP, left))
                if not block:
                    fail("source_corrupt")
                outgoing.write(block)
                left -= len(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
    except OSError:
        fail("disk_failure")


def _build_view(binding, claim, catalog, files, commit, tree_chain, *, check):
    prior = accepted_view(binding)
    old = {entry["path"]: entry for entry in prior["catalog"]} if prior else {}
    if set(old) - {x["path"] for x in catalog}:
        fail("prefix_changed")
    result, partial, findings = [], 0, {"invalid_row": 0, "row_cap": 0}
    for entry in catalog:
        check()
        source = private(files[entry["path"]])
        size, digest = file_hash(source, check=check)
        if size != entry["bytes"] or entry.get("sha256", digest) != digest:
            fail("source_corrupt")
        git_digest = hashlib.sha1(b"blob " + str(size).encode() + b"\0")
        with source.open("rb") as handle:
            while block := handle.read(ROW_CAP):
                check()
                git_digest.update(block)
        if git_digest.hexdigest() != entry["sha"]:
            fail("source_corrupt")
        previous = old.get(entry["path"])
        if previous:
            if size < previous["bytes"]:
                fail("prefix_changed")
            with source.open("rb") as current, under(binding.roots["source"], previous["object"]).open("rb") as former:
                while block := former.read(ROW_CAP):
                    check()
                    if current.read(len(block)) != block:
                        fail("prefix_changed")
        reference = "objects/" + digest
        target = under(binding.roots["source"], reference, missing=True)
        _copy_object(source, target, count=size, check=check)
        if file_hash(target, check=check) != (size, digest):
            fail("source_corrupt")
        complete_bytes, lines, trailing_bytes, trailing_hash = 0, 0, 0, sha(b"")
        for row in _scan(target, check=check):
            if row["complete"]:
                complete_bytes = row["offset"] + row["bytes"]
                lines = row["line"]
                if row["finding"]:
                    findings[row["finding"]] += 1
            else:
                trailing_bytes, trailing_hash = row["bytes"], row["sha256"]
        prefix_digest = hashlib.sha256()
        with target.open("rb") as handle:
            left = complete_bytes
            while left:
                check()
                block = handle.read(min(ROW_CAP, left))
                prefix_digest.update(block)
                left -= len(block)
        prefix_hash = prefix_digest.hexdigest()
        chunks = []
        if complete_bytes:
            chunk_ref = "chunks/" + prefix_hash
            chunk = under(binding.roots["source"], chunk_ref, missing=True)
            _copy_object(target, chunk, count=complete_bytes, check=check)
            if file_hash(chunk, check=check) != (complete_bytes, prefix_hash):
                fail("source_corrupt")
            chunks.append(dict(id=prefix_hash, object=chunk_ref, bytes=complete_bytes, sha256=prefix_hash, first_line=1, last_line=lines))
        partial += int(trailing_bytes > 0)
        result.append(dict(path=entry["path"], mode="100644", type="blob", blob_sha1=entry["sha"],
                           bytes=size, sha256=digest, object=reference, complete_bytes=complete_bytes,
                           complete_lines=lines, prefix_sha256=prefix_hash, trailing_bytes=trailing_bytes,
                           trailing_sha256=trailing_hash, previous_bytes=previous["bytes"] if previous else 0,
                           previous_sha256=previous["sha256"] if previous else sha(b""),
                           previous_complete_bytes=previous["complete_bytes"] if previous else 0,
                           previous_prefix_sha256=previous["prefix_sha256"] if previous else sha(b""), chunks=chunks))
    value = dict(schema="w40-source-view-v1", study_id_sha256=binding.config["study_id_sha256"],
                 config_sha256=binding.config_pin, code_manifest_sha256=binding.manifest_pin,
                 origin_sha256=sha(encoded(binding.config["archive_origin"])), sequence=(prior["sequence"] + 1 if prior else 1),
                 previous_view_sha256=prior["view_sha256"] if prior else None, archive_commit=commit,
                 tree_chain=tree_chain, catalog=result, claim_sha256=claim["claim_sha256"],
                 allocation_ticket_sha256=claim["allocation_ticket_sha256"], row_findings=findings)
    value["view_sha256"] = sha(encoded(value))
    write_new(under(binding.roots["source"], "views/" + value["view_sha256"] + ".json", missing=True), encoded(value))
    return value, partial


def _begin(binding, lease, kind, clock, *, date=None, slot=None):
    transaction = uuid.uuid4().hex + uuid.uuid4().hex
    if kind == "seed":
        ceilings = {"source": SEED_CAP - 4 * REPORT_CAP, "control": 4 * REPORT_CAP}
    else:
        ceilings = {"source": INCREMENT_CAP - 4 * REPORT_CAP, "control": 4 * REPORT_CAP}
    ticket = reserve(binding, lease, reservation_id=transaction, owner=kind, ceilings=ceilings)
    sample = _snapshot(clock)
    claim = dict(transaction_id=transaction, kind=kind, date=date, slot=slot,
                 utc=sample["utc"], monotonic=sample["mono"], allocation_ticket_sha256=sha(encoded(dict(ticket))))
    claim["claim_sha256"] = append(binding, lease, "archive", "claim", claim)
    return claim, ticket


def _finish_transaction(binding, lease, claim, ticket, *, state, reason=None, view=None, examined=0, unexamined=0, partial=0):
    result = _source_result(binding, lease, claim["transaction_id"], state, reason, view=view,
                            examined=examined, unexamined=unexamined, partial=partial)
    receipt = settle(binding, lease, ticket, inventory=inventory(binding))
    return _public_result(result, receipt)


def _blocked_result(binding, reason, *, state="gap"):
    old = accepted_view(binding)
    return dict(schema="w40-source-result-v1", state=state, reason=reason,
                view_sha256=old["view_sha256"] if old else None, transaction_receipt_sha256=None,
                allocation_receipt_sha256=None, examined=0, unexamined=0, partial=0)


def seed(binding, lease, *, clock=None):
    lease_guard(binding, lease)
    clock = clock or Clock()
    start = _snapshot(clock)
    deadline = start["mono"] + SEED_SECONDS
    check = lambda: _check(binding, clock, start, deadline)
    claim, ticket = None, None
    try:
        check()
        prior_claims, results, _attempts = _archive_state(binding)
        if any(key not in results for key in prior_claims):
            fail("source_incomplete")
        catalog = _seed_input(binding)
        source_total = sum(x["bytes"] for x in catalog["catalog"])
        staged_total = sum(x["bytes"] for x in measured(binding, areas=("seed",)))
        if staged_total + source_total * 2 + TERMINAL_RESERVE + 4 * REPORT_CAP > SEED_CAP:
            fail("seed_limit")
        claim, ticket = _begin(binding, lease, "seed", clock)
        check()
        files = {x["path"]: under(binding.roots["seed"], x["object"]) for x in catalog["catalog"]}
        view, partial = _build_view(binding, claim, catalog["catalog"], files, catalog["archive_commit"], catalog["tree_chain"], check=check)
        check()
        return _finish_transaction(binding, lease, claim, ticket, state="accepted", view=view["view_sha256"],
                                   examined=sum(x["complete_lines"] for x in view["catalog"]), partial=partial)
    except ArchiveError as exc:
        reason = str(exc)
        if claim:
            return _finish_transaction(binding, lease, claim, ticket, state="terminal", reason=reason)
        return _blocked_result(binding, reason, state="terminal")


def _request(binding, path, *, cap, blob=False):
    origin = binding.config["archive_origin"]
    prefix = "/repos/%s/%s/git/" % (origin["owner"], origin["repo"])
    suffix = path[len(prefix):] if path.startswith(prefix) else ""
    if (not suffix or not (suffix == "ref/heads/master" or re.fullmatch("(?:commits|trees|blobs)/[0-9a-f]{40}", suffix))
            or type(cap) is not int or not 0 <= cap <= INCREMENT_CAP or blob != suffix.startswith("blobs/")):
        fail("source_corrupt")
    return dict(method="GET", host="api.github.com", path=path, cap=cap,
                headers={"Accept": "application/vnd.github.raw+json" if blob else "application/vnd.github+json",
                         "Accept-Encoding": "identity", "User-Agent": "vetagent-w40-local-source",
                         "X-GitHub-Api-Version": origin["api_version"]})


def _headers_status(directory):
    path = directory / "headers.json"
    if not path.exists():
        return None
    value = parsed(read(path, ROW_CAP), ROW_CAP)
    status = value.get("status")
    if type(status) is not int or not 100 <= status <= 599:
        fail("invalid_response")
    return status


class FetchSession:
    def __init__(self, binding, lease, claim, ticket, clock, start, deadline, transport, hooks):
        self.binding, self.lease, self.claim, self.ticket = binding, lease, claim, ticket
        self.clock, self.start, self.deadline = clock, start, deadline
        self.transport, self.hooks, self.number = transport, hooks, 0
        self.date = start["utc"][:10]
        self.last = None
        self.base_source = sum(x["bytes"] for x in measured(binding, areas=("source",)))
        _claims, _results, attempts = _archive_state(binding)
        if attempts:
            self.last = attempts[-1]["monotonic"]
            if self.last > start["mono"]:
                fail("invalid_clock")

    def check(self, allowance=0):
        lease_guard(self.binding, self.lease)
        return _check(self.binding, self.clock, self.start, self.deadline, allowance=allowance, date=self.date)

    async def get(self, request):
        if self.number >= 133:
            fail("request_cap")
        sample = self.check(REQUEST_SECONDS)
        if self.last is not None:
            delay = self.last + 1.0 - sample["mono"]
            if delay > 0:
                await self.clock.sleep(delay)
        sample = self.check(REQUEST_SECONDS)
        used = sum(x["bytes"] for x in measured(self.binding, areas=("source",))) - self.base_source
        if used + request["cap"] + 4 * ROW_CAP > self.ticket["ceilings"]["source"]:
            fail("candidate_limit")
        self.number += 1
        relative = "transactions/%s/attempts/%03d" % (self.claim["transaction_id"], self.number)
        directory = under(self.binding.roots["source"], relative, missing=True)
        directory.mkdir(parents=True)
        raw_request = encoded(request)
        write_new(directory / "request-metadata.json", raw_request)
        permit = dict(reserved_date=self.date, expires_mono=sample["mono"] + REQUEST_SECONDS,
                      request_deadline=sample["mono"] + REQUEST_SECONDS, outer_deadline=self.deadline,
                      allowance_seconds=REQUEST_SECONDS, binding=self.binding.identity)
        write_new(directory / "permit.json", encoded(permit))
        append(self.binding, self.lease, "archive", "attempt", dict(transaction_id=self.claim["transaction_id"],
               number=self.number, directory=relative, request_sha256=sha(raw_request), permit_sha256=sha(encoded(permit)),
               utc=sample["utc"], monotonic=sample["mono"]))
        self.last = sample["mono"]
        value, error = None, None
        try:
            self.check(REQUEST_SECONDS)
            transport = self.transport or _native_transport
            value = await transport(request, directory=directory, permit=permit, binding=self.binding,
                                    clock=self.clock, hooks=self.hooks, recheck=self.check)
        except BaseException as exc:
            error = str(exc) if isinstance(exc, ArchiveError) else "source_unavailable"
        if value is not None:
            if not isinstance(value, dict) or value.get("retired") != "exited":
                fail("cleanup_uncertain")
            raw = value.get("raw", b"")
            if not isinstance(raw, bytes):
                fail("invalid_response")
            raw = raw[:request["cap"] + 1]
            if not (directory / "body.bin").exists():
                write_new(directory / "body.bin", raw)
            elif read(directory / "body.bin", request["cap"] + 1) != raw:
                fail("source_corrupt")
            status = value.get("status")
            if status is not None and (type(status) is not int or not 100 <= status <= 599):
                fail("invalid_response")
            if not (directory / "headers.json").exists() and status is not None:
                write_new(directory / "headers.json", encoded(dict(status=status, content_length=value.get("content_length"),
                          content_encoding=value.get("content_encoding"), utc=utc(self.clock.utc()), monotonic=self.clock.mono())))
        status = _headers_status(directory)
        if error == "cleanup_uncertain":
            fail(error)
        identity_path = directory / "creation.json"
        identity = parsed(read(identity_path, ROW_CAP), ROW_CAP) if identity_path.exists() else None
        if not (directory / "retired.json").exists():
            write_new(directory / "retired.json", encoded(dict(state="exited", identity_sha256=sha(encoded(identity)) if identity else None)))
        _verify_retired(self.binding, directory)
        if status in (401, 403):
            error = "source_permission"
        if error is None:
            if value is None or status is None:
                error = "source_unavailable"
            elif status == 429 or status >= 500:
                error = "source_unavailable"
            elif status != 200:
                error = "invalid_response"
            elif (value.get("content_encoding") not in (None, "identity", "")
                    or value.get("content_length") is not None and value["content_length"] != len(value["raw"])
                    or len(value["raw"]) > request["cap"] or value.get("complete", True) is not True):
                error = "invalid_response"
        body = directory / "body.bin"
        body_size, body_hash = file_hash(body) if body.exists() else (0, None)
        write_new(directory / "commit.json", encoded(dict(status=status, state="observed" if error is None else error,
                                                          bytes=body_size, sha256=body_hash)))
        if error:
            fail(error)
        self.check()
        return value["raw"], body


def _tree(value, expected):
    if (not isinstance(value, dict) or value.get("sha") != expected or value.get("truncated") is not False
            or not isinstance(value.get("tree"), list)):
        fail("source_corrupt")
    seen, entries = set(), []
    for item in value["tree"]:
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str) or item["path"] in seen
                or item["path"] in ("", ".", "..") or "/" in item["path"] or "\\" in item["path"]
                or not hex_value(item.get("sha"), 40) or item.get("mode") not in ("040000", "100644", "100755", "120000", "160000")
                or item.get("type") not in ("tree", "blob", "commit")):
            fail("source_corrupt")
        seen.add(item["path"])
        entries.append(item)
    return entries


async def _refresh_acquire(session):
    binding = session.binding
    origin = binding.config["archive_origin"]
    prefix = "/repos/%s/%s/git/" % (origin["owner"], origin["repo"])

    async def metadata(suffix):
        raw, _path = await session.get(_request(binding, prefix + suffix, cap=REPORT_CAP))
        return parsed(raw)

    ref = await metadata("ref/heads/master")
    if (not isinstance(ref, dict) or ref.get("ref") != "refs/heads/master" or not isinstance(ref.get("object"), dict)
            or ref["object"].get("type") != "commit" or not hex_value(ref["object"].get("sha"), 40)):
        fail("source_corrupt")
    commit = ref["object"]["sha"]
    commit_value = await metadata("commits/" + commit)
    if (not isinstance(commit_value, dict) or commit_value.get("sha") != commit or not isinstance(commit_value.get("tree"), dict)
            or not hex_value(commit_value["tree"].get("sha"), 40)):
        fail("source_corrupt")
    identity = commit_value["tree"]["sha"]
    trees = [identity]
    for child in ("bench", "snapshots"):
        entries = _tree(await metadata("trees/" + identity), identity)
        entry = next((x for x in entries if x["path"] == child), None)
        if entry is None or entry["mode"] != "040000" or entry["type"] != "tree":
            fail("source_corrupt")
        identity = entry["sha"]
        trees.append(identity)
    entries = _tree(await metadata("trees/" + identity), identity)
    catalog = []
    for entry in sorted(entries, key=lambda x: x["path"].encode()):
        if re.fullmatch(r"pools-\d{4}-\d{2}-\d{2}\.ndjson", entry["path"]):
            catalog.append(dict(path="bench/snapshots/" + entry["path"], mode=entry["mode"], type=entry["type"],
                                sha=entry["sha"], bytes=entry.get("size")))
    _catalog(catalog)
    prior = accepted_view(binding)
    old = {x["path"]: x for x in prior["catalog"]} if prior else {}
    if set(old) - {x["path"] for x in catalog}:
        fail("prefix_changed")
    changed = [x for x in catalog if x["path"] not in old or old[x["path"]]["blob_sha1"] != x["sha"]]
    used = sum(x["bytes"] for x in measured(binding, areas=("source",))) - session.base_source
    if used + sum(x["bytes"] * 3 + 4 * ROW_CAP for x in changed) + REPORT_CAP > session.ticket["ceilings"]["source"]:
        fail("candidate_limit")
    files = {}
    for entry in catalog:
        if entry not in changed:
            if old[entry["path"]]["bytes"] != entry["bytes"]:
                fail("source_corrupt")
            files[entry["path"]] = under(binding.roots["source"], old[entry["path"]]["object"])
        else:
            _raw, path = await session.get(_request(binding, prefix + "blobs/" + entry["sha"], cap=entry["bytes"], blob=True))
            files[entry["path"]] = path
    view, partial = _build_view(binding, session.claim, catalog, files, commit, trees, check=session.check)
    return view, partial


def refresh(binding, lease, *, live=False, deadline_mono, clock=None, transport=None, hooks=None):
    lease_guard(binding, lease)
    if live is not True:
        fail("not_live")
    clock = clock or Clock()
    start = _snapshot(clock)
    if type(deadline_mono) not in (int, float) or not math.isfinite(deadline_mono):
        fail("invalid_clock")
    deadline = min(start["mono"] + REFRESH_SECONDS, deadline_mono)
    if transport is None:
        verify_live(binding)
    claims, results, _attempts = _archive_state(binding)
    terminal = next((x for x in results.values() if x["state"] == "terminal"), None)
    if terminal:
        return _blocked_result(binding, terminal["reason"], state="terminal")
    if any(identity not in results for identity in claims):
        return _blocked_result(binding, "source_incomplete", state="terminal")
    wall = datetime.fromisoformat(start["utc"].replace("Z", "+00:00"))
    date = start["utc"][:10]
    slot = (wall.hour * 60 + wall.minute) // 15
    reserved = [x for x in claims.values() if x["kind"] == "refresh" and x["date"] == date]
    if any(x["slot"] == slot for x in reserved):
        return _blocked_result(binding, "slot_consumed")
    if len(reserved) >= 96:
        return _blocked_result(binding, "daily_cap")
    claim, ticket, session = None, None, None
    try:
        _check(binding, clock, start, deadline, allowance=REQUEST_SECONDS, date=date)
        claim, ticket = _begin(binding, lease, "refresh", clock, date=date, slot=slot)
        session = FetchSession(binding, lease, claim, ticket, clock, start, deadline, transport, hooks)
        view, partial = asyncio.run(_refresh_acquire(session))
        session.check()
        return _finish_transaction(binding, lease, claim, ticket, state="accepted", view=view["view_sha256"],
                                   examined=sum(x["complete_lines"] for x in view["catalog"]), partial=partial)
    except ArchiveError as exc:
        reason = str(exc)
        state = "gap" if reason in ("source_unavailable", "deadline", "candidate_limit", "request_cap") else "terminal"
        if claim:
            prior = accepted_view(binding)
            return _finish_transaction(binding, lease, claim, ticket, state=state, reason=reason,
                                       view=prior["view_sha256"] if prior else None, unexamined=1)
        return _blocked_result(binding, reason, state=state)


def recover_archive(binding, lease):
    lease_guard(binding, lease)
    claims, results, attempts = _archive_state(binding)
    tickets, receipts, _retained, _pending = allocation_state(binding)
    last = None
    for identity, claim in claims.items():
        if identity in receipts:
            verify_inventory(binding, receipts[identity])
            last = _public_result(results[identity], receipts[identity])
            continue
        ticket = tickets.get(identity)
        if ticket is None or sha(encoded(ticket)) != claim["allocation_ticket_sha256"]:
            fail("history_corrupt")
        reason = "source_unavailable"
        for attempt in (x for x in attempts if x["transaction_id"] == identity):
            directory = under(binding.roots["source"], attempt["directory"])
            if sha(read(directory / "request-metadata.json", ROW_CAP)) != attempt["request_sha256"]:
                fail("history_corrupt")
            if sha(read(directory / "permit.json", ROW_CAP)) != attempt["permit_sha256"]:
                fail("history_corrupt")
            creation = directory / "creation.json"
            actual = parsed(read(creation, ROW_CAP), ROW_CAP) if creation.exists() else None
            if actual is not None and _native(binding).identity_alive(actual):
                fail("cleanup_uncertain")
            if actual is None and (directory / "request.json").exists():
                fail("cleanup_uncertain")
            if not (directory / "retired.json").exists():
                write_new(directory / "retired.json", encoded(dict(state="exited", identity_sha256=sha(encoded(actual)) if actual else None)))
            _verify_retired(binding, directory)
            if _headers_status(directory) in (401, 403):
                reason = "source_permission"
        if identity not in results:
            old = accepted_view(binding)
            result = _source_result(binding, lease, identity, "terminal" if reason == "source_permission" else "gap", reason,
                                    view=old["view_sha256"] if old else None, unexamined=1)
        else:
            result = results[identity]
        receipt = settle(binding, lease, ticket, inventory=inventory(binding))
        last = _public_result(result, receipt)
    return last or _blocked_result(binding, None)


def plan(binding):
    guard(binding)
    return dict(state="not_started", source_manifest_sha256=binding.manifest_pin, config_sha256=binding.config_pin,
                started_at=None, limits=dict(study_bytes=STUDY_CAP, seed_bytes=SEED_CAP,
                increment_bytes=INCREMENT_CAP, source_files=SOURCE_CAP, refresh_gets=133, refresh_seconds=60,
                request_seconds=10, refresh_daily=96, seed_seconds=1200))


def report(binding):
    guard(binding)
    claims, results, attempts = _archive_state(binding)
    _tickets, _receipts, retained, pending = allocation_state(binding)
    view = accepted_view(binding)
    last = next(reversed(results.values())) if results else None
    return dict(state=last["state"] if last else "not_started", reason=last["reason"] if last else None,
                view_sha256=view["view_sha256"] if view else None, started_at=None,
                refresh_reserved=sum(x["kind"] == "refresh" for x in claims.values()),
                attempts_reserved=len(attempts), unfinished=sum(x not in results for x in claims),
                source_files=len(view["catalog"]) if view else 0, source_rows=sum(x["complete_lines"] for x in view["catalog"]) if view else 0,
                allocation=dict(retained_bytes=retained, reserved_bytes=pending + TERMINAL_RESERVE,
                                committed_and_reserved_bytes=retained + pending + TERMINAL_RESERVE),
                stop=stop_state(binding), detail_omitted=0)


class NativeSourceWorker:
    """An independent GET child; T046 provides only verified OS containment."""
    def __init__(self, request, *, directory, permit, binding, clock=None, hooks=None, recheck=None, route=None):
        ci_guard()
        self.request, self.directory, self.permit, self.binding = request, Path(directory), permit, binding
        self.clock, self.hooks, self.recheck, self.route = clock or Clock(), hooks, recheck, route
        native = _native(binding)
        self.worker = native.NativeWorker(request, directory=directory, permit=permit,
                                          permit_sha256=sha(encoded(permit)))
        self.configuration = dict(schema="w40-source-worker-v1", config=str(binding.config_path),
            expected_config_sha256=binding.config_pin, expected_manifest_sha256=binding.manifest_pin,
            request=request, permit=permit, parent=os.getpid(), nonce=uuid.uuid4().hex,
            route=list(route) if route is not None else None)

    @property
    def identity(self):
        return self.worker.identity

    async def wait_file(self, name):
        path = self.directory / name
        while not path.exists():
            private(path, missing=True)
            if self.worker.process.poll() is not None or time.monotonic() >= self.permit["request_deadline"] - .4:
                fail("source_unavailable")
            await asyncio.sleep(.005)
        return parsed(read(path, ROW_CAP), ROW_CAP)

    async def fetch(self):
        native = _native(self.binding)
        error, complete = None, False
        try:
            guard(self.binding, mutate=True)
            verify_install(self.binding.config_path, expected_config_sha256=self.binding.config_pin,
                           expected_manifest_sha256=self.binding.manifest_pin, component="archive")
            _request(self.binding, self.request["path"], cap=self.request["cap"], blob="/blobs/" in self.request["path"])
            raw = encoded(self.configuration)
            write_new(self.directory / "request.json", raw)
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            env["PYTHONNOUSERSITE"] = "1"
            executable = self.binding.manifest["interpreter"]["path"]
            self.worker.process = subprocess.Popen([executable, "-I", "-B", str(Path(__file__).resolve()),
                "--source-child", str(self.directory / "request.json")], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.worker.identity = dict(pid=self.worker.process.pid, creation=native.creation_identity(self.worker.process.pid),
                                        token=self.configuration["nonce"], parent=os.getpid())
            write_new(self.directory / "creation.json", encoded(self.identity))
            self.worker.job = native.Job(self.worker.process)
            ready = await self.wait_file("ready.json")
            if (parsed(read(self.directory / "identity.json", ROW_CAP), ROW_CAP) != self.identity
                    or ready != {"identity_sha256": sha(encoded(self.identity))} or not native.identity_alive(self.identity)):
                fail("containment_unavailable")
            if self.hooks:
                await self.hooks("before_ack", self)
            if self.recheck:
                self.recheck(REQUEST_SECONDS)
            write_new(self.directory / "arming.json", encoded(dict(request_sha256=sha(raw), permit_sha256=sha(encoded(self.permit)))))
            if self.recheck:
                self.recheck(REQUEST_SECONDS)
            self.worker.process.stdin.write(("arm " + self.configuration["nonce"] + "\n").encode())
            self.worker.process.stdin.flush()
            await self.wait_file("invocation.json")
            await self.wait_file("sent.json")
            if self.hooks:
                await self.hooks("native_entry", self)
            await self.wait_file("headers.json")
            end = await self.wait_file("end.json")
            complete = end.get("state") == "observed"
        except BaseException as exc:
            error = str(exc) if isinstance(exc, ArchiveError) else "source_unavailable"
        finally:
            try:
                await self.worker.retire()
            except BaseException:
                fail("cleanup_uncertain")
        header_path = self.directory / "headers.json"
        header = parsed(read(header_path, ROW_CAP), ROW_CAP) if header_path.exists() else {}
        body_path = self.directory / "body.bin"
        body = read(body_path, self.request["cap"] + 1) if body_path.exists() else b""
        if error and header.get("status") not in (401, 403) and not header:
            fail(error)
        return dict(status=header.get("status"), raw=body, content_length=header.get("content_length"),
                    content_encoding=header.get("content_encoding"), complete=complete, retired="exited", identity=self.identity)


async def _native_transport(request, **kwargs):
    return await NativeSourceWorker(request, **kwargs).fetch()


def _child_parent_death(parent):
    if sys.platform.startswith("linux"):
        import ctypes
        import signal
        api = ctypes.CDLL(None, use_errno=True)
        actual = ctypes.c_int()
        if (os.getppid() != parent or api.prctl(1, signal.SIGKILL, 0, 0, 0) != 0
                or api.prctl(2, ctypes.byref(actual), 0, 0, 0) != 0 or actual.value != signal.SIGKILL
                or os.getppid() != parent):
            fail("containment_unavailable")
    elif sys.platform != "win32":
        fail("containment_unavailable")


def _source_child(path):
    ci_guard()
    configuration = parsed(read(private(path), ROW_CAP), ROW_CAP)
    required = {"schema", "config", "expected_config_sha256", "expected_manifest_sha256", "request", "permit", "parent", "nonce", "route"}
    if set(configuration) != required or configuration["schema"] != "w40-source-worker-v1":
        fail("source_corrupt")
    parent, permit = configuration["parent"], configuration["permit"]
    _child_parent_death(parent)
    remaining = permit["request_deadline"] - time.monotonic() - .45
    if not 0 < remaining <= REQUEST_SECONDS:
        return 2
    watchdog = threading.Timer(remaining, os._exit, args=(3,))
    watchdog.daemon = True
    watchdog.start()
    binding = verify_install(configuration["config"], expected_config_sha256=configuration["expected_config_sha256"],
                             expected_manifest_sha256=configuration["expected_manifest_sha256"], component="archive")
    if configuration["route"] is None:
        verify_live(binding)
    directory = private(Path(path).parent)
    if not directory.is_relative_to(binding.roots["source"]) or permit.get("binding") != binding.identity:
        fail("source_corrupt")
    request = configuration["request"]
    expected = _request(binding, request["path"], cap=request["cap"], blob="/blobs/" in request["path"])
    if request != expected or not re.fullmatch("[0-9a-f]{32}", configuration["nonce"]):
        fail("source_corrupt")
    native = _native(binding)
    identity = dict(pid=os.getpid(), creation=native.creation_identity(os.getpid()), token=configuration["nonce"], parent=parent)
    write_new(directory / "identity.json", encoded(identity))
    origins = {name: str(Path(module.__file__).resolve()) for name, module in tuple(sys.modules.items())
               if name in ("w40_evidence", "labels", "w40_archive_native") and getattr(module, "__file__", None)}
    write_new(directory / "origins.json", encoded(dict(interpreter=str(Path(sys.executable).resolve()),
              base_prefix=str(Path(sys.base_prefix).resolve()), origins=origins,
              config_sha256=binding.config_pin, manifest_sha256=binding.manifest_pin)))
    write_new(directory / "ready.json", encoded(dict(identity_sha256=sha(encoded(identity)))))
    if sys.stdin.buffer.readline(128) != ("arm " + configuration["nonce"] + "\n").encode():
        return 0
    if sys.platform.startswith("linux") and os.getppid() != parent:
        return 0
    if (utc(datetime.now(timezone.utc))[:10] != permit["reserved_date"] or time.monotonic() >= permit["expires_mono"]
            or time.monotonic() + REQUEST_SECONDS > permit["outer_deadline"] or stop_state(binding)["state"] != "not_started"):
        return 0
    import http.client
    connection = None
    try:
        remaining = max(.01, permit["request_deadline"] - time.monotonic() - .45)
        route = configuration["route"]
        if route is None:
            connection = http.client.HTTPSConnection("api.github.com", timeout=remaining)
        else:
            if not isinstance(route, list) or len(route) != 2 or route[0] != "127.0.0.1" or type(route[1]) is not int or not 1 <= route[1] <= 65535:
                fail("source_corrupt")
            connection = http.client.HTTPConnection(route[0], route[1], timeout=remaining)
        entry = dict(utc=utc(datetime.now(timezone.utc)), monotonic=time.monotonic(), permit_sha256=sha(encoded(permit)))
        if entry["utc"][:10] != permit["reserved_date"] or entry["monotonic"] >= permit["expires_mono"]:
            return 0
        try:
            connection.request("GET", request["path"], headers=request["headers"])
        finally:
            write_new(directory / "invocation.json", encoded(entry))
        write_new(directory / "sent.json", encoded(dict(state="observed")))
        response = connection.getresponse()
        header = dict(status=response.status, content_length=response.length,
                      content_encoding=response.getheader("Content-Encoding"),
                      headers=response.getheaders(), utc=utc(datetime.now(timezone.utc)), monotonic=time.monotonic())
        if len(encoded(header)) > ROW_CAP:
            fail("invalid_response")
        write_new(directory / "headers.json", encoded(header))
        size, digest = 0, hashlib.sha256()
        with private(directory / "body.bin", missing=True).open("xb") as handle:
            while size <= request["cap"]:
                if time.monotonic() >= permit["request_deadline"] - .45:
                    fail("deadline")
                block = response.read1(min(ROW_CAP, request["cap"] + 1 - size))
                if not block:
                    break
                handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
                size += len(block)
                digest.update(block)
                progress = dict(bytes=size, sha256=digest.hexdigest())
                native.replace_private(directory / "progress.json", progress)
        if size > request["cap"] or response.length not in (None, 0):
            fail("invalid_response")
        write_new(directory / "end.json", encoded(dict(state="observed", bytes=size, sha256=digest.hexdigest())))
    except BaseException:
        if not (directory / "end.json").exists():
            write_new(directory / "end.json", encoded(dict(state="source_unavailable")))
    finally:
        if connection:
            connection.close()
    return 0


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        fail("invalid_arguments")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == "--source-child":
        return _source_child(argv[1])
    parser = Parser(add_help=False)
    parser.add_argument("command", nargs="?", choices=("plan", "seed", "report"), default="plan")
    parser.add_argument("--help", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--config-sha256")
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args(argv)
    if args.command == "seed":
        ci_guard()
    if args.help or not any((args.config, args.config_sha256, args.manifest_sha256)):
        print(encoded(dict(state="configuration_required", reason="configuration_required")).decode())
        return 0
    if not all((args.config, args.config_sha256, args.manifest_sha256)):
        fail("source_drift")
    binding = verify_install(args.config, expected_config_sha256=args.config_sha256,
                             expected_manifest_sha256=args.manifest_sha256, component="archive")
    if args.command == "seed":
        with study_writer(binding) as lease:
            value = seed(binding, lease)
    else:
        value = plan(binding) if args.command == "plan" else report(binding)
    raw = encoded(value)
    if len(raw) > REPORT_CAP:
        fail("storage_refused")
    print(raw.decode())
    return 0 if value["state"] not in ("gap", "terminal", "stop_unknown") else 2


if __name__ == "__main__":
    try:
        exit_code = main()
    except ArchiveError as exc:
        print(encoded(dict(state="terminal", reason=str(exc))).decode())
        exit_code = 2
    except BaseException:
        print(encoded(dict(state="terminal", reason="source_unavailable")).decode())
        exit_code = 2
    sys.exit(exit_code)
