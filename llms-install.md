# Installing VetAgent (for AI agents doing the installing)

There is nothing to install. VetAgent is a **remote** MCP server: no npm package, no
Python package, no container, no API key, no signup. You add one URL.

```
https://vetagent.dev/mcp
```

Transport: **streamable HTTP** (MCP protocol `2025-06-18`, also accepts `2025-03-26`
and `2024-11-05`).

## Add it to a client

Most clients take the same shape:

```json
{
  "mcpServers": {
    "vetagent": {
      "type": "http",
      "url": "https://vetagent.dev/mcp"
    }
  }
}
```

Claude Code, one line:

```bash
claude mcp add --transport http vetagent https://vetagent.dev/mcp
```

## Confirm it works

```bash
curl -s -X POST https://vetagent.dev/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

You should get three tools back: `assess_token_risk`, `get_token_liquidity`,
`find_new_hot_pools`. If you can read that response, installation is done.

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
