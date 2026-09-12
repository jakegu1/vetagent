"""selector_mine.py -- where the owner-power selector list comes from, and it is not the oracle.

WHY THIS FILE EXISTS

W18. `src/risk.py` USED TO pin a hand-written list of 23 four-byte selectors for the four
powers that let an owner close the exit after you are in. Measured against the labelling
oracle's own per-flag fields, **that list** found 37% of the contracts that can pause, 26%
of those that can blacklist, 52% of those that can mint and **8%** of those that can change
the tax. Contracts name these functions in more ways than any list somebody typed will hold.

Those four figures are the BEFORE picture, said in the past tense because an audit pointed
out that they were not: a reader who ran this script saw 52.6 / 78.9 / 55.1 / 89.5 and had
no way to tell which set the header was describing. The current table is written by
`--write` into `bench/owner_powers.json` and printed by every run below.

The obvious fix is forbidden. Taking the contracts GoPlus flags, reading what functions
they have, and keeping the ones that correlate would lift recall immediately and **void the
benchmark** -- DECISIONS B2 holds GoPlus out as the oracle, and an engine tuned on the
oracle's labels cannot be scored against them. So the widening needs a source of function
names that is not the oracle.

THREE STEPS, AND NOT ONE OF THEM READS A LABEL

1. **PUSH4 extraction.** A Solidity dispatcher compares calldata's first four bytes against
   each selector it handles, pushing each as a PUSH4 immediate. Walking the bytecode as an
   opcode stream recovers very nearly the exact set of functions a contract dispatches.
   This is a fact about the bytecode. No label is involved.

2. **A public signature directory.** openchain.xyz maps a selector back to the Solidity
   signatures that hash to it, from contracts verified across public explorers. Cached in
   `bench/cache_selectors.json` and committed, so every later run is offline and free and
   a stranger gets the same answer.

3. **A pre-registered name rule.** Which signatures name which power, decided from the
   *text of the signature* and written down before this was measured. `--show-rule` prints
   it. The rule is public Solidity vernacular -- how token contracts name things -- and not
   a fact about any labelled set.

FOUR CONTROLS, BECAUSE STEP 3 IS WHERE A HONEST MISTAKE WOULD HIDE

- **Held-out split.** Contracts are split by MD5 of their address into `dev` and `holdout`.
  The rule was authored looking at `dev` names only, and the headline recall is reported on
  `holdout`. Both are printed. If they diverge, the rule was fitted and the honest number
  is the smaller one.

- **Recomputation.** Every selector admitted here must recompute from its signature through
  `bench/keccak.py`. openchain is a third party and a typo is silent; a selector that does
  not recompute is dropped, loudly.

- **A prevalence ceiling.** A selector that appears in most contracts is infrastructure,
  not a power. Prevalence is counted from bytecode, so this filter reads no label either.

- **An ERC-20 denylist, because the directory contains ground collisions.** openchain
  answers `40c10f19` with both `mint(address,uint256)` and `cat642998653(address,uint256)`
  -- someone ground the second to collide with the first, and both genuinely hash to those
  four bytes. If a ground name ever matches a power pattern while its selector is really
  `transfer`, this scan would flag every ERC-20 on earth. The standard surface is therefore
  refused by selector, before any pattern runs.

WHAT THE EXTRACTION PROVABLY MISSES

Cross-checked against a second PUSH4 extractor written independently, from the same spec and
without seeing this one. It returned the identical corpus figures -- 559 contracts, 2230
distinct selectors, median 21 per contract, 79 with none -- and identical zero-selector
accounting: 48 canonical 45-byte EIP-1167 proxies, the 12 44-byte 0age clones this project
had been reading as ordinary tokens, and 19 larger EIP-1967 proxies with a fallback and no
dispatcher. Two implementations agreeing is worth more than one implementation with a test.

It also measured three gaps, and they are recorded here because a scan whose blindness is
merely admitted is worth less than one whose blindness has a number:

- **Leading-zero selectors.** A selector whose top byte is zero is a small constant, and the
  compiler emits PUSH3, PUSH2 or PUSH1 for it. A PUSH4 walk cannot see those. Measured
  undercount on this corpus: 0.31% of dispatcher sites.

- **Selectors carried as the top four bytes of a PUSH32** (`sel << 224`). Numerically the
  largest gap: 213 of 559 contracts hold at least one, and 175 distinct four-byte values
  appear only in that form. It matters much less than it sounds, and that was checked rather
  than assumed -- all 19 sites that compare a shifted PUSH32 with EQ lie OUTSIDE their
  contract's dispatcher, so no dispatcher in this corpus is in that form. What the gap costs
  is outbound call selectors, not functions the contract answers to.

- **Jump-table dispatchers.** Vyper 0.3.10 and later, and hand-written assembly routers, can
  keep the selector table in a data blob and read it with CODECOPY, emitting no PUSH4 at all.
  This is **unmeasured**, not measured-as-zero: nothing in the corpus was identified as such
  a contract and no attempt was made to count them. An unobserved dimension.

Two smaller notes with teeth. `PUSH4 0xffffffff` is a bit mask and appears in 223 of 559
contracts -- the directory answers it with a ground-collision name, `LOCK8605463013()`, which
is exactly the trap `_ERC20_SURFACE` and the pattern rule exist to survive, and neither
admitted it. And `strip_metadata`'s refusal to strip without a CBOR header is load-bearing on
a real contract: Curve's CRV is metadata-less Vyper whose last two bytes are `0x00fd`, so a
length-only rule would cut 253 bytes of live code off the end of it.

WHAT THIS CANNOT SETTLE

Recall against GoPlus is not recall against reality, and a name is not a power: a contract
can hold `setFee(uint256)` and never have an owner able to call it. This raises the floor
under "we looked" -- it does not turn disclosure into detection, and E19 still applies.

Usage:
    python bench/selector_mine.py                 # offline, from the committed caches
    python bench/selector_mine.py --resolve        # fill the signature cache, then run
    python bench/selector_mine.py --show-rule      # print the pre-registered rule only
    python bench/selector_mine.py --emit           # print the list in src/risk.py's shape
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import risk  # noqa: E402
from keccak import selector as keccak_selector  # noqa: E402

CODE_CACHE = os.path.join(HERE, "cache_bytecode")
SIG_CACHE = os.path.join(HERE, "cache_selectors.json")

OPENCHAIN = "https://api.openchain.xyz/signature-database/v1/lookup?function="
BATCH = 200          # probed 2026-09-09: 800 answers in one request, 200 keeps URLs sane

# Distinguishes "the server did not answer for this selector" from "the server answered
# null, meaning it holds no entry". Both arrive as a falsy value from a plain dict.get,
# and reading them as one thing is the bug this module tripped over on its first run.
_MISSING = object()

# A selector in more than this share of the corpus is infrastructure every token carries,
# whatever it is called. Set from the measured shape of the distribution: the ERC-20 surface
# tops out at 74.4% -- which is 416 of 559, i.e. every contract that is not a forwarder --
# then owner() at 41.5%, and nothing power-shaped sits above about 20%.
#
# So this ceiling removes NOTHING today, and the run says so rather than leaving a zero to
# be read as either "working" or "never wired up". It is here because the ERC-20 denylist
# below is a list of selectors somebody thought of, and this is the filter that does not
# depend on having thought of them.
PREVALENCE_CEILING = 0.60

# The standard ERC-20 / Ownable surface, refused by SELECTOR before any name rule runs.
# openchain returns ground collisions -- signatures somebody brute-forced to hash to a
# well-known selector -- so a pattern match on a returned name is not proof that the
# selector means what the name says. These four bytes have a settled public meaning and
# nothing here may reclassify them.
_ERC20_SURFACE = {
    "a9059cbb": "transfer(address,uint256)",
    "23b872dd": "transferFrom(address,address,uint256)",
    "095ea7b3": "approve(address,uint256)",
    "dd62ed3e": "allowance(address,address)",
    "70a08231": "balanceOf(address)",
    "18160ddd": "totalSupply()",
    "313ce567": "decimals()",
    "95d89b41": "symbol()",
    "06fdde03": "name()",
    "8da5cb5b": "owner()",
    "715018a6": "renounceOwnership()",
    "f2fde38b": "transferOwnership(address)",
    "a457c2d7": "decreaseAllowance(address,uint256)",
    "39509351": "increaseAllowance(address,uint256)",
}


# The hand-written list as it stood before W18, with the signature of each selector, frozen
# here as a literal.
#
# Frozen rather than read from src/risk.py, because src/risk.py is what W18 changes. Read
# live, the "before" column of every table in this file would silently become the "after"
# column the moment the widening shipped, and the improvement this file exists to measure
# would become unquotable -- the same way the R12 negative result became unreproducible
# because nobody kept the instrument that produced it.
BASELINE = {
    "can pause transfers": (
        "pause()", "unpause()", "setPause(bool)", "setPaused(bool)", "pauseTrading()",
        "setTradingEnabled(bool)", "setTradingStatus(bool)"),
    "can blacklist addresses": (
        "blacklist(address)", "addBlackList(address)", "setBlacklist(address,bool)",
        "isBlackListed(address)", "setBots(address[],bool)", "setBlackList(address,bool)"),
    "can change the tax": (
        "setFee(uint256)", "setFees(uint256,uint256)", "setTaxes(uint256,uint256,uint256)",
        "setBuyTax(uint256)", "setSellTax(uint256)", "setTaxFeePercent(uint256)",
        "setSellFee(uint256)", "setBuyFee(uint256)"),
    "can mint new supply": ("mint(address,uint256)", "mint(uint256)"),
}


def baseline_selectors():
    """selector -> power, for the pre-W18 list. Computed, never pinned twice."""
    out = {}
    for power, sigs in BASELINE.items():
        for sig in sigs:
            out[keccak_selector(sig)] = power
    return out


# ---------------------------------------------------------------- 1. PUSH4 extraction

def strip_metadata(body):
    """Drop solc's CBOR trailer, which is data and not code.

    The last two bytes hold the trailer's length. Walking into it yields selectors that
    are really fragments of an IPFS hash, and they resolve to nothing -- so the damage is
    noise in the denominator rather than a wrong power, but the noise is large: the trailer
    is ~50 bytes of high-entropy data per contract and 0x63 appears in it constantly.

    Refuses to strip unless the result looks like CBOR (a map header, 0xa1-0xaf). A guess
    that quietly removed real code would be worse than not stripping.
    """
    if len(body) < 8:
        return body
    try:
        n = int(body[-4:], 16)
    except ValueError:
        return body
    end = len(body) - 4 - n * 2
    if n <= 0 or end <= 0:
        return body
    try:
        head = int(body[end:end + 2], 16)
    except ValueError:
        return body
    if 0xa1 <= head <= 0xaf:
        return body[:end]
    return body


def selectors_from_code(code, strip=True):
    """Every PUSH4 immediate, walking the opcode stream. Lowercase 8-char hex.

    The naive version -- find "63", take the next eight characters -- is wrong, and not
    marginally: 0x63 is a byte like any other inside the 32 arbitrary bytes of every
    PUSH32, and every contract is full of PUSH32. The walk skips each PUSH's immediate,
    so only real opcodes are read.
    """
    if not code:
        return set()
    body = code[2:] if code[:2].lower() == "0x" else code
    body = body.lower()
    if strip:
        body = strip_metadata(body)
    out = set()
    i = 0
    n = len(body)
    while i + 2 <= n:
        try:
            op = int(body[i:i + 2], 16)
        except ValueError:
            break
        i += 2
        if 0x60 <= op <= 0x7f:                      # PUSH1 .. PUSH32
            width = (op - 0x5f) * 2
            if op == 0x63 and i + width <= n:       # PUSH4
                out.add(body[i:i + width])
            i += width
    return out


def load_contracts():
    """Every cached contract. (chain, address, code)."""
    out = []
    if not os.path.isdir(CODE_CACHE):
        return out
    for name in sorted(os.listdir(CODE_CACHE)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(CODE_CACHE, name), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:                                    # noqa: BLE001
            continue
        code = d.get("code")
        if code and len(code) > 10:
            out.append((d.get("chain"), (d.get("address") or "").lower(), code))
    return out


# ---------------------------------------------------------------- 2. the directory

def load_sig_cache():
    """selector -> {"names": [...]} | {"names": []} | absent.

    Three states, deliberately, because two would collapse the distinction this project
    keeps breaking. `absent` means nobody asked. `"names": []` means the directory was
    asked and holds no entry -- which is a fact about the directory, not about the
    contract. Only a non-empty list is a resolution.
    """
    if not os.path.exists(SIG_CACHE):
        return {}
    try:
        with open(SIG_CACHE, encoding="utf-8") as f:
            return json.load(f).get("selectors") or {}
    except Exception:                                        # noqa: BLE001
        return {}


def save_sig_cache(cache):
    with open(SIG_CACHE, "w", encoding="utf-8") as f:
        json.dump({
            "source": "https://api.openchain.xyz/signature-database/v1/lookup",
            "note": ("Selector -> signature, from a public directory. An empty list means "
                     "the directory was asked and had no entry; a missing key means it was "
                     "never asked. Committed so this measurement replays offline."),
            "selectors": cache,
        }, f, indent=0, sort_keys=True)


def resolve(selectors, cache, verbose=True):
    """Ask the directory about every selector not already cached. Returns count fetched.

    A failed request leaves the key ABSENT rather than empty, so a rate limit can never be
    recorded as "the directory has no entry for this". That substitution is the single most
    repeated bug in this repository.
    """
    todo = sorted(s for s in selectors if s not in cache)
    if not todo:
        return 0
    got = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        url = OPENCHAIN + ",".join("0x" + s for s in chunk)
        try:
            req = urllib.request.Request(
                url, headers={"user-agent": "vetagent-bench/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:                               # noqa: BLE001
            if verbose:
                print("  batch %d-%d FAILED (%s) -- left unasked, not empty"
                      % (i, i + len(chunk), type(e).__name__))
            continue
        if not data.get("ok"):
            if verbose:
                print("  batch %d-%d answered not-ok -- left unasked" % (i, i + len(chunk)))
            continue
        answers = (data.get("result") or {}).get("function") or {}
        for sel in chunk:
            # `null` is how this directory says "I was asked and I hold no entry". A
            # MISSING KEY is how it would say nothing at all. The first version of this
            # loop read both as None and skipped both -- so 289 selectors the directory
            # had answered about were filed as never-asked, re-fetched on every run, and
            # reported as an unobserved dimension when they were an observed absence.
            # That is E11, in the function whose own docstring is about E11, written the
            # same afternoon. `_MISSING` exists so the two cannot collapse again.
            entries = answers.get("0x" + sel, _MISSING)
            if entries is _MISSING:
                continue                    # the server did not answer for this one
            entries = entries or []
            cache[sel] = {"names": [e.get("name") for e in entries if e.get("name")],
                          "verified": [e.get("name") for e in entries
                                       if e.get("name") and e.get("hasVerifiedContract")]}
            got += 1
        if verbose:
            print("  resolved %d/%d" % (min(i + BATCH, len(todo)), len(todo)))
    return got


# ---------------------------------------------------------------- 3. the rule

# THE PRE-REGISTERED RULE. Authored before any recall was measured, from how token
# contracts name things rather than from which contracts the oracle flags. Filled in from
# three independent drafts; see PREREG_NOTE.
PREREG_NOTE = """The rule below was written before any recall was measured, by three
independent drafts that never saw this corpus, the dataset, or the oracle's labels.

Each draft was given the four power names, told how a signature becomes a selector, and
told explicitly not to read bench/dataset.json, bench/cache_bytecode, bench/labels.py or
the pinned list in src/risk.py. Each was given a different lens on the same question:

  oz           the OpenZeppelin / audited tradition, and the USDT-family stablecoins
               whose blacklist and fee code is the most-copied in existence
  meme         the launchpad and bot-generated tradition -- Base and BSC tax tokens,
               SafeMoon derivatives, token-maker output -- which is where a mutable tax
               and a trading switch actually live
  adversarial  the author who wants the power and does not want it named obviously:
               trading gates named as enablement, blacklists named as bot protection

They converged, which is the useful part: all three reached `paus`, `black_?list`,
`bot`, `snipe`, `freeze`, a mutation verb before `fee|tax`, and bare `mint`. Where they
diverged, the divergence was informative rather than noise -- the adversarial draft was
the only one to notice that a bare `mint` pattern under re.I also matches `minTokens`,
`minTxAmount` and `minTradeAmount`, and it carried the exclusions to stop it.

Composed as the UNION of includes and the UNION of excludes, per power, taken verbatim.
No pattern here was added, removed or altered by anyone who had seen the corpus, and none
was chosen because it improved a number. Whether the composition is nonetheless overfitted
is not asserted -- it is measured, by reporting recall on a holdout half of the contracts
alongside the half the rule could conceivably have been influenced by.

Two patterns are worth flagging as PRE-REGISTERED RISKS rather than discovered later: the
pause rule admits a bare `trad`, and the blacklist rule a bare `bot`. Both are broad on
purpose -- the trading switch is the single most common way a Base token closes the exit,
and it is almost never called `pause` -- and both are the reason the precision column is
printed beside the recall column below. They were left exactly as drafted."""


RULE = {
    "can pause transfers": {
        "include": [
            re.compile(r"""pause""", re.I),   # oz
            re.compile(r"""trading|trade""", re.I),   # oz
            re.compile(r"""(enable|disable|allow|deny|set|toggle|open|close|start|stop|halt|resume|lock|unlock|block|restrict|activate|deactivate|suspend|freeze)[a-z0-9_]{0,20}transfer""", re.I),   # oz
            re.compile(r"""(enable|disable|allow|set|toggle|open|close|start|stop|halt|block|lock|activate)_?(sell|buy)""", re.I),   # oz
            re.compile(r"""(sell|buy)[a-z0-9_]{0,8}(enabled|allowed|status|active)""", re.I),   # oz
            re.compile(r"""launch|golive|go_live""", re.I),   # oz
            re.compile(r"""(global|all|total)freeze|freeze(all|transfer|trading|global)""", re.I),   # oz
            re.compile(r"""restriction""", re.I),   # oz
            re.compile(r"""paus""", re.I),   # meme
            re.compile(r"""^_{0,2}(enable|disable|set|unset|toggle|open|close|start|stop|begin|end|halt|resume|activate|deactivate|allow|disallow|unlock|lock|update|change|flip|switch|lift|freeze|unfreeze|block|unblock|restrict|suspend)_?(all_?|the_?)?(trad(e|es|ing)|transfer(s|ring)?|market|txn?|selling|buying|sales)""", re.I),   # meme
            re.compile(r"""(trad(e|es|ing)|transfer(s)?|market|txn?|buy(ing)?|sell(ing)?)_?(is)?_?(enabled?|active|allowed|open(ed)?|live|started|halted?|blocked?|locked?|frozen|restricted|status|state)""", re.I),   # meme
            re.compile(r"""^_{0,2}(set|start|do|is)?_?(launch|go_?live|liftoff|open_?market)""", re.I),   # meme
            re.compile(r"""trad""", re.I),   # adversarial
            re.compile(r"""(?:enable|disable|allow|disallow|block|unblock|halt|stop|resume|suspend|lock|unlock|freeze|unfreeze|toggle|open|close|activate|deactivate|can|restrict)_?(?:transfers?|sells?|selling|buys?|buying|contract)""", re.I),   # adversarial
            re.compile(r"""(?:set|update|change|is|get|has|toggle)_?(?:transfers?|sells?|selling|buys?|buying)_?(?:enabled|disabled|allowed|active|status|state|paused|locked|blocked|open|able|on|off)""", re.I),   # adversarial
            re.compile(r"""launch""", re.I),   # adversarial
            re.compile(r"""^(?:transfers?|sells?|selling|buys?|buying|trading|trade)_?(?:enabled|disabled|allowed|active|open|status|paused|locked|blocked|able|lock)""", re.I),   # adversarial
        ],
        "exclude": [
            re.compile(r"""^(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|renounceownership|transferownership|permit|nonces|increaseallowance|decreaseallowance)$""", re.I),   # oz
            re.compile(r"""fee|tax|slippage|commission""", re.I),   # oz
            re.compile(r"""buyback|buy_back|buysback""", re.I),   # oz
            re.compile(r"""max|min(tx|imum|buy|sell|amount|hold|swap|token)|limit|amount|threshold|percent|delay|cooldown|holding|multiplier""", re.I),   # oz
            re.compile(r"""swapback|swaptokens|swapthreshold""", re.I),   # oz
            re.compile(r"""^_{0,2}(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|getowner|renounceownership|transferownership|increaseallowance|decreaseallowance|permit|nonces|version)$""", re.I),   # meme
            re.compile(r"""fee|tax|percent|commission|slippage""", re.I),   # meme
            re.compile(r"""max|min|limit|amount|threshold|cooldown|delay|timer|time""", re.I),   # meme
            re.compile(r"""wallet|receiver|recipient""", re.I),   # meme
            re.compile(r"""fee""", re.I),   # adversarial
            re.compile(r"""tax""", re.I),   # adversarial
            re.compile(r"""multiplier""", re.I),   # adversarial
            re.compile(r"""delay""", re.I),   # adversarial
            re.compile(r"""cool_?down""", re.I),   # adversarial
            re.compile(r"""max""", re.I),   # adversarial
            re.compile(r"""limit""", re.I),   # adversarial
            re.compile(r"""amount""", re.I),   # adversarial
            re.compile(r"""threshold""", re.I),   # adversarial
            re.compile(r"""percent""", re.I),   # adversarial
            re.compile(r"""buy_?back""", re.I),   # adversarial
            re.compile(r"""price""", re.I),   # adversarial
            re.compile(r"""wallet""", re.I),   # adversarial
            re.compile(r"""receiv""", re.I),   # adversarial
            re.compile(r"""recipient""", re.I),   # adversarial
            re.compile(r"""dividend""", re.I),   # adversarial
            re.compile(r"""reward""", re.I),   # adversarial
            re.compile(r"""exclu""", re.I),   # adversarial
            re.compile(r"""exempt""", re.I),   # adversarial
            re.compile(r"""white_?list""", re.I),   # adversarial
            re.compile(r"""volume""", re.I),   # adversarial
            re.compile(r"""snapshot""", re.I),   # adversarial
        ],
    },
    "can blacklist addresses": {
        "include": [
            re.compile(r"""black_?list|blocklist|block_?list|deny_?list|ban_?list|black_?address|black_?wallet|black_?funds|black_?account""", re.I),   # oz
            re.compile(r"""(add|set|del|remove|un|is|manage|mark|multi|update|enable|disable|force|block|ban|check|kill)[a-z0-9_]{0,8}bots?""", re.I),   # oz
            re.compile(r"""anti_?bot|bots?_?(list|address|wallet|protection|mode)|^bots?$""", re.I),   # oz
            re.compile(r"""snipe""", re.I),   # oz
            re.compile(r"""freeze|frozen|unfreeze""", re.I),   # oz
            re.compile(r"""ban(ned|list)|(un)?ban(address|wallet|account|user)|^un?ban$|setban|isban""", re.I),   # oz
            re.compile(r"""(is|set|add|un|remove|update|toggle|mark)[a-z0-9_]{0,8}(blocked|restricted)""", re.I),   # oz
            re.compile(r"""lock(address|wallet|account|holder)""", re.I),   # oz
            re.compile(r"""(black|block|deny|ban|bad|blk)_?list""", re.I),   # meme
            re.compile(r"""bot""", re.I),   # meme
            re.compile(r"""freeze|frozen|unfreeze|thaw""", re.I),   # meme
            re.compile(r"""^_{0,2}(set|is|get|add|remove|un|update|mark|flag|toggle|multi|bulk)?_?(un)?ban(ned|s)?($|_|address|account|wallet|user|list|status|from)""", re.I),   # meme
            re.compile(r"""restrict""", re.I),   # meme
            re.compile(r"""block(ed)?_?(address|account|wallet|user|holder|status)|^_{0,2}(set|is|get|un|add|remove)?_?block(ed)?$""", re.I),   # meme
            re.compile(r"""lock(ed)?_?(address|account|wallet|user|holder)|(address|account|wallet|user|holder)_?(un)?lock""", re.I),   # meme
            re.compile(r"""law_?enforcement""", re.I),   # meme
            re.compile(r"""destroy_?black|wipe_?frozen|seize|confiscate""", re.I),   # meme
            re.compile(r"""black_?(?:list|funds)""", re.I),   # adversarial
            re.compile(r"""bots?""", re.I),   # adversarial
            re.compile(r"""snip""", re.I),   # adversarial
            re.compile(r"""deny|denied|deny_?list|ban_?list|block_?list|gr[ae]y_?list""", re.I),   # adversarial
            re.compile(r"""(?:^|set|is|un|add|del|remove|update|toggle|get)ban(?:ned|s)?(?:$|address|account|wallet|user|list|bots?)""", re.I),   # adversarial
            re.compile(r"""frozen""", re.I),   # adversarial
            re.compile(r"""^(?:un)?freeze$""", re.I),   # adversarial
            re.compile(r"""freez\w*?(?:account|address|wallet|user|holder|funds|balance)""", re.I),   # adversarial
            re.compile(r"""(?:un)?block(?:ed)?_?(?:list|address|account|wallet|user|holder|bots?|snipers?)""", re.I),   # adversarial
            re.compile(r"""(?:un)?lock(?:ed)?_?(?:address|account|wallet|user|holder)""", re.I),   # adversarial
        ],
        "exclude": [
            re.compile(r"""^(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|renounceownership|transferownership|permit|nonces|increaseallowance|decreaseallowance)$""", re.I),   # oz
            re.compile(r"""white_?list|allow_?list""", re.I),   # oz
            re.compile(r"""blocknumber|blocktimestamp|perblock|blockreward|blocksper|deadblock""", re.I),   # oz
            re.compile(r"""^_{0,2}(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|getowner|renounceownership|transferownership|increaseallowance|decreaseallowance|permit|nonces|version)$""", re.I),   # meme
            re.compile(r"""whitelist|allow_?list""", re.I),   # meme
            re.compile(r"""trad(e|es|ing)|market|swap""", re.I),   # meme
            re.compile(r"""liquid|lp_?token|time_?lock|unlock_?time|lock_?duration""", re.I),   # meme
            re.compile(r"""(freeze|frozen|unfreeze|thaw|lock|block|restrict|suspend|halt)_?(all_?)?(transfer|token_?transfer|sell|buy)""", re.I),   # meme
            re.compile(r"""both""", re.I),   # adversarial
            re.compile(r"""robot""", re.I),   # adversarial
            re.compile(r"""white_?list""", re.I),   # adversarial
            re.compile(r"""fee""", re.I),   # adversarial
            re.compile(r"""tax""", re.I),   # adversarial
            re.compile(r"""reward""", re.I),   # adversarial
            re.compile(r"""dividend""", re.I),   # adversarial
        ],
    },
    "can change the tax": {
        "include": [
            re.compile(r"""(set|update|change|modify|adjust|edit|reduce|raise|lower|increase|decrease|remove|clear|reset|enable|disable|amend|revise|toggle|switch|manage|config|configure|apply|renew|new|force|init)[a-z0-9_]{0,24}(fee|tax|slippage|commission|royalt)""", re.I),   # oz
            re.compile(r"""(set|update|change|adjust|modify)_?(sell|buy|tax|fee)_?multiplier""", re.I),   # oz
            re.compile(r"""(set|update|change|adjust|modify|reduce|remove)[a-z0-9_]{0,12}burn_?(rate|percent|fee)""", re.I),   # oz
            re.compile(r"""^_{0,2}(set|update|change|modify|adjust|edit|configure|config|reduce|increase|decrease|raise|lower|remove|restore|apply|assign|manage|new|enable|disable|toggle|switch|reset)_?[a-z0-9_]{0,24}(fees?|taxe?s?|taxation|commission|royalt(y|ies)|basis_?points?|bps|slippage)""", re.I),   # meme
            re.compile(r"""^_{0,2}(fees?|taxe?s?)_?(set|update|change|modify|adjust)""", re.I),   # meme
            re.compile(r"""^_{0,2}set_?params$""", re.I),   # meme
            re.compile(r"""(?:set|update|change|adjust|modify|edit|alter|reset|remove|increase|decrease|raise|lower|reduce|enable|disable|toggle|switch|apply|configure|manage)\w*?(?:fee|tax|slippage|commission|royalt|toll)""", re.I),   # adversarial
            re.compile(r"""(?:sell|buy|transfer|final|launch)_?(?:tax|fee)?_?multiplier""", re.I),   # adversarial
            re.compile(r"""(?:set|update|change|adjust|modify|increase|decrease|raise|lower|reduce)\w*?(?:burnrate|taxrate|feerate|burnpercent)""", re.I),   # adversarial
        ],
        "exclude": [
            re.compile(r"""^(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|renounceownership|transferownership|permit|nonces|increaseallowance|decreaseallowance)$""", re.I),   # oz
            re.compile(r"""exclud|exempt|include_?in|white_?list|allow_?list""", re.I),   # oz
            re.compile(r"""wallet|receiver|recipient|collector|distributor|holder|address|addr|account|beneficiar""", re.I),   # oz
            re.compile(r"""threshold|swaptokens|atamount|swapback|buyback|buy_back|feed""", re.I),   # oz
            re.compile(r"""^_{0,2}(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|getowner|renounceownership|transferownership|increaseallowance|decreaseallowance|permit|nonces|version)$""", re.I),   # meme
            re.compile(r"""exclud|includ|exempt|whitelist|allow_?list|no_?fee|fee_?free|tax_?free""", re.I),   # meme
            re.compile(r"""receiver|recipient|collector|fee_?to|wallet|address$|_address|distributor""", re.I),   # meme
            re.compile(r"""swap_?tokens_?at|num_?tokens|threshold""", re.I),   # meme
            re.compile(r"""exclu""", re.I),   # adversarial
            re.compile(r"""exempt""", re.I),   # adversarial
            re.compile(r"""white_?list""", re.I),   # adversarial
            re.compile(r"""wallet""", re.I),   # adversarial
            re.compile(r"""address""", re.I),   # adversarial
            re.compile(r"""receiv""", re.I),   # adversarial
            re.compile(r"""recipient""", re.I),   # adversarial
            re.compile(r"""collector""", re.I),   # adversarial
            re.compile(r"""treasur""", re.I),   # adversarial
            re.compile(r"""destination""", re.I),   # adversarial
            re.compile(r"""distribut""", re.I),   # adversarial
            re.compile(r"""claim""", re.I),   # adversarial
            re.compile(r"""withdraw""", re.I),   # adversarial
            re.compile(r"""balance""", re.I),   # adversarial
            re.compile(r"""holder""", re.I),   # adversarial
        ],
    },
    "can mint new supply": {
        "include": [
            re.compile(r"""mint""", re.I),   # oz
            re.compile(r"""issue""", re.I),   # oz
            re.compile(r"""(increase|expand|add|set|update|new|change|modify|raise|grow|adjust|create|inflate)[a-z0-9_]{0,12}supply""", re.I),   # oz
            re.compile(r"""inflate""", re.I),   # oz
            re.compile(r"""^_{0,2}(re)?issue""", re.I),   # meme
            re.compile(r"""^_{0,2}(increase|expand|add|inflate|raise|grow|set|update|change|adjust|bump|extend)_?(the_?)?(total|max|maximum|token|circulating|new)?_?supply""", re.I),   # meme
            re.compile(r"""^_{0,2}(set|update|change|raise|increase|lift|remove|extend)_?(the_?)?(max|maximum|hard|supply|token|mint)?_?cap""", re.I),   # meme
            re.compile(r"""rebase""", re.I),   # meme
            re.compile(r"""^_{0,2}(create|generate|print)_?(new_?)?(token|tokens|coin|coins|supply|money)""", re.I),   # meme
            re.compile(r"""(?:set|update|increase|add|expand|inflate|change|adjust|raise|grow|modify|create)\w*?supply""", re.I),   # adversarial
            re.compile(r"""(?:set|update|change|write|force|adjust|modify)_?balances?""", re.I),   # adversarial
        ],
        "exclude": [
            re.compile(r"""^(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|renounceownership|transferownership|permit|nonces|increaseallowance|decreaseallowance)$""", re.I),   # oz
            re.compile(r"""^(?!.*(mint|issue)).*(max_?supply|supply_?cap|cap_?supply)""", re.I),   # oz
            re.compile(r"""min(tx|time|transfer|threshold|trade|tax|hold|swap|amount|balance|period|delay|gas|liquidity|eth|bnb)""", re.I),   # oz
            re.compile(r"""mintokens?(before|to|for|balance|swap|amount|at)""", re.I),   # oz
            re.compile(r"""circulating|^getsupply$""", re.I),   # oz
            re.compile(r"""^_{0,2}(transfer|transferfrom|approve|allowance|balanceof|totalsupply|decimals|symbol|name|owner|getowner|renounceownership|transferownership|increaseallowance|decreaseallowance|permit|nonces|version)$""", re.I),   # meme
            re.compile(r"""^_{0,2}(cap|max_?supply|maximum_?supply|total_?supply|circulating_?supply|supply|get_?supply|remaining_?supply)$""", re.I),   # meme
            re.compile(r"""^_{0,2}(burn|redeem|destroy)(from|tokens?|s)?$""", re.I),   # meme
            re.compile(r"""capacit|capital""", re.I),   # meme
            re.compile(r"""airdrop""", re.I),   # adversarial
            re.compile(r"""distribut""", re.I),   # adversarial
            re.compile(r"""^balanceof$""", re.I),   # adversarial
            re.compile(r"""^totalsupply$""", re.I),   # adversarial
            re.compile(r"""min_?tokens?""", re.I),   # adversarial
            re.compile(r"""min_?tx""", re.I),   # adversarial
            re.compile(r"""min_?time""", re.I),   # adversarial
            re.compile(r"""min_?transfer""", re.I),   # adversarial
            re.compile(r"""min_?trade""", re.I),   # adversarial
            re.compile(r"""min_?total""", re.I),   # adversarial
            re.compile(r"""min_?threshold""", re.I),   # adversarial
            re.compile(r"""min_?balance""", re.I),   # adversarial
            re.compile(r"""min_?holding""", re.I),   # adversarial
            re.compile(r"""min_?amount""", re.I),   # adversarial
        ],
    },
}

# Signatures all three drafts named outright, kept only so a reader can see what the
# rule was aiming at. Nothing is admitted from this list: admission runs through the
# patterns above and the four gates in candidates(), or it does not happen.
PREREG_EXAMPLES = {
    "can pause transfers": (
        "PAUSER_ROLE()",
        "enableTrading()",
        "launch()",
        "openTrading()",
        "pause()",
        "paused()",
        "setPause(bool)",
        "setPaused(bool)",
        "setTradingEnabled(bool)",
        "setTradingStatus(bool)",
        "startTrading()",
        "tradingActive()",
        "tradingEnabled()",
        "tradingOpen()",
        "transfersEnabled()",
        "unpause()",
    ),
    "can blacklist addresses": (
        "_isBlacklisted(address)",
        "addBlackList(address)",
        "addToBlacklist(address)",
        "blacklist(address)",
        "blacklister()",
        "bots(address)",
        "delBots(address[])",
        "destroyBlackFunds(address)",
        "freeze(address)",
        "freezeAccount(address,bool)",
        "getBlackListStatus(address)",
        "isBlackListed(address)",
        "isBlacklisted(address)",
        "isFrozen(address)",
        "removeBlackList(address)",
        "removeFromBlacklist(address)",
        "setBots(address[])",
        "setBots(address[],bool)",
        "unBlacklist(address)",
        "unfreeze(address)",
        "updateBlacklister(address)",
        "wipeFrozenAddress(address)",
    ),
    "can change the tax": (
        "changeFee(uint256)",
        "setBothFees(uint256,uint256)",
        "setBurnFee(uint256)",
        "setBuyFee(uint256)",
        "setBuyTax(uint256)",
        "setDevFee(uint256)",
        "setFee(uint256)",
        "setFees(uint256,uint256)",
        "setLiquidityFeePercent(uint256)",
        "setMarketingFee(uint256)",
        "setParams(uint256,uint256)",
        "setSellFee(uint256)",
        "setSellMultiplier(uint256)",
        "setSellTax(uint256)",
        "setTax(uint256)",
        "setTaxFee(uint256)",
        "setTaxFeePercent(uint256)",
        "setTaxRate(uint256)",
        "setTaxes(uint256,uint256)",
        "setTotalFees(uint256)",
        "updateFee(uint256)",
    ),
    "can mint new supply": (
        "MINTER_ROLE()",
        "addMinter(address)",
        "configureMinter(address,uint256)",
        "finishMinting()",
        "increaseSupply(uint256)",
        "isMinter(address)",
        "issue(uint256)",
        "masterMinter()",
        "mint(address,uint256)",
        "mint(uint256)",
        "mintTo(address,uint256)",
        "minterAllowance(address)",
        "mintingFinished()",
        "removeMinter(address)",
        "setBalance(address,uint256)",
        "setMaxSupply(uint256)",
        "setMintable(bool)",
        "setMinter(address)",
    ),
}


# AMENDMENT, 2026-09-09, stated here rather than folded quietly into the rule above.
#
# The pre-registered rule for "can pause transfers" admitted 72 selectors, and reading them
# showed it had caught two different powers under one name:
#
#   pause(), unpause(), paused(), EnforcedPause(), PAUSER_ROLE(), setPaused(bool),
#   transfersEnabled(), MODE_TRANSFER_RESTRICTED(), setTransferState(bool)
#   enableTrading(), openTrading(), launch(), launched(), tradingActive(), startTrading()
#
# The second row is not a pause switch. It is a trading gate, and it is the commonest way a
# Base token closes the exit -- but telling a user "the owner can pause transfers" about a
# contract whose only such function is `launch()` is a FALSE STATEMENT, not a bucketing
# nicety. That is the reason for the split, and it is why the split survives the test this
# project applies to any change made after seeing a result: would I have made it if the
# numbers had come out the other way? Yes. It fixes a sentence, and it moves no recall --
# the same selectors are admitted either way, under two names instead of one.
#
# It also corrects an interpretation. Measured against GoPlus's `transfer_pausable`, the
# combined category showed 87 claims against 14 agreements, which reads like poor precision
# and mostly is not: `transfer_pausable` is a field about a pause function, and the oracle
# has NO field for a trading gate. An unobserved dimension, not an observed disagreement.
# After the split the pause figure can be compared to the oracle and the trading figure
# cannot -- so the trading one is reported with no agreement column at all, rather than with
# a column that would read as precision.
_PAUSE_PROPER = re.compile(r"paus|transfer|restrict", re.I)
_TRADING_GATE = re.compile(r"trad|launch|market|golive|go_?live|open|close", re.I)


def _split_pause(name):
    """Which of the two the name belongs to. Pause wins ties: pauseTrading() is a pause."""
    if _PAUSE_PROPER.search(name):
        return "can pause transfers"
    if _TRADING_GATE.search(name):
        return "can halt trading"
    return "can pause transfers"


def function_name(signature):
    """The text before the open paren. The rule matches names, never argument lists."""
    return (signature or "").split("(")[0]


def classify(signature):
    """Which power this signature names, or None. Pure text, no corpus, no label."""
    name = function_name(signature)
    if not name:
        return None
    for power, spec in RULE.items():
        if any(p.search(name) for p in spec["exclude"]):
            continue
        if any(p.search(name) for p in spec["include"]):
            return _split_pause(name) if power == "can pause transfers" else power
    return None


# ---------------------------------------------------------------- the split

def split_of(address):
    """dev or holdout, from MD5 of the address. Stable, and nothing to do with any label."""
    h = hashlib.md5((address or "").encode("utf-8")).hexdigest()
    return "dev" if int(h[:2], 16) < 128 else "holdout"


def candidates(cache, prevalence, n_contracts):
    """Selectors the rule admits, per power, each with the signature that admitted it.

    Four gates, and every one of them reads bytecode or text -- never a label.

    1. The name rule above.
    2. Recomputation. openchain is a third party; a signature that does not hash to the
       selector it was returned for is dropped and counted. This is also what stops a
       ground collision from being admitted under a name it does not really have.
    3. The ERC-20 surface, refused by selector before the rule runs.
    4. A prevalence ceiling. Reported even when it removes nothing, because a guard that
       silently carries nothing looks the same as a guard that is working.
    """
    out = {p: {} for p in RULE}
    out["can halt trading"] = {}          # the amendment's category; see _split_pause
    dropped = {"erc20_surface": [], "did_not_recompute": [], "too_prevalent": []}
    for sel, entry in sorted(cache.items()):
        names = (entry or {}).get("names") or []
        if not names:
            continue
        if sel in _ERC20_SURFACE:
            for sig in names:
                if classify(sig):
                    dropped["erc20_surface"].append((sel, sig))
            continue
        share = prevalence.get(sel, 0) / float(n_contracts or 1)
        # Prefer a signature from a verified contract: the directory also holds names
        # somebody ground to collide with a well-known selector, and those are unverified.
        ordered = ((entry.get("verified") or []) +
                   [x for x in names if x not in (entry.get("verified") or [])])
        for sig in ordered:
            power = classify(sig)
            if not power:
                continue
            try:
                recomputed = keccak_selector(sig)
            except Exception:                                # noqa: BLE001
                dropped["did_not_recompute"].append((sel, sig))
                break
            if recomputed != sel:
                dropped["did_not_recompute"].append((sel, sig))
                break
            if share > PREVALENCE_CEILING:
                dropped["too_prevalent"].append((sel, sig))
                break
            out[power][sel] = sig
            break
    return out, dropped


def _flags_by_contract():
    """The oracle's per-flag fields, for SCORING ONLY -- never for choosing a selector.

    This is the only place in this file that touches a label, it happens strictly after
    `candidates()` has closed, and it is the same use `bench/owner_powers_measure.py`
    already makes of them: measuring what the scan misses. B2 forbids wiring the oracle
    into the engine; it does not forbid scoring the engine against it.
    """
    path = os.path.join(HERE, "dataset.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        tokens = json.load(f).get("tokens") or []
    out = {}
    for t in tokens:
        raw = t.get("goplus_raw") or {}
        if raw:
            out[((t.get("chain") or "").lower(), (t.get("address") or "").lower())] = raw
    return out


FLAG_TO_POWER = {
    "transfer_pausable": "can pause transfers",
    "is_blacklisted": "can blacklist addresses",
    "slippage_modifiable": "can change the tax",
    "is_mintable": "can mint new supply",
}


def wilson(hits, n, z=1.96):
    """95% Wilson interval as (low, high) percentages. Small denominators are the story."""
    if not n:
        return (0.0, 100.0)
    p = float(hits) / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, centre - half) * 100.0, min(1.0, centre + half) * 100.0)


def measure(per_contract, admitted, flags):
    # (docstring below; the two columns come from _recall_rows so they cannot diverge)
    """Recall of the shipped list and of the mined list, on dev and on holdout.

    The split is the control on the rule. Patterns were authored against Solidity naming
    in general and, where a corpus was consulted at all, against `dev`. If holdout recall
    comes in materially below dev recall, the rule was fitted and the honest number is
    holdout's. Both are printed; neither is chosen after the fact.
    """
    final = final_list(admitted)
    mined = {p: set(sels) for p, sels in final.items()}
    base = baseline_selectors()

    # The amendment's category, reported on its own because the oracle has no field for it.
    gate = mined.get("can halt trading") or set()
    if gate:
        n_gate = sum(1 for k in per_contract if per_contract[k] & gate)
        print()
        print("can halt trading: %d of %d contracts (%.1f%%) name a trading gate."
              % (n_gate, len(per_contract), 100.0 * n_gate / len(per_contract)))
        print("  Deliberately printed with NO agreement column. GoPlus has no field for a")
        print("  trading gate, so any number in that column would be a comparison against")
        print("  a question the oracle was never asked -- which is the substitution this")
        print("  project keeps paying for. It is unmeasured, not zero.")
    print()
    print("%-24s %-6s %5s %9s %9s" % ("power (GoPlus flag)", "split", "n",
                                      "baseline", "mined"))
    print("-" * 62)
    for flag, power, split, n, hs, hm in _recall_rows(per_contract, admitted, flags):
        if not n:
            print("%-24s %-6s %5d %9s %9s" % (flag, split, 0, "-", "-"))
            continue
        lo, hi = wilson(hm, n)
        print("%-24s %-6s %5d %8.1f%% %8.1f%%   (95%% %.0f-%.0f%%)"
              % (flag, split, n, 100.0 * hs / n, 100.0 * hm / n, lo, hi))
    print()
    print("The other direction: contracts we would claim the power for, and how many of")
    print("those the oracle also flags. A selector match is a function that exists, so a")
    print("disagreement here is not necessarily our error -- but it is the number that")
    print("decides whether W17 can ever score this, so it is printed beside the recall.")
    print("%-24s %-6s %14s %14s" % ("power", "list", "we claim", "oracle agrees"))
    print("-" * 62)
    for flag, power in sorted(FLAG_TO_POWER.items()):
        shipped_sels = set(s for s, p in base.items() if p == power)
        for label, sels in (("baseline", shipped_sels),
                            ("mined", mined.get(power, set()))):
            ours = [k for k in per_contract if per_contract[k] & sels]
            agree = [k for k in ours
                     if str((flags.get(k) or {}).get(flag) or "0") == "1"]
            print("%-24s %-6s %14d %14d" % (power, label, len(ours), len(agree)))


def _recall_rows(per_contract, admitted, flags):
    """(flag, power, n, shipped_hits, mined_hits) per flag and split, plus the pool."""
    final = final_list(admitted)
    mined = {p: set(sels) for p, sels in final.items()}
    base = baseline_selectors()
    out = []
    for flag, power in sorted(FLAG_TO_POWER.items()):
        shipped_sels = set(s for s, p in base.items() if p == power)
        for split in ("dev", "holdout", "both"):
            have = [k for k in per_contract
                    if str((flags.get(k) or {}).get(flag) or "0") == "1"
                    and (split == "both" or split_of(k[1]) == split)]
            hs = sum(1 for k in have if per_contract[k] & shipped_sels)
            hm = sum(1 for k in have if per_contract[k] & mined.get(power, set()))
            out.append((flag, power, split, len(have), hs, hm))
    return out


def report_union_and_pool(per_contract, admitted, flags):
    """Two numbers the per-flag table cannot show, and both matter.

    The UNION line, because the split of the pause category is honest about naming and
    slightly dishonest about mechanism: a trading gate is frequently how a transfer pause
    is *implemented*, so four of the nineteen contracts the oracle calls pausable are found
    only through a trading-gate name. Reporting pause-proper alone understates what the scan
    sees; reporting the union alone would overstate what the disclosure says. Both, then.

    The POOLED line, because it is the figure quoted outward -- "the scan finds N% of the
    powers the oracle asserts" -- and it was hand-computed and went stale twice.
    """
    mined = {p: set(sels) for p, sels in final_list(admitted).items()}
    pause = mined.get("can pause transfers", set())
    gate = mined.get("can halt trading", set())
    have = [k for k in per_contract
            if str((flags.get(k) or {}).get("transfer_pausable") or "0") == "1"]
    only_pause = sum(1 for k in have if per_contract[k] & pause)
    union = sum(1 for k in have if per_contract[k] & (pause | gate))
    print()
    print("transfer_pausable, pause-proper only : %d of %d = %.1f%%"
          % (only_pause, len(have), 100.0 * only_pause / len(have) if have else 0))
    print("transfer_pausable, incl trading gates: %d of %d = %.1f%%"
          % (union, len(have), 100.0 * union / len(have) if have else 0))
    print("  A trading gate is often how a transfer pause is implemented, so the second")
    print("  number is what the scan SEES and the first is what the disclosure SAYS.")

    rows = [r for r in _recall_rows(per_contract, admitted, flags) if r[2] == "both"]
    n = sum(r[3] for r in rows)
    hs = sum(r[4] for r in rows)
    hm = sum(r[5] for r in rows)
    print()
    print("POOLED over all four oracle flags: shipped %d of %d = %.1f%%, "
          "mined %d of %d = %.1f%% (IN-SAMPLE)"
          % (hs, n, 100.0 * hs / n if n else 0, hm, n, 100.0 * hm / n if n else 0))
    return {"n": n, "shipped_hits": hs, "mined_hits": hm,
            "shipped_pct": "%.1f" % (100.0 * hs / n if n else 0),
            "mined_pct": "%.1f" % (100.0 * hm / n if n else 0),
            "pausable_pause_only_pct": "%.1f" % (100.0 * only_pause / len(have)
                                                 if have else 0),
            "pausable_with_gates_pct": "%.1f" % (100.0 * union / len(have) if have else 0)}


def cross_fit(per_contract, cache, flags):
    """Recall on contracts the miner has not seen. The number a caller's token deserves.

    **The published 62.5% was in-sample and nobody noticed for three days.** The list is
    mined from all 559 cached contracts and then scored on those same 559, so it has already
    seen every contract it is graded on. 193 of the 285 shipped selectors occur in exactly
    ONE corpus contract: they are not a rule about how Solidity names things, they are a
    memory of a specific token.

    The dev/holdout split above does not catch this and was never able to. It holds out
    LABELS, so it can detect a name rule fitted to the oracle's answers -- and it correctly
    reported none. It cannot hold out the BYTECODE the universe was built from, which is the
    thing that leaks. `selector_mine.py` said "the split is the control on the rule", and
    that was true and insufficient: the rule was controlled, the universe was not.

    So: split the corpus in two by address hash, mine a list from each half using only that
    half's bytecode, and score each half with the list mined from the other. Identical
    pipeline, identical gates, identical name rule -- only the universe shrinks, which is
    exactly what happens to a stranger's contract.

    Measured 2026-09-12, and the tax figure is the one that matters:

        flag                   n    in-sample    out-of-sample
        slippage_modifiable   38        89.5%            31.6%
        is_blacklisted        19        78.9%            63.2%
        transfer_pausable     19        52.6%            47.4%
        is_mintable          156        55.1%            53.2%
        pooled               232        62.5%            50.0%

    The residual biases run OPTIMISTIC, so 50.0% is a ceiling on the honest number rather
    than a floor: `final_list()` still injects the full 23-selector baseline into every
    cross-fit list, the prevalence ceiling removes nothing, and the ERC-20 denylist is a
    fixed standard rather than something derived from the corpus. The one pessimistic
    source -- training on about 280 contracts instead of 559 -- is worth under a point.
    """
    keys = sorted(per_contract)
    halves = {"dev": [], "holdout": []}
    for k in keys:
        halves[split_of(k[1])].append(k)

    mined = {}
    for name, training in halves.items():
        sub_prev = {}
        for k in training:
            for sel in per_contract[k]:
                sub_prev[sel] = sub_prev.get(sel, 0) + 1
        sub_cache = {sel: cache[sel] for sel in sub_prev if sel in cache}
        admitted, _ = candidates(sub_cache, sub_prev, len(training))
        mined[name] = final_list(admitted)

    out = {}
    tot_n = tot_hit = 0
    for flag, power in sorted(FLAG_TO_POWER.items()):
        hit = n = 0
        for scored, trained_on in (("dev", "holdout"), ("holdout", "dev")):
            sels = set(mined[trained_on].get(power) or {})
            have = [k for k in halves[scored]
                    if str((flags.get(k) or {}).get(flag) or "0") == "1"]
            hit += sum(1 for k in have if per_contract[k] & sels)
            n += len(have)
        out[flag] = {"n": n, "hits": hit,
                     "pct": "%.1f" % (100.0 * hit / n if n else 0)}
        tot_n += n
        tot_hit += hit
    out["pooled"] = {"n": tot_n, "hits": tot_hit,
                     "pct": "%.1f" % (100.0 * tot_hit / tot_n if tot_n else 0)}
    return out


def singleton_share(per_contract, final):
    """How many shipped selectors were seen in exactly one contract. The mechanism."""
    prev = {}
    for sels in per_contract.values():
        for sel in sels:
            prev[sel] = prev.get(sel, 0) + 1
    shipped = set()
    for group in final.values():
        shipped |= set(group)
    return {"shipped": len(shipped),
            "seen_in_one_contract": sum(1 for sel in shipped if prev.get(sel, 0) == 1),
            "seen_in_none": sum(1 for sel in shipped if prev.get(sel, 0) == 0)}


def write_json(per_contract, admitted, flags, pool, n_sel, n_named, today):
    """The measurement as a file, so a published sentence can be guarded against it.

    Every recall figure this project has printed about its own owner-power scan was
    hand-copied, and three copies of a superseded one were still in src/risk.py nine days
    after the number changed -- in the file that does the scanning. Numbers that are
    generated do not do that. This is the source they get generated from.
    """
    rows = {r[0]: r for r in _recall_rows(per_contract, admitted, flags) if r[2] == "both"}
    out = {
        "measured": today,
        "generated_by": "python bench/selector_mine.py --write",
        # Both, always, and out-of-sample first in every sentence that quotes one. The
        # in-sample figure describes this corpus; the out-of-sample figure describes the
        # next contract a caller asks about, which is the only one they have.
        "out_of_sample": cross_fit(per_contract, load_sig_cache(), flags),
        "selector_concentration": singleton_share(per_contract, final_list(admitted)),
        "note": ("Recall against the benchmark's held-out oracle is not recall against "
                 "reality. It bounds the scan's blindness from one side: a power the "
                 "oracle sees and we miss is definitely a miss."),
        "contracts": len(per_contract),
        "selectors_dispatched": n_sel,
        "selectors_named": n_named,
        "powers": {},
        "pooled": pool,
    }
    for flag, r in sorted(rows.items()):
        power = r[1]
        out["powers"][power] = {
            "oracle_flag": flag,
            "selectors_pinned": len(final_list(admitted).get(power) or {}),
            "oracle_says": r[3],
            "shipped_finds": r[4],
            "mined_finds": r[5],
            "shipped_pct": "%.1f" % (100.0 * r[4] / r[3] if r[3] else 0),
            "mined_pct": "%.1f" % (100.0 * r[5] / r[3] if r[3] else 0),
        }
    gate = set(final_list(admitted).get("can halt trading") or {})
    out["powers"]["can halt trading"] = {
        # Not "0" and not omitted: the oracle has no field for a trading gate, so its
        # recall here is UNMEASURED. Writing 0 would be the substitution this whole file
        # is about, committed into the artifact that other files quote from.
        "oracle_flag": None,
        "selectors_pinned": len(gate),
        "oracle_says": None,
        "mined_pct": None,
        "contracts_naming_one": sum(1 for k in per_contract if per_contract[k] & gate),
    }
    path = os.path.join(HERE, "owner_powers.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print()
    print("wrote bench/owner_powers.json")
    return out


def final_list(admitted):
    """What actually ships: the baseline and the mined selectors, under the split.

    The split is applied to the BASELINE too, not only to what was mined. `setTradingEnabled`
    and `setTradingStatus` were pinned under "can pause transfers" and are trading gates by
    the same rule that moved the mined ones, so leaving them where they were would make the
    shipped list disagree with the sentence the split exists to fix.
    """
    out = {}
    for power, sigs in BASELINE.items():
        for sig in sigs:
            target = (_split_pause(function_name(sig))
                      if power == "can pause transfers" else power)
            out.setdefault(target, {})[keccak_selector(sig)] = sig
    for power, sels in admitted.items():
        for sel, sig in sels.items():
            out.setdefault(power, {})[sel] = sig
    return out


def emit(admitted):
    """Print the pinned list for src/risk.py and the mirror for tests/test_owner_powers.py.

    Both halves come out of one command on purpose. The test recomputes every selector
    from its signature, which is the guard that makes a pinned list safe -- and a guard
    whose two halves are typed separately is a guard waiting to drift.
    """
    admitted = final_list(admitted)
    print("# ---- paste into src/risk.py ----")
    print("_OWNER_POWERS = {")
    for power in sorted(admitted):
        sels = sorted(admitted[power])
        print('    "%s": (' % power)
        line = "        "
        for sel in sels:
            piece = '"%s", ' % sel
            if len(line) + len(piece) > 88:
                print(line.rstrip())
                line = "        "
            line += piece
        if line.strip():
            print(line.rstrip().rstrip(","))
        print("    ),")
    print("}")
    print()
    print("# ---- paste into tests/test_owner_powers.py ----")
    print("SIGNATURES = {")
    for power in sorted(admitted):
        print('    "%s": (' % power)
        for sel in sorted(admitted[power]):
            print('        "%s",' % admitted[power][sel])
        print("    ),")
    print("}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resolve", action="store_true",
                    help="ask the public directory about unresolved selectors")
    ap.add_argument("--show-rule", action="store_true", help="print the rule and exit")
    ap.add_argument("--emit", action="store_true",
                    help="print the admitted list in src/risk.py's shape")
    ap.add_argument("--write", action="store_true",
                    help="write bench/owner_powers.json, the source guarded figures use")
    ap.add_argument("--today", default="2026-09-09",
                    help="the date stamped into owner_powers.json")
    args = ap.parse_args()

    if args.show_rule:
        print(PREREG_NOTE)
        for power, spec in sorted(RULE.items()):
            print("\n%s" % power)
            print("  include: %s" % " | ".join(p.pattern for p in spec["include"]))
            print("  exclude: %s" % " | ".join(p.pattern for p in spec["exclude"]))
        return 0

    contracts = load_contracts()
    print("cached contracts: %d" % len(contracts))
    if not contracts:
        print("Nothing to mine. bench/cache_bytecode is empty.")
        return 1

    per_contract = {}
    prevalence = {}
    for chain, address, code in contracts:
        sels = selectors_from_code(code)
        per_contract[(chain, address)] = sels
        for s in sels:
            prevalence[s] = prevalence.get(s, 0) + 1
    allsel = set(prevalence)
    print("distinct selectors dispatched: %d" % len(allsel))
    print("median per contract: %d" % sorted(len(v) for v in per_contract.values())[
        len(per_contract) // 2])

    cache = load_sig_cache()
    if args.resolve:
        print("resolving against the public signature directory...")
        got = resolve(allsel, cache, verbose=True)
        save_sig_cache(cache)
        print("newly resolved: %d" % got)

    asked = sum(1 for s in allsel if s in cache)
    named = sum(1 for s in allsel if (cache.get(s) or {}).get("names"))
    print("resolution: %d of %d asked (%.1f%%), %d carry a signature, %d the directory "
          "has no entry for, %d unasked"
          % (asked, len(allsel), 100.0 * asked / len(allsel), named,
             asked - named, len(allsel) - asked))
    if not RULE:
        print()
        print("No rule loaded. RULE is empty, so nothing can be admitted -- this is the")
        print("pre-registration step not having happened, not a measurement of zero.")
        return 1

    admitted, dropped = candidates(cache, prevalence, len(contracts))
    print()
    print("admitted by the pre-registered rule:")
    for power in sorted(admitted):
        sels = admitted[power]
        shipped = len(BASELINE.get(power) or ())
        egs = ", ".join(sorted(sels.values())[:3])
        print("  %-24s %4d selectors (shipped: %d)   e.g. %s"
              % (power, len(sels), shipped, egs[:70]))
    print("dropped: %d on the ERC-20 surface, %d did not recompute, %d too prevalent"
          % (len(dropped["erc20_surface"]), len(dropped["did_not_recompute"]),
             len(dropped["too_prevalent"])))
    for why in ("erc20_surface", "did_not_recompute", "too_prevalent"):
        for sel, sig in dropped[why][:4]:
            print("    %-18s %s  %s" % (why, sel, sig[:60]))

    per_contract_l = {(c, a): sels for (c, a), sels in per_contract.items()}
    flags = _flags_by_contract()
    measure(per_contract_l, admitted, flags)
    pool = report_union_and_pool(per_contract_l, admitted, flags)
    if args.write:
        write_json(per_contract_l, admitted, flags, pool, len(allsel), named, args.today)

    if args.emit:
        print()
        emit(admitted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
