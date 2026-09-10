"""test_mcp.py — offline tests for the MCP protocol layer.

No network: the risk layer's fetches are stubbed out, so this only exercises
JSON-RPC protocol behaviour.

Run:  python tests/test_mcp.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import mcp_server  # noqa: E402
import risk  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

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


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def stub_upstream():
    async def _stub(url, *a, **kw):
        if "dexscreener" in url:
            return _load("ds_matic.json")
        if "honeypot.is" in url:
            return _load("hp_matic.json")
        return {"data": []}
    risk._fetch_json = _stub


def call(body):
    return asyncio.run(mcp_server.handle_mcp_request(body))


def test_jsonrpc_envelope():
    print("\n[JSON-RPC] response envelope")
    r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    check("jsonrpc field present", r.get("jsonrpc") == "2.0", str(r.get("jsonrpc")))
    check("id echoed back unchanged", r.get("id") == 1, str(r.get("id")))
    check("result present", "result" in r, str(r.keys()))
    check("no error", "error" not in r, "")
    check("serverInfo complete",
          r["result"]["serverInfo"]["name"] == "vetagent", str(r["result"].get("serverInfo")))


def test_errors_are_top_level():
    """Regression: unknown methods used to come back wrapped in result.error, which
    violates JSON-RPC 2.0.

    What makes this more than spec pedantry: to a compliant client, a response carrying
    a `result` key is a success. It reads `result` and never looks for `error`, so an
    error nested at `result.error` is not a reported failure -- it is invisible. For a
    risk tool that means a check which never ran comes back looking like a check that
    passed, which is the same fail-open shape the engine's own upstream handling is
    built to avoid.
    """
    print("\n[JSON-RPC] errors must be top-level")
    r = call({"jsonrpc": "2.0", "id": 7, "method": "does/not/exist"})
    check("error is top-level", "error" in r, str(r))
    check("no result key", "result" not in r, str(r))
    check("error code is -32601", r["error"]["code"] == mcp_server.METHOD_NOT_FOUND,
          str(r["error"]["code"]))
    check("id preserved", r.get("id") == 7, str(r.get("id")))

    r2 = call({"jsonrpc": "2.0", "id": 8})
    check("missing method gives InvalidRequest",
          r2.get("error", {}).get("code") == mcp_server.INVALID_REQUEST, str(r2))

    r3 = call("not-an-object")
    check("non-object gives InvalidRequest",
          r3.get("error", {}).get("code") == mcp_server.INVALID_REQUEST, str(r3))


def test_notification_gets_no_response():
    print("\n[JSON-RPC] notifications and id=0")
    r = call({"jsonrpc": "2.0", "method": "notifications/initialized"})
    check("notification gets no response", r is None, str(r))

    # id=0 is a legal request id; a truthiness check mistakes it for a notification
    r2 = call({"jsonrpc": "2.0", "id": 0, "method": "ping"})
    check("id=0 must get a response", r2 is not None, "")
    check("id=0 echoed back unchanged", r2 and r2.get("id") == 0, str(r2))


def test_protocol_negotiation():
    print("\n[MCP] protocol version negotiation")
    r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05"}})
    check("echoes back the version the client supports",
          r["result"]["protocolVersion"] == "2024-11-05",
          str(r["result"]["protocolVersion"]))
    r2 = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "1999-01-01"}})
    check("unsupported version falls back to the default",
          r2["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION,
          str(r2["result"]["protocolVersion"]))


def test_tools_list_shape():
    """The tool list is the only manual the calling model ever reads.

    This test enforces two decisions and, until 2026-09-10, carried no docstring at all --
    which is how the consolidation check found it: DECISIONS.md rates a named test as the
    strongest enforcement there is, and the retirement rule offers to delete a row "because
    the test is the documentation". Here there was no documentation to be.

    **`unknown` is not a low-risk result, and the description has to say so** (DECISIONS
    M4). An MCP client sees the tool description and nothing else -- no README, no landing
    page. A model that reads `unknown` as a softer `low` will buy on it, which is the most
    dangerous single misreading this product allows, and it is the reason the phrase "NOT a
    low-risk result" is asserted literally rather than by paraphrase.

    **The interface is English-only, and every tool carries a `title`** (DECISIONS M3).
    These tools go to an international agent ecosystem; a Chinese description blocks
    adoption outright. The check is for CJK code points specifically rather than for
    non-ASCII, because dashes and curly quotes are legitimate and a blanket ASCII rule would
    have to be worked around rather than obeyed.

    The rest is shape a caller depends on: three tools, each with an `inputSchema`, each
    annotated read-only so an agent framework knows it is safe to call speculatively, and
    `assess_token_risk` carrying an `outputSchema` -- the field whose absence on
    `find_new_hot_pools` let `count` mean two different things for a day (W22).

    This is the guard for the tool manifest, and for two decisions recorded about it.  A
    calling model never sees this repository, the README or the site. tools/list is the
    whole manual, which is why rules that look cosmetic are asserted here: every
    description has to be English, because Chinese blocks adoption outside China
    outright, and the assess description has to say in words that `unknown` is not a
    low-risk result.  `unknown` is a verdict the engine really returns -- fail-closed,
    whenever a critical check could not complete -- so it reaches callers whether or not
    anyone explained it. The check matches the literal sentence "NOT a low-risk result"
    in src/mcp_server.py. Rewording that line is meant to turn this test red; the
    wording is the guarantee, not an implementation detail.  Several separate rules are
    asserted inside this one function. Splitting or trimming it drops whichever of them
    nobody remembers.
    """
    print("\n[MCP] tools/list shape")
    r = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = r["result"]["tools"]
    check("three tools", len(tools) == 3, str(len(tools)))
    for t in tools:
        check("%s has inputSchema" % t["name"], "inputSchema" in t, "")
        check("%s has annotations" % t["name"], "annotations" in t, "")
        check("%s annotated read-only" % t["name"],
              t["annotations"].get("readOnlyHint") is True, "")
    assess = [t for t in tools if t["name"] == "assess_token_risk"][0]
    check("assess has outputSchema", "outputSchema" in assess, "")
    check("assess accepts verbose", "verbose" in assess["inputSchema"]["properties"], "")
    check("liquidity accepts chain_hint",
          "chain_hint" in [t for t in tools if t["name"] == "get_token_liquidity"][0]
          ["inputSchema"]["properties"], "")
    # The tool description is the only usage doc an LLM gets. Without an explicit
    # unknown != safe, the calling model treats unknown as low — the worst misread there is.
    check("description states unknown is not safe",
          "unknown" in assess["description"]
          and "NOT a low-risk result" in assess["description"], "")
    # Shipping gate: these tools go out to an international agent ecosystem, so the
    # descriptions have to be English. Check CJK only, not all non-ASCII — dashes and
    # curly quotes are legitimate.
    def _has_cjk(text):
        # Code points rather than literal characters, so this file stays English itself.
        return any(0x4E00 <= ord(c) <= 0x9FFF for c in text)
    for t in tools:
        check("%s description has no Chinese" % t["name"], not _has_cjk(t["description"]), "")
        for pname, prop in t["inputSchema"].get("properties", {}).items():
            check("%s.%s description has no Chinese" % (t["name"], pname),
                  not _has_cjk(prop.get("description", "")), "")
    for t in tools:
        check("%s has title" % t["name"], bool(t.get("title")), str(t.get("title")))


def test_every_tool_declares_its_output_shape():
    """W22. A field a caller reads must be declared where a caller looks.

    `find_new_hot_pools` was the only tool without an `outputSchema`, so `count`'s meaning
    -- which changed on 2026-09-08 from "fetched" to "returned" -- and the three fields
    added the same week were announced nowhere. That tool has now shipped two defects of
    exactly this shape: `count` said 20 beside three pools, and `scanned` could not tell a
    half scan from a complete one. Both were a caller reading a field name and guessing.

    The check is not "is there a schema" but "does the schema cover what the tool
    actually returns", because a schema written once and left behind is how the field
    names drifted from their meanings in the first place.
    """
    print("\n[MCP] every tool declares the shape it returns")
    tools = call({"jsonrpc": "2.0", "id": 9, "method": "tools/list"})["result"]["tools"]
    for t in tools:
        check("%s declares an outputSchema" % t["name"], "outputSchema" in t)

    pools = [t for t in tools if t["name"] == "find_new_hot_pools"][0]
    declared = set(pools["outputSchema"]["properties"])

    # Drive the real function with a stub so the comparison is against what it returns
    # today, not against what the schema's author remembered.
    rows = [{"id": "eth_0xabc%d" % i,
             "attributes": {"name": "T%d / WETH" % i, "base_token_price_usd": "1",
                            "reserve_in_usd": "10", "volume_usd": {"h24": "5"},
                            "pool_created_at": "2026-09-07T00:00:00Z"},
             "relationships": {"base_token": {"data": {"id": "eth_0xdef%d" % i}}}}
            for i in range(3)]
    original = risk._fetch_json

    async def _stub(url, *a, **k):
        return {"data": rows}

    risk._fetch_json = _stub
    try:
        got = asyncio.run(risk.new_pools("ethereum", 2))
    finally:
        risk._fetch_json = original

    missing = sorted(set(got) - declared)
    check("every key the tool returns is declared", not missing,
          "undeclared: %s" % ", ".join(missing))

    pool_props = set(pools["outputSchema"]["properties"]["pools"]["items"]["properties"])
    missing_pool = sorted(set(got["pools"][0]) - pool_props) if got.get("pools") else []
    check("every key inside a pool row is declared", not missing_pool,
          "undeclared: %s" % ", ".join(missing_pool))

    # The two fields whose meaning has already been misread once each.
    for field, needle in (("count", "NOT how many were examined"),
                          ("sources_failed", "PARTIAL")):
        desc = pools["outputSchema"]["properties"][field].get("description", "")
        check("%s says what it is not, as well as what it is" % field, needle in desc,
              desc[:70])


def test_tools_call_returns_structured_content():
    print("\n[MCP] tools/call returns structured content")
    stub_upstream()
    r = call({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "assess_token_risk",
                         "arguments": {"address": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
                                       "chain_hint": "ethereum"}}})
    res = r["result"]
    check("content present", isinstance(res.get("content"), list), "")
    check("structuredContent present", isinstance(res.get("structuredContent"), dict), "")
    check("structuredContent matches text",
          res["structuredContent"] == json.loads(res["content"][0]["text"]), "")
    check("includes risk_level", "risk_level" in res["structuredContent"], "")
    check("no error", not res.get("isError"), "")


def test_invalid_input_is_tool_error():
    print("\n[MCP] invalid input comes back as a tool error")
    stub_upstream()
    r = call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "assess_token_risk", "arguments": {"address": "0xdeadbeef"}}})
    check("isError is true", r["result"].get("isError") is True, str(r["result"]))
    check("error text readable", "Invalid token address" in r["result"]["content"][0]["text"],
          r["result"]["content"][0]["text"])

    r2 = call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
               "params": {"name": "no_such_tool", "arguments": {}}})
    check("unknown tool gives a top-level error", "error" in r2, str(r2))

    r3 = call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
               "params": {"name": "assess_token_risk", "arguments": "oops"}})
    check("non-object arguments gives InvalidParams",
          r3.get("error", {}).get("code") == mcp_server.INVALID_PARAMS, str(r3))


def test_verbose_flag_changes_payload_size():
    print("\n[MCP] verbose flag")
    stub_upstream()
    addr = "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"

    def size(verbose):
        r = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "assess_token_risk",
                             "arguments": {"address": addr, "chain_hint": "ethereum",
                                           "verbose": verbose}}})
        return len(r["result"]["content"][0]["text"])

    slim, full = size(False), size(True)
    check("default no larger than verbose", slim <= full, "slim=%d full=%d" % (slim, full))
    check("slim output < 1800 bytes", slim < 1800, "%d" % slim)


def test_array_params_are_rejected_not_fatal():
    """`"params": [1, 2]` is legal JSON-RPC, and it took the endpoint down.

    Found by external audit. `params = body.get("params") or {}` leaves a list intact --
    a list is truthy -- and `_call_tool` then calls `params.get("name")`, which raises
    AttributeError. `/mcp` is routed before the try/except that guards `/assess` and
    `/liquidity`, so nothing caught it. Inside a batch it took down every other message in
    the batch with it.

    JSON-RPC 2.0 permits `params` to be an Array. This server's methods all take arguments
    by name, so the right answer is INVALID_PARAMS -- a refusal, which is a normal thing
    for a protocol to say, rather than a 500 for a request the spec allows.

    Two smaller conformance points fixed with it: `id` is restricted to String, Number or
    Null, and a dict or list was being echoed back verbatim; and the dispatch is now
    wrapped so an unforeseen exception becomes INTERNAL_ERROR for that one message instead
    of a dead response for all of them.
    """
    print("\n[jsonrpc] a legal message must not be a fatal one")

    def call(body):
        return asyncio.run(mcp_server.handle_mcp_request(body))

    # -- Array params: a refusal, not a crash. -------------------------------
    for method in ("tools/call", "tools/list", "initialize"):
        try:
            r = call({"jsonrpc": "2.0", "id": 1, "method": method, "params": [1, 2]})
        except Exception as e:  # noqa: BLE001
            check("%s with array params does not raise" % method, False,
                  "%s: %s" % (type(e).__name__, e))
            continue
        check("%s with array params does not raise" % method, True)
        check("%s with array params is INVALID_PARAMS" % method,
              (r or {}).get("error", {}).get("code") == mcp_server.INVALID_PARAMS,
              json.dumps(r)[:200])

    # -- Other non-object params are refused the same way. -------------------
    for bad in ("a string", 7, True):
        r = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": bad})
        check("params=%r is refused" % (bad,),
              (r or {}).get("error", {}).get("code") == mcp_server.INVALID_PARAMS,
              json.dumps(r)[:200])

    # -- Absent or null params still mean "no arguments". --------------------
    for ok in ({}, None):
        r = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": ok})
        check("params=%r still lists tools" % (ok,), "result" in (r or {}),
              json.dumps(r)[:200])

    # -- id must be String, Number or Null. ----------------------------------
    for bad_id in ({"a": 1}, [1, 2]):
        r = call({"jsonrpc": "2.0", "id": bad_id, "method": "tools/list"})
        check("a %s id is refused" % type(bad_id).__name__,
              (r or {}).get("error", {}).get("code") == mcp_server.INVALID_REQUEST,
              json.dumps(r)[:200])
        check("and is not echoed back as-is", (r or {}).get("id") is None,
              json.dumps(r)[:200])

    for good_id in (0, "abc", None, 1.5):
        body = {"jsonrpc": "2.0", "id": good_id, "method": "tools/list"}
        r = call(body)
        check("a %r id is accepted" % (good_id,), "result" in (r or {}),
              json.dumps(r)[:200])


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print("=" * 68)
    print("VetAgent MCP protocol tests")
    print("=" * 68)
    for t in tests:
        t()
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
