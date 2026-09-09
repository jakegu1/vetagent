"""mcp_server.py — a minimal MCP streamable-http handler.

Hand-rolled rather than built on the official mcp SDK because:
- Cloudflare Python Workers (Pyodide) is a compatibility gamble with heavy SDKs
  (pydantic/uvicorn/httpx)
- we expose exactly 3 tools, so routing JSON-RPC by hand is smaller, faster and steadier
- streamable-http is really just one POST endpoint answering in JSON-RPC 2.0

Lifecycle:
- initialize                 -> protocol version + capabilities + serverInfo
- notifications/initialized  -> a notification: no id, no response
- tools/list                 -> tool list (name/description/inputSchema/outputSchema)
- tools/call                 -> run the tool, return content + structuredContent
- anything else              -> a top-level JSON-RPC error (not stuffed into result)
"""

import contextvars
import json

import risk  # reuse the pure-Python risk engine (risk.py)

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

# Standard JSON-RPC error codes
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
            "Check 'status' before using the numbers. 'ok' means real data. "
            "'unavailable' means the upstream request failed, which does NOT mean the "
            "token has no liquidity. 'not_found' means no trading pair exists for this "
            "address at all. 'unpriced' means pairs exist but no source has costed them, "
            "so liquidity_usd is null and the depth is unknown -- this is NOT a report of "
            "zero liquidity. 'drained' means every pool on the token's own chain reports "
            "its depth and every one is empty: there is nothing to sell into."
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
                "status": {"type": "string",
                           "enum": ["ok", "not_found", "unpriced", "drained",
                                    "unavailable"]},
                "price_usd": {"type": "number"},
                "liquidity_usd": {"type": ["number", "null"]},
                "volume_24h_usd": {"type": "number"},
                "pairs_total": {"type": "integer"},
                "served_stale": {
                    "type": "array",
                    "description": "Present only when an upstream was unreachable and "
                                   "this answer used cached data. Each entry names the "
                                   "source and how many seconds old it was.",
                    "items": {"type": "object"}},
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
            "token_address, price, liquidity, 24h volume and pool age.\n"
            "Discovery only. New pools carry inherently high risk and appearing here is NOT "
            "a safety endorsement — pass token_address straight to assess_token_risk for "
            "anything you intend to act on."
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
        "outputSchema": {
            "type": "object",
            "description":
                "Discovery only, never an endorsement. Call assess_token_risk on "
                "token_address before saying anything about a pool's risk.",
            "properties": {
                "chain": {"type": "string"},
                "network": {"type": "string",
                            "description": "The upstream's own name for the chain, "
                                           "which differs from `chain` (eth vs ethereum)."},
                "count": {
                    "type": "integer",
                    "description":
                        "How many pools are in `pools`. NOT how many were examined -- "
                        "that is `scanned`. This field reported the fetched total beside "
                        "a shorter list until 2026-09-08, so a caller reading it believed "
                        "it had seen twenty pools when it had three.",
                },
                "scanned": {
                    "type": "integer",
                    "description":
                        "How many distinct pools were examined before the limit was "
                        "applied. Always >= count.",
                },
                "sources_ok": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["new", "trending"]},
                    "description":
                        "Which of the two upstream listings answered. Both means a full "
                        "scan.",
                },
                "sources_failed": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["new", "trending"]},
                    "description":
                        "Which listings did NOT answer. A non-empty array means this is a "
                        "PARTIAL scan: a smaller `scanned` here is a coverage gap, not a "
                        "quiet market. Treat it as missing information, not as absence.",
                },
                "served_stale": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description":
                        "Present only when an upstream was unreachable and cached data "
                        "was used. Each entry names the source and its age in seconds.",
                },
                "pools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pool_id": {"type": "string"},
                            "name": {"type": "string"},
                            "token_address": {
                                "type": "string",
                                "description":
                                    "The base token. This is the field to hand to "
                                    "assess_token_risk -- pool_id is not an address, and "
                                    "passing it produced six empty answers before the "
                                    "discovery-to-vetting seam was fixed.",
                            },
                            "kind": {"type": "string", "enum": ["new", "trending"]},
                            "price_usd": {"type": ["number", "null"]},
                            "liquidity_usd": {"type": ["number", "null"]},
                            "volume_24h_usd": {"type": ["number", "null"]},
                            "pool_age_days": {"type": ["integer", "null"]},
                        },
                        "required": ["pool_id", "name", "token_address", "kind"],
                    },
                },
            },
            "required": ["chain", "network", "count", "scanned",
                         "sources_ok", "sources_failed", "pools"],
        },
    },
]


def _as_bool(v):
    """JSON-RPC clients send booleans as booleans, strings, and 0/1. Read all three.

    bool("false") is True, so a client that sent the string "false" -- which several
    MCP clients do, because the schema type gets lost on the way through -- turned
    verbose on and got the full evidence payload it had explicitly declined.
    """
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


# What the client called itself on initialize, for this request only. A contextvar
# rather than a global: a Worker isolate serves many requests and a module-level
# variable would leak one caller's identity into another's telemetry.
_LAST_CLIENT_INFO = contextvars.ContextVar("vetagent_client_info", default="")


def declared_client():
    """The client's own declared name/version, or "" if it never said."""
    try:
        return _LAST_CLIENT_INFO.get()
    except LookupError:
        return ""


async def handle_mcp_request(body):
    """Handle a single MCP JSON-RPC message.

    Returns the full JSON-RPC response dict; None means this was a notification and
    must not get a response body.
    Errors always go in the **top-level error**, never stuffed into result.
    """
    if not isinstance(body, dict):
        return _error(None, INVALID_REQUEST, "Request must be a JSON object")

    method = body.get("method")
    req_id = body.get("id")

    # A notification has no "id" key. id=0 is a legal request id, so test for the
    # key itself, not for truthiness.
    if "id" not in body:
        return None

    # JSON-RPC restricts id to String, Number or Null; a dict or list was being echoed
    # back verbatim. bool is excluded explicitly because in Python it is a subclass of
    # int, and a JSON boolean is not a Number.
    if not (req_id is None or isinstance(req_id, str)
            or (isinstance(req_id, (int, float)) and not isinstance(req_id, bool))):
        return _error(None, INVALID_REQUEST,
                      "id must be a string, number or null")

    # `params` was read as `body.get("params") or {}`, and a list is truthy, so an Array
    # survived unchanged and `_call_tool` then called `.get` on it -- AttributeError,
    # uncaught, on a message JSON-RPC 2.0 explicitly permits. Every method here takes its
    # arguments by name, so an Array is a refusal rather than a crash: INVALID_PARAMS is
    # a normal thing for a protocol to say. Tested against `is None` rather than
    # truthiness so that `"params": 0` is refused too and does not fall through as {}.
    params = body.get("params")
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        return _error(req_id, INVALID_PARAMS, "params must be an object")

    if not method:
        return _error(req_id, INVALID_REQUEST, "Missing method")

    if method == "initialize":
        # The client declares its own name and version here, and the MCP spec requires
        # it. That is application self-description, not personal data, and it de-mushes
        # the 11% of traffic currently arriving as "mozilla", "node", "undici" and
        # "unknown" -- buckets that are User-Agent artefacts rather than callers.
        info = params.get("clientInfo")
        if isinstance(info, dict):
            _LAST_CLIENT_INFO.set("%s %s" % (str(info.get("name") or "?")[:32],
                                             str(info.get("version") or "?")[:16]))
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _ok(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vetagent", "version": "0.2.0"},
            # The second sentence is a product decision, not a nicety.
            #
            # A decision gate asks whether anyone outside this project uses this server,
            # and fourteen days of telemetry could not answer it. The traffic is 96%
            # handshakes from directory crawlers; the one candidate that looks like real
            # use arrives as "mozilla", which is a User-Agent prefix shared by every
            # browser and every bot that spoofs one. No amount of log forensics resolves
            # that, and the fields that would -- addresses, identities, tokens -- are ones
            # this project has deliberately refused to record.
            #
            # So: ask. An operator who has wired this into something can say so in one
            # line, and that is worth more than any inference from 42 requests. It costs
            # a sentence and it is the only path here that produces a name attached to a
            # human intention.
            "instructions": (
                "Call assess_token_risk before an agent buys, holds, or recommends a "
                "token. risk_level 'unknown' means a critical check could not run — it is "
                "not a low-risk result and must not be used to justify a trade.\n\n"
                "Building on this? The maintainer would like to know it is being used, "
                "and will tell you before anything changes under you: "
                "hello@vetagent.dev, or github.com/jakegu1/vetagent/issues. Free, no "
                "signup, no tracking — "
                "this server records no addresses, no token queries and no identities, "
                "which is also why it cannot tell who you are unless you say."
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
                                       _as_bool(args.get("verbose", False)))
        elif name == "get_token_liquidity":
            result = await risk.liquidity(args.get("address", ""), args.get("chain_hint"))
        elif name == "find_new_hot_pools":
            result = await risk.new_pools(args.get("chain", "solana"), args.get("limit", 10))
        else:
            return _error(req_id, INVALID_PARAMS, "Unknown tool: %s" % name)
    except ValueError as e:
        # Bad input: return it as a tool error so the calling model sees it and self-corrects
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text", "text": str(e)}]})
    except Exception as e:  # noqa: BLE001
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text",
                                         "text": "Tool execution failed: %s" % e}]})

    payload = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    # structuredContent must be an object, so wrap array results in one
    payload["structuredContent"] = result if isinstance(result, dict) else {"items": result}
    return _ok(req_id, payload)
