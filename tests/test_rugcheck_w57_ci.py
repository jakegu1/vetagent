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
        self.assertEqual(answer["proposal"], "different_rule_e14_review")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
