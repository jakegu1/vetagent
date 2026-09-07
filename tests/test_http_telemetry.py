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
