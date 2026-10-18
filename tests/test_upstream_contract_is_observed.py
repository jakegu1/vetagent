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


def _coverage_source(probes, values, path="field", asked=None):
    """Collect actual list-valued synthetic bodies with stable key/type shape."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upstream_collection_fixture", os.path.join(HERE, "test_upstream_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bodies = [{path: [1] if i < values else []} for i in range(probes)]
    return {"probes": probes, "asked": probes if asked is None else asked,
            "paths": module.collect(bodies, [path])}


def _freeze_scenario(old, sources, unobserved=(), collapses=(), monitor=False,
                     repeats=1, raw=None, unreadable=False):
    """Exercise a fresh real CLI against private files, with network calls fatal."""
    import copy
    import importlib.util
    import socket
    import tempfile
    import time
    from unittest import mock

    spec = importlib.util.spec_from_file_location(
        "upstream_freeze_scenario", os.path.join(HERE, "test_upstream_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    initial = (list(module._COLLAPSES), list(module._UNOBSERVED))
    protected = (module.BASELINE, STATUS)
    original_bytes = [open(path, "rb").read() for path in protected]
    measures, opens, network, other_tests = [], [], [], []
    output = io.StringIO()
    original_open = open
    clock = time.struct_time((2030, 1, 2, 3, 4, 5, 2, 2, 0))
    with tempfile.TemporaryDirectory(prefix="upstream-freeze-") as directory:
        baseline = os.path.join(directory, "baseline.json")
        status = os.path.join(directory, "status.json")
        module.BASELINE = baseline
        if raw is not None or old is not None:
            payload = {"measured_utc": "2026-09-21T02:00:00Z", "engine_paths": 1,
                       "rule": {"value_band": 0.4, "min_for_share": 8}, "sources": old}
            before = raw if raw is not None else (json.dumps(payload) + "\n").encode()
            with original_open(baseline, "wb") as f:
                f.write(before)
        else:
            before = None
        module._COLLAPSES.extend(collapses)

        def measure():
            measures.append(copy.deepcopy(sources))
            module._UNOBSERVED.extend(unobserved)
            return copy.deepcopy(sources), {}

        def track_open(path, mode="r", *args, **kwargs):
            if os.path.abspath(os.fspath(path)) == baseline:
                opens.append(mode)
                if unreadable and mode == "r":
                    raise PermissionError("synthetic existing baseline cannot be read")
            return original_open(path, mode, *args, **kwargs)

        def fatal(*args, **kwargs):
            network.append(repr(args))
            raise AssertionError("offline freeze attempted network or live probe")

        def other_test(name):
            return lambda: other_tests.append(name)

        fields = mock.Mock(incomplete=False, rounds=1)
        fields.table.return_value = {source: set(row["paths"]) for source, row in sources.items()}
        argv = ["test_upstream_contract.py", "--status-json", status] if monitor else [
            "test_upstream_contract.py", "--write"]
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(module, "measure", measure))
            stack.enter_context(mock.patch.object(module, "open", track_open, create=True))
            stack.enter_context(mock.patch.object(module.upstream_fields, "build", return_value=fields))
            stack.enter_context(mock.patch.object(module.time, "gmtime", return_value=clock))
            for name in ("fetch", "get", "fetch_bodies"):
                stack.enter_context(mock.patch.object(module, name, fatal))
            stack.enter_context(mock.patch.object(module.subprocess, "run", fatal))
            stack.enter_context(mock.patch.object(socket, "create_connection", fatal))
            stack.enter_context(mock.patch.object(socket.socket, "connect", fatal))
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            for name in sorted(vars(module)):
                if name.startswith("test_") and name != "test_generated_field_contract":
                    stack.enter_context(mock.patch.object(
                        module, name, other_test(name) if monitor else fatal))
            stack.enter_context(contextlib.redirect_stdout(output))
            results = [module.main() for _ in range(repeats)]
        after = original_open(baseline, "rb").read() if os.path.exists(baseline) else None
        record = json.load(original_open(status, encoding="utf-8")) if monitor else None
        preserved = all(original_open(path, "rb").read() == data
                        for path, data in zip(protected, original_bytes))
        return {"results": results, "before": before, "after": after,
                "opens": opens, "measures": measures, "initial": initial,
                "collapses": list(module._COLLAPSES), "unobserved": list(module._UNOBSERVED),
                "failures": list(module._FAILURES), "passed": module._PASSED,
                "stdout": output.getvalue(), "status": record, "network": network,
                "other_tests": other_tests, "protected": preserved,
                "constants": (module.VALUE_BAND, module.MIN_FOR_SHARE,
                              module.MAX_COLLAPSE_DAYS, module.HISTORY_DAYS)}


def _check_refused_freeze(label, receipt, diagnostic):
    check(label + ": cold CLI refuses", receipt["results"] == [1], receipt["stdout"])
    check(label + ": old bytes are unchanged", receipt["before"] == receipt["after"])
    check(label + ": no baseline write was opened",
          not any(any(c in mode for c in "wax+") for mode in receipt["opens"]),
          repr(receipt["opens"]))
    check(label + ": one measurement pass", len(receipt["measures"]) == 1)
    check(label + ": truthful refusal diagnostic", diagnostic in receipt["stdout"],
          receipt["stdout"])
    check(label + ": no network or public data change",
          not receipt["network"] and receipt["protected"])


def test_cold_freeze_refuses_observed_value_share_collapses():
    """Cold --write must compare first, including a partial nonzero old share."""
    for label, old_hits, now_hits in (("full share to zero", 8, 0),
                                     ("partial old share", 6, 2)):
        old = {"synthetic": _coverage_source(8, old_hits)}
        now = {"synthetic": _coverage_source(8, now_hits)}
        receipt = _freeze_scenario(old, now)
        check(label + ": fresh collapse and blindness lists", receipt["initial"] == ([], []))
        check(label + ": same observed key/type shape",
              old["synthetic"]["paths"]["field"]["key"] == 1.0
              and old["synthetic"]["paths"]["field"]["types"] == ["list"]
              and now["synthetic"]["paths"]["field"]["key"] == 1.0
              and now["synthetic"]["paths"]["field"]["types"] == ["list"])
        _check_refused_freeze(label, receipt, "coverage is collapsed")
        check(label + ": the collapsed source/path is named",
              [name for name, _ in receipt["collapses"]] == ["synthetic:field"]
              and "synthetic:field" in receipt["stdout"], receipt["stdout"])


def test_cold_freeze_keeps_the_strict_R2_boundary_and_probe_floor():
    """The existing share rule stays strict; a small sample gets no new rule."""
    for label, probes, old_hits, now_hits, collapsed in (
            ("equality", 10000, 10000, 6000, False),
            ("just above", 10000, 10000, 6001, False),
            ("just below", 10000, 10000, 5999, True),
            ("under minimum", 7, 7, 0, False),
            ("observed zero stays zero", 8, 0, 0, False)):
        receipt = _freeze_scenario({"synthetic": _coverage_source(probes, old_hits)},
                                   {"synthetic": _coverage_source(probes, now_hits)})
        check(label + ": exact unchanged constants", receipt["constants"] == (0.4, 8, 5, 30))
        check(label + ": strict R2 result", receipt["results"] == [1 if collapsed else 0],
              receipt["stdout"])
        check(label + ": collapse recording", bool(receipt["collapses"]) == collapsed)
        check(label + ": one measurement", len(receipt["measures"]) == 1)
        check(label + ": bytes protected on refusal",
              not collapsed or receipt["before"] == receipt["after"])
        check(label + ": no network or committed data change",
              not receipt["network"] and receipt["protected"])


def test_cold_freeze_success_and_bootstrap_keep_the_usual_payload():
    """A valid re-freeze still writes measured sources, paths, rules and UTC time."""
    sources = {"synthetic": _coverage_source(8, 6),
               "another": _coverage_source(8, 8, path="other")}
    for label, old in (("existing noncollapsed", {"synthetic": _coverage_source(8, 8)}),
                       ("no old file", None),
                       ("intentional shape re-freeze", {"synthetic": _coverage_source(8, 8, "old")})):
        receipt = _freeze_scenario(old, sources)
        check(label + ": writer succeeds", receipt["results"] == [0], receipt["stdout"])
        payload = json.loads(receipt["after"])
        check(label + ": usual payload shape",
              set(payload) == {"measured_utc", "engine_paths", "rule", "sources"})
        check(label + ": current measured UTC timestamp",
              payload["measured_utc"] == "2030-01-02T03:04:05Z")
        check(label + ": current sources and path count",
              payload["sources"] == sources and payload["engine_paths"] == 2)
        check(label + ": unchanged rule constants",
              payload["rule"] == {"value_band": 0.4, "min_for_share": 8})
        check(label + ": usual sorted JSON and final newline",
              receipt["after"] == (json.dumps(payload, indent=1, sort_keys=True) + "\n")
              .replace("\n", os.linesep).encode())
        check(label + ": one measurement and one write",
              len(receipt["measures"]) == 1 and receipt["opens"].count("w") == 1)
        check(label + ": no normal network test was invoked", not receipt["other_tests"])
        check(label + ": no network or public file change",
              not receipt["network"] and receipt["protected"])


def test_cold_freeze_refuses_an_existing_uncomparable_baseline():
    """An unreadable existing file never impersonates no-old-file bootstrap."""
    sources = {"synthetic": _coverage_source(8, 8)}
    for label, raw, unreadable in (("invalid JSON", b'{"sources":', False),
                                    ("list", b'[]', False), ("null", b'null', False),
                                    ("string", b'"baseline"', False),
                                    ("number", b'8', False), ("boolean", b'true', False),
                                    ("read failure", b'{"sources": {}}', True)):
        receipt = _freeze_scenario({}, sources, raw=raw, unreadable=unreadable)
        _check_refused_freeze(label, receipt, "baseline")
        check(label + ": diagnostic explains refusal", "refusing" in receipt["stdout"])


def test_cold_freeze_retains_partial_and_populated_refusal_priority():
    """Already known blindness and collapses are retained, with their old diagnostics."""
    old = {"synthetic": _coverage_source(8, 8)}
    healthy = {"synthetic": _coverage_source(8, 8, asked=9)}
    known = [("already:field", "carried by 100% of probes at baseline, 0% now")]
    partial = [("synthetic", "HTTP 429")]
    for label, unobserved, collapses, diagnostic in (
            ("partial run", partial, [], "partial run"),
            ("known collapse", [], known, "coverage is collapsed"),
            ("known collapse before blindness", partial, known, "coverage is collapsed")):
        receipt = _freeze_scenario(old, healthy, unobserved=unobserved, collapses=collapses)
        _check_refused_freeze(label, receipt, diagnostic)
        check(label + ": existing evidence is not cleared",
              receipt["collapses"] == collapses and receipt["unobserved"] == unobserved)
        if collapses:
            check(label + ": collapsed diagnostic retains priority",
                  "already:field" in receipt["stdout"] and "partial run" not in receipt["stdout"])
        else:
            check(label + ": partial diagnostic names the failed source and cause",
                  "synthetic" in receipt["stdout"] and "HTTP 429" in receipt["stdout"])
    receipt = _freeze_scenario(old, {"synthetic": _coverage_source(8, 0, asked=9)},
                               unobserved=partial)
    _check_refused_freeze("observed trough plus partial run", receipt, "partial run")
    check("the existing partial refusal remains truthful", receipt["unobserved"] == partial)


def test_default_generated_monitor_retains_collapse_names_and_status():
    """Normal comparison and status keep R2 recorded rather than failed, without duplicates."""
    old = {"synthetic": _coverage_source(8, 8)}
    now = {"synthetic": _coverage_source(8, 0)}
    receipt = _freeze_scenario(old, now, monitor=True, repeats=2)
    check("normal monitor records but does not fail a new collapse", receipt["results"] == [0, 0])
    check("repeated normal comparison records the path exactly once",
          [name for name, _ in receipt["collapses"]] == ["synthetic:field"], repr(receipt["collapses"]))
    check("normal comparison keeps the exact collapse detail",
          receipt["collapses"][0][1] == "carried by 100% of probes at baseline, 0% now")
    check("normal key/type/new/removed/fixpoint checks still pass",
          receipt["passed"] == 10 and not receipt["failures"])
    check("normal monitor never rewrites its baseline",
          receipt["before"] == receipt["after"] and receipt["opens"] == ["r", "r"])
    check("normal monitor measures once per comparison", len(receipt["measures"]) == 2)
    status = receipt["status"]
    check("status keeps its ordinary shape", set(status) == {
        "date", "status", "failures", "unobserved_sources", "unobserved_probes",
        "collapsed_paths", "history"})
    check("status records the same path only once",
          status["status"] == "collapsed" and status["collapsed_paths"] == ["synthetic:field"])
    check("status retains one current history row",
          status["history"] == [{"date": "2030-01-02", "status": "collapsed",
                                  "unobserved_sources": [], "collapsed_paths": ["synthetic:field"]}])
    check("status retains failures and observation counts",
          status["failures"] == [] and status["unobserved_sources"] == []
          and status["unobserved_probes"] == 0)
    check("the default monitor still discovers its other tests", len(receipt["other_tests"]) == 12)
    check("monitor is offline and leaves committed data intact",
          not receipt["network"] and receipt["protected"])


def test_default_generated_monitor_keeps_common_observed_and_structural_rules():
    """R2 ignores blind/noncommon paths while normal R1/R3 and engine-shape guards stay active."""
    old = {"synthetic": _coverage_source(8, 8), "blind": _coverage_source(8, 8),
           "old_source": _coverage_source(8, 8)}
    old["synthetic"]["paths"]["removed"] = {"key": 1.0, "value": 1.0, "types": ["list"]}
    now = {"synthetic": _coverage_source(8, 8), "blind": _coverage_source(0, 0, asked=8),
           "new_source": _coverage_source(8, 8)}
    now["synthetic"]["paths"]["field"]["key"] = 0.5
    now["synthetic"]["paths"]["field"]["types"] = ["dict"]
    now["synthetic"]["paths"]["new"] = {"key": 1.0, "value": 0.0, "types": ["list"]}
    receipt = _freeze_scenario(old, now, monitor=True, unobserved=[("blind", "HTTP 503")])
    names = [name for name, _ in receipt["failures"]]
    check("noncommon and unobserved paths do not collapse", receipt["collapses"] == [])
    check("new engine path still fails the normal monitor",
          "synthetic: no unmeasured new path in the engine" in names)
    check("removed engine path still fails the normal monitor",
          "synthetic: no path has silently left the engine" in names)
    check("missing key still fails the normal monitor",
          "synthetic: field still present in every probe" in names)
    check("new type still fails the normal monitor",
          "synthetic: field sends no new JSON type" in names)
    check("blind source asserts nothing about its fields",
          "BLIND blind" in receipt["stdout"] and not any(name.startswith("blind:") for name in names))
    check("normal status priority remains red before blind",
          receipt["results"] == [1] and receipt["status"]["status"] == "red"
          and receipt["status"]["unobserved_sources"] == ["blind"]
          and receipt["status"]["collapsed_paths"] == [])
    check("structural monitor keeps baseline bytes and one measurement",
          receipt["before"] == receipt["after"] and len(receipt["measures"]) == 1)
    check("structural controls make no network or public data change",
          not receipt["network"] and receipt["protected"])


def test_freeze_acceptance_uses_the_existing_offline_registration():
    """The additive cases run through the unchanged discovered runner and CI step."""
    with open(os.path.join(ROOT, ".github", "workflows", "test.yml"), encoding="utf-8") as f:
        workflow = f.read()
    check("the observed guard remains registered exactly once",
          workflow.count("run: python tests/test_upstream_contract_is_observed.py") == 1)
    check("the discovered runner sees every new freeze case",
          sum(name.startswith("test_") for name in globals()) == 12)


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
