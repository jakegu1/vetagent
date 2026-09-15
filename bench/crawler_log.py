"""crawler_log.py -- what search and AI crawlers actually received from vetagent.dev.

Reads Cloudflare's zone request analytics one day at a time (the plan refuses a wider window)
for the last N days, and prints requests per crawler and status, plus the paths the named
crawlers fetched. Settings say what might happen to a crawler; this says what did.

Run in CI by .github/workflows/zone-check.yml, which holds the token:
    CLOUDFLARE_API_TOKEN=... python bench/crawler_log.py <zone_id> [days]
Needs Zone Analytics Read. Prints counts only.
"""

import datetime
import json
import os
import re
import sys
import urllib.request

CRAWLERS = re.compile(r"(GPTBot|OAI-SearchBot|ChatGPT-User|ClaudeBot|Claude-User|Claude-SearchBot|"
                      r"PerplexityBot|Perplexity-User|Googlebot|bingbot|Bytespider|Amazonbot|"
                      r"Applebot|meta-externalagent|CCBot|DuckDuckBot|YandexBot)")
QUERY = """query($zone: String!, $since: Time!, $until: Time!) { viewer { zones(filter: {zoneTag: $zone}) {
  httpRequestsAdaptiveGroups(limit: 500, filter: {datetime_geq: $since, datetime_lt: $until,
    userAgent_like: "%bot%"}, orderBy: [count_DESC]) {
    count dimensions { userAgent edgeResponseStatus clientRequestPath } } } } }"""


def day(zone, token, start):
    body = json.dumps({"query": QUERY, "variables": {
        "zone": zone, "since": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "until": (start + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}}).encode()
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql", data=body,
                                 headers={"Authorization": "Bearer " + token,
                                          "content-type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    if d.get("errors"):
        return None, d["errors"]
    zones = ((d.get("data") or {}).get("viewer") or {}).get("zones") or []
    return (zones[0].get("httpRequestsAdaptiveGroups") or []) if zones else [], None


def main():
    zone, days = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 7
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    now = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    by_status, paths, failed = {}, {}, 0
    for i in range(days):
        rows, err = day(zone, token, now - datetime.timedelta(days=i + 1))
        if rows is None:
            failed += 1
            print("day -%d: not readable: %s" % (i + 1, str(err)[:160]))
            continue
        for r in rows:
            ua = r["dimensions"]["userAgent"]
            m = CRAWLERS.search(ua)
            name = m.group(1) if m else "other bot"
            key = (name, r["dimensions"]["edgeResponseStatus"])
            by_status[key] = by_status.get(key, 0) + r["count"]
            if m:
                p = r["dimensions"]["clientRequestPath"]
                paths[(name, p)] = paths.get((name, p), 0) + r["count"]
    print("Requests by crawler and status, last %d days (%d day(s) unreadable):" % (days, failed))
    for (name, status), n in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print("  %-20s %s  %d" % (name, status, n))
    print("Paths the named crawlers fetched:")
    for (name, p), n in sorted(paths.items(), key=lambda kv: -kv[1])[:25]:
        print("  %-20s %-40s %d" % (name, p[:40], n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
