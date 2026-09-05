"""usage.py — usage numbers. Answers what the decision gate asks, not vanity metrics.

Why this isn't an analytics dashboard:
  Right now there is exactly one question worth answering — **is anyone outside calling
  this?** (decision gate 09-18 in DECISIONS/STRATEGY). "Total calls" can't answer it:
  ten thousand calls that are all mine are worth zero. So this computes three things:
  how many **distinct clients**, how many **distinct countries**, and the error rate.
  A dashboard can wait until there is traffic.

Usage:
    export CLOUDFLARE_API_TOKEN=...      # needs Account Analytics: Read
    export CLOUDFLARE_ACCOUNT_ID=...
    python bench/usage.py [--days 14]

Data comes from Cloudflare Analytics Engine (Worker-side writes: src/entry.py).
**The queried token address is deliberately not recorded** — that is the user's intent.
The price is that we have no idea which tokens are popular.
"""

import argparse
import json
import os
import subprocess
import sys

DATASET = "vetagent_calls"
API = "https://api.cloudflare.com/client/v4/accounts/%s/analytics_engine/sql"

# What each blob means is set by the write order in src/entry.py; change one, change both
BLOB = {"method": "blob1", "tool": "blob2", "verdict": "blob3",
        "client": "blob4", "country": "blob5"}


def query(sql, account, token):
    r = subprocess.run(
        ["curl", "-s", "-m", "45", "-X", "POST", API % account,
         "-H", "Authorization: Bearer %s" % token,
         "--data-binary", sql],
        capture_output=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"_raw": (r.stdout or "")[:400]}


def rows_of(resp):
    if not isinstance(resp, dict):
        return None
    if "data" in resp:
        return resp["data"]
    return None


# Our own traffic, excluded from the external-caller count. Add to this list rather than
# reasoning about it later: the whole value of the gate is that it can come back "no".
SELF_CLIENTS = {"claude-code", "curl", "python-requests", "vetagent-bench",
                "vetagent-contract-test", "unknown"}
OWNER_COUNTRIES = {"CN"}


def external_callers(account, token, since):
    """Distinct (client, calls) that are neither our tooling nor the owner's country."""
    resp = query(
        "SELECT %s AS client, %s AS country, count() AS n FROM %s "
        "WHERE timestamp > now() - %s GROUP BY client, country ORDER BY n DESC LIMIT 50"
        % (BLOB["client"], BLOB["country"], DATASET, since), account, token)
    out = {}
    for row in (rows_of(resp) or []):
        client = str(row.get("client") or "").strip().lower()
        country = str(row.get("country") or "").strip().upper()
        if not client or client in SELF_CLIENTS or country in OWNER_COUNTRIES:
            continue
        out[client] = out.get(client, 0) + int(float(row.get("n") or 0))
    return sorted(out.items(), key=lambda kv: -kv[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        print("Missing CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID.")
        print("The token needs Account Analytics: Read (the deploy token will do).")
        return 2

    since = "INTERVAL '%d' DAY" % args.days
    print("=" * 62)
    print("VetAgent usage · last %d days" % args.days)
    print("=" * 62)

    total = query(
        "SELECT count() AS calls, sum(double2) AS errors, "
        "count(DISTINCT %s) AS clients, count(DISTINCT %s) AS countries "
        "FROM %s WHERE timestamp > now() - %s"
        % (BLOB["client"], BLOB["country"], DATASET, since), account, token)

    rows = rows_of(total)
    if rows is None:
        print("\nQuery failed. Raw response:")
        print(json.dumps(total, ensure_ascii=False)[:600])
        print("\nUsually: token lacks Account Analytics: Read, or the account id is wrong.")
        return 1

    if not rows or int(float(rows[0].get("calls") or 0)) == 0:
        # The thing that matters: tell "nobody called" apart from "the write path never
        # fired". Both look like zero rows and they mean opposite things, and confusing
        # the two makes the decision gate answer the wrong question.
        print("\n0 records. Two possibilities, and you have to tell them apart:")
        print("  a) nobody has called yet — gate 09-18's answer is 'no external callers'")
        print("  b) the write path is broken — this 0 tells you nothing")
        print("\nHow to tell: send one call yourself, wait 1-2 minutes, rerun this.")
        print("  curl -s -X POST https://vetagent.dev/mcp -H 'Content-Type: application/json' \\")
        print("    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' > /dev/null")
        print("  records show up = writes work, and the earlier 0 was real.")
        print("  still 0 = writes are broken; fix _record() in src/entry.py first.")
        return 0

    r = rows[0]
    calls = int(float(r.get("calls") or 0))
    errors = int(float(r.get("errors") or 0))
    clients = int(float(r.get("clients") or 0))
    countries = int(float(r.get("countries") or 0))

    print("\nTotal calls     : %d" % calls)
    print("Errors          : %d (%.1f%%)" % (errors, 100.0 * errors / calls if calls else 0))
    print("Unique clients  : %d" % clients)
    print("Unique countries: %d" % countries)

    # ---- Gate 2026-09-18, counted by a rule written down BEFORE the gate falls due ----
    #
    # The old rule was "more than one client OR more than one country -> yes". An external
    # audit pointed out it could not fail honestly: `client` is a user-agent prefix, this
    # repository ships a .mcp.json that points the owner's own editor at production, and
    # one curl from anywhere is a second client. Two self-generated data points passed a
    # gate meant to detect strangers.
    #
    # The rule now: a caller counts only if its client name is not ours and its country is
    # not the owner's. Written here, in code, ahead of the date, so it cannot be adjusted
    # once the answer is visible.
    ext = external_callers(account, token, since)
    print("\n--- Gate 2026-09-18: is anyone outside this project using it? ---")
    print("  counting rule: distinct client names excluding %s, from countries "
          "excluding %s" % (", ".join(sorted(SELF_CLIENTS)) or "(none)",
                            ", ".join(sorted(OWNER_COUNTRIES)) or "(none)"))
    if not ext:
        print("  NO. Nothing that is not us.")
        print("  -> STRATEGY: distribution problem, not product. Experiment C only, "
              "no new features.")
    else:
        print("  YES: %s" % ", ".join("%s (%s)" % (c, n) for c, n in ext))
        print("  -> STRATEGY: keep following the roadmap.")
    print("  raw totals for context: %d clients / %d countries (includes us)"
          % (clients, countries))

    for title, col in (("By tool", BLOB["tool"]), ("By client", BLOB["client"]),
                       ("By country", BLOB["country"]), ("By verdict", BLOB["verdict"])):
        resp = query(
            "SELECT %s AS k, count() AS n FROM %s WHERE timestamp > now() - %s "
            "GROUP BY k ORDER BY n DESC LIMIT 8" % (col, DATASET, since), account, token)
        rs = rows_of(resp) or []
        if rs:
            print("\n%s:" % title)
            for row in rs:
                print("  %-28s %s" % ((row.get("k") or "(empty)")[:28], row.get("n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
