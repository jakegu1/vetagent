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


def test_a_call_from_our_own_page_is_ours_even_with_stale_javascript():
    """The demo button's own header is not enough, because the page can be cached.

    The worker sets Cache-Control: no-cache on the landing page and the custom domain
    strips it -- verified against vetagent.dev and vetagent.jake-gu95.workers.dev on
    2026-09-07, where only the workers.dev origin returns the header. So a visitor can
    hold a copy of the page from before the tag shipped and keep arriving as an anonymous
    browser. That bucket is what put a YES on the 09-18 gate.

    Origin and Referer are set by the browser, not by our JavaScript, so they are true of
    a cached page too.
    """
    print("\n[http] a click on our own page is ours however old the page is")
    for name in ("origin", "referer"):
        for host in ("https://vetagent.dev", "https://www.vetagent.dev/",
                     "https://vetagent.jake-gu95.workers.dev/index.html"):
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
    for path, must_contain in (("/privacy", "Privacy"), ("/terms", "Terms of use")):
        r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev" + path)))
        check("%s returns 200" % path, r.status == 200, str(r.status))
        check("%s says what it is" % path, must_contain in r.body, r.body[:80])
    r = asyncio.run(w.fetch(FakeRequest("https://vetagent.dev/terms")))
    check("terms states the liability limit", "no warranty" in r.body.lower())
    check("terms repeats that unknown is not low",
          "not a low-risk result" in r.body)
    check("terms does not claim to be advice",
          "not financial advice" in r.body.lower())


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
