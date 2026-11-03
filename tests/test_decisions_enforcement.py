"""test_decisions_enforcement.py — the enforcement column has to be true.

DECISIONS.md's whole premise is in its own header: "docs rot, and they rot silently. So
every decision also has to answer: what is enforcing it?" The enforcement column names a
test, and a named test is called "**the strongest kind** -- the rule alarms on its own."

Nothing checked that those names existed.

An external audit found two that did not. E20 cited `test_owner_power_selectors_are_real`;
the real name is `test_selectors_are_real`. E12 cited
`test_liquidity_prefers_canonical_chain`; no such test has ever existed -- the coverage
lives inside `test_liquidity_picks_the_right_pool`. Both are naming drift rather than
missing coverage, which is precisely why nobody noticed: the rule was enforced, the
document just pointed at the wrong guard. A reader auditing the project would have gone
looking for a test that is not there and drawn their own conclusion.

R11 built a currency check for ROUNDS.md and a shape check for BACKLOG.md and left this
one unguarded -- the file whose entire point is enforcement was the file with none.

Run:  python tests/test_decisions_enforcement.py
"""

import io
import os
import re
import sys

import contextlib
import subprocess
import tempfile
from unittest.mock import patch

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DECISIONS = os.path.join(ROOT, "docs", "DECISIONS.md")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

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


def defined_test_names():
    """Every test function defined anywhere under tests/."""
    names = set()
    for fn in sorted(os.listdir(TESTS_DIR)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(TESTS_DIR, fn), encoding="utf-8") as f:
            for m in re.finditer(r"^def (test_[A-Za-z0-9_]+)", f.read(), re.M):
                names.add(m.group(1))
    return names


def cited_test_names(text):
    """Every `test_...` cited anywhere in DECISIONS.md, with its row id."""
    out = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        row_id = cells[1] if len(cells) > 2 else "?"
        for m in re.finditer(r"`(test_[A-Za-z0-9_]+)`", line):
            out.append((row_id, m.group(1)))
    return out


def test_every_test_file_runs_in_ci():
    """A guard CI never invokes is a guard nobody will ever see fail.

    .github/workflows/test.yml names each suite in its own step. That is readable, and it
    means adding a test file is silently a no-op in CI until someone also edits the
    workflow. This project has already paid for that shape twice -- test_owner_powers.py
    ran a hand-maintained list of three functions, so a fourth passed by never executing;
    and CI was red from R11 for days with nobody looking.

    So the list is allowed to stay explicit, but it is no longer allowed to be incomplete.
    """
    print("\n[decisions] every test file is wired into CI")
    workflow = os.path.join(ROOT, ".github", "workflows", "test.yml")
    check("the workflow exists", os.path.exists(workflow), workflow)
    if not os.path.exists(workflow):
        return
    with open(workflow, encoding="utf-8") as f:
        ci = f.read()
    files = sorted(fn for fn in os.listdir(TESTS_DIR)
                   if fn.startswith("test_") and fn.endswith(".py"))
    orphans = [fn for fn in files if fn not in ci]
    check("no test file is missing from the workflow", not orphans, str(orphans))


def test_every_named_test_exists():
    """The strongest enforcement kind must actually be enforcing something."""
    print("\n[decisions] every test named in the enforcement column exists")
    with open(DECISIONS, encoding="utf-8") as f:
        text = f.read()
    defined = defined_test_names()
    # A row may legitimately name a whole test FILE rather than one function -- "the
    # sellability gap is covered by tests/test_owner_powers.py" is a real enforcement.
    # Accept either, and only fail when neither exists.
    defined |= {fn[:-3] for fn in os.listdir(TESTS_DIR) if fn.endswith(".py")}
    cited = cited_test_names(text)
    check("the file cites at least a dozen tests", len(cited) >= 12,
          "%d cited" % len(cited))
    missing = [(rid, n) for rid, n in cited if n not in defined]
    check("every cited test is defined under tests/", not missing,
          "; ".join("%s -> %s" % (rid, n) for rid, n in missing))


def test_the_row_count_is_honest():
    """The file states its own size, and that number drifted too.

    DECISIONS.md said 54 and BACKLOG.md W8 said 63; the real count was 55. A file that
    miscounts its own rows is weak evidence for every other number in it, and this one is
    trivially derivable.
    """
    print("\n[decisions] the stated row count matches the table")
    with open(DECISIONS, encoding="utf-8") as f:
        text = f.read()
    rows = [ln for ln in text.splitlines()
            if re.match(r"^\|\s*[A-Z]+\d+\s*\|", ln)]
    stated = re.search(r"table is at (\d+) rows", text)
    check("the file states its row count", bool(stated),
          "no 'table is at N rows' line")
    if stated:
        check("and the count is right",
              int(stated.group(1)) == len(rows),
              "states %s, actual %d" % (stated.group(1), len(rows)))


def test_no_test_function_is_unreachable_by_its_own_runner():
    """A test defined and never called is worse than no test: it reads as coverage.

    Every file here is its own runner -- `python tests/test_x.py` -- and a runner that names
    its tests by hand goes stale the moment somebody adds one. On 2026-09-10 a new test was
    added to `tests/test_backfill.py`, whose `main()` held a hand-written tuple of four
    function names. The file printed "12 passed, 0 failed" with eleven of its own checks
    never executed, and it was green in CI.

    This repo already records that incident once -- "four hand-maintained test runners were
    silently skipping tests, including CI's own step list" -- and the fix at the time was to
    repair the four. Repairing instances is not closing a class.

    So: a test file either uses the discovery idiom, or names every one of its own test
    functions inside `main()`. Static, because running twenty files to find out costs a
    minute and the answer is in the source.
    """
    print(chr(10) + "[enforcement] every test a file defines is a test that runs")
    tests_dir = os.path.join(ROOT, "tests")
    checked = 0
    for name in sorted(os.listdir(tests_dir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        src = io.open(os.path.join(tests_dir, name), encoding="utf-8").read()
        defined = set(re.findall(r"^def (test_[A-Za-z0-9_]+)", src, re.M))
        if not defined:
            continue                       # script-style file with no test functions
        checked += 1
        if re.search(r"startswith\(['\"]test_['\"]\)", src):
            continue                       # discovers its own tests
        body = src[src.index("def main("):] if "def main(" in src else src
        missing = sorted(f for f in defined if f not in body)
        check("%s: runner reaches all %d of its tests" % (name, len(defined)),
              not missing,
              "hand-listed runner is missing %s -- switch to the discovery idiom"
              % ", ".join(missing))
    check("test files with test functions were found", checked >= 15, str(checked))


def _registration_fixture_checks(case):
    """Call the real registration guard with inert, external fixture data only."""
    source_root = os.path.realpath(ROOT)
    parser_path = os.path.join(source_root, ".github", "scripts", "offline_suite.py")
    with open(parser_path, "rb") as source:
        parser_bytes = source.read()
    parent = os.path.realpath(tempfile.gettempdir())
    try:
        inside_source = os.path.commonpath((source_root, parent)) == source_root
    except ValueError:
        inside_source = False  # Different Windows drives cannot share a parent.
    if inside_source:
        raise AssertionError("registration fixtures require external temporary storage")
    cursor = parent
    while True:
        if os.path.lexists(os.path.join(cursor, ".git")):
            raise AssertionError("registration fixture TEMP must be outside a Git checkout")
        above = os.path.dirname(cursor)
        if above == cursor:
            break
        cursor = above
    commands = {
        "native": "python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16",
        "clock": "python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3",
        "verify_source": "python tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf",
        "offline_backfill": "python tests/test_backfill.py --offline",
        "live_upstream": "python tests/test_upstream_contract.py",
    }
    observed = []
    def capture(label, condition, detail=""):
        observed.append((label, bool(condition), str(detail)))
    def forbidden(*args, **kwargs):
        raise AssertionError("registration fixtures cannot execute commands or recurse into main")
    with tempfile.TemporaryDirectory(prefix="registration-fixture-", dir=parent) as directory:
        tests = os.path.join(directory, "tests")
        scripts = os.path.join(directory, ".github", "scripts")
        workflows = os.path.join(directory, ".github", "workflows")
        tools = os.path.join(directory, "tools")
        for path in (tests, scripts, workflows, tools):
            os.makedirs(path)
        stub = b'raise AssertionError("registration fixture body must never execute")\n'
        for name in tuple(case["test_files"]) + ("inert.py",):
            if os.path.basename(name) != name or not name.endswith(".py"):
                raise AssertionError("fixture inventory must contain local Python basenames")
            with open(os.path.join(tests, name), "xb") as target:
                target.write(stub)
        with open(os.path.join(tools, "engine_versions.py"), "xb") as target:
            target.write(b'raise AssertionError("registration must never import SourceAPI")\n')
        with open(os.path.join(scripts, "offline_suite.py"), "xb") as target:
            target.write(parser_bytes)
        lines = ["name: inert registration fixture"]
        lines.extend("# " + comment for comment in case.get("comment_only", ()))
        lines.append("jobs:")
        jobs = [] if case.get("omit_test_job") else [("test", case.get("test_job_commands", ()))]
        jobs.extend(case.get("other_jobs", {}).items())
        for job, values in jobs:
            lines.extend(("  " + job + ":", "    steps:"))
            for index, value in enumerate(values):
                label = case.get("step_label", "inert fixture step") if job == "test" and index == 0 else "inert fixture step"
                lines.append("      - name: " + label)
                value = commands.get(value, value)
                if case.get("workflow_shape") and job == "test" and index == 0:
                    lines.extend(("        run: >", "          " + value))
                else:
                    lines.append("        run:" + (" " + value if value is not None else ""))
        text = "\n".join(lines) + "\n"
        if "stray_break_codepoint" in case:
            text += "# fixture comment" + chr(case["stray_break_codepoint"]) + "still one YAML comment\n"
        with open(os.path.join(workflows, "test.yml"), "x", encoding="utf-8", newline="\n") as target:
            target.write(text)
        with patch.dict(globals(), {"ROOT": directory, "TESTS_DIR": tests,
                                   "check": capture, "main": forbidden,
                                   "_FAILURES": [], "_PASSED": 0}), \
                patch.object(subprocess, "Popen", side_effect=forbidden), \
                patch.object(os, "system", side_effect=forbidden), \
                patch.object(os, "popen", side_effect=forbidden), \
                contextlib.redirect_stdout(io.StringIO()):
            test_every_test_file_runs_in_ci()
        with open(os.path.join(scripts, "offline_suite.py"), "rb") as source:
            if source.read() != parser_bytes:
                raise AssertionError("the copied parser must stay byte-exact")
    case_id = case["id"]
    workflow = [item for item in observed if item[0] == "the workflow exists"]
    orphan = [item for item in observed if item[0] == "no test file is missing from the workflow"]
    errors = [item for item in observed if not item[1] and item[0] not in
              {"the workflow exists", "no test file is missing from the workflow"}]
    check(case_id + ": actual guard workflow check", len(workflow) == 1 and workflow[0][1])
    check(case_id + ": overall registration outcome",
          bool(observed) and all(item[1] for item in observed) == case["expected_accept"])
    expected_orphans = sorted(case["expected_orphans"])
    check(case_id + ": exact orphan finding",
          len(orphan) == 1 and orphan[0][1] == (not expected_orphans)
          and orphan[0][2] == str(expected_orphans),
          "expected %s; observed %s" % (expected_orphans, [(item[1], item[2]) for item in orphan]))
    if case.get("expected_registration_error"):
        missing = case.get("missing_file")
        check(case_id + ": explicit registration error",
              bool(errors) and (missing is None or any(missing in item[2] for item in errors)),
              "expected explicit registration error" + (" for " + missing if missing else ""))


def test_registration_direct_and_maintained_commands():
    cases = (
        {"id": "P01", "test_files": ["test_w40_native.py"], "test_job_commands": ["native"],
         "expected_accept": True, "expected_orphans": []},
        {"id": "P02", "test_files": ["test_w40_native_clock.py"], "test_job_commands": ["clock"],
         "expected_accept": True, "expected_orphans": []},
        {"id": "P03", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["native", "verify_source", "clock"], "expected_accept": True, "expected_orphans": []},
        {"id": "P04", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python tests/test_w40_native.py", "python tests/test_w40_native_clock.py"],
         "expected_accept": True, "expected_orphans": []},
        {"id": "P05", "test_files": ["test_backfill.py", "test_unit_direct.py"],
         "test_job_commands": ["offline_backfill", "python tests/test_unit_direct.py --unit"],
         "expected_accept": True, "expected_orphans": []},
        {"id": "P06", "test_files": ["test_unit_direct.py", "test_upstream_contract.py"],
         "test_job_commands": ["python tests/test_unit_direct.py"], "other_jobs": {"upstream-contract": ["live_upstream"]},
         "expected_accept": True, "expected_orphans": []},
    )
    for case in cases:
        _registration_fixture_checks(case)


def test_registration_rejects_textual_wiring():
    cases = (
        {"id": "N01", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python -c pass"], "comment_only": ["test_w40_native.py", "test_w40_native_clock.py"],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"]},
        {"id": "N02", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python -c pass"], "other_jobs": {"build": ["native", "clock"]},
         "expected_accept": False, "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"]},
        {"id": "N03", "test_files": ["test_w40_native.py"],
         "test_job_commands": ["python -c \"print('tests/test_w40_native.py')\""],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N04", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python -c pass"], "step_label": "test_w40_native.py test_w40_native_clock.py",
         "expected_accept": False, "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"]},
        {"id": "N05", "test_files": ["test_w40_native.py"], "test_job_commands": [None],
         "step_label": "tests/test_w40_native.py", "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N06", "test_files": ["test_w40_native.py"], "omit_test_job": True,
         "comment_only": ["tests/test_w40_native.py"], "other_jobs": {"build": ["native"]},
         "expected_accept": False, "expected_orphans": ["test_w40_native.py"], "expected_registration_error": True},
    )
    for case in cases:
        _registration_fixture_checks(case)


def test_registration_rejects_unqualified_selectors():
    cases = (
        {"id": "N07", "test_files": ["test_w40_native.py"],
         "test_job_commands": ["python tools/engine_versions.py maintained-test UNIT_UNKNOWN git-lf native-all16"],
         "comment_only": ["test_w40_native.py"], "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N08", "test_files": ["test_w40_native.py"],
         "test_job_commands": ["python tools/engine_versions.py maintained-test w40-v1-e3ec46a observed-windows-crlf native-all16"],
         "comment_only": ["test_w40_native.py"], "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N09", "test_files": ["test_w40_native.py"],
         "test_job_commands": ["python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all13"],
         "comment_only": ["test_w40_native.py"], "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N10", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf native-all16 extra",
                               "python tools/engine_versions.py maintained-test w40-v1-e3ec46a git-lf clock-all3 extra"],
         "comment_only": ["test_w40_native.py", "test_w40_native_clock.py"], "expected_accept": False,
         "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"]},
        {"id": "N11", "test_files": ["test_w40_native.py"],
         "test_job_commands": ["python tests/test_w40_native.py NativeAcceptance",
                               "python tools/engine_versions.py adapter-test w40-v1-e3ec46a git-lf InterruptedProgressStagingTests"],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py"]},
        {"id": "N12", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native.py",
                               "python tools/engine_versions.py legacy-test w40-v1-e3ec46a git-lf tests/test_w40_native_clock.py", "verify_source"],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"]},
    )
    for case in cases:
        _registration_fixture_checks(case)


def test_registration_parser_and_inventory_fail_closed():
    cases = (
        {"id": "N13", "test_files": ["test_w40_native.py"], "test_job_commands": ["native"],
         "workflow_shape": "folded run: > containing valid native command", "comment_only": ["test_w40_native.py"],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py"], "expected_registration_error": True},
        {"id": "N14", "test_files": ["test_w40_native.py", "test_w40_native_clock.py"],
         "test_job_commands": ["python tests/test_w40_native.py && python tests/test_w40_native_clock.py"],
         "expected_accept": False, "expected_orphans": ["test_w40_native.py", "test_w40_native_clock.py"], "expected_registration_error": True},
        {"id": "N15", "test_files": ["test_w40_native.py"], "test_job_commands": ["native"],
         "comment_only": ["test_w40_native.py"], "stray_break_codepoint": 8232,
         "expected_accept": False, "expected_orphans": ["test_w40_native.py"], "expected_registration_error": True},
        {"id": "N16", "test_files": ["test_w40_native_clock.py"], "test_job_commands": ["native", "clock"],
         "comment_only": ["test_w40_native_clock.py"], "missing_file": "test_w40_native.py",
         "expected_accept": False, "expected_orphans": [], "expected_registration_error": True},
        {"id": "N17", "test_files": ["test_w40_native.py", "test_w40_native_clock.py", "test_unit_orphan.py"],
         "test_job_commands": ["native", "clock"], "expected_accept": False, "expected_orphans": ["test_unit_orphan.py"]},
        {"id": "N18", "test_files": ["test_unit_direct.py", "test_upstream_contract.py"],
         "test_job_commands": ["python tests/test_unit_direct.py"], "other_jobs": {"build": ["live_upstream"]},
         "expected_accept": False, "expected_orphans": ["test_upstream_contract.py"]},
    )
    for case in cases:
        _registration_fixture_checks(case)


def main():
    print("=" * 68)
    print("DECISIONS.md enforcement column")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
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
