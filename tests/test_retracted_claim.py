"""Every phrasing the retracted claim has actually taken, pinned as a fixture.

The claim is "nobody in this category publishes their own error rates". It is false --
several vendors publish a rate, and two academic groups have published re-runnable
head-to-head evaluations of these very scanners with released datasets. It was retracted
on 2026-09-06 from the landing page, the share card and the structured data.

It then survived **six** more times, and three successive guards missed it, because each
guard was written against the wording of the survivor in front of it:

    1  "nobody else in this category does"                 landing page, og, JSON-LD
    2  "nobody else does it"                               docs/HANDOFF.md:137
    3  "nobody else publishes a rate"                       docs/HANDOFF.md:374
    4  "Nobody else in this category does"                  docs/STRATEGY.md:62
    5  "Nobody in this category publishes their own ..."    docs/STRATEGY.md:161
    6  "nobody in this category does"                       docs/STRATEGY.md:307

Guard v1 grepped the exact sentence and found one of six. Guard v2 required the word
"else". Guard v3 required "publish" in the sentence. Each was written after seeing the
survivor it was about to catch, which is fitting a rule to the data.

So this file stops describing the predicate and pins the corpus instead. Every line above
must be caught; every legitimate line -- the accurate "none of them publishes a METHOD you
can re-run", and the corrective sentences that quote the false claim in order to retract
it -- must not be. A seventh phrasing then fails a test rather than reaching a reader.

Run: python tests/test_retracted_claim.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import publish_numbers as pn  # noqa: E402

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


def flagged(line):
    """True when the guard would refuse this line."""
    low = line.lower()
    for pattern, corrective in pn.RETRACTED_CLAIMS:
        if re.search(pattern, low) and not re.search(corrective, low):
            return True
    return False


# Every phrasing the claim has actually taken, with where it was found.
MUST_CATCH = [
    ("landing page 2026-09-06", "we publish our own error rates and nobody else in this "
                                "category does"),
    ("HANDOFF.md:137", "it is the only way a risk product earns trust, and nobody else "
                       "does it"),
    ("HANDOFF.md:374", "we published our own false-positive rate, and nobody else "
                       "publishes a rate"),
    ("STRATEGY.md:62", "Nobody else in this category does, which is the whole pitch"),
    ("STRATEGY.md:161", "Nobody in this category publishes their own recall and "
                        "false-positive rates."),
    ("STRATEGY.md:307", 'The headline is the differentiator: "we published our own miss '
                        'rate - nobody in this category does".'),
    # Variants nobody has written yet, but which say the same false thing.
    ("plausible variant", "no one in this category publishes an error rate"),
    ("plausible variant", "none of them publish their own false-positive rate"),
]

# Lines that are accurate, or that quote the false claim in order to retract it.
MUST_NOT_CATCH = [
    ("the accurate claim", "What none of them publishes is a method you can re-run."),
    ("the accurate claim", "none of them publishes a dataset you can download"),
    ("retraction, HANDOFF", 'Not "nobody else publishes a rate" - several do, and a '
                            'commenter disproves it in one minute.'),
    ("retraction, STRATEGY", '"Nobody else publishes a rate" is not the claim, and it '
                             'stood here for two days after it was retracted'),
    ("the launch-draft warning", 'Do not claim "nobody publishes error rates." Several '
                                 'do.'),
    ("unrelated use of nobody", "nobody else wants to keep managing four upstreams for "
                                "years"),
]


def test_every_historical_phrasing_is_caught():
    print("\n[retracted] every phrasing this claim has actually taken")
    for where, line in MUST_CATCH:
        check("caught: %s" % where, flagged(line), line[:66])


def test_the_accurate_claim_and_the_retractions_survive():
    """A guard that also refuses the true sentence gets deleted, and then nothing guards."""
    print("\n[retracted] the accurate claim and the corrections are not touched")
    for where, line in MUST_NOT_CATCH:
        check("allowed: %s" % where, not flagged(line), line[:66])


def test_the_repository_is_clean_right_now():
    print("\n[retracted] no surviving occurrence in the repository")
    files = (pn.LIVE_CLAIM_FILES + pn.FROZEN_LOG_FILES +
             ("llms-install.md", "plugin/README.md", "docs/AGENT-INTEGRATION.md"))
    hits = pn.retracted(files)
    check("nothing in any tracked surface", not hits,
          "; ".join("%s:%d" % (r, l) for r, l, _ in hits))


def main():
    print("=" * 68)
    print("The retracted claim: six survivors, three guards, one corpus")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
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
