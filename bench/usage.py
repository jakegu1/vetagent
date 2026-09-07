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
SELF_CLIENTS = {"curl", "python-requests", "vetagent-bench",
                "vetagent-contract-test", "unknown"}

# Clients that are OURS and also the most likely shape of a real user, so they can be
# neither counted nor silently dropped.
#
# `_client_name` reads the User-Agent, so "claude-code" is any Claude Code instance --
# the owner's editor and a stranger's, indistinguishable. It sat in SELF_CLIENTS, which
# means the gate excluded by name the single most likely client for a real user of an MCP
# server. That is a false negative exactly mirroring the crawler false positive: one rule
# counted robots as users, the same rule counted users as the owner.
#
# There is no honest way to separate them from what is recorded. The engine deliberately
# logs no address and no token, `request.cf.country` comes back "??" for every row, and
# adding an identifier to tell the owner apart from a customer would be tracking the
# customer. So the number is reported on its own line, with the ambiguity stated, and the
# owner can settle it in one move: remove vetagent from the owner's own MCP config, after
# which any claude-code traffic is external by construction.
AMBIGUOUS_CLIENTS = {"claude-code"}
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


def tool_callers(account, token, since):
    """Clients that actually invoked a tool, not clients that merely connected.

    This is the discriminator the first two versions of this gate were missing, and the
    data made it obvious the moment it existed. Over 14 days: 3,314 requests, of which
    **3,193 carry no tool name at all** -- 96.3%. Those are `initialize` and `tools/list`
    handshakes. Only 118 requests called a tool.

    The client names say the same thing out loud. sentineloracle, mcpbeat,
    rokmcp-collector, mcpscan, sasame-mcp-audit, mcpwatch, mcpwitness, mcp-observatory,
    endpointaudit, teppi-probe, wellknownbot, aisec-registry, lastseen-schema-probe,
    rootz-mcp-registry-prober, mcp-schema-archive, mcpgrade-probe, x402-observatory,
    mcp-stats-prober, mcplookup.com-probe, pod-directory-probe. Twenty of the forty-seven
    "external callers" have prober, scan, audit, watch, witness, observatory, index,
    archive, registry, census or stats in their own name. Registering in the official MCP
    registry buys an audience of directory crawlers, and they arrive first.

    "At least three calls on at least two days" -- the previous tightening -- does not
    help: sentineloracle made 1,259 requests. Volume is the one thing a crawler has in
    abundance. Calling a tool is the thing it has no reason to do.

    Note also that the country filter has never excluded anything: Analytics Engine
    reports every one of these as "??", so `OWNER_COUNTRIES` has been inert since the day
    it was written. A filter that has never removed a row is not protecting the gate.
    """
    resp = query(
        "SELECT %s AS client, %s AS tool, count() AS n, "
        "count(DISTINCT toDate(timestamp)) AS days FROM %s "
        "WHERE timestamp > now() - %s AND %s != '' "
        "GROUP BY client, tool ORDER BY n DESC LIMIT 200"
        % (BLOB["client"], BLOB["tool"], DATASET, since, BLOB["tool"]), account, token)
    rows = rows_of(resp)
    if rows is None:
        return None                      # query failed; not the same as "nobody called"
    by_client = {}
    for row in rows:
        client = str(row.get("client") or "").strip().lower()
        tool = str(row.get("tool") or "").strip()
        if not client or client in SELF_CLIENTS:
            continue
        if not tool or tool.startswith("__"):
            continue                     # auth probes are not tool use
        rec = by_client.setdefault(client, {"n": 0, "days": 0, "tools": set(),
                                            "ambiguous": client in AMBIGUOUS_CLIENTS})
        rec["n"] += int(float(row.get("n") or 0))
        rec["days"] = max(rec["days"], int(float(row.get("days") or 0)))
        rec["tools"].add(tool)
    return sorted(by_client.items(), key=lambda kv: -kv[1]["n"])


def caller_profile(account, token, since, clients):
    """Timing and verdict spread per client -- what separates a monitor from a user.

    Passing "did it call a tool" was necessary and is not sufficient. A thorough MCP
    auditor calls every tool once to check that each one answers; sasame-mcp-audit did
    exactly that, thirteen times across all three tools. So the filter that finally
    excluded crawlers still admits the diligent ones.

    Two things separate them, and both are already recorded:

    VERDICT SPREAD. A monitor re-tests the same fixed token, so it receives the same
    verdict every time. A user asks about the token in front of them, so the verdicts
    vary. One distinct verdict across forty calls is a health check; five distinct
    verdicts is somebody looking things up. This costs nothing -- `verdict` has been in
    the blob since the first version.

    HOUR SPREAD. A monitor runs on a timer and its calls land in a small number of
    repeating hours. A person or an agent works in bursts inside a waking day. Distinct
    hours-of-day, and calls per active day, separate those without recording anything
    about who is calling.

    Neither is conclusive alone and both are free. Reported so a human can read them
    together rather than have a threshold decide.
    """
    if not clients:
        return {}
    names = ", ".join("'%s'" % c.replace("'", "") for c, _ in clients)
    resp = query(
        "SELECT %s AS client, %s AS verdict, toDate(timestamp) AS day, "
        "toHour(timestamp) AS hour, count() AS n FROM %s "
        "WHERE timestamp > now() - %s AND %s != '' AND %s IN (%s) "
        "GROUP BY client, verdict, day, hour ORDER BY client LIMIT 1000"
        % (BLOB["client"], BLOB["verdict"], DATASET, since, BLOB["tool"],
           BLOB["client"], names), account, token)
    rows = rows_of(resp)
    if rows is None:
        return {}
    prof = {}
    for row in rows:
        c = str(row.get("client") or "").strip().lower()
        p = prof.setdefault(c, {"verdicts": {}, "hours": set(), "days": set(), "n": 0})
        v = str(row.get("verdict") or "").strip() or "(none)"
        n = int(float(row.get("n") or 0))
        p["verdicts"][v] = p["verdicts"].get(v, 0) + n
        p["hours"].add(int(float(row.get("hour") or 0)))
        p["days"].add(str(row.get("day")))
        p["n"] += n
    return prof


def print_profile(prof, clients):
    """Print the shape of each caller's traffic, without deciding for the reader."""
    if not prof:
        return
    print("\n  --- what each caller's traffic looks like ---")
    print("  %-26s %-6s %-6s %-7s %s"
          % ("client", "calls", "days", "hours", "verdicts seen"))
    for client, _ in clients:
        p = prof.get(client)
        if not p:
            continue
        vs = ", ".join("%s x%d" % (k, v) for k, v in
                       sorted(p["verdicts"].items(), key=lambda kv: -kv[1])[:5])
        print("  %-26s %-6d %-6d %-7d %s"
              % (client, p["n"], len(p["days"]), len(p["hours"]), vs))
    print("  A single repeated verdict across many calls is a health check on one fixed")
    print("  token. Varied verdicts are somebody looking different things up. Calls")
    print("  spread evenly over many hours is a timer; clustered in few hours is a person")
    print("  or an agent working. Neither settles it alone; read them together.")


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
    tools = tool_callers(account, token, since)

    print("\n--- Gate 2026-09-18: is anyone outside this project using it? ---")
    print("  counting rule: a client that is not ours AND actually called a tool.")
    print("  Connecting is not using. A first run of this gate answered YES on 47")
    print("  'external callers' of whom 20 have prober/scan/audit/registry in their own")
    print("  name, across 3,314 requests of which 3,193 carried no tool name at all.")

    if tools is None:
        print("  QUERY FAILED -- this is not the same as nobody calling.")
    elif not tools:
        print("  NO. %d clients connected and none of them called a tool."
              % len(ext or []))
        print("  -> STRATEGY: distribution problem, not product. Experiment C only, "
              "no new features.")
    else:
        clear = [(c, r) for c, r in tools if not r["ambiguous"]]
        murky = [(c, r) for c, r in tools if r["ambiguous"]]

        for client, rec in clear:
            print("  YES: %-28s %d calls on %d day(s): %s"
                  % (client, rec["n"], rec["days"], ", ".join(sorted(rec["tools"]))))
        for client, rec in murky:
            print("  MAYBE: %-26s %d calls on %d day(s): %s"
                  % (client, rec["n"], rec["days"], ", ".join(sorted(rec["tools"]))))
            print("         Cannot be told from the owner's own editor. `_client_name`")
            print("         reads the User-Agent, and this project deliberately records")
            print("         no address. Settle it by removing vetagent from the owner's")
            print("         own MCP config -- then this line is external by construction.")

        if clear:
            print("  -> STRATEGY: keep following the roadmap.")
        else:
            print("  -> NOT SETTLED. Every tool call came from a client that cannot be")
            print("     distinguished from us. Resolve the ambiguity above, then re-run.")

    if tools:
        print_profile(caller_profile(account, token, since, tools), tools)

    print("\n  for context, clients that merely connected: %d" % len(ext or []))
    if ext:
        print("    %s" % ", ".join("%s (%s)" % (c, n) for c, n in ext[:12]))
    print("  raw totals: %d clients / %d countries (includes us)"
          % (clients, countries))
    print("  NOTE: every row reports country '??', so the owner-country filter has")
    print("  never excluded anything. Do not read it as protection.")

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
