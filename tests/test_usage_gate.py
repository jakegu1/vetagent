"""test_usage_gate.py — the gate's counting rule has to be the one that runs.

Two failures produced this file, and the second one is mine.

FIRST: the gate answered YES on crawlers. Over 14 days the endpoint took 3,314 requests
from 64 clients, and the rule at the time -- "a distinct client name that is not ours,
from a country that is not the owner's" -- reported 47 external callers and printed
"keep following the roadmap". But 3,193 of those 3,314 requests (96.3%) carry no tool
name at all: they are `initialize` and `tools/list` handshakes. Only 118 requests called
a tool. And twenty of the forty-seven "callers" have prober, scan, audit, watch, witness,
observatory, index, archive, registry, census or stats in their own names. Registering in
the official MCP registry buys an audience of directory crawlers, and they arrive first.

SECOND: the tightening I wrote for that -- `qualifying_callers`, "at least three calls on
at least two days" -- was defined and never called. `main()` still ran the old rule. I
committed it under a message saying "the gate and its instrument agree", in a round whose
entire subject was guards that do not guard. It would not have helped anyway:
sentineloracle made 1,259 requests. Volume is the one thing a crawler has in abundance.

So this file pins two things: that the rule which decides the gate is actually invoked,
and that it counts tool use rather than connections.

Run:  python tests/test_usage_gate.py
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "bench"))

import usage  # noqa: E402

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def test_the_deciding_rule_is_actually_called():
    """A counting rule that main() never invokes decides nothing.

    `qualifying_callers` was defined, committed, described in a commit message as the
    gate's instrument, and never called. Nothing caught it because nothing tested this
    file at all.
    """
    print("\n[gate] the rule that prints the verdict is the rule that ran")
    src = open(os.path.join(ROOT, "bench", "usage.py"), encoding="utf-8").read()
    body = src.split("def main(")[-1]
    defined = set(re.findall(r"^def ([a-z_]+_callers)\(", src, re.M))
    check("the file defines at least one counting rule", bool(defined), str(defined))
    dead = [fn for fn in defined if fn + "(" not in body]
    check("no counting rule is dead code", not dead,
          "%s defined but never called from main()" % ", ".join(sorted(dead)))


def test_connecting_is_not_using():
    """The rule must count tool calls, not handshakes."""
    print("\n[gate] a handshake is not a caller")

    # Shaped like the real Analytics Engine rows.
    rows = [
        # A crawler: many requests, never a tool. This is 96% of real traffic.
        {"client": "sentineloracle", "tool": "", "n": 1259, "days": 14},
        {"client": "mcpbeat", "tool": "", "n": 813, "days": 14},
        {"client": "rootz-mcp-registry-prober", "tool": "", "n": 6, "days": 3},
        # An auth probe is not tool use either.
        {"client": "io.verifymcp", "tool": "__verifymcp_auth_probe_367ac",
         "n": 1, "days": 1},
        # Our own tooling, which must never count however it behaves.
        {"client": "vetagent-bench", "tool": "assess_token_risk", "n": 576, "days": 2},
        {"client": "claude-code", "tool": "assess_token_risk", "n": 40, "days": 5},
        # The thing the gate exists to detect.
        {"client": "somebodys-trading-bot", "tool": "assess_token_risk",
         "n": 7, "days": 3},
    ]

    real = {}
    original = usage.query, usage.rows_of
    usage.query = lambda *a, **k: {"data": rows}
    usage.rows_of = lambda resp: (resp or {}).get("data")
    try:
        got = usage.tool_callers("acct", "tok", "INTERVAL '14' DAY")
        real = dict(got or [])
    finally:
        usage.query, usage.rows_of = original

    names = set(real)
    check("a crawler that only connects does not count",
          "sentineloracle" not in names and "mcpbeat" not in names, str(names))
    check("a registry prober does not count",
          "rootz-mcp-registry-prober" not in names, str(names))
    check("an auth probe is not tool use", "io.verifymcp" not in names, str(names))
    check("our own benchmark never counts", "vetagent-bench" not in names, str(names))
    # claude-code is NOT dropped. `_client_name` reads the User-Agent, so it is any
    # Claude Code instance -- the owner's editor and a stranger's, indistinguishable.
    # Excluding it by name meant the gate excluded the single most likely client for a
    # real user of an MCP server: a false negative exactly mirroring the crawler false
    # positive. It is surfaced and marked ambiguous so a human resolves it, rather than
    # silently deciding it either way.
    check("an ambiguous client is surfaced, not dropped",
          "claude-code" in names, str(names))
    check("and it is marked ambiguous",
          real.get("claude-code", {}).get("ambiguous") is True,
          str(real.get("claude-code")))
    check("a genuinely external caller is not marked ambiguous",
          real.get("somebodys-trading-bot", {}).get("ambiguous") is False,
          str(real.get("somebodys-trading-bot")))
    check("a real caller that used a tool does count",
          "somebodys-trading-bot" in names, str(names))
    if "somebodys-trading-bot" in real:
        rec = real["somebodys-trading-bot"]
        check("and its tool use is reported",
              rec["n"] == 7 and "assess_token_risk" in rec["tools"], str(rec))


def test_a_failed_query_is_not_an_answer():
    """"The query failed" and "nobody called" must not look alike.

    They are opposite facts and both arrive as an empty result. Confusing them makes the
    gate answer a question nobody asked -- the same distinction the whole engine is built
    around, applied to our own telemetry.
    """
    print("\n[gate] a failed query is not a finding")
    original = usage.query, usage.rows_of
    usage.query = lambda *a, **k: {"errors": ["nope"]}
    usage.rows_of = lambda resp: None
    try:
        got = usage.tool_callers("acct", "tok", "INTERVAL '14' DAY")
    finally:
        usage.query, usage.rows_of = original
    check("a failed query returns None, not an empty list", got is None, repr(got))


def main():
    print("=" * 68)
    print("Usage gate: does the counting rule count the right thing?")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
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
