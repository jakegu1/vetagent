"""mcp_server.py — 极简 MCP streamable-http handler。

选择手写而非引入官方 mcp SDK 的原因：
- Cloudflare Python Workers (Pyodide) 对重型 SDK(pydantic/uvicorn/httpx)兼容性风险高
- 我们只暴露 3 个工具，手写 JSON-RPC 路由更小、更快、更稳
- streamable-http 本质是一个 POST 端点按 JSON-RPC 2.0 响应

lifecycle：
- initialize                 -> 协议版本 + capabilities + serverInfo
- notifications/initialized  -> 通知，无 id，不响应
- tools/list                 -> 工具列表(name/description/inputSchema/outputSchema)
- tools/call                 -> 执行工具，返回 content + structuredContent
- 其他                       -> JSON-RPC 顶层 error（不是塞进 result 里）
"""

import json

import risk  # 复用纯 Python 风险引擎（risk.py）

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

# JSON-RPC 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

_SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["ok", "info", "warn", "critical", "fatal"]},
        "name": {"type": "string"},
        "message": {"type": "string"},
        "category": {"type": "string"},
    },
}

_ASSESS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "address": {"type": "string"},
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high", "unknown"],
            "description": ("'unknown' means a critical check could not be completed. "
                            "It is NOT a low-risk result and must not justify a trade."),
        },
        "risk_score": {"type": "integer", "description": "0-100; higher is more dangerous"},
        "confidence": {
            "type": "string", "enum": ["low", "medium", "high"],
            "description": "How complete the input data was — not how safe the token is.",
        },
        "signals": {"type": "array", "items": _SIGNAL_SCHEMA},
        "recommendation": {"type": "string"},
        "evidence": {"type": "object"},
    },
    "required": ["address", "risk_level", "risk_score", "confidence", "signals"],
}

TOOLS = [
    {
        "name": "assess_token_risk",
        "title": "Assess Token Risk",
        "description": (
            "Safety check to run BEFORE buying, holding, or recommending a token. "
            "Returns an actionable verdict (low / medium / high / unknown), a 0-100 risk "
            "score, and the individual signals behind it.\n"
            "Covers: sell simulation (honeypot detection, buy/sell/transfer taxes), "
            "liquidity depth, trading-pair age, cross-chain presence, whether the contract "
            "is open source, and on Solana the mint/freeze authority and holder "
            "concentration — plus the aggregate verdicts of upstream security scanners.\n"
            "IMPORTANT: risk_level 'unknown' means a critical check could not be completed. "
            "It is NOT a low-risk result and must not be used to justify a trade; "
            "evidence.data_gaps lists exactly what was missing. 'confidence' measures how "
            "complete the input data was, not how safe the token is.\n"
            "Reports observable on-chain risk only. Not financial advice, does not size "
            "positions, and cannot see off-chain risk such as team behaviour, social "
            "engineering, or a rug executed through governance. Treat 'low' as 'no fatal "
            "signal found in the checks that ran', never as 'safe to buy'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string",
                            "description": "Token contract address: ERC-20 (0x + 40 hex) or Solana (base58)"},
                "chain_hint": {"type": "string",
                               "description": "Optional chain name (ethereum / bsc / base / polygon / "
                                              "arbitrum / solana). Strongly recommended: Ethereum forks "
                                              "such as PulseChain inherit contract addresses, so the same "
                                              "address exists on several chains at wildly different prices."},
                "verbose": {"type": "boolean", "default": False,
                            "description": "Return full upstream evidence. Off by default to save tokens."},
            },
            "required": ["address"],
        },
        "outputSchema": _ASSESS_OUTPUT_SCHEMA,
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_token_liquidity",
        "title": "Get Token Liquidity",
        "description": (
            "Liquidity snapshot for a token's primary trading pair: price, 24h volume, "
            "pair count and the chains it trades on.\n"
            "Check 'status' before using the numbers: 'ok' means real data, 'unavailable' "
            "means the upstream request failed (which does NOT mean the token has no "
            "liquidity), and 'not_found' means no trading pair was found."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Token contract address"},
                "chain_hint": {"type": "string",
                               "description": "Optional chain name; disambiguates forks that share addresses"},
            },
            "required": ["address"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "status": {"type": "string", "enum": ["ok", "not_found", "unavailable"]},
                "price_usd": {"type": "number"},
                "liquidity_usd": {"type": "number"},
                "volume_24h_usd": {"type": "number"},
                "pairs_total": {"type": "integer"},
                "chains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["address", "status"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "find_new_hot_pools",
        "title": "Find New Hot Pools",
        "description": (
            "Scan a chain for the newest and most active trading pools, returning name, "
            "price, liquidity, 24h volume and pool age.\n"
            "Discovery only. New pools carry inherently high risk and appearing here is NOT "
            "a safety endorsement — call assess_token_risk on anything you intend to act on."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "default": "solana",
                          "description": "Chain name, e.g. solana / ethereum / base / bsc"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": False},
    },
]


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


async def handle_mcp_request(body):
    """处理一条 MCP JSON-RPC 消息。

    返回完整的 JSON-RPC 响应 dict；返回 None 表示这是通知（不应有响应体）。
    错误一律放在**顶层 error**，而不是塞进 result 里。
    """
    if not isinstance(body, dict):
        return _error(None, INVALID_REQUEST, "Request must be a JSON object")

    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    # 通知：没有 id 键。注意 id=0 是合法请求 id，不能用真值判断。
    if "id" not in body:
        return None
    if not method:
        return _error(req_id, INVALID_REQUEST, "Missing method")

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _ok(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vetagent", "version": "0.2.0"},
            "instructions": (
                "Call assess_token_risk before an agent buys, holds, or recommends a "
                "token. risk_level 'unknown' means a critical check could not run — it is "
                "not a low-risk result and must not be used to justify a trade."
            ),
        })

    if method == "ping":
        return _ok(req_id, {})

    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})

    if method == "tools/call":
        return await _call_tool(req_id, params)

    return _error(req_id, METHOD_NOT_FOUND, "Method not found: %s" % method)


async def _call_tool(req_id, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        return _error(req_id, INVALID_PARAMS, "arguments must be an object")

    try:
        if name == "assess_token_risk":
            result = await risk.assess(args.get("address", ""),
                                       args.get("chain_hint"),
                                       bool(args.get("verbose", False)))
        elif name == "get_token_liquidity":
            result = await risk.liquidity(args.get("address", ""), args.get("chain_hint"))
        elif name == "find_new_hot_pools":
            result = await risk.new_pools(args.get("chain", "solana"), args.get("limit", 10))
        else:
            return _error(req_id, INVALID_PARAMS, "Unknown tool: %s" % name)
    except ValueError as e:
        # 输入不合法：作为工具错误返回，让调用方的模型能看到并自我纠正
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text", "text": str(e)}]})
    except Exception as e:  # noqa: BLE001
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text",
                                         "text": "工具执行失败: %s" % e}]})

    payload = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    # structuredContent 必须是对象；数组结果包一层
    payload["structuredContent"] = result if isinstance(result, dict) else {"items": result}
    return _ok(req_id, payload)
