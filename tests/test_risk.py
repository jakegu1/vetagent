"""test_risk.py — offline regression tests.

Driven by real upstream response snapshots (tests/fixtures/), no network, safe in CI.
Every case maps to a **bug that actually shipped**, and exists to stop it coming back.

Run:  python tests/test_risk.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import risk  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Known addresses -> fixture files
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
MATIC = "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
RETAIL = "0xb954d1ba6bb92123609fcfb724c68b810c668feb"   # honeypot.is: very_high
ALIGN = "0x50614cc8e44f7814549c223aa31db9296e58057c"    # honeypot.is: simulation failed
TAXED = "0x1c48955a39952e74ef03a173de52958138cb92ab"    # 4.94% sell tax + closed source
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"   # Solana, clean on RugCheck


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def install_stub(routes, default=None):
    """Swap risk._fetch_json for a lookup table so nothing hits the network.

    routes: [(url substring, return value)]; a value of None means **the fetch failed**.
    """
    async def _stub(url, *a, **kw):
        for frag, payload in routes:
            if frag in url:
                return payload
        return default
    risk._fetch_json = _stub


# ---------------------------------------------------------------- assertion helpers

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


def sig_categories(result):
    return {s["category"]: s["severity"] for s in result["signals"]}


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- test cases

def test_honeypot_key_is_read_from_the_right_object():
    """Regression P0-A: isHoneypot lives on honeypotResult, not simulationResult.

    The old code read simulationResult.isHoneypot, a key that does not exist, so the
    honeypot dimension came back ok for every token.
    """
    print("\n[P0-A] honeypot key path + upstream aggregate verdict")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_retail_veryhigh.json")),
    ])
    r = run(risk.assess(RETAIL, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("very_high token must not be rated low", r["risk_level"] != "low",
          "got %s" % r["risk_level"])
    check("must emit an upstream_risk signal", "upstream_risk" in cats, str(cats))
    check("upstream_risk must be critical",
          cats.get("upstream_risk") == "critical", str(cats.get("upstream_risk")))
    check("closed source must be flagged", cats.get("contract") == "warn", str(cats))
    check("evidence keeps the upstream risk",
          r["evidence"]["honeypot"]["upstream_risk"] == "very_high", "")


def test_simulation_failure_is_fail_closed():
    """Regression P0-A2: on a failed simulation the old code printed 'ok / not a honeypot'.

    align's simulationError is 'HP: BUY_FAILED' — you cannot even buy in, and we called
    it safe.
    """
    print("\n[P0-A2] simulation failure must fail closed")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_align_simfail.json")),
    ])
    r = run(risk.assess(ALIGN, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("no ok honeypot signal allowed", cats.get("honeypot") != "ok", str(cats))
    check("must emit a sellability signal", "sellability" in cats, str(cats))
    # warn, not critical. The regression this test exists for is "we called it safe",
    # and that is guarded by the two checks above and the one below -- not by the
    # severity, which was an implementation detail that happened to get written down.
    #
    # Scored as critical it was 60 points at sellability's weight of 1.0, so any token
    # the simulator could not drive reached "high" on one more warning of any kind.
    # Measured over 558 tokens: 42 such tokens, 29 already rated high, **none**
    # confirmed bad and 33 confirmed good. "We could not check" must not be scored like
    # "we checked and it is bad", in either direction.
    check("sellability is a warning, not a finding",
          cats.get("sellability") == "warn", str(cats))
    check("never rated low", r["risk_level"] != "low", r["risk_level"])
    check("and an unverifiable simulation alone cannot reach high",
          r["risk_level"] != "high", "%s %s" % (r["risk_level"], cats))
    check("data_gaps must be recorded", bool(r["evidence"].get("data_gaps")), "")


def test_tax_and_closed_source():
    print("\n[P0-A3] transfer tax + closed source")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_test_hightax.json")),
    ])
    r = run(risk.assess(TAXED, chain_hint="ethereum"))
    cats = sig_categories(r)
    check("4.94% sell tax is not an extreme tax",
          cats.get("sell_tax") != "critical", str(cats))
    check("closed source must warn", cats.get("contract") == "warn", str(cats))
    check("upstream high must show up", cats.get("upstream_risk") == "warn", str(cats))
    check("must not be rated low", r["risk_level"] != "low", r["risk_level"])


def test_liquidity_picks_the_right_pool():
    """Regression P0-C: liquidity() never called _pick_best and priced USDC at $0.00097."""
    print("\n[P0-C] liquidity() pool selection")
    install_stub([("dexscreener", _load("ds_usdc.json"))])
    r = run(risk.liquidity(USDC, chain_hint="ethereum"))
    check("status is ok", r.get("status") == "ok", str(r.get("status")))
    check("must pick ethereum, not pulsechain",
          r.get("best_pair_chain") == "ethereum", str(r.get("best_pair_chain")))
    check("USDC price must be close to $1", 0.9 <= r.get("price_usd", 0) <= 1.1,
          "got %s" % r.get("price_usd"))

    # Without chain_hint, the median-price filter must still block mispriced fork pools
    r2 = run(risk.liquidity(USDC))
    check("price still sane without chain_hint", 0.5 <= r2.get("price_usd", 0) <= 2.0,
          "got %s" % r2.get("price_usd"))


def test_address_validation_on_every_entrypoint():
    """Regression P0-C2: liquidity() had no address validation at all."""
    print("\n[P0-C2] address validation on every entrypoint")
    install_stub([])
    for fn, label in ((risk.assess, "assess"), (risk.liquidity, "liquidity")):
        for bad in ("0xdeadbeef", "", "   ", "not-an-address", "0x" + "z" * 40):
            try:
                run(fn(bad))
                check("%s(%r) must raise" % (label, bad), False, "nothing raised")
            except ValueError:
                check("%s(%r) raises ValueError" % (label, bad), True)
            except Exception as e:
                check("%s(%r) raises ValueError" % (label, bad), False, type(e).__name__)


def test_pair_age_works_on_integer_timestamps():
    """Regression P0-D: DexScreener's pairCreatedAt is an integer in milliseconds.

    The old code called .replace() on it; the AttributeError got swallowed by an except,
    so the pair-age signal never fired on our primary data source.
    """
    print("\n[P0-D] pair age (integer milliseconds)")
    check("millisecond integer parses",
          risk._pair_created_ms(1589841515000) == 1589841515000.0, "")
    check("second integer promoted to milliseconds",
          risk._pair_created_ms(1589841515) == 1589841515000.0, "")
    check("ISO string parses",
          risk._pair_created_ms("2020-05-19T00:00:00Z") is not None, "")
    check("None returns None", risk._pair_created_ms(None) is None, "")
    check("bool is not treated as a number", risk._pair_created_ms(True) is None, "")
    check("garbage string returns None", risk._pair_created_ms("not-a-date") is None, "")

    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_matic.json")),
    ])
    r = run(risk.assess(MATIC, chain_hint="ethereum"))
    check("pair age must be computed", r["evidence"].get("pair_age_days", 0) > 1000,
          str(r["evidence"].get("pair_age_days")))
    check("must emit a freshness signal", "freshness" in sig_categories(r),
          str(sig_categories(r)))


def test_engine_output_is_english():
    """Regression: the engine's **output** used to be in Chinese.

    The tool descriptions had been translated, but what the agent actually relays to the
    end user is signals and recommendation. A Chinese verdict on an English page is
    merely ugly; an agent reading Chinese signals to an English user is broken.

    Check CJK only, not every non-ASCII character — dashes and curly quotes are valid
    typography, and a test that goes red over punctuation gets switched off eventually.
    """
    print("\n[i18n] engine output must be English")

    def cjk(text):
        return [c for c in str(text) if 0x4E00 <= ord(c) <= 0x9FFF]

    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_retail_veryhigh.json")),
    ])
    r = run(risk.assess(RETAIL, chain_hint="ethereum"))
    bad = []
    for s in r["signals"]:
        if cjk(s["name"]) or cjk(s["message"]):
            bad.append(s["name"])
    check("no Chinese in signals", not bad, str(bad))
    check("no Chinese in recommendation", not cjk(r["recommendation"]),
          r["recommendation"][:40])

    # Failure-path copy gets relayed too, so check it as well
    install_stub([], default=None)
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    gaps = (r2["evidence"].get("data_gaps") or [])
    check("no Chinese in data_gaps",
          not any(cjk(g.get("reason", "")) for g in gaps), str(gaps)[:60])
    check("no Chinese in failure-path recommendation",
          not cjk(r2["recommendation"]), r2["recommendation"][:40])

    try:
        risk.validate_address("0xdeadbeef")
    except ValueError as e:
        check("no Chinese in error messages", not cjk(str(e)), str(e)[:50])


def test_benchmark_oracle_stays_out_of_the_engine():
    """DECISIONS B2: GoPlus is the benchmark's held-out oracle. The moment the engine
    reads it, the benchmark is worthless.

    This used to be one sentence in a doc. Conventions get broken with the best of
    intentions — "just add GoPlus and we get EVM holder concentration" is a perfectly
    reasonable idea, and whoever has it is unlikely to read the benchmark methodology
    first. So make it something that turns the build red.

    If we do want GoPlus one day, the order is: give the benchmark a new independent
    labelling source, then change the engine, then delete this test and record why in
    DECISIONS.md.
    """
    print("\n[DECISIONS B2] held-out oracle must stay out of the engine")
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
    forbidden = ("gopluslabs", "goplus")
    offenders = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(src_dir, fn), encoding="utf-8") as f:
            body = f.read().lower()
        for token in forbidden:
            if token in body:
                offenders.append("%s contains %r" % (fn, token))
    check("no GoPlus anywhere in src/", not offenders, "; ".join(offenders))


def test_upstream_failure_yields_unknown():
    """Hard rule: no data on a critical dimension -> unknown, never low."""
    print("\n[hard rule] upstream failure must yield unknown")
    # Every data source fails
    install_stub([], default=None)
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("total failure must be unknown", r["risk_level"] == "unknown", r["risk_level"])
    check("confidence must be low", r["confidence"] == "low", r["confidence"])
    # This used to grep for two Chinese words ("test the waters", "open a position").
    # Once the output was translated those words were gone and the test passed
    # vacuously — **passing because the thing it checked no longer exists** is the most
    # useless kind of test. Now it checks the English position/investment wording.
    rec = r["recommendation"].lower()
    banned = ("position size", "buy a small", "small position", "invest",
              "we recommend buying", "safe to buy")
    hit = [w for w in banned if w in rec]
    check("no position sizing or investment advice in the recommendation", not hit,
          "hit: %s | %s" % (hit, r["recommendation"]))

    # Only honeypot fails: sellability is unknown, so low is still not allowed
    install_stub([("dexscreener", _load("ds_weth.json")), ("honeypot.is", None)])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("no low when sellability is missing", r2["risk_level"] != "low", r2["risk_level"])
    check("data_gaps must be recorded", bool(r2["evidence"].get("data_gaps")), "")


def test_no_trace_is_high_but_our_outage_is_unknown():
    """Two situations empty every critical dimension, and they mean opposite things.

    If our upstreams failed, the token may be perfectly fine and we simply cannot see;
    rating it high would smear legitimate tokens for our own outage. If the token has no
    trace anywhere -- no pool prices it, nothing can be simulated -- that is not a
    question mark, because every legitimate token clears at least one of those.

    This distinction was missed on the first attempt: the escalation counted how many
    critical dimensions were empty and ignored why, which turned an outage on our side
    into a high-risk verdict about someone else's token. The existing fail-closed test
    caught it.
    """
    print("\n[fail-closed] no trace vs our outage")

    # Our side is down: every fetch returns None.
    install_stub([], default=None)
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("our outage stays unknown", r["risk_level"] == "unknown", r["risk_level"])

    # The token has no trace: sources answer, they just have nothing on it.
    install_stub([("dexscreener", {"pairs": []}),
                  ("geckoterminal", {"data": []}),
                  ("honeypot.is", {"summary": {}, "simulationSuccess": False,
                                   "simulationError": "no pair to simulate against"})])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("no verifiable trace is high", r2["risk_level"] == "high",
          "%s %s" % (r2["risk_level"], sig_categories(r2)))
    check("and says why", any("can be verified" in s["name"] for s in r2["signals"]),
          str([s["name"] for s in r2["signals"]]))


def test_chain_activity_overrules_a_honeypot_verdict():
    """A simulator saying "you cannot sell" loses to a chain showing thousands just did.

    Measured: honeypot.is returned isHoneypot=true, simulationSuccess=true and sellTax=0
    for tokens with tens of thousands of completed sells in 24h. AKE had 59,031. Thirteen
    of twenty benchmark false positives traced to relaying that flag unexamined.

    The override is deliberately narrow. Real honeypots do let a whitelisted address or
    two out, so a couple of sells prove nothing; the test is volume plus a sell/buy ratio
    that a working trap cannot produce. And the verdict is downgraded, not dropped —
    something is wrong with a token its upstream flags, we just know it is not that
    nobody can exit.
    """
    print("\n[adjudication] chain activity vs a honeypot flag")

    hp_flagged = _load("hp_matic.json")
    hp_flagged["honeypotResult"] = {"isHoneypot": True}
    hp_flagged["simulationSuccess"] = True

    def pairs_with(buys, sells):
        d = json.loads(json.dumps(_load("ds_matic.json")))
        for p in d["pairs"]:
            p["txns"] = {"h24": {"buys": buys, "sells": sells}}
        return d

    # Thousands of completed sells: the flag is contradicted, not obeyed.
    install_stub([("dexscreener", pairs_with(4134, 4228)), ("honeypot.is", hp_flagged)])
    r = run(risk.assess(MATIC, chain_hint="ethereum"))
    hp_sigs = [x for x in r["signals"] if x["category"] == "honeypot"]
    check("active selling downgrades the fatal verdict",
          hp_sigs and hp_sigs[0]["severity"] != "fatal",
          str([(x["severity"], x["name"]) for x in hp_sigs]))
    check("not rated high on that basis alone", r["risk_level"] != "high",
          "%s %s" % (r["risk_level"], sig_categories(r)))
    check("the contradiction is recorded as evidence",
          bool((r["evidence"].get("honeypot") or {}).get("contradicted_by_chain")),
          str(r["evidence"].get("honeypot", {}).keys()))

    # Buys but almost no sells: that is the shape of a real trap. Flag stands.
    install_stub([("dexscreener", pairs_with(900, 3)), ("honeypot.is", hp_flagged)])
    r2 = run(risk.assess(MATIC, chain_hint="ethereum"))
    hp2 = [x for x in r2["signals"] if x["category"] == "honeypot"]
    check("buys without sells keeps the fatal verdict",
          hp2 and hp2[0]["severity"] == "fatal",
          str([(x["severity"], x["name"]) for x in hp2]))
    check("and that still reads high", r2["risk_level"] == "high", r2["risk_level"])

    # Sells happened, but the pool has since been drained. One benchmark token showed
    # 458 completed sells against $0 of liquidity: people got out and the pool was
    # emptied behind them. Past sells say nothing about exiting now.
    def drained(buys, sells):
        d = json.loads(json.dumps(_load("ds_matic.json")))
        for p in d["pairs"]:
            p["txns"] = {"h24": {"buys": buys, "sells": sells}}
            p["liquidity"] = {"usd": 0}
        return d

    install_stub([("dexscreener", drained(809, 458)), ("honeypot.is", hp_flagged)])
    r4 = run(risk.assess(MATIC, chain_hint="ethereum"))
    hp4 = [x for x in r4["signals"] if x["category"] == "honeypot"]
    check("a drained pool cannot vouch for past sells",
          hp4 and hp4[0]["severity"] == "fatal",
          str([(x["severity"], x["name"]) for x in hp4]))

    # No transaction data at all: nothing to contradict with, so the flag stands.
    install_stub([("dexscreener", pairs_with(None, None)), ("honeypot.is", hp_flagged)])
    r3 = run(risk.assess(MATIC, chain_hint="ethereum"))
    hp3 = [x for x in r3["signals"] if x["category"] == "honeypot"]
    check("missing txn data does not excuse the token",
          hp3 and hp3[0]["severity"] == "fatal",
          str([(x["severity"], x["name"]) for x in hp3]))


def test_impersonation_is_comparative_not_absolute():
    """Being dwarfed under a shared ticker is the signal; sharing one is not.

    The loss an agent is most likely to take is buying the wrong contract with the right
    name. No contract scan catches it: the impostor's code is often perfectly ordinary,
    because what is dishonest is the identity, not the bytecode.

    Verified live before this test was written. DexScreener lists 29 contracts under the
    ticker PEPE. The real one holds $27.1M and comes back low, carrying only an info note
    that the ticker is shared. A namesake holding $3,394 -- 7,982x less -- comes back high
    on "almost certainly not the token you meant". Both readings have to hold, or the
    check is either useless or unusable.
    """
    print("\n[impersonation] dwarfed under a shared ticker")

    def market(mine_liq, rival_liq, rivals=1):
        """A DexScreener response where our token and N namesakes share a ticker."""
        me = {"chainId": "ethereum", "dexId": "uniswap",
              "baseToken": {"address": WETH, "symbol": "TKN"},
              "quoteToken": {"address": "0xq"}, "priceUsd": "1.0",
              "liquidity": {"usd": mine_liq}, "volume": {"h24": mine_liq},
              "txns": {"h24": {"buys": 100, "sells": 100}},
              "pairCreatedAt": 1589841515000}
        others = [{"chainId": "ethereum", "dexId": "uniswap",
                   "baseToken": {"address": "0x%040d" % (i + 1), "symbol": "TKN"},
                   "quoteToken": {"address": "0xq"}, "priceUsd": "1.0",
                   "liquidity": {"usd": rival_liq}, "volume": {"h24": rival_liq},
                   "pairCreatedAt": 1589841515000}
                  for i in range(rivals)]
        return {"pairs": [me] + others}

    def run_with(mine, rival, rivals=1):
        # The token lookup and the ticker search are different DexScreener paths, so the
        # stub has to answer them separately or the search sees our own pair back.
        install_stub([("dex/tokens", market(mine, rival, 0)),
                      ("dex/search", market(mine, rival, rivals)),
                      ("honeypot.is", _load("hp_matic.json"))])
        return run(risk.assess(WETH, chain_hint="ethereum"))

    # Dwarfed by 8000x: this is not the token the name refers to.
    r = run_with(3_394, 27_144_100)
    imp = [x for x in r["signals"] if x["category"] == "impersonation"]
    check("a token dwarfed 8000x is called out", imp and imp[0]["severity"] == "critical",
          str([(x["severity"], x["name"]) for x in imp]))
    # Never low, but not forced to high either. Impersonation is a question of identity,
    # not of danger: a token that is liquid, clean, and merely shares a ticker with
    # something bigger is not itself hazardous — what went wrong is that a name resolved
    # to the wrong address. Rating that high would conflate "dangerous token" with "wrong
    # token". Medium is the product's "put this in front of the user", which is exactly
    # right here, and the token's other properties decide whether it climbs from there.
    # The live $3,394 namesake does reach high, on low liquidity, not on this signal.
    check("never low", r["risk_level"] != "low", r["risk_level"])
    check("and at least medium", r["risk_level"] in ("medium", "high"), r["risk_level"])

    # The largest holder of the ticker is not an impostor, however many namesakes exist.
    r2 = run_with(27_144_100, 4_098_720, rivals=5)
    imp2 = [x for x in r2["signals"] if x["category"] == "impersonation"]
    check("the biggest token under a ticker is never critical",
          not imp2 or imp2[0]["severity"] in ("ok", "info"),
          str([(x["severity"], x["name"]) for x in imp2]))
    check("and stays low", r2["risk_level"] == "low",
          "%s %s" % (r2["risk_level"], sig_categories(r2)))

    # A modest gap is not impersonation. Small tokens are allowed to exist.
    r3 = run_with(400_000, 1_000_000)
    imp3 = [x for x in r3["signals"] if x["category"] == "impersonation"]
    check("a 2.5x gap raises nothing",
          not imp3 or imp3[0]["severity"] in ("ok", "info"),
          str([(x["severity"], x["name"]) for x in imp3]))

    # Search unreachable: no claim either way. Not finding the check is not evidence.
    install_stub([("dex/tokens", market(3_394, 27_144_100, 0)),
                  ("dex/search", None),
                  ("honeypot.is", _load("hp_matic.json"))])
    r4 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("an unreachable search invents nothing",
          not [x for x in r4["signals"] if x["category"] == "impersonation"],
          str([x["name"] for x in r4["signals"]]))


def _num_or_zero(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _liq_of(result):
    """Liquidity the engine settled on, for assertions about pool selection."""
    return _num_or_zero((result.get("evidence", {}).get("best_pair") or {})
                        .get("liquidity_usd"))


def test_a_tiny_price_is_still_a_price():
    """A coin minted in quadrillions is not an unpriceable coin.

    Supply and price are reciprocal, so a token with a quadrillion units and real money
    behind it trades at something like 1e-22. A price floor of 1e-12 does not exclude a
    class of error, it excludes a class of token -- and it excluded them at the worst
    possible moment, because high-supply micro-caps are where the scams live.

    Measured on the benchmark set: 8 of the 10 confirmed-unsafe tokens came back
    "unknown". hPERPS held $293 across five buys and a sell, priced at 5.5e-24, and the
    engine declined to judge a token whose every detail it could see.
    """
    print("\n[pricing] a very small price is not a missing price")

    def token_at(price, liq):
        return {"pairs": [{
            "chainId": "ethereum", "dexId": "uniswap",
            "baseToken": {"address": WETH, "symbol": "TINY"},
            "quoteToken": {"address": "0xq"}, "priceUsd": price,
            "liquidity": {"usd": liq}, "volume": {"h24": 500.0},
            "txns": {"h24": {"buys": 5, "sells": 1}},
            "pairCreatedAt": 1589841515000}]}

    install_stub([("dex/tokens", token_at("0.000000000000000000000005458", 293.65)),
                  ("honeypot.is", _load("hp_matic.json"))])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("a token priced 5.5e-24 is assessed, not refused",
          r["risk_level"] != "unknown", r["risk_level"])
    check("and its liquidity is the number actually reported",
          abs(_liq_of(r) - 293.65) < 0.01, str(_liq_of(r)))

    # Zero is still not a price. That is the case a floor was ever for.
    install_stub([("dex/tokens", token_at("0", 293.65)),
                  ("honeypot.is", _load("hp_matic.json"))])
    r0 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("a price of exactly zero is still not usable",
          _liq_of(r0) == 0.0, str(_liq_of(r0)))


def test_every_pool_empty_is_a_finding_not_a_gap():
    """Complete information saying the exit is closed is not missing information.

    Fail-closed exists so an *unobserved* dimension cannot buy reassurance. It was never
    meant to file an *observed* absence as a question. A token whose every pool holds
    nothing is the loudest thing this tool can find: there is no price at which you get
    out, which is the honeypot outcome reached from the other direction.
    """
    print("\n[liquidity] pools that exist and hold nothing")

    def empty_pools(n):
        return {"pairs": [{
            "chainId": "ethereum", "dexId": "uniswap",
            "baseToken": {"address": WETH, "symbol": "DRAINED"},
            "quoteToken": {"address": "0xq"}, "priceUsd": "0.0001",
            "liquidity": {"usd": 0}, "volume": {"h24": 0},
            "txns": {"h24": {"buys": 0, "sells": 0}},
            "pairCreatedAt": 1589841515000} for _ in range(n)]}

    install_stub([("dex/tokens", empty_pools(3)), ("honeypot.is", _load("hp_matic.json"))])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    sell = [x for x in r["signals"] if x["category"] == "sellability"]
    check("drained pools raise a critical sellability signal",
          any(x["severity"] == "critical" for x in sell),
          str([(x["severity"], x["name"]) for x in r["signals"]]))
    check("it says how many pools were checked",
          r.get("evidence", {}).get("pools_all_empty") == 3,
          str(r.get("evidence", {}).get("pools_all_empty")))
    check("and it is not also filed as a liquidity data gap",
          not [g for g in (r.get("evidence", {}).get("data_gaps") or [])
               if g.get("dimension") == "liquidity"],
          str(r.get("evidence", {}).get("data_gaps")))
    check("the verdict is not low", r["risk_level"] != "low", r["risk_level"])


_MISSING = object()


def test_unpriced_pools_are_not_empty_pools():
    """A pool nobody costed is not a pool that holds nothing.

    Found by adversarial review of the change that introduced it, not by any test here.
    DexScreener returns "liquidity": null for pairs it has not costed -- 303 of the 3,909
    pairs in this project's own benchmark cache, and for six tokens *every* pair is like
    that. _pair_liquidity reports that as 0.0, which is correct for ranking pools and
    catastrophic as evidence, and the drained-pool branch used it as evidence.

    The engine told the truth about a token it had never measured: 30 pools, all
    uncosted, 174 buys and 104 sells that same day, and the verdict read "there is
    nothing to sell into at any price" with the liquidity data gap deleted, so confidence
    went *up*. That is the fail-closed rule running backwards -- an unmeasured dimension
    being converted into a measurement.
    """
    print("\n[liquidity] uncosted is not empty")

    def pools(liq_value, n=3):
        pair = {"chainId": "ethereum", "dexId": "uniswap",
                "baseToken": {"address": WETH, "symbol": "UNPRICED"},
                "quoteToken": {"address": "0xq"}, "priceUsd": "0.0001",
                "volume": {"h24": 900.0},
                "txns": {"h24": {"buys": 174, "sells": 104}},
                "pairCreatedAt": 1589841515000}
        out = []
        for _ in range(n):
            p = dict(pair)
            p["liquidity"] = {"usd": liq_value} if liq_value is not _MISSING else None
            out.append(p)
        return {"pairs": out}

    install_stub([("dex/tokens", pools(_MISSING)), ("dex/search", None),
                  ("honeypot.is", _load("hp_matic.json"))])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    claims = [x for x in r["signals"]
              if "every one of them is empty" in (x.get("message") or "")]
    check("an uncosted pool is never called empty", not claims,
          str([x["name"] for x in r["signals"]]))
    gaps = (r.get("evidence") or {}).get("data_gaps") or []
    check("and the liquidity gap is kept, so fail-closed still applies",
          any(g.get("dimension") == "liquidity" for g in gaps), str(gaps))
    check("the verdict is not low", r["risk_level"] != "low", r["risk_level"])

    # A pool that really does report zero is still called out -- the fix must not have
    # bought its safety by disabling the check.
    install_stub([("dex/tokens", pools(0)), ("dex/search", None),
                  ("honeypot.is", _load("hp_matic.json"))])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("a pool that reports zero is still called out",
          any(x["severity"] == "critical" and x["category"] == "sellability"
              for x in r2["signals"]),
          str([(x["severity"], x["category"]) for x in r2["signals"]]))


def test_impersonation_only_compares_within_one_chain():
    """A rival on another chain is not evidence, and usually is not a rival.

    Two failures, one filter. A same-ticker token on a foreign venue arrives with a
    liquidity figure nobody here can check and an attacker can manufacture: canonical
    ZORA on Base was called "almost certainly not the token you meant" because a Solana
    pool under that ticker reported $1,015,244,216. And a token deployed on several
    chains has a different address on each, so its own deployments looked like impostors.

    Measured before the fix, over the 207-token benchmark: warn-or-critical on 81 tokens
    labelled safe or alive.
    """
    print("\n[impersonation] rivals are compared on their own chain")

    def pair(chain, addr, liq, sym="TKN"):
        return {"chainId": chain, "dexId": "uniswap",
                "baseToken": {"address": addr, "symbol": sym},
                "quoteToken": {"address": "0xq"}, "priceUsd": "1.0",
                # Healthy turnover on purpose: at 1% the engine correctly calls the
                # pair abandoned, and this test is about impersonation, not lifecycle.
                "liquidity": {"usd": liq}, "volume": {"h24": max(1.0, liq * 0.5)},
                "txns": {"h24": {"buys": 30, "sells": 30}},
                "pairCreatedAt": 1589841515000}

    ours = pair("ethereum", WETH, 94_943.0)
    foreign_giant = pair("solana", "SoLnaMintAddr1111111111111111111111111111", 1_015_244_216.0)
    home_giant = pair("ethereum", "0x%040d" % 7, 3_366_238.0)

    install_stub([("dex/tokens", {"pairs": [ours]}),
                  ("dex/search", {"pairs": [ours, foreign_giant]}),
                  ("honeypot.is", _load("hp_matic.json"))])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("a giant on another chain raises nothing",
          not [x for x in r["signals"] if x["category"] == "impersonation"],
          str([(x["severity"], x["name"]) for x in r["signals"]
               if x["category"] == "impersonation"]))
    check("and the verdict stays low", r["risk_level"] == "low", r["risk_level"])

    # The genuine case still fires: a much larger namesake on our own chain.
    install_stub([("dex/tokens", {"pairs": [pair("ethereum", WETH, 4_275.0)]}),
                  ("dex/search", {"pairs": [pair("ethereum", WETH, 4_275.0), home_giant]}),
                  ("honeypot.is", _load("hp_matic.json"))])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    imp = [x for x in r2["signals"] if x["category"] == "impersonation"]
    check("a much larger namesake on the same chain still fires",
          imp and imp[0]["severity"] in ("warn", "critical"),
          str([(x["severity"], x["name"]) for x in imp]))


def test_simulator_404_is_about_the_token_not_about_us():
    """A 404 means the simulator has no record. That is evidence, not an outage.

    Measured 2026-09-05: 15 of 25 sampled unknown verdicts were honeypot.is answering
    404. The engine filed every one under "upstream request failed", which is the string
    _finalize uses to decide a gap is OUR fault and therefore must not escalate. So the
    tokens nothing can verify -- no market data, no simulator record -- were the ones
    getting excused, which is the exact case the no-trace escalation exists for.

    Same distinction as _reported_liquidity and the drained-pool branch: an observed
    absence and an unobserved dimension are different things, and neither may impersonate
    the other. Third time it has mattered in one day.
    """
    print("\n[upstream] 404 is an answer, not a failure")

    pair = {"pairs": [{
        "chainId": "ethereum", "dexId": "uniswap",
        "baseToken": {"address": WETH, "symbol": "GHOST"},
        "quoteToken": {"address": "0xq"}, "priceUsd": "0.01",
        "liquidity": {"usd": 4000.0}, "volume": {"h24": 2000.0},
        "txns": {"h24": {"buys": 10, "sells": 8}},
        "pairCreatedAt": 1589841515000}]}

    # Upstream says "no record of this token".
    install_stub([("dex/tokens", pair), ("dex/search", None),
                  ("honeypot.is", risk.NO_DATA)])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    gaps = (r.get("evidence") or {}).get("data_gaps") or []
    sell = [g for g in gaps if g.get("dimension") == "sellability"]
    check("a 404 records a sellability gap", bool(sell), str(gaps))
    check("and the reason names the token, not our plumbing",
          sell and "no record of this token" in sell[0].get("reason", ""),
          str(sell))
    check("it does not claim our request failed",
          not any(str(g.get("reason", "")).startswith("upstream request failed")
                  for g in gaps), str(gaps))
    check("the verdict is not low", r["risk_level"] != "low", r["risk_level"])

    # Contrast: we genuinely could not reach upstream. That must stay our fault, so the
    # escalation keeps excusing it -- otherwise our outage becomes a verdict about
    # somebody else's token.
    install_stub([("dex/tokens", pair), ("dex/search", None),
                  ("honeypot.is", None)])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    gaps2 = (r2.get("evidence") or {}).get("data_gaps") or []
    check("an unreachable upstream is still recorded as ours",
          any(str(g.get("reason", "")).startswith("upstream request failed")
              for g in gaps2), str(gaps2))


def test_market_activity_informs_but_does_not_verify_your_exit():
    """Other people's completed sells are context, never a substitute for the check.

    This exists because I tried to make it a substitute and the fail-closed test caught
    me. The case for it was strong: of 97 unknown verdicts, 72 had twenty or more sells
    against a live pool, 63 confirmed good and none bad, and the list included WETH --
    4,540 sells against $117.8M of liquidity, answered "unknown". That looks broken.

    It is still wrong. A simulation tests whether *you* can sell; completed trades show
    that *other people* could. Those separate exactly where it matters, because a
    blacklist honeypot lets ordinary traders through precisely so the market looks
    healthy and blocks the addresses it picks. From outside, that is indistinguishable
    from health -- which is the whole reason the simulation is worth running.

    So: report the activity, keep the gap, keep the verdict honest.
    """
    print("\n[sellability] the market is context, not verification")

    busy = {"pairs": [{
        "chainId": "ethereum", "dexId": "uniswap",
        "baseToken": {"address": WETH, "symbol": "BUSY"},
        "quoteToken": {"address": "0xq"}, "priceUsd": "1.0",
        "liquidity": {"usd": 500_000.0}, "volume": {"h24": 900_000.0},
        "txns": {"h24": {"buys": 900, "sells": 850}},
        "pairCreatedAt": 1589841515000}]}

    # The simulator has no record of the token at all.
    install_stub([("dex/tokens", busy), ("dex/search", None),
                  ("honeypot.is", risk.NO_DATA)])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    sell = [x for x in r["signals"] if x["category"] == "sellability"]
    check("the completed sells are reported",
          any(x["severity"] == "info" and "completing on-chain" in x["name"]
              for x in sell), str([(x["severity"], x["name"]) for x in sell]))
    gaps = (r.get("evidence") or {}).get("data_gaps") or []
    check("but the sellability gap stays open",
          any(g.get("dimension") == "sellability" for g in gaps), str(gaps))
    check("so the verdict is never low", r["risk_level"] != "low", r["risk_level"])
    check("and the evidence says plainly that your exit is unverified",
          (r.get("evidence") or {}).get("sellability_from_chain", {})
          .get("verifies_your_exit") is False,
          str((r.get("evidence") or {}).get("sellability_from_chain")))

    # A quiet pool earns no such note -- there is nothing to report.
    quiet = json.loads(json.dumps(busy))
    quiet["pairs"][0]["txns"]["h24"] = {"buys": 3, "sells": 1}
    install_stub([("dex/tokens", quiet), ("dex/search", None),
                  ("honeypot.is", risk.NO_DATA)])
    r2 = run(risk.assess(WETH, chain_hint="ethereum"))
    check("a quiet pool produces no market-activity note",
          not [x for x in r2["signals"]
               if x["category"] == "sellability" and x["severity"] == "info"],
          str([(x["severity"], x["name"]) for x in r2["signals"]]))


def test_clean_token_stays_low():
    """Guard the other way: more signals must not let the score push a healthy token high."""
    print("\n[scoring] healthy token stays low")
    install_stub([
        ("dexscreener", _load("ds_weth.json")),
        ("honeypot.is", _load("hp_matic.json")),  # clean: not a honeypot, no tax, low risk
    ])
    r = run(risk.assess(WETH, chain_hint="ethereum"))
    check("WETH should be low", r["risk_level"] == "low", "got %s (score=%s) %s"
          % (r["risk_level"], r["risk_score"], sig_categories(r)))
    check("score should be well down", r["risk_score"] < 35, str(r["risk_score"]))

    # Being on one chain should not push a clean token up
    only_warn = [risk._sig("ok", "a", "", "liquidity"),
                 risk._sig("warn", "b", "", "cross_chain")]
    check("cross_chain warn alone must not reach high", risk._score(only_warn) < 70,
          str(risk._score(only_warn)))
    # But a fatal signal must go straight to high
    fatal = [risk._sig("fatal", "hp", "", "honeypot")]
    check("fatal must be >= 70", risk._score(fatal) >= 70, str(risk._score(fatal)))


def test_output_is_compact():
    """Slim evidence by default; verbose gets it all. Floats cut to 6 significant digits."""
    print("\n[size] compact output")
    install_stub([
        ("dexscreener", _load("ds_matic.json")),
        ("honeypot.is", _load("hp_matic.json")),
    ])
    slim = run(risk.assess(MATIC, chain_hint="ethereum"))
    payload = json.dumps(slim, ensure_ascii=False)
    check("default output < 1800 bytes", len(payload) < 1800, "%d bytes" % len(payload))
    check("must not leak raw reserves", "reserves0" not in payload, "")
    check("must not leak taxDistribution", "taxDistribution" not in payload, "")
    check("floats are truncated",
          len(str(slim["evidence"]["best_pair"]["price_usd"]).split(".")[-1]) <= 8,
          str(slim["evidence"]["best_pair"]["price_usd"]))
    check("_sig_round works", risk._sig_round("0.000566716962961376896743") == 0.000566717,
          str(risk._sig_round("0.000566716962961376896743")))


def test_solana_rugcheck_signals():
    """Regression: the Solana path used to read one raw score on the wrong scale.

    BONK's raw score is 101, compared against a threshold of 5000 — every token passed
    unconditionally. Meanwhile rugged / mintAuthority / freezeAuthority / risks[] /
    topHolders sit in the same response and were all thrown away. freezeAuthority is the
    Solana version of a honeypot.
    """
    print("\n[Solana] RugCheck signals")
    install_stub([("dexscreener", _load("ds_bonk.json")),
                  ("rugcheck", _load("rc_bonk.json"))])
    r = run(risk.assess(BONK))
    cats = sig_categories(r)
    check("clean token with revoked authorities is ok",
          cats.get("honeypot") == "ok", str(cats))
    check("must report holder concentration", "concentration" in cats, str(cats))
    check("evidence records the normalised score",
          r["evidence"]["rugcheck"]["score_normalised"] == 7,
          str(r["evidence"]["rugcheck"].get("score_normalised")))
    check("normalised score 7 is not high risk", cats.get("rugcheck") == "ok", str(cats))

    # Dangerous variant: freeze + mint authorities still live, top10 at 77%, danger items
    install_stub([("dexscreener", _load("ds_bonk.json")),
                  ("rugcheck", _load("rc_dangerous.json"))])
    r2 = run(risk.assess(BONK))
    c2 = sig_categories(r2)
    # Regression: the engine rated Circle's USDC on Solana high risk at score 80 purely
    # because the issuer retains freeze and mint authority. Circle holds both by design -
    # freeze is how a regulated issuer honours sanctions, mint is how it issues against
    # reserves - and RugCheck itself scored that token 1/100. Privileged functions are not
    # by themselves evidence of a scam. This is the same error the benchmark labeler made
    # twice; it was fixed there and never carried across to the engine.
    established = _load("rc_dangerous.json")
    established["totalHolders"] = 2_400_000
    established["score_normalised"] = 1
    install_stub([("dexscreener", _load("ds_bonk.json")), ("rugcheck", established)])
    r3 = run(risk.assess(BONK))
    auth3 = [s for s in r3["signals"] if "authority" in s["name"].lower()]
    check("established issuer keeping authorities is not critical",
          auth3 and auth3[0]["severity"] != "critical",
          str(auth3[0]["severity"]) if auth3 else "no signal")
    check("and does not on its own make the verdict high",
          r3["risk_level"] != "high" or any(
              s["severity"] in ("critical", "fatal") and "authority" not in s["name"].lower()
              for s in r3["signals"]),
          "%s %s" % (r3["risk_level"], sig_categories(r3)))

    # One combined signal rather than two. The score adds +10 per distinct bad category,
    # so splitting freeze and mint would count the same fact twice.
    auth = [s for s in r2["signals"] if "authority" in s["name"].lower()]
    check("retained authorities produce exactly one signal", len(auth) == 1, str(auth))
    check("that signal is critical for an anonymous issuer",
          auth and auth[0]["severity"] == "critical", str(auth))
    check("it names both authorities",
          auth and "freeze" in auth[0]["message"].lower() and "mint" in auth[0]["message"].lower(),
          str(auth[0]["message"]) if auth else "")
    check("normalised score 68 must read high", c2.get("rugcheck") == "critical", str(c2))
    check("77% holder concentration must be critical",
          c2.get("concentration") == "critical", str(c2))
    check("overall must be high", r2["risk_level"] == "high",
          "%s score=%s" % (r2["risk_level"], r2["risk_score"]))


def test_new_pools_is_fail_closed():
    """Regression: [] on a fetch failure reads as "we scanned and there are no new pools"."""
    print("\n[fail-closed] new_pools must raise when the fetch fails")
    install_stub([], default=None)
    try:
        run(risk.new_pools("solana"))
        check("total upstream failure must raise", False, "returned a result")
    except RuntimeError:
        check("total upstream failure raises RuntimeError", True)

    install_stub([], default={"data": []})
    out = run(risk.new_pools("solana"))
    check("reachable but empty returns a dict", isinstance(out, dict), str(type(out)))
    check("count is 0", out.get("count") == 0, str(out.get("count")))


def test_new_pools_input_guarding():
    print("\n[input] new_pools argument guarding")
    install_stub([], default={"data": []})
    for bad in ("../etc", "sol ana", "a" * 40):
        try:
            run(risk.new_pools(bad))
            check("new_pools(%r) must raise" % bad, False, "nothing raised")
        except ValueError:
            check("new_pools(%r) raises ValueError" % bad, True)
    try:
        run(risk.new_pools("solana", "abc"))
        check("bad limit must raise", False, "nothing raised")
    except ValueError:
        check("bad limit raises ValueError", True)
    check("chain alias mapping", risk._GT_NETWORK["polygon"] == "polygon_pos", "")
    check("ethereum -> eth", risk._GT_NETWORK["ethereum"] == "eth", "")


def test_geckoterminal_fallback_is_multichain():
    """Regression P0-E: the fallback was hardcoded to eth, so it never fired on polygon."""
    print("\n[P0-E] GeckoTerminal fallback is multichain")
    seen = []

    async def _stub(url, *a, **kw):
        seen.append(url)
        if "dexscreener" in url:
            return {"pairs": []}
        if "polygon_pos" in url:
            return _load("gt_matic_polygon.json")
        return {"data": []}

    risk._fetch_json = _stub
    r = run(risk.liquidity("0x0000000000000000000000000000000000001010",
                           chain_hint="polygon"))
    check("polygon fallback hits", r.get("status") == "ok", str(r))
    check("request goes to polygon_pos", any("polygon_pos" in u for u in seen), str(seen))
    check("chain name normalised to polygon", r.get("best_pair_chain") == "polygon",
          str(r.get("best_pair_chain")))


# ---------------------------------------------------------------- main

def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print("=" * 68)
    print("VetAgent regression tests (offline, real upstream snapshots)")
    print("=" * 68)
    for t in tests:
        t()
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
