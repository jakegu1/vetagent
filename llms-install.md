# Installing VetAgent (for AI agents doing the installing)

There is nothing to install. VetAgent is a **remote** MCP server: no npm package, no
Python package, no container, no API key, no signup. You add one URL.

```
https://vetagent.dev/mcp
```

Transport: **streamable HTTP** (MCP protocol `2025-06-18`, also accepts `2025-03-26`
and `2024-11-05`).

## Add it to a client

### Claude Code

```bash
claude mcp add --transport http vetagent https://vetagent.dev/mcp
```

### Claude Desktop

Open **Customize → Connectors**, choose **Add custom connector**, and enter
`https://vetagent.dev/mcp`. Choose **No sign in** if asked, then enable the connector
in your conversation. An organization owner may need to add it first in a managed
workspace. See [Claude's remote connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

### Cursor

Add this to your project's `.cursor/mcp.json`, merging with existing servers:

```json
{
  "mcpServers": {
    "vetagent": {
      "url": "https://vetagent.dev/mcp"
    }
  }
}
```

### Plain HTTP

The same engine answers without an MCP client. Include the chain when you know it:

```bash
curl 'https://vetagent.dev/assess/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2?chain_hint=ethereum'
```

## Confirm it works

```bash
curl -s -X POST https://vetagent.dev/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

You should get three tools back: `assess_token_risk`, `get_token_liquidity`,
`find_new_hot_pools`. This response confirms endpoint access. In your chosen client,
check that these three tools appear before considering the connection ready.

## Identify yourself (optional, and it helps)

Send `X-MCP-Client: your-client-name` on requests, or the standard `clientInfo.name` on
`initialize`. Nothing breaks without it. It exists because this server deliberately
records no addresses, no identities and no token queries, which means it genuinely
cannot tell who its users are — a header is the only way an integrator can say "someone
is actually using this".

## The one thing worth knowing before you use the output

`assess_token_risk` returns four verdicts, not three: `low`, `medium`, `high` and
**`unknown`**.

`unknown` means a critical check could not run. **It is not a low-risk result and must
never be used to justify a trade.** The server is deliberately fail-closed: it refuses
rather than guessing, because an agent acting on a confident wrong answer is worse than
an agent that reads "I could not tell". Roughly one answer in seven is this refusal, and
that is the product working, not an error.

## No auth, no state

No API key. No account. No rate limit you need to negotiate. The server stores no
addresses, no identities and no token queries, so there is nothing to configure for
privacy and nothing to revoke.

Free, MIT, one maintainer, no SLA. Source and the benchmark that measures its error rate:
<https://github.com/jakegu1/vetagent>

If you are installing this for something real, <hello@vetagent.dev> reaches a person.
The server counts calls but records no identities, so it can see that someone is using it
and never who -- which makes a header or an email the only way an integration becomes
visible, and the only way you get told before something changes under you.
