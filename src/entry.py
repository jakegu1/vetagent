"""entry.py — VetAgent Worker 入口（HTTP 路由）。

core 逻辑在 risk.py（风险评估）+ mcp_server.py（MCP 端点），这里只做路由分发。
入口类必须叫 Default（Cloudflare 要求）。request.url 是字符串，用 urlparse 解析。
"""

import json
import os
from urllib.parse import parse_qsl, urlparse

from workers import Response, WorkerEntrypoint

import mcp_server
import risk

_LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing.html")

# MCP Registry 域名验证的**公钥**记录。公开可读是设计的一部分。
# 对应私钥不在这个仓库里，也不该在任何仓库里。
_REGISTRY_AUTH = "v=MCPv1; k=ed25519; p=748fDl4SJZZt9TWfmYNDC3Xy1OIbfSjhf72vo8j8ZgI=\n"

# 隐私政策。内联而不是单独文件，因为它必须永远可达——
# 目录审核会直接抓这个 URL，404 是即时驳回项。
_PRIVACY_HTML = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VetAgent - Privacy</title>
<style>
 body{max-width:44rem;margin:0 auto;padding:3rem 1.25rem;line-height:1.7;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
   background:#0d1117;color:#c9d1d9}
 h1{color:#e6edf3;font-size:1.9rem;margin:0 0 .4rem}
 h2{color:#e6edf3;font-size:1.05rem;margin:2rem 0 .5rem}
 a{color:#58a6ff} code{background:#161b22;padding:.1rem .35rem;border-radius:4px}
 .sub{color:#8b949e;margin:0 0 2rem}
</style>
<h1>Privacy</h1>
<p class="sub">VetAgent &middot; last updated 2026-09-04</p>

<h2>What we collect</h2>
<p><strong>No accounts, no cookies, no tracking.</strong> VetAgent is a stateless
service. It has no user database and no analytics scripts.</p>
<p>When you call the API or the MCP endpoint, the request carries a token contract
address and an optional chain name. That address is used to query public data
sources and is <strong>not stored</strong> after the response is returned.</p>

<h2>What reaches third parties</h2>
<p>To answer a request we query these public APIs, sending only the token address:</p>
<ul>
  <li>DexScreener &mdash; trading pairs, price, liquidity</li>
  <li>GeckoTerminal &mdash; liquidity fallback, new and trending pools</li>
  <li>honeypot.is &mdash; EVM buy/sell simulation</li>
  <li>RugCheck &mdash; Solana contract risk</li>
</ul>
<p>These are third-party services with their own privacy policies. We never send
them wallet addresses, identities, or anything about who is asking.</p>

<h2>Logs</h2>
<p>Cloudflare, which serves this Worker, keeps standard edge request metadata
(IP, timestamp, path) for operational and abuse-prevention purposes under its own
policy. We do not export, retain, sell, or analyse it, and we do not join it to
anything else.</p>

<h2>Not financial advice</h2>
<p>VetAgent reports observable on-chain risk. It is not investment advice, does not
size positions, and cannot detect off-chain risk. A <code>low</code> verdict means
"no fatal signal found in the checks that ran" &mdash; never "safe to buy". A verdict
of <code>unknown</code> means a critical check could not be completed and must not be
read as low risk.</p>

<h2>Contact</h2>
<p>Open an issue at
<a href="https://github.com/jakegu1/vetagent">github.com/jakegu1/vetagent</a>.</p>
"""

_JSON = "application/json"
_CORS = {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-allow-headers": "content-type, accept, mcp-protocol-version, mcp-session-id",
    "access-control-max-age": "86400",
}


def _json_response(obj, status=200, extra_headers=None):
    headers = {"content-type": _JSON}
    headers.update(_CORS)
    if extra_headers:
        headers.update(extra_headers)
    return Response(json.dumps(obj, ensure_ascii=False), headers=headers, status=status)


class Default(WorkerEntrypoint):
    """Worker 入口。注意：Cloudflare 要求入口类名必须是 Default。"""

    async def fetch(self, request):
        parsed = urlparse(request.url)
        path = parsed.path.rstrip("/") or "/"
        query = dict(parse_qsl(parsed.query))

        if request.method == "OPTIONS":
            return Response("", headers=_CORS, status=204)

        if path == "/mcp":
            return await self._handle_mcp(request)

        if path == "/":
            try:
                with open(_LANDING_PATH, "r", encoding="utf-8") as f:
                    return Response(f.read(), headers={"content-type": "text/html"}, status=200)
            except OSError:
                return Response(
                    "VetAgent - token risk intelligence for AI agents.\n"
                    "Use /assess/{address}, /liquidity/{address}, /new-pools, or MCP at /mcp",
                    headers={"content-type": "text/plain"}, status=200)

        if path == "/health":
            return _json_response({"status": "ok", "service": "vetagent",
                                   "version": "0.2.0", "mcp_tools": len(mcp_server.TOOLS)})

        if path == "/privacy":
            return Response(_PRIVACY_HTML, headers={"content-type": "text/html"}, status=200)

        # 官方 MCP Registry 的域名归属验证。走域名而不是 GitHub 账号，
        # 这样命名空间是 dev.vetagent/* 而不是 io.github.<某个人>/*——
        # 产品的身份挂在产品的域名上，不挂在某个人的账号上。
        # 这里只放公钥；私钥在仓库外，永不提交。
        if path == "/.well-known/mcp-registry-auth":
            return Response(_REGISTRY_AUTH,
                            headers={"content-type": "text/plain"}, status=200)

        try:
            if path.startswith("/assess/"):
                return _json_response(await risk.assess(
                    path[len("/assess/"):],
                    query.get("chain_hint") or query.get("chain"),
                    query.get("verbose", "").lower() in ("1", "true", "yes")))

            if path.startswith("/liquidity/"):
                return _json_response(await risk.liquidity(
                    path[len("/liquidity/"):],
                    query.get("chain_hint") or query.get("chain")))

            if path == "/new-pools":
                return _json_response(await risk.new_pools(
                    query.get("chain", "solana"), query.get("limit", 10)))
        except ValueError as e:
            return _json_response({"error": "invalid_request", "detail": str(e)}, status=400)
        except Exception as e:  # noqa: BLE001
            return _json_response({"error": "internal_error", "detail": str(e)}, status=500)

        return _json_response({"error": "not_found", "detail": "Not Found"}, status=404)

    async def _handle_mcp(self, request):
        """MCP streamable-http：POST 一条 JSON-RPC 消息，返回一条响应。"""
        if request.method == "GET":
            # streamable-http 的 GET 用于打开 SSE 流。我们不提供服务端推送，
            # 按规范返回 405 让客户端知道不必等待，而不是回一段人类可读文本。
            return _json_response(
                {"error": "sse_not_supported",
                 "detail": "VetAgent 是无状态 MCP server，请用 POST 发送 JSON-RPC 请求。"},
                status=405, extra_headers={"allow": "POST, OPTIONS"})

        if request.method != "POST":
            return _json_response({"error": "method_not_allowed"}, status=405,
                                  extra_headers={"allow": "POST, OPTIONS"})

        try:
            body = await request.json()
        except Exception:
            return _json_response(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": mcp_server.PARSE_ERROR, "message": "Parse error"}},
                status=400)

        headers = {"mcp-protocol-version": mcp_server.PROTOCOL_VERSION}

        # 批量请求：JSON-RPC 允许数组
        if isinstance(body, list):
            if not body:
                return _json_response(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": mcp_server.INVALID_REQUEST, "message": "Empty batch"}},
                    status=400)
            responses = []
            for item in body:
                r = await mcp_server.handle_mcp_request(item)
                if r is not None:
                    responses.append(r)
            if not responses:
                return Response("", headers=_CORS, status=202)
            return _json_response(responses, extra_headers=headers)

        result = await mcp_server.handle_mcp_request(body)
        if result is None:
            return Response("", headers=_CORS, status=202)  # 通知无响应体
        return _json_response(result, extra_headers=headers)
