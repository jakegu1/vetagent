"""Offline input-availability inventory; a completed inventory is not a replay.

Pool fetched_at records a response observation. Sellability seen_at instead
records the earlier batch, so those rows have no certified response clock.
Only aggregate, fixed-schema facts leave this reader; source bytes stay put.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import stat
import sys


LIMITS = {"max_entries": 256, "max_file_bytes": 64 * 1024 * 1024,
          "max_total_bytes": 512 * 1024 * 1024,
          "max_line_bytes": 256 * 1024, "max_rows": 1000000}
KINDS = ("pools", "sellability", "runs")
FIELDS = {"pools": ("pool_id", "base_token", "reserve_usd", "price_usd",
                    "volume_usd", "transactions", "fetched_at"),
          "sellability": ("answered", "isHoneypot", "simulationSuccess",
                          "buyTax", "sellTax", "seen_at"),
          "runs": ("outcome", "rows", "page", "fetched_at", "recovery_fetched_at")}
COUNTS = ("bytes_read", "lines_read", "rows", "malformed_rows", "eligible_rows",
          "future_rows", "unknown_time_rows", "batch_time_only_rows")
NAME = re.compile(r"(pools|sellability|runs)-(\d{4}-\d{2}-\d{2})\.ndjson\Z")


def _instant(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _utc(value):
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _counts(kind):
    result = dict.fromkeys(COUNTS, 0)
    result.update(observation_min_utc=None, observation_max_utc=None,
                  field_presence=dict.fromkeys(FIELDS[kind], 0))
    return result


def _result(cutoff, limits):
    return {"schema": "snapshot-input-readiness-v1", "as_of_utc": _utc(cutoff),
            "status": "complete", "inventory_complete": True,
            "replay_ready": False, "independent_outcomes_established": False,
            "full_engine_inputs_validated": False,
            "reasons": ["engine_inputs_not_validated", "independent_outcomes_not_established",
                        "sellability_response_clock_not_recorded"],
            "limits": dict(limits), "diagnostics": [], "entries_seen": 0,
            "ignored_entries": 0, "files": [],
            "kinds": {kind: dict(_counts(kind), files=0, empty_files=0) for kind in KINDS}}


def _problem(result, diagnostic):
    result["inventory_complete"] = False
    if result["status"] == "complete":
        result["status"] = "incomplete"
    if diagnostic not in result["diagnostics"]:
        result["diagnostics"].append(diagnostic)


def _identity(info):
    # Windows fstat and lstat do not consistently expose the same ctime clock.
    # Birth time is stable there; mtime and byte count still detect a writer.
    changed = getattr(info, "st_birthtime_ns", info.st_ctime_ns) if os.name == "nt" else info.st_ctime_ns
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, changed)


def _symlink(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _open_readonly(path):
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags), "rb")


def _observation_time(kind, row):
    if kind == "sellability":
        return None
    if kind == "runs" and "recovery_fetched_at" in row:
        # The final recovery state cannot be available at its initial attempt.
        return _instant(row["recovery_fetched_at"])
    return _instant(row.get("fetched_at"))


def _object(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError
        row[key] = value
    return row


def _invalid_constant(value):
    raise ValueError


def _row(file_result, kind, row, cutoff):
    file_result["rows"] += 1
    for field in FIELDS[kind]:
        file_result["field_presence"][field] += int(field in row)
    observed = _observation_time(kind, row)
    if kind == "sellability" and _instant(row.get("seen_at")) is not None:
        file_result["batch_time_only_rows"] += 1
    if observed is None:
        file_result["unknown_time_rows"] += 1
        return
    field = "eligible_rows" if observed <= cutoff else "future_rows"
    file_result[field] += 1
    stamp = _utc(observed)
    for key, comparator in (("observation_min_utc", min), ("observation_max_utc", max)):
        old = file_result[key]
        file_result[key] = stamp if old is None else comparator(old, stamp, key=_instant)


def _read_file(path, before, file_result, kind, cutoff, limits, budget, result):
    digest = hashlib.sha256()
    complete = True
    with _open_readonly(path) as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            _problem(result, "source_changed")
            file_result["status"] = "source_changed"
            return
        while file_result["bytes_read"] < before.st_size:
            if budget["lines"] >= limits["max_rows"]:
                _problem(result, "row_cap")
                file_result["status"] = "row_cap"
                complete = False
                break
            # readline's size bounds allocation even for a newline-free file.
            line = stream.readline(min(limits["max_line_bytes"] + 1,
                                       before.st_size - file_result["bytes_read"]))
            if not line:
                _problem(result, "source_changed")
                file_result["status"] = "source_changed"
                complete = False
                break
            file_result["bytes_read"] += len(line)
            if len(line) > limits["max_line_bytes"]:
                _problem(result, "line_byte_cap")
                file_result["status"] = "line_byte_cap"
                complete = False
                break
            digest.update(line)
            budget["lines"] += 1
            file_result["lines_read"] += 1
            if not line.strip():
                continue
            try:
                row = json.loads(line.decode("utf-8"), object_pairs_hook=_object,
                                 parse_constant=_invalid_constant)
                if not isinstance(row, dict):
                    raise ValueError
            except (ValueError, UnicodeError, RecursionError):
                file_result["malformed_rows"] += 1
                _problem(result, "malformed_input")
                continue
            _row(file_result, kind, row, cutoff)
        try:
            stable = (_identity(before) == _identity(os.fstat(stream.fileno()))
                      == _identity(os.lstat(path)))
        except OSError:
            stable = False
    if not stable or (complete and file_result["bytes_read"] != before.st_size):
        _problem(result, "source_changed")
        file_result["status"] = "source_changed"
        return
    if complete:
        file_result["sha256"] = digest.hexdigest()
        file_result["hash_complete"] = True
        if file_result["malformed_rows"]:
            file_result["status"] = "malformed"
        elif file_result["unknown_time_rows"]:
            file_result["status"] = "unknown_time"
            _problem(result, "unknown_observation_time")
        else:
            file_result["status"] = "empty" if not file_result["lines_read"] else "ok"


def _source(path, kind, date, cutoff, limits, budget, result):
    file_result = dict(_counts(kind), kind=kind, date=date, status="unreadable",
                       sha256=None, hash_complete=False, source_bytes=None)
    result["files"].append(file_result)
    try:
        before = os.lstat(path)
        file_result["source_bytes"] = before.st_size
        if _symlink(before):
            _problem(result, "source_symlink")
            file_result["status"] = "symlink_refused"
        elif not stat.S_ISREG(before.st_mode):
            _problem(result, "source_not_regular")
            file_result["status"] = "not_regular"
        elif before.st_size > limits["max_file_bytes"]:
            _problem(result, "file_byte_cap")
            file_result["status"] = "file_byte_cap"
        elif budget["bytes"] + before.st_size > limits["max_total_bytes"]:
            _problem(result, "total_byte_cap")
            file_result["status"] = "total_byte_cap"
        else:
            budget["bytes"] += before.st_size
            _read_file(path, before, file_result, kind, cutoff, limits, budget, result)
    except (OSError, ValueError, OverflowError):
        _problem(result, "source_unreadable")
        file_result.update(status="unreadable", sha256=None, hash_complete=False)
    summary = result["kinds"][kind]
    summary["files"] += 1
    summary["empty_files"] += int(file_result["status"] == "empty")
    for key in COUNTS:
        summary[key] += file_result[key]
    for field in FIELDS[kind]:
        summary["field_presence"][field] += file_result["field_presence"][field]
    for key, comparator in (("observation_min_utc", min), ("observation_max_utc", max)):
        value = file_result[key]
        if value is not None:
            summary[key] = value if summary[key] is None else comparator(summary[key], value, key=_instant)


def inventory(archive, as_of, limits=None):
    """Inventory existing sources; optional lower limits support bounded callers."""
    bounds = dict(LIMITS)
    cutoff = _instant(as_of)
    valid = cutoff is not None and isinstance(archive, str) and 0 < len(archive) <= 4096 and "\0" not in archive
    if limits is not None:
        valid = valid and isinstance(limits, dict)
        if isinstance(limits, dict):
            for key, value in limits.items():
                if key not in bounds or type(value) is not int or not 0 < value <= bounds[key]:
                    valid = False
                else:
                    bounds[key] = value
    result = _result(cutoff, bounds)
    if not valid:
        _problem(result, "invalid_arguments")
        result["status"] = "invalid_arguments"
        return result
    try:
        archive = os.path.abspath(archive)
        current = archive
        while True:
            info = os.lstat(current)
            if _symlink(info):
                _problem(result, "source_symlink")
                return result
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        before = os.lstat(archive)
        if not stat.S_ISDIR(before.st_mode):
            _problem(result, "archive_not_directory")
            return result
        selected = []
        with os.scandir(archive) as entries:
            for entry in entries:
                result["entries_seen"] += 1
                if result["entries_seen"] > bounds["max_entries"]:
                    _problem(result, "entry_cap")
                    return result
                match = NAME.fullmatch(entry.name)
                try:
                    if match is None:
                        raise ValueError
                    datetime.strptime(match[2], "%Y-%m-%d")
                except ValueError:
                    result["ignored_entries"] += 1
                    _problem(result, "unsupported_entry")
                    continue
                selected.append((match[1], match[2], entry.path))
        budget = {"bytes": 0, "lines": 0}
        for kind, date, path in sorted(selected):
            _source(path, kind, date, cutoff, bounds, budget, result)
        if _identity(before) != _identity(os.lstat(archive)):
            _problem(result, "archive_changed")
        if any(result["kinds"][kind]["files"] == 0 for kind in KINDS):
            _problem(result, "source_kind_absent")
    except FileNotFoundError:
        _problem(result, "archive_absent")
        result["status"] = "absent"
    except (OSError, ValueError, OverflowError):
        _problem(result, "archive_unreadable")
        result["status"] = "unreadable"
    return result


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError


def main(argv=None):
    try:
        parser = _Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--archive", required=True)
        parser.add_argument("--as-of", required=True)
        args = parser.parse_args(argv)
        result = inventory(args.archive, args.as_of)
        if "invalid_arguments" in result["diagnostics"]:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        print(json.dumps({"schema": "snapshot-input-readiness-v1", "status": "invalid_arguments",
                          "inventory_complete": False, "replay_ready": False,
                          "independent_outcomes_established": False,
                          "diagnostics": ["invalid_arguments"]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["inventory_complete"] or result["files"] else 1


if __name__ == "__main__":
    sys.exit(main())
