"""test_mcp.py — offline tests for the MCP protocol layer.

No network: the risk layer's fetches are stubbed out, so this only exercises
JSON-RPC protocol behaviour.

Run:  python tests/test_mcp.py
"""

import asyncio
import copy
import importlib.util
import json
import os
import socket
import sys
from contextlib import contextmanager
from unittest.mock import patch
import io
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace

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
    # 1,870 since 2026-09-14, for the same three fields; see test_output_is_compact.
    check("slim output < 1870 bytes", slim < 1870, "%d" % slim)


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


def _t028_pool(suffix):
    return {"id": "eth_pool" + suffix,
            "attributes": {"name": "Pool " + suffix, "base_token_price_usd": "1.25",
                           "reserve_in_usd": "100", "volume_usd": {"h24": "20"}},
            "relationships": {"base_token": {"data": {"id": "eth_0x" + suffix * 40}}}}


@contextmanager
def _t028_runtime(new, trending, stale=()):
    """Use the existing Workers shim, real handlers, and explicit local upstreams only."""
    import test_http_telemetry as runtime

    seen, recorded = [], []

    def no_network(*args, **kwargs):
        raise AssertionError("T-028 acceptance must not access the network")

    def loopback_only(operation):
        def connect(sock, address):
            # Windows asyncio creates its internal socketpair over loopback TCP.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return operation(sock, address)
            return no_network()
        return connect

    async def fetch(url, *args, **kwargs):
        prefix = "https://api.geckoterminal.com/api/v2/networks/"
        if not url.startswith(prefix):
            raise AssertionError("Unexpected discovery upstream: " + url)
        path = url.rsplit("/", 1)[-1]
        if path not in ("new_pools", "trending_pools"):
            raise AssertionError("Unexpected discovery listing: " + url)
        kind = "new" if path == "new_pools" else "trending"
        seen.append((kind, url))
        if kind in stale:
            risk._stale_hits().append((url, 321))
        return copy.deepcopy(new if kind == "new" else trending)

    def record(env, blobs, doubles):
        recorded.append((list(blobs), list(doubles)))

    with patch.object(socket.socket, "connect", loopback_only(socket.socket.connect)), \
            patch.object(socket.socket, "connect_ex", loopback_only(socket.socket.connect_ex)), \
            patch.object(socket, "create_connection", no_network), \
            patch.object(risk, "cf_fetch", no_network), \
            patch.object(risk, "_fetch_json", fetch), \
            patch.object(runtime.entry, "_record", record):
        yield runtime, recorded, seen


def _t028_scan(new, trending, args=("ethereum", 10), stale=()):
    with _t028_runtime(new, trending, stale) as (_, _, seen):
        try:
            result, error = asyncio.run(risk.new_pools(*args)), None
        except Exception as exc:
            result, error = {}, exc
    return result, error, seen


def _t028_malformed_listings():
    containers = [("missing data", {}), ("null data", {"data": None}),
                  ("zero data", {"data": 0}), ("boolean data", {"data": False}),
                  ("string data", {"data": "rows"}), ("empty string data", {"data": ""}),
                  ("object data", {"data": {}}), ("null body", None),
                  ("array body", []), ("nonempty array body", [{"data": []}]),
                  ("string body", "rows"), ("number body", 7), ("boolean body", True),
                  ("error body", {"status": {"error_code": 429}, "data": []})]
    bad_rows = [("null row", None), ("array row", [1]), ("string row", "row"),
                ("number row", 7), ("array id", {"id": [1]}),
                ("object id", {"id": {"value": 1}})]
    for field in ("attributes", "relationships"):
        for value in ("invalid", [1], 7):
            bad_rows.append((field + " " + type(value).__name__,
                             {"id": "eth_bad", field: value}))
    for value in ("invalid", [1], 7):
        bad_rows.append(("volume " + type(value).__name__,
                         {"id": "eth_bad", "attributes": {"volume_usd": value}}))
        bad_rows.append(("base token " + type(value).__name__,
                         {"id": "eth_bad", "relationships": {"base_token": value}}))
        bad_rows.append(("token data " + type(value).__name__,
                         {"id": "eth_bad", "relationships": {"base_token": {"data": value}}}))
    for label, row in bad_rows:
        polluted = _t028_pool("9")
        polluted["attributes"]["name"] = "Discarded listing"
        containers.append((label, {"data": [_t028_pool("1"), polluted, row, _t028_pool("2")]}))
    return containers


def test_t028_discovery_status_preserves_counts_order_and_defaults():
    print("\n[T-028] completeness is explicit without changing discovery data")
    first, second, third = (_t028_pool(x) for x in ("1", "2", "3"))
    duplicate = copy.deepcopy(second)
    duplicate["attributes"]["name"] = "Later duplicate"
    out, error, seen = _t028_scan({"data": [first, second]}, {"data": [duplicate, third]},
                                  args=(" Ethereum ", 2))
    check("T028 complete discovery succeeds", error is None, repr(error))
    check("T028 both observed listings mean ok", out.get("status") == "ok", str(out))
    check("T028 chain normalization is preserved", out.get("chain") == "ethereum"
          and out.get("network") == "eth", str(out))
    check("T028 both endpoints were read", [x[0] for x in seen] == ["new", "trending"], str(seen))
    check("T028 count and scanned keep their different meanings",
          out.get("count") == 2 and out.get("scanned") == 3, str(out))
    rows = out.get("pools", [])
    check("T028 deduplication and order preserve first listing rows",
          [(r.get("pool_id"), r.get("name"), r.get("kind")) for r in rows]
          == [("eth_pool1", "Pool 1", "new"), ("eth_pool2", "Pool 2", "new")], str(rows))
    check("T028 token and finite market fields are unchanged", bool(rows)
          and rows[0].get("token_address") == "0x" + "1" * 40
          and [rows[0].get(k) for k in ("price_usd", "liquidity_usd", "volume_24h_usd")]
          == [1.25, 100.0, 20.0], str(rows))
    check("T028 fresh scan has timestamp without stale disclosure",
          bool(out.get("checked_at")) and "served_stale" not in out, str(out))
    for limit, expected in ((0, 1), (100, 50)):
        out, error, _ = _t028_scan({"data": [{"id": "pool%d" % i} for i in range(55)]},
                                   {"data": []}, args=("solana", limit))
        check("T028 limit %s keeps clamping and optional missing fields" % limit,
              error is None and out.get("count") == expected and out.get("scanned") == 55
              and all(r.get("token_address") == "" and r.get("name") == ""
                      and r.get("price_usd") is None for r in out.get("pools", [])), repr(error))
    out, error, _ = _t028_scan({"data": []}, {"data": []}, args=())
    check("T028 default chain remains solana", error is None and out.get("chain") == "solana"
          and out.get("network") == "solana", str(out))
    check("T028 two observed empty listings mean ok and zero pools",
          out.get("status") == "ok" and out.get("count") == out.get("scanned") == 0
          and out.get("pools") == [] and out.get("sources_ok") == ["new", "trending"]
          and out.get("sources_failed") == [], str(out))


def test_t028_malformed_listing_is_atomic_and_keeps_the_other_listing():
    print("\n[T-028] malformed listings are failures, with no half-merged rows")
    survivor = {"data": [_t028_pool("9")]}
    for label, bad in _t028_malformed_listings():
        for failed in ("new", "trending"):
            out, error, seen = _t028_scan(bad if failed == "new" else survivor,
                                         survivor if failed == "new" else bad)
            tag = "T028 %s %s: " % (failed, label)
            healthy = "trending" if failed == "new" else "new"
            check(tag + "other listing survives", error is None, repr(error))
            check(tag + "failure is disclosed as partial", out.get("status") == "partial"
                  and out.get("sources_ok") == [healthy] and out.get("sources_failed") == [failed],
                  str(out))
            rows = out.get("pools", [])
            check(tag + "failed listing contributes no rows or duplicate overrides",
                  out.get("count") == out.get("scanned") == 1
                  and [(r.get("pool_id"), r.get("name"), r.get("kind")) for r in rows]
                  == [("eth_pool9", "Pool 9", healthy)], str(out))
            check(tag + "both listings are attempted", [x[0] for x in seen] == ["new", "trending"],
                  str(seen))


def test_t028_empty_failure_and_previous_observations_stay_distinct():
    print("\n[T-028] empty observed results never stand in for failed observations")
    for label, bad in _t028_malformed_listings():
        out, error, _ = _t028_scan(bad, {"data": []})
        check("T028 %s plus observed empty is partial zero" % label,
              error is None and out.get("status") == "partial"
              and out.get("count") == out.get("scanned") == 0 and out.get("pools") == []
              and out.get("sources_ok") == ["trending"] and out.get("sources_failed") == ["new"],
              str(out) + repr(error))
        _, error, _ = _t028_scan(bad, bad)
        check("T028 %s on both listings retains RuntimeError" % label,
              isinstance(error, RuntimeError) and str(error)
              == "GeckoTerminal request failed; could not scan new pools on ethereum", repr(error))
    _t028_scan({"data": [_t028_pool("1")]}, {"data": []})
    out, error, _ = _t028_scan({"data": [_t028_pool("9")]}, None, stale=("new",))
    check("T028 an older healthy listing cannot hide the failed listing",
          error is None and out.get("status") == "partial" and out.get("sources_ok") == ["new"]
          and out.get("sources_failed") == ["trending"], str(out))
    check("T028 stale disclosure survives the completeness change",
          out.get("served_stale") == [{"source": "api.geckoterminal.com", "age_seconds": 321}],
          str(out))


def test_t028_mcp_schema_declares_completeness_only_status():
    print("\n[T-028] the public tool contract names completeness explicitly")
    with _t028_runtime({"data": []}, {"data": []}):
        tools = call({"jsonrpc": "2.0", "id": 28, "method": "tools/list"})["result"]["tools"]
    schema = next(t for t in tools if t["name"] == "find_new_hot_pools")["outputSchema"]
    status = schema.get("properties", {}).get("status", {})
    check("T028 discovery requires status", "status" in schema.get("required", []), str(schema))
    check("T028 discovery status is exactly ok or partial", status.get("type") == "string"
          and status.get("enum") == ["ok", "partial"], str(status))
    description = status.get("description", "").lower()
    check("T028 status describes completeness and both versus one listing",
          "completeness" in description and "both" in description and "one" in description,
          description)
    check("T028 status makes no token risk endorsement", "risk" in description
          and ("not" in description or "never" in description), description)


def test_t028_real_http_and_mcp_preserve_status_errors_and_prospective_telemetry():
    print("\n[T-028] real routing carries completeness into future telemetry")
    good, empty = {"data": [_t028_pool("9")]}, {"data": []}
    cases = [("complete", good, empty, "ok"), ("partial", good, {}, "partial"),
             ("partial empty", {}, empty, "partial"), ("malformed failure", {}, {}, None),
             ("transport failure", None, None, None)]
    usage_path = os.path.join(os.path.dirname(__file__), "..", "bench", "usage.py")
    spec = importlib.util.spec_from_file_location("t028_usage", usage_path)
    usage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usage)
    for label, new, trending, expected in cases:
        for client in ("vetagent-manual-probe", "integrator-fixture"):
            for interface in ("http", "mcp"):
                with _t028_runtime(new, trending) as (runtime, recorded, seen):
                    body = {"jsonrpc": "2.0", "id": 28, "method": "tools/call",
                            "params": {"name": "find_new_hot_pools",
                                       "arguments": {"chain": "ethereum", "limit": 2}}}

                    class Request(runtime.FakeRequest):
                        async def json(self):
                            return body

                    request = Request("https://offline.invalid" + (
                        "/mcp" if interface == "mcp" else "/new-pools?chain=ethereum&limit=2"),
                        method="POST" if interface == "mcp" else "GET",
                        headers={"user-agent": "fixture/1", "x-mcp-client": client})
                    response = asyncio.run(runtime.entry.Default().fetch(request))
                    answer = json.loads(response.body)
                tag = "T028 %s %s %s: " % (interface, client, label)
                if expected is not None:
                    result = answer.get("result", {}) if interface == "mcp" else answer
                    data = result.get("structuredContent", {}) if interface == "mcp" else result
                    check(tag + "successful response carries completeness", response.status == 200
                          and data.get("status") == expected and not result.get("isError"), str(answer))
                    if interface == "mcp":
                        text = result.get("content", [{}])[0].get("text", "null")
                        check(tag + "structuredContent equals text", data == json.loads(text), str(answer))
                elif interface == "mcp":
                    result = answer.get("result", {})
                    check(tag + "existing tool error envelope is preserved", response.status == 200
                          and result.get("isError") is True and "structuredContent" not in result
                          and "Tool execution failed: GeckoTerminal request failed;" in
                          result.get("content", [{}])[0].get("text", ""), str(answer))
                else:
                    check(tag + "existing HTTP error envelope is preserved", response.status == 500
                          and answer.get("error") == "internal_error"
                          and answer.get("detail", "").startswith("GeckoTerminal request failed;"), str(answer))
                check(tag + "prospective telemetry has status or empty error verdict",
                      len(recorded) == 1 and recorded[0] == (
                          ["tools/call" if interface == "mcp" else "http", "find_new_hot_pools",
                           expected or "", client, "??", ""],
                          [1.0, 0.0 if expected is not None else 1.0]), str(recorded))
                check(tag + "self client separation is unchanged",
                      bool(recorded) and usage.is_self(recorded[0][0][3])
                      == (client == "vetagent-manual-probe"), str(recorded))
                check(tag + "telemetry contains no pool or token data", "eth_pool" not in json.dumps(recorded)
                      and "0x" + "9" * 40 not in json.dumps(recorded), str(recorded))
                check(tag + "real engine reads both local listings",
                      [x[0] for x in seen] == ["new", "trending"], str(seen))


def test_discovery_extreme_creation_times_keep_other_listing():
    """Creation-time overflow fails one listing without discarding the usable source."""
    print("\n[T-028] extreme numeric creation times stay inside their listing boundary")
    for label, value in (("401-digit integer", 10 ** 400), ("finite negative", -1e308)):
        value = json.loads(json.dumps(value, allow_nan=False))
        overflow = _t028_pool("2")
        overflow["attributes"]["pool_created_at"] = value
        bad = {"data": [_t028_pool("1"), overflow, _t028_pool("3")]}
        for failed in ("new", "trending"):
            healthy = "trending" if failed == "new" else "new"
            for survivor_name, survivor in (("populated", {"data": [_t028_pool("9")]}),
                                             ("empty", {"data": []}), ("all bad", bad)):
                new, trending = (bad, survivor) if failed == "new" else (survivor, bad)
                out, error, seen = _t028_scan(new, trending)
                tag = "T028 time %s %s %s: " % (label, failed, survivor_name)
                all_bad = survivor_name == "all bad"
                expected_rows = [("eth_pool9", healthy)] if survivor_name == "populated" else []
                if all_bad:
                    check(tag + "both unusable retain the existing RuntimeError",
                          isinstance(error, RuntimeError) and str(error)
                          == "GeckoTerminal request failed; could not scan new pools on ethereum",
                          repr(error))
                else:
                    check(tag + "the usable listing still returns partial",
                          error is None and out.get("status") == "partial"
                          and out.get("sources_failed") == [failed] and out.get("sources_ok") == [healthy],
                          str(out) + repr(error))
                    check(tag + "bad listing rows are discarded atomically",
                          out.get("count") == out.get("scanned") == len(expected_rows)
                          and [(r.get("pool_id"), r.get("kind")) for r in out.get("pools", [])]
                          == expected_rows, str(out))
                check(tag + "both listings are attempted", [x[0] for x in seen] == ["new", "trending"],
                      str(seen))
                for interface in ("http", "mcp"):
                    with _t028_runtime(new, trending) as (runtime, recorded, routed):
                        body = {"jsonrpc": "2.0", "id": 28, "method": "tools/call",
                                "params": {"name": "find_new_hot_pools",
                                           "arguments": {"chain": "ethereum"}}}

                        class Request(runtime.FakeRequest):
                            async def json(self):
                                return body

                        request = Request("https://offline.invalid" + (
                            "/mcp" if interface == "mcp" else "/new-pools?chain=ethereum"),
                            method="POST" if interface == "mcp" else "GET",
                            headers={"x-mcp-client": "vetagent-manual-probe"})
                        response = asyncio.run(runtime.entry.Default().fetch(request))
                        answer = json.loads(response.body)
                    route_tag = tag + interface + " "
                    result = answer.get("result", {}) if interface == "mcp" else answer
                    data = result.get("structuredContent", {}) if interface == "mcp" else result
                    if all_bad:
                        if interface == "mcp":
                            check(route_tag + "all-bad tool error retains the scan failure",
                                  response.status == 200 and result.get("isError") is True
                                  and "structuredContent" not in result
                                  and "Tool execution failed: GeckoTerminal request failed;" in
                                  result.get("content", [{}])[0].get("text", ""), str(answer))
                        else:
                            check(route_tag + "all-bad HTTP error retains the scan failure",
                                  response.status == 500 and answer.get("error") == "internal_error"
                                  and answer.get("detail", "").startswith("GeckoTerminal request failed;"),
                                  str(answer))
                    else:
                        check(route_tag + "survivor response is a partial success",
                              response.status == 200 and not result.get("isError")
                              and data.get("status") == "partial" and data.get("sources_ok") == [healthy]
                              and data.get("sources_failed") == [failed], str(answer))
                        check(route_tag + "response contains only the complete surviving listing",
                              data.get("count") == data.get("scanned") == len(expected_rows)
                              and [(r.get("pool_id"), r.get("kind")) for r in data.get("pools", [])]
                              == expected_rows, str(answer))
                        if interface == "mcp":
                            check(route_tag + "text and structured content agree",
                                  not result.get("isError") and data == json.loads(
                                      result.get("content", [{}])[0].get("text", "null")),
                                  str(answer))
                    check(route_tag + "telemetry distinguishes partial from error",
                          len(recorded) == 1 and recorded[0] == (
                              ["tools/call" if interface == "mcp" else "http", "find_new_hot_pools",
                               "" if all_bad else "partial", "vetagent-manual-probe", "??", ""],
                              [1.0, 1.0 if all_bad else 0.0]), str(recorded))
                    check(route_tag + "both local listings were attempted",
                          [x[0] for x in routed] == ["new", "trending"], str(routed))


@contextmanager
def _t030_mcp_market(fallback):
    """Feed actual upstream conversion, selection, assessment and MCP serialization locally."""
    address = "0x" + "ef" * 20
    anchor = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    pool = "0x" + "ab" * 32
    seen = []
    raw = {"id": "eth_" + pool,
           "attributes": {"address": pool, "name": "TOKEN / USDC",
                          "base_token_price_usd": "1", "reserve_in_usd": "250000",
                          "volume_usd": {"h24": "100000"},
                          "transactions": {"h24": {"buys": 40, "sells": 35}},
                          "pool_created_at": "2020-09-13T12:26:40Z"},
           "relationships": {"base_token": {"data": {"id": "eth_" + address}},
                             "quote_token": {"data": {"id": "eth_" + anchor}}}}
    pair = {"chainId": "ethereum", "dexId": "uniswap", "pairAddress": pool,
            "baseToken": {"address": address, "symbol": ""},
            "quoteToken": {"address": anchor, "symbol": "USDC"},
            "priceUsd": "1", "priceNative": "1", "liquidity": {"usd": 250_000},
            "volume": {"h24": 100_000}, "txns": {"h24": {"buys": 40, "sells": 35}},
            "pairCreatedAt": 1_600_000_000_000}

    class NetworkForbidden(BaseException):
        pass

    def no_network(*args, **kwargs):
        raise NetworkForbidden("T-030 MCP acceptance forbids external network access")

    def loopback_only(operation):
        def connect(sock, destination):
            if isinstance(destination, tuple) and destination[0] in ("127.0.0.1", "::1"):
                return operation(sock, destination)
            return no_network()
        return connect

    async def fetch(url, *args, **kwargs):
        seen.append(url)
        if url == "https://api.dexscreener.com/latest/dex/tokens/" + address:
            return {"pairs": [] if fallback else [copy.deepcopy(pair)]}
        if url == "https://api.geckoterminal.com/api/v2/networks/eth/tokens/" + address + "/pools":
            return {"data": [copy.deepcopy(raw)]}
        if url.startswith("https://api.honeypot.is/v2/IsHoneypot?address="):
            return _load("hp_matic.json")
        if url.startswith("https://api.dexscreener.com/latest/dex/search?q="):
            return {"pairs": []}
        return no_network()

    with patch.object(socket.socket, "connect", loopback_only(socket.socket.connect)), \
            patch.object(socket.socket, "connect_ex", loopback_only(socket.socket.connect_ex)), \
            patch.object(socket, "create_connection", no_network), \
            patch.object(socket, "getaddrinfo", no_network), \
            patch.object(risk, "cf_fetch", None), \
            patch.object(risk, "_fetch_json", fetch):
        yield address, pool, seen


def test_unchecked_reserve_disclosure_reaches_both_real_mcp_tools():
    """The marker must survive the real loader, both assess modes and both MCP payloads."""
    print("\n[T-030 MCP] unchecked reserve disclosure survives the complete tool seam")
    note = "Upstream estimate; reserve amounts not checked."
    for fallback in (False, True):
        with _t030_mcp_market(fallback) as (address, pool, seen):
            for tool, extra in (("assess_token_risk", {"verbose": False}),
                                ("assess_token_risk", {"verbose": True}),
                                ("get_token_liquidity", {})):
                start = len(seen)
                response = call({"jsonrpc": "2.0", "id": 30, "method": "tools/call",
                                 "params": {"name": tool, "arguments": {
                                     "address": address, "chain_hint": "ethereum", **extra}}})
                result = response.get("result") or {}
                data = result.get("structuredContent") or {}
                tag = ("fallback" if fallback else "other provider") + " " + tool + str(extra) + ": "
                check(tag + "normal structured success and text agree",
                      not result.get("isError") and bool(data)
                      and data == json.loads(result.get("content", [{}])[0].get("text", "null")), str(response))
                evidence = data.get("evidence", {}) if tool == "assess_token_risk" else data
                check(tag + "the conditional reserve marker reaches the client",
                      evidence.get("liquidity_reserve_check") == "not_checkable", str(data))
                if tool == "assess_token_risk":
                    signals = [s for s in data.get("signals", []) if s.get("category") == "liquidity"]
                    check(tag + "existing adequate signal has the exact qualification",
                          len(signals) == 1 and signals[0].get("severity") == "ok"
                          and signals[0].get("name") == "Liquidity is adequate"
                          and signals[0].get("message") == "Main pair holds $250,000. " + note, str(signals))
                    check(tag + "the public identifier remains compact",
                          pool not in json.dumps(data)
                          and ((evidence.get("best_pair") or {}).get("pair_address") == pool[:48] + "..."
                               if extra["verbose"] else "pair_address" not in (evidence.get("best_pair") or {})),
                          str(evidence.get("best_pair")))
                else:
                    check(tag + "usable upstream numbers and qualification coexist",
                          data.get("status") == "ok" and data.get("liquidity_usd") == 250_000
                          and data.get("price_usd") == 1 and data.get("volume_24h_usd") == 100_000
                          and data.get("pairs_total") == 1 and data.get("note") == note, str(data))
                calls = seen[start:]
                expected = ["https://api.dexscreener.com/latest/dex/tokens/" + address]
                if fallback:
                    expected.append("https://api.geckoterminal.com/api/v2/networks/eth/tokens/" + address + "/pools")
                if tool == "assess_token_risk":
                    if fallback:
                        expected.append("https://api.dexscreener.com/latest/dex/search?q=TOKEN")
                    expected.append("https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1")
                check(tag + "disclosure makes no additional request", calls == expected, str(calls))


def test_liquidity_schema_explains_upstream_ok_without_certifying_unmarked_pools():
    print("\n[T-030 MCP] optional reserve marker and honest status description")
    tools = call({"jsonrpc": "2.0", "id": 30, "method": "tools/list"})["result"]["tools"]
    tool = next(t for t in tools if t["name"] == "get_token_liquidity")
    schema = tool["outputSchema"]
    field = schema.get("properties", {}).get("liquidity_reserve_check") or {}
    check("reserve marker is an optional string with exactly the one observed enum",
          field.get("type") == "string" and field.get("enum") == ["not_checkable"]
          and "liquidity_reserve_check" not in schema.get("required", []), str(field))
    description = tool["description"].lower()
    check("ok explicitly means usable upstream data", "'ok' means usable upstream data" in description, description)
    check("ok does not certify reserves or executable sell depth",
          "not independently verified reserves or executable sell depth" in description, description)
    check("absence of the optional marker never certifies reserves, prices or exits",
          "missing" in description and "marker" in description and "never" in description
          and "prices" in description and "exit trade" in description, description)


def _t031_reply(body, status=200):
    return status, json.dumps(body)


def _t031_pool(suffix, net="eth"):
    row = _t028_pool(suffix)
    row["id"] = net + "_pool" + suffix
    address = "1" * 43 + suffix if net == "solana" else "0x" + suffix * 40
    row["relationships"]["base_token"]["data"]["id"] = net + "_" + address
    row["attributes"]["pool_created_at"] = "2026-10-16T00:00:00Z"
    return row


@contextmanager
def _t031_runtime(outcomes, key="t031-synthetic-header-only-credential", cache=None,
                  real_fetch=risk._fetch_json):
    """Exercise real retries/cache/fetch and handlers with all upstreams local and bounded."""
    import test_http_telemetry as runtime

    state = {"requests": [], "cache_reads": [], "cache_writes": [], "sleeps": [],
             "recorded": [], "blocked": [], "logs": io.StringIO(), "unexpected": []}
    cached = copy.deepcopy(cache or {})
    env = SimpleNamespace(CG_DEMO_KEY=key) if key is not None else None

    def no_network(*args, **kwargs):
        state["blocked"].append("external network blocked")
        raise AssertionError("T-031 acceptance must not access external networking")

    def loopback_only(operation):
        def connect(sock, address):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return operation(sock, address)
            return no_network()
        return connect

    def route(url):
        for provider, prefix in (("coingecko", "https://api.coingecko.com/api/v3/onchain/"),
                                 ("geckoterminal", "https://api.geckoterminal.com/api/v2/")):
            if url.startswith(prefix):
                parts = url[len(prefix):].split("/")
                if len(parts) == 3 and parts[0] == "networks" and parts[2] in (
                        "new_pools", "trending_pools"):
                    return provider, "new" if parts[2] == "new_pools" else "trending"
        state["unexpected"].append("unexpected URL")
        raise AssertionError("Unexpected local discovery upstream")

    async def fetch(url, **kwargs):
        provider, kind = route(url)
        state["requests"].append((provider, kind, url, dict(kwargs.get("headers") or {})))
        if len(state["requests"]) > 12:
            raise AssertionError("Discovery exceeded two providers times three attempts per listing")
        response = outcomes.get((provider, kind), _t031_reply({"data": []}))
        if isinstance(response, Exception):
            raise response
        status, text = response

        class Response:
            async def text(self):
                return text

        answer = Response()
        answer.status = status
        return answer

    async def cache_get(url):
        state["cache_reads"].append(url)
        return copy.deepcopy(cached.get(route(url), (None, None)))

    async def cache_put(url, data, ttl=None):
        state["cache_writes"].append(url)
        cached[route(url)] = copy.deepcopy(data), 0

    async def sleep(delay):
        state["sleeps"].append(delay)

    def record(env, blobs, doubles):
        state["recorded"].append((list(blobs), list(doubles)))

    with patch.object(socket.socket, "connect", loopback_only(socket.socket.connect)), \
            patch.object(socket.socket, "connect_ex", loopback_only(socket.socket.connect_ex)), \
            patch.object(socket, "create_connection", no_network), \
            patch.object(socket, "getaddrinfo", no_network), \
            patch.object(risk, "cf_fetch", fetch), \
            patch.object(risk, "_fetch_json", real_fetch), \
            patch.object(risk, "_cache_get", cache_get), \
            patch.object(risk, "_cache_put", cache_put), \
            patch.object(risk.asyncio, "sleep", sleep), \
            patch.object(risk, "_clock_now", lambda: datetime(2026, 10, 18, tzinfo=timezone.utc)), \
            patch.object(risk, "_now_iso", lambda: "2026-10-18T00:00:00Z"), \
            patch.dict(risk._ONCHAIN, risk._ONCHAIN.copy(), clear=True), \
            patch.object(runtime.entry, "_record", record), \
            redirect_stdout(state["logs"]), redirect_stderr(state["logs"]):
        risk.configure(env)
        yield runtime, state, env


def _t031_scan(outcomes, key="t031-synthetic-header-only-credential", cache=None,
                args=("ethereum", 10)):
    with _t031_runtime(outcomes, key=key, cache=cache) as (_, state, _):
        try:
            answer, error = asyncio.run(risk.new_pools(*args)), None
        except Exception as exc:
            answer, error = {}, exc
    return answer, error, state


def _t031_trace(state):
    return [(provider, kind) for provider, kind, _, _ in state["requests"]]


def _t031_private(tag, state, answer, error=None):
    marker = "t031-synthetic-header-only-credential"
    visible = json.dumps([answer, str(error), state["recorded"], state["cache_reads"],
                          state["cache_writes"], state["logs"].getvalue()])
    check(tag + "credential never reaches output, errors, cache keys, telemetry or logs",
          marker not in visible)
    check(tag + "credential is only the keyed host header",
          all(marker not in url and headers.get("Accept") == "application/json"
              and (headers.get("x-cg-demo-api-key") == marker if provider == "coingecko"
                   else "x-cg-demo-api-key" not in headers and marker not in str(headers))
              for provider, _, url, headers in state["requests"]))
    check(tag + "upstreams remain bounded local fixtures",
          len(state["requests"]) <= 12 and not state["blocked"] and not state["unexpected"])


def test_t031_keyed_preference_and_independent_listing_fallback():
    print("\n[T-031] existing configured provider is preferred separately for each listing")
    for fallback in ((), ("new",), ("trending",), ("new", "trending")):
        outcomes, expected = {}, []
        for kind, suffix in (("new", "1"), ("trending", "2")):
            outcomes[("coingecko", kind)] = (_t031_reply({}, 429) if kind in fallback else
                                               _t031_reply({"data": [_t031_pool(suffix)]}))
            outcomes[("geckoterminal", kind)] = _t031_reply({"data": [_t031_pool(suffix)]})
            expected.append(("coingecko", kind))
            if kind in fallback:
                expected.append(("geckoterminal", kind))
        answer, error, state = _t031_scan(outcomes)
        tag = "T031 fallback %s: " % (fallback,)
        check(tag + "keyed source is first and only necessary fallback is called",
              _t031_trace(state) == expected, str(_t031_trace(state)))
        check(tag + "provider redundancy remains two observed listing kinds",
              error is None and answer.get("status") == "ok"
              and answer.get("sources_ok") == ["new", "trending"]
              and answer.get("sources_failed") == [] and answer.get("count") == answer.get("scanned") == 2)
        check(tag + "rows retain listing order and usable token addresses",
              [(row["pool_id"], row["kind"]) for row in answer.get("pools", [])]
              == [("eth_pool1", "new"), ("eth_pool2", "trending")]
              and all(risk.validate_address(row["token_address"]) for row in answer.get("pools", [])))
        _t031_private(tag, state, answer, error)
    empty = {("coingecko", kind): _t031_reply({"data": []}) for kind in ("new", "trending")}
    empty.update({("geckoterminal", kind): _t031_reply({"data": [_t031_pool("9")]})
                  for kind in ("new", "trending")})
    answer, error, state = _t031_scan(empty)
    check("T031 valid keyed empty is final without a redundant copy", error is None
          and answer.get("status") == "ok" and answer.get("count") == answer.get("scanned") == 0
          and answer.get("pools") == []
          and _t031_trace(state) == [("coingecko", "new"), ("coingecko", "trending")])
    _t031_private("T031 keyed empty: ", state, answer, error)


def test_t031_no_or_invalid_key_preserves_complete_parent_answer():
    print("\n[T-031] no usable key keeps the exact unkeyed answer")
    first, second = _t031_pool("1"), _t031_pool("2")
    duplicate = copy.deepcopy(first)
    duplicate["attributes"]["name"] = "Discarded later duplicate"
    outcomes = {("geckoterminal", "new"): _t031_reply({"data": [first]}),
                ("geckoterminal", "trending"): _t031_reply({"data": [duplicate, second]})}
    expected = {"status": "ok", "chain": "ethereum", "network": "eth", "count": 1,
                "scanned": 2, "sources_ok": ["new", "trending"], "sources_failed": [],
                "pools": [{"kind": "new", "pool_id": "eth_pool1", "token_address": "0x" + "1" * 40,
                           "name": "Pool 1", "price_usd": 1.25, "liquidity_usd": 100.0,
                           "volume_24h_usd": 20.0, "pool_age_days": 2}],
                "checked_at": "2026-10-18T00:00:00Z"}
    for key in (None, "", "short", "\x01", "contains spaces but is long", "a" * 20 + "\x01"):
        answer, error, state = _t031_scan(outcomes, key=key, args=(" Ethereum ", 0))
        check("T031 absent or unusable key preserves every parent answer field",
              error is None and answer == expected)
        check("T031 absent or unusable key only calls the original provider",
              _t031_trace(state) == [("geckoterminal", "new"), ("geckoterminal", "trending")])
        _t031_private("T031 keyless: ", state, answer, error)


def test_t031_bad_provider_replies_fall_back_before_atomic_merge():
    print("\n[T-031] transport, containers and later malformed rows all trigger fallback")
    failures = [(label, _t031_reply(body), 1) for label, body in _t028_malformed_listings()]
    failures.extend([("invalid JSON", (200, "{broken"), 3),
                     ("HTTP refusal", _t031_reply({}, 503), 3),
                     ("transport exception", OSError("private transport text"), 3)])
    for label, bad, attempts in failures:
        for failed in ("new", "trending"):
            other = "trending" if failed == "new" else "new"
            outcomes = {("coingecko", failed): bad,
                        ("geckoterminal", failed): _t031_reply({"data": [_t031_pool("9")]}),
                        ("coingecko", other): _t031_reply({"data": [_t031_pool("8")]})}
            answer, error, state = _t031_scan(outcomes)
            tag = "T031 %s %s: " % (failed, label)
            expected = [("coingecko", "new")] * (attempts if failed == "new" else 1)
            if failed == "new":
                expected.append(("geckoterminal", "new"))
            expected.extend([("coingecko", "trending")] * (attempts if failed == "trending" else 1))
            if failed == "trending":
                expected.append(("geckoterminal", "trending"))
            check(tag + "real fetch attempts retain retry bounds and independent routes",
                  _t031_trace(state) == expected, str(_t031_trace(state)))
            check(tag + "complete fallback observes both listings", error is None
                  and answer.get("status") == "ok" and answer.get("sources_ok") == ["new", "trending"]
                  and answer.get("sources_failed") == [])
            wanted = [("eth_pool9", "Pool 9", failed), ("eth_pool8", "Pool 8", other)]
            if failed == "trending":
                wanted.reverse()
            check(tag + "no partial row or duplicate override survives the failed provider",
                  answer.get("count") == answer.get("scanned") == 2
                  and [(row["pool_id"], row["name"], row["kind"]) for row in answer.get("pools", [])] == wanted)
            check(tag + "backoff remains the existing fetch policy",
                  state["sleeps"] == ([0.3, 0.6] if attempts == 3 else []))
            _t031_private(tag, state, answer, error)


def test_t031_partial_empty_and_total_failure_keep_truthful_diagnostics():
    print("\n[T-031] listing completeness and safe all-source diagnostics stay distinct")
    for failed in ("new", "trending"):
        other = "trending" if failed == "new" else "new"
        for rows in ([], [_t031_pool("9")]):
            outcomes = {(provider, failed): _t031_reply({"data": [_t031_pool("1"), None]})
                        for provider in ("coingecko", "geckoterminal")}
            outcomes[("coingecko", other)] = _t031_reply({"data": rows})
            answer, error, state = _t031_scan(outcomes)
            check("T031 all providers failing one listing yields truthful partial or partial-empty",
                  error is None and answer.get("status") == "partial"
                  and answer.get("sources_failed") == [failed] and answer.get("sources_ok") == [other]
                  and answer.get("count") == answer.get("scanned") == len(rows)
                  and all(row["kind"] == other for row in answer.get("pools", [])))
            check("T031 both listings are attempted after an all-provider listing failure",
                  _t031_trace(state) == ([("coingecko", "new"), ("geckoterminal", "new"),
                                         ("coingecko", "trending")] if failed == "new" else
                                        [("coingecko", "new"), ("coingecko", "trending"),
                                         ("geckoterminal", "trending")]))
            _t031_private("T031 partial: ", state, answer, error)
    generic = "GeckoTerminal request failed; could not scan new pools on ethereum"
    cases = [("no safe fetch detail", _t031_reply({}), ""),
             ("HTTP status", _t031_reply({}, 429), "coingecko 429, geckoterminal 429"),
             ("numeric API code", _t031_reply({"error_code": 10010}, 401),
              "coingecko 401 (10010), geckoterminal 401 (10010)"),
             ("error body", _t031_reply({"status": {"error_code": 429}}),
              "coingecko error body 429, geckoterminal error body 429"),
             ("invalid JSON", (200, "raw private HTML {"),
              "coingecko JSONDecodeError, geckoterminal JSONDecodeError"),
             ("transport", OSError("raw private URL https://private.invalid/"),
              "coingecko OSError, geckoterminal OSError"),
             ("hostile error text", _t031_reply({"status": {
                 "error_code": "t031-synthetic-header-only-credential https://private.invalid/"}}), "")]
    for label, response, detail in cases:
        outcomes = {(provider, kind): response for provider in ("coingecko", "geckoterminal")
                    for kind in ("new", "trending")}
        answer, error, state = _t031_scan(outcomes)
        check("T031 %s keeps RuntimeError with only known safe provider detail" % label,
              isinstance(error, RuntimeError) and str(error) == generic + (" (%s)" % detail if detail else ""))
        check("T031 all-source failure never exposes raw bodies, exception messages or URLs",
              "private" not in str(error) and "http" not in str(error))
        _t031_private("T031 total failure: ", state, answer, error)


def test_t031_real_cache_policy_and_disclosure_survive_provider_failover():
    print("\n[T-031] actual cache freshness and stale disclosures survive the route")
    for provider in ("coingecko", "geckoterminal"):
        for age in (20, 321):
            cache = {(provider, kind): ({"data": [_t031_pool(suffix)]}, age)
                     for kind, suffix in (("new", "1"), ("trending", "2"))}
            outcomes = {(name, kind): _t031_reply({}, 429)
                        for name in ("coingecko", "geckoterminal") for kind in ("new", "trending")}
            answer, error, state = _t031_scan(outcomes, cache=cache)
            check("T031 usable cached listing prevents redundant provider reads", error is None
                  and answer.get("status") == "ok" and answer.get("count") == 2
                  and len(state["requests"]) == (0 if age == 20 else 2)
                  + (2 if provider == "geckoterminal" else 0))
            expected = [{"source": "api.%s.com" % provider, "age_seconds": age}] * 2
            check("T031 only stale cache gets its original provider and age disclosure",
                  answer.get("served_stale") == expected if age == 321 else "served_stale" not in answer)
            _t031_private("T031 cache: ", state, answer, error)
    expired = {("coingecko", kind): ({"data": [_t031_pool("1")]}, 901)
               for kind in ("new", "trending")}
    outcomes = {("coingecko", kind): _t031_reply({}, 429) for kind in ("new", "trending")}
    answer, error, state = _t031_scan(outcomes, cache=expired)
    check("T031 expired cache is discarded before keyless observed empty fallback", error is None
          and answer.get("status") == "ok" and answer.get("pools") == []
          and "served_stale" not in answer and len(state["requests"]) == 4)


def test_t031_real_http_and_mcp_keep_provider_keys_out_of_public_surfaces():
    print("\n[T-031] real HTTP/MCP route through actual fetch with private header auth")
    for interface in ("http", "mcp"):
        for mode in ("complete", "partial empty", "failure"):
            outcomes = {(provider, kind): _t031_reply({}, 429)
                        for provider in ("coingecko", "geckoterminal") for kind in ("new", "trending")}
            if mode != "failure":
                outcomes[("coingecko", "new")] = _t031_reply(
                    {"data": [_t031_pool("1", "solana")] if mode == "complete" else []})
            if mode == "complete":
                outcomes[("geckoterminal", "trending")] = _t031_reply({"data": []})
            with _t031_runtime(outcomes) as (runtime, state, env):
                body = {"jsonrpc": "2.0", "id": 31, "method": "tools/call",
                        "params": {"name": "find_new_hot_pools", "arguments": {"chain": "solana", "limit": 1}}}

                class Request(runtime.FakeRequest):
                    async def json(self):
                        return body

                request = Request("https://offline.invalid" + (
                    "/mcp" if interface == "mcp" else "/new-pools?chain=solana&limit=1"),
                    method="POST" if interface == "mcp" else "GET",
                    headers={"x-mcp-client": "vetagent-manual-probe"})
                worker = runtime.entry.Default()
                worker.env = env
                response = asyncio.run(worker.fetch(request))
                answer = json.loads(response.body)
            result = answer.get("result", {}) if interface == "mcp" else answer
            data = result.get("structuredContent", {}) if interface == "mcp" else result
            expected = {"complete": "ok", "partial empty": "partial", "failure": ""}[mode]
            tag = "T031 %s %s: " % (interface, mode)
            if expected:
                check(tag + "real response preserves listing status", response.status == 200
                      and data.get("status") == expected and not result.get("isError"))
                check(tag + "Solana token survives discovery handoff", mode != "complete"
                      or (data.get("pools") or [{}])[0].get("token_address") == "1" * 44)
                if interface == "mcp":
                    check(tag + "structured and text payloads match",
                          not result.get("isError") and data == json.loads(
                              result.get("content", [{}])[0].get("text", "null")))
            elif interface == "mcp":
                check(tag + "real tool error retains safe provider status", response.status == 200
                      and result.get("isError") is True and "structuredContent" not in result
                      and "(coingecko 429, geckoterminal 429)" in result.get("content", [{}])[0].get("text", ""))
            else:
                check(tag + "real HTTP error retains safe provider status", response.status == 500
                      and answer.get("error") == "internal_error"
                      and answer.get("detail", "").endswith("(coingecko 429, geckoterminal 429)"))
            check(tag + "telemetry keeps prospective completeness with no listing data",
                  state["recorded"] == [(["tools/call" if interface == "mcp" else "http",
                                           "find_new_hot_pools", expected, "vetagent-manual-probe", "??", ""],
                                          [1.0, 0.0 if expected else 1.0])])
            _t031_private(tag, state, answer)


def test_t031_limits_validation_and_network_block_are_preserved():
    print("\n[T-031] input limits and the acceptance network guard are real")
    outcomes = {("coingecko", "new"): _t031_reply({"data": [{"id": "pool%d" % i} for i in range(55)]})}
    for limit, expected in ((-1, 1), ("100", 50), (2, 2)):
        answer, error, state = _t031_scan(outcomes, args=(" BASE ", limit))
        check("T031 original limits and chain normalization survive provider preference",
              error is None and answer.get("count") == expected and answer.get("scanned") == 55
              and answer.get("chain") == answer.get("network") == "base"
              and [row["pool_id"] for row in answer.get("pools", [])] == ["pool%d" % i for i in range(expected)])
        _t031_private("T031 limits: ", state, answer, error)
    for args in (("invalid/chain", 1), ("ethereum", "invalid"), ("ethereum", None)):
        _, error, state = _t031_scan({}, args=args)
        check("T031 invalid input still fails before any provider/cache access", isinstance(error, ValueError)
              and not state["requests"] and not state["cache_reads"])
    with _t031_runtime({}) as (_, state, _):
        try:
            socket.create_connection(("blocked.invalid", 443))
        except AssertionError:
            pass
    check("T031 external networking guard is observed failing", state["blocked"] == ["external network blocked"])


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
