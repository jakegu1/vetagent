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
    defined = set(re.findall(r"^def ([a-z_]+_callers)\(", src, re.M))
    check("the file defines at least one counting rule", bool(defined), str(defined))

    # REACHABLE from main(), not merely called by it. The first version searched only
    # main()'s own body, so a counting rule invoked one level down read as dead -- which it
    # is not. `unjudgeable_callers` is called by `blind_spot_lines`, which main() calls, and
    # the guard failed it on 2026-09-11. Renaming the function to dodge the pattern would
    # have been the dishonest fix available; this is the honest one, and it still catches
    # what the guard exists for, because a function nothing reaches is still unreachable.
    bodies = {}
    for m in re.finditer(r"^def ([a-z_0-9]+)\(", src, re.M):
        start = m.start()
        nxt = re.search(r"^def ", src[m.end():], re.M)
        bodies[m.group(1)] = src[start:m.end() + (nxt.start() if nxt else len(src))]
    reachable, frontier = set(), ["main"]
    while frontier:
        fn = frontier.pop()
        if fn in reachable or fn not in bodies:
            continue
        reachable.add(fn)
        for called in set(re.findall(r"\b([a-z_0-9]+)\(", bodies[fn])):
            if called in bodies and called not in reachable:
                frontier.append(called)
    dead = [fn for fn in defined if fn not in reachable]
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


def _caller(name, n=6, days=2, tools=("assess_token_risk",),
            verdicts=("high", "low"), countries=("US",)):
    """One caller, in the two shapes the two queries return it."""
    rec = {"n": n, "days": days, "tools": set(tools),
           "ambiguous": name in usage.AMBIGUOUS_CLIENTS}
    prof = {"verdicts": {v: 1 for v in verdicts if v}, "hours": {3, 4},
            "days": {"2026-09-0%d" % (i + 1) for i in range(days)},
            "countries": set(countries),
            "country_n": {c: 1 for c in countries}, "n": n}
    return (name, rec), prof


def _decide(*callers):
    tools = [c for c, _ in callers]
    prof = {name: p for (name, _), p in callers}
    return usage.gate_verdict(tools, prof)[0]


def test_the_frozen_rule_says_no_to_everything_seen_so_far():
    """Every bucket in fourteen days of real traffic, replayed through the rule.

    This is the test the previous three rules did not have. Each of them was written in
    prose, read by a human against a printout, and each said YES to something that was
    us or a robot. On 2026-09-07 the printed verdict was:

        YES: sasame-mcp-audit    13 calls, verdicts "(none) x13"
        YES: rokmcp-collector     3 calls, 1 per day, find_new_hot_pools only
        YES: vetagent-r16-verify  1 call
        -> STRATEGY: keep following the roadmap.

    An audit scanner that never got an answer, a once-a-day collector, and the developer's
    own verification call made eight minutes earlier -- and on the strength of those three
    lines the gate recommended another round of building.
    """
    print("\n[gate] the three lines that printed YES must now print NO")

    verify, vp = _caller("vetagent-r16-verify", n=1, days=1, verdicts=("high",))
    check("our own verification call is ours, by prefix not by list",
          _decide((verify, vp)) == "NO")

    demo, dp = _caller(usage.LANDING_DEMO, n=42, days=4,
                       verdicts=("high", "unknown"), countries=("CN",))
    check("a click on our own landing page is never adoption",
          _decide((demo, dp)) == "NO")

    # A thorough auditor calls every tool once and receives an error from each.
    sasame, sp = _caller("sasame-mcp-audit", n=13, days=2, verdicts=(),
                         tools=("assess_token_risk", "get_token_liquidity",
                                "find_new_hot_pools"))
    check("a scanner that never received a verdict is not a user",
          _decide((sasame, sp)) == "NO")

    # A collector on a timer: many days, one tool, the same answer every time.
    rok, rp = _caller("rokmcp-collector", n=3, days=3,
                      tools=("find_new_hot_pools",), verdicts=("ok",))
    check("one repeated verdict across many days is a monitor",
          _decide((rok, rp)) == "NEAR")

    # The browser bucket before the demo was tagged: real verdicts, but the name is
    # shared with every browser and every bot that spoofs one, and country was "??".
    moz, mp = _caller("mozilla", n=42, days=4, verdicts=("high", "unknown"),
                      countries=("??",))
    check("an unattributable name with no known country cannot pass",
          _decide((moz, mp)) == "NEAR")

    check("all of them together still say NO",
          _decide((verify, vp), (demo, dp), (sasame, sp), (rok, rp), (moz, mp))
          in ("NO", "NEAR"))


def test_the_frozen_rule_can_still_say_yes():
    """A gate that cannot pass is not a gate -- it is a decision already made.

    The rule has been tightened four times, always upward. This pins the other end: a
    caller with the properties the gate was written to detect must clear it, or the
    tightening has quietly turned into a refusal to look.
    """
    print("\n[gate] and it must still be passable by the thing it is looking for")

    real, rp = _caller("acme-trading-agent", n=9, days=3,
                       verdicts=("high", "low", "unknown"), countries=("US",))
    check("a named client, repeat days, varied verdicts, foreign country -> YES",
          _decide((real, rp)) == "YES")

    # `_country` was fixed on 2026-09-07, and this is what that fix buys: the one bucket
    # the gate could never resolve becomes resolvable without recording anything new.
    cc_home, hp = _caller("claude-code", n=9, days=3, countries=("CN",))
    cc_away, ap = _caller("claude-code", n=9, days=3, countries=("US",))
    check("claude-code from the owner's country is still ours", _decide((cc_home, hp)) == "NEAR")
    check("claude-code from anywhere else is external by construction",
          _decide((cc_away, ap)) == "YES")

    mixed, mxp = _caller("claude-code", n=9, days=3, countries=("CN", "SG"))
    check("one foreign row is enough -- the owner cannot be in two places",
          _decide((mixed, mxp)) == "YES")


def test_our_own_ci_names_itself():
    """CI curls production five times per deploy, from a US GitHub runner.

    Those calls carried no client name, so they arrived as `curl` from a foreign country
    and the 2026-09-07 run of this gate printed YES on them. It is the same defect as
    `vetagent-r16-verify` -- our own tooling that does not say it is ours -- and it is
    fixed the same way: by naming the tooling, not by changing what the gate counts.

    The distinction matters, because fixing attribution after a run looks exactly like
    moving the goalposts. The test is whether the fix would have been made had the gate
    said NO, and it would: our own deploy traffic in the gate's evidence is a defect
    whichever way the gate points.
    """
    print("\n[gate] our own smoke test is not an external caller")
    wf = open(os.path.join(ROOT, ".github", "workflows", "deploy.yml"),
              encoding="utf-8").read()
    smoke = wf.split("Smoke test production")[-1]
    calls = [ln for ln in smoke.splitlines()
             if "curl" in ln and "vetagent.dev" in ln]
    check("the smoke test still calls production", len(calls) >= 4, str(len(calls)))
    check("and every one of those calls names itself",
          all("$CI_TAG" in ln for ln in calls),
          str([ln.strip()[:60] for ln in calls if "$CI_TAG" not in ln]))
    check("under a name the gate counts as ours",
          usage.is_self("vetagent-ci-smoke"))


def test_a_yes_says_how_much_evidence_it_rests_on():
    """A YES on three rows out of forty-seven is still a YES. It must say "three".

    `_country` only started working on 2026-09-07, so every older row carries "??" and
    can support nothing. The rule is frozen and is not moved after a run -- but a reader
    deciding whether to spend another month on this is entitled to see the denominator.
    """
    print("\n[gate] the verdict line carries its own evidence density")
    caller, prof = _caller("acme-trading-agent", n=47, days=3,
                           verdicts=("high", "low"), countries=("US",))
    prof["country_n"] = {"US": 3, "??": 44}
    verdict, lines = usage.gate_verdict([caller], {"acme-trading-agent": prof})
    check("it still passes", verdict == "YES", verdict)
    check("and it shows 3 of 47", "on 3 of 47 rows" in " ".join(lines),
          " ".join(lines))


def test_the_rule_is_frozen_and_the_date_says_so():
    """The rule is dated in the file, and main() prints that date when it runs."""
    print("\n[gate] the rule is frozen, dated, and printed")
    src = open(os.path.join(ROOT, "bench", "usage.py"), encoding="utf-8").read()
    check("the freeze date is recorded next to the rule",
          usage.GATE_FROZEN == "2026-09-07", usage.GATE_FROZEN)
    check("main() prints the date, so a reader sees when it was fixed",
          "GATE_FROZEN" in src.split("def main(")[-1])
    check("main() decides with gate_verdict and not with an inline rule",
          "gate_verdict(tools, prof)" in src.split("def main(")[-1])
    check("no counting rule is dead code",
          all(("%s(" % fn) in src.split("def main(")[-1]
              for fn in ("gate_verdict", "tool_callers", "external_callers")))


def test_rows_older_than_the_attribution_fix_are_not_gate_evidence():
    """The gate reads only rows the fixed instrument wrote, and says how many it dropped.

    On 2026-09-08 the 14-day window returned YES on exactly two clients, `mozilla` and
    `curl`. Those are precisely the two buckets that a03f430 and b078d65 emptied the
    day before: before them our own CI smoke tests were recorded as `curl` and our own
    landing-page demo as `mozilla`. The run was not wrong that calls happened. It was
    unable to say who made them, and that is the only thing the gate asks.

    So gate evidence carries a floor. Note which way it cuts: the floor removes rows and
    makes YES harder, and it would have been added on a NO just as fast -- a pre-fix row
    can hide a real caller inside our own traffic exactly as easily as it can invent one.
    """
    print("\n[gate] pre-fix rows are a gap, not evidence")
    seen = []
    original = usage.query, usage.rows_of
    usage.query = lambda sql, *a, **k: (seen.append(sql), {"data": []})[1]
    usage.rows_of = lambda resp: (resp or {}).get("data")
    try:
        usage.tool_callers("acct", "tok", "INTERVAL '14' DAY")
        usage.caller_profile("acct", "tok", "INTERVAL '14' DAY",
                             [("somebodys-trading-bot", {"n": 7})])
        usage.unattributable_calls("acct", "tok", "INTERVAL '14' DAY")
    finally:
        usage.query, usage.rows_of = original

    check("the gate's evidence queries ran", len(seen) == 3, "%d queries" % len(seen))
    check("every gate query carries the attribution floor",
          all(usage.ATTRIBUTION_FIXED in sql for sql in seen[:2]),
          "; ".join(s[:70] for s in seen[:2] if usage.ATTRIBUTION_FIXED not in s))
    check("the floor is the day the two attribution commits deployed",
          usage.ATTRIBUTION_FIXED.startswith("2026-09-07"), usage.ATTRIBUTION_FIXED)
    check("the set-aside count asks for the complement, not the same rows again",
          "timestamp < toDateTime" in seen[2], seen[2][:120])

    src = open(os.path.join(ROOT, "bench", "usage.py"), encoding="utf-8").read()
    body = src.split("def main(")[-1]
    check("main() reports what it set aside rather than dropping it silently",
          "evidence_base_lines(" in body)
    check("the reconciliation counts over the same window the gate reads",
          "gate_window(since)" in body,
          "reconciliation still spans the raw window")


def test_only_one_document_states_the_bar():
    """Three documents restated the gate's rule from memory and all three were weaker.

    - docs/STRATEGY.md's table row said "at least one external client that called a
      tool", dropping "came back on a second day" and "asked about more than one thing".
    - docs/BACKLOG.md W11 said "at least one external caller" -- the FIRST of the four
      rules, superseded on 2026-09-07 and still sitting there.
    - .github/workflows/usage.yml's job summary described the SECOND.

    On 2026-09-18 the owner reads one of those. Each said the gate passes on evidence
    `gate_verdict()` refuses, and every one of them drifted in the same direction: easier.
    A rule restated in four places is a rule with three chances to be quietly loosened.

    `RULE_TEXT` in bench/usage.py is the only statement now. Anything else points at it.
    """
    print("\n[gate] the bar is stated once, in the file that decides it")

    check("the canonical text exists and is not empty", bool(usage.RULE_TEXT.strip()))
    for clause in ("second day", "more than one thing", "real verdict", "not ours"):
        check("it carries '%s'" % clause, clause in usage.RULE_TEXT, usage.RULE_TEXT)

    src = open(os.path.join(ROOT, "bench", "usage.py"), encoding="utf-8").read()
    check("main() prints it rather than retyping it", "RULE_TEXT" in src.split("def main(")[-1])

    # The superseded wording must not survive anywhere except the historical record in
    # STRATEGY section 8, which exists precisely to show how the rule was tightened.
    dead = "≥1 external caller"
    for rel in ("docs/BACKLOG.md", "docs/OWNER.md", "README.md",
                ".github/workflows/usage.yml"):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        check("%s does not restate the superseded bar" % rel,
              dead not in text or "superseded" in text,
              "carries the first of four counting rules as if it were current")


def test_the_evidence_base_is_never_silent():
    """Three states, three outputs. The first version had three states and one silence.

    `unattributable_calls()` returned None both when the floor query failed and when it
    answered zero, because `rows_of` gives `[]` for empty and `None` for failure and
    `if not rows` swallowed the difference. `main()` then guarded the notice with
    `if set_aside:`, which also swallowed a legitimate 0. So on 2026-09-18 the owner could
    read a verdict with no mention that the evidence was floored at all -- and would
    reasonably assume the full fourteen days -- either because nothing was dropped or
    because the run could not find out. That is E11, in the block whose own comment reads
    "say what was dropped".

    Caught by an adversarial review, not by the test above it, which grepped main()'s
    source for two substrings and never executed anything. `set_aside = None` with those
    substrings in a trailing comment would have kept it green.
    """
    print("\n[gate] the evidence base speaks in all three states")

    original = usage.query, usage.rows_of
    try:
        # A failed query is not zero.
        usage.query = lambda *a, **k: {"_raw": "<html>gateway timeout</html>"}
        usage.rows_of = original[1]
        got = usage.unattributable_calls("acct", "tok", "INTERVAL '14' DAY")
        check("a failed floor query returns None, not 0", got is None, repr(got))

        # An answer of "nothing" is a measurement.
        usage.query = lambda *a, **k: {"data": []}
        got = usage.unattributable_calls("acct", "tok", "INTERVAL '14' DAY")
        check("an empty answer returns 0, not None", got == 0, repr(got))

        usage.query = lambda *a, **k: {"data": [{"n": 260}]}
        got = usage.unattributable_calls("acct", "tok", "INTERVAL '14' DAY")
        check("a real count comes back as itself", got == 260, repr(got))
    finally:
        usage.query, usage.rows_of = original

    unknown = "\n".join(usage.evidence_base_lines(None))
    none_set = "\n".join(usage.evidence_base_lines(0))
    some = "\n".join(usage.evidence_base_lines(260))

    check("all three say something", all(s.strip() for s in (unknown, none_set, some)))
    check("and all three say something different",
          len({unknown, none_set, some}) == 3)
    check("'could not determine' is unmistakable in the failure case",
          "COULD NOT DETERMINE" in unknown, unknown)
    check("zero is stated as a measurement, not as silence",
          "Nothing was set aside" in none_set, none_set)
    check("a real count names the number and the cutoff",
          "260" in some and usage.ATTRIBUTION_FIXED in some, some)


def test_the_blind_spot_report_never_moves_the_verdict():
    """The gate may print what it cannot see. It may not decide differently because of it.

    On 2026-09-11 the gate read YES on `curl` -- untagged probes from the owner's own
    machine, which egresses through Tokyo, so `OWNER_COUNTRIES = {"CN"}` did not catch them.
    Looking into that turned up a second thing: `find_new_hot_pools` returns `count` and
    `scanned` and no verdict field, so `_record_call` writes "" for it, and a caller whose
    use of this product is pool discovery can never satisfy "received a real verdict".
    The two clients in the data that named themselves something unmistakably not ours were
    both filed under `no:` for that reason.

    Both of the edits that would make the gate read differently -- widening
    `OWNER_COUNTRIES`, or counting a verdictless tool -- happen to favour YES. That is the
    pressure a frozen rule exists to resist, so neither was made. The blind spot is
    REPORTED instead, and this test is what keeps that honest: the same inputs must produce
    the same verdict whether or not anything is reported beside it.
    """
    print(chr(10) + "[gate] reporting the blind spot changes no verdict")

    tools = [("sasame-mcp-audit", {"n": 15, "days": 3, "tools": {"find_new_hot_pools"}}),
             ("curl", {"n": 14, "days": 4, "tools": {"assess_token_risk"}})]
    prof = {"sasame-mcp-audit": {"verdicts": {"(none)": 15}, "days": {"a", "b", "c"}},
            "curl": {"verdicts": {"low": 12, "unknown": 2}, "days": set("abcd"),
                     "countries": {"JP"}, "country_n": {"JP": 14}}}

    before, _ = usage.gate_verdict(tools, prof)
    lines = usage.blind_spot_lines(tools, prof)
    after, _ = usage.gate_verdict(tools, prof)
    check("the verdict is identical before and after reporting", before == after,
          "%s then %s" % (before, after))
    check("the unjudgeable caller is named", any("sasame-mcp-audit" in l for l in lines),
          str(lines[:2]))
    check("the caller that DID get a verdict is not named here",
          not any(l.strip().startswith("curl") for l in lines), str(lines[:3]))
    check("the report says it changes nothing",
          any("changes nothing" in l for l in lines), str(lines[-3:]))

    # A caller that is ours must never appear in the report, however unjudgeable.
    ours = [("vetagent-ci-smoke", {"n": 9, "days": 5, "tools": {"find_new_hot_pools"}})]
    ours_prof = {"vetagent-ci-smoke": {"verdicts": {"(none)": 9}, "days": {"a", "b"}}}
    check("our own tooling is not reported as unjudgeable",
          not usage.unjudgeable_callers(ours, ours_prof),
          str(usage.unjudgeable_callers(ours, ours_prof)))

    # And a caller failing on some OTHER ground belongs in gate_verdict's output, not here.
    oneday = [("someone", {"n": 4, "days": 1, "tools": {"find_new_hot_pools"}})]
    oneday_prof = {"someone": {"verdicts": {"(none)": 4}, "days": {"a"}}}
    check("a one-day caller is left to the rule to report",
          not usage.unjudgeable_callers(oneday, oneday_prof),
          str(usage.unjudgeable_callers(oneday, oneday_prof)))


def test_reporting_the_transport_never_moves_the_verdict():
    """`GET /assess/<address>` is a documented API, so the engine has no method guard.

    The cost lands in the gate: `_record_http` files a browser GET with
    `tool=assess_token_risk` and a real verdict, and `tool_callers()` groups on client and
    tool alone, so a pasted URL is the same row as an MCP `tools/call`. The 2026-09-11
    artifact's second passing client is `mozilla`.

    Reported rather than counted, for the third time in this file and for the same reason:
    the rule is frozen, and every edit available here would move the answer.
    """
    print(chr(10) + "[gate] transport is reported, never counted")
    tools = [("mozilla", {"n": 6, "days": 3, "tools": {"assess_token_risk"}})]
    prof = {"mozilla": {"verdicts": {"low": 3, "unknown": 2}, "days": {"a", "b", "c"},
                        "countries": {"US"}, "country_n": {"US": 6},
                        "methods": {"http": 6}}}
    before, lines = usage.gate_verdict(tools, prof)
    passing = [ln.split()[1] for ln in lines if ln.strip().startswith("YES:")]
    out = usage.transport_lines(tools, prof, passing)
    after, _ = usage.gate_verdict(tools, prof)
    check("the verdict is identical before and after", before == after,
          "%s then %s" % (before, after))
    check("an all-REST caller is named as one",
          any("not an MCP client" in l for l in out), str(out[:3]))

    # A row written before the method column existed must read as unrecorded, never as
    # http. "We did not look" and "it was a REST call" are different statements.
    silent = usage.transport_lines(tools, {"mozilla": {}}, ["mozilla"])
    check("a missing method reads as unrecorded, not as REST",
          any("not recorded" in l for l in silent)
          and not any("REST GET" in l for l in silent[:2]), str(silent[:2]))


def test_the_parameters_that_decide_the_answer_are_pinned():
    """The rule's header says frozen. Three values it depends on were not.

    Measured by an external audit on 2026-09-12, each mutation applied on its own and the
    whole file re-run: `OWNER_COUNTRIES = {"CN"}` widened to `{"CN", "JP"}`, `curl` removed
    from `AMBIGUOUS_CLIENTS`, and `ATTRIBUTION_FIXED`'s time of day moved to 23:59 -- **all
    three left 61 passed, 0 failed.** The test asserted only the frozen DATE and the
    attribution day, so "pinned by tests/test_usage_gate.py" was true of the calendar and
    not of the arithmetic.

    What that costs is specific, not theoretical. The 2026-09-11 artifact reads YES on
    `curl` because JP is foreign to `{"CN"}`. Adding JP -- the edit 63c485b called "the
    owner's to make", since the owner's own machine egresses through Tokyo -- flips the
    gate to NO with CI green. Removing `curl` from the ambiguous list flips any untagged
    curl, from anywhere, to YES with CI green. Both directions were reachable without a
    single red check, which is the opposite of frozen.

    **A pin is a tripwire, not an endorsement.** `OWNER_COUNTRIES = {"CN"}` is disputed:
    the owner's traffic is observed leaving from JP, so the country clause may be looking
    for the wrong country, and the gate may be reading the owner's own probes as a
    stranger's. That argument belongs in a dated decision with the reasoning written down,
    not in a one-character edit nobody notices. This test does not say the value is right.
    It says changing it has to be on purpose.
    """
    print(chr(10) + "[gate] the parameters that decide the answer are pinned")

    check("OWNER_COUNTRIES is exactly {'CN'}", usage.OWNER_COUNTRIES == {"CN"},
          repr(usage.OWNER_COUNTRIES))
    check("curl is judged by country, not by name",
          "curl" in usage.AMBIGUOUS_CLIENTS, str(sorted(usage.AMBIGUOUS_CLIENTS)))
    check("mozilla too, for the same reason",
          "mozilla" in usage.AMBIGUOUS_CLIENTS, str(sorted(usage.AMBIGUOUS_CLIENTS)))
    check("claude-code too -- the repo points the owner's editor at production",
          "claude-code" in usage.AMBIGUOUS_CLIENTS, str(sorted(usage.AMBIGUOUS_CLIENTS)))
    check("ATTRIBUTION_FIXED is the exact instant, not just the day",
          usage.ATTRIBUTION_FIXED == "2026-09-07 12:35:00", usage.ATTRIBUTION_FIXED)

    # The floor is what decides which rows the gate may read at all. Moving it later
    # silently discards evidence; moving it earlier admits rows written before attribution
    # worked, which is what it exists to exclude.
    check("and it is not later than the gate's own frozen date",
          usage.ATTRIBUTION_FIXED[:10] == usage.GATE_FROZEN,
          "%s vs %s" % (usage.ATTRIBUTION_FIXED, usage.GATE_FROZEN))


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
