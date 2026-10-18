"""Bounded read-only operational observations, never a user or cold-start verdict.

Default invocation sends no requests. Use --offline FIXTURE for deterministic fixture
evaluation, or explicitly --live in CI with the existing read credentials. Only the
aggregate JSON is retained, including when collection fails.

SQL dialect/sampling: developers.cloudflare.com/analytics/analytics-engine/sql-api/
Minute buckets: analytics-engine/sql-reference/date-time-functions/#tostartofinterval
Documented retention is three months; the requested lookback is capped at 90 days.
An actual successful upload step is a time anchor, not proof of an instance cold start.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROW_CAP = 512
INVENTORY_CAP = 20
QUERY_CAP = 42
REQUEST_CAP = 64
REQUEST_TIMEOUT = 10
BYTE_CAP = 1024 * 1024
RELEASE_RUN = 39055170209
DATASET = "vetagent_calls"
TOOLS = {"find_new_hot_pools": ("ok", "partial", ""),
         "assess_token_risk": ("low", "medium", "high", "unknown")}
COHORTS = ("self", "other")
ROW_KEYS = {"tool", "verdict", "cohort", "minute", "weighted_count",
            "sampled_rows", "max_sample_interval"}


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:T| )\d{2}:\d{2}:\d{2}(?:Z)?", value):
        raise ValueError("invalid_time")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)


def _iso(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("invalid_count")
    if isinstance(value, str) and (len(value) > 32 or not re.fullmatch(r"\d+(?:\.0+)?", value)):
        raise ValueError("invalid_count")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.to_integral_value() or number > 10 ** 15:
            raise ValueError("invalid_count")
        return int(number)
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("invalid_count") from exc


def _body(reply):
    if not isinstance(reply, dict) or type(reply.get("http_status")) is not int:
        return "malformed", None
    status = reply["http_status"]
    if reply.get("error") == "response_too_large":
        return "truncated", None
    if status == 0:
        return "transport_error", None
    if 300 <= status < 400:
        return "redirect", None
    if status != 200:
        return "http_error", None
    body = reply.get("body")
    if not isinstance(body, dict) or body.get("success") is False or body.get("errors"):
        return "malformed", None
    return "observed", body


def _unavailable(state):
    return {"state": state, "rows": [], "weighted_count": None, "sampled_rows": None,
            "sampled": None, "count_label": "weighted events; not exact users"}


def aggregate_reply(reply, *, tool, cohort, start, end):
    """Validate fixed aggregate cells; never copy unknown keys or error strings."""
    if tool not in TOOLS or cohort not in COHORTS:
        raise ValueError("invalid_aggregate_selection")
    lower, upper = _time(start), _time(end)
    if lower >= upper:
        raise ValueError("invalid_window")
    state, body = _body(reply)
    if body is None:
        return _unavailable(state)
    rows = body.get("data")
    if not isinstance(rows, list):
        return _unavailable("malformed")
    if len(rows) > ROW_CAP:
        return _unavailable("truncated")
    try:
        if "rows" in body and _count(body["rows"]) != len(rows):
            raise ValueError("invalid_row_count")
        if "rows_before_limit" in body and _count(body["rows_before_limit"]) > len(rows):
            return _unavailable("truncated")
        clean, seen = [], set()
        weighted, stored, sampled = 0, 0, False
        for row in rows:
            if not isinstance(row, dict) or set(row) != ROW_KEYS:
                raise ValueError("invalid_row")
            if row["tool"] != tool or row["cohort"] != cohort or row["verdict"] not in TOOLS[tool]:
                raise ValueError("invalid_enum")
            minute = _time(row["minute"])
            if minute.second or minute >= upper or minute + timedelta(minutes=1) <= lower:
                raise ValueError("invalid_bucket")
            key = (minute, row["verdict"])
            if key in seen:
                raise ValueError("duplicate_cell")
            seen.add(key)
            n, count, interval = (_count(row[k]) for k in
                                  ("weighted_count", "sampled_rows", "max_sample_interval"))
            if count < 1 or interval < 1 or not count + interval - 1 <= n <= count * interval:
                raise ValueError("inconsistent_counts")
            weighted += n
            stored += count
            sampled = sampled or interval > 1
            clean.append({"tool": tool, "verdict": row["verdict"], "cohort": cohort,
                          "minute": _iso(minute), "weighted_count": n,
                          "sampled_rows": count, "max_sample_interval": interval})
        return {"state": "observed" if clean else "empty", "rows": sorted(
                    clean, key=lambda r: (r["minute"], r["verdict"])),
                "weighted_count": weighted, "sampled_rows": stored, "sampled": sampled,
                "count_label": "weighted events; not exact users"}
    except (ValueError, TypeError, KeyError, OverflowError):
        return _unavailable("malformed")


def query_sql(tool, cohort, start, end):
    """Only fixed enums and parsed time literals enter the query; no caller output."""
    if tool not in TOOLS or cohort not in COHORTS:
        raise ValueError("invalid_aggregate_selection")
    lower, upper = _time(start), _time(end)
    if not lower < upper <= lower + timedelta(days=90):
        raise ValueError("invalid_window")
    where_self = "LIKE" if cohort == "self" else "NOT LIKE"
    verdicts = ", ".join("'%s'" % value for value in TOOLS[tool])
    return (
        "SELECT blob2 AS tool, blob3 AS verdict, '%s' AS cohort, "
        "toStartOfInterval(timestamp, INTERVAL '1' MINUTE) AS minute, "
        "SUM(_sample_interval) AS weighted_count, COUNT() AS sampled_rows, "
        "MAX(_sample_interval) AS max_sample_interval FROM %s "
        "WHERE timestamp >= toDateTime('%s') AND timestamp < toDateTime('%s') "
        "AND blob2 = '%s' AND blob3 IN (%s) AND blob4 %s 'vetagent-%%' "
        "GROUP BY tool, verdict, minute ORDER BY minute, verdict LIMIT %d FORMAT JSON"
    ) % (cohort, DATASET, lower.strftime("%Y-%m-%d %H:%M:%S"),
         upper.strftime("%Y-%m-%d %H:%M:%S"), tool, verdicts, where_self, ROW_CAP + 1)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, *, data=None, headers=None, opener=None):
    """A capped HTTPS read request, with redirects and raw diagnostics suppressed."""
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in ("api.cloudflare.com", "api.github.com")
                or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
            return {"http_status": 0, "error": "invalid_endpoint"}
        request = urllib.request.Request(url, data=data, headers=headers or {},
                                         method="POST" if data is not None else "GET")
        client = opener or urllib.request.build_opener(NoRedirect())
        with client.open(request, timeout=REQUEST_TIMEOUT) as response:
            status = response.status
            if status != 200:
                return {"http_status": status}
            raw = response.read(BYTE_CAP + 1)
            if len(raw) > BYTE_CAP:
                return {"http_status": status, "error": "response_too_large"}
            try:
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError):
                return {"http_status": status, "body": None}
            return {"http_status": status, "body": body}
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code}
    except (OSError, ValueError, urllib.error.URLError):
        return {"http_status": 0, "error": "transport"}


class LiveSource:
    def __init__(self, repository, account, token, github_token):
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or "")
                or len(repository) > 200 or not re.fullmatch(r"[a-fA-F0-9]{32}", account or "")
                or not all(isinstance(v, str) and 0 < len(v) <= 4096 and not any(c.isspace() for c in v)
                           for v in (token, github_token))):
            raise ValueError("invalid_live_configuration")
        self.github = "https://api.github.com/repos/%s/actions/" % repository
        self.analytics = "https://api.cloudflare.com/client/v4/accounts/%s/analytics_engine/sql" % account
        self.github_headers = {"Authorization": "Bearer " + github_token,
                               "Accept": "application/vnd.github+json", "User-Agent": "vetagent-operations"}
        self.analytics_headers = {"Authorization": "Bearer " + token, "Content-Type": "text/plain"}

    def inventory(self):
        return request_json(self.github + "workflows/deploy.yml/runs?branch=master&per_page=%d" % INVENTORY_CAP,
                            headers=self.github_headers)

    def jobs(self, run_id):
        return request_json(self.github + "runs/%d/jobs?per_page=100" % run_id, headers=self.github_headers)

    def aggregate(self, tool, cohort, start, end):
        sql = query_sql(tool, cohort, start, end)
        return request_json(self.analytics, data=sql.encode("utf-8"), headers=self.analytics_headers)


class FixtureSource:
    """Offline receipts have the same aggregate boundary as the live transport."""
    def __init__(self, fixture):
        if (not isinstance(fixture, dict) or not isinstance(fixture.get("jobs"), dict)
                or not isinstance(fixture.get("aggregates"), list)
                or len(fixture["aggregates"]) > QUERY_CAP):
            raise ValueError("invalid_fixture")
        self.fixture = fixture

    def inventory(self):
        return self.fixture.get("inventory")

    def jobs(self, run_id):
        return self.fixture["jobs"].get(str(run_id))

    def aggregate(self, tool, cohort, start, end):
        selected = [r.get("reply") for r in self.fixture["aggregates"] if isinstance(r, dict)
                    and (r.get("tool"), r.get("cohort"), r.get("start"), r.get("end"))
                    == (tool, cohort, start, end)]
        return selected[0] if len(selected) == 1 else None


def upload_anchor(reply):
    state, body = _body(reply)
    if body is None:
        return {"state": "unobserved", "reason": state}
    try:
        jobs = body["jobs"]
        if not isinstance(jobs, list) or len(jobs) > 100:
            raise ValueError("invalid_jobs")
        if "total_count" in body and _count(body["total_count"]) != len(jobs):
            return {"state": "unobserved", "reason": "truncated_jobs"}
        times = []
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("steps"), list) or len(job["steps"]) > 100:
                raise ValueError("invalid_steps")
            for step in job["steps"]:
                if not isinstance(step, dict):
                    raise ValueError("invalid_step")
                if step.get("name") == "Deploy to Cloudflare" and step.get("conclusion") == "success":
                    times.append(_time(step["completed_at"]))
        if len(times) != 1:
            return {"state": "unobserved", "reason": "missing_or_ambiguous_upload"}
        return {"state": "observed", "completed_at": _iso(times[0]),
                "anchor_kind": "successful_upload_step_completion", "version_log_at": None}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {"state": "unobserved", "reason": "malformed_jobs"}


def observe(source, *, captured_at, days=90, deploy_limit=10, release_run=RELEASE_RUN):
    """Collect a bounded, privacy-limited descriptive report through a read source."""
    capture = _time(captured_at)
    if (type(days) is not int or not 1 <= days <= 90 or type(deploy_limit) is not int
            or not 1 <= deploy_limit <= 10 or type(release_run) is not int or not 1 <= release_run <= 10 ** 15):
        raise ValueError("invalid_limits")
    try:
        floor = capture - timedelta(days=days)
    except OverflowError as exc:
        raise ValueError("invalid_capture_range") from exc
    report = {"schema_version": 1, "captured_at": _iso(capture), "available": True,
              "interpretation": "descriptive; no causal or no-effect verdict",
              "cohort_labels": {"self": "known vetagent-* self traffic", "other": "other traffic; attribution unknown"},
              "limits": {"days": days, "deployments": deploy_limit, "inventory": INVENTORY_CAP,
                         "queries": QUERY_CAP, "rows_per_query": ROW_CAP, "requests": REQUEST_CAP,
                         "timeout_seconds": REQUEST_TIMEOUT, "response_bytes": BYTE_CAP},
              "discovery": {"release_run_id": release_run, "anchor": None, "status_observed": None,
                            "cohorts": {}, "state": "unobserved"},
              "inventory": {"state": "unobserved", "limited": True,
                            "potential_unobserved_transitions": True}, "deployments": [], "exclusions": [],
              "limitations": ["No instance, version, token or cache-warmth dimension is collected.",
                              "Deployment completion is an anchor, not an edge propagation observation.",
                              "No sample-size decision rule is adopted; sparse and empty windows are inconclusive.",
                              "Version log timestamps were not collected; they are not substituted for step completion."],
              "execution": {"requests": 0, "queries": 0}}

    def ask(kind, *args):
        if (report["execution"]["requests"] >= REQUEST_CAP
                or (kind == "aggregate" and report["execution"]["queries"] >= QUERY_CAP)):
            return {"http_status": 0, "error": "budget_exhausted"}
        report["execution"]["requests"] += 1
        if kind == "aggregate":
            report["execution"]["queries"] += 1
        try:
            return getattr(source, kind)(*args)
        except Exception:
            return {"http_status": 0, "error": "transport"}

    def aggregates(tool, start, end):
        result = {}
        for cohort in COHORTS:
            cell = aggregate_reply(ask("aggregate", tool, cohort, start, end), tool=tool,
                                   cohort=cohort, start=start, end=end)
            result[cohort] = cell
            if cell["state"] not in ("observed", "empty"):
                report["available"] = False
        return result

    anchor = upload_anchor(ask("jobs", release_run))
    if anchor["state"] == "observed" and _time(anchor["completed_at"]) < capture:
        release_time = _time(anchor["completed_at"])
        start = _iso(max(release_time, floor))
        report["discovery"].update(anchor=anchor["completed_at"], anchor_kind=anchor["anchor_kind"],
                                   window_start=start, window_end=_iso(capture),
                                   lookback_censored=release_time < floor)
        cells = aggregates("find_new_hot_pools", start, _iso(capture))
        report["discovery"]["cohorts"] = cells
        valid = all(c["state"] in ("observed", "empty") for c in cells.values())
        report["discovery"]["state"] = "observed" if valid else "unobserved"
        report["discovery"]["status_observed"] = (any(
            row["verdict"] in ("ok", "partial") and row["weighted_count"] > 0
            for cell in cells.values() for row in cell["rows"]) if valid else None)
    else:
        report["available"] = False
        report["discovery"]["reason"] = anchor.get("reason", "anchor_not_before_capture")

    state, body = _body(ask("inventory"))
    try:
        if body is None:
            raise ValueError(state)
        runs = body["workflow_runs"]
        if not isinstance(runs, list) or len(runs) > INVENTORY_CAP:
            raise ValueError("truncated_inventory")
        total = _count(body["total_count"])
        if total < len(runs):
            raise ValueError("malformed_inventory")
        parsed, seen = [], set()
        for run in runs:
            if not isinstance(run, dict) or type(run.get("id")) is not int or not 1 <= run["id"] <= 10 ** 15:
                raise ValueError("malformed_inventory")
            if not isinstance(run.get("head_sha"), str) or not re.fullmatch(r"[a-f0-9]{40}", run["head_sha"]):
                raise ValueError("malformed_inventory")
            if run["id"] in seen:
                raise ValueError("malformed_inventory")
            seen.add(run["id"])
            parsed.append({"run_id": run["id"], "head_sha": run["head_sha"]})
        report["inventory"].update(state="observed" if parsed else "empty", returned=len(parsed),
                                   limited=total > len(parsed), lookback_start=_iso(floor))
    except (KeyError, ValueError, TypeError, OverflowError):
        report["available"] = False
        report["inventory"]["state"] = state if body is None else "malformed"
        return report

    anchors = []
    for run in parsed:
        upload = anchor if run["run_id"] == release_run else upload_anchor(ask("jobs", run["run_id"]))
        if upload["state"] != "observed":
            report["available"] = False
            report["exclusions"].append({"run_id": run["run_id"], "reason": upload["reason"]})
            continue
        time = _time(upload["completed_at"])
        if time > capture:
            report["available"] = False
            report["exclusions"].append({"run_id": run["run_id"], "reason": "upload_after_capture"})
            continue
        anchors.append(dict(run, **upload))
    anchors.sort(key=lambda a: (a["completed_at"], a["run_id"]))
    selected = [a for a in anchors if _time(a["completed_at"]) >= floor][-deploy_limit:]
    selected_ids = {a["run_id"] for a in selected}
    for a in anchors:
        if a["run_id"] not in selected_ids:
            report["exclusions"].append({"run_id": a["run_id"], "reason": "lookback_or_deployment_cap"})
    for a in selected:
        index = anchors.index(a)
        next_time = _time(anchors[index + 1]["completed_at"]) if index + 1 < len(anchors) else None
        bound = min(capture, next_time) if next_time is not None else capture
        cause = "next_upload" if next_time is not None and next_time <= capture else "capture_clock"
        deployed = dict(a, windows=[])
        for phase, begin, finish in (("first_0_5_minutes", 0, 5), ("subsequent_5_60_minutes", 5, 60)):
            start_time = _time(a["completed_at"]) + timedelta(minutes=begin)
            end_time = _time(a["completed_at"]) + timedelta(minutes=finish)
            window = {"phase": phase, "start": _iso(start_time), "end": None,
                      "bounded_until": _iso(bound), "censored": bound < end_time,
                      "censor_reason": cause if bound < end_time else None, "state": "unobserved",
                      "inference": "inconclusive", "cohorts": {}}
            if start_time < bound:
                window["end"] = _iso(min(end_time, bound))
                window["cohorts"] = aggregates("assess_token_risk", window["start"], window["end"])
                window["state"] = "observed" if all(
                    c["state"] in ("observed", "empty") for c in window["cohorts"].values()) else "unobserved"
            deployed["windows"].append(window)
        report["deployments"].append(deployed)
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid_arguments")


def main(argv=None):
    parser = _Parser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", metavar="FIXTURE")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--output", default="operational-evidence.json")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--deploy-limit", type=int, default=10)
    parser.add_argument("--release-run", type=int, default=RELEASE_RUN)
    args = None
    try:
        args = parser.parse_args(argv)
        if args.offline:
            raw = Path(args.offline).read_bytes()
            if len(raw) > BYTE_CAP:
                raise ValueError("fixture_too_large")
            fixture = json.loads(raw.decode("utf-8"))
            source, captured_at = FixtureSource(fixture), fixture["captured_at"]
        elif args.live:
            source = LiveSource(os.environ.get("GITHUB_REPOSITORY"), os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
                                os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("GITHUB_TOKEN"))
            captured_at = _iso(datetime.now(timezone.utc))
        else:
            raise ValueError("explicit_mode_required")
        report = observe(source, captured_at=captured_at, days=args.days,
                         deploy_limit=args.deploy_limit, release_run=args.release_run)
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, OverflowError):
        report = {"schema_version": 1, "available": False, "state": "unavailable",
                  "reason": "invalid_input_or_missing_explicit_live_configuration"}
    encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    try:
        Path(args.output if args else "operational-evidence.json").write_text(encoded, encoding="utf-8")
    except OSError:
        print("Operational observation unavailable: aggregate output could not be saved.")
        return 2
    print("Operational observation saved; availability: %s." % ("observed" if report["available"] else "unavailable"))
    return 0 if report["available"] else 1


if __name__ == "__main__":
    sys.exit(main())
