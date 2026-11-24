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
                    best = evidence.get("best_pair") or {}
                    check(tag + "complete pool identity coexists with the compact display contract",
                          best.get("pool_id") == pool and
                          (best.get("pair_address") == pool[:48] + "..." if extra["verbose"] else "pair_address" not in best),
                          str(best))
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
                           "assessment_args": {"address": "0x" + "1" * 40, "chain_hint": "ethereum"},
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


# T-070 acceptance contract: additions only; original tests stay exact.
@contextmanager
def _a2_no_effects():
    import subprocess
    import time
    import urllib.request
    def blocked(*args, **kwargs):
        raise AssertionError("T070_effect_boundary_invoked")
    with patch.object(socket, "socket", blocked), patch.object(socket, "create_connection", blocked), \
            patch.object(subprocess, "run", blocked), patch.object(subprocess, "Popen", blocked), \
            patch.object(urllib.request, "urlopen", blocked), patch.object(urllib.request.OpenerDirector, "open", blocked), \
            patch.object(time, "sleep", blocked):
        yield


def _a2_module():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "examples" / "assessment_policy.py"
    check("T070 assessment policy example exists", path.is_file())
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("t070_policy_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    with _a2_no_effects():
        spec.loader.exec_module(module)
    return module


def _a2_call(function, *args, **kwargs):
    with _a2_no_effects():
        return function(*args, **kwargs)


def _a2_expected(action, reason, delay=None):
    return {"action": action, "reason": reason, "retry_after_seconds": delay}


def _a2_envelope(payload):
    return {"jsonrpc": "2.0", "id": 70, "result": {"structuredContent": payload}}


def _a2_cli(raw, arguments):
    import subprocess
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "examples" / "assessment_policy.py"
    bootstrap = "\n".join([
        "import runpy,sys,socket,subprocess,time,urllib.request",
        "def blocked(*a,**k): raise AssertionError('T070_effect_boundary_invoked')",
        "socket.socket=blocked", "socket.create_connection=blocked",
        "subprocess.run=blocked", "subprocess.Popen=blocked", "time.sleep=blocked",
        "urllib.request.urlopen=blocked", "urllib.request.OpenerDirector.open=blocked",
        "sys.argv=sys.argv[1:]", "from pathlib import Path",
        "sys.path.insert(0,str(Path(sys.argv[0]).parent))",
        "runpy.run_path(sys.argv[0],run_name='__main__')"])
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLOUDFLARE_API_TOKEN="T070-PRIVATE-TOKEN",
               CLOUDFLARE_ACCOUNT_ID="T070-PRIVATE-ACCOUNT", GITHUB_TOKEN="T070-PRIVATE-GH")
    return subprocess.run([sys.executable, "-B", "-c", bootstrap, str(path), *arguments],
                          input=raw, capture_output=True, env=env, timeout=20)


def test_a2_policy_http_and_mcp_actions():
    module = _a2_module()
    if module is None:
        return
    cases = [({"risk_level": "high", "risk_score": 0}, _a2_expected("reject", "high_risk")),
             ({"risk_level": "medium"}, _a2_expected("manual_review", "risk_requires_review")),
             ({"risk_level": "low", "risk_score": {"malformed": "unused"}},
              _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal")),
             ({"risk_level": "unknown", "unknown_kind": "infrastructure", "next_action": "retry",
               "retry_after_seconds": 30}, _a2_expected("retry", "infrastructure_retry_advised", 30)),
             ({"risk_level": "unknown", "unknown_kind": "coverage", "risk_score": 0,
               "next_action": "retry", "retry_after_seconds": 1},
              _a2_expected("abstain", "coverage_requires_abstention"))]
    for payload, expected in cases:
        before = copy.deepcopy(payload)
        for transport, value in ((module.route_http, payload), (module.route_mcp, _a2_envelope(payload))):
            result = _a2_call(transport, value)
            check("T070 exact action/reason/delay contract", result == expected, str(result))
            check("T070 response has only the three policy fields", set(result) == {"action", "reason", "retry_after_seconds"})
        check("T070 response routing does not mutate inputs", payload == before)


def test_a2_policy_unknown_retry_or_abstain():
    module = _a2_module()
    if module is None:
        return
    for kind in ("infrastructure", "mixed"):
        for delay in (1, 2147483647):
            payload = {"risk_level": "unknown", "risk_score": 0, "unknown_kind": kind,
                       "next_action": "retry", "retry_after_seconds": delay}
            expected = _a2_expected("retry", "infrastructure_retry_advised", delay)
            check("T070 strict valid retry is advice only", _a2_call(module.route_http, payload) == expected
                  and _a2_call(module.route_mcp, _a2_envelope(payload)) == expected)
        for delay in (None, -1, 0, True, False, 1.0, 1.5, "30", 2147483648, [], {}, float("nan"), float("inf")):
            payload = {"risk_level": "unknown", "risk_score": 100, "unknown_kind": kind,
                       "next_action": "retry", "retry_after_seconds": delay}
            expected = _a2_expected("abstain", "retry_guidance_invalid")
            check("T070 invalid delays do not coerce into retries", _a2_call(module.route_http, payload) == expected
                  and _a2_call(module.route_mcp, _a2_envelope(payload)) == expected)
        for changes in ({"next_action": "abstain"}, {"next_action": "Retry"}, {"next_action": None}):
            payload = dict(risk_level="unknown", unknown_kind=kind, next_action="retry", retry_after_seconds=30)
            payload.update(changes)
            check("T070 contradictory retry guidance abstains", _a2_call(module.route_http, payload)
                  == _a2_expected("abstain", "retry_guidance_invalid"))
        for missing in ("next_action", "retry_after_seconds"):
            payload = dict(risk_level="unknown", unknown_kind=kind, next_action="retry", retry_after_seconds=30)
            payload.pop(missing)
            check("T070 incomplete retry guidance abstains", _a2_call(module.route_mcp, _a2_envelope(payload))
                  == _a2_expected("abstain", "retry_guidance_invalid"))
    for kind in (None, "", "Infrastructure", "T070-PRIVATE-KIND", [], {}, True):
        payload = dict(risk_level="unknown", risk_score=0, unknown_kind=kind, next_action="retry", retry_after_seconds=30)
        check("T070 missing kind overrides even a low score", _a2_call(module.route_http, payload)
              == _a2_expected("abstain", "unknown_kind_unavailable"))
    for score in (0, 100, None, [], "T070-PRIVATE-SCORE"):
        payload = dict(risk_level="unknown", risk_score=score, unknown_kind="coverage", next_action="retry", retry_after_seconds=True)
        expected = _a2_expected("abstain", "coverage_requires_abstention")
        check("T070 coverage overrides score and bad retry claim", _a2_call(module.route_http, payload) == expected
              and _a2_call(module.route_mcp, _a2_envelope(payload)) == expected)


def test_a2_policy_envelope_errors():
    module = _a2_module()
    if module is None:
        return
    invalid = _a2_expected("abstain", "invalid_envelope")
    invalid_verdict = _a2_expected("abstain", "invalid_verdict")
    low = {"risk_level": "low"}
    for status in (None, True, False, 200.0, "200", 201, 429, 500):
        check("T070 exact HTTP200 status required", _a2_call(module.route_http, low, status) == invalid
              and _a2_call(module.route_mcp, _a2_envelope(low), status) == invalid)
    for value in (None, [], True, 42, "T070-PRIVATE-ENVELOPE"):
        check("T070 non-object HTTP/MCP envelopes abstain", _a2_call(module.route_http, value) == invalid
              and _a2_call(module.route_mcp, value) == invalid)
    for error in (None, False, 0, "", {}, []):
        check("T070 present HTTP error beats a low verdict even when null", _a2_call(module.route_http, dict(low, error=error)) == invalid)
        envelope = _a2_envelope(low)
        envelope["error"] = error
        check("T070 present MCP top-level error beats structured low", _a2_call(module.route_mcp, envelope) == invalid)
    for flag in (None, True, 0, 1, "false", [], {}):
        envelope = _a2_envelope(low)
        envelope["result"]["isError"] = flag
        check("T070 present MCP isError must be exactly false", _a2_call(module.route_mcp, envelope) == invalid)
    success = _a2_envelope(low)
    success["result"]["isError"] = False
    check("T070 exact false isError permits success", _a2_call(module.route_mcp, success)
          == _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal"))
    for envelope in ({}, {"result": None}, {"result": []}, {"result": {"structuredContent": []}},
                     {"result": {"structuredContent": "T070-PRIVATE-TEXT"}},
                     {"result": {"content": [{"type": "text", "text": '{"risk_level":"low"}'}]}},
                     [_a2_envelope(low)]):
        check("T070 malformed/batch/text-only MCP never becomes a verdict", _a2_call(module.route_mcp, envelope) == invalid)
    for verdict in (None, "Low", "", "T070-PRIVATE-VERDICT", True, 0, [], {}):
        payload = {"risk_level": verdict}
        check("T070 unsupported verdicts abstain", _a2_call(module.route_http, payload) == invalid_verdict
              and _a2_call(module.route_mcp, _a2_envelope(payload)) == invalid_verdict)
    check("T070 absent verdict is not low", _a2_call(module.route_http, {}) == invalid_verdict
          and _a2_call(module.route_mcp, _a2_envelope({})) == invalid_verdict)


def test_a2_policy_private_data_and_no_network():
    module = _a2_module()
    if module is None:
        return
    secret = "T070-PRIVATE-IDENTITY@example.invalid"
    address = "0x" + "1" * 40
    payload = {"risk_level": "low", "address": address, "signals": [{"message": secret}],
               "risk_score": {"unused": secret}, "url": "https://example.invalid/" + secret,
               "checked_at": secret, "evidence": {"raw": secret}}
    expected = _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal")
    check("T070 unused private assessment fields are ignored safely", _a2_call(module.route_http, payload) == expected
          and _a2_call(module.route_mcp, _a2_envelope(payload)) == expected)
    for transport, value in (("http", payload), ("mcp", _a2_envelope(payload)),
                             ("http", {"error": secret, "risk_level": "low"}),
                             ("mcp", {"error": secret, "result": {"structuredContent": payload}})):
        run = _a2_cli(json.dumps(value).encode("utf-8"), ["--transport", transport])
        text = (run.stdout + run.stderr).decode("utf-8")
        check("T070 real child emits no identity/address/URL/credential text", run.returncode == 0
              and all(s not in text for s in (secret, address, "https://example.invalid", "T070-PRIVATE-TOKEN",
                                               "T070-PRIVATE-ACCOUNT", "T070-PRIVATE-GH")))
        check("T070 child performed no forbidden effect", run.stderr == b""
              and "T070_effect_boundary_invoked" not in text and "Traceback" not in text)
    for arguments in ([], ["--transport", "T070-PRIVATE-TRANSPORT"], ["--T070-PRIVATE-ARG"], ["--trans", "http"]):
        run = _a2_cli(b"", arguments)
        text = (run.stdout + run.stderr).decode("utf-8")
        check("T070 default and bad arguments fail without reflection", run.returncode != 0
              and "T070-PRIVATE" not in text and "Traceback" not in text)


def test_a2_policy_real_cli():
    from pathlib import Path
    module = _a2_module()
    if module is None:
        return
    cases = [("http", {"risk_level": "medium"}, _a2_expected("manual_review", "risk_requires_review")),
             ("mcp", _a2_envelope(dict(risk_level="unknown", unknown_kind="mixed", next_action="retry", retry_after_seconds=7)),
              _a2_expected("retry", "infrastructure_retry_advised", 7)),
             ("http", [], _a2_expected("abstain", "invalid_envelope")),
             ("mcp", _a2_envelope({}), _a2_expected("abstain", "invalid_verdict"))]
    for transport, value, expected in cases:
        run = _a2_cli(json.dumps(value).encode("utf-8"), ["--transport", transport])
        check("T070 real stdin CLI agrees with the exact policy", run.returncode == 0
              and json.loads(run.stdout) == expected and run.stderr == b"")
    valid = b'{"risk_level":"low"}'
    at_limit = valid + b" " * (1024 * 1024 - len(valid))
    boundary = _a2_cli(at_limit, ["--transport", "http"])
    check("T070 byte cap admits its exact valid boundary", boundary.returncode == 0
          and json.loads(boundary.stdout) == _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal"))
    valid_non_object = _a2_cli(b"[" * 32 + b"]" * 32, ["--transport", "http"])
    check("T070 valid JSON non-object yields envelope abstention", valid_non_object.returncode == 0
          and json.loads(valid_non_object.stdout) == _a2_expected("abstain", "invalid_envelope")
          and valid_non_object.stderr == b"")
    invalids = [b"", b"{bad", b"\xff", b'{"risk_level":"low","risk_level":"high"}',
                b'{"risk_level":"low","unused":{"x":1,"x":2}}', b"[" * 1100,
                at_limit + b" ", b'{"risk_level":"low","risk_score":NaN}']
    for raw in invalids:
        run = _a2_cli(raw, ["--transport", "http"])
        output = (run.stdout + run.stderr).decode("utf-8")
        check("T070 invalid/duplicate/deep/oversized input has a safe native failure", run.returncode != 0
              and "Traceback" not in output and "risk_level" not in output and "T070-PRIVATE" not in output)
    doc = (Path(__file__).resolve().parents[1] / "docs" / "AGENT-INTEGRATION.md").read_text(encoding="utf-8")
    check("T070 docs contain executable local examples and existing time context", all(word in doc for word in
          ("examples/assessment_policy.py", "--transport http", "--transport mcp", "checked_at", "evidence_max_age_seconds")))


# T-082 acceptance contract: the real CLI must preserve transport status.
def test_a4_cli_http_status_handoff():
    module = _a2_module()
    if module is None:
        return
    payloads = ({"risk_level": "low", "unused": "T082-PRIVATE-BODY"},
                {"risk_level": "unknown", "unknown_kind": "infrastructure",
                 "next_action": "retry", "retry_after_seconds": 30})
    for transport, route in (("http", module.route_http), ("mcp", module.route_mcp)):
        for payload in payloads:
            value = payload if transport == "http" else _a2_envelope(payload)
            raw = json.dumps(value).encode("utf-8")
            default = _a2_cli(raw, ["--transport", transport])
            check("T082 default CLI status remains compatible", default.returncode == 0
                  and json.loads(default.stdout) == _a2_call(route, value, 200)
                  and default.stderr == b"")
            for status in (100, 200, 201, 204, 400, 429, 503, 599):
                run = _a2_cli(raw, ["--transport", transport, "--http-status", str(status)])
                expected = _a2_call(route, value, status)
                check("T082 actual CLI carries status to existing %s router %d" % (transport, status),
                      run.returncode == 0 and json.loads(run.stdout) == expected and run.stderr == b"")
                check("T082 status routing reveals no body or environment values",
                      b"T082-PRIVATE" not in run.stdout + run.stderr
                      and b"T070-PRIVATE" not in run.stdout + run.stderr)
                if status != 200:
                    check("T082 non-200 transport never grants continuation or retry",
                          run.returncode == 0 and json.loads(run.stdout)
                          == _a2_expected("abstain", "invalid_envelope"))
    for raw in (b'{"risk_level":"low","risk_level":"high"}', b" " * (1024 * 1024 + 1)):
        run = _a2_cli(raw, ["--transport", "http", "--http-status", "200"])
        check("T082 explicit status preserves duplicate and byte-cap refusal",
              run.returncode != 0 and json.loads(run.stdout) == {"error": "input_refused"}
              and run.stderr == b"")


def test_a4_cli_http_status_invalid_arguments():
    invalid = ("", "99", "099", "600", "999", "0200", "2000", "+200", "-200",
               "200.0", "2e2", "0xC8", " 200", "200 ", "True", "T082-PRIVATE-STATUS",
               "\u0662\u0660\u0660", "\uff12\uff10\uff10")
    for transport in ("http", "mcp"):
        for status in (*invalid, None):
            args = ["--transport", transport, "--http-status"]
            if status is not None:
                args.append(status)
            run = _a2_cli(b'{"risk_level":"low","unused":"T082-PRIVATE-BODY"}', args)
            check("T082 malformed or missing status fails with a fixed private-safe diagnostic",
                  run.returncode != 0 and json.loads(run.stdout) == {"error": "arguments_refused"}
                  and run.stderr == b"")


def _retry_context_call(route, payload, attempted, http_status=200):
    try:
        return _a2_call(route, payload, http_status, retry_attempted=attempted)
    except TypeError:
        check("retry context keyword is supported without an exception", False)
        return None


def test_bounded_retry_context_signature_and_positional_status():
    import inspect
    module = _a2_module()
    for route, payload in ((module.route_http, {"risk_level": "low"}),
                           (module.route_mcp, _a2_envelope({"risk_level": "low"}))):
        params = inspect.signature(route).parameters
        context = params.get("retry_attempted")
        check("retry history is optional and keyword-only",
              context is not None and context.kind == inspect.Parameter.KEYWORD_ONLY
              and context.default is False)
        for status in (200, 429):
            original = _a2_call(route, payload, status)
            check("positional HTTP status retains the existing result",
                  original == (_a2_expected("continue_evaluation", "checks_ran_without_fatal_signal")
                               if status == 200 else _a2_expected("abstain", "invalid_envelope")))
            check("explicit false context preserves positional status behavior",
                  _retry_context_call(route, payload, False, status) == original)
        try:
            _a2_call(route, payload, 200, True)
        except TypeError:
            check("retry context cannot be passed positionally", True)
        else:
            check("retry context cannot be passed positionally", False)


def test_bounded_retry_context_only_changes_advised_retry():
    import copy
    module = _a2_module()
    cases = [
        ({"risk_level": "high"}, _a2_expected("reject", "high_risk")),
        ({"risk_level": "medium"}, _a2_expected("manual_review", "risk_requires_review")),
        ({"risk_level": "low"}, _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal")),
        ({"risk_level": "invalid"}, _a2_expected("abstain", "invalid_verdict")),
        ({"risk_level": "unknown"}, _a2_expected("abstain", "unknown_kind_unavailable")),
        ({"risk_level": "unknown", "unknown_kind": "coverage", "next_action": "retry",
          "retry_after_seconds": 60}, _a2_expected("abstain", "coverage_requires_abstention")),
    ]
    for kind in ("infrastructure", "mixed"):
        unknown = dict(risk_level="unknown", unknown_kind=kind, next_action="retry", retry_after_seconds=60)
        cases.append((unknown, _a2_expected("retry", "infrastructure_retry_advised", 60)))
        for change in ({"next_action": "abstain"}, {"retry_after_seconds": True},
                       {"retry_after_seconds": None}):
            cases.append((dict(unknown, **change), _a2_expected("abstain", "retry_guidance_invalid")))
    for route, wrap in ((module.route_http, lambda value: value), (module.route_mcp, _a2_envelope)):
        for payload, expected in cases:
            for attempted in (False, True):
                supplied = wrap(copy.deepcopy(payload))
                saved = copy.deepcopy(supplied)
                actual = _retry_context_call(route, supplied, attempted)
                final = (_a2_expected("abstain", "retry_budget_exhausted")
                         if attempted and expected["action"] == "retry" else expected)
                check("only an already-advised retry can exhaust the caller budget", actual == final)
                check("retry context leaves caller response data untouched", supplied == saved)
                check("retry context returns only the existing three fields",
                      isinstance(actual, dict) and set(actual) == {"action", "reason", "retry_after_seconds"})


def test_bounded_retry_context_is_strict_caller_owned_and_error_subordinate():
    module = _a2_module()
    unknown = dict(risk_level="unknown", unknown_kind="infrastructure", next_action="retry",
                   retry_after_seconds=60, unused="RETRY-PRIVATE-BODY")
    for route, wrap in ((module.route_http, lambda value: value), (module.route_mcp, _a2_envelope)):
        for bad in (0, 1, -1, 0.0, 1.0, "true", "false", "RETRY-PRIVATE-CONTEXT", None, [], {}):
            result = _retry_context_call(route, wrap(dict(unknown)), bad)
            check("non-boolean retry context fails closed with a fixed reason",
                  result == _a2_expected("abstain", "invalid_retry_context"))
            check("invalid context never echoes caller data", "RETRY-PRIVATE" not in json.dumps(result))
            check("transport refusal precedes invalid retry context",
                  _retry_context_call(route, wrap(dict(unknown)), bad, 429)
                  == _a2_expected("abstain", "invalid_envelope"))
        for claimed in (False, True, None, "RETRY-PRIVATE-HISTORY"):
            payload = wrap(dict(unknown, retry_attempted=claimed))
            check("payload cannot self-report an exhausted caller budget",
                  _a2_call(route, payload) == _a2_expected("retry", "infrastructure_retry_advised", 60))
            check("payload cannot override a caller's exhausted budget",
                  _retry_context_call(route, payload, True)
                  == _a2_expected("abstain", "retry_budget_exhausted"))
        check("invalid context precedes verdict parsing inside a valid envelope",
              _retry_context_call(route, wrap({"risk_level": "invalid"}), 1)
              == _a2_expected("abstain", "invalid_retry_context"))
    bad_http = (None, [], {"risk_level": "low", "error": None})
    bad_mcp = (None, [], {"error": None, "result": {"structuredContent": unknown}},
               {"result": {"isError": True, "structuredContent": unknown}},
               {"result": {"structuredContent": []}})
    for route, values in ((module.route_http, bad_http), (module.route_mcp, bad_mcp)):
        for value in values:
            for attempted in (False, True, "RETRY-PRIVATE-CONTEXT"):
                check("all existing envelope errors beat retry context validation",
                      _retry_context_call(route, value, attempted)
                      == _a2_expected("abstain", "invalid_envelope"))


def test_bounded_retry_context_real_cli_handoff():
    retry = dict(risk_level="unknown", unknown_kind="mixed", next_action="retry", retry_after_seconds=60,
                 retry_attempted=False, unused="RETRY-PRIVATE-INPUT")
    for transport, wrap in (("http", lambda value: value), ("mcp", _a2_envelope)):
        for payload, expected in (
                (retry, _a2_expected("abstain", "retry_budget_exhausted")),
                ({"risk_level": "low"}, _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal")),
                ({"risk_level": "medium"}, _a2_expected("manual_review", "risk_requires_review")),
                ({"risk_level": "high"}, _a2_expected("reject", "high_risk"))):
            raw = json.dumps(wrap(payload)).encode()
            run = _a2_cli(raw, ["--transport", transport, "--http-status", "200", "--retry-attempted"])
            check("actual CLI uses context without overriding a completed response",
                  run.returncode == 0 and json.loads(run.stdout) == expected and run.stderr == b"")
            check("context CLI keeps response and environment values private",
                  b"RETRY-PRIVATE" not in run.stdout + run.stderr and b"T070-PRIVATE" not in run.stdout + run.stderr)
        raw = json.dumps(wrap(retry)).encode()
        first = _a2_cli(raw, ["--transport", transport])
        check("omitting the CLI flag still allows the first advised retry",
              first.returncode == 0 and json.loads(first.stdout)
              == _a2_expected("retry", "infrastructure_retry_advised", 60))
        refused = _a2_cli(raw, ["--transport", transport, "--retry-attempted", "--http-status", "429"])
        check("new CLI flag still carries actual transport refusal first",
              refused.returncode == 0 and json.loads(refused.stdout) == _a2_expected("abstain", "invalid_envelope"))
        bad_arg = _a2_cli(raw, ["--transport", transport, "--retry-attempted=RETRY-PRIVATE-ARG"])
        check("retry flag does not accept a value or echo malformed arguments",
              bad_arg.returncode == 2 and json.loads(bad_arg.stdout) == {"error": "arguments_refused"}
              and bad_arg.stderr == b"")
        for malformed in (b"{", b'{"risk_level":"low","risk_level":"high"}'):
            bad_input = _a2_cli(malformed, ["--transport", transport, "--retry-attempted"])
            check("retry flag preserves fixed JSON input refusals",
                  bad_input.returncode == 1 and json.loads(bad_input.stdout) == {"error": "input_refused"}
                  and bad_input.stderr == b"")


def test_permission_contract_is_discoverable_without_requiring_an_observation():
    print("\n[permission contract] optional evidence and observation limits")
    tools = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    schema = next(t["outputSchema"] for t in tools if t["name"] == "assess_token_risk")
    evidence = schema["properties"]["evidence"]
    owner = evidence.get("properties", {}).get("owner_powers", {})
    props = owner.get("properties", {})
    expected = {"evidence_basis": "string", "matched_selectors": "object",
                "current_authority": "string", "powers": "array", "found_none": "boolean",
                "scan_is_incomplete": "boolean", "is_proxy": "boolean",
                "selectors_dispatched": "integer", "bytecode_bytes": "integer",
                "unavailable": "string"}
    check("tools/list declares the existing owner evidence object", owner.get("type") == "object")
    for field, kind in expected.items():
        check("tools/list declares owner field " + field, props.get(field, {}).get("type") == kind)
    check("assessment keeps its original required fields",
          schema.get("required") == ["address", "risk_level", "risk_score", "confidence", "signals"])
    check("owner evidence is optional and other evidence remains open",
          "owner_powers" not in evidence.get("required", [])
          and evidence.get("additionalProperties", True) is not False)
    check("failed or absent observations need no success fields", not owner.get("required"))
    selectors = props.get("matched_selectors", {}).get("additionalProperties", {})
    check("selector labels are open and values are unique eight-hex strings",
          selectors.get("type") == "array" and selectors.get("uniqueItems") is True
          and selectors.get("items", {}).get("type") == "string"
          and selectors.get("items", {}).get("pattern") == "^[0-9a-f]{8}$"
          and "maxItems" not in selectors and "maxProperties" not in props.get("matched_selectors", {})
          and "enum" not in props.get("matched_selectors", {}).get("propertyNames", {}))
    check("legacy powers are strings", props.get("powers", {}).get("items") == {"type": "string"})
    check("only the existing basis and unobserved authority are advertised",
          props.get("evidence_basis", {}).get("enum") == ["bytecode_selector_match"]
          and props.get("current_authority", {}).get("enum") == ["not_checked"])
    for field, phrases in {
        "evidence_basis": ("code indicators", "not verified callable", "present control"),
        "powers": ("legacy", "not", "current"),
        "current_authority": ("authority", "activation", "reachability", "not observed"),
        "found_none": ("incomplete", "no mapped selector", "not prove"),
        "is_proxy": ("wrapper", "implementation"),
        "unavailable": ("failed", "not", "no-match"),
    }.items():
        description = props.get(field, {}).get("description", "").lower()
        check("discovery explains the limits of " + field, all(p in description for p in phrases))


async def _permission_contract_solana(verbose):
    """Exercise the real non-EVM MCP path with the existing BONK snapshots."""
    requests = []
    market = _load("ds_bonk.json")
    address = market["pairs"][0]["baseToken"]["address"]

    def denied(*args, **kwargs):
        raise AssertionError("permission contract fixtures forbid network access")

    async def upstream(url, *args, **kwargs):
        if "/dex/tokens/" in url:
            requests.append("market")
            return copy.deepcopy(market)
        if "/dex/search" in url:
            requests.append("search")
            return {"pairs": []}
        if "api.rugcheck.xyz" in url:
            requests.append("rugcheck")
            return _load("rc_bonk.json")
        return denied()

    with patch.object(socket.socket, "connect", denied), \
            patch.object(socket, "getaddrinfo", denied), \
            patch.object(risk, "cf_fetch", denied), \
            patch.object(risk, "_fetch_json", upstream):
        envelope = await mcp_server.handle_mcp_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "assess_token_risk", "arguments": {
                "address": address, "chain_hint": "solana", "verbose": verbose}},
        })
    result = envelope["result"]["structuredContent"]
    assert json.loads(envelope["result"]["content"][0]["text"]) == result
    return result, requests


def test_permission_contract_matches_normal_mcp_assessment_handoff():
    print("\n[permission contract] compact, verbose, failed and non-EVM handoff")
    spec = importlib.util.spec_from_file_location(
        "permission_contract_fixtures", os.path.join(os.path.dirname(__file__), "test_owner_powers.py"))
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    schema = next(t["outputSchema"] for t in call({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list"
    })["result"]["tools"] if t["name"] == "assess_token_risk")
    props = schema["properties"]["evidence"].get("properties", {}).get("owner_powers", {}).get("properties", {})
    cases = [
        ("match", {"result": "0x63d539139300"}),
        ("no-match", {"result": "0x6318160ddd00"}),
        ("proxy-match", {"result": "0x635c60da1b63d539139300"}),
        ("unavailable", {"error": {"code": -32000, "message": "synthetic RPC failure"}}),
    ]
    clock = risk._BENCH_NOW.set(datetime(2026, 11, 15, tzinfo=timezone.utc))
    try:
        for name, reply in cases:
            compact = None
            for verbose in (False, True):
                result, requests, _ = asyncio.run(fixtures._permission_assessment(reply, verbose=verbose, mcp=True))
                owner = result["evidence"]["owner_powers"]
                prefix = name + (" verbose: " if verbose else " compact: ")
                check(prefix + "actual output fields are discoverable", set(owner) <= set(props))
                check(prefix + "existing request budget is unchanged",
                      requests == ["market", "search", "bytecode", "sell"])
                check(prefix + "authority remains explicitly unobserved", owner.get("current_authority") == "not_checked")
                check(prefix + "existing decision and informational score remain unchanged",
                      result["risk_level"] == "low" and result["risk_score"] == (0 if name == "unavailable" else 3))
                if name == "unavailable":
                    check(prefix + "failure is not a completed empty match",
                          owner == {"unavailable": "rpc error response", "current_authority": "not_checked"})
                else:
                    labels = {} if name == "no-match" else {"can mint new supply": ["d5391393"]}
                    check(prefix + "legacy labels and selectors describe the same incomplete observation",
                          owner["matched_selectors"] == labels and owner["powers"] == list(labels)
                          and owner["evidence_basis"] == "bytecode_selector_match"
                          and owner["found_none"] is (name == "no-match")
                          and owner["scan_is_incomplete"] is True
                          and owner["is_proxy"] is (name == "proxy-match")
                          and type(owner["bytecode_bytes"]) is int
                          and type(owner["selectors_dispatched"]) is int)
                if verbose:
                    check(prefix + "permission evidence agrees across output modes", owner == compact)
                else:
                    compact = owner
        for verbose in (False, True):
            result, requests = asyncio.run(_permission_contract_solana(verbose))
            check("non-EVM assessment keeps absent owner evidence valid",
                  "owner_powers" not in result["evidence"]
                  and result["risk_level"] == "unknown" and result["next_action"] == "abstain")
            check("non-EVM assessment keeps its existing request budget",
                  requests == ["market", "search", "rugcheck"])
    finally:
        risk._BENCH_NOW.reset(clock)


def test_discovery_assessment_args_are_optional_and_described():
    tools = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    tool = next(t for t in tools if t["name"] == "find_new_hot_pools")
    row = tool["outputSchema"]["properties"]["pools"]["items"]
    args = row["properties"].get("assessment_args", {})
    check("discovery declares exactly the existing assessment arguments",
          args.get("type") == "object" and set(args.get("properties", {})) == {"address", "chain_hint"}
          and set(args.get("required", [])) == {"address", "chain_hint"}
          and args.get("additionalProperties") is False)
    check("ready arguments remain optional on a discovery row", "assessment_args" not in row.get("required", []))
    description = tool["description"] + " " + args.get("description", "")
    check("handoff instructions preserve context without certifying the discovered pool",
          all(p in description for p in ("assessment_args", "absent", "different primary pool", "not guess")))


def test_discovery_assessment_args_follow_only_supported_selected_networks():
    cases = [("ethereum", "eth", "ethereum"), ("eth", "eth", "ethereum"),
             ("binance", "bsc", "bsc"), ("bsc", "bsc", "bsc"),
             ("matic", "polygon_pos", "polygon"), ("polygon_pos", "polygon_pos", "polygon"),
             ("arbitrum_one", "arbitrum", "arbitrum"), ("optimism", "optimism", "optimism"),
             ("avax", "avax", "avalanche"), ("base", "base", "base"),
             ("solana", "solana", "solana"), ("mainnet", "mainnet", None),
             ("bnb", "bnb", None), ("unlisted", "unlisted", None)]
    solana = _load("ds_bonk.json")["pairs"][0]["baseToken"]["address"]
    for chain, network, canonical in cases:
        token = solana if chain == "solana" else "0x" + "A1" * 20
        valid = _t028_pool("1")
        valid["relationships"]["base_token"]["data"]["id"] = network + "_" + token
        invalid = copy.deepcopy(valid)
        invalid["id"] = "invalid"
        invalid["relationships"]["base_token"]["data"]["id"] = network + "_bad"
        absent = {"id": "absent", "attributes": {"name": token}}
        with patch.dict(risk._ONCHAIN, {"key": None, "unusable": False}), \
                _t028_runtime({"data": [valid, invalid, absent]}, {"data": [copy.deepcopy(valid)]}) as (_, _, seen):
            envelope = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "find_new_hot_pools", "arguments": {"chain": chain, "limit": 3}}})
        result = envelope["result"]["structuredContent"]
        rows = result["pools"]
        expected = {"address": token if chain == "solana" else token.lower(), "chain_hint": canonical}
        check(chain + ": only a known selected network produces callable arguments",
              rows[0].get("assessment_args") == expected if canonical else "assessment_args" not in rows[0])
        check(chain + ": invalid and missing addresses never get ready arguments",
              all("assessment_args" not in row for row in rows[1:]))
        check(chain + ": legacy rows, routing, deduplication and completeness stay intact",
              result["network"] == network and result["chain"] == chain
              and result["status"] == "ok" and result["count"] == result["scanned"] == 3
              and rows[0]["token_address"] == token and rows[1]["token_address"] == "bad"
              and rows[2]["token_address"] == ""
              and [r["pool_id"] for r in rows] == [valid["id"], "invalid", "absent"]
              and [s[0] for s in seen] == ["new", "trending"]
              and all("/networks/" + network + "/" in s[1] for s in seen))


async def _discovery_assessment_handoff():
    address, requests = "0x" + "1" * 40, []
    listing = _t028_pool("1")
    listing["id"] = "base_discovered_pool"
    listing["relationships"]["base_token"]["data"]["id"] = "base_" + address
    pairs = [{"chainId": chain, "dexId": "uniswap", "pairAddress": "0x" + suffix * 40,
              "baseToken": {"address": address, "symbol": "TKN"}, "quoteToken": {"address": "0xq"},
              "priceUsd": "0.05", "liquidity": {"usd": depth}, "volume": {"h24": depth * 0.2},
              "txns": {"h24": {"buys": 300, "sells": 280}}, "pairCreatedAt": 1589841515000}
             for chain, depth, suffix in (("base", 345000, "a"), ("bsc", 364000, "b"))]

    def denied(*args, **kwargs):
        raise AssertionError("discovery handoff must remain offline")

    async def fetch(url, *args, **kwargs):
        if url.endswith(("/new_pools", "/trending_pools")):
            requests.append(url.rsplit("/", 1)[-1])
            return {"data": [copy.deepcopy(listing)]}
        if "/dex/tokens/" in url:
            requests.append("market")
            return {"pairs": copy.deepcopy(pairs)}
        if "/dex/search" in url:
            requests.append("search")
            return {"pairs": []}
        if "api.honeypot.is" in url:
            chain = "base" if url.endswith("chainID=8453") else "bsc" if url.endswith("chainID=56") else "unexpected"
            requests.append("sell:" + chain)
            # Existing snapshots supply mechanics, not identities for these synthetic deployments.
            hp = _load("hp_retail_veryhigh.json" if chain == "base" else "hp_matic.json")
            for key in ("chain", "pair", "pairAddress"):
                hp.pop(key, None)
            hp.get("token", {}).pop("address", None)
            return hp
        denied()

    async def bytecode(url, **kwargs):
        assert json.loads(kwargs["body"])["params"] == [address, "latest"]
        requests.append("rpc:" + next(c for c, rpc in risk._CHAIN_RPC.items() if rpc == url))
        async def text():
            return '{"result":"0x6318160ddd00"}'
        return SimpleNamespace(status=200, text=text)

    async def cache_get(key):
        return None, None

    async def cache_put(*args, **kwargs):
        pass

    async def invoke(name, arguments):
        envelope = await mcp_server.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}})
        data = envelope["result"]["structuredContent"]
        assert json.loads(envelope["result"]["content"][0]["text"]) == data
        return data

    with patch.object(socket.socket, "connect", denied), patch.object(socket, "getaddrinfo", denied), \
            patch.object(risk, "_fetch_json", fetch), patch.object(risk, "cf_fetch", bytecode), \
            patch.object(risk, "_cache_get", cache_get), patch.object(risk, "_cache_put", cache_put), \
            patch.dict(risk._ONCHAIN, {"key": None, "unusable": False}):
        discovery = await invoke("find_new_hot_pools", {"chain": "base", "limit": 1})
        discovery_calls = requests[:]
        args = discovery["pools"][0].get("assessment_args", {"address": address})
        original_args = copy.deepcopy(args)
        answers = []
        # First pass forwards the object unchanged; verbose adds only the existing output option.
        for arguments in (args, {**args, "verbose": True}, {"address": address}):
            requests.clear()
            answers.append((await invoke("assess_token_risk", arguments), requests[:]))
        assert args == original_args
    return discovery, discovery_calls, answers


def test_discovery_assessment_args_preserve_real_mcp_chain_context():
    discovery, calls, answers = asyncio.run(_discovery_assessment_handoff())
    check("discovery does not assess or make extra requests", calls == ["new_pools", "trending_pools"])
    for result, requests in answers[:2]:
        check("ready handoff assesses the discovered Base deployment",
              result["evidence"]["chain_searched"] == discovery["chain"] == "base"
              and result["evidence"]["best_pair"]["chain"] == "base"
              and result["risk_level"] == "medium" and result["risk_score"] == 58)
        check("ready handoff sends actual bytecode and sell checks to Base",
              requests == ["market", "search", "rpc:base", "sell:base"])
    compact, verbose = answers[0][0], answers[1][0]
    check("normal output modes retain the same decision and owner observations",
          all(compact[k] == verbose[k] for k in ("risk_level", "risk_score", "signals"))
          and compact["evidence"]["owner_powers"] == verbose["evidence"]["owner_powers"])
    result, requests = answers[2]
    check("existing unhinted calls still choose the deeper BSC deployment",
          result["evidence"]["chain_searched"] == "bsc" and result["risk_level"] == "low"
          and result["risk_score"] == 3 and requests == ["market", "search", "rpc:bsc", "sell:bsc"])


def test_conditional_holder_disclosure_matches_existing_offline_observations():
    original_load = _load
    for missing in (False, True):
        report = original_load("rc_bonk.json")
        if missing:
            report["topHolders"], report["totalHolders"] = None, 0

        def substituted(name):
            return copy.deepcopy(report) if name == "rc_bonk.json" else original_load(name)

        with patch.object(sys.modules[__name__], "_load", substituted):
            result, requests = asyncio.run(_permission_contract_solana(False))
        signals = [s for s in result["signals"] if s["category"] == "concentration"]
        gaps = [g for g in result["evidence"].get("data_gaps", []) if g.get("dimension") == "concentration"]
        check("holder disclosure follows the list, never inventing a missing observation",
              not signals and bool(gaps) if missing else bool(signals) and not gaps)
        check("Solana still has no sell simulation and stays unknown",
              result["risk_level"] == "unknown" and result["next_action"] == "abstain"
              and requests == ["market", "search", "rugcheck"])
    signals, evidence, gaps = [], {}, []
    risk._rugcheck_signals(original_load("rc_pump_pool_vault.json"), signals, evidence, gaps)
    check("existing identified LP exclusion remains an observation, not a new capability",
          evidence["rugcheck"]["top10_holder_pct"] == 100.0
          and evidence["rugcheck"]["top10_outside_pools_pct"] == 0.07801
          and any(s["category"] == "concentration" and s["severity"] == "ok" for s in signals))


def test_discovery_assessment_args_require_the_selected_address_family():
    solana = _load("ds_bonk.json")["pairs"][0]["baseToken"]["address"]
    evm = "0x" + "1" * 40
    for chain, address, compatible in (("base", evm, True), ("solana", solana, True),
                                        ("base", solana, False), ("solana", evm, False)):
        row = _t028_pool("1")
        row["relationships"]["base_token"]["data"]["id"] = chain + "_" + address
        with patch.dict(risk._ONCHAIN, {"key": None, "unusable": False}), \
                _t028_runtime({"data": [row]}, {"data": []}) as (_, _, requests):
            result = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "find_new_hot_pools", "arguments": {"chain": chain, "limit": 1}}})["result"]["structuredContent"]
        discovered = result["pools"][0]
        check("ready arguments require a chain-compatible address family",
              discovered.get("assessment_args") == {"address": address, "chain_hint": chain}
              if compatible else "assessment_args" not in discovered)
        check("address-family refusal preserves the observed row and request budget",
              discovered["token_address"] == address and result["count"] == result["scanned"] == 1
              and result["status"] == "ok" and [r[0] for r in requests] == ["new", "trending"])


def _expected_chain_call(route, payload, expected, status=200, attempted=False):
    try:
        return _a2_call(route, payload, status, expected_chain=expected, retry_attempted=attempted)
    except TypeError:
        return {"missing_expected_chain_support": True}


def test_expected_chain_context_rejects_unverified_results_without_effects():
    import inspect
    module = _a2_module()
    for route, wrap in ((module.route_http, lambda value: value), (module.route_mcp, _a2_envelope)):
        parameter = inspect.signature(route).parameters.get("expected_chain")
        check("expected chain is optional and keyword-only", parameter is not None
              and parameter.kind == inspect.Parameter.KEYWORD_ONLY and parameter.default is None)
        for chain in sorted(risk._KNOWN_CHAINS):
            payload = {"risk_level": "low", "evidence": {"chain_searched": chain}}
            check("every supported canonical chain can be verified",
                  _expected_chain_call(route, wrap(payload), chain)
                  == _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal"))
        for invalid in ("", "eth", "BASE", "private-chain", 0, True, [], {}):
            payload = wrap({"risk_level": "low", "evidence": {"chain_searched": "base"}})
            check("noncanonical expected context abstains with a fixed private-safe reason",
                  _expected_chain_call(route, payload, invalid) == _a2_expected("abstain", "invalid_expected_chain"))
            check("transport rejection wins over expected-chain validation",
                  _expected_chain_call(route, payload, invalid, 429) == _a2_expected("abstain", "invalid_envelope"))
        for evidence in (None, [], "private-evidence", {}, {"chain_searched": None},
                         {"chain_searched": True}, {"chain_searched": []},
                         {"chain_searched": "eth"}, {"chain_searched": "BASE"},
                         {"chain_searched": "private-observation"}):
            payload = {"risk_level": "low", "evidence": evidence}
            check("missing or invalid observed chain is unavailable, never an implicit match",
                  _expected_chain_call(route, wrap(payload), "base")
                  == _a2_expected("abstain", "chain_context_unavailable"))
        mismatch = {"risk_level": "low", "evidence": {"chain_searched": "bsc"}, "expected_chain": "bsc"}
        check("a different observed chain cannot be used for the caller's target",
              _expected_chain_call(route, wrap(mismatch), "base")
              == _a2_expected("abstain", "assessment_chain_mismatch"))
        for payload in ({"risk_level": "low"}, mismatch, {"risk_level": "high", "evidence": []}):
            check("omitting expected context preserves prior behavior, ignoring payload history",
                  _expected_chain_call(route, wrap(payload), None) == _a2_call(route, wrap(payload)))
        unknown = {"risk_level": "unknown", "unknown_kind": "infrastructure", "next_action": "retry",
                   "retry_after_seconds": 60, "evidence": {"chain_searched": "base"}}
        check("matching context retains the first advised retry",
              _expected_chain_call(route, wrap(unknown), "base")
              == _a2_expected("retry", "infrastructure_retry_advised", 60))
        check("matching context retains the caller-owned retry limit",
              _expected_chain_call(route, wrap(unknown), "base", attempted=True)
              == _a2_expected("abstain", "retry_budget_exhausted"))
        unknown["evidence"]["chain_searched"] = "bsc"
        check("a wrong-chain unknown cannot cause a retry",
              _expected_chain_call(route, wrap(unknown), "base")
              == _a2_expected("abstain", "assessment_chain_mismatch"))
        check("invalid existing retry context keeps its reason",
              _expected_chain_call(route, wrap(unknown), "base", attempted="bad")
              == _a2_expected("abstain", "invalid_retry_context"))
    for route, envelope in ((module.route_http, {"error": None, "risk_level": "low"}),
                            (module.route_mcp, {"error": None}),
                            (module.route_mcp, {"result": {"isError": True}})):
        check("existing error envelopes take priority over both contexts",
              _expected_chain_call(route, envelope, "private-context", attempted="bad")
              == _a2_expected("abstain", "invalid_envelope"))


async def _discovery_handoff_only_other_chain():
    address, requests = "0x" + "1" * 40, []
    row = _t028_pool("1")
    row["relationships"]["base_token"]["data"]["id"] = "base_" + address
    market = {"pairs": [{"chainId": "bsc", "dexId": "uniswap", "pairAddress": "0x" + "b" * 40,
                        "baseToken": {"address": address, "symbol": "TKN"}, "quoteToken": {"address": "0xq"},
                        "priceUsd": "0.05", "liquidity": {"usd": 364000}, "volume": {"h24": 72800},
                        "txns": {"h24": {"buys": 300, "sells": 280}}, "pairCreatedAt": 1589841515000}]}

    def denied(*args, **kwargs):
        raise AssertionError("chain-context fixture forbids network access")

    async def fetch(url, *args, **kwargs):
        if url.endswith(("/new_pools", "/trending_pools")):
            requests.append(url.rsplit("/", 1)[-1])
            return {"data": [copy.deepcopy(row)]}
        if "/dex/tokens/" in url:
            requests.append("market:bsc-only")
            return copy.deepcopy(market)
        if "/token-pairs/v1/base/" in url:
            requests.append("market:requested-base")
            return []
        if "/dex/search" in url:
            requests.append("search")
            return {"pairs": []}
        if "api.honeypot.is" in url:
            assert url.endswith("chainID=56")
            requests.append("sell:bsc")
            hp = _load("hp_matic.json")
            for key in ("chain", "pair", "pairAddress"):
                hp.pop(key, None)
            hp.get("token", {}).pop("address", None)
            return hp
        denied()

    async def bytecode(url, **kwargs):
        assert url == risk._CHAIN_RPC["bsc"] and json.loads(kwargs["body"])["params"] == [address, "latest"]
        requests.append("rpc:bsc")
        async def text():
            return '{"result":"0x6318160ddd00"}'
        return SimpleNamespace(status=200, text=text)

    async def cache_get(key):
        return None, None

    async def cache_put(*args, **kwargs):
        pass

    async def invoke(name, arguments):
        return await mcp_server.handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}})

    with patch.object(socket.socket, "connect", denied), patch.object(socket, "getaddrinfo", denied), \
            patch.object(risk, "_fetch_json", fetch), patch.object(risk, "cf_fetch", bytecode), \
            patch.object(risk, "_cache_get", cache_get), patch.object(risk, "_cache_put", cache_put), \
            patch.dict(risk._ONCHAIN, {"key": None, "unusable": False}):
        discovery = await invoke("find_new_hot_pools", {"chain": "base", "limit": 1})
        args = discovery["result"]["structuredContent"]["pools"][0]["assessment_args"]
        original = copy.deepcopy(args)
        envelope = await invoke("assess_token_risk", args)
        assert args == original
    return args, envelope, requests


def test_expected_chain_guard_consumes_real_mcp_handoffs():
    module = _a2_module()
    discovery, _, answers = asyncio.run(_discovery_assessment_handoff())
    args = discovery["pools"][0]["assessment_args"]
    for result, _ in answers[:2]:
        check("normal compact and verbose Base responses retain manual review",
              _expected_chain_call(module.route_mcp, _a2_envelope(result), args["chain_hint"])
              == _a2_expected("manual_review", "risk_requires_review"))
    args, envelope, requests = asyncio.run(_discovery_handoff_only_other_chain())
    result = envelope["result"]["structuredContent"]
    check("the existing soft hint may still observe only BSC",
          args["chain_hint"] == "base" and result["evidence"]["chain_searched"] == "bsc"
          and result["risk_level"] == "low" and requests == [
              "new_pools", "trending_pools", "market:bsc-only", "market:requested-base",
              "search", "rpc:bsc", "sell:bsc"]
          and result["network_selection"] == {
              "requested_chain": "base", "returned_chain": "bsc", "status": "different", "lookup": "empty"})
    check("the adapter refuses the different chain for the discovered target",
          _expected_chain_call(module.route_mcp, envelope, args["chain_hint"])
          == _a2_expected("abstain", "assessment_chain_mismatch"))
    check("without caller context the old adapter behavior remains unchanged",
          _a2_call(module.route_mcp, envelope) == _a2_expected("continue_evaluation", "checks_ran_without_fatal_signal"))


def test_expected_chain_cli_preserves_routing_and_private_errors():
    for transport, wrap in (("http", lambda value: value), ("mcp", _a2_envelope)):
        for chain, reason in (("base", "checks_ran_without_fatal_signal"),
                              ("bsc", "assessment_chain_mismatch"), (None, "chain_context_unavailable")):
            payload = wrap({"risk_level": "low", "evidence": {"chain_searched": chain}})
            proc = _a2_cli(json.dumps(payload).encode(), ["--transport", transport, "--expected-chain", "base"])
            expected = _a2_expected("continue_evaluation" if chain == "base" else "abstain", reason)
            check("CLI uses the same observed-chain policy", proc.returncode == 0 and proc.stderr == b""
                  and json.loads(proc.stdout) == expected)
        proc = _a2_cli(b'{"risk_level":"low"}', ["--transport", transport, "--expected-chain", "PRIVATE-EXPECTED-CHAIN"])
        check("invalid CLI chain context has a fixed non-echoing policy result",
              proc.returncode == 0 and proc.stderr == b"" and b"PRIVATE-EXPECTED" not in proc.stdout
              and json.loads(proc.stdout) == _a2_expected("abstain", "invalid_expected_chain")
              if transport == "http" else proc.returncode == 0 and proc.stderr == b""
              and json.loads(proc.stdout) == _a2_expected("abstain", "invalid_envelope"))
        missing = _a2_cli(b'{}', ["--transport", transport, "--expected-chain"])
        check("a missing CLI chain value keeps the fixed argument refusal", missing.returncode == 2
              and missing.stderr == b"" and json.loads(missing.stdout) == {"error": "arguments_refused"})


def _t090_route(interface, args, outcomes, key=None):
    from urllib.parse import urlencode

    with _t031_runtime(outcomes, key=key) as (runtime, state, env):
        body = {"jsonrpc": "2.0", "id": 90, "method": "tools/call",
                "params": {"name": "find_new_hot_pools", "arguments": args}}

        class Request(runtime.FakeRequest):
            async def json(self):
                return body

        request = Request("https://offline.invalid" + (
            "/mcp" if interface == "mcp" else "/new-pools?" + urlencode(args)),
            method="POST" if interface == "mcp" else "GET",
            headers={"x-mcp-client": "vetagent-manual-probe"})
        worker = runtime.entry.Default()
        worker.env = env
        response = asyncio.run(worker.fetch(request))
        envelope = json.loads(response.body)
    result = envelope.get("result", {}) if interface == "mcp" else envelope
    data = result.get("structuredContent", {}) if interface == "mcp" else result
    if interface == "mcp" and not result.get("isError"):
        check("T090 MCP text agrees with structured content",
              json.loads(result.get("content", [{}])[0].get("text", "null")) == data)
    check("T090 route stays within local fixture networking", not state["blocked"] and not state["unexpected"])
    return response.status, result, data, state


def test_t099_complete_discovery_ids_cross_real_http_and_mcp():
    """A discovered pool must remain distinguishable from another with the same prefix."""
    solana = "Ab" * 22
    for chain, network, token, ids in (
            ("ethereum", "eth", "0x" + "1" * 40,
             ["eth_0x" + "AB" * 32, "eth_0x" + "AB" * 31 + "AC",
              "0x" + "CD" * 32, "eth_0x" + "EF" * 20, "0x" + "12" * 20]),
            ("base", "base", "0x" + "2" * 40, ["base_0x" + "34" * 32]),
            ("bsc", "bsc", "0x" + "3" * 40, ["bsc_0x" + "56" * 32]),
            ("solana", "solana", solana, ["solana_" + solana, solana])):
        rows = [_t028_pool("1") for _ in ids]
        for row, pool_id in zip(rows, ids):
            row["id"] = pool_id
            row["relationships"]["base_token"]["data"]["id"] = network + "_" + token
        outcomes = {("geckoterminal", kind): _t031_reply({"data": rows})
                    for kind in ("new", "trending")}
        for interface in ("http", "mcp"):
            for listing in ("mixed", "trending"):
                status, result, answer, state = _t090_route(
                    interface, {"chain": chain, "listing": listing, "limit": 10}, outcomes)
                check("T099 valid pool IDs survive the actual discovery response completely",
                      status == 200 and not result.get("isError")
                      and [row["pool_id"] for row in answer.get("pools", [])] == ids,
                      "%s %s %s" % (chain, interface, listing))
                check("T099 full IDs retain deduplication and token-only assessment arguments",
                      answer.get("count") == answer.get("scanned") == len(ids)
                      and all(row.get("assessment_args") == {"address": token, "chain_hint": chain}
                              for row in answer.get("pools", [])))
                check("T099 identity display adds no calls or changes listing scope",
                      _t031_trace(state) == [("geckoterminal", kind) for kind in (
                          ("new", "trending") if listing == "mixed" else ("trending",))])


def test_t099_nonstandard_discovery_ids_keep_existing_bounds_and_escaping():
    """A long or hostile value remains bounded display text, never a complete identity."""
    examples = [("base_0x" + "f" * 1000, "base_0x" + "f" * 57 + "..."),
                ("solana_0x" + "A" * 64, "solana_0x" + "A" * 55 + "..."),
                ("base_0x" + "A" * 64 + "\n", "base_0x" + "A" * 57 + "..."),
                ("line\n\"\\|", "line\\u000a\\u0022\\u005c\\u007c"),
                ("\u202e" * 1000, "\\u202e" * 64 + "..."),
                ("solana_" + "\u0430" * 44, "solana_" + "\\u0430" * 44),
                (17, "17")]
    rows = [dict(_t028_pool("1"), id=pool_id) for pool_id, _ in examples]
    rows.extend({"id": value} for value in (None, "", False, 0))
    outcomes = {("geckoterminal", kind): _t031_reply({"data": rows})
                for kind in ("new", "trending")}
    for interface in ("http", "mcp"):
        status, _, answer, _ = _t090_route(
            interface, {"chain": "solana", "listing": "trending", "limit": 10}, outcomes)
        check("T099 malformed strings and scalars keep exact bounded legacy rendering",
              status == 200 and [row["pool_id"] for row in answer.get("pools", [])]
              == [expected for _, expected in examples])
        check("T099 missing and false IDs remain excluded without invented handoff arguments",
              answer.get("count") == answer.get("scanned") == len(examples)
              and all("assessment_args" not in row for row in answer.get("pools", [])))


def _t090_overlap():
    return {("geckoterminal", "new"): _t031_reply({"data": [_t031_pool("1"), _t031_pool("2")]}),
            ("geckoterminal", "trending"): _t031_reply(
                {"data": [_t031_pool("2"), _t031_pool("2"), _t031_pool("3")]})}


def test_discovery_reports_disjoint_trade_counts_on_the_selected_pool():
    limit = 2**53 - 1
    def windows(last_buys, last_sells, six_buys, six_sells):
        return {"h1": {"buys": last_buys, "sells": last_sells},
                "h6": {"buys": six_buys, "sells": six_sells}}

    readings = [
        (windows(2, 3, 11, 13), {"trades_last_1h": 5, "trades_prior_5h": 19}),
        (windows(0, 0, 0, 0), {"trades_last_1h": 0, "trades_prior_5h": 0}),
        (windows(0, 0, limit, 0), {"trades_last_1h": 0, "trades_prior_5h": limit}),
        (None, None), ([], None), ({"h1": {}, "h6": {"sells": 0}}, None),
        (windows(2, 3, 1, 20), None), (windows(3, 2, 20, 1), None),
        (windows(True, 0, 1, 0), None), (windows(0, -1, 0, 0), None),
        (windows(0, 0, "8", 0), None), (windows(0, 0, 0, 1.5), None),
        (windows(0, 0, limit + 1, 0), None), (windows(limit, 1, limit, 1), None),
        (windows(0, 0, limit, 1), None),
    ]
    rows = []
    for i, (reading, _) in enumerate(readings):
        row = _t031_pool(str(i))
        row["attributes"]["transactions"] = reading
        rows.append(row)
    args = {"chain": "ethereum", "limit": len(rows), "listing": "trending"}
    outcomes = {("geckoterminal", "trending"): _t031_reply({"data": rows})}
    for interface in ("mcp", "http"):
        status, _, data, state = _t090_route(interface, args, outcomes)
        pools = data.get("pools", [])
        check("observing optional trade counts keeps every pool in provider order",
              status == 200 and data.get("status") == "ok"
              and [p["pool_id"] for p in pools] == [r["id"] for r in rows]
              and _t031_trace(state) == [("geckoterminal", "trending")])
        check("only consistent same-pool counts yield two exact disjoint windows",
              [p.get("trade_activity") for p in pools] == [expected for _, expected in readings]
              and all("trade_activity" not in p for p, (_, expected) in zip(pools, readings)
                      if expected is None))

    tools = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    schema = next(t for t in tools if t["name"] == "find_new_hot_pools")["outputSchema"]
    item = schema["properties"]["pools"]["items"]
    activity = item["properties"].get("trade_activity", {})
    fields = {"trades_last_1h", "trades_prior_5h"}
    check("tools/list declares both integer windows on an optional activity object",
          "trade_activity" not in item["required"] and activity.get("type") == "object"
          and set(activity.get("required", [])) == fields and all(
              activity.get("properties", {}).get(k, {}).get("type") == "integer" for k in fields))


def test_t090_selected_listing_reaches_real_http_and_mcp_before_limit():
    for interface in ("http", "mcp"):
        args = {"chain": "ethereum", "limit": 2}
        status, _, default, state = _t090_route(interface, args, _t090_overlap())
        explicit = _t090_route(interface, dict(args, listing="mixed"), _t090_overlap())
        check("T090 explicit mixed preserves the entire default answer and provider order",
              status == explicit[0] == 200 and default == explicit[2]
              and _t031_trace(state) == _t031_trace(explicit[3])
              == [("geckoterminal", "new"), ("geckoterminal", "trending")]
              and "listing" not in default)
        default_ids = [row["pool_id"] for row in default.get("pools", [])]
        check("T090 default retains the original new-first overlap result",
              default_ids == ["eth_pool1", "eth_pool2"] and default.get("scanned") == 3)
        for limit in (1, 2):
            status, result, selected, state = _t090_route(
                interface, dict(args, listing="trending", limit=limit), _t090_overlap())
            ids = [row["pool_id"] for row in selected.get("pools", [])]
            check("T090 selects original trending order before deduplication and limit",
                  status == 200 and not result.get("isError") and ids == ["eth_pool2", "eth_pool3"][:limit]
                  and selected.get("count") == limit and selected.get("scanned") == 2)
            check("T090 selected scope is complete and does not request new",
                  selected.get("listing") == "trending" and selected.get("status") == "ok"
                  and selected.get("sources_ok") == ["trending"] and selected.get("sources_failed") == []
                  and _t031_trace(state) == [("geckoterminal", "trending")])
            check("T090 selected rows retain callable chain context",
                  all(row.get("assessment_args") == {"address": row["token_address"], "chain_hint": "ethereum"}
                      for row in selected.get("pools", [])) and len(ids) == limit)
            if limit == 2:
                trending = {"eth_pool2", "eth_pool3"}
                check("T090 real identity membership improves one to two and unique zero to one",
                      len(set(default_ids) & trending) == 1 and len(set(ids) & trending) == 2
                      and "eth_pool3" not in default_ids and "eth_pool3" in ids)


def test_t090_selected_empty_failure_and_provider_fallback_remain_distinct():
    for interface in ("http", "mcp"):
        args = {"chain": "ethereum", "listing": "trending", "limit": 2}
        for label, reply in (("empty", _t031_reply({"data": []})),
                             ("malformed", _t031_reply({"data": [{"id": "eth_bad", "attributes": [1]}]})),
                             ("failed", _t031_reply({}, 429))):
            outcomes = _t090_overlap()
            outcomes[("geckoterminal", "trending")] = reply
            status, result, data, state = _t090_route(interface, args, outcomes)
            check("T090 selected source never substitutes healthy unrequested new",
                  _t031_trace(state) == [("geckoterminal", "trending")])
            if label == "empty":
                check("T090 observed empty selected listing is a complete zero",
                      status == 200 and not result.get("isError") and data.get("pools") == []
                      and data.get("count") == data.get("scanned") == 0 and data.get("status") == "ok"
                      and data.get("listing") == "trending" and data.get("sources_ok") == ["trending"]
                      and data.get("sources_failed") == [])
            else:
                check("T090 unusable selected listing retains the existing error envelope",
                      (status == 200 and result.get("isError") is True and "structuredContent" not in result
                       and "GeckoTerminal request failed;" in result.get("content", [{}])[0].get("text", ""))
                      if interface == "mcp" else status == 500 and data.get("error") == "internal_error"
                      and data.get("detail", "").startswith("GeckoTerminal request failed;"))
        outcomes = _t090_overlap()
        outcomes[("coingecko", "trending")] = _t031_reply({}, 429)
        status, result, data, state = _t090_route(interface, args, outcomes, key="t031-synthetic-header-only-credential")
        check("T090 provider fallback stays within selected listing and retains its overlap",
              status == 200 and not result.get("isError") and data.get("status") == "ok"
              and [row["pool_id"] for row in data.get("pools", [])] == ["eth_pool2", "eth_pool3"]
              and _t031_trace(state) == [("coingecko", "trending"), ("geckoterminal", "trending")])
        _t031_private("T090 selected fallback: ", state, data)


def test_t090_invalid_selection_is_refused_before_any_upstream():
    for interface in ("http", "mcp"):
        invalid = ["", "new", "Trending", " trending", "PRIVATE-LISTING" * 100]
        if interface == "mcp":
            invalid += [None, True, 1, [], {}]
        for value in invalid:
            status, result, data, state = _t090_route(
                interface, {"chain": "ethereum", "listing": value}, _t090_overlap())
            message = (result.get("content", [{}])[0].get("text", "") if interface == "mcp"
                       else data.get("detail", ""))
            check("T090 invalid listing uses bounded static transport refusal before upstream",
                  not state["requests"] and "PRIVATE-LISTING" not in message
                  and message.endswith("Invalid listing: expected mixed or trending")
                  and len(message) < 100 and (status == 200 and result.get("isError") is True
                      if interface == "mcp" else status == 400 and data.get("error") == "invalid_request"))
    with _t031_runtime(_t090_overlap(), key=None) as (_, state, _):
        try:
            asyncio.run(risk.new_pools("ethereum", 2, "new"))
            error = None
        except Exception as exc:
            error = exc
    check("T090 engine also validates listing before its fetch boundary",
          isinstance(error, ValueError) and str(error) == "Invalid listing: expected mixed or trending"
          and not state["requests"])


def test_t090_tools_list_exposes_selected_scope_without_changing_default_contract():
    tools = call({"jsonrpc": "2.0", "id": 90, "method": "tools/list"})["result"]["tools"]
    tool = next(item for item in tools if item["name"] == "find_new_hot_pools")
    selection = tool["inputSchema"]["properties"].get("listing", {})
    output = tool["outputSchema"]
    check("T090 listing input is optional mixed or trending with compatible default",
          selection.get("type") == "string" and selection.get("enum") == ["mixed", "trending"]
          and selection.get("default") == "mixed" and "listing" not in tool["inputSchema"].get("required", []))
    check("T090 selected response scope is optional and only emits trending",
          output["properties"].get("listing", {}).get("enum") == ["trending"]
          and "listing" not in output.get("required", []))
    description = output["properties"]["status"]["description"].lower()
    check("T090 status preserves both/one mixed meaning and explains selected completeness",
          all(word in description for word in ("both", "one", "mixed", "trending", "selected")))
    check("T090 discovery instructions recommend selection without claiming persistent funding",
          "listing" in tool["description"] and "active" in tool["description"]
          and "pool_age_days" in tool["description"] and "sustained funding" in tool["description"]
          and "assessment_args" in tool["description"] and "chain_searched" in tool["description"])


def test_t090_duplicate_http_selection_is_refused_before_upstream():
    from urllib.parse import urlencode

    for first, second in (("", "trending"), ("trending", ""),
                          ("PRIVATE-DUPLICATE", "trending"), ("trending", "PRIVATE-DUPLICATE"),
                          ("mixed", "trending"), ("trending", "mixed"),
                          ("trending", "trending"), ("mixed", "mixed")):
        with _t031_runtime(_t090_overlap(), key=None) as (runtime, state, env):
            query = urlencode([("chain", "ethereum"), ("listing", first), ("listing", second)])
            request = runtime.FakeRequest("https://offline.invalid/new-pools?" + query,
                                          headers={"x-mcp-client": "vetagent-manual-probe"})
            worker = runtime.entry.Default()
            worker.env = env
            response = asyncio.run(worker.fetch(request))
            answer = json.loads(response.body)
        check("T090 duplicate selection is a static HTTP refusal with zero upstream calls",
              response.status == 400 and answer == {
                  "error": "invalid_request", "detail": "Invalid listing: expected mixed or trending"}
              and not state["requests"] and not state["blocked"] and not state["unexpected"])


def _t091_public_assessment(interface, chain, hint, verbose, json_age=None, bytecode_age=None,
                            hp_status=200, reader=risk._fetch_json):
    from urllib.parse import urlencode
    import test_http_telemetry as runtime
    import test_risk as fixtures

    with fixtures._t091_runtime(chain, hp_status=hp_status, reader=reader) as state:
        requested = risk._canonical_chain(hint)
        if requested in risk._KNOWN_CHAINS and requested != chain:
            fixtures._t091_empty_scoped_listing(state, requested)
        if json_age is not None:
            state["cache"]["market"] = (state["market"], json_age)
        if bytecode_age is not None:
            state["cache"]["bytecode"] = (state["code"], bytecode_age)
        args = {"address": state["address"], "chain_hint": hint, "verbose": verbose}
        body = {"jsonrpc": "2.0", "id": 91, "method": "tools/call",
                "params": {"name": "assess_token_risk", "arguments": args}}

        class Request(runtime.FakeRequest):
            async def json(self):
                return body

        url = ("/mcp" if interface == "mcp" else "/assess/" + state["address"] + "?"
               + urlencode({"chain_hint": hint, "verbose": verbose}))
        request = Request("https://offline.invalid" + url, method="POST" if interface == "mcp" else "GET",
                          headers={"x-mcp-client": "vetagent-manual-probe"})
        with patch.object(runtime.entry, "_record", lambda *args: None):
            response = asyncio.run(runtime.entry.Default().fetch(request))
        envelope = json.loads(response.body)
    result = envelope.get("result", {}) if interface == "mcp" else envelope
    answer = result.get("structuredContent", {}) if interface == "mcp" else result
    check("T091 normal public route returns an assessment", response.status == 200
          and not result.get("isError") and "risk_level" in answer)
    if interface == "mcp":
        check("T091 MCP text and structured evidence agree",
              json.loads(result.get("content", [{}])[0].get("text", "null")) == answer)
    return answer, state


def test_t091_cache_age_and_selected_chain_cross_real_http_and_mcp():
    for interface in ("http", "mcp"):
        for verbose in (False, True):
            for json_age, bytecode_age, expected in ((0.25, None, 1), (59, None, 59),
                                                     (60, 3600.25, 3601)):
                answer, state = _t091_public_assessment(interface, "ethereum", "ethereum", verbose,
                                                       json_age, bytecode_age)
                check("T091 both transports and evidence modes report usable local cache residence",
                      answer.get("evidence_max_age_seconds") == expected
                      and "served_stale" not in answer["evidence"]
                      and (bytecode_age is None or all(kind != "rpc" for kind, _ in state["requests"])))
            answer, state = _t091_public_assessment(interface, "arbitrum", "ethereum", verbose,
                                                   hp_status=503)
            check("T091 selected unsupported chain is an unchanged abstention without simulator work",
                  answer["evidence"]["chain_searched"] == "arbitrum" and answer["risk_level"] == "unknown"
                  and answer.get("next_action") == "abstain" and not state["sleeps"]
                  and all(not kind.startswith("sell") for kind, _ in state["requests"])
                  and all(not kind.startswith("sell") for kind in state["cache_reads"]))
            answer, state = _t091_public_assessment(interface, "base", "arbitrum", verbose)
            sells = [url for kind, url in state["requests"] if kind == "sell"]
            check("T091 an unsupported hint does not skip observed Base simulation",
                  answer["evidence"]["chain_searched"] == "base" and len(sells) == 1
                  and "chainID=8453" in sells[0])


def test_assessment_prefers_the_requested_market_and_keeps_checks_on_the_actual_network(reader=risk._fetch_json):
    import test_risk as fixtures

    cases = [("base", "ethereum", True, "ethereum", 200, "found"),
             ("ethereum", "bsc", False, "ethereum", 200, "empty"),
             ("ethereum", "bsc", False, "ethereum", 429, "unconfirmed")]
    cases.extend(("ethereum", chain, True, chain, 200, "found")
                 for chain in ("polygon", "arbitrum", "optimism", "avalanche"))
    for initial, requested, found, used, status, lookup in cases:
        for interface, verbose in (("http", False), ("mcp", True), ("mcp", False)):
            target = fixtures._t030_pair(175000, reserves=False, chain=requested)
            target["pairAddress"] = "0x" + "cd" * 20
            hp = fixtures._t092_report(target["pairAddress"] if found else "0x" + "ab" * 20)
            with fixtures._t091_runtime(initial, hp_body=hp, reader=reader) as state:
                address = state["address"]
                scoped_url = "https://api.dexscreener.com/token-pairs/v1/" + requested + "/" + address
                state["scoped"][scoped_url] = (status, [target] if found else [])
                answer = asyncio.run(_t092_worker_request(interface, "assess_token_risk",
                    {"address": address, "chain_hint": requested, "verbose": verbose}))
            evidence = answer["evidence"]
            check("assessment uses the scoped request once and names the observed chain in both evidence modes",
                  state["requests"][:2] == [("market", fixtures._T083_DS + address), ("scoped", scoped_url)]
                  and [kind for kind, _ in state["requests"]].count("scoped") == 1
                  and evidence["chain_searched"] == used and evidence["best_pair"]["chain"] == used
                  and evidence["best_pair"]["liquidity_usd"] == (175000 if found else 250000)
                  and answer.get("network_selection") == {"requested_chain": requested, "returned_chain": used,
                      "status": "matched" if found else "different", "lookup": lookup}, str(answer))
            sells = [url for kind, url in state["requests"] if kind.startswith("sell")]
            rpcs = [url for kind, url in state["requests"] if kind == "rpc"]
            if used == "ethereum":
                check("sell and bytecode use the actual Ethereum deployment",
                      len(sells) == 1 and sells[0].endswith("&chainID=1")
                      and rpcs == [risk._CHAIN_RPC["ethereum"]] and evidence.get("pool_link") == "same")
            else:
                check("unsupported selected market never runs another network's simulator or RPC",
                      not sells and not rpcs and answer["risk_level"] != "low"
                      and "honeypot" not in evidence and evidence["pool_link"] == "unknown")
            if not found:
                check("a foreign low recommendation names both scopes before the low statement",
                      answer["risk_level"] == "low" and answer["risk_score"] == 0
                      and answer["recommendation"].startswith(
                          "You requested bsc. This assessment covers ethereum only."), answer["recommendation"])


def test_assessment_incompatible_hint_does_not_probe_an_undeclared_evm_network(reader=risk._fetch_json):
    import test_risk as fixtures

    with fixtures._t091_runtime("ethereum", reader=reader) as state:
        state["market"]["pairs"] = []
        address = state["address"]
        answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk",
            {"address": address, "chain_hint": "solana"}))
    check("an incompatible hint without an observed EVM scope cannot run a bare simulation or bytecode lookup",
          state["requests"] == [("market", fixtures._T083_DS + address)]
          and answer.get("network_selection") == {
              "requested_chain": "solana", "status": "unresolved", "lookup": "incompatible_address"}
          and answer.get("risk_level") == "unknown" and answer.get("evidence", {}).get("chain_searched") == "",
          str((answer, state["requests"])))


def test_assessment_scopes_drained_and_unpriced_market_checks_without_a_best_pair(reader=risk._fetch_json):
    import test_risk as fixtures

    for initial, depth, risk_level in (("ethereum", {"usd": 0}, "high"), ("polygon", {}, "unknown")):
        with fixtures._t091_runtime(initial, reader=reader) as state:
            state["market"]["pairs"][0]["liquidity"] = depth
            address = state["address"]
            requested = "https://api.dexscreener.com/token-pairs/v1/bsc/" + address
            state["scoped"][requested] = (200, [])
            answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk",
                {"address": address, "chain_hint": "bsc", "verbose": True}))
        evidence = answer["evidence"]
        sells = [url for kind, url in state["requests"] if kind == "sell"]
        rpcs = [url for kind, url in state["requests"] if kind == "rpc"]
        check("a drained or unpriced market establishes its observed chain without a selected pool",
              answer["risk_level"] == risk_level and evidence["chain_searched"] == initial
              and "best_pair" not in evidence and evidence["pool_link"] == "unknown"
              and answer.get("network_selection", {}).get("returned_chain") == initial
              and [url for kind, url in state["requests"] if kind == "scoped"] == [requested])
        check("bytecode and sell evidence follow the observed scope even without a best pair",
              evidence["pool_link_details"]["policy_chain"] == initial
              and rpcs == ([risk._CHAIN_RPC["ethereum"]] if initial == "ethereum" else [])
              and (len(sells) == 1 and sells[0].endswith("&chainID=1") if initial == "ethereum" else not sells))


def test_t091_tools_list_defines_local_residence_not_live_observation_age():
    tools = call({"jsonrpc": "2.0", "id": 91, "method": "tools/list"})["result"]["tools"]
    tool = next(item for item in tools if item["name"] == "assess_token_risk")
    description = tool["outputSchema"]["properties"]["evidence_max_age_seconds"]["description"].lower()
    check("T091 existing age field explains local cache residence including bytecode",
          all(word in description for word in ("local", "cache", "bytecode", "zero"))
          and "every source answered live" not in description)


def _t092_market_cases():
    import test_risk as fixtures
    address = fixtures.WETH.lower()
    a, b = fixtures._T084_USDC_POOL, fixtures._T084_LEEPH_POOL
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
    base = {fixtures._T083_DS + address: ("market", 200, {"pairs": []}),
            fixtures._t083_market_url("eth", address): ("fallback", 200, fixtures._load("gt_weth_anchor_pools.json")),
            "https://api.dexscreener.com/latest/dex/search?q=WETH": ("search", 200, {"pairs": []})}
    cases = []
    for name, pool, relation, reason in (("default same", a, "same", None),
                                       ("default different", b, "different", None),
                                       ("default missing", None, "unknown", "missing_pool")):
        body = fixtures._t092_report(pool)
        cases.append((name, dict(base, **{sell: ("default", 200, body)}), relation, reason, "default", a, pool))
    for name, pool, relation, reason, adopted, final in (
            ("retry matching", b, "different", None, "retry", a),
            ("retry unreported", None, "unknown", "missing_pool", "retry", a),
            ("retry rejected", a, "same", None, "default", b)):
        first = fixtures._t092_report(b)
        first.update(simulationSuccess=False, simulationError="execution reverted: HP: BUY_FAILED")
        routes = dict(base, **{sell: ("default", 200, first),
                      sell + "&pair=" + b: ("retry", 200, fixtures._t092_report(pool))})
        cases.append((name, routes, relation, reason, adopted, final, pool))
    return address, a, b, cases


async def _t092_worker_request(interface, tool, args):
    from urllib.parse import urlencode
    import test_http_telemetry as runtime
    body = {"jsonrpc": "2.0", "id": 92, "method": "tools/call",
            "params": {"name": tool, "arguments": args}}

    class Request(runtime.FakeRequest):
        async def json(self):
            return body

    prefix = "/assess/" if tool == "assess_token_risk" else "/liquidity/"
    url = "/mcp" if interface == "mcp" else prefix + args["address"] + "?" + urlencode(
        {key: value for key, value in args.items() if key != "address"})
    with patch.object(runtime.entry, "_record", lambda *args: None):
        response = await runtime.entry.Default().fetch(Request(
            "https://offline.invalid" + url, method="POST" if interface == "mcp" else "GET",
            headers={"x-mcp-client": "vetagent-manual-probe"}))
    envelope = json.loads(response.body)
    answer = envelope.get("result", {}).get("structuredContent", {}) if interface == "mcp" else envelope
    check("T092 actual Worker route succeeds", response.status == 200 and bool(answer))
    if interface == "mcp":
        check("T092 actual MCP text matches structured output",
              json.loads(envelope["result"]["content"][0]["text"]) == answer)
    return answer


def _t092_public_market(interface, tool, arguments, routes, reader=risk._fetch_json, *, cached=None):
    import test_risk as fixtures
    original_handle = mcp_server.handle_mcp_request

    async def worker_route(payload):
        with patch.object(mcp_server, "handle_mcp_request", original_handle):
            answer = await _t092_worker_request(interface, tool, arguments)
        return {"result": {"structuredContent": answer}}

    with patch.object(mcp_server, "handle_mcp_request", worker_route), \
            patch.object(fixtures, "_ORIGINAL_FETCH_JSON", reader):
        return asyncio.run(fixtures._t083_mcp(tool, arguments, routes, cached))


def test_t092_final_market_and_adopted_simulator_cross_both_worker_routes():
    address, a, b, cases = _t092_market_cases()
    for name, routes, relation, reason, adopted, final, reported in cases:
        for interface in ("http", "mcp"):
            for verbose in (False, True):
                answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                    {"address": address, "chain_hint": "ethereum", "verbose": verbose}, routes)
                ev = answer["evidence"]
                detail = ev.get("pool_link_details") or {}
                tag = "T092 %s %s %s" % (name, interface, verbose)
                check(tag + " relation follows final promotion and adopted response", ev.get("pool_link") == relation)
                check(tag + " complete pool ID tracks the final displayed market in both modes",
                      ev["best_pair"].get("pool_id") == final)
                check(tag + " scope details and reasons are verbose only",
                      ("pool_link_details" in ev) is verbose and "pool_scope_reason" not in ev)
                check(tag + " original request trace and verdict survive",
                      calls == ["market", "fallback", "search", "default"] + (["retry"] if name.startswith("retry") else [])
                      and not sleeps and answer["risk_level"] == ("unknown" if name == "retry rejected" else "low"))
                if verbose:
                    check(tag + " final versus requested and reported identities remain separate",
                          detail.get("reason") == reason and detail.get("market_pool") == final
                          and detail.get("market_chain") == "ethereum" and detail.get("adopted_response") == adopted
                          and detail.get("policy_chain") == "ethereum" and detail.get("requested_chain") == "ethereum"
                          and detail.get("requested_pool") == (b if adopted == "retry" else None)
                          and detail.get("reported_pool") == (b if name == "retry rejected" else reported)
                          and detail.get("reported_chain") == "ethereum", str(detail))
                    if name.startswith("retry"):
                        check(tag + " attempted retry is not mistaken for adopted evidence",
                              detail.get("retry") == {"requested_pool": b, "reported_pool": reported,
                                                      "reported_chain": "ethereum", "accepted": adopted == "retry"}, str(detail))
                    else:
                        check(tag + " no fictitious retry", "retry" not in detail)
                else:
                    check(tag + " compact keeps original market address omission", "pair_address" not in ev["best_pair"])
    routes = cases[0][1]
    for interface in ("http", "mcp"):
        answer, calls, _, sleeps, _ = _t092_public_market(interface, "get_token_liquidity",
            {"address": address, "chain_hint": "ethereum"}, routes)
        check("T092 liquidity identifies its own selected market without a simulation",
              answer.get("best_pair_address") == a and answer.get("source") == "geckoterminal"
              and answer.get("best_pair_chain") == "ethereum" and answer["status"] == "ok"
              and "pool_link" not in answer and calls == ["market", "fallback"] and not sleeps)


def test_sell_recommendation_names_only_the_adopted_simulation_scope():
    address, _, _, cases = _t092_market_cases()
    descriptions = {
        "same": ("honeypot.is", "completed simulation", "in the displayed pool"),
        "different": ("honeypot.is", "completed simulation", "another pool", "did not verify selling in the displayed pool"),
        "unknown": ("honeypot.is", "completed simulation", "whether it simulated the displayed pool is unknown"),
    }
    for name, routes, relation, _, _, _, _ in cases:
        for interface in ("mcp", "http"):
            for verbose in (False, True):
                answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                    {"address": address, "chain_hint": "ethereum", "verbose": verbose}, routes)
                recommendation = answer["recommendation"].lower()
                tag = "%s %s verbose=%s" % (name, interface, verbose)
                check(tag + " legacy venue, verdict and request policy",
                      answer["evidence"]["pool_link"] == relation
                      and answer["risk_level"] == ("unknown" if name == "retry rejected" else "low")
                      and calls == ["market", "fallback", "search", "default"]
                      + (["retry"] if name.startswith("retry") else []) and not sleeps)
                check(tag + " recommendation does not promise an exit",
                      all(phrase not in recommendation for phrase in
                          ("sellable and liquid", "exit was open", "your wallet can sell")),
                      answer["recommendation"])
                positive = [s for s in answer["signals"]
                            if s["severity"] == "ok" and s["category"] == "honeypot"]
                if name == "retry rejected":
                    check(tag + " failed adoption does not report completion",
                          "completed simulation" not in recommendation and not positive, answer["recommendation"])
                else:
                    check(tag + " recommendation names provider and matched scope",
                          all(phrase in recommendation for phrase in descriptions[relation]),
                          answer["recommendation"])
                    check(tag + " success signal identifies the simulation, with original tax readings",
                          len(positive) == 1 and "simulation" in positive[0]["name"].lower()
                          and all(phrase in positive[0]["message"].lower() for phrase in
                                  ("honeypot.is", "buy 0.0%", "sell 0.0%")), str(positive))


def test_sell_recommendation_distinguishes_selected_pool_history_and_missing_scope(reader=risk._fetch_json):
    import test_risk as fixtures
    for verbose in (False, True):
        with fixtures._t091_runtime("ethereum", hp_status=404, reader=reader) as state:
            state["market"]["pairs"][0]["txns"]["h24"] = {"buys": 900, "sells": 850}
            answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk",
                {"address": state["address"], "chain_hint": "ethereum", "verbose": verbose}))
        rec = answer["recommendation"].lower()
        chain_sells = answer["evidence"].get("sellability_from_chain", {})
        check("market history keeps the sellability gap and original requests",
              answer["risk_level"] == "unknown" and chain_sells.get("verifies_your_exit") is False
              and chain_sells.get("sells_24h") == 850 and not state["sleeps"]
              and [kind for kind, _ in state["requests"]].count("sell") == 1, str(chain_sells))
        check("recommendation attributes past sells to market data for the displayed pool",
              all(phrase in rec for phrase in ("market data", "past sells", "displayed pool"))
              and "completed simulation" not in rec, answer["recommendation"])
        with fixtures._t091_runtime("arbitrum", reader=reader) as state:
            fixtures._t091_empty_scoped_listing(state, "ethereum")
            answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk",
                {"address": state["address"], "chain_hint": "ethereum", "verbose": verbose}))
        rec = answer["recommendation"].lower()
        check("selected unsupported chain preserves bounded abstention",
              answer["risk_level"] == "unknown" and answer["next_action"] == "abstain"
              and answer["evidence"]["chain_searched"] == "arbitrum"
              and not any(kind.startswith("sell") for kind, _ in state["requests"]))
        check("unsupported chain offers no completed simulation or exit assurance",
              "completed simulation" not in rec and "exit was open" not in rec, answer["recommendation"])


def test_t092_conflicted_unpriced_chain_routes_keep_unknown_and_calls(reader=risk._fetch_json):
    import test_risk as fixtures
    for observed, hint in (("base", "arbitrum"), ("arbitrum", "ethereum")):
        for interface in ("http", "mcp"):
            for verbose in (False, True):
                with fixtures._t091_runtime(observed, reserves=True, hp_status=503, reader=reader) as state:
                    fixtures._t091_empty_scoped_listing(state, hint)
                    answer = asyncio.run(_t092_worker_request(interface, "assess_token_risk",
                        {"address": state["address"], "chain_hint": hint, "verbose": verbose}))
                ev = answer["evidence"]
                check("T092 conflicting unpriced chain remains unknown on the real route",
                      answer["risk_level"] == "unknown" and ev.get("pool_link") == "unknown"
                      and ev.get("chain_searched") == observed and "best_pair" not in ev)
                sells = [u for kind, u in state["requests"] if kind == "sell"]
                check("T092 unpriced real route uses the observed network for bounded sell checks",
                      len(sells) == 3 and all(url.endswith("chainID=8453") for url in sells)
                      and state["sleeps"] == [0.3, 0.6] if observed == "base" else not sells and not state["sleeps"])
                if verbose:
                    detail = ev.get("pool_link_details") or {}
                    check("T092 the missing priced market has a consistent simulation policy scope",
                          detail.get("reason") == "no_market" and detail.get("policy_chain") == observed
                          and detail.get("requested_chain") == ("base" if observed == "base" else None))
            with fixtures._t091_runtime(observed, reserves=True, reader=reader) as state:
                address = state["address"]
                routes = {fixtures._T083_DS + address: ("market", 200, state["market"]),
                          "https://api.dexscreener.com/token-pairs/v1/" + hint + "/" + address:
                              ("requested", 200, [])}
            answer, calls, _, _, _ = _t092_public_market(interface, "get_token_liquidity",
                {"address": address, "chain_hint": hint}, routes, reader)
            check("T092 unpriced liquidity invents no selected identity",
                  answer["status"] == "unpriced" and "best_pair_address" not in answer
                  and "pool_link" not in answer and calls == ["market", "requested"])


def test_t092_schema_declares_correspondence_and_liquidity_identity():
    tools = call({"jsonrpc": "2.0", "id": 92, "method": "tools/list"})["result"]["tools"]
    assess = next(t for t in tools if t["name"] == "assess_token_risk")["outputSchema"]
    props = assess["properties"]["evidence"].get("properties", {})
    check("T092 scope has exactly the three correspondence values",
          props.get("pool_link", {}).get("enum") == ["same", "different", "unknown"])
    details = props.get("pool_link_details", {}).get("properties", {})
    required = {"reason", "market_pool", "market_chain", "adopted_response", "policy_chain",
                "requested_chain", "requested_pool", "reported_chain", "reported_pool", "retry"}
    check("T092 verbose details declare requested and reported facts separately", required <= set(details))
    check("T092 source disclosure does not require successful simulation",
          "simulation_success" not in props.get("pool_link_details", {}).get("required", []))
    liquidity = next(t for t in tools if t["name"] == "get_token_liquidity")["outputSchema"]
    check("T092 liquidity declares both old provenance and new optional display ID",
          {"source", "best_pair_chain", "best_pair_dex", "best_pair_address"} <= set(liquidity["properties"])
          and liquidity["required"] == ["address", "status"])


def test_t092_source_pool_rejects_terminal_lf_in_every_alias():
    import test_risk as fixtures
    address, pool, _, cases = _t092_market_cases()
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
    for alias in ("top", "nested", "legacy", "mixed"):
        body = fixtures._t092_report(None)
        if alias in ("top", "mixed"):
            body["pairAddress"] = pool + "\n"
        if alias == "nested":
            body["pair"] = {"pair": {"address": pool + "\n"}}
        elif alias == "legacy":
            body["pair"] = {"address": pool + "\n"}
        elif alias == "mixed":
            body["pair"] = {"address": pool}
        routes = dict(cases[0][1], **{sell: ("default", 200, body)})
        for interface in ("http", "mcp"):
            for verbose in (False, True):
                answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                    {"address": address, "chain_hint": "ethereum", "verbose": verbose}, routes)
                ev = answer["evidence"]
                tag = "T092 terminal LF %s %s %s" % (alias, interface, verbose)
                check(tag + " is not an affirmative source identity", ev.get("pool_link") == "unknown")
                check(tag + " leaves existing requests and score unchanged",
                      calls == ["market", "fallback", "search", "default"] and not sleeps
                      and answer["risk_level"] == "low" and answer["risk_score"] == 0)
                if verbose:
                    detail = ev.get("pool_link_details") or {}
                    check(tag + " rejects instead of stripping or comparing the malformed declaration",
                          detail.get("reason") == "invalid_pool" and detail.get("reported_pool") is None,
                          str(detail))


def test_t092_malformed_simulator_metadata_cannot_identify_correspondence():
    import test_risk as fixtures
    address, pool, _, cases = _t092_market_cases()
    body = fixtures._t092_report(pool)
    body["simulationResult"] = []
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
    routes = dict(cases[0][1], **{sell: ("default", 200, body)})
    for interface in ("http", "mcp"):
        for verbose in (False, True):
            answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                {"address": address, "chain_hint": "ethereum", "verbose": verbose}, routes)
            ev = answer["evidence"]
            tag = "T092 malformed simulator metadata %s %s" % (interface, verbose)
            check(tag + " cannot affirm source correspondence", ev.get("pool_link") == "unknown")
            check(tag + " retains the old structural rejection and request path",
                  answer["risk_level"] == "unknown"
                  and any("invalid simulator metadata" in gap["reason"] for gap in ev["data_gaps"])
                  and calls == ["market", "fallback", "search", "default"] and not sleeps)
            if verbose:
                check(tag + " reports the existing structural failure",
                      ev.get("pool_link_details", {}).get("reason") == "invalid_response")


def _t094_cap_routes(case=0, amount="996", label="default"):
    """Reuse established transport fixtures; only add the documented quantity shape."""
    address, _, _, cases = _t092_market_cases()
    routes = copy.deepcopy(cases[case][1])
    for kind, _, body in routes.values():
        if kind == label:
            body["simulationResult"]["maxSell"] = {
                "tokenWei": amount, "token": 9.96e-6,
                "withTokenWei": "3850", "withToken": 3.9e-15}
    return address, routes


def _t094_compare(address, routes, verbose, expected, name, interface="mcp"):
    """Compare real Worker/MCP answers with only maxSell added, with I/O denied."""
    control = copy.deepcopy(routes)
    for _, _, body in control.values():
        sim = body.get("simulationResult") if isinstance(body, dict) else None
        if isinstance(sim, dict):
            sim.pop("maxSell", None)
    args = {"address": address, "chain_hint": "ethereum"}
    if verbose:
        args["verbose"] = True  # False deliberately uses the ordinary default.
    with patch.object(risk, "_now_iso", lambda: "2026-11-19T00:00:00Z"):
        before = _t092_public_market(interface, "assess_token_risk", args, control)
        after = _t092_public_market(interface, "assess_token_risk", args, routes)
    answer = after[0]
    evidence = answer.get("evidence", {})
    tag = "T094 %s %s %s" % (name, interface, verbose)
    check(tag + " exact qualified cap or absence", evidence.get("max_sell") == expected,
          str(evidence.get("max_sell")))
    check(tag + " absence never means an unlimited placeholder",
          expected is not None or "max_sell" not in evidence)
    stripped = copy.deepcopy(answer)
    stripped.get("evidence", {}).pop("max_sell", None)
    check(tag + " no score, level, confidence, signals or other result changes", stripped == before[0])
    check(tag + " same requests, cache writes, sleeps and diagnostics", after[1:] == before[1:])
    return answer


def _t094_expected(amount, relation="same"):
    return {"source": "honeypot.is", "scope": "simulated_transaction", "amount": amount,
            "unit": "token_smallest_unit", "pool_link": relation}


def test_t094_exact_max_sell_survives_default_and_verbose_mcp():
    """A detected single-sale cap is a precise source fact, not a risk-score input."""
    for amount in ("996", "0", "9007199254740993", str(2**256 - 1)):
        address, routes = _t094_cap_routes(amount=amount)
        facts = []
        for verbose in (False, True):
            result = _t094_compare(address, routes, verbose, _t094_expected(amount), "amount=" + amount)
            facts.append(result["evidence"].get("max_sell"))
        check("T094 the same compact fact is returned in both modes", facts[0] == facts[1])
    address, routes = _t094_cap_routes()
    for verbose in (False, True):
        _t094_compare(address, routes, verbose, _t094_expected("996"), "HTTP parity", interface="http")


def test_t094_malformed_or_unreported_quantity_does_not_become_unlimited():
    values = (None, True, 996, 996.0, [], {}, "", "01", "+1", "-1", "-0", "1.0", "1e3",
              " 1", "1 ", "1\n", "\n1", chr(0x0661), str(2**256), "9" * 79)
    for value in values:
        address, routes = _t094_cap_routes(amount=value)
        for verbose in (False, True):
            _t094_compare(address, routes, verbose, None, "invalid quantity " + repr(value))
    for shape in (None, [], {}, {"token": 0.00000996, "withTokenWei": "3850"}):
        address, routes = _t094_cap_routes()
        for kind, _, body in routes.values():
            if kind == "default":
                body["simulationResult"]["maxSell"] = shape
                body["simulationResult"]["maxBuy"] = {"tokenWei": "996"}
        for verbose in (False, True):
            _t094_compare(address, routes, verbose, None, "invalid or token-only maxSell " + repr(shape))


def test_t094_cap_uses_adopted_simulation_and_final_pool_correspondence():
    for case, label, relation, expected in (
            (1, "default", "different", True), (2, "default", "unknown", True),
            (3, "retry", "different", True), (4, "retry", "unknown", True),
            (5, "retry", "same", False), (3, "default", "different", False)):
        address, routes = _t094_cap_routes(case, label=label)
        for verbose in (False, True):
            answer = _t094_compare(address, routes, verbose,
                _t094_expected("996", relation) if expected else None, "adopted case %s/%s" % (case, label))
            check("T094 final pool correspondence remains the existing result",
                  answer["evidence"].get("pool_link") == relation)
    address, routes = _t094_cap_routes()
    for kind, _, body in routes.values():
        if kind == "default":
            body.pop("chain")
    for verbose in (False, True):
        _t094_compare(address, routes, verbose, _t094_expected("996", "unknown"), "missing reported chain")


def test_t094_invalid_simulation_cannot_lend_a_cap():
    import test_risk as fixtures
    mutations = (
        ("other token", lambda b: b.update(token={"address": "0x" + "12" * 20})),
        ("requested token is the paired asset", lambda b: b.update(withToken={"address": fixtures.WETH})),
        ("other chain", lambda b: b.update(chain={"id": 8453})),
        ("conflicting chain", lambda b: b.update(pair={"chainId": 8453})),
        ("pool conflict", lambda b: b.update(pair={"pair": {"address": fixtures._T084_LEEPH_POOL}})),
        ("invalid pool", lambda b: b.update(pairAddress="not-a-pool")),
        ("missing success", lambda b: b.pop("simulationSuccess")),
        ("nonboolean success", lambda b: b.update(simulationSuccess=1)),
        ("failed", lambda b: b.update(simulationSuccess=False, simulationError="execution reverted: HP: BUY_FAILED")),
        ("never ran", lambda b: (b.update(router="", honeypotResult={"isHoneypot": True,
                                        "honeypotReason": "Target contract does not contain code"}),
                                b["simulationResult"].update(buyGas="0"))),
        ("contradictory error", lambda b: b.update(simulationError="failed")),
        ("invalid metadata", lambda b: b.update(contractCode=[])),
        ("missing taxes", lambda b: b["simulationResult"].pop("sellTax")),
        ("missing result", lambda b: b.pop("honeypotResult")),
    )
    for name, mutate in mutations:
        address, routes = _t094_cap_routes()
        sell = next(url for url, (kind, _, _) in routes.items() if kind == "default")
        mutate(routes[sell][2])
        # Existing failed-simulation retries remain unchanged and cannot contribute a cap.
        routes[sell + "&pair=" + fixtures._T084_LEEPH_POOL] = ("retry", 404, {})
        for verbose in (False, True):
            _t094_compare(address, routes, verbose, None, name)


def test_t094_valid_cap_and_honeypot_warning_coexist():
    address, routes = _t094_cap_routes()
    for kind, _, body in routes.values():
        if kind == "default":
            body["honeypotResult"]["isHoneypot"] = True
            body["summary"] = {"risk": "honeypot", "riskLevel": 100}
    for verbose in (False, True):
        answer = _t094_compare(address, routes, verbose, _t094_expected("996", "different"), "reported honeypot")
        check("T094 cap does not clear the existing honeypot finding",
              answer["evidence"]["honeypot"]["is_honeypot"] is True
              and any(s["category"] == "honeypot" for s in answer["signals"]))


def test_t094_absent_or_unsupported_simulator_has_no_cap():
    import test_risk as fixtures
    address, routes = _t094_cap_routes()
    sell = next(url for url, (kind, _, _) in routes.items() if kind == "default")
    routes[sell] = ("default", 404, {})
    for verbose in (False, True):
        _t094_compare(address, routes, verbose, None, "simulator has no record")
        body = fixtures._t092_report()
        body["simulationResult"]["maxSell"] = {"tokenWei": "996"}
        with fixtures._t091_runtime("arbitrum", hp_body=body) as state:
            answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk",
                {"address": state["address"], "chain_hint": "arbitrum", "verbose": verbose}))
        check("T094 unsupported chain cannot display an unrequested cap",
              "max_sell" not in answer["evidence"]
              and all(not kind.startswith("sell") for kind, _ in state["requests"]))


def test_t094_tools_list_explains_precise_quantity_and_simulation_scope():
    tool = next(t for t in call({"jsonrpc": "2.0", "id": 94, "method": "tools/list"})
                ["result"]["tools"] if t["name"] == "assess_token_risk")
    schema = tool["outputSchema"]["properties"]["evidence"]["properties"].get("max_sell", {})
    props = schema.get("properties", {})
    check("T094 optional output fact has all its source, scope and exact-amount fields",
          schema.get("type") == "object"
          and set(schema.get("required", [])) == {"source", "scope", "amount", "unit", "pool_link"}
          and props.get("amount", {}).get("type") == "string"
          and props.get("unit", {}).get("enum") == ["token_smallest_unit"]
          and props.get("source", {}).get("enum") == ["honeypot.is"]
          and props.get("scope", {}).get("enum") == ["simulated_transaction"]
          and props.get("pool_link", {}).get("enum") == ["same", "different", "unknown"])
    description = schema.get("description", "").lower()
    check("T094 tool clients can read units, missing evidence and scope without a separate manual",
          all(word in description for word in ("smallest", "assessed token", "per-sell", "simulation",
                                               "unlimited", "guarantee", "uint256")))


def test_t094_review_rejects_unbound_market_and_malformed_paired_identity():
    """The first candidate let no_market hide source defects and accepted a bad paired identity."""
    import test_risk as fixtures
    address = fixtures._t030_pair(chain="ethereum", reserves=True)["baseToken"]["address"]
    cases = (
        ("bad pool without market", True, "ethereum", {"pairAddress": "malformed"}),
        ("unsupported chain without market", True, None, {"chain": {"id": 137}}),
        ("malformed paired object", False, "ethereum", {"withToken": ["bad"]}),
        ("malformed paired address", False, "ethereum", {"withToken": {"address": []}}),
    )
    for name, empty, hint, update in cases:
        for verbose in (False, True):
            observations = []
            for with_cap in (False, True):
                body = fixtures._t092_report()
                body.update(copy.deepcopy(update))  # token.address is deliberately undeclared.
                if with_cap:
                    body["simulationResult"]["maxSell"] = {"tokenWei": "996"}
                args = {"address": address, "verbose": verbose}
                if hint:
                    args["chain_hint"] = hint
                with fixtures._t091_runtime("ethereum", hp_body=body, reserves=True) as state:
                    if empty:
                        state["market"]["pairs"] = []
                    with patch.object(risk, "_now_iso", lambda: "2026-11-19T00:00:00Z"):
                        answer = asyncio.run(_t092_worker_request("mcp", "assess_token_risk", args))
                observations.append((answer, state["requests"], state["sleeps"]))
            check("T094 review %s/%s cannot attach the cap" % (name, verbose),
                  "max_sell" not in observations[1][0]["evidence"])
            stripped = copy.deepcopy(observations[1])
            stripped[0]["evidence"].pop("max_sell", None)
            check("T094 review changes no existing result or requests", stripped == observations[0])


def _price_attribution_routes(address, chain, rows, fallback=False):
    import test_risk as fixtures
    address = address.lower() if chain != "solana" else address
    network = risk._GT_NETWORK[chain]
    routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": [] if fallback else rows}),
              fixtures._t083_market_url(network, address): ("fallback", 200, {"data": rows}),
              "https://api.dexscreener.com/latest/dex/search?q=SAME": ("search", 200, {"pairs": []}),
              "https://api.dexscreener.com/latest/dex/search?q=WETH": ("search", 200, {"pairs": []})}
    if chain == "solana":
        routes["https://api.rugcheck.xyz/v1/tokens/" + address + "/report"] = (
            "sell", 200, fixtures._load("rc_bonk.json"))
    else:
        routes["https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"] = (
            "sell", 200, copy.deepcopy(fixtures._T084_HP))
    return routes


def test_token2022_transfer_fee_preserves_each_period_and_exact_caps_at_public_routes():
    import test_risk as fixtures

    u64_max = 2**64 - 1

    def period(rate, cap):
        return {"transferFeeBasisPoints": rate, "maximumFee": cap}

    bern = _load("rc_bern.json")
    report_fee = bern["token_extensions"]["transferFeeConfig"]
    cases = [
        ("recorded BERN", report_fee["olderTransferFee"], report_fee["newerTransferFee"],
         [420, 269], [3906250000000000000] * 2, "info"),
        ("full u64 and exact decimal string", period(10000, u64_max), period("501", str(2**53 + 1)),
         [10000, 501], [u64_max, 2**53 + 1], "critical"),
        ("invalid cap and a zero cap", period(5000, "missing"), period(5000, 0),
         [5000, 5000], [None, 0], "critical"),
        ("invalid rate and a zero rate", period("missing", 100), period(0, 0),
         [None, 0], [100, 0], "warn"),
        ("omitted period and readable high rate", None, period(5000, 900),
         [None, 5000], [None, 900], "critical"),
        ("wrong period type and a readable high rate", period(5000, 900), [0, 0],
         [5000, None], [900, None], "critical"),
        ("omitted values", {"maximumFee": 0}, {"transferFeeBasisPoints": 0},
         [None, 0], [0, None], "warn"),
        ("complete zero rates", period(0, None), period("0", None),
         [0, 0], [None, None], "info"),
        ("complete zero caps", period(5000, "0"), period(7500, 0),
         [5000, 7500], [0, 0], "info"),
        ("20 percent boundary", period(2000, 1), period(500, 3), [2000, 500], [1, 3], "warn"),
        ("5 percent boundary", period(500, 1), period(0, 1), [500, 0], [1, 1], "info"),
    ]
    for invalid in (True, -1, 1.5, 10001, "10001", "0.0", "1e-5000", float("inf"), float("nan")):
        cases.append(("invalid basis points %r" % invalid, period(invalid, 100), period(5000, 100),
                      [None, 5000], [100, 100], "critical"))
    for invalid in (True, -1, 1.5, 2**64, str(2**64), "9" * 50, "0.0", "1e-5000", float("inf"), float("nan")):
        cases.append(("invalid cap %r" % invalid, period(5000, 0), period(5000, invalid),
                      [5000, 5000], [0, None], "critical"))

    bonk_rows = _load("ds_bonk.json")["pairs"]
    bern_row = copy.deepcopy(bonk_rows[0])
    bern_row["baseToken"]["address"] = fixtures.BERN
    bern_row["baseToken"]["symbol"] = "SAME"
    for interface, verbose in (("mcp", False), ("mcp", True), ("http", False), ("http", True)):
        bonk_routes = _price_attribution_routes(fixtures.BONK, "solana", bonk_rows)
        bonk_routes["https://api.dexscreener.com/latest/dex/search?q=Bonk"] = ("search", 200, {"pairs": []})
        bonk, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
            {"address": fixtures.BONK, "chain_hint": "solana", "verbose": verbose}, bonk_routes)
        check("T106 ordinary BONK makes no transfer-fee claim or extra request",
              not any(s["category"] == "sell_tax" for s in bonk.get("signals", []))
              and "transfer_fee_bps" not in bonk.get("evidence", {}).get("token2022", {})
              and calls == ["market", "search", "sell"] and not sleeps, str(calls))

        for name, older, newer, rates, caps, severity in cases:
            report = copy.deepcopy(bern)
            config = report["token_extensions"]["transferFeeConfig"]
            for key, value in (("olderTransferFee", older), ("newerTransferFee", newer)):
                if value is None:
                    config.pop(key)
                else:
                    config[key] = value
            routes = _price_attribution_routes(fixtures.BERN, "solana", [bern_row])
            routes["https://api.rugcheck.xyz/v1/tokens/" + fixtures.BERN + "/report"] = ("sell", 200, report)
            tag = "T106 %s/%s %s" % (interface, verbose, name)
            try:
                answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                    {"address": fixtures.BERN, "chain_hint": "solana", "verbose": verbose}, routes)
            except json.JSONDecodeError:
                check(tag + " returns a JSON assessment", False, "MCP returned an error instead of a JSON assessment")
                continue
            evidence = answer.get("evidence", {})
            fee = evidence.get("token2022", {})
            exact = [str(cap) if cap is not None else None for cap in caps]
            check(tag + " retains each period's independently valid rate and exact cap",
                  fee.get("transfer_fee_bps") == rates and fee.get("transfer_fee_max_raw_exact") == exact,
                  str(fee))
            check(tag + " legacy numeric caps are exact and only present for two valid caps",
                  ("transfer_fee_max_raw" not in fee if None in caps else
                   fee.get("transfer_fee_max_raw") == caps and
                   all(type(cap) is int for cap in fee["transfer_fee_max_raw"])), str(fee))
            tax = [s for s in answer.get("signals", []) if s["category"] == "sell_tax"]
            detail = tax[0]["message"].lower() if tax else ""
            check(tag + " keeps the appropriate transfer-fee signal and existing request budget",
                  len(tax) == 1 and tax[0]["severity"] == severity and "simulat" not in detail
                  and calls == ["market", "search", "sell"] and not sleeps, str((tax, calls)))
            if None in rates or (None in caps and any(rates)):
                check(tag + " incomplete evidence does not assert a live rate or a fee bound",
                      bool(detail) and "up to" not in detail and "no transfer pays" not in detail
                      and "measured at 0" not in detail
                      and ("rate" in detail if None in rates else "cap" in detail), detail)
            if name in ("complete zero rates", "complete zero caps"):
                check(tag + " asserts zero only for the complete zero schedule",
                      "0.00%" in detail if name == "complete zero rates" else "no transfer pays" in detail, detail)


def _price_attribution_compare(name, address, chain, routes, expected, interface, verbose):
    """Use real Worker routes and preserve the existing scoring of genuine base facts."""
    control = copy.deepcopy(routes)
    for _, _, body in control.values():
        for row in body.get("pairs", []) or []:
            row.pop("priceChange", None)
        for row in body.get("data", []) or []:
            row.get("attributes", {}).pop("price_change_percentage", None)
    args = {"address": address, "chain_hint": chain, "verbose": verbose}
    with patch.object(risk, "_now_iso", lambda: "2026-11-19T00:00:00Z"):
        before = _t092_public_market(interface, "assess_token_risk", args, control)
        after = _t092_public_market(interface, "assess_token_risk", args, routes)
    answer = after[0]
    evidence = answer["evidence"]
    tag = "Price attribution %s %s %s" % (name, interface, verbose)
    # Existing formatting keeps two significant digits, not two decimal places.
    displayed = {12.34: 12.0, -49.99: -50.0}.get(expected, expected)
    check(tag + " reports only the queried declared base change",
          ("price_change_24h_pct" in evidence) is (expected is not None)
          and evidence.get("price_change_24h_pct") == displayed, str(evidence.get("price_change_24h_pct")))
    sharp = [s for s in answer["signals"] if s["name"] == "Price is sharply down today"]
    check(tag + " preserves the original inclusive drop threshold",
          bool(sharp) is (expected is not None and expected <= -50)
          and all(s["severity"] == "info" for s in sharp))
    stripped = copy.deepcopy(answer)
    stripped["evidence"].pop("price_change_24h_pct", None)
    stripped["signals"] = [s for s in stripped["signals"] if s["name"] != "Price is sharply down today"]
    check(tag + " changes no other response, scoring, request, cache or retry", stripped == before[0]
          and after[1:] == before[1:])
    return answer


def test_price_change_attribution_crosses_actual_assessment_routes():
    import test_risk as fixtures
    base, quote = "0x" + "ab" * 20, fixtures.USDC
    pool = {"chainId": "ethereum", "dexId": "uniswap", "pairAddress": "0x" + "cd" * 20,
            "baseToken": {"address": base, "symbol": "SAME"},
            "quoteToken": {"address": quote, "symbol": "SAME"},
            "priceUsd": "1", "priceNative": "1", "liquidity": {"usd": 200000},
            "volume": {"h24": 100000}, "pairCreatedAt": 1600000000000,
            "txns": {"h24": {"buys": 100, "sells": 100}}, "priceChange": {"h24": -62}}
    missing = copy.deepcopy(pool)
    missing["baseToken"].pop("address")
    sol = copy.deepcopy(pool)
    sol.update(chainId="solana", baseToken={"address": fixtures.BONK, "symbol": "SAME"},
               quoteToken={"address": "So11111111111111111111111111111111111111112", "symbol": "SAME"})
    mismatched_sol = copy.deepcopy(sol)
    mismatched_sol["baseToken"]["address"] = "d" + fixtures.BONK[1:]
    mismatched_sol["quoteToken"]["address"] = fixtures.BONK
    cases = [("same-ticker quote", quote, pool, None), ("missing base", quote, missing, None),
             ("EVM mixed case base", "0x" + "Ab" * 20, pool, -62),
             ("Solana exact base", fixtures.BONK, sol, -62),
             ("Solana case-distinct quote", fixtures.BONK, mismatched_sol, None)]
    for value in (0, 12.34, -49.99, -50):
        changed = copy.deepcopy(pool)
        changed["priceChange"]["h24"] = value
        cases.append(("base change %s" % value, base, changed, value))
    for name, address, row, expected in cases:
        chain = row["chainId"]
        routes = _price_attribution_routes(address, chain, [row])
        for interface in ("mcp", "http"):
            for verbose in (False, True):
                answer = _price_attribution_compare(name, address, chain, routes, expected, interface, verbose)
                if verbose:
                    check("Price attribution keeps the same selected pool", answer["evidence"]["best_pair"]["pair_address"]
                          == row["pairAddress"])


def test_price_change_attribution_gecko_fallback_and_market_replacement():
    import test_risk as fixtures
    raw = fixtures._load("gt_weth_anchor_pools.json")["data"][0]
    # Synthetic drop, not a measured historical return.
    raw["attributes"]["price_change_percentage"]["h24"] = "-62"
    base = raw["relationships"]["base_token"]["data"]["id"].split("_", 1)[1]
    quote = raw["relationships"]["quote_token"]["data"]["id"].split("_", 1)[1]
    cases = [("fallback base", base, raw, -62), ("fallback quote", quote, raw, None)]
    for mutation in ("missing", "cross-network"):
        invalid = copy.deepcopy(raw)
        if mutation == "missing":
            invalid["relationships"].pop("base_token")
        else:
            invalid["relationships"]["base_token"]["data"]["id"] = "base_" + base
        cases.append(("fallback " + mutation, base, invalid, None))
    for name, address, row, expected in cases:
        routes = _price_attribution_routes(address, "ethereum", [row], fallback=True)
        routes["https://api.dexscreener.com/latest/dex/search?q=USDC"] = ("search", 200, {"pairs": []})
        for verbose in (False, True):
            _price_attribution_compare(name, address, "ethereum", routes, expected, "mcp", verbose)
    address, _, _, markets = _t092_market_cases()
    for name, routes, _, _, _, final, _ in markets:
        routes = copy.deepcopy(routes)
        for row in routes[fixtures._t083_market_url("eth", address)][2]["data"]:
            row["attributes"]["price_change_percentage"]["h24"] = "-62"
        expected = -62 if final == fixtures._T084_USDC_POOL else None
        for verbose in (False, True):
            answer = _price_attribution_compare(name, address, "ethereum", routes, expected, "mcp", verbose)
            if verbose:
                check("Price attribution follows the final market, including rejected promotion",
                      answer["evidence"]["best_pair"]["pair_address"] == final)


def test_price_change_attribution_legacy_normalization_cannot_invent_base():
    import test_risk as fixtures
    raw = fixtures._load("gt_weth_anchor_pools.json")["data"][0]
    raw["attributes"]["price_change_percentage"]["h24"] = "-62"
    for relation in (None, "base_" + fixtures.WETH, "eth_not-an-address"):
        row = copy.deepcopy(raw)
        row["relationships"]["base_token"] = {"data": {"id": relation}}
        pair = risk._gt_to_pair(row, fixtures.WETH, "eth")
        signals, evidence = [], {}
        risk._liquidity_signals(pair, [pair], signals, evidence, target=fixtures.WETH)
        check("Price attribution legacy query-derived or cross-network base stays unconfirmed",
              "price_change_24h_pct" not in evidence
              and not any(s["name"] == "Price is sharply down today" for s in signals))


def test_price_change_attribution_disclosure_does_not_count_as_safety_evidence():
    import test_risk as fixtures
    with patch.object(sys, "path", [os.path.join(FIXTURES, "..", "..", "bench"), *sys.path]):
        import run_benchmark as benchmark
    address = fixtures.WETH.lower()
    for kind in ("confidence boundary", "other lifecycle warning", "unknown sellability"):
        raw = fixtures._load("gt_weth_anchor_pools.json")["data"][0]
        raw["attributes"].pop("pool_created_at", None)
        raw["attributes"]["price_change_percentage"]["h24"] = "-62"
        if kind == "other lifecycle warning":
            raw["attributes"]["volume_usd"]["h24"] = "1"
        routes = _price_attribution_routes(address, "ethereum", [raw], fallback=True)
        sell = next(url for url, (label, _, _) in routes.items() if label == "sell")
        routes[sell][2].pop("contractCode", None)
        if kind == "unknown sellability":
            routes[sell] = ("sell", 404, {})
        for verbose in (False, True):
            answer = _price_attribution_compare(kind, address, "ethereum", routes, -62, "mcp", verbose)
            signals = answer["signals"]
            without = [s for s in signals if s["name"] != "Price is sharply down today"]
            gaps = answer["evidence"].get("data_gaps")
            check("Price disclosure never drives the independent benchmark or its ablation",
                  benchmark.driving_category(signals) == benchmark.driving_category(without)
                  and benchmark.ablate(address, signals, gaps) == benchmark.ablate(address, without, gaps))
            if kind == "confidence boundary":
                check("Three safety facts plus a price note still have medium confidence",
                      len(without) == 3 and answer["confidence"] == "medium"
                      and answer["risk_score"] == 0 and answer["driver"] is None)
            elif kind == "other lifecycle warning":
                check("An actual lifecycle warning keeps its original risk weight",
                      any(s["category"] == "lifecycle" and s["severity"] == "warn" for s in without)
                      and answer["risk_score"] == 12 and answer["driver"]["category"] == "lifecycle")
            else:
                check("A price disclosure cannot close unknown sellability",
                      answer["risk_level"] == "unknown" and answer["confidence"] == "low"
                      and any(g["dimension"] == "sellability" for g in gaps))


def test_price_change_attribution_disclosure_alone_remains_unknown():
    import test_risk as fixtures
    raw = fixtures._load("gt_weth_anchor_pools.json")["data"][0]
    raw["attributes"]["price_change_percentage"]["h24"] = "-62"
    pair = risk._gt_to_pair(raw, fixtures.WETH, "eth")
    emitted = []
    risk._liquidity_signals(pair, [pair], emitted, {}, target=fixtures.WETH)
    price_only = [s for s in emitted if s["name"] == "Price is sharply down today"]
    empty = risk._finalize(fixtures.WETH, [], {}, [])
    answer = risk._finalize(fixtures.WETH, price_only, {}, [])
    check("A real emitted price note is still visible without safety observations", len(price_only) == 1
          and answer["signals"] == price_only)
    stripped = copy.deepcopy(answer)
    stripped["signals"] = []
    check("A price note alone preserves the exact unknown empty-evidence response", stripped == empty)


def test_liquidity_selected_pool_activity_and_complete_identity_cross_both_routes():
    import test_risk as fixtures
    token = fixtures.WETH.lower()
    pool = "0x" + "AB" * 32
    pair = {"chainId": "ethereum", "dexId": "uniswap", "pairAddress": pool,
            "baseToken": {"address": token, "symbol": "WETH"},
            "quoteToken": {"address": "0x" + "1" * 40},
            "priceUsd": "1", "liquidity": {"usd": 100000},
            "txns": {"h24": {"buys": 30, "sells": 20}}}
    other = copy.deepcopy(pair)
    other.update(pairAddress="0x" + "cd" * 20, liquidity={"usd": 100})
    other["txns"].update(h1={"buys": 90, "sells": 90}, h6={"buys": 100, "sells": 100})
    maximum = 2**53 - 1
    readings = [
        ({"h1": {"buys": 2, "sells": 3}, "h6": {"buys": 11, "sells": 13}},
         {"trades_last_1h": 5, "trades_prior_5h": 19}),
        ({"h1": {"buys": 0, "sells": 0}, "h6": {"buys": 0, "sells": 0}},
         {"trades_last_1h": 0, "trades_prior_5h": 0}),
        ({}, None),
        ({"h1": {"buys": 1, "sells": 1}}, None),
        ({"h1": {"buys": 2, "sells": 0}, "h6": {"buys": 1, "sells": 3}}, None),
        ({"h1": {"buys": True, "sells": 0}, "h6": {"buys": 1, "sells": 0}}, None),
        ({"h1": {"buys": 1.0, "sells": 0}, "h6": {"buys": 1, "sells": 0}}, None),
        ({"h1": {"buys": 0, "sells": 0}, "h6": {"buys": "4", "sells": 0}}, None),
        ({"h1": {"buys": 0, "sells": 0}, "h6": {"buys": -1, "sells": 0}}, None),
        ({"h1": {"buys": maximum, "sells": 1},
          "h6": {"buys": maximum, "sells": 1}}, None),
    ]
    for interface in ("http", "mcp"):
        for windows, expected in readings:
            selected = copy.deepcopy(pair)
            selected["txns"].update(windows)
            routes = {fixtures._T083_DS + token: ("market", 200, {"pairs": [selected, other]})}
            answer, calls, _, sleeps, _ = _t092_public_market(
                interface, "get_token_liquidity", {"address": token, "chain_hint": "ethereum"}, routes)
            check("liquidity keeps the selected full 32-byte EVM pool identity",
                  answer.get("best_pair_address") == pool)
            check("liquidity reports only complete raw integer windows from its selected pool",
                  answer.get("trade_activity") == expected
                  and ("trade_activity" in answer) is (expected is not None))
            check("activity disclosure preserves provider, selection, estimates and request budget",
                  answer["source"] == "dexscreener" and answer["liquidity_usd"] == 100000
                  and calls == ["market"] and not sleeps)


def test_liquidity_gt_activity_and_conflicting_identity_remain_same_row():
    import test_risk as fixtures
    token, pool, _, cases = _t092_market_cases()
    for interface in ("http", "mcp"):
        for value, expected in (
                ({"h1": {"buys": 2, "sells": 3}, "h6": {"buys": 11, "sells": 13}},
                 {"trades_last_1h": 5, "trades_prior_5h": 19}),
                ({"h1": {"buys": 0, "sells": 0}, "h6": {"buys": 0, "sells": 0}},
                 {"trades_last_1h": 0, "trades_prior_5h": 0}),
                ({"h1": {"buys": 1.0, "sells": 0}, "h6": {"buys": 1, "sells": 0}}, None),
                ({}, None)):
            routes = copy.deepcopy(cases[0][1])
            rows = next(body["data"] for label, _, body in routes.values() if label == "fallback")
            for row in rows:
                row["attributes"]["transactions"].update(value if row["attributes"]["address"].lower() == pool
                    else {"h1": {"buys": 99, "sells": 99}, "h6": {"buys": 100, "sells": 100}})
            answer, calls, _, sleeps, _ = _t092_public_market(
                interface, "get_token_liquidity", {"address": token, "chain_hint": "ethereum"}, routes)
            check("GT fallback preserves raw integer windows for the actual selected venue",
                  answer.get("best_pair_address") == pool and answer.get("trade_activity") == expected
                  and ("trade_activity" in answer) is (expected is not None))
            check("GT activity adds no source requests or simulator work",
                  calls == ["market", "fallback"] and not sleeps and answer["source"] == "geckoterminal")

        routes = copy.deepcopy(cases[0][1])
        rows = next(body["data"] for label, _, body in routes.values() if label == "fallback")
        selected = next(row for row in rows if row["attributes"]["address"].lower() == pool)
        selected["id"] = "eth_0x" + "de" * 32
        rows[:] = [selected]
        answer, _, _, _, _ = _t092_public_market(
            interface, "get_token_liquidity", {"address": token, "chain_hint": "ethereum"}, routes)
        check("conflicting GT resource and address cannot identify a comparable pool",
              answer["status"] == "ok" and "best_pair_address" not in answer)

        solana_pair = _load("ds_bonk.json")["pairs"][0]
        mint = solana_pair["baseToken"]["address"]
        routes = {fixtures._T083_DS + mint: ("market", 200, {"pairs": [solana_pair]})}
        answer, _, _, _, _ = _t092_public_market(
            interface, "get_token_liquidity", {"address": mint, "chain_hint": "solana"}, routes)
        check("Solana selected identity keeps its complete case and original window counts",
              answer.get("best_pair_address") == solana_pair["pairAddress"]
              and answer.get("trade_activity") == {"trades_last_1h": 384, "trades_prior_5h": 3886})


def test_liquidity_complete_pool_identity_validates_gt_aliases_and_solana_bytes():
    import test_risk as fixtures
    token, pool, _, cases = _t092_market_cases()
    full = "0x" + "Ab" * 32
    for interface in ("http", "mcp"):
        routes = copy.deepcopy(cases[0][1])
        rows = next(body["data"] for label, _, body in routes.values() if label == "fallback")
        selected = next(row for row in rows if row["attributes"]["address"].lower() == pool)
        rows[:] = [selected]
        selected.update(id="eth_" + full.lower())
        selected["attributes"]["address"] = full
        answer, _, _, _, _ = _t092_public_market(
            interface, "get_token_liquidity", {"address": token, "chain_hint": "ethereum"}, routes)
        check("matching 32-byte GT aliases preserve complete original EVM hex case",
              answer.get("best_pair_address") == full)

        pair = _load("ds_bonk.json")["pairs"][0]
        mint = pair["baseToken"]["address"]
        for invalid in ("z" * 44, pair["pairAddress"] + "\n", "not-a-pool", "0x" + "ab" * 32):
            market = copy.deepcopy(pair)
            market["pairAddress"] = invalid
            routes = {fixtures._T083_DS + mint: ("market", 200, {"pairs": [market]})}
            answer, _, _, _, _ = _t092_public_market(
                interface, "get_token_liquidity", {"address": mint, "chain_hint": "solana"}, routes)
            check("invalid or wrong-size Solana identity is omitted without changing the estimate",
                  answer["status"] == "ok" and "best_pair_address" not in answer
                  and answer["liquidity_usd"] == 78588.0)

        raw = {"id": "solana_" + pair["quoteToken"]["address"],
               "attributes": {"address": pair["pairAddress"], "name": "BONK / SOL",
                              "base_token_price_usd": "1", "reserve_in_usd": "100000"},
               "relationships": {
                   "base_token": {"data": {"id": "solana_" + mint}},
                   "quote_token": {"data": {"id": "solana_" + pair["quoteToken"]["address"]}}}}
        routes = {fixtures._T083_DS + mint: ("market", 200, {"pairs": []}),
                  fixtures._t083_market_url("solana", mint): ("fallback", 200, {"data": [raw]})}
        answer, _, _, _, _ = _t092_public_market(
            interface, "get_token_liquidity", {"address": mint, "chain_hint": "solana"}, routes)
        check("a Solana GT row with contradictory complete identities cannot support comparison",
              answer["status"] == "ok" and "best_pair_address" not in answer)


def test_liquidity_gt_invalid_resource_and_duplicate_identity_are_omitted():
    import test_risk as fixtures
    token, pool, _, cases = _t092_market_cases()
    evm = next(row for label, _, body in cases[0][1].values() if label == "fallback"
               for row in body["data"] if row["attributes"]["address"].lower() == pool)
    pair = _load("ds_bonk.json")["pairs"][0]
    mint = pair["baseToken"]["address"]
    solana = {"id": "solana_" + pair["pairAddress"],
              "attributes": {"address": pair["pairAddress"], "name": "BONK / SOL",
                             "base_token_price_usd": "1", "reserve_in_usd": "100000"},
              "relationships": {
                  "base_token": {"data": {"id": "solana_" + mint}},
                  "quote_token": {"data": {"id": "solana_" + pair["quoteToken"]["address"]}}}}
    for interface in ("http", "mcp"):
        for chain, network, address, row, second_address in (
                ("ethereum", "eth", token, evm, "0x" + "de" * 20),
                ("solana", "solana", mint, solana, pair["quoteToken"]["address"])):
            for bad_id in (False, None, 0, ""):
                broken = copy.deepcopy(row)
                broken["id"] = bad_id
                routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": []}),
                          fixtures._t083_market_url(network, address): ("fallback", 200, {"data": [broken]})}
                answer, _, _, _, _ = _t092_public_market(interface, "get_token_liquidity",
                    {"address": address, "chain_hint": chain}, routes)
                check("an explicitly invalid GT resource cannot borrow a comparable address",
                      answer["status"] == "ok" and "best_pair_address" not in answer)
            duplicate = copy.deepcopy(row)
            duplicate["attributes"].update(address=second_address, reserve_in_usd="1")
            routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": []}),
                      fixtures._t083_market_url(network, address): ("fallback", 200, {"data": [row, duplicate]})}
            answer, _, _, _, _ = _t092_public_market(interface, "get_token_liquidity",
                {"address": address, "chain_hint": chain}, routes)
            check("batch-level duplicate pool identity remains ambiguous on the selected market",
                  answer["status"] == "ok" and "best_pair_address" not in answer)


def test_liquidity_tools_list_exposes_optional_activity_and_complete_identity():
    tools = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    liquidity = next(tool for tool in tools if tool["name"] == "get_token_liquidity")
    input_context = liquidity["inputSchema"]["properties"]["comparison_context"]
    output_context = liquidity["outputSchema"]["properties"]["comparison_context"]
    observation = input_context["items"]
    check("both MCP context schemas admit drained with a numeric zero only",
          input_context == output_context and observation["properties"]["status"]["enum"] == ["ok", "drained"]
          and observation.get("if", {}).get("properties", {}).get("status") == {"const": "drained"}
          and observation.get("then", {}).get("properties", {}).get("liquidity_usd") == {"const": 0})
    description = liquidity["description"]
    check("tool text scopes drained to estimates and identifies the narrower provider zero",
          "estimates for the returned market scope are zero" in description
          and "single pool whose provider reported zero" in description
          and "nothing to sell into" not in description)
    schema = liquidity["outputSchema"]
    fields = schema["properties"]
    activity = fields.get("trade_activity", {})
    check("liquidity declares the two optional integer activity windows",
          "trade_activity" not in schema["required"]
          and set(activity.get("required", [])) == {"trades_last_1h", "trades_prior_5h"}
          and all(value.get("type") == "integer" for value in activity.get("properties", {}).values()))
    check("the public liquidity contract names complete identity and cached reply time",
          "complete" in fields["best_pair_address"]["description"]
          and "32-byte" in fields["best_pair_address"]["description"]
          and "Reply time" in fields["checked_at"]["description"]
          and "cached" in fields["checked_at"]["description"])
    check("liquidity preserves snapshot inputs and adds bounded optional comparison context",
          set(liquidity["inputSchema"]["properties"]) == {"address", "chain_hint", "comparison_context"}
          and liquidity["inputSchema"]["required"] == ["address"]
          and liquidity["inputSchema"]["properties"]["comparison_context"].get("maxItems") == 8)


def test_assessment_complete_market_ids_match_liquidity_and_separate_shared_prefixes():
    import test_risk as fixtures

    pool_a = "0x" + "Ab" * 32
    pool_b = pool_a[:-2] + "cD"
    pool_20 = "0x" + "fE" * 20
    assert pool_a[:48] == pool_b[:48]
    for interface in ("http", "mcp"):
        for pool in (pool_a, pool_b, pool_20):
            pair = fixtures._t030_pair(100000, reserves=False)
            pair["pairAddress"] = pool
            address = pair["baseToken"]["address"]
            sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address + "&chainID=1"
            routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": [pair]}),
                      sell: ("default", 200, fixtures._t092_report(pool_20))}
            args = {"address": address, "chain_hint": "ethereum"}
            liquidity, _, _, _, _ = _t092_public_market(interface, "get_token_liquidity", args, routes)
            for verbose in (False, True):
                answer, calls, _, sleeps, _ = _t092_public_market(interface, "assess_token_risk",
                    dict(args, verbose=verbose), routes)
                evidence = answer["evidence"]
                market = evidence["best_pair"]
                check("assessment has exactly the full market identity used by liquidity",
                      market.get("pool_id") == liquidity["best_pair_address"] == pool
                      and calls == ["market", "default"] and not sleeps
                      and evidence["pool_link"] == ("same" if pool == pool_20 else "different"), str(market))
                if verbose:
                    detail = evidence["pool_link_details"]
                    check("verbose keeps the legacy display and separates the full market and reported venue",
                          market["pair_address"] == risk._ascii_safe(pool, 48)
                          and detail["market_pool"] == pool
                          and detail["reported_pool"] == pool_20.lower(), str(detail))
                else:
                    check("compact still omits the old display ID", "pair_address" not in market)


def test_assessment_does_not_adopt_or_query_an_ambiguous_gecko_market_identity():
    import test_risk as fixtures

    token, pool, _, cases = _t092_market_cases()
    for kind in ("conflict", "duplicate"):
        for response in ("clean", "failed", "contested", "claimed_sellers"):
            routes = copy.deepcopy(cases[0][1])
            rows = next(body["data"] for label, _, body in routes.values() if label == "fallback")
            row = next(item for item in rows if item["attributes"]["address"].lower() == pool)
            rows[:] = [row]
            if kind == "conflict":
                row["id"] = "eth_0x" + "cd" * 20
            else:
                rows.append(copy.deepcopy(row))
            for item in rows:
                item["attributes"]["transactions"]["h24"].pop("sellers", None)
            sell = next(url for url, (label, _, _) in routes.items() if label == "default")
            hp = fixtures._t092_report(pool)
            hp["simulationResult"]["maxSell"] = {"tokenWei": "996"}
            if response == "failed":
                hp.update(simulationSuccess=False, simulationError="execution reverted: HP: BUY_FAILED")
                routes[sell + "&pair=" + pool] = ("unqualified_retry", 200, fixtures._t092_report(pool))
            elif response in ("contested", "claimed_sellers"):
                hp["honeypotResult"]["isHoneypot"] = True
                routes[fixtures._T083_GT + "eth/pools/" + pool] = ("unqualified_sellers", 404, {})
                if response == "claimed_sellers":
                    for item in rows:
                        item["attributes"]["transactions"]["h24"]["sellers"] = 120
            routes[sell] = ("default", 200, hp)
            answer, calls, _, sleeps, _ = _t092_public_market("mcp", "assess_token_risk",
                {"address": token, "chain_hint": "ethereum", "verbose": True}, routes)
            evidence = answer["evidence"]
            check("an ambiguous Gecko ID cannot appear as qualified or be used for a pool operation",
                  "pool_id" not in evidence["best_pair"] and "max_sell" not in evidence
                  and evidence.get("pool_link") == "unknown"
                  and evidence["pool_link_details"]["reason"] == "invalid_pool"
                  and evidence["pool_link_details"]["market_pool"] is None
                  and calls == ["market", "fallback", "search", "default"] and not sleeps,
                  str((kind, response, evidence.get("pool_link_details"), calls)))
            if response == "claimed_sellers":
                check("embedded seller counts cannot qualify a contradicted market ID",
                      evidence["best_pair"].get("sellers_24h") is None
                      and "contradicted_by_chain" not in evidence.get("honeypot", {}))


def test_assessment_solana_market_identity_is_case_sensitive_and_complete():
    raw = _load("ds_bonk.json")["pairs"][0]
    address = raw["baseToken"]["address"]
    valid = raw["pairAddress"]
    for value, expected in ((valid, valid), ("z" * 44, None), (valid + "\n", None), ("0x" + "ab" * 32, None)):
        pair = copy.deepcopy(raw)
        pair["baseToken"]["symbol"] = "SAME"
        pair["pairAddress"] = value
        args = {"address": address, "chain_hint": "solana", "verbose": True}
        answer, calls, _, _, _ = _t092_public_market("mcp", "assess_token_risk", args,
            _price_attribution_routes(address, "solana", [pair]))
        evidence = answer["evidence"]
        check("Solana complete IDs preserve case and omit malformed or wrong-family values",
              evidence["best_pair"].get("pool_id") == expected
              and evidence["pool_link_details"]["market_pool"] == expected
              and evidence["pool_link"] == "unknown" and "sell" in calls, str(evidence["best_pair"]))


def test_assessment_requires_a_market_chain_and_pool_before_using_sellers():
    import test_risk as fixtures

    pool = "0x" + "de" * 20
    pair = fixtures._t030_pair(250000, reserves=False)
    pair["txns"]["h24"] = {"buys": 250, "sells": 200}
    pair["traders"] = {"h24": {"sellers": 170}}
    address = pair["baseToken"]["address"]
    hp = fixtures._t092_report(pool)
    hp["honeypotResult"]["isHoneypot"] = True
    hp["holderAnalysis"] = {"holders": "400", "failed": "4", "siphoned": "0", "successful": "396"}
    sell = "https://api.honeypot.is/v2/IsHoneypot?address=" + address
    for chain in ("ethereum", "sui", None):
        for address_field in ("pairAddress", "pool_id", None):
            market = {key: value for key, value in pair.items() if key not in ("chainId", "pairAddress")}
            if chain is not None:
                market["chainId"] = chain
            if address_field is not None:
                market[address_field] = pool
            routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": [market]}),
                      sell + "&chainID=1": ("default", 200, hp),
                      sell: ("unscoped", 200, hp)}
            if chain is None:
                for network in ("eth", "base", "bsc", "polygon_pos"):
                    routes[fixtures._T083_GT + network + "/tokens/" + address + "/pools"] = ("fallback", 404, {})
            answer, calls, _, _, _ = _t092_public_market("mcp", "assess_token_risk",
                {"address": address, "verbose": True}, routes)
            evidence = answer["evidence"]
            best = evidence.get("best_pair", {})
            context = str((chain, address_field, best, calls))
            if chain == "ethereum" and address_field == "pairAddress":
                check("identified market can retain its reported distinct sellers",
                      best.get("pool_id") == pool and best.get("sellers_24h") == 170
                      and "contradicted_by_chain" in evidence.get("honeypot", {}), context)
            else:
                check("missing or unqualified identity cannot establish seller corroboration",
                      "pool_id" not in best and best.get("sellers_24h") is None
                      and evidence["pool_link_details"]["market_pool"] is None
                      and "contradicted_by_chain" not in evidence.get("honeypot", {})
                      and answer["risk_level"] != "low", context)


def _liquidity_comparison_module():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "examples" / "liquidity_compare.py"
    check("the runnable saved-liquidity example exists", path.is_file())
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("liquidity_comparison_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(path.parent), *sys.path]), _a2_no_effects():
        spec.loader.exec_module(module)
    return module


def test_saved_liquidity_example_compares_only_compatible_estimates():
    module = _liquidity_comparison_module()
    if module is None:
        return
    before = {"status": "ok", "address": "0x" + "ab" * 20, "best_pair_chain": "ethereum",
              "best_pair_address": "0x" + "cd" * 32, "source": "dexscreener",
              "liquidity_usd": 100, "checked_at": "2026-11-20T00:00:00Z"}
    after = dict(before, liquidity_usd=125, checked_at="2026-11-20T00:10:00Z")
    for start, end, change in ((100, 125, 25), (125, 100, -25), (0, 0, 0), (100, 0, -100)):
        first, second = dict(before, liquidity_usd=start), dict(after, liquidity_usd=end)
        saved = copy.deepcopy((first, second))
        result = _a2_call(module.compare, first, second)
        check("saved same-pool estimates yield their USD change including genuine zero",
              result == {"status": "compared", "before_usd": start, "after_usd": end, "change_usd": change})
        check("comparison never mutates the two saved responses", (first, second) == saved)
    case_variant = dict(after, address="0x" + "AB" * 20, best_pair_address="0x" + "CD" * 32)
    check("complete EVM hex identities compare case-insensitively",
          _a2_call(module.compare, before, case_variant).get("status") == "compared")
    reasons = [
        (dict(after, source="geckoterminal"), "different_source"),
        (dict(after, best_pair_address="0x" + "ef" * 32), "different_pool"),
        (dict(after, best_pair_chain="base"), "different_pool"),
        (dict(after, address="0x" + "ef" * 20), "different_pool"),
        (dict(after, served_stale=[{"source": "api.dexscreener.com", "age_seconds": 900}]), "stale_response"),
        (dict(after, checked_at=before["checked_at"]), "invalid_order"),
        (dict(after, checked_at="2026-11-19T23:59:59Z"), "invalid_order"),
        (dict(after, checked_at="2026-11-20T00:10:00"), "invalid_time"),
        (dict(after, checked_at="2026-11-20T00:10:00-00:63"), "invalid_time"),
        (dict(after, checked_at="2026-11-20T00:10:00+01:60"), "invalid_time"),
        (dict(after, checked_at="20261120T001000Z"), "invalid_time"),
        (dict(after, checked_at="2026-11-20T00:10:00-00:00"), "invalid_time"),
        (dict(after, best_pair_address="0x" + "c" * 48 + "..."), "invalid_identity"),
        (dict(after, best_pair_address="0x" + "cd" * 31), "invalid_identity"),
        (dict(after, best_pair_address=None), "invalid_identity"),
        (dict(after, source=""), "invalid_source"),
        (dict(after, status="drained"), "unusable_response"),
        (dict(after, liquidity_usd=True), "invalid_amount"),
        (dict(after, liquidity_usd="125"), "invalid_amount"),
        (dict(after, liquidity_usd=-1), "invalid_amount"),
        (dict(after, liquidity_usd=None), "invalid_amount"),
        (dict(after, liquidity_usd=float("inf")), "invalid_amount"),
        (dict(after, liquidity_usd=float("nan")), "invalid_amount"),
        (dict(after, liquidity_usd=10**400), "invalid_amount"),
    ]
    for second, reason in reasons:
        result = _a2_call(module.compare, before, second)
        check("noncomparable snapshots never fabricate USD change: " + reason,
              result == {"status": "not_comparable", "reason": reason})
    offset = dict(after, checked_at="2026-11-19T19:10:00-05:00")
    check("ordering uses timezone-aware instants, not timestamp text",
          _a2_call(module.compare, before, offset).get("status") == "compared")
    pair = _load("ds_bonk.json")["pairs"][0]
    sol_before = dict(before, address=pair["baseToken"]["address"], best_pair_chain="solana",
                      best_pair_address=pair["pairAddress"])
    sol_after = dict(sol_before, liquidity_usd=101, checked_at=after["checked_at"])
    check("a complete case-sensitive Solana pool can be compared",
          _a2_call(module.compare, sol_before, sol_after).get("change_usd") == 1)
    check("a changed Solana identity never becomes the same through lowercasing",
          _a2_call(module.compare, sol_before, dict(sol_after,
              best_pair_address=pair["pairAddress"].lower())).get("status") == "not_comparable")


def test_saved_liquidity_example_cli_reads_two_local_response_objects():
    module = _liquidity_comparison_module()
    if module is None:
        return
    from pathlib import Path
    import subprocess
    import tempfile
    pair = {"status": "ok", "address": "0x" + "1" * 40, "best_pair_chain": "base",
            "best_pair_address": "0x" + "2" * 40, "source": "geckoterminal",
            "liquidity_usd": 100, "checked_at": "2026-11-20T00:00:00Z"}
    with tempfile.TemporaryDirectory() as directory:
        first, second = Path(directory) / "before.json", Path(directory) / "after.json"
        first.write_text(json.dumps(pair), encoding="utf-8")
        second.write_text(json.dumps(dict(pair, liquidity_usd=80, checked_at="2026-11-20T00:10:00Z")),
                          encoding="utf-8")
        bootstrap = "\n".join([
            "import runpy,sys,socket,subprocess,time,urllib.request",
            "def blocked(*a,**k): raise AssertionError('effect_refused')",
            "socket.socket=blocked; socket.create_connection=blocked",
            "subprocess.Popen=blocked; time.sleep=blocked; urllib.request.urlopen=blocked",
            "sys.argv=sys.argv[1:]; from pathlib import Path",
            "sys.path.insert(0,str(Path(sys.argv[0]).parent)); runpy.run_path(sys.argv[0],run_name='__main__')"])
        args = [sys.executable, "-B", "-c", bootstrap, module.__file__, str(first), str(second)]
        run = subprocess.run(args, capture_output=True, timeout=20)
        check("the documented two-file CLI runs with network, sleep and subprocess effects forbidden",
              run.returncode == 0 and not run.stderr and json.loads(run.stdout) ==
              {"status": "compared", "before_usd": 100, "after_usd": 80, "change_usd": -20})
        second.write_text('{"liquidity_usd": NaN}', encoding="utf-8")
        run = subprocess.run(args, capture_output=True, timeout=20)
        check("invalid JSON input is refused without echoing private filenames or content",
              run.returncode == 1 and not run.stderr and json.loads(run.stdout) == {"error": "input_refused"})


def _native_liquidity_call(reading, context=None, *, legacy=False):
    from unittest.mock import AsyncMock
    args = {"address": reading.get("address", ""), "chain_hint": reading.get("best_pair_chain")}
    if not legacy:
        args["comparison_context"] = [] if context is None else context
    with patch.object(risk, "liquidity", AsyncMock(return_value=copy.deepcopy(reading))) as fetch:
        reply = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "get_token_liquidity", "arguments": args}})
    return reply, fetch


def test_native_liquidity_roundtrip_selects_latest_comparable_source_and_reports_pool_changes():
    readings = _load("liquidity_recheck.json")
    history = []
    answers = []
    for reading in readings:
        reply, fetch = _native_liquidity_call(reading, history)
        answer = reply["result"].get("structuredContent", {})
        check("native comparison fetches exactly one current snapshot", fetch.await_count == 1)
        check("native comparison returns bounded round-trippable context",
              type(answer.get("comparison_context")) is list and len(answer["comparison_context"]) <= 8)
        history = answer.get("comparison_context", [])
        answers.append(answer)
    check("first observation saves a baseline without inventing a prior reading",
          answers[0].get("comparison", {}).get("reason") == "no_previous_observation")
    check("the intervening provider observation is explicitly incomparable",
          answers[1].get("comparison", {}).get("reason") == "different_source"
          and "change_usd" not in answers[1].get("comparison", {}))
    result = answers[2].get("comparison", {})
    check("returning provider uses the original UTC baseline and signed estimate change",
          result.get("status") == "compared" and result.get("change_usd") == -366200
          and result.get("before_usd") == 86312200 and result.get("after_usd") == 85946000
          and result.get("before_checked_at") == readings[0]["checked_at"]
          and result.get("after_checked_at") == readings[2]["checked_at"]
          and result.get("baseline_origin") == "client_observation")
    changed = dict(readings[1], best_pair_address="0x" + "cd" * 32)
    reply, _ = _native_liquidity_call(changed, answers[0].get("comparison_context", []))
    middle = reply["result"].get("structuredContent", {})
    reply, _ = _native_liquidity_call(readings[2], middle.get("comparison_context", []))
    result = reply["result"].get("structuredContent", {}).get("comparison", {})
    check("returning to an older pool discloses both its older baseline and the latest pool change",
          result.get("change_usd") == -366200 and result.get("baseline_is_latest_observation") is False
          and result.get("pool_transition", {}).get("status") == "changed"
          and result.get("pool_transition", {}).get("previous_pool_address") == changed["best_pair_address"])
    only_changed, _ = _native_liquidity_call(changed, answers[0].get("comparison_context", []))
    result = only_changed["result"].get("structuredContent", {}).get("comparison", {})
    check("two different pools never produce a subtraction",
          result.get("reason") == "different_pool" and "change_usd" not in result)


def test_liquidity_checks_the_requested_network_before_returning_another_market():
    import test_risk as fixtures

    eth = fixtures._t030_pair(796872, reserves=False)
    bsc = fixtures._t030_pair(25000, reserves=False, chain="bsc")
    address = eth["baseToken"]["address"]
    bsc["pairAddress"] = "0x" + "bc" * 20
    ds = fixtures._T083_DS + address
    endpoint = "https://api.dexscreener.com/token-pairs/v1/"
    wrong_target = copy.deepcopy(bsc)
    wrong_target["baseToken"]["address"] = "0x" + "ee" * 20
    base_routes = {endpoint + "ethereum/" + address: ("wrong_network", 200, [])}
    for interface in ("http", "mcp"):
        for hint, count, pair, status in (
                ("bsc", 1, bsc, "ok"),
                ("bnb", 30, bsc, "ok"),
                ("bsc", 1, dict(bsc, liquidity={"usd": 0}), "drained"),
                ("bsc", 1, dict(bsc, liquidity={}), "unpriced")):
            routes = dict(base_routes)
            routes[ds] = ("market", 200, {"pairs": [eth] * count})
            routes[endpoint + "bsc/" + address] = ("bsc", 200, [eth, wrong_target, pair])
            answer, calls, _, sleeps, _ = _t092_public_market(interface, "get_token_liquidity",
                {"address": address, "chain_hint": hint}, routes)
            check("the explicit network lookup comes first, even for a saturated wrong-chain listing",
                  calls == ["market", "bsc"] and not sleeps, str(calls))
            check("matching BSC rows determine status, amount and network despite other rows",
                  answer.get("status") == status
                  and answer.get("liquidity_usd") == {"ok": 25000, "drained": 0, "unpriced": None}[status]
                  and answer.get("network_selection") == {
                      "requested_chain": "bsc", "returned_chain": "bsc", "status": "matched", "lookup": "found"}
                  and (status == "unpriced" or answer.get("best_pair_address") == bsc["pairAddress"]), str(answer))

    for hint in (None, "ethereum", "unrecognized", "solana"):
        answer, calls, _, _, _ = _t092_public_market("mcp", "get_token_liquidity",
            {"address": address, "chain_hint": hint}, {ds: ("market", 200, {"pairs": [eth]})})
        selection = {"requested_chain": "solana", "returned_chain": "ethereum", "status": "different",
                     "lookup": "incompatible_address"} if hint == "solana" else None
        check("Auto, exact match and unknown hints preserve request counts, and incompatible hints do not query",
              answer.get("network_selection") == selection and calls == ["market"]
              and answer.get("liquidity_usd") == 796872, str((answer, calls)))


def test_liquidity_keeps_a_foreign_snapshot_without_turning_it_into_a_requested_network_change():
    import test_risk as fixtures

    eth = fixtures._t030_pair(796872, reserves=False)
    address = eth["baseToken"]["address"]
    ds = fixtures._T083_DS + address
    url = "https://api.dexscreener.com/token-pairs/v1/bsc/" + address
    baseline = {"address": address, "best_pair_chain": "ethereum", "best_pair_address": eth["pairAddress"],
                "checked_at": "2026-11-22T12:00:00Z", "status": "ok", "liquidity_usd": 100, "source": "dexscreener"}
    for label, code, body, cached, lookup in (
            ("confirmed empty", 200, [], None, "empty"),
            ("mixed unqualified rows", 200, [eth, None], None, "unconfirmed"),
            ("unrecognized response shape", 200, {"pairs": []}, None, "unconfirmed"),
            ("provider did not answer", 429, fixtures._T083_ERROR, None, "unconfirmed"),
            ("stale empty fallback", 429, fixtures._T083_ERROR, ([], 300), "unconfirmed")):
        routes = {ds: ("market", 200, {"pairs": [eth]}), url: ("bsc", code, body)}
        args = {"address": address, "chain_hint": "bsc", "comparison_context": [baseline]}
        with patch.object(risk, "_now_iso", return_value="2026-11-23T00:00:00Z"):
            answer, calls, _, sleeps, _ = _t092_public_market(
                "mcp", "get_token_liquidity", args, routes, cached={url: cached} if cached else None)
        check(label + " keeps an Ethereum estimate and reports whether the BSC query was conclusive",
              answer.get("status") == "ok" and answer.get("best_pair_chain") == "ethereum"
              and answer.get("liquidity_usd") == 796872 and calls == ["market", "bsc"] and not sleeps
              and answer.get("network_selection") == {
                  "requested_chain": "bsc", "returned_chain": "ethereum", "status": "different", "lookup": lookup},
              str((answer, calls)))
        comparison = answer["comparison"]
        check(label + " cannot compare or adopt the foreign snapshot as the selected-network baseline",
              comparison.get("reason") == ("stale_response" if cached else "different_network")
              and "change_usd" not in comparison and answer["comparison_context"] == [baseline], str(comparison))


def test_liquidity_network_lookup_keeps_the_existing_market_fallback_for_unconfirmed_forks():
    import test_risk as fixtures

    address, _, _, cases = _t092_market_cases()
    eth = fixtures._t030_pair(100000, reserves=False)
    eth["baseToken"]["address"] = address
    fork = dict(eth, chainId="pulsechain")
    ds = fixtures._T083_DS + address
    url = "https://api.dexscreener.com/token-pairs/v1/ethereum/" + address
    gecko = fixtures._t083_market_url("eth", address)
    for code, body, status in ((200, cases[0][1][gecko][2], "ok"), (429, fixtures._T083_ERROR, "unavailable")):
        routes = {ds: ("global", 200, {"pairs": [fork]}), url: ("requested", 429, fixtures._T083_ERROR),
                  gecko: ("fallback", code, body)}
        answer, calls, _, sleeps, _ = _t092_public_market("mcp", "get_token_liquidity",
            {"address": address, "chain_hint": "ethereum", "comparison_context": []}, routes)
        check("failed scoped listing keeps the established fallback without using unconfirmed fork depth",
              answer.get("status") == status and calls == ["global", "requested", "fallback"] and not sleeps
              and answer.get("best_pair_chain") == ("ethereum" if status == "ok" else None)
              and answer.get("source") == ("geckoterminal" if status == "ok" else None)
              and answer.get("network_selection", {}).get("lookup") == "unconfirmed"
              and answer.get("network_selection", {}).get("status") == ("matched" if status == "ok" else "unresolved"),
              str((answer, calls)))


def test_liquidity_incompatible_network_preserves_only_available_global_data():
    import test_risk as fixtures

    evm = fixtures._t030_pair(100000, reserves=False)
    sol = _load("ds_bonk.json")["pairs"][0]
    for pair, hint in ((evm, "solana"), (sol, "ethereum")):
        address = pair["baseToken"]["address"]
        actual_chain = pair["chainId"]
        ds = fixtures._T083_DS + address
        for markets, status in (([pair], "ok"), ([], "unavailable")):
            routes = {ds: ("global", 200, {"pairs": markets})}
            for net in ("eth", "base", "bsc", "polygon_pos", "solana"):
                routes[fixtures._t083_market_url(net, address)] = (net, 429, fixtures._T083_ERROR)
            answer, calls, _, sleeps, _ = _t092_public_market("mcp", "get_token_liquidity",
                {"address": address, "chain_hint": hint, "comparison_context": []}, routes)
            selection = answer.get("network_selection", {})
            check("an incompatible hint neither probes the hinted network nor fans out to other chains",
                  calls == ["global"] and not sleeps and answer.get("status") == status
                  and selection.get("lookup") == "incompatible_address"
                  and selection.get("requested_chain") == hint
                  and selection.get("returned_chain") == (actual_chain if markets else None)
                  and selection.get("status") == ("different" if markets else "unresolved")
                  and not answer["comparison_context"], str((answer, calls)))


def test_liquidity_foreign_market_chain_is_bounded_in_zero_and_missing_depth_replies():
    import test_risk as fixtures

    supplied = "bsc\n" + "MARKET" * 30
    pair = fixtures._t030_pair(0, reserves=False)
    address = pair["baseToken"]["address"]
    args = {"address": address, "chain_hint": "bsc", "comparison_context": []}
    for depth, status in (({"usd": 0}, "drained"), ({}, "unpriced")):
        row = dict(pair, chainId=supplied, liquidity=depth)
        routes = {fixtures._T083_DS + address: ("global", 200, {"pairs": [row]}),
                  "https://api.dexscreener.com/token-pairs/v1/bsc/" + address: ("bsc", 200, [])}
        answer, _, _, _, _ = _t092_public_market("mcp", "get_token_liquidity", args, routes)
        selection = answer.get("network_selection", {})
        check("a foreign chain is compared before its display label is bounded and escaped",
              answer.get("status") == status and selection.get("status") == "different"
              and selection.get("returned_chain") == risk._ascii_safe(supplied.lower(), 24)
              and "\n" not in selection.get("returned_chain", ""), str(selection))


def test_real_worker_liquidity_rechecks_keep_a_reported_single_pool_zero():
    import test_risk as fixtures
    from liquidity_comparison import compare

    pool = "0x" + "Ab" * 32
    history, observations = [], []
    for index, amount in enumerate((100, 0, 0, 125)):
        pair = fixtures._t030_pair(amount)
        pair["pairAddress"] = pool
        address = pair["baseToken"]["address"]
        routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": [pair]})}
        args = {"address": address, "chain_hint": "ethereum"}
        stamp = "2026-11-23T00:00:0%dZ" % index
        with patch.object(risk, "_now_iso", return_value=stamp):
            rest, calls, _, sleeps, _ = _t092_public_market("http", "get_token_liquidity", args, routes)
            check("REST states the complete selected identity with no extra market work",
                  rest.get("best_pair_address") == pool and rest.get("source") == "dexscreener"
                  and rest.get("best_pair_chain") == "ethereum" and rest.get("checked_at") == stamp
                  and rest["status"] == ("ok" if amount else "drained")
                  and rest["liquidity_usd"] == amount and calls == ["market"] and not sleeps)
            if not amount:
                check("identified zero note attributes the estimate to the provider and pool",
                      rest.get("note") == "The provider reported a USD liquidity estimate of zero for this pool.")
            kwargs = dict(args, comparison_context=history)
            mcp, calls, _, sleeps, _ = _t092_public_market("mcp", "get_token_liquidity", kwargs, routes)
        check("MCP preserves the REST snapshot and the original request sequence",
              all(mcp.get(key) == value for key, value in rest.items()) and calls == ["market"] and not sleeps)
        history = mcp["comparison_context"]
        check("MCP keeps the latest zero or positive baseline for that exact pool",
              len(history) == 1 and history[0]["checked_at"] == stamp
              and history[0]["status"] == rest["status"] and history[0]["liquidity_usd"] == amount)
        if observations:
            before = observations[-1]
            actual = mcp["comparison"]
            expected = {"status": "compared", "before_usd": before["liquidity_usd"],
                        "after_usd": amount, "change_usd": amount - before["liquidity_usd"]}
            check("native and saved comparisons both support drop, zero change and recovery",
                  compare(before, rest) == expected
                  and all(actual.get(key) == value for key, value in expected.items())
                  and actual.get("before_checked_at") == before["checked_at"]
                  and actual.get("after_checked_at") == stamp, str(actual))
        observations.append(rest)


def test_liquidity_drained_identity_refuses_ambiguous_or_derived_zero():
    import test_risk as fixtures

    zero = fixtures._t030_pair(0)
    address = zero["baseToken"]["address"]
    args = {"address": address, "chain_hint": "ethereum", "comparison_context": []}
    variants = (
        ("multiple pools", [zero, dict(zero, pairAddress="0x" + "ac" * 20)], "ethereum", "drained"),
        ("different chain hint", [zero], "base", "drained"),
        ("cross-chain without a hint", [zero, dict(zero, chainId="base")], None, "drained"),
        ("short pool", [dict(zero, pairAddress="short")], "ethereum", "drained"),
        ("untrusted pool alias", [dict(zero, pairAddress=None, pool_id=zero["pairAddress"])], "ethereum", "drained"),
        ("cap is zero while stated depth is positive", [dict(zero, liquidity={"usd": 100, "base": 0, "quote": 0})],
         "ethereum", "drained"),
        ("conflicting depth aliases", [dict(zero, reserveInUsd=1)], "ethereum", "drained"),
        ("unquoted", [dict(zero, liquidity={})], "ethereum", "unpriced"),
        ("nonzero underflow", [dict(zero, liquidity={"usd": "1e-400"})], "ethereum", "unpriced"),
        ("boolean zero", [dict(zero, liquidity={"usd": False})], "ethereum", "unpriced"),
    )
    for name, rows, hint, status in variants:
        routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": rows})}
        if hint == "base":
            routes["https://api.dexscreener.com/token-pairs/v1/base/" + address] = ("base", 200, [])
        answer, _, _, _, _ = _t092_public_market("mcp", "get_token_liquidity", dict(args, chain_hint=hint), routes)
        check(name + " retains its prior status without a new baseline or claimed pool identity",
              answer.get("status") == status and "best_pair_address" not in answer
              and not answer.get("comparison_context") and "change_usd" not in answer["comparison"], str(answer))
        if status == "drained":
            note = answer.get("note", "")
            check(name + " reports zero estimates without calling the underlying pools empty",
                  "liquidity estimates" in note and "in this market scope are zero" in note
                  and "No pool-specific provider zero is available for comparison." in note, note)


def test_liquidity_fallback_zero_requires_the_qualified_pool_identity():
    import test_risk as fixtures

    token, pool, _, cases = _t092_market_cases()
    mint_pair = _load("ds_bonk.json")["pairs"][0]
    mint = mint_pair["baseToken"]["address"]
    quote = mint_pair["quoteToken"]["address"]
    evm = next(row for label, _, body in cases[0][1].values() if label == "fallback"
               for row in body["data"] if row["attributes"]["address"].lower() == pool)
    sol = {"id": "solana_" + mint_pair["pairAddress"],
           "attributes": {"address": mint_pair["pairAddress"], "name": "BONK / SOL",
                          "base_token_price_usd": "1"},
           "relationships": {"base_token": {"data": {"id": "solana_" + mint}},
                             "quote_token": {"data": {"id": "solana_" + quote}}}}
    for chain, network, address, raw, invalid_address in (
            ("ethereum", "eth", token, evm, "0x" + "de" * 20),
            ("solana", "solana", mint, sol, "z" * 44)):
        row = copy.deepcopy(raw)
        row["attributes"]["reserve_in_usd"] = "0.00"
        expected = row["attributes"]["address"]
        mismatched = copy.deepcopy(row)
        mismatched["attributes"]["address"] = invalid_address
        for rows, pool_id in (([row], expected), ([mismatched], None), ([row, mismatched], None)):
            routes = {fixtures._T083_DS + address: ("market", 200, {"pairs": []}),
                      fixtures._t083_market_url(network, address): ("fallback", 200, {"data": rows})}
            answer, calls, _, sleeps, _ = _t092_public_market("mcp", "get_token_liquidity",
                {"address": address, "chain_hint": chain, "comparison_context": []}, routes)
            check("fallback zero only names a valid, unique pool for the requested asset",
                  answer.get("status") == "drained" and answer.get("best_pair_address") == pool_id
                  and answer.get("source") == ("geckoterminal" if pool_id else None)
                  and bool(answer["comparison_context"]) == bool(pool_id)
                  and calls == ["market", "fallback"] and not sleeps, str(answer))


def test_native_liquidity_context_refuses_invalid_records_and_preserves_legacy_snapshots():
    before, _, after = _load("liquidity_recheck.json")
    first, _ = _native_liquidity_call(before)
    context = first["result"].get("structuredContent", {}).get("comparison_context", [])
    if not context:
        check("native context exists for validation controls", False)
        return
    for change in ({"served_stale": []}, {"error": "failed"}, {"status": "unavailable"},
                   {"best_pair_address": "truncated..."}, {"checked_at": "2026-11-19T16:09:07"},
                   {"liquidity_usd": True}, {"liquidity_usd": -1}, {"liquidity_usd": None},
                   {"source": "unknown"}, {"address": "x" * 9000},
                   {"status": "drained", "liquidity_usd": 1}, {"status": "drained", "liquidity_usd": False},
                   {"status": "drained", "liquidity_usd": "0"}, {"status": "drained", "liquidity_usd": None},
                   {"status": "drained", "liquidity_usd": 0, "source": ""},
                   {"status": "drained", "liquidity_usd": 0, "best_pair_address": "short"},
                   {"status": "drained", "liquidity_usd": 0, "served_stale": []}):
        reply, fetch = _native_liquidity_call(after, [dict(context[0], **change)])
        check("invalid client context is refused before current upstream work",
              reply.get("result", {}).get("isError") is True and fetch.await_count == 0)
    for bad in (None, {}, "history", context * 9):
        # Explicit null must not become an empty context.
        from unittest.mock import AsyncMock
        with patch.object(risk, "liquidity", AsyncMock(return_value=after)) as fetch:
            reply = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "get_token_liquidity", "arguments": {"address": before["address"],
                "comparison_context": bad}}})
        check("context has a hard list and count boundary", reply.get("result", {}).get("isError") is True
              and fetch.await_count == 0)
    reply, _ = _native_liquidity_call(after, legacy=True)
    answer = reply["result"]["structuredContent"]
    check("legacy callers still receive a snapshot without a comparison",
          all(answer.get(key) == value for key, value in after.items()) and "comparison" not in answer)
    legacy, _ = _native_liquidity_call(before, legacy=True)
    baseline = legacy["result"]["structuredContent"].get("comparison_context", [])
    reply, _ = _native_liquidity_call(after, baseline)
    check("a first ordinary snapshot needs no opt-in to support a later comparison",
          bool(baseline) and reply["result"].get("structuredContent", {}).get("comparison", {}).get("change_usd") == -366200)
    for change, reason in (({"served_stale": []}, "stale_response"),
                           ({"best_pair_address": "short"}, "invalid_identity"),
                           ({"checked_at": before["checked_at"]}, "invalid_order"),
                           ({"status": "unavailable"}, "unusable_response")):
        reply, _ = _native_liquidity_call(dict(after, **change), context)
        answer = reply["result"].get("structuredContent", {})
        check("an unusable current reply cannot overwrite its usable baseline",
              answer.get("comparison", {}).get("reason") == reason
              and answer.get("comparison_context") == context)
    for change in ({"served_stale": []}, {"checked_at": before["checked_at"]},
                   {"best_pair_address": None}, {"source": None}):
        reply, _ = _native_liquidity_call(dict(after, status="drained", liquidity_usd=0, **change), context)
        answer = reply["result"]["structuredContent"]
        check("unusable drained replies cannot replace the valid previous baseline",
              answer["comparison"]["status"] == "not_comparable"
              and "change_usd" not in answer["comparison"] and answer["comparison_context"] == context)
    newer = dict(context[0], checked_at="2026-11-19T16:20:00Z", liquidity_usd=86000000)
    reply, _ = _native_liquidity_call(after, [newer, context[0]])
    result = reply["result"].get("structuredContent", {}).get("comparison", {})
    check("history ordering cannot select an older comparable reading",
          result.get("before_checked_at") == newer["checked_at"] and result.get("change_usd") == -54000)
    many = [dict(context[0], best_pair_address="0x" + ("%040x" % n)) for n in range(1, 9)]
    reply, _ = _native_liquidity_call(after, many)
    answer = reply["result"].get("structuredContent", {})
    check("context eviction stays bounded and is disclosed",
          len(answer.get("comparison_context", [])) == 8
          and answer.get("comparison", {}).get("context_evicted") == 1)


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
