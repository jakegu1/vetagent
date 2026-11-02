"""T-071: closed historical fixtures and present runtime, never old-run qualification."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/engine_versions.py"
REGISTRY = ROOT / "bench/engine_versions.json"
CONTRACT = "w40-v1-e3ec46a"
COMMIT = "e3ec46ad8e4c485243fe20a606ac263564d350f0"
TREE = "77775bf267f0543bd2355b84c541d9933d36b31c"
RISK_LF = "67b52bd3f7610aa98d6ed5f94457e875d16b489f633be54d170453e313dd8d2d"
RISK_CRLF = "1be89b566f0c42b40043803cdab1e8d81d376aa6df8500ca3c7018f123d06df9"
MEMBERS = (
    ("bench/goplus_quota_probe.py", "18785d8def90ca7b166cabc219211e506c0a3fc4"),
    ("bench/w40_evidence.py", "06b7ceffea1024914d0d584908dae6b380bb9dd8"),
    ("src/risk.py", "be42fe24a818bbba9565a4991a2bc4c1e55f49cb"),
    ("bench/labels.py", "ff6d7ad02aabe1ccb247828c7b77e32875b95b12"),
    ("docs/BACKLOG.md", "6ba4a388d88fe24b7231428574a74ba297de1666"),
    ("tests/test_dataset_replayable.py", "01ec092bc84c6566f9b32e07c765d6293a62ab8e"),
    ("bench/w40_native.py", "5d60d8e2571c775d510a728454d85813bee36857"),
    ("tests/test_w40_native.py", "f634c654d4d2d9edde892d4beba9f8729f1acf2f"),
    ("tests/test_w40_native_clock.py", "ddd83b387f5ab2baaed819d19535528978dbd32c"),
    (".github/workflows/test.yml", "e8fd47a52270608d44a6db06d8f26193def9a3eb"),
    ("bench/dataset.json", "3c2e7ce9fb866ec0a5cc28972b64ec9efa04158f"),
)
LAYERS = ("source_fixture", "loaded_runtime", "historical_record_tuple", "historical_interpreter")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class EngineVersionAcceptance(unittest.TestCase):
    def subject(self):
        self.assertTrue(HELPER.is_file(), "T-071 verify-source helper is missing")
        self.assertTrue(REGISTRY.is_file(), "T-071 closed source registry is missing")
        spec = importlib.util.spec_from_file_location("t071_subject", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def selection(self, module, profile="git-lf"):
        return module.select(module.load_registry(), CONTRACT, profile)

    def cli(self, *arguments, env=None):
        self.subject()
        return subprocess.run([sys.executable, "-B", str(HELPER), *arguments], cwd=ROOT,
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)

    def receipt(self, value):
        self.assertEqual(value["schema"], "engine-version-qualification-v1")
        self.assertNotIn("passed", value)
        self.assertIn(value["invocation_status"], ("completed", "refused", "failed"))
        for name in LAYERS:
            self.assertIn(value[name]["status"], ("passed", "failed", "not_evaluated", "unavailable", "unknown"))
            self.assertIsInstance(value[name]["evidence_sha256"], list)
        for name, reason in (("historical_record_tuple", "historical_record_not_supplied"),
                             ("historical_interpreter", "historical_interpreter_not_examined")):
            self.assertEqual(value[name], {"status": "not_evaluated", "reason": reason, "evidence_sha256": []})
        self.assertIs(value["historical_execution_qualified"], False)
        self.assertEqual(value["v2_historical_native_positive_compatibility"], "unsupported")
        self.assertEqual(value["legacy_tests"]["status"], "not_run")
        self.assertIsNone(value["legacy_tests"]["child_exit_code"])
        rendered = json.dumps(value)
        self.assertNotIn(str(ROOT), rendered)
        self.assertNotIn("PRIVATE-SOURCE-SENTINEL", rendered)

    def test_registry_is_closed_and_role_specific(self):
        m = self.subject()
        registry = m.load_registry()
        self.assertEqual(registry["engine_source_commit"], COMMIT)
        self.assertEqual(registry["source_tree"], TREE)
        self.assertEqual([(row["path"], row["blob"]) for row in registry["members"]], list(MEMBERS))
        self.assertEqual(set(registry["profiles"]), {"git-lf", "observed-windows-crlf"})
        for contract, profile, role in (("unknown", "git-lf", "historical_v1"),
                                        (CONTRACT, "unknown", "historical_v1"),
                                        (CONTRACT, "git-lf", "production_v2")):
            with self.subTest(contract=contract, profile=profile, role=role), self.assertRaises(m.VersionError):
                m.select(registry, contract, profile, role=role)
        self.assertEqual(m.select(registry, CONTRACT, "git-lf")["profile_id"], "git-lf")

    def test_registry_rejects_malformed_changed_or_duplicate_members(self):
        m = self.subject()
        registry = m.load_registry()
        bad = [b'{"schema":1,"schema":1}', b'{}', b'[]', b'null', b'\xff', b' ' * (128 * 1024 + 1)]
        for key, value in (("role", "production_v2"), ("engine_source_commit", "0" * 40),
                           ("source_tree", "0" * 40), ("normalization", "accept_any")):
            item = copy.deepcopy(registry)
            item[key] = value
            bad.append(encoded(item))
        for alteration in ("missing", "duplicate", "path", "mode", "hash", "extra"):
            item = copy.deepcopy(registry)
            if alteration == "missing":
                item["members"].pop()
            elif alteration == "duplicate":
                item["members"].append(copy.deepcopy(item["members"][0]))
            elif alteration == "path":
                item["members"][0]["path"] = "../PRIVATE-SOURCE-SENTINEL"
            elif alteration == "mode":
                item["members"][0]["mode"] = "120000"
            elif alteration == "hash":
                item["profiles"]["git-lf"]["raw_sha256"][2] = "0" * 64
            else:
                item["extra"] = True
            bad.append(encoded(item))
        for raw in bad:
            with self.subTest(raw_bytes=len(raw)), self.assertRaises(m.VersionError):
                m.load_registry(raw)

    def test_missing_fixed_git_objects_fail_without_fetch(self):
        m = self.subject()
        calls = []
        def missing(*arguments):
            calls.append(arguments)
            raise m.VersionError("source_unavailable")
        with patch.object(m, "_git_bytes", side_effect=missing), self.assertRaises(m.VersionError):
            m.read_objects(self.selection(m))
        self.assertTrue(calls)
        self.assertFalse(any(word in str(calls) for word in ("fetch", "clone", "checkout", "reset")))

    def test_exact_git_and_checkout_profiles_are_distinct(self):
        m = self.subject()
        for profile, expected in (("git-lf", RISK_LF), ("observed-windows-crlf", RISK_CRLF)):
            selected = self.selection(m, profile)
            objects = m.read_objects(selected)
            self.assertEqual(set(objects), {path for path, _ in MEMBERS})
            self.assertEqual(sum(len(raw) for raw in objects.values()), 1264582)
            with m.source_view(selected, objects) as view:
                view = Path(view)
                self.assertNotEqual(view.resolve(), ROOT.resolve())
                self.assertTrue((view / ".git").exists())
                self.assertEqual(hashlib.sha256((view / "src/risk.py").read_bytes()).hexdigest(), expected)
                self.assertEqual({p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_file()},
                                 {path for path, _ in MEMBERS} | {".git"})
                m.verify_view(view, selected)
            self.assertFalse(view.exists())

    def test_wrong_objects_refuse_before_source_view_creation(self):
        m = self.subject()
        selected = self.selection(m)
        objects = m.read_objects(selected)
        for kind in ("changed", "missing", "extra"):
            bad = dict(objects)
            if kind == "changed":
                bad["src/risk.py"] += b"\n# PRIVATE-SOURCE-SENTINEL\n"
            elif kind == "missing":
                bad.pop("src/risk.py")
            else:
                bad["../PRIVATE-SOURCE-SENTINEL"] = b"x"
            with self.subTest(kind=kind), self.assertRaises(m.VersionError):
                with m.source_view(selected, bad):
                    self.fail("unverified source view was made available")

    def test_source_view_alias_and_changed_bytes_are_refused(self):
        m = self.subject()
        selected = self.selection(m)
        with m.source_view(selected, m.read_objects(selected)) as view:
            risk_path = Path(view) / "src/risk.py"
            original_lstat = Path.lstat
            def alias(path, *args, **kwargs):
                result = original_lstat(path, *args, **kwargs)
                if path == risk_path:
                    return types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0x400)
                return result
            with patch.object(Path, "lstat", alias), self.assertRaises(m.VersionError):
                m.verify_view(view, selected)
            raw = risk_path.read_bytes()
            try:
                risk_path.write_bytes(raw + b"\n# changed external fixture\n")
                with self.assertRaises(m.VersionError):
                    m.verify_view(view, selected)
            finally:
                risk_path.write_bytes(raw)
            m.verify_view(view, selected)

    def test_actual_loaded_runtime_is_original_v1(self):
        m = self.subject()
        sentinel = types.ModuleType("risk")
        sentinel.__file__ = "PRIVATE-SOURCE-SENTINEL"
        for profile in ("git-lf", "observed-windows-crlf"):
            selected = self.selection(m, profile)
            with m.source_view(selected, m.read_objects(selected)) as view, patch.dict(sys.modules, {"risk": sentinel}):
                result = m.verify_runtime(view, selected)
            self.assertEqual(result["module_files"], {"risk": "src/risk.py", "native": "bench/w40_native.py", "core": "bench/w40_evidence.py"})
            self.assertIs(result["predicates"]["code_manifest"], True)
            self.assertIs(result["predicates"]["engine_bindings"], True)
            self.assertRegex(result["interpreter_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["evidence_sha256"], r"^[0-9a-f]{64}$")

    def test_original_plan_is_not_rebound(self):
        m = self.subject()
        for profile, engine in (("git-lf", RISK_LF), ("observed-windows-crlf", RISK_CRLF)):
            selected = self.selection(m, profile)
            with m.source_view(selected, m.read_objects(selected)) as view:
                plan = m.verify_runtime(view, selected)["synthetic_plan"]
            self.assertEqual(plan["declared_source_commit"], "1" * 40)
            self.assertEqual(plan["bindings"]["engine_sha256"], engine)
            for key in ("valid", "bytes_unchanged", "wrong_profile_refused", "unknown_binding_refused"):
                self.assertIs(plan[key], True, key)

    def test_wrong_loaded_code_defaults_and_rpc_refuse(self):
        m = self.subject()
        marker = "native.engine_bindings(risk)"
        self.assertEqual(m._CHILD_SCRIPT.count(marker), 1)
        mutations = ("risk.__file__ = 'wrong-runtime'", "risk.assess.__defaults__ = (None, True)",
                     "risk._CHAIN_RPC = {}")
        for mutation in mutations:
            script = m._CHILD_SCRIPT.replace(marker, mutation + "\n    " + marker)
            with self.subTest(mutation=mutation), patch.object(m, "_CHILD_SCRIPT", script):
                result = m.verify_source(CONTRACT, "git-lf")
            self.receipt(result)
            self.assertEqual(result["source_fixture"]["status"], "passed")
            self.assertEqual(result["loaded_runtime"]["status"], "failed")
            self.assertNotEqual(result["wrapper_exit_code"], 0)

    def test_fixture_success_does_not_qualify_history(self):
        m = self.subject()
        for profile in ("git-lf", "observed-windows-crlf"):
            value = m.verify_source(CONTRACT, profile)
            self.receipt(value)
            self.assertEqual(value["selected_profile"], profile)
            self.assertEqual(value["requested_profile"], profile)
            self.assertEqual(value["engine_source_commit"], COMMIT)
            self.assertEqual(value["source_tree"], TREE)
            self.assertEqual(value["invocation_status"], "completed")
            self.assertEqual(value["wrapper_exit_code"], 0)
            self.assertEqual(value["source_fixture"]["status"], "passed")
            self.assertEqual(value["loaded_runtime"]["status"], "passed")
            self.assertTrue(value["loaded_runtime"]["evidence_sha256"])

    def test_missing_and_unknown_profile_refuse_before_work(self):
        m = self.subject()
        for args in (("verify-source", CONTRACT), ("verify-source", CONTRACT, "unknown"),
                     ("verify-source", "unknown", "git-lf")):
            result = self.cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            value = json.loads(result.stdout)
            self.receipt(value)
            self.assertEqual(value["invocation_status"], "refused")
            self.assertIsNone(value["selected_profile"])
            self.assertEqual(value["loaded_runtime"]["status"], "not_evaluated")
        with patch.object(m, "read_objects", side_effect=AssertionError("objects must not be read")):
            value = m.verify_source(CONTRACT, "unknown")
            self.assertEqual(value["invocation_status"], "refused")

    def test_wrong_raw_profile_never_falls_back(self):
        m = self.subject()
        original = m.verify_view
        seen = []
        def mismatch(view, selected):
            seen.append(selected["profile_id"])
            raise m.VersionError("source_mismatch")
        with patch.object(m, "verify_view", side_effect=mismatch):
            value = m.verify_source(CONTRACT, "git-lf")
        self.receipt(value)
        self.assertNotEqual(value["wrapper_exit_code"], 0)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {"git-lf"})
        self.assertEqual(value["selected_profile"], "git-lf")
        self.assertEqual(value["loaded_runtime"]["status"], "not_evaluated")

    def test_cli_is_explicit_offline_and_rejects_all_operational_modes(self):
        for args in ((), ("--help",)):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
        for action in ("collect", "recover", "pilot", "study", "scheduler", "legacy-test", "report", "--runtime-child"):
            result = self.cli(action, CONTRACT, "git-lf", "tests/test_w40_native.py")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            value = json.loads(result.stdout)
            self.receipt(value)
            self.assertEqual(value["loaded_runtime"]["status"], "not_evaluated")

    def test_cli_fixed_profile_ignores_parent_checkout_and_pythonpath(self):
        with tempfile.TemporaryDirectory(prefix="engine-parent-") as directory:
            Path(directory, "risk.py").write_text("raise RuntimeError('PRIVATE-SOURCE-SENTINEL')\n", encoding="utf-8")
            for autocrlf in ("true", "false"):
                env = dict(os.environ, PYTHONPATH=directory, GIT_CONFIG_COUNT="1",
                           GIT_CONFIG_KEY_0="core.autocrlf", GIT_CONFIG_VALUE_0=autocrlf)
                result = self.cli("verify-source", CONTRACT, "git-lf", env=env)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(result.stderr, b"")
                value = json.loads(result.stdout)
                self.receipt(value)
                self.assertEqual(value["selected_profile"], "git-lf")
                self.assertEqual(value["source_fixture"]["status"], "passed")
                self.assertEqual(value["loaded_runtime"]["status"], "passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
