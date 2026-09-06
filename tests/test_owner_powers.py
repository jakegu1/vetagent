"""test_owner_powers.py -- the pinned selectors are real, and disclosure stays disclosure.

Two things this guards.

**The selectors.** `src/risk.py` pins four-byte function selectors so the Worker does not
have to carry a Keccak implementation. Pinned constants rot, and worse, a wrong one here
is invisible: it simply never matches, the contract looks powerless, and the tool reports
that as reassurance. So they are recomputed from the signatures and compared. Note that
hashlib's `sha3_256` is *not* Keccak-256 -- they differ by one padding byte, and using it
would produce four entirely plausible bytes that match nothing on any chain.

**That it never scores.** The measurement behind this feature did not support a threshold:
over 417 labelled contracts, pausable appeared in 11% of the unsafe cohort against 5% of
the safe one, mutable tax in 11% against 0%, blacklist in neither, and mintable ran the
wrong way -- 12% of safe against 0% of unsafe. With nine tokens in the unsafe cohort,
"11%" is one token. So this discloses what a contract can do and must not move the
verdict; if someone later wires it into the score, this goes red.

Run:  python tests/test_owner_powers.py
"""

import asyncio
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import risk  # noqa: E402
from keccak import selector  # noqa: E402

_FAILURES = []
_PASSED = 0

# The signatures each pinned selector is supposed to be. Written out so the test can
# recompute rather than trust.
SIGNATURES = {
    "can pause transfers": [
        "pause()", "unpause()", "setPause(bool)", "setPaused(bool)", "pauseTrading()",
        "setTradingEnabled(bool)", "setTradingStatus(bool)"],
    "can blacklist addresses": [
        "blacklist(address)", "addBlackList(address)", "setBlacklist(address,bool)",
        "isBlackListed(address)", "setBots(address[],bool)", "setBlackList(address,bool)"],
    "can change the tax": [
        "setFee(uint256)", "setFees(uint256,uint256)", "setTaxes(uint256,uint256,uint256)",
        "setBuyTax(uint256)", "setSellTax(uint256)", "setTaxFeePercent(uint256)",
        "setSellFee(uint256)", "setBuyFee(uint256)"],
    "can mint new supply": ["mint(address,uint256)", "mint(uint256)"],
}


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def test_selectors_are_real():
    print("\n[selectors] every pinned constant recomputes from its signature")
    # A selector everyone can verify independently, to prove the hash itself is right.
    check("keccak is Keccak-256, not SHA3",
          selector("transfer(address,uint256)") == "a9059cbb",
          selector("transfer(address,uint256)"))

    for group, sigs in SIGNATURES.items():
        want = tuple(selector(s) for s in sigs)
        have = risk._OWNER_POWERS.get(group)
        check("%s: %d selectors match" % (group, len(sigs)), have == want,
              "pinned %s vs computed %s" % (have, want))

    check("the proxy selector is implementation()",
          risk._PROXY_SELECTOR == selector("implementation()"), risk._PROXY_SELECTOR)

    check("every pinned group is covered by this test",
          set(risk._OWNER_POWERS) == set(SIGNATURES),
          str(set(risk._OWNER_POWERS) ^ set(SIGNATURES)))


def test_disclosure_never_moves_the_verdict():
    print("\n[disclosure] powers are reported and never scored")
    signals, evidence = [], {}
    risk._owner_power_signal(
        {"powers": ["can blacklist addresses", "can change the tax",
                    "can pause transfers"],
         "is_proxy": False, "bytecode_bytes": 9000}, signals, evidence)

    check("a signal is emitted", len(signals) == 1, str(signals))
    check("and it is only informational",
          signals and signals[0]["severity"] == "info",
          signals[0]["severity"] if signals else "none")
    # Assert the property, not the number. An info signal scores 3 (5 at the contract
    # weight of 0.6), and what matters is that the verdict is identical with it and
    # without it -- across a clean token and a dirty one, not just in the easy case.
    def level(extra):
        base = [risk._sig("ok", "fine", "", "liquidity")]
        return risk._finalize("0x0", base + extra, {}, [])["risk_level"]

    def level_dirty(extra):
        base = [risk._sig("warn", "thin", "", "liquidity")]
        return risk._finalize("0x0", base + extra, {}, [])["risk_level"]

    check("the verdict on a clean token is identical with and without it",
          level([]) == level(list(signals)), "%s vs %s" % (level([]), level(list(signals))))
    check("and on a token that already has a warning",
          level_dirty([]) == level_dirty(list(signals)),
          "%s vs %s" % (level_dirty([]), level_dirty(list(signals))))
    check("the powers are recorded as evidence",
          evidence.get("owner_powers", {}).get("powers"), str(evidence))

    # A proxy must not read as "no powers found".
    signals2, evidence2 = [], {}
    risk._owner_power_signal({"powers": [], "is_proxy": True, "bytecode_bytes": 300},
                             signals2, evidence2)
    check("a proxy says the powers are not visible, not that there are none",
          signals2 and "not visible" in signals2[0]["name"],
          str([x["name"] for x in signals2]))
    check("and that is informational too",
          signals2 and signals2[0]["severity"] == "info",
          signals2[0]["severity"] if signals2 else "none")

    # Finding nothing must not read as finding nothing there. Measured against the
    # labelling oracle over 120 contracts it says hold at least one of these powers, the
    # bytecode scan finds 31% of them -- 5% for a mutable tax. So an empty list is a
    # statement about the scan, and the payload has to say which.
    signals5, evidence5 = [], {}
    risk._owner_power_signal({"powers": [], "is_proxy": False, "found_none": True,
                              "scan_is_incomplete": True, "bytecode_bytes": 9000},
                             signals5, evidence5)
    check("finding nothing produces an explicit caveat",
          signals5 and "weaker than it sounds" in signals5[0]["name"],
          str([x["name"] for x in signals5]))
    check("and the payload marks the scan incomplete",
          evidence5.get("owner_powers", {}).get("scan_is_incomplete") is True,
          str(evidence5))

    # Unreadable contract: say nothing at all.
    signals3, evidence3 = [], {}
    risk._owner_power_signal(None, signals3, evidence3)
    check("an unreadable contract discloses nothing",
          not signals3 and not evidence3, str(signals3))

    # A lookup that failed is recorded, never claimed. This is the only POST the Worker
    # makes and its signature cannot be checked outside production; if it is wrong the
    # feature would otherwise do nothing forever while looking like an unreadable
    # contract -- which is precisely how a honeypot check that never ran survived here.
    signals4, evidence4 = [], {}
    risk._owner_power_signal({"unavailable": "fetch signature: x"}, signals4, evidence4)
    check("a failed lookup is recorded in evidence",
          evidence4.get("owner_powers", {}).get("unavailable"), str(evidence4))
    check("and claims nothing about the contract", not signals4, str(signals4))


def test_a_real_contract_reads_correctly():
    """Contracts whose powers are public record, checked against their real bytecode.

    Fetched through the benchmark's own RPC rather than the engine's, because the engine's
    fetch needs the Worker runtime and would skip here -- and a check that skips is how a
    honeypot detector that never ran survived for weeks. The matching half is pure, so it
    can be handed real code from anywhere.
    """
    print("\n[live] contracts whose powers are a matter of public record")
    sys.path.insert(0, os.path.join(ROOT, "bench"))
    import backfill as B  # noqa: E402

    CASES = [
        ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7",
         ["can blacklist addresses", "can pause transfers"], False),
        ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", [], True),
        ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", [], False),
    ]
    try:
        codes = B.rpc_batch(B.CHAINS["eth"]["rpc"],
                            [("eth_getCode", [a, "latest"]) for _, a, _, _ in CASES],
                            chunk=3)
    except Exception as e:  # noqa: BLE001
        check("ethereum RPC reachable", False, str(e)[:80])
        return

    for (name, _addr, expect, is_proxy), code in zip(CASES, codes):
        info = risk._powers_from_code(code)
        if info is None:
            check("%s bytecode was returned" % name, False, "empty")
            continue
        for power in expect:
            check("%s is seen to have: %s" % (name, power),
                  power in info["powers"], str(info["powers"]))
        check("%s proxy detection is %s" % (name, is_proxy),
              info["is_proxy"] == is_proxy,
              "got is_proxy=%s, %d bytes" % (info["is_proxy"], info["bytecode_bytes"]))

    # WETH has no owner at all: finding powers in it would mean the matcher is matching
    # coincidental byte sequences rather than selectors.
    weth = risk._powers_from_code(codes[2])
    check("WETH, which has no owner, shows no powers",
          weth is not None and not weth["powers"], str(weth))



def test_minimal_and_slot_proxies_are_recognised():
    """`is_proxy` looked for one selector, and missed the proxy that has no selectors.

    Found by external audit, with the strongest evidence in the report: bytecode fetched
    for 555 dataset contracts, and **53 of 53 EIP-1167 minimal proxies read
    `is_proxy=False`**. Of 99 contracts the labelling oracle flags as proxies, 49 read
    False, and 48 of those then got the silent empty-`powers` treatment.

    The check was `"5c60da1b" in body` -- the selector for `implementation()`. An EIP-1167
    minimal proxy has no dispatcher and no selectors at all: it is 45 bytes of delegatecall
    around a hardcoded address. Looking for a function in a contract that has no functions.

    Why it matters is the pattern this project keeps paying for. `is_proxy` exists so that
    `found_none` can be read correctly -- a proxy's logic lives at another address, so
    finding no powers in *this* bytecode means nothing whatsoever. With `is_proxy` wrong,
    `evidence.owner_powers` says "no powers found, and this is not a proxy" about a
    contract whose behaviour is entirely somewhere else. An unobserved dimension reported
    as an observed absence, on the one field whose whole job was to prevent that reading.
    """
    print("\n[proxy] a proxy with no functions is still a proxy")

    # A real EIP-1167 minimal proxy: prefix, 20-byte implementation address, suffix.
    impl = "bebc44782c7db0a1a60cb6fe97d0b483032ff1c7"
    eip1167 = "0x363d3d373d3d3d363d73" + impl + "5af43d82803e903d91602b57fd5bf3"
    r = risk._powers_from_code(eip1167)
    check("an EIP-1167 minimal proxy is recognised", r and r["is_proxy"] is True,
          repr(r))
    check("and it does not claim the contract has no powers",
          r and r["found_none"] is False, repr(r))

    # ERC-1967: the implementation slot constant appears in the bytecode.
    slot = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    erc1967 = "0x6080604052" + slot + "600080fd"
    r2 = risk._powers_from_code(erc1967)
    check("an ERC-1967 slot proxy is recognised", r2 and r2["is_proxy"] is True,
          repr(r2))

    # The original transparent-proxy selector still works.
    r3 = risk._powers_from_code("0x6080604052635c60da1b600080fd")
    check("implementation() still counts", r3 and r3["is_proxy"] is True, repr(r3))

    # And an ordinary contract is still not a proxy.
    r4 = risk._powers_from_code("0x6080604052" + "63a9059cbb" + "600080fd")
    check("a plain token is not called a proxy", r4 and r4["is_proxy"] is False,
          repr(r4))

    # Case-insensitivity: node responses are not consistent about hex casing.
    r5 = risk._powers_from_code(eip1167.upper().replace("0X", "0x"))
    check("uppercase bytecode is read the same way", r5 and r5["is_proxy"] is True,
          repr(r5))


def test_bytecode_is_cached_as_advertised():
    """"cached hard and costs almost nothing after the first look" -- it was neither.

    Found by external audit. The comment above `_CHAIN_RPC` states that bytecode is
    immutable for an address, so the lookup is cached and nearly free after the first
    call. `_eth_get_code` called `cf_fetch` directly and never touched `_cache_get` or
    `_cache_put`. Every EVM `assess()` made an uncached POST to a free public RPC on the
    request path -- and HANDOFF trap 18 already records that free RPCs meter per call, not
    per request.

    The premise was right and only the caching was missing, which is the dangerous version
    of this mistake: the comment is load-bearing documentation that a reader (including
    me, later) uses to reason about cost, and it was describing an intention rather than
    the code underneath it.

    Cached under a synthetic key, because the real request is a POST to one shared RPC URL
    for every address -- caching on the request URL would have served one contract's
    bytecode for another's. Successes only: a cached failure turns one busy node into a
    permanent "we cannot read this contract", which is the same rule `_fetch_json` already
    follows and for the same reason.
    """
    print("\n[cache] bytecode is immutable, so read it once")

    calls = []
    store = {}

    async def _fake_get_code(rpc, address):
        calls.append(address)
        if address.endswith("dead"):
            return None, "rpc 429"
        return "0x6080604052" + "63a9059cbb" + "600080fd", None

    async def _fake_cache_get(url):
        hit = store.get(url)
        return (hit, 0) if hit is not None else (None, None)

    async def _fake_cache_put(url, data, ttl=None):
        store[url] = data

    real = (risk._eth_get_code, risk._cache_get, risk._cache_put)
    risk._eth_get_code, risk._cache_get, risk._cache_put = (
        _fake_get_code, _fake_cache_get, _fake_cache_put)
    try:
        addr = "0x" + "ab" * 20
        first = asyncio.run(risk._owner_powers(addr, "ethereum"))
        second = asyncio.run(risk._owner_powers(addr, "ethereum"))
        check("the bytecode is read once, not twice", len(calls) == 1, repr(calls))
        check("and the second answer is the same", first == second,
              "%r != %r" % (first, second))

        other = "0x" + "cd" * 20
        asyncio.run(risk._owner_powers(other, "ethereum"))
        check("a different address is not served the first one's code",
              len(calls) == 2 and calls[1] == other, repr(calls))

        # A failure must not be cached: one busy node would become permanent blindness.
        bad = "0x" + "00" * 18 + "dead"
        asyncio.run(risk._owner_powers(bad, "ethereum"))
        asyncio.run(risk._owner_powers(bad, "ethereum"))
        check("a failed read is retried, not remembered",
              calls.count(bad) == 2, repr(calls))
    finally:
        risk._eth_get_code, risk._cache_get, risk._cache_put = real


def main():
    print("=" * 68)
    print("Owner-power disclosure")
    print("=" * 68)
    # Discovered, not listed. A hand-maintained list means a new test runs only if
    # someone remembers to add it, and a test that never runs is worse than no test --
    # it reports PASS by silence. test_risk.py and test_mcp.py already discover.
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
