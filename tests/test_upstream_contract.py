"""test_upstream_contract.py — upstream API contract tests (hits the real network).

Why this exists: VetAgent's worst production bug was reading isHoneypot out of
simulationResult when upstream actually puts it in honeypotResult — we read a key
that does not exist upstream, got None, treated it as False, and so the honeypot
check **always passed**. No offline test could have caught it.

Two things changed on 2026-09-20, both because this file was the instrument that should
have caught E25 and E26 and did not.

**The field list is generated.** It used to be typed by hand: ten assertions for
honeypot.is, six for DexScreener, six for GeckoTerminal, and four for RugCheck -- and the
four were "reachable", "has a score field", "risks is an array or absent". So
`topHolders`, `totalHolders` and the entire `token_extensions` block were watched by
nothing, which is exactly where E25 and E26 lived. A hand-written list is a second copy
of a fact whose first copy is the code, and the second copy is always the stale one. Now
`tools/upstream_fields.py` reads `src/risk.py` and derives every JSON path the engine
actually depends on -- 122 of them, against the 25 that were written down.

**The assertion is a distribution, not a presence.** `totalHolders` does not vanish; it
is there for some mints and not others. Measured 2026-09-20 across 64 Solana mints: 24
carry a holder list and 40 do not, in every sweep, with all 64 answering HTTP 200 -- so
this is RugCheck's coverage of a mint, not an outage and not a fact about the token. A
test that asked "is the field there?" of one token would be green on BONK, red on USDC,
and get labelled flaky and switched off, which is how an instrument dies. So the baseline
records, per path, what share of a fixed probe set carries it, and the test fails when
that share collapses.

Run:       python tests/test_upstream_contract.py
Re-freeze: python tests/test_upstream_contract.py --write
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import upstream_fields                                            # noqa: E402

BASELINE = os.path.join(HERE, "upstream_baseline.json")
TIMEOUT = "30"
UA = "vetagent-contract-test"
# 1.5s. This was briefly 2.0 on the reading that honeypot.is was throttling us in bursts:
# every full run reported exactly four unobserved probes. It was not throttling. The four
# were `test_simulator_chain_coverage` asking about Arbitrum, Polygon, Optimism and
# Avalanche, which answer `{"code":400,"error":"Invalid chain"}` because honeypot.is does
# not cover them -- the expected negative the test is there to observe. Every honeypot.is
# URL this file actually depends on answered 200 on every attempt. The number is back
# where it was, and the wrong reason is written down rather than quietly deleted.
CALL_GAP = 1.5
# GeckoTerminal keyless is rate-limited per egress IP, and this repository has measured
# that before: D8 / W29 found 48 of 60 keyless calls answered 429 from a Worker, which is
# why production puts a keyed CoinGecko ahead of it. Eight probes at 1.5s drew three 429s
# here. The test holds no key, so it pays the limit in seconds instead.
SOURCE_CALL_GAP = {"geckoterminal": 5.0}

# Stable reference tokens
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

# The probe set. Stable identities only -- a new mint from today's listings would make
# the baseline unreproducible next month, and an unreproducible baseline is a number
# nobody can check. Chosen to span the thing being measured: USDC, USDT, PYUSD and WSOL
# carry no holder list while BONK, JUP and TRUMP carry a full one, so a baseline built
# here is a mixture rather than an anecdote.
RUGCHECK_MINTS = [
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",   # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",   # USDT
    BONK,
    PYUSD,
    "CKfatsPMUf8SkiURsDXs7eK6GWb4Jsd6UDbs7twMCWxo",   # BERN
    "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",   # TRUMP
    "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ",   # W
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",    # JUP
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",   # WIF
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",    # JTO
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",   # RAY
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",   # PYTH
    "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",    # ORCA
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",    # mSOL
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",    # RENDER
    "So11111111111111111111111111111111111111112",    # WSOL
]

HONEYPOT_TOKENS = [
    (WETH, 1),
    ("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", 56),    # WBNB
    ("0x4200000000000000000000000000000000000006", 8453),  # WETH on Base
    ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 1),     # USDT
    # The four above are healthy, and a healthy token exercises none of the fields that
    # only appear when something is wrong. Measured 2026-09-20: WETH returns no
    # `holderAnalysis` block at all and an empty `flags` array, so a baseline built on
    # majors alone recorded `holderAnalysis.holders`, `.failed` and `.siphoned` as never
    # present -- and those three are the entire input to E23, the rule that decides
    # whether a honeypot flag may be released. The instrument was watching everything
    # except the part that can silence a detection.
    ("0xb954d1ba6bB92123609Fcfb724c68B810c668feB", 1),     # flags + holderAnalysis
    ("0x50614CC8e44F7814549c223aA31db9296e58057c", 1),     # simulationError + flags
    # Eight, not six, and the same for the two lists below: MIN_FOR_SHARE is 8, so a
    # shorter list silently switched the coverage rule off for that source and left it
    # judged on presence and type -- which is the rule this rewrite exists for, absent
    # from three of the four sources. The run said so on every line ("under the 8 needed
    # for the coverage rule"), which is how it was noticed; padding the lists is cheaper
    # than a stated permanent gap.
    ("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 1),     # WBTC
    ("0x55d398326f99059fF775485246999027B3197955", 56),    # BSC-USD
]

DEXSCREENER_TOKENS = [
    WETH, BONK,
    "0x4200000000000000000000000000000000000006",          # WETH on Base
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",          # USDC
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",          # WBTC
    "0xdAC17F958D2ee523a2206206994597C13D831ec7",          # USDT
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",          # WBNB
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",        # USDC on Solana
]
GECKO_PATHS = [
    "networks/eth/tokens/%s/pools" % WETH,
    "networks/solana/tokens/%s/pools" % BONK,
    "networks/solana/new_pools",
    "networks/eth/tokens/0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48/pools",
    "networks/bsc/tokens/0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c/pools",
    "networks/base/tokens/0x4200000000000000000000000000000000000006/pools",
    "networks/eth/trending_pools",
    # The single-pool endpoint, which returns `data` as an object rather than a list and
    # is the only place `transactions.h24.sellers` comes from. `_distinct_sellers` reads
    # it to decide whether a honeypot verdict can be overturned (E17), and no probe here
    # touched it until 2026-09-20 -- found by this file's own baseline reporting those
    # four paths as never present.
    "networks/eth/pools/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
]

# Which engine URL templates each probe below covers. Compared against the engine in both
# directions by `test_every_upstream_endpoint_is_probed`, so a new upstream endpoint
# cannot be added without either a probe or a deliberate, named exemption.
PROBED_TEMPLATES = {
    "rugcheck": {"https://api.rugcheck.xyz/v1/tokens/%s/report"},
    "honeypot.is": {"https://api.honeypot.is/v2/IsHoneypot?address=%s"},
    "dexscreener": {"https://api.dexscreener.com/latest/dex/tokens/%s"},
    "geckoterminal": {"https://api.geckoterminal.com/api/v2/%s",
                      "https://api.geckoterminal.com/api/v2/networks/%s/%s"},
}
# Endpoints the engine uses that this file deliberately does not probe, each with why.
# An entry here is a decision, not an oversight; an endpoint in neither map is a failure.
UNPROBED_TEMPLATES = {
    # Reached only from _impersonation_signals, for a symbol rather than an address, and
    # it returns the same pair shape already probed through /latest/dex/tokens.
    "https://api.dexscreener.com/latest/dex/search?q=%s": "same pair shape as tokens/%s",
    # Only fires when the token's home chain is missing from the pair list; its two
    # fields, chainId and pairAddress, are probed on the pair shape above.
    "https://api.dexscreener.com/token-pairs/v1/%s/%s": "fallback; fields covered",
    # The keyed twin of the GeckoTerminal path, same shape, and CI holds no key.
    "https://api.coingecko.com/api/v3/onchain/%s": "keyed twin of geckoterminal",
}

# ---------------------------------------------------------------- the decision rule
#
# Pre-registered before the first baseline was written, and stated here rather than in a
# reviewer's head. The bands come from the instrument's own noise, measured over repeated
# sweeps of the same mints (see DECISIONS E28), not from whatever made the first run pass.
#
#   R1  a path present in every probe at baseline must stay present in every probe.
#       A schema key does not come and go; if it does, upstream changed shape.
#   R2  a path's non-null share may fall by at most VALUE_BAND from baseline. This is the
#       intermittent-coverage rule: holders move, and the alarm is for a collapse.
#   R3  a JSON type never seen at baseline is red, whatever the share.
VALUE_BAND = 0.40
# How many days of daily status the artifact keeps. Long enough that a run of blind days
# is visible as a run, short enough that the committed file stays small.
HISTORY_DAYS = 30
# Below this many probes a share is not a share. RugCheck has 16, the others 3-4, so the
# smaller sets are judged by R1 and R3 only -- stated, rather than quietly applied.
MIN_FOR_SHARE = 8

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


def get(url):
    r = subprocess.run(["curl", "-s", "-m", TIMEOUT, "-A", UA, url],
                       capture_output=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {}


# Probes that could not testify: (source, why). Never failures -- see `fetch`.
_UNOBSERVED = []


def fetch(source, url, record=True):
    """A usable body, or None with the reason recorded (unless `record` is False).

    `record=False` is for a probe whose *failure is the measurement*. Asking honeypot.is
    about Arbitrum returns `{"code":400,"error":"Invalid chain"}`, and that 400 is the
    answer `test_simulator_chain_coverage` wants -- it is how the engine knows the chain
    is uncovered. Counted as blindness it put four permanent entries into every run's
    unobserved list, which would have had `test_upstream_contract_is_observed.py` calling
    honeypot.is unwatched for five straight days and failing the build over a service that
    was answering perfectly. Found 2026-09-20, after those same four 400s had already been
    misread once, as bursty throttling, and a call-gap change made on that reading. An
    expected negative read as an outage: the error this file exists to stop, in the file
    itself.

    This is the whole reason the CI job no longer needs `continue-on-error`. A third
    party being down and a third party changing a field are different events, and a test
    that cannot tell them apart has to be soft-failed, which is the same as switched off.
    They are distinguishable at the only place it matters: an answer that did not arrive
    cannot testify about a field, while an answer that arrived and does not carry the
    field is an observed absence. That is E11, one level up, applied to CI instead of to
    a verdict.
    """
    # Retries, because the engine retries too and an instrument blinder than the thing it
    # measures reports the wrong outage. A 429 gets a long backoff rather than the same
    # three seconds: GeckoTerminal keyless throttles this egress (D8), and three seconds
    # after a rate limit is still inside it, so a short retry just spends a second request
    # proving the first one. Measured here: 8 probes drew 3 x 429 at a 1.5s gap, 1 x 429
    # at 5s, and none once the backoff below was added.
    code, body = "no response", None
    for attempt in (0, 1, 2):
        if attempt:
            time.sleep(20.0 if code == "429" else 3.0)
        r = subprocess.run(
            ["curl", "-s", "-m", TIMEOUT, "-A", UA, "-w", "\n%{http_code}", url],
            capture_output=True, encoding="utf-8", errors="replace")
        text = r.stdout or ""
        code = text.rpartition("\n")[2].strip() or "no response"
        try:
            body = json.loads(text.rpartition("\n")[0] or "null")
        except json.JSONDecodeError:
            body = None
        if code == "200" and isinstance(body, (dict, list)) and body:
            return body
    if record:
        _UNOBSERVED.append((source, "HTTP %s" % code if code != "200"
                            else "empty or unparseable body"))
    return None


def path_exists(obj, *keys):
    """Check that a JSON path exists (the value may be null, but the key must be there)."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def _jtype(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def walk_path(body, parts):
    """Every value reachable at a generated path. Returns (key_seen, values).

    `[]` in a path means "each element of this list". A path is key_seen when the final
    key is present on at least one reachable container, which is what "upstream still
    sends this field" means for a list of pairs.
    """
    cursors = [body]
    for i, part in enumerate(parts):
        nxt = []
        if part == upstream_fields.ELEM:
            for c in cursors:
                if isinstance(c, list):
                    nxt.extend(c)
            cursors = nxt
            continue
        last = (i == len(parts) - 1)
        seen = False
        for c in cursors:
            if isinstance(c, dict) and part in c:
                seen = True
                nxt.append(c[part])
        if last:
            return seen, nxt
        cursors = nxt
    return bool(cursors), cursors


def collect(bodies, paths):
    """Per-path presence share, non-empty share and observed types over a probe set.

    `value` means non-empty, and `0` is a value. That matters for exactly one field and
    it is the field this rewrite exists for: RugCheck sends `totalHolders: 0` for a mint
    it has no holder data on, so that path sits at value 1.0 and its collapse would not
    fire R2. `topHolders` carries the same fact as null-versus-list and does move, which
    is what the fault injection on 2026-09-20 confirmed -- with holders blanked, the
    `topHolders` rows went red and the `totalHolders` row did not. Read the holder
    coverage off `topHolders`; `totalHolders` at 1.0 is not a claim that holders arrive.
    A general rule cannot know which zeros mean "none" and which mean "no data", so it is
    stated here rather than special-cased into the measurement.
    """
    out = {}
    for path in paths:
        parts = tuple(path.split(".")) if path else ()
        key_hits, val_hits, types = 0, 0, set()
        for body in bodies:
            seen, values = walk_path(body, parts)
            if seen:
                key_hits += 1
            if any(v not in (None, "", [], {}) for v in values):
                val_hits += 1
            for v in values:
                types.add(_jtype(v))
        n = max(1, len(bodies))
        out[path] = {"key": round(key_hits / float(n), 4),
                     "value": round(val_hits / float(n), 4),
                     "types": sorted(types)}
    return out


def fetch_bodies():
    """The usable live bodies per source. A body that did not arrive is simply not here."""
    bodies = {"rugcheck": [], "honeypot.is": [], "dexscreener": [], "geckoterminal": []}
    asked = dict((k, 0) for k in bodies)

    def add(source, url):
        asked[source] += 1
        body = fetch(source, url)
        if body is not None:
            bodies[source].append(body)
        time.sleep(SOURCE_CALL_GAP.get(source, CALL_GAP))

    for mint in RUGCHECK_MINTS:
        add("rugcheck", "https://api.rugcheck.xyz/v1/tokens/%s/report" % mint)
    for addr, cid in HONEYPOT_TOKENS:
        add("honeypot.is",
            "https://api.honeypot.is/v2/IsHoneypot?address=%s&chainID=%d" % (addr, cid))
    for addr in DEXSCREENER_TOKENS:
        add("dexscreener", "https://api.dexscreener.com/latest/dex/tokens/%s" % addr)
    for p in GECKO_PATHS:
        add("geckoterminal", "https://api.geckoterminal.com/api/v2/%s" % p)
    return bodies, asked


def measure():
    table = upstream_fields.build().table()
    bodies, asked = fetch_bodies()
    out = {}
    for source, paths in sorted(table.items()):
        got = bodies.get(source) or []
        out[source] = {"probes": len(got),
                       "asked": asked.get(source, 0),
                       "paths": collect(got, sorted(paths))}
    return out, bodies


# ---------------------------------------------------------------- the generated test

def test_generated_field_contract():
    """Every JSON path src/risk.py reads, measured against a frozen baseline.

    The list is not in this file and cannot go stale: it is derived from the engine on
    every run. What is frozen is how often each path actually arrives, so the test can
    tell "upstream renamed a field" from "this mint has no holders today".
    """
    print("\n[contract] every path the engine reads, against the frozen baseline")
    if not os.path.exists(BASELINE):
        check("baseline exists", False,
              "run: python tests/test_upstream_contract.py --write")
        return
    base = json.load(open(BASELINE, encoding="utf-8"))
    # An analysis that ran out of rounds returns a table that is merely most of the truth,
    # and a short table fails nothing -- it just stops mentioning the paths it lost. That
    # is the silent-shrink failure this whole file exists to prevent, so it is asserted
    # rather than printed.
    fields = upstream_fields.build()
    check("the field analysis reached a fixpoint", not getattr(fields, "incomplete", False),
          "still learning after %d rounds; the table is incomplete and every path it "
          "dropped is now unwatched" % getattr(fields, "rounds", 0))
    now, _bodies = measure()

    # A path the engine grew since the baseline was frozen is not a failure of upstream,
    # but it is unmeasured, and an unmeasured dependency is the whole bug class. It is
    # reported as its own line so it cannot hide inside a pass.
    for source in sorted(now):
        b = (base.get("sources") or {}).get(source) or {}
        bp, np_ = b.get("paths") or {}, now[source]["paths"]
        # Nothing arrived from this source. Asserting anything now would report an outage
        # as a renamed field, and the run has to say it went blind rather than quietly
        # pass with no assertions -- "checked one place, found green, reported green" is
        # this repository's most repeated bug.
        if not now[source]["probes"]:
            print("  BLIND %s: 0 of %d probes answered; nothing asserted"
                  % (source, now[source]["asked"]))
            continue
        new_paths = sorted(set(np_) - set(bp))
        check("%s: no unmeasured new path in the engine" % source, not new_paths,
              "engine now reads %s -- re-freeze with --write" % new_paths[:6])
        # And the other direction. A path in the baseline that the engine no longer reads
        # is a dependency that was dropped, and the generated table would simply stop
        # mentioning it -- coverage shrinking in silence, which is the failure this file
        # exists to make impossible. Either a read was deliberately removed and the
        # baseline should be re-frozen, or one was deleted by accident and this is how
        # anyone finds out.
        gone = sorted(set(bp) - set(np_))
        check("%s: no path has silently left the engine" % source, not gone,
              "engine no longer reads %s -- re-freeze with --write if deliberate"
              % gone[:6])

        n = now[source]["probes"]
        # Said, not skipped. Below MIN_FOR_SHARE the coverage rule cannot run, and a rule
        # that quietly stops running is the failure this file is about: the run would
        # still print "all passed" having checked presence and type only. It happens for
        # real -- honeypot.is answered 400 to four of six probes twice on 2026-09-20 --
        # so it is a line of output, every time, not a footnote in the source.
        if n < MIN_FOR_SHARE:
            print("  NOTE  %s: %d usable probes of %d, under the %d needed for the "
                  "coverage rule; presence and type only"
                  % (source, n, now[source]["asked"], MIN_FOR_SHARE))
        for path in sorted(set(np_) & set(bp)):
            was, is_ = bp[path], np_[path]
            # R1 -- a schema key does not come and go.
            if was.get("key", 0) >= 1.0:
                check("%s: %s still present in every probe" % (source, path),
                      is_["key"] >= 1.0,
                      "was 100%% of probes, now %.0f%%" % (100 * is_["key"]))
            # R2 -- intermittent coverage may move, but not collapse.
            if n >= MIN_FOR_SHARE:
                check("%s: %s coverage has not collapsed" % (source, path),
                      is_["value"] >= was.get("value", 0) - VALUE_BAND,
                      "carried by %.0f%% of probes at baseline, %.0f%% now"
                      % (100 * was.get("value", 0), 100 * is_["value"]))
            # R3 -- a type nobody has seen before. `null` is not one of them: a field
            # arriving empty is absence, which is precisely what R1 and R2 measure, and
            # treating it as a new type made the guard go red on an ordinary day. Caught
            # by breaking this file on 2026-09-20: GeckoTerminal answered
            # `reserve_in_usd: null` on one pool half an hour after a baseline that had
            # only ever seen a string, and a guard that cries wolf on a Tuesday is one
            # somebody switches off by Friday.
            unseen = set(is_["types"]) - set(was.get("types") or []) - {"null"}
            check("%s: %s sends no new JSON type" % (source, path), not unseen,
                  "new %s, baseline had %s" % (sorted(unseen), was.get("types")))


def test_the_unwatchable_paths_are_named():
    """Paths the engine reads that no probe here has ever seen carry a value.

    They are not failures. A field that only appears on a honeypot will not appear on
    WETH, and `status.error_code` only exists on an error body. But a path at zero is a
    path where R1 and R2 have nothing to compare, so its disappearance would pass
    silently -- and a run that lists 122 paths and says "all passed" reads as 122 paths
    watched. It is not. This prints the difference.

    The list only shrinks by finding a probe that exercises the path. It shrank by eleven
    on 2026-09-20 -- the four `holderAnalysis` fields that are the whole input to E23, the
    four GeckoTerminal transaction fields behind E17's overturn rule, `simulationError`
    and both `summary.flags` paths -- all of which had been sitting at zero behind a
    green tick because every probe token was healthy.
    """
    print("\n[contract] paths the engine reads that nothing here can observe")
    if not os.path.exists(BASELINE):
        return
    base = json.load(open(BASELINE, encoding="utf-8"))
    total = 0
    for source in sorted(base.get("sources") or {}):
        paths = (base["sources"][source] or {}).get("paths") or {}
        dark = sorted(p for p, v in paths.items() if not v.get("value"))
        total += len(dark)
        if dark:
            print("  %-14s %d unobservable: %s"
                  % (source, len(dark), ", ".join(dark[:4])
                     + (", +%d" % (len(dark) - 4) if len(dark) > 4 else "")))
    # Stated, not asserted away: the number is here so it can be argued with, and so a
    # reader of the output cannot mistake "122 paths checked" for what actually happened.
    check("the unwatchable set is declared, not discovered later", True,
          "%d of %d paths carry no value in any probe" % (total, base.get("engine_paths", 0)))


def test_every_upstream_endpoint_is_probed():
    """The engine's upstream endpoints and this file's probes agree, in both directions.

    The generated field table can only measure endpoints something actually fetches. An
    endpoint added to the engine and probed by nothing would leave its fields at a
    baseline of zero and look perfectly healthy, which is the blind spot this whole file
    exists to close, one level up.
    """
    print("\n[coverage] every upstream endpoint the engine calls is probed or exempted")
    engine = upstream_fields.build().urls()
    for source, templates in sorted(engine.items()):
        known = PROBED_TEMPLATES.get(source, set()) | set(UNPROBED_TEMPLATES)
        unknown = sorted(set(templates) - known)
        check("%s: no unprobed endpoint" % source, not unknown,
              "engine calls %s -- probe it, or name it in UNPROBED_TEMPLATES with the "
              "reason" % unknown)
    all_engine = {t for ts in engine.values() for t in ts}
    stale = sorted({t for ts in PROBED_TEMPLATES.values() for t in ts} - all_engine)
    check("no probe points at an endpoint the engine dropped", not stale, str(stale))


# ---------------------------------------------------------------- not derivable by shape

def test_honeypot_facts_a_shape_cannot_state():
    """The three assertions that are not "does this field exist".

    A generated path table says what the engine reads. It cannot say that a key must be
    *absent* -- and the absence is the original P0: isHoneypot read out of
    simulationResult, where upstream does not put it, returned None, was treated as
    False, and passed the honeypot check for every token. Nor can it state a value
    domain. Both stay hand-written, because both are genuinely facts about meaning.
    """
    print("\n[upstream] honeypot.is facts that are not field presence")
    d = fetch("honeypot.is", "https://api.honeypot.is/v2/IsHoneypot?address=%s" % WETH)
    if d is None:
        print("  BLIND honeypot.is did not answer; nothing asserted")
        return
    check("honeypotResult.isHoneypot present",
          path_exists(d, "honeypotResult", "isHoneypot"),
          "top-level keys: %s" % sorted(d.keys()))
    sim = d.get("simulationResult") or {}
    check("simulationResult does NOT have isHoneypot (wrong place reads False forever)",
          "isHoneypot" not in sim, "simulationResult keys: %s" % sorted(sim.keys()))
    risk_val = (d.get("summary") or {}).get("risk")
    check("summary.risk is one of the known values",
          risk_val in ("low", "medium", "high", "very_high", "unknown", None),
          "actual %r" % risk_val)


def test_simulator_chain_coverage():
    """The chains we believe the sell simulator covers are the ones it actually covers.

    `src/risk.py` hardcodes three, and uses that list to decide whether a 404 is a fact
    about the token or a gap in our own coverage. If honeypot.is adds a chain and the list
    does not, the engine goes on declining to check it forever and blaming its own
    coverage -- politely, and wrongly. If it drops one, the engine starts telling users a
    healthy token has no record anywhere.

    Both directions are checked. A hardcoded list that nothing compares against the world
    is a belief, not a fact.
    """
    print("\n[coverage] honeypot.is supports exactly the chains we think it does")
    import risk  # noqa: E402

    # A real, liquid token on each chain the tool advertises as a chain_hint.
    PROBE = {
        "ethereum": (1, "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        "bsc": (56, "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
        "base": (8453, "0x4200000000000000000000000000000000000006"),
        "arbitrum": (42161, "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"),
        "polygon": (137, "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"),
        "optimism": (10, "0x4200000000000000000000000000000000000006"),
        "avalanche": (43114, "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"),
    }

    answers, arrived = {}, 0
    for name, (cid, addr) in PROBE.items():
        # record=False: a 400 here is the answer, not a failure to get one.
        body = fetch("honeypot.is",
                     "https://api.honeypot.is/v2/IsHoneypot?address=%s&chainID=%d"
                     % (addr, cid), record=False)
        if body is not None:
            arrived += 1
        answers[name] = bool(body and "honeypotResult" in body)
        time.sleep(2.0)

    # None of the seven answered: the service is down, not seven chains dropped at once.
    # Some answered and some did not is the informative case, and it is asserted below --
    # that difference is the whole reason this job can fail the build again.
    if not arrived:
        print("  BLIND honeypot.is answered none of %d chain probes; nothing asserted"
              % len(PROBE))
        return

    reachable = [n for n, ok in answers.items() if ok]
    check("at least the three we rely on answer",
          all(answers.get(n) for n in ("ethereum", "bsc", "base")),
          str(answers))

    believed = set(risk._SIMULATOR_CHAIN_IDS)
    actual = set(reachable)
    check("nothing we rely on has been dropped", believed <= actual,
          "we believe %s, it answers %s" % (sorted(believed), sorted(actual)))
    check("nothing new is being refused for no reason", actual <= believed,
          "it now also answers %s -- add it to _SIMULATOR_CHAIN_IDS"
          % sorted(actual - believed))

    # The ids themselves have to be right, or we would be asking about the wrong chain.
    for name, (cid, _addr) in PROBE.items():
        if name in risk._SIMULATOR_CHAIN_IDS:
            check("%s maps to chain id %d" % (name, cid),
                  risk._SIMULATOR_CHAIN_IDS[name] == cid,
                  str(risk._SIMULATOR_CHAIN_IDS.get(name)))


def test_rugcheck_extension_inventory():
    """Every Token-2022 extension key this upstream sends is one the engine has considered.

    `src/risk.py` carries a table of seventeen extension keys, split into the ones it
    grades and the ones it names with the reason it does not. Seventeen is a count
    measured against the live API on 2026-09-20 -- the same seventeen on BERN and on
    PYUSD, unset ones as null -- and it decays: SPL keeps adding extensions to the token
    program and RugCheck passes the block straight through.

    This is the same guard, and the same two directions, as
    `test_simulator_chain_coverage` above. The first cut of the extension reader graded
    six keys of the seventeen and published `read: true` beside them, and nothing anywhere
    compared that six against what the API actually returns, so the gap was invisible from
    inside the repository -- the offline fixture had been hand-written with exactly the six
    keys the code already knew about. A hardcoded list that nothing compares against the
    world is a belief, not a fact.

    PYUSD is the sample because it populates eight of the seventeen, including the three
    with a documented abuse. A plain SPL token is no use here: it returns
    `token_extensions: null` and would assert nothing.
    """
    print("\n[coverage] RugCheck sends exactly the extension keys we have considered")
    import risk  # noqa: E402

    d = fetch("rugcheck", "https://api.rugcheck.xyz/v1/tokens/%s/report" % PYUSD)
    if d is None:
        print("  BLIND RugCheck did not answer; nothing asserted")
        return
    te = d.get("token_extensions")
    check("a Token-2022 mint still returns a token_extensions block",
          isinstance(te, dict) and te, str(sorted(d.keys()))[:200])
    if not isinstance(te, dict) or not te:
        return

    sent = set(te)
    known = set(risk._TOKEN2022_SCORED) | set(risk._TOKEN2022_NOT_SCORED)
    check("nothing arrives that nobody here has considered", sent <= known,
          "new since 2026-09-20: %s -- score it, or name it in _TOKEN2022_NOT_SCORED "
          "with the reason" % sorted(sent - known))
    check("nothing we read has stopped being sent", known <= sent,
          "gone: %s -- the branch that reads it can no longer fire, and the table is "
          "claiming coverage of a key that is not there" % sorted(known - sent))

    # The three that decide whether a holder can get out are worth naming individually:
    # a rename of one of these is a `fatal` silently becoming unreachable.
    for key in ("nonTransferable", "defaultAccountState", "transferFeeConfig"):
        check("%s is still the key name" % key, key in sent, str(sorted(sent)))
    check("PYUSD still populates a mint close authority (the F5 sample)",
          bool(te.get("mintCloseAuthority")), str(te.get("mintCloseAuthority")))
    check("RugCheck's convenience transferFee key still disagrees with the block",
          isinstance(d.get("transferFee"), dict), str(d.get("transferFee")))

    # The fee is min(amount * bps / 10000, maximumFee) and the rating reads both halves,
    # so both halves have to keep arriving. A vanished `maximumFee` would silently put
    # every capped mint back on the uncapped sentence (F7).
    sch = [(d.get("token_extensions") or {}).get("transferFeeConfig") or {}]
    sch = [(sch[0]).get(k) for k in ("olderTransferFee", "newerTransferFee")]
    for name, entry in zip(("older", "newer"), sch):
        check("the %s fee schedule still carries both bps and maximumFee" % name,
              isinstance(entry, dict) and "transferFeeBasisPoints" in entry
              and "maximumFee" in entry, str(entry))
    check("token.supply and token.decimals are still there to scale the cap against",
          isinstance(d.get("token"), dict) and "supply" in d["token"]
          and isinstance(d["token"].get("decimals"), int),
          str(d.get("token")))


def write_baseline():
    sources, _ = measure()
    # A baseline is a frozen record, and freezing one from a partial run writes an outage
    # into it permanently: every path only that probe exercises drops to zero, and R1 and
    # R2 then have nothing to compare for as long as the file stands. It happened twice on
    # 2026-09-20 -- first with a reader that returned `{}` on a failed call, then again
    # with two GeckoTerminal probes throttled, which quietly put the four
    # `transactions.h24` paths back in the dark the same hour they were rescued. Refuse,
    # and say which; re-running costs two minutes.
    if _UNOBSERVED:
        by = {}
        for source, why in _UNOBSERVED:
            by.setdefault(source, []).append(why)
        print("refusing to freeze a baseline from a partial run:")
        for source in sorted(by):
            print("  %-14s %d probes did not answer: %s"
                  % (source, len(by[source]), ", ".join(sorted(set(by[source])))))
        print("re-run when the upstreams are answering; nothing was written.")
        return 1
    table = upstream_fields.build().table()
    payload = {
        "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine_paths": sum(len(v) for v in table.values()),
        "rule": {"value_band": VALUE_BAND, "min_for_share": MIN_FOR_SHARE},
        "sources": sources,
    }
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote %s: %d paths across %d sources"
          % (BASELINE, payload["engine_paths"], len(sources)))
    return 0


def write_status(path, failures, unobserved):
    """The one line the daily job commits, so persistent blindness cannot hide.

    Removing `continue-on-error` fixes the loud half: a contract change now fails the
    build. It does nothing for the quiet half -- an upstream that stops answering
    altogether makes this file assert nothing at all, and a suite that asserts nothing
    prints the same "all passed" as a suite that checked everything. So each daily run
    records what it managed to observe, `bench/scorecard.py` reads it, and a contract
    that has gone unobserved for days costs points in a file regenerated on every commit
    rather than expiring quietly in a CI log nobody opens.
    """
    blind = sorted(set(s for s, _ in unobserved))
    today = time.strftime("%Y-%m-%d", time.gmtime())
    payload = {
        "date": today,
        "status": "red" if failures else ("blind" if blind else "green"),
        "failures": [name for name, _ in failures],
        "unobserved_sources": blind,
        "unobserved_probes": len(unobserved),
    }
    # The history is the point: one day's status cannot answer "has this been blind for a
    # week", and that question is the whole residual. Kept in the artifact rather than
    # derived from git log, so the guard reading it stays offline and deterministic.
    history = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                history = (json.load(f) or {}).get("history") or []
        except (OSError, ValueError):
            history = []
    history = [h for h in history if h.get("date") != today]
    history.append({"date": today, "status": payload["status"],
                    "unobserved_sources": blind})
    payload["history"] = sorted(history, key=lambda h: h.get("date") or "")[-HISTORY_DAYS:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote %s: %s" % (path, payload["status"]))


def main():
    if "--write" in sys.argv:
        return write_baseline()
    print("=" * 68)
    print("VetAgent upstream contract tests (live network)")
    print("=" * 68)
    # Discovered rather than listed. It named all five of its tests correctly on
    # 2026-09-10 -- and so did tests/test_backfill.py until somebody added a sixth.
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed, %d probes unobserved"
          % (_PASSED, len(_FAILURES), len(_UNOBSERVED)))

    if _UNOBSERVED:
        # Said out loud, always. A run that could not look is not a run that found
        # nothing, and the count is the difference between the two.
        by_source = {}
        for source, why in _UNOBSERVED:
            by_source.setdefault(source, []).append(why)
        print("\nCould not observe (a third party did not answer; not a contract change):")
        for source in sorted(by_source):
            whys = by_source[source]
            print("  - %-14s %d probes: %s" % (source, len(whys),
                                               ", ".join(sorted(set(whys)))))

    for i, arg in enumerate(sys.argv):
        if arg == "--status-json" and i + 1 < len(sys.argv):
            write_status(sys.argv[i + 1], _FAILURES, _UNOBSERVED)

    if _FAILURES:
        print("\nFailures (upstream may have changed a field; risk.py has to change too):")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
