"""Route an existing HTTP/MCP assessment response without performing any action.

This is a limited policy example, not whole-schema validation or permission to
place an order. Unused scores/evidence do not change the verdict-routing policy.
"""

import argparse
import json
import sys

BYTE_CAP = 1024 * 1024
_VERDICTS = ("high", "medium", "low", "unknown")
_ACTIONS = {"high": ("reject", "high_risk"),
            "medium": ("manual_review", "risk_requires_review"),
            "low": ("continue_evaluation", "checks_ran_without_fatal_signal")}


def _decision(action, reason, delay=None):
    return {"action": action, "reason": reason, "retry_after_seconds": delay}


def _route(payload):
    verdict = payload.get("risk_level")
    if type(verdict) is not str or verdict not in _VERDICTS:
        return _decision("abstain", "invalid_verdict")
    if verdict != "unknown":
        action, reason = _ACTIONS[verdict]
        return _decision(action, reason)

    kind = payload.get("unknown_kind")
    if type(kind) is not str or kind not in ("coverage", "infrastructure", "mixed"):
        return _decision("abstain", "unknown_kind_unavailable")
    if kind == "coverage":
        return _decision("abstain", "coverage_requires_abstention")
    action, delay = payload.get("next_action"), payload.get("retry_after_seconds")
    if (type(action) is str and action == "retry" and type(delay) is int
            and 1 <= delay <= 2147483647):
        return _decision("retry", "infrastructure_retry_advised", delay)
    return _decision("abstain", "retry_guidance_invalid")


def route_http(payload, http_status=200):
    """Read only HTTP status/error/verdict/guidance; never retain response content."""
    if type(http_status) is not int or http_status != 200 or type(payload) is not dict or "error" in payload:
        return _decision("abstain", "invalid_envelope")
    return _route(payload)


def route_mcp(envelope, http_status=200):
    """Use structuredContent only; any transport/top-level/tool error wins first."""
    if (type(http_status) is not int or http_status != 200
            or type(envelope) is not dict or "error" in envelope):
        return _decision("abstain", "invalid_envelope")
    result = envelope.get("result")
    if type(result) is not dict or ("isError" in result and result["isError"] is not False):
        return _decision("abstain", "invalid_envelope")
    payload = result.get("structuredContent")
    if type(payload) is not dict:
        return _decision("abstain", "invalid_envelope")
    return _route(payload)


def _emit(value):
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False))


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # Ordinary argparse diagnostics may echo private argument values.
        _emit({"error": "arguments_refused"})
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
    parser = _Parser(prog="assessment_policy", description=__doc__, allow_abbrev=False)
    parser.add_argument("--transport", required=True, choices=("http", "mcp"))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(BYTE_CAP + 1)
        if len(raw) > BYTE_CAP:
            raise ValueError("input_too_large")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (OSError, ValueError, TypeError, RecursionError, OverflowError, UnicodeError):
        _emit({"error": "input_refused"})
        return 1
    result = route_http(payload) if args.transport == "http" else route_mcp(payload)
    _emit(result)
    # A valid abstention is a policy result, not a command failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
