# VetAgent — Claude Code / Cowork plugin

This directory is the plugin. It is deliberately tiny: a manifest, one MCP server
definition, and one skill. It lives in a subdirectory rather than at the repository root
so that installing it does not pull down `bench/snapshots/`, the daily archive, which
grows every day and has nothing to do with using the tool.

```
plugin/
  .claude-plugin/plugin.json   name, version, author, license
  .mcp.json                    the remote server: https://vetagent.dev/mcp
  skills/vet-token/SKILL.md    when to call it, and how to read `unknown`
```

## Install

```bash
/plugin marketplace add anthropics/claude-plugins-community
/plugin install vetagent@claude-community
```

Or, without the plugin at all — it is a remote server, so one URL is the whole install:

```bash
claude mcp add --transport http vetagent https://vetagent.dev/mcp
```

## What it does

Pre-trade token safety: sell simulation, buy/sell tax, liquidity depth, pair age,
same-ticker impersonation, and owner powers read from contract bytecode — returned as one
`low` / `medium` / `high` / `unknown` verdict with the signals behind it.

The skill exists to carry one rule that an agent gets wrong otherwise: **`unknown` is not
`low`.** It means a critical check could not run, and it must never justify a trade.

Free, no signup, no API key, no tracking. Source, benchmark and measured error rates:
<https://github.com/jakegu1/vetagent>. Questions: <hello@vetagent.dev>.
