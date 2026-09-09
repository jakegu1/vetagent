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
