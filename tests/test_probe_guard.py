"""The public probe guard rejects untagged internal traffic.

Both denied requests and allowed non-request commands are tested. Local
editor hook configuration is private; the distributable guard is tested here.
Run: python tests/test_probe_guard.py
"""

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "tools", "no_untagged_probe.py")

_PASSED = 0
_FAILURES = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def decision(command):
    """Run the hook exactly as Claude Code runs it: JSON on stdin, JSON or nothing out."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    out = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                         encoding="utf-8", errors="replace",
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if out.returncode != 0:
        return "ERROR:%s" % (out.stderr or "")[:120]
    body = (out.stdout or "").strip()
    if not body:
        return "allow"
    try:
        d = json.loads(body)
    except ValueError:
        return "UNPARSEABLE:%s" % body[:120]
    return (d.get("hookSpecificOutput") or {}).get("permissionDecision") or "allow"


MUST_DENY = [
    ("curl -s https://vetagent.dev/mcp -d '{}'", "a bare curl at the MCP endpoint"),
    ("curl -s https://vetagent.dev/health", "a bare curl at any route"),
    ("curl -s https://vetagent.dev/cdn-cgi/trace", "even the Cloudflare trace endpoint"),
    ("wget -qO- https://vetagent.dev/llms.txt", "wget"),
    ("Invoke-RestMethod -Uri https://vetagent.dev/mcp -Method POST", "PowerShell"),
    ("python -c \"import urllib.request as u; u.urlopen('https://vetagent.dev/health')\"",
     "python urlopen, which is how the bench probes"),
    ("curl -H 'accept: application/json' -X POST https://VETAGENT.DEV/mcp",
     "an uppercase host"),
    ("true && curl -s https://vetagent.dev/mcp", "a curl chained behind something else"),
]

MUST_ALLOW = [
    ("curl -sS -H 'x-mcp-client: vetagent-manual-probe' https://vetagent.dev/mcp -d '{}'",
     "the tagged form the note prescribes"),
    ("curl -H 'X-MCP-Client: vetagent-manual-probe' https://vetagent.dev/health",
     "the same header in different casing"),
    ("grep 'curl https://vetagent.dev' CLAUDE.md",
     "searching the documentation for its own example"),
    ("rg -n 'https://vetagent.dev' docs/", "ripgrep over the docs"),
    ("cat docs/EXPERIMENT_C.md", "reading a file"),
    ("git push origin master", "git, which never names the domain"),
    ("curl -s https://api.openchain.xyz/signature-database/v1/lookup?function=0xa9059cbb",
     "a curl at a different host entirely"),
    ("gh run list --limit 5", "an unrelated command"),
    ("python bench/selector_mine.py --resolve",
     "a bench script that talks to a third party"),
]


def test_the_public_guard_is_available():
    check("the public guard script exists", os.path.isfile(HOOK), HOOK)


def test_an_untagged_request_to_production_is_refused():
    """The shapes that must never reach production unnamed."""
    print("\n[probe] an untagged request to vetagent.dev is denied")
    for command, why in MUST_DENY:
        d = decision(command)
        check("denied: %s" % why, d == "deny", "got %r for %r" % (d, command[:60]))


def test_everything_else_is_left_alone():
    """The half that keeps the guard usable.

    A hook that blocks reading its own documentation, or any curl to any host, gets turned
    off within a day -- and a guard that has been switched off is indistinguishable from one
    that was never written. The false-positive cases are therefore pinned as tightly as the
    true ones.
    """
    print("\n[probe] nothing else is touched")
    for command, why in MUST_ALLOW:
        d = decision(command)
        check("allowed: %s" % why, d == "allow", "got %r for %r" % (d, command[:60]))


def test_the_hook_never_blocks_on_bad_input():
    """Unreadable input is not grounds to block. This hook sees every Bash command.

    Fail-open is the right direction HERE and nowhere else in this project: the hook runs on
    every shell command in the session, so a parse error that denied would stop all work
    rather than one probe. The guard against that fail-open is this test file, not a
    fallback -- a broken hook turns CI red instead of going quiet.
    """
    print("\n[probe] malformed input is not a reason to block a command")
    for payload, why in ((b"", "empty stdin"), (b"not json", "non-JSON stdin"),
                         (b'{"tool_input":{}}', "no command field"),
                         (b'{"tool_input":{"command":null}}', "a null command")):
        out = subprocess.run([sys.executable, HOOK], input=payload.decode("utf-8"),
                             capture_output=True, encoding="utf-8", errors="replace",
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        check("%s does not deny" % why,
              out.returncode == 0 and not (out.stdout or "").strip(),
              "rc=%s out=%r" % (out.returncode, (out.stdout or "")[:80]))


def test_the_deny_message_says_how_to_proceed():
    """A refusal that does not say what to do instead gets worked around, not obeyed."""
    print("\n[probe] the refusal is actionable")
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "curl https://vetagent.dev/mcp"}})
    out = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                         encoding="utf-8", errors="replace",
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    reason = ((json.loads(out.stdout).get("hookSpecificOutput") or {})
              .get("permissionDecisionReason") or "")
    check("it names the header to add", "x-mcp-client" in reason.lower(), reason[:80])
    check("it gives the literal flag", "-H 'x-mcp-client:" in reason, reason[:200])
    check("it says why, not just no", "gate" in reason.lower(), reason[:200])
    check("and it refuses the obvious workaround",
          "do not work around" in reason.lower(), reason[-200:])


def main():
    print("=" * 70)
    print("The probe guard: an untagged request cannot reach production")
    print("=" * 70)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 70)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
