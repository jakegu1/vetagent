"""Offline W40 enrollment and paired-receipt core. This module never runs a study.

plan() seals declared NDJSON prefixes, enroll() writes their prospective queue,
ingest() imports a saved packet, and report() reads the immutable safe journal.
Source paths and identities are resolved only in memory. Safe files contain ordinals,
hashes, UTC clocks and fixed states. Explicit external raw storage is required for
imports and is refused in CI, inside Git checkouts, or beside nested safe output.

A packet is bounded UTF-8 JSON. Its reserve/ohlcv/oracle/engine objects carry state,
http_status, request_at, response_at, base64 raw bytes and their SHA-256. Reserve and
OHLCV bodies use the existing GeckoTerminal shapes; oracle bodies use token_security;
engine bodies are saved verbose answers. Source, pool and engine context declarations
remain separate from raw bodies. A declared external start receipt is an observation,
not proof this offline program performed any live work. No success gate is evaluated.
"""

import argparse
import base64
import contextlib
import hashlib
import io
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import labels

HERE = Path(__file__).resolve().parent
ROW_CAP = 64 * 1024
RAW_CAP = 1024 * 1024
PACKET_CAP = 4 * 1024 * 1024
REPORT_CAP = 1024 * 1024
COHORT_CAP = 10_000
SOURCE_CAP = 128
SOURCE_BYTES_CAP = 64 * 1024 * 1024
EVENT_CAP = 40_010
DETAIL_CAP = 256
RULES = {"age_hours": 24, "reserve_usd": 5000, "days": 30, "unsafe_tokens": 18}
REASONS = ("enrolled", "duplicate", "invalid_clock", "future_clock", "unsupported",
           "missed_before_enrollment", "invalid_row", "row_cap", "cohort_cap")
STATES = {"observed", "not_asked", "timeout", "interrupted_intent", "budget_exhausted",
          "transport_error", "http_429", "http_refusal", "http_failure", "invalid_body",
          "invalid_evidence", "missing_raw", "invalid_clock"}
FLAGS = ("is_honeypot", "cannot_sell_all", "cannot_buy", "selfdestruct",
         "personal_slippage_modifiable", "transfer_pausable", "is_blacklisted",
         "slippage_modifiable", "can_take_back_ownership", "owner_change_balance",
         "is_mintable", "is_open_source", "trust_list")
HOSTS = {"api.gopluslabs.io", "api.geckoterminal.com", "api.dexscreener.com",
         "api.honeypot.is", "api.coingecko.com", "api.rugcheck.xyz"}


class EvidenceError(Exception):
    """Only fixed, non-identifying error categories leave the core."""


def _error(code):
    raise EvidenceError(code)


def _bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        _error("invalid_json")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{%d}" % length, value) is not None


def _json(raw, limit):
    if not isinstance(raw, bytes) or len(raw) > limit:
        _error("input_limit")
    def constant(_value):
        raise ValueError()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=constant, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        _error("invalid_json")


def _read(path, limit):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError:
        _error("input_unavailable")
    if len(raw) > limit:
        _error("input_limit")
    return raw


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        _error("invalid_clock")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            _error("invalid_clock")
        result = result.astimezone(timezone.utc)
        if not 1900 <= result.year <= 2199:
            _error("invalid_clock")
        return result
    except (ValueError, OverflowError):
        _error("invalid_clock")


def _iso(value):
    return value.isoformat(timespec="microseconds" if value.microsecond else "seconds").replace("+00:00", "Z")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, str) and (not value or len(value) > 128):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _address(value):
    return value.lower() if isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", value) else None


def _pool(value):
    return value.lower() if isinstance(value, str) and re.fullmatch(r"0x(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", value) else None


def _bindings():
    return {"rule_sha256": _sha(_read(HERE.parent / "docs/BACKLOG.md", RAW_CAP)),
            "label_sha256": _sha(_read(HERE / "labels.py", RAW_CAP)),
            "engine_sha256": _sha(_read(HERE.parent / "src/risk.py", RAW_CAP))}


def _sources(sources):
    if not isinstance(sources, list) or len(sources) > SOURCE_CAP:
        _error("source_limit")
    declared, seen, total = [], set(), 0
    for ordinal, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"path", "bytes", "sha256"}:
            _error("invalid_source")
        size = source["bytes"]
        if type(size) is not int or size < 0 or not _hex(source["sha256"]):
            _error("invalid_source")
        total += size
        if total > SOURCE_BYTES_CAP:
            _error("source_limit")
        try:
            path = Path(source["path"]).resolve()
            if str(path) in seen:
                _error("duplicate_source")
            seen.add(str(path))
            digest, left, last, rows = hashlib.sha256(), size, b"", 0
            with path.open("rb") as handle:
                while left:
                    raw = handle.read(min(ROW_CAP, left))
                    if not raw:
                        _error("source_hash_mismatch")
                    digest.update(raw)
                    rows += raw.count(b"\n")
                    last = raw[-1:]
                    left -= len(raw)
        except (OSError, TypeError, ValueError):
            _error("source_unavailable")
        if digest.hexdigest() != source["sha256"]:
            _error("source_hash_mismatch")
        if size and last != b"\n":
            _error("partial_source_row")
        declared.append({"source": ordinal, "bytes": size, "rows": rows, "sha256": source["sha256"]})
    return declared


def plan(source_commit, sources):
    """Verify and seal local prefixes. The commit is declared, not a Git lookup."""
    if not _hex(source_commit, 40):
        _error("invalid_source_commit")
    value = {"schema": 1, "state": "not_started", "source_commit": source_commit,
             "source_commit_evidence": "declared", "sources": _sources(sources),
             "rules": dict(RULES), "limits": {"cohort": COHORT_CAP, "row": ROW_CAP,
             "raw": RAW_CAP, "packet": PACKET_CAP, "report": REPORT_CAP,
             "source_files": SOURCE_CAP, "source_bytes": SOURCE_BYTES_CAP}}
    value.update(_bindings())
    value["plan_sha256"] = _sha(_bytes(value))
    return value


def _validate_plan(value, sources=None):
    expected = {"schema", "state", "source_commit", "source_commit_evidence", "sources",
                "rules", "limits", "rule_sha256", "label_sha256", "engine_sha256", "plan_sha256"}
    if not isinstance(value, dict) or set(value) != expected:
        _error("invalid_plan")
    if value["schema"] != 1 or value["state"] != "not_started" or value["rules"] != RULES:
        _error("invalid_plan")
    limits = value["limits"]
    expected_limits = {"row": ROW_CAP, "raw": RAW_CAP, "packet": PACKET_CAP,
                       "report": REPORT_CAP, "source_files": SOURCE_CAP, "source_bytes": SOURCE_BYTES_CAP}
    if (not isinstance(limits, dict) or set(limits) != set(expected_limits) | {"cohort"}
            or type(limits.get("cohort")) is not int or not 1 <= limits["cohort"] <= COHORT_CAP
            or any(type(limits.get(k)) is not int or limits[k] != n for k, n in expected_limits.items())):
        _error("invalid_plan")
    declared = value["sources"]
    if not isinstance(declared, list) or len(declared) > SOURCE_CAP:
        _error("invalid_plan")
    total = 0
    for number, source in enumerate(declared):
        if (not isinstance(source, dict) or set(source) != {"source", "bytes", "rows", "sha256"}
                or type(source["source"]) is not int or source["source"] != number
                or type(source["bytes"]) is not int or source["bytes"] < 0
                or type(source["rows"]) is not int or not 0 <= source["rows"] <= source["bytes"]
                or not _hex(source["sha256"])):
            _error("invalid_plan")
        total += source["bytes"]
    if total > SOURCE_BYTES_CAP:
        _error("invalid_plan")
    if not _hex(value["source_commit"], 40) or value["source_commit_evidence"] != "declared":
        _error("invalid_plan")
    unsigned = {k: v for k, v in value.items() if k != "plan_sha256"}
    if value["plan_sha256"] != _sha(_bytes(unsigned)):
        _error("plan_mismatch")
    if any(value.get(k) != v for k, v in _bindings().items()):
        _error("source_drift")
    if sources is not None and value["sources"] != _sources(sources):
        _error("source_hash_mismatch")


def _rows(source):
    """Read no more than the declared prefix; drain oversized lines without parsing."""
    try:
        with Path(source["path"]).open("rb") as handle:
            sealed = handle.read(source["bytes"])
        if len(sealed) != source["bytes"] or _sha(sealed) != source["sha256"]:
            _error("source_hash_mismatch")
        # Parse the very bytes just verified, not a second view of a moving file.
        with io.BytesIO(sealed) as handle:
            remaining, line = len(sealed), 0
            while remaining:
                raw = handle.readline(min(ROW_CAP + 1, remaining))
                remaining -= len(raw)
                if not raw:
                    _error("source_hash_mismatch")
                line += 1
                oversized = len(raw) > ROW_CAP
                while raw[-1:] != b"\n" and remaining:
                    part = handle.readline(min(ROW_CAP + 1, remaining))
                    if not part:
                        _error("source_hash_mismatch")
                    remaining -= len(part)
                    oversized = True
                    raw = part
                yield line, None if oversized else raw
    except OSError:
        _error("source_unavailable")


def _identity(row):
    if not isinstance(row, dict):
        _error("invalid_row")
    if not isinstance(row.get("chain"), str):
        _error("invalid_row")
    net_to_chain = {net: chain for chain, net in labels.GT_NETWORK.items()}
    chain = net_to_chain.get(row.get("chain"), row.get("chain"))
    if chain not in labels.GOPLUS_CHAIN_ID:
        _error("unsupported")
    network = labels.GT_NETWORK[chain]
    token = row.get("base_token")
    prefix = network + "_"
    if not isinstance(token, str) or not token.startswith(prefix):
        _error("invalid_row")
    address, pool = _address(token[len(prefix):]), _pool(row.get("pool_address"))
    if not address or not pool:
        _error("invalid_row")
    return chain, address, pool


def _atomic_index(directory, value):
    path = directory / "index.pending"
    try:
        with path.open("wb") as handle:
            handle.write(_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(path, directory / "index.json")
    finally:
        if path.exists():
            path.unlink()


@contextlib.contextmanager
def _writer(directory):
    lock = directory / ".writer"
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _error("writer_busy")
    except OSError:
        _error("persistence_failed")
    os.close(descriptor)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _append(directory, index, payload):
    if index["last"] >= EVENT_CAP:
        _error("event_limit")
    event = {"sequence": index["last"] + 1, "parent_sha256": index["head"], "payload": payload}
    raw = _bytes(event)
    if len(raw) > ROW_CAP:
        _error("event_limit")
    path = directory / "events" / ("%08d.json" % event["sequence"])
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    updated = {"last": event["sequence"], "head": _sha(raw)}
    _atomic_index(directory, updated)
    index.update(updated)


def _history(directory):
    directory = Path(directory).resolve()
    value = _json(_read(directory / "plan.json", REPORT_CAP), REPORT_CAP)
    _validate_plan(value)
    index = _json(_read(directory / "index.json", ROW_CAP), ROW_CAP)
    if (not isinstance(index, dict) or set(index) != {"last", "head"}
            or type(index["last"]) is not int or not 0 <= index["last"] <= EVENT_CAP
            or not _hex(index["head"])):
        _error("history_corrupt")
    parent, events = "0" * 64, []
    for sequence in range(1, index["last"] + 1):
        raw = _read(directory / "events" / ("%08d.json" % sequence), ROW_CAP)
        event = _json(raw, ROW_CAP)
        if (not isinstance(event, dict) or set(event) != {"sequence", "parent_sha256", "payload"}
                or event["sequence"] != sequence or event["parent_sha256"] != parent
                or not isinstance(event["payload"], dict)):
            _error("history_corrupt")
        events.append(event["payload"])
        parent = _sha(raw)
    if parent != index["head"]:
        _error("history_corrupt")
    names = []
    try:
        for entry in (directory / "events").iterdir():
            if not entry.is_file() or not re.fullmatch(r"\d{8}\.json", entry.name):
                _error("history_corrupt")
            names.append(entry.name)
            if len(names) > EVENT_CAP:
                _error("event_limit")
    except OSError:
        _error("history_corrupt")
    orphans = len(names) - index["last"]
    if orphans < 0:
        _error("history_corrupt")
    return directory, value, index, events, orphans


def enroll(value, sources, *, boundary, ingested_at, output):
    """Create one immutable prospective enrollment from declared local prefixes."""
    _validate_plan(value, sources)
    boundary, ingested = _time(boundary), _time(ingested_at)
    if boundary > ingested:
        _error("invalid_clock")
    directory = Path(output).resolve()
    if directory.exists():
        _error("existing_store")
    counts, identities = dict.fromkeys(REASONS, 0), set()
    index = {"last": 0, "head": "0" * 64}
    try:
        directory.mkdir(parents=True)
        (directory / "events").mkdir()
        with (directory / "plan.json").open("xb") as handle:
            handle.write(_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_index(directory, index)
        with _writer(directory):
            for source_number, source in enumerate(sources):
                for line, raw in _rows(source):
                    if counts["enrolled"] >= value["limits"]["cohort"]:
                        counts["cohort_cap"] += 1
                        continue
                    if raw is None:
                        counts["row_cap"] += 1
                        continue
                    try:
                        row = _json(raw, ROW_CAP)
                        chain, token, pool = _identity(row)
                        born, seen = _time(row.get("pool_created_at")), _time(row.get("seen_at"))
                        fetched = _time(row["fetched_at"]) if row.get("fetched_at") is not None else None
                        if any(t > ingested for t in (born, seen) + ((fetched,) if fetched else ())):
                            _error("future_clock")
                        if born > seen or seen > boundary or (fetched and (fetched < seen or fetched > boundary)):
                            _error("invalid_clock")
                        target = born + timedelta(hours=24)
                        if target < boundary:
                            _error("missed_before_enrollment")
                        key = _sha((chain + ":" + token).encode("ascii"))
                        if key in identities:
                            _error("duplicate")
                    except EvidenceError as exc:
                        reason = str(exc)
                        counts[reason if reason in counts else "invalid_row"] += 1
                        continue
                    identities.add(key)
                    counts["enrolled"] += 1
                    record = {"ordinal": counts["enrolled"], "source_ref": {
                        "source": source_number, "line": line, "sha256": _sha(raw)},
                        "chain": chain, "identity_sha256": key, "pool_sha256": _sha(pool.encode()),
                        "born_at": _iso(born), "target_at": _iso(target), "seen_at": _iso(seen),
                        "fetched_at": _iso(fetched) if fetched else None,
                        "fetch_time_state": "observed" if fetched else "missing",
                        "ingested_at": _iso(ingested), "enrollment_boundary": _iso(boundary)}
                    _append(directory, index, {"kind": "enrollment", "record": record,
                                              "counts": dict(counts)})
            _append(directory, index, {"kind": "enrollment_complete", "counts": dict(counts)})
    except EvidenceError:
        raise
    except (OSError, ValueError, OverflowError):
        _error("persistence_failed")
    return report(directory, now=_iso(ingested))


def _private_directory(value, safe):
    if not value or any(os.environ.get(k, "").lower() not in ("", "0", "false")
                        for k in ("CI", "GITHUB_ACTIONS")):
        _error("raw_directory_refused")
    try:
        path = Path(value).resolve()
        safe = Path(safe).resolve()
        if path == safe or path in safe.parents or safe in path.parents:
            _error("raw_directory_refused")
        if any((parent / ".git").exists() for parent in (path,) + tuple(path.parents)):
            _error("raw_directory_refused")
    except (OSError, TypeError, ValueError):
        _error("raw_directory_refused")
    return path


def _resolve(record, value, sources):
    _validate_plan(value, sources)
    ref = record.get("source_ref", {})
    number, wanted = ref.get("source"), ref.get("line")
    if type(number) is not int or not 0 <= number < len(sources) or type(wanted) is not int or wanted < 1:
        _error("source_reference_mismatch")
    for line, raw in _rows(sources[number]):
        if line == wanted:
            if raw is None or _sha(raw) != ref.get("sha256"):
                _error("source_reference_mismatch")
            identity = _identity(_json(raw, ROW_CAP))
            if (_sha((identity[0] + ":" + identity[1]).encode()) != record.get("identity_sha256")
                    or _sha(identity[2].encode()) != record.get("pool_sha256")):
                _error("source_reference_mismatch")
            return identity
    _error("source_reference_mismatch")


def _raw_fields(packet):
    for name in ("reserve", "ohlcv", "oracle", "engine"):
        field = packet.get(name)
        if not isinstance(field, dict):
            continue
        raw = field.get("raw")
        if raw is not None and (not isinstance(raw, str) or len(raw) > 4 * ((RAW_CAP + 2) // 3)):
            _error("raw_limit")
        if isinstance(raw, str):
            try:
                decoded = base64.b64decode(raw, validate=True)
            except (ValueError, TypeError):
                continue
            if len(decoded) > RAW_CAP:
                _error("raw_limit")


def _stage(field, imported):
    result = {"state": "not_asked", "http_status": None, "request_at": None,
              "response_at": None, "raw_sha256": None, "field_coverage": False,
              "request_time_state": "missing", "response_time_state": "missing",
              "timing_state": "missing_clock"}
    if field is None:
        return result, None
    if not isinstance(field, dict):
        result["state"] = "invalid_evidence"
        return result, None
    clocks = {}
    for name, time_state in (("request_at", "request_time_state"), ("response_at", "response_time_state")):
        if field.get(name) is None:
            continue
        try:
            clock = _time(field[name])
        except EvidenceError:
            result[time_state] = "invalid"
        else:
            result[name] = _iso(clock)
            result[time_state] = "observed" if clock <= imported else "invalid"
            clocks[name] = clock
    if ("invalid" in (result["request_time_state"], result["response_time_state"])
            or (len(clocks) == 2 and clocks["request_at"] > clocks["response_at"])):
        result["timing_state"] = "invalid_clock"
    elif all(result[name] == "observed" for name in ("request_time_state", "response_time_state")):
        result["timing_state"] = "observed"
    status = field.get("http_status")
    result["http_status"] = status if type(status) is int and 100 <= status <= 599 else None
    body, raw_error = None, None
    if field.get("raw") is not None:
        try:
            raw = base64.b64decode(field["raw"], validate=True)
            digest = _sha(raw)
            if digest != field.get("sha256"):
                _error("raw_hash_mismatch")
            result["raw_sha256"] = digest
        except (EvidenceError, ValueError, TypeError):
            raw_error = "invalid_evidence"
        else:
            try:
                body = _json(raw, RAW_CAP)
                if "parsed" in field and field["parsed"] != body:
                    _error("parsed_mismatch")
            except EvidenceError as exc:
                raw_error = "invalid_evidence" if str(exc) == "parsed_mismatch" else "invalid_body"
    else:
        raw_error = "missing_raw"
    observed_state = field.get("state")
    if observed_state != "observed":
        result["state"] = observed_state if isinstance(observed_state, str) and observed_state in STATES else "invalid_evidence"
        return result, None
    if result["http_status"] != 200:
        result["state"] = ("http_429" if status == 429 else "http_refusal" if type(status) is int and 300 <= status < 500 else "http_failure")
        return result, None
    if raw_error:
        result["state"] = raw_error
        return result, None
    result["state"] = "observed"
    return result, body


def _endpoint_set(values):
    if not isinstance(values, list) or len(values) > 128:
        return None
    results = set()
    for value in values:
        if not isinstance(value, str) or len(value) > 4096:
            return None
        try:
            parsed = urlsplit(value if "://" in value else "https://" + value)
            if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
                return None
        except ValueError:
            return None
        parts = ["{id}" if x.startswith("0x") or len(x) > 25 or x.isdigit() else x
                 for x in parsed.path.strip("/").split("/") if x]
        results.add(_sha((parsed.hostname + "/" + "/".join(parts)).encode()))
    return sorted(results)


def _independence(packet):
    endpoint = packet.get("endpoints")
    endpoint = endpoint if isinstance(endpoint, dict) else {}
    label, engine, eligibility = (_endpoint_set(endpoint.get(k)) for k in ("label", "engine", "eligibility"))
    overlap = sorted(set(label or []) & set(engine or []))
    state = ("independence_unobserved" if not label or not engine else
             "independence_failed" if overlap else "independence_observed")
    return {"state": state, "label": label or [], "engine": engine or [],
            "eligibility": eligibility or [], "overlap": overlap,
            "eligibility_shared": bool(set(eligibility or []) & set(engine or []))}


def _daily_query_context(parsed, field):
    """A daily current-series declaration must agree with its acquisition clocks."""
    from urllib.parse import parse_qs
    try:
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=16)
        if "aggregate" in query and query["aggregate"] != ["1"]:
            return "invalid_daily_query"
        if "before_timestamp" not in query:
            return "current_series"
        values = query["before_timestamp"]
        if len(values) != 1 or not re.fullmatch(r"[0-9]{1,16}", values[0]):
            return "invalid_daily_query"
        before = int(values[0])
        begin, end = _time(field.get("request_at")), _time(field.get("response_at"))
        if not begin.timestamp() <= before <= end.timestamp():
            return "historical_or_mismatched_query"
        return "current_series"
    except (ValueError, TypeError, AttributeError, EvidenceError):
        return "query_context_unavailable"


def _source_targets(packet, chain, token, pool):
    """Bind the declared request targets as well as the body key; no live claim."""
    result = {"oracle": False, "ohlcv": False, "reserve": False}
    endpoint = packet.get("endpoints")
    endpoint = endpoint if isinstance(endpoint, dict) else {}
    expected_pool = "/api/v2/networks/%s/pools/%s" % (labels.GT_NETWORK[chain], pool)
    daily_queries = []
    for role in ("label", "eligibility"):
        values = endpoint.get(role)
        if not isinstance(values, list) or len(values) > 128:
            continue
        for value in values:
            if not isinstance(value, str) or len(value) > 4096:
                continue
            try:
                parsed = urlsplit(value if "://" in value else "https://" + value)
                if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
                    continue
            except ValueError:
                continue
            if parsed.hostname == "api.geckoterminal.com":
                result["reserve"] |= role == "eligibility" and parsed.path.lower() == expected_pool
                if role == "label" and parsed.path.lower() == expected_pool + "/ohlcv/day":
                    daily_queries.append(_daily_query_context(parsed, packet.get("ohlcv")))
            if parsed.hostname == "api.gopluslabs.io" and role == "label":
                from urllib.parse import parse_qs
                try:
                    query = parse_qs(parsed.query, max_num_fields=16)
                except ValueError:
                    continue
                targets = query.get("contract_addresses")
                result["oracle"] |= (parsed.path == "/api/v1/token_security/" + labels.GOPLUS_CHAIN_ID[chain]
                                      and isinstance(targets, list) and len(targets) == 1
                                      and _address(targets[0]) == token)
    query_state = ("query_context_unavailable" if not daily_queries else
                   next((state for state in daily_queries if state != "current_series"), "current_series"))
    result["ohlcv"] = bool(daily_queries) and all(state == "current_series" for state in daily_queries)
    return result, query_state


def _volume(stage, body, born_at):
    stage.update(recent_volume_7d=None, outcome_label=None, recent_days_observed=0,
                 recent_window_complete=False, recent_window_state="unavailable")
    if stage["state"] != "observed":
        return None
    if stage["timing_state"] != "observed":
        stage["recent_window_state"] = stage["timing_state"]
        return None
    try:
        rows = body["data"]["attributes"]["ohlcv_list"]
        if not isinstance(rows, list) or not rows or len(rows) > 1000:
            raise ValueError()
        acquired = _time(stage["response_at"])
        born = _time(born_at)
        # The unchanged helper sums seven daily buckets, including the current bucket.
        # Seven old/sparse rows are not necessarily those seven calendar buckets.
        recent_start = acquired.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
        stage.update(recent_window_start_at=_iso(recent_start), recent_window_end_at=_iso(acquired))
        normalized = []
        previous = None
        for row in rows:
            if not isinstance(row, list) or len(row) != 6:
                raise ValueError()
            numbers = [_number(x) for x in row]
            if any(x is None for x in numbers) or (previous is not None and numbers[0] >= previous):
                raise ValueError()
            if (not numbers[0].is_integer() or numbers[0] % 86400 != 0
                    or numbers[0] > acquired.timestamp()
                    or numbers[0] + 86400 <= born.timestamp()):
                raise ValueError()
            previous = numbers[0]
            normalized.append(numbers)
        if any(row[0] < recent_start.timestamp() for row in normalized[:7]):
            raise ValueError()
        outcome, facts = labels.outcome_label(normalized)
        volume = _number(facts.get("recent_volume_7d"))
        if volume is None:
            raise ValueError()
        stage.update(field_coverage=True, recent_volume_7d=volume, outcome_label=outcome,
                     recent_days_observed=len(normalized[:7]), recent_window_state="observed_buckets")
        # An array's length cannot establish complete temporal coverage. In particular,
        # a newly born pool's sparse candles are not seven fully observed days.
        return facts
    except (TypeError, KeyError, ValueError, EvidenceError, OverflowError):
        stage["state"] = "invalid_body"
        return None


def _oracle(stage, body, token, volume):
    stage.update(label=None, label_state="not_available")
    replay = {"label": None, "reasons": [], "outcome": None}
    if stage["state"] != "observed":
        return replay
    if not isinstance(body, dict) or type(body.get("code")) is not int or body["code"] != 1 or not isinstance(body.get("result"), dict):
        stage["state"] = "invalid_body"
        return replay
    matches = [item for key, item in body["result"].items() if _address(key) == token]
    if len(matches) != 1 or not isinstance(matches[0], dict) or not matches[0]:
        stage["state"] = "invalid_evidence"
        return replay
    fields = matches[0]
    holder = _number(fields.get("holder_count"))
    cex = fields.get("is_in_cex")
    coverage = (all(type(fields.get(k)) in (str, int) and str(fields[k]) in ("0", "1") for k in FLAGS)
                and all(_number(fields.get(k)) is not None for k in ("buy_tax", "sell_tax"))
                and holder is not None and holder.is_integer()
                and isinstance(fields.get("owner_address"), str)
                and (fields["owner_address"] == "" or _address(fields["owner_address"]) is not None)
                and isinstance(cex, dict) and type(cex.get("listed")) in (str, int)
                and str(cex["listed"]) in ("0", "1"))
    stage["field_coverage"] = coverage
    if not coverage:
        stage["label_state"] = "unavailable_fields"
        return replay
    try:
        label, reasons, _subset = labels.goplus_label(
            {"result": {token: fields}}, token, recent_volume_7d=volume)
        if label not in (None, "safe", "unsafe", "centralized"):
            raise ValueError()
        stage.update(label=label, label_state="returned_null" if label is None else "returned")
        replay.update(label=label, reasons=reasons)
    except Exception:
        stage["label_state"] = "label_error"
    return replay


def _receipt(packet, record, identity, value, imported):
    chain, token, pool = identity
    stages, bodies = {}, {}
    for name in ("reserve", "ohlcv", "oracle", "engine"):
        stages[name], bodies[name] = _stage(packet.get(name), imported)
    valid_identity = (packet.get("chain") == chain and _address(packet.get("token")) == token
                      and _pool(packet.get("pool")) == pool)
    targets, query_state = _source_targets(packet, chain, token, pool)
    stages["ohlcv"]["query_state"] = query_state
    for name, matched in targets.items():
        stages[name]["source_target_state"] = "declared_match" if matched else "unobserved_or_mismatched"
        if not matched and stages[name]["state"] == "observed":
            stages[name]["state"] = "invalid_evidence"
    reserve = stages["reserve"]
    reserve["reserve_usd"] = None
    if not valid_identity:
        for stage in stages.values():
            stage["state"] = "invalid_evidence"
    if reserve["state"] == "observed":
        try:
            if not isinstance(bodies["reserve"], dict):
                raise ValueError()
            body = bodies["reserve"]["data"]
            if not isinstance(body, dict):
                raise ValueError()
            attributes = body["attributes"]
            if not isinstance(attributes, dict):
                raise ValueError()
            number = _number(attributes.get("reserve_in_usd"))
            if (body.get("id") != labels.GT_NETWORK[chain] + "_" + pool
                    or _pool(attributes.get("address")) != pool):
                _error("pool_mismatch")
            if number is None:
                raise ValueError()
            reserve.update(reserve_usd=number, field_coverage=True)
        except EvidenceError:
            reserve["state"] = "invalid_evidence"
        except (KeyError, TypeError, ValueError):
            reserve["state"] = "invalid_body"
    facts = _volume(stages["ohlcv"], bodies["ohlcv"], record["born_at"])
    replay = _oracle(stages["oracle"], bodies["oracle"], token, stages["ohlcv"]["recent_volume_7d"])
    replay["outcome"] = facts
    engine, pool_mismatch = stages["engine"], False
    engine.update(verdict=None, context_at=None, source_sha256=value["engine_sha256"],
                  observed_source_sha256=packet.get("engine_sha256") if _hex(packet.get("engine_sha256")) else None)
    if engine["state"] == "observed":
        try:
            body = bodies["engine"]
            if not isinstance(body, dict) or not isinstance(body.get("evidence"), dict):
                raise ValueError()
            best = body["evidence"].get("best_pair") or {}
            if not isinstance(best, dict):
                raise ValueError()
            context = _time(packet.get("engine_context_at"))
            if (packet.get("engine_source_commit") != value["source_commit"]
                    or packet.get("engine_sha256") != value["engine_sha256"]
                    or _address(body.get("address")) != token
                    or not _time(engine["request_at"]) <= context <= _time(engine["response_at"])):
                _error("engine_mismatch")
            if body.get("risk_level") not in ("low", "medium", "high", "unknown") or not isinstance(body.get("signals"), list):
                raise ValueError()
            pool_mismatch = _pool(best.get("pair_address")) != pool or best.get("chain") != chain
            engine.update(verdict=body["risk_level"], context_at=_iso(context), field_coverage=True,
                          selected_pool_sha256=_sha(str(best.get("pair_address") or "").lower().encode()))
        except EvidenceError:
            engine["state"] = "invalid_evidence"
        except (TypeError, KeyError, ValueError):
            engine["state"] = "invalid_body"
    independence = _independence(packet)
    timing = {"age_seconds": None, "lateness_seconds": None, "skew_seconds": None,
              "tolerance": None, "simultaneous_claim": False,
              "range_state": "observed" if all(s["timing_state"] == "observed" for s in stages.values()) else "incomplete",
              "skew_scope": "known_clocks_only"}
    label_time = stages["oracle"]["request_at"]
    if label_time:
        timing.update(age_seconds=(_time(label_time) - _time(record["born_at"])).total_seconds(),
                      lateness_seconds=(_time(label_time) - _time(record["target_at"])).total_seconds())
    time_values = [stage[k] for stage in stages.values() for k in ("request_at", "response_at") if stage[k]]
    if time_values:
        time_values = [_time(t) for t in time_values]
        timing["skew_seconds"] = (max(time_values) - min(time_values)).total_seconds()
    # This is an evidence-availability count, never a tolerated-skew or W40 success rule.
    qualified = (all(stages[k]["state"] == "observed" for k in stages)
                 and all(stages[k]["timing_state"] == "observed" for k in stages)
                 and reserve["reserve_usd"] is not None and reserve["reserve_usd"] >= RULES["reserve_usd"]
                 and stages["oracle"]["label"] == "unsafe" and engine["verdict"] is not None
                 and independence["state"] == "independence_observed" and not pool_mismatch
                 and timing["lateness_seconds"] is not None and timing["lateness_seconds"] >= 0)
    result = {"ordinal": record["ordinal"], "source_ref": record["source_ref"],
              "imported_at": _iso(imported), "pool_mismatch": pool_mismatch,
              "timing": timing, "independence": independence,
              "qualified_unsafe_observed": bool(qualified)}
    result.update(stages)
    return result, replay


def ingest(output, sources, packet, *, private_dir, imported_at):
    """Import one saved packet. Intents survive failures; imports never resume live work."""
    raw_directory = _private_directory(private_dir, output)
    if not isinstance(packet, bytes) or len(packet) > PACKET_CAP:
        _error("packet_limit")
    value_packet = _json(packet, PACKET_CAP)
    if not isinstance(value_packet, dict):
        _error("invalid_packet")
    _raw_fields(value_packet)
    directory, value, index, events, orphans = _history(output)
    _validate_plan(value, sources)
    committed = {e.get("ordinal") for e in events if e.get("kind") == "receipt"}
    if orphans or any(e.get("kind") == "intent" and e.get("ordinal") not in committed for e in events):
        _error("incomplete_history")
    if value_packet.get("schema") != 1 or value_packet.get("plan_sha256") != value["plan_sha256"]:
        _error("plan_mismatch")
    ordinal = value_packet.get("ordinal")
    records = [e["record"] for e in events if e.get("kind") == "enrollment"]
    record = next((r for r in records if type(ordinal) is int and r["ordinal"] == ordinal), None)
    if record is None:
        _error("ordinal_not_enrolled")
    if any(e.get("kind") in ("receipt", "intent") and e.get("ordinal") == ordinal for e in events):
        _error("existing_receipt")
    if value_packet.get("source_ref") != record["source_ref"]:
        _error("source_reference_mismatch")
    imported = _time(imported_at)
    if imported < _time(record["ingested_at"]):
        _error("invalid_clock")
    identity = _resolve(record, value, sources)
    digest = _sha(packet)
    receipt, replay = _receipt(value_packet, record, identity, value, imported)
    receipt["packet_sha256"] = digest
    private_replay = _bytes(replay)
    if len(private_replay) > RAW_CAP:
        _error("raw_limit")
    receipt["replay_sha256"] = _sha(private_replay)
    try:
        with _writer(directory):
            # Recheck after exclusive acquisition, not merely before waiting for it.
            _dir, _plan, current, _events, current_orphans = _history(directory)
            if current != index or current_orphans:
                _error("history_changed")
            _append(directory, index, {"kind": "intent", "ordinal": ordinal,
                                      "packet_sha256": digest, "imported_at": _iso(imported)})
            raw_directory.mkdir(parents=True, exist_ok=True)
            for name, raw in ((digest + ".packet", packet), (digest + ".replay.json", private_replay)):
                with (raw_directory / name).open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
            _append(directory, index, {"kind": "receipt", "ordinal": ordinal, "receipt": receipt})
    except EvidenceError:
        raise
    except Exception:
        _error("persistence_failed")
    return receipt


def report(output, *, now, live_start=None):
    """Read safe history only. A due report still makes no experiment decision."""
    _directory, value, _index, events, orphans = _history(output)
    instant = _time(now)
    records, receipts, intents = {}, {}, set()
    counts, complete = dict.fromkeys(REASONS, 0), False
    for event in events:
        kind = event.get("kind")
        if kind == "enrollment":
            record = event["record"]
            ordinal = record["ordinal"]
            if type(ordinal) is not int or ordinal != len(records) + 1 or ordinal > value["limits"]["cohort"]:
                _error("history_corrupt")
            records[ordinal] = record
            counts = event["counts"]
        elif kind == "enrollment_complete":
            counts, complete = event["counts"], True
        elif kind == "intent":
            if event.get("ordinal") not in records or event["ordinal"] in intents:
                _error("history_corrupt")
            intents.add(event["ordinal"])
        elif kind == "receipt":
            ordinal = event.get("ordinal")
            if ordinal not in intents or ordinal in receipts:
                _error("history_corrupt")
            receipts[ordinal] = event["receipt"]
        else:
            _error("history_corrupt")
    if set(counts) != set(REASONS) or any(type(n) is not int or n < 0 for n in counts.values()) or counts["enrolled"] != len(records):
        _error("history_corrupt")
    source_rows = sum(s["rows"] for s in value["sources"])
    unprocessed_rows = source_rows - sum(counts.values())
    if unprocessed_rows < 0 or (complete and unprocessed_rows):
        _error("history_corrupt")
    state, origin, start, end = "not_started", "none", None, None
    if live_start is not None:
        try:
            if (not isinstance(live_start, dict) or set(live_start) != {
                    "schema", "plan_sha256", "source_commit", "started_at", "evidence_sha256"}
                    or live_start["schema"] != 1 or live_start["plan_sha256"] != value["plan_sha256"]
                    or live_start["source_commit"] != value["source_commit"] or not _hex(live_start["evidence_sha256"])):
                _error("invalid_live_start")
            start_time = _time(live_start["started_at"])
            if start_time > instant:
                _error("invalid_live_start")
            end_time = start_time + timedelta(days=30)
            start, end = _iso(start_time), _iso(end_time)
            state, origin = ("not_due" if instant < end_time else "readout_due"), "declared_external_observation"
        except (EvidenceError, OverflowError):
            _error("invalid_live_start")
    oracle_states, qualified, rows, oracle_unasked = {}, 0, [], 0
    for ordinal, record in records.items():
        row = dict(record)
        receipt = receipts.get(ordinal)
        if receipt:
            stage = receipt.get("oracle", {})
            if (not isinstance(stage.get("state"), str) or stage["state"] not in STATES
                    or stage.get("label") not in (None, "unsafe", "safe", "centralized")):
                _error("history_corrupt")
            oracle_states[stage["state"]] = oracle_states.get(stage["state"], 0) + 1
            oracle_unasked += int(stage["state"] == "not_asked")
            qualified += int(receipt.get("qualified_unsafe_observed") is True)
            row["receipt"] = receipt
        if len(rows) < DETAIL_CAP:
            rows.append(row)
    result = {"schema": 1, "plan_sha256": value["plan_sha256"], "state": state,
              "clock_evidence": origin, "started_at": start, "ends_at": end,
              "rules": dict(RULES), "limits": value["limits"], "outcome": "not_evaluated",
              "enrollment_complete": complete, "enrollment_counts": counts,
              "enrolled": len(records), "receipts": len(receipts),
              "unasked": len(records) - len(receipts) + oracle_unasked,
              "unimported": len(records) - len(intents),
              "pending_intents": len(intents - set(receipts)), "orphan_events": orphans,
              "original_unsafe_target": 18, "qualified_unsafe_observed": qualified,
              "oracle_states": oracle_states, "rows": rows, "rows_omitted": len(records) - len(rows),
              "source_rows": source_rows, "unprocessed_source_rows": unprocessed_rows,
              "unexamined_source_rows": counts["cohort_cap"] + counts["row_cap"] + unprocessed_rows,
              "limitations": ["offline_core_no_live_work", "source_commit_declared",
                              "no_approved_lateness_or_skew_tolerance", "no_daily_capacity_inference",
                              "observation_count_is_not_W40_success", "private_material_not_revalidated_by_report"]}
    while len(_bytes(result)) > REPORT_CAP and result["rows"]:
        result["rows"].pop()
        result["rows_omitted"] += 1
    if len(_bytes(result)) > REPORT_CAP:
        _error("report_limit")
    return result


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        _error("invalid_arguments")


def main(argv=None):
    parser = _Parser(prog="w40_evidence.py", description=__doc__)
    commands = parser.add_subparsers(dest="command")
    p = commands.add_parser("plan")
    p.add_argument("--source-commit", required=True)
    p.add_argument("--sources", required=True)
    p = commands.add_parser("enroll")
    for option in ("plan", "sources", "boundary", "ingested-at", "output"):
        p.add_argument("--" + option, required=True)
    p = commands.add_parser("ingest")
    for option in ("output", "sources", "packet", "private-dir", "imported-at"):
        p.add_argument("--" + option, required=True)
    p = commands.add_parser("report")
    p.add_argument("--output", required=True)
    p.add_argument("--now", required=True)
    p.add_argument("--live-start")
    try:
        args = parser.parse_args(argv)
    except EvidenceError:
        print('{"error":"invalid_arguments"}')
        return 2
    if args.command is None:
        parser.print_help()
        return 0
    try:
        sources = _json(_read(args.sources, REPORT_CAP), REPORT_CAP) if hasattr(args, "sources") else None
        if args.command == "plan":
            result = plan(args.source_commit, sources)
        elif args.command == "enroll":
            value = _json(_read(args.plan, REPORT_CAP), REPORT_CAP)
            result = enroll(value, sources, boundary=args.boundary, ingested_at=args.ingested_at, output=args.output)
        elif args.command == "ingest":
            # Refuse CI/raw paths before reading or writing any packet material.
            _private_directory(args.private_dir, args.output)
            raw = _read(args.packet, PACKET_CAP)
            result = ingest(args.output, sources, raw, private_dir=args.private_dir, imported_at=args.imported_at)
        else:
            start = _json(_read(args.live_start, ROW_CAP), ROW_CAP) if args.live_start else None
            result = report(args.output, now=args.now, live_start=start)
        raw = _bytes(result)
        if len(raw) > REPORT_CAP:
            _error("report_limit")
        print(raw.decode("ascii"))
        return 0
    except EvidenceError as exc:
        print(_bytes({"error": str(exc)}).decode("ascii"))
        return 2
    except Exception:
        print('{"error":"invalid_input"}')
        return 2


if __name__ == "__main__":
    sys.exit(main())
