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
