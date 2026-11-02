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
        {"storage_schema": "legacy-v1", "client": "sentineloracle", "tool": "", "n": 1259, "days": 14},
        {"storage_schema": "legacy-v1", "client": "mcpbeat", "tool": "", "n": 813, "days": 14},
        {"storage_schema": "legacy-v1", "client": "rootz-mcp-registry-prober", "tool": "", "n": 6, "days": 3},
        # An auth probe is not tool use either.
        {"storage_schema": "legacy-v1", "client": "io.verifymcp", "tool": "__verifymcp_auth_probe_367ac",
         "n": 1, "days": 1},
        # Our own tooling, which must never count however it behaves.
        {"storage_schema": "legacy-v1", "client": "vetagent-bench", "tool": "assess_token_risk", "n": 576, "days": 2},
        {"storage_schema": "legacy-v1", "client": "claude-code", "tool": "assess_token_risk", "n": 40, "days": 5},
        # The thing the gate exists to detect.
        {"storage_schema": "legacy-v1", "client": "somebodys-trading-bot", "tool": "assess_token_risk",
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

        usage.query = lambda *a, **k: {"data": [{"storage_schema": "legacy-v1", "n": 260}]}
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


def test_operational_evidence_refuses_unobserved_queries_and_private_output():
    """Operational observations never turn a refused/private reply into successful zero."""
    import importlib.util
    import json
    from pathlib import Path

    path = Path(ROOT) / "bench" / "operational_evidence.py"
    check("the bounded operational analyzer exists", path.is_file())
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("operational_evidence_acceptance_a", path)
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    start, end = "2026-10-18T10:00:00Z", "2026-10-18T11:00:00Z"

    def row(**changes):
        value = dict(tool="find_new_hot_pools", verdict="ok", cohort="self",
                     minute="2026-10-18 10:01:00", weighted_count="6",
                     sampled_rows="2", max_sample_interval="3")
        value.update(changes)
        return value

    def parse(reply):
        return op.aggregate_reply(reply, tool="find_new_hot_pools", cohort="self",
                                  start=start, end=end)

    def reply(rows):
        return {"http_status": 200, "body": {"data": rows}}

    valid = parse(reply([row()]))
    check("sample weights and stored rows remain distinct",
          valid["state"] == "observed" and valid["weighted_count"] == 6
          and valid["sampled_rows"] == 2 and valid["sampled"] is True)
    check("weighted counts are not exact users", "not exact users" in valid["count_label"])
    empty = parse(reply([]))
    check("a valid empty query is explicit", empty["state"] == "empty"
          and empty["weighted_count"] == 0 and empty["rows"] == [])
    for status, state in ((401, "http_error"), (403, "http_error"), (500, "http_error"),
                          (302, "redirect"), (0, "transport_error")):
        result = parse({"http_status": status, "body": {"data": [], "error": "PRIVATE-CALLER-SENTINEL"}})
        check("HTTP %d cannot masquerade as empty" % status,
              result["state"] == state and result["weighted_count"] is None)
        check("raw API errors never enter a report", "PRIVATE-CALLER-SENTINEL" not in json.dumps(result))
    for bad in (None, [], {"http_status": True}, {"http_status": 200, "body": {}},
                {"http_status": 200, "body": {"data": None}},
                {"http_status": 200, "body": {"success": False, "data": []}},
                {"http_status": 200, "body": {"data": [], "rows": 1}}):
        result = parse(bad)
        check("malformed or failed payload is unobserved", result["state"] == "malformed"
              and result["weighted_count"] is None)
    changes = [dict(weighted_count=True), dict(weighted_count="NaN"), dict(weighted_count=-1),
               dict(weighted_count=1.5), dict(sampled_rows=0), dict(sampled_rows=9),
               dict(max_sample_interval=0), dict(max_sample_interval=float("inf")),
               dict(weighted_count=7), dict(tool="get_token_liquidity"),
               dict(cohort="customer-secret"), dict(verdict="PRIVATE-CALLER-SENTINEL"),
               dict(client="PRIVATE-CALLER-SENTINEL"), dict(country="XX"),
               dict(minute="2026-10-18 12:00:00"), dict(minute="2026-10-18 10:01:01")]
    for change in changes:
        result = parse(reply([row(**change)]))
        check("untrusted aggregate fields are refused", result["state"] == "malformed"
              and "PRIVATE-CALLER-SENTINEL" not in json.dumps(result))
    duplicate = parse(reply([row(), row()]))
    check("duplicate aggregate cells are refused", duplicate["state"] == "malformed")
    check("there is a finite aggregate cap", 1 <= op.ROW_CAP <= 1000)
    capped = parse(reply([row()] * (op.ROW_CAP + 1)))
    check("truncated replies are distinct from empty and errors", capped["state"] == "truncated"
          and capped["weighted_count"] is None and capped["rows"] == [])
    check("credential redirects are never followed",
          op.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.invalid") is None)
    called = []

    class NeverOpen:
        def open(self, *args, **kwargs):
            called.append(True)
            raise AssertionError("network boundary should refuse this URL")

    result = op.request_json("http://api.cloudflare.com/unsafe", opener=NeverOpen())
    check("unsafe endpoints are refused before opening", not called and result["http_status"] == 0)
    result = op.request_json("https://example.invalid/unsafe", opener=NeverOpen())
    check("an unrelated host cannot receive credentials", not called and result["http_status"] == 0)


def test_operational_evidence_binds_tool_status_and_actual_deployment_windows():
    """Discovery status belongs to that tool; windows belong to actual successful uploads."""
    import importlib.util
    import json
    from pathlib import Path

    path = Path(ROOT) / "bench" / "operational_evidence.py"
    check("the deployment observation interface exists", path.is_file())
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("operational_evidence_acceptance_b", path)
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)

    def pack(body, status=200):
        return {"http_status": status, "body": body}

    def jobs(at, *, conclusion="success", step_conclusion="success", named=True):
        return pack({"jobs": [{"conclusion": conclusion, "steps": [
            {"name": "Deploy to Cloudflare" if named else "Smoke test production",
             "conclusion": step_conclusion, "completed_at": at},
            {"name": "Smoke test production", "conclusion": "success",
             "completed_at": "2026-10-18T10:08:59Z"}]}]})

    class Source:
        def __init__(self):
            self.requests = []
            self.replies = {
                39055170209: jobs("2026-10-18T09:50:00Z"),
                101: jobs("2026-10-18T10:00:00Z"),
                102: jobs("2026-10-18T10:03:00Z"),
                103: jobs("2026-10-18T10:07:00Z", conclusion="failure"),
            }

        def inventory(self):
            return pack({"total_count": 100, "workflow_runs": [
                {"id": n, "head_sha": c * 40, "created_at": "2026-10-18T00:00:00Z",
                 "updated_at": "2026-10-18T10:08:59Z"}
                for n, c in ((103, "c"), (101, "a"), (102, "b"))]})

        def jobs(self, run_id):
            return self.replies[run_id]

        def aggregate(self, tool, cohort, start, end):
            self.requests.append((tool, cohort, start, end))
            if cohort == "other":
                return pack({"data": []})
            return pack({"data": [{"tool": tool, "cohort": cohort,
                "verdict": "partial" if tool == "find_new_hot_pools" else "unknown",
                "minute": start[:16].replace("T", " ") + ":00",
                "weighted_count": 2, "sampled_rows": 2, "max_sample_interval": 1}]})

    source = Source()
    report = op.observe(source, captured_at="2026-10-18T10:09:00Z")
    check("the release anchor uses upload completion", report["discovery"]["anchor"] == "2026-10-18T09:50:00Z")
    check("discovery status is directly attributed", report["discovery"]["status_observed"] is True
          and report["discovery"]["cohorts"]["self"]["rows"][0]["verdict"] == "partial"
          and report["discovery"]["cohorts"]["other"]["state"] == "empty")
    check("known self and other queries are separate", {q[1] for q in source.requests} == {"self", "other"})
    check("other is never asserted to be an external user", "attribution unknown" in report["cohort_labels"]["other"])
    deployed = {d["run_id"]: d for d in report["deployments"]}
    check("an upload before a later job failure still bounds time", set(deployed) == {101, 102, 103})
    first = deployed[101]["windows"][0]
    check("the next actual upload censors the first five minutes",
          first["start"] == "2026-10-18T10:00:00Z" and first["end"] == "2026-10-18T10:03:00Z"
          and first["censored"] is True and first["censor_reason"] == "next_upload")
    check("a wholly censored steady window is not queried",
          deployed[101]["windows"][1]["state"] == "unobserved"
          and deployed[101]["windows"][1]["cohorts"] == {})
    last = deployed[103]["windows"][0]
    check("capture time censors an incomplete latest window",
          last["end"] == "2026-10-18T10:09:00Z" and last["censor_reason"] == "capture_clock")
    check("inventory truncation and unobserved transitions are disclosed", report["inventory"]["limited"] is True
          and report["inventory"]["potential_unobserved_transitions"] is True)
    check("empty/sparse observations never imply no cold-start effect",
          report["interpretation"] == "descriptive; no causal or no-effect verdict"
          and all(w["inference"] == "inconclusive" for d in deployed.values() for w in d["windows"]))
    check("the output never calculates a caller gate", "gate_verdict" not in json.dumps(report)
          and "external_users" not in json.dumps(report))
    for tool, cohort, start, end in source.requests:
        check("all requested intervals are positive and bounded", start < end <= "2026-10-18T10:09:00Z")
        sql = op.query_sql(tool, cohort, start, end)
        check("SQL binds the actual tool and supported minute bucket", "toStartOfInterval(timestamp, INTERVAL '1' MINUTE)" in sql
              and "blob2 = '%s'" % tool in sql and "SUM(_sample_interval)" in sql)
        check("self prefix filtering has the correct direction",
              ("blob4 LIKE 'vetagent-%'" in sql) if cohort == "self" else ("blob4 NOT LIKE 'vetagent-%'" in sql))
        check("SQL returns no caller/country dimension", " AS client" not in sql and "blob5" not in sql)
    for failure in (jobs("2026-10-18T09:50:00Z", step_conclusion="failure"),
                    jobs("2026-10-18T09:50:00Z", named=False), pack({}, 403)):
        bad = Source()
        bad.replies[39055170209] = failure
        result = op.observe(bad, captured_at="2026-10-18T10:09:00Z")
        check("failed/missing upload keeps discovery unobserved", result["discovery"]["status_observed"] is None
              and result["available"] is False
              and not any(q[0] == "find_new_hot_pools" for q in bad.requests))
    mixed = Source()
    mixed.aggregate = lambda *a: pack({"data": [{"tool": "get_token_liquidity", "cohort": "self",
        "verdict": "ok", "minute": "2026-10-18 10:00:00", "weighted_count": 2,
        "sampled_rows": 2, "max_sample_interval": 1}]})
    result = op.observe(mixed, captured_at="2026-10-18T10:09:00Z")
    check("another tool's ok can never prove discovery", result["discovery"]["status_observed"] is None
          and result["available"] is False)
    check("the cap and query budget remain finite", len(report["deployments"]) <= 10
          and report["limits"]["queries"] <= 42 and report["limits"]["inventory"] <= 100)
    for kwargs in (dict(days=91), dict(days=True), dict(deploy_limit=11), dict(deploy_limit=0),
                   dict(captured_at="not-a-time")):
        try:
            op.observe(Source(), **({"captured_at": "2026-10-18T10:09:00Z"} | kwargs))
        except ValueError:
            refused = True
        else:
            refused = False
        check("invalid observation limits refuse before collection", refused)


def test_operational_evidence_cli_and_opt_in_workflow_contract():
    """The real CLI is offline by default; the old scheduled gate job stays exact."""
    import hashlib
    import importlib.util
    import json
    import subprocess
    import tempfile
    from pathlib import Path

    path = Path(ROOT) / "bench" / "operational_evidence.py"
    check("the operational CLI exists", path.is_file())
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("operational_evidence_acceptance_c", path)
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    fixture = {"captured_at": "2026-10-18T10:09:00Z",
        "inventory": {"http_status": 200, "body": {"workflow_runs": [], "total_count": 0}},
        "jobs": {"39055170209": {"http_status": 200, "body": {"jobs": [{"steps": [
            {"name": "Deploy to Cloudflare", "conclusion": "success", "completed_at": "2026-10-18T09:50:00Z"}]}]}}},
        "aggregates": [{"tool": "find_new_hot_pools", "cohort": c,
            "start": "2026-10-18T09:50:00Z", "end": "2026-10-18T10:09:00Z",
            "reply": {"http_status": 200, "body": {"data": []}}} for c in ("self", "other")]}
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        src, out = base / "fixture.json", base / "report.json"
        src.write_text(json.dumps(fixture), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLOUDFLARE_API_TOKEN="TOKEN-SENTINEL",
                   CLOUDFLARE_ACCOUNT_ID="ACCOUNT-SENTINEL", GITHUB_TOKEN="GH-SENTINEL",
                   HTTP_PROXY="http://127.0.0.1:1", HTTPS_PROXY="http://127.0.0.1:1")
        def run(args):
            return subprocess.run([sys.executable, str(path), *args, "--output", str(out)],
                                  capture_output=True, encoding="utf-8", env=env, timeout=20)
        success = run(["--offline", str(src)])
        check("the real offline CLI exits successfully", success.returncode == 0, success.stdout + success.stderr)
        first = out.read_bytes()
        again = run(["--offline", str(src)])
        check("offline evaluation is byte deterministic", again.returncode == 0 and out.read_bytes() == first)
        result = json.loads(first)
        check("valid empty discovery stays explicit", result["discovery"]["status_observed"] is False
              and result["discovery"]["cohorts"]["self"]["state"] == "empty")
        default = run([])
        check("default invocation refuses accidental live access", default.returncode != 0
              and json.loads(out.read_text(encoding="utf-8"))["available"] is False)
        src.write_text('{"private":"PRIVATE-CALLER-SENTINEL"}', encoding="utf-8")
        failed = run(["--offline", str(src)])
        check("failed observations preserve JSON and fail the process", failed.returncode != 0
              and json.loads(out.read_text(encoding="utf-8"))["available"] is False)
        check("CLI diagnostics expose no raw input or secrets", all(s not in out.read_text(encoding="utf-8")
              + failed.stdout + failed.stderr + default.stdout + default.stderr
              for s in ("PRIVATE-CALLER-SENTINEL", "TOKEN-SENTINEL", "ACCOUNT-SENTINEL", "GH-SENTINEL")))
    wf = (Path(ROOT) / ".github" / "workflows" / "usage.yml").read_text(encoding="utf-8")
    start = wf.index("\n  usage:")
    end = wf.index("\n  operations-evidence:")
    old = wf[start:end]
    check("the complete original usage job is frozen", hashlib.sha256(old.encode()).hexdigest()
          == "8c8723abc3d7f5f93de3fd8d9f8a583f5ba8db199e4c9bde52603681573056ab")
    optional = wf[end:]
    check("manual boolean opt-in defaults false", "operations_evidence:" in wf
          and "type: boolean" in wf and "default: false" in wf)
    check("optional job never runs on a schedule", "github.event_name == 'workflow_dispatch'" in optional
          and "inputs.operations_evidence == true" in optional)
    check("optional job uses a standard bounded read-only runner", "runs-on: ubuntu-24.04" in optional
          and "timeout-minutes:" in optional and "contents: read" in optional and "actions: read" in optional
          and ": write" not in optional)
    check("the optional command requires explicit live intent", "python bench/operational_evidence.py --live" in optional
          and "secrets.CLOUDFLARE_API_TOKEN" in optional and "secrets.CLOUDFLARE_ACCOUNT_ID" in optional
          and "github.token" in optional)
    check("failure still retains only bounded aggregate JSON", "if: always()" in optional
          and "path: operational-evidence.json" in optional and "retention-days: 7" in optional)
    check("workflow keeps pinned existing actions", all(pin in optional for pin in (
          "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
          "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
          "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9")))


# T-069 acceptance contract: additions only; no older assertion is changed.
def _a1_module():
    import importlib.util
    from pathlib import Path
    path = Path(ROOT) / "bench" / "telemetry_diagnostics.py"
    check("T069 offline diagnostic composer exists", path.is_file())
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("t069_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _a1_bundle():
    import json
    from pathlib import Path
    return json.loads((Path(ROOT) / "tests" / "fixtures" / "telemetry_diagnostics_v1.json").read_text(encoding="utf-8"))


def _a1_cell(report, tool="assess_token_risk", cohort="self"):
    return next(r for r in report["results"] if r["tool"] == tool and r["cohort"] == cohort)


def _a1_cli(args):
    import subprocess
    from pathlib import Path
    # The parent starts the real CLI; these guards run INSIDE the child process.
    bootstrap = "\n".join([
        "import runpy,socket,subprocess,sys,urllib.request",
        "def refused(*args, **kwargs): raise AssertionError('offline_boundary_invoked')",
        "socket.socket=refused", "socket.create_connection=refused",
        "subprocess.run=refused", "subprocess.Popen=refused",
        "urllib.request.urlopen=refused", "urllib.request.OpenerDirector.open=refused",
        "sys.argv=sys.argv[1:]", "from pathlib import Path",
        "sys.path.insert(0,str(Path(sys.argv[0]).parent))",
        "runpy.run_path(sys.argv[0],run_name='__main__')"])
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLOUDFLARE_API_TOKEN="T069-TOKEN-PRIVATE",
               CLOUDFLARE_ACCOUNT_ID="T069-ACCOUNT-PRIVATE", GITHUB_TOKEN="T069-GH-PRIVATE")
    return subprocess.run([sys.executable, "-B", "-c", bootstrap,
                           str(Path(ROOT) / "bench" / "telemetry_diagnostics.py"), *map(str, args)],
                          capture_output=True, encoding="utf-8", env=env, timeout=20)


def test_a1_telemetry_weighted_empty_missing():
    import copy
    import operational_evidence as op
    from unittest.mock import patch
    module = _a1_module()
    if module is None:
        return
    bundle = _a1_bundle()
    before = copy.deepcopy(bundle)
    with patch.object(op, "aggregate_reply", wraps=op.aggregate_reply) as seam:
        report = module.diagnose(bundle)
    check("T069 reuses the existing parser once per selection", seam.call_count == 2)
    check("T069 preserves caller input", bundle == before)
    cell = _a1_cell(report)
    check("T069 weights and rows stay distinct", cell["weighted_count"] == 6
          and cell["sampled_rows"] == 2 and cell["sampled"] is True
          and cell["rows"][0]["max_sample_interval"] == 3)
    empty = _a1_cell(report, "find_new_hot_pools", "other")
    missing = _a1_cell(report, "assess_token_risk", "other")
    check("T069 valid empty is zero", empty["state"] == "empty"
          and empty["weighted_count"] == empty["sampled_rows"] == 0)
    check("T069 missing query is null", missing["state"] == "not_queried"
          and missing["weighted_count"] is missing["sampled_rows"] is None)
    check("T069 separate windows are never pooled", cell["start"] == "2026-10-18T10:00:00Z"
          and empty["start"] == "2026-10-18T10:30:00Z" and "weighted_count" not in report)
    check("T069 selections are fixed and sorted", [(r["tool"], r["cohort"]) for r in report["results"]]
          == sorted((t, c) for t in op.TOOLS for c in op.COHORTS))
    check("T069 missing dimensions alone do not fail", report["state"] == "observed")
    bundle["aggregates"] = []
    check("T069 no queries is unobserved", module.diagnose(bundle)["state"] == "unobserved")


def test_a1_telemetry_query_failures():
    import copy
    import operational_evidence as op
    module = _a1_module()
    if module is None:
        return
    cases = [({"http_status": n, "body": {"data": []}}, state) for n, state in
             ((401, "http_error"), (403, "http_error"), (500, "http_error"),
              (302, "redirect"), (0, "transport_error"))]
    cases += [(None, "malformed"), ({"http_status": True, "body": {}}, "malformed"),
              ({"http_status": 200, "body": {}}, "malformed"),
              ({"http_status": 200, "body": {"success": False, "data": []}}, "malformed"),
              ({"http_status": 200, "error": "response_too_large"}, "truncated")]
    base = _a1_bundle()
    row = base["aggregates"][0]["reply"]["body"]["data"][0]
    for change in ({"client": "T069-ROW-PRIVATE"}, {"weighted_count": 7}, {"weighted_count": True},
                   {"weighted_count": "NaN"}, {"sampled_rows": 0}, {"max_sample_interval": 0},
                   {"verdict": "T069-VERDICT-PRIVATE"}):
        cases.append(({"http_status": 200, "body": {"data": [dict(row, **change)]}}, "malformed"))
    cases += [({"http_status": 200, "body": {"data": [row, row]}}, "malformed"),
              ({"http_status": 200, "body": {"data": [row] * (op.ROW_CAP + 1)}}, "truncated"),
              ({"http_status": 200, "body": {"data": [], "rows_before_limit": 1}}, "truncated")]
    for reply, expected in cases:
        bundle = copy.deepcopy(base)
        bundle["aggregates"][0]["reply"] = reply
        report = module.diagnose(bundle)
        got = _a1_cell(report)
        check("T069 query %s cannot masquerade as zero" % expected, report["state"] == "partial"
              and got["state"] == expected and got["weighted_count"] is got["sampled_rows"] is None)
        check("T069 failed selection retains healthy neighbor",
              _a1_cell(report, "find_new_hot_pools", "other")["state"] == "empty")


def test_a1_telemetry_invalid_contract():
    import copy
    module = _a1_module()
    if module is None:
        return
    base = _a1_bundle()
    cases = [None, [], {}, dict(base, schema=True), dict(base, storage_schema="calls-v2"),
             dict(base, captured_at="2026-10-18 11:00:00"), dict(base, captured_at=True),
             dict(base, captured_at="2026-02-30T11:00:00Z"), dict(base, extra="T069-TOP-PRIVATE")]
    for field, value in (("start", "2026-01-01T00:00:00Z"), ("start", "2026-10-18T11:00:00Z"),
                         ("end", "2026-10-19T00:00:00Z"), ("end", "bad-T069-TIME-PRIVATE"),
                         ("tool", []), ("cohort", "T069-COHORT-PRIVATE")):
        bundle = copy.deepcopy(base)
        bundle["aggregates"][0][field] = value
        cases.append(bundle)
    duplicate = copy.deepcopy(base)
    duplicate["aggregates"].append(copy.deepcopy(duplicate["aggregates"][0]))
    cases.extend([duplicate, dict(base, aggregates=base["aggregates"] * 3)])
    for number in (float("nan"), float("inf"), float("-inf")):
        bundle = copy.deepcopy(base)
        bundle["aggregates"][0]["reply"]["body"]["data"][0]["weighted_count"] = number
        cases.append(bundle)
    for bundle in cases:
        try:
            module.diagnose(bundle)
        except ValueError as exc:
            check("T069 invalid bundle has a fixed safe error", len(str(exc)) < 80
                  and "PRIVATE" not in str(exc) and "2026" not in str(exc))
        else:
            check("T069 invalid bundle is refused", False)


def test_a1_telemetry_legacy_dimensions():
    import json
    module = _a1_module()
    if module is None:
        return
    report = module.diagnose(_a1_bundle())
    check("T069 fixed report schema", report["schema"] == "telemetry-diagnostics-report-v1")
    for key in ("chain", "request_latency"):
        check("T069 legacy %s is not recorded" % key, report["capabilities"][key]["state"] == "not_recorded")
    for key in ("reason_breakdown", "error_rate", "liquidity_tool", "caller_identity"):
        check("T069 %s is not queried" % key, report["capabilities"][key]["state"] == "not_queried")
    check("T069 identity is explicitly unsupported", "unsupported_by_anonymous_diagnostics"
          in json.dumps(report["capabilities"]["caller_identity"]))
    check("T069 cannot claim a gate or readiness", report["production_gate_evaluated"] is False
          and report["interpretation"] == "descriptive; not customer, readiness, or service-quality evidence")
    check("T069 cannot invent missing measurements", all(key not in json.dumps(report)
          for key in ('"p95"', '"latency_ms"', '"unknown_rate"', '"customers"', '"score"', '"slo"')))


def test_a1_telemetry_private_input_and_offline_boundary():
    import copy
    import json
    import socket
    import subprocess
    import tempfile
    import urllib.request
    from pathlib import Path
    from unittest.mock import patch
    module = _a1_module()
    if module is None:
        return
    bundle = _a1_bundle()
    bundle["aggregates"][0]["reply"].update(private="T069-ENVELOPE-PRIVATE", error="T069-ERROR-PRIVATE")
    bundle["aggregates"][0]["reply"]["body"]["private"] = "T069-BODY-PRIVATE"
    def blocked(*args, **kwargs):
        raise AssertionError("offline_boundary_invoked")
    with patch.object(socket, "socket", blocked), patch.object(socket, "create_connection", blocked), \
            patch.object(subprocess, "run", blocked), patch.object(subprocess, "Popen", blocked), \
            patch.object(urllib.request, "urlopen", blocked), patch.object(urllib.request.OpenerDirector, "open", blocked):
        safe = json.dumps(module.diagnose(copy.deepcopy(bundle)))
    check("T069 raw envelope/body/error never reflected", "T069-" not in safe)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        src, out = root / "T069-INPUT-PATH-PRIVATE.json", root / "T069-OUTPUT-PATH-PRIVATE.json"
        src.write_text(json.dumps(bundle), encoding="utf-8")
        results = [_a1_cli(["--input", src, "--output", out]), _a1_cli([]),
                   _a1_cli(["--T069-ARG-PRIVATE"]),
                   _a1_cli(["--input", root / "T069-MISSING-PATH-PRIVATE", "--output", root / "unused.json"])]
        text = "".join(r.stdout + r.stderr for r in results) + out.read_text(encoding="utf-8")
        sentinels = ["T069-INPUT-PATH-PRIVATE", "T069-OUTPUT-PATH-PRIVATE", "T069-ARG-PRIVATE",
                     "T069-MISSING-PATH-PRIVATE", "T069-TOKEN-PRIVATE", "T069-ACCOUNT-PRIVATE",
                     "T069-GH-PRIVATE", "T069-ENVELOPE-PRIVATE", "T069-BODY-PRIVATE", "T069-ERROR-PRIVATE"]
        check("T069 child errors do not echo private text", all(s not in text for s in sentinels), text[:100])
        check("T069 default/unknown arguments/input failure refuse without network", results[0].returncode == 0
              and all(r.returncode != 0 for r in results[1:]) and "Traceback" not in text
              and "offline_boundary_invoked" not in text)


def test_a1_telemetry_cli_preserves_files():
    import hashlib
    import json
    import tempfile
    from pathlib import Path
    module = _a1_module()
    if module is None:
        return
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        src = root / "input.json"
        src.write_text(json.dumps(_a1_bundle()), encoding="utf-8")
        before = hashlib.sha256(src.read_bytes()).hexdigest()
        first, second = root / "first.json", root / "second.json"
        a, b = _a1_cli(["--input", src, "--output", first]), _a1_cli(["--input", src, "--output", second])
        check("T069 real fixture CLI is deterministic", a.returncode == b.returncode == 0
              and first.read_bytes() == second.read_bytes())
        saved = first.read_bytes()
        existing, alias = _a1_cli(["--input", src, "--output", first]), _a1_cli(["--input", src, "--output", src])
        check("T069 preserves existing output and input aliases", existing.returncode != 0
              and alias.returncode != 0 and first.read_bytes() == saved
              and hashlib.sha256(src.read_bytes()).hexdigest() == before)
        failed_bundle = _a1_bundle()
        failed_bundle["aggregates"][0]["reply"] = {"http_status": 403, "body": {"data": []}}
        failed_src, failed_out = root / "failed-input.json", root / "failed-output.json"
        failed_src.write_text(json.dumps(failed_bundle), encoding="utf-8")
        failed = _a1_cli(["--input", failed_src, "--output", failed_out])
        report = json.loads(failed_out.read_text(encoding="utf-8"))
        check("T069 failed query retains a report and failing native exit", failed.returncode == 1
              and report["state"] == "partial" and _a1_cell(report)["state"] == "http_error")
        invalids = ['{"schema":"one","schema":"two"}', '{"value":NaN}', '[[' * 1100,
                    '"' + 'x' * (1024 * 1024) + '"', '{bad']
        for i, raw in enumerate(invalids):
            bad, out = root / ("bad%d.json" % i), root / ("bad-out%d.json" % i)
            bad.write_text(raw, encoding="utf-8")
            run = _a1_cli(["--input", bad, "--output", out])
            check("T069 duplicate/deep/nonfinite/oversize/malformed input refuses safely", run.returncode != 0
                  and "Traceback" not in run.stderr + run.stdout and "one" not in run.stderr + run.stdout)


# T-074 additive tests; original functions/helpers/assertions/runner remain exact.
_T074_PROJECTION = "if(blob7 = '', 'legacy-v1', if(blob7 = 'calls-v2-io', 'calls-v2-io', 'unsupported'))"
_T074_PRIVATE = "T074-PRIVATE-PROVIDER"
_T074_FROZEN_HASHES = {
    "is_self": "249a352b8dbbb3b9553cbbec979988ae20a03d7d37a47267f27f3e4fed605b6b",
    "AMBIGUOUS_CLIENTS": "aa505d468679d0e0e4c9f312914596c98c5887d7abaebe5e7791792da68b8ab4",
    "OWNER_COUNTRIES": "21228d8350478bc473953e8c61008e303f8b37615e4302583655b52c4a7cff0c",
    "ATTRIBUTION_FIXED": "73825f877dfb44da50f898165f868a9b1fc79e8d989f19bc2e3239440fd36b86",
    "gate_window": "5d70dba113f84879fc3df358263412e43182c47877c888627838d9d52bbcb56f",
    "GATE_FROZEN": "00c799ab1361fcb980e3ff8fd48815747b5226ad0828868bd3a7e3d33bdf67df",
    "RULE_TEXT": "4e8d241c8a0f60643ec04a2c68d5b885afd5f274af21500e1d240a940e8f451d",
    "gate_verdict": "9d0b809264938afaa5669fc7c90242c1665679867dc82cdaacf11a36973a260e",
    "PRODUCTION_WINDOW_DAYS": "d83e50045f741b793b0dc1a0268d6e67faf86f6ff42acc03b8ec820f9d9c77db",
    "PRODUCTION_EXCLUDED_CLIENTS": "1497999afa08adcab8c1ac4f9931b18b86dd59a666d3071f9af13dc117478eb9",
    "production_verdicts": "3d80cb724f5c12cf4f4afc4383d74042ca9735204a6990c8b4eb0746178d3109",
}


def _t074_slot(sql):
    text = " ".join(sql.lower().split())
    if " as calls" in text:
        return "Q1"
    if "count(distinct todate(timestamp))" in text:
        return "Q3"
    if "tohour(timestamp)" in text:
        return "Q4"
    if "timestamp < todatetime(" in text:
        return "Q5"
    column = re.search(r"\b(blob[23456]) as k\b", text)
    if column:
        return {"blob2": "Q7", "blob4": "Q8", "blob5": "Q9",
                "blob3": "Q10", "blob6": "Q11"}[column.group(1)]
    if " as client" in text and " as country" in text:
        return "Q2"
    if " as why" in text:
        return "P2" if "= 'unknown'" in text else "P3"
    if " as verdict" in text:
        return "P1"
    if "sum(_sample_interval)" in text and "not startswith(" in text:
        return "Q6"
    raise RuntimeError("T074_UNEXPECTED_QUERY_SHAPE")


def _t074_case(domains, eligible=False):
    legacy = "legacy-v1" in domains
    client = "t074-example-agent"
    replies = {"Q%d" % i: {"data": []} for i in range(1, 12)}
    replies["Q1"]["data"] = [dict(storage_schema=s, calls=8, errors=1, clients=1, countries=1)
                              for s in domains]
    if legacy:
        replies["Q2"]["data"] = [dict(storage_schema="legacy-v1", client=client,
                                         country="US", n=6)]
        replies["Q5"]["data"] = [dict(storage_schema="legacy-v1", n=0)]
    if legacy and eligible:
        replies["Q3"]["data"] = [dict(storage_schema="legacy-v1", client=client,
            tool="assess_token_risk", n=6, days=2)]
        replies["Q4"]["data"] = [dict(storage_schema="legacy-v1", client=client,
            verdict=v, country="US", method="http", day=d, hour=h, n=3)
            for v, d, h in (("low", "2026-10-28", 3), ("high", "2026-10-29", 4))]
    for schema in domains:
        group = "legacy_named_nonself" if schema == "legacy-v1" else (
            "v2" if schema == "calls-v2-io" else "unsupported")
        replies["Q6"]["data"].append(dict(storage_schema=schema, attribution_group=group,
                                            n=6 if schema == "legacy-v1" else 7))
        for slot, value in (("Q7", "assess_token_risk"),
                            ("Q8", client if schema == "legacy-v1" else "vetagent-other"),
                            ("Q9", "US" if schema == "legacy-v1" else "??"),
                            ("Q10", "low"), ("Q11", "")):
            replies[slot]["data"].append(dict(storage_schema=schema, k=value, n=3))
    return {"domains": tuple(domains), "eligible": legacy and eligible, "replies": replies}


def _t074_main(case, credentials=True, production=False):
    import contextlib
    import copy
    import io
    import socket
    import subprocess
    import tempfile
    import time
    import urllib.request
    from unittest.mock import patch
    seen, gates, effects = [], [], []
    stdout, stderr = io.StringIO(), io.StringIO()
    original_gate = usage.gate_verdict
    fake_env = ({"CLOUDFLARE_ACCOUNT_ID": "T074-DUMMY-ACCOUNT",
                 "CLOUDFLARE_API_TOKEN": "T074-DUMMY-TOKEN"} if credentials else {})
    argv = ["usage.py", "--days", "14"]
    target = None
    if production:
        target = os.path.join(tempfile.mkdtemp(prefix="t074-mode-"), "verdicts.json")
        argv = ["usage.py", "--write-verdicts", target]

    def query(sql, account, token):
        if account != "T074-DUMMY-ACCOUNT" or token != "T074-DUMMY-TOKEN":
            raise RuntimeError("T074_CREDENTIAL_BOUNDARY")
        slot = _t074_slot(sql)
        seen.append((slot, sql))
        if slot not in case["replies"]:
            raise RuntimeError("T074_UNEXPECTED_QUERY_SLOT")
        return copy.deepcopy(case["replies"][slot])

    def gate(tools, prof):
        gates.append(copy.deepcopy((tools, prof)))
        return original_gate(tools, prof)

    def forbidden(*args, **kwargs):
        effects.append("forbidden_effect")
        raise RuntimeError("T074_UNMOCKED_EFFECT")

    value, escaped = None, None
    with contextlib.ExitStack() as stack:
        for obj, name, replacement in ((usage, "query", query), (usage, "gate_verdict", gate),
                (usage.os, "environ", fake_env), (sys, "argv", argv),
                (socket, "socket", forbidden), (socket, "create_connection", forbidden),
                (urllib.request, "urlopen", forbidden), (urllib.request.OpenerDirector, "open", forbidden),
                (subprocess, "run", forbidden), (subprocess, "Popen", forbidden), (time, "sleep", forbidden)):
            stack.enter_context(patch.object(obj, name, replacement))
        stack.enter_context(contextlib.redirect_stdout(stdout))
        stack.enter_context(contextlib.redirect_stderr(stderr))
        try:
            value = usage.main()
        except Exception as exc:
            escaped = type(exc).__name__
    artifact = None
    if target and os.path.exists(target):
        import json
        with open(target, encoding="utf-8") as handle:
            artifact = json.load(handle)
    return {"value": value, "exception": escaped, "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(), "seen": seen, "gates": gates,
            "effects": effects, "artifact": artifact}


def _t074_show(name, result):
    print("\n[T074 %s] main_return=%s exception=%s query_slots=%s" %
          (name, result["value"], result["exception"], [slot for slot, _ in result["seen"]]))
    print(result["stdout"], end="")
    if result["stderr"]:
        print(result["stderr"], end="")
    check("T074 %s uses real main without harness/import exceptions" % name,
          result["exception"] is None, str(result["exception"]))
    check("T074 %s makes no unmocked network/process/sleep call" % name,
          result["effects"] == [], str(result["effects"]))


def _t074_no_current_decision(name, result):
    text = result["stdout"].lower()
    check("T074 %s has no current strategy/adoption directive" % name,
          not re.search(r"->\s*(?:no|yes).*strategy|no new features|experiment c only|distribution problem", text),
          text[-220:])
    check("T074 %s does not claim no attributable/current external callers" % name,
          "no. no attributable client" not in text and "no external callers" not in text,
          text[-220:])


def _t074_expected_slots(eligible):
    return ["Q1", "Q2", "Q3"] + (["Q4"] if eligible else []) + [
        "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "Q11"]


def test_a3_usage_summary_and_early_returns():
    cases = []
    empty = _t074_case(())
    cases.append(("U07-empty", empty, 0))
    zero = _t074_case(("calls-v2-io",))
    zero["replies"]["Q1"] = {"data": [dict(storage_schema="calls-v2-io", calls=0,
                                              errors=0, clients=0, countries=0)]}
    cases.append(("U07-qualified-zero", zero, 0))
    failed = _t074_case(())
    failed["replies"]["Q1"] = {"errors": [_T074_PRIVATE]}
    cases.append(("U08-failed", failed, 1))
    missing = _t074_case(("legacy-v1",))
    del missing["replies"]["Q1"]["data"][0]["storage_schema"]
    cases.append(("U09-missing-marker", missing, 1))
    for name, case, expected in cases:
        result = _t074_main(case)
        _t074_show(name, result)
        check("T074 %s preserves exact primary return/query budget" % name,
              result["value"] == expected and [s for s, _ in result["seen"]] == ["Q1"], str(result["value"]))
        check("T074 %s emits no raw provider diagnostic/probe" % name,
              _T074_PRIVATE not in result["stdout"] + result["stderr"]
              and "curl " not in result["stdout"].lower()
              and "send one call" not in result["stdout"].lower())
        check("T074 %s does not evaluate a missing legacy domain" % name, not result["gates"])
        _t074_no_current_decision(name, result)
    result = _t074_main(empty, credentials=False)
    _t074_show("credentials", result)
    check("T074 missing credentials returns2 without a query", result["value"] == 2 and not result["seen"])


def test_a3_usage_main_domain_matrix():
    inputs = (("U01", ("legacy-v1",), True), ("U02", ("legacy-v1",), False),
              ("U03", ("calls-v2-io",), False), ("U04-handshake-only", ("calls-v2-io",), False),
              ("U05", ("legacy-v1", "calls-v2-io"), True),
              ("U06", ("legacy-v1", "calls-v2-io"), False),
              ("U10", ("unsupported",), False),
              ("U11", ("legacy-v1", "calls-v2-io", "unsupported"), True))
    for name, domains, eligible in inputs:
        case = _t074_case(domains, eligible)
        if name == "U04-handshake-only":
            case["replies"]["Q6"] = {"data": []}
            case["replies"]["Q7"] = {"data": []}
        result = _t074_main(case)
        _t074_show(name, result)
        expected_exit = 1 if "unsupported" in domains else 0
        check("T074 %s follows exact existing query order/native-value policy" % name,
              result["value"] == expected_exit and [s for s, _ in result["seen"]] == _t074_expected_slots(eligible))
        text = result["stdout"].lower()
        for schema in domains:
            word = "v2" if schema == "calls-v2-io" else schema.split("-")[0]
            check("T074 %s retains %s presence before filtering" % (name, schema), word in text)
        if domains != ("legacy-v1",):
            cardinality = [line for line in text.splitlines() if re.search(
                r"unique\s+(?:clients|countries)|raw totals:.*clients", line)]
            check("T074 %s has no all-version identity/country cardinality" % name,
                  all("legacy" in line for line in cardinality), str(cardinality))
            check("T074 %s explicitly marks current identity unavailable" % name,
                  any(any(word in line for word in ("identity", "caller", "client"))
                      and any(word in line for word in ("not_recorded", "not recorded", "unavailable",
                              "not comparable", "not_comparable", "not evaluated")) for line in text.splitlines()))
            check("T074 %s does not promise new rows carry countries" % name,
                  "rows from today carry a country" not in text)
        if eligible:
            check("T074 %s reaches the original rule only for legacy" % name,
                  len(result["gates"]) == 1 and "legacy" in text)
            if result["gates"]:
                tools, prof = result["gates"][0]
                check("T074 %s preserves exact legacy caller inputs" % name,
                      tools == [("t074-example-agent", {"n": 6, "days": 2,
                          "tools": {"assess_token_risk"}, "ambiguous": False})]
                      and prof == {"t074-example-agent": {"verdicts": {"low": 3, "high": 3},
                          "hours": {3, 4}, "days": {"2026-10-28", "2026-10-29"},
                          "countries": {"US"}, "country_n": {"US": 6}, "methods": {"http": 6}, "n": 6}})
        elif "legacy-v1" not in domains:
            check("T074 %s has no fabricated empty-legacy gate result" % name, not result["gates"])
        _t074_no_current_decision(name, result)


def test_a3_usage_secondary_states():
    faults = [("U12", "Q3", "failed"), ("U13", "Q4", "failed"),
              ("U14", "Q2", "failed"), ("U15", "Q5", "failed"), ("U16", "Q6", "failed")]
    faults += [("U17", "Q%d" % i, "failed") for i in range(7, 12)]
    faults += [("U18", "Q%d" % i, "missing") for i in range(2, 12)]
    for label, slot, kind in faults:
        name = "%s-%s-%s" % (label, slot, kind)
        case = _t074_case(("legacy-v1", "calls-v2-io"), True)
        if kind == "failed":
            case["replies"][slot] = {"errors": [_T074_PRIVATE]}
        else:
            del case["replies"][slot]["data"][0]["storage_schema"]
        result = _t074_main(case)
        _t074_show(name, result)
        check("T074 %s returns partial1 without adding requests" % name,
              result["value"] == 1 and [s for s, _ in result["seen"]] == _t074_expected_slots(slot != "Q3"))
        text = result["stdout"].lower()
        check("T074 %s names failed/malformed/unavailable rather than empty" % name,
              any(word in text for word in ("failed", "malformed", "unavailable", "could not", "missing")))
        check("T074 %s retains known neighboring evidence and v2 presence" % name,
              "assess_token_risk" in text and "v2" in text)
        check("T074 %s never reflects provider text" % name,
              _T074_PRIVATE not in result["stdout"] + result["stderr"])
        if slot in ("Q3", "Q4"):
            check("T074 %s never passes failed caller/profile data as empty" % name, not result["gates"])
        _t074_no_current_decision(name, result)


def test_a3_usage_reconciliation_and_tail():
    case = _t074_case(("legacy-v1", "calls-v2-io", "unsupported"), True)
    case["replies"]["Q6"]["data"] = [
        dict(storage_schema="legacy-v1", attribution_group="legacy_named_nonself", n=8),
        dict(storage_schema="legacy-v1", attribution_group="legacy_self", n=2),
        dict(storage_schema="legacy-v1", attribution_group="legacy_no_client", n=1),
        dict(storage_schema="calls-v2-io", attribution_group="v2", n=7),
        dict(storage_schema="unsupported", attribution_group="unsupported", n=4)]
    result = _t074_main(case)
    _t074_show("U19", result)
    text = result["stdout"].lower()
    check("T074 U19 separates no-client/v2/unsupported and unexplained residual",
          any(word in text for word in ("no_client", "no-client", "no client"))
          and "v2" in text and "unsupported" in text
          and any(word in text for word in ("residual", "unexplained", "unresolved", "inconsistent")))
    check("T074 U19 never assigns every gap to self", "these belong to clients filtered out as ours" not in text
          and "expected to hold only vetagent" not in text)
    _t074_no_current_decision("U19", result)
    for slot, bound in (("Q2", 500), ("Q3", 200), ("Q4", 1000), ("Q8", 8)):
        cap = _t074_case(("legacy-v1",), True)
        if slot == "Q2":
            cap["replies"][slot]["data"] = [dict(storage_schema="legacy-v1",
                client="fixture-cap-%03d" % i, country="US", n=1) for i in range(bound)]
        elif slot == "Q3":
            cap["replies"][slot]["data"] = [dict(storage_schema="legacy-v1",
                client="fixture-cap-%03d" % i, tool="assess_token_risk", n=1, days=2) for i in range(bound)]
            cap["replies"]["Q4"] = {"data": []}
        elif slot == "Q4":
            cap["replies"][slot]["data"] = [dict(storage_schema="legacy-v1", client="t074-example-agent",
                verdict=("low", "medium", "high", "unknown")[i % 4], country="US", method="http",
                day="2026-10-%02d" % (20 + i // 96), hour=(i // 4) % 24, n=1) for i in range(bound)]
        else:
            cap["replies"][slot]["data"] = [dict(storage_schema="legacy-v1",
                k="fixture-cap-%03d" % i, n=1) for i in range(bound)]
        result = _t074_main(cap)
        name = "U20-%s" % slot
        _t074_show(name, result)
        check("T074 %s returns partial1 for capped evidence" % name,
              result["value"] == 1, str(result["value"]))
        check("T074 %s states cap/limited coverage" % name,
              any(word in result["stdout"].lower() for word in ("capped", "truncated", "limited", "incomplete")))
        check("T074 %s keeps the original slot budget" % name,
              [s for s, _ in result["seen"]] == _t074_expected_slots(True))
        _t074_no_current_decision(name, result)


def test_a3_usage_frozen_inputs_and_query_budget():
    import ast
    import hashlib
    source = open(os.path.join(ROOT, "bench", "usage.py"), encoding="utf-8").read()
    actual = {}
    for node in ast.parse(source).body:
        names = [node.name] if isinstance(node, ast.FunctionDef) else [
            target.id for target in getattr(node, "targets", []) if isinstance(target, ast.Name)]
        for name in names:
            if name in _T074_FROZEN_HASHES:
                actual[name] = hashlib.sha256(ast.get_source_segment(source, node).encode("utf-8")).hexdigest()
    for name, expected in _T074_FROZEN_HASHES.items():
        check("T074 protected source %s is byte-exact" % name, actual.get(name) == expected)
    case = _t074_case(("legacy-v1", "calls-v2-io"), True)
    result = _t074_main(case)
    _t074_show("SQL-budget", result)
    for slot, sql in result["seen"]:
        normalized = " ".join(sql.lower().split())
        check("T074 %s projects the root-fixed schema expression" % slot,
              " ".join(_T074_PROJECTION.lower().split()) + " as storage_schema" in normalized)
        check("T074 %s groups the projected domain" % slot,
              "group by storage_schema" in normalized)
        if slot in ("Q2", "Q3", "Q4"):
            where = normalized.split(" where ", 1)[1].split(" group by ", 1)[0]
            check("T074 %s restricts legacy before ranking" % slot, "blob7 = ''" in where)
        if slot in ("Q3", "Q4", "Q6"):
            check("T074 %s keeps literal attribution floor and weights" % slot,
                  "2026-09-07 12:35:00" in sql and "sum(_sample_interval)" in normalized)
        if slot == "Q5":
            check("T074 Q5 retains the complement and weights", "timestamp < todatetime('2026-09-07 12:35:00')" in normalized
                  and "sum(_sample_interval)" in normalized)
        limit = {"Q2": 500, "Q3": 200, "Q4": 1000, "Q7": 8, "Q8": 8, "Q9": 8, "Q10": 8, "Q11": 8}.get(slot)
        if limit:
            check("T074 %s retains original limit" % slot, "limit %d" % limit in normalized)
    production = {"replies": {
        "P1": {"data": [dict(verdict=v, n=n) for v, n in (("low", 7), ("medium", 5), ("high", 2), ("unknown", 4))]},
        "P2": {"data": [dict(why="coverage|liquidity:no pair", n=4)]},
        "P3": {"data": [dict(why="driver=honeypot", n=2)]}}}
    result = _t074_main(production, production=True)
    _t074_show("production", result)
    check("T074 production is original3 query/native-value policy", result["value"] == 0
          and [s for s, _ in result["seen"]] == ["P1", "P2", "P3"])
    check("T074 production keeps synthetic weighted counts and only CI exclusion", result["artifact"] is not None
          and result["artifact"]["counts"] == {"low": 7, "medium": 5, "high": 2, "unknown": 4}
          and result["artifact"]["excluded_clients"] == ["vetagent-ci-smoke"])
    for _, sql in result["seen"]:
        check("T074 production SQL remains seven-day assessment/onlyCI with no domain filter",
              "INTERVAL '7' DAY" in sql and "assess_token_risk" in sql and "vetagent-ci-smoke" in sql
              and "sum(_sample_interval)" in sql and "blob7" not in sql and "vetagent-other" not in sql)
    production["replies"]["P1"] = {"errors": [_T074_PRIVATE]}
    result = _t074_main(production, production=True)
    _t074_show("production-primary-failure", result)
    check("T074 failed production query remains1/read-only with no artifact", result["value"] == 1
          and [s for s, _ in result["seen"]] == ["P1"] and result["artifact"] is None)


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
