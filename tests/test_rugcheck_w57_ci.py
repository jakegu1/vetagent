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
        self.assertIn("*/15 * * * *", text)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
