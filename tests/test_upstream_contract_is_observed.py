"""test_upstream_contract_is_observed.py — the contract monitor is still monitoring.

DECISIONS E30, second half.

Removing `continue-on-error` from the `upstream-contract` job fixes the loud failure: a
field that changes shape now fails the build. It does nothing at all for the quiet one.
`tests/test_upstream_contract.py` asserts against bodies that arrived, and when a third
party stops answering it says so and asserts nothing -- correctly, because a body that
never came cannot testify. But a suite that asserted nothing still prints "all passed",
and a green tick means "we checked" to everyone who reads it. Blindness that lasts is
indistinguishable, from the outside, from health.

That is the same error this repository keeps writing down and keeps rewriting: an
observed absence and an unobserved dimension wearing each other's clothes (E11), a failed
page fetch and an exhausted listing taking the same `break`, a telemetry field where
"we could not ask" and "there is no record" collapsed into one boolean. Here it would be
"upstream was down for a week" collapsing into "the contract is fine".

So `production.yml` records what each daily run managed to observe into
`bench/production/upstream_contract.json`, and this reads it. One bad day for a third
party is not actionable and does not fail. A week of them is not weather -- it is an
endpoint that moved, an auth requirement that appeared, or a probe of ours that broke,
and all three are ours to fix.

Offline: it reads a committed artifact and calls nothing.

Run:  python tests/test_upstream_contract_is_observed.py
"""

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATUS = os.path.join(ROOT, "bench", "production", "upstream_contract.json")

# Pre-registered, before the first artifact existed, and deliberately generous. honeypot.is
# answered 400 to four consecutive probes on 2026-09-20 and 200 to the same URLs ninety
# seconds later; a threshold tight enough to catch that would fail on weather and get this
# file switched off, which is the failure mode E30 exists to end.
MAX_BLIND_DAYS = 5
# The record itself can stop. A daily job that silently stopped running leaves a file that
# looks green forever, which is the same bug one level up again.
MAX_RECORD_AGE_DAYS = 8
# And the same shape for a coverage collapse. `test_upstream_contract.py` records rather
# than fails when a path's share falls off a cliff, because on 2026-09-20 RugCheck served
# HTTP 200 for all 16 probe mints and a holder list for none of them -- 0 of 16 against 12
# of 16 the same morning, BONK included, which had carried 2,069,663 holders in nine
# consecutive sweeps twelve hours earlier. Nothing had changed shape. One sample cannot
# tell a trough from a removal; five days of trough is not weather.
MAX_COLLAPSE_DAYS = 5

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


def _load():
    if not os.path.exists(STATUS):
        return None
    try:
        with open(STATUS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _days_since(stamp):
    try:
        then = datetime.date.fromisoformat(str(stamp)[:10])
    except (TypeError, ValueError):
        return None
    return (datetime.datetime.now(datetime.timezone.utc).date() - then).days


def test_the_contract_monitor_has_a_record():
    """There is a record, and it is not stale.

    An absent artifact is not a pass. Until `production.yml` has run once this is the
    expected state, so it reports rather than fails -- but the moment a record exists, a
    record that stops updating does fail, because a daily job that quietly stopped is
    exactly as blind as an upstream that quietly stopped.
    """
    print("\n[observed] the daily contract record exists and is current")
    data = _load()
    if data is None:
        print("  NOTE  no %s yet; production.yml writes it on its next run"
              % os.path.relpath(STATUS, ROOT))
        return
    age = _days_since(data.get("date"))
    check("the record parses and carries a date", age is not None,
          "date is %r" % data.get("date"))
    if age is None:
        return
    check("the record is not stale",
          age <= MAX_RECORD_AGE_DAYS,
          "last written %d days ago (%s); the daily job may have stopped"
          % (age, data.get("date")))


def test_no_upstream_has_been_unobserved_for_a_week():
    """A run of blind days is an endpoint that moved, not weather.

    The test that matters -- `test_upstream_contract.py` -- goes quiet rather than red
    when a third party does not answer, and that is right. This is the other half of
    that bargain: the quiet is allowed to last a few days and no longer.
    """
    print("\n[observed] no upstream has gone unwatched for more than %d days"
          % MAX_BLIND_DAYS)
    data = _load()
    if data is None:
        print("  NOTE  no record yet; nothing to judge")
        return
    history = [h for h in (data.get("history") or []) if isinstance(h, dict)]
    history.sort(key=lambda h: h.get("date") or "")
    check("the record keeps a history to judge", bool(history),
          "no history entries; --status-json may be writing the short form")
    if not history:
        return

    # Per source, because "something was observed" is not the claim. honeypot.is being
    # up for a week while RugCheck was down the whole time is precisely the case a
    # whole-run status would call healthy, and RugCheck is the only source on Solana.
    sources = sorted({s for h in history for s in (h.get("unobserved_sources") or [])})
    for source in sources:
        run = 0
        for h in reversed(history):
            if source in (h.get("unobserved_sources") or []):
                run += 1
            else:
                break
        check("%s has been observed within the last %d recorded days"
              % (source, MAX_BLIND_DAYS),
              run <= MAX_BLIND_DAYS,
              "unobserved on the last %d recorded days -- the endpoint moved, an auth "
              "requirement appeared, or our probe broke; all three are ours" % run)

    # The same rule for a collapsed coverage share, per path, for the same reason: the
    # share rule cannot fail on sight without dying of ordinary upstream weather, so its
    # alarm lives here instead, on the one thing weather does not do -- persist.
    paths = sorted({p for h in history for p in (h.get("collapsed_paths") or [])})
    for path in paths:
        run = 0
        for h in reversed(history):
            if path in (h.get("collapsed_paths") or []):
                run += 1
            else:
                break
        check("%s has carried its data within the last %d recorded days"
              % (path, MAX_COLLAPSE_DAYS),
              run <= MAX_COLLAPSE_DAYS,
              "collapsed on the last %d recorded days -- that is no longer a trough; the "
              "engine reads this path and it is not arriving" % run)

    # A run of contract failures is a different fault and fails on sight: `red` means
    # bodies arrived and did not match, which test.yml has already failed the build for.
    # It is reported here so a reader of the record sees both kinds in one place.
    reds = [h.get("date") for h in history if h.get("status") == "red"]
    check("the record shows no unresolved contract failure", not reds,
          "red on %s" % ", ".join(str(d) for d in reds[-5:]))


def main():
    print("=" * 68)
    print("Upstream contract monitor is still monitoring")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
