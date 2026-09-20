"""test_advertised_coverage.py — what the public surfaces promise, against what we cover.

WHY THIS EXISTS, AND WHY IT IS NOT A LIST OF PHRASES

The guard this replaces was a table of exact sentences. It was written on 2026-09-19,
green on 2026-09-20, and blind:

  - README.md:92 advertised "holder concentration" with no qualifier while both holder
    concentration rows in RISK_VECTORS were open. The guard was looking for the string
    "mint/freeze authority, holder concentration" -- correctly deleted from that file --
    and could not see the other wording one column away.
  - "holder concentration (EVM)" had no entry at all, so it was not checked anywhere.

tests/test_retracted_claim.py already records this exact failure in this repo's own words:
"six wordings, three guards each written against the survivor in front of it". It came
back in a day, on the guard written to stop it.

So this one is a rule, not a list:

  **A capability noun on a public surface is a claim about every advertised chain the
  dimension applies to, unless its own sentence says otherwise.**

  A sentence says otherwise by naming chains -- then it claims exactly those -- or by
  denying the capability before naming it, which is a disclosure rather than a claim. An
  HTML table row counts as one sentence, because its chain column is part of the same
  statement.

Then: claimed chains must be a subset of the chains bench/scorecard.py says are covered.
The vocabulary is keyed by RISK_VECTORS dimension, so a dimension cannot be silently
unmapped -- `test_every_dimension_has_a_vocabulary` fails if one has no forms, which is
precisely how "holder concentration (EVM)" went quiet.

Run: python tests/test_advertised_coverage.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import scorecard  # noqa: E402

_PASSED = 0
_FAILURES = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


# --------------------------------------------------------------- the surfaces
#
# Everything a caller or a reader meets before they meet the engine. `src/risk.py` is not
# here: it is the engine, and the sentences in it are code comments and gap reasons rather
# than advertising. Every other file under src/ is, and so is the README -- the discovery
# check below fails if a new one appears and nobody classified it.
SURFACES = [
    "README.md",
    "src/entry.py",        # / , /llms.txt, /llms-full.txt, the HTTP API help
    "src/mcp_server.py",   # the MCP tool descriptions, which an agent reads as the contract
    "src/pages.py",        # /api, /method, /unknown
    "src/landing.html",    # the homepage, its meta description and its structured data
]
NOT_A_SURFACE = {
    "src/risk.py": "the engine itself; its strings are gap reasons, not advertising",
    "src/og_image.py": "renders the share card image, carries no capability text",
    "src/__pycache__": "build output",
}


# ------------------------------------------------------------- the vocabulary
#
# RISK_VECTORS dimension -> the ways a public surface says it. Short nouns on purpose: the
# guard before this one matched whole sentences, and a whole sentence can be reworded
# without changing a single claim it makes.
#
# Every dimension needs at least one form. That is the structural half of the fix -- the
# old guard's second bug was a dimension with no mapping, which reads exactly like a
# dimension with nothing wrong.
VOCABULARY = {
    "sellability simulation": [
        "sell simulation", "sellability simulation", "buy/sell simulation",
        "buy / sell simulation", "sell test", "sellability", "honeypot simulation",
        "honeypot detection", "simulation (honeypot",
    ],
    "buy / sell / transfer tax": [
        "buy/sell/transfer tax", "buy / sell / transfer tax", "sell tax", "buy tax",
        "transfer tax", "extraction tax", "the taxes",
    ],
    "liquidity depth": ["liquidity depth", "thin liquidity", "depth checks"],
    "pair age": ["pair age", "trading-pair age", "pair, age"],
    "contract source published": [
        "open source", "open-source", "contract source", "source published",
        "contract openness",
    ],
    "upstream aggregator verdict": [
        "upstream scanner verdict", "upstream aggregate verdict", "aggregate verdict",
        "aggregate risk", "upstream security scanner", "upstream scanner",
    ],
    "holder concentration": [
        "holder concentration", "holder distribution", "top-10 holder",
    ],
    "mint / freeze authority": [
        "mint/freeze authority", "mint and freeze authority", "freeze authority",
        "mint authority",
    ],
    "LP lock / burn": ["lp lock", "lp burn", "liquidity lock"],
    "same-name token impersonation": [
        "impersonation", "same-ticker", "same-name token", "same ticker",
    ],
    "deployer history": ["deployer history", "deployer"],
}

# Chain names as a reader writes them, including the two collective ones. "EVM" names the
# seven, which is how this project has always used it -- and is why "EVM holder
# concentration" is a claim about seven chains, not a hedge.
_CHAIN_WORDS = {
    "ethereum": ("ethereum", "eth "), "bsc": ("bsc", "binance"),
    "base": ("base",), "arbitrum": ("arbitrum",), "polygon": ("polygon", "matic"),
    "optimism": ("optimism",), "avalanche": ("avalanche", "avax"),
    "solana": ("solana",),
}
_EVM_CHAINS = tuple(c for c in scorecard.ADVERTISED_CHAINS if c != "solana")
_ALL_CHAIN_PHRASES = ("every chain", "all chains", "any chain", "each chain")

# Words that turn "we do X" into "we do not do X". Looked for in the run-up to the noun,
# not anywhere in the sentence: "covers A but not B" must still be a claim about A.
_DENIALS = ("no ", "not ", "never", "cannot", "can't", "unavailable", "without",
            "nothing", "gap", "missing", "omits", "lacks", "untested", "stops",
            "instead of", "unverified", "could not", "did not")
_DENIAL_WINDOW = 90
# How far from the noun a chain qualifier still belongs to it. Asymmetric on purpose: a
# qualifier follows what it qualifies far more often than it precedes it.
_SCOPE_BEFORE, _SCOPE_AFTER = 60, 130
# A colon this early in a sentence introduces a list, and what precedes it scopes the lot.
_HEADING_COLON = 60


# Occurrences reviewed by hand and found not to be capability claims. Default-deny: a new
# sentence is checked until someone puts it here with a reason, which is the opposite of
# the blacklist this file replaces -- that one checked nothing until someone remembered to
# add it. Each entry must still match something, or `test_no_stale_exemptions` fails, so
# an exemption cannot outlive the sentence it was written for.
REVIEWED_NOT_A_CLAIM = {
    ("src/pages.py", "whether it can be sold (sellability)"):
        "the /unknown page naming which two checks are critical. It says what makes an "
        "answer unknown, not where the check runs, and the same page's table gives the "
        "chains three paragraphs later",
    ("src/pages.py", "A critical check - liquidity or sellability - could not be"):
        "the /unknown FAQ structured data, quoting the same definition",
    ("src/pages.py", '{"dimension": "sellability", "source": "rugcheck"'):
        "a sample data_gaps payload: the engine's own field value, shown so a caller can "
        "parse it",
    ("src/pages.py", "on any other chain the sell test is a gap of ours"):
        "names its scope as the complement of the chains it just listed -- 'on any other "
        "chain' -- which this guard reads chain by chain and cannot express",
    ("src/entry.py", "sellability:no record"):
        "a docstring example of the telemetry string, not text a caller is shown",
    ("README.md", "Review liquidity, holder distribution and contract permissions"):
        "inside the sample response: the engine's recommendation telling the caller what "
        "to go and look at, which is the opposite of a claim to have looked",
}


# ------------------------------------------------------------------ mechanics

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n\s*\n|</?tr>|</?li>|</?p>|\|")


def sentences(text):
    """Split a surface into claim-sized pieces, one line of whitespace each.

    A markdown table cell, an HTML row, a list item and an ordinary sentence are each one
    claim. `<tr>` is a boundary rather than a split point of its own contents, so a row
    keeps its chain column: `<td>Buy/sell simulation</td><td>Ethereum, BSC, Base</td>`
    is one statement and reads as one here.

    Whitespace is collapsed first. Every surface here wraps its sentences across lines --
    entry.py's help text, mcp_server.py's description, landing.html's paragraphs -- and a
    window measured in characters has to see the sentence a reader sees, not the one the
    line breaks made. The first version of this file did not, and read "does not yet check
    ... or sellability on Solana" as an unqualified promise because the denial was on the
    previous line.
    """
    for piece in _SENTENCE_SPLIT.split(text):
        if piece and piece.strip():
            yield " ".join(piece.split())


def chains_named(sentence, index, form):
    """The chains this occurrence scopes itself to, or None for "it does not say".

    Scoped to a window around the noun rather than the whole sentence. A sentence can name
    a chain for one dimension and say nothing about another -- "Covers: sell simulation
    ..., and on Solana the mint/freeze authority" names Solana for the authority check and
    nothing for the simulation -- and reading the sentence as a whole would hand Solana to
    both. The window is wider after the noun than before it, because that is where a
    qualifier goes: "Buy/sell simulation (honeypot), buy/sell/transfer tax | Ethereum, BSC,
    Base".
    """
    low = sentence.lower()[max(0, index - _SCOPE_BEFORE):index + len(form) + _SCOPE_AFTER]
    # A qualifier at the head of the sentence governs everything the sentence lists.
    # "Checks on Ethereum, BSC and Base only: sell simulation, taxes, whether the contract
    # is open source, upstream scanner verdicts" -- the fourth item is past any window
    # measured from the noun, and it is scoped just as tightly as the first.
    head = sentence[:sentence.find(":")].lower() \
        if 0 <= sentence.find(":") <= _HEADING_COLON else ""
    low += " " + head
    if any(p in low for p in _ALL_CHAIN_PHRASES):
        return set(scorecard.ADVERTISED_CHAINS)
    named = set()
    if re.search(r"\bevm\b", low):
        named.update(_EVM_CHAINS)
    for chain, words in _CHAIN_WORDS.items():
        if any(w in low for w in words):
            named.add(chain)
    return named or None


def denied_before(sentence, index):
    """Is this occurrence inside a denial rather than a promise?

    Only the run-up counts. "Covers A but not B" has to stay a claim about A, so a denial
    after the noun does not excuse it -- which means a sentence that discloses a gap must
    disclose it before naming the thing. Three sentences were reworded for that in the
    commit that added this file, and they read better for it.
    """
    run_up = sentence.lower()[max(0, index - _DENIAL_WINDOW):index]
    return any(d in run_up for d in _DENIALS)


def covered_on(dimension):
    for name, applies, on in scorecard.RISK_VECTORS:
        if name == dimension:
            if applies is None:
                return frozenset(), frozenset()   # measured and rejected: covered nowhere
            return frozenset(on), frozenset(applies)
    raise KeyError(dimension)


def claims(text):
    """Every capability claim a surface makes: (dimension, sentence, claimed chains).

    Every occurrence, not the first one per sentence. A sentence that denies a capability
    and then promises it -- or the reverse -- makes two statements, and checking only the
    first is how a guard reports on half a page.
    """
    found = []
    for sentence in sentences(text):
        low = sentence.lower()
        for dimension, forms in VOCABULARY.items():
            _on, applies = covered_on(dimension)
            seen = set()
            for form in forms:
                at = low.find(form)
                while at >= 0:
                    if not denied_before(sentence, at):
                        named = chains_named(sentence, at, form)
                        claimed = frozenset(named & set(applies)) if named \
                            else frozenset(applies)
                        if claimed and claimed not in seen:
                            seen.add(claimed)
                            found.append((dimension, sentence, set(claimed)))
                    at = low.find(form, at + 1)
    return found


def exempt(rel, sentence):
    for (where, phrase), _why in REVIEWED_NOT_A_CLAIM.items():
        if where == rel and flat(phrase) in flat(sentence):
            return True
    return False


def flat(text):
    """Whitespace-collapsed and lowercased, so a phrase can be written the way it reads.

    Every surface here wraps. An exemption quoted from a rendered page will not match the
    source byte for byte, and an exemption that silently matches nothing is the same bug
    as a guard that silently checks nothing."""
    return " ".join(text.split()).lower()


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------- tests

def test_every_dimension_has_a_vocabulary():
    """A dimension with no way of being said is a dimension nobody is checking."""
    print("\n[advertising] every scorecard dimension is one this guard can recognise")
    for name, _applies, _on in scorecard.RISK_VECTORS:
        check("%s has at least one surface form" % name,
              bool(VOCABULARY.get(name)), "add it to VOCABULARY")
    stale = sorted(set(VOCABULARY) - set(n for n, _, _ in scorecard.RISK_VECTORS))
    check("no vocabulary for a dimension the scorecard dropped", not stale, str(stale))


def test_a_named_token_2022_extension_list_names_all_of_them():
    """A parenthesis that names four of them reads as all of them.

    Three surfaces carried the identical closed list -- "the Token-2022 extensions
    (transfer fee, permanent delegate, transfer hook, frozen-by-default)" -- in the API
    help, in the MCP tool description an agent reads as the contract, and in the method
    page's coverage table. The engine graded **six** when that sentence was written, so
    non-transferable and pausable were already missing from it, and nine after 2026-09-20.

    This is the same defect as `evidence.token2022 = {"read": true}` beside six of the
    seventeen keys RugCheck sends (DECISIONS E28), moved one layer out onto the surface an
    agent meets first, and the fix is the same: what was looked at and what was not must
    not be the same shape. An agent handed a complete-looking parenthesis has no way to
    tell it is a sample.

    The rule is not "every surface must list nine things". A surface may say
    "Token-2022 extensions" and enumerate nothing -- README.md's upstream table does, and
    that claims nothing about which ones. **But a surface that names any of them must name
    all of them**, because naming some is what makes the list look closed.
    """
    print("\n[advertising] a named Token-2022 extension list is not a sample of four")
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import risk  # noqa: E402

    missing_label = sorted(set(risk._TOKEN2022_SCORED) - set(risk._TOKEN2022_LABEL))
    check("every scored extension has a public name", not missing_label,
          "%s: add to _TOKEN2022_LABEL, or no surface can be checked against it"
          % missing_label)
    stale = sorted(set(risk._TOKEN2022_LABEL) - set(risk._TOKEN2022_SCORED))
    check("no public name for an extension nothing scores", not stale, str(stale))

    labels = {k: v for k, v in risk._TOKEN2022_LABEL.items()
              if k in risk._TOKEN2022_SCORED}
    for rel in SURFACES:
        text = read(rel).lower()
        named = {k for k, v in labels.items() if v.lower() in text}
        if not named:
            continue        # enumerates none, so it closes no list
        absent = sorted(labels[k] for k in set(labels) - named)
        check("%s names every scored extension, having named one" % rel, not absent,
              "names %d of %d; missing %s" % (len(named), len(labels), absent))


def test_the_surface_list_is_complete():
    """A new public file must be classified, not silently unscanned."""
    print("\n[advertising] every public file is either scanned or excused by name")
    for rel in SURFACES:
        check("%s exists" % rel, os.path.exists(os.path.join(ROOT, rel)))
    on_disk = set()
    for entry in sorted(os.listdir(os.path.join(ROOT, "src"))):
        rel = "src/%s" % entry
        if rel in NOT_A_SURFACE or entry.startswith("__"):
            continue
        on_disk.add(rel)
    missing = sorted(on_disk - set(SURFACES))
    check("no unclassified file under src/", not missing,
          "%s: add to SURFACES or to NOT_A_SURFACE with a reason" % missing)


def test_a_surface_the_guard_cannot_read_is_a_failure():
    """Zero matches means the vocabulary went blind, not that the page is clean."""
    print("\n[advertising] the guard can still see each surface")
    for rel in SURFACES:
        n = len(claims(read(rel)))
        check("%s yields capability claims to check (%d)" % (rel, n), n > 0,
              "no capability noun matched: VOCABULARY has drifted from the copy")


def test_no_surface_claims_a_dimension_on_a_chain_we_do_not_cover():
    """The rule. Every claim is about every applicable advertised chain unless it says so."""
    print("\n[advertising] no public surface promises a check we do not run")
    for rel in SURFACES:
        text = read(rel)
        for dimension, sentence, claimed in claims(text):
            if exempt(rel, sentence):
                continue
            on, _applies = covered_on(dimension)
            over = sorted(claimed - on)
            check("%s: %s claimed only where it is covered" % (rel, dimension),
                  not over,
                  "claims %s; covered on %s; sentence: %s"
                  % (", ".join(over) or "-", ", ".join(sorted(on)) or "nothing",
                     " ".join(sentence.split())[:160]))


def test_no_stale_exemptions():
    """An exemption must not outlive the sentence it excused."""
    print("\n[advertising] every hand-reviewed exemption still matches something")
    for (rel, phrase), why in REVIEWED_NOT_A_CLAIM.items():
        hit = flat(phrase) in flat(read(rel))
        check("%s still contains the exempted phrase" % rel, hit,
              "%r is gone -- delete the exemption (%s)" % (phrase[:60], why))


def main():
    print("=" * 68)
    print("Advertised coverage: every capability noun maps to a scorecard row")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s\n      %s" % (name, detail))
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
