"""Read-only snapshot freshness and latest-pass coverage monitor.

Twelve hours is an operational alarm, allowing two nominal collection intervals.
Pass counts include manual observations; they do not prove scheduled triggers. The
daily observer shares GitHub's scheduler with collection, so this is not independent
uptime monitoring. Only manifests are read, never the archived pool observations.
All JSON and timestamps are validated. Coverage is checked for the latest pass and
the inclusive last 24 hours; older schema history cannot describe current coverage.
The optional older_passes_not_checked field counts distinct older passes excluded
from coverage evaluation and is emitted only when positive.
"""

import argparse
import io
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import snapshot  # noqa: E402


def _duration(value):
    try:
        hours = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("maximum age must be a finite positive duration in hours") from None
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("maximum age must be a finite positive duration in hours")
    return hours


def _age_option(value):
    try:
        return _duration(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _complete(coverage):
    rows, _, gaps, causes = coverage
    return rows > 0 and gaps == 0 and not causes


def report(archive_dir=snapshot.OUT_DIR, *, now=None, max_age_hours=12):
    """Return observed health, preserving unavailable measurements as null.

    Invalid JSON or timestamps anywhere fail closed; all timestamps are normalized
    to UTC before grouping. Coverage is validated for the latest pass and the
    inclusive last 24 hours, so legacy history outside that scope cannot mask
    current health. Invalid relevant coverage never falls back to an older pass.
    """
    max_age_hours = _duration(max_age_hours)
    now = datetime.now(timezone.utc) if now is None else now
    if not hasattr(now, "utcoffset") or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the report clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    result = {"checked_at": now.isoformat(), "status": "unobserved",
              "latest_seen_at": None, "latest_age_hours": None,
              "observed_passes_24h": None, "complete_passes_24h": None,
              "coverage": None, "causes": {"manifest_missing_or_invalid": 1}}
    try:
        files = sorted(name for name in os.listdir(archive_dir)
                       if name.startswith("runs-") and name.endswith(".ndjson"))
        if not files:
            return result
        entries = []
        for name in files:
            before = len(entries)
            with io.open(os.path.join(archive_dir, name), encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        entries.append(json.loads(line))
            if len(entries) == before:
                return result
        passes = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("seen_at"), str):
                return result
            instant = datetime.fromisoformat(entry["seen_at"])
            if instant.tzinfo is None or instant.utcoffset() is None:
                return result
            instant = instant.astimezone(timezone.utc)
            if instant > now:
                result["causes"] = {"future_evidence": 1}
                return result
            passes.setdefault(instant, []).append(entry)
        latest = max(passes)
        window_start = now - timedelta(hours=24)
        coverages = {instant: snapshot._coverage(manifest)
                     for instant, manifest in passes.items()
                     if instant == latest or instant >= window_start}
        older_passes = len(passes) - len(coverages)
        if older_passes:
            result["older_passes_not_checked"] = older_passes
        if any(coverage[3].get("manifest_invalid") for coverage in coverages.values()):
            return result
        coverage = coverages[latest]
        rows, pages, gaps, causes = coverage
        complete = _complete(coverage)
        age = (now - latest).total_seconds() / 3600
        if not complete:
            status = "incomplete"
        elif age <= max_age_hours:
            status = "healthy"
        else:
            status = "stale"
        recent = [item for instant, item in coverages.items() if window_start <= instant <= now]
        result.update(status=status, latest_seen_at=latest.isoformat(), latest_age_hours=age,
                      observed_passes_24h=len(recent),
                      complete_passes_24h=sum(_complete(item) for item in recent),
                      coverage={"complete": complete, "rows": rows, "pages": pages, "gaps": gaps},
                      causes=dict(causes))
        return result
    except (OSError, ValueError, TypeError, OverflowError):
        # Exception strings may contain source paths or raw input. Emit only the
        # fixed category, and never convert an unreadable archive into zero passes.
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default=snapshot.OUT_DIR,
                        help="directory containing snapshot pass manifests")
    parser.add_argument("--max-age-hours", type=_age_option, default=12,
                        help="finite positive maximum pass age in hours (default: 12)")
    args = parser.parse_args(argv)
    result = report(args.archive_dir, max_age_hours=args.max_age_hours)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return {"healthy": 0, "stale": 1, "incomplete": 1, "unobserved": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
