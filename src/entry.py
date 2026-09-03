"""entry.py — VetAgent Worker 入口（HTTP 路由）。

core 逻辑在 risk.py（风险评估）+ mcp_server.py（MCP 端点），这里只做路由分发。
入口类必须叫 Default（Cloudflare 要求）。request.url 是字符串，用 urlparse 解析。
"""

import json
from urllib.parse import urlparse

from workers import WorkerEntrypoint, Response

import risk
import mcp_server


class Default(WorkerEntrypoint):
    """Worker 入口。注意：Cloudflare 要求入口类名必须是 Default。"""

    async def fetch(self, request):
        parsed = urlparse(request.url)
        path = parsed.path

        # MCP streamable-http 端点
        if path == "/mcp":
            return await self._handle_mcp(request)

        if path in ("/", ""):
            return Response(
                "VetAgent - token risk intelligence for AI agents.\n"
                "Use /assess/{address}, /liquidity/{address}, /new-pools, or MCP at /mcp",
                headers={"content-type": "text/plain"}, status=200)

        if path == "/health":
            return Response(json.dumps({"status": "ok", "service": "vetagent", "mcp_tools": 3}),
                            headers={"content-type": "application/json"}, status=200)

        if path.startswith("/assess/"):
            address = path.split("/assess/")[1]
            r = await risk.assess(address)
            return self._json_response(r)

        if path.startswith("/liquidity/"):
            address = path.split("/liquidity/")[1]
            r = await risk.liquidity(address)
            return self._json_response(r)

        if path == "/new-pools":
            import urllib.parse as up
            qs = dict(up.parse_qsl(parsed.query))
            r = await risk.new_pools(qs.get("chain", "solana"), int(qs.get("limit", "10")))
            return self._json_response(r)

        return Response(json.dumps({"detail": "Not Found"}),
                        headers={"content-type": "application/json"}, status=404)

    async def _handle_mcp(self, request):
        """处理 MCP streamable-http：POST 一个 JSON-RPC 消息，返回响应。"""
        if request.method == "GET":
            # streamable-http 的 GET 用于探测/SSE，这里返回一个可用的描述
            return Response("VetAgent MCP endpoint. Send JSON-RPC POST requests.",
                            headers={"content-type": "text/plain"}, status=200)
        try:
            body = await request.json()
        except Exception:
            return Response(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}),
                            headers={"content-type": "application/json"}, status=400)
        result = await mcp_server.handle_mcp_request(body)
        if result is None:
            return Response("", status=202)  # 通知无响应
        resp = {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
        return Response(json.dumps(resp, ensure_ascii=False),
                        headers={"content-type": "application/json"}, status=200)

    def _json_response(self, obj):
        return Response(json.dumps(obj, ensure_ascii=False),
                        headers={"content-type": "application/json"}, status=200)
