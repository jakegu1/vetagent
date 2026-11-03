"""Closed offline W40 source-fixture verification; no operational native API."""
import contextlib
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "bench/engine_versions.json"
REGISTRY_SHA256 = "a4f11a36ecb25a0c4957df8480277d96285b4b4a299b08b14b07a673c0e10f73"
REGISTRY_CAP = 128 * 1024
MEMBER_CAP = 16
FILE_CAP = 4 * 1024 * 1024
TOTAL_CAP = 8 * 1024 * 1024
RESULT_CAP = 128 * 1024
MARKER = b"Historical validation boundary; not a Git checkout.\n"
REASONS = {"invalid_registry", "unknown_contract", "unknown_profile", "role_mismatch",
           "source_unavailable", "source_mismatch", "unsafe_source_view", "runtime_mismatch",
           "runtime_unavailable", "invalid_arguments", "unsupported_command", "verification_failed",
           "invalid_result_layers"}
REASONS |= {"unknown_runner", "unknown_test_context", "test_failed", "test_timeout",
            "test_interrupted", "test_output_limit", "test_execution_unobserved",
            "test_ids_mismatch", "child_protocol_invalid", "validation_quarantined", "operation_limit"}

REASONS.add("legacy_native_execution_unqualified")

class VersionError(Exception):
    def __init__(self, code):
        self.code = code if code in REASONS else "verification_failed"
        super().__init__(self.code)


def require(condition, code):
    if not condition:
        raise VersionError(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    value = {}
    for key, entry in items:
        require(key not in value, "invalid_registry")
        value[key] = entry
    return value


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise VersionError("invalid_registry") from None


def _metadata(path):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "unsafe_source_view")
    return info


def _no_alias(path):
    path = Path(os.path.abspath(path))
    for component in tuple(reversed(path.parents)) + (path,):
        _metadata(component)
    return path


def _read_file(path, cap):
    try:
        path = _no_alias(path)
        before = _metadata(path)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
                "unsafe_source_view")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            actual = os.fstat(handle.fileno())
            raw = handle.read(cap + 1)
        after = _metadata(path)
        signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        require(signature(before) == signature(actual) == signature(after) and len(raw) <= cap,
                "source_mismatch")
        return raw
    except (OSError, ValueError, TypeError):
        raise VersionError("source_unavailable") from None


def load_registry(raw=None):
    if raw is None:
        raw = _read_file(REGISTRY_PATH, REGISTRY_CAP)
    require(type(raw) is bytes and len(raw) <= REGISTRY_CAP, "invalid_registry")
    value = _json(raw)
    try:
        # The digest pins all fields, member order, modes, raw hashes and both profiles.
        require(type(value) is dict and sha(encoded(value)) == REGISTRY_SHA256, "invalid_registry")
        members = value["members"]
        require(len(members) <= MEMBER_CAP and sum(m["bytes"] for m in members) <= TOTAL_CAP,
                "invalid_registry")
        require(all(0 <= m["bytes"] <= FILE_CAP and m["mode"] == "100644" for m in members),
                "invalid_registry")
        for profile in value["profiles"].values():
            require(len(profile["raw_sha256"]) == len(profile["raw_bytes"]) == len(members)
                    and sum(profile["raw_bytes"]) <= TOTAL_CAP
                    and all(0 <= n <= FILE_CAP for n in profile["raw_bytes"]), "invalid_registry")
        return value
    except (KeyError, TypeError, ValueError, OverflowError):
        raise VersionError("invalid_registry") from None


def select(registry, contract_id, profile_id, role="historical_v1"):
    value = load_registry(encoded(registry))
    require(contract_id == value["contract_id"], "unknown_contract")
    require(type(profile_id) is str and profile_id in value["profiles"], "unknown_profile")
    require(role == value["role"] == "historical_v1", "role_mismatch")
    return {"registry": value, "contract_id": contract_id, "profile_id": profile_id}


def _selection(selected):
    require(type(selected) is dict and set(selected) == {"registry", "contract_id", "profile_id"},
            "invalid_registry")
    return select(selected["registry"], selected["contract_id"], selected["profile_id"])


def _git_bytes(*arguments, input_data=None):
    require(arguments and arguments[0] in {"rev-parse", "ls-tree", "cat-file"}, "unsupported_command")
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "--no-replace-objects", "-C", str(ROOT), *arguments],
                                input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15, env=env)
        require(result.returncode == 0 and len(result.stdout) <= TOTAL_CAP, "source_unavailable")
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise VersionError("source_unavailable") from None


def read_objects(selected):
    selected = _selection(selected)
    registry = selected["registry"]
    anchor = registry["engine_source_commit"]
    require(_git_bytes("rev-parse", anchor + "^{tree}").decode("ascii").strip() == registry["source_tree"],
            "source_mismatch")
    members = registry["members"]
    listing = _git_bytes("ls-tree", "-r", "-z", anchor, "--", *(row["path"] for row in members))
    expected = {row["path"]: (row["mode"], "blob", row["blob"]) for row in members}
    actual = {}
    try:
        for line in listing.split(b"\0")[:-1]:
            header, path = line.decode("ascii").split("\t")
            require(path not in actual, "source_mismatch")
            actual[path] = tuple(header.split())
        require(listing.endswith(b"\0") and actual == expected, "source_mismatch")
        request = ("".join(row["blob"] + "\n" for row in members)).encode("ascii")
        sizes = _git_bytes("cat-file", "--batch-check", input_data=request).decode("ascii").splitlines()
        require(len(sizes) == len(members), "source_mismatch")
        for line, row in zip(sizes, members):
            require(line == "%s blob %d" % (row["blob"], row["bytes"]), "source_mismatch")
        packed = _git_bytes("cat-file", "--batch", input_data=request)
        offset, objects = 0, {}
        for row in members:
            header = ("%s blob %d\n" % (row["blob"], row["bytes"])).encode("ascii")
            require(packed[offset:offset + len(header)] == header, "source_mismatch")
            offset += len(header)
            raw = packed[offset:offset + row["bytes"]]
            offset += row["bytes"]
            require(packed[offset:offset + 1] == b"\n", "source_mismatch")
            offset += 1
            require(len(raw) == row["bytes"] and sha(raw) == row["canonical_sha256"], "source_mismatch")
            require(hashlib.sha1(("blob %d\0" % len(raw)).encode("ascii") + raw).hexdigest() == row["blob"],
                    "source_mismatch")
            objects[row["path"]] = raw
        require(offset == len(packed), "source_mismatch")
        return objects
    except (UnicodeError, ValueError, IndexError):
        raise VersionError("source_mismatch") from None


def _external_parent(parent):
    parent = _no_alias(parent)
    require(stat.S_ISDIR(_metadata(parent).st_mode), "unsafe_source_view")
    for ancestor in (parent,) + tuple(parent.parents):
        require(not os.path.lexists(ancestor / ".git"), "unsafe_source_view")
    return parent


def _profile_bodies(selected, objects):
    selected = _selection(selected)
    registry = selected["registry"]
    require(type(objects) is dict and set(objects) == {m["path"] for m in registry["members"]},
            "source_mismatch")
    profile = registry["profiles"][selected["profile_id"]]
    bodies = {}
    for index, member in enumerate(registry["members"]):
        raw = objects[member["path"]]
        require(type(raw) is bytes and len(raw) == member["bytes"]
                and sha(raw) == member["canonical_sha256"], "source_mismatch")
        body = raw if selected["profile_id"] == "git-lf" else raw.replace(b"\n", b"\r\n")
        require(len(body) == profile["raw_bytes"][index] and sha(body) == profile["raw_sha256"][index],
                "source_mismatch")
        bodies[member["path"]] = body
    return bodies


@contextlib.contextmanager
def source_view(selected, objects):
    selected = _selection(selected)
    bodies = _profile_bodies(selected, objects)
    parent = _external_parent(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="engine-source-", dir=parent) as temporary:
        view = Path(temporary)
        try:
            for relative, raw in bodies.items():
                path = view / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as handle:
                    handle.write(raw)
            with (view / ".git").open("xb") as handle:
                handle.write(MARKER)
            verify_view(view, selected)
            try:
                yield view
            finally:
                verify_view(view, selected)
        except (OSError, ValueError, TypeError):
            raise VersionError("unsafe_source_view") from None


def verify_view(view, selected):
    selected = _selection(selected)
    view = _no_alias(view)
    _external_parent(view.parent)
    registry = selected["registry"]
    profile = registry["profiles"][selected["profile_id"]]
    expected = {row["path"] for row in registry["members"]} | {".git"}
    directories = {"."}
    for relative in expected:
        directories.update(p.as_posix() for p in Path(relative).parents)
    pending, files, visited = [view], set(), 0
    try:
        while pending:
            directory = pending.pop()
            for entry in directory.iterdir():
                visited += 1
                require(visited <= 4 * MEMBER_CAP, "unsafe_source_view")
                info = _metadata(entry)
                relative = entry.relative_to(view).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    require(relative in directories, "source_mismatch")
                    pending.append(entry)
                else:
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "unsafe_source_view")
                    files.add(relative)
        require(files == expected and _read_file(view / ".git", 256) == MARKER, "source_mismatch")
        for index, member in enumerate(registry["members"]):
            raw = _read_file(view / member["path"], FILE_CAP)
            require(len(raw) == profile["raw_bytes"][index] and sha(raw) == profile["raw_sha256"][index]
                    and sha(raw.replace(b"\r\n", b"\n")) == member["canonical_sha256"], "source_mismatch")
        return sha(encoded({"profile": selected["profile_id"], "raw": profile["raw_sha256"]}))
    except (OSError, ValueError, TypeError):
        raise VersionError("unsafe_source_view") from None


_CHILD_SCRIPT = r'''
import copy, hashlib, json, os, stat, sys
from pathlib import Path
def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
def no_external_actions(event, args):
    if event.startswith("socket.") and event not in {"socket.gethostname"} or event == "subprocess.Popen":
        raise RuntimeError("action_refused")
sys.addaudithook(no_external_actions)
try:
    root = Path(sys.argv[1])
    value = json.loads(sys.stdin.buffer.read(131073))
    for member in value["members"]:
        path = root / member["path"]
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
        raw = path.read_bytes()
        assert len(raw) == member["bytes"] and digest(raw) == member["sha256"]
    sys.path[:0] = [str(root / "bench"), str(root / "src")]
    import w40_native as native
    import w40_evidence as core
    import risk
    manifest = native.code_manifest()
    native.engine_bindings(risk)
    paths = {"risk": "src/risk.py", "native": "bench/w40_native.py", "core": "bench/w40_evidence.py"}
    for module, name in ((risk, "risk"), (native, "native"), (core, "core")):
        assert Path(module.__file__).resolve() == (root / paths[name]).resolve()
    plan = core.plan("1" * 40, [])
    before = core._bytes(plan)
    core._validate_plan(plan)
    controls = []
    for bindings in (value["opposite_bindings"], {"engine_sha256": "0" * 64}):
        wrong = copy.deepcopy(plan)
        wrong.update(bindings)
        wrong["plan_sha256"] = core._sha(core._bytes({k: v for k, v in wrong.items() if k != "plan_sha256"}))
        try:
            core._validate_plan(wrong)
            controls.append(False)
        except core.EvidenceError as error:
            controls.append(str(error) == "source_drift")
    assert all(controls) and core._bytes(plan) == before
    interpreter = digest(Path(sys.executable).resolve().read_bytes())
    output = {"module_files": paths, "predicates": {"code_manifest": True, "engine_bindings": True},
              "interpreter_sha256": interpreter, "python_version": sys.version.split()[0],
              "cache_tag": sys.implementation.cache_tag, "manifest_sha256": digest(dumps(manifest)),
              "synthetic_plan": {"declared_source_commit": plan["source_commit"],
                  "bindings": core._bindings(), "valid": True, "bytes_unchanged": core._bytes(plan) == before,
                  "wrong_profile_refused": controls[0], "unknown_binding_refused": controls[1]}}
    output["evidence_sha256"] = digest(dumps(output))
    sys.stdout.buffer.write(dumps(output))
except Exception:
    sys.stdout.buffer.write(b'{"error":"runtime_mismatch"}')
    sys.exit(2)
'''


def verify_runtime(view, selected):
    selected = _selection(selected)
    before = verify_view(view, selected)
    registry = selected["registry"]
    profile = registry["profiles"][selected["profile_id"]]
    opposite = registry["profiles"]["observed-windows-crlf" if selected["profile_id"] == "git-lf" else "git-lf"]
    paths = [row["path"] for row in registry["members"]]
    raw = {"members": [{"path": row["path"], "bytes": profile["raw_bytes"][index],
                        "sha256": profile["raw_sha256"][index]} for index, row in enumerate(registry["members"])],
           "opposite_bindings": {key: opposite["raw_sha256"][paths.index(path)] for key, path in (
               ("rule_sha256", "docs/BACKLOG.md"), ("label_sha256", "bench/labels.py"),
               ("engine_sha256", "src/risk.py"))}}
    try:
        # -I -S excludes parent module state, PYTHONPATH and third-party site packages.
        child = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", _CHILD_SCRIPT, str(view)],
                               input=encoded(raw), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        after = verify_view(view, selected)
        require(before == after, "source_mismatch")
        require(child.returncode == 0 and not child.stderr and len(child.stdout) <= RESULT_CAP, "runtime_mismatch")
        value = _json(child.stdout)
        require(type(value) is dict and value.get("predicates") == {"code_manifest": True, "engine_bindings": True},
                "runtime_mismatch")
        evidence = value.get("evidence_sha256")
        require(evidence == sha(encoded({k: v for k, v in value.items() if k != "evidence_sha256"})),
                "runtime_mismatch")
        require(value.get("interpreter_sha256") == sha(Path(sys.executable).resolve().read_bytes()),
                "runtime_mismatch")
        return value
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        raise VersionError("runtime_unavailable") from None


def _layer(status="not_evaluated", reason=None, evidence=()):
    return {"status": status, "reason": reason, "evidence_sha256": list(evidence)}


def _validate_result_layers(value):
    """Pure scope/shape check; synthetic states are not historical verification."""
    error = "invalid_result_layers"
    require(type(value) is dict and value.get("historical_execution_qualified") is False, error)
    names = ("source_fixture", "loaded_runtime", "historical_record_tuple", "historical_interpreter")
    states = {"passed", "failed", "not_evaluated", "unavailable", "unknown"}
    for name in names:
        layer = value.get(name)
        require(type(layer) is dict and set(layer) == {"status", "reason", "evidence_sha256"}, error)
        status, reason, hashes = layer["status"], layer["reason"], layer["evidence_sha256"]
        require(type(status) is str and status in states, error)
        require(reason is None or type(reason) is str, error)
        require(type(hashes) is list and len(hashes) <= MEMBER_CAP, error)
        require(all(type(item) is str and len(item) == 64
                    and all(c in "0123456789abcdef" for c in item) for item in hashes), error)
        require(len(set(hashes)) == len(hashes), error)
        if status in {"not_evaluated", "unavailable"}:
            require(not hashes, error)
        if name in names[2:]:
            reasons = {
                "not_evaluated": "historical_record_not_supplied" if name == names[2] else "historical_interpreter_not_examined",
                "unavailable": "historical_record_unavailable" if name == names[2] else "historical_interpreter_unavailable",
                "unknown": "historical_record_unknown" if name == names[2] else "historical_interpreter_unknown",
            }
            require(status in reasons and reason == reasons[status], error)
        elif status == "passed":
            require(reason is None and bool(hashes), error)
        else:
            require(reason in REASONS or status == "not_evaluated" and reason is None, error)
    if value["loaded_runtime"]["status"] == "passed":
        require(value["source_fixture"]["status"] == "passed", error)
        require(not set(value["loaded_runtime"]["evidence_sha256"]) &
                set(value["source_fixture"]["evidence_sha256"]), error)
    return value


def _receipt(contract_id, profile_id, arguments=None):
    return {"schema": "engine-version-qualification-v1", "operation": "verify-source",
            "invocation_status": "refused", "contract_id": None, "role": None,
            "engine_source_commit": None, "source_tree": None,
            "requested_profile": profile_id if profile_id in ("git-lf", "observed-windows-crlf") else None,
            "selected_profile": None,
            "command_argv": ["python", "tools/engine_versions.py"] + (arguments or ["verify-source"]),
            "original_runner": None, "source_fixture": _layer(), "loaded_runtime": _layer(),
            "historical_record_tuple": _layer(reason="historical_record_not_supplied"),
            "historical_interpreter": _layer(reason="historical_interpreter_not_examined"),
            "legacy_tests": {"status": "not_run", "executed_test_ids_sha256": None, "stdout_sha256": None,
                             "stderr_sha256": None, "child_exit_code": None},
            "wrapper_exit_code": 2, "reason": None, "historical_execution_qualified": False,
            "v2_historical_native_positive_compatibility": "unsupported"}


def _checked_result(value):
    try:
        return _validate_result_layers(value)
    except VersionError:
        # Reset independently of a defective result; do not recurse into the guard.
        refused = _receipt(None, None)
        refused.update(invocation_status="refused", wrapper_exit_code=2,
                       reason="invalid_result_layers", historical_execution_qualified=False)
        for name in ("source_fixture", "loaded_runtime"):
            refused[name] = {"status": "not_evaluated", "reason": "invalid_result_layers", "evidence_sha256": []}
        refused["historical_record_tuple"] = {"status": "not_evaluated", "reason": "historical_record_not_supplied", "evidence_sha256": []}
        refused["historical_interpreter"] = {"status": "not_evaluated", "reason": "historical_interpreter_not_examined", "evidence_sha256": []}
        return refused


def verify_source(contract_id, profile_id):
    # Only known fixed IDs enter receipt text; unknown caller text is never echoed.
    args = ["verify-source", contract_id, profile_id] if contract_id == "w40-v1-e3ec46a" and profile_id in (
        "git-lf", "observed-windows-crlf") else ["verify-source"]
    result = _receipt(contract_id, profile_id, args)
    stage = "source_fixture"
    try:
        selected = select(load_registry(), contract_id, profile_id)
        registry = selected["registry"]
        result.update(contract_id=registry["contract_id"], role=registry["role"],
                      engine_source_commit=registry["engine_source_commit"], source_tree=registry["source_tree"],
                      selected_profile=profile_id)
        objects = read_objects(selected)
        with source_view(selected, objects) as view:
            seal = verify_view(view, selected)
            result[stage] = _layer("passed", evidence=[seal])
            stage = "loaded_runtime"
            runtime = verify_runtime(view, selected)
            result[stage] = _layer("passed", evidence=[runtime["evidence_sha256"]])
        result.update(invocation_status="completed", wrapper_exit_code=0)
    except VersionError as error:
        result["reason"] = error.code
        if error.code in {"source_mismatch", "unsafe_source_view"}:
            stage = "source_fixture"
            result["loaded_runtime"] = _layer(reason="source_mismatch")
        if result["selected_profile"] is not None:
            status = "unavailable" if error.code in {"source_unavailable", "runtime_unavailable"} else "failed"
            result[stage] = _layer(status, error.code)
            result["invocation_status"] = "failed" if stage == "loaded_runtime" else "refused"
        else:
            status = "unavailable" if error.code == "source_unavailable" else "not_evaluated"
            result[stage] = _layer(status, error.code)
    except (OSError, ValueError, TypeError, KeyError):
        result["reason"] = "verification_failed"
        result[stage] = _layer("unknown", "verification_failed")
    return _checked_result(result)


RUNNERS = {"tests/test_w40_native.py": (13, 900), "tests/test_w40_native_clock.py": (3, 180),
           "tests/test_dataset_replayable.py": (9, 120)}
# Sorted top-level IDs from the three runners in the pinned eleven-member fixture.
RUNNER_IDS_SHA256 = {
    "tests/test_w40_native.py": "59631c95ddbe6c756e67c80f8802e9baf700ee5a08221b2ebbf1bc6c4b84884b",
    "tests/test_w40_native_clock.py": "39f2079c4022d0c24beafa0738f5017aafd5a561a905d88b9a606f103c8542ab",
    "tests/test_dataset_replayable.py": "f273a599b919037385df091769fce0a8ca78750cc9fb174747bb18599911bdcf"}
ADAPTER_CLASS = "InterruptedProgressStagingTests"
ADAPTER_IDS = tuple(ADAPTER_CLASS + "." + name for name in (
    "test_pending_progress_handoff_binds_bytes_and_absence",
    "test_pending_progress_is_opaque_retained_evidence",
    "test_pending_progress_keeps_prior_limits_and_refusals"))
DEPENDENCIES = ("bench/goplus_quota_probe.py", "bench/w40_evidence.py", "src/risk.py",
                "bench/labels.py", "docs/BACKLOG.md", "tests/test_dataset_replayable.py")
CURRENT_MEMBERS = ("bench/w40_native.py", "tests/test_w40_native.py")
WORKFLOW_BASE = "9b83558481ae54afd5fc4e9b59c9cb27caa0e3d6"
STREAM_CAP = 1024 * 1024
OPERATION_CAP = 16


def _write_json(path, value, *, exclusive=False, cap=RESULT_CAP):
    raw = encoded(value)
    require(len(raw) <= cap, "child_protocol_invalid")
    if exclusive:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        pending = path.with_name(path.name + ".pending")
        with pending.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, path)


def _scope_path(scope=None):
    if scope is None:
        scope = os.environ.get("VETAGENT_VALIDATION_SCOPE") or str(
            Path(tempfile.gettempdir()) / ("engine-validation-" + sha(str(ROOT).encode())[:16]))
    path = Path(os.path.abspath(scope))
    _external_parent(path.parent)
    path.mkdir(exist_ok=True)
    _external_parent(path)
    require(all(p.name in {"operations", "quarantine.json", "admission.lock"} for p in path.iterdir()),
            "validation_quarantined")
    operations = path / "operations"
    operations.mkdir(exist_ok=True)
    _metadata(operations)
    return path


def _quarantine_scope(scope, operation_id, reason):
    marker = scope / "quarantine.json"
    if not os.path.lexists(marker):
        try:
            _write_json(marker, {"schema": "validation-quarantine-v1", "operation_id": operation_id,
                "reason": reason, "recovery_required": True, "automatic_clear_allowed": False}, exclusive=True)
        except (OSError, VersionError):
            # The existing unfinished state/lock still refuses admission if publication fails.
            raise VersionError("validation_quarantined") from None


def _admission_state(scope):
    if os.path.lexists(scope / "quarantine.json"):
        raise VersionError("validation_quarantined")
    for count, operation in enumerate((scope / "operations").iterdir(), 1):
        try:
            require(count <= OPERATION_CAP and stat.S_ISDIR(_metadata(operation).st_mode)
                and len(operation.name) == 32 and all(c in "0123456789abcdef" for c in operation.name),
                "validation_quarantined")
            state = _json(_read_file(operation / "state.json", RESULT_CAP))
            require(type(state) is dict and set(state) == {"status", "operation_id"}
                and type(state["status"]) is str and state["status"] == "finished"
                and type(state["operation_id"]) is str and state["operation_id"] == operation.name,
                "validation_quarantined")
        except (OSError, VersionError):
            _quarantine_scope(scope, operation.name, "unfinished_operation")
            raise VersionError("validation_quarantined") from None
    return scope


def validation_admission(scope=None):
    """Root47 must call this before EVERY successor command, including after nested suites."""
    scope = _scope_path(scope)
    if os.path.lexists(scope / "admission.lock"):
        _quarantine_scope(scope, None, "admission_owner_unknown")
        raise VersionError("validation_quarantined")
    return _admission_state(scope)


def begin_validation_operation(scope=None):
    scope = _scope_path(scope)
    lock = scope / "admission.lock"
    try:
        with lock.open("xb") as handle:
            handle.write(b"exclusive validation admission\n")
    except FileExistsError:
        _quarantine_scope(scope, None, "admission_owner_unknown")
        raise VersionError("validation_quarantined") from None
    try:
        _admission_state(scope)
        require(len(list((scope / "operations").iterdir())) < OPERATION_CAP, "operation_limit")
        identity = uuid.uuid4().hex
        path = scope / "operations" / identity
        path.mkdir()
        operation = {"scope": scope, "path": path, "id": identity}
        _write_json(path / "state.json", {"status": "running", "operation_id": identity}, exclusive=True)
        _write_json(path / "environment.json", {"TEMP": tempfile.gettempdir(),
            "CI": os.environ.get("CI"), "GITHUB_ACTIONS": os.environ.get("GITHUB_ACTIONS"),
            "executable": sys.executable, "interpreter_sha256": sha(Path(sys.executable).resolve().read_bytes()),
            "python_version": sys.version}, exclusive=True)
        return operation
    finally:
        lock.unlink()


def quarantine_operation(operation, reason):
    _quarantine_scope(operation["scope"], operation["id"], reason)
    _write_json(operation["path"] / "state.json", {"status": "quarantined",
        "operation_id": operation["id"], "reason": reason})


def _finish_operation(operation):
    if not os.path.lexists(operation["scope"] / "quarantine.json"):
        _write_json(operation["path"] / "state.json", {"status": "finished", "operation_id": operation["id"]})


def _test_ids(raw, selector=None):
    tree = ast.parse(raw)
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_") and selector is None:
            found.append(node.name)
        elif isinstance(node, ast.ClassDef) and (selector is None or node.name == selector):
            found += [node.name + "." + child.name for child in node.body
                      if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_")]
    require(len(found) == len(set(found)) and len(found) <= 64, "test_ids_mismatch")
    return sorted(found)


def adapter_sources(selected, objects):
    selected = _selection(selected)
    require(selected["profile_id"] == "git-lf", "unknown_profile")
    fixed = _profile_bodies(selected, objects)
    head = _git_bytes("rev-parse", "HEAD^{commit}").decode("ascii").strip()
    tree = _git_bytes("rev-parse", "HEAD^{tree}").decode("ascii").strip()
    listing = _git_bytes("ls-tree", "-z", head, "--", *CURRENT_MEMBERS)
    current = {}
    metadata = []
    for entry in listing.split(b"\0")[:-1]:
        fields, name = entry.decode("ascii").split("\t")
        mode, kind, blob = fields.split()
        require(name in CURRENT_MEMBERS and mode == "100644" and kind == "blob", "source_mismatch")
        raw = _git_bytes("cat-file", "blob", blob)
        physical = _read_file(ROOT / name, FILE_CAP)
        require(physical.replace(b"\r\n", b"\n") == raw, "source_mismatch")
        current[name] = raw
        metadata.append({"path": name, "mode": mode, "blob": blob, "canonical_sha256": sha(raw),
                         "raw_sha256": sha(physical), "raw_bytes": len(physical)})
    require(set(current) == set(CURRENT_MEMBERS), "source_mismatch")
    require(_git_bytes("rev-parse", "HEAD^{commit}").decode("ascii").strip() == head, "source_mismatch")
    bodies = {name: fixed[name] for name in DEPENDENCIES}
    bodies.update(current)
    require(len(bodies) == 8 and sum(map(len, bodies.values())) <= TOTAL_CAP
            and all(len(raw) <= FILE_CAP for raw in bodies.values()), "source_mismatch")
    require(tuple(_test_ids(bodies["tests/test_w40_native.py"], ADAPTER_CLASS)) == ADAPTER_IDS, "test_ids_mismatch")
    identity = {"dependency_identity": {"contract_id": selected["contract_id"],
        "engine_source_commit": selected["registry"]["engine_source_commit"],
        "source_tree": selected["registry"]["source_tree"], "profile": "git-lf",
        "registry_sha256": REGISTRY_SHA256,
        "members": [row for row in selected["registry"]["members"] if row["path"] in DEPENDENCIES]},
        "current_adapter_identity": {"candidate_commit": head, "candidate_tree": tree, "members": metadata}}
    return bodies, identity


def _view_seal(view, bodies):
    expected = set(bodies) | {".git"}
    files = set()
    visited = 0
    for path in view.rglob("*"):
        visited += 1
        require(visited <= 4 * MEMBER_CAP, "unsafe_source_view")
        info = _metadata(path)
        if stat.S_ISREG(info.st_mode):
            require(info.st_nlink == 1, "unsafe_source_view")
            files.add(path.relative_to(view).as_posix())
        else:
            require(stat.S_ISDIR(info.st_mode), "unsafe_source_view")
    require(files == expected and _read_file(view / ".git", 256) == MARKER, "source_mismatch")
    for name, raw in bodies.items():
        require(_read_file(view / name, FILE_CAP) == raw, "source_mismatch")
    return sha(encoded({name: sha(raw) for name, raw in bodies.items()}))


def _materialize_test_view(operation, bodies):
    require(len(bodies) <= MEMBER_CAP and sum(map(len, bodies.values())) <= TOTAL_CAP, "source_mismatch")
    view = operation["path"] / "source"
    view.mkdir()
    for name, raw in bodies.items():
        path = view / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
    with (view / ".git").open("xb") as handle:
        handle.write(MARKER)
    _view_seal(view, bodies)
    return view


def test_execution_qualified(observation, expected_ids):
    """Execution evidence and complete descendant telemetry are different predicates."""
    try:
        runtime = observation["runtime"]
        ids = observation["executed_test_ids"]
        lifecycle = observation["outer_lifecycle"]
        deep = observation["descendant_observations"]
        return (observation["child_exit_code"] == 0 and type(observation["child_exit_code"]) is int
            and sorted(ids) == sorted(expected_ids) and len(ids) == len(set(ids))
            and runtime["predicates"] == {"code_manifest": True, "engine_bindings": True}
            and runtime["interpreter_sha256"] == sha(Path(sys.executable).resolve().read_bytes())
            and lifecycle["final_observed"] is True and lifecycle["uncertain"] is False
            and not any(observation[key] for key in ("timed_out", "interrupted", "overflow"))
            and observation["stdout_complete"] is True and observation["stderr_complete"] is True
            and observation["descendant_observations_complete"] is False
            and bool(deep) and all(item.get("exit_code") is None and item.get("command") is None
                for item in deep if item.get("state") == "not_recorded"))
    except (KeyError, TypeError, ValueError):
        return False


def _uncertain(observation):
    lifecycle = observation.get("outer_lifecycle", {})
    return (any(observation.get(key) for key in ("timed_out", "interrupted", "overflow"))
            or lifecycle.get("final_observed") is not True or lifecycle.get("uncertain") is not False
            or observation.get("stdout_complete") is not True or observation.get("stderr_complete") is not True)


_TEST_CHILD_SCRIPT = r'''
import ast, hashlib, json, os, runpy, stat, subprocess, sys, traceback
from pathlib import Path
def encoded(value): return json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()
payload=json.loads(sys.stdin.buffer.read(131073))
root=Path(sys.argv[1]); report_path=Path(sys.argv[2]); runner=root/payload["runner"]
ids=[]; nested_ids=[]; direct={}; audit_events=[]; runner_globals={}; runtime=None; uncertain=False; exit_code=1
popen_type=subprocess.Popen
audit_dropped=0; nested_dropped=0; direct_dropped=0; ids_dropped=0
def command(value):
    if isinstance(value,str): return {"representation":"command_line","value":value}
    if isinstance(value,(list,tuple)): return {"representation":"argv_sequence","value":[str(v) for v in value]}
    return {"representation":"not_recorded","value":None}
def audit(event,args):
    global audit_dropped
    if event=="subprocess.Popen":
        if len(audit_events)<256:
            audit_events.append({"observation_source":"python_audit_subprocess.Popen", "command":command(args[1]),"pid":None})
        else: audit_dropped+=1
def observe(frame,event,arg):
    global runner_globals,uncertain,nested_dropped,direct_dropped,ids_dropped
    code=frame.f_code
    if event=="call" and code.co_filename==str(runner):
        runner_globals=frame.f_globals
        if code.co_name.startswith("test_"):
            caller=frame.f_back; nested=False
            while caller is not None:
                if caller.f_code.co_filename==str(runner) and caller.f_code.co_name.startswith("test_"):
                    nested=True; break
                caller=caller.f_back
            if nested:
                if len(nested_ids)<256: nested_ids.append(code.co_qualname)
                else: nested_dropped+=1
            elif len(ids)<65: ids.append(code.co_qualname)
            else: ids_dropped+=1
    obj=frame.f_locals.get("self")
    if event=="return" and code.co_name=="__init__" and isinstance(obj,popen_type) and getattr(obj,"pid",None):
        if id(obj) in direct or len(direct)<256: direct[id(obj)]=obj
        else: uncertain=True; direct_dropped+=1
    if event=="call" and code.co_name=="addError":
        error=frame.f_locals.get("err")
        if isinstance(error,tuple) and len(error)>1 and type(error[1]).__name__=="NativeError" and str(error[1])=="cleanup_uncertain":
            uncertain=True
sys.addaudithook(audit)
try:
    for member in payload["members"]:
        path=root/member["path"]; info=path.lstat(); raw=path.read_bytes()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not getattr(info,"st_file_attributes",0)&0x400
        assert len(raw)==member["bytes"] and sha(raw)==member["sha256"]
    sys.path[:0]=[str(root/"bench"),str(root/"src")]
    import w40_native as native, w40_evidence as core, risk
    manifest=native.code_manifest(); native.engine_bindings(risk)
    for module,name in ((native,"bench/w40_native.py"),(core,"bench/w40_evidence.py"),(risk,"src/risk.py")):
        assert Path(module.__file__).resolve()==(root/name).resolve()
    runtime={"predicates":{"code_manifest":True,"engine_bindings":True},"interpreter_sha256":sha(Path(sys.executable).resolve().read_bytes()),
        "module_files":{"risk":"src/risk.py","native":"bench/w40_native.py","core":"bench/w40_evidence.py"},
        "manifest_sha256":sha(encoded(manifest)),"test_process_pid":os.getpid(),
        "validation_operation_id":payload["operation_id"]}
    sys.argv=[str(runner)]+([payload["selector"]] if payload["selector"] else [])
    sys.setprofile(observe)
    try:
        runpy.run_path(str(runner),run_name="__main__")
        exit_code=0
    except SystemExit as error:
        exit_code=0 if error.code is None else error.code if type(error.code) is int else 1
    except BaseException as error:
        uncertain|=type(error).__name__=="NativeError" and str(error)=="cleanup_uncertain"
        traceback.print_exc(); exit_code=1
    finally:
        sys.setprofile(None)
except BaseException:
    traceback.print_exc(); exit_code=2
observations=[]
for process in direct.values():
    pid=process.pid
    try:
        status=process.poll()
        uncertain|=status is None
        observations.append({"pid":pid,"command":command(process.args),"exit_code":status,
            "state":"observed" if status is not None else "unknown","observation_source":"actual_Popen.poll"})
    except BaseException:
        uncertain=True
        observations.append({"pid":pid,"command":None,"exit_code":None,"state":"unknown","observation_source":"poll_unavailable"})
observations.append({"command":None,"exit_code":None,"state":"not_recorded","observation_source":"not_recorded"})
counters=None
if "_PASSED" in runner_globals and "_FAILURES" in runner_globals and "_UNCHECKED" in runner_globals:
    counters={"passed":runner_globals["_PASSED"],"failed":len(runner_globals["_FAILURES"]),"not_checked":len(runner_globals["_UNCHECKED"])}
report={"executed_test_ids":ids,"runtime":runtime,"outer_lifecycle":{"final_observed":True,"uncertain":uncertain},
    "nested_test_function_calls":nested_ids,
    "descendant_observations_complete":False,"descendant_observations":observations,
    "audit_command_observations":audit_events,"harness_assertion_evidence":"original_harness_assertions",
    "observation_dropped":{"audit":audit_dropped,"nested_test_calls":nested_dropped,"direct_children":direct_dropped,"top_test_ids":ids_dropped},
    "dynamic_counters":counters,"reported_original_exit":exit_code,
    "environment":{"TEMP":__import__('tempfile').gettempdir(),"CI":os.environ.get("CI"),"GITHUB_ACTIONS":os.environ.get("GITHUB_ACTIONS"),
        "executable":sys.executable,"python_version":sys.version}}
report["evidence_sha256"]=sha(encoded(report))
with report_path.open("xb") as handle: handle.write(encoded(report)); handle.flush(); os.fsync(handle.fileno())
raise SystemExit(exit_code)
'''


def _launch_test_child(view, runner, expected_ids, seconds, operation, selector=None):
    """Bounded parent observation; uncertainty retains the view and never kills a process tree."""
    path = operation["path"]
    members = [{"path": p.relative_to(view).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha(_read_file(p, FILE_CAP))} for p in view.rglob("*") if p.is_file()]
    require(len(members) <= MEMBER_CAP + 1, "source_mismatch")
    payload = {"members": members, "runner": runner, "selector": selector, "operation_id": operation["id"]}
    command = [sys.executable, "-I", "-S", "-B", "-c", _TEST_CHILD_SCRIPT, str(view), str(path / "child-report.json")]
    _write_json(path / "child-intent.json", {"argv": command, "runner": runner,
        "selector": selector, "seconds": seconds, "stream_cap": STREAM_CAP}, exclusive=True)
    start = time.monotonic()
    overflow = threading.Event()
    captures = {}
    threads = []
    process = None
    timed_out = interrupted = False
    def capture(pipe, name):
        state = captures[name]
        try:
            with (path / name).open("xb") as handle:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk:
                        break
                    with state["lock"]:
                        piece = chunk[:max(0, STREAM_CAP - len(state["raw"]))]
                        state["raw"].extend(piece)
                        handle.write(piece)
                        handle.flush()
                        state["observed_bytes"] += len(chunk)
                        if state["observed_bytes"] > STREAM_CAP:
                            overflow.set()
        except BaseException:
            state["error"] = True
        finally:
            pipe.close()
            state["ended"] = True
    try:
        operation["launch_attempted"] = True
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=view, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
        _write_json(path / "child-process.json", {"pid": process.pid, "argv": command}, exclusive=True)
        for name, pipe in (("stdout.log", process.stdout), ("stderr.log", process.stderr)):
            captures[name] = {"lock": threading.Lock(), "raw": bytearray(), "observed_bytes": 0, "ended": False, "error": False}
            thread = threading.Thread(target=capture, args=(pipe, name), daemon=True)
            thread.start()
            threads.append(thread)
        process.stdin.write(encoded(payload))
        process.stdin.close()
        while process.poll() is None:
            if overflow.is_set():
                break
            if time.monotonic() - start >= seconds:
                timed_out = True
                break
            time.sleep(.02)
    except BaseException:
        interrupted = True
    actual_exit = process.poll() if process is not None else None
    operation["child_exit_code"] = actual_exit
    if actual_exit is not None:
        for thread in threads:
            thread.join(timeout=1)
    report = {}
    try:
        report = _json(_read_file(path / "child-report.json", STREAM_CAP))
        evidence = report.pop("evidence_sha256")
        require(evidence == sha(encoded(report)), "child_protocol_invalid")
        require(report["reported_original_exit"] == actual_exit, "child_protocol_invalid")
        if report.get("runtime") is not None:
            require(report["runtime"].get("test_process_pid") == process.pid
                and report["runtime"].get("validation_operation_id") == operation["id"], "child_protocol_invalid")
    except (VersionError, KeyError, TypeError, AttributeError):
        report = {}
    observation = dict(report)
    observation.update(child_exit_code=actual_exit, timed_out=timed_out, interrupted=interrupted,
        overflow=overflow.is_set(), elapsed_seconds=time.monotonic() - start)
    for name, field in (("stdout.log", "stdout"), ("stderr.log", "stderr")):
        state = captures.get(name)
        if state is None:
            raw, complete = b"", False
        else:
            with state["lock"]:
                raw = bytes(state["raw"])
                complete = state["ended"] and not state["error"] and state["observed_bytes"] <= STREAM_CAP
        observation[field + "_sha256"] = sha(raw)
        observation[field + "_complete"] = complete
        observation[field + "_recorded_bytes"] = len(raw)
    if not report or any(thread.is_alive() for thread in threads):
        observation["outer_lifecycle"] = {"final_observed": False, "uncertain": True}
    if _uncertain(observation):
        quarantine_operation(operation, "outer_lifecycle_uncertain")
    _write_json(path / "observation.json", observation, exclusive=True, cap=STREAM_CAP)
    if not _uncertain(observation) and not operation.get("dispatch_managed"):
        _finish_operation(operation)
    return observation


def _dispatch(contract_id, profile_id, runner, *, adapter=False, scope=None):
    operation_name = "adapter-test" if adapter else "legacy-test"
    result = _receipt(None, profile_id)
    result.update(operation=operation_name, command_argv=["python", "tools/engine_versions.py", operation_name],
        test_execution_qualified=False, descendant_observations_complete=False,
        descendant_observations=[{"command": None, "exit_code": None, "state": "not_recorded",
                                  "observation_source": "not_recorded"}])
    key = "adapter_tests" if adapter else "legacy_tests"
    if adapter:
        result.update(schema="engine-adapter-regression-v1", domain="current_adapter_on_v1_dependencies",
            original_v1_fixture_qualified_by_adapter_result=False, current_production_behavior_qualified=False)
        result[key] = dict(result["legacy_tests"])
    operation = None
    phase = "selection_and_admission"
    try:
        selected = select(load_registry(), contract_id, profile_id)
        require(runner == ADAPTER_CLASS if adapter else runner in RUNNERS,
                "unknown_test_context" if adapter else "unknown_runner")
        require(not adapter or profile_id == "git-lf", "unknown_profile")
        result.update(contract_id=contract_id, requested_profile=profile_id, selected_profile=profile_id,
            role="current_adapter_on_v1_dependencies" if adapter else "historical_v1",
            engine_source_commit=selected["registry"]["engine_source_commit"], source_tree=selected["registry"]["source_tree"],
            original_runner=None if adapter else runner,
            command_argv=["python", "tools/engine_versions.py", operation_name, contract_id, profile_id, runner])
        operation = begin_validation_operation(scope)
        operation["dispatch_managed"] = True
        phase = "source_materialization"
        objects = read_objects(selected)
        if adapter:
            bodies, identity = adapter_sources(selected, objects)
            result.update(identity)
            selected_runner, selector, seconds = "tests/test_w40_native.py", ADAPTER_CLASS, 120
            expected = list(ADAPTER_IDS)
        else:
            bodies = _profile_bodies(selected, objects)
            selected_runner, selector = runner, None
            count, seconds = RUNNERS[runner]
            expected = _test_ids(bodies[runner])
            require(len(expected) == count, "test_ids_mismatch")
        view = _materialize_test_view(operation, bodies)
        seal = _view_seal(view, bodies)
        if not adapter:
            verify_view(view, selected)
        result["source_fixture"] = _layer("passed", evidence=[seal])
        result["context_manifest_sha256"] = seal
        phase = "child_observation"
        operation["launch_attempted"] = True
        observed = _launch_test_child(view, selected_runner, expected, seconds, operation, selector=selector)
        operation["child_exit_code"] = observed.get("child_exit_code")
        phase = "postlaunch_source_check"
        result[key] = {"status": "failed", "child_exit_code": observed.get("child_exit_code"),
            "executed_test_ids": observed.get("executed_test_ids", []),
            "executed_test_ids_sha256": sha(encoded(observed.get("executed_test_ids", []))),
            "stdout_sha256": observed.get("stdout_sha256"), "stderr_sha256": observed.get("stderr_sha256"),
            "dynamic_counters": observed.get("dynamic_counters")}
        _view_seal(view, bodies)
        if adapter:
            _, after_identity = adapter_sources(selected, read_objects(selected))
            require(after_identity == identity, "source_mismatch")
        else:
            verify_view(view, selected)
        result["descendant_observations_complete"] = False
        result["descendant_observations"] = [{"command": None, "exit_code": None,
            "state": "not_recorded", "observation_source": "not_recorded"}]
        result["direct_observations_evidence_sha256"] = sha(encoded(observed.get("descendant_observations", [])))
        runtime = observed.get("runtime")
        if runtime and runtime.get("predicates") == {"code_manifest": True, "engine_bindings": True}:
            result["loaded_runtime"] = _layer("passed", evidence=[sha(encoded(runtime))])
        else:
            result["loaded_runtime"] = _layer("failed", "runtime_mismatch")
        qualified = test_execution_qualified(observed, expected)
        if selected_runner == "tests/test_dataset_replayable.py":
            counters = observed.get("dynamic_counters")
            qualified = (qualified and type(counters) is dict
                and set(counters) == {"passed", "failed", "not_checked"}
                and all(type(v) is int and v >= 0 for v in counters.values()) and counters["failed"] == 0)
        actual = observed.get("child_exit_code")
        result[key] = {"status": "passed" if qualified else "failed", "child_exit_code": actual,
            "executed_test_ids": observed.get("executed_test_ids", []),
            "executed_test_ids_sha256": sha(encoded(observed.get("executed_test_ids", []))),
            "stdout_sha256": observed.get("stdout_sha256"), "stderr_sha256": observed.get("stderr_sha256"),
            "dynamic_counters": observed.get("dynamic_counters")}
        result.update(test_execution_qualified=qualified, invocation_status="completed" if qualified else "failed",
            wrapper_exit_code=0 if qualified else actual if type(actual) is int and 1 <= actual <= 255 else 2)
        if _uncertain(observed):
            reason = "test_timeout" if observed.get("timed_out") else "test_output_limit" if observed.get("overflow") else "test_interrupted"
            quarantine_operation(operation, reason)
            result["reason"] = reason
        else:
            result["reason"] = None if qualified else "test_failed"
        phase = "receipt_validation"
        validate_dispatch_receipt(result)
        phase = "receipt_publication"
        _write_json(operation["path"] / "receipt.json", result, exclusive=True)
        phase = "operation_completion"
        _finish_operation(operation)
        return result
    except VersionError as error:
        result.update(reason=error.code, invocation_status="refused", wrapper_exit_code=2, test_execution_qualified=False)
        if error.code in {"source_mismatch", "unsafe_source_view"} and result["source_fixture"]["status"] == "passed":
            result["source_fixture"] = _layer("failed", error.code)
            result["loaded_runtime"] = _layer(reason="source_mismatch")
        if operation and not operation.get("launch_attempted"):
            _finish_operation(operation)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        result.update(reason="child_protocol_invalid", invocation_status="failed", wrapper_exit_code=2,
                      test_execution_qualified=False)
    if operation and operation.get("launch_attempted"):
        # Generic evidence failure cannot establish retirement, even with a known top exit.
        result.update(invocation_status="failed", wrapper_exit_code=2, test_execution_qualified=False)
        result[key] = {"status": "failed", "child_exit_code": operation.get("child_exit_code"),
            "executed_test_ids": [], "executed_test_ids_sha256": sha(encoded([])),
            "stdout_sha256": None, "stderr_sha256": None, "dynamic_counters": None}
        try:
            quarantine_operation(operation, "child_protocol_invalid")
        except (OSError, VersionError):
            pass  # Keep the initial running state: admission still refuses it.
        try:
            _write_json(operation["path"] / "failure-stage.json", {"schema": "validation-evidence-failure-v1",
                "operation_id": operation["id"], "phase": phase, "reason": result["reason"],
                "actual_child_exit_code": operation.get("child_exit_code"), "wrapper_exit_code": 2}, exclusive=True)
            _write_json(operation["path"] / "failure.json", result, exclusive=True)
        except (OSError, VersionError):
            pass  # Retain the selected view and all successfully recorded partial evidence.
    return result


# Maintained execution has its own closed context and receipt domain.
MAINTAINED_RUNNERS = {"native-all16": ("tests/test_w40_native.py", 16, 900),
                      "clock-all3": ("tests/test_w40_native_clock.py", 3, 180)}
MAINTAINED_DOMAIN = "maintained_adapter_on_fixed_v1_dependencies"
MAINTAINED_IDS_SHA256 = {"native-all16": "bf5a5ec99635d00e8b331396850d3a1c5e6a9c4e0e9d3cc7cdcabd3e9ab3d3af",
                         "clock-all3": RUNNER_IDS_SHA256["tests/test_w40_native_clock.py"]}


def maintained_context_sources(selected, objects, selector):
    """Compose exactly native9 or clock8, without importing a source member."""
    selected = _selection(selected)
    require(selected["profile_id"] == "git-lf", "unknown_profile")
    require(type(selector) is str and selector in MAINTAINED_RUNNERS, "unknown_test_context")
    fixed = _profile_bodies(selected, objects)
    paths = CURRENT_MEMBERS if selector == "native-all16" else ("bench/w40_native.py",)
    support = ".github/workflows/test.yml" if selector == "native-all16" else "tests/test_w40_native_clock.py"
    head = _git_bytes("rev-parse", "HEAD^{commit}").decode("ascii").strip()
    tree = _git_bytes("rev-parse", head + "^{tree}").decode("ascii").strip()
    listing = _git_bytes("ls-tree", "-z", head, "--", *paths)
    current, metadata = {}, []
    require(listing.endswith(b"\0"), "source_mismatch")
    for entry in listing.split(b"\0")[:-1]:
        fields, name = entry.decode("ascii").split("\t")
        mode, kind, blob = fields.split()
        require(name in paths and name not in current and mode == "100644" and kind == "blob", "source_mismatch")
        require(0 < int(_git_bytes("cat-file", "-s", blob)) <= FILE_CAP, "source_mismatch")
        raw = _git_bytes("cat-file", "blob", blob)
        physical = _read_file(ROOT / name, FILE_CAP)
        require(physical.replace(b"\r\n", b"\n") == raw, "source_mismatch")
        require(hashlib.sha1(("blob %d\0" % len(raw)).encode("ascii") + raw).hexdigest() == blob, "source_mismatch")
        current[name] = raw
        metadata.append({"path": name, "mode": mode, "blob": blob, "canonical_sha256": sha(raw),
                         "raw_sha256": sha(physical), "raw_bytes": len(physical)})
    require(set(current) == set(paths), "source_mismatch")
    bodies = {name: fixed[name] for name in DEPENDENCIES}
    bodies[support] = fixed[support]
    bodies.update(current)
    require(len(bodies) == (9 if selector == "native-all16" else 8)
        and len(bodies) <= MEMBER_CAP and sum(map(len, bodies.values())) <= TOTAL_CAP
        and all(len(raw) <= FILE_CAP for raw in bodies.values()), "source_mismatch")
    runner, count, _ = MAINTAINED_RUNNERS[selector]
    ids = _test_ids(bodies[runner])
    require(len(ids) == count and sha(encoded(ids)) == MAINTAINED_IDS_SHA256[selector], "test_ids_mismatch")
    registry = selected["registry"]
    def fixed_identity(names):
        return {"contract_id": registry["contract_id"], "engine_source_commit": registry["engine_source_commit"],
            "source_tree": registry["source_tree"], "profile": "git-lf", "registry_sha256": REGISTRY_SHA256,
            "members": [row for row in registry["members"] if row["path"] in names]}
    identity = {"dependency_identity": fixed_identity(DEPENDENCIES), "support_identity": fixed_identity((support,)),
        "current_adapter_identity": {"candidate_commit": head, "candidate_tree": tree, "members": metadata}}
    require(_git_bytes("rev-parse", "HEAD^{commit}").decode("ascii").strip() == head, "source_mismatch")
    return bodies, identity


def _maintained_receipt(profile_id=None):
    return {"schema": "engine-maintained-adapter-execution-v1", "operation": "maintained-test",
        "domain": MAINTAINED_DOMAIN, "invocation_status": "refused", "contract_id": None, "role": None,
        "engine_source_commit": None, "source_tree": None,
        "requested_profile": "git-lf" if profile_id == "git-lf" else None, "selected_profile": None,
        "selector": None, "maintained_runner": None, "command_argv": ["python", "tools/engine_versions.py", "maintained-test"],
        "context_source": _layer(), "maintained_loaded_runtime": _layer(),
        "historical_record_tuple": _layer(reason="historical_record_not_supplied"),
        "historical_interpreter": _layer(reason="historical_interpreter_not_examined"),
        "maintained_tests": {"status": "not_run", "executed_test_ids_sha256": None, "stdout_sha256": None,
            "stderr_sha256": None, "child_exit_code": None},
        "test_execution_qualified": False, "historical_execution_qualified": False,
        "original_v1_fixture_qualified_by_maintained_result": False, "current_production_behavior_qualified": False,
        "v2_historical_native_positive_compatibility": "unsupported", "descendant_observations_complete": False,
        "descendant_observations": [{"command": None, "exit_code": None, "state": "not_recorded", "observation_source": "not_recorded"}],
        "wrapper_exit_code": 2, "reason": None}


def _maintained_receipt_members(value, registry):
    """Validate named immutable identities, not the authenticity of an execution."""
    error = "invalid_result_layers"
    selector = value["selector"]
    paths = CURRENT_MEMBERS if selector == "native-all16" else ("bench/w40_native.py",)
    support = ".github/workflows/test.yml" if selector == "native-all16" else "tests/test_w40_native_clock.py"
    for key, names in (("dependency_identity", DEPENDENCIES), ("support_identity", (support,))):
        expected = {"contract_id": registry["contract_id"], "engine_source_commit": registry["engine_source_commit"],
            "source_tree": registry["source_tree"], "profile": "git-lf", "registry_sha256": REGISTRY_SHA256,
            "members": [row for row in registry["members"] if row["path"] in names]}
        require(type(value[key]) is dict and value[key] == expected, error)
    current = value["current_adapter_identity"]
    require(type(current) is dict and set(current) == {"candidate_commit", "candidate_tree", "members"}
        and _digest(current["candidate_commit"], 40) and _digest(current["candidate_tree"], 40), error)
    require(_git_bytes("rev-parse", current["candidate_commit"] + "^{tree}").decode("ascii").strip()
        == current["candidate_tree"], error)
    listing = _git_bytes("ls-tree", "-z", current["candidate_commit"], "--", *paths)
    actual = {}
    require(listing.endswith(b"\0"), error)
    for entry in listing.split(b"\0")[:-1]:
        fields, name = entry.decode("ascii").split("\t")
        mode, kind, blob = fields.split()
        require(name in paths and name not in actual and mode == "100644" and kind == "blob", error)
        actual[name] = blob
    require(set(actual) == set(paths), error)
    members = current["members"]
    require(type(members) is list and len(members) == len(paths), error)
    fixed = read_objects(select(registry, registry["contract_id"], "git-lf"))
    bodies = {name: fixed[name] for name in (*DEPENDENCIES, support)}
    seen = set()
    for member in members:
        require(type(member) is dict and set(member) == {"path", "mode", "blob", "canonical_sha256", "raw_sha256", "raw_bytes"}, error)
        name = member["path"]
        require(type(name) is str and name in paths and name not in seen and member["mode"] == "100644"
            and _digest(member["blob"], 40) and member["blob"] == actual[name]
            and _digest(member["canonical_sha256"]) and _digest(member["raw_sha256"])
            and type(member["raw_bytes"]) is int and 0 < member["raw_bytes"] <= FILE_CAP, error)
        require(0 < int(_git_bytes("cat-file", "-s", member["blob"])) <= FILE_CAP, error)
        raw = _git_bytes("cat-file", "blob", member["blob"])
        require(sha(raw) == member["canonical_sha256"] and len(raw) <= member["raw_bytes"] <= 2 * len(raw), error)
        if len(raw) == member["raw_bytes"]:
            require(member["raw_sha256"] == member["canonical_sha256"], error)
        seen.add(name)
        bodies[name] = raw
    require(len(bodies) == (9 if selector == "native-all16" else 8)
        and sum(map(len, bodies.values())) <= TOTAL_CAP, error)
    runner, count, _ = MAINTAINED_RUNNERS[selector]
    ids = _test_ids(bodies[runner])
    require(len(ids) == count and sha(encoded(ids)) == MAINTAINED_IDS_SHA256[selector], "test_ids_mismatch")
    return sha(encoded({name: sha(raw) for name, raw in bodies.items()})), ids


def validate_maintained_receipt(value):
    """Separate closed domain; never widen the historical or staging validators."""
    error = "invalid_result_layers"
    try:
        require(type(value) is dict and len(encoded(value)) <= RESULT_CAP, error)
        required = set(_maintained_receipt())
        optional = {"dependency_identity", "support_identity", "current_adapter_identity",
                    "context_manifest_sha256", "direct_observations_evidence_sha256"}
        require(required <= set(value) <= required | optional, error)
        require(value["schema"] == "engine-maintained-adapter-execution-v1" and value["operation"] == "maintained-test"
            and value["domain"] == MAINTAINED_DOMAIN, error)
        require(all(value[key] is False for key in ("historical_execution_qualified", "current_production_behavior_qualified",
            "original_v1_fixture_qualified_by_maintained_result", "descendant_observations_complete")), error)
        require(value["v2_historical_native_positive_compatibility"] == "unsupported"
            and value["descendant_observations"] == _maintained_receipt()["descendant_observations"], error)
        _validate_result_layers(dict(value, source_fixture=value["context_source"], loaded_runtime=value["maintained_loaded_runtime"]))
        require(type(value["test_execution_qualified"]) is bool and type(value["wrapper_exit_code"]) is int
            and 0 <= value["wrapper_exit_code"] <= 255, error)
        require(value["reason"] is None or type(value["reason"]) is str and value["reason"] in REASONS, error)
        registry = load_registry()
        profile, selector = value["selected_profile"], value["selector"]
        require(value["requested_profile"] is None or value["requested_profile"] == "git-lf", error)
        expected_ids, expected_seal = None, None
        if profile is None:
            require(all(value[key] is None for key in ("contract_id", "role", "engine_source_commit", "source_tree", "selector", "maintained_runner"))
                and value["command_argv"] == ["python", "tools/engine_versions.py", "maintained-test"]
                and value["context_source"]["status"] != "passed" and not optional & set(value), error)
        else:
            require(type(profile) is str and profile == value["requested_profile"] == "git-lf"
                and type(selector) is str and selector in MAINTAINED_RUNNERS
                and value["contract_id"] == registry["contract_id"] and value["role"] == MAINTAINED_DOMAIN
                and value["engine_source_commit"] == registry["engine_source_commit"] and value["source_tree"] == registry["source_tree"]
                and value["maintained_runner"] == MAINTAINED_RUNNERS[selector][0]
                and value["command_argv"] == ["python", "tools/engine_versions.py", "maintained-test", registry["contract_id"], profile, selector], error)
            identity_keys = {"dependency_identity", "support_identity", "current_adapter_identity"}
            if identity_keys & set(value) or value["context_source"]["status"] == "passed":
                require(identity_keys <= set(value), error)
                expected_seal, expected_ids = _maintained_receipt_members(value, registry)
        if "context_manifest_sha256" in value:
            require(_digest(value["context_manifest_sha256"]) and value["context_manifest_sha256"] == expected_seal, error)
        if value["context_source"]["status"] == "passed":
            require(value.get("context_manifest_sha256") == expected_seal
                and value["context_source"]["evidence_sha256"] == [expected_seal], error)
        if "direct_observations_evidence_sha256" in value:
            require(_digest(value["direct_observations_evidence_sha256"]), error)
        test = value["maintained_tests"]
        base = _maintained_receipt()["maintained_tests"]
        require(type(test) is dict and type(test.get("status")) is str and test["status"] in {"passed", "failed", "not_run"}, error)
        if test["status"] == "not_run":
            require(test == base, error)
        else:
            require(profile is not None and set(test) == set(base) | {"executed_test_ids", "dynamic_counters"}, error)
            ids = test["executed_test_ids"]
            require(type(ids) is list and len(ids) <= 64 and all(type(item) is str for item in ids)
                and ids == sorted(set(ids)) and test["executed_test_ids_sha256"] == sha(encoded(ids)), "test_ids_mismatch")
            require(test["child_exit_code"] is None or type(test["child_exit_code"]) is int, error)
            require(all(test[key] is None or _digest(test[key]) for key in ("stdout_sha256", "stderr_sha256"))
                and test["dynamic_counters"] is None, error)
        if value["test_execution_qualified"]:
            require(profile is not None and value["invocation_status"] == "completed" and value["reason"] is None
                and value["wrapper_exit_code"] == 0 and test["status"] == "passed"
                and type(test["child_exit_code"]) is int and test["child_exit_code"] == 0
                and value["context_source"]["status"] == value["maintained_loaded_runtime"]["status"] == "passed"
                and _digest(value.get("direct_observations_evidence_sha256"))
                and all(_digest(test[key]) for key in ("stdout_sha256", "stderr_sha256")), error)
            require(expected_ids is not None and test["executed_test_ids"] == expected_ids, "test_ids_mismatch")
        else:
            require(type(value["invocation_status"]) is str and value["invocation_status"] in {"refused", "failed"}
                and value["reason"] is not None and value["wrapper_exit_code"] != 0 and test["status"] != "passed", error)
        return value
    except VersionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, RecursionError, OverflowError):
        raise VersionError("invalid_result_layers") from None


def maintained_test(contract_id, profile_id, selector, *, scope=None):
    result = _maintained_receipt(profile_id)
    operation = None
    phase = "selection_and_admission"
    try:
        selected = select(load_registry(), contract_id, profile_id)
        require(profile_id == "git-lf", "unknown_profile")
        require(type(selector) is str and selector in MAINTAINED_RUNNERS, "unknown_test_context")
        runner, count, seconds = MAINTAINED_RUNNERS[selector]
        result.update(contract_id=contract_id, requested_profile=profile_id, selected_profile=profile_id,
            role=MAINTAINED_DOMAIN, selector=selector, maintained_runner=runner,
            engine_source_commit=selected["registry"]["engine_source_commit"], source_tree=selected["registry"]["source_tree"],
            command_argv=["python", "tools/engine_versions.py", "maintained-test", contract_id, profile_id, selector])
        operation = begin_validation_operation(scope)
        operation["dispatch_managed"] = True
        phase = "source_materialization"
        bodies, identity = maintained_context_sources(selected, read_objects(selected), selector)
        result.update(identity)
        expected = _test_ids(bodies[runner])
        require(len(expected) == count and sha(encoded(expected)) == MAINTAINED_IDS_SHA256[selector], "test_ids_mismatch")
        view = _materialize_test_view(operation, bodies)
        seal = _view_seal(view, bodies)
        result["context_source"] = _layer("passed", evidence=[seal])
        result["context_manifest_sha256"] = seal
        phase = "child_observation"
        operation["launch_attempted"] = True
        observed = _launch_test_child(view, runner, expected, seconds, operation, selector=None)
        operation["child_exit_code"] = observed.get("child_exit_code")
        phase = "postlaunch_source_check"
        result["maintained_tests"] = {"status": "failed", "child_exit_code": observed.get("child_exit_code"),
            "executed_test_ids": observed.get("executed_test_ids", []),
            "executed_test_ids_sha256": sha(encoded(observed.get("executed_test_ids", []))),
            "stdout_sha256": observed.get("stdout_sha256"), "stderr_sha256": observed.get("stderr_sha256"),
            "dynamic_counters": observed.get("dynamic_counters")}
        _view_seal(view, bodies)
        _, after_identity = maintained_context_sources(selected, read_objects(selected), selector)
        require(after_identity == identity, "source_mismatch")
        result["direct_observations_evidence_sha256"] = sha(encoded(observed.get("descendant_observations", [])))
        runtime = observed.get("runtime")
        if runtime and runtime.get("predicates") == {"code_manifest": True, "engine_bindings": True}:
            result["maintained_loaded_runtime"] = _layer("passed", evidence=[sha(encoded(runtime))])
        else:
            result["maintained_loaded_runtime"] = _layer("failed", "runtime_mismatch")
        qualified = test_execution_qualified(observed, expected)
        actual = observed.get("child_exit_code")
        result["maintained_tests"]["status"] = "passed" if qualified else "failed"
        result.update(test_execution_qualified=qualified, invocation_status="completed" if qualified else "failed",
            wrapper_exit_code=0 if qualified else actual if type(actual) is int and 1 <= actual <= 255 else 2)
        if _uncertain(observed):
            reason = "test_timeout" if observed.get("timed_out") else "test_output_limit" if observed.get("overflow") else "test_interrupted"
            quarantine_operation(operation, reason)
            result["reason"] = reason
        else:
            result["reason"] = None if qualified else "test_failed"
        phase = "receipt_validation"
        validate_maintained_receipt(result)
        phase = "receipt_publication"
        _write_json(operation["path"] / "receipt.json", result, exclusive=True)
        phase = "operation_completion"
        _finish_operation(operation)
        return result
    except VersionError as error:
        result.update(reason=error.code, invocation_status="refused", wrapper_exit_code=2, test_execution_qualified=False)
        if error.code in {"source_mismatch", "unsafe_source_view"}:
            result["context_source"] = _layer("failed", error.code)
            result["maintained_loaded_runtime"] = _layer(reason="source_mismatch")
        if operation and not operation.get("launch_attempted"):
            _finish_operation(operation)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        result.update(reason="child_protocol_invalid", invocation_status="failed", wrapper_exit_code=2,
                      test_execution_qualified=False)
    if operation and operation.get("launch_attempted"):
        # Evidence failure cannot establish retirement, even with a known top exit.
        result.update(invocation_status="failed", wrapper_exit_code=2, test_execution_qualified=False)
        result["maintained_tests"] = {"status": "failed", "child_exit_code": operation.get("child_exit_code"),
            "executed_test_ids": [], "executed_test_ids_sha256": sha(encoded([])),
            "stdout_sha256": None, "stderr_sha256": None, "dynamic_counters": None}
        try:
            _view_seal(view, bodies)
            _, after_identity = maintained_context_sources(selected, read_objects(selected), selector)
            require(after_identity == identity, "source_mismatch")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, VersionError):
            result["context_source"] = _layer("failed", "source_mismatch")
            result["maintained_loaded_runtime"] = _layer(reason="source_mismatch")
        try:
            quarantine_operation(operation, "child_protocol_invalid")
        except (OSError, VersionError):
            pass  # Keep the initial running state: admission still refuses it.
        try:
            _write_json(operation["path"] / "failure-stage.json", {"schema": "validation-evidence-failure-v1",
                "operation_id": operation["id"], "phase": phase, "reason": result["reason"],
                "actual_child_exit_code": operation.get("child_exit_code"), "wrapper_exit_code": 2}, exclusive=True)
            _write_json(operation["path"] / "failure.json", result, exclusive=True)
        except (OSError, VersionError):
            pass  # Retain the view and all successfully recorded partial evidence.
    return result


def legacy_test(contract_id, profile_id, runner, *, scope=None):
    if runner not in ("tests/test_w40_native.py", "tests/test_w40_native_clock.py"):
        return _dispatch(contract_id, profile_id, runner, scope=scope)
    result = _receipt(None, profile_id)
    result.update(operation="legacy-test", command_argv=["python", "tools/engine_versions.py", "legacy-test"],
        test_execution_qualified=False, descendant_observations_complete=False,
        descendant_observations=[{"command": None, "exit_code": None, "state": "not_recorded", "observation_source": "not_recorded"}])
    try:
        selected = select(load_registry(), contract_id, profile_id)
        registry = selected["registry"]
        result.update(contract_id=contract_id, requested_profile=profile_id, selected_profile=profile_id,
            role="historical_v1", engine_source_commit=registry["engine_source_commit"], source_tree=registry["source_tree"],
            original_runner=runner, command_argv=["python", "tools/engine_versions.py", "legacy-test", contract_id, profile_id, runner])
        result["reason"] = "legacy_native_execution_unqualified"
    except VersionError as error:
        result["reason"] = error.code
    return validate_dispatch_receipt(result)


def adapter_test(contract_id, profile_id, selector, *, scope=None):
    return _dispatch(contract_id, profile_id, selector, adapter=True, scope=scope)


def _digest(value, length=64):
    return type(value) is str and len(value) == length and all(c in "0123456789abcdef" for c in value)


def _adapter_receipt_members(value, registry):
    """Check named Git identities; raw execution evidence is still a separate requirement."""
    error = "invalid_result_layers"
    dependency, current = value["dependency_identity"], value["current_adapter_identity"]
    expected = {"contract_id": registry["contract_id"], "engine_source_commit": registry["engine_source_commit"],
        "source_tree": registry["source_tree"], "profile": "git-lf", "registry_sha256": REGISTRY_SHA256,
        "members": [row for row in registry["members"] if row["path"] in DEPENDENCIES]}
    require(type(dependency) is dict and dependency == expected, error)
    require(type(current) is dict and set(current) == {"candidate_commit", "candidate_tree", "members"}
        and _digest(current["candidate_commit"], 40) and _digest(current["candidate_tree"], 40), error)
    members = current["members"]
    require(type(members) is list and len(members) == 2, error)
    hashes = {row["path"]: row["canonical_sha256"] for row in expected["members"]}
    require(_git_bytes("rev-parse", current["candidate_commit"] + "^{tree}").decode("ascii").strip()
        == current["candidate_tree"], error)
    listing = _git_bytes("ls-tree", "-z", current["candidate_commit"], "--", *CURRENT_MEMBERS)
    actual = {}
    for entry in listing.split(b"\0")[:-1]:
        fields, name = entry.decode("ascii").split("\t")
        mode, kind, blob = fields.split()
        require(name in CURRENT_MEMBERS and mode == "100644" and kind == "blob", error)
        actual[name] = blob
    require(set(actual) == set(CURRENT_MEMBERS), error)
    for row in members:
        require(type(row) is dict and set(row) == {"path", "mode", "blob", "canonical_sha256", "raw_sha256", "raw_bytes"}, error)
        name = row["path"]
        require(type(name) is str and name in CURRENT_MEMBERS and name not in hashes
            and row["mode"] == "100644" and _digest(row["blob"], 40) and row["blob"] == actual[name]
            and _digest(row["canonical_sha256"]) and _digest(row["raw_sha256"])
            and type(row["raw_bytes"]) is int and 0 < row["raw_bytes"] <= FILE_CAP, error)
        require(int(_git_bytes("cat-file", "-s", row["blob"])) <= FILE_CAP, error)
        raw = _git_bytes("cat-file", "blob", row["blob"])
        require(sha(raw) == row["canonical_sha256"] and len(raw) <= row["raw_bytes"] <= 2 * len(raw), error)
        if len(raw) == row["raw_bytes"]:
            require(row["raw_sha256"] == row["canonical_sha256"], error)
        hashes[name] = row["canonical_sha256"]
    require(set(hashes) == set(DEPENDENCIES) | set(CURRENT_MEMBERS), error)
    return sha(encoded(hashes))


def _execution_receipt(value):
    error = "invalid_result_layers"
    _validate_result_layers(value)  # The original source-layer contract stays independent and unchanged.
    require(len(encoded(value)) <= RESULT_CAP, "child_protocol_invalid")
    operation = value["operation"]
    require(type(operation) is str and operation in {"legacy-test", "adapter-test"}, error)
    adapter = operation == "adapter-test"
    required = set(_receipt(None, None)) | {"test_execution_qualified", "descendant_observations_complete", "descendant_observations"}
    optional = {"context_manifest_sha256", "direct_observations_evidence_sha256"}
    if adapter:
        required |= {"domain", "original_v1_fixture_qualified_by_adapter_result", "current_production_behavior_qualified", "adapter_tests"}
        optional |= {"dependency_identity", "current_adapter_identity"}
        require(value["domain"] == "current_adapter_on_v1_dependencies"
            and value["original_v1_fixture_qualified_by_adapter_result"] is False
            and value["current_production_behavior_qualified"] is False, error)
        require(value["legacy_tests"] == _receipt(None, None)["legacy_tests"], error)
    require(required <= set(value) <= required | optional, error)
    require(value["schema"] == ("engine-adapter-regression-v1" if adapter else "engine-version-qualification-v1"), error)
    require(value["v2_historical_native_positive_compatibility"] == "unsupported"
        and value["descendant_observations_complete"] is False
        and value["descendant_observations"] == [{"command": None, "exit_code": None,
            "state": "not_recorded", "observation_source": "not_recorded"}]
        and type(value["test_execution_qualified"]) is bool and type(value["wrapper_exit_code"]) is int
        and 0 <= value["wrapper_exit_code"] <= 255, error)
    reason = value["reason"]
    require(reason is None or type(reason) is str and reason in REASONS, error)
    registry = load_registry()
    profile = value["selected_profile"]
    require(profile is None or type(profile) is str and profile in registry["profiles"], error)
    require(value["requested_profile"] is None or type(value["requested_profile"]) is str
        and value["requested_profile"] in registry["profiles"], error)
    key = "adapter_tests" if adapter else "legacy_tests"
    test = value[key]
    require(type(test) is dict and type(test.get("status")) is str and test["status"] in {"passed", "failed", "not_run"}, error)
    if profile is None:
        require(all(value[k] is None for k in ("contract_id", "role", "engine_source_commit", "source_tree", "original_runner"))
            and value["command_argv"] == ["python", "tools/engine_versions.py", operation]
            and test["status"] == "not_run" and value["source_fixture"]["status"] != "passed"
            and not optional & set(value), error)
    else:
        require(value["contract_id"] == registry["contract_id"] and value["engine_source_commit"] == registry["engine_source_commit"]
            and value["source_tree"] == registry["source_tree"] and value["requested_profile"] == profile
            and value["role"] == ("current_adapter_on_v1_dependencies" if adapter else "historical_v1"), error)
        runner = ADAPTER_CLASS if adapter else value["original_runner"]
        require(value["original_runner"] is None and profile == "git-lf" if adapter
            else type(runner) is str and runner in RUNNERS, error)
        require(value["command_argv"] == ["python", "tools/engine_versions.py", operation, registry["contract_id"], profile, runner], error)
        if adapter:
            has_identity = "dependency_identity" in value or "current_adapter_identity" in value
            if has_identity or value["source_fixture"]["status"] == "passed":
                expected_seal = _adapter_receipt_members(value, registry)
            else:
                expected_seal = None
        else:
            expected_seal = sha(encoded({row["path"]: registry["profiles"][profile]["raw_sha256"][index]
                for index, row in enumerate(registry["members"])}))
        if "context_manifest_sha256" in value:
            require(_digest(value["context_manifest_sha256"]) and value["context_manifest_sha256"] == expected_seal, error)
        if value["source_fixture"]["status"] == "passed":
            require(value.get("context_manifest_sha256") == expected_seal
                and value["source_fixture"]["evidence_sha256"] == [expected_seal], error)
    if "direct_observations_evidence_sha256" in value:
        require(_digest(value["direct_observations_evidence_sha256"]), error)
    base = _receipt(None, None)["legacy_tests"]
    if test["status"] == "not_run":
        require(test == base, error)
    else:
        require(profile is not None and set(test) == set(base) | {"executed_test_ids", "dynamic_counters"}, error)
        ids = test["executed_test_ids"]
        require(type(ids) is list and len(ids) <= 64 and all(type(item) is str for item in ids)
            and ids == sorted(set(ids)) and test["executed_test_ids_sha256"] == sha(encoded(ids)), "test_ids_mismatch")
        require(test["child_exit_code"] is None or type(test["child_exit_code"]) is int, error)
        require(all(test[k] is None or _digest(test[k]) for k in ("stdout_sha256", "stderr_sha256")), error)
        counters = test["dynamic_counters"]
        require(counters is None or type(counters) is dict and set(counters) == {"passed", "failed", "not_checked"}
            and all(type(v) is int and v >= 0 for v in counters.values()), error)
    if value["test_execution_qualified"]:
        require(profile is not None and value["invocation_status"] == "completed" and value["wrapper_exit_code"] == 0
            and reason is None and test["status"] == "passed" and type(test["child_exit_code"]) is int and test["child_exit_code"] == 0
            and value["source_fixture"]["status"] == value["loaded_runtime"]["status"] == "passed"
            and _digest(value.get("direct_observations_evidence_sha256"))
            and all(_digest(test[k]) for k in ("stdout_sha256", "stderr_sha256")), error)
        expected_hash = sha(encoded(list(ADAPTER_IDS))) if adapter else RUNNER_IDS_SHA256[runner]
        require(len(test["executed_test_ids"]) == (3 if adapter else RUNNERS[runner][0])
            and test["executed_test_ids_sha256"] == expected_hash, "test_ids_mismatch")
        if not adapter and runner == "tests/test_dataset_replayable.py":
            require(counters is not None and counters["failed"] == 0, error)
        else:
            require(counters is None, error)
    else:
        require(type(value["invocation_status"]) is str and value["invocation_status"] in {"refused", "failed"}
            and value["wrapper_exit_code"] != 0 and test["status"] != "passed", error)
    return value


def validate_dispatch_receipt(value):
    """Bounded execution-domain validation; a receipt alone does not prove execution."""
    try:
        return _execution_receipt(value)
    except VersionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, RecursionError, OverflowError):
        raise VersionError("invalid_result_layers") from None


def workflow_dispatch_contract(text):
    spec = importlib.util.spec_from_file_location("engine_workflow_parser", ROOT / ".github/scripts/offline_suite.py")
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    base = _git_bytes("cat-file", "blob", "bb6e1b2cc5e602e94f0560c37dbc3bd79674edab:.github/workflows/test.yml").decode("utf-8")
    old, unknown = parser.steps_from_workflow(base)
    require(not unknown and len(old) == 47, "source_mismatch")
    original = [command for _, command in old]
    replacements = {
        "python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py":
            "python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16",
        "python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests":
            "python tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf",
        "python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native_clock.py":
            "python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3"}
    require(all(original.count(command) == 1 for command in replacements), "source_mismatch")
    expected = [replacements.get(command, command) for command in original]
    actual, refused = parser.steps_from_workflow(text)
    commands = [command for _, command in actual]
    status = "registered" if not refused and commands == expected else "registration_pending" if not refused and commands == original else "invalid"
    return {"status": status, "actual_count": len(commands), "expected_count": 47, "commands": commands}


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments in ([], ["--help"]):
        print("usage: engine_versions.py verify-source <contract-id> <profile-id>\n"
              "       engine_versions.py legacy-test <contract-id> <profile-id> <original-runner>\n"
              "       engine_versions.py adapter-test <contract-id> git-lf InterruptedProgressStagingTests\n"
              "       engine_versions.py maintained-test <contract-id> git-lf <native-all16|clock-all3>")
        return 0
    if len(arguments) == 3 and arguments[0] == "verify-source":
        result = verify_source(arguments[1], arguments[2])
    elif len(arguments) == 4 and arguments[0] == "legacy-test":
        result = legacy_test(*arguments[1:])
    elif len(arguments) == 4 and arguments[0] == "adapter-test":
        result = adapter_test(*arguments[1:])
    elif len(arguments) == 4 and arguments[0] == "maintained-test":
        result = maintained_test(*arguments[1:])
    elif arguments[0] == "maintained-test":
        result = maintained_test(None, None, None)
        result["reason"] = "invalid_arguments"
    elif arguments[0] in {"legacy-test", "adapter-test"}:
        result = _dispatch(None, None, None, adapter=arguments[0] == "adapter-test")
        result["reason"] = "invalid_arguments"
    else:
        result = _receipt(None, None)
        result["reason"] = "invalid_arguments" if arguments[0] == "verify-source" else "unsupported_command"
    if result.get("operation") == "maintained-test":
        result = validate_maintained_receipt(result)
    else:
        result = validate_dispatch_receipt(result) if result.get("operation") in {"legacy-test", "adapter-test"} else _checked_result(result)
    sys.stdout.buffer.write(encoded(result) + b"\n")
    return result["wrapper_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
