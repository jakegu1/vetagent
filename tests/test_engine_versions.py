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
            seen = []
            def child(view, runner, ids, seconds, operation, selector=None):
                seen.append((runner, list(ids), seconds, selector))
                return self.observation(ids)
            with patch.object(m, "_launch_test_child", side_effect=child):
                for runner, count, seconds in (("tests/test_w40_native.py", 13, 900),
                                               ("tests/test_w40_native_clock.py", 3, 180)):
                    completed = m.legacy_test(CONTRACT, "git-lf", runner, scope=scope)
                    self.assertEqual(completed["wrapper_exit_code"], 0)
                    self.assertEqual(len(seen[-1][1]), count)
                    self.assertEqual(seen[-1][2:], (seconds, None))
                    self.assertEqual(completed["original_runner"], runner)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
