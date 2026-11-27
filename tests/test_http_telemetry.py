"""test_http_telemetry.py — the HTTP interface has to be visible to the gate too.

`_record_call` was reachable only from `_handle_mcp`, so every /assess, /liquidity and
/new-pools request was invisible. The 2026-09-18 gate asks whether anyone outside this
project uses the tool, and for fourteen days it answered from one of the two interfaces
the product actually exposes.

That is not an academic gap. An integrator wiring this into a bot reaches for curl or
requests against /assess long before they configure an MCP client, so the surface most
likely to carry a first real user was the surface with no telemetry on it at all.

This file also pins the invariant that makes the whole thing defensible: **the token
address is never recorded**. It is the reason this server cannot identify its callers,
which is a cost the project accepted deliberately, and adding telemetry is exactly the
moment that cost gets quietly paid back by someone in a hurry.

`src/entry.py` imports `workers`, which only exists inside the Cloudflare runtime, so
this stubs it. That is worth doing rather than skipping: a test that cannot run is how
this project shipped a honeypot check that never fired.

Run:  python tests/test_http_telemetry.py
"""

import asyncio
import io
import os
import re
import subprocess
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def _install_worker_stub():
    """Stand in for the Cloudflare runtime so entry.py can be imported at all."""
    mod = types.ModuleType("workers")

    class Response:
        def __init__(self, body="", headers=None, status=200):
            self.body, self.headers, self.status = body, headers or {}, status

    class WorkerEntrypoint:
        def __init__(self, *a, **k):
            self.env = None

    mod.Response = Response
    mod.WorkerEntrypoint = WorkerEntrypoint
    sys.modules.setdefault("workers", mod)


_install_worker_stub()
import entry  # noqa: E402
import mcp_server  # noqa: E402
import risk  # noqa: E402


class FakeRequest:
    def __init__(self, url, method="GET", headers=None):
        self.url = url
        self.method = method
        self.headers = headers or {"user-agent": "somebodys-bot/1.0"}
        self.cf = {}


ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"


def _routes(recorded):
    """Drive each HTTP route with the engine stubbed, collecting what got recorded."""
    original_record = entry._record
    original_assess = risk.assess
    original_liq = risk.liquidity
    original_pools = risk.new_pools

    def _rec(env, blobs, doubles):
        recorded.append((blobs, doubles))

    async def _assess(address, chain_hint=None, verbose=False):
        return {"address": address, "risk_level": "high", "signals": []}

    async def _liquidity(address, chain_hint=None):
        return {"address": address, "status": "unpriced"}

    async def _pools(chain="solana", limit=10):
        return {"chain": chain, "count": 0, "pools": []}

    entry._record = _rec
    risk.assess, risk.liquidity, risk.new_pools = _assess, _liquidity, _pools
    try:
        w = entry.Default()
        for url in ("https://vetagent.dev/assess/%s?chain=ethereum" % ADDRESS,
                    "https://vetagent.dev/liquidity/%s" % ADDRESS,
                    "https://vetagent.dev/new-pools?chain=base"):
            asyncio.run(w.fetch(FakeRequest(url)))
    finally:
        entry._record = original_record
        risk.assess, risk.liquidity, risk.new_pools = (
            original_assess, original_liq, original_pools)


def test_every_http_route_is_recorded():
    """All three GET routes reach the telemetry, tagged so HTTP is distinguishable."""
    print("\n[http] the other half of the product is visible to the gate")
    recorded = []
    _routes(recorded)

    check("all three routes recorded", len(recorded) == 3,
          "%d recorded: %s" % (len(recorded), [b[1] for b, _ in recorded]))
    if len(recorded) != 3:
        return

    methods = [b[0] for b, _ in recorded]
    tools = [b[1] for b, _ in recorded]
    verdicts = [b[2] for b, _ in recorded]

    check("each is tagged http, not mcp", set(methods) == {"http"}, str(methods))
    check("the tool names match the MCP tool names",
          tools == ["assess_token_risk", "get_token_liquidity", "find_new_hot_pools"],
          str(tools))
    check("the verdict is carried through", verdicts[0] == "high", str(verdicts))
    check("a status counts as a verdict too", verdicts[1] == "unpriced", str(verdicts))
    check("the caller name is recorded", all(b[3] for b, _ in recorded),
          str([b[3] for b, _ in recorded]))


def test_the_token_address_is_never_recorded():
    """The invariant that makes the rest of this defensible.

    This server records no addresses, no token queries and no identities. That is why it
    cannot tell who is calling it -- a cost accepted on purpose -- and adding telemetry
    is precisely the moment somebody in a hurry pays it back.
    """
    print("\n[http] telemetry must not learn what anyone asked about")
    recorded = []
    _routes(recorded)
    for blobs, _ in recorded:
        joined = " ".join(str(b) for b in blobs)
        check("no address in %r" % (blobs[1],),
              ADDRESS.lower() not in joined.lower(), joined[:120])
        check("no URL in %r" % (blobs[1],),
              "vetagent.dev" not in joined and "http://" not in joined
              and "https://" not in joined, joined[:120])


def test_an_unknown_records_why_without_recording_what():
    """Production answered unknown to 187 of 460 calls in a week, and nothing recorded why.

    The telemetry kept method, tool, verdict, client and country, so "the extra half is
    429s" (2026-09-15 numbers audit) and "the key will fix it" were both arguments. W35
    records the reason class of an `unknown` -- its `unknown_kind`, and per critical
    dimension which upstream answered what -- built from a fixed vocabulary, so no
    upstream text, and therefore no address, can ride along.
    """
    print("\n[http] an unknown records why, from a fixed vocabulary")
    recorded = []
    original_record, original_assess = entry._record, risk.assess

    def _rec(env, blobs, doubles):
        recorded.append(blobs)

    answers = {
        "infra": {"address": ADDRESS, "risk_level": "unknown", "unknown_kind": "infrastructure",
                  "signals": [], "evidence": {"data_gaps": [
                      {"dimension": "liquidity", "source": "dexscreener",
                       "reason": "upstream request failed (dexscreener 429, geckoterminal 429)"},
                      {"dimension": "sellability", "source": "honeypot.is",
                       "reason": "simulation failed: execution reverted at %s" % ADDRESS}]}},
        "coverage": {"address": ADDRESS, "risk_level": "unknown", "unknown_kind": "coverage",
                     "signals": [], "evidence": {"data_gaps": [
                         {"dimension": "sellability", "source": "honeypot.is",
                          "reason": "the sell simulator has no record of this token"},
                         {"dimension": "liquidity", "source": "dexscreener",
                          "reason": "no pool's depth is priced in an asset we can verify"}]}},
        "low": {"address": ADDRESS, "risk_level": "low", "signals": [], "evidence": {}},
    }
    which = {"k": "infra"}

    async def _assess(address, chain_hint=None, verbose=False):
        return answers[which["k"]]

    entry._record, risk.assess = _rec, _assess
    try:
        w = entry.Default()
        for k in ("infra", "coverage", "low"):
            which["k"] = k
            asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/assess/%s" % ADDRESS)))
    finally:
        entry._record, risk.assess = original_record, original_assess

    whys = [b[5] if len(b) > 5 else None for b in recorded]
    check("three answers recorded", len(whys) == 3, str(recorded))
    if len(whys) == 3:
        check("an infrastructure unknown names the upstreams and what they answered",
              whys[0] == "infrastructure|liquidity:dexscreener 429,geckoterminal 429"
                         "|sellability:simulation failed", str(whys[0]))
        check("a coverage unknown names the gap classes",
              whys[1] == "coverage|liquidity:unpriced|sellability:no record", str(whys[1]))
        check("an answer that is not unknown records no reason", whys[2] == "", str(whys[2]))
        check("and the reason never carries the address, even when the upstream text did",
              all(ADDRESS.lower() not in str(x).lower() for x in whys), str(whys))


def test_an_unconfirmed_absence_is_named_as_one():
    """W58's reason must be countable in production, whatever status came with it.

    `_gap_tags` labels an "upstream request failed" reason by its HTTP statuses and only
    otherwise by phrase, so the `unconfirmed` class W58 added was reachable only by a
    failure with no status at all: a 429 from the fallback read `liquidity:geckoterminal
    429`, the same words a plain outage uses (E14 review, 2026-09-22). The case is named
    now, and keeps its statuses.
    """
    print("\n[http] an unconfirmed absence is recorded as unconfirmed")
    reason = ("upstream request failed: DexScreener lists no pair, and the fallback that "
              "would confirm it did not answer")

    def why(detail):
        return entry._why_unknown({"risk_level": "unknown", "unknown_kind": "infrastructure",
                                   "evidence": {"data_gaps": [
                                       {"dimension": "liquidity", "reason": reason + detail}]}})
    check("with a status: named, and the status kept",
          why(" (geckoterminal 429)") == "infrastructure|liquidity:unconfirmed geckoterminal 429",
          why(" (geckoterminal 429)"))
    check("with none (a timeout): named",
          why("") == "infrastructure|liquidity:unconfirmed", why(""))
    plain = entry._why_unknown({"risk_level": "unknown", "unknown_kind": "infrastructure",
                                "evidence": {"data_gaps": [
                                    {"dimension": "liquidity",
                                     "reason": "upstream request failed (dexscreener 429, "
                                               "geckoterminal 429)"}]}})
    check("and a plain outage is not called unconfirmed",
          plain == "infrastructure|liquidity:dexscreener 429,geckoterminal 429", plain)


def test_a_high_records_why_without_recording_what():
    """`high` is the verdict our own failure can turn against someone else's token, and
    until 2026-09-22 it was the one recorded as a bare count.

    BACKLOG W58: DexScreener empty, the fallback unasked, and on a hinted chain the no-trace
    escalation made our outage `high` 70. Nothing in production could have said how often,
    because the reason field was filled only for `unknown`. It is now filled for `high` too,
    from the same fixed vocabulary plus the driver's category -- never its name or message,
    which carry figures and could carry an address.
    """
    print("\n[http] a high records why, from the same fixed vocabulary")
    recorded = []
    original_record, original_assess = entry._record, risk.assess

    def _rec(env, blobs, doubles):
        recorded.append(blobs)

    no_trace = {"dimension": "liquidity", "source": "dexscreener",
                "reason": "about the token: no trading pair found"}
    no_record = {"dimension": "sellability", "source": "honeypot.is",
                 "reason": "about the token: the sell simulator has no record of %s" % ADDRESS}
    answers = [
        {"risk_level": "high", "signals": [], "evidence": {"data_gaps": [no_trace, no_record]},
         "driver": {"name": "Nothing about this token can be verified", "category": "no_liquidity"}},
        {"risk_level": "high", "signals": [], "evidence": {"data_gaps": []},
         "driver": {"name": "Deployer %s rugged before" % ADDRESS, "category": "honeypot"}},
        {"risk_level": "high", "signals": [], "evidence": {"data_gaps": []},
         "driver": {"name": "x", "category": "honeypot %s" % ADDRESS}},
        {"risk_level": "high", "signals": [], "evidence": {"data_gaps": []}, "driver": None},
        {"risk_level": "medium", "signals": [], "evidence": {"data_gaps": [no_trace]},
         "driver": {"name": "Thin liquidity", "category": "liquidity"}},
    ]
    at = {"i": 0}

    async def _assess(address, chain_hint=None, verbose=False):
        return dict(answers[at["i"]], address=ADDRESS)

    entry._record, risk.assess = _rec, _assess
    try:
        w = entry.Default()
        for i in range(len(answers)):
            at["i"] = i
            asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/assess/%s" % ADDRESS)))
    finally:
        entry._record, risk.assess = original_record, original_assess

    whys = [b[5] if len(b) > 5 else None for b in recorded]
    check("five answers recorded", len(whys) == len(answers), str(recorded))
    if len(whys) == len(answers):
        check("a no-trace high names its driver's category and its gap classes",
              whys[0] == "driver=no_liquidity|liquidity:no pair|sellability:no record",
              str(whys[0]))
        check("a driver contributes its category, never its name",
              whys[1] == "driver=honeypot", str(whys[1]))
        check("a category that is not a plain word is recorded as `other`",
              whys[2] == "driver=other", str(whys[2]))
        check("a high with no driver says so", whys[3] == "driver=none", str(whys[3]))
        check("a medium still records no reason", whys[4] == "", str(whys[4]))
        check("and no reason carries the address, wherever the answer put it",
              all(ADDRESS.lower() not in str(x).lower() for x in whys), str(whys))


class FakeCf:
    """What `request.cf` actually is: a JsProxy of a plain JS object.

    Attribute access only. No `.get`, no `__getitem__`, no mapping protocol -- which is
    precisely why `(cf or {}).get("country")` raised AttributeError on every request the
    service ever served, and why the bare `except` turned all 3,414 rows into "??".
    """

    def __init__(self, country="US"):
        self.country = country
        self.colo = "SIN"


def test_country_reads_a_jsproxy_not_a_dict():
    """The discriminator the gate wrote off as unavailable was available all along.

    STRATEGY §8 records "the country filter has never excluded a single row ... it has
    been inert since it was written", and the gate was re-argued three times around that
    absence. It was not Cloudflare withholding the field. It was one `.get`.
    """
    print("\n[http] request.cf is attribute-access, and it always was")
    r = FakeRequest("https://vetagent.dev/assess/%s" % ADDRESS)
    r.cf = FakeCf("SG")
    check("a JsProxy-shaped cf yields the country", entry._country(r) == "SG",
          entry._country(r))

    check("the old expression is what failed",
          not hasattr(FakeCf("SG"), "get"),
          "if cf grows a .get, this test stops proving anything")

    r.cf = {"country": "US"}
    check("a plain dict still works, so tests and production agree",
          entry._country(r) == "US", entry._country(r))

    r.cf = None
    check("no cf is still '??', not a crash", entry._country(r) == "??")

    r.cf = FakeCf(None)
    check("cf without a country is '??'", entry._country(r) == "??")


def test_a_caller_can_name_itself_on_every_request():
    """`clientInfo` labels the handshake. The gate counts the tool call.

    `declared_client()` reads a contextvar set while handling `initialize`. No session id
    is issued, so the `tools/call` that follows is a different request in a different
    context and the contextvar is back at its default. R15 claimed this field
    "de-mushes 370 requests"; it de-mushes handshakes, which `tool_callers()` discards.
    A header travels with every request and needs no session.
    """
    print("\n[http] the row the gate counts is the row that must carry a name")
    r = FakeRequest(
        "https://vetagent.dev/assess/%s" % ADDRESS,
        headers={"user-agent": "Mozilla/5.0", "x-mcp-client": "Acme-Bot"})
    check("the header wins over the User-Agent",
          entry._caller_id(r) == "acme-bot", entry._caller_id(r))

    plain = FakeRequest("https://vetagent.dev/assess/%s" % ADDRESS,
                        headers={"user-agent": "Mozilla/5.0"})
    check("without it we still fall back, so nothing is lost",
          entry._caller_id(plain) == "mozilla", entry._caller_id(plain))

    check("the header is allowed cross-origin, or a browser blocks the caller trying",
          "x-mcp-client" in entry._CORS["access-control-allow-headers"])

    landing = io.open(os.path.join(ROOT, "src", "landing.html"),
                      encoding="utf-8").read()
    check("our own demo button sends it, so browser clicks stop hiding in 'mozilla'",
          "X-MCP-Client" in landing and "vetagent-landing-demo" in landing)
    # The page used to call run() on load, so every visit -- crawlers that execute JS
    # included -- sent one live assessment of the demo token. Those rows are counted in the
    # production unknown rate (only the CI smoke client is excluded), and the demo token is
    # usually `unknown`: our own page was inflating the figure the scorecard publishes as
    # "live", and greeting each visitor with a verdict nobody asked for (2026-09-18 pre-post
    # review). The call now happens only on a click.
    script = landing[landing.rindex("<script>"):]
    body_end = script.rindex("})();")
    tail = script[:body_end].rstrip().splitlines()[-1].strip()
    check("the demo does not run until someone asks it to",
          tail != "run();", "the script ends by calling run() on page load")


def test_landing_trial_runs_the_served_script_with_request_scope():
    """Replay the actual page, not a rewritten copy of its request logic."""
    import json
    with open(os.path.join(ROOT, "tests", "fixtures", "homepage_assessment_cases.json"), encoding="utf-8") as handle:
        recorded = json.load(handle)
    gaps = {
        "no_record": [{"dimension": "sellability", "source": "honeypot.is",
            "reason": "about the token: the sell simulator has no record of this token"}],
        "unsupported": [{"dimension": "sellability", "source": "honeypot.is",
            "reason": "our coverage gap: the sell simulator does not cover polygon"}],
        "outage": [{"dimension": "sellability", "source": "honeypot.is",
            "reason": "upstream request failed (honeypot.is 503)"}],
        "non_sell": [{"dimension": "liquidity", "source": "quote_prices", "reason": risk._UNBACKED_REASON}],
    }
    gaps["mixed"] = gaps["no_record"] + [{"dimension": "liquidity", "source": "dexscreener",
        "reason": "upstream request failed (dexscreener 429)"}]
    controls = {}
    for name, missing in gaps.items():
        controls[name] = risk._finalize("0x" + "ab" * 20,
            [risk._sig("warn", "Check incomplete", "Evidence missing", "sellability"),
             risk._sig("ok", "Observed contract", "Contract observation available", "contract")],
            {"chain_searched": "polygon" if name == "unsupported" else "ethereum"}, missing)
    controls["t114_outage"] = asyncio.run(_t114_assessment("MCP", 429, verbose=False))[0]
    landing = asyncio.run(entry.Default().fetch(FakeRequest("https://vetagent.dev/"))).body
    runner = os.path.join(ROOT, "tests", "fixtures", "landing_trial_contract.cjs")
    result = subprocess.run(["node", runner], input=json.dumps({"html": landing, "recorded": recorded,
                            "controls": controls}), encoding="utf-8",
                            capture_output=True, timeout=30)
    print(result.stdout)
    check("served trial preserves submitted asset, network and latest request",
          result.returncode == 0, result.stdout + result.stderr)


def test_landing_liquidity_recheck_roundtrips_actual_mcp_results_in_the_served_script():
    import json
    from unittest.mock import AsyncMock, patch
    import mcp_server
    import risk
    from test_mcp import _t119_curve_archive
    with open(os.path.join(ROOT, "tests", "fixtures", "liquidity_recheck.json"), encoding="utf-8") as handle:
        readings = json.load(handle)

    def replay(market_readings):
        replies, context = [], []
        for reading in market_readings:
            with patch.object(risk, "liquidity", AsyncMock(return_value=reading)):
                reply = asyncio.run(mcp_server.handle_mcp_request({"jsonrpc": "2.0", "id": 1,
                    "method": "tools/call", "params": {"name": "get_token_liquidity", "arguments": {
                        "address": reading["address"], "chain_hint": reading.get("best_pair_chain", "base"),
                        "comparison_context": context}}}))
            replies.append(reply)
            context = reply["result"].get("structuredContent", {}).get("comparison_context", [])
        return replies

    precision_readings = [
        dict(readings[0], liquidity_usd=amount, status=status, checked_at="2026-11-19T17:00:%02dZ" % index)
        for index, (amount, status) in enumerate(((0.102263, "ok"), (0.104263, "ok"), (0.004, "ok"),
                                                 (0.002, "ok"), (0.002, "ok"), (0, "drained"),
                                                 (None, "unpriced"), (0, "drained"), (0.002, "ok"),
                                                 (0, "not_found"), (0, "drained")))
    ]
    for key in ("source", "best_pair_address", "best_pair_chain"):
        precision_readings[-1].pop(key)
    token, _, _, _, _, curve = _t119_curve_archive()
    curve_readings = [{"address": token, "best_pair_chain": "ethereum", "source": "dexscreener", "status": "ok",
                       "best_pair_market_id": curve["pairAddress"], "liquidity_usd": 122443000,
                       "checked_at": stamp} for stamp in
                      ("2026-11-27T03:00:00Z", "2026-11-27T03:02:00Z")]
    limited = asyncio.run(_t115_liquidity("MCP", "chain rate limited"))[0]
    landing = asyncio.run(entry.Default().fetch(FakeRequest("https://vetagent.dev/"))).body
    runner = os.path.join(ROOT, "tests", "fixtures", "liquidity_recheck_contract.cjs")
    result = subprocess.run(["node", runner], input=json.dumps({"html": landing, "replies": replay(readings),
                            "precision_replies": replay(precision_readings), "curve_replies": replay(curve_readings),
                            "limited_reply": {"result": {"structuredContent": limited}}}),
                            encoding="utf-8", capture_output=True, timeout=30)
    print(result.stdout)
    check("served liquidity recheck uses real MCP context and bounded browser-only history",
          result.returncode == 0, result.stdout + result.stderr)
    check("public privacy explains local observations, scoped return, clearing and server nonretention",
          all(text in entry._PRIVACY_HTML for text in ("eight compact", "local storage", "current token",
              "Other token observations", "Clear saved observations", "does not store or log this")))


def test_a_call_from_our_own_page_is_ours_even_with_stale_javascript():
    """The demo button's own header is not enough, because the page can be cached.

    The worker sets Cache-Control: no-cache on the landing page and the custom domain
    strips it -- verified against vetagent.dev and the workers.dev fallback on
    2026-09-07, where only the workers.dev origin returns the header. So a visitor can
    hold a copy of the page from before the tag shipped and keep arriving as an anonymous
    browser. That bucket is what put a YES on the 09-18 gate.

    Origin and Referer are set by the browser, not by our JavaScript, so they are true of
    a cached page too.
    """
    print("\n[http] a click on our own page is ours however old the page is")
    for name in ("origin", "referer"):
        for host in ("https://vetagent.dev", "https://www.vetagent.dev/",
                     "https://vetagent.some-account.workers.dev/index.html"):
            r = FakeRequest("https://vetagent.dev/mcp", method="POST",
                            headers={"user-agent": "Mozilla/5.0", name: host})
            check("%s %s -> the landing demo" % (name, host),
                  entry._caller_id(r) == entry.LANDING_CLIENT, entry._caller_id(r))

    # Narrow on purpose: an integrator's own web app must not be mislabelled as ours.
    other = FakeRequest("https://vetagent.dev/mcp", method="POST",
                        headers={"user-agent": "Mozilla/5.0",
                                 "origin": "https://someones-trading-app.example"})
    check("somebody else's page is not ours", entry._caller_id(other) == "mozilla",
          entry._caller_id(other))

    lookalike = FakeRequest("https://vetagent.dev/mcp", method="POST",
                            headers={"user-agent": "Mozilla/5.0",
                                     "origin": "https://vetagent.dev.evil.example"})
    check("and neither is a host that merely starts the same",
          entry._caller_id(lookalike) == "mozilla", entry._caller_id(lookalike))

    # An explicit header still wins, so a real client can always name itself.
    named = FakeRequest("https://vetagent.dev/mcp", method="POST",
                        headers={"user-agent": "Mozilla/5.0",
                                 "origin": "https://vetagent.dev",
                                 "x-mcp-client": "acme-bot"})
    check("an explicit name still wins over the origin guess",
          entry._caller_id(named) == "acme-bot", entry._caller_id(named))


def _mcp(body, recorded, result=None):
    """Drive _handle_mcp with the MCP layer stubbed, collecting what got recorded."""
    original_record = entry._record
    original_handle = mcp_server.handle_mcp_request

    def _rec(env, blobs, doubles):
        recorded.append(blobs)

    async def _handle(msg):
        return result if result is not None else {
            "jsonrpc": "2.0", "id": msg.get("id"),
            "result": {"structuredContent": {"risk_level": "high"}}}

    class Req(FakeRequest):
        async def json(self):
            return body

    entry._record = _rec
    mcp_server.handle_mcp_request = _handle
    try:
        w = entry.Default()
        asyncio.run(w.fetch(Req("https://vetagent.dev/mcp", method="POST")))
    finally:
        entry._record = original_record
        mcp_server.handle_mcp_request = original_handle


def test_a_batched_tool_call_is_still_a_tool_call():
    """The batch branch returned before reaching the recording block.

    JSON-RPC batching is what an integration reaches for the moment it has more than one
    token to check -- so the invisible path was, again, the one a real user is most
    likely to be on.
    """
    print("\n[http] batched calls were invisible to the gate")
    recorded = []
    _mcp([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": "assess_token_risk", "arguments": {"address": ADDRESS}}},
          {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
           "params": {"name": "get_token_liquidity", "arguments": {"address": ADDRESS}}}],
         recorded)
    check("both messages in the batch are recorded", len(recorded) == 2,
          str(recorded))
    if len(recorded) == 2:
        check("with their own tool names",
              [b[1] for b in recorded]
              == ["assess_token_risk", "get_token_liquidity"],
              str([b[1] for b in recorded]))
        check("and no address leaks through the batch path either",
              ADDRESS.lower() not in " ".join(str(b) for r in recorded
                                              for b in r).lower())


def test_an_unnamed_tool_call_is_not_tool_use():
    """`tool` was recorded as "?" for a malformed tools/call, which then sat in the
    gate's evidence looking exactly like a real one."""
    print("\n[http] a malformed call is not evidence of use")
    recorded = []
    _mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}, recorded)
    check("one row recorded", len(recorded) == 1, str(recorded))
    if recorded:
        check("the tool is empty, not '?'", recorded[0][1] == "",
              repr(recorded[0][1]))


def test_privacy_names_every_third_party_that_receives_the_address():
    """The privacy page lists who gets the token address. The list has to be the real one.

    It named four recipients -- DexScreener, GeckoTerminal, honeypot.is, RugCheck -- and
    read as exhaustive. It was not: `_CHAIN_RPC` in src/risk.py sends `eth_getCode` to
    rpc.mevblocker.io, mainnet.base.org or bsc-dataseed.bnbchain.org on every EVM
    assessment, so three third parties had been receiving the most sensitive field this
    service handles, undisclosed, since the owner-powers check shipped.

    A privacy page is a promise, and this one was quietly incomplete rather than wrong in
    a way anyone would notice. So the list is generated-adjacent now: every host the engine
    can contact must appear on the page, and adding an upstream without disclosing it fails
    the build.
    """
    print("\n[privacy] the disclosed recipients are the actual recipients")
    risk_src = io.open(os.path.join(ROOT, "src", "risk.py"), encoding="utf-8").read()
    hosts = set(re.findall(r"https://([a-zA-Z0-9.-]+)", risk_src))
    # Not a real destination: the internal marker for the bytecode cache namespace.
    hosts = {h for h in hosts if not h.endswith(".vetagent.internal")}
    check("found the engine's outbound hosts", len(hosts) >= 4, str(sorted(hosts)))

    privacy = entry._PRIVACY_HTML
    for host in sorted(hosts):
        # The page may name the vendor rather than the hostname, so accept either the
        # host itself or its second-level label (dexscreener, geckoterminal, rugcheck).
        label = host.split(".")[-2] if host.count(".") >= 2 else host.split(".")[0]
        named = host in privacy or label.lower() in privacy.lower()
        check("privacy names %s" % host, named,
              "the engine sends the token address here and the page does not say so")


def test_a_failed_http_call_is_still_recorded():
    """A caller whose HTTP calls all error was invisible to the gate. MCP's were not.

    `risk.assess(...)` is awaited inside the argument list of `_record_http`, so a raise
    meant `_record_http` was never reached and the outer handler returned 400 or 500
    having written nothing. The MCP path records its errors through `_record_call`. So
    the 2026-09-18 gate -- which asks whether anyone outside this project uses the tool --
    could not see a caller who was using it and failing, on the interface an integrator
    reaches for first. 9.3% of requests in the last window were errors.

    Rows not written today cannot be recovered later, which is why this could not wait.

    The verdict stays empty: an error is not a verdict, and `gate_verdict` requires a
    real one. This makes a failing caller visible without letting failures qualify.
    """
    print("\n[http] a call that fails is still a call")
    recorded = []
    original_record = entry._record
    original_assess, original_pools = risk.assess, risk.new_pools

    async def _boom(*a, **k):
        raise RuntimeError("upstream on fire")

    async def _bad_input(*a, **k):
        raise ValueError("Invalid chain name")

    entry._record = lambda env, blobs, doubles: recorded.append((blobs, doubles))
    risk.assess, risk.new_pools = _boom, _bad_input
    try:
        w = entry.Default()
        asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/assess/%s" % ADDRESS)))
        asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/new-pools?chain=../etc")))
    finally:
        entry._record = original_record
        risk.assess, risk.new_pools = original_assess, original_pools

    check("both failures were recorded", len(recorded) == 2, str(recorded))
    if len(recorded) != 2:
        return
    tools = [b[1] for b, _ in recorded]
    check("a 500 names the tool it failed in", tools[0] == "assess_token_risk", str(tools))
    check("a 400 names it too", tools[1] == "find_new_hot_pools", str(tools))
    for blobs, doubles in recorded:
        check("it is tagged as an error", doubles[1] == 1.0, str(doubles))
        check("the verdict stays empty, so a failure cannot qualify as one",
              blobs[2] == "", repr(blobs[2]))
        check("the caller is still identified", bool(blobs[3]), str(blobs))
        check("and no address rode along", ADDRESS.lower() not in " ".join(blobs).lower())

    # A path that never reached a tool is not a failed tool call.
    recorded[:] = []
    entry._record = lambda env, blobs, doubles: recorded.append((blobs, doubles))
    try:
        r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/nope")))
        check("a 404 is not recorded as a tool call", not recorded, str(recorded))
        check("and it is still a 404", r.status == 404, str(r.status))
    finally:
        entry._record = original_record


def test_the_pages_a_directory_asks_for_exist():
    """Directories want a privacy URL and a terms URL. Both have to actually resolve.

    A submission is rejected on a 404 as surely as on a bad answer, and there is no way
    to notice a missing static route from inside the code that does not serve it.
    """
    print("\n[pages] /privacy and /terms answer")
    w = entry.Default()
    privacy_terms = ("Privacy", "eth_getCode", "eth_call", "total supply", "selected pool",
                     "zero address", "dead address")
    for path, required in (("/privacy", privacy_terms), ("/terms", ("Terms of use",))):
        r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev" + path)))
        check("%s returns 200" % path, r.status == 200, str(r.status))
        body = " ".join(r.body.split())
        missing = [term for term in required if term not in body]
        check("%s includes its required disclosures" % path, not missing, str(missing))
    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/terms")))
    check("terms states the liability limit", "no warranty" in r.body.lower())
    check("terms repeats that unknown is not low",
          "not a low-risk result" in r.body)
    check("terms does not claim to be advice",
          "not financial advice" in r.body.lower())


def test_dead_outcome_copy_describes_assessed_pool_liquidity_without_promising_sales():
    import json
    import re

    worker = entry.Default()
    landing = asyncio.run(worker.fetch(FakeRequest("https://vetagent.dev/")))
    scripts = re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', landing.body, re.S)
    structured = next(script for script in scripts if json.loads(script[1])["@type"] == "FAQPage")
    faq = next(question["acceptedAnswer"]["text"]
               for question in json.loads(structured[1])["mainEntity"] if "accurate" in question["name"].lower())
    visible = landing.body[:structured.start()] + landing.body[structured.end():]
    surfaces = {"visible FAQ": visible, "FAQPage": faq}
    for path in ("/llms.txt", "/llms-full.txt"):
        response = asyncio.run(worker.fetch(FakeRequest("https://vetagent.dev" + path)))
        check(path + " still returns its public representation", response.status == 200)
        surfaces[path] = response.body
    for name, body in surfaces.items():
        text = " ".join(body.lower().split())
        check(name + " reports historical price and volume and scopes selling evidence",
              "price and volume" in text and "wallet" in text and "amount" in text
              and all(phrase not in text for phrase in ("positions can still be sold", "liquidity can still be sold",
                                                        "confirmed-dead tokens", "project died")))
        if name != "FAQPage":
            check(name + " attributes counted liquidity to assessed pools",
                  re.search(r"\b\d+ of the \d+\b[^.]*\$5,000[^.]*assessed pool", text) is not None)


def test_public_http_homepage_leads_to_its_https_canonical():
    worker = entry.Default()
    canonical = "https://vetagent.dev/"
    for method, suffix in (("GET", ""), ("HEAD", ""), ("GET", "?ref=a%2Fb&tag=x&tag=y&empty=")):
        response = asyncio.run(worker.fetch(FakeRequest("http://vetagent.dev/" + suffix, method)))
        location = response.headers.get("location")
        check("HTTP homepage %s %r permanently redirects to the matching HTTPS URL" % (method, suffix),
              response.status in (301, 308) and location == canonical + suffix,
              "status=%s location=%r" % (response.status, location))
        if location == canonical + suffix:
            landing = asyncio.run(worker.fetch(FakeRequest(location, method)))
            check("HTTPS destination serves the homepage in one hop for %s %r" % (method, suffix),
                  landing.status == 200 and
                  (method == "HEAD" or '<link rel="canonical" href="%s">' % canonical in landing.body))

    for url, method, status in (("http://vetagent.dev/api", "GET", 200),
                                ("http://vetagent.dev/;", "GET", 200),
                                ("http://vetagent.dev/;?a=1", "HEAD", 200),
                                ("http://preview.example/", "GET", 200),
                                ("http://vetagent.dev/", "POST", 200),
                                ("http://vetagent.dev/", "OPTIONS", 204)):
        response = asyncio.run(worker.fetch(FakeRequest(url, method)))
        check("%s %s keeps its existing response" % (method, url),
              response.status == status and "location" not in response.headers)


def test_search_engines_are_told_what_to_index():
    """The site was not in the search index at all, and nothing told an engine it existed.

    GEO baseline, 2026-09-15: `site:vetagent.dev` returned no results, and vetagent.dev
    appeared in none of fifteen result lists -- VetAgent was found only through directory and
    GitHub pages. There was no sitemap (404), robots.txt was Cloudflare's managed preamble with
    no Sitemap line, and no engine had been pinged. A sitemap only helps if every URL in it
    resolves, so each one is fetched here; and IndexNow only accepts a submission if the key
    file on the host says exactly the key that was submitted.
    """
    print("\n[seo] sitemap, robots.txt and the IndexNow key agree with each other")
    w = entry.Default()
    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/sitemap.xml")))
    check("/sitemap.xml returns 200", r.status == 200, str(r.status))
    check("  as XML", "xml" in (r.headers or {}).get("content-type", ""), str(r.headers))
    urls = re.findall(r"<loc>([^<]+)</loc>", r.body or "")
    check("  listing the landing page and the reference pages",
          {"https://vetagent.dev/", "https://vetagent.dev/llms.txt", "https://vetagent.dev/privacy",
           "https://vetagent.dev/terms"} <= set(urls), str(urls))
    for u in urls:
        rr = asyncio.run(w.fetch(FakeRequest(u)))
        check("  %s resolves" % u, rr.status == 200, str(rr.status))

    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/robots.txt")))
    check("/robots.txt names the sitemap", r.status == 200
          and "Sitemap: https://vetagent.dev/sitemap.xml" in (r.body or ""), (r.body or "")[:120])
    check("  and blocks nobody", not re.search(r"^Disallow:\s*/\s*$", r.body or "", re.M), r.body)

    key = entry.INDEXNOW_KEY
    check("the IndexNow key is a valid key", bool(re.fullmatch(r"[a-zA-Z0-9-]{8,128}", key)), key)
    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/%s.txt" % key)))
    check("  and its key file answers with exactly the key", r.status == 200
          and (r.body or "").strip() == key, "%s %r" % (r.status, (r.body or "")[:40]))
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "deploy.yml"), encoding="utf-8").read()
    check("the deploy pings IndexNow with that same key", "api.indexnow.org" in wf and key in wf,
          "deploy.yml does not submit, or submits a different key")


def test_each_reference_page_can_be_indexed_cited_and_shared():
    """One landing page answered no specific question, and a shared link showed no card.

    GEO baseline 2026-09-15: crawlers were reaching the site (the zone logs show Googlebot,
    bingbot, OAI-SearchBot, ClaudeBot and GPTBot getting 200), yet vetagent.dev appeared in
    none of fifteen search result lists -- nothing on it matched a question an agent developer
    types. And links carried no og:image or twitter:card. Each reference page must be
    reachable, in the sitemap, self-describing to a crawler, and shareable.
    """
    print("\n[seo] reference pages, share card, llms-full.txt")
    import struct
    w = entry.Default()
    sitemap = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/sitemap.xml"))).body or ""
    for path in ("/api", "/unknown", "/method"):
        r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev" + path)))
        body = r.body or ""
        check("%s returns 200 HTML" % path, r.status == 200
              and "text/html" in (r.headers or {}).get("content-type", ""), str(r.status))
        check("  %s has one title and a description" % path, body.count("<title>") == 1
              and '<meta name="description"' in body)
        check("  %s is canonical to itself" % path,
              '<link rel="canonical" href="https://vetagent.dev%s">' % path in body)
        check("  %s carries a share card" % path, 'property="og:image"' in body
              and 'name="twitter:card" content="summary_large_image"' in body)
        check("  %s has structured data" % path, "application/ld+json" in body)
        check("  %s is in the sitemap" % path, "<loc>https://vetagent.dev%s</loc>" % path in sitemap)

    landing = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/"))).body or ""
    check("the landing page carries the share card too", 'property="og:image"' in landing
          and 'name="twitter:card"' in landing)
    check("  and links the reference pages", all('href="%s"' % p in landing
                                                 for p in ("/api", "/unknown", "/method")))

    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/og.png")))
    png = r.body if isinstance(r.body, (bytes, bytearray)) else b""
    ok = png[:8] == b"\x89PNG\r\n\x1a\n"
    size = struct.unpack(">II", png[16:24]) if ok else None
    check("/og.png is a 1200x630 PNG", r.status == 200 and ok and size == (1200, 630),
          "%s %s" % (r.status, size))

    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/llms-full.txt")))
    body = r.body or ""
    check("/llms-full.txt returns 200", r.status == 200, str(r.status))
    check("  and documents every tool the server lists",
          all(t["name"] in body for t in mcp_server.TOOLS), body[:120])
    check("  and links the reference pages", all("https://vetagent.dev%s" % p in body
                                                for p in ("/api", "/unknown", "/method")))


def test_an_unissued_verification_token_is_absent_not_wrong():
    """The OpenAI challenge path 404s until a real token exists, and never guesses one.

    Their requirement is that the endpoint return *only* that plugin's token. Serving a
    placeholder, an empty 200, or the string "TODO" would all be a wrong answer where the
    honest answer is no answer -- the same distinction the engine makes between `unknown`
    and `low`, applied to our own plumbing.
    """
    print("\n[pages] the OpenAI challenge answers nothing rather than something wrong")
    w = entry.Default()
    path = "https://vetagent.dev/.well-known/openai-apps-challenge"

    check("no token configured in the repo", entry._OPENAI_CHALLENGE == "",
          repr(entry._OPENAI_CHALLENGE))
    r = asyncio.run(w.fetch(FakeRequest(path)))
    check("unset means 404, not an empty 200", r.status == 404, str(r.status))
    check("and no placeholder body", r.body == "", repr(r.body))

    original = entry._OPENAI_CHALLENGE
    entry._OPENAI_CHALLENGE = "openai-apps-challenge-abc123"
    try:
        r = asyncio.run(w.fetch(FakeRequest(path)))
        check("a set token is served verbatim", r.body == "openai-apps-challenge-abc123",
              repr(r.body))
        check("with nothing wrapped around it",
              r.headers.get("content-type") == "text/plain" and r.status == 200,
              repr(r.headers))
    finally:
        entry._OPENAI_CHALLENGE = original


def test_the_glama_ownership_proof_is_still_served():
    """`docs/SCORECARD.md` claims a Glama listing. That claim rests on this route.

    `src/entry.py`'s own comment says it: the claim file "must stay served -- Glama
    re-verifies, and ownership lapses if it 404s". Nothing checked that it was served, and
    the scorecard scores the Glama channel `True` with the note "Ownership verified", so a
    refactor that dropped this route would silently turn a published claim false. The
    scorecard's own rule is that a channel row changes only when somebody went and looked;
    this is the part a test can look at.

    Why it earned a test on 2026-09-10: punkpeye/awesome-remote-mcp-servers#131 was held by
    an automated triage check reading the Glama connector as unknown/unhealthy. The
    connector turned out to be Healthy, tested 2026-09-10T05:40:19Z, and this route serving
    200 is a precondition of that -- so the question "is our half of it still true" got
    asked, and had no answer in the repo.

    Offline, and deliberately: the realistic regression is a refactor deleting the route,
    not Cloudflare going down. A live fetch would also make CI depend on a third party.
    """
    print(chr(10) + "[pages] the Glama ownership proof is still routed")
    w = entry.Default()
    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/.well-known/glama.json")))
    check("the route answers 200", r.status == 200, str(r.status))
    check("as JSON", (r.headers.get("content-type") or "").startswith("application/json"),
          repr(r.headers.get("content-type")))
    check("carrying a claim token", '"claim"' in r.body and "glama_claim_" in r.body,
          r.body[:80])
    # It is a bare claim and nothing else: Glama parses it, and an extra field or a
    # placeholder would be the same class of wrong answer the OpenAI challenge test above
    # refuses -- something served where nothing is the honest answer.
    import json as _json
    try:
        parsed = _json.loads(r.body)
    except ValueError as e:
        parsed = None
        check("the body is valid JSON", False, str(e))
    if parsed is not None:
        check("the body is valid JSON", True)
        check("it carries exactly $schema and claim",
              set(parsed) == {"$schema", "claim"}, str(sorted(parsed)))
        check("and the claim is not a placeholder",
              parsed.get("claim", "").startswith("glama_claim_")
              and "TODO" not in parsed.get("claim", "")
              and len(parsed.get("claim", "")) > 20, repr(parsed.get("claim"))[:60])


def test_an_unsupported_protocol_version_header_is_refused():
    """Streamable HTTP: "If the server receives a request with an invalid or unsupported
    `MCP-Protocol-Version`, it MUST respond with `400 Bad Request`."

    We answered 200. Measured against production on 2026-09-10: `MCP-Protocol-Version:
    banana` and `1999-01-01` both returned a full `tools/list` result. `SUPPORTED_PROTOCOLS`
    already existed in mcp_server.py and was already the right list -- it negotiated
    `initialize` and was never consulted for the header. The allowlist was there; nothing
    read it.

    Found while checking why an automated triage bot on a directory PR read our Glama
    connector as unhealthy. It was not the cause -- the connector reports Healthy and their
    check POSTs -- but looking for one conformance gap is how you find another.

    Three behaviours, and the third is the one worth being careful about:

    - A known version passes: all three the project already claims.
    - An ABSENT header passes. The spec says the server SHOULD then assume 2025-03-26, and
      refusing would break every client that predates the header. Fail open here, because
      absence is a client that never negotiated, not a client asking for something we
      cannot do.
    - `initialize` is exempt even with a bad header, because a client cannot know the
      negotiated version before it has negotiated. Refusing there would turn a rule about
      subsequent requests into a lockout on the first one.
    """
    print(chr(10) + "[protocol] an unsupported version header is a 400, not a 200")

    listed = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "1"}}}

    def post(body, version=None):
        hdrs = {"user-agent": "probe/1.0"}
        if version is not None:
            hdrs["mcp-protocol-version"] = version

        class Req(FakeRequest):
            async def json(self):
                return body

        original = mcp_server.handle_mcp_request

        async def _handle(msg):
            return {"jsonrpc": "2.0", "id": msg.get("id"), "result": {}}

        mcp_server.handle_mcp_request = _handle
        try:
            w = entry.Default()
            return asyncio.run(w.fetch(Req("https://vetagent.dev/mcp", method="POST",
                                           headers=hdrs)))
        finally:
            mcp_server.handle_mcp_request = original

    for good in mcp_server.SUPPORTED_PROTOCOLS:
        r = post(listed, good)
        check("a supported version passes: %s" % good, r.status == 200, str(r.status))

    r = post(listed, None)
    check("an absent header still passes", r.status == 200, str(r.status))

    for bad in ("banana", "1999-01-01", "2026-13-45", "2025-06-18, 2025-03-26"):
        r = post(listed, bad)
        check("an unsupported version is refused: %r" % bad, r.status == 400, str(r.status))
        check("  and the answer names what we do support: %r" % bad,
              "2025-06-18" in (r.body or ""), (r.body or "")[:100])

    r = post(init, "banana")
    check("initialize stays reachable with a bad header", r.status == 200, str(r.status))


def _call(address="0xdAC17F958D2ee523a2206206994597C13D831ec7", i=1):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": "assess_token_risk", "arguments": {"address": address}}}


class _Limiter:
    """The Workers rate-limit binding's shape: limit({key}) -> {success}."""

    def __init__(self, allow):
        self.allow, self.keys = allow, []

    async def limit(self, opts):
        key = opts.get("key") if isinstance(opts, dict) else getattr(opts, "key", None)
        self.keys.append(key)
        return {"success": len(self.keys) <= self.allow}


def _post(body, limiter=None, path="/mcp", method="POST", ip="203.0.113.7"):
    """POST through the real fetch(), with the engine stubbed so nothing leaves."""
    engine_calls = []

    class Req(FakeRequest):
        async def json(self):
            return body

    async def _assess(address, *a, **k):
        engine_calls.append(address)
        return {"address": address, "risk_level": "low", "risk_score": 0,
                "confidence": "high", "signals": [], "evidence": {},
                "recommendation": "x"}

    saved = (risk.assess, entry._record)
    risk.assess, entry._record = _assess, (lambda env, blobs, doubles: None)
    try:
        w = entry.Default()
        w.env = types.SimpleNamespace(CALL_LIMITER=limiter) if limiter else None
        hdrs = {"user-agent": "somebodys-bot/1.0", "cf-connecting-ip": ip}
        return asyncio.run(w.fetch(Req("https://vetagent.dev" + path, method=method,
                                       headers=hdrs))), engine_calls
    finally:
        risk.assess, entry._record = saved


def test_the_deploy_flood_cannot_fail_on_a_minute_boundary():
    """W48 / T078 NC1: the minute-boundary argument assumes one caller in one location.
    Within that location,125 calls in less than60 seconds cross at most one boundary
    and force one window past60. It does not hold when fresh connections split by colo.
    The original75-call check could split as30/49 and failed on3 of17 deploys with a
    working counter (2026-09-18 review); one failure inside a minute also needed the
    location dimension. Connection reuse and bounded location aggregates are tested
    separately; only a real429/limited response proves observed enforcement, not a
    precise or worldwide quota. These two assertions retain the count and cf-ray seam.
    """
    print("\n[deploy] count/window bound assumes a single caller and location")
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "deploy.yml"), encoding="utf-8").read()
    step = wf[wf.index("a flooding caller must get 429"):]
    step = step[:step.index("- name:")]
    m = re.search(r"seq 1 (\d+)", step)
    check("the flood sends enough calls that one window must pass the limit",
          bool(m) and int(m.group(1)) >= 125, m.group(0) if m else "no seq")
    check("  and records the data centre each call landed on",
          "cf-ray" in step.lower(), "no cf-ray in the flood step")


def test_one_request_cannot_carry_an_unbounded_batch():
    """Fifty assessments rode in on one POST and were all served.

    Measured by the 2026-09-13 adversarial audit against production: a JSON-RPC batch of
    50 `tools/call` messages returned HTTP 200 and 50 assessments in 1.42 s. Each
    assessment makes about four requests to free upstreams that rate-limit by IP, and a
    Worker's egress IP is shared -- so one such POST spends roughly 200 upstream requests
    of a budget every other caller also draws on, and pushes them into `unknown`. The
    service is free; that makes it the one thing it cannot afford.
    """
    print("\n[abuse] a batch has a ceiling")
    cap = entry.MAX_BATCH
    r, ran = _post([_call(i=i) for i in range(cap + 1)])
    check("a batch over the ceiling is refused", r.status == 400, str(r.status))
    check("  before a single assessment runs", ran == [], "%d ran" % len(ran))
    check("  and the refusal says what the ceiling is", str(cap) in (r.body or ""),
          (r.body or "")[:160])
    r, ran = _post([_call(i=i) for i in range(cap)])
    check("a batch at the ceiling is served", r.status == 200 and len(ran) == cap,
          "%s, %d ran" % (r.status, len(ran)))


def test_a_caller_that_floods_is_slowed_not_served():
    """Nothing limited how fast one caller could spend the shared upstream budget.

    Same audit: ten back-to-back calls, no 429. Calls are counted per minute in the edge
    cache under a hash of the connecting IP. The counter is injected here as
    `env.CALL_LIMITER`; in production it is `_EdgeCounter`, after Cloudflare's own binding
    answered success on 313 calls in 100 s against a limit of 60.

    Fail-open when there is no cache runtime -- local runs -- because
    a limiter that refuses everyone when it breaks turns an abuse control into an outage.
    That choice has a cost, paid in the deploy workflow: the smoke test checks that
    production does answer 429, so "absent" cannot quietly become the permanent state.
    """
    print("\n[abuse] a flooding caller gets 429")
    lim = _Limiter(allow=2)
    for i in range(2):
        r, ran = _post(_call(i=i), limiter=lim)
        check("call %d under the limit is served" % (i + 1), r.status == 200, str(r.status))
    r, ran = _post(_call(i=3), limiter=lim)
    check("the call over the limit is a 429", r.status == 429, str(r.status))
    check("  and runs no assessment", ran == [], str(ran))
    check("  and says when to come back",
          (r.headers or {}).get("retry-after") == str(entry.RATE_LIMIT_PERIOD_SECONDS),
          str(r.headers))
    check("the limiter is keyed by the connecting IP", lim.keys and lim.keys[0] == "203.0.113.7",
          str(lim.keys))

    lim = _Limiter(allow=0)
    r, ran = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                   limiter=lim)
    check("discovery is not rate limited -- it costs no upstream", r.status == 200,
          str(r.status))

    lim = _Limiter(allow=1)
    r, ran = _post([_call(i=1), _call(i=2)], limiter=lim)
    check("each tool call in a batch counts", len(lim.keys) == 2 and len(ran) == 1,
          "keys=%s ran=%d" % (lim.keys, len(ran)))
    check("  and the limited one gets its own error",
          r.status == 200 and "Rate limit" in (r.body or ""), (r.body or "")[:200])

    lim = _Limiter(allow=0)
    r, ran = _post(None, limiter=lim, path="/assess/%s" % ADDRESS, method="GET")
    check("the HTTP interface is limited too", r.status == 429 and ran == [],
          "%s %s" % (r.status, ran))

    r, ran = _post(_call(), limiter=None)
    check("no cache runtime: fail open, served", r.status == 200 and len(ran) == 1,
          str(r.status))


def test_the_worker_hands_its_provider_key_to_the_engine():
    """A key set with `wrangler secret put` has to reach risk.py, or the keyed fallback is
    code that never runs -- the rate limiter's exact shape on its first deploy."""
    print("\n[keys] the Worker's CG_DEMO_KEY secret reaches the engine")

    class Req(FakeRequest):
        async def json(self):
            return {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

    saved = risk._onchain_key()
    try:
        w = entry.Default()
        w.env = types.SimpleNamespace(CG_DEMO_KEY="CG-from-a-secret")
        asyncio.run(w.fetch(Req("https://vetagent.dev/mcp", method="POST")))
        check("a request configures the engine with the secret",
              risk._onchain_key() == "CG-from-a-secret", str(risk._onchain_key() is not None))
        w.env = types.SimpleNamespace()
        asyncio.run(w.fetch(Req("https://vetagent.dev/mcp", method="POST")))
        check("no secret: the engine is keyless again", risk._onchain_key() is None,
              "a key survived its secret being removed")
    finally:
        risk.configure(types.SimpleNamespace(CG_DEMO_KEY=saved) if saved else None)


def test_traded_depth_gap_records_a_fixed_unique_label():
    """T-012 AC 5a: telemetry names the actual new gap without copying upstream text."""
    print("\n[T-012] a traded depth gap has its own fixed telemetry class")
    pair = {"chainId": "bsc", "dexId": "pancakeswap",
            "baseToken": {"address": ADDRESS, "symbol": "TKN"},
            "quoteToken": {"address": "0xq"},
            "txns": {"h24": {"buys": 10540, "sells": 148}}}
    original = risk._fetch_json

    async def stub(url, *a, **kw):
        if "dex/tokens" in url:
            return {"pairs": [pair]}
        if "dex/search" in url:
            return {"pairs": []}
        if "geckoterminal" in url:
            return {"data": []}
        return risk.NO_DATA if "honeypot.is" in url or "rugcheck" in url else None

    risk._fetch_json = stub
    try:
        observed = asyncio.run(risk.assess(ADDRESS, chain_hint="bsc"))
        gaps = (observed.get("evidence") or {}).get("data_gaps") or []
        answer = {"risk_level": "unknown", "unknown_kind": "coverage", "evidence": {"data_gaps": gaps}}
        why = entry._why_unknown(answer)
        match = re.fullmatch(r"coverage\|liquidity:([a-z ]+)\|sellability:no record", why)
        label = match.group(1) if match else ""
        prior_labels = {word for phrase, word in entry._GAP_CLASSES
                        if phrase not in next((g["reason"] for g in gaps
                                              if g.get("dimension") == "liquidity"), "")}
        check("T-012 telemetry records exactly the fixed new class and no-record class",
              bool(match) and label not in prior_labels and label not in ("other", "no depth"), why)
        check("T-012 telemetry label contains only lowercase words", bool(re.fullmatch(r"[a-z ]+", label)), label)
        check("T-012 telemetry does not copy the address or trade count",
              ADDRESS.lower() not in why.lower() and not re.search(r"\d", why), why)
        pair["txns"] = {"h24": {"buys": 0, "sells": 0}}
        untraded = asyncio.run(risk.assess(ADDRESS, chain_hint="bsc"))
        old = {"risk_level": "unknown", "unknown_kind": "coverage", "evidence": untraded["evidence"]}
        check("T-012 untraded depth gap retains its existing telemetry label",
              entry._why_unknown(old) == "coverage|liquidity:no depth|sellability:no record",
              entry._why_unknown(old))
    finally:
        risk._fetch_json = original


def test_unknown_page_distinguishes_traded_depth_from_absence():
    """T-012 AC 6b: the public absence paragraph states the narrow unknown case."""
    import pages
    print("\n[T-012] /unknown names the traded-depth exception")
    section = pages.UNKNOWN_HTML.split("<h2>When the absence is the answer</h2>", 1)[-1].split("<h2>", 1)[0]
    check("T-012 /unknown says traded pools are not an absence", "not an absence" in section, section)
    check("T-012 /unknown names last-day sells, missing depth and unknown",
          all(x in section for x in ("sells", "last day", "depth", "unknown")), section)
    check("T-012 /unknown adds no digits to the rule", not re.search(r"\d", section), section)
    check("T-012 /unknown promises no rating for retry", "retry" not in section.lower(), section)


def _t012_transaction_container_cases():
    cases = []
    for level in ("txns", "h24"):
        for label, value in (("list", [1]), ("text", "bad"), ("integer", 1),
                             ("true", True), ("false", False), ("null", None),
                             ("empty", {})):
            fields = {"txns": value if level == "txns" else {"h24": value}}
            cases.append((level + " " + label, fields, False))
    return cases + [("txns missing", {}, False), ("h24 missing", {"txns": {}}, False),
                    ("finite positive sells", {"txns": {"h24": {"buys": 0, "sells": 3}}}, True)]


def test_malformed_trade_containers_preserve_http_and_mcp_assessments():
    """T-012 fix (b): real routes keep their complete verdict on unavailable containers."""
    import json
    print("\n[T-012] malformed transactions preserve the HTTP and MCP seams")
    token_url = "https://api.dexscreener.com/latest/dex/tokens/" + ADDRESS.lower()
    simulator_url = ("https://api.honeypot.is/v2/IsHoneypot?address="
                     + ADDRESS.lower() + "&chainID=56")
    saved = risk._fetch_json, entry._record, dict(risk._ONCHAIN)
    try:
        for label, fields, traded in _t012_transaction_container_cases():
            pair = {"chainId": "bsc", "dexId": "uniswap",
                    "baseToken": {"address": ADDRESS, "symbol": "TKN"},
                    "quoteToken": {"address": "0xq"}, **fields}
            for route in ("http", "mcp"):
                calls, recorded = [], []

                async def fetch(url, *a, **kw):
                    calls.append((url, bool(kw.get("mark_missing"))))
                    if url == token_url:
                        return {"pairs": [pair]}
                    if url == simulator_url:
                        return risk.NO_DATA
                    raise AssertionError("Unmatched local fixture URL: " + url)

                risk._fetch_json = fetch
                entry._record = lambda env, blobs, doubles: recorded.append(blobs)
                body = ({"address": ADDRESS, "chain_hint": "bsc"} if route == "http" else
                        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": "assess_token_risk",
                                    "arguments": {"address": ADDRESS, "chain_hint": "bsc"}}})

                class Request(FakeRequest):
                    async def json(self):
                        return body

                    async def text(self):
                        return json.dumps(body)

                prefix = "T-012 %s container %s: " % (route, label)
                response, payload, error = None, {}, ""
                try:
                    response = asyncio.run(entry.Default().fetch(Request(
                        "https://offline.invalid/" + ("assess" if route == "http" else "mcp"),
                        method="POST", headers={"content-type": "application/json",
                                                "x-mcp-client": "vetagent-offline-acceptance"})))
                    payload = json.loads(response.body)
                except Exception as exc:
                    error = type(exc).__name__
                check(prefix + "transport completes without raising", not error, error)
                check(prefix + "HTTP succeeds", response is not None and response.status == 200,
                      str(response.status if response is not None else None))
                check(prefix + "only the same two fixture requests",
                      calls == [(token_url, False), (simulator_url, True)], str(calls))
                result = payload.get("result") or {} if route == "mcp" else payload
                answer = result.get("structuredContent") or {} if route == "mcp" else result
                check(prefix + "no protocol or tool error", "error" not in payload and not result.get("isError"),
                      str(payload))
                check(prefix + "no unsafe exception detail",
                      "detail" not in payload and not any(word in str(payload) for word in
                                                         ("AttributeError", "has no attribute", "Traceback")),
                      str(payload))
                expected = "unknown" if traded else "high"
                check(prefix + "complete structured verdict",
                      answer.get("risk_level") == expected and isinstance(answer.get("signals"), list)
                      and isinstance(answer.get("evidence"), dict), str(answer))
                check(prefix + "score and driver are unchanged",
                      answer.get("risk_score") == (40 if traded else 70)
                      and (answer.get("driver") or {}).get("category") == ("sellability" if traded else "no_liquidity"),
                      str(answer))
                escalation = any(s.get("name") == "Nothing about this token can be verified"
                                 for s in answer.get("signals", []))
                check(prefix + "only the valid sell avoids no-trace", escalation is not traded, str(escalation))
                gaps = (answer.get("evidence") or {}).get("data_gaps") or []
                depth = next((g for g in gaps if g.get("dimension") == "liquidity"), {})
                simulator = next((g for g in gaps if g.get("dimension") == "sellability"), {})
                check(prefix + "critical depth gap has no invented sell evidence",
                      "liquidity" in risk._CRITICAL_DIMENSIONS and depth.get("reason") == (
                          risk._TRADED_DEPTH_REASON if traded else "about the token: no source reported pool depth"),
                      str(depth))
                check(prefix + "critical simulator gap stays",
                      "sellability" in risk._CRITICAL_DIMENSIONS and simulator.get("reason") ==
                      "about the token: the sell simulator has no record of this token", str(simulator))
                check(prefix + "valid traded control abstains and high keeps its action",
                      answer.get("next_action") == ("abstain" if traded else None), str(answer.get("next_action")))
                check(prefix + "telemetry carries the verdict without identifying the token",
                      len(recorded) == 1 and recorded[0][2] == expected
                      and ADDRESS.lower() not in str(recorded).lower(), str(recorded))
                if route == "mcp":
                    content = result.get("content") or []
                    text_answer = {}
                    try:
                        text_answer = json.loads(content[0]["text"])
                    except (IndexError, KeyError, TypeError, ValueError):
                        pass
                    check(prefix + "MCP text equals its structured assessment",
                          bool(answer) and text_answer == answer and payload.get("id") == 1, str(content))
    finally:
        risk._fetch_json, entry._record = saved[:2]
        risk._ONCHAIN.clear()
        risk._ONCHAIN.update(saved[2])


def _evidence_fixture(name):
    import json
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as source:
        return json.load(source)


async def _evidence_endpoint(surface, tool, address, chain, routes, *, verbose=True, extra=None, rpc=None):
    """Drive the actual Worker endpoint with only the supplied upstream responses."""
    import json
    import socket
    import subprocess
    from datetime import datetime, timezone
    from unittest.mock import patch

    calls = []

    def deny(*args, **kwargs):
        raise AssertionError("unexpected I/O in evidence test")

    async def fetch(url, **kwargs):
        if rpc is not None and kwargs.get("method") == "POST":
            return await rpc(url, **kwargs)
        label, status, body = routes[url]
        calls.append(label)
        if status is None:
            raise TimeoutError

        async def content():
            return json.dumps(body, allow_nan=False)

        return types.SimpleNamespace(status=status, text=content)

    async def no_owner(*args, **kwargs):
        return None

    async def no_cache(*args, **kwargs):
        return None, None

    class MCPRequest(FakeRequest):
        async def json(self):
            return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": tool, "arguments": {
                        "address": address, "chain_hint": chain, **({"verbose": True} if verbose else {}),
                        **(extra or {})}}}

    if surface == "MCP":
        request = MCPRequest("https://offline.invalid/mcp", method="POST")
    else:
        from urllib.parse import urlencode
        path = "assess" if tool == "assess_token_risk" else "liquidity"
        query = {"chain": chain, **({"verbose": "true"} if verbose else {}), **(extra or {})}
        request = FakeRequest("https://offline.invalid/%s/%s?%s" % (path, address, urlencode(query)))
    pin = risk._BENCH_NOW.set(datetime(2026, 11, 10, tzinfo=timezone.utc))
    try:
        with patch.object(socket.socket, "connect", deny), patch.object(socket, "getaddrinfo", deny), \
                patch.object(subprocess, "Popen", deny), patch.object(risk, "cf_fetch", fetch), \
                patch.object(risk, "_cache_get", no_cache), patch.object(risk, "_cache_put", no_cache), \
                patch.object(risk, "_owner_powers", no_owner), patch.object(entry, "_record"), \
                patch.dict(risk._ONCHAIN, {"key": "", "unusable": False}):
            response = await entry.Default().fetch(request)
    finally:
        risk._BENCH_NOW.reset(pin)
    result = json.loads(response.body)
    if surface == "MCP":
        result = (result.get("result") or {}).get("structuredContent") or {}
    return result, calls, response.status


_T115_TOKEN = "0x" + "12" * 20
_T115_POOL = "0x" + "34" * 20
_T115_QUOTE = "0x4200000000000000000000000000000000000006"
_T115_ZERO = "0x" + "0" * 40
_T115_DEAD = "0x" + "0" * 36 + "dead"
_T115_BLOCK = "0x106"
_T115_HASH = "0x" + "ab" * 32
_T115_SUPPLY = 10**40


async def _t115_liquidity(surface, variant="complete", *, opt=True, chain="base"):
    import json
    rpc_calls = []
    pool = "0x" + "34" * 32 if variant == "v4" else _T115_POOL
    market = {
        "pairAddress": pool, "chainId": "base", "dexId": "uniswap", "priceUsd": "1",
        "liquidity": {"usd": 80000}, "baseToken": {"address": _T115_TOKEN},
        "quoteToken": {"address": _T115_QUOTE},
    }
    markets = [market]
    if variant == "conflicting market":
        markets.append(dict(market, quoteToken={"address": "0x" + "ef" * 20}))
    if variant == "drained":
        market["liquidity"] = {"usd": 0}
    if variant == "no market":
        markets = []
    if variant == "unsupported":
        market["chainId"] = "polygon"

    def word(value):
        return "0x%064x" % (int(value, 16) if isinstance(value, str) else value)

    async def rpc(url, **kwargs):
        if kwargs.get("redirect") not in ("follow", "manual", None):
            raise TypeError("workerd requires redirect follow or manual")
        payload = json.loads(kwargs["body"])
        method, params = payload["method"], payload["params"]
        rpc_calls.append((url, method, params))
        assert kwargs.get("redirect") == "manual"
        reply = {"jsonrpc": "2.0", "id": payload["id"]}
        if method == "eth_chainId":
            reply["result"] = "0x1" if variant == "wrong chain" else "0x2105"
            if variant == "wrong envelope":
                reply["id"] = True
            if variant == "JSON code 429":
                reply["error"] = {"code": 429}
        elif method == "eth_getBlockByNumber":
            reply["result"] = {"number": _T115_BLOCK, "hash": _T115_HASH}
            if params[0] != "latest" and variant == "reorg":
                reply["result"]["hash"] = "0x" + "bc" * 32
            if params[0] != "latest" and variant == "missing final block":
                reply["result"] = None
        elif method == "eth_call":
            target, data = params[0]["to"], params[0]["data"]
            if target == _T115_POOL:
                assert data in {"0x0dfe1681", "0xd21220a7"}
                result = word(_T115_QUOTE if data == "0x0dfe1681" else _T115_TOKEN)
                if data == "0x0dfe1681" and variant == "wrong pool":
                    result = word("0x" + "41" * 20)
                if data == "0x0dfe1681" and variant == "bad pool padding":
                    result = "0x01" + result[4:]
            else:
                assert target == _T115_TOKEN
                balances = {_T115_POOL: _T115_SUPPLY // 4, _T115_ZERO: 0, _T115_DEAD: 1}
                if variant == "excess":
                    balances[_T115_DEAD] = _T115_SUPPLY
                if data == "0x18160ddd":
                    result = word(0 if variant == "zero supply" else _T115_SUPPLY)
                    if variant == "bad supply ABI":
                        result = "0x01"
                else:
                    assert data.startswith("0x70a08231") and len(data) == 74
                    holder = "0x" + data[-40:]
                    result = "0x01" if holder == _T115_DEAD and variant == "bad balance ABI" else word(balances[holder])
                    if holder == _T115_DEAD and variant == "rpc error and result":
                        reply["error"] = {"code": -32000, "message": "mock failure"}
            reply["result"] = result
        else:
            raise AssertionError(method)

        async def content():
            return json.dumps(reply)

        if method == "eth_chainId" and variant == "redirected RPC":
            async def unread():
                rpc_calls.append((url, "read redirect body", []))
                raise AssertionError("do not parse a redirect body")
            return types.SimpleNamespace(status=307, text=unread)
        if method == "eth_chainId" and variant in {"chain rate limited", "chain unavailable"}:
            return types.SimpleNamespace(status=429 if variant == "chain rate limited" else 503, text=content)
        if method == "eth_getBlockByNumber" and variant == "block rate limited":
            return types.SimpleNamespace(status=429, text=content)
        return types.SimpleNamespace(status=200, text=content)

    extra = {}
    if surface == "MCP" and opt is not None:
        extra = {"include_known_address_balances": opt, "comparison_context": []}
    elif surface == "REST" and opt is not None:
        extra = {"include_known_address_balances": str(opt).lower()}
    result, calls, http = await _evidence_endpoint(surface, "get_token_liquidity", _T115_TOKEN, chain, {
        "https://api.dexscreener.com/latest/dex/tokens/" + _T115_TOKEN: ("market", 200, {"pairs": markets}),
        "https://api.dexscreener.com/token-pairs/v1/bsc/" + _T115_TOKEN: ("preferred", 200, []),
        "https://api.geckoterminal.com/api/v2/networks/base/tokens/" + _T115_TOKEN + "/pools":
            ("fallback", 200, {"data": []}),
    }, extra=extra, rpc=rpc)
    return result, calls, rpc_calls, http


def test_t115_known_address_balances_are_opt_in_exact_and_same_block():
    async def run():
        for surface in ("MCP", "REST"):
            base, old, no_rpc, http = await _t115_liquidity(surface, opt=False)
            answer, calls, rpc, new_http = await _t115_liquidity(surface)
            reading = answer.pop("known_address_balances", {})
            base.pop("checked_at", None)
            answer.pop("checked_at", None)
            for body in (base, answer):
                for row in body.get("comparison_context", []):
                    row.pop("checked_at", None)
            check("T115 %s opt-in leaves liquidity, observation history and market reads intact" % surface,
                  http == new_http == 200 and base == answer and not no_rpc and old == calls == ["market"],
                  str((answer, calls)))
            check("T115 %s nine RPC operations use the existing Base node and pin every contract read" % surface,
                  len(rpc) == 9 and {x[0] for x in rpc} == {"https://mainnet.base.org"}
                  and rpc[0][1:] == ("eth_chainId", [])
                  and rpc[1][1:] == ("eth_getBlockByNumber", ["latest", False])
                  and rpc[-1][1:] == ("eth_getBlockByNumber", [_T115_BLOCK, False])
                  and all(m == "eth_call" and args[1] == _T115_BLOCK for _, m, args in rpc[2:-1]), str(rpc))
            samples = reading.get("balances", {})
            check("T115 %s verifies scope, raw integers, zero and a tiny positive share" % surface,
                  reading.get("status") == "ok" and reading.get("address") == _T115_TOKEN
                  and reading.get("chain") == "base" and reading.get("pool_id") == _T115_POOL
                  and reading.get("block_number") == "262" and reading.get("block_hash") == _T115_HASH
                  and reading.get("source") == "public_rpc" and reading.get("total_supply_raw") == str(_T115_SUPPLY)
                  and [(samples.get(k, {}).get("address"), samples.get(k, {}).get("balance_raw"),
                        samples.get(k, {}).get("supply_percent")) for k in ("pool", "zero", "dead")]
                  == [(_T115_POOL, str(_T115_SUPPLY // 4), "25.000000"), (_T115_ZERO, "0", "0.000000"),
                      (_T115_DEAD, "1", "<0.000001")], str(reading))
        omitted, _, rpc, _ = await _t115_liquidity("REST", opt=None)
        check("T115 legacy lookup makes no optional reads", not rpc and "known_address_balances" not in omitted)

    asyncio.run(run())


def test_t115_wrong_scope_and_partial_or_invalid_rpc_never_become_zero():
    async def run():
        for variant, chain, reason, limit in (
            ("complete", "bsc", "network_mismatch", 0),
            ("unsupported", "polygon", "unsupported_network", 0),
            ("no market", "base", "network_unconfirmed", 0),
            ("wrong chain", "base", "rpc_chain_mismatch", 1),
            ("wrong envelope", "base", "rpc_chain_unavailable", 1),
            ("redirected RPC", "base", "rpc_chain_unavailable", 1),
            ("zero supply", "base", "invalid_total_supply", 9),
            ("bad supply ABI", "base", "invalid_total_supply", 9),
            ("reorg", "base", "block_changed", 9),
            ("missing final block", "base", "block_unconfirmed", 9),
            ("excess", "base", "balances_exceed_supply", 9),
        ):
            result, _, rpc, http = await _t115_liquidity("MCP", variant, chain=chain)
            reading = result.get("known_address_balances", {})
            check("T115 %s leaves a tagged unavailable observation and usable liquidity" % reason,
                  http == 200 and reading.get("status") == "unavailable" and reading.get("reason") == reason
                  and not reading.get("balances") and len(rpc) <= limit
                  and (variant == "no market" or result.get("liquidity_usd") == 80000), str((reading, rpc)))
            if variant == "redirected RPC":
                check("T115 refuses the provider redirect after one request to the approved node",
                      rpc == [("https://mainnet.base.org", "eth_chainId", [])], str(rpc))
        for variant, role, reason, count in (
            ("v4", "pool", "pool_id_not_address", 6),
            ("conflicting market", "pool", "pool_identity_unconfirmed", 6),
            ("wrong pool", "pool", "pool_tokens_mismatch", 8),
            ("bad pool padding", "pool", "pool_tokens_unavailable", 8),
            ("bad balance ABI", "dead", "balance_unavailable", 9),
            ("rpc error and result", "dead", "balance_unavailable", 9),
        ):
            result, _, rpc, _ = await _t115_liquidity("MCP", variant)
            reading = result.get("known_address_balances", {})
            balances = reading.get("balances", {})
            missing = balances.get(role, {})
            check("T115 %s retains only verified partial observations" % variant,
                  len(rpc) == count and reading.get("status") == "partial" and reading.get("block_hash") == _T115_HASH
                  and missing.get("status") == "unavailable" and missing.get("reason") == reason
                  and "balance_raw" not in missing and balances.get("zero", {}).get("balance_raw") == "0",
                  str((reading, rpc)))
        result, _, rpc, _ = await _t115_liquidity("MCP", "drained")
        check("T115 an identified drained market can still have a measured token balance",
              result.get("status") == "drained" and result.get("liquidity_usd") == 0
              and result.get("known_address_balances", {}).get("status") == "ok" and len(rpc) == 9,
              str(result))

    asyncio.run(run())


def test_t115_first_chain_rpc_rate_limit_is_explicit_and_does_not_retry():
    async def run():
        for surface in ("MCP", "REST"):
            for variant, reason, count in (
                ("chain rate limited", "rpc_rate_limited", 1),
                ("chain unavailable", "rpc_chain_unavailable", 1),
                ("JSON code 429", "rpc_chain_unavailable", 1),
                ("block rate limited", "block_unavailable", 2),
            ):
                result, calls, rpc, http_status = await _t115_liquidity(surface, variant)
                reading = result.get("known_address_balances", {})
                message = reading.get("message", "").lower()
                check("T115 %s reports %s without retrying or losing market liquidity" % (surface, variant),
                      http_status == 200 and result.get("status") == "ok" and result.get("liquidity_usd") == 80000
                      and result.get("best_pair_address") == _T115_POOL and calls == ["market"]
                      and reading.get("status") == "unavailable" and reading.get("reason") == reason
                      and "balances" not in reading and [m for _, m, _ in rpc] ==
                      (["eth_chainId"] if count == 1 else ["eth_chainId", "eth_getBlockByNumber"])
                      and (("rate limit" in message and "manually" in message) if reason == "rpc_rate_limited"
                           else not message), str((reading, rpc)))

    asyncio.run(run())


async def _t114_assessment(surface, status, *, verbose=True, variant="regular"):
    address, pool = "0x" + "ab" * 20, "0x" + "cd" * 20
    market = {"chainId": "base", "dexId": "uniswap", "pairAddress": pool,
              "baseToken": {"address": address, "symbol": "T114"},
              "quoteToken": {"address": "0x4200000000000000000000000000000000000006"},
              "liquidity": {"usd": 1000}, "priceUsd": "0.01",
              "pairCreatedAt": 1793577600000,  # Eight days before the frozen assessment clock.
              "volume": {"h24": 5}, "txns": {"h24": {"buys": 2, "sells": 1}}}
    peers = []
    if variant == "independent high":
        peers = [dict(market, pairAddress="0x" + "de" * 20,
                      baseToken={"address": "0x" + "ef" * 20, "symbol": "T114"},
                      liquidity={"usd": 2_000_000})]
    if variant == "observed sells":
        market.update(liquidity={"usd": 80_000}, txns={"h24": {"buys": 120, "sells": 53}})
    simulation = {"token": {"address": address}, "chain": {"id": 8453}, "pairAddress": pool,
                  "simulationSuccess": True, "honeypotResult": {"isHoneypot": False},
                  "simulationResult": {"buyTax": 0, "sellTax": 0, "transferTax": 0},
                  "summary": {"risk": "low", "riskLevel": 1}}
    if variant == "failed trade":
        simulation.update(simulationSuccess=False, simulationError="SELL_FAILED")
        del simulation["simulationResult"]
    if variant == "tax and holder":
        simulation["simulationResult"]["sellTax"] = 26
        simulation["holderAnalysis"] = {"holders": 100, "failed": 5}
        simulation["contractCode"] = {"openSource": False}
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=8453"
    return await _evidence_endpoint(surface, "assess_token_risk", address, "base", {
        "https://api.dexscreener.com/latest/dex/tokens/" + address: ("market", 200, {"pairs": [market]}),
        "https://api.dexscreener.com/latest/dex/search?q=T114": ("ticker", 200, {"pairs": peers}),
        sell: ("simulator", status, simulation if status == 200 else {}),
        sell + "&pair=" + pool: ("retry", 404, {}),
    }, verbose=verbose)


def test_t114_simulator_outage_is_a_visible_gap_without_risk_corroboration():
    from unittest.mock import patch

    async def no_wait(*args, **kwargs):
        pass

    async def run():
        for surface, verbose in (("MCP", False), ("MCP", True), ("REST", False)):
            healthy, usual_calls, healthy_status = await _t114_assessment(surface, 200, verbose=verbose)
            expected_market = [s for s in healthy.get("signals", [])
                               if s["category"] in {"liquidity", "freshness", "lifecycle"}]
            check("T114 %s verbose=%s successful provider result keeps medium/68" % (surface, verbose),
                  healthy_status == 200 and (healthy.get("risk_level"), healthy.get("risk_score")) == ("medium", 68)
                  and len(expected_market) == 3
                  and all(s["severity"] in ("warn", "critical") for s in expected_market)
                  and usual_calls == ["market", "ticker", "simulator"], str((healthy, usual_calls)))
            for failure, detail, attempts in ((429, "429", 1), (503, "503", 3), (None, "TimeoutError", 3)):
                result, calls, http_status = await _t114_assessment(surface, failure, verbose=verbose)
                signals = result.get("signals", [])
                gap = {"dimension": "sellability", "source": "honeypot.is",
                       "reason": "upstream request failed (honeypot.is %s)" % detail}
                check("T114 %s verbose=%s %s is unknown/68 and keeps the market driver" % (surface, verbose, detail),
                      http_status == 200 and (result.get("risk_level"), result.get("risk_score")) == ("unknown", 68)
                      and result.get("next_action") == "retry" and result.get("driver") == healthy.get("driver")
                      and result.get("evidence", {}).get("best_pair") == healthy.get("evidence", {}).get("best_pair")
                      and result.get("evidence", {}).get("data_gaps") == [gap]
                      and all(s in signals for s in expected_market)
                      and calls == usual_calls[:2] + ["simulator"] * attempts, str((result, calls)))
                check("T114 %s verbose=%s %s coverage warning remains visible" % (surface, verbose, detail),
                      any(s["name"] == "Sellability unverified" and s["severity"] == "info"
                          and s["category"] == "coverage" and "request" in s["message"] for s in signals),
                      str(signals))

        for variant, status, expected in (
            ("regular", 404, ("high", 78, "sellability", "No simulator has traded this token")),
            ("failed trade", 200, ("high", 78, "sellability", "Sellability unverified")),
            ("tax and holder", 200, ("high", None, "sell_tax", "Extreme transaction tax")),
            ("independent high", 429, ("high", 84, "impersonation", "Almost certainly not the token you meant")),
            ("observed sells", 429, ("unknown", None, "sellability", "Sells are completing on-chain for other holders")),
        ):
            answer, calls, _ = await _t114_assessment("MCP", status, variant=variant)
            level, score, category, name = expected
            check("T114 %s keeps its original attribution" % variant,
                  answer.get("risk_level") == level and (score is None or answer.get("risk_score") == score)
                  and any(s["category"] == category and s["name"] == name for s in answer.get("signals", [])),
                  str((answer, calls)))
            if variant == "independent high":
                check("T114 high market risk exposes actual provider failure in its visible warning",
                      answer.get("driver", {}).get("category") == category
                      and any(s["category"] == "coverage" and "honeypot.is 429" in s["message"]
                              for s in answer.get("signals", []))
                      and answer.get("evidence", {}).get("data_gaps", [])[0]["reason"]
                      == "upstream request failed (honeypot.is 429)", str(answer))
            elif variant == "tax and holder":
                provider = answer.get("evidence", {}).get("honeypot", {})
                check("T114 holder sell failures and contract evidence remain visible beside sell tax",
                      provider.get("holder_analysis", {}).get("failed") == 5
                      and "5 of 100 sampled holders" in answer.get("recommendation", "")
                      and any(s["name"] == "Contract is closed source" for s in answer.get("signals", [])),
                      str(answer))
            elif variant == "observed sells":
                check("T114 observed trades remain separate from the missing simulation",
                      answer.get("evidence", {}).get("sellability_from_chain", {}).get("sells_24h") == 53
                      and answer.get("evidence", {}).get("data_gaps", [])[0]["reason"]
                      == "upstream request failed (honeypot.is 429)", str(answer))
            elif variant in {"regular", "failed trade"}:
                reason = answer.get("evidence", {}).get("data_gaps", [])[0]["reason"]
                check("T114 actual provider response preserves token-side sell gap",
                      reason.startswith("about the token:") and
                      ("no record" if variant == "regular" else "SELL_FAILED") in reason, reason)

    with patch.object(risk.asyncio, "sleep", no_wait):
        asyncio.run(run())


def test_t086_sell_evidence_at_both_entry_points():
    print("\n[T086] explicit simulation evidence is required on both attempts")
    address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    pool = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
    clean = {"token": {"address": address}, "chain": {"id": 1}, "pairAddress": pool,
             "pair": {"chainId": 1, "pair": {"address": pool}},
             "simulationSuccess": True, "honeypotResult": {"isHoneypot": False},
             "simulationResult": {"buyTax": 0, "sellTax": 0, "transferTax": 0},
             "summary": {"risk": "low", "riskLevel": 1}}
    failed = {"simulationSuccess": False, "simulationError": "BUY_FAILED"}
    market = next(p for p in _evidence_fixture("ds_weth.json")["pairs"]
                  if p["pairAddress"].lower() == pool)
    ds = "https://api.dexscreener.com/latest/dex/tokens/" + address
    search = "https://api.dexscreener.com/latest/dex/search?q=WETH"
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
    retry_url = sell + "&pair=" + market["pairAddress"]
    gt = "https://api.geckoterminal.com/api/v2/networks/eth/tokens/" + address + "/pools"
    malformed = {
        "wrong token": dict(clean, token={"address": "0x" + "a" * 40}),
        "wrong chain": dict(clean, chain={"id": 56}),
        "wrong pair chain": dict(clean, pair={"chainId": 56}),
        "null identity": dict(clean, token=None),
        "wrong venue tokens": dict(clean, pair={"chainId": 1, "pair": {
            "token0": "0x" + "a" * 40, "token1": "0x" + "b" * 40}}),
        "no simulation result": dict(clean, simulationResult=None),
        "bad tax": dict(clean, simulationResult={"buyTax": 0, "sellTax": "n/a"}),
        "missing success": {k: v for k, v in clean.items() if k != "simulationSuccess"},
        "success with error": dict(clean, simulationError="SELL_FAILED"),
        "siphoned holders": dict(clean, holderAnalysis={"holders": 100, "failed": 0, "siphoned": 1}),
        "all holders fail": dict(clean, holderAnalysis={"holders": 10, "failed": 10}),
        "partial holder evidence": dict(clean, holderAnalysis={"siphoned": 1}),
        "empty holder evidence": dict(clean, holderAnalysis={}),
        "siphoning flag": dict(clean, summary={"risk": "low", "riskLevel": 1,
                                                "flags": [{"flag": "medium_siphon_rate"}]}),
        "malformed result container": dict(clean, simulationResult=[0]),
    }
    market = dict(market, traders={"h24": {"sellers": 500}})
    async def call(surface, initial, retry, fallback=False):
        routes = {ds: ("market", 200, {"pairs": [] if fallback else [market]}),
                  gt: ("fallback", 200, _evidence_fixture("gt_weth_anchor_pools.json")),
                  search: ("ticker", 200, {"pairs": []}),
                  sell: ("sell", 200, initial), retry_url: ("retry", 200, retry),
                  sell + "&pair=0x7380e4a66f89e9fd4db32e6c6e9934130123ae66": ("retry", 200, retry)}
        return await _evidence_endpoint(surface, "assess_token_risk", address, "ethereum", routes)

    async def run():
        for surface in ("MCP", "REST"):
            for label, candidate in malformed.items():
                for phase in ("initial", "retry"):
                    initial, retry = (candidate, clean) if phase == "initial" else (failed, candidate)
                    result, calls, status = await call(surface, initial, retry)
                    ev = result.get("evidence") or {}
                    messages = [s["name"] for s in result.get("signals", [])]
                    check("T086 %s %s %s fails closed" % (surface, phase, label),
                          status == 200 and result.get("risk_level") == "unknown"
                          and any(g["dimension"] == "sellability" for g in ev.get("data_gaps", []))
                          and "Buys and sells normally" not in messages
                          and "Simulation completed" not in messages
                          and calls.count("retry") == (1 if phase == "retry" else 0))
            wrong_pool = dict(clean, pairAddress="0x" + "c" * 40)
            result, calls, _ = await call(surface, failed, wrong_pool)
            check("T086 %s wrong retry venue cannot replace failure" % surface,
                  result.get("risk_level") == "unknown" and calls[-1] == "retry"
                  and any("BUY_FAILED" in g["reason"] for g in result.get("evidence", {}).get("data_gaps", [])))
            result, calls, _ = await call(surface, failed, clean)
            check("T086 %s matching retry supplies observed sell" % surface,
                  result.get("risk_level") == "low" and calls[-1] == "retry")
            result, _, _ = await call(surface, malformed["wrong token"], clean, fallback=True)
            check("T086 %s fallback also records a sellability gap" % surface,
                  result.get("risk_level") == "unknown"
                  and result.get("evidence", {}).get("liquidity_reserve_check") == "not_checkable")
            holder_result, _, _ = await call(surface, malformed["siphoned holders"], clean)
            check("T086 %s conflicting holder observations remain visible" % surface,
                  holder_result.get("evidence", {}).get("honeypot", {}).get("holder_analysis", {})
                  .get("siphoned") == 1)
            contested = dict(clean, honeypotResult={"isHoneypot": True},
                             summary={"risk": "honeypot", "riskLevel": 100},
                             holderAnalysis={"holders": 1555, "failed": 1})
            for label, broken in (("missing taxes", dict(contested, simulationResult=None)),
                                  ("reported failure", dict(contested, simulationError="SELL_FAILED"))):
                first, _, _ = await call(surface, broken, clean)
                second, _, _ = await call(surface, failed, broken)
                check("T086 %s incomplete flagged evidence cannot release or replace (%s)" % (surface, label),
                      first.get("risk_level") != "low" and second.get("risk_level") == "unknown"
                      and any("BUY_FAILED" in g["reason"] for g in second.get("evidence", {}).get("data_gaps", [])))
            complete, _, _ = await call(surface, failed, contested)
            check("T086 %s complete matching evidence still allows a contested release" % surface,
                  complete.get("risk_level") == "low")
            adverse = dict(contested, summary={"flags": "malformed"},
                           holderAnalysis={"holders": 100, "failed": 60})
            result, _, _ = await call(surface, adverse, clean)
            check("T086 %s invalid optional metadata preserves the matching fatal holder evidence" % surface,
                  result.get("risk_level") == "high"
                  and result.get("evidence", {}).get("honeypot", {}).get("holder_analysis", {}).get("failed") == 60)

    asyncio.run(run())


def test_t087_market_evidence_at_both_entry_points():
    print("\n[T087] a market response must belong to the requested token")
    import copy

    address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    market = next(p for p in _evidence_fixture("ds_weth.json")["pairs"]
                  if p["pairAddress"].lower() == "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640")
    unrelated = copy.deepcopy(market)
    for token in ("baseToken", "quoteToken"):
        unrelated[token]["address"] = "0x" + "f" * 40
    unrelated["liquidity"]["usd"] = 10**11
    rows = _evidence_fixture("gt_weth_anchor_pools.json")["data"]
    foreign = copy.deepcopy(rows[0])
    foreign["id"] = foreign["id"].replace("eth_", "bsc_")
    for side in ("base_token", "quote_token"):
        data = foreign["relationships"][side]["data"]
        data["id"] = data["id"].replace("eth_", "bsc_")
    no_relationships = dict(rows[0], relationships={})
    composite_namespace = copy.deepcopy(rows[0])
    for side in ("base_token", "quote_token"):
        data = composite_namespace["relationships"][side]["data"]
        data["id"] = data["id"].replace("eth_", "eth_bsc_")
    invalid_ticker = copy.deepcopy(market)
    invalid_ticker["baseToken"]["symbol"] = "WETH\ud800"
    ds = "https://api.dexscreener.com/latest/dex/tokens/" + address
    gt = "https://api.geckoterminal.com/api/v2/networks/eth/tokens/" + address + "/pools"
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
    search = "https://api.dexscreener.com/latest/dex/search?q=WETH"
    clean = {"simulationSuccess": True, "honeypotResult": {"isHoneypot": False},
             "simulationResult": {"buyTax": 0, "sellTax": 0, "transferTax": 0},
             "summary": {"risk": "low", "riskLevel": 1}}
    async def run():
        for surface in ("MCP", "REST"):
            for label, primary, fallback, market_status, risk_level, sell_status in (
                ("genuine empty", {"pairs": None}, {"data": []}, "not_found", "high", 404),
                ("primary has no list field", {}, {"data": []}, "unavailable", "unknown", 404),
                ("unrelated primary", {"pairs": [unrelated]}, {"data": []}, "unavailable", "unknown", 200),
                ("wrong address family", {"pairs": [dict(market, chainId="solana")]}, {"data": []},
                 "unavailable", "unknown", 200),
                ("mixed primary", {"pairs": [None, unrelated, market]}, {}, "ok", "low", 200),
                ("missing fallback list", {"pairs": []}, {"meta": {}}, "unavailable", "unknown", 404),
                ("wrong fallback list type", {"pairs": []}, {"data": {}}, "unavailable", "unknown", 404),
                ("wrong network", {"pairs": []}, {"data": [foreign]}, "unavailable", "unknown", 200),
                ("composite network", {"pairs": []}, {"data": [composite_namespace]},
                 "unavailable", "unknown", 200),
                ("invalid namesake ticker", {"pairs": [invalid_ticker, market]}, {}, "ok", "low", 200),
                ("no fallback relationships", {"pairs": []}, {"data": [no_relationships]},
                 "unavailable", "unknown", 200),
                ("mixed fallback", {"pairs": []}, {"data": [None, foreign] + rows}, "ok", "low", 200),
                ("unrelated primary rescued", {"pairs": [unrelated]}, {"data": rows}, "ok", "low", 200),
            ):
                routes = {ds: ("primary", 200, primary), gt: ("fallback", 200, fallback),
                          sell: ("sell", sell_status, clean if sell_status == 200 else {}),
                          search: ("ticker", 200, {"pairs": []})}
                for tool in ("assess_token_risk", "get_token_liquidity"):
                    result, calls, status = await _evidence_endpoint(surface, tool, address, "ethereum", routes)
                    check("T087 %s %s %s uses target evidence" % (surface, label, tool),
                          status == 200 and ((result.get("risk_level") == risk_level
                              and (market_status == "ok" or not result.get("evidence", {}).get("best_pair")))
                              if tool == "assess_token_risk" else result.get("status") == market_status
                              and (market_status != "ok" or 0 < result.get("liquidity_usd", 0) < 10**10)),
                          str((result.get("status"), result.get("risk_level"), calls)))

            fork_copy = dict(market, chainId="pulsechain")
            routes = {ds: ("primary", 200, {"pairs": [fork_copy]}),
                      "https://api.dexscreener.com/token-pairs/v1/ethereum/" + address: ("home", 200, [market]),
                      sell: ("sell", 200, clean), search: ("ticker", 200, {"pairs": []})}
            result, calls, _ = await _evidence_endpoint(surface, "get_token_liquidity", address, "ethereum", routes)
            check("T087 %s a fork cannot shadow a same-address home pool" % surface,
                  result.get("best_pair_chain") == "ethereum" and calls == ["primary", "home"], str(result))

            flagged = dict(clean, honeypotResult={"isHoneypot": True},
                           holderAnalysis={"holders": 1555, "failed": 1},
                           summary={"risk": "honeypot", "riskLevel": 100})
            pool = market["pairAddress"]
            detail_url = "https://api.geckoterminal.com/api/v2/networks/eth/pools/" + pool
            detail = {"id": "eth_" + pool,
                      "relationships": {
                          "base_token": {"data": {"id": "eth_" + market["baseToken"]["address"].lower()}},
                          "quote_token": {"data": {"id": "eth_" + market["quoteToken"]["address"].lower()}},
                      },
                      "attributes": {"transactions": {"h24": {"sellers": 1000}}}}
            for label, body, expected in (
                ("matching detail", {"data": detail}, "low"),
                ("unscoped detail", {"data": {k: v for k, v in detail.items() if k != "relationships"}},
                 "unknown"),
                ("wrong detail", {"data": dict(detail, id="eth_0x" + "a" * 40)}, "unknown"),
                ("malformed detail", {"data": [detail]}, "unknown"),
            ):
                routes = {ds: ("primary", 200, {"pairs": [market]}), sell: ("sell", 200, flagged),
                          search: ("ticker", 200, {"pairs": []}), detail_url: ("detail", 200, body)}
                result, calls, status = await _evidence_endpoint(surface, "assess_token_risk", address, "ethereum", routes)
                pair = (result.get("evidence") or {}).get("best_pair") or {}
                check("T087 %s %s cannot supply foreign seller evidence" % (surface, label),
                      status == 200 and result.get("risk_level") == expected and calls[-1] == "detail"
                      and pair.get("sellers_24h") == (1000 if expected == "low" else None),
                      str((result.get("risk_level"), calls)))

    asyncio.run(run())


def test_t119_curve_market_never_becomes_a_balance_account():
    import json
    from test_mcp import _t119_curve_archive

    async def run():
        token, url, _, _, _, curve = _t119_curve_archive()
        requests = []

        async def rpc(host, **kwargs):
            packet = json.loads(kwargs["body"])
            requests.append((host, packet))
            if packet["method"] == "eth_chainId":
                result = "0x1"
            elif packet["method"] == "eth_getBlockByNumber":
                result = {"number": "0x106", "hash": "0x" + "ab" * 32}
            else:
                result = "0x%064x" % (100 if packet["params"][0]["data"] == "0x18160ddd" else 0)

            async def text():
                return json.dumps({"jsonrpc": "2.0", "id": packet["id"], "result": result})

            return types.SimpleNamespace(status=200, text=text)

        answer, reads, http = await _evidence_endpoint(
            "MCP", "get_token_liquidity", token, "ethereum", {url: ("market", 200, {"pairs": [curve]})},
            extra={"include_known_address_balances": True}, rpc=rpc)
        reading = answer.get("known_address_balances", {})
        targets = [p["params"][0] for _, p in requests if p["method"] == "eth_call"]
        check("T119 a verified Curve market ID never supplies a pool target to fixed-block RPC",
              http == 200 and reads == ["market"] and answer.get("best_pair_market_id") == curve["pairAddress"]
              and reading.get("status") == "partial" and reading.get("pool_id") is None and len(requests) == 6
              and {host for host, _ in requests} == {"https://rpc.mevblocker.io"}
              and {call["to"] for call in targets} == {token}
              and {call["data"] for call in targets} == {"0x18160ddd", "0x70a08231" + "0" * 64,
                                                         "0x70a08231" + "0" * 60 + "dead"}
              and "address" not in reading["balances"]["pool"], str((reading, requests)))

    asyncio.run(run())


def main():
    print("=" * 68)
    print("HTTP telemetry: the interface the gate could not see")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
