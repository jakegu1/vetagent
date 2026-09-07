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
# Only names WE chose for our own tooling. Nothing else can be assumed to be us.
#
# This set used to contain "unknown", "curl" and "python-requests" as well, and that cost
# 19 tool calls -- 16% of all tool use in 14 days -- which were filtered out and never
# looked at. "unknown" is what `_client_name` returns when a request carries no
# User-Agent at all: that is UNIDENTIFIED, not ours. And curl and python-requests are
# what any integrator reaches for first while trying a server out.
#
# The arithmetic that exposed it: 83 + 22 + 15 = 120 tool calls by tool, against 101
# attributed to the four clients the gate printed. A single genuine adopter making two
# calls sits exactly in that gap, and the gate was reporting on a set it had silently
# truncated.
SELF_CLIENTS = {"vetagent-bench", "vetagent-contract-test"}

# Anything naming itself vetagent-* is this project. An exact-match set is a list that
# has to be remembered at the exact moment nobody is thinking about it: the /assess
# instrumentation was verified with User-Agent `vetagent-r16-verify`, which is not in the
# set above, so the next run of this gate printed
#
#     YES: vetagent-r16-verify   1 call
#     -> STRATEGY: keep following the roadmap.
#
# The instrument built to answer "is anyone outside using this" answered YES on the
# developer's own test call, on its first day. A prefix cannot be forgotten.
LANDING_DEMO = "vetagent-landing-demo"


def is_self(client):
    """Ours: our tooling, our verification calls, our own landing-page demo button."""
    return client.startswith("vetagent-") or client in SELF_CLIENTS

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
AMBIGUOUS_CLIENTS = {"claude-code", "curl", "python-requests", "unknown",
                     "node", "undici", "mozilla", "python-httpx", "python-httpx2",
                     "go-http-client", "bun"}
OWNER_COUNTRIES = {"CN"}


def external_callers(account, token, since):
    """Distinct (client, calls) that are neither our tooling nor the owner's country."""
    resp = query(
        "SELECT %s AS client, %s AS country, count() AS n FROM %s "
        "WHERE timestamp > now() - %s GROUP BY client, country ORDER BY n DESC LIMIT 500"
        % (BLOB["client"], BLOB["country"], DATASET, since), account, token)
    out = {}
    for row in (rows_of(resp) or []):
        client = str(row.get("client") or "").strip().lower()
        country = str(row.get("country") or "").strip().upper()
        if not client or is_self(client) or country in OWNER_COUNTRIES:
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

    The country filter was inert for a different reason than anyone thought. Every row
    reported "??", and this docstring recorded that as a fact about Analytics Engine.
    It was a fact about `_country()`, which called `.get()` on a JsProxy that has no
    `.get`, and swallowed the AttributeError. Fixed 2026-09-07. Rows written before that
    date still say "??" and always will, so the filter only starts protecting the gate
    from today -- which is why `gate_verdict` treats "??" as unknown rather than as
    cleared.
    """
    resp = query(
        "SELECT %s AS client, %s AS tool, sum(_sample_interval) AS n, "
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
        if not client or is_self(client):
            continue
        if not tool or tool == "?" or tool.startswith("__"):
            continue    # auth probes and unnamed tools/call are not tool use
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
        "SELECT %s AS client, %s AS verdict, %s AS country, toDate(timestamp) AS day, "
        "toHour(timestamp) AS hour, sum(_sample_interval) AS n FROM %s "
        "WHERE timestamp > now() - %s AND %s != '' AND %s IN (%s) "
        "GROUP BY client, verdict, country, day, hour ORDER BY client LIMIT 1000"
        % (BLOB["client"], BLOB["verdict"], BLOB["country"], DATASET, since,
           BLOB["tool"], BLOB["client"], names), account, token)
    rows = rows_of(resp)
    if rows is None:
        return {}
    prof = {}
    for row in rows:
        c = str(row.get("client") or "").strip().lower()
        p = prof.setdefault(c, {"verdicts": {}, "hours": set(), "days": set(),
                                "countries": set(), "country_n": {}, "n": 0})
        v = str(row.get("verdict") or "").strip() or "(none)"
        n = int(float(row.get("n") or 0))
        p["verdicts"][v] = p["verdicts"].get(v, 0) + n
        p["hours"].add(int(float(row.get("hour") or 0)))
        p["days"].add(str(row.get("day")))
        c = str(row.get("country") or "??").strip().upper() or "??"
        p["countries"].add(c)
        p["country_n"][c] = p["country_n"].get(c, 0) + n
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


# --------------------------------------------------------------------------------------
# The gate's decision function. Frozen 2026-09-07, eleven days before the date.
# --------------------------------------------------------------------------------------
#
# Four counting rules have now been written for one gate, each after looking at the data
# the previous one produced, each on a 14-day window that slides under the reader's feet.
# That is fitting, whatever the intention: a rule chosen after seeing the answer is not a
# test. This is the last one, it lives in a function rather than in prose and a human's
# judgement, and `tests/test_usage_gate.py` pins its behaviour so it cannot drift quietly.
#
# It moves the bar UP, as every previous correction did. The five conditions are the
# properties the traffic actually observed does not have:
#
#   1. not ours          -- vetagent-* is this project, including the landing-page demo
#                           button and any verification call made while deploying
#   2. named a tool      -- "" and "?" are handshakes and malformed calls, not use
#   3. got an answer     -- at least one non-empty verdict. Scanners fuzz arguments and
#                           collect errors; sasame-mcp-audit called all three tools
#                           thirteen times and received a verdict on none of them
#   4. came back         -- two distinct days. One visit is a look, not use
#   5. asked more than   -- two distinct verdicts. A monitor re-checks one fixed token
#      one question         and sees one verdict forever; rokmcp-collector calls
#                           find_new_hot_pools once a day and always gets the same shape
#
#   plus, for a client whose NAME cannot be told from ours (claude-code, curl, mozilla):
#   at least one request from a country that is not the owner's. `_country` was broken
#   until today, so every historical row says "??" and "??" can neither confirm nor
#   disqualify -- an ambiguous client with no known country stays NEAR, never YES.
#
# Condition 5 has a false-negative cost and it is accepted deliberately: a real user who
# only ever checks scam tokens sees "high" every time and this rule says NO. The gate is
# built to be hard to pass, its failing branch prescribes an action we would take anyway
# (Experiment C, no new features), and the expensive direction to fail in is the other
# one -- buying another month of building on a robot.
GATE_FROZEN = "2026-09-07"


def gate_verdict(tools, prof):
    """Decide the 2026-09-18 gate. Returns (verdict, lines) with verdict in
    YES / NEAR / NO. Pure -- takes what the queries returned, touches no network."""
    lines = []
    passed, near = [], []
    for client, rec in (tools or []):
        p = (prof or {}).get(client) or {}
        real_tools = sorted(t for t in rec.get("tools") or ()
                            if t and t != "?" and not t.startswith("__"))
        verdicts = sorted(v for v in (p.get("verdicts") or {})
                          if v and v != "(none)")
        days = max(int(rec.get("days") or 0), len(p.get("days") or ()))
        known = {c for c in (p.get("countries") or set()) if c and c != "??"}
        foreign = known - OWNER_COUNTRIES

        fails = []
        if is_self(client):
            fails.append("ours (vetagent-*)")
        if not real_tools:
            fails.append("never named a tool")
        if not verdicts:
            fails.append("never received a verdict")
        if days < 2:
            fails.append("one day only")
        if len(verdicts) < 2:
            fails.append("one distinct verdict (%s)" % (verdicts[0] if verdicts else "-"))
        if client in AMBIGUOUS_CLIENTS and not foreign:
            fails.append("name indistinguishable from ours, country %s"
                         % ("/".join(sorted(known)) or "??"))

        if not fails:
            passed.append(client)
            # How much of the evidence actually carries a country, spelled out. A YES
            # resting on three rows out of forty-seven is still a YES under this rule --
            # the rule is frozen and is not moved after a run -- but a reader is entitled
            # to see that it rests on three. Country only started working on 2026-09-07,
            # so every row older than that says "??" and can support nothing.
            cn = p.get("country_n") or {}
            known_rows = sum(v for k, v in cn.items() if k and k != "??")
            all_rows = sum(cn.values()) or (rec.get("n") or 0)
            lines.append(
                "  YES:  %-26s %d calls, %d days, verdicts %s, country %s "
                "(on %d of %d rows)"
                % (client, rec.get("n") or 0, days, "/".join(verdicts),
                   "/".join(sorted(known)) or "??", known_rows, all_rows))
        elif not is_self(client) and real_tools and verdicts:
            near.append(client)
            lines.append("  NEAR: %-26s %s" % (client, "; ".join(fails)))
        else:
            lines.append("  no:   %-26s %s" % (client, "; ".join(fails)))

    if passed:
        return "YES", lines
    if near:
        return "NEAR", lines
    return "NO", lines


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

    prof = caller_profile(account, token, since, tools) if tools else {}

    print("\n--- Gate 2026-09-18: is anyone outside this project using it? ---")
    print("  rule frozen %s, in gate_verdict(), pinned by tests/test_usage_gate.py:" %
          GATE_FROZEN)
    print("  not ours; named a tool; got a verdict; two distinct days; two distinct")
    print("  verdicts; and if the name could be ours, one non-owner country.")
    print("  Four rules have been written for this gate, each after seeing the data the")
    print("  last one produced. This is the last. It is not adjusted after a run.")

    if tools is None:
        print("  QUERY FAILED -- this is not the same as nobody calling.")
    elif not tools:
        print("  NO. %d clients connected and none of them called a tool."
              % len(ext or []))
        print("  -> STRATEGY: distribution problem, not product. Experiment C only, "
              "no new features.")
    else:
        verdict, lines = gate_verdict(tools, prof)
        for line in lines:
            print(line)
        if verdict == "YES":
            print("  -> YES. STRATEGY: continue per the roadmap.")
        elif verdict == "NEAR":
            print("  -> NO. Callers marked NEAR did something real and did not clear the")
            print("     bar. They are evidence, not a pass, and the rule is not moved to")
            print("     admit them. STRATEGY: Experiment C only, no new features.")
        else:
            print("  -> NO. STRATEGY: Experiment C only, no new features.")

    if tools:
        print_profile(prof, tools)
        demo = prof.get(LANDING_DEMO)
        if demo:
            print("\n  landing-page demo button: %d clicks on %d day(s), %d hour(s)."
                  % (demo["n"], len(demo["days"]), len(demo["hours"])))
            print("  This is Experiment C's own metric, not the gate's. A click on our")
            print("  own page is interest; it is not an integration and never counts.")

    # Does the per-client attribution account for every tool call? It did not, and
    # nothing noticed: 120 calls by tool against 101 attributed, so 19 belonged to
    # clients the gate had filtered out as "ours". A gate that silently drops a sixth of
    # its own evidence is not measuring what it claims to.
    by_tool = query(
        "SELECT sum(_sample_interval) AS n FROM %s WHERE timestamp > now() - %s "
        "AND %s != '' AND %s != '?' AND NOT startsWith(%s, '__')"
        % (DATASET, since, BLOB["tool"], BLOB["tool"], BLOB["tool"]), account, token)
    tot_rows = rows_of(by_tool)
    if tot_rows:
        total_tool_calls = int(float(tot_rows[0].get("n") or 0))
        attributed = sum(r["n"] for _, r in (tools or []))
        print("\n  reconciliation: %d tool calls recorded, %d attributed above"
              % (total_tool_calls, attributed))
        if total_tool_calls != attributed:
            print("  %d UNATTRIBUTED -- these belong to clients filtered out as ours."
                  % (total_tool_calls - attributed))
            print("  These are clients filtered out as ours. That gap once hid 19")
            print("  real tool calls; it is now expected to hold only vetagent-* rows,")
            print("  so a gap LARGER than our own traffic is the thing to look at.")

    # This printed "merely connected: 50" against 78 distinct clients, because the
    # query said LIMIT 50 and the print said "clients". The 28 it cut were the
    # lowest-volume ones -- which is exactly where a person trying the tool once sits,
    # and exactly the opposite of where a crawler sits.
    print("\n  for context, clients that merely connected: %d%s"
          % (len(ext or []), " (CAPPED -- raise the LIMIT)" if len(ext or []) >= 500
             else ""))
    if ext:
        print("    %s" % ", ".join("%s (%s)" % (c, n) for c, n in ext[:12]))
    print("  raw totals: %d clients / %d countries (includes us)"
          % (clients, countries))
    print("  NOTE: rows written before 2026-09-07 all report country '??'. _country()")
    print("  called .get() on a JsProxy, which has no .get, and the bare except turned")
    print("  every AttributeError into '??'. Fixed; rows from today carry a country.")

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
