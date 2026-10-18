"""One fixed held-out-oracle quota pilot; default use is offline.

plan binds an existing Git dataset to 316 array indices. Explicit run makes one paced
single-contract request per index, without retries. report reads saved receipts only.
Safe outputs contain no addresses, URLs, raw responses or arbitrary error messages.
A short single-date run is not continuous 24-hour or prospective evidence.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import labels

REQUEST_CAP = 316
GAP_SECONDS = 2.1
REQUEST_TIMEOUT = 30
RUN_SECONDS = 1800
BODY_CAP = 256 * 1024
SAFE_CAP = 1024 * 1024
DATASET_CAP = 16 * 1024 * 1024
ROOT = Path(__file__).resolve().parent.parent
_HASH = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
_REASONS = {"completed", "permission_refused", "run_deadline", "utc_day_end",
            "persistence_failed", "interrupted"}
LIMITATIONS = [
    "Single-date paced quota/throughput pilot; not continuous 24-hour observation.",
    "daily reset unobserved; remaining allowance and shared usage unknown.",
    "Historical fixed workload; not a T+24h indexing sample or a 30-day study.",
    "No new labels, unsafe yield, demand or BUILD decision is measured.",
    "Attempted counts receipted transport invocations; pending intents remain uncertain.",
]


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (ValueError, OverflowError):
        return None


def _hashes(source, dataset_sha, label_sha):
    if (not isinstance(source, str) or not _COMMIT.fullmatch(source)
            or not isinstance(dataset_sha, str) or not _HASH.fullmatch(dataset_sha)
            or not isinstance(label_sha, str) or not _HASH.fullmatch(label_sha)):
        raise ValueError("invalid_source")


def context_from_bytes(raw, source_commit, dataset_sha256, label_code_sha256):
    """Validate declared bytes; the CLI additionally proves the two Git blobs."""
    _hashes(source_commit, dataset_sha256, label_code_sha256)
    if not isinstance(raw, bytes) or len(raw) > DATASET_CAP or _sha(raw) != dataset_sha256:
        raise ValueError("source_mismatch")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tokens"), list) or len(data["tokens"]) > 100000:
        raise ValueError("invalid_dataset")
    return {"source_commit": source_commit, "dataset_sha256": dataset_sha256,
            "label_code_sha256": label_code_sha256, "dataset_blob_sha256": dataset_sha256,
            "label_blob_sha256": label_code_sha256, "tokens": data["tokens"]}


def load_context(path, source_commit):
    """Read local Git only, never fetch; do not trust a filename as provenance."""
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise ValueError("invalid_source")
    target = Path(path)
    if target.stat().st_size > DATASET_CAP:
        raise ValueError("invalid_dataset")
    raw = target.read_bytes()
    try:
        dataset = subprocess.check_output(["git", "show", source_commit + ":bench/dataset.json"],
                                          cwd=ROOT, stderr=subprocess.DEVNULL)
        label_code = subprocess.check_output(["git", "show", source_commit + ":bench/labels.py"],
                                             cwd=ROOT, stderr=subprocess.DEVNULL)
    except subprocess.SubprocessError as exc:
        raise ValueError("source_unavailable") from exc
    local_labels = Path(labels.__file__).read_bytes()
    # Git's Windows checkout can use CRLF; bind both byte forms explicitly. Nothing
    # other than that checkout conversion is accepted as the same tracked source.
    def checkout_matches(actual, canonical):
        return actual == canonical or (b"\r\n" not in canonical and b"\r\n" in actual
                                        and actual.replace(b"\r\n", b"\n") == canonical)
    if not checkout_matches(raw, dataset) or not checkout_matches(local_labels, label_code):
        raise ValueError("source_mismatch")
    context = context_from_bytes(raw, source_commit, _sha(raw), _sha(local_labels))
    context.update(dataset_blob_sha256=_sha(dataset), label_blob_sha256=_sha(label_code))
    return context


def make_plan(context):
    _hashes(context.get("source_commit"), context.get("dataset_sha256"), context.get("label_code_sha256"))
    if any(not isinstance(context.get(k), str) or not _HASH.fullmatch(context[k])
           for k in ("dataset_blob_sha256", "label_blob_sha256")):
        raise ValueError("invalid_blob_hash")
    tokens = context.get("tokens")
    if not isinstance(tokens, list) or len(tokens) > 100000:
        raise ValueError("invalid_dataset")
    indices, seen = [], set()
    excluded = {"invalid_address": 0, "unsupported_chain": 0, "duplicate": 0, "not_selected": 0}
    for index, row in enumerate(tokens):
        if not isinstance(row, dict) or not isinstance(row.get("address"), str) or not _ADDRESS.fullmatch(row["address"]):
            excluded["invalid_address"] += 1
            continue
        chain = row.get("chain")
        if not isinstance(chain, str) or chain not in labels.GOPLUS_CHAIN_ID:
            excluded["unsupported_chain"] += 1
            continue
        identity = chain, row["address"].lower()
        if identity in seen:
            excluded["duplicate"] += 1
            continue
        seen.add(identity)
        if len(indices) < REQUEST_CAP:
            indices.append(index)
        else:
            excluded["not_selected"] += 1
    if len(indices) != REQUEST_CAP:
        raise ValueError("insufficient_queue")
    return {"schema_version": 1, "source_commit": context["source_commit"],
            "dataset_sha256": context["dataset_sha256"], "label_code_sha256": context["label_code_sha256"],
            "dataset_blob_sha256": context["dataset_blob_sha256"], "label_blob_sha256": context["label_blob_sha256"],
            "indices": indices, "queue_sha256": _sha(_encode(indices)), "exclusions": excluded}


def _public_plan(plan):
    keys = {"schema_version", "source_commit", "dataset_sha256", "label_code_sha256", "dataset_blob_sha256",
            "label_blob_sha256", "indices", "queue_sha256", "exclusions"}
    if not isinstance(plan, dict) or set(plan) != keys or type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ValueError("invalid_plan")
    _hashes(plan["source_commit"], plan["dataset_sha256"], plan["label_code_sha256"])
    if any(not isinstance(plan[k], str) or not _HASH.fullmatch(plan[k]) for k in ("dataset_blob_sha256", "label_blob_sha256")):
        raise ValueError("invalid_blob_hash")
    indices = plan["indices"]
    if (not isinstance(indices, list) or len(indices) != REQUEST_CAP
            or any(type(i) is not int or not 0 <= i < 100000 for i in indices)
            or indices != sorted(set(indices)) or plan["queue_sha256"] != _sha(_encode(indices))):
        raise ValueError("invalid_queue")
    excluded = plan["exclusions"]
    if (not isinstance(excluded, dict) or set(excluded) != {"invalid_address", "unsupported_chain", "duplicate", "not_selected"}
            or any(type(n) is not int or not 0 <= n <= 100000 for n in excluded.values())):
        raise ValueError("invalid_exclusions")
    return plan


def validate_plan(plan, context):
    _public_plan(plan)
    if plan != make_plan(context):
        raise ValueError("source_or_queue_mismatch")
    return plan


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_once(chain, address, *, timeout=REQUEST_TIMEOUT, opener=None):
    """Exactly one keyless GET to the already-used held-out endpoint."""
    if (chain not in labels.GOPLUS_CHAIN_ID or not isinstance(address, str) or not _ADDRESS.fullmatch(address)
            or timeout != REQUEST_TIMEOUT):
        raise ValueError("invalid_request")
    url = ("https://api.gopluslabs.io/api/v1/token_security/%s?contract_addresses=%s"
           % (labels.GOPLUS_CHAIN_ID[chain], address))
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "vetagent-benchmark/1.0"}, method="GET")
    client = opener or urllib.request.build_opener(NoRedirect())
    try:
        try:
            response = client.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = getattr(response, "status", getattr(response, "code", None))
            return {"http_status": status, "body": response.read(BODY_CAP + 1)}
    except (TimeoutError, urllib.error.URLError) as exc:
        timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        return {"http_status": 0, "error": "timeout" if timed_out else "transport"}
    except (OSError, ValueError):
        return {"http_status": 0, "error": "transport"}


def classify(reply, address, *, recent_volume=None, labeler=None):
    """Normalize a response into a fixed safe schema before any output boundary."""
    cell = {"http_status": None, "http_state": "transport", "body_state": "unobserved",
            "api_state": "unobserved", "api_code": None, "result_state": "unobserved", "label_state": "unobserved",
            "field_states": {"buy_tax": "unobserved", "sell_tax": "unobserved", "holder_count": "unobserved"},
            "captured_body_sha256": None, "body_complete": None}
    if not isinstance(reply, dict):
        return cell
    status = reply.get("http_status")
    if type(status) is int and 100 <= status <= 599:
        cell["http_status"] = status
        cell["http_state"] = ("observed" if status == 200 else "rate_limited" if status == 429
                              else "permission_refused" if status in (401, 403)
                              else "redirect" if 300 <= status < 400 else "http_error")
    elif reply.get("error") == "timeout":
        cell["http_state"] = "timeout"
    raw = reply.get("body")
    if not isinstance(raw, bytes):
        return cell
    captured = raw[:BODY_CAP]
    cell.update(captured_body_sha256=_sha(captured), body_complete=len(raw) <= BODY_CAP)
    if len(raw) > BODY_CAP:
        cell["body_state"] = "truncated"
        return cell
    if not raw:
        cell["body_state"] = "empty"
        return cell
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        cell["body_state"] = "malformed"
        return cell
    cell["body_state"] = "json"
    if not isinstance(payload, dict):
        cell["api_state"] = "malformed"
        return cell
    code = payload.get("code")
    if type(code) is int and abs(code) <= 2147483647:
        cell["api_code"] = code
    if status != 200:
        return cell
    if cell["api_code"] != 1 or payload.get("success") is False or payload.get("errors"):
        cell["api_state"] = "api_error"
        return cell
    result = payload.get("result")
    if not isinstance(result, dict):
        cell.update(api_state="missing_result", result_state="missing")
        return cell
    matches = [v for k, v in result.items() if isinstance(k, str) and k.lower() == address.lower()]
    if not matches:
        cell.update(api_state="missing_result", result_state="missing")
        return cell
    if len(matches) != 1 or not isinstance(matches[0], dict) or not matches[0]:
        cell.update(api_state="invalid_result", result_state="malformed")
        return cell
    row = matches[0]
    cell.update(api_state="matching_result", result_state="matched")
    for field in cell["field_states"]:
        value = row.get(field)
        if value in (None, ""):
            state = "missing"
        else:
            number = _finite(value)
            state = ("integer" if field == "holder_count" and number is not None and number.is_integer() and number <= 10 ** 15
                     else "finite" if field != "holder_count" and number is not None else "invalid")
        cell["field_states"][field] = state
    try:
        label, _, _ = (labeler or labels.goplus_label)(payload, address, recent_volume_7d=_finite(recent_volume))
        cell["label_state"] = "returned" if label in ("safe", "unsafe", "centralized") else "null" if label is None else "error"
    except Exception:
        cell["label_state"] = "error"
    return cell


def _outside_git(path):
    target = Path(path).resolve()
    if any((p / ".git").exists() for p in (target, *target.parents)):
        raise ValueError("git_output_refused")
    return target


def _durable(path, raw, mode="xb"):
    with path.open(mode) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


class FileSink:
    """A claimed, immutable run directory; no live restart or overwritten history."""
    def __init__(self, path):
        self.path = _outside_git(path)

    def begin(self, plan):
        self.path.mkdir(parents=True, exist_ok=False)
        _durable(self.path / "plan.json", _encode(plan))
        _durable(self.path / "receipts.jsonl", b"")

    def _check(self, addition, replacing=None):
        size = sum(p.stat().st_size for p in self.path.iterdir() if p.is_file() and p.name != replacing)
        if size + addition > SAFE_CAP:
            raise OSError("safe_output_limit")

    def append(self, event):
        raw = _encode(event)
        self._check(len(raw))
        _durable(self.path / "receipts.jsonl", raw, "ab")

    def save(self, report):
        raw = _encode(report)
        self._check(len(raw), replacing="report.json")
        temporary = self.path / "report.partial"
        _durable(temporary, raw, "wb")
        os.replace(temporary, self.path / "report.json")


class Clock:
    def time(self):
        return time.time()

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


def _report(plan, events, reason=None):
    starts = [e for e in events if e["kind"] == "start"]
    stops = [e for e in events if e["kind"] == "stop"]
    intents = {e["index"]: e for e in events if e["kind"] == "intent"}
    receipts = {e["index"]: e for e in events if e["kind"] == "receipt"}
    stop = reason or (stops[-1]["reason"] if stops else "interrupted")
    cells = []
    for index in plan["indices"]:
        cell = {"index": index}
        intent, receipt = intents.get(index), receipts.get(index)
        if intent is None:
            cell.update(state="not_asked", reason=stop)
        elif receipt is None:
            cell.update(state="unobserved", reason="missing_receipt", scheduled_at=intent["scheduled_at"], request_at=intent["request_at"])
        else:
            observation = receipt["observation"]
            valid = observation["label_state"] == "returned" and all(
                value in ("integer", "finite") for value in observation["field_states"].values())
            cell.update(observation)
            cell.update(state="observed" if valid else "unobserved", scheduled_at=intent["scheduled_at"],
                        request_at=intent["request_at"], response_at=receipt["response_at"], duration_seconds=receipt["duration_seconds"])
        cells.append(cell)
    observed = list(receipts.values())
    counts = {"requested": len(plan["indices"]), "claimed": len(intents), "attempted": len(receipts),
              "completed_http": sum(e["observation"]["http_status"] is not None for e in observed),
              "rate_limited": sum(e["observation"]["http_status"] == 429 for e in observed),
              "http_errors": sum(e["observation"]["http_status"] is not None and e["observation"]["http_status"] != 200 for e in observed),
              "transport_errors": sum(e["observation"]["http_status"] is None for e in observed),
              "not_asked": len(plan["indices"]) - len(intents), "uncertain": len(intents) - len(receipts),
              "unobserved_label": sum(c["state"] == "unobserved" for c in cells),
              "matching_result": sum(e["observation"]["result_state"] == "matched" for e in observed),
              "label_returned": sum(e["observation"]["label_state"] == "returned" for e in observed)}
    coverage = {field: {state: sum(e["observation"]["field_states"][field] == state for e in observed)
                        for state in ("finite", "integer", "missing", "invalid", "unobserved")}
                for field in ("buy_tax", "sell_tax", "holder_count")}
    end_mono = stops[-1]["mono"] if stops else max(
        (intents[e["index"]]["mono"] + e["duration_seconds"] for e in observed), default=starts[0]["mono"] if starts else 0)
    elapsed = max(0, end_mono - starts[0]["mono"]) if starts else 0
    return {"schema_version": 1, "source_commit": plan["source_commit"], "dataset_sha256": plan["dataset_sha256"],
            "label_code_sha256": plan["label_code_sha256"], "queue_sha256": plan["queue_sha256"],
            "dataset_blob_sha256": plan["dataset_blob_sha256"], "label_blob_sha256": plan["label_blob_sha256"],
            "plan_sha256": _sha(_encode(plan)), "receipt_chain_sha256": _sha(b"".join(_encode(e) for e in events)),
            "available": counts["claimed"] == REQUEST_CAP and counts["unobserved_label"] == 0 and stop == "completed",
            "stop_reason": stop, "counts": counts, "field_coverage": coverage, "cells": cells,
            "started_at": starts[0]["at"] if starts else None, "ended_at": stops[-1]["at"] if stops else None,
            "first_observation_at": observed[0]["response_at"] if observed else None,
            "last_observation_at": observed[-1]["response_at"] if observed else None,
            "elapsed_seconds": elapsed, "elapsed_minutes": elapsed / 60,
            "limits": {"requests": REQUEST_CAP, "gap_seconds": GAP_SECONDS, "request_timeout_seconds": REQUEST_TIMEOUT,
                       "elapsed_seconds": RUN_SECONDS, "body_bytes": BODY_CAP, "safe_bundle_bytes": SAFE_CAP},
            "limitations": LIMITATIONS}


def run_plan(plan, context, *, sink, transport=None, clock=None, private_raw_dir=None, ci=False):
    validate_plan(plan, context)
    if private_raw_dir is not None and (ci or os.environ.get("GITHUB_ACTIONS", "").lower() == "true"):
        raise ValueError("ci_raw_refused")
    raw_dir = _outside_git(private_raw_dir) if private_raw_dir is not None else None
    if raw_dir is not None and raw_dir.exists():
        raise ValueError("existing_raw_refused")
    if raw_dir is not None and isinstance(sink, FileSink) and (
            raw_dir.is_relative_to(sink.path) or sink.path.is_relative_to(raw_dir)):
        raise ValueError("raw_and_safe_outputs_overlap")
    current, fetch = clock or Clock(), transport or request_once
    wall, mono = current.time(), current.monotonic()
    if _finite(wall) is None or _finite(mono) is None:
        raise ValueError("invalid_clock")
    start_day = datetime.fromtimestamp(wall, timezone.utc).date()
    day_end = datetime.combine(start_day + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()
    sink.begin(plan)
    events, raw_manifest = [], {}
    reason, last_start = "completed", None

    def append(event):
        sink.append(event)
        events.append(event)

    try:
        append({"kind": "start", "at": _utc(wall), "mono": mono})
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=False)
        sink.save(_report(plan, events, "interrupted"))
        for index in plan["indices"]:
            wait = max(0, last_start + GAP_SECONDS - current.monotonic()) if last_start is not None else 0
            if current.time() + wait + REQUEST_TIMEOUT > day_end or datetime.fromtimestamp(current.time(), timezone.utc).date() != start_day:
                reason = "utc_day_end"
                break
            if current.monotonic() + wait + REQUEST_TIMEOUT > mono + RUN_SECONDS:
                reason = "run_deadline"
                break
            scheduled = _utc(current.time() + wait)
            if wait:
                current.sleep(wait)
            if current.time() + REQUEST_TIMEOUT > day_end:
                reason = "utc_day_end"
                break
            if current.monotonic() + REQUEST_TIMEOUT > mono + RUN_SECONDS:
                reason = "run_deadline"
                break
            actual_start = current.monotonic()
            append({"kind": "intent", "index": index, "scheduled_at": scheduled, "request_at": _utc(current.time()), "mono": actual_start})
            row = context["tokens"][index]
            last_start = actual_start
            try:
                reply = fetch(row["chain"], row["address"], timeout=REQUEST_TIMEOUT)
            except KeyboardInterrupt:
                reason = "interrupted"
                break
            except Exception:
                reply = {"http_status": 0, "error": "transport"}
            facts = row.get("outcome_facts")
            volume = facts.get("recent_volume_7d") if isinstance(facts, dict) else None
            observation = classify(reply, row["address"], recent_volume=volume)
            append({"kind": "receipt", "index": index, "response_at": _utc(current.time()),
                    "duration_seconds": max(0, current.monotonic() - actual_start), "observation": observation})
            if raw_dir is not None and isinstance(reply, dict) and isinstance(reply.get("body"), bytes):
                body = reply["body"][:BODY_CAP]
                _durable(raw_dir / ("%06d.bin" % index), body)
                raw_manifest[str(index)] = {"captured_body_sha256": _sha(body), "complete": observation["body_complete"]}
                temporary = raw_dir / "manifest.partial"
                _durable(temporary, _encode(raw_manifest), "wb")
                os.replace(temporary, raw_dir / "manifest.json")
            sink.save(_report(plan, events, "interrupted"))
            if observation["http_status"] in (401, 403):
                reason = "permission_refused"
                break
    except (OSError, ValueError, OverflowError):
        reason = "persistence_failed"
    except KeyboardInterrupt:
        reason = "interrupted"
    try:
        append({"kind": "stop", "at": _utc(current.time()), "mono": current.monotonic(), "reason": reason})
    except (OSError, ValueError):
        reason = "persistence_failed"
    report = _report(plan, events, reason)
    try:
        sink.save(report)
    except (OSError, ValueError):
        report = _report(plan, events, "persistence_failed")
    return report


def _safe_observation(value):
    template = classify(None, "")
    if not isinstance(value, dict) or set(value) != set(template):
        raise ValueError("invalid_observation")
    enums = {"http_state": {"transport", "timeout", "observed", "rate_limited", "permission_refused", "redirect", "http_error"},
             "body_state": {"unobserved", "truncated", "empty", "malformed", "json"},
             "api_state": {"unobserved", "malformed", "api_error", "missing_result", "invalid_result", "matching_result"},
             "result_state": {"unobserved", "missing", "malformed", "matched"},
             "label_state": {"unobserved", "returned", "null", "error"}}
    if any(not isinstance(value[k], str) or value[k] not in allowed for k, allowed in enums.items()):
        raise ValueError("invalid_state")
    status, code = value["http_status"], value["api_code"]
    if (status is not None and (type(status) is not int or not 100 <= status <= 599)
            or code is not None and (type(code) is not int or abs(code) > 2147483647)
            or value["body_complete"] is not None and type(value["body_complete"]) is not bool
            or value["captured_body_sha256"] is not None and (not isinstance(value["captured_body_sha256"], str)
                or not _HASH.fullmatch(value["captured_body_sha256"]))):
        raise ValueError("invalid_status")
    fields = value["field_states"]
    if (not isinstance(fields, dict) or set(fields) != set(template["field_states"])
            or any(not isinstance(s, str) or s not in {"finite", "integer", "missing", "invalid", "unobserved"} for s in fields.values())):
        raise ValueError("invalid_fields")
    return value


def read_report(path):
    """Reconstruct immutable receipts without transport, dataset reads or live resume."""
    directory = Path(path)
    entries = list(directory.iterdir())
    if any(not p.is_file() or p.name not in {"plan.json", "receipts.jsonl", "report.json", "report.partial"} for p in entries):
        raise ValueError("invalid_bundle")
    if sum(p.stat().st_size for p in entries) > SAFE_CAP:
        raise ValueError("oversized_bundle")
    plan = _public_plan(json.loads((directory / "plan.json").read_text(encoding="utf-8")))
    events, claimed, answered = [], set(), set()
    ledger = (directory / "receipts.jsonl").read_bytes()
    tail_complete = not ledger or ledger.endswith(b"\n")
    lines = ledger.splitlines(keepends=True)
    # A killed append can leave a partial final record. Retain its bytes and all
    # earlier observations; the already-persisted intent still consumes its slot.
    if not tail_complete:
        lines = lines[:-1]
    if len(lines) > REQUEST_CAP * 2 + 2:
        raise ValueError("oversized_ledger")
    for raw in lines:
        event = json.loads(raw.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("invalid_event")
        kind = event.get("kind")
        keys = {"start": {"kind", "at", "mono"}, "stop": {"kind", "at", "mono", "reason"},
                "intent": {"kind", "index", "scheduled_at", "request_at", "mono"},
                "receipt": {"kind", "index", "response_at", "duration_seconds", "observation"}}
        if not isinstance(kind, str) or kind not in keys or set(event) != keys[kind]:
            raise ValueError("invalid_event")
        for field in ("at", "scheduled_at", "request_at", "response_at"):
            if field in event:
                value = event[field]
                if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
                    raise ValueError("invalid_time")
                datetime.fromisoformat(value.replace("Z", "+00:00"))
        for field in ("mono", "duration_seconds"):
            if field in event and (type(event[field]) not in (int, float) or _finite(event[field]) is None):
                raise ValueError("invalid_duration")
        if kind == "start" and events or kind == "stop" and event["reason"] not in _REASONS:
            raise ValueError("invalid_transition")
        if events and events[-1]["kind"] == "stop":
            raise ValueError("terminal_ledger")
        if kind in ("intent", "receipt"):
            index = event["index"]
            if type(index) is not int or index not in plan["indices"]:
                raise ValueError("invalid_index")
            if kind == "intent":
                if index in claimed or index != plan["indices"][len(claimed)]:
                    raise ValueError("duplicate_or_reordered_intent")
                claimed.add(index)
            else:
                if index not in claimed or index in answered:
                    raise ValueError("orphan_receipt")
                _safe_observation(event["observation"])
                answered.add(index)
        events.append(event)
    report = _report(plan, events, "interrupted" if not tail_complete else None)
    report.update(ledger_tail_state="complete" if tail_complete else "incomplete", receipt_bytes_sha256=_sha(ledger))
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid_arguments")


def main(argv=None, *, context_loader=None, transport=None, clock=None):
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--dataset", required=True)
    plan_parser.add_argument("--source", required=True)
    plan_parser.add_argument("--output", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--dataset", required=True)
    run_parser.add_argument("--plan", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--private-raw-dir")
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--output", required=True)
    try:
        args = parser.parse_args(argv)
        loader = context_loader or load_context
        if args.command == "plan":
            plan = make_plan(loader(args.dataset, args.source))
            output = _outside_git(args.output)
            _durable(output, _encode(plan))
            print(json.dumps({"state": "planned", "requests": REQUEST_CAP, "queue_sha256": plan["queue_sha256"]}))
            return 0
        if args.command == "run":
            plan_path = Path(args.plan)
            if plan_path.stat().st_size > SAFE_CAP:
                raise ValueError("oversized_plan")
            plan = _public_plan(json.loads(plan_path.read_text(encoding="utf-8")))
            context = loader(args.dataset, plan["source_commit"])
            report = run_plan(plan, context, sink=FileSink(args.output), transport=transport, clock=clock,
                              private_raw_dir=args.private_raw_dir)
        elif args.command == "report":
            report = read_report(args.output)
        else:
            raise ValueError("explicit_mode_required")
        print(json.dumps({k: report[k] for k in ("available", "stop_reason", "counts", "started_at", "ended_at",
                                                "elapsed_seconds", "elapsed_minutes", "limitations")}, sort_keys=True))
        return 0 if report["available"] else 1
    except (ValueError, TypeError, OSError, UnicodeError, OverflowError, subprocess.SubprocessError, KeyboardInterrupt):
        print('{"available":false,"reason":"invalid_input_or_unavailable_evidence"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
