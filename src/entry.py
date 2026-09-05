"""entry.py — VetAgent Worker entrypoint (HTTP routing).

The core logic lives in risk.py (risk assessment) and mcp_server.py (MCP endpoint);
this file only dispatches routes. The entrypoint class has to be named Default —
Cloudflare requires it. request.url is a string, so parse it with urlparse.
"""

import json
import os
from urllib.parse import parse_qsl, urlparse

from workers import Response, WorkerEntrypoint

import mcp_server
import risk

_LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing.html")

# The **public key** record for MCP Registry domain verification. Being publicly
# readable is part of the design. The matching private key is not in this repo, and
# should not be in any repo.
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

## Measured accuracy (n=558, published)

False positives (healthy tokens flagged high) ....... 3.5%
Answers returned as unknown ......................... 17.2%
Legitimate centralised assets flagged high .......... 6.7%
Dead tokens not rated low ........................... 95% (19 of 20)

What that last line does and does not say. Recall was unmeasurable here
until recently: every public data source ranks by liquidity, so rugged pools
drop off the list and sampling produced no dead tokens at all. Pools are now
recovered from chain history instead -- any past day is readable from the logs
of the contract that created the pool -- which produced a cohort of 20
confirmed-dead tokens.

The honest reading is not flattering. Only 2 of those 20 are rated high; most
land at medium. That is close to correct rather than a miss: half the dead
cohort still holds over $5,000 of liquidity, so those positions can still be
sold. "Dead" means the project died, a market outcome, while this tool scores
whether you can get out, a safety property.

The number we would most like to publish -- recall against deliberately
adversarial contracts -- is still measured on about five tokens, because the
oracle that labels them raises its honeypot flag whenever its own sell
simulation fails, and that happens against any empty pool whatever the contract
does. Until that cohort grows, read this tool as answering "can I still get out
of this" rather than "is this a scam".

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

# Privacy policy, inlined instead of a separate file because it has to be reachable
# forever — directory reviews fetch this URL directly, and a 404 is an instant
# rejection.
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
<p><strong>Our analytics never records the token address.</strong> That query is the
most sensitive thing you send us &mdash; it can reveal what you are about to trade
&mdash; so it is used to fetch public data and then discarded with the response. This
is a deliberate trade: it means we cannot tell you which tokens are popular, and we
consider that the correct side of the trade for a tool whose only asset is trust.</p>
<p>We do keep aggregate usage counts, so we can tell whether anyone is using the
service. Each call records: which method and tool was invoked, the resulting risk
level, whether it errored, a coarse client name taken from the user agent, and the
country code Cloudflare attaches at the edge. <strong>No IP addresses, no full user
agents, no token addresses, nothing that identifies a person or a request.</strong></p>

<h2>One thing we cannot promise for you</h2>
<p>The line above is about what <em>we</em> record, and it is enforced in code. It is not
a claim about the internet. The convenience route <code>GET /assess/&lt;address&gt;</code>
carries the address in the URL, and URLs are visible to the platform serving the request
and to anything between you and it. We do not control those logs and neither do you.</p>
<p>If that matters for what you are looking up, use a route that keeps the address out of
the URL: the MCP endpoint at <code>/mcp</code> is a POST and carries it in the body, and
<code>POST /assess</code> accepts <code>{"address": "0x...", "chain_hint": "..."}</code>
for the same reason. Same answer, same code path.</p>

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
    """Write one usage data point.

    Three constraints, most important first:
    1. **Never log the token address being queried.** That is the user's intent,
       and it reveals what they are about to buy. The privacy policy promises we
       don't retain it, so the code has to hold that line — a promise like this is
       worthless the moment it is broken once.
    2. **Never log IPs or full user agents.** Country plus MCP client name is
       enough to answer "is anyone outside actually calling this", which is the
       question the decision gate turns on.
    3. **Never let a failure here touch the main path.** The risk endpoint staying
       up beats collecting statistics.
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
    """Get the MCP client name. It is the cleanest signal for whether the caller is
    external — the client declares it itself, and it carries no personal data."""
    try:
        ua = request.headers.get("user-agent") or ""
    except Exception:  # noqa: BLE001
        ua = ""
    # Keep a coarse client identifier only; drop the version and everything after it
    ua = ua.split("/")[0].strip().lower()[:32]
    return ua or "unknown"


def _country(request):
    try:
        return (getattr(request, "cf", None) or {}).get("country") or "??"
    except Exception:  # noqa: BLE001
        return "??"


def _truthy(v):
    """Accept a flag however the caller spelled it: bool, "true", "1", "yes"."""
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


async def _read_json(request):
    """Parse a JSON request body, returning None rather than raising."""
    try:
        return json.loads(await request.text())
    except Exception:  # noqa: BLE001
        return None


def _json_response(obj, status=200, extra_headers=None):
    headers = {"content-type": _JSON}
    headers.update(_CORS)
    if extra_headers:
        headers.update(extra_headers)
    return Response(json.dumps(obj, ensure_ascii=False), headers=headers, status=status)


class Default(WorkerEntrypoint):
    """Worker entrypoint. Cloudflare requires the entrypoint class to be named Default."""

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

        # Site summary written for LLMs. Our users don't Google — they ask a model
        # "how do I do a token safety check inside an agent". Being cited beats being
        # searchable, and models cite **concrete numbers you can check**, not
        # adjectives. So the unflattering ones go in here too: the false-positive
        # rate, and the recall we can't measure.
        if path == "/llms.txt":
            return Response(_LLMS_TXT, headers={"content-type": "text/plain; charset=utf-8"},
                            status=200)

        # Domain-ownership verification for the official MCP Registry. Verifying by
        # domain rather than a GitHub account keeps the namespace at dev.vetagent/*
        # instead of io.github.<someone>/* — the product's identity hangs on the
        # product's domain, not on one person's account.
        # Public key only; the private key lives outside the repo and is never
        # committed.
        if path == "/.well-known/mcp-registry-auth":
            return Response(_REGISTRY_AUTH,
                            headers={"content-type": "text/plain"}, status=200)

        try:
            # POST /assess keeps the address in the body. GET /assess/<address> is
            # kept because it is genuinely convenient, but a URL is logged by every hop
            # that carries it, and the privacy page now says so rather than implying
            # otherwise.
            if path == "/assess" and request.method == "POST":
                body = await _read_json(request)
                if not isinstance(body, dict) or not body.get("address"):
                    return _json_response({"error": "POST /assess needs "
                                                    "{\"address\": \"0x...\"}"},
                                          status=400)
                return _json_response(await risk.assess(
                    body.get("address", ""),
                    body.get("chain_hint") or body.get("chain"),
                    _truthy(body.get("verbose"))))

            if path.startswith("/assess/"):
                return _json_response(await risk.assess(
                    path[len("/assess/"):],
                    query.get("chain_hint") or query.get("chain"),
                    _truthy(query.get("verbose"))))

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
        """MCP streamable-http: POST one JSON-RPC message, get one response back."""
        if request.method == "GET":
            # In streamable-http, GET opens an SSE stream. We don't push from the
            # server, so return 405 as the spec says, which tells the client not to
            # wait — better than replying with a chunk of human-readable prose.
            return _json_response(
                {"error": "sse_not_supported",
                 "detail": "VetAgent is a stateless MCP server; POST your JSON-RPC request."},
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

        # Batch request — JSON-RPC allows an array
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

        # Record one usage point: which tool was called, what the verdict was, and
        # what kind of client it came from. No addresses, no IPs.
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
            return Response("", headers=_CORS, status=202)  # notification: no response body
        return _json_response(result, extra_headers=headers)

    def _record_call(self, request, method, tool, verdict, result):
        is_error = bool((result or {}).get("error")
                        or ((result or {}).get("result") or {}).get("isError"))
        _record(self.env,
                [method, tool, verdict, _client_name(request), _country(request)],
                [1.0, 1.0 if is_error else 0.0])
