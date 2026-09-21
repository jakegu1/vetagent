"""pages.py -- the reference pages a search engine or a model can cite, one question each.

Why these exist: GEO baseline 2026-09-15 (bench/geo/) found vetagent.dev in none of fifteen
search result lists and `site:vetagent.dev` empty. Crawlers were reaching the site -- the zone
logs show Googlebot, bingbot, OAI-SearchBot, ClaudeBot and GPTBot receiving 200 -- but it was one
landing page, so there was nothing that answered a specific question an agent developer asks.

Every accuracy figure on these pages is written by `python bench/publish_numbers.py --write` and
checked by tests/test_published_numbers.py, like every other surface. The oracle that labels the
benchmark is not named here: src/ must never contain its name (DECISIONS B2).
"""

_CSS = """
 :root{--bg:#0B1110;--panel:#111917;--line:#1E2B29;--txt:#DDE7E4;--dim:#8AA09C;--accent:#3FBFAA}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--txt);line-height:1.7;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
 main{max-width:46rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
 nav{font-size:.9rem;color:var(--dim);margin-bottom:2rem}
 nav a{color:var(--dim);margin-right:1rem}
 h1{font-size:1.9rem;line-height:1.3;margin:0 0 .6rem;text-wrap:balance}
 h2{font-size:1.15rem;margin:2.2rem 0 .6rem}
 .lede{color:var(--dim);font-size:1.05rem;margin:0 0 1.5rem}
 a{color:var(--accent)}
 code{background:var(--panel);padding:.1rem .35rem;border-radius:4px;font-size:.92em}
 pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:1rem;
   overflow-x:auto;font-size:.88rem;line-height:1.55}
 pre code{background:none;padding:0}
 table{border-collapse:collapse;font-size:.95rem;margin:.5rem 0 1rem}
 th,td{border-bottom:1px solid var(--line);padding:.5rem .4rem;text-align:left;vertical-align:top}
 th{color:var(--dim);font-weight:600}
 td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
 footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--dim);
   font-size:.9rem}
"""

_NAV = ('<nav><a href="/">VetAgent</a><a href="/api">API</a><a href="/unknown">unknown</a>'
        '<a href="/method">Method</a><a href="https://github.com/jakegu1/vetagent">GitHub</a></nav>')


def _page(path, title, description, body, jsonld):
    url = "https://vetagent.dev%s" % path
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="canonical" href="%(url)s">
<meta property="og:type" content="article">
<meta property="og:site_name" content="VetAgent">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:url" content="%(url)s">
<meta property="og:image" content="https://vetagent.dev/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(description)s">
<meta name="twitter:image" content="https://vetagent.dev/og.png">
<script type="application/ld+json">%(jsonld)s</script>
<style>%(css)s</style>
</head>
<body><main>
%(nav)s
%(body)s
<footer>VetAgent &middot; free, no key, MIT &middot;
<a href="https://vetagent.dev/mcp">MCP endpoint</a> &middot; <a href="/privacy">privacy</a> &middot;
<a href="/terms">terms</a> &middot; <a href="/llms.txt">llms.txt</a>. Reports observable on-chain
risk; not investment advice.</footer>
</main></body></html>
""" % {"title": title, "description": description, "url": url, "jsonld": jsonld,
       "css": _CSS, "nav": _NAV, "body": body}


# ------------------------------------------------------------------ /api

_API_BODY = """
<h1>Honeypot and rug-pull check API for AI agents</h1>
<p class="lede">One call before your agent buys a token: liquidity depth, pair age and
same-ticker impersonation on all eight chains, a sell simulation and the taxes on Ethereum, BSC
and Base, rolled into <code>low</code>, <code>medium</code>, <code>high</code> or
<code>unknown</code> with every signal behind it. Remote MCP server and plain
HTTP. Free, no account, no API key.</p>

<h2>Connect over MCP</h2>
<p>Streamable HTTP at <code>https://vetagent.dev/mcp</code>. Any MCP client that accepts a remote
server URL works; for one that reads a JSON config:</p>
<pre><code>{
  "mcpServers": {
    "vetagent": { "type": "http", "url": "https://vetagent.dev/mcp" }
  }
}</code></pre>
<p>Three tools: <code>assess_token_risk</code> (the verdict), <code>get_token_liquidity</code>
(price and depth only) and <code>find_new_hot_pools</code> (discovery, never an endorsement).</p>

<h2>Or call it over HTTP</h2>
<pre><code># the address in the body, which keeps it out of URLs and logs along the way
curl -X POST https://vetagent.dev/assess \\
  -H 'content-type: application/json' \\
  -d '{"address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "chain_hint": "base"}'

# convenient, but the address travels in the URL
curl "https://vetagent.dev/assess/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913?chain_hint=base"</code></pre>

<h2>What comes back</h2>
<p>A shortened real answer for USDC on Base (evidence trimmed):</p>
<pre><code>{
  "risk_level": "low",
  "risk_score": 0,
  "confidence": "high",
  "driver": null,
  "signals": [
    {"severity": "ok", "name": "Liquidity is adequate", "category": "liquidity"},
    {"severity": "ok", "name": "Buys and sells normally", "category": "honeypot"}
  ],
  "recommendation": "Low risk: sellable and liquid when checked, no fatal signal. ...",
  "checked_at": "2026-09-15T05:17:23Z",
  "evidence_max_age_seconds": 0
}</code></pre>
<table>
<tr><th>Field</th><th>How an agent should read it</th></tr>
<tr><td><code>risk_level</code></td><td><code>low</code> means no fatal signal in the checks that
ran &mdash; the exit was open when we looked, not that nobody can close it. <code>medium</code>:
real signals, none fatal; surface them. <code>high</code>: do not proceed unreviewed.
<code>unknown</code>: a critical check could not run &mdash; <a href="/unknown">never a green
light</a>.</td></tr>
<tr><td><code>driver</code></td><td>The one signal that decided the verdict, by name and
category. <code>null</code> when nothing above <code>ok</code> fired.</td></tr>
<tr><td><code>confidence</code></td><td>How complete the input data was, not how safe the token
is. An answer that leaned on cached data is at most <code>medium</code>.</td></tr>
<tr><td><code>unknown_kind</code>, <code>next_action</code></td><td>Only on
<code>unknown</code>: whether to retry (our upstream failed) or abstain (nothing can see the
token, or we do not cover its chain). An answer can hold both, and then it says both.</td></tr>
<tr><td><code>checked_at</code>, <code>evidence_max_age_seconds</code></td><td>When the answer was
made, and how old its oldest evidence is.</td></tr>
</table>

<h2>What it checks, and where</h2>
<table>
<tr><th>Check</th><th>Chains</th></tr>
<tr><td>Buy/sell simulation (honeypot), buy/sell/transfer tax</td><td>Ethereum, BSC, Base</td></tr>
<tr><td>Mint and freeze authority; the Token-2022 extension block &mdash; non-transferable, frozen-by-default, transfer fee (with its cap), permanent delegate, transfer hook, pausable, close authority, scaled balances, interest-bearing balances &mdash; with every other extension the report carries named in the answer beside the reason it is not scored. No sell test; holder concentration unavailable while the upstream omits holders</td><td>Solana</td></tr>
<tr><td>Liquidity depth &mdash; counted only for reserves held in independently priced assets,
so a pool priced in its creator's own token cannot buy a <code>low</code></td><td>Ethereum, BSC,
Base, Arbitrum, Optimism, Polygon, Avalanche, Solana; elsewhere the depth a pool states is used
as stated</td></tr>
<tr><td>Pair age, 24h turnover across the token's pools</td><td>Every chain</td></tr>
<tr><td>Same-ticker impersonation, within one chain</td><td>Every chain</td></tr>
<tr><td>Owner powers in the bytecode (blacklist, tax change, pause, mint) &mdash; disclosed,
never scored</td><td>Ethereum, BSC, Base</td></tr>
</table>
<p>On a chain the sell simulator does not cover, the answer says so and comes back
<code>unknown</code> rather than pretending the check ran. Pass <code>chain_hint</code>
(<code>ethereum</code>, <code>bsc</code>, <code>base</code>, <code>arbitrum</code>,
<code>polygon</code>, <code>optimism</code>, <code>avalanche</code>, <code>solana</code>): the same
address can exist on several chains, and without a hint an answer covers the one holding the most
depth and names it.</p>

<h2>Limits</h2>
<p>About 60 tool calls a minute per caller, then HTTP 429 with <code>Retry-After</code>. At most 10
messages in one JSON-RPC batch. The token address you look up is not logged. How accurate it is,
including the numbers that make it look worst, is on <a href="/method">the method page</a>.</p>
"""

_API_JSONLD = """{"@context":"https://schema.org","@type":"TechArticle",
"headline":"Honeypot and rug-pull check API for AI agents",
"description":"How to call VetAgent over MCP or HTTP before an AI agent buys a token, what the answer contains, and what each field means.",
"url":"https://vetagent.dev/api","image":"https://vetagent.dev/og.png",
"author":{"@type":"Organization","name":"VetAgent","url":"https://vetagent.dev/"},
"about":{"@type":"SoftwareApplication","name":"VetAgent","applicationCategory":"DeveloperApplication","url":"https://vetagent.dev/"}}"""

API_HTML = _page(
    "/api", "Honeypot and rug-pull check API for AI agents (MCP and HTTP) - VetAgent",
    "Check a crypto token for honeypots, taxes, thin liquidity and impersonation before an AI "
    "agent buys it. Remote MCP server and HTTP API, free, no key. Request, response and fields.",
    _API_BODY, _API_JSONLD)


# ------------------------------------------------------------------ /unknown

_UNKNOWN_BODY = """
<h1>What <code>unknown</code> means, and what your agent should do with it</h1>
<p class="lede"><code>unknown</code> means a check the verdict depends on could not be completed.
It is not a low-risk result, and an agent must never trade on it. It is also not an error: it is
the product refusing to guess.</p>

<h2>Why a risk check says "I don't know"</h2>
<p>Two checks are critical: whether the token has a market you can exit into (liquidity), and
whether it can be sold (sellability). If either could not be read, the answer is
<code>unknown</code> &mdash; never <code>low</code> or <code>medium</code>, however clean the rest
looks. A safety check that answers optimistically when it is broken is worse than no check.</p>

<h2>Retry or abstain: read <code>unknown_kind</code></h2>
<table>
<tr><th><code>unknown_kind</code></th><th>What happened</th><th><code>next_action</code></th></tr>
<tr><td><code>infrastructure</code></td><td>Our upstream data sources did not answer &mdash; usually
rate limits. The token may be fine.</td><td><code>retry</code>, once, after
<code>retry_after_seconds</code></td></tr>
<tr><td><code>coverage</code></td><td>The check could not be run for this token, and a retry
will not change that. Either the token cannot be checked &mdash; no trading pair, no simulator
record, a sell simulation that reverted, no pool priced in an asset whose value can be verified
&mdash; or this tool does not cover the chain, which is our gap and says nothing about the
token: no sell simulator covers Solana. The recommendation names which.</td><td><code>abstain</code> &mdash; retrying will not change it</td></tr>
<tr><td><code>mixed</code></td><td>Some of each. When one half is an upstream of ours that failed, <code>retry_after_seconds</code> is set and the retry is worth making for what it brings back &mdash; but if the other half is a chain we do not cover, or a fact about the token, the rating stays <code>unknown</code> however the retry goes. The recommendation says which halves are in play.</td><td><code>retry</code> when an upstream of ours failed, otherwise <code>abstain</code></td></tr>
</table>
<p>Retry at most once. An agent that retries every <code>unknown</code> until it gets an answer
has turned "we could not check" into "we checked", which is exactly the mistake the verdict exists
to prevent.</p>

<h2>Reading the reason</h2>
<p><code>evidence.data_gaps</code> says which check was missing and why, in the upstreams' own
terms:</p>
<pre><code>"data_gaps": [
  {"dimension": "liquidity", "source": "dexscreener+geckoterminal",
   "reason": "upstream request failed (dexscreener 429, coingecko 400, geckoterminal 429)"},
  {"dimension": "sellability", "source": "rugcheck",
   "reason": "our coverage gap: the sell simulator does not cover solana"}
]</code></pre>
<p>Every reason opens with one of exactly three phrases, and that phrase is the whole of what
your agent needs to decide what to do next. The detail after it is for a human reading the log.</p>
<table>
<tr><th>Reason begins with</th><th>Means</th><th>Worth retrying?</th></tr>
<tr><td><code>upstream request failed</code></td><td>Ours, and temporary: a source did not answer.
The parentheses say what each one returned.</td><td>Yes, once</td></tr>
<tr><td><code>our coverage gap</code></td><td>Ours, not the token's, and it takes three shapes: we
do not run this check here, or the one source that carries it has nothing for this mint, or what it
sent is not yet usable. No sell simulator covers Solana, and honeypot.is covers only Ethereum, BSC
and Base &mdash; on any other chain the sell test is a gap of ours and says nothing about the token.
The detail after the prefix says which shape, and names an expiry when there is one.</td><td>No &mdash;
not on any retry you would make</td></tr>
<tr><td><code>about the token</code></td><td>What came back does not contain it. A finding, or the
absence of one.</td><td>No</td></tr>
</table>
<p>Some details you will see after those prefixes:</p>
<table>
<tr><th>Reason</th><th>Means</th></tr>
<tr><td><code>about the token: the sell simulator has no record of this token</code></td><td>The
simulator has never seen it.</td></tr>
<tr><td><code>about the token: simulation failed: &hellip;</code></td><td>The simulator ran and the
trade reverted, often on a router it cannot drive. Unverified, not dangerous.</td></tr>
<tr><td><code>about the token: no pool's depth is priced in an asset we can verify</code></td><td>Pools
exist, but every one is priced in a token whose value no independent market sets &mdash; so the depth
it claims cannot be checked.</td></tr>
<tr><td><code>upstream request failed: no distinct-seller count</code></td><td>The simulator calls
it a honeypot while sells are completing, and the number of distinct sellers &mdash; which tells
real exits from one wallet trading with itself &mdash; could not be read.</td></tr>
</table>
<p>Before 2026-09-20 only the first two prefixes existed and everything else was bare, which meant
"a fact about the token" was whatever was left over. A gap that forgot its prefix changed meaning
silently: a transfer fee we could not read was published as an upstream outage, and a real outage on
Solana was published as a permanent coverage gap telling callers not to retry. The third prefix
exists so that no reason can mean something by default.</p>

<h2>When the absence is the answer</h2>
<p>If no market data source can price a token and no simulator can trade it, on a chain we know we
searched, the answer is not <code>unknown</code> but <code>high</code>, with the signal
"Nothing about this token can be verified". Every legitimate token clears at least one of those.
The rule applies only when the gaps are about the token, never when they are our own outage.</p>

<h2>How often</h2>
<p>The benchmark's rate is on <a href="/method">the method page</a>. Production refuses more often
than the benchmark, because the benchmark replays cached data and cannot see live rate limits; a
daily reading of the live rate is in
<a href="https://github.com/jakegu1/vetagent/blob/master/docs/SCORECARD.md">the scorecard</a>.</p>
"""

_UNKNOWN_JSONLD = """{"@context":"https://schema.org","@type":"FAQPage","url":"https://vetagent.dev/unknown",
"mainEntity":[
{"@type":"Question","name":"What does a risk_level of unknown mean in VetAgent?","acceptedAnswer":{"@type":"Answer","text":"A critical check - liquidity or sellability - could not be completed. It is not a low-risk result and must never be used to justify a trade."}},
{"@type":"Question","name":"Should an AI agent retry an unknown answer?","acceptedAnswer":{"@type":"Answer","text":"Only when unknown_kind is infrastructure and next_action is retry, and only once, after retry_after_seconds. A coverage unknown will not change on retry: abstain. A mixed unknown sets retry_after_seconds when part of it was an upstream failure - that retry brings back what the outage hid, but the rating stays unknown."}},
{"@type":"Question","name":"Where does VetAgent say why an answer is unknown?","acceptedAnswer":{"@type":"Answer","text":"evidence.data_gaps lists each missing check with its reason. Every reason begins with one of three phrases: 'upstream request failed' (ours and temporary - retry once), 'our coverage gap' (ours not the token's - no retry you would make closes it, and the detail names an expiry when there is one) or 'about the token' (what came back does not contain it - do not retry)."}}]}"""

UNKNOWN_HTML = _page(
    "/unknown", "What 'unknown' means in a token risk check, and what an AI agent should do - VetAgent",
    "unknown means a critical check could not run. It is never a green light. How to tell a retry "
    "from an abstain with unknown_kind and next_action, and how to read data_gaps.",
    _UNKNOWN_BODY, _UNKNOWN_JSONLD)


# ------------------------------------------------------------------ /method

_METHOD_BODY = """
<h1>How VetAgent measures its own accuracy</h1>
<p class="lede">The numbers that make it look good and the ones that make it look bad, the dataset
behind both, and the harness that reproduces them. Measured on 576 tokens across Ethereum, BSC and
Base.</p>

<h2>The numbers</h2>
<table>
<tr><th>Measure</th><th>Result</th></tr>
<tr><td>Healthy tokens rated high (false positives)</td><td class="num">3.1% (5 of 162)</td></tr>
<tr><td>Liquid healthy tokens rated medium or high (false blocks)</td><td class="num">13.0% (20 of 154)</td></tr>
<tr><td>Answers returned as unknown</td><td class="num">21.2% (122 of 576)</td></tr>
<tr><td>Confirmed-dead tokens not rated low</td><td class="num">86.7% (26 of 30)</td></tr>
<tr><td>Confirmed-dead tokens rated high</td><td class="num">10.0% (3 of 30)</td></tr>
<tr><td>Adversarial contracts rated high</td><td class="num">58.8% (10 of 17)</td></tr>
<tr><td>Oracle-tagged centralised tokens rated high</td><td class="num">22.3% (40 of 179)</td></tr>
</table>

<h2>Read the unflattering rows first</h2>
<p><strong>20 of 154 liquid, healthy tokens are refused.</strong> The false-positive row counts
only <code>high</code>, but an agent treats <code>medium</code> as do-not-trade too; the false-block
row counts it that way, on tokens that are alive or merely centralised and hold $100,000 or more.</p>
<p><strong>Much of the dead-token recall is detecting an empty pool.</strong> Keep only the contract
signals and dead tokens not rated low falls to 20.0%; adversarial contracts rated high falls to
17.6%. The adversarial cohort is 17 tokens and 15 of them hold under a dollar, so it is too small
and too drained to support a discrimination claim yet.</p>
<p><strong>The benchmark replays cached market data.</strong> It measures the engine under ideal
upstreams. Live answers are <code>unknown</code> more often, because free data sources rate-limit
the shared network the service runs on; the live figure is read daily into
<a href="https://github.com/jakegu1/vetagent/blob/master/docs/SCORECARD.md">the scorecard</a>.</p>
<p><strong>The owner-power scan is incomplete.</strong> On contracts its selector list has never
seen it finds 50.0% of the owner powers an independent oracle asserts, which is why those powers
are disclosed and never scored.</p>

<h2>By the depth of the pool</h2>
<p>Every row above mixes deep markets with pools holding cents. Split by the depth of the pool
the engine judged -- its own pick, so a token whose real market it missed lands in a shallower
row than it should. <em>High on contract signals only</em> is the verdict with the liquidity, pool
age, lifecycle and impersonation signals removed, beside each count so the depth checks cannot
flatter a row.</p>
<table>
<tr><th>Oracle-tagged centralised tokens, pool depth</th><th>Tokens</th><th>High</th><th>Medium</th><th>Unknown</th><th>High on contract signals only</th></tr>
<tr><td>No depth figure</td><td class="num">6</td><td class="num">4</td><td class="num">0</td><td class="num">2</td><td class="num">2</td></tr>
<tr><td>Every pool reports $0</td><td class="num">15</td><td class="num">15</td><td class="num">0</td><td class="num">0</td><td class="num">0</td></tr>
<tr><td>Under $1</td><td class="num">40</td><td class="num">16</td><td class="num">23</td><td class="num">1</td><td class="num">1</td></tr>
<tr><td>$1 to $1,000</td><td class="num">15</td><td class="num">1</td><td class="num">10</td><td class="num">4</td><td class="num">1</td></tr>
<tr><td>$1,000 to $100,000</td><td class="num">37</td><td class="num">3</td><td class="num">25</td><td class="num">5</td><td class="num">2</td></tr>
<tr><td>$100,000 or more</td><td class="num">66</td><td class="num">1</td><td class="num">13</td><td class="num">8</td><td class="num">1</td></tr>
</table>
<p>So most of the 22.3% centralised row is empty pools: 31 of its 40 highs are on pools reporting
$0 or under a dollar, and 30 of those 31 are not high on contract signals only; 4 more have no depth
figure at all. USDT and WBTC themselves are rated low (4 of 4 benchmark rows).</p>
<p>Across the 246 benchmark tokens holding $100,000 or more -- the 154 in the false-block row plus 92
others -- 156 are low, 53 unknown and 37 medium or high. On contract signals only it is 176 low, 53 unknown
and 17 medium or high: the 20 that move to low all have a pool-age or lifecycle flag as their driver
(20 of 20), and 13 of the 37 medium-or-high answers are honeypot verdicts, which contract signals keep.
These are the benchmark's tokens, not the tokens callers ask about, and live answers are
<code>unknown</code> more often; the live rate is read daily into
<a href="https://github.com/jakegu1/vetagent/blob/master/docs/SCORECARD.md">the scorecard</a>.</p>

<h2>Where the labels come from</h2>
<p>Two label families, from sources the engine never reads: an outcome label (a token is
<em>dead</em> or <em>alive</em>) from daily price and volume history, and a contract-security label
(<em>unsafe</em>, <em>safe</em>, <em>centralised</em>) from an independent oracle held out of the
product entirely. The benchmark asserts at runtime that the endpoints the engine calls and the
endpoints the labeller calls do not intersect, and exits non-zero if they do.</p>

<h2>What was attacked, and fixed</h2>
<p>On 2026-09-13 an adversarial audit tried to make the engine answer <code>low</code> for tokens it
should not. A pool priced in its creator's own token could claim any depth; a two-dollar pool made a
real token read as an impostor; and a check meant to stop wash-traded sells from overruling a
honeypot verdict never ran on the data source most tokens use. All three were fixed with tests that
failed first, and the table above is measured after the fixes.</p>

<h2>Reproduce it</h2>
<pre><code>git clone https://github.com/jakegu1/vetagent
cd vetagent
python bench/run_benchmark.py        # re-measures against live upstreams
python bench/publish_numbers.py      # fails if a published figure no longer matches</code></pre>
<p>Every figure on this page, the landing page and the README is generated from the benchmark
result and checked by the build. The full report, per token, is
<a href="https://github.com/jakegu1/vetagent/blob/master/bench/results.md">bench/results.md</a>.</p>
"""

_METHOD_JSONLD = """{"@context":"https://schema.org","@type":"TechArticle",
"headline":"How VetAgent measures its own accuracy",
"description":"False positives, false blocks, unknown rate and recall for a crypto token risk check, measured on 576 labelled tokens with a reproducible harness.",
"url":"https://vetagent.dev/method","image":"https://vetagent.dev/og.png",
"author":{"@type":"Organization","name":"VetAgent","url":"https://vetagent.dev/"},
"isBasedOn":"https://github.com/jakegu1/vetagent/blob/master/bench/results.md"}"""

METHOD_HTML = _page(
    "/method", "How VetAgent measures its accuracy: false positives, false blocks, recall - VetAgent",
    "A token risk check that publishes its own error rates, including the unflattering ones: "
    "measured on 576 tokens with independent labels and a harness anyone can re-run.",
    _METHOD_BODY, _METHOD_JSONLD)


PAGES = {"/api": API_HTML, "/unknown": UNKNOWN_HTML, "/method": METHOD_HTML}
