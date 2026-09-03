"""mcp_server.py — 极简 MCP streamable-http handler。

选择手写而非引入官方 mcp SDK 的原因：
- Cloudflare Python Workers (Pyodide) 对重型 SDK(pydantic/uvicorn/httpx)兼容性风险高
- 我们只暴露 3 个工具，手写 JSON-RPC 路由更小、更快、更稳
- streamable-http 本质是一个 POST 端点按 JSON-RPC 2.0 响应

正确处理 lifecycle：
- initialize        -> 返回协议版本 + capabilities + serverInfo
- notifications/initialized -> 通知，无 id，不响应
- tools/list        -> 返回工具列表(name/description/inputSchema)
- tools/call        -> 执行工具，返回 result{content:[{type:text,text}]}
- 其他              -> JSON-RPC 错误
"""

import risk  # 复用纯 Python 风险引擎（risk.py）

# 工具定义（供 tools/list 和 schema 复用）
TOOLS = [
    {
        "name": "assess_token_risk",
        "description": "评估一个代币的综合风险，返回可执行的 low/medium/high 结论和给 agent 的建议。address 应为 ERC-20 或 Solana 合约地址。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "ERC-20 或 Solana 合约地址"},
                "chain_hint": {"type": "string", "description": "可选，主链提示"},
            },
            "required": ["address"],
        },
    },
    {
        "name": "get_token_liquidity",
        "description": "返回某代币主交易对的流动性快照：价格、24h 量、跨链数。",
        "inputSchema": {
            "type": "object",
            "properties": {"address": {"type": "string", "description": "代币合约地址"}},
            "required": ["address"],
        },
    },
    {
        "name": "find_new_hot_pools",
        "description": "扫描某链(默认 solana)最新创建或最热的新交易池，返回价格/流动性/交易量概览。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "default": "solana"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]


async def handle_mcp_request(body, request_env=None) -> dict:
    """处理一条 MCP JSON-RPC 消息，返回响应 dict。"""
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    # 通知（无 id）：不响应
    if req_id is None:
        return None

    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vetagent", "version": "0.1.0"},
        }

    if method == "tools/list":
        return {"tools": TOOLS}

    if method == "tools/call":
        return await _call_tool(params)

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


async def _call_tool(params) -> dict:
    """执行工具调用，返回 MCP result 格式。"""
    name = params.get("name")
    args = params.get("arguments") or {}
    try:
        if name == "assess_token_risk":
            address = args.get("address", "")
            chain_hint = args.get("chain_hint")
            result = await risk.assess(address, chain_hint)
        elif name == "get_token_liquidity":
            result = await risk.liquidity(args.get("address", ""))
        elif name == "find_new_hot_pools":
            result = await risk.new_pools(args.get("chain", "solana"), args.get("limit", 10))
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
        return {"content": [{"type": "text", "text": _json(result)}]}
    except Exception as e:  # noqa: BLE001
        return {"isError": True, "content": [{"type": "text", "text": f"Error: {e}"}]}


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
