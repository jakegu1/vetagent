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

# The signature each pinned selector is supposed to be. GENERATED beside the list itself by
# `python bench/selector_mine.py --emit`, so the two halves of the guard cannot drift -- a
# guard whose halves are typed separately is a guard waiting to disagree with itself.
#
# The comparison below is by SET, not by tuple. It was by tuple when both sides were typed
# by hand and twenty-three selectors long; the list is generated and two hundred and
# ninety-six long now, and ordering carries no meaning, so an order comparison would fail on
# a re-emit that changed nothing. The strength is unchanged -- every selector still has to
# recompute from its signature -- and a length check is added beside it, because a set
# comparison alone would not notice a duplicate.
SIGNATURES = {
    "can pause transfers": [
        "pauseTrading()",
        "setPaused(bool)",
        "setBuyRates(uint256)",
        "MODE_TRANSFER_RESTRICTED()",
        "areTransfersAllowed()",
        "transferAllowed()",
        "setTransferState(bool)",
        "unpause()",
        "isPauser(address)",
        "setPauseRole(address,bool)",
        "paused()",
        "setTx(uint256)",
        "removePauser(address)",
        "renouncePauser()",
        "setSellRates(uint256)",
        "addPauser(address)",
        "pause()",
        "allowTransfersFor(address[])",
        "ExpectedPause()",
        "nodeBuyEnabled()",
        "setPreMigrationTransferable(address,bool)",
        "enableTransfers()",
        "setPause(bool)",
        "transfersEnabled()",
        "updateTransferEnabled(bool)",
        "transferableBalanceOf(address)",
        "pauseRoles(address)",
        "isTransferEnabled()",
        "TransferPaused()",
        "TransferRestricted(address,address)",
        "EnforcedPause()",
        "PAUSER_ROLE()",
        "restrictionPeriod()",
        "pauseSendTokens(bool)",
        "enableTransfer()",
        "enableTransfers(bool)",
        "transferStatus()",
    ],
    "can halt trading": [
        "launch()",
        "TradingOpen()",
        "FirstLaunch__AlreadyLaunched()",
        "TradingAlreadyActive()",
        "launcher()",
        "launchContract()",
        "launch(address)",
        "startTrading()",
        "enableTradingStatus(bool)",
        "setTradingStatus(bool)",
        "tradingEnabled()",
        "tradingStarted()",
        "launchPublic()",
        "launched()",
        "setLaunch(address)",
        "enableTrading()",
        "launching()",
        "openTrading(uint256,uint256,uint256,address)",
        "NotLaunched()",
        "launchedAtCoefficient()",
        "finishLaunch()",
        "NotLauncher()",
        "marketBuyOpen()",
        "tradingActive()",
        "launchedAt()",
        "setTradingEnabled(bool)",
        "openTrading()",
        "launchBlock()",
        "setMarketOpen(bool,bool)",
        "TradingNotOpen()",
        "updateLaunchedAtCoefficient(uint256)",
        "trading()",
        "tradingActiveBlock()",
        "tradingStart()",
        "openTrade()",
        "closeTrade()",
        "launch(uint160,int24,int24)",
        "tradingStopped()",
        "tradingOpen()",
    ],
    "can blacklist addresses": [
        "isNotRestricted()",
        "checkBlacklist()",
        "addBlackList(address)",
        "freezeParameters()",
        "setBlacklist(address,bool)",
        "blacklists(address)",
        "FULL_RESTRICTED_STAKER_ROLE()",
        "blacklistAccount(address,bool)",
        "delBots(address[])",
        "isBot(address)",
        "blacklistRenounced()",
        "blacklist(address,bool)",
        "BLACKLIST_MANAGER_ROLE()",
        "tokenLockAddress()",
        "BulkisBot(address[],bool)",
        "getBlackListStatus(address)",
        "withdrawStuckUnibot()",
        "renounceBlacklist()",
        "setBlackList(address,bool)",
        "unblacklist(address)",
        "blackListAddress(address,bool)",
        "isAddressBlacklisted(address)",
        "setBots(address[],bool)",
        "deny(address)",
        "setCheckBlacklist(bool)",
        "blacklistUpdate(address,bool)",
        "SOFT_RESTRICTED_STAKER_ROLE()",
        "removeFromBlacklist(address,bool)",
        "blacklist(address[],bool)",
        "BlackListAddress(address,bool)",
        "setProtectionBot()",
        "setBlacklisted(address,bool)",
        "addBots(address[])",
        "blacklisted(address)",
        "isBlackListed(address)",
        "removeBlackList(address)",
        "parametersFrozen()",
        "addToBlacklist(address,bool)",
        "destroyBlackFunds(address)",
        "blacklist(address)",
        "isBlacklisted(address)",
    ],
    "can change the tax": [
        "updateSellFees(uint256,uint256)",
        "SetFee(uint256,uint256)",
        "setTaxFeePercent(uint256)",
        "changeFeeSell(uint256)",
        "setFees(uint256,uint256)",
        "_reduceBuyTaxAt()",
        "setBuyFee(uint256)",
        "setBuyFees(uint256,uint256,uint256)",
        "setExtraSellTax(uint256)",
        "setSellFees(uint256,uint256,uint256)",
        "removeTransferTax()",
        "setBuyFeeLeverage(uint16)",
        "initialBuyTaxBps()",
        "setFeeSetting(uint256,uint256,uint256,uint256)",
        "_initialSellLPFee()",
        "setFeeOwner(address)",
        "setFees(uint8,uint8)",
        "setFeesBuy(uint256,uint256)",
        "setTokenRoyalty()",
        "setFeePerMillion(uint256)",
        "setDefaultFeeBp(uint16)",
        "updateTaxInfo(address,uint256)",
        "setTax(uint256,uint256)",
        "updateBuyFees(uint256,uint256)",
        "setFee(uint256)",
        "setBuyFee(uint16)",
        "setFeeBp(uint16,bool,uint16)",
        "changeFeeBuy(uint256)",
        "_initialSellMarketingFee()",
        "updateBuyFees(uint256,uint256,uint256)",
        "removeTaxesAndLimits()",
        "updateFee(uint256,uint256,address)",
        "setChargeFee(address,bool)",
        "updateFeeCalculationData(uint256)",
        "setSellFee(uint256)",
        "setSellTax(uint256)",
        "setLiquidityFeePercent(uint256)",
        "setSellFees(uint256)",
        "setSwapFee(address,uint256)",
        "setBuyFeeRatio(uint256)",
        "setFeesSell(uint256,uint256)",
        "setEarlySellTax(bool)",
        "enableEarlySellTax()",
        "reduceFee()",
        "changeFeeTransfer(uint256)",
        "setParams(uint256,uint256)",
        "updateSellFees(uint256,uint256,uint256)",
        "_reduceSellTaxAt()",
        "setTaxEnabled(bool)",
        "setFeesPercentage(uint256)",
        "setFeeSplit(uint256)",
        "initialSellTaxBps()",
        "setBuyTax(uint256)",
        "setBuyFees(uint256)",
        "setSellFee(uint16)",
        "setSellFeeRatio(uint256)",
        "setTradeFees(uint256,uint256)",
        "setTaxes(uint256,uint256,uint256)",
        "reduceFee(uint256)",
        "setFeesBps(uint256)",
        "setFinalTax()",
        "setTaxes(uint16,uint16,uint16,uint16)",
        "setTaxConfig(address,uint256)",
        "setProfitTax(bool,uint256)",
        "ForceTaxCooldown(uint256)",
        "updateSellFees(uint256,uint256,uint256,uint256,uint256)",
    ],
    "can mint new supply": [
        "getMinterLength()",
        "InvalidMinterZeroAddress()",
        "mintingFinished()",
        "minter()",
        "minterTimelock()",
        "mintingMaxLimitOf(address)",
        "MaxYearlyMintRateExceeded(uint256,uint256)",
        "applyMinter()",
        "MINIMUM_TIME_BETWEEN_MINTS()",
        "lastestMinting()",
        "YEARLY_MINTABLE_AMOUNT()",
        "mint()",
        "mint(uint256,address,uint256,uint256,bool)",
        "set_minter(address)",
        "crosschainMint(address,uint256)",
        "mint(address,uint96)",
        "mint(address,uint256,bytes32)",
        "yearlyMintRate()",
        "ERC4626ExceededMaxMint(address,uint256,uint256)",
        "removeMinter(address)",
        "mintingAllowedAfter()",
        "MINT_WAIT_PERIOD()",
        "MinterNotSet()",
        "maxMintOfYears(uint256)",
        "MINT()",
        "totalStakingMinted()",
        "mint(address,uint256)",
        "MINT_DELAY()",
        "NoPendingMinterChange()",
        "proposeMinter(address)",
        "addAdminAndMinterAndBurner(address)",
        "renounceAdminAndMinterAndBurner()",
        "setIssuer(address)",
        "getMinter(uint256)",
        "minimumTimeBetweenMints()",
        "mintInitialSupply(address)",
        "totalMintedSupply()",
        "changeMinter()",
        "minterApprove(address,uint256)",
        "mintingCurrentLimitOf(address)",
        "revokeMinterRole(address)",
        "getMinters()",
        "mint(uint256,address,uint256,uint256,bool,uint256,uint256,uint256)",
        "MINTER_BURNER_ROLE()",
        "mintRemaining()",
        "mintCap()",
        "minterChangeEffectiveAt()",
        "notifyMintingDone()",
        "finishMinting()",
        "MINT_BASE()",
        "generateTokens(address,uint256)",
        "acceptMinterAdmin()",
        "MINT_INTERVAL()",
        "minterAllowance(address)",
        "lastMintTimestamp()",
        "pendingMinter()",
        "mint(uint256,address)",
        "setUpMinter()",
        "addMinter(address)",
        "renounceMinter()",
        "MINT_CAP()",
        "updateMintRate(uint256)",
        "mint(uint256)",
        "decreaseMinterAllowance(address,uint256)",
        "minterAdmin()",
        "MintingClosed()",
        "isMinter(address)",
        "unpauseMinting()",
        "assignMinterRole(address)",
        "previewMint(uint256)",
        "nextMinting()",
        "NoMintableAmount()",
        "issueLockedTokens(address,uint256,uint256)",
        "increaseMinterAllowance(address,uint256)",
        "cancelMinter()",
        "initialMint(address)",
        "grantMintRole(address)",
        "mintInflation()",
        "grantMintAndBurnRoles(address)",
        "maxMint(address)",
        "selfMint(address,uint256,bytes)",
        "initialMinted()",
        "INITIAL_MINT()",
        "MINTING_PAUSER_ROLE()",
        "issue(uint256)",
        "pendingMinterAdmin()",
        "MINTER_ROLE()",
        "batchMint(address[],uint256[],uint256[])",
        "mintable_in_timeframe(uint256,uint256)",
        "pauseMinting()",
        "transferMinterAdmin(address)",
        "yearMint()",
        "mintAllocations((address,uint256,bytes32,bytes32)[])",
        "getMinterMembers()",
        "NotMinterAdmin()",
        "MINTING_INTERVAL()",
        "maxTotalMintedSupply()",
        "getMinter()",
        "minters(address)",
        "revokeMintRole(address)",
        "initialSupplyMinted()",
        "setMinter(address)",
    ],
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
        check("%s: no duplicate selector is pinned" % group,
              have is not None and len(set(have)) == len(have),
              "%d pinned, %d distinct" % (len(have or ()), len(set(have or ()))))
        check("%s: %d selectors match" % (group, len(sigs)), set(have or ()) == set(want),
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

    # Finding nothing must not read as finding nothing there. Measured against the labelling
    # oracle's own per-flag fields over 232 (contract, power) pairs drawn from 559 cached
    # contracts, the scan finds 62.5% of them as of W18 -- and its worst power is pause at
    # 52.6%, not mint at 55.1%. Both of those were wrong in this comment an hour after
    # tests/test_owner_power_recall.py was written to catch exactly that error in
    # src/risk.py: that test read one file, so the same mistake one file over was invisible.
    # It reads both now. So an empty list is a statement about the scan, and the payload has
    # to say which.
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


def test_a_power_is_matched_on_what_the_contract_dispatches():
    """A selector inside PUSH32 data is not a function the contract has.

    `powers` matched by substring over the whole bytecode: `"40c10f19" in body`. Four bytes
    is eight hex characters, and a 24 kB contract offers about 49,000 eight-character
    windows, none of which has to fall on an instruction boundary.

    Measured rather than assumed, twice, and the answer changed between the two runs -- which
    is the point of measuring after as well as before. With the old 23-selector list,
    substring and the opcode walk disagreed on **0 of 559** cached contracts, so switching
    would have been a fix for a problem that did not exist. With W18's 285-selector list they
    disagree on **1**: base 0x03587953... matches `c68d4283` inside code that is not a PUSH4,
    and the oracle does not confirm that power either. Recall is identical on all four flags,
    so the walk costs nothing and removes one false claim.

    It is also free. `_dispatched_selectors` is already called in `_powers_from_code` for
    `found_none`, so matching on its result rather than on the raw hex adds no work -- and it
    makes the two halves of that function agree about what "the contract has a function"
    means, which they did not before.

    The residual gap, stated because it is real: a compiler may push a selector whose leading
    bytes are zero as PUSH3 or PUSH2, and a binary-search dispatcher may not push it at all.
    Neither cost anything on this corpus -- the walk lost no hit the substring found -- but
    neither is impossible, and the direction of that failure is a MISS, which the disclosure
    already says nothing can be read into.
    """
    print(chr(10) + "[powers] matched on dispatch, not on any eight characters in the file")

    mint = "40c10f19"                                    # mint(address,uint256)
    assert mint in risk._OWNER_POWERS["can mint new supply"]

    # 0x7f is PUSH32: the next 32 bytes are data. A selector buried there is not a function.
    buried = "0x7f" + mint + "00" * 28 + "6318160ddd" + "00"   # 8+56 hex = PUSH32's 32 bytes
    r = risk._powers_from_code(buried)
    check("a selector inside PUSH32 data is not reported as a power",
          r and "can mint new supply" not in r["powers"], repr(r))
    check("and the real PUSH4 beside it is still seen",
          r and r["selectors_dispatched"] == 1, repr(r))

    # The same selector as an actual PUSH4 must still be found.
    real = "0x63" + mint + "00"
    r2 = risk._powers_from_code(real)
    check("the same selector dispatched IS reported as a power",
          r2 and r2["powers"] == ["can mint new supply"], repr(r2))

    # And in solc's CBOR trailer, which is data appended after the code.
    trailer = "a165" + "6276" + mint + "0033"            # a CBOR map holding the bytes
    body = "63" + "18160ddd" + "00" + trailer
    r3 = risk._powers_from_code("0x" + body + "%04x" % (len(trailer) // 2))
    check("a selector in the metadata trailer is not reported as a power",
          r3 and "can mint new supply" not in r3["powers"], repr(r3))


def test_a_forwarder_with_no_dispatcher_is_never_called_clean():
    """The same bug as EIP-1167, one variant down, found the same way.

    `test_minimal_and_slot_proxies_are_recognised` above fixed 53 EIP-1167 proxies that
    read `is_proxy=False` and then got the silent empty-powers treatment. It fixed them by
    pinning EIP-1167's exact 45 bytes. W18 mined PUSH4 selectors out of all 559 cached
    contracts and found **12 more** that dispatch no functions at all and still read
    `is_proxy=False` -- every one of them exactly 44 bytes:

        3d3d3d3d363d3d37363d73<20-byte address>5af43d3d93803e602a57fd5bf3

    That is the Solady/0age optimised clone: the same delegatecall forwarder as EIP-1167
    with the stack shuffling rewritten a byte shorter. `_EIP1167_PREFIX` and
    `_EIP1167_SUFFIX` are both full-body constants, so neither matched, and 12 contracts
    whose behaviour lives entirely at another address were reported as ordinary tokens
    with nothing found.

    So the fix here is deliberately NOT a third pinned constant. Two things:

    1. `is_proxy` keys on the delegatecall CORE both variants share -- a PUSH20 of an
       address followed by GAS DELEGATECALL -- rather than on the surrounding stack
       shuffling, which is the part that varies between forwarder generations.

    2. `found_none` additionally requires that a dispatcher was actually seen. A contract
       that dispatches no function selectors cannot be said to lack owner powers, whatever
       shape of forwarder it turns out to be. That is the structural half: the next variant
       nobody has written yet fails check 1 and still cannot produce a false clean bill.
    """
    print(chr(10) + "[proxy] a 44-byte forwarder is not a clean token")

    # A real one, from bench/cache_bytecode: base 0x020eaeee24bcad37cb9a01aa1f8c591c47341ba3
    clone = ("0x3d3d3d3d363d3d37363d73"
             "db7b520bb5c3a2c5d4871198081911359f93be87"
             "5af43d3d93803e602a57fd5bf3")
    r = risk._powers_from_code(clone)
    check("the 44-byte clone is recognised as a proxy", r and r["is_proxy"] is True,
          repr(r))
    check("and it is not reported as a contract with no powers",
          r and r["found_none"] is False, repr(r))

    # The structural half, tested independently of any proxy pattern: a contract that
    # dispatches nothing must not claim an absence, even when it is a shape nobody has a
    # name for.
    nondescript = "0x" + "60016002" * 8          # valid opcodes, no PUSH4, no delegatecall
    r2 = risk._powers_from_code(nondescript)
    check("a contract that dispatches no selectors is not called clean",
          r2 and r2["found_none"] is False, repr(r2))
    check("and it reports how many it dispatched, so the reason is visible",
          r2 and r2.get("selectors_dispatched") == 0, repr(r2))

    # And the guarantee runs the other way too: an ordinary token that DOES dispatch
    # functions, has none of the powers and is not a proxy still gets its clean reading.
    plain = "0x" + "63a9059cbb" + "6370a08231" + "6318160ddd" + "00"
    r3 = risk._powers_from_code(plain)
    check("a real token with no powers still reads found_none",
          r3 and r3["found_none"] is True, repr(r3))
    check("and its dispatched count is real", r3 and r3.get("selectors_dispatched") == 3,
          repr(r3))

    # The walk must not be fooled by a selector sitting inside another PUSH's immediate.
    # 0x7f is PUSH32: the 32 bytes after it are data, and the 0x63 inside them is not an
    # opcode. A naive scan for "63" reads a selector here; the walk must not.
    buried = "0x7f" + "63a9059cbb" + "00" * 27 + "00"
    r4 = risk._powers_from_code(buried)
    check("a selector buried in PUSH32 data is not counted as dispatched",
          r4 and r4.get("selectors_dispatched") == 0, repr(r4))


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


def test_selector_rejects_a_signature_it_cannot_compute():
    """A space silently produced a selector that matches nothing on any chain.

    `selector("mint(address, uint256)")` returned 36e59c31 against the correct 40c10f19 --
    no error, no warning, just four bytes that will never match a function anywhere. That
    is exactly the failure this module exists to prevent: the whole reason selectors are
    computed here rather than pinned by hand is so a typo cannot quietly become a wrong
    answer, and a typo was quietly becoming a wrong answer.

    It refuses rather than strips. A signature carrying a space is one somebody typed by
    hand, and the next hand-typed one may be wrong in a way stripping cannot repair.
    Refusing converts a silent wrong answer into a loud question.
    """
    print("\n[keccak] a signature we cannot compute is an error, not a guess")
    check("the canonical form still works",
          selector("mint(address,uint256)") == "40c10f19",
          selector("mint(address,uint256)"))
    for bad in ("mint(address, uint256)", " mint(address,uint256)",
                "mint(address,uint256) ", "mint(address,\tuint256)"):
        try:
            got = selector(bad)
            check("%r is refused" % bad, False, "returned %s" % got)
        except ValueError:
            check("%r is refused" % bad, True)


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
