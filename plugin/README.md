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

**Not in a marketplace yet**, so there is no `/plugin install` line to give you: the
community directory needs an account the maintainer has not created. Until then, load it
from a clone:

```bash
claude --plugin-dir ./plugin
```

Or skip the plugin entirely — it is a remote server, so one URL is the whole install:

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
