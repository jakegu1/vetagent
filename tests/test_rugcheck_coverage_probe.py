"""T-040: coverage observations require real UTC ages and usable upstream evidence.

All reports, refusals and transport results below are synthetic. No upstream is called.
Run: python tests/test_rugcheck_coverage_probe.py
"""
import contextlib
import copy
import datetime
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("coverage_probe", ROOT / "bench/rugcheck_coverage_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 19, 12, 0, 0, 500000, tzinfo=UTC)
STAMP = "2026-10-19T11:55:00.500000Z"
MINT = "synthetic-mint-" + "a" * 32
INVALID_SCORES = (True, False, float("nan"), float("inf"), float("-inf"),
                  -1, "1", {}, [], "unavailable")


def no_network(*args, **kwargs):
    raise AssertionError("coverage-probe acceptance prohibits external transport")


def valid_body(holders=True):
    body = {"score_normalised": 80, "totalHolders": 1200, "detectedAt": STAMP,
            "risks": [{"name": "Synthetic concern", "level": "danger"}]}
    if holders:
        body["topHolders"] = [{"pct": 1.0}]
    return body


def row(mint="synthetic-primary", sweep=1, score=80, holders=1, **fields):
    result = {"mint": mint, "label": mint, "http": "200", "body": "ok",
              "ts": NOW.timestamp() + (sweep - 1) * 60, "sweep": sweep,
              "topHolders_n": holders, "totalHolders": 1200,
              "score_normalised": score, "detectedAt": STAMP,
              "gated": {"permanentDelegate": True}}
    result.update(fields)
    return result


class CoverageProbeContract(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(socket, "create_connection", no_network))
        self.stack.enter_context(patch.object(socket.socket, "connect", no_network))
        self.stack.enter_context(patch.object(probe.subprocess, "run", no_network))

    def capture_report(self, rows):
        with tempfile.TemporaryDirectory(prefix="coverage-contract-") as directory:
            path = Path(directory) / "synthetic.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = probe.report(str(path))
            return result, output.getvalue()

    def test_equivalent_offsets_and_fractional_seconds_have_the_same_real_age(self):
        stamps = (STAMP, "2026-10-19T11:55:00.500000+00:00",
                  "2026-10-19T17:25:00.500000+05:30",
                  "2026-10-19T06:55:00.500000-05:00",
                  "2026-10-19T11:55:00.500000")
        for stamp in stamps:
            with self.subTest(stamp=stamp):
                self.assertAlmostEqual(probe.age_minutes(stamp, NOW), 5.0, places=10)
        self.assertAlmostEqual(probe.age_minutes("2026-10-19T11:55:00Z", NOW),
                               5.0 + 0.5 / 60, places=10)

    def test_invalid_timestamps_are_unobserved_and_future_ages_are_negative(self):
        for stamp in (None, "", "not-a-time", "2026-02-30T12:00:00Z",
                      "2026-10-19T11:55:00junk", "2026-10-19T11:55:00+99:00"):
            with self.subTest(stamp=stamp):
                self.assertIsNone(probe.age_minutes(stamp, NOW))
        self.assertLess(probe.age_minutes("2026-10-19T12:01:00.500000Z", NOW), 0)

    def test_recruitment_uses_the_same_closed_nonnegative_age_window(self):
        cases = (("2026-10-19T07:00:00.500000-05:00", True),
                 ("2026-10-19T17:20:00.500000+05:30", True),
                 ("2026-10-19T11:50:00.499999Z", False),
                 ("2026-10-19T12:00:00.500001Z", False),
                 ("2026-10-19T17:31:00.500000+05:30", False),
                 ("invalid", False))
        original_age = probe.age_minutes
        listing = {"data": [{"relationships": {"base_token": {"data": {
            "id": "solana_" + MINT}}}, "attributes": {"name": "Synthetic"}}]}
        for stamp, expected in cases:
            with self.subTest(stamp=stamp), contextlib.redirect_stdout(io.StringIO()), \
                    patch.object(probe, "curl", return_value=("200", listing)), \
                    patch.object(probe, "observe", return_value=row(mint=MINT, detectedAt=stamp)), \
                    patch.object(probe, "age_minutes", side_effect=lambda value: original_age(value, NOW)), \
                    patch.object(probe.time, "sleep", return_value=None):
                self.assertEqual(probe.recruit_fresh(1, 10.0, pages=1, gap=0),
                                 [("Synthetic", MINT)] if expected else [])

    def test_retrospective_score_cohort_cannot_recruit_future_or_invalid_times(self):
        cases = (("2026-10-19T07:00:00.500000-05:00", 1),
                 ("2026-10-19T17:20:00.500000+05:30", 1),
                 ("2026-10-19T11:50:00.499999Z", 0),
                 ("2026-10-19T12:00:00.500001Z", 0),
                 ("invalid", 0))
        for stamp, expected in cases:
            output = io.StringIO()
            with self.subTest(stamp=stamp), contextlib.redirect_stdout(output):
                probe._score_verdict({"synthetic": [row(detectedAt=stamp)]})
                self.assertIn("cohort: %d mints caught within 10 min" % expected,
                              output.getvalue())

    def test_curl_preserves_status_for_empty_malformed_and_refused_json(self):
        for raw, status, body in (("\n200", "200", None),
                                  ("not-json\n200", "200", None),
                                  ('{"error":"refused"}\n429', "429", {"error": "refused"}),
                                  ("", "0", None)):
            with self.subTest(raw=raw), patch.object(probe.subprocess, "run",
                    return_value=types.SimpleNamespace(stdout=raw, returncode=0)) as transport:
                self.assertEqual(probe.curl("https://synthetic.invalid/report"), (status, body))
                self.assertEqual(transport.call_count, 1)

    def test_refused_and_transport_failed_requests_never_become_report_observations(self):
        for code, body in (("429", valid_body()), ("503", valid_body(False)),
                           ("000", valid_body()), ("0", None),
                           ("429", {"error": "quota"}), ("503", {"error": "unavailable"})):
            with self.subTest(code=code, body=body), \
                    patch.object(probe, "curl", return_value=(code, body)), \
                    patch.object(probe.time, "time", return_value=NOW.timestamp()):
                observation = probe.observe("Synthetic", MINT, "scores")
                self.assertEqual((observation["http"], observation["ts"], observation["mint"],
                                  observation["label"]), (code, NOW.timestamp(), MINT, "Synthetic"))
                self.assertNotEqual(observation.get("body"), "ok")

    def test_http_200_empty_scalar_list_and_error_only_bodies_are_not_reports(self):
        bodies = (None, {}, [], [valid_body()], True, 42, "report",
                  {"error": "quota"}, {"message": "unavailable", "statusCode": 503},
                  {"errors": ["upstream failed"]}, {"status": "error"})
        for body in bodies:
            with self.subTest(body=body), patch.object(probe, "curl", return_value=("200", body)), \
                    patch.object(probe.time, "time", return_value=NOW.timestamp()):
                observation = probe.observe("Synthetic", MINT, "holders")
                self.assertEqual((observation["http"], observation["ts"], observation["mint"],
                                  observation["label"]), ("200", NOW.timestamp(), MINT, "Synthetic"))
                self.assertNotEqual(observation.get("body"), "ok")

    def test_valid_holder_presence_empty_list_and_absence_are_observable(self):
        for holder_field, expected in (([{}], 1), ([], 0), (None, -1)):
            body = valid_body(False)
            if holder_field is not None:
                body["topHolders"] = holder_field
            for mode in ("holders", "scores"):
                with self.subTest(holders=holder_field, mode=mode), \
                        patch.object(probe, "curl", return_value=("200", body)):
                    observation = probe.observe("Synthetic", MINT, mode)
                    self.assertEqual(observation["body"], "ok")
                    self.assertEqual(observation["topHolders_n"], expected)
                    self.assertEqual(observation["score_normalised"], 80)
                    if mode == "scores":
                        self.assertEqual(observation["risks"], body["risks"])

    def test_score_bands_accept_only_finite_nonnegative_numeric_evidence(self):
        for value, expected in ((0, "ok"), (5, "ok"), (19.9, "ok"),
                                (20, "warn"), (49.9, "warn"), (50, "critical"),
                                (100, "critical"), (None, None)):
            with self.subTest(value=value):
                self.assertEqual(probe.band(value), expected)
        for value in INVALID_SCORES:
            with self.subTest(invalid=value):
                self.assertIsNone(probe.band(value))

    def test_unreadable_score_keeps_the_separately_valid_holder_observation(self):
        for value in INVALID_SCORES:
            body = valid_body()
            body["score_normalised"] = value
            with self.subTest(value=value), patch.object(probe, "curl", return_value=("200", body)):
                observation = probe.observe("Synthetic", MINT, "scores")
                self.assertEqual(observation["body"], "ok")
                self.assertEqual(observation["topHolders_n"], 1)
                raw = observation.get("score_normalised")
                if isinstance(value, float) and math.isnan(value):
                    self.assertTrue(isinstance(raw, float) and math.isnan(raw))
                else:
                    self.assertEqual(raw, value)
                self.assertIsNone(probe.band(raw))

    def test_mixed_historical_report_excludes_old_ok_refusals_from_every_denominator(self):
        rows = [row(), row(sweep=2),
                row(sweep=3, score=1, holders=-1, http="429"),
                row(sweep=4, score=1, holders=-1, http="503"),
                row(sweep=5, score=1, holders=-1, body="empty"),
                {"mint": "synthetic-empty", "label": "Empty", "http": "200", "body": "ok",
                 "ts": NOW.timestamp(), "sweep": 1}]
        result, output = self.capture_report(rows)
        self.assertEqual(result, 0)
        self.assertIn("1 mints x 2 sweeps = 2 observations", output)
        self.assertIn("2 of 6 requests non-200", output)
        self.assertRegex(output, r"4 of 6 requests unavailable")
        self.assertIn("mints whose holder coverage changed: 0", output)
        self.assertIn("mints whose score_normalised moved: 0", output)
        self.assertIn("cohort: 1 mints caught within 10 min", output)

    def test_all_unusable_historical_files_cannot_exit_as_a_successful_study(self):
        cases = ([row(http="429")], [row(http="503")], [row(body="empty")],
                 [{"mint": "synthetic-empty", "label": "Empty", "http": "200", "body": "ok",
                   "ts": NOW.timestamp(), "sweep": 1}],
                 [row(http="000"), row(sweep=2, body="invalid")], [])
        for rows in cases:
            with self.subTest(rows=rows):
                result, output = self.capture_report(rows)
                self.assertNotEqual(result, 0)
                self.assertIn("no usable rows", output)
                self.assertNotIn("VERDICT:", output)

    def test_retry_agreement_needs_a_usable_primary_for_the_same_mint_and_sweep(self):
        rows = [row(), row(immediate_retry=True),
                row(sweep=2, body="empty"), row(sweep=2, immediate_retry=True),
                row(mint="synthetic-orphan", immediate_retry=True),
                row(sweep=9, immediate_retry=True),
                row(http="429", immediate_retry=True),
                row(mint="synthetic-absent", holders=-1),
                row(mint="synthetic-absent", holders=-1, immediate_retry=True),
                row(mint="synthetic-absent", sweep=2, holders=-1),
                row(mint="synthetic-absent", sweep=2, holders=1, immediate_retry=True)]
        result, output = self.capture_report(rows)
        self.assertEqual(result, 0)
        self.assertIn("immediate retries agreeing with their own sweep: 2 of 3", output)
        self.assertIn("3 observations", output)

    def test_valid_absence_coverage_flip_score_change_and_oscillation_still_report(self):
        rows = [row(mint="synthetic-changing", sweep=1, score=80, holders=-1),
                row(mint="synthetic-changing", sweep=2, score=1, holders=2),
                row(mint="synthetic-changing", sweep=3, score=80, holders=2),
                row(mint="synthetic-absent", holders=-1),
                row(mint="synthetic-absent", holders=-1, immediate_retry=True)]
        result, output = self.capture_report(rows)
        self.assertEqual(result, 0)
        self.assertIn("2 mints x 3 sweeps = 4 observations", output)
        self.assertIn("sweep 1    0 of  2 carry a holder list", output)
        self.assertIn("mints whose holder coverage changed: 1", output)
        self.assertIn("mints whose score_normalised moved: 1", output)
        self.assertIn("FIRE CONDITION: 1 of 2 fresh mints left a band and returned", output)
        self.assertIn("immediate retries agreeing with their own sweep: 1 of 1", output)

    def test_invalid_score_cannot_create_a_historical_move_or_clean_score_conclusion(self):
        for value in INVALID_SCORES:
            rows = [row(sweep=1), row(sweep=2, score=value), row(sweep=3)]
            with self.subTest(value=value):
                original = copy.deepcopy(rows)
                result, output = self.capture_report(rows)
                self.assertEqual(result, 0)
                self.assertIn("3 observations", output)
                self.assertIn("mints whose score_normalised moved: 0", output)
                self.assertIn("fresh mints that read <=5 in at least one sweep: 0 of 1", output)
                self.assertIn("FIRE CONDITION: 0 of 1 fresh mints left a band and returned", output)
                self.assertEqual(rows[0], original[0])
                self.assertEqual(rows[-1], original[-1])

    def test_frozen_historical_reference_and_preregistered_constants_stay_intact(self):
        historical = ROOT / "bench/rugcheck_scores_rerun.jsonl"
        committed_bytes = historical.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(committed_bytes).hexdigest(),
                         "4afc84daa5bd6fd930fcfcf464f18a806f506a55be32a11fd58779f10c17c961")
        self.assertEqual(probe.BANDS, ((50, "critical"), (20, "warn"), (0, "ok")))
        self.assertEqual(probe.ESTABLISHED_AT, 5)
        captured = []
        with patch.object(probe, "run_probe", side_effect=lambda args: captured.append(args) or 0):
            self.assertEqual(probe.main(["--mode", "scores"]), 0)
        self.assertEqual((captured[0].min_fresh, captured[0].max_age_min), (40, 10.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
