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

import contextlib
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATUS = os.path.join(ROOT, "bench", "production", "upstream_contract.json")
DECISIONS = os.path.join(ROOT, "docs", "DECISIONS.md")

# The first record has a due date, pre-registered on 2026-09-21 while no record existed yet
# (DECISIONS E30). Until then a missing record was a NOTE with no end: "production.yml
# writes it on its next run" is also exactly what this guard would print for ever if that
# step never wrote anything, so the instrument built to catch lasting blindness had a
# failure mode identical to having only just started. E11, on the guard itself.
#
# Not a new tolerance. The writer went live with bea8520 on 2026-09-20, and a record that
# never started is at least as stale as one that stopped -- which MAX_RECORD_AGE_DAYS below
# already bounds at eight days. From the day after this date, no record is red.
FIRST_RECORD_DUE = datetime.date(2026, 9, 28)

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


# What `_load` returns for a record that exists and cannot be read.
_UNREADABLE = object()


def _load():
    """The record; None when there is no file; `_UNREADABLE` when there is one we cannot read.

    Those are different facts and they used to be one None, so a truncated or conflicted
    record read as "no record yet" -- the absence of a file impersonated by a file we
    failed to read.
    """
    if not os.path.exists(STATUS):
        return None
    try:
        with open(STATUS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _UNREADABLE
    return data if isinstance(data, dict) else _UNREADABLE


def _today():
    """The UTC date every rule here is judged against.

    One function, so a deadline can be watched failing before it arrives rather than
    trusted until it does (`test_a_record_that_never_arrives_goes_red_after_its_due_date`).
    """
    return datetime.datetime.now(datetime.timezone.utc).date()


def _days_since(stamp):
    try:
        then = datetime.date.fromisoformat(str(stamp)[:10])
    except (TypeError, ValueError):
        return None
    return (_today() - then).days


def test_the_contract_monitor_has_a_record():
    """There is a record, and it is not stale.

    An absent artifact is not a pass. Until `production.yml` has run once this is the
    expected state, so it does not fail -- **until `FIRST_RECORD_DUE`**, and from the day
    after, it does. Without the date, "not yet" had no end, and a writer that never worked
    would have kept this at "not yet" for ever. The moment a record exists, a record that
    stops updating fails too, because a daily job that quietly stopped is exactly as blind
    as an upstream that quietly stopped.
    """
    print("\n[observed] the daily contract record exists and is current")
    data = _load()
    if data is _UNREADABLE:
        check("the record on disk can be read", False,
              "%s exists but is not a JSON object -- a truncated write or a conflicted "
              "merge, not a record still to come" % os.path.relpath(STATUS, ROOT))
        return
    if data is None:
        where = os.path.relpath(STATUS, ROOT)
        late = (_today() - FIRST_RECORD_DUE).days
        check("no %s yet, and it is not due until %s" % (where, FIRST_RECORD_DUE),
              late <= 0,
              "%d day(s) past the due date DECISIONS E30 pre-registered: the step in "
              "production.yml that writes it is not writing, and this guard has been blind "
              "since it went live" % late)
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
    if data is None or data is _UNREADABLE:
        # Nothing to judge here; the record check above says which of the two it is.
        print("  NOTE  no readable record; nothing to judge")
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


def _record_check_fails(day, status_path):
    """Run the record check as if today were `day` and the record lived at `status_path`.

    Returns (failed, what it printed). Everything it touches is put back, so the forced
    run leaves no trace in this file's own tally.
    """
    global STATUS, _today, _PASSED
    saved = STATUS, _today, list(_FAILURES), _PASSED
    out = io.StringIO()
    try:
        STATUS = status_path
        _today = lambda: day
        with contextlib.redirect_stdout(out):
            test_the_contract_monitor_has_a_record()
        failed = len(_FAILURES) > len(saved[2])
    finally:
        STATUS, _today = saved[0], saved[1]
        _FAILURES[:] = saved[2]
        _PASSED = saved[3]
    return failed, " ".join(out.getvalue().split())


def test_a_record_that_never_arrives_goes_red_after_its_due_date():
    """The due date has been watched failing, not only written down.

    A deadline nobody has seen fire is a constant, and a guard nobody has watched fail is
    not a guard. So the record check is run against a clock forced to the day after
    `FIRST_RECORD_DUE` with no record on disk, and must fail; and on the due date itself,
    and must not yet. The date has to match the one DECISIONS E30 pre-registered, so it
    cannot be pushed out in this file alone -- the escape an external audit found in the
    gate check (moving a date to next year turned an overdue gate green).
    """
    print("\n[observed] a record that never arrives is red after %s" % FIRST_RECORD_DUE)
    absent = os.path.join(HERE, "no-such-upstream-contract-record.json")
    if os.path.exists(absent):
        check("the stand-in path for a missing record is really missing", False, absent)
        return
    after, said_after = _record_check_fails(FIRST_RECORD_DUE + datetime.timedelta(days=1),
                                            absent)
    on, said_on = _record_check_fails(FIRST_RECORD_DUE, absent)
    check("no record on the day after its due date is a failure", after, said_after)
    check("  and on the due date itself it is not one yet", not on, said_on)

    with open(DECISIONS, encoding="utf-8") as f:
        row = next((ln for ln in f.read().splitlines() if ln.startswith("| E30 |")), "")
    check("  and the date is the one DECISIONS E30 pre-registered",
          FIRST_RECORD_DUE.isoformat() in row,
          "E30 does not carry %s; a due date moved in one place only is a date moved "
          "silently" % FIRST_RECORD_DUE)


def test_a_record_that_cannot_be_read_is_not_a_missing_one():
    """A file we could not read is not the absence of a file.

    Both used to come back from `_load` as None, so a truncated or conflicted record read
    as "no record yet; production.yml writes it on its next run" -- inside the due window a
    pass, after it a failure blaming a writer that had written. Judged inside the window
    here, so the due date cannot be what makes it red.
    """
    import tempfile
    print("\n[observed] an unreadable record is a failure, not a record still to come")
    for label, body in (("not JSON", '{"date": "2026-09-2'), ("not an object", '["green"]')):
        # Beside this file, not in the system temp dir: that can sit on another drive,
        # where the path the check prints cannot be made relative to the repository.
        fd, path = tempfile.mkstemp(suffix=".json", dir=HERE)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(body)
            failed, said = _record_check_fails(FIRST_RECORD_DUE, path)
        finally:
            os.remove(path)
        check("a record that is %s fails, even inside the due window" % label, failed, said)


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
