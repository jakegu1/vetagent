"""Compose anonymous legacy telemetry aggregates offline; never collect new data.

The input timestamp and storage version are declarations, not authenticated source
or freshness evidence. Existing aggregate validation owns weights and query states.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

import operational_evidence as _op

BYTE_CAP = 1024 * 1024
_INPUT_KEYS = {"schema", "storage_schema", "captured_at", "aggregates"}
_SELECTION_KEYS = {"tool", "cohort", "start", "end", "reply"}
_AGGREGATE_FIELDS = ("state", "rows", "weighted_count", "sampled_rows", "sampled", "count_label")
_INTERPRETATION = "descriptive; not customer, readiness, or service-quality evidence"


def _stamp(value):
    if type(value) is not str or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is None:
        raise ValueError("invalid_time")
    try:
        return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("invalid_time") from None


def _bounded_json(value):
    """Apply the same finite JSON value/size boundary to direct Python callers."""
    try:
        size = 0
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        for chunk in encoder.iterencode(value):
            size += len(chunk.encode("utf-8"))
            if size > BYTE_CAP:
                raise ValueError("input_too_large")
    except (ValueError, TypeError, RecursionError, OverflowError, UnicodeError):
        raise ValueError("invalid_json_value") from None


def _missing(tool, cohort):
    return {"tool": tool, "cohort": cohort, "start": None, "end": None,
            "state": "not_queried", "rows": [], "weighted_count": None,
            "sampled_rows": None, "sampled": None,
            "count_label": "weighted events; not exact users"}


def diagnose(bundle):
    """Return a fixed, safe report or raise ValueError with a fixed refusal code.

    Query failures are ordinary partial reports. Invalid bundle metadata cannot
    establish even a declared query/window and is refused instead.
    """
    _bounded_json(bundle)
    if type(bundle) is not dict or set(bundle) != _INPUT_KEYS:
        raise ValueError("invalid_bundle")
    if bundle["schema"] != "telemetry-diagnostics-input-v1" or bundle["storage_schema"] != "legacy-v1":
        raise ValueError("unsupported_schema")
    captured = _stamp(bundle["captured_at"])
    aggregates = bundle["aggregates"]
    if type(aggregates) is not list or len(aggregates) > len(_op.TOOLS) * len(_op.COHORTS):
        raise ValueError("invalid_selections")
    selections = {}
    for item in aggregates:
        if type(item) is not dict or set(item) != _SELECTION_KEYS:
            raise ValueError("invalid_selection")
        tool, cohort = item["tool"], item["cohort"]
        if type(tool) is not str or type(cohort) is not str or tool not in _op.TOOLS or cohort not in _op.COHORTS:
            raise ValueError("invalid_selection")
        key = (tool, cohort)
        if key in selections:
            raise ValueError("duplicate_selection")
        start, end = _stamp(item["start"]), _stamp(item["end"])
        if not start < end <= captured or end - start > timedelta(days=90):
            raise ValueError("invalid_window")
        selections[key] = item

    results, failed = [], False
    for tool, cohort in sorted((t, c) for t in _op.TOOLS for c in _op.COHORTS):
        item = selections.get((tool, cohort))
        if item is None:
            results.append(_missing(tool, cohort))
            continue
        validated = _op.aggregate_reply(item["reply"], tool=tool, cohort=cohort,
                                        start=item["start"], end=item["end"])
        cell = {"tool": tool, "cohort": cohort, "start": item["start"], "end": item["end"]}
        cell.update({field: validated[field] for field in _AGGREGATE_FIELDS})
        results.append(cell)
        failed = failed or cell["state"] not in ("observed", "empty")

    capabilities = {name: {"state": "not_recorded"} for name in ("chain", "request_latency")}
    capabilities.update({name: {"state": "not_queried"} for name in
                         ("reason_breakdown", "error_rate", "liquidity_tool", "caller_identity")})
    capabilities["caller_identity"]["limitation"] = "unsupported_by_anonymous_diagnostics"
    return {"schema": "telemetry-diagnostics-report-v1", "captured_at": bundle["captured_at"],
            "state": "partial" if failed else "observed" if selections else "unobserved",
            "results": results, "capabilities": capabilities,
            "production_gate_evaluated": False, "interpretation": _INTERPRETATION}


def _diagnostic(code):
    print(json.dumps({"error": code}, ensure_ascii=True, allow_nan=False))


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's ordinary error text includes unknown arguments and filenames.
        _diagnostic("arguments_refused")
        raise SystemExit(2)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError("nonfinite_json")


def main(argv=None):
    parser = _Parser(prog="telemetry_diagnostics", description=__doc__, allow_abbrev=False)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        with Path(args.input).open("rb") as source:
            raw = source.read(BYTE_CAP + 1)
        if len(raw) > BYTE_CAP:
            raise ValueError("input_too_large")
        bundle = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
        report = diagnose(bundle)
        encoded = (json.dumps(report, sort_keys=True, ensure_ascii=True, allow_nan=False,
                              indent=2) + "\n").encode("ascii")
    except OSError:
        _diagnostic("input_unavailable")
        return 1
    except (ValueError, TypeError, RecursionError, OverflowError, UnicodeError):
        _diagnostic("input_refused")
        return 1
    try:
        # Exclusive create also refuses existing symlinks/hardlinks and input aliases.
        # A failed partial new write is retained; it is never overwritten or deleted.
        with Path(args.output).open("xb") as destination:
            destination.write(encoded)
    except (OSError, ValueError):
        _diagnostic("output_refused")
        return 1
    print(json.dumps({"state": report["state"]}, ensure_ascii=True))
    return 0 if report["state"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
