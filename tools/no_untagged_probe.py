"""Reject untagged manual requests to the production service.

Internal requests must identify themselves with an x-mcp-client vetagent-* name
so they cannot be mistaken for external usage. This reads a tool-hook JSON
message on stdin; it makes no HTTP requests and changes no local settings.
It leaves unrelated hosts and non-request commands alone.
"""

import json
import sys

DOMAIN = "vetagent.dev"
TAG = "x-mcp-client"

# Tokens that mean "this command speaks HTTP". Deliberately NOT bare "http", which appears
# in every URL and would make this check fire on `grep https://vetagent.dev docs/*.md`.
CLIENTS = (
    "curl", "wget", "httpie", "xh ",
    "invoke-webrequest", "invoke-restmethod", "iwr ",
    "urlopen", "requests.get", "requests.post", "requests.request", "http.client",
    "httpx.", "aiohttp", "fetch(",
)

# If the command STARTS with one of these it is reading text, not sending a request. The
# case this exists for is real: CLAUDE.md now documents the tagged curl, so searching that
# documentation would otherwise trip the guard on its own example.
TEXT_TOOLS = ("grep", "rg", "cat", "sed", "awk", "head", "tail", "less", "echo", "printf",
              "diff", "wc", "sort", "uniq", "git")

REASON = (
    "Blocked: an HTTP request to %s with no `%s` header.\n"
    "\n"
    "An untagged probe from this machine is recorded as client `curl` from country JP, and "
    "the usage gate counts that as an external caller -- it is what made the 2026-09-18 "
    "gate read YES on our own verification traffic on 2026-09-11.\n"
    "\n"
    "Add the header and run it again:\n"
    "  -H 'x-mcp-client: vetagent-manual-probe'\n"
    "\n"
    "Anything starting `vetagent-` is filtered out by `is_self()` in bench/usage.py, so a "
    "tagged probe cannot reach the gate's evidence. If you genuinely need an untagged "
    "request -- to reproduce what an outside caller sees -- say so and disable this hook "
    "deliberately; do not work around it by renaming the header."
) % (DOMAIN, TAG)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:                                        # noqa: BLE001
        return 0                     # unreadable input is not grounds to block a command
    cmd = ((payload.get("tool_input") or {}).get("command") or "")
    if not isinstance(cmd, str) or not cmd.strip():
        return 0
    low = cmd.lower()

    if DOMAIN not in low:
        return 0
    if TAG in low:
        return 0
    if low.lstrip().split(" ")[0].split("/")[-1] in TEXT_TOOLS:
        return 0
    if not any(tok in low for tok in CLIENTS):
        return 0

    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
