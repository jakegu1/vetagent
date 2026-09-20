"""entry.py — VetAgent Worker entrypoint (HTTP routing).

The core logic lives in risk.py (risk assessment) and mcp_server.py (MCP endpoint);
this file only dispatches routes. The entrypoint class has to be named Default —
Cloudflare requires it. request.url is a string, so parse it with urlparse.
"""

import json
import os
import re
from urllib.parse import parse_qsl, urlparse

from workers import Response, WorkerEntrypoint

import mcp_server
import og_image
import pages
import risk

_LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing.html")

# The **public key** record for MCP Registry domain verification. Being publicly
# readable is part of the design. The matching private key is not in this repo, and
# should not be in any repo.
_REGISTRY_AUTH = "v=MCPv1; k=ed25519; p=748fDl4SJZZt9TWfmYNDC3Xy1OIbfSjhf72vo8j8ZgI=\n"

# Domain-ownership proof for the Glama directory. Public by design, like the key above:
# the challenge only works if anyone can fetch it. It identifies the listing, not a
# person, and it must stay served -- Glama re-verifies, and ownership lapses if it 404s.
_GLAMA_CLAIM = (
    '{\n'
    '  "$schema": "https://glama.ai/mcp/schemas/connector.json",\n'
    '  "claim": "glama_claim_AmFi89yHEn61PWt8oMtitwH-xbAejCJ4"\n'
    '}\n'
)

# Pages an engine should index. Every URL here must resolve;
# tests/test_http_telemetry.py fetches each one.
_SITEMAP_URLS = ("https://vetagent.dev/", "https://vetagent.dev/api",
                 "https://vetagent.dev/unknown", "https://vetagent.dev/method",
                 "https://vetagent.dev/llms.txt", "https://vetagent.dev/llms-full.txt",
                 "https://vetagent.dev/privacy", "https://vetagent.dev/terms")
_SITEMAP_XML = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join("  <url><loc>%s</loc></url>\n" % u for u in _SITEMAP_URLS)
                + "</urlset>\n")
_ROBOTS_TXT = ("User-agent: *\n"
               "Allow: /\n"
               "\n"
               "Sitemap: https://vetagent.dev/sitemap.xml\n")

def _llms_full():
    """llms.txt plus every tool's full contract, read from the live tool list so it cannot drift."""
    out = [_LLMS_TXT, "", "## Reference pages", "",
           "https://vetagent.dev/api      how to call it over MCP or HTTP, and every field",
           "https://vetagent.dev/unknown  what unknown means, and when to retry or abstain",
           "https://vetagent.dev/method   how accuracy is measured, including the worst numbers",
           "", "## Tool reference (generated from the server's tools/list)", ""]
    for tool in mcp_server.TOOLS:
        out.append("### %s" % tool["name"])
        out.append("")
        out.append(tool.get("description", "").strip())
        out.append("")
        props = (tool.get("inputSchema") or {}).get("properties") or {}
        required = set((tool.get("inputSchema") or {}).get("required") or [])
        for name, spec in props.items():
            out.append("  %s%s: %s" % (name, "" if name in required else " (optional)",
                                       (spec.get("description") or spec.get("type") or "").strip()))
        out.append("")
    return chr(10).join(out) + chr(10)


# IndexNow (Bing, Yandex, Seznam, Naver and others share submissions). Not a secret: the
# protocol requires this exact string to be served at /<key>.txt on the host being submitted.
INDEXNOW_KEY = "bff341c9bde3fe572840f1d103debec5"

_LLMS_TXT = """# VetAgent

> A pre-trade safety check for AI agents. Before an agent buys, holds or
> recommends a crypto token, it calls VetAgent and gets an actionable verdict
> instead of forty raw fields.

MCP endpoint: https://vetagent.dev/mcp  (streamable-http, no auth, no API key)
HTTP API:     https://vetagent.dev/assess/{address}?chain_hint={chain}
Source:       https://github.com/jakegu1/vetagent  (MIT)
Contact:      hello@vetagent.dev  (no signup; the maintainer answers)
Terms:        https://vetagent.dev/terms  ·  Privacy: https://vetagent.dev/privacy
Registry:     dev.vetagent/vetagent on registry.modelcontextprotocol.io

## What it does

assess_token_risk(address, chain_hint?, verbose?)
  Returns risk_level (low | medium | high | unknown), a 0-100 risk_score,
  a confidence level, and every signal that fired with its evidence.
  Checks on every chain: liquidity depth, trading-pair age, cross-chain
  presence, same-ticker impersonation.
  Checks on Ethereum, BSC and Base only: sell simulation (honeypot detection),
  buy/sell/transfer taxes, whether the contract is open source, upstream scanner
  verdicts. No sell simulation runs on the four other EVM chains we accept, nor on
  Solana, so those answers are `unknown` rather than `low`.
  Checks on Solana: the mint/freeze authority and the Token-2022 extensions
  (transfer fee, permanent delegate, transfer hook, frozen-by-default), plus the
  RugCheck score. No holder concentration on any chain: on EVM it needs an oracle
  the benchmark holds out, and on Solana the upstream stopped sending holders.

get_token_liquidity(address, chain_hint?)
  Price, 24h volume, pair count and chains for the primary trading pair.
  Check `status` first: ok | not_found | unpriced | drained | unavailable.
  `unpriced` means nobody costed the pools, not that liquidity is zero.

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

## Measured accuracy (n=576, published)

False positives (healthy tokens flagged high) ....... 3.1%
Answers returned as unknown ......................... 21.2%
Centralised tokens (oracle-tagged) rated high ....... 22.3%
Dead tokens not rated low ........................... 86.7% (26 of 30)

What that last line does and does not say. Recall was unmeasurable here
until recently: every public data source ranks by liquidity, so rugged pools
drop off the list and sampling produced no dead tokens at all. Pools are now
recovered from chain history instead -- any past day is readable from the logs
of the contract that created the pool -- which produced a cohort of 30
confirmed-dead tokens.

The honest reading is not flattering. Only 3 of those 30 are rated high; 11
land at medium. That is close to correct rather than a miss: 13 of the 30
dead tokens still hold $5,000 or more of liquidity, so those positions can
still be sold. "Dead" means the project died, a market outcome, while this tool scores
whether you can get out, a safety property.

The number we would most like to publish -- recall against deliberately
adversarial contracts -- is still measured on 17 tokens, because the
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
or a rug executed through governance. Does not yet check LP lock status, and has
no holder concentration on any chain -- on EVM it needs an oracle the benchmark
holds out, on Solana the upstream omits holders. Does not test sellability on
Solana, nor on polygon, arbitrum, optimism and avalanche: the sell simulator
reaches three of the eight chains accepted as a chain_hint. Open gaps are listed
in docs/SCORECARD.md.

## Privacy

Token addresses you look up are not logged. They are used to query public
sources and discarded with the response. Aggregate counts only: which tool,
which verdict, a coarse client name, a country code, and for an unknown answer
which check could not run (e.g. "liquidity: dexscreener 429"). No IPs, no
addresses.

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
level, whether it errored, a coarse client name taken from the user agent, the
country code Cloudflare attaches at the edge, and -- only when the answer is
<code>unknown</code> -- which check could not run and what the data source answered, in
fixed words such as <code>liquidity:dexscreener 429</code>. <strong>No IP addresses, no full user
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
  <li>CoinGecko (on-chain API) &mdash; liquidity fallback when DexScreener does not answer,
      and distinct-seller counts; requested with our own API key since 2026-09-15</li>
  <li>GeckoTerminal &mdash; the same fallback without a key, if CoinGecko does not answer;
      new and trending pools</li>
  <li>honeypot.is &mdash; buy/sell simulation, on Ethereum, BSC and Base only</li>
  <li>RugCheck &mdash; Solana contract risk</li>
  <li>rpc.mevblocker.io (Ethereum), mainnet.base.org (Base),
      bsc-dataseed.bnbchain.org (BSC) &mdash; public RPC nodes, read-only
      <code>eth_getCode</code> to read the contract's own bytecode and see which
      powers it holds</li>
</ul>
<p>That last line was missing until 2026-09-09. The three RPC endpoints have received
the token address on every EVM assessment since the owner-powers check shipped, and this
page listed four recipients as though the list were complete. It is corrected here rather
than quietly, and <code>tests/test_http_telemetry.py</code> now fails the build if the
engine gains an outbound host this list does not name.</p>
<p>These are third-party services with their own privacy policies. We never send
them wallet addresses, identities, or anything about who is asking.</p>

<h2>Logs</h2>
<p>Cloudflare, which serves this Worker, keeps standard edge request metadata
(IP, timestamp, path) for operational and abuse-prevention purposes under its own
policy. We do not export, retain, sell, or analyse it, and we do not join it to
anything else.</p>
<p>To stop one caller using up the free upstream services every other caller depends on,
tool calls are counted per minute at the edge under a one-way hash of the connecting IP,
which expires after 70 seconds. The IP itself is not stored; a caller over the limit gets
HTTP 429 and can retry after a minute.</p>

<h2>Not financial advice</h2>
<p>VetAgent reports observable on-chain risk. It is not investment advice, does not
size positions, and cannot detect off-chain risk. A <code>low</code> verdict means
"no fatal signal found in the checks that ran" &mdash; never "safe to buy". A verdict
of <code>unknown</code> means a critical check could not be completed and must not be
read as low risk.</p>

<h2>Contact</h2>
<p>Questions about any of the above, or about data this service holds on you (it holds
none, and this page explains why): <a href="mailto:hello@vetagent.dev">hello@vetagent.dev</a>.
Anything public &mdash; bugs, a verdict you disagree with &mdash; is better as an issue at
<a href="https://github.com/jakegu1/vetagent">github.com/jakegu1/vetagent</a>.</p>
"""

# Directories that list a service ask for a terms URL alongside the privacy URL, and
# until now there was nothing to give them. Writing one is also the honest thing: this
# endpoint tells people whether to risk money, so the limits of what it claims should be
# stated somewhere they can point at, not only in a README section.
_TERMS_HTML = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VetAgent - Terms</title>
<style>
 body{max-width:44rem;margin:0 auto;padding:3rem 1.25rem;line-height:1.7;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
   background:#0d1117;color:#c9d1d9}
 h1{color:#e6edf3;font-size:1.9rem;margin:0 0 .4rem}
 h2{color:#e6edf3;font-size:1.05rem;margin:2rem 0 .5rem}
 a{color:#58a6ff} code{background:#161b22;padding:.1rem .35rem;border-radius:4px}
 .sub{color:#8b949e;margin:0 0 2rem}
</style>
<h1>Terms of use</h1>
<p class="sub">VetAgent &middot; last updated 2026-09-08</p>

<h2>What this is</h2>
<p>VetAgent reports <strong>observable on-chain risk</strong> about a token. It is a
measurement tool. It is <strong>not financial advice</strong>, it does not size positions,
and nothing it returns is a recommendation to buy, hold or sell anything.</p>

<h2>What a verdict means, and what it does not</h2>
<p><code>low</code> means <em>no fatal signal fired in the checks that actually ran</em>.
It does not mean safe. <code>unknown</code> means a critical check could not run at all;
it is not a low-risk result and must never be used to justify a trade.</p>
<p>There is risk this service cannot see: team behaviour, social engineering, off-chain
agreements, and rugs executed through governance. A token can pass every check here and
still take your money.</p>

<h2>Accuracy, stated rather than promised</h2>
<p>The service publishes its own measured error rates and the benchmark that produces
them, including the parts that do not work yet, at
<a href="https://github.com/jakegu1/vetagent/blob/master/bench/results.md">bench/results.md</a>.
Those numbers are the claim. Anything beyond them is not claimed. Upstream data sources
can be wrong, stale or unavailable, and when they are, the answer is
<code>unknown</code>.</p>

<h2>No warranty, and the liability limit</h2>
<p>The service is provided free, as is, with no warranty of any kind and no service level.
It may change, break or be withdrawn at any time. To the maximum extent permitted by law,
the maintainer is not liable for any loss arising from use of this service or reliance on
its output. <strong>You are responsible for your own trading decisions.</strong></p>
<p>The source code is MIT licensed; the licence governs the code, these terms govern the
hosted service.</p>

<h2>Acceptable use</h2>
<p>No authentication, no account, no rate limit you need to negotiate. In return: do not
attempt to disrupt the service for others, and do not present its output as a guarantee of
safety to anyone else. If the traffic ever threatens availability, rate limiting will be
added and said so on this page.</p>

<h2>Maintenance commitment</h2>
<p>A risk tool whose upstreams have drifted does not go quiet &mdash; it keeps answering,
just as confidently, and it is wrong precisely when someone is trusting it. So: as long as
this service is online it is maintained, and if it is ever no longer maintained it will be
taken offline rather than left to rot.</p>

<h2>Contact</h2>
<p><a href="mailto:hello@vetagent.dev">hello@vetagent.dev</a>, or an issue at
<a href="https://github.com/jakegu1/vetagent">github.com/jakegu1/vetagent</a>.
See also the <a href="/privacy">privacy page</a>.</p>
"""

# OpenAI's plugin directory verifies domain ownership by fetching a token from this path,
# and requires that the endpoint return **only** that plugin's token. The token is issued
# by their submission portal, which needs a verified identity, so it cannot be filled in
# from here. Until it is, the path 404s: serving a placeholder would be a wrong answer
# rather than no answer, and those are not the same thing.
_OPENAI_CHALLENGE = ""

_JSON = "application/json"
_CORS = {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, POST, OPTIONS",
    # x-mcp-client lets a caller name itself on every request, not only on initialize.
    # Without it here, a cross-origin caller that tries is blocked by its own browser.
    "access-control-allow-headers":
        "content-type, accept, mcp-protocol-version, mcp-session-id, x-mcp-client",
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


CLIENT_HEADER = "x-mcp-client"
LANDING_CLIENT = "vetagent-landing-demo"

# Hosts whose pages are ours. A call whose Origin or Referer is one of these came from
# the demo button on our own landing page.
_OUR_HOSTS = ("vetagent.dev", "www.vetagent.dev")


def _is_our_host(host):
    """Our custom domain, or the Worker's workers.dev fallback, vetagent.<account>.workers.dev.

    The account subdomain is not written here: it is the owner's account name, and it was
    taken out of the public files on 2026-09-18 (tests/test_no_private_identifiers.py).
    """
    return host in _OUR_HOSTS or (host.startswith("vetagent.") and host.endswith(".workers.dev")
                                  and host.count(".") == 3)


def _from_our_own_page(request):
    """Is this the demo button on our own landing page?

    The button sends `X-MCP-Client`, which would be enough if every visitor loaded fresh
    HTML. They do not: the worker sets `Cache-Control: no-cache` and the custom domain
    strips it, so a visitor can hold a copy of the page from before the tag existed and
    keep arriving as an anonymous browser -- the one bucket the usage gate cannot
    attribute, and the bucket that put a YES on the 09-18 gate.

    `Origin` and `Referer` are set by the browser, not by our JavaScript, so they are
    true of a cached page too. This is deliberately narrow: only OUR hosts count. An
    integrator calling from their own web app carries their own Origin and is unaffected.
    """
    for name in ("origin", "referer"):
        try:
            value = (request.headers.get(name) or "").strip().lower()
        except Exception:                                    # noqa: BLE001
            continue
        if not value:
            continue
        host = value.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        if _is_our_host(host):
            return True
    return False


_UPSTREAM_STATUS = re.compile(r"\b(dexscreener|coingecko|geckoterminal|honeypot\.is|rugcheck)"
                              r"(?: error body)? (\d{3})\b")

# Gap reasons, reduced to a fixed vocabulary. Order matters: the first phrase found wins.
_GAP_CLASSES = (
    ("does not cover", "chain not covered"),
    ("distinct-seller", "contested"),
    ("no record", "no record"),
    ("simulation failed", "simulation failed"),
    ("priced in an asset", "unpriced"),
    ("no source reported pool depth", "no depth"),
    ("no pair with a sane price", "price outlier"),
    ("no trading pair found", "no pair"),
    ("upstream request failed", "failed"),
)


def _why_unknown(answer):
    """Why an answer is `unknown`, in words this module chose -- "" for any other answer.

    "infrastructure|liquidity:dexscreener 429,geckoterminal 429|sellability:no record".
    Built only from `unknown_kind` (one of three values), the gap's dimension, a fixed list
    of reason classes, and upstream names with a three-digit status matched against a
    fixed list. Upstream text is never copied, so an address inside a revert message has
    nowhere to go (W35; the no-address rule in `_record`).
    """
    if not isinstance(answer, dict) or answer.get("risk_level") != "unknown":
        return ""
    kind = str(answer.get("unknown_kind") or "")
    if kind not in ("infrastructure", "coverage", "mixed"):
        kind = "unstated"
    per_dim = {}
    for gap in ((answer.get("evidence") or {}).get("data_gaps") or []):
        if not isinstance(gap, dict):
            continue
        dim = str(gap.get("dimension") or "")
        if dim not in ("liquidity", "sellability"):
            continue
        reason = str(gap.get("reason") or "")
        statuses = ["%s %s" % m for m in _UPSTREAM_STATUS.findall(reason)]
        if statuses and reason.startswith("upstream request failed"):
            tag = ",".join(dict.fromkeys(statuses))
        else:
            tag = next((label for phrase, label in _GAP_CLASSES if phrase in reason), "other")
        per_dim.setdefault(dim, [])
        if tag not in per_dim[dim]:
            per_dim[dim].append(tag)
    parts = [kind] + ["%s:%s" % (d, "+".join(per_dim[d])) for d in sorted(per_dim)]
    return "|".join(parts)[:160]


def _caller_id(request):
    """What the caller calls itself: header, then handshake declaration, then User-Agent.

    **`clientInfo` cannot label the rows the gate counts, and R15 claimed it could.**
    `declared_client()` reads a contextvar set while handling `initialize`. This server
    issues no `Mcp-Session-Id`, so every POST is a separate request in a separate
    context: on the `tools/call` that follows, the contextvar is back at its default.
    The claim that this "de-mushes 370 requests" is true of handshake rows only -- and
    handshake rows are exactly the rows `tool_callers()` throws away. For the gate the
    field was decorative.

    `X-MCP-Client` is the fix that works on the request that matters. Any caller can name
    itself on every request with one header, it survives having no session, and it is
    application self-description -- no address, no identity, nothing about a person. It
    is what the `initialize` instructions invite integrators to send, and our own landing
    page demo is the first thing to use it, so browser clicks stop hiding inside
    "mozilla".

    The User-Agent fallback stays, so nothing is lost for callers that send neither.
    """
    try:
        header = (request.headers.get(CLIENT_HEADER) or "").strip().lower()[:32]
    except Exception:                                        # noqa: BLE001
        header = ""
    if header:
        return header
    if _from_our_own_page(request):
        return LANDING_CLIENT
    declared = ""
    try:
        declared = mcp_server.declared_client()
    except Exception:                                        # noqa: BLE001
        declared = ""
    return (declared.strip().lower()[:32] or _client_name(request))


def _country(request):
    """Cloudflare's two-letter country for this request, or "??" if unavailable.

    This function returned "??" for **every request the service has ever served** --
    3,414 of 3,414 rows -- and not because Cloudflare withheld the field.

    `request.cf` is a **JsProxy of a plain JS object**, not a dict. The vendored SDK says
    so in as many words (`workers/request.py`: "access fields via attribute notation, for
    example ``request.cf.colo``"). A JsProxy over a plain object exposes no `.get`, so
    `(cf or {}).get("country")` raised AttributeError on every call, the bare `except`
    swallowed it, and "??" went into the blob.

    The cost was not cosmetic. STRATEGY §8 reasons about the gate from the premise that
    "the country filter has never excluded a single row ... it has been inert since it
    was written", and `bench/usage.py` prints "do not read it as protection." The
    discriminator that separates the owner's clicks from a stranger's was in the schema,
    already judged acceptable to record, and available the whole time. This is the third
    time in this project that the answer was already on disk.

    Attribute first, `.get` second, so a dict from a test and a JsProxy from production
    both work -- and so this never silently degrades to "??" again without saying why.
    """
    try:
        cf = getattr(request, "cf", None)
        if cf is None:
            return "??"
        country = getattr(cf, "country", None)
        if country is None and hasattr(cf, "get"):
            country = cf.get("country")
        return str(country)[:2].upper() if country else "??"
    except Exception:  # noqa: BLE001
        return "??"


def _truthy(v):
    """Accept a flag however the caller spelled it: bool, "true", "1", "yes"."""
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


# How many JSON-RPC messages one POST may carry, and how many tool calls one caller may make
# per window. Both exist because the upstreams this service reads are free, rate-limited by
# IP, and reached through an egress address the Worker shares: one caller's burst is spent
# out of every other caller's budget. Measured 2026-09-13: a 50-message batch returned 50
# assessments (about 200 upstream requests) in 1.42 s, and ten back-to-back calls drew no
# 429. 60 per minute is a guess aimed well above one agent checking tokens before a trade,
# not a measurement: the gate records no per-caller rates to measure it from.
MAX_BATCH = 10
RATE_LIMIT_CALLS = 60
RATE_LIMIT_PERIOD_SECONDS = 60


class _EdgeCounter:
    """Counts tool calls per caller per minute in the edge cache.

    Why not Cloudflare's rate-limit binding: it was deployed first (2026-09-14) and measured
    not enforcing. From one stable IP, 313 calls in 100 s against a 60-per-60-s binding were
    all answered success=true -- with the SDK converting a plain-dict key, the binding
    present, and the answer read back in a response header on every call. Cloudflare
    documents that binding as permissive and eventually consistent; whatever the reason, a
    limiter measured never to limit is not one.

    This one is approximate too, and says so: the cache is per data centre and a read-then-
    write can race, so concurrent calls in one location can overshoot. It is the same order
    of guarantee the binding advertised, with the difference that it was watched to trip.

    The key is a SHA-256 of the connecting IP, living 70 seconds in the edge cache. The IP
    itself is never stored or logged by this code.
    """

    async def limit(self, opts):
        import hashlib
        from js import Date, Object, Request, Response as JsResponse, caches
        from pyodide.ffi import to_js
        window = int(Date.now() / 1000.0 // RATE_LIMIT_PERIOD_SECONDS)
        digest = hashlib.sha256(str(opts["key"]).encode("utf-8")).hexdigest()[:32]
        req = Request.new("https://ratelimit.vetagent.internal/%s/%d" % (digest, window))
        hit = await caches.default.match(req)
        count = (int(await hit.text()) if hit else 0) + 1
        headers = to_js({"cache-control": "max-age=%d" % (RATE_LIMIT_PERIOD_SECONDS + 10)},
                        dict_converter=Object.fromEntries)
        await caches.default.put(req, JsResponse.new(
            str(count), to_js({"headers": headers}, dict_converter=Object.fromEntries)))
        return {"success": count <= RATE_LIMIT_CALLS}


_EDGE_COUNTER = _EdgeCounter()


async def _rate_limited(env, request):
    """True when this caller has used up its tool calls for the current window."""
    return (await _limit_state(env, request)) == "limited"


async def _limit_state(env, request):
    """"limited", "ok", or "open:<why>" -- the limiter's answer for this tool call.

    Returned in the `x-vetagent-ratelimit` response header on tool calls. The first
    deploy served 280 rapid calls without a 429 and left no way to tell "the limiter said
    yes" from "the limiter never ran"; the header is how the binding was found not to
    enforce. It carries nothing about the caller.

    `env.CALL_LIMITER`, when present, replaces the edge counter -- that is how the tests
    drive this without a Worker runtime.

    Fails OPEN -- no IP, no cache runtime, or a counter that throws all mean "not limited".
    A broken abuse control must not become an outage for everyone. The deploy smoke test
    floods production and requires a 429, so "open" cannot quietly become permanent.
    """
    limiter = getattr(env, "CALL_LIMITER", None) if env is not None else None
    if limiter is None:
        limiter = _EDGE_COUNTER
    try:
        key = request.headers.get("cf-connecting-ip") or ""
    except Exception as e:  # noqa: BLE001
        return "open:headers-%s" % type(e).__name__
    if not key:
        return "open:no-ip"
    try:
        outcome = await limiter.limit({"key": key})
        success = (outcome.get("success") if isinstance(outcome, dict)
                   else getattr(outcome, "success", None))
        if success is None:
            return "open:no-answer"
        return "limited" if success is False else "ok"
    except Exception as e:  # noqa: BLE001
        return "open:%s" % type(e).__name__


def _rate_limit_error(message_id):
    return {"jsonrpc": "2.0", "id": message_id,
            "error": {"code": -32000,
                      "message": "Rate limit exceeded: retry after %d seconds"
                                 % RATE_LIMIT_PERIOD_SECONDS}}


def _is_tool_call(message):
    return isinstance(message, dict) and message.get("method") == "tools/call"


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
        # Provider keys live in Worker secrets (CG_DEMO_KEY). Read per request so a key set or
        # rotated with `wrangler secret put` takes effect without a code change.
        risk.configure(self.env)
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
                    # no-cache, because this page's JavaScript identifies itself to our
                    # own telemetry. A visitor holding a cached copy from before the
                    # `X-MCP-Client` tag shipped keeps arriving as an anonymous browser,
                    # which is the one bucket the usage gate cannot attribute. Correctness
                    # of the measurement beats one round trip on a 19 KiB page.
                    return Response(f.read(),
                                    headers={"content-type": "text/html",
                                             "cache-control": "no-cache"},
                                    status=200)
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

        if path == "/terms":
            return Response(_TERMS_HTML, headers={"content-type": "text/html"}, status=200)

        # Domain verification for the OpenAI plugin directory. Their requirement is that
        # this returns only the token, so it is served as bare text with nothing around
        # it -- and 404s while no token has been issued, because "we have not been given
        # one" and "here is a token" must not look the same to their checker.
        if path == "/.well-known/openai-apps-challenge":
            if not _OPENAI_CHALLENGE:
                return Response("", headers={"content-type": "text/plain"}, status=404)
            return Response(_OPENAI_CHALLENGE,
                            headers={"content-type": "text/plain"}, status=200)

        # Site summary written for LLMs. Our users don't Google — they ask a model
        # "how do I do a token safety check inside an agent". Being cited beats being
        # searchable, and models cite **concrete numbers you can check**, not
        # adjectives. So the unflattering ones go in here too: the false-positive
        # rate, and the recall we can't measure.
        if path == "/llms.txt":
            return Response(_LLMS_TXT, headers={"content-type": "text/plain; charset=utf-8"},
                            status=200)

        # Search engines had nothing pointing at this site: GEO baseline 2026-09-15 found
        # `site:vetagent.dev` empty and the domain in none of fifteen result lists, with no
        # sitemap and no Sitemap line in robots.txt. Cloudflare prepends its managed content
        # signals to whatever robots.txt the origin serves, so this file only adds rules.
        # One question per page, for the searches VetAgent was absent from (bench/geo/).
        if path in pages.PAGES:
            return Response(pages.PAGES[path],
                            headers={"content-type": "text/html; charset=utf-8"}, status=200)
        if path == "/og.png":
            return Response(og_image.PNG, headers={"content-type": "image/png",
                                                   "cache-control": "public, max-age=86400"},
                            status=200)
        if path == "/llms-full.txt":
            return Response(_llms_full(), headers={"content-type": "text/plain; charset=utf-8"},
                            status=200)
        if path == "/sitemap.xml":
            return Response(_SITEMAP_XML, headers={"content-type": "application/xml; charset=utf-8"},
                            status=200)
        if path == "/robots.txt":
            return Response(_ROBOTS_TXT, headers={"content-type": "text/plain; charset=utf-8"},
                            status=200)
        # IndexNow key file. Public by protocol, like the registry key: an engine accepts a
        # URL submission for this host only if this file answers with the submitted key.
        if path == "/%s.txt" % INDEXNOW_KEY:
            return Response(INDEXNOW_KEY, headers={"content-type": "text/plain; charset=utf-8"},
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

        # Glama's directory listing was created by auto-indexing the official MCP
        # registry, not by us, so the entry existed before we knew about it. Serving this
        # proves we control the domain and lets the listing be corrected rather than left
        # as whatever the registry happened to say.
        #
        # Being publicly readable is the point, exactly as with the registry key above.
        # The token identifies the listing, not a person, and it has to stay in place --
        # Glama re-checks it, and ownership lapses if it disappears.
        if path == "/.well-known/glama.json":
            return Response(_GLAMA_CLAIM,
                            headers={"content-type": "application/json"}, status=200)

        # Which tool this request turned out to be for, if it got that far. The error
        # handlers below need it, and a request that never reached a route leaves it
        # empty -- a 404 is not a failed tool call.
        tool = ""
        limited_tool = ("assess_token_risk" if path == "/assess" or path.startswith("/assess/")
                        else "get_token_liquidity" if path.startswith("/liquidity/")
                        else "find_new_hot_pools" if path == "/new-pools" else "")
        if limited_tool:
            state = await _limit_state(self.env, request)
            if state == "limited":
                # Recorded as a failed call to the tool it was, so the gate sees it and a
                # refusal never counts as a verdict.
                self._record_http_error(request, limited_tool)
                return _json_response(
                    {"error": "rate_limited",
                     "detail": "Too many calls; retry after %d seconds."
                               % RATE_LIMIT_PERIOD_SECONDS},
                    status=429,
                    extra_headers={"retry-after": str(RATE_LIMIT_PERIOD_SECONDS),
                                   "x-vetagent-ratelimit": state})
        try:
            # POST /assess keeps the address in the body. GET /assess/<address> is
            # kept because it is genuinely convenient, but a URL is logged by every hop
            # that carries it, and the privacy page now says so rather than implying
            # otherwise.
            if path == "/assess" and request.method == "POST":
                tool = "assess_token_risk"
                body = await _read_json(request)
                if not isinstance(body, dict) or not body.get("address"):
                    self._record_http_error(request, tool)
                    return _json_response({"error": "POST /assess needs "
                                                    "{\"address\": \"0x...\"}"},
                                          status=400)
                return _json_response(self._record_http(
                    request, "assess_token_risk", await risk.assess(
                        body.get("address", ""),
                        body.get("chain_hint") or body.get("chain"),
                        _truthy(body.get("verbose")))))

            if path.startswith("/assess/"):
                tool = "assess_token_risk"
                return _json_response(self._record_http(
                    request, "assess_token_risk", await risk.assess(
                        path[len("/assess/"):],
                        query.get("chain_hint") or query.get("chain"),
                        _truthy(query.get("verbose")))))

            if path.startswith("/liquidity/"):
                tool = "get_token_liquidity"
                return _json_response(self._record_http(
                    request, "get_token_liquidity", await risk.liquidity(
                        path[len("/liquidity/"):],
                        query.get("chain_hint") or query.get("chain"))))

            if path == "/new-pools":
                tool = "find_new_hot_pools"
                return _json_response(self._record_http(
                    request, "find_new_hot_pools", await risk.new_pools(
                        query.get("chain", "solana"), query.get("limit", 10))))
        except ValueError as e:
            self._record_http_error(request, tool)
            return _json_response({"error": "invalid_request", "detail": str(e)}, status=400)
        except Exception as e:  # noqa: BLE001
            self._record_http_error(request, tool)
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

        # Streamable HTTP: "If the server receives a request with an invalid or unsupported
        # `MCP-Protocol-Version`, it MUST respond with `400 Bad Request`." We answered 200 to
        # anything, including the string "banana", until 2026-09-10.
        #
        # `SUPPORTED_PROTOCOLS` was already the right list and was already correct -- it
        # negotiated `initialize` and nothing ever consulted it for the header. The allowlist
        # existed and no code read it, which is the same shape as a guard that is defined and
        # never called.
        #
        # Two deliberate exemptions, both fail-open, because the failure mode of getting this
        # wrong is refusing a client that would have worked:
        #
        # - An ABSENT header passes. The spec says the server SHOULD then assume 2025-03-26,
        #   and every client older than the header sends nothing. Absence here is a client
        #   that never negotiated, not a client asking for something we cannot do -- the same
        #   distinction the engine makes between `unknown` and a finding.
        # - `initialize` passes whatever it carries. A client cannot know the negotiated
        #   version before it has negotiated, so enforcing there would turn a rule about
        #   subsequent requests into a lockout on the first one.
        #
        # THE OBLIGATION THIS CREATES, written here because it is the cost of the fix rather
        # than a footnote to it: when the next protocol version is published, it has to go
        # into `SUPPORTED_PROTOCOLS` or clients using it will get a 400 from us. Before this
        # change a new version cost nothing; now it costs one line, and the failure mode of
        # forgetting is a refusal rather than a warning. `tests/test_upstream_contract.py`
        # is where a check on the published version list would belong if this ever bites.
        asked = request.headers.get("mcp-protocol-version")
        if asked is not None and asked not in mcp_server.SUPPORTED_PROTOCOLS:
            method = None
            if isinstance(body, dict):
                method = body.get("method")
            if method != "initialize":
                return _json_response(
                    {"jsonrpc": "2.0", "id": (body.get("id")
                                              if isinstance(body, dict) else None),
                     "error": {"code": mcp_server.INVALID_REQUEST,
                               "message": "Unsupported MCP-Protocol-Version",
                               "data": {"requested": str(asked)[:40],
                                        "supported": list(mcp_server.SUPPORTED_PROTOCOLS)}}},
                    status=400, extra_headers=headers)

        # Batch request — JSON-RPC allows an array
        if isinstance(body, list):
            if not body:
                return _json_response(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": mcp_server.INVALID_REQUEST, "message": "Empty batch"}},
                    status=400)
            if len(body) > MAX_BATCH:
                return _json_response(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": mcp_server.INVALID_REQUEST,
                               "message": "Batch too large: at most %d messages per request"
                                          % MAX_BATCH}},
                    status=400, extra_headers=headers)
            # One bad message must not take the batch down with it. /mcp is routed
            # before the try/except that guards /assess and /liquidity, so an
            # unforeseen exception here meant no response at all -- for every message
            # in the batch, including the well-formed ones.
            responses = []
            for item in body:
                if _is_tool_call(item) and await _rate_limited(self.env, request):
                    r = _rate_limit_error(item.get("id"))
                    self._record_message(request, item, r)
                    responses.append(r)
                    continue
                try:
                    r = await mcp_server.handle_mcp_request(item)
                except Exception:  # noqa: BLE001
                    r = {"jsonrpc": "2.0",
                         "id": (item.get("id") if isinstance(item, dict) else None),
                         "error": {"code": mcp_server.INTERNAL_ERROR,
                                   "message": "Internal error"}}
                # A batched tools/call is still a tool call. This loop returned before
                # reaching the recording block below, so every message inside a batch was
                # invisible to the gate -- the same defect as /assess, in the one code
                # path a real integration is most likely to use once it has more than one
                # token to check.
                self._record_message(request, item, r)
                if r is not None:
                    responses.append(r)
            if not responses:
                return Response("", headers=_CORS, status=202)
            return _json_response(responses, extra_headers=headers)

        if _is_tool_call(body):
            headers["x-vetagent-ratelimit"] = await _limit_state(self.env, request)
            if headers["x-vetagent-ratelimit"] == "limited":
                r = _rate_limit_error(body.get("id"))
                self._record_message(request, body, r)
                limited = dict(headers)
                limited["retry-after"] = str(RATE_LIMIT_PERIOD_SECONDS)
                return _json_response(r, status=429, extra_headers=limited)

        try:
            result = await mcp_server.handle_mcp_request(body)
        except Exception:  # noqa: BLE001
            return _json_response(
                {"jsonrpc": "2.0",
                 "id": (body.get("id") if isinstance(body, dict) else None),
                 "error": {"code": mcp_server.INTERNAL_ERROR,
                           "message": "Internal error"}},
                extra_headers=headers)

        self._record_message(request, body, result)

        if result is None:
            return Response("", headers=_CORS, status=202)  # notification: no response body
        return _json_response(result, extra_headers=headers)

    def _record_message(self, request, message, result):
        """Record one JSON-RPC message: which tool, what verdict, what kind of client.

        No addresses, no IPs, no token queries -- the same invariant as everywhere else.

        `tool` used to be recorded as "?" when `tools/call` arrived without a name. That
        is a malformed request, and it was landing in the gate's evidence as a tool call
        indistinguishable from a real one. An unnamed tool is not tool use, so it records
        as empty and `tool_callers()` skips it like any other non-call.
        """
        try:
            method = message.get("method") or "?"
            tool, verdict = "", ""
            if method == "tools/call":
                tool = (message.get("params") or {}).get("name") or ""
                sc = ((result or {}).get("result") or {}).get("structuredContent") or {}
                verdict = sc.get("risk_level") or sc.get("status") or ""
            self._record_call(request, method, tool, verdict, result)
        except Exception:  # noqa: BLE001
            pass

    def _record_http(self, request, tool, result):
        """Record an HTTP call the same way an MCP call is recorded.

        `_record_call` was reachable only from `_handle_mcp`, so every /assess,
        /liquidity and /new-pools request was invisible. The 2026-09-18 gate asks whether
        anyone outside this project uses the tool, and it has been answering that
        question from one of the two interfaces the product actually exposes.

        The distinction is not academic. An integrator wiring this into a bot reaches for
        curl or requests against /assess long before they configure an MCP client, so the
        surface most likely to carry a first real user was the surface with no telemetry
        on it at all.

        Same blob layout as the MCP path, so `bench/usage.py` needs no special case, with
        `method` set to "http" so the two can still be told apart. The token address is
        NOT recorded, here or anywhere -- that invariant is why this server cannot
        identify its callers, and it stands.
        """
        verdict = ""
        if isinstance(result, dict):
            verdict = str(result.get("risk_level") or result.get("status") or "")[:24]
        is_error = isinstance(result, dict) and bool(result.get("error"))
        _record(self.env,
                ["http", tool, verdict, _caller_id(request), _country(request),
                 _why_unknown(result)],
                [1.0, 1.0 if is_error else 0.0])
        return result

    def _record_http_error(self, request, tool):
        """Record an HTTP tool call that failed. The success path had one; this did not.

        `risk.assess(...)` is awaited inside the argument list of `_record_http`, so when
        it raised, `_record_http` was never called and the outer handler returned 400 or
        500 having recorded nothing. The MCP path records its errors. So a caller whose
        HTTP calls all failed was invisible to the 2026-09-18 gate, while the same caller
        over MCP was visible. Measured once, on 2026-09-08: 9.3% of requests in the
        14-day window were errors.

        The verdict is left empty on purpose. An error is not a verdict, and writing one
        here would let a caller clear "received a real verdict" and "two distinct
        verdicts" on failures alone. This makes them *visible*, which is what was
        missing; it must not make them *qualify*.

        Rows not written today cannot be recovered later, which is why this could not
        wait for the gate.
        """
        if not tool:
            return                    # never reached a tool: a 404 is not a tool call
        _record(self.env,
                ["http", tool, "", _caller_id(request), _country(request), ""],
                [1.0, 1.0])

    def _record_call(self, request, method, tool, verdict, result):
        is_error = bool((result or {}).get("error")
                        or ((result or {}).get("result") or {}).get("isError"))
        sc = ((result or {}).get("result") or {}).get("structuredContent") \
            if isinstance(result, dict) else None
        _record(self.env,
                [method, tool, verdict, _caller_id(request), _country(request),
                 _why_unknown(sc)],
                [1.0, 1.0 if is_error else 0.0])
