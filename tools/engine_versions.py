"""Closed offline W40 source-fixture verification; no operational native API."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

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
           "runtime_unavailable", "invalid_arguments", "unsupported_command", "verification_failed"}


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
    return result


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments in ([], ["--help"]):
        print("usage: engine_versions.py verify-source <contract-id> <profile-id>")
        return 0
    if len(arguments) == 3 and arguments[0] == "verify-source":
        result = verify_source(arguments[1], arguments[2])
    else:
        result = _receipt(None, None)
        result["reason"] = "invalid_arguments" if arguments[0] == "verify-source" else "unsupported_command"
    sys.stdout.buffer.write(encoded(result) + b"\n")
    return result["wrapper_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
