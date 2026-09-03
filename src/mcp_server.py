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
            "description": "unknown 表示关键数据缺失，不是'低风险'——不可据此建仓。",
        },
        "risk_score": {"type": "integer", "description": "0-100，越高越危险"},
        "confidence": {
            "type": "string", "enum": ["low", "medium", "high"],
            "description": "衡量的是数据完整度，不是风险高低。",
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
        "description": (
            "买入或持有某个代币前的安全检查。返回 low/medium/high/unknown 四档结论、"
            "0-100 风险分、逐条命中的风险信号，以及给 agent 的可执行建议。\n"
            "覆盖：可卖出性仿真(honeypot/交易税)、流动性深度、交易对年龄、"
            "跨链存在性、合约是否开源、活跃度。\n"
            "重要：risk_level='unknown' 表示关键数据拿不到，**不等于低风险**，"
            "此时不应据此做交易决策；confidence 衡量的是数据完整度而非风险高低。\n"
            "本工具只覆盖链上可观测风险，不构成投资建议，也不检测团队跑路、"
            "社工诈骗或链下风险。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string",
                            "description": "ERC-20 (0x+40位十六进制) 或 Solana (base58) 合约地址"},
                "chain_hint": {"type": "string",
                               "description": "可选主链提示，如 ethereum/bsc/base/polygon/solana。"
                                              "强烈建议传入：不传时同名分叉链上的错价池可能干扰选池。"},
                "verbose": {"type": "boolean", "default": False,
                            "description": "true 返回完整上游证据；默认精简以节省 token"},
            },
            "required": ["address"],
        },
        "outputSchema": _ASSESS_OUTPUT_SCHEMA,
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_token_liquidity",
        "description": (
            "某代币主交易对的流动性快照：价格、24h 成交量、池子数与跨链分布。"
            "status='ok' 才有数据；'unavailable' 表示上游请求失败（不代表没有流动性），"
            "'not_found' 表示确实没检索到交易对。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "代币合约地址"},
                "chain_hint": {"type": "string", "description": "可选，主链提示"},
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
        "description": (
            "扫描某条链上最新创建或最热门的交易池，返回名称/价格/流动性/24h量/池龄。"
            "新池风险天然极高，返回结果**不代表任何安全性背书**，"
            "对感兴趣的标的请再调用 assess_token_risk。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "default": "solana",
                          "description": "链名，如 solana/ethereum/base/bsc"},
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
                "在买入/持有某代币前调用 assess_token_risk。"
                "risk_level='unknown' 表示数据不足，不等于安全。"
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
