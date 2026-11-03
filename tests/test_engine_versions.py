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
        for action in ("collect", "recover", "pilot", "study", "scheduler", "report", "--runtime-child"):
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
    def test_r2_all_valid_result_layer_vectors(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "_validate_result_layers", None)), "T-071 R2 pure result-layer guard is missing")
        vectors = (
            ("fixture_and_present_runtime_pass_history_not_checked", "passed", "passed", "not_evaluated", "not_evaluated"),
            ("good_fixture_wrong_loaded_runtime", "passed", "failed", "not_evaluated", "not_evaluated"),
            ("good_fixture_runtime_not_checked", "passed", "not_evaluated", "not_evaluated", "not_evaluated"),
            ("known_absent_history_stays_unavailable", "passed", "passed", "unavailable", "unavailable"),
            ("inconclusive_history_stays_unknown", "passed", "passed", "unknown", "unknown"),
        )
        for label, fixture, runtime, record, interpreter in vectors:
            value = {"historical_execution_qualified": False}
            for name, status, token in zip(LAYERS, (fixture, runtime, record, interpreter), "abcd"):
                if name in LAYERS[2:]:
                    reason = {"not_evaluated": "historical_record_not_supplied" if name == LAYERS[2] else "historical_interpreter_not_examined",
                              "unavailable": "historical_record_unavailable" if name == LAYERS[2] else "historical_interpreter_unavailable",
                              "unknown": "historical_record_unknown" if name == LAYERS[2] else "historical_interpreter_unknown"}[status]
                else:
                    reason = "runtime_mismatch" if status == "failed" else None
                value[name] = {"status": status, "reason": reason,
                               "evidence_sha256": [token * 64] if status == "passed" else []}
            before = encoded(value)
            with self.subTest(vector=label), patch.object(m.subprocess, "run", side_effect=AssertionError("pure guard performed IO")):
                self.assertIs(m._validate_result_layers(value), value)
            self.assertEqual(encoded(value), before)

    def test_r2_rejects_result_layer_promotions(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "_validate_result_layers", None)), "T-071 R2 pure result-layer guard is missing")
        base = {"historical_execution_qualified": False,
                "source_fixture": {"status": "passed", "reason": None, "evidence_sha256": ["a" * 64]},
                "loaded_runtime": {"status": "passed", "reason": None, "evidence_sha256": ["b" * 64]},
                "historical_record_tuple": {"status": "not_evaluated", "reason": "historical_record_not_supplied", "evidence_sha256": []},
                "historical_interpreter": {"status": "not_evaluated", "reason": "historical_interpreter_not_examined", "evidence_sha256": []}}
        bad = []
        for label, layer in (("fixture_promotes_historical_tuple", LAYERS[2]),
                             ("current_interpreter_promotes_historical_interpreter", LAYERS[3])):
            value = copy.deepcopy(base)
            value[layer] = {"status": "passed", "reason": None, "evidence_sha256": ["c" * 64]}
            bad.append((label, value))
        value = copy.deepcopy(base)
        value["historical_execution_qualified"] = True
        bad.append(("global_history_pass_from_fixture", value))
        value = copy.deepcopy(base)
        value["source_fixture"] = {"status": "failed", "reason": "source_mismatch", "evidence_sha256": []}
        bad.append(("runtime_pass_without_matching_fixture", value))
        value = copy.deepcopy(base)
        value["loaded_runtime"] = copy.deepcopy(value["source_fixture"])
        bad.append(("fixture_status_and_evidence_copied_into_runtime", value))
        for label, layer, key, replacement in (
            ("unexamined_history_with_fabricated_evidence", LAYERS[2], "evidence_sha256", ["c" * 64]),
            ("unavailable_history_with_execution_evidence", LAYERS[3], "status", "unavailable"),
            ("invalid_hash", LAYERS[0], "evidence_sha256", ["not-a-sha"]),
            ("arbitrary_reason", LAYERS[1], "reason", "PRIVATE-SOURCE-SENTINEL"),
            ("unknown_status", LAYERS[0], "status", "assumed_passed"),
            ("extra_layer_key", LAYERS[0], "extra", True),
        ):
            value = copy.deepcopy(base)
            value[layer][key] = replacement
            if label == "unavailable_history_with_execution_evidence":
                value[layer].update(reason="historical_interpreter_unavailable", evidence_sha256=["c" * 64])
            bad.append((label, value))
        for label, value in bad:
            with self.subTest(vector=label), self.assertRaises(m.VersionError) as raised:
                m._validate_result_layers(value)
            self.assertEqual(raised.exception.code, "invalid_result_layers")

    def test_r2_real_receipt_uses_layer_guard(self):
        import io
        m = self.subject()
        self.assertTrue(callable(getattr(m, "_validate_result_layers", None)), "T-071 R2 pure result-layer guard is missing")
        refusal = m.VersionError("invalid_result_layers")
        with patch.object(m, "_validate_result_layers", side_effect=refusal) as guard:
            value = m.verify_source(CONTRACT, "unknown")
        self.assertEqual(guard.call_count, 1)
        self.receipt(value)
        self.assertEqual(value["reason"], "invalid_result_layers")
        self.assertNotEqual(value["wrapper_exit_code"], 0)
        forged = m._receipt(CONTRACT, "git-lf")
        forged.update(invocation_status="completed", wrapper_exit_code=0)
        stream = io.BytesIO()
        with patch.object(m, "verify_source", return_value=forged), \
                patch.object(m, "_validate_result_layers", side_effect=refusal) as guard, \
                patch.object(m.sys, "stdout", types.SimpleNamespace(buffer=stream)):
            native_exit = m.main(["verify-source", CONTRACT, "git-lf"])
        self.assertEqual(guard.call_count, 1)
        emitted = json.loads(stream.getvalue())
        self.receipt(emitted)
        self.assertEqual(emitted["reason"], "invalid_result_layers")
        self.assertNotEqual(native_exit, 0)
        self.assertEqual(emitted["wrapper_exit_code"], native_exit)


class B12DispatchAcceptance(unittest.TestCase):
    """T-073: closed dispatch, actual tiny children and persistent uncertainty admission."""

    def subject(self):
        return EngineVersionAcceptance.subject(self)

    def cli(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(HELPER), *arguments], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=150)

    def observation(self, ids, exit_code=0):
        return {"child_exit_code": exit_code, "executed_test_ids": list(ids),
            "runtime": {"predicates": {"code_manifest": True, "engine_bindings": True},
                        "interpreter_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
                        "module_files": {"risk": "src/risk.py", "native": "bench/w40_native.py",
                                         "core": "bench/w40_evidence.py"}, "manifest_sha256": "a" * 64},
            "stdout_sha256": hashlib.sha256(b"unit stdout").hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(), "stdout_complete": True, "stderr_complete": True,
            "timed_out": False, "interrupted": False, "overflow": False,
            "outer_lifecycle": {"final_observed": True, "uncertain": False},
            "descendant_observations_complete": False,
            "descendant_observations": [{"command": None, "exit_code": None,
                                         "state": "not_recorded", "observation_source": "not_recorded"}],
            "harness_assertion_evidence": "original_harness_assertions", "dynamic_counters": None}

    def tiny_view(self, operation, exit_code=0):
        view = operation["path"] / "source"
        files = {
            "bench/w40_native.py": "from pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef code_manifest(): return {'unit':True}\ndef engine_bindings(risk): assert risk.UNIT is True\n",
            "bench/w40_evidence.py": "UNIT=True\n",
            "src/risk.py": "UNIT=True\n",
            "tests/test_tiny.py": "import sys\ndef test_a(): print('unit stdout')\nif __name__=='__main__':\n    test_a()\n    raise SystemExit(%d)\n" % exit_code,
        }
        for name, text in files.items():
            path = view / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return view

    def planned_workflow(self):
        text = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        if "run: python tests/test_w40_native.py" in text:
            text = text.replace("        run: python tests/test_w40_native.py",
                "        run: python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py\n"
                "\n      - name: Current adapter data regression\n"
                "        run: python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests", 1)
            text = text.replace("        run: python tests/test_w40_native_clock.py",
                "        run: python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native_clock.py", 1)
        return text

    def test_legacy_dispatch_whitelist_and_exact_argv(self):
        # On the parent this reaches the real unsupported-command refusal, not a missing import.
        result = self.cli("legacy-test", CONTRACT, "git-lf", "tests/not_allowed.py")
        value = json.loads(result.stdout)
        self.assertEqual(value["operation"], "legacy-test")
        self.assertEqual(value["reason"], "unknown_runner")
        self.assertNotEqual(result.returncode, 0)
        m = self.subject()
        self.assertTrue(callable(getattr(m, "legacy_test", None)), "fixed legacy dispatch is absent")
        with tempfile.TemporaryDirectory(prefix="t073-whitelist-") as directory:
            scope = Path(directory) / "scope"
            with patch.object(m, "_launch_test_child", side_effect=AssertionError("refusal spawned a child")) as child:
                for contract, profile, runner in (("unknown", "git-lf", "tests/test_w40_native.py"),
                        (CONTRACT, "unknown", "tests/test_w40_native.py"),
                        (CONTRACT, "git-lf", "../tests/test_w40_native.py"),
                        (CONTRACT, "git-lf", "tests/not_allowed.py")):
                    refused = m.legacy_test(contract, profile, runner, scope=scope)
                    self.assertNotEqual(refused["wrapper_exit_code"], 0)
                    self.assertEqual(refused["legacy_tests"]["status"], "not_run")
                child.assert_not_called()
            with patch.object(m, "begin_validation_operation", side_effect=AssertionError("ineligible operation")) as admission, \
                    patch.object(m, "_launch_test_child", side_effect=AssertionError("ineligible child")) as child:
                for runner in ("tests/test_w40_native.py", "tests/test_w40_native_clock.py"):
                    refused = m.legacy_test(CONTRACT, "git-lf", runner, scope=scope)
                    self.assertEqual(refused["reason"], "legacy_native_execution_unqualified")
                    self.assertEqual(refused["wrapper_exit_code"], 2)
                    self.assertEqual(refused["legacy_tests"]["status"], "not_run")
                admission.assert_not_called()
                child.assert_not_called()
            seen = []
            def child(view, runner, ids, seconds, operation, selector=None):
                seen.append((runner, list(ids), seconds, selector))
                return self.observation(ids)
            with patch.object(m, "_launch_test_child", side_effect=child):
                for runner, selector, count, seconds in (("tests/test_w40_native.py", "native-all16", 16, 900),
                                                         ("tests/test_w40_native_clock.py", "clock-all3", 3, 180)):
                    completed = m.maintained_test(CONTRACT, "git-lf", selector, scope=scope)
                    self.assertEqual(completed["wrapper_exit_code"], 0)
                    self.assertEqual(len(seen[-1][1]), count)
                    self.assertEqual(seen[-1][2:], (seconds, None))
                    self.assertEqual(completed["maintained_runner"], runner)
                    self.assertEqual(completed["domain"], "maintained_adapter_on_fixed_v1_dependencies")
                    self.assertTrue(completed["test_execution_qualified"])
            self.assertEqual(len(seen), 2)  # Unit spies; no complete native/clock execution.

    def test_legacy_execution_and_exit_are_real(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "begin_validation_operation", None)), "operation admission is absent")
        with tempfile.TemporaryDirectory(prefix="t073-exit-") as directory:
            scope = Path(directory) / "scope"
            for code in (0, 7):
                operation = m.begin_validation_operation(scope)
                view = self.tiny_view(operation, code)
                observation = m._launch_test_child(view, "tests/test_tiny.py", ["test_a"], 10, operation)
                self.assertEqual(observation["child_exit_code"], code)
                self.assertEqual(observation["executed_test_ids"], ["test_a"])
                self.assertEqual(observation["runtime"]["predicates"],
                                 {"code_manifest": True, "engine_bindings": True})
                self.assertEqual(m.test_execution_qualified(observation, ["test_a"]), code == 0)
                self.assertFalse(observation["descendant_observations_complete"])
                self.assertEqual(observation["descendant_observations"][-1]["exit_code"], None)
                self.assertEqual(observation["descendant_observations"][-1]["state"], "not_recorded")
            for fault in ("no_op", "missing_id", "nonzero", "wrong_runtime"):
                observed = self.observation(["test_a"])
                if fault in ("no_op", "missing_id"):
                    observed["executed_test_ids"] = []
                elif fault == "nonzero":
                    observed["child_exit_code"] = 7
                else:
                    observed["runtime"]["predicates"]["engine_bindings"] = False
                self.assertFalse(m.test_execution_qualified(observed, ["test_a"]))
            seen = []
            def failure(view, runner, ids, seconds, operation, selector=None):
                seen.append(runner)
                return self.observation(ids, 7)
            with patch.object(m, "_launch_test_child", side_effect=failure):
                receipt = m.legacy_test(CONTRACT, "git-lf", "tests/test_w40_native.py", scope=scope)
            self.assertEqual(receipt["legacy_tests"]["child_exit_code"], 7)
            self.assertEqual(receipt["wrapper_exit_code"], 7)
            self.assertEqual(receipt["legacy_tests"]["status"], "failed")
            self.assertEqual(seen, ["tests/test_w40_native.py"])

    def test_whole_historical_dataset_dispatches_once(self):
        result = self.cli("legacy-test", CONTRACT, "git-lf", "tests/test_dataset_replayable.py")
        self.assertEqual(result.returncode, 0, result.stdout.decode())
        value = json.loads(result.stdout)
        self.assertEqual(value["operation"], "legacy-test")
        self.assertEqual(value["original_runner"], "tests/test_dataset_replayable.py")
        self.assertEqual(value["legacy_tests"]["status"], "passed")
        self.assertEqual(len(value["legacy_tests"]["executed_test_ids"]), 9)
        self.assertEqual(value["legacy_tests"]["dynamic_counters"]["failed"], 0)
        self.assertGreater(value["legacy_tests"]["dynamic_counters"]["passed"], 0)
        self.assertGreaterEqual(value["legacy_tests"]["dynamic_counters"]["not_checked"], 0)
        self.assertEqual(value["source_fixture"]["status"], "passed")
        self.assertEqual(value["loaded_runtime"]["status"], "passed")
        self.assertIs(value["historical_execution_qualified"], False)
        self.assertFalse(value["descendant_observations_complete"])

    def test_current_workflow_dispatch_is_real(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "workflow_dispatch_contract", None)), "semantic workflow guard is absent")
        planned = self.planned_workflow()
        good = m.workflow_dispatch_contract(planned)
        self.assertEqual(good["status"], "registered")
        self.assertEqual(good["actual_count"], 47)
        self.assertIn("python tests/test_backfill.py --offline", good["commands"])
        actual = m.workflow_dispatch_contract((ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8"))
        self.assertIn(actual["status"], ("registered", "registration_pending"))
        self.assertEqual(actual["actual_count"], 47 if actual["status"] == "registered" else 46)
        legacy = "python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py"
        adapter = "python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests"
        for mutated in (planned.replace("run: " + legacy, "# run: " + legacy, 1),
                        planned.replace(legacy, "python -c pass", 1),
                        planned.replace(adapter, adapter + " extra", 1),
                        planned.replace("python tests/test_backfill.py --offline", "python tests/test_backfill.py", 1)):
            self.assertEqual(m.workflow_dispatch_contract(mutated)["status"], "invalid")

    def test_receipt_scopes_match_executed_domain(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "test_execution_qualified", None)), "truthful execution qualification is absent")
        observed = self.observation(["test_a"])
        self.assertTrue(m.test_execution_qualified(observed, ["test_a"]))
        self.assertFalse(observed["descendant_observations_complete"])
        for corruption in ("inferred_zero", "complete_tree", "timeout", "no_final"):
            bad = copy.deepcopy(observed)
            if corruption == "inferred_zero":
                bad["descendant_observations"][0]["exit_code"] = 0
            elif corruption == "complete_tree":
                bad["descendant_observations_complete"] = True
            elif corruption == "timeout":
                bad["timed_out"] = True
            else:
                bad["outer_lifecycle"]["final_observed"] = False
            self.assertFalse(m.test_execution_qualified(bad, ["test_a"]))
        with tempfile.TemporaryDirectory(prefix="t073-quarantine-") as directory:
            scope = Path(directory) / "isolated-negative-scope"
            def timeout(view, runner, ids, seconds, operation, selector=None):
                observation = self.observation(ids)
                observation.update(timed_out=True)
                observation["outer_lifecycle"] = {"final_observed": False, "uncertain": True}
                return observation
            with patch.object(m, "_launch_test_child", side_effect=timeout):
                failed = m.legacy_test(CONTRACT, "git-lf", "tests/test_dataset_replayable.py", scope=scope)
            self.assertFalse(failed["test_execution_qualified"])
            marker = scope / "quarantine.json"
            self.assertTrue(marker.is_file())
            original = marker.read_bytes()
            self.assertTrue(list(scope.glob("operations/*/source/src/risk.py")))
            with self.assertRaises(m.VersionError):
                m.validation_admission(scope)
            with patch.object(m, "_launch_test_child", side_effect=AssertionError("successor launched")) as child:
                refused = m.legacy_test(CONTRACT, "git-lf", "tests/test_w40_native.py", scope=scope)
                self.assertNotEqual(refused["wrapper_exit_code"], 0)
                child.assert_not_called()
            self.assertEqual(marker.read_bytes(), original)
            # This is the nested-suite -> root operator admission seam, not a CI/test flag.
            successors = []
            try:
                m.validation_admission(scope)
                successors.append("heavy")
            except m.VersionError:
                pass
            self.assertEqual(successors, [])
            self.assertEqual(marker.read_bytes(), original)

    def test_current_adapter_context_is_separate_and_complete(self):
        m = self.subject()
        self.assertTrue(callable(getattr(m, "adapter_test", None)), "fixed contemporary context is absent")
        selected = m.select(m.load_registry(), CONTRACT, "git-lf")
        objects = m.read_objects(selected)
        bodies, identity = m.adapter_sources(selected, objects)
        self.assertEqual(len(bodies), 8)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        self.assertEqual(identity["current_adapter_identity"]["candidate_commit"], head)
        self.assertEqual(bodies["bench/w40_native.py"], subprocess.check_output(
            ["git", "show", "HEAD:bench/w40_native.py"], cwd=ROOT))
        self.assertEqual(bodies["tests/test_w40_native.py"], subprocess.check_output(
            ["git", "show", "HEAD:tests/test_w40_native.py"], cwd=ROOT))
        bad = dict(objects)
        bad["src/risk.py"] += b"\n# altered fixed dependency\n"
        with self.assertRaises(m.VersionError):
            m.adapter_sources(selected, bad)
        with tempfile.TemporaryDirectory(prefix="t073-adapter-") as directory:
            scope = Path(directory) / "scope"
            seen = []
            def child(view, runner, ids, seconds, operation, selector=None):
                self.assertEqual(selector, "InterruptedProgressStagingTests")
                self.assertEqual(len(ids), 3)
                self.assertEqual(seconds, 120)
                with self.assertRaises(m.VersionError):
                    m.verify_view(view, selected)  # The8-member context cannot claim original11.
                seen.append(runner)
                return self.observation(ids)
            with patch.object(m, "_launch_test_child", side_effect=child):
                receipt = m.adapter_test(CONTRACT, "git-lf", "InterruptedProgressStagingTests", scope=scope)
            self.assertEqual(receipt["schema"], "engine-adapter-regression-v1")
            self.assertEqual(receipt["domain"], "current_adapter_on_v1_dependencies")
            self.assertEqual(receipt["wrapper_exit_code"], 0)
            self.assertTrue(receipt["test_execution_qualified"])
            for field in ("historical_execution_qualified", "current_production_behavior_qualified",
                          "original_v1_fixture_qualified_by_adapter_result"):
                self.assertIs(receipt[field], False)
            self.assertEqual(receipt["v2_historical_native_positive_compatibility"], "unsupported")
            self.assertEqual(seen, ["tests/test_w40_native.py"])
            for field in ("domain", "historical_execution_qualified"):
                forged = copy.deepcopy(receipt)
                forged[field] = "historical_v1" if field == "domain" else True
                with self.assertRaises(m.VersionError):
                    m.validate_dispatch_receipt(forged)
            with patch.object(m, "_launch_test_child", side_effect=AssertionError("invalid selector spawned")):
                for profile, selector in (("observed-windows-crlf", "InterruptedProgressStagingTests"),
                                           ("git-lf", "NativeAcceptance")):
                    self.assertNotEqual(m.adapter_test(CONTRACT, profile, selector, scope=scope)["wrapper_exit_code"], 0)

    def test_original_native_refuses_changed_production_source(self):
        m = self.subject()
        selected = m.select(m.load_registry(), CONTRACT, "git-lf")
        with self.assertRaises(m.VersionError):
            m.select(m.load_registry(), CONTRACT, "git-lf", role="production_v2")
        with m.source_view(selected, m.read_objects(selected)) as view:
            path = Path(view) / "src/risk.py"
            original = path.read_bytes()
            try:
                path.write_bytes(original + b"\n_T073_CHANGED_PRODUCTION_SOURCE = 1\n")
                script = "\n".join(["import sys", "sys.path[:0]=[sys.argv[1]+'/bench',sys.argv[1]+'/src']",
                    "import w40_native as n", "try: n.code_manifest()",
                    "except n.NativeError as e:", "    assert str(e)=='source_drift'; print('source_drift')",
                    "else: raise AssertionError('changed source accepted')"])
                child = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(view)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
                self.assertEqual(child.returncode, 0, child.stderr.decode())
                self.assertEqual(child.stdout.strip(), b"source_drift")
            finally:
                path.write_bytes(original)
            m.verify_view(view, selected)


class B12ReviewRegressionAcceptance(unittest.TestCase):
    """NC5: bounded review regressions; spies never start an OS process."""

    def subject(self):
        return EngineVersionAcceptance.subject(self)

    def observation(self, ids):
        return B12DispatchAcceptance.observation(self, ids)

    def test_postlaunch_evidence_failures_preserve_admission_quarantine(self):
        import io
        modes = ("observation_cap", "observation_version", "observation_os",
                 "marker_failure", "receipt_version", "receipt_os", "receipt_protocol", "valid_A1")
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="t073-review-m1-") as directory:
                m = self.subject()
                scope = Path(directory) / "synthetic-scope"
                original_launch, original_write = m._launch_test_child, m._write_json
                seen = []
                def launch(view, runner, ids, seconds, operation, selector=None):
                    report = self.observation(ids)
                    for field in ("child_exit_code", "stdout_sha256", "stderr_sha256", "stdout_complete",
                                  "stderr_complete", "timed_out", "interrupted", "overflow"):
                        report.pop(field)
                    report["reported_original_exit"] = 0
                    report["runtime"].update(test_process_pid=732001, validation_operation_id=operation["id"])
                    if mode.startswith("observation") or mode == "marker_failure":
                        report["outer_lifecycle"]["uncertain"] = True
                    if mode == "observation_cap":
                        report.update(padding="", evidence_sha256="0" * 64)
                        report["padding"] = "x" * (m.STREAM_CAP - 32 - len(m.encoded(report)))
                    report.pop("evidence_sha256", None)
                    report["evidence_sha256"] = m.sha(m.encoded(report))
                    raw = m.encoded(report)
                    self.assertLessEqual(len(raw), m.STREAM_CAP)
                    class Process:
                        pid = 732001
                        def __init__(self, *args, **kwargs):
                            self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
                            (operation["path"] / "child-report.json").write_bytes(raw)
                        def poll(self):
                            return 0
                    seen.append(operation)
                    with patch.object(m.subprocess, "Popen", Process):
                        return original_launch(view, runner, ids, seconds, operation, selector)
                def write(path, value, **kwargs):
                    if path.name == "observation.json" and mode in ("observation_version", "observation_os", "marker_failure"):
                        if mode == "observation_version":
                            raise m.VersionError("child_protocol_invalid")
                        raise OSError("synthetic evidence publication failure")
                    if path.name == "quarantine.json" and mode == "marker_failure":
                        raise OSError("synthetic marker publication failure")
                    if path.name == "receipt.json" and mode in ("receipt_version", "receipt_os"):
                        if mode == "receipt_version":
                            raise m.VersionError("child_protocol_invalid")
                        raise OSError("synthetic receipt publication failure")
                    return original_write(path, value, **kwargs)
                original_validator = m.validate_dispatch_receipt
                def validate(value):
                    if mode == "receipt_protocol" and seen:
                        raise m.VersionError("child_protocol_invalid")
                    return original_validator(value)
                result = None
                escaped = None
                with patch.object(m, "_launch_test_child", side_effect=launch), \
                        patch.object(m, "_write_json", side_effect=write), \
                        patch.object(m, "validate_dispatch_receipt", side_effect=validate):
                    try:
                        result = m.legacy_test(CONTRACT, "git-lf", "tests/test_w40_native.py", scope=scope)
                    except Exception as error:
                        escaped = error
                    admitted = False
                    admission_error = None
                    try:
                        m.validation_admission(scope)
                        admitted = True
                    except Exception as error:
                        admission_error = error
                self.assertEqual(len(seen), 1)
                op = seen[0]
                self.assertTrue((op["path"] / "source/src/risk.py").is_file())
                self.assertTrue((op["path"] / "child-report.json").is_file())
                if mode == "valid_A1":
                    self.assertIsNone(escaped)
                    self.assertTrue(admitted)
                    self.assertEqual(result["wrapper_exit_code"], 0)
                    self.assertTrue(result["test_execution_qualified"])
                    self.assertFalse(result["descendant_observations_complete"])
                    self.assertIsNone(result["descendant_observations"][-1]["exit_code"])
                else:
                    self.assertFalse(admitted, "postlaunch evidence failure admitted a successor")
                    self.assertIsInstance(admission_error, m.VersionError)
                    self.assertNotEqual(json.loads((op["path"] / "state.json").read_bytes())["status"], "finished")
                    self.assertTrue(escaped is None or isinstance(escaped, m.VersionError), repr(escaped))
                    if result is not None:
                        self.assertNotEqual(result["wrapper_exit_code"], 0)
                        self.assertFalse(result["test_execution_qualified"])
                        self.assertEqual(result["legacy_tests"]["child_exit_code"], 0)
                        self.assertEqual(result["legacy_tests"]["status"], "failed")

    def test_finished_operation_state_requires_exact_identity(self):
        modes = ("valid", "foreign_id", "missing_id", "integer_id", "null_id", "list_id",
                 "extra_key", "boolean_status", "nonobject", "malformed", "duplicate_key",
                 "missing_file", "running", "unknown_status", "invalid_directory", "linked_state", "overcount")
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="t073-review-m2-") as directory:
                m = self.subject()
                scope = m._scope_path(Path(directory) / "synthetic-scope")
                identity = "a" * 32 if mode != "invalid_directory" else "g" * 32
                operation = scope / "operations" / identity
                operation.mkdir()
                state = {"status": "finished", "operation_id": identity}
                if mode == "foreign_id":
                    state["operation_id"] = "b" * 32
                elif mode == "missing_id":
                    state.pop("operation_id")
                elif mode in ("integer_id", "null_id", "list_id"):
                    state["operation_id"] = {"integer_id": 4, "null_id": None, "list_id": []}[mode]
                elif mode == "extra_key":
                    state["unproved"] = True
                elif mode == "boolean_status":
                    state["status"] = True
                elif mode in ("running", "unknown_status"):
                    state["status"] = "running" if mode == "running" else "retired_somehow"
                elif mode == "nonobject":
                    state = []
                raw = encoded(state)
                if mode == "malformed":
                    raw = b"{"
                elif mode == "duplicate_key":
                    raw = ('{"status":"running","status":"finished","operation_id":"' + identity + '"}').encode()
                path = operation / "state.json"
                if mode != "missing_file":
                    path.write_bytes(raw)
                if mode == "linked_state":
                    os.link(path, operation / "state-alias.json")
                if mode == "overcount":
                    for number in range(m.OPERATION_CAP):
                        other_id = format(number, "032x")
                        other = scope / "operations" / other_id
                        other.mkdir()
                        (other / "state.json").write_bytes(encoded({"status": "finished", "operation_id": other_id}))
                admitted = False
                error = None
                try:
                    m.validation_admission(scope)
                    admitted = True
                except Exception as observed:
                    error = observed
                if mode == "valid":
                    self.assertTrue(admitted)
                    self.assertIsNone(error)
                    self.assertFalse((scope / "quarantine.json").exists())
                else:
                    self.assertFalse(admitted, "unproved completed-state identity admitted a successor")
                    self.assertIsInstance(error, m.VersionError)
                if mode != "missing_file":
                    self.assertEqual(path.read_bytes(), raw)

    def test_dispatch_receipt_cannot_cross_source_and_case_domains(self):
        m = self.subject()
        receipts = {}
        def child(view, runner, ids, seconds, operation, selector=None):
            observed = self.observation(ids)
            if runner == "tests/test_dataset_replayable.py":
                observed["dynamic_counters"] = {"passed": 1, "failed": 0, "not_checked": 0}
            return observed
        with tempfile.TemporaryDirectory(prefix="t073-review-m3-") as directory:
            scope = Path(directory) / "synthetic-scope"
            with patch.object(m, "_launch_test_child", side_effect=child):
                for name, runner, count in (("native", "tests/test_w40_native.py", 13),
                                             ("clock", "tests/test_w40_native_clock.py", 3),
                                             ("dataset", "tests/test_dataset_replayable.py", 9)):
                    value = m.legacy_test(CONTRACT, "git-lf", runner, scope=scope)
                    self.assertEqual(len(value["legacy_tests"]["executed_test_ids"]), count)
                    receipts[name] = value
                receipts["crlf"] = m.legacy_test(CONTRACT, "observed-windows-crlf", "tests/test_w40_native.py", scope=scope)
                receipts["adapter"] = m.adapter_test(CONTRACT, "git-lf", "InterruptedProgressStagingTests", scope=scope)
            for name, value in receipts.items():
                with self.subTest(valid=name):
                    self.assertTrue(value["test_execution_qualified"])
                    candidate = copy.deepcopy(value)
                    self.assertIs(m.validate_dispatch_receipt(candidate), candidate)
                    self.assertFalse(value["descendant_observations_complete"])
        def refused(label, value):
            with self.subTest(refused=label):
                caught = None
                try:
                    m.validate_dispatch_receipt(value)
                except Exception as error:
                    caught = error
                self.assertIsInstance(caught, m.VersionError, "invalid artifact admitted or escaped with an uncontrolled exception")
                self.assertNotIn("NC5_UNKNOWN_CALLER", str(caught))
        adapter = receipts["adapter"]
        forged = copy.deepcopy(adapter)
        forged.update(schema="engine-version-qualification-v1", operation="legacy-test", role="historical_v1",
            original_runner="tests/test_w40_native.py",
            command_argv=["python", "tools/engine_versions.py", "legacy-test", CONTRACT, "git-lf", "tests/test_w40_native.py"])
        forged["legacy_tests"] = copy.deepcopy(forged["adapter_tests"])
        refused("adapter relabel with adapter fields", forged)
        for field in ("adapter_tests", "domain", "dependency_identity", "current_adapter_identity",
                      "original_v1_fixture_qualified_by_adapter_result", "current_production_behavior_qualified"):
            forged.pop(field)
        refused("adapter relabel with adapter fields removed", forged)
        vectors = [
            ("contract_id", "NC5_UNKNOWN_CALLER"), ("engine_source_commit", "0" * 40),
            ("source_tree", "1" * 40), ("selected_profile", "NC5_UNKNOWN_CALLER"),
            ("requested_profile", "observed-windows-crlf"), ("original_runner", "tests/not_allowed.py"),
            ("command_argv", ["NC5_UNKNOWN_CALLER"]), ("context_manifest_sha256", "2" * 64),
            ("test_execution_qualified", 1), ("wrapper_exit_code", True), ("reason", "NC5_UNKNOWN_CALLER"),
            ("invocation_status", "failed"), ("historical_execution_qualified", True),
            ("v2_historical_native_positive_compatibility", "supported"), ("descendant_observations", []),
            ("unexpected", "NC5_UNKNOWN_CALLER")]
        for field, replacement in vectors:
            value = copy.deepcopy(receipts["native"])
            value[field] = replacement
            refused("legacy " + field, value)
        for name in ("native", "clock", "dataset"):
            for ids in (["arbitrary.test"], list(m.ADAPTER_IDS), ["bad"] * 3, [{"bad": True}]):
                value = copy.deepcopy(receipts[name])
                value["legacy_tests"]["executed_test_ids"] = ids
                value["legacy_tests"]["executed_test_ids_sha256"] = m.sha(m.encoded(ids))
                refused(name + " wrong IDs " + str(ids)[:24], value)
        for field, replacement in (("executed_test_ids_sha256", "x" * 64), ("stdout_sha256", None),
                                   ("stderr_sha256", "2" * 63), ("child_exit_code", True), ("status", "not_run")):
            value = copy.deepcopy(receipts["native"])
            value["legacy_tests"][field] = replacement
            refused("legacy test " + field, value)
        for field, replacement in (("domain", "historical_v1"), ("original_runner", "tests/test_w40_native.py"),
                                   ("selected_profile", "observed-windows-crlf"), ("current_production_behavior_qualified", True),
                                   ("original_v1_fixture_qualified_by_adapter_result", True)):
            value = copy.deepcopy(adapter)
            value[field] = replacement
            refused("adapter " + field, value)
        for domain in ("dependency_identity", "current_adapter_identity"):
            for fault in ("nonobject", "missing", "duplicate", "foreign_path", "wrong_type", "bad_blob", "bad_hash", "extra"):
                value = copy.deepcopy(adapter)
                identity = value[domain]
                if fault == "nonobject":
                    value[domain] = []
                elif fault == "missing":
                    identity["members"].pop()
                elif fault == "duplicate":
                    identity["members"].append(copy.deepcopy(identity["members"][0]))
                elif fault == "foreign_path":
                    identity["members"][0]["path"] = "NC5_UNKNOWN_CALLER"
                elif fault == "wrong_type":
                    identity["members"] = [None]
                elif fault == "bad_blob":
                    identity["members"][0]["blob"] = "z" * 40
                elif fault == "bad_hash":
                    identity["members"][0]["canonical_sha256"] = "3" * 64
                else:
                    identity["extra"] = True
                refused(domain + " " + fault, value)
        for field, replacement in (("candidate_commit", True), ("candidate_tree", "g" * 40)):
            value = copy.deepcopy(adapter)
            value["current_adapter_identity"][field] = replacement
            refused(field, value)
        for field, replacement in (("raw_bytes", True), ("mode", "100755"), ("raw_sha256", "g" * 64)):
            value = copy.deepcopy(adapter)
            value["current_adapter_identity"]["members"][0][field] = replacement
            refused("candidate " + field, value)
        value = copy.deepcopy(receipts["dataset"])
        value["legacy_tests"]["dynamic_counters"]["failed"] = 1
        refused("positive dataset with failed dynamic cases", value)
        for value in (None, [], {"schema": "NC5_UNKNOWN_CALLER"}):
            refused("nonreceipt", value)


class MaintainedAdapterAcceptance(unittest.TestCase):
    """T-075: synthetic metadata/spies only; no native, risk, dataset or test child."""

    def subject(self):
        import builtins
        original_import = builtins.__import__
        original_spec = importlib.util.spec_from_file_location
        original_popen = subprocess.Popen
        blocked = {"w40_native", "w40_evidence", "risk", "labels", "goplus_quota_probe",
                   "test_w40_native", "test_w40_native_clock", "test_dataset_replayable"}
        def imports(name, *args, **kwargs):
            if blocked.intersection(name.split(".")):
                raise AssertionError("metadata test forbids native/dependency imports")
            return original_import(name, *args, **kwargs)
        def specs(name, location, *args, **kwargs):
            allowed = {HELPER.resolve(), (ROOT / ".github/scripts/offline_suite.py").resolve()}
            if Path(location).resolve() not in allowed:
                raise AssertionError("metadata test forbids another project module")
            return original_spec(name, location, *args, **kwargs)
        def processes(command, *args, **kwargs):
            if (not isinstance(command, (list, tuple)) or not command
                    or Path(str(command[0])).name.lower() not in {"git", "git.exe"}
                    or not any(word in command for word in ("cat-file", "ls-tree", "rev-parse"))):
                raise AssertionError("metadata test permits only fixed read-only Git children")
            return original_popen(command, *args, **kwargs)
        for target, name, replacement in ((builtins, "__import__", imports),
                (importlib.util, "spec_from_file_location", specs), (subprocess, "Popen", processes)):
            guard = patch.object(target, name, side_effect=replacement)
            guard.start()
            self.addCleanup(guard.stop)
        m = EngineVersionAcceptance.subject(self)
        guard = patch.object(m, "verify_runtime", side_effect=AssertionError("no separate runtime child in metadata tests"))
        guard.start()
        self.addCleanup(guard.stop)
        return m

    def _required(self, m, name):
        function = getattr(m, name, None)
        self.assertTrue(callable(function), "T-075 required closed interface is absent: " + name)
        return function

    def _cli(self, m, arguments):
        import io
        output = io.BytesIO()
        with patch.object(m.sys, "stdout", types.SimpleNamespace(buffer=output)):
            code = m.main(arguments)
        value = json.loads(output.getvalue())
        self.assertEqual(code, value["wrapper_exit_code"])
        return value

    def _paths(self, m, selector):
        paths = {path for path, _ in MEMBERS[:6]} | {"bench/w40_native.py"}
        paths |= ({"tests/test_w40_native.py", ".github/workflows/test.yml"}
                  if selector == "native-all16" else {"tests/test_w40_native_clock.py"})
        return paths

    def _ids(self, raw):
        import ast
        found = []
        for node in ast.parse(raw).body:
            if isinstance(node, ast.ClassDef):
                found.extend(node.name + "." + item.name for item in node.body
                             if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"))
            elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                found.append(node.name)
        return sorted(found)

    def _observation(self, ids, exit_code):
        value = B12DispatchAcceptance.observation(self, ids, exit_code)
        if exit_code is None:
            value["outer_lifecycle"] = {"final_observed": False, "uncertain": True}
        return value

    def _metadata_run(self, m, selector, exit_code=0, transform=None, fault=None):
        execute = self._required(m, "maintained_test")
        original_validator = self._required(m, "validate_maintained_receipt")
        original_write = m._write_json
        seen, validators = [], []
        with tempfile.TemporaryDirectory(prefix="maintained-metadata-") as directory:
            scope = Path(directory) / "synthetic-scope"
            (scope / "operations").mkdir(parents=True)
            identity = "7" * 32
            operation = {"scope": scope, "path": scope / "operations" / identity, "id": identity}
            def begin(requested=None, **kwargs):
                requested = kwargs.pop("scope", requested)
                self.assertFalse(kwargs)
                self.assertEqual(Path(requested), scope)
                m.validation_admission(scope)
                operation["path"].mkdir()
                (operation["path"] / "state.json").write_bytes(encoded({"status": "running", "operation_id": identity}))
                return operation
            def child(view, runner, ids, seconds, actual_operation, selector=None):
                self.assertIs(actual_operation, operation)
                self.assertIsNone(selector, "maintained execution must run the complete original __main__")
                paths = sorted(p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_file() and p.name != ".git")
                seen.append({"runner": runner, "ids": list(ids), "seconds": seconds, "paths": paths})
                value = self._observation(ids, exit_code)
                value["runtime"].update(test_process_pid=740075, validation_operation_id=identity)
                if transform is not None:
                    transform(value)
                return value
            def validate(value):
                validators.append(value.get("operation"))
                if fault == "receipt_protocol":
                    raise m.VersionError("child_protocol_invalid")
                return original_validator(value)
            def write(path, value, **kwargs):
                if path.name == "receipt.json" and fault in {"receipt_publish", "marker_write"}:
                    raise m.VersionError("child_protocol_invalid")
                if path.name == "quarantine.json" and fault == "marker_write":
                    raise OSError("synthetic marker publication failure")
                return original_write(path, value, **kwargs)
            with patch.object(m, "begin_validation_operation", side_effect=begin), \
                    patch.object(m, "_launch_test_child", side_effect=child), \
                    patch.object(m, "validate_maintained_receipt", side_effect=validate), \
                    patch.object(m, "_write_json", side_effect=write):
                result = execute(CONTRACT, "git-lf", selector, scope=scope)
                admitted, admission_error = False, None
                try:
                    m.validation_admission(scope)
                    admitted = True
                except Exception as error:
                    admission_error = type(error).__name__
                state = json.loads((operation["path"] / "state.json").read_bytes())
                marker = scope / "quarantine.json"
                marker_before = marker.read_bytes() if marker.exists() else None
                if not admitted:
                    with self.assertRaises(m.VersionError):
                        m.validation_admission(scope)
                    self.assertEqual(marker.read_bytes() if marker.exists() else None, marker_before)
            return result, {"launches": seen, "validator_calls": validators, "admitted": admitted,
                            "admission_error": admission_error, "state": state,
                            "retained_source": (operation["path"] / "source/bench/w40_native.py").is_file()}

    def _legacy_metadata(self, m, child_exit=1):
        # Synthetic reader input only. This is never claimed as actual historical execution.
        registry = m.load_registry()
        paths = [r["path"] for r in registry["members"]]
        seal = m.sha(m.encoded(dict(zip(paths, registry["profiles"]["git-lf"]["raw_sha256"]))))
        ids = self._ids(m.read_objects(m.select(registry, CONTRACT, "git-lf"))["tests/test_w40_native.py"])
        value = m._receipt(None, "git-lf")
        value.update(operation="legacy-test", contract_id=CONTRACT, role="historical_v1", engine_source_commit=COMMIT,
            source_tree=TREE, selected_profile="git-lf", original_runner="tests/test_w40_native.py",
            command_argv=["python", "tools/engine_versions.py", "legacy-test", CONTRACT, "git-lf", "tests/test_w40_native.py"],
            invocation_status="failed", reason="test_interrupted", wrapper_exit_code=2, test_execution_qualified=False,
            descendant_observations_complete=False, descendant_observations=[{"command": None, "exit_code": None,
                "state": "not_recorded", "observation_source": "not_recorded"}], context_manifest_sha256=seal,
            source_fixture=m._layer("passed", evidence=[seal]),
            loaded_runtime=m._layer("passed", evidence=[m.sha(b"synthetic runtime reader metadata")]))
        value["legacy_tests"] = {"status": "failed", "child_exit_code": child_exit, "executed_test_ids": ids,
            "executed_test_ids_sha256": m.sha(m.encoded(ids)), "stdout_sha256": m.sha(b""),
            "stderr_sha256": m.sha(b"synthetic failure"), "dynamic_counters": None}
        return value

    def test_maintained_selectors_and_legacy_execution_eligibility(self):
        m = self.subject()
        with patch.object(m, "begin_validation_operation", side_effect=m.VersionError("validation_quarantined")), \
                patch.object(m, "validation_admission", side_effect=m.VersionError("validation_quarantined")), \
                patch.object(m, "_scope_path", side_effect=AssertionError("implicit scope forbidden")), \
                patch.object(m, "_launch_test_child", side_effect=AssertionError("child forbidden")):
            recognized = self._cli(m, ["maintained-test", CONTRACT, "git-lf", "native-all16"])
        self.assertEqual(recognized["operation"], "maintained-test")
        self.assertEqual(recognized["schema"], "engine-maintained-adapter-execution-v1")
        execute = self._required(m, "maintained_test")
        for contract, profile, selector in (("UNIT_UNKNOWN", "git-lf", "native-all16"),
                (CONTRACT, "UNIT_UNKNOWN", "native-all16"), (CONTRACT, "observed-windows-crlf", "native-all16"),
                (CONTRACT, "git-lf", "NativeAcceptance"), (CONTRACT, "git-lf", "../native-all16"),
                (CONTRACT, "git-lf", "native-all16 extra")):
            with self.subTest(selector=selector, profile=profile), \
                    patch.object(m, "begin_validation_operation", side_effect=AssertionError("invalid admission")) as admission, \
                    patch.object(m, "_scope_path", side_effect=AssertionError("implicit scope forbidden")):
                refused = execute(contract, profile, selector)
                self.assertNotEqual(refused["wrapper_exit_code"], 0)
                self.assertEqual(refused["maintained_tests"]["status"], "not_run")
                self.assertNotIn("UNIT_UNKNOWN", m.encoded(refused).decode())
                admission.assert_not_called()
        for runner in ("tests/test_w40_native.py", "tests/test_w40_native_clock.py"):
            with self.subTest(legacy=runner), \
                    patch.object(m, "begin_validation_operation", side_effect=m.VersionError("validation_quarantined")) as admission, \
                    patch.object(m, "_scope_path", side_effect=AssertionError("implicit scope forbidden")), \
                    patch.object(m, "_launch_test_child", side_effect=AssertionError("legacy child forbidden")) as child:
                for value in (m.legacy_test(CONTRACT, "git-lf", runner),
                              self._cli(m, ["legacy-test", CONTRACT, "git-lf", runner])):
                    self.assertEqual(value["reason"], "legacy_native_execution_unqualified")
                    self.assertEqual(value["wrapper_exit_code"], 2)
                    self.assertEqual(value["legacy_tests"]["status"], "not_run")
                admission.assert_not_called()
                child.assert_not_called()

    def test_native9_and_clock8_source_closure_and_actual_candidate_identity(self):
        m = self.subject()
        build = self._required(m, "maintained_context_sources")
        selected = m.select(m.load_registry(), CONTRACT, "git-lf")
        objects = m.read_objects(selected)
        head = m._git_bytes("rev-parse", "HEAD^{commit}").decode().strip()
        for selector, count in (("native-all16", 9), ("clock-all3", 8)):
            with self.subTest(selector=selector):
                bodies, identity = build(selected, objects, selector)
                self.assertEqual(set(bodies), self._paths(m, selector))
                self.assertEqual(len(bodies), count)
                fixed_paths = {path for path, _ in MEMBERS[:6]}
                for path in fixed_paths:
                    self.assertEqual(bodies[path], objects[path])
                support = ".github/workflows/test.yml" if selector == "native-all16" else "tests/test_w40_native_clock.py"
                self.assertEqual(bodies[support], objects[support])
                self.assertEqual(bodies["bench/w40_native.py"], m._git_bytes("cat-file", "blob", head + ":bench/w40_native.py"))
                current = identity["current_adapter_identity"]
                self.assertEqual(current["candidate_commit"], head)
                expected_current = {"bench/w40_native.py", "tests/test_w40_native.py"} if selector == "native-all16" else {"bench/w40_native.py"}
                self.assertEqual({r["path"] for r in current["members"]}, expected_current)
                self.assertEqual({r["path"] for r in identity["dependency_identity"]["members"]}, fixed_paths)
                self.assertEqual({r["path"] for r in identity["support_identity"]["members"]}, {support})
                for r in current["members"]:
                    physical = (ROOT / r["path"]).read_bytes()
                    self.assertEqual(r["raw_sha256"], m.sha(physical))
                    self.assertEqual(r["canonical_sha256"], m.sha(physical.replace(b"\r\n", b"\n")))
                    self.assertEqual(bodies[r["path"]], physical.replace(b"\r\n", b"\n"))
                with self.assertRaises(m.VersionError):
                    m._profile_bodies(selected, bodies)
        for fault in ("missing", "changed", "extra"):
            bad = dict(objects)
            if fault == "missing":
                bad.pop("src/risk.py")
            elif fault == "changed":
                bad["src/risk.py"] += b"\n# synthetic changed fixed dependency\n"
            else:
                bad["../extra.py"] = b"pass\n"
            with self.subTest(fault=fault), self.assertRaises(m.VersionError):
                build(selected, bad, "native-all16")
        with self.assertRaises(m.VersionError):
            build(m.select(m.load_registry(), CONTRACT, "observed-windows-crlf"), objects, "native-all16")
        original_metadata = m._metadata
        def alias(path):
            if path == ROOT / "bench/w40_native.py":
                return types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0x400)
            return original_metadata(path)
        with patch.object(m, "_metadata", side_effect=alias), self.assertRaises(m.VersionError):
            build(selected, objects, "native-all16")

    def test_maintained_original13_staging3_clock3_ids_and_real_exit_separation(self):
        m = self.subject()
        self._required(m, "maintained_test")
        def missing(value):
            value["executed_test_ids"].pop()
        def wrong_runtime(value):
            value["runtime"]["predicates"]["engine_bindings"] = False
        cases = (("native-all16", 0, None), ("clock-all3", 0, None), ("native-all16", 7, None),
                 ("clock-all3", 7, None), ("native-all16", -9, None), ("native-all16", None, None),
                 ("native-all16", 0, missing), ("native-all16", 0, wrong_runtime))
        for selector, exit_code, transform in cases:
            with self.subTest(selector=selector, exit=exit_code, fault=transform is not None):
                result, evidence = self._metadata_run(m, selector, exit_code, transform)
                self.assertEqual(len(evidence["launches"]), 1)
                actual = evidence["launches"][0]
                runner = "tests/test_w40_native.py" if selector == "native-all16" else "tests/test_w40_native_clock.py"
                expected = self._ids((ROOT / runner).read_bytes())
                self.assertEqual(actual["ids"], expected)
                self.assertEqual(len(actual["ids"]), 16 if selector == "native-all16" else 3)
                self.assertEqual(actual["runner"], runner)
                self.assertEqual(actual["seconds"], 900 if selector == "native-all16" else 180)
                self.assertEqual(set(actual["paths"]), self._paths(m, selector))
                self.assertEqual(result["maintained_tests"]["child_exit_code"], exit_code)
                qualified = exit_code == 0 and transform is None
                self.assertIs(result["test_execution_qualified"], qualified)
                self.assertEqual(result["maintained_tests"]["status"], "passed" if qualified else "failed")
                self.assertEqual(result["wrapper_exit_code"] == 0, qualified)
                if exit_code == 7:
                    self.assertEqual(result["wrapper_exit_code"], 7)
                self.assertFalse(result["descendant_observations_complete"])
                self.assertIsNone(result["descendant_observations"][-1]["exit_code"])
                if exit_code is None:
                    self.assertFalse(evidence["admitted"])

    def test_maintained_receipts_cannot_qualify_historical_or_production_domains(self):
        m = self.subject()
        validate = self._required(m, "validate_maintained_receipt")
        for selector in ("native-all16", "clock-all3"):
            good, _ = self._metadata_run(m, selector)
            self.assertIs(validate(good), good)
            self.assertEqual(good["schema"], "engine-maintained-adapter-execution-v1")
            self.assertEqual(good["domain"], "maintained_adapter_on_fixed_v1_dependencies")
            self.assertNotIn("source_fixture", good)
            self.assertEqual(good["context_source"]["status"], "passed")
            self.assertEqual(good["maintained_loaded_runtime"]["status"], "passed")
            for field in ("historical_execution_qualified", "current_production_behavior_qualified",
                          "original_v1_fixture_qualified_by_maintained_result"):
                self.assertIs(good[field], False)
                bad = copy.deepcopy(good)
                bad[field] = True
                with self.subTest(field=field), self.assertRaises(m.VersionError):
                    validate(bad)
            for field, value in (("domain", "historical_v1"), ("role", "production_v2"),
                    ("v2_historical_native_positive_compatibility", "supported"), ("wrapper_exit_code", True),
                    ("context_manifest_sha256", "0" * 64), ("unexpected", "UNIT_UNKNOWN")):
                bad = copy.deepcopy(good)
                bad[field] = value
                with self.subTest(field=field), self.assertRaises(m.VersionError):
                    validate(bad)
            for identity in ("dependency_identity", "support_identity", "current_adapter_identity"):
                bad = copy.deepcopy(good)
                bad[identity]["members"].append(copy.deepcopy(bad[identity]["members"][0]))
                with self.subTest(duplicate=identity), self.assertRaises(m.VersionError):
                    validate(bad)
            for fault in ("missing_id", "self_hashed_ids", "boolean_exit", "copied_runtime"):
                bad = copy.deepcopy(good)
                if fault in {"missing_id", "self_hashed_ids"}:
                    ids = bad["maintained_tests"]["executed_test_ids"]
                    ids.pop() if fault == "missing_id" else ids.__setitem__(0, "arbitrary.test")
                    bad["maintained_tests"]["executed_test_ids_sha256"] = m.sha(m.encoded(ids))
                elif fault == "boolean_exit":
                    bad["maintained_tests"]["child_exit_code"] = True
                else:
                    bad["maintained_loaded_runtime"] = copy.deepcopy(bad["context_source"])
                with self.subTest(fault=fault), self.assertRaises(m.VersionError):
                    validate(bad)
            for operation, schema, domain in (("legacy-test", "engine-version-qualification-v1", "historical_v1"),
                    ("adapter-test", "engine-adapter-regression-v1", "current_adapter_on_v1_dependencies")):
                bad = self._legacy_metadata(m, 0)
                bad.update(operation=operation, schema=schema, domain=domain)
                bad.update(invocation_status="completed", reason=None, wrapper_exit_code=0, test_execution_qualified=True)
                bad["source_fixture"] = copy.deepcopy(good["context_source"])
                bad["loaded_runtime"] = copy.deepcopy(good["maintained_loaded_runtime"])
                bad["context_manifest_sha256"] = good["context_manifest_sha256"]
                bad["direct_observations_evidence_sha256"] = m.sha(m.encoded(good["descendant_observations"]))
                if operation == "legacy-test":
                    bad.pop("domain")
                    runner = "tests/test_w40_native.py" if selector == "native-all16" else "tests/test_w40_native_clock.py"
                    bad["original_runner"] = runner
                    bad["command_argv"] = ["python", "tools/engine_versions.py", operation, CONTRACT, "git-lf", runner]
                    bad["legacy_tests"] = copy.deepcopy(good["maintained_tests"])
                else:
                    bad.update(role=domain, original_runner=None,
                        original_v1_fixture_qualified_by_adapter_result=False, current_production_behavior_qualified=False)
                    bad["command_argv"] = ["python", "tools/engine_versions.py", operation, CONTRACT, "git-lf", "InterruptedProgressStagingTests"]
                    bad["legacy_tests"] = m._receipt(None, None)["legacy_tests"]
                    bad["adapter_tests"] = copy.deepcopy(good["maintained_tests"])
                    bad["dependency_identity"] = copy.deepcopy(good["dependency_identity"])
                    bad["current_adapter_identity"] = copy.deepcopy(good["current_adapter_identity"])
                with self.subTest(relabel=operation), self.assertRaises(m.VersionError):
                    m.validate_dispatch_receipt(bad)
                with self.assertRaises(m.VersionError):
                    validate(bad)

    def test_historical_workflow_fixture_cannot_qualify_current47_dispatch(self):
        m = self.subject()
        old = m._git_bytes("cat-file", "blob", "bb6e1b2cc5e602e94f0560c37dbc3bd79674edab:.github/workflows/test.yml").decode()
        pending = m.workflow_dispatch_contract(old)
        self.assertEqual(pending["status"], "registration_pending")
        replacements = (
            ("legacy-test " + CONTRACT + " git-lf tests/test_w40_native.py", "maintained-test " + CONTRACT + " git-lf native-all16"),
            ("adapter-test " + CONTRACT + " git-lf InterruptedProgressStagingTests", "verify-source " + CONTRACT + " git-lf"),
            ("legacy-test " + CONTRACT + " git-lf tests/test_w40_native_clock.py", "maintained-test " + CONTRACT + " git-lf clock-all3"))
        current = old
        for before, after in replacements:
            self.assertEqual(current.count(before), 1)
            current = current.replace(before, after, 1)
        registered = m.workflow_dispatch_contract(current)
        self.assertEqual(registered["status"], "registered")
        self.assertEqual(registered["actual_count"], 47)
        self.assertEqual(sum(a == b for a, b in zip(pending["commands"], registered["commands"])), 44)
        historical = m._git_bytes("cat-file", "blob", COMMIT + ":.github/workflows/test.yml").decode()
        self.assertNotEqual(m.workflow_dispatch_contract(historical)["status"], "registered")
        command = "python tools/engine_versions.py maintained-test " + CONTRACT + " git-lf native-all16"
        for bad in (current.replace("run: " + command, "# run: " + command, 1),
                    current.replace(command, "python -c pass", 1), current.replace(command, command + " extra", 1),
                    current.replace("python tests/test_backfill.py --offline", "python tests/test_backfill.py", 1)):
            self.assertEqual(m.workflow_dispatch_contract(bad)["status"], "invalid")

    def test_maintained_failure_and_quarantine_admission_remain_closed(self):
        m = self.subject()
        self._required(m, "maintained_test")
        for fault in ("uncertain", "receipt_protocol", "receipt_publish", "marker_write"):
            with self.subTest(fault=fault):
                result, evidence = self._metadata_run(m, "native-all16", None if fault == "uncertain" else 0,
                                                      fault=None if fault == "uncertain" else fault)
                self.assertEqual(len(evidence["launches"]), 1)
                self.assertTrue(evidence["retained_source"])
                self.assertFalse(result["test_execution_qualified"])
                self.assertNotEqual(result["wrapper_exit_code"], 0)
                self.assertEqual(result["maintained_tests"]["child_exit_code"], None if fault == "uncertain" else 0)
                self.assertFalse(evidence["admitted"])
                self.assertEqual(evidence["admission_error"], "VersionError")
                self.assertNotEqual(evidence["state"]["status"], "finished")
                if fault == "receipt_protocol":
                    self.assertTrue(evidence["validator_calls"], "the actual unique maintained guard was not intercepted")

    def test_legacy_receipt_reader_preserves_failed_and_unknown_states(self):
        m = self.subject()
        for child_exit in (1, 0, None):
            value = self._legacy_metadata(m, child_exit)
            for name, status, reason in (("historical_record_tuple", "unknown", "historical_record_unknown"),
                    ("historical_interpreter", "unavailable", "historical_interpreter_unavailable")):
                value[name] = m._layer(status, reason)
            before = m.encoded(value)
            self.assertIs(m.validate_dispatch_receipt(value), value)
            self.assertEqual(m.encoded(value), before)
            self.assertEqual(value["legacy_tests"]["status"], "failed")
            self.assertEqual(value["legacy_tests"]["child_exit_code"], child_exit)
            self.assertIs(value["test_execution_qualified"], False)
            self.assertIs(value["historical_execution_qualified"], False)
            promoted = copy.deepcopy(value)
            promoted["historical_execution_qualified"] = True
            with self.assertRaises(m.VersionError):
                m.validate_dispatch_receipt(promoted)
        with patch.object(m, "begin_validation_operation", side_effect=m.VersionError("validation_quarantined")) as admission, \
                patch.object(m, "_scope_path", side_effect=AssertionError("implicit scope forbidden")), \
                patch.object(m, "_launch_test_child", side_effect=AssertionError("reader reopened legacy execution")):
            refused = m.legacy_test(CONTRACT, "git-lf", "tests/test_w40_native.py")
            self.assertEqual(refused["reason"], "legacy_native_execution_unqualified")
            admission.assert_not_called()
        validate = self._required(m, "validate_maintained_receipt")
        with self.assertRaises(m.VersionError):
            validate(self._legacy_metadata(m))


if __name__ == "__main__":
    unittest.main(verbosity=2)
