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
    async def _stub(url, retries=2):
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
    violates JSON-RPC 2.0."""
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
