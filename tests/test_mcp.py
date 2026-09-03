"""test_mcp.py — MCP 协议层离线测试。

不打网络：risk 层的抓取被 stub 掉，只验证 JSON-RPC 协议行为。

运行：  python tests/test_mcp.py
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
    print("\n[JSON-RPC] 响应信封")
    r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    check("有 jsonrpc 字段", r.get("jsonrpc") == "2.0", str(r.get("jsonrpc")))
    check("id 原样回传", r.get("id") == 1, str(r.get("id")))
    check("有 result", "result" in r, str(r.keys()))
    check("无 error", "error" not in r, "")
    check("serverInfo 完整",
          r["result"]["serverInfo"]["name"] == "vetagent", str(r["result"].get("serverInfo")))


def test_errors_are_top_level():
    """回归：未知方法此前被包成 result.error，违反 JSON-RPC 2.0。"""
    print("\n[JSON-RPC] 错误必须在顶层")
    r = call({"jsonrpc": "2.0", "id": 7, "method": "does/not/exist"})
    check("error 在顶层", "error" in r, str(r))
    check("result 不存在", "result" not in r, str(r))
    check("错误码为 -32601", r["error"]["code"] == mcp_server.METHOD_NOT_FOUND,
          str(r["error"]["code"]))
    check("id 保留", r.get("id") == 7, str(r.get("id")))

    r2 = call({"jsonrpc": "2.0", "id": 8})
    check("缺 method 报 InvalidRequest",
          r2.get("error", {}).get("code") == mcp_server.INVALID_REQUEST, str(r2))

    r3 = call("not-an-object")
    check("非对象报 InvalidRequest",
          r3.get("error", {}).get("code") == mcp_server.INVALID_REQUEST, str(r3))


def test_notification_gets_no_response():
    print("\n[JSON-RPC] 通知与 id=0")
    r = call({"jsonrpc": "2.0", "method": "notifications/initialized"})
    check("通知不返回响应", r is None, str(r))

    # id=0 是合法请求 id，不能被真值判断当成通知
    r2 = call({"jsonrpc": "2.0", "id": 0, "method": "ping"})
    check("id=0 必须有响应", r2 is not None, "")
    check("id=0 原样回传", r2 and r2.get("id") == 0, str(r2))


def test_protocol_negotiation():
    print("\n[MCP] 协议版本协商")
    r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05"}})
    check("回传客户端支持的版本",
          r["result"]["protocolVersion"] == "2024-11-05",
          str(r["result"]["protocolVersion"]))
    r2 = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "1999-01-01"}})
    check("不支持的版本回退到默认",
          r2["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION,
          str(r2["result"]["protocolVersion"]))


def test_tools_list_shape():
    print("\n[MCP] tools/list 结构")
    r = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = r["result"]["tools"]
    check("三个工具", len(tools) == 3, str(len(tools)))
    for t in tools:
        check("%s 有 inputSchema" % t["name"], "inputSchema" in t, "")
        check("%s 有 annotations" % t["name"], "annotations" in t, "")
        check("%s 标注为只读" % t["name"],
              t["annotations"].get("readOnlyHint") is True, "")
    assess = [t for t in tools if t["name"] == "assess_token_risk"][0]
    check("assess 有 outputSchema", "outputSchema" in assess, "")
    check("assess 支持 verbose", "verbose" in assess["inputSchema"]["properties"], "")
    check("liquidity 支持 chain_hint",
          "chain_hint" in [t for t in tools if t["name"] == "get_token_liquidity"][0]
          ["inputSchema"]["properties"], "")
    # 工具描述是 LLM 唯一的使用说明。若不写明 unknown≠安全，
    # 调用方模型会把它当成 low 处理——这是最危险的误读。
    check("描述里说明 unknown 不等于安全",
          "unknown" in assess["description"]
          and "NOT a low-risk result" in assess["description"], "")
    # 分发前置：工具面向国际 agent 生态，描述必须是英文。
    # 只查 CJK，不查全部非 ASCII——破折号、引号这类排版字符是合法的。
    def _has_cjk(text):
        return any("一" <= c <= "鿿" for c in text)
    for t in tools:
        check("%s 描述无中文" % t["name"], not _has_cjk(t["description"]), "")
        for pname, prop in t["inputSchema"].get("properties", {}).items():
            check("%s.%s 描述无中文" % (t["name"], pname),
                  not _has_cjk(prop.get("description", "")), "")
    for t in tools:
        check("%s 有 title" % t["name"], bool(t.get("title")), str(t.get("title")))


def test_tools_call_returns_structured_content():
    print("\n[MCP] tools/call 返回结构化内容")
    stub_upstream()
    r = call({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "assess_token_risk",
                         "arguments": {"address": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
                                       "chain_hint": "ethereum"}}})
    res = r["result"]
    check("有 content", isinstance(res.get("content"), list), "")
    check("有 structuredContent", isinstance(res.get("structuredContent"), dict), "")
    check("structuredContent 与 text 一致",
          res["structuredContent"] == json.loads(res["content"][0]["text"]), "")
    check("含 risk_level", "risk_level" in res["structuredContent"], "")
    check("未出错", not res.get("isError"), "")


def test_invalid_input_is_tool_error():
    print("\n[MCP] 非法输入作为工具错误返回")
    stub_upstream()
    r = call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "assess_token_risk", "arguments": {"address": "0xdeadbeef"}}})
    check("isError 为 true", r["result"].get("isError") is True, str(r["result"]))
    check("错误文本可读", "无效的代币地址" in r["result"]["content"][0]["text"],
          r["result"]["content"][0]["text"])

    r2 = call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
               "params": {"name": "no_such_tool", "arguments": {}}})
    check("未知工具走顶层 error", "error" in r2, str(r2))

    r3 = call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
               "params": {"name": "assess_token_risk", "arguments": "oops"}})
    check("arguments 非对象报 InvalidParams",
          r3.get("error", {}).get("code") == mcp_server.INVALID_PARAMS, str(r3))


def test_verbose_flag_changes_payload_size():
    print("\n[MCP] verbose 开关")
    stub_upstream()
    addr = "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"

    def size(verbose):
        r = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "assess_token_risk",
                             "arguments": {"address": addr, "chain_hint": "ethereum",
                                           "verbose": verbose}}})
        return len(r["result"]["content"][0]["text"])

    slim, full = size(False), size(True)
    check("默认精简小于 verbose", slim <= full, "slim=%d full=%d" % (slim, full))
    check("精简输出 < 1800 字节", slim < 1800, "%d" % slim)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print("=" * 68)
    print("VetAgent MCP 协议测试")
    print("=" * 68)
    for t in tests:
        t()
    print("\n" + "=" * 68)
    print("通过 %d 项，失败 %d 项" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\n失败明细：")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
