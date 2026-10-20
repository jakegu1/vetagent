"""Offline acceptance contract for the bounded immutable archive seam."""
import asyncio
from contextlib import ExitStack, contextmanager
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
import w40_archive as archive

CODE = None


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_object(kind, raw):
    framed = kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw
    return hashlib.sha1(framed).hexdigest(), framed


def external(path):
    return not any((parent / ".git").exists() for parent in (Path(path), *Path(path).parents))


def load_module():
    spec = importlib.util.spec_from_file_location("w40_archive_fixture", CODE / "bench/w40_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self, utc=None, mono=None):
        self.wall = utc or datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        self.value = time.monotonic() if mono is None else mono

    def utc(self):
        return self.wall

    def mono(self):
        return self.value

    async def sleep(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.value += seconds

    def advance(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.value += seconds


class Repo:
    def __init__(self, rows=None):
        self.rows = rows or {"pools-2026-10-01.ndjson": b'{"n":1}\n'}
        self.objects, catalog = {}, []
        for name, raw in sorted(self.rows.items()):
            identity, _framed = git_object("blob", raw)
            catalog.append(dict(path="bench/snapshots/" + name, mode="100644", type="blob",
                                sha=identity, bytes=len(raw), sha256=sha(raw), object="blobs/" + identity))
        self.catalog = catalog

        def tree(entries):
            raw = b"".join(mode.lstrip("0").encode() + b" " + name.encode() + b"\0" + bytes.fromhex(identity)
                           for name, mode, identity in entries)
            identity, framed = git_object("tree", raw)
            self.objects[identity] = framed
            return identity

        snapshots = tree([(x["path"].split("/")[-1], x["mode"], x["sha"]) for x in catalog])
        bench = tree([("snapshots", "040000", snapshots)])
        root = tree([("bench", "040000", bench)])
        commit, framed = git_object("commit", b"tree " + root.encode() + b"\n\nfixture\n")
        self.objects[commit] = framed
        self.commit, self.trees = commit, [root, bench, snapshots]
        self.responses = [
            (200, encoded(dict(ref="refs/heads/master", object=dict(type="commit", sha=commit)))),
            (200, encoded(dict(sha=commit, tree=dict(sha=root)))),
            (200, encoded(dict(sha=root, truncated=False, tree=[dict(path="bench", mode="040000", type="tree", sha=bench)]))),
            (200, encoded(dict(sha=bench, truncated=False, tree=[dict(path="snapshots", mode="040000", type="tree", sha=snapshots)]))),
            (200, encoded(dict(sha=snapshots, truncated=False,
                               tree=[dict(path=x["path"].split("/")[-1], mode=x["mode"], type="blob", sha=x["sha"], size=x["bytes"]) for x in catalog]))),
        ] + [(200, raw) for _name, raw in sorted(self.rows.items())]


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def __call__(self, request, **kwargs):
        self.requests.append(dict(request))
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, raw = item[:2]
        return dict(status=status, raw=raw, content_length=len(raw), content_encoding="identity",
                    retired="exited", identity=None, **(item[2] if len(item) > 2 else {}))


class LocalTransport:
    def __init__(self, module, route):
        self.module, self.route = module, route

    async def __call__(self, request, **kwargs):
        worker = self.module.NativeSourceWorker(request, route=self.route, **kwargs)
        return await worker.fetch()


class Server:
    def __init__(self, responses, hold=False):
        self.responses, self.hold, self.calls = list(responses), hold, []
        self.release, self.entered = threading.Event(), threading.Event()

    def __enter__(self):
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                owner.calls.append(self.path)
                status, raw = owner.responses[min(len(owner.calls) - 1, len(owner.responses) - 1)]
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Encoding", "identity")
                self.end_headers()
                try:
                    if owner.hold:
                        self.wfile.write(raw[:3])
                        self.wfile.flush()
                        owner.entered.set()
                        owner.release.wait(15)
                        self.wfile.write(raw[3:])
                    else:
                        self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.route = self.server.server_address
        return self

    def __exit__(self, *_args):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)


class Fixture:
    def __init__(self, repo=None):
        self.repo = repo or Repo()
        self.root = Path(tempfile.mkdtemp(prefix="w40-archive-fixture-"))
        self.roots = {name: self.root / name for name in ("control", "source", "raw", "safe", "seed")}
        self.roots["code"] = CODE
        for path in self.roots.values():
            path.mkdir(exist_ok=True)
        (self.roots["control"] / "writer.lock").touch()
        self.module = load_module()
        self.write_bundle()
        executable = Path(sys.executable).resolve()
        origins = []
        for name in ("os", "json", "pathlib", "ssl", "http.client", "ctypes", "asyncio"):
            target = __import__(name, fromlist=["_"])
            filename = getattr(target, "__file__", None)
            if filename and Path(filename).is_file():
                origins.append(dict(module=name, path=str(Path(filename).resolve()), sha256=sha(Path(filename).read_bytes())))
        prefix, base = Path(sys.prefix), Path(sys.base_prefix)
        cfg = prefix / "pyvenv.cfg"
        self.manifest = dict(schema="w40-code-v1", files=[dict(path=str(path.relative_to(CODE)).replace(os.sep, "/"),
                             bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
                             for path in sorted(CODE.rglob("*")) if path.is_file() and "__pycache__" not in path.parts],
                             interpreter=dict(path=str(executable), sha256=sha(executable.read_bytes()),
                             prefix=str(prefix.resolve()), base_prefix=str(base.resolve()), origins=origins,
                             pyvenv_cfg=None if prefix.resolve() == base.resolve() else
                             dict(path=str(cfg.resolve()), sha256=sha(cfg.read_bytes()))), powershell=None)
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_bytes(encoded(self.manifest))
        self.config = dict(schema="w40-install-v1", study_id_sha256=sha(self.root.name.encode()),
                           executable_commit="1" * 40, code_manifest_sha256=sha(encoded(self.manifest)),
                           manifest=str(self.manifest_path), roots={k: str(v.resolve()) for k, v in self.roots.items()},
                           archive_origin=dict(owner="example-owner", repo="pool-archive", ref="refs/heads/master",
                                               api_version="2026-03-10", verification_sha256=sha(encoded(self.origin))),
                           seed=dict(manifest="catalog.json", manifest_sha256=sha(encoded(self.catalog)),
                                     receipt="origin.json", receipt_sha256=sha(encoded(self.origin))),
                           task=dict(task_path="\\VetAgent\\W40\\", name="W40-" + sha(self.root.name.encode())),
                           quality_gates=[])
        self.config_path = self.root / "config.json"
        self.rebind()
        self.stack = ExitStack()

    def write_bundle(self):
        seed_root = self.roots["seed"]
        (seed_root / "blobs").mkdir(exist_ok=True)
        (seed_root / "proof").mkdir(exist_ok=True)
        for entry, (_name, raw) in zip(self.repo.catalog, sorted(self.repo.rows.items())):
            (seed_root / entry["object"]).write_bytes(raw)
        proofs = []
        for identity, framed in sorted(self.repo.objects.items()):
            relative = "proof/" + identity
            (seed_root / relative).write_bytes(framed)
            proofs.append(dict(id=identity, object=relative, bytes=len(framed), sha256=sha(framed)))
        self.catalog = dict(schema="w40-seed-v1", archive_commit=self.repo.commit,
                            tree_chain=self.repo.trees, catalog=self.repo.catalog)
        self.origin = dict(schema="w40-origin-v1", archive_commit=self.repo.commit,
                           tree_chain=self.repo.trees, catalog_sha256=sha(encoded(self.catalog)), objects=proofs)
        (seed_root / "catalog.json").write_bytes(encoded(self.catalog))
        (seed_root / "origin.json").write_bytes(encoded(self.origin))

    def rebind(self):
        self.config_path.write_bytes(encoded(self.config))
        self.pins = dict(expected_config_sha256=sha(encoded(self.config)),
                         expected_manifest_sha256=sha(encoded(self.manifest)))

    def __enter__(self):
        self.stack.enter_context(patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""}))
        self.binding = self.module.verify_install(self.config_path, component="archive", **self.pins)
        return self

    def __exit__(self, *_args):
        self.stack.close()

    def refresh(self, transport=None, clock=None, hooks=None):
        clock = clock or Clock()
        with self.module.study_writer(self.binding) as lease:
            return self.module.refresh(self.binding, lease, live=True, deadline_mono=clock.mono() + 60,
                                       clock=clock, transport=transport or Transport(self.repo.responses), hooks=hooks)

    def seed(self, clock=None):
        with self.module.study_writer(self.binding) as lease:
            return self.module.seed(self.binding, lease, clock=clock or Clock())

    def cli(self, *args, env=None):
        command = [sys.executable, "-I", "-B", str(CODE / "bench/w40_archive.py"), *args,
                   "--config", str(self.config_path), "--config-sha256", self.pins["expected_config_sha256"],
                   "--manifest-sha256", self.pins["expected_manifest_sha256"]]
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=30)


def wait_for(path, timeout=12):
    end = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < end:
        time.sleep(.01)
    if not path.exists():
        raise AssertionError("fixture_wait_timeout")
    return json.loads(path.read_bytes())


def child_main(arguments):
    global CODE
    config_path, mode, host, port = arguments
    config = json.loads(Path(config_path).read_bytes())
    CODE = Path(config["roots"]["code"])
    module = load_module()
    pins = dict(expected_config_sha256=sha(Path(config_path).read_bytes()),
                expected_manifest_sha256=config["code_manifest_sha256"])
    with patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""}):
        binding = module.verify_install(config_path, component="archive", **pins)
        with module.study_writer(binding) as lease:
            if mode == "recover":
                result = module.recover_archive(binding, lease)
                (Path(config_path).parent / "recovered.json").write_bytes(encoded(result))
                return

            async def hooks(stage, worker):
                if stage == mode:
                    (Path(config_path).parent / "parent-hook.json").write_bytes(encoded(dict(identity=worker.identity,
                        directory=str(worker.directory))))
                    await asyncio.Event().wait()

            module.refresh(binding, lease, live=True, deadline_mono=time.monotonic() + 60,
                           transport=LocalTransport(module, (host, int(port))), hooks=hooks)


class ArchiveAcceptance(unittest.TestCase):
    def test_w40_archive_frozen_bootstrap_and_private_boundary(self):
        environment = dict(os.environ)
        with Fixture() as f:
            a, binding = f.module, f.binding
            self.assertEqual(a.plan(binding)["state"], "not_started")
            with self.assertRaises(a.ArchiveError):
                a.verify_install(f.config_path, expected_config_sha256="0" * 64,
                                 expected_manifest_sha256=f.pins["expected_manifest_sha256"], component="archive")
            original = f.config_path.read_bytes()
            f.config_path.write_bytes(original + b" ")
            with self.assertRaises(a.ArchiveError):
                a.verify_install(f.config_path, component="archive", **f.pins)
            f.config_path.write_bytes(original)
            with a.study_writer(binding) as lease:
                with self.assertRaises(a.ArchiveError):
                    with a.study_writer(binding):
                        pass
                with self.assertRaises(a.ArchiveError):
                    a.reserve(binding, True, reservation_id="1" * 64, owner="runtime", ceilings={"raw": 1})
                ticket = a.reserve(binding, lease, reservation_id="2" * 64, owner="runtime", ceilings={"raw": 128})
                with self.assertRaises(a.ArchiveError):
                    a.reserve(binding, lease, reservation_id="2" * 64, owner="runtime", ceilings={"raw": 128})
                self.assertEqual(ticket["owner"], "runtime")
                a.request_stop(binding, reason="requested")
                self.assertEqual(a.stop_state(binding)["state"], "stopped")
                self.assertEqual(a.request_stop(binding, reason="requested")["state"], "stopped")
            before = sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*"))
            with patch.dict(os.environ, {"CI": "true"}):
                with self.assertRaises(a.ArchiveError):
                    with a.study_writer(binding):
                        pass
            self.assertEqual(before, sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*")))
        self.assertEqual(dict(os.environ), environment)
        with Fixture() as f:
            git_dir = f.root / "isolated-git"
            subprocess.run(["git", "init", "--quiet", str(git_dir)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            marker = git_dir / "untouched"
            marker.write_bytes(b"marker")
            source = f.roots["source"]
            saved = f.root / "source-saved"
            source.rename(saved)
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(source), str(git_dir)], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                source.symlink_to(git_dir, target_is_directory=True)
            try:
                with self.assertRaises(f.module.ArchiveError):
                    f.seed()
                self.assertEqual(marker.read_bytes(), b"marker")
            finally:
                os.rmdir(source) if os.name == "nt" else source.unlink()
                saved.rename(source)

    def test_w40_archive_exact_rest_graph_and_blob_integrity(self):
        with Fixture() as f:
            transport = Transport(f.repo.responses)
            result = f.refresh(transport)
            self.assertEqual(result["state"], "accepted")
            requests = transport.requests
            self.assertEqual(len(requests), 6)
            self.assertEqual([r["path"] for r in requests[:2]], [
                "/repos/example-owner/pool-archive/git/ref/heads/master",
                "/repos/example-owner/pool-archive/git/commits/" + f.repo.commit])
            self.assertEqual([r["path"].rsplit("/", 1)[1] for r in requests[2:5]], f.repo.trees)
            self.assertTrue(all(r["method"] == "GET" and r["host"] == "api.github.com" for r in requests))
            self.assertTrue(all("recursive" not in r["path"] for r in requests))
            self.assertEqual(requests[-1]["headers"]["Accept"], "application/vnd.github.raw+json")
            self.assertEqual(requests[0]["headers"]["Accept-Encoding"], "identity")
            self.assertEqual(requests[0]["headers"]["User-Agent"], "vetagent-w40-local-source")
            self.assertEqual(requests[0]["headers"]["X-GitHub-Api-Version"], "2026-03-10")
        cases = ["ref", "sha", "tree_sha", "truncated", "mode", "type", "duplicate", "blob", "length", "encoding", "deep", "redirect"]
        for case in cases:
            with self.subTest(case=case), Fixture() as f:
                responses = list(f.repo.responses)
                if case in ("ref", "sha"):
                    value = json.loads(responses[0][1])
                    value["ref"] = "refs/heads/other" if case == "ref" else value["ref"]
                    if case == "sha":
                        value["object"]["sha"] = "bad"
                    responses[0] = 200, encoded(value)
                elif case in ("tree_sha", "truncated", "mode", "type", "duplicate"):
                    value = json.loads(responses[2][1])
                    if case == "tree_sha": value["sha"] = "0" * 40
                    if case == "truncated": value["truncated"] = True
                    if case == "mode": value["tree"][0]["mode"] = "120000"
                    if case == "type": value["tree"][0]["type"] = "commit"
                    if case == "duplicate": value["tree"].append(dict(value["tree"][0]))
                    responses[2] = 200, encoded(value)
                elif case == "blob": responses[-1] = 200, b"changed"
                elif case == "length": responses[-1] = (200, responses[-1][1], {"content_length": 99})
                elif case == "encoding": responses[0] = (200, responses[0][1], {"content_encoding": "gzip"})
                elif case == "deep": responses[0] = 200, b"[" * 100 + b"0" + b"]" * 100
                else: responses[0] = 302, b""
                result = f.refresh(Transport(responses))
                self.assertEqual(result["state"], "terminal")
                self.assertIsNone(f.module.accepted_view(f.binding))

    def test_w40_archive_prefix_chunks_and_row_findings(self):
        raw = b'{"n":1}\n' + b"invalid\n" + b'{"long":"' + b"x" * 65536 + b'"}\n' + b'{"n":'
        first = Repo({"pools-2026-10-01.ndjson": raw})
        with Fixture(first) as f:
            self.assertEqual(f.seed()["state"], "accepted")
            view = f.module.accepted_view(f.binding)
            rows = list(f.module.iter_complete_rows(f.binding, view))
            self.assertEqual([r["line"] for r in rows], [1, 2, 3])
            self.assertEqual([r["finding"] for r in rows], [None, "invalid_row", "row_cap"])
            self.assertEqual(rows[0]["raw"], b'{"n":1}\n')
            self.assertEqual(rows[2]["bytes"], len(b'{"long":"' + b"x" * 65536 + b'"}\n'))
            self.assertGreater(view["catalog"][0]["trailing_bytes"], 0)
            updated = Repo({"pools-2026-10-01.ndjson": raw + b"2}\n"})
            self.assertEqual(f.refresh(Transport(updated.responses))["state"], "accepted")
            newer = f.module.accepted_view(f.binding)
            added = list(f.module.iter_complete_rows(f.binding, newer, after_view_sha256=view["view_sha256"]))
            self.assertEqual([(r["line"], r["raw"]) for r in added], [(4, b'{"n":2}\n')])
            self.assertEqual(newer["previous_view_sha256"], view["view_sha256"])
        for replacement in (b'{"n":9}\n', b"", b'{"n":1}\n{"different":2}\n'):
            with self.subTest(rewrite=len(replacement)), Fixture(first) as f:
                f.seed()
                old = f.module.accepted_view(f.binding)["view_sha256"]
                bad = Repo({"pools-2026-10-01.ndjson": replacement})
                self.assertEqual(f.refresh(Transport(bad.responses))["state"], "terminal")
                self.assertEqual(f.module.accepted_view(f.binding)["view_sha256"], old)
        with Fixture() as f:
            f.seed()
            view = f.module.accepted_view(f.binding)
            blob = f.roots["source"] / view["catalog"][0]["object"]
            blob.write_bytes(b"tampered")
            with self.assertRaises(f.module.ArchiveError):
                f.module.accepted_view(f.binding)

    def test_w40_archive_seed_whole_catalog_and_allocation(self):
        line = b'{"padding":"' + b"x" * (24 * 1024) + b'"}\n'
        rows = {"pools-2026-08-%02d.ndjson" % n: line * 64 for n in range(1, 32)}
        rows.update({"pools-2026-09-%02d.ndjson" % n: line * 64 for n in range(1, 16)})
        with Fixture(Repo(rows)) as f:
            self.assertGreater(sum(len(raw) for raw in rows.values()), 64 * 1024 * 1024)
            result = f.seed()
            self.assertEqual(result["state"], "accepted")
            view = f.module.accepted_view(f.binding)
            self.assertEqual(len(view["catalog"]), 46)
            self.assertEqual(sum(x["complete_lines"] for x in view["catalog"]), 46 * 64)
            report = f.module.report(f.binding)
            self.assertLessEqual(report["allocation"]["committed_and_reserved_bytes"], 16 * 1024 ** 3)
            self.assertGreater(report["allocation"]["retained_bytes"], sum(len(raw) for raw in rows.values()))
            self.assertIsNone(report["started_at"])
        for case in ("missing_catalog", "missing_origin", "fabricated_origin", "oversize_file", "too_many", "clock", "disk"):
            with self.subTest(case=case), Fixture() as f:
                if case == "missing_catalog": (f.roots["seed"] / "catalog.json").unlink()
                if case == "missing_origin": (f.roots["seed"] / "origin.json").unlink()
                if case == "fabricated_origin": (f.roots["seed"] / "origin.json").write_bytes(encoded(dict(schema="w40-origin-v1")))
                if case == "oversize_file":
                    f.repo = Repo({"pools-2026-10-01.ndjson": b"x" * (8 * 1024 * 1024 + 1)})
                if case == "too_many":
                    f.repo = Repo({"pools-2025-%02d-%02d.ndjson" % (1 + n // 28, 1 + n % 28): b"{}\n" for n in range(129)})
                if case in ("oversize_file", "too_many"):
                    f.write_bundle()
                    f.config["seed"].update(manifest_sha256=sha(encoded(f.catalog)), receipt_sha256=sha(encoded(f.origin)))
                    f.config["archive_origin"]["verification_sha256"] = sha(encoded(f.origin))
                    f.rebind()
                    f.binding = f.module.verify_install(f.config_path, component="archive", **f.pins)
                clock = Clock()
                if case == "clock":
                    initial = clock.mono()
                    samples = iter([initial, initial + 1201])
                    clock.mono = lambda: next(samples, initial + 1201)
                with ExitStack() as stack:
                    if case == "disk":
                        stack.enter_context(patch.object(f.module.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(1, 1, 0)))
                    outcome = f.seed(clock)
                self.assertIn(outcome["state"], ("gap", "terminal"))
                self.assertIsNone(f.module.accepted_view(f.binding))
        with Fixture() as f:
            with f.module.study_writer(f.binding) as lease:
                with self.assertRaises(f.module.ArchiveError):
                    f.module.reserve(f.binding, lease, reservation_id="3" * 64, owner="runtime", ceilings={"raw": 16 * 1024 ** 3})

    def test_w40_archive_refresh_ledger_caps_and_refusals(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status), Fixture() as f:
                transport = Transport([(status, b"{}")])
                result = f.refresh(transport)
                self.assertEqual(result["state"], "terminal" if status in (401, 403) else "gap")
                self.assertEqual(len(transport.requests), 1)
                again = Transport(f.repo.responses)
                result2 = f.refresh(again)
                self.assertEqual(len(again.requests), 0)
                self.assertNotEqual(result2["state"], "accepted")
        with Fixture() as f:
            clock = Clock()
            uncertain = Transport([TimeoutError()])
            self.assertEqual(f.refresh(uncertain, clock)["state"], "gap")
            same = Transport(f.repo.responses)
            self.assertNotEqual(f.refresh(same, clock)["state"], "accepted")
            self.assertEqual(len(same.requests), 0)
            clock.advance(900)
            self.assertEqual(f.refresh(Transport(f.repo.responses), clock)["state"], "accepted")
            self.assertEqual(f.module.report(f.binding)["refresh_reserved"], 2)
        for case in ("deadline", "midnight", "metadata", "candidate", "catalog"):
            with self.subTest(case=case), Fixture() as f:
                clock = Clock()
                transport = Transport(f.repo.responses)
                if case == "deadline":
                    with f.module.study_writer(f.binding) as lease:
                        outcome = f.module.refresh(f.binding, lease, live=True, deadline_mono=clock.mono() + 9,
                                                   clock=clock, transport=transport)
                    self.assertEqual(len(transport.requests), 0)
                else:
                    if case == "midnight": clock.wall = clock.wall.replace(hour=23, minute=59, second=55)
                    if case == "metadata": transport.responses[0] = 200, b"x" * (1024 * 1024 + 1)
                    if case == "candidate": transport.responses[-1] = 200, b"x" * (64 * 1024 * 1024 + 1)
                    if case == "catalog":
                        value = json.loads(transport.responses[4][1])
                        value["tree"] = [dict(path="pools-2025-%02d-%02d.ndjson" % (1 + n // 28, 1 + n % 28), mode="100644", type="blob", sha="1" * 40, size=1) for n in range(129)]
                        transport.responses[4] = 200, encoded(value)
                    outcome = f.refresh(transport, clock)
                self.assertIn(outcome["state"], ("gap", "terminal"))
                self.assertIsNone(f.module.accepted_view(f.binding))

    def test_w40_archive_parent_death_and_fresh_process_restore(self):
        for mode in ("before_ack", "native_entry"):
            with self.subTest(mode=mode), Fixture() as f, Server(f.repo.responses, hold=True) as server:
                f.seed()
                before_view = f.module.accepted_view(f.binding)["view_sha256"]
                command = [sys.executable, "-B", str(Path(__file__)), "--fixture-parent", str(f.config_path), mode,
                           server.route[0], str(server.route[1])]
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                evidence = wait_for(f.root / "parent-hook.json")
                try:
                    if mode == "native_entry":
                        self.assertTrue(server.entered.wait(8))
                        end = time.monotonic() + 5
                        body = Path(evidence["directory"]) / "body.bin"
                        while (not body.exists() or body.stat().st_size == 0) and time.monotonic() < end:
                            time.sleep(.01)
                        self.assertGreater(body.stat().st_size, 0)
                    else:
                        self.assertEqual(len(server.calls), 0)
                    with self.assertRaises(f.module.ArchiveError):
                        with f.module.study_writer(f.binding):
                            pass
                finally:
                    process.kill()
                    process.wait(10)
                identity = evidence["identity"]
                end = time.monotonic() + 3
                while f.module._native(f.binding).identity_alive(identity) and time.monotonic() < end:
                    time.sleep(.01)
                self.assertFalse(f.module._native(f.binding).identity_alive(identity))
                calls = len(server.calls)
                recovered = subprocess.run([*command[:5], "recover", *command[6:]], stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, timeout=20)
                self.assertEqual(recovered.returncode, 0)
                receipt = wait_for(f.root / "recovered.json")
                self.assertIn(receipt["state"], ("gap", "terminal", "accepted"))
                self.assertEqual(len(server.calls), calls)
                self.assertEqual(f.module.accepted_view(f.binding)["view_sha256"], before_view)
                self.assertEqual(f.module.report(f.binding)["refresh_reserved"], 1)
                self.assertIsNone(f.module.report(f.binding)["started_at"])
        with Fixture() as f, Server(f.repo.responses) as server:
            outcome = f.refresh(LocalTransport(f.module, server.route), clock=f.module.Clock())
            self.assertEqual(outcome["state"], "accepted")
            self.assertEqual(len(server.calls), 6)

    def test_w40_archive_cli_and_complete_existing_runner(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(CODE / "bench/w40_archive.py")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "configuration_required")
        with Fixture() as f:
            for verb in ("plan", "report"):
                before = sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*"))
                result = f.cli(verb)
                self.assertEqual(result.returncode, 0)
                self.assertLessEqual(len(result.stdout), 1024 * 1024)
                self.assertEqual(before, sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*")))
            for option in ("--url", "--live", "--now", "--clock", "--transport", "--owner", "--ref"):
                result = f.cli("plan", option, "forged")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"forged", result.stdout + result.stderr)
            for flag in ("CI", "GITHUB_ACTIONS"):
                environment = dict(os.environ, **{flag: "true"})
                before = sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*"))
                result = f.cli("seed", env=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["reason"], "ci_refused")
                self.assertEqual(before, sorted(str(x.relative_to(f.root)) for x in f.root.rglob("*")))
            self.assertNotIn(str(f.root).encode(), f.cli("plan").stdout)
        workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("python tests/test_w40_archive.py"), 1)
        self.assertEqual(workflow.count("python tests/test_w40_native.py"), 1)


def prepare_code(existing=None):
    global CODE
    if existing:
        CODE = Path(existing)
        return
    CODE = Path(tempfile.mkdtemp(prefix="w40-archive-code-"))
    if not external(CODE):
        raise RuntimeError("private_temp_required")
    for relative in ("bench/w40_archive.py", "bench/w40_native.py", "bench/w40_evidence.py", "bench/labels.py",
                     "bench/goplus_quota_probe.py", "src/risk.py", "docs/BACKLOG.md", "tests/test_dataset_replayable.py"):
        target = CODE / relative
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / relative, target)
    (CODE / "bench/w40_local.py").write_bytes(b'"""Technical future component fixture."""\n')
    (CODE / "tools").mkdir()
    (CODE / "tools/w40-local.ps1").write_bytes(b"# Technical future component fixture.\n")
    executable = Path(sys.executable).resolve()
    if os.name == "nt":
        if Path(sys.prefix).resolve() != Path(sys.base_prefix).resolve():
            raise RuntimeError("direct_base_required")
        relocated = CODE / "python-base"
        relocated.mkdir()
        base = Path(sys.base_prefix)
        for directory in ("Lib", "DLLs"):
            shutil.copytree(base / directory, relocated / directory,
                            ignore=shutil.ignore_patterns("site-packages", "__pycache__", "*.pyc"))
        for source in base.iterdir():
            if source.is_file() and source.suffix.lower() in (".dll", ".exe", ".zip", ".pyd"):
                shutil.copyfile(source, relocated / source.name)
        executable = relocated / executable.name
        interpreter = executable
    else:
        venv = CODE / "venv"
        subprocess.run([str(executable), "-I", "-B", "-m", "venv", "--copies", "--without-pip", str(venv)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        interpreter = venv / "bin/python"
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        environment.pop(name, None)
    environment.update(PYTHONSAFEPATH="1", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(interpreter), "-I", "-B", str(Path(__file__)), "--fixture-code", str(CODE), *sys.argv[1:]],
                            env=environment)
    sys.exit(result.returncode)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture-parent":
        child_main(sys.argv[2:])
    else:
        existing = None
        if len(sys.argv) > 2 and sys.argv[1] == "--fixture-code":
            existing = sys.argv[2]
            del sys.argv[1:3]
        prepare_code(existing)
        unittest.main()
