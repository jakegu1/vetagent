"""test_coverage_matrix.py — does the engine actually do what the scorecard claims?

Every advertised chain x every risk dimension, against a real token on that chain.

WHY THIS EXISTS

`bench/scorecard.py` said `("sellability simulation (honeypot, EVM)", True)`. The comment
immediately under it said "The simulator covers ethereum, bsc and base". Both were written
in the same sitting, by the same person, and four advertised chains -- polygon, arbitrum,
optimism, avalanche -- had nothing testing whether a holder can sell while the scorecard
called the dimension covered. The same shape had already shipped twice: a RugCheck report
accepted in place of a Solana sell test (E24), and the EVM twin of the Solana coverage
signal scoring a token it knew nothing about (F2).

Three bugs, one missing instrument. Nothing compared the claim against the engine. Reviews
did not catch it because reading a table of `True`s tells you what someone believed.

WHAT IT DOES

For each advertised chain it replays one real token's recorded upstream responses through
`risk.assess()`, then asks, dimension by dimension, what the engine actually produced. The
expectations are **generated** from `scorecard.RISK_VECTORS` -- there is no second table
here to drift from the first one. Adding a chain to `ADVERTISED_CHAINS` adds a column and
fails until a token is recorded for it; marking a cell covered fails until the engine
covers it.

THREE ANSWERS, NOT TWO

An observer returns `covered`, `open`, or `None` for "this token could not settle it" --
a ticker with no rival says nothing about whether impersonation is checked. `None` is
printed as `----` and counted separately. This file exists because a dimension nobody
looked at was reported as a dimension that passed; it must not make that mistake itself.

RE-RECORDING

    python tests/test_coverage_matrix.py --record          # all chains, live
    python tests/test_coverage_matrix.py --record solana    # one chain

recorded responses land in tests/fixtures/coverage_matrix/. Replay is offline and safe in
CI. A recording is a moment: if an upstream changes what it serves, this file keeps
passing on the old bytes and `tests/test_upstream_contract.py` is what notices. The
recording date is printed on every run so a stale matrix is visible rather than silent.

Run:  python tests/test_coverage_matrix.py
"""

import asyncio
import datetime
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import risk        # noqa: E402
import scorecard   # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures", "coverage_matrix")

# One real token per advertised chain. Established tokens on purpose: the question is
# what the engine *can* read on a chain, and a token nothing has indexed yet cannot
# answer it. Checked against ADVERTISED_CHAINS below, so a new chain cannot be advertised
# without one.
TOKENS = {
    "ethereum":  ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC"),
    "bsc":       ("0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82", "CAKE"),
    "base":      ("0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed", "DEGEN"),
    "arbitrum":  ("0x912CE59144191C1204E64559FE8253a0e49E6548", "ARB"),
    "polygon":   ("0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39", "LINK"),
    "optimism":  ("0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db", "VELO"),
    "avalanche": ("0x60781C2586D68229fde47564546784ab3fACA982", "PNG"),
    "solana":    ("rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof", "RENDER"),
}

COVERED, OPEN = "covered", "open"

_PASSED = 0
_FAILURES = []
_UNCHECKED = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def unchecked(name, why):
    _UNCHECKED.append((name, why))
    print("  ----  %s  (not settled by this token: %s)" % (name, why))


# ------------------------------------------------------------------ replay

class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body


def _replay(responses):
    """A cf_fetch that serves recorded bytes and refuses to invent any."""
    async def _fetch(url, method="GET", headers=None, body=None, **kw):
        hit = responses.get(url)
        if hit is None:
            # Never a silent miss. An unrecorded URL means the engine asked something the
            # recording never saw, and answering "fetch failed" would quietly turn that
            # into a data gap -- the exact confusion this repo keeps paying for.
            raise AssertionError(
                "engine requested an unrecorded URL, re-record this chain: %s" % url)
        return _Response(hit["status"], hit["body"])
    return _fetch


def _assess(chain):
    """Replay one chain's recording through the engine. (result, recorded_at)."""
    path = os.path.join(FIXTURES, "%s.json" % chain)
    with io.open(path, encoding="utf-8") as f:
        rec = json.load(f)
    risk.cf_fetch = _replay(rec["responses"])
    try:
        result = asyncio.run(risk.assess(rec["address"], chain_hint=chain, verbose=True))
    finally:
        risk.cf_fetch = None
    return result, rec


# ------------------------------------------------------------------ observers
#
# One per dimension in RISK_VECTORS, and `test_every_dimension_has_an_observer` fails if a
# dimension has none. That check is the point: the guard this file replaces went quiet on
# "holder concentration (EVM)" by simply having no entry for it, and an instrument that can
# be disarmed by omission is not an instrument.
#
# Each observer returns COVERED, OPEN, or None (this token cannot settle it). OPEN is only
# returned where the absence is conclusive -- the single source that would carry the
# reading did not report -- never from "the key is missing".

def _gaps(result, dimension):
    ev = result.get("evidence") or {}
    return [g for g in (ev.get("data_gaps") or []) if g.get("dimension") == dimension]


def _not_covered_gap(result, dimension):
    return any(str(g.get("reason", "")).startswith(risk._NOT_COVERED)
               for g in _gaps(result, dimension))


def _hp(result):
    """honeypot.is's reading, or None when the simulator never answered about this token.

    Absence here is conclusive for every dimension honeypot.is is the only source of:
    the simulation, the three taxes, whether the source is published, and the aggregate
    verdict all arrive in one payload, so no payload means none of them were read.
    """
    return (result.get("evidence") or {}).get("honeypot")


def _obs_sellability(result):
    if _not_covered_gap(result, "sellability"):
        return OPEN
    hp = _hp(result)
    if hp and hp.get("simulation_success") is not None:
        return COVERED
    if hp is None:
        return OPEN
    return None


def _obs_tax(result):
    hp = _hp(result)
    if hp is not None:
        taxes = [hp.get("buy_tax"), hp.get("sell_tax"), hp.get("transfer_tax")]
        return COVERED if any(t is not None for t in taxes) else None
    t22 = (result.get("evidence") or {}).get("token2022")
    if isinstance(t22, dict):
        # Token-2022's transfer fee is read out of the extensions block. `read: True` means
        # the block was there and was parsed, which is the reading; a token with no fee
        # extension is an answer, not a gap.
        return COVERED if t22.get("read") else None
    return OPEN


def _obs_liquidity(result):
    if _not_covered_gap(result, "liquidity"):
        return OPEN
    return COVERED if (result.get("evidence") or {}).get("liquidity_source") else None


def _obs_pair_age(result):
    ev = result.get("evidence") or {}
    if "pair_age_days" in ev:
        return COVERED
    # DexScreener does not carry pairCreatedAt on every pair. Absent is a fact about this
    # pair, not about the chain, so this token cannot settle the cell either way.
    return None


def _obs_source_published(result):
    hp = _hp(result)
    if hp is None:
        return OPEN
    return COVERED if hp.get("open_source") is not None else None


def _obs_aggregator(result):
    hp = _hp(result)
    if hp is not None:
        return COVERED if hp.get("upstream_risk") is not None else None
    rc = (result.get("evidence") or {}).get("rugcheck")
    if isinstance(rc, dict):
        return COVERED if (rc.get("score_normalised") is not None
                           or rc.get("score_raw") is not None) else None
    return OPEN


def _obs_holder_concentration(result):
    """A concentration reading is a share of supply held by the top holders.

    Covered means a number came back. Not covered is conclusive in both of the ways this
    dimension is currently missing: on EVM nothing is asked at all (the source would be
    GoPlus, held out under DECISIONS B2), and on Solana the request is made and RugCheck
    returns no holders, which the engine records as a gap on this dimension.
    """
    rc = (result.get("evidence") or {}).get("rugcheck")
    if isinstance(rc, dict) and rc.get("top_holder_pct") is not None:
        return COVERED
    if any(s.get("category") == "concentration" and s.get("severity") != "info"
           for s in result.get("signals") or []):
        return COVERED
    return OPEN


def _obs_mint_freeze(result):
    rc = (result.get("evidence") or {}).get("rugcheck")
    if not isinstance(rc, dict):
        return OPEN
    return COVERED if ("mint_authority" in rc and "freeze_authority" in rc) else OPEN


def _obs_impersonation(result):
    ev = result.get("evidence") or {}
    if ev.get("same_symbol") or any(s.get("category") == "impersonation"
                                    for s in result.get("signals") or []):
        return COVERED
    # No other contract shares this ticker, so the check ran and found nothing. That does
    # not distinguish "ran" from "never ran", and guessing is how this repo got here.
    return None


def _obs_deployer_history(result):
    ev = result.get("evidence") or {}
    return COVERED if ev.get("deployer") else OPEN


OBSERVERS = {
    "sellability simulation": _obs_sellability,
    "buy / sell / transfer tax": _obs_tax,
    "liquidity depth": _obs_liquidity,
    "pair age": _obs_pair_age,
    "contract source published": _obs_source_published,
    "upstream aggregator verdict": _obs_aggregator,
    "holder concentration": _obs_holder_concentration,
    "mint / freeze authority": _obs_mint_freeze,
    "same-name token impersonation": _obs_impersonation,
    "deployer history": _obs_deployer_history,
}


# ------------------------------------------------------------------ tests

def test_every_advertised_chain_has_a_token():
    print("\n[matrix] a chain cannot be advertised without a token to check it on")
    for chain in scorecard.ADVERTISED_CHAINS:
        check("%s has a reference token" % chain, chain in TOKENS, sorted(TOKENS))
        check("%s has a recording" % chain,
              os.path.exists(os.path.join(FIXTURES, "%s.json" % chain)),
              "run: python tests/test_coverage_matrix.py --record %s" % chain)
    extra = sorted(set(TOKENS) - set(scorecard.ADVERTISED_CHAINS))
    check("no reference token for a chain we do not advertise", not extra, str(extra))


def test_every_dimension_has_an_observer():
    """No dimension may be unchecked by omission.

    The guard this replaces had no entry at all for "holder concentration (EVM)" and
    reported green. A missing key is the quietest way for a check to stop checking.
    """
    print("\n[matrix] every scorecard dimension is observable")
    for name, applies, _on in scorecard.RISK_VECTORS:
        if applies is None:
            print("  ----  %s  (measured and rejected, no engine behaviour to check)" % name)
            continue
        check("%s has an observer" % name, name in OBSERVERS, sorted(OBSERVERS))
    stale = sorted(set(OBSERVERS) - set(n for n, a, _ in scorecard.RISK_VECTORS if a))
    check("no observer for a dimension the scorecard dropped", not stale, str(stale))


def test_the_engine_does_what_the_scorecard_claims():
    """The matrix. Generated from RISK_VECTORS x ADVERTISED_CHAINS, measured per cell."""
    print("\n[matrix] the engine's behaviour, chain by chain, against the claim")
    for chain in scorecard.ADVERTISED_CHAINS:
        if chain not in TOKENS or not os.path.exists(
                os.path.join(FIXTURES, "%s.json" % chain)):
            continue                      # already failed above; do not fail twice
        result, rec = _assess(chain)
        age = _age_days(rec.get("recorded_at"))
        print("\n  %s / %s  recorded %s%s -> %s"
              % (chain, rec.get("symbol", "?"), str(rec.get("recorded_at"))[:10],
                 "" if age is None else " (%d days ago)" % age,
                 result.get("risk_level")))
        for name, applies, on in scorecard.RISK_VECTORS:
            if applies is None or chain not in applies:
                continue
            claimed = COVERED if chain in on else OPEN
            observed = OBSERVERS[name](result)
            label = "%s on %s: scorecard says %s" % (name, chain, claimed)
            if observed is None:
                unchecked(label, "%s / %s produced no reading either way"
                          % (chain, rec.get("symbol", "?")))
            else:
                check(label, observed == claimed, "engine says %s" % observed)


def test_a_dimension_is_not_claimed_on_a_chain_it_is_not_asked_about():
    """`n/a` has to be measured too, or it is just a quieter way of not looking."""
    print("\n[matrix] the cells marked n/a really are outside the question")
    for name, applies, _on in scorecard.RISK_VECTORS:
        if applies is None:
            continue
        for chain in scorecard.ADVERTISED_CHAINS:
            if chain in applies or chain not in TOKENS:
                continue
            if not os.path.exists(os.path.join(FIXTURES, "%s.json" % chain)):
                continue
            result, _rec = _assess(chain)
            observed = OBSERVERS[name](result)
            check("%s is not quietly covered on %s, where it is marked n/a"
                  % (name, chain), observed != COVERED,
                  "engine says %s -- if it is covered there it is not n/a" % observed)


def _age_days(stamp):
    try:
        then = datetime.datetime.strptime(str(stamp)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (datetime.date.today() - then).days


# ------------------------------------------------------------------ recording

def record(chains):
    """Fetch live and write the fixtures. Never runs as part of the test."""
    import urllib.request
    import urllib.error

    class _Live:
        def __init__(self, status, body):
            self.status, self._body = status, body

        async def text(self):
            return self._body

    os.makedirs(FIXTURES, exist_ok=True)
    for chain in chains:
        address, symbol = TOKENS[chain]
        seen = {}

        async def _fetch(url, method="GET", headers=None, body=None, **kw):
            def _do():
                req = urllib.request.Request(
                    url, method=method,
                    data=body.encode() if isinstance(body, str) else body)
                for k, v in (headers or {}).items():
                    req.add_header(k, v)
                req.add_header("User-Agent", "vetagent-coverage-matrix/1.0 "
                                             "(+https://github.com/jakegu1/vetagent)")
                try:
                    with urllib.request.urlopen(req, timeout=25) as r:
                        return r.status, r.read().decode("utf-8", "replace")
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode("utf-8", "replace")
            status, text = await asyncio.get_event_loop().run_in_executor(None, _do)
            seen[url] = {"status": status, "body": text}
            return _Live(status, text)

        risk.cf_fetch = _fetch
        result = asyncio.run(risk.assess(address, chain_hint=chain, verbose=True))
        risk.cf_fetch = None
        payload = {
            "chain": chain, "address": address, "symbol": symbol,
            "recorded_at": datetime.datetime.now(datetime.timezone.utc)
                                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "responses": seen,
        }
        path = os.path.join(FIXTURES, "%s.json" % chain)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, sort_keys=True)
        print("recorded %-10s %-7s %2d responses, %4d KB, verdict %s"
              % (chain, symbol, len(seen), os.path.getsize(path) // 1024,
                 result.get("risk_level")))


def main():
    if "--record" in sys.argv:
        rest = [a for a in sys.argv[sys.argv.index("--record") + 1:]
                if not a.startswith("-")]
        record(rest or list(scorecard.ADVERTISED_CHAINS))
        return 0
    print("=" * 68)
    print("Coverage matrix: advertised chain x risk dimension, on a real token")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n%d passed, %d failed, %d not settled by the reference token"
          % (_PASSED, len(_FAILURES), len(_UNCHECKED)))
    if _UNCHECKED:
        print("\nNot settled here (a cell nobody measured is a gap, not a pass):")
        for name, why in _UNCHECKED:
            print("  - %s: %s" % (name, why))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
