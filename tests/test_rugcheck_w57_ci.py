"""T-043: a finite, explicitly started study survives CI jobs without inventing evidence.

Run: python tests/test_rugcheck_w57_ci.py
All vendor, Artifact and clock interfaces are synthetic.
"""
import contextlib
import copy
import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
import rugcheck_coverage_probe as probe

DRIVER = ROOT / "bench/rugcheck_w57_ci.py"
driver = None
if DRIVER.exists():
    spec = importlib.util.spec_from_file_location("w57_ci", DRIVER)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)

EPOCH = datetime.datetime(2026, 10, 20, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def stamp(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


def mint(index):
    return "A" * 30 + ALPHABET[index // len(ALPHABET)] + ALPHABET[index % len(ALPHABET)]


def context(run=1):
    return {"repository": "synthetic/study", "workflow": ".github/workflows/rugcheck-w57.yml",
            "branch": "master", "default_branch": "master", "run_id": run,
            "head": "a" * 40, "source": {"driver": "b" * 64, "probe": "c" * 64, "workflow": "d" * 64}}


class Clock:
    def __init__(self, value=EPOCH):
        self.value = value

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class MemoryArtifacts:
    def __init__(self, expected=None):
        self.expected = expected or context()
        self.items = {}
        self.reads = []
        self.fail_upload = False

    def list(self):
        return [copy.deepcopy(x[0]) for x in self.items.values()]

    def load(self, ident):
        self.reads.append(ident)
        meta, data = self.items[ident]
        if meta.get("expired"):
            raise driver.StudyError("artifact_unavailable")
        return driver.decode_bundle(data, meta["provenance"], self.expected)

    def publish(self, state, rows, kind, ctx):
        if self.fail_upload:
            raise driver.StudyError("upload_failed")
        ident = max(self.items, default=0) + 1
        data = driver.bundle_bytes(state, rows, kind, ctx)
        meta = {"id": ident, "name": driver.artifact_name(state, kind, ctx),
                "expired": False, "provenance": copy.deepcopy(ctx)}
        self.items[ident] = (meta, data)
        return ident


class StudyTests(unittest.TestCase):
    def need(self):
        self.assertIsNotNone(driver, "the durable W57 driver is not implemented")

    def vendor(self, clock, ages=None, scores=None, count=60, failures=None):
        ages, scores, failures = ages or {}, scores or {}, failures or {}
        candidates = [mint(i) for i in range(count)]
        calls = []

        def fetch(url):
            calls.append(url)
            if "geckoterminal" in url:
                page = int(url.rsplit("page=", 1)[-1])
                rows = [{"relationships": {"base_token": {"data": {"id": "solana_" + m}}}}
                        for m in candidates[(page - 1) * 30:page * 30]]
                return "200", {"data": rows}
            m = url.split("/tokens/", 1)[1].split("/", 1)[0]
            if m in failures:
                return failures[m]
            age = ages.get(m, 1)
            detected = None if age is None else stamp(clock() - age * 60)
            return "200", {"score_normalised": scores.get(m, 1), "detectedAt": detected,
                           "topHolders": [], "totalHolders": 0, "token_extensions": {}}
        return fetch, calls

    def job(self, phase, store, clock, ctx=None, study="study-one", pilot=None):
        ctx = ctx or context(len(store.items) + 1)
        plan = driver.prepare(phase, store, ctx, clock(), study=study, pilot_id=pilot)
        if plan["action"] == "idle":
            return None, [], plan
        if plan["action"] == "checkpoint":
            state, rows = plan["state"], []
        else:
            receipt = store.publish(plan["state"], [], "intent", ctx)
            state, rows = driver.collect(plan, receipt, store, ctx, clock, clock.sleep)
        result = store.publish(state, rows, "result", ctx)
        return result, rows, dict(plan, result_state=state)

    def active(self, clock=None, count=60, ages=None):
        clock = clock or Clock()
        store = MemoryArtifacts()
        fetch, calls = self.vendor(clock, ages=ages, count=count)
        with patch.object(probe, "curl", side_effect=fetch):
            pilot, _, _ = self.job("pilot", store, clock, context(1), "pilot-one")
            result, rows, plan = self.job("start", store, clock, context(2), "study-one", pilot)
        return clock, store, result, rows, plan, calls

    def test_existing_probe_bands_offsets_and_historical_reference_are_characterized(self):
        self.assertEqual([probe.band(x) for x in (0, 19, 20, 49, 50)],
                         ["ok", "ok", "warn", "warn", "critical"])
        self.assertIsNone(probe.band(True))
        now = datetime.datetime.fromtimestamp(EPOCH, datetime.timezone.utc)
        self.assertEqual(probe.age_minutes("2026-10-19T19:55:00-04:00", now), 5)
        self.assertEqual(hashlib.sha256((ROOT / "bench/rugcheck_scores_rerun.jsonl").read_bytes()
                                       .replace(b"\r\n", b"\n")).hexdigest(),
                         "4afc84daa5bd6fd930fcfcf464f18a806f506a55be32a11fd58779f10c17c961")

    def test_default_cli_is_offline_and_limits_match_the_adopted_experiment(self):
        self.need()
        with patch.object(probe, "curl", side_effect=AssertionError("vendor call")), \
                patch.object(driver, "GitHubArtifacts", side_effect=AssertionError("Artifact call")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(driver.main([]), 0)
        self.assertIn("pilot", output.getvalue())
        self.assertEqual((driver.FRESH_MIN, driver.FRESH_TARGET, driver.MAX_AGE_MIN), (40, 45, 10))
        self.assertEqual((driver.DURATION, driver.INTERVAL, driver.LAST_SLOT), (48 * 3600, 15 * 60, 192))
        self.assertEqual(driver.MAX_VENDOR_CALLS, 12414)

    def test_missing_state_is_idle_and_bad_or_expired_state_never_recruits(self):
        self.need()
        clock, store = Clock(), MemoryArtifacts()
        with patch.object(probe, "curl", side_effect=AssertionError("vendor call")):
            self.assertEqual(driver.prepare("tick", store, context(), clock())["action"], "idle")
        clock, store, ident, _, _, _ = self.active()
        for field, value in (("expired", True),):
            changed = copy.deepcopy(store)
            changed.items[ident][0][field] = value
            with patch.object(probe, "curl", side_effect=AssertionError("vendor call")):
                with self.assertRaises(driver.StudyError):
                    driver.prepare("tick", changed, context(8), clock(), study="study-one")
        for field, value in (("repository", "foreign/project"), ("workflow", "other.yml"),
                             ("branch", "pull-request")):
            changed = copy.deepcopy(store)
            changed.items[ident][0]["provenance"][field] = value
            with self.assertRaises(driver.StudyError):
                driver.prepare("tick", changed, context(8), clock(), study="study-one")
        changed = copy.deepcopy(store)
        changed.items[ident] = (changed.items[ident][0], b"not a zip")
        with self.assertRaises(driver.StudyError):
            driver.prepare("tick", changed, context(8), clock(), study="study-one")

    def test_pilot_uses_one_listing_and_exactly_six_existing_controls(self):
        self.need()
        clock, store = Clock(), MemoryArtifacts()
        fetch, calls = self.vendor(clock)
        with patch.object(probe, "curl", side_effect=fetch):
            ident, rows, plan = self.job("pilot", store, clock, context(1), "pilot-one")
        self.assertEqual(plan["result_state"]["status"], "pilot_passed")
        self.assertEqual(len(calls), 7)
        self.assertEqual([r["mint"] for r in rows if r["kind"] == "report"], [m for _, m in probe.MAJORS[:6]])
        self.assertEqual(store.load(ident)["state"]["requests"], {"rugcheck": 6, "gecko": 1})
        bad = {probe.MAJORS[2][1]: ("429", {"score_normalised": 1, "detectedAt": stamp(EPOCH)})}
        fetch, calls = self.vendor(clock, failures=bad)
        store = MemoryArtifacts()
        with patch.object(probe, "curl", side_effect=fetch):
            _, rows, plan = self.job("pilot", store, clock, context(2), "pilot-two")
        self.assertEqual(plan["result_state"]["status"], "pilot_failed")
        self.assertEqual(len(calls), 7)
        refused = next(r for r in rows if r.get("mint") == probe.MAJORS[2][1])
        self.assertEqual((refused["http"], refused["body"]), ("429", "unavailable"))
        self.assertIsNone(refused["score_normalised"])

    def test_start_requires_prior_successful_pilot_and_refuses_duplicate_or_active_study(self):
        self.need()
        clock, store = Clock(), MemoryArtifacts()
        with self.assertRaises(driver.StudyError):
            driver.prepare("start", store, context(), clock(), study="new", pilot_id=None)
        clock, store, ident, _, plan, _ = self.active(clock)
        with patch.object(probe, "curl", side_effect=AssertionError("vendor call")):
            for study in ("study-one", "another-study"):
                with self.assertRaises(driver.StudyError):
                    driver.prepare("start", store, context(9), clock(), study=study, pilot_id=2)
        changed_ctx = context(10)
        changed_ctx["source"]["probe"] = "e" * 64
        before = {i: b for i, (_, b) in store.items.items()}
        changed = driver.prepare("tick", store, changed_ctx, clock(), study="study-one")
        self.assertEqual((changed["action"], changed["state"]["status"]), ("checkpoint", "source_changed"))
        self.assertEqual(before, {i: b for i, (_, b) in store.items.items()})

    def test_enrollment_uses_its_own_closed_index_age_and_keeps_original_response(self):
        self.need()
        ages = {mint(0): -0.01, mint(1): 10.01, mint(2): None, mint(3): 0, mint(4): 10}
        clock, store, ident, rows, plan, _ = self.active(ages=ages)
        state = plan["result_state"]
        fresh = [m for m in state["cohort"] if m["group"] == "fresh"]
        self.assertEqual(len(fresh), 45)
        self.assertEqual(len([m for m in state["cohort"] if m["group"] == "control"]), 18)
        self.assertFalse({mint(0), mint(1), mint(2)} & {m["mint"] for m in fresh})
        self.assertTrue({mint(3), mint(4)} <= {m["mint"] for m in fresh})
        self.assertEqual(next(m for m in fresh if m["mint"] == mint(4))["enrollment"]["age_minutes"], 10)
        self.assertGreaterEqual(len(rows), 48)
        self.assertTrue(all("http" in r and "ts" in r for r in rows))
        clock.sleep(7200)
        restored = store.load(ident)["state"]
        self.assertEqual(restored["cohort"], state["cohort"])
        self.assertEqual(driver.readout(restored, rows)["fresh_enrolled"], 45)

    def test_underpowered_or_bounded_recruitment_stops_without_starting_a_clock(self):
        self.need()
        _, _, _, _, plan, _ = self.active(count=39)
        self.assertEqual(plan["result_state"]["status"], "insufficient_cohort")
        self.assertIsNone(plan["result_state"]["started_at"])
        ages = {mint(i): 20 for i in range(240)}
        _, _, _, rows, plan, calls = self.active(count=240, ages=ages)
        self.assertEqual(plan["result_state"]["status"], "insufficient_cohort")
        self.assertLessEqual(plan["result_state"]["requests"]["gecko"], 8)
        self.assertLessEqual(plan["result_state"]["requests"]["rugcheck"], 240)
        self.assertEqual(len([r for r in rows if r["kind"] == "report"]), 240)

    def test_slots_use_wall_time_skip_gaps_and_do_not_recruit_again(self):
        self.need()
        clock, store, _, _, plan, _ = self.active()
        started = plan["result_state"]["started_at"]
        fetch, calls = self.vendor(clock)
        with patch.object(probe, "curl", side_effect=fetch):
            _, rows, first = self.job("tick", store, clock, context(5))
            self.assertEqual(first["state"]["slot"], 0)
            _, _, duplicate = self.job("tick", store, clock, context(6))
            self.assertEqual(duplicate["action"], "idle")
            clock.value = started + 3 * 900 + 10
            _, rows, later = self.job("tick", store, clock, context(7))
        state = later["result_state"]
        self.assertEqual((state["started_at"], state["ends_at"]), (started, started + 48 * 3600))
        self.assertEqual([s["slot"] for s in state["slots"] if s["status"] == "not_observed"], [1, 2])
        self.assertEqual(len(rows), 63)
        self.assertTrue(all(r["slot"] == 3 and r["ts"] >= started + 3 * 900 for r in rows))
        self.assertTrue(all("rugcheck" in url for url in calls))

    def test_terminal_deadline_and_remaining_timeout_bound_calls_and_preserve_partial_rows(self):
        self.need()
        clock, store, _, _, plan, _ = self.active()
        end = plan["result_state"]["ends_at"]
        clock.value = end + 900 - 31
        with patch.object(probe, "curl", side_effect=AssertionError("past deadline call")):
            _, rows, stopped = self.job("tick", store, clock, context(8))
        self.assertEqual(stopped["result_state"]["status"], "completed")
        self.assertTrue(all(r["body"] == "not_observed" for r in rows))
        clock.value = end + 901
        with patch.object(probe, "curl", side_effect=AssertionError("terminal call")):
            self.assertEqual(driver.prepare("tick", store, context(9), clock(), study="study-one")["action"], "idle")
        clock, store, _, _, _plan, _ = self.active()
        fetch, calls = self.vendor(clock)
        def slow(url):
            value = fetch(url)
            clock.sleep(175)
            return value
        with patch.object(probe, "curl", side_effect=slow):
            _, rows, partial = self.job("tick", store, clock, context(10))
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(rows), 63)
        self.assertEqual(sum(r["body"] == "not_observed" for r in rows), 61)

    def test_real_observe_persist_restore_readout_keeps_failed_fields_out_of_votes(self):
        self.need()
        clock, store, _, enrollment, plan, _ = self.active()
        started = plan["result_state"]["started_at"]
        originals = {i: data for i, (_, data) in store.items.items()}
        fetch, _ = self.vendor(clock, scores={mint(1): True}, failures={mint(0): ("503", {"score_normalised": 1})})
        with patch.object(probe, "curl", side_effect=fetch):
            _, early, _ = self.job("tick", store, clock, context(5))
        self.assertEqual(next(r for r in early if r["mint"] == mint(0))["body"], "unavailable")
        self.assertIsNone(next(r for r in early if r["mint"] == mint(1))["score_normalised"])
        clock.value = started + 900
        fetch, _ = self.vendor(clock, scores={mint(0): 80, mint(2): 80})
        with patch.object(probe, "curl", side_effect=fetch):
            latest, later, _ = self.job("tick", store, clock, context(6))
        restored = store.load(latest)["state"]
        readout = driver.readout(restored, enrollment + early + later)
        self.assertEqual([e["mint"] for e in readout["events"]], [mint(2)])
        self.assertGreater(readout["unavailable_score_cells"], 0)
        self.assertEqual(readout["fresh_enrolled"], 45)
        for ident, data in originals.items():
            self.assertEqual(store.items[ident][1], data)
        combined = driver.reconstruct(store, context(7), "study-one")
        self.assertEqual(combined["events"], readout["events"])

    def test_intent_upload_failure_or_lost_result_cannot_replay_vendor_calls(self):
        self.need()
        clock, store, _, _, _, _ = self.active()
        plan = driver.prepare("tick", store, context(5), clock(), study="study-one")
        store.fail_upload = True
        with patch.object(probe, "curl", side_effect=AssertionError("vendor call")):
            with self.assertRaises(driver.StudyError):
                store.publish(plan["state"], [], "intent", context(5))
            with self.assertRaises(driver.StudyError):
                driver.collect(plan, 99999, store, context(5), clock, clock.sleep)
        store.fail_upload = False
        store.publish(plan["state"], [], "intent", context(5))
        lost = driver.prepare("tick", store, context(6), clock(), study="study-one")
        self.assertEqual((lost["action"], lost["state"]["status"]), ("checkpoint", "lost_checkpoint"))
        self.assertIn("not_observed", [s["status"] for s in lost["state"]["slots"]])

    def test_bundle_validation_rejects_corruption_unsafe_paths_and_wrong_provenance(self):
        self.need()
        clock, store, ident, _, _, _ = self.active()
        meta, data = store.items[ident]
        decoded = store.load(ident)
        self.assertLessEqual(len(data), 1024 * 1024)
        self.assertEqual(decoded["manifest"]["schema"], 1)
        self.assertEqual(set(zipfile.ZipFile(io.BytesIO(data)).namelist()),
                         {"state.json", "manifest.json", "observations.jsonl"})
        self.assertEqual(decoded["digest"], hashlib.sha256(json.dumps(decoded["manifest"], sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()).hexdigest())
        for change in ("hash", "schema", "path", "duplicate", "size"):
            source = zipfile.ZipFile(io.BytesIO(data))
            members = {name: source.read(name) for name in source.namelist()}
            if change == "hash":
                members["observations.jsonl"] += b"{}\n"
            elif change == "schema":
                value = json.loads(members["manifest.json"])
                value["schema"] = 99
                members["manifest.json"] = json.dumps(value).encode()
            elif change == "path":
                members["../escape"] = b"no"
            elif change == "size":
                members["observations.jsonl"] = b"x" * (1024 * 1024 + 1)
            target = io.BytesIO()
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, value in members.items():
                    archive.writestr(name, value)
                if change == "duplicate":
                    archive.writestr("state.json", members["state.json"])
            with self.subTest(change=change), self.assertRaises(driver.StudyError):
                driver.decode_bundle(target.getvalue(), meta["provenance"], context(9))
        for key, value in (("repository", "wrong/repo"), ("workflow", "wrong.yml"), ("branch", "feature")):
            bad = copy.deepcopy(meta["provenance"])
            bad[key] = value
            with self.assertRaises(driver.StudyError):
                driver.decode_bundle(data, bad, context(9))

    def test_github_adapter_bounds_metadata_downloads_and_masks_transport_exceptions(self):
        self.need()
        artifact = driver.GitHubArtifacts(context(), "synthetic-token")
        with patch.object(artifact, "request", return_value={"artifacts": [{"name": "other"}] * 100}) as request:
            with self.assertRaises(driver.StudyError):
                artifact.list()
            self.assertEqual(request.call_count, 5)
        artifact.downloads = 2
        with patch.object(artifact, "request", side_effect=AssertionError("third download")):
            with self.assertRaises(driver.StudyError):
                artifact.load(123)
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(driver, "GitHubArtifacts", side_effect=driver.StudyError("transport_unavailable")), \
                contextlib.redirect_stdout(output):
            self.assertEqual(driver.main(["prepare", "--phase", "tick", "--out", directory]), 1)
        self.assertNotIn("synthetic-token", output.getvalue())
        self.assertNotIn("http", output.getvalue())

    def test_readout_uses_fixed_time_final_tenth_and_marks_late_or_missing_samples_censored(self):
        self.need()
        clock, store, ident, enrollment, plan, _ = self.active()
        state = store.load(ident)["state"]
        start = state["started_at"]
        m = next(x["mint"] for x in state["cohort"] if x["group"] == "fresh")
        def observed(slot, elapsed, score, body="ok", http="200"):
            return {"kind": "report", "study": state["study"], "phase": "tick", "slot": slot,
                    "sweep": slot + 1, "mint": m, "label": "fresh-0", "attempt": 0,
                    "http": http, "body": body, "ts": start + elapsed,
                    "score_normalised": score, "detectedAt": stamp(start - 60), "gated": {}}
        early = observed(1, 900, 1)
        late = observed(175, 44 * 3600, 80)
        answer = driver.readout(state, enrollment + [early, late])
        self.assertEqual(answer["proposal"], "inconclusive")
        self.assertTrue(answer["censored"])
        self.assertEqual(answer["events"][0]["interval_start"], early["ts"])
        self.assertEqual(answer["events"][0]["interval_end"], late["ts"])
        self.assertEqual(answer["final_tenth_start"], start + 48 * 3600 * 0.9)
        outside = observed(192, 48 * 3600 + 10, 80)
        answer = driver.readout(state, enrollment + [early, outside])
        self.assertEqual(answer["proposal"], "inconclusive")
        self.assertEqual(answer["events"], [])
        self.assertEqual(answer["outside_window_observations"], 1)
        answer = driver.readout(state, enrollment + [early, observed(2, 1800, 1, "unavailable", "429")])
        self.assertEqual(answer["proposal"], "inconclusive")
        self.assertFalse(answer["negative_tail_established"])

    def test_workflow_is_independent_read_only_pinned_and_preserves_before_failure(self):
        text = (ROOT / ".github/workflows/rugcheck-w57.yml").read_text(encoding="utf-8") if (ROOT / ".github/workflows/rugcheck-w57.yml").exists() else ""
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn("contents: read", text)
        self.assertIn("actions: read", text)
        self.assertNotIn(": write", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("ubuntu-24.04", text)
        self.assertIn("retention-days: 7", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("actions/download-artifact", text)
        self.assertNotIn("secrets.", text.replace("secrets.GITHUB_TOKEN", ""))
        self.assertLess(text.index("id: intent"), text.index("id: collect"))
        self.assertIn("steps.intent.outputs.artifact-id", text)
        self.assertIn("always()", text[text.index("id: collect"):])
        self.assertIn("test_rugcheck_w57_ci.py", (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8"))

    def test_readout_discloses_groups_field_denominators_and_unattempted_gaps(self):
        self.need()
        clock, store, _, _, initial, _ = self.active()
        start = initial["result_state"]["started_at"]
        old = {i: data for i, (_, data) in store.items.items()}
        service = type("ArtifactService", (), {})()
        service.list, service.load = store.list, store.load
        service.reads = service.downloads = 0
        def publish(folder, kind, ctx):
            state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
            target = io.BytesIO()
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(folder.iterdir()):
                    archive.writestr(path.name, path.read_bytes())
            ident = max(store.items, default=0) + 1
            store.items[ident] = ({"id": ident, "name": driver.artifact_name(state, kind, ctx),
                                  "expired": False, "provenance": copy.deepcopy(ctx)}, target.getvalue())
            return ident
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            def cli(args, ctx):
                with patch.object(driver, "_context_env", return_value=ctx), \
                        patch.object(driver, "GitHubArtifacts", return_value=service), \
                        patch.object(driver.time, "time", side_effect=clock), \
                        patch.object(driver.collect, "__defaults__", (clock, clock.sleep, None)), \
                        contextlib.redirect_stdout(io.StringIO()):
                    return driver.main(args)
            def tick(run, elapsed, slow=False):
                clock.value = start + elapsed
                ctx, folder = context(run), base / str(run)
                failures = {m: ("503", {"score_normalised": 1}) for _, m in probe.MAJORS}
                fetch, _ = self.vendor(clock, failures=failures)
                def raw(url):
                    result = fetch(url)
                    if "rugcheck" in url:
                        if slow:
                            clock.sleep(30)
                        if result[0] == "200":
                            result[1]["token_extensions"] = {"permanentDelegate": False,
                                "pausableConfig": "false", "mintCloseAuthority": True}
                            result[1]["freezeAuthority"] = result[1]["mintAuthority"] = False
                            m = url.split("/tokens/", 1)[1].split("/", 1)[0]
                            if m in (mint(0), mint(1)):
                                result[1]["totalHolders"] = -3 if m == mint(0) else float("nan")
                    return result
                with patch.object(probe, "curl", side_effect=raw):
                    self.assertEqual(cli(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(folder)], ctx), 0)
                    intent = publish(folder / "intent", "intent", ctx)
                    self.assertEqual(cli(["collect", "--out", str(folder), "--intent", str(intent)], ctx), 0)
                return publish(folder / "result", "result", ctx)
            tick(5, 0)
            tick(6, 3 * 900)
            latest = tick(7, 4 * 900, slow=True)
            report_dir = base / "report"
            self.assertEqual(cli(["prepare", "--phase", "report", "--study", "study-one", "--out", str(report_dir)], context(8)), 0)
            answer = json.loads((report_dir / "result/report.json").read_text(encoding="utf-8"))
        fresh, control = answer["coverage"]["fresh"], answer["coverage"]["control"]
        self.assertEqual((fresh["population"], control["population"]), (45, 18))
        self.assertEqual(fresh["scheduled_slots"], 193)
        self.assertEqual((fresh["slots"]["4"]["attempted_cells"], fresh["slots"]["4"]["never_attempted_cells"]), (11, 34))
        self.assertEqual(control["slots"]["4"]["never_attempted_cells"], 18)
        self.assertEqual(control["fields"]["score_normalised"]["attempted_unavailable_or_invalid"], 36)
        self.assertEqual(fresh["fields"]["score_normalised"]["attempted_unavailable_or_invalid"], 0)
        self.assertEqual(answer["unavailable_score_cells"], 0)
        self.assertEqual(answer["not_observed_score_cells"], 45 * 193 - 101)
        self.assertEqual(fresh["fields"]["totalHolders"]["attempted_unavailable_or_invalid"], 6)
        self.assertEqual(fresh["fields"]["permanentDelegate"]["usable"], 101)
        self.assertEqual(fresh["fields"]["pausableConfig"]["usable"], 0)
        self.assertEqual(fresh["fields"]["pausableConfig"]["attempted_unavailable_or_invalid"], 101)
        self.assertEqual(fresh["fields"]["mintCloseAuthority"]["usable"], 101)
        self.assertEqual(fresh["fields"]["freeze_or_mint"]["usable"], 101)
        self.assertEqual(fresh["fields"]["detectedAt"]["usable"], 101)
        self.assertEqual(fresh["fields"]["topHolders_n"]["usable"], 101)
        self.assertEqual(answer["missing_slot_intervals"][0]["slots"], [1, 2])
        self.assertEqual([r["slot"] for r in fresh["observation_intervals"]], [0, 3, 4])
        rows = store.load(latest)["rows"]
        first = next(r for r in rows if r.get("mint") == mint(0))
        self.assertIsNone(first["totalHolders"])
        self.assertIsNone(first["gated"]["pausableConfig"])
        self.assertIs(first["gated"]["permanentDelegate"], False)
        self.assertEqual(first["score_normalised"], 1)
        self.assertTrue(all(store.items[i][1] == data for i, data in old.items()))

        # Amendment (b2): existing domain objects/keys remain measured powers.
        domain_fixture = json.loads((ROOT / "tests/fixtures/rc_pyusd.json").read_text(encoding="utf-8"))
        domain_extensions = domain_fixture["token_extensions"]
        domain_key = domain_extensions["permanentDelegate"]["delegate"]
        domain_none = "1" * 32
        domain_powers = ("permanentDelegate", "pausableConfig", "mintCloseAuthority", "freeze_or_mint")
        domain_cases = [
            ({"permanentDelegate": domain_extensions["permanentDelegate"],
              "mintCloseAuthority": domain_extensions["mintCloseAuthority"],
              "pausableConfig": {"authority": domain_key, "paused": False}},
             {"freezeAuthority": domain_key, "mintAuthority": None}, True),
            ({key: None for key in domain_powers[:-1]},
             {"freezeAuthority": None, "mintAuthority": None}, False),
            ({"permanentDelegate": {"delegate": None}, "mintCloseAuthority": {"closeAuthority": domain_none},
              "pausableConfig": None}, {"freezeAuthority": domain_none, "mintAuthority": None}, False),
            ({}, {}, None),
            ({"permanentDelegate": "false", "mintCloseAuthority": {"closeAuthority": "false"},
              "pausableConfig": "false"}, {"freezeAuthority": "false", "mintAuthority": "false"}, None),
            ({"permanentDelegate": domain_key, "mintCloseAuthority": domain_key,
              "pausableConfig": {"authority": domain_key, "paused": True}},
             {"freezeAuthority": None, "mintAuthority": domain_key}, True),
        ]
        domain_clock, domain_store, _, _, _, _ = self.active()
        domain_prior = {i: data for i, (_, data) in domain_store.items.items()}
        domain_service = type("ArtifactService", (), {})()
        domain_service.list, domain_service.load = domain_store.list, domain_store.load
        domain_service.reads = domain_service.downloads = 0
        domain_fetch, domain_calls = self.vendor(domain_clock)
        domain_inputs = {mint(i): value for i, value in enumerate(domain_cases)}
        def domain_raw(url):
            code, body = domain_fetch(url)
            domain_mint = url.split("/tokens/", 1)[1].split("/", 1)[0]
            if domain_mint in domain_inputs:
                extensions, authorities, _ = domain_inputs[domain_mint]
                body["token_extensions"] = copy.deepcopy(extensions)
                body.pop("freezeAuthority", None)
                body.pop("mintAuthority", None)
                body.update(authorities)
            return code, body
        with tempfile.TemporaryDirectory() as domain_directory:
            domain_folder = Path(domain_directory) / "tick"
            domain_ctx = context(11)
            with patch.object(driver, "_context_env", return_value=domain_ctx), \
                    patch.object(driver, "GitHubArtifacts", return_value=domain_service), \
                    patch.object(driver.time, "time", side_effect=domain_clock), \
                    patch.object(driver.collect, "__defaults__", (domain_clock, domain_clock.sleep, None)), \
                    patch.object(probe, "curl", side_effect=domain_raw), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(domain_folder)]), 0)
                domain_plan = json.loads((domain_folder / "plan.json").read_text(encoding="utf-8"))
                domain_intent = domain_store.publish(domain_plan["state"], [], "intent", domain_ctx)
                self.assertEqual(driver.main(["collect", "--out", str(domain_folder), "--intent", str(domain_intent)]), 0)
                domain_state = json.loads((domain_folder / "result/state.json").read_text(encoding="utf-8"))
                domain_rows = [json.loads(line) for line in (domain_folder / "result/observations.jsonl").read_bytes().splitlines()]
                domain_result = domain_store.publish(domain_state, domain_rows, "result", domain_ctx)
                domain_report = Path(domain_directory) / "report"
                self.assertEqual(driver.main(["prepare", "--phase", "report", "--study", "study-one", "--out", str(domain_report)]), 0)
                domain_answer = json.loads((domain_report / "result/report.json").read_text(encoding="utf-8"))
        domain_restored = domain_store.load(domain_result)["rows"]
        for domain_index, (_, _, domain_expected) in enumerate(domain_cases):
            domain_row = next(row for row in domain_restored if row.get("mint") == mint(domain_index))
            for domain_power in domain_powers:
                self.assertIs(domain_row["gated"][domain_power], domain_expected)
            self.assertEqual(domain_row["score_normalised"], 1)
        for domain_power in domain_powers:
            self.assertEqual(domain_answer["coverage"]["fresh"]["fields"][domain_power]["usable"], 4)
            self.assertEqual(domain_answer["coverage"]["fresh"]["fields"][domain_power]["attempted_unavailable_or_invalid"], 41)
        self.assertEqual(len(domain_calls), 63)
        self.assertTrue(all(domain_store.items[i][1] == data for i, data in domain_prior.items()))

    def test_cli_interruption_preserves_a_restorable_partial_checkpoint(self):
        self.need()
        clock, store, _, _, _, _ = self.active()
        prior = {i: data for i, (_, data) in store.items.items()}
        service = type("ArtifactService", (), {})()
        service.list, service.load = store.list, store.load
        service.reads = service.downloads = 0
        ctx = context(8)
        def publish(folder, kind):
            state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
            target = io.BytesIO()
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(folder.iterdir()):
                    archive.writestr(path.name, path.read_bytes())
            ident = max(store.items, default=0) + 1
            store.items[ident] = ({"id": ident, "name": driver.artifact_name(state, kind, ctx),
                                  "expired": False, "provenance": copy.deepcopy(ctx)}, target.getvalue())
            return ident
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "job"
            fetch, calls = self.vendor(clock)
            def interrupted(url):
                if len(calls) == 1:
                    raise KeyboardInterrupt()
                return fetch(url)
            with patch.object(driver, "_context_env", return_value=ctx), \
                    patch.object(driver, "GitHubArtifacts", return_value=service), \
                    patch.object(driver.time, "time", side_effect=clock), \
                    patch.object(driver.collect, "__defaults__", (clock, clock.sleep, None)), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(driver.main(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(folder)]), 0)
                intent = publish(folder / "intent", "intent")
                with patch.object(probe, "curl", side_effect=interrupted):
                    try:
                        driver.main(["collect", "--out", str(folder), "--intent", str(intent)])
                    except KeyboardInterrupt:
                        pass
                try:
                    finalized = driver.main(["finalize", "--out", str(folder)])
                except SystemExit as exc:
                    finalized = exc.code
                self.assertEqual(finalized, 0, "always-preserve must finalize the actual interrupted journal")
            result = publish(folder / "result", "result")
        decoded = store.load(result)
        self.assertEqual(len([r for r in decoded["rows"] if r.get("body") == "ok"]), 1)
        self.assertIn(decoded["state"]["status"], ("failed", "lost_checkpoint"))
        with patch.object(probe, "curl", side_effect=AssertionError("interrupted slot replay")):
            self.assertEqual(driver.prepare("tick", store, context(9), clock(), study="study-one")["action"], "idle")
            answer = driver.reconstruct(store, context(9), "study-one")
        self.assertTrue(answer["censored"])
        self.assertEqual(answer["coverage"]["fresh"]["attempted_cells"], 1)
        self.assertTrue(all(store.items[i][1] == data for i, data in prior.items()))
        workflow = (ROOT / ".github/workflows/rugcheck-w57.yml").read_text(encoding="utf-8")
        self.assertIn("finalize --out", workflow)
        self.assertLess(workflow.index("finalize --out"), workflow.index("name: Preserve completed and partial observations"))

    def test_intent_only_terminal_checkpoint_reconstructs_without_replay(self):
        self.need()
        clock, store, previous_id, _, _, _ = self.active()
        prior = {i: data for i, (_, data) in store.items.items()}
        service = type("ArtifactService", (), {})()
        service.list, service.load = store.list, store.load
        service.reads = service.downloads = 0
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            def cli(args, ctx):
                with patch.object(driver, "_context_env", return_value=ctx), \
                        patch.object(driver, "GitHubArtifacts", return_value=service), \
                        patch.object(driver.time, "time", side_effect=clock), \
                        contextlib.redirect_stdout(io.StringIO()):
                    return driver.main(args)
            with patch.object(probe, "curl", side_effect=AssertionError("lost intent replay")):
                first, second, report_dir = base / "first", base / "second", base / "report"
                self.assertEqual(cli(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(first)], context(5)), 0)
                plan = json.loads((first / "plan.json").read_text(encoding="utf-8"))
                intent = store.publish(plan["state"], [], "intent", context(5))
                intent_digest = store.load(intent)["digest"]
                self.assertEqual(cli(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(second)], context(6)), 0)
                lost = json.loads((second / "plan.json").read_text(encoding="utf-8"))
                self.assertEqual(lost["action"], "checkpoint")
                result_state = json.loads((second / "result/state.json").read_text(encoding="utf-8"))
                result = store.publish(result_state, [], "result", context(6))
                self.assertEqual(cli(["prepare", "--phase", "report", "--study", "study-one", "--out", str(report_dir)], context(7)), 0)
                report = json.loads((report_dir / "result/report.json").read_text(encoding="utf-8"))
        state = store.load(result)["state"]
        self.assertEqual(state["status"], "lost_checkpoint")
        self.assertEqual(state["lost_intent"], {"id": intent, "digest": intent_digest})
        self.assertEqual(state["parent"]["id"], previous_id)
        self.assertEqual(report["losses"][0]["reason"], "lost_checkpoint")
        self.assertEqual(report["losses"][0]["slot"], 0)
        self.assertEqual(report["fresh_enrolled"], 45)
        self.assertTrue(report["censored"])
        self.assertTrue(all(store.items[i][1] == data for i, data in prior.items()))

    def test_crossing_intervals_do_not_assert_a_right_endpoint_as_a_lower_bound(self):
        self.need()
        clock, store, _, _, initial, _ = self.active()
        state = initial["result_state"]
        start = state["started_at"]
        origins = {m["mint"]: m["enrollment"]["detectedAt"] for m in state["cohort"] if m["group"] == "fresh"}
        service = type("ArtifactService", (), {})()
        service.list, service.load = store.list, store.load
        service.reads = service.downloads = 0
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            def cli(args, ctx):
                with patch.object(driver, "_context_env", return_value=ctx), \
                        patch.object(driver, "GitHubArtifacts", return_value=service), \
                        patch.object(driver.time, "time", side_effect=clock), \
                        patch.object(driver.collect, "__defaults__", (clock, clock.sleep, None)), \
                        contextlib.redirect_stdout(io.StringIO()):
                    return driver.main(args)
            def tick(run, hours, score, unavailable=False):
                clock.value = start + hours * 3600
                ctx, folder = context(run), base / str(run)
                fetch, _ = self.vendor(clock)
                def raw(url):
                    code, body = fetch(url)
                    if "rugcheck" in url:
                        if unavailable:
                            return "429", {"score_normalised": 1}
                        m = url.split("/tokens/", 1)[1].split("/", 1)[0]
                        body["score_normalised"] = score
                        body["detectedAt"] = origins.get(m, body["detectedAt"])
                    return code, body
                self.assertEqual(cli(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(folder)], ctx), 0)
                plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
                intent = store.publish(plan["state"], [], "intent", ctx)
                with patch.object(probe, "curl", side_effect=raw):
                    self.assertEqual(cli(["collect", "--out", str(folder), "--intent", str(intent)], ctx), 0)
                rows = [json.loads(line) for line in (folder / "result/observations.jsonl").read_text(encoding="utf-8").splitlines()]
                result_state = json.loads((folder / "result/state.json").read_text(encoding="utf-8"))
                store.publish(result_state, rows, "result", ctx)
            tick(5, 0, 1)
            tick(6, 20, 1, unavailable=True)
            tick(7, 44, 80)
            wide = driver.reconstruct(store, context(8), "study-one")
            self.assertEqual(wide["proposal"], "inconclusive")
            event = wide["events"][0]
            self.assertEqual(event["tail_location"], "ambiguous")
            self.assertLess(event["elapsed_interval_minutes"][0], 43.2 * 60)
            self.assertGreater(event["elapsed_interval_minutes"][1], 43.2 * 60)
            self.assertEqual(len(event["index_age_interval_minutes"]), 2)
            bound = wide.get("proposed_lower_bound_minutes")
            self.assertTrue(bound is None or bound <= event["index_age_interval_minutes"][0])
            tick(9, 44.5, 1)
            tick(10, 45, 80)
            tail = driver.reconstruct(store, context(11), "study-one")
            self.assertEqual(tail["proposal"], "different_rule_e14_review")
            latest = tail["latest_flip"]
            self.assertEqual(latest["tail_location"], "within_final_tenth")
            self.assertGreaterEqual(latest["elapsed_interval_minutes"][0], 43.2 * 60)
            self.assertLessEqual(tail["proposed_lower_bound_minutes"], latest["index_age_interval_minutes"][0])
            self.assertEqual(tail["final_tenth_start"], start + 48 * 3600 * 0.9)

    def test_normalized_overflow_preserves_prior_rows_and_an_explicit_receipt(self):
        self.need()
        clock, store, _, _, _, _ = self.active()
        old = {i: data for i, (_, data) in store.items.items()}
        service = type("ArtifactService", (), {})()
        service.list, service.load = store.list, store.load
        service.reads = service.downloads = 0
        ctx = context(8)
        fetch, calls = self.vendor(clock)
        def raw(url):
            code, body = fetch(url)
            if len(calls) == 2:
                body["score_normalised"] = 10 ** 2500
            return code, body
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "job"
            with patch.object(driver, "_context_env", return_value=ctx), \
                    patch.object(driver, "GitHubArtifacts", return_value=service), \
                    patch.object(driver.time, "time", side_effect=clock), \
                    patch.object(driver.collect, "__defaults__", (clock, clock.sleep, None)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(["prepare", "--phase", "tick", "--study", "study-one", "--out", str(folder)]), 0)
                plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
                intent = store.publish(plan["state"], [], "intent", ctx)
                with patch.object(probe, "curl", side_effect=raw):
                    self.assertEqual(driver.main(["collect", "--out", str(folder), "--intent", str(intent)]), 0)
            state = json.loads((folder / "result/state.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in (folder / "result/observations.jsonl").read_text(encoding="utf-8").splitlines()]
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted((folder / "result").iterdir()):
                    archive.writestr(path.name, path.read_bytes())
        decoded = driver.decode_bundle(data.getvalue(), ctx, context(9))
        self.assertEqual(state["status"], "overflow")
        self.assertEqual(state["failure"], "row_overflow")
        self.assertEqual(len(calls), 2)
        self.assertEqual(rows[0]["score_normalised"], 1)
        receipt = next(r for r in decoded["rows"] if r.get("kind") == "overflow_receipt")
        self.assertEqual((receipt["reason"], receipt["mint"], receipt["slot"]), ("row_overflow", mint(1), 0))
        self.assertLessEqual(len(driver.encoded(receipt)), 2048)
        self.assertLessEqual(len(data.getvalue()), 1024 * 1024)
        self.assertTrue(all(store.items[i][1] == previous for i, previous in old.items()))


class CheckpointChronologyTests(unittest.TestCase):
    """Opaque Artifact IDs never determine the study's publication chronology."""

    def fixture(self, later=False, ids=None):
        harness = StudyTests("test_slots_use_wall_time_skip_gaps_and_do_not_recruit_again")
        clock, memory, active, _, _, _ = harness.active()
        if later:
            clock.sleep(1800)
            fetch, _ = harness.vendor(clock)
            with patch.object(probe, "curl", side_effect=fetch):
                harness.job("tick", memory, clock, context(3), "study-one")
        old = list(memory.items)
        ids = ids or ([701, 904, 500, 800, 499, 600] if later else [701, 904, 500, 800])
        self.assertEqual(len(ids), len(old))
        references, metadata, payloads, runs, decoded = {}, [], {}, {}, {}

        def rebound(value):
            if isinstance(value, dict):
                if set(value) == {"id", "digest"}:
                    return copy.deepcopy(references[value["id"]])
                return {key: rebound(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rebound(item) for item in value]
            return copy.deepcopy(value)

        for order, (original, ident) in enumerate(zip(old, ids)):
            part = memory.load(original)
            state, ctx = rebound(part["state"]), part["manifest"]["context"]
            data = driver.bundle_bytes(state, part["rows"], part["manifest"]["kind"], ctx)
            item = driver.decode_bundle(data, ctx, context(7))
            references[original] = {"id": ident, "digest": item["digest"]}
            payloads[ident], decoded[ident] = data, item
            metadata.append({"id": ident, "name": driver.artifact_name(state, item["manifest"]["kind"], ctx),
                             "expired": False, "size_in_bytes": len(data),
                             "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                             "created_at": stamp(EPOCH - 600 + order * 60).replace("+00:00", "Z"),
                             "workflow_run": {"id": ctx["run_id"], "head_sha": ctx["head"],
                                              "head_branch": "master", "repository_id": 1,
                                              "head_repository_id": 1}})
            runs[ctx["run_id"]] = {"id": ctx["run_id"], "repository": {"full_name": ctx["repository"]},
                                   "head_repository": {"full_name": ctx["repository"]},
                                   "path": driver.WORKFLOW, "head_branch": "master", "head_sha": ctx["head"],
                                   "event": "workflow_dispatch"}
        return {"clock": clock, "metadata": metadata, "payloads": payloads, "runs": runs,
                "decoded": decoded, "active": ids[old.index(active)], "ids": ids}

    def service(self, fixture, ctx=None, report=False, reverse=False, pages=None):
        ctx = ctx or context(7)
        service = driver.GitHubArtifacts(ctx, "synthetic-token", max_reads=600 if report else 12,
                                         max_downloads=195 if report else 2,
                                         seconds=720 if report else 110)
        requests = []
        by_id = {row["id"]: row for row in fixture["metadata"] if type(row.get("id")) is int}

        def request(path, binary=False):
            service._count(2 if binary else 1)
            requests.append((path, binary))
            prefix = "/repos/synthetic/study/actions/"
            self.assertTrue(path.startswith(prefix), "the real adapter must keep its owned endpoint")
            tail = path[len(prefix):]
            if tail.startswith("artifacts?name="):
                kind = tail.split("w57-", 1)[1].split("-v1", 1)[0]
                page = int(tail.rsplit("page=", 1)[1])
                if pages is not None:
                    rows = pages.get((kind, page), [])
                else:
                    rows = [row for row in fixture["metadata"] if row.get("name") == "w57-%s-v1" % kind]
                    if reverse:
                        rows = list(reversed(rows))
                    rows = rows[(page - 1) * 100:page * 100]
                return {"total_count": len(rows), "artifacts": copy.deepcopy(rows)}
            if tail.startswith("runs/"):
                return copy.deepcopy(fixture["runs"][int(tail.split("/")[1])])
            if tail.endswith("/zip"):
                return fixture["payloads"][int(tail.split("/")[1])]
            if tail.startswith("artifacts/"):
                return copy.deepcopy(by_id[int(tail.split("/")[1])])
            self.fail("unexpected control-plane route")

        return service, requests, patch.object(service, "request", side_effect=request)

    def downloads(self, requests):
        return [int(path.split("/artifacts/", 1)[1].split("/", 1)[0])
                for path, binary in requests if binary]

    def rewrite(self, fixture, ident, change):
        item = fixture["decoded"][ident]
        state, rows, ctx = copy.deepcopy(item["state"]), copy.deepcopy(item["rows"]), item["manifest"]["context"]
        change(state, rows)
        fixture["payloads"][ident] = driver.bundle_bytes(state, rows, item["manifest"]["kind"], ctx)

    def test_checkpoint_chronology_ignores_nonmonotonic_artifact_ids(self):
        self.assertIsNotNone(driver)
        with patch.object(probe, "curl", side_effect=AssertionError("unexpected vendor request")):
            for ids in ([701, 904, 500, 800], [9, 40, 30, 1]):
                fixture = self.fixture(ids=ids)
                active = fixture["decoded"][fixture["active"]]["state"]
                now = active["started_at"] + 7 * driver.INTERVAL + 1
                for reverse in (False, True):
                    service, requests, transport = self.service(fixture, reverse=reverse)
                    with transport:
                        plan = driver.prepare("tick", service, context(7), now)
                    self.assertEqual(plan["action"], "collect", "a newer active start must supersede its earlier terminal pilot")
                    self.assertEqual(self.downloads(requests), [fixture["active"]])
                    self.assertEqual(plan["state"]["slot"], 7)
                    self.assertEqual(plan["state"]["cohort"], active["cohort"])
                    self.assertEqual((plan["state"]["started_at"], plan["state"]["ends_at"]),
                                     (active["started_at"], active["ends_at"]))
                    self.assertEqual([slot["slot"] for slot in plan["state"]["slots"] if slot["status"] == "not_observed"],
                                     list(range(7)))
                    self.assertLessEqual(service.reads, 12)
                    self.assertLessEqual(service.downloads, 2)
                for phase in ("pilot", "start"):
                    service, _, transport = self.service(fixture)
                    with transport, self.assertRaises(driver.StudyError):
                        driver.prepare(phase, service, context(7), now, study="another-study", pilot_id=ids[1])
                changed = context(7)
                changed["source"]["driver"] = "e" * 64
                service, _, transport = self.service(fixture, changed)
                with transport:
                    terminal = driver.prepare("tick", service, changed, now)
                self.assertEqual((terminal["action"], terminal["state"]["status"]), ("checkpoint", "source_changed"))
                for key in ("source", "cohort", "started_at", "ends_at"):
                    self.assertEqual(terminal["state"][key], active[key])
                self.assertEqual(terminal["state"]["chunks"][:-1], active["chunks"])
                self.assertEqual(terminal["state"]["chunks"][-1]["id"], fixture["active"])
                orphan = self.fixture(later=True)
                del orphan["payloads"][orphan["ids"][-1]]
                orphan["metadata"] = orphan["metadata"][:-1]
                service, requests, transport = self.service(orphan)
                with transport:
                    lost = driver.prepare("tick", service, context(7), now)
                self.assertEqual((lost["action"], lost["state"]["status"]), ("checkpoint", "lost_checkpoint"))
                self.assertEqual(lost["state"]["lost_intent"]["id"], orphan["ids"][-2])
                self.assertEqual(self.downloads(requests), [orphan["ids"][-2]])

            paged = self.fixture()
            results = [row for row in paged["metadata"] if row["name"] == "w57-result-v1"]
            padding = []
            for index in range(98):
                row = copy.deepcopy(results[0])
                row.update(id=10000 + index, created_at=stamp(EPOCH - 20000 + index).replace("+00:00", "Z"))
                row["workflow_run"]["id"] = 10000 + index
                padding.append(row)
            pages = {("result", 1): list(reversed(padding + results)), ("result", 2): [],
                     ("intent", 1): [row for row in paged["metadata"] if row["name"] == "w57-intent-v1"]}
            paged["metadata"].extend(padding)
            service, requests, transport = self.service(paged, pages=pages)
            with transport:
                plan = driver.prepare("tick", service, context(7), now)
            self.assertEqual(plan["action"], "collect")
            self.assertEqual(self.downloads(requests), [paged["active"]])
            self.assertEqual(len([path for path, binary in requests if "artifacts?name=" in path]), 3)

    def test_checkpoint_chronology_fails_closed_on_invalid_or_ambiguous_metadata(self):
        self.assertIsNotNone(driver)
        changes = [("missing_time", lambda row: row.pop("created_at")),
                   ("bad_time", lambda row: row.update(created_at="unavailable")),
                   ("naive_time", lambda row: row.update(created_at="2026-10-20T00:00:00")),
                   ("invalid_date", lambda row: row.update(created_at="2026-02-30T00:00:00Z")),
                   ("non_utc_time", lambda row: row.update(created_at="2026-10-20T00:00:00+08:00")),
                   ("invalid_id", lambda row: row.update(id=0)),
                   ("boolean_id", lambda row: row.update(id=True)),
                   ("missing_run", lambda row: row.pop("workflow_run")),
                   ("boolean_run", lambda row: row["workflow_run"].update(id=True)),
                   ("missing_run_head", lambda row: row["workflow_run"].pop("head_sha"))]
        with patch.object(probe, "curl", side_effect=AssertionError("unexpected vendor request")):
            for name, change in changes:
                fixture = self.fixture()
                change(fixture["metadata"][-1])
                service, requests, transport = self.service(fixture)
                with self.subTest(name=name), transport, self.assertRaises(driver.StudyError):
                    driver.prepare("tick", service, context(7), fixture["clock"]() + 1800)
                self.assertEqual(self.downloads(requests), [], "invalid chronology must stop before checkpoint downloads")
            for duplicate in (False, True):
                fixture = self.fixture()
                row = copy.deepcopy(fixture["metadata"][-1])
                if not duplicate:
                    row["id"] += 100
                    row["workflow_run"]["id"] += 100
                fixture["metadata"].append(row)
                service, requests, transport = self.service(fixture)
                with self.subTest(duplicate=duplicate), transport, self.assertRaises(driver.StudyError):
                    service.list()
                self.assertEqual(self.downloads(requests), [])
            tied = self.fixture()
            tied["metadata"][-2]["created_at"] = tied["metadata"][-1]["created_at"]
            tied["metadata"][-2]["id"] = 999999
            service, requests, transport = self.service(tied)
            with transport:
                plan = driver.prepare("tick", service, context(7), tied["clock"]() + 1800)
            self.assertEqual(plan["action"], "collect")
            self.assertEqual(self.downloads(requests), [tied["active"]])
            for conflict in ("head", "kind"):
                fixture = copy.deepcopy(tied)
                if conflict == "head":
                    fixture["metadata"][-2]["workflow_run"]["head_sha"] = "f" * 40
                else:
                    fixture["metadata"][-2]["name"] = "w57-result-v1"
                service, _, transport = self.service(fixture)
                with self.subTest(conflict=conflict), transport, self.assertRaises(driver.StudyError):
                    service.list()
            bounded = driver.GitHubArtifacts(context(7), "synthetic-token")
            with patch.object(bounded, "request", return_value={"artifacts": [{"name": "unrelated"}] * 100}) as request:
                with self.assertRaises(driver.StudyError):
                    bounded.list()
                self.assertEqual(request.call_count, 5)
            bounded.downloads = 2
            with patch.object(bounded, "request", side_effect=AssertionError("download limit escaped")):
                with self.assertRaises(driver.StudyError):
                    bounded.load(1)

            for malformed in (None, {"id": 3}, {"id": 3, "name": None}):
                unavailable = driver.GitHubArtifacts(context(7), "synthetic-token")
                with self.subTest(raw_row=malformed), \
                        patch.object(unavailable, "request", return_value={"artifacts": [malformed]}), \
                        self.assertRaises(driver.StudyError):
                    driver.prepare("tick", unavailable, context(7), EPOCH)
                self.assertEqual(unavailable.downloads, 0)
            exhausted = driver.GitHubArtifacts(context(7), "synthetic-token")
            with patch.object(exhausted, "request", return_value={"artifacts": []}):
                self.assertEqual(driver.prepare("tick", exhausted, context(7), EPOCH),
                                 {"action": "idle", "reason": "no_state"})
            self.assertEqual(exhausted.downloads, 0)

    def test_checkpoint_reconstruction_keeps_later_lower_id_generations(self):
        self.assertIsNotNone(driver)
        with patch.object(probe, "curl", side_effect=AssertionError("unexpected vendor request")):
            for reverse in (False, True):
                fixture = self.fixture(later=True)
                latest, earlier = fixture["ids"][-1], fixture["active"]
                service, requests, transport = self.service(fixture, report=True, reverse=reverse)
                with transport:
                    answer = driver.reconstruct(service, context(7), "study-one")
                self.assertEqual(self.downloads(requests), [latest, earlier], "a larger pilot or older ID must not truncate later study history")
                rows = fixture["decoded"][earlier]["rows"] + fixture["decoded"][latest]["rows"]
                expected = driver.readout(fixture["decoded"][latest]["state"], rows)
                self.assertEqual(answer, expected)
                self.assertTrue(answer["censored"])
                self.assertLessEqual(service.downloads, 195)
                self.assertLessEqual(service.reads, 600)
            for defect in ("digest", "parent", "cohort", "provenance", "source"):
                fixture = self.fixture(later=True)
                latest = fixture["ids"][-1]
                if defect == "digest":
                    data = io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(fixture["payloads"][latest])) as source, \
                            zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as target:
                        for name in source.namelist():
                            raw = source.read(name)
                            if name == "manifest.json":
                                manifest = json.loads(raw)
                                manifest["files"]["observations.jsonl"] = "f" * 64
                                raw = driver.encoded(manifest)
                            target.writestr(name, raw)
                    fixture["payloads"][latest] = data.getvalue()
                elif defect == "parent":
                    self.rewrite(fixture, latest, lambda state, rows: state["parent"].update(digest="f" * 64))
                elif defect == "cohort":
                    self.rewrite(fixture, latest, lambda state, rows: state["cohort"][0].update(mint=mint(200)))
                elif defect == "source":
                    self.rewrite(fixture, latest, lambda state, rows: state["source"].update(driver="e" * 64))
                else:
                    fixture["runs"][3]["path"] = "other.yml"
                service, requests, transport = self.service(fixture, report=True)
                with patch.object(service, "load", wraps=service.load) as attempted:
                    with self.subTest(defect=defect), transport, self.assertRaises(driver.StudyError):
                        driver.reconstruct(service, context(7), "study-one")
                self.assertTrue(attempted.call_args_list)
                self.assertEqual(attempted.call_args_list[0].args[0], latest)
                if defect == "provenance":
                    self.assertEqual(self.downloads(requests), [])
                else:
                    self.assertTrue(self.downloads(requests) and self.downloads(requests)[0] == latest,
                                    "a damaged latest checkpoint must not downgrade to an older report")


class SessionClock:
    """UTC and monotonic clocks advance independently under explicit fault injection."""
    def __init__(self, value=EPOCH):
        self.value, self.elapsed, self.sleeps = value, 0, []

    def utc(self):
        return self.value

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds
        self.elapsed += seconds


class SessionMemory:
    def __init__(self, module, ctx):
        self.module, self.ctx, self.items = module, ctx, {}
        self.fail_upload = False

    def __deepcopy__(self, memo):
        result = SessionMemory(self.module, copy.deepcopy(self.ctx, memo))
        result.items = copy.deepcopy(self.items, memo)
        result.fail_upload = self.fail_upload
        return result

    def list(self, scope="run", namespace="live"):
        rows = [copy.deepcopy(meta) for meta, _ in self.items.values()]
        if scope == "admission":
            return [row for row in rows if row["name"] in self.module.ADMISSION_NAMES]
        return [row for row in rows if row["workflow_run"]["id"] == self.ctx["run_id"]]

    def load(self, ident):
        meta, data = self.items[ident]
        return self.module.decode_bundle(data, meta["provenance"], self.ctx)

    def publish(self, state, rows, kind, ctx, namespace="live"):
        if self.fail_upload:
            raise driver.StudyError("upload_failed")
        ident = 9000000 - len(self.items) * 7919
        name = self.module.artifact_name(state, kind, ctx, namespace)
        if any(meta["name"] == name for meta, _ in self.items.values()):
            raise driver.StudyError("duplicate_publication")
        data = self.module.bundle_bytes(state, rows, kind, ctx, namespace)
        self.items[ident] = ({"id": ident, "name": name, "expired": False,
                              "size_in_bytes": len(data), "digest": "sha256:" + driver.sha(data),
                              "created_at": stamp(EPOCH).replace("+00:00", "Z"),
                              "workflow_run": {"id": ctx["run_id"], "head_sha": ctx["head"],
                                               "head_branch": ctx["branch"]},
                              "provenance": copy.deepcopy(ctx)}, data)
        return ident


class RunningSessionTests(unittest.TestCase):
    """T-054: full finite clocks and transport handoffs, with zero real network calls."""
    def setUp(self):
        path = ROOT / "bench/rugcheck_w57_session.py"
        self.assertTrue(path.is_file(), "T-054 running-session adapter is missing")
        spec = importlib.util.spec_from_file_location("w57_session_acceptance", path)
        self.session = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"rugcheck_w57_ci": driver}):
            spec.loader.exec_module(self.session)
        self.ctx = dict(context(300), attempt=1, source=self.session.source_hashes(),
                        control_sources=self.session.source_freeze())

    def active(self):
        harness = StudyTests("test_slots_use_wall_time_skip_gaps_and_do_not_recruit_again")
        clock, _, _, _, plan, _ = harness.active()
        state = self.session.bind_state(plan["result_state"], self.ctx, "live")
        fake = SessionClock(state["started_at"])
        store = SessionMemory(self.session, self.ctx)
        ident = store.publish(state, [], "result", self.ctx)
        return fake, store, ident, state

    def run_slot(self, clock, store, slot, namespace="live", lease=None):
        lease = lease or self.session.Lease(clock)
        plan = self.session.prepare_slot(store, self.ctx, clock, lease, slot, namespace=namespace)
        if plan["action"] == "idle":
            return None, plan
        rows = []
        if plan["action"] == "collect":
            intent = store.publish(plan["state"], [], "intent", self.ctx, namespace)
            state, rows = self.session.collect(plan, intent, store, self.ctx, clock, lease)
        else:
            state = plan["state"]
        result = store.publish(state, rows, "result", self.ctx, namespace)
        self.session.verify_result(store, result, state, self.ctx, namespace)
        return result, dict(plan, final_state=state, rows=rows)

    def service(self, memory, *, report=False, admission=False, body_change=None):
        module, ctx = self.session, self.ctx
        service = module.Artifacts(ctx, "synthetic-token", report=report, admission=admission)
        requests = []
        def request(path, binary=False):
            service._count(2 if binary else 1)
            requests.append((path, binary))
            tail = path.split("/actions/", 1)[1]
            if "artifacts?" in tail:
                rows = [copy.deepcopy(meta) for meta, _ in memory.items.values()]
                if tail.startswith("artifacts?name="):
                    name = tail.split("name=", 1)[1].split("&", 1)[0]
                    rows = [row for row in rows if row["name"] == name]
                elif tail.startswith("runs/"):
                    run = int(tail.split("/")[1])
                    rows = [row for row in rows if row["workflow_run"]["id"] == run]
                page = int(tail.rsplit("page=", 1)[1])
                body = {"total_count": len(rows), "artifacts": list(reversed(rows))[(page - 1) * 100:page * 100]}
                if body_change:
                    body_change(body)
                return body
            if tail.startswith("runs/"):
                run = int(tail.split("/")[1])
                provenance = next(meta["provenance"] for meta, _ in memory.items.values()
                                  if meta["workflow_run"]["id"] == run)
                return {"id": run, "run_attempt": 1, "event": "workflow_dispatch", "status": "in_progress",
                        "conclusion": None, "path": driver.WORKFLOW, "head_sha": provenance["head"],
                        "head_branch": provenance["branch"], "repository": {"full_name": provenance["repository"]},
                        "head_repository": {"full_name": provenance["repository"]}}
            ident = int(tail.split("/")[1])
            return memory.items[ident][1] if binary else copy.deepcopy(memory.items[ident][0])
        return service, requests, patch.object(service, "request", side_effect=request)

    def test_source_freeze_covers_every_executed_control_and_legacy_bytes(self):
        freeze = self.session.source_freeze()
        expected = {"driver": "bench/rugcheck_w57_ci.py", "probe": "bench/rugcheck_coverage_probe.py",
                    "session": "bench/rugcheck_w57_session.py", "workflow": driver.WORKFLOW,
                    "generator": ".github/scripts/render_w57_session_workflow.py"}
        self.assertEqual(freeze, {key: driver.sha((ROOT / path).read_bytes()) for key, path in expected.items()})
        legacy = json.loads((ROOT / "tests/fixtures/w57_legacy193_characterization.json").read_bytes())
        self.assertEqual(driver.protocol_descriptor(driver.LEGACY193), legacy["legacy_protocol"])
        self.assertEqual(driver.sha((ROOT / expected["probe"]).read_bytes().replace(b"\r\n", b"\n")),
                         "3734d9c3b51114a90c7512ee77c6d90754e205a14085bbf22eee012acb4fbc21")
        self.assertEqual(set(self.ctx["source"]), {"driver", "probe", "workflow"})
        self.assertNotEqual(self.ctx["source"]["workflow"], freeze["workflow"])
        self.assertIn("composite", self.session.__doc__.lower())

    def test_reruns_and_untrusted_context_stop_before_transport(self):
        env = {"GITHUB_REPOSITORY": "synthetic/study", "GITHUB_REF_NAME": "master", "W57_DEFAULT_BRANCH": "master",
               "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "300", "GITHUB_RUN_ATTEMPT": "1",
               "GITHUB_EVENT_NAME": "workflow_dispatch"}
        self.assertEqual(self.session.context(env)["attempt"], 1)
        for key, value in (("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_RUN_ATTEMPT", "0"),
                           ("GITHUB_REF_NAME", "foreign"), ("GITHUB_EVENT_NAME", "schedule")):
            with self.subTest(key=key, value=value), self.assertRaises(driver.StudyError):
                self.session.context(dict(env, **{key: value}))
        with patch.object(probe, "curl", side_effect=AssertionError("Vendor request")), \
                patch.object(self.session, "Artifacts", side_effect=AssertionError("transport")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.session.main([]), 0)

    def test_full_193_slot_schedule_uses_absolute_time_and_ten_finite_handoffs(self):
        clock, memory, _, initial = self.active()
        source = copy.deepcopy(initial["source"])
        calls, handoffs, pairs = [], [], []
        def vendor(url):
            calls.append(clock.utc())
            return "200", {"score_normalised": 1, "detectedAt": stamp(initial["started_at"] - 60),
                           "topHolders": [], "totalHolders": 0, "token_extensions": {}}
        with patch.object(probe, "curl", side_effect=vendor):
            for segment in range(10):
                lease = self.session.Lease(clock)
                handoffs.append(clock.utc())
                for slot in range(segment * 20, min(193, (segment + 1) * 20)):
                    ident, result = self.run_slot(clock, memory, slot, lease=lease)
                    state = result["final_state"]
                    self.assertEqual(state["source"], source)
                    self.assertEqual(state["started_at"], initial["started_at"])
                    rows = result["rows"]
                    self.assertEqual(len(rows), 63)
                    self.assertEqual({row["slot"] for row in rows}, {slot})
                    self.assertEqual(rows[0]["request_started_at"], initial["started_at"] + slot * 900)
                    self.assertTrue(all(row["due_at"] == initial["started_at"] + slot * 900 for row in rows))
                    pairs.append((state["generation"], state["intent"]["id"], ident))
        self.assertEqual(len(calls), 193 * 63)
        self.assertEqual(len(set(g for g, _, _ in pairs)), 193)
        self.assertEqual(len(handoffs), 10)
        self.assertLessEqual(max(clock.sleeps), 30)
        self.assertEqual(state["status"], "completed")
        self.assertTrue(all(row["outside_window"] for row in rows[1:]))
        before = len(calls)
        self.assertEqual(self.session.prepare_slot(memory, self.ctx, clock, self.session.Lease(clock), 192)["action"], "idle")
        self.assertEqual(len(calls), before)
        service, requests, transport = self.service(memory, report=True)
        with transport:
            answer = self.session.reconstruct(service, self.ctx, initial["study"])
        self.assertEqual(answer["proposal"], "inconclusive")
        self.assertTrue(answer["censored"])
        self.assertEqual(answer["coverage"]["fresh"]["scheduled_slots"], 193)
        self.assertLessEqual(service.reads, 600)
        self.assertLessEqual(service.downloads, 195)

    def test_missed_due_is_explicit_and_never_replayed_or_backfilled(self):
        clock, memory, _, initial = self.active()
        clock.sleep(2 * 900 + 5)
        with patch.object(probe, "curl", side_effect=AssertionError("late backfill")):
            _, outcome = self.run_slot(clock, memory, 0)
        self.assertEqual(outcome["action"], "checkpoint")
        self.assertEqual(outcome["final_state"]["slots"], [{"slot": 0, "status": "not_observed"}])
        self.assertEqual(outcome["final_state"]["session"]["timing"]["due_at"], initial["started_at"])
        self.assertEqual(self.session.prepare_slot(memory, self.ctx, clock, self.session.Lease(clock), 0)["action"], "idle")

    def test_clock_jumps_source_changes_and_job_reserve_stop_without_vendor(self):
        for jump in (-120, 120):
            clock = SessionClock()
            lease = self.session.Lease(clock)
            sleep = clock.sleep
            def shifted(seconds):
                sleep(seconds)
                clock.value += jump
            clock.sleep = shifted
            with self.subTest(jump=jump), self.assertRaisesRegex(driver.StudyError, "clock_changed"):
                self.session.wait_due(clock, EPOCH + 900, lease)
            self.assertLessEqual(sum(clock.sleeps), 30)
        clock, memory, _, _ = self.active()
        lease = self.session.Lease(clock, seconds=330 * 60)
        clock.sleep(325 * 60 - 31)
        with patch.object(probe, "curl", side_effect=AssertionError("reserve consumed")):
            with self.assertRaises(driver.StudyError):
                self.session.wait_due(clock, clock.utc() + 1, lease, request_seconds=32)
        clock, memory, _, _ = self.active()
        changed = dict(self.ctx["source"], workflow="f" * 64)
        with patch.object(self.session, "source_hashes", return_value=changed), \
                patch.object(probe, "curl", side_effect=AssertionError("source drift")):
            plan = self.session.prepare_slot(memory, self.ctx, clock, self.session.Lease(clock), 1)
        self.assertEqual((plan["action"], plan["state"]["status"]), ("checkpoint", "source_changed"))

    def test_versioned_metadata_is_validated_before_normalizing_or_downloading(self):
        clock, memory, _, _ = self.active()
        with patch.object(probe, "curl", return_value=("503", {})):
            self.run_slot(clock, memory, 0)
            self.run_slot(clock, memory, 1)
        service, requests, transport = self.service(memory)
        with transport:
            listed = service.list()
            decoded = service.load(listed[-1]["id"])
        self.assertEqual(decoded["state"]["slots"][-1]["slot"], 1)
        self.assertLess(listed[-1]["id"], listed[0]["id"])
        self.assertEqual(len(set(row["name"] for row in listed)), len(listed))
        self.assertLessEqual(service.reads, 12)
        mutations = (lambda row: row.update(id=True), lambda row: row.update(name="w57-foreign-v2"),
                     lambda row: row.update(digest="sha256:" + "0" * 64), lambda row: row.update(expired=True),
                     lambda row: row.update(created_at="naive"), lambda row: row.update(size_in_bytes=1048577),
                     lambda row: row["workflow_run"].update(head_branch="foreign"))
        for mutate in mutations:
            changed = copy.deepcopy(memory)
            mutate(list(changed.items.values())[-1][0])
            service, requests, transport = self.service(changed)
            with transport, self.subTest(mutate=mutate), self.assertRaises(driver.StudyError):
                listed = service.list()
                service.load(listed[-1]["id"])
        changed = copy.deepcopy(memory)
        meta, data = list(changed.items.values())[-1]
        meta["digest"] = "sha256:" + "0" * 64
        service, _, transport = self.service(changed)
        with transport, self.assertRaises(driver.StudyError):
            service.list()
            service.load(meta["id"])
        service, requests, transport = self.service(memory, body_change=lambda body: body.update(total_count=100))
        with transport, self.assertRaises(driver.StudyError):
            service.list()
        self.assertFalse(any(binary for _, binary in requests))
        duplicate = copy.deepcopy(memory)
        duplicate.items[17] = copy.deepcopy(list(duplicate.items.values())[-1])
        duplicate.items[17][0]["id"] = 17
        service, _, transport = self.service(duplicate)
        with transport, self.assertRaises(driver.StudyError):
            service.list()

    def test_dangling_intent_and_failed_persistence_close_without_another_acquisition(self):
        clock, memory, _, _ = self.active()
        plan = self.session.prepare_slot(memory, self.ctx, clock, self.session.Lease(clock), 0)
        lost = memory.publish(plan["state"], [], "intent", self.ctx)
        with patch.object(probe, "curl", side_effect=AssertionError("replayed intent")):
            result = self.session.prepare_slot(memory, self.ctx, clock, self.session.Lease(clock), 0)
        self.assertEqual((result["action"], result["state"]["status"]), ("checkpoint", "lost_checkpoint"))
        self.assertEqual(result["state"]["lost_intent"]["id"], lost)
        with self.assertRaises(driver.StudyError):
            self.session.verify_result(memory, 999, result["state"], self.ctx, "live")
        memory.fail_upload = True
        with self.assertRaises(driver.StudyError):
            memory.publish(result["state"], [], "result", self.ctx)

    def test_v2_manifest_source_and_parent_chain_reject_corruption(self):
        clock, memory, ident, initial = self.active()
        meta, data = memory.items[ident]
        foreign = dict(meta["provenance"], head="f" * 40)
        with self.assertRaises(driver.StudyError):
            self.session.decode_bundle(data, foreign, self.ctx)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        files["state.json"] = files["state.json"].replace(b'"status":"active"', b'"status":"failed"')
        broken = io.BytesIO()
        with zipfile.ZipFile(broken, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in files.items():
                archive.writestr(name, payload)
        with self.assertRaises(driver.StudyError):
            self.session.decode_bundle(broken.getvalue(), self.ctx, self.ctx)
        with patch.object(probe, "curl", return_value=("503", {})):
            result, _ = self.run_slot(clock, memory, 0)
        part = memory.load(result)
        changed = copy.deepcopy(part["state"])
        changed["parent"] = {"id": ident, "digest": "0" * 64}
        data = self.session.bundle_bytes(changed, part["rows"], "result", self.ctx, "live")
        memory.items[result] = (dict(memory.items[result][0], digest="sha256:" + driver.sha(data),
                                    size_in_bytes=len(data)), data)
        with self.assertRaises(driver.StudyError):
            self.session.reconstruct(memory, self.ctx, initial["study"])

    def test_slow_live_phase_keeps_unavailable_and_unattempted_cells_distinct(self):
        clock, memory, _, _ = self.active()
        calls = []
        def slow(url):
            calls.append(clock.utc())
            clock.sleep(30)
            return "503", {}
        with patch.object(probe, "curl", side_effect=slow):
            _, outcome = self.run_slot(clock, memory, 0)
        self.assertGreater(len(calls), 0)
        self.assertLess(len(calls), 63)
        rows = outcome["rows"]
        self.assertEqual(sum(row["body"] == "unavailable" for row in rows), len(calls))
        self.assertEqual(sum(row["body"] == "not_observed" for row in rows), 63 - len(calls))
        self.assertEqual(outcome["final_state"]["slots"][-1]["status"], "partial")

    def test_unarmed_canary_three_real_intervals_cross_two_jobs_and_never_enters_live_readout(self):
        clock, memory = SessionClock(), SessionMemory(self.session, self.ctx)
        pairs = []
        with patch.object(probe, "curl", side_effect=AssertionError("canary Vendor call")):
            lease = self.session.Lease(clock)
            for slot in (0, 1):
                ident, result = self.run_slot(clock, memory, slot, "canary", lease)
                pairs.append((result["final_state"]["intent"]["id"], ident))
            lease = self.session.Lease(clock)
            ident, result = self.run_slot(clock, memory, 2, "canary", lease)
            pairs.append((result["final_state"]["intent"]["id"], ident))
            answer = self.session.reconstruct(memory, self.ctx, result["final_state"]["study"], namespace="canary")
        self.assertEqual(len(set(pairs)), 3)
        self.assertEqual(answer["readiness"], "passed")
        self.assertEqual(answer["vendor_requests"], 0)
        self.assertEqual([row["due_at"] for row in answer["timings"]], [EPOCH, EPOCH + 900, EPOCH + 1800])
        self.assertTrue(all(row["operation_started_at"] - row["due_at"] <= 60 for row in answer["timings"]))
        self.assertEqual(answer["observed_cells"], 3 * 63)
        self.assertEqual(answer["scientific_evidence"], False)
        self.assertIn("48", answer["disclosure"])
        self.assertEqual(memory.list("admission"), [])
        with self.assertRaises(driver.StudyError):
            self.session.reconstruct(memory, self.ctx, result["final_state"]["study"], namespace="live")

    def test_admission_combines_v1_v2_history_and_three_distinct_bounded_proofs(self):
        clock, memory, result_id, state = self.active()
        initial_state = copy.deepcopy(state)
        state["status"], state["phase"], state["cohort"] = "pilot_passed", "pilot", []
        state["started_at"] = state["ends_at"] = None
        state["study"], state["used_studies"] = "old-pilot", ["old-pilot"]
        pilot_ctx = dict(self.ctx, run_id=298)
        pilot = memory.publish(state, [], "result", pilot_ctx)
        terminal = copy.deepcopy(state)
        terminal["study"], terminal["used_studies"] = "later-pilot", ["old-pilot", "later-pilot"]
        last = memory.publish(terminal, [], "result", dict(self.ctx, run_id=299))
        terminal["session"]["last_durable"] = {"id": last, "digest": memory.load(last)["digest"]}
        history = memory.publish(terminal, [], "admission-result", dict(self.ctx, run_id=299))
        service, requests, transport = self.service(memory, admission=True)
        with transport:
            plan = self.session.prepare_admission("start", service, self.ctx, clock.utc(), "new-study", pilot)
            intent = memory.publish(plan["state"], [], "intent", self.ctx)
            service.load(intent)
        self.assertEqual(set(plan["state"]["used_studies"]), {"old-pilot", "later-pilot", "new-study"})
        self.assertEqual({int(path.split("/artifacts/")[1].split("/")[0]) for path, binary in requests if binary},
                         {history, pilot, intent})
        self.assertLessEqual(service.reads, 16)
        self.assertEqual(service.downloads, 3)
        with self.assertRaises(driver.StudyError):
            service.load(result_id)
        service.reads = 16
        with self.assertRaises(driver.StudyError):
            service._count()
        for status in ("active", "lost_checkpoint"):
            blocked = copy.deepcopy(memory)
            pending = self.session.bind_state(copy.deepcopy(initial_state), self.ctx, "live")
            pending["status"] = status
            blocked.publish(pending, [], "admission-intent", self.ctx)
            with self.subTest(status=status), self.assertRaises(driver.StudyError):
                self.session.prepare_admission("pilot", blocked, dict(self.ctx, run_id=301), clock.utc(), "another")
        old = CheckpointChronologyTests().fixture()
        for ident, part in old["decoded"].items():
            memory.items[ident] = (dict(next(row for row in old["metadata"] if row["id"] == ident),
                                       provenance=part["manifest"]["context"]), old["payloads"][ident])
        # Legacy active history remains authoritative even after introducing the new decoder.
        legacy_only = SessionMemory(self.session, self.ctx)
        legacy_only.items = {ident: value for ident, value in memory.items.items() if ident in old["decoded"]}
        with self.assertRaises(driver.StudyError):
            self.session.prepare_admission("pilot", legacy_only, self.ctx, clock.utc(), "another")

    def test_final_phase_clock_drift_cannot_pass_readiness(self):
        for namespace in ("canary", "live"):
            for jump in (0, 120, -120):
                with self.subTest(namespace=namespace, jump=jump), tempfile.TemporaryDirectory() as directory:
                    if namespace == "canary":
                        clock, memory = SessionClock(), SessionMemory(self.session, self.ctx)
                        lease = self.session.Lease(clock)
                        self.run_slot(clock, memory, 0, namespace, lease)
                        self.run_slot(clock, memory, 1, namespace, lease)
                        slot = 2
                    else:
                        clock, memory, first, state = self.active()
                        state["slots"] = [{"slot": i, "status": "not_observed"} for i in range(192)]
                        data = self.session.bundle_bytes(state, [], "result", self.ctx, namespace)
                        memory.items[first] = (dict(memory.items[first][0], size_in_bytes=len(data),
                                                   digest="sha256:" + driver.sha(data)), data)
                        clock.sleep(192 * 900)
                        slot = 192
                    lease = self.session.Lease(clock)
                    plan = self.session.prepare_slot(memory, self.ctx, clock, lease, slot, namespace)
                    plan["lease"] = copy.deepcopy(lease.record)
                    folder = Path(directory)
                    self.session._atomic(folder / "plan.json", driver.encoded(plan))
                    self.session.write_bundle(folder / "intent", plan["state"], [], "intent", self.ctx, namespace)
                    intent = memory.publish(plan["state"], [], "intent", self.ctx, namespace)
                    fallback = copy.deepcopy(plan["state"])
                    fallback["status"] = "lost_checkpoint"
                    self.session.write_bundle(folder / "result", fallback, [], "result", self.ctx, namespace)
                    self.session._atomic(folder / "collection.json", driver.encoded({"id": intent}))
                    original_sleep, pacing = clock.sleep, [0]
                    def sleep(seconds):
                        original_sleep(seconds)
                        if seconds == 2:
                            pacing[0] += 1
                            if pacing[0] == 63:
                                clock.value += jump
                    clock.sleep = sleep
                    collected = None
                    with patch.object(probe, "curl", return_value=("503", {})), \
                            (folder / "result/observations.jsonl").open("wb") as stream:
                        def append(row):
                            stream.write(driver.encoded(row) + b"\n")
                            stream.flush()
                        try:
                            collected = self.session.collect(plan, intent, memory, self.ctx, clock, lease, append)
                        except driver.StudyError:
                            pass
                    if collected is not None:
                        self.session.write_bundle(folder / "result", *collected, "result", self.ctx, namespace)
                    self.session.finalize(folder, self.ctx, clock)
                    sealed = self.session._local(folder / "result", self.ctx)
                    self.assertEqual(pacing[0], 63)
                    self.assertEqual(len(sealed["rows"]), 63, "finalization must retain every flushed row")
                    memory.publish(sealed["state"], sealed["rows"], "result", self.ctx, namespace)
                    memory.reads = memory.downloads = memory.seconds_spent = 0
                    memory.runs = {}
                    # A new closure job may have a healthy lease; it cannot erase the old jump.
                    self.session.Lease(clock).check(clock)
                    with patch.object(self.session, "_store", return_value=memory):
                        answer = self.session.closure(folder / "closure", self.ctx, clock,
                                                      "canary" if namespace == "canary" else "start")
                    self.assertEqual(sealed["state"]["status"], "failed" if jump else "completed")
                    if namespace == "canary":
                        self.assertEqual(answer["readiness"], "failed" if jump else "passed")
                        self.assertEqual(answer["vendor_requests"], 0)
                    else:
                        self.assertEqual(answer.get("session_clock_stable", True), not bool(jump))

    def test_canary_readiness_requires_every_matching_intent(self):
        clock, memory = SessionClock(), SessionMemory(self.session, self.ctx)
        lease = self.session.Lease(clock)
        self.run_slot(clock, memory, 0, "canary", lease)
        self.run_slot(clock, memory, 1, "canary", lease)
        self.run_slot(clock, memory, 2, "canary", self.session.Lease(clock))
        study = "canary-%d" % self.ctx["run_id"]
        self.assertEqual(self.session.reconstruct(memory, self.ctx, study, "canary")["readiness"], "passed")
        intents = [ident for ident, (meta, _) in memory.items.items() if "-intent-" in meta["name"]]
        self.assertEqual(len(intents), 3)
        for ident in intents:
            changed = copy.deepcopy(memory)
            del changed.items[ident]
            with self.subTest(missing=ident), self.assertRaises(driver.StudyError):
                self.session.reconstruct(changed, self.ctx, study, "canary")
        for field in ("receipt", "source"):
            changed = copy.deepcopy(memory)
            ident = intents[-1]
            meta, _ = changed.items[ident]
            part = changed.load(ident)
            state, ctx = copy.deepcopy(part["state"]), copy.deepcopy(self.ctx)
            if field == "source":
                ctx["control_sources"]["driver"] = "f" * 64
                ctx["source"] = self.session.composite(ctx["control_sources"])
                state["source"], state["session"]["freeze"] = ctx["source"], ctx["control_sources"]
            else:
                state["session"]["different_intent"] = True
            data = self.session.bundle_bytes(state, [], "intent", ctx, "canary")
            changed.items[ident] = (dict(meta, digest="sha256:" + driver.sha(data), size_in_bytes=len(data)), data)
            with self.subTest(mismatch=field), self.assertRaises(driver.StudyError):
                self.session.reconstruct(changed, self.ctx, study, "canary")

    def test_canary_rows_cover_exact_frozen_cells(self):
        clock, memory = SessionClock(), SessionMemory(self.session, self.ctx)
        lease = self.session.Lease(clock)
        self.run_slot(clock, memory, 0, "canary", lease)
        self.run_slot(clock, memory, 1, "canary", lease)
        result, _ = self.run_slot(clock, memory, 2, "canary", self.session.Lease(clock))
        study = "canary-%d" % self.ctx["run_id"]
        self.assertEqual(self.session.reconstruct(memory, self.ctx, study, "canary")["observed_cells"], 189)
        changes = (lambda row: row.update(member="not-an-enrolled-synthetic-member"),
                   lambda row: row.update(slot=3), lambda row: row.update(slot=True),
                   lambda row: row.update(kind="report"), lambda row: row.update(vendor_request=True),
                   lambda row: row.update(scientific_evidence=True), lambda row: row.pop("member"))
        for change in changes:
            changed = copy.deepcopy(memory)
            part = changed.load(result)
            rows = copy.deepcopy(part["rows"])
            change(rows[0])
            with self.subTest(change=change), self.assertRaises(driver.StudyError):
                data = self.session.bundle_bytes(part["state"], rows, "result", self.ctx, "canary")
                changed.items[result] = (dict(changed.items[result][0], digest="sha256:" + driver.sha(data),
                                             size_in_bytes=len(data)), data)
                self.session.reconstruct(changed, self.ctx, study, "canary")
        part = memory.load(result)
        with self.assertRaises(driver.StudyError):
            data = self.session.bundle_bytes(part["state"], part["rows"] + [part["rows"][0]], "result", self.ctx, "canary")
            self.session.decode_bundle(data, self.ctx, self.ctx)

    def test_completed_run_requires_successful_conclusion(self):
        _, memory, ident, _ = self.active()
        for status, conclusion, accepted in (("in_progress", None, True), ("completed", "success", True),
                                              ("completed", None, False), ("completed", "unknown", False),
                                              ("completed", "failure", False), ("completed", "cancelled", False),
                                              ("in_progress", "success", False)):
            service, requests, transport = self.service(memory)
            with transport:
                original = service.request
                def response(path, binary=False):
                    value = original(path, binary)
                    if "/runs/" in path and "artifacts?" not in path:
                        value.update(status=status, conclusion=conclusion)
                    return value
                with patch.object(service, "request", side_effect=response), self.subTest(status=status, conclusion=conclusion):
                    if accepted:
                        self.assertEqual(service.load(ident)["state"]["status"], "active")
                    else:
                        with self.assertRaises(driver.StudyError):
                            service.load(ident)
                        self.assertFalse(any(binary for _, binary in requests), "bad run outcome must stop before ZIP")

    def test_run_attempt_boolean_is_not_integer_one(self):
        _, memory, ident, _ = self.active()
        for attempt in (1, True, False, 1.0, 0, 2, "1", None):
            service, requests, transport = self.service(memory)
            with transport:
                original = service.request
                def response(path, binary=False):
                    value = original(path, binary)
                    if "/runs/" in path and "artifacts?" not in path:
                        value["run_attempt"] = attempt
                    return value
                with patch.object(service, "request", side_effect=response), self.subTest(attempt=attempt, kind=type(attempt).__name__):
                    if type(attempt) is int and attempt == 1:
                        service.load(ident)
                    else:
                        with self.assertRaises(driver.StudyError):
                            service.load(ident)
                        self.assertFalse(any(binary for _, binary in requests), "bad attempt must stop before ZIP")
        part = memory.load(ident)
        for attempt in (True, 1.0):
            malformed = dict(self.ctx, attempt=attempt)
            with self.subTest(transport_attempt=attempt), self.assertRaises(driver.StudyError):
                data = self.session.bundle_bytes(part["state"], [], "result", malformed, "live")
                self.session.decode_bundle(data, malformed, self.ctx)

    def test_generated_explicit_workflow_is_manual_finite_default_canary_and_drift_guarded(self):
        generator = ROOT / ".github/scripts/render_w57_session_workflow.py"
        self.assertTrue(generator.is_file())
        spec = importlib.util.spec_from_file_location("session_workflow_generator", generator)
        render = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(render)
        data = render.render()
        self.assertEqual(data, render.render())
        self.assertEqual(data, (ROOT / driver.WORKFLOW).read_bytes())
        self.assertLess(len(data), 500000)
        text = data.decode("utf-8")
        self.assertNotIn("schedule:", text)
        self.assertNotIn("steps: &", text)
        self.assertNotIn("steps: *", text)
        self.assertNotIn("overwrite: true", text)
        self.assertIn("default: canary", text)
        self.assertIn("legacy-report", text)
        self.assertNotIn("--phase ${{", text)
        sys.path.insert(0, str(ROOT / "tests"))
        import test_workflow_runtime_pins as pins
        import test_deploy_gate as workflow
        self.assertEqual(pins.workflow_errors("rugcheck-w57.yml", text), [])
        jobs = workflow.jobs(text)
        self.assertLessEqual(len(jobs), 11)
        for lines in jobs.values():
            for line in lines:
                if line.strip().startswith("timeout-minutes:"):
                    self.assertLessEqual(int(line.split(":", 1)[1]), 330)
        self.assertEqual(render.main(["--check"]), 0)


class New192CoreTests(unittest.TestCase):
    """T-059: explicit new science; all omitted arguments retain LEGACY193."""

    def protocol(self):
        self.assertTrue(hasattr(driver, "START192_V1"), "T-059 explicit 192-start protocol is missing")
        return driver.START192_V1

    def memory(self, protocol=None):
        selected = self.protocol() if protocol is None else protocol

        class Store(MemoryArtifacts):
            def load(store, ident):
                store.reads.append(ident)
                meta, data = store.items[ident]
                if meta.get("expired"):
                    raise driver.StudyError("artifact_unavailable")
                return driver.decode_bundle(data, meta["provenance"], store.expected,
                                            protocol=meta.get("protocol", driver.LEGACY193))

            def publish(store, state, rows, kind, ctx):
                ident = max(store.items, default=0) + 1
                data = driver.bundle_bytes(state, rows, kind, ctx, protocol=selected)
                store.items[ident] = ({"id": ident, "name": driver.artifact_name(state, kind, ctx, protocol=selected),
                                       "expired": False, "provenance": copy.deepcopy(ctx), "protocol": selected}, data)
                return ident

        return Store()

    def job(self, phase, store, clock, ctx, study, pilot=None):
        protocol = self.protocol()
        plan = driver.prepare(phase, store, ctx, clock(), study=study, pilot_id=pilot, protocol=protocol)
        if plan["action"] == "idle":
            return None, [], plan
        if plan["action"] == "checkpoint":
            state, rows = plan["state"], []
        else:
            ident = store.publish(plan["state"], [], "intent", ctx)
            state, rows = driver.collect(plan, ident, store, ctx, clock, clock.sleep, protocol=protocol)
        ident = store.publish(state, rows, "result", ctx)
        return ident, rows, dict(plan, result_state=state)

    def active(self, count=60, failures=None):
        clock, store = Clock(), self.memory()
        fetch, calls = StudyTests().vendor(clock, count=count, failures=failures)
        with patch.object(probe, "curl", side_effect=fetch):
            pilot, pilot_rows, pilot_plan = self.job("pilot", store, clock, context(1), "new-pilot")
            if pilot_plan["result_state"]["status"] != "pilot_passed":
                return clock, store, pilot, pilot_rows, pilot_plan, calls
            result, rows, plan = self.job("start", store, clock, context(2), "new-study", pilot)
        return clock, store, result, rows, plan, calls

    def row(self, state, slot, elapsed, score=1, http="200", member=0):
        member = state["cohort"][member]
        row = driver._row({"http": http, "body": "ok" if http == "200" else "unavailable",
                           "score_normalised": score, "detectedAt": member["enrollment"]["detectedAt"],
                           "totalHolders": 0, "topHolders_n": 0, "gated": {}},
                          dict(state, phase="tick"), member["label"], member["mint"], state["started_at"] + elapsed, slot)
        row["request_started_at"] = state["started_at"] + elapsed
        return row

    def test_parent_legacy_characterization_and_immutable_explicit_capsules(self):
        protocol = self.protocol()
        fixture = json.loads((ROOT / "tests/fixtures/w57_legacy193_characterization.json").read_bytes())
        self.assertEqual(fixture["provenance"]["driver_lf_sha256"],
                         "7649040cb53bee691ea678d0c7876bda772d48ffc12fa5c04510715e31a3fe29")
        self.assertEqual(driver.protocol_descriptor(driver.LEGACY193), fixture["legacy_protocol"])
        self.assertEqual(driver.protocol_descriptor(protocol),
                         {"id": "w57-start192-v1", "schema": 3, "duration_seconds": 172800,
                          "interval_seconds": 900, "last_slot": 191, "planned_starts": 192,
                          "acquisition_grace_seconds": 0, "max_vendor_calls": 12351})
        self.assertEqual(driver.protocol_digest(protocol), driver.sha(driver.encoded(driver.protocol_descriptor(protocol))))
        with self.assertRaises(AttributeError):
            protocol.last_slot = 192
        for case in fixture["cases"]:
            state = copy.deepcopy(fixture["base_state"])
            state["slots"] = case["slots"]
            self.assertEqual(driver.readout(state, case["rows"]), case["expected"], case["name"])
            packed = driver.bundle_bytes(state, case["rows"], "result", context())
            self.assertEqual(driver.decode_bundle(packed, context(), context())["rows"], case["rows"])
        self.assertEqual((driver.SCHEMA, driver.DURATION, driver.INTERVAL, driver.LAST_SLOT, driver.MAX_VENDOR_CALLS),
                         (1, 172800, 900, 192, 12414))

    def test_new_state_and_bundle_refuse_unknown_mismatched_or_implicit_protocol(self):
        protocol = self.protocol()
        state = driver._new_state("new-state", "pilot", context(), EPOCH, protocol=protocol)
        self.assertEqual(state["schema"], 3)
        self.assertEqual(state["protocol"], driver.protocol_descriptor(protocol))
        self.assertEqual(state["protocol_digest"], driver.protocol_digest(protocol))
        for selection in (object(), protocol._replace(last_slot=192)):
            with self.assertRaises(driver.StudyError):
                driver._new_state("new-state", "pilot", context(), EPOCH, protocol=selection)
        for change in (lambda s: s.update(schema=1), lambda s: s.update(protocol_digest="e" * 64),
                       lambda s: s["protocol"].update(last_slot=192)):
            broken = copy.deepcopy(state)
            change(broken)
            with self.assertRaises(driver.StudyError):
                driver._validate_state(broken, protocol=protocol)
        data = driver.bundle_bytes(state, [], "intent", context(), protocol=protocol)
        self.assertEqual(driver.decode_bundle(data, context(), context(), protocol=protocol)["state"], state)
        with self.assertRaises(driver.StudyError):
            driver.decode_bundle(data, context(), context())
        self.assertEqual(driver.artifact_name(state, "intent", context(), protocol=protocol), "w57-intent-v3")

    def test_new_pilot_cohort_and_underpower_keep_original_qualification(self):
        clock, store, _, rows, plan, calls = self.active(count=40)
        state = plan["result_state"]
        self.assertEqual(state["status"], "active")
        self.assertEqual(len([m for m in state["cohort"] if m["group"] == "fresh"]), 40)
        self.assertEqual([m["mint"] for m in state["cohort"] if m["group"] == "control"], [m for _, m in probe.MAJORS])
        self.assertTrue(all(0 <= m["enrollment"]["age_minutes"] <= 10 for m in state["cohort"] if m["group"] == "fresh"))
        self.assertEqual(len(calls), 7 + 43)
        pilot = store.load(state["pilot"]["id"])
        self.assertEqual([r["mint"] for r in pilot["rows"] if r["kind"] == "report"], [m for _, m in probe.MAJORS[:6]])
        _, _, _, _, under, _ = self.active(count=39)
        self.assertEqual(under["result_state"]["status"], "insufficient_cohort")
        self.assertIsNone(under["result_state"]["started_at"])
        _, _, _, failed_rows, failed, failed_calls = self.active(failures={probe.MAJORS[2][1]: ("400", {})})
        self.assertEqual(failed["result_state"]["status"], "pilot_failed")
        self.assertEqual(len(failed_calls), 7)
        self.assertEqual(next(r for r in failed_rows if r.get("mint") == probe.MAJORS[2][1])["http"], "400")
        old_clock, old_store = Clock(), MemoryArtifacts()
        old_fetch, _ = StudyTests().vendor(old_clock)
        with patch.object(probe, "curl", side_effect=old_fetch):
            old_pilot, _, _ = StudyTests().job("pilot", old_store, old_clock, context(1), "old-pilot")
        new_store = self.memory()
        new_store.items = old_store.items
        with self.assertRaises(driver.StudyError), patch.object(probe, "curl", side_effect=AssertionError("Vendor")):
            driver.prepare("start", new_store, context(8), old_clock(), study="different-study", pilot_id=old_pilot,
                           protocol=self.protocol())

    def test_all_192_real_core_sweeps_complete_schedule_but_leave_endpoint_censored(self):
        protocol = self.protocol()
        clock, store, _, _, initial, _ = self.active()
        start = initial["result_state"]["started_at"]
        calls = []
        def vendor(url):
            calls.append(clock())
            return "200", {"score_normalised": 1, "detectedAt": stamp(start - 60), "topHolders": [], "totalHolders": 0}
        with patch.object(probe, "curl", side_effect=vendor):
            for slot in range(192):
                clock.value = start + slot * 900
                _, rows, current = self.job("tick", store, clock, context(slot + 3), "new-study")
                self.assertEqual(current["state"]["slot"], slot)
                self.assertEqual(rows[0]["request_started_at"], start + slot * 900)
                self.assertTrue(all(row["ts"] <= start + 172800 for row in rows))
        state = current["result_state"]
        self.assertEqual(state["status"], "completed")
        self.assertEqual([s["slot"] for s in state["slots"]], list(range(192)))
        self.assertEqual(len(calls), 192 * 63)
        answer = driver.reconstruct(store, context(), "new-study", protocol=protocol)
        self.assertEqual(answer["coverage"]["fresh"]["scheduled_slots"], 192)
        self.assertEqual(answer["expected_score_cells"], 45 * 192)
        self.assertTrue(answer["planned_schedule_complete"])
        self.assertTrue(answer["all_score_cells_usable"])
        self.assertTrue(answer["endpoint_right_censored"])
        self.assertTrue(answer["censored"])
        self.assertFalse(answer["negative_tail_established"])
        self.assertEqual(answer["proposal"], "no_flip_observed")
        self.assertLess(answer["data_horizon_at"], state["ends_at"])
        self.assertEqual(set(answer["last_usable_at"]), {m["mint"] for m in state["cohort"]})
        invalid = copy.deepcopy(state)
        invalid["slots"].append({"slot": 192, "status": "observed"})
        with self.assertRaises(driver.StudyError):
            driver._validate_state(invalid, protocol=protocol)
        invalid["slots"] = [{"slot": True, "status": "observed"}]
        with self.assertRaises(driver.StudyError):
            driver._validate_state(invalid, protocol=protocol)

    def test_strict_completion_deadline_retains_boundary_overrun_and_unattempted_cells(self):
        protocol = self.protocol()
        for remaining, duration, expected_calls, usable in ((31, 0, 0, 0), (32, 32, 1, 1), (32, 33, 1, 0)):
            with self.subTest(remaining=remaining, duration=duration):
                clock, store, _, _, initial, _ = self.active()
                end = initial["result_state"]["ends_at"]
                clock.value = end - remaining
                calls = []
                def vendor(url):
                    calls.append(clock())
                    clock.sleep(duration)
                    return "200", {"score_normalised": 1, "detectedAt": stamp(end - 172860)}
                with patch.object(probe, "curl", side_effect=vendor):
                    _, rows, final = self.job("tick", store, clock, context(9), "new-study")
                self.assertEqual(len(calls), expected_calls)
                answer = driver.readout(final["result_state"], rows, protocol=protocol)
                self.assertEqual(answer["observed_score_cells"], usable)
                self.assertEqual(answer["coverage"]["fresh"]["attempted_cells"], expected_calls)
                if expected_calls:
                    self.assertEqual(rows[0]["outside_window"], duration > remaining)
                    self.assertEqual(rows[1]["body"], "not_observed")
                self.assertTrue(answer["endpoint_right_censored"])

    def test_fields_missing_requests_and_censoring_keep_separate_fixed_denominators(self):
        _, _, _, _, initial, _ = self.active()
        state = dict(initial["result_state"], phase="tick", slots=[{"slot": 0, "status": "partial"}])
        rows = [self.row(state, 0, 1), self.row(state, 0, 2, 80, "400", 1), self.row(state, 0, 3, None, "200", 2)]
        answer = driver.readout(state, rows, protocol=self.protocol())
        fields = answer["coverage"]["fresh"]["fields"]
        self.assertEqual(fields["score_normalised"], {"usable": 1, "attempted_unavailable_or_invalid": 2,
                                                     "outside_window": 0, "never_attempted": 45 * 192 - 3})
        self.assertEqual(fields["permanentDelegate"]["usable"], 0)
        self.assertEqual(answer["coverage"]["fresh"]["attempted_failed_requests"], 1)
        self.assertEqual(answer["coverage"]["control"]["expected_cells"], 18 * 192)
        self.assertFalse(answer["planned_schedule_complete"])
        self.assertFalse(answer["all_score_cells_usable"])
        self.assertEqual(answer["proposal"], "inconclusive")

    def test_crossing_intervals_keep_wall_tenth_latest_flip_and_left_lower_bound(self):
        _, _, _, _, initial, _ = self.active()
        state = dict(initial["result_state"], phase="tick")
        rows = [self.row(state, 170, 154000), self.row(state, 176, 158400, 80)]
        answer = driver.readout(state, rows, protocol=self.protocol())
        self.assertEqual(answer["final_tenth_start"], state["started_at"] + 155520)
        self.assertEqual(answer["latest_flip"]["tail_location"], "ambiguous")
        self.assertEqual(answer["proposal"], "inconclusive")
        rows = [self.row(state, 176, 158400), self.row(state, 177, 159300, 20)]
        answer = driver.readout(state, rows, protocol=self.protocol())
        self.assertEqual(answer["proposal"], "different_rule_e14_review")
        origin_lag = (state["started_at"] - state["cohort"][0]["enrollment"]["ts"] + 60) / 60
        self.assertEqual(answer["latest_flip"]["lower_bound_minutes"], 2640 + origin_lag)
        self.assertEqual(answer["latest_flip"]["index_age_interval_minutes"], [2640 + origin_lag, 2655 + origin_lag])
        mismatched = copy.deepcopy(rows)
        mismatched[-1]["detectedAt"] = stamp(state["started_at"] - 60)
        self.assertIsNone(driver.readout(state, mismatched, protocol=self.protocol())["latest_flip"]["lower_bound_minutes"])
        rows = [self.row(state, 2, 1800), self.row(state, 3, 2700, 50)]
        answer = driver.readout(state, rows, protocol=self.protocol())
        self.assertEqual(answer["proposal"], "larger_window_lower_bound_with_censoring")
        self.assertEqual(answer["proposed_lower_bound_minutes"], 30 + origin_lag)

    def test_new_protocol_source_clock_and_call_ceiling_fail_before_vendor(self):
        protocol = self.protocol()
        clock, store, _, _, initial, _ = self.active()
        plan = driver.prepare("tick", store, context(3), clock(), study="new-study", protocol=protocol)
        ident = store.publish(plan["state"], [], "intent", context(3))
        for change in (lambda p: p["state"].update(protocol_digest="f" * 64),
                       lambda p: p["state"].update(ends_at=p["state"]["ends_at"] + 1)):
            broken = copy.deepcopy(plan)
            change(broken)
            with self.assertRaises(driver.StudyError), patch.object(probe, "curl", side_effect=AssertionError("Vendor")):
                driver.collect(broken, ident, store, context(3), clock, clock.sleep, protocol=protocol)
        with self.assertRaises(driver.StudyError), patch.object(probe, "curl", side_effect=AssertionError("Vendor")):
            driver.collect(plan, ident, store, dict(context(3), source=dict(context()["source"], driver="e" * 64)),
                           clock, clock.sleep, protocol=protocol)
        exhausted = copy.deepcopy(plan)
        exhausted["state"]["requests"] = {"rugcheck": 12351, "gecko": 0}
        capped = self.memory()
        capped_id = capped.publish(exhausted["state"], [], "intent", context(3))
        with patch.object(probe, "curl", side_effect=AssertionError("Vendor")):
            state, rows = driver.collect(exhausted, capped_id, capped, context(3), clock, clock.sleep, protocol=protocol)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["requests"], {"rugcheck": 12351, "gecko": 0})

    def test_a2_legacy_markers_are_rejected_before_decode_or_collection(self):
        fixture = json.loads((ROOT / "tests/fixtures/w57_legacy193_characterization.json").read_bytes())
        genuine = copy.deepcopy(fixture["base_state"])
        genuine["slot"] = 0
        driver._validate_state(genuine)
        packed = driver.bundle_bytes(genuine, [], "intent", context())
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            original = {name: archive.read(name) for name in archive.namelist()}
        descriptor = driver.protocol_descriptor(self.protocol())
        markers = ({"protocol": descriptor, "protocol_digest": "f" * 64},
                   {"protocol": dict(descriptor, id="unknown-protocol"), "protocol_digest": "f" * 64},
                   {"protocol_digest": "f" * 64})
        for marker in markers:
            with self.subTest(marker=marker):
                marked = dict(genuine, **marker)
                with self.assertRaises(driver.StudyError):
                    driver._validate_state(marked)
                with self.assertRaises(driver.StudyError):
                    driver.bundle_bytes(marked, [], "intent", context())
                files = dict(original, **{"state.json": driver.encoded(marked)})
                manifest = json.loads(files["manifest.json"])
                manifest["files"]["state.json"] = driver.sha(files["state.json"])
                files["manifest.json"] = driver.encoded(manifest)
                target = io.BytesIO()
                with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                    for name, data in files.items():
                        archive.writestr(name, data)
                with self.assertRaises(driver.StudyError):
                    driver.decode_bundle(target.getvalue(), context(), context())
                class RawStore:
                    def load(self, ident):
                        return {"state": marked, "manifest": {"kind": "intent", "context": context()}, "digest": "e" * 64}
                plan = {"action": "collect", "state": marked, "phase": "tick", "prepared_at": EPOCH}
                with patch.object(probe, "curl", side_effect=AssertionError("Vendor")) as vendor:
                    with self.assertRaises(driver.StudyError):
                        driver.collect(plan, 1, RawStore(), context(), Clock(), lambda seconds: None)
                    self.assertEqual(vendor.call_count, 0)
        # A marker on the manifest alone is also a conflicting legacy envelope.
        manifest = json.loads(original["manifest.json"])
        manifest.update(protocol=descriptor, protocol_digest="f" * 64)
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in dict(original, **{"manifest.json": driver.encoded(manifest)}).items():
                archive.writestr(name, data)
        with self.assertRaises(driver.StudyError):
            driver.decode_bundle(target.getvalue(), context(), context())
        self.assertEqual(driver.decode_bundle(packed, context(), context())["state"], genuine)

    def test_a2_clock_backwards_or_nonfinite_stops_and_retains_attempt_evidence(self):
        protocol = self.protocol()
        for bad_at in (1, 2):
            for fault in ("backward", "nan", "infinity"):
                with self.subTest(fault=fault, bad_at=bad_at):
                    clock, store, _, _, initial, _ = self.active()
                    start = initial["result_state"]["started_at"]
                    ctx = context(3)
                    plan = driver.prepare("tick", store, ctx, clock(), study="new-study", protocol=protocol)
                    ident = store.publish(plan["state"], [], "intent", ctx)
                    earlier = {key: value[1] for key, value in store.items.items()}
                    calls = []
                    def vendor(url):
                        calls.append(clock())
                        if len(calls) == bad_at:
                            clock.value = start - 100 if fault == "backward" else float("nan" if fault == "nan" else "inf")
                        return "200", {"score_normalised": 1, "detectedAt": plan["state"]["cohort"][0]["enrollment"]["detectedAt"]}
                    with patch.object(probe, "curl", side_effect=vendor):
                        state, rows = driver.collect(plan, ident, store, ctx, clock, clock.sleep, protocol=protocol)
                    self.assertEqual(len(calls), bad_at)
                    self.assertEqual(state["status"], "failed")
                    self.assertEqual(state["failure"], "clock_changed")
                    self.assertEqual(len(rows), bad_at)
                    uncertain = rows[-1]
                    self.assertEqual(uncertain["timing_state"], "uncertain")
                    self.assertEqual(uncertain["http"], "200")
                    self.assertIsNone(uncertain["score_normalised"])
                    self.assertTrue(driver.number(uncertain["request_started_at"]))
                    self.assertEqual(uncertain["ts"], start - 100 if fault == "backward" else None)
                    answer = driver.readout(state, rows, protocol=protocol)
                    self.assertEqual(answer["observed_score_cells"], bad_at - 1)
                    self.assertEqual(answer["coverage"]["fresh"]["attempted_cells"], bad_at)
                    self.assertEqual(answer["coverage"]["fresh"]["attempted_failed_requests"], 0)
                    self.assertEqual(answer["coverage"]["fresh"]["timing_uncertain_cells"], 1)
                    packed = driver.bundle_bytes(state, rows, "result", ctx, protocol=protocol)
                    self.assertEqual(driver.decode_bundle(packed, ctx, context(), protocol=protocol)["rows"], rows)
                    self.assertEqual({key: value[1] for key, value in store.items.items()}, earlier)
        # A backwards step in pacing is detected before another physical call.
        clock, store, _, _, _, _ = self.active()
        ctx, calls = context(3), []
        plan = driver.prepare("tick", store, ctx, clock(), study="new-study", protocol=protocol)
        ident = store.publish(plan["state"], [], "intent", ctx)
        def pacing(seconds):
            clock.sleep(seconds)
            clock.value -= 100
        def valid(url):
            calls.append(clock())
            return "200", {"score_normalised": 1, "detectedAt": plan["state"]["cohort"][0]["enrollment"]["detectedAt"]}
        with patch.object(probe, "curl", side_effect=valid):
            state, rows = driver.collect(plan, ident, store, ctx, clock, pacing, protocol=protocol)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(state["failure"], "clock_changed")
        self.assertEqual(driver.readout(state, rows, protocol=protocol)["observed_score_cells"], 1)

    def test_new_lost_intent_and_partial_finalize_preserve_chain_without_replay(self):
        protocol = self.protocol()
        clock, store, _, _, initial, _ = self.active()
        ctx = context(3)
        plan = driver.prepare("tick", store, ctx, clock(), study="new-study", protocol=protocol)
        ident = store.publish(plan["state"], [], "intent", ctx)
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            driver.write_bundle(out / "intent", plan["state"], [], "intent", ctx, protocol=protocol)
            driver.write_bundle(out / "result", dict(plan["state"], status="lost_checkpoint"), [], "result", ctx, protocol=protocol)
            row = self.row(plan["state"], 0, 1)
            (out / "result/observations.jsonl").write_bytes(driver.encoded(row) + b"\n")
            (out / "plan.json").write_bytes(driver.encoded(plan))
            (out / "collection.json").write_bytes(driver.encoded({"id": ident}))
            with patch.object(probe, "curl", side_effect=AssertionError("Vendor")):
                driver.finalize(out, ctx, protocol=protocol)
            state = json.loads((out / "result/state.json").read_bytes())
            rows = [json.loads(line) for line in (out / "result/observations.jsonl").read_bytes().splitlines()]
            self.assertEqual(state["status"], "failed")
            self.assertEqual(rows, [row])
            self.assertEqual(state["protocol_digest"], driver.protocol_digest(protocol))
            self.assertEqual(driver.decode_bundle(driver.bundle_bytes(state, rows, "result", ctx, protocol=protocol),
                                                 ctx, context(), protocol=protocol)["rows"], rows)
        clock.sleep(900)
        with patch.object(probe, "curl", side_effect=AssertionError("replay")):
            _, _, result = self.job("tick", store, clock, context(4), "new-study")
        self.assertEqual(result["result_state"]["status"], "lost_checkpoint")
        answer = driver.reconstruct(store, context(), "new-study", protocol=protocol)
        self.assertEqual(answer["proposal"], "inconclusive")
        self.assertTrue(answer["endpoint_right_censored"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
