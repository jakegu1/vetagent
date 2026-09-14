"""production_probe.py -- observe the abuse guards on the live service, and keep the result.

Usage:
    python bench/production_probe.py            # probe and print
    python bench/production_probe.py --write    # also write bench/production/guards-probe.json

Why this exists
---------------
On 2026-09-14 every test was green while production served 313 tool calls in 100 seconds
from one IP, past a rate limiter the tests said worked -- Cloudflare's binding answered
"allowed" to every call. The deploy smoke test caught it, but a smoke test's verdict lives
in a CI log that expires, and the maturity score can only read what was committed. So the
guards are probed on a schedule and the observation is written to a file the scorecard
reads (`bench/scorecard.py`, "production guards observed live").

What it sends: `tools/call` with an invalid address, which the server rejects before any
upstream request -- the flood costs the shared upstream budget nothing -- and one batch one
message over the cap. Every request names itself `vetagent-ci-smoke`, which the usage gate
counts as ours. It does not call anything but vetagent.dev.
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(HERE, "production", "guards-probe.json")
ENDPOINT = "https://vetagent.dev/mcp"
TAG = "vetagent-ci-smoke"
# The existing deploy smoke test's bound, reused rather than tuned to a reading.
FLOOD_CALLS = 75


def max_batch():
    """MAX_BATCH read out of src/entry.py, so the probe cannot drift from the code."""
    text = open(os.path.join(ROOT, "src", "entry.py"), encoding="utf-8").read()
    m = re.search(r"^MAX_BATCH = (\d+)", text, re.M)
    return int(m.group(1)) if m else None


def post(body):
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "x-mcp-client": TAG,
                 "user-agent": "vetagent-production-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001 -- a probe that could not run is recorded as such
        return type(e).__name__


def call(i):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": "assess_token_risk", "arguments": {"address": "not-an-address"}}}


def probe():
    flood = {"ran": False, "calls": 0, "calls_until_429": None, "statuses": {}}
    for i in range(1, FLOOD_CALLS + 1):
        status = post(call(i))
        flood["ran"] = True
        flood["calls"] = i
        flood["statuses"][str(status)] = flood["statuses"].get(str(status), 0) + 1
        if status == 429:
            flood["calls_until_429"] = i
            break
    # A request that never got an HTTP answer is not evidence the guard is off.
    if not any(k.isdigit() for k in flood["statuses"]):
        flood["ran"] = False

    cap = max_batch()
    batch = {"ran": False, "messages": None, "http_status": None}
    if cap:
        # The flood may have tripped the limiter; a batch is checked for size before any
        # message is rate-limited, so the cap answers 400 either way.
        status = post([call(i) for i in range(cap + 1)])
        batch = {"ran": isinstance(status, int), "messages": cap + 1, "http_status": status}

    return {
        "probed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checked_out_sha": os.environ.get("GITHUB_SHA", ""),
        "flood": flood,
        "batch_cap": batch,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    result = probe()
    print(json.dumps(result, indent=1))
    if args.write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
        print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
