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



def main():
    print("=" * 68)
    print("Owner-power disclosure")
    print("=" * 68)
    for fn in (test_selectors_are_real, test_disclosure_never_moves_the_verdict,
               test_a_real_contract_reads_correctly):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for name, detail in _FAILURES:
        print("  FAIL  %s  %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
