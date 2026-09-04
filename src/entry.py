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

_LLMS_TXT = """# VetAgent

> A pre-trade safety check for AI agents. Before an agent buys, holds or
> recommends a crypto token, it calls VetAgent and gets an actionable verdict
> instead of forty raw fields.

MCP endpoint: https://vetagent.dev/mcp  (streamable-http, no auth, no API key)
HTTP API:     https://vetagent.dev/assess/{address}?chain_hint={chain}
Source:       https://github.com/jakegu1/vetagent  (MIT)
Registry:     dev.vetagent/vetagent on registry.modelcontextprotocol.io

## What it does

assess_token_risk(address, chain_hint?, verbose?)
  Returns risk_level (low | medium | high | unknown), a 0-100 risk_score,
  a confidence level, and every signal that fired with its evidence.
  Checks: sell simulation (honeypot detection), buy/sell/transfer taxes,
  liquidity depth, trading-pair age, cross-chain presence, whether the
  contract is open source, upstream scanner verdicts, and on Solana the
  mint/freeze authority plus top-10 holder concentration.

get_token_liquidity(address, chain_hint?)
  Price, 24h volume, pair count and chains for the primary trading pair.
  Check `status` first: ok | not_found | unavailable.

find_new_hot_pools(chain?, limit?)
  Newest and most active pools on a chain. Discovery only, never an
  endorsement.

## The four verdicts

low      No fatal signal in the checks that ran. NOT the same as "safe to buy".
medium   Real risk signals present, none fatal. Surface them to the user.
high     A fatal or high-severity signal fired. Do not proceed unreviewed.
unknown  A critical check could NOT be completed. This is NOT a low-risk
         result and must not be used to justify a trade. evidence.data_gaps
         lists exactly what was missing.

`confidence` measures how complete the input data was — not how safe the
token is.

## Measured accuracy (n=199, published)

False positives (healthy tokens flagged high) ....... 11.3%
Answers returned as unknown ......................... 21.0%
Legitimate centralised assets flagged high .......... 6.7%
Recall against actual rugs .......................... not measurable

Recall is unmeasurable today for a structural reason worth stating: 199
sampled tokens yielded zero dead ones, because every public data source
(DexScreener search, GeckoTerminal listings) ranks by liquidity, so rugged
pools drop off the list entirely. That data does not exist on any public
endpoint at any price. The only way to obtain it is to record pools while
alive and revisit them later, which VetAgent now does daily. Until that
dataset matures the figure stays blank rather than becoming a marketing
number.

Labels come from sources the engine itself never reads, and the benchmark
exits non-zero if the two endpoint sets ever intersect.
Full method: https://github.com/jakegu1/vetagent/blob/master/bench/results.md

## Limits

Covers observable on-chain risk only. Not investment advice. Does not size
positions. Cannot detect off-chain risk: team behaviour, social engineering,
or a rug executed through governance. Does not yet check LP lock status or
EVM holder concentration; open gaps are listed in docs/SCORECARD.md.

## Privacy

Token addresses you look up are not logged. They are used to query public
sources and discarded with the response. Aggregate counts only: which tool,
which verdict, a coarse client name, a country code. No IPs, no addresses.

## Business model

Free tier, paid tiers for volume and SLA. Takes no referral fees, no order
flow, and no payment from token projects — revenue that correlated with
saying "low risk" would destroy the only asset the tool has.
"""

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
<p><strong>No accounts, no cookies, no browser tracking.</strong> VetAgent has no
user database and serves no third-party scripts.</p>
<p><strong>We do not log the token addresses you look up.</strong> That query is the
most sensitive thing you send us &mdash; it can reveal what you are about to trade
&mdash; so it is used to fetch public data and then discarded with the response. This
is a deliberate trade: it means we cannot tell you which tokens are popular, and we
consider that the correct side of the trade for a tool whose only asset is trust.</p>
<p>We do keep aggregate usage counts, so we can tell whether anyone is using the
service. Each call records: which method and tool was invoked, the resulting risk
level, whether it errored, a coarse client name taken from the user agent, and the
country code Cloudflare attaches at the edge. <strong>No IP addresses, no full user
agents, no token addresses, nothing that identifies a person or a request.</strong></p>

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


def _record(env, blobs, doubles):
    """写一条用量数据点。

    三条约束，按重要性排：
    1. **绝不记录被查询的代币地址。** 那是用户的查询意图，能反推出他打算买什么。
       隐私政策承诺了不留存，代码就必须守住——这类承诺一旦破一次就再也不值钱。
    2. **绝不记录 IP 或完整 UA。** 国家 + MCP 客户端名足以回答
       「有没有外部调用方」，而这正是决策门要判的东西。
    3. **绝不因为观测失败而影响主路径。** 风控接口的可用性优先于统计。
    """
    try:
        ds = getattr(env, "ANALYTICS", None)
        if ds is None:
            return
        from js import Object
        from pyodide.ffi import to_js
        ds.writeDataPoint(to_js({"blobs": blobs, "doubles": doubles, "indexes": blobs[:1]},
                                dict_converter=Object.fromEntries))
    except Exception:  # noqa: BLE001
        pass


def _client_name(request):
    """取 MCP 客户端名。这是判断「是不是外部调用方」最干净的信号——
    它由客户端自己声明，不含任何个人数据。"""
    try:
        ua = request.headers.get("user-agent") or ""
    except Exception:  # noqa: BLE001
        ua = ""
    # 只保留粗粒度的客户端标识，丢掉版本号和其余部分
    ua = ua.split("/")[0].strip().lower()[:32]
    return ua or "unknown"


def _country(request):
    try:
        return (getattr(request, "cf", None) or {}).get("country") or "??"
    except Exception:  # noqa: BLE001
        return "??"


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

        # 给 LLM 读的站点摘要。我们的用户不 Google——他们问模型
        # 「怎么在 agent 里做代币安全检查」。被引用比被搜索到重要，
        # 而模型引用的是**可核对的具体数字**，不是形容词。
        # 所以这里连难看的数字（误报率、测不出的召回率）也一起给。
        if path == "/llms.txt":
            return Response(_LLMS_TXT, headers={"content-type": "text/plain; charset=utf-8"},
                            status=200)

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

        # 记一条用量。只记「调了哪个工具、结论是什么、来自哪种客户端」，
        # 不记地址、不记 IP。
        try:
            method = body.get("method") or "?"
            tool, verdict = "", ""
            if method == "tools/call":
                tool = (body.get("params") or {}).get("name") or "?"
                sc = ((result or {}).get("result") or {}).get("structuredContent") or {}
                verdict = sc.get("risk_level") or sc.get("status") or ""
            self._record_call(request, method, tool, verdict, result)
        except Exception:  # noqa: BLE001
            pass

        if result is None:
            return Response("", headers=_CORS, status=202)  # 通知无响应体
        return _json_response(result, extra_headers=headers)

    def _record_call(self, request, method, tool, verdict, result):
        is_error = bool((result or {}).get("error")
                        or ((result or {}).get("result") or {}).get("isError"))
        _record(self.env,
                [method, tool, verdict, _client_name(request), _country(request)],
                [1.0, 1.0 if is_error else 0.0])
