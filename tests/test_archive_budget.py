"""The snapshot archive stays public in git until a measured, pre-registered threshold.

DECISIONS B15. The archive is committed to a public repository four times a day, and that
was decided on numbers rather than argued: `.git` was 5.8 MB packed after six days, growing
0.95 MB/day, which reaches 200 MB in about 205 days. Publishing buys reproducibility -- a
hostile review of the launch post had just found a stranger could not reproduce our figures
at all -- and moving the archive to R2 would make W7's future "would it have warned you"
claim unverifiable by anyone outside the project.

So the move to R2 is not cancelled. It is **triggered**, and this is the trigger. A plan to
do something "when the repo gets big" is a wish; a test that fails on the day is a date.

Two properties this deliberately has:

**It measures the packed repository, not the working tree.** `du -sh bench/snapshots` says
12 MB and `.git` says 5.8 MB, and the second is what a person cloning this actually pays.
This project once filed a storage ticket off the working-tree number and was wrong by 18x.

**It warns before it fails.** Crossing the threshold is not an emergency -- it is a day of
work that should be scheduled, so the run goes yellow at 80% and red at 100%.

Run: python tests/test_archive_budget.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The number in DECISIONS B15. Changing it here changes the decision, so it must be
# changed there too -- and the test below fails if the two disagree.
BUDGET_MB = 200
WARN_AT = 0.8
RETAIN_DAYS = 90

_PASSED = 0
_FAILURES = []
_WARNINGS = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def packed_mb():
    """What the server stores, which is what a cloner pays -- not the working tree."""
    total = 0
    git_dir = os.path.join(ROOT, ".git")
    for root, _, files in os.walk(git_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return total / 1048576.0


def test_the_repository_is_inside_its_budget():
    print("\n[B15] the archive's cost to a cloner")
    mb = packed_mb()
    print("       .git is %.1f MB of a %d MB budget (%.0f%%)"
          % (mb, BUDGET_MB, 100.0 * mb / BUDGET_MB))

    check("the packed repository is under budget", mb < BUDGET_MB,
          "%.1f MB >= %d MB -- DECISIONS B15 says move snapshots older than %d days to "
          "R2 now and keep a rolling window in git" % (mb, BUDGET_MB, RETAIN_DAYS))

    if BUDGET_MB * WARN_AT <= mb < BUDGET_MB:
        _WARNINGS.append(
            "%.1f MB is past %.0f%% of the budget. B15's move to R2 is close: schedule it "
            "rather than waiting for a red build." % (mb, WARN_AT * 100))
        print("  WARN  approaching the budget: %s" % _WARNINGS[-1])


def test_the_decision_says_the_same_number():
    """A threshold in a test and a different one in the decision is two decisions."""
    print("\n[B15] the test and the decision agree")
    path = os.path.join(ROOT, "docs", "DECISIONS.md")
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    row = [l for l in text.splitlines() if l.startswith("| B15 |")]
    check("B15 exists in DECISIONS.md", bool(row))
    if not row:
        return
    check("it states the same budget", "%d MB" % BUDGET_MB in row[0],
          "test says %d MB; the row does not" % BUDGET_MB)
    check("it states the same retention", "%d" % RETAIN_DAYS in row[0],
          "test retains %d days; the row does not say so" % RETAIN_DAYS)
    check("it names this test as the enforcement", "test_archive_budget" in row[0],
          "a decision whose enforcement is nobody is a wish")


def _archive_call(root, stdout=None, failure=None, environ=None, stderr=b"", code=0):
    """Call the real helper with isolated globals and optional command responses."""
    import contextlib
    import subprocess
    import types

    namespace = dict(globals())
    namespace["ROOT"] = str(root)
    namespace["os"] = types.SimpleNamespace(**dict(vars(os), environ=dict(
        os.environ if environ is None else environ)))
    calls = []
    if stdout is not None or failure is not None:
        def run(*args, **kwargs):
            calls.append((args, kwargs))
            if failure is not None:
                raise failure
            output, error = stdout, stderr
            if kwargs.get("encoding") or kwargs.get("text"):
                if isinstance(output, bytes):
                    output = output.decode(kwargs.get("encoding", "utf-8"),
                                           kwargs.get("errors", "strict"))
                if isinstance(error, bytes):
                    error = error.decode(kwargs.get("encoding", "utf-8"),
                                         kwargs.get("errors", "strict"))
            return subprocess.CompletedProcess(args[0], code, output, error)
        namespace["subprocess"] = types.SimpleNamespace(**dict(vars(subprocess), run=run))
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        value = types.FunctionType(packed_mb.__code__, namespace)()
    return value, calls, output.getvalue()


def _archive_stats(**changes):
    values = {"count": "0", "size": "0", "in-pack": "3", "packs": "1",
              "size-pack": "2049", "prune-packable": "0", "garbage": "0",
              "size-garbage": "0"}
    values.update(changes)
    return "".join("%s: %s\n" % (key, value) for key, value in values.items()).encode("ascii")


def _archive_gate(value):
    """Exercise the actual budget function without changing its module globals."""
    import contextlib
    import types

    outcomes, warnings = [], []
    namespace = dict(globals(), packed_mb=lambda: value, _WARNINGS=warnings,
                     check=lambda *args: outcomes.append(args))
    output, error = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            types.FunctionType(test_the_repository_is_inside_its_budget.__code__, namespace)()
    except Exception as exc:
        error = type(exc).__name__
    return outcomes, warnings, output.getvalue(), error


def _archive_fixture():
    """All fixture writes and packing stay below a verified owned temporary root."""
    import contextlib
    from pathlib import Path
    import subprocess
    import tempfile

    @contextlib.contextmanager
    def fixture():
        with tempfile.TemporaryDirectory(prefix="vetagent-archive-budget-",
                                         ignore_cleanup_errors=True) as name:
            owned = Path(name).resolve()
            assert owned.parent == Path(tempfile.gettempdir()).resolve()
            assert owned.name.startswith("vetagent-archive-budget-")
            assert not (owned / ".git").exists()
            env = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("GIT_")}
            env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

            def git(repo, *args):
                repo = Path(repo).resolve()
                assert repo == owned or owned in repo.parents
                result = subprocess.run(["git", "-C", str(repo), *args], env=env,
                                        capture_output=True, timeout=20, check=True)
                return result.stdout

            repo, linked, unrelated = owned / "normal", owned / "linked", owned / "elsewhere"
            repo.mkdir()
            unrelated.mkdir()
            git(repo, "init", "--quiet", "--initial-branch=main")
            yield owned, repo, linked, unrelated, git
    return fixture()


def test_packed_storage_native_normal_linked_and_unrelated_bytes():
    from pathlib import Path

    with _archive_fixture() as (owned, repo, linked, unrelated, git):
        empty, _, _ = _archive_call(repo)
        check("a native empty object database measures zero", empty == 0)
        (repo / "payload").write_bytes(bytes(range(256)) * 200)
        git(repo, "add", "payload")
        git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")
        loose, _, _ = _archive_call(repo)
        check("native loose-only storage is unavailable rather than zero", loose is None)
        git(repo, "repack", "-ad")
        git(repo, "worktree", "add", "--quiet", "--detach", str(linked))
        pack_dir = repo / ".git" / "objects" / "pack"
        exact_bytes = sum(path.stat().st_size for path in pack_dir.iterdir()
                          if path.suffix in (".pack", ".idx"))
        native = git(repo, "count-objects", "-v").decode("ascii")
        native_kib = int(dict(line.split(": ", 1) for line in native.splitlines())["size-pack"])
        expected = (exact_bytes // 1024) / 1024.0
        check("native KiB accounting equals pack plus index bytes at Git precision",
              exact_bytes > 0 and native_kib == exact_bytes // 1024)
        previous = Path.cwd()
        try:
            os.chdir(unrelated)
            normal, _, _ = _archive_call(repo)
            worktree, _, _ = _archive_call(linked)
            check("normal checkout measures only the native packed quantity", normal == expected)
            check("linked checkout resolves the same shared packed quantity", worktree == expected)
            (repo / ".git" / "unrelated-metadata").write_bytes(b"metadata" * 32000)
            (repo / "untracked-checkout").write_bytes(b"checkout" * 16000)
            (pack_dir / "unrelated.rev").write_bytes(b"reverse index" * 2000)
            (pack_dir / "unrelated.mtimes").write_bytes(b"mtime" * 2000)
            (repo / "loose-payload").write_bytes(b"new loose object" * 8000)
            git(repo, "hash-object", "-w", "loose-payload")
            normal_after, _, _ = _archive_call(repo)
            linked_after, _, _ = _archive_call(linked)
            check("unrelated metadata and mixed loose storage leave normal packs unchanged",
                  normal_after == expected)
            check("unrelated metadata and mixed loose storage leave linked packs unchanged",
                  linked_after == expected)
        finally:
            os.chdir(previous)


def test_packed_storage_command_contract_and_warning():
    import subprocess

    environment = dict(os.environ, GIT_DIR="elsewhere", GIT_COMMON_DIR="elsewhere",
                       GIT_WORK_TREE="elsewhere", GIT_OBJECT_DIRECTORY="elsewhere",
                       GIT_ALTERNATE_OBJECT_DIRECTORIES="elsewhere", GIT_INDEX_FILE="elsewhere",
                       GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.bare",
                       GIT_CONFIG_VALUE_0="true", GIT_NAMESPACE="elsewhere",
                       CI="preserve-ci", GITHUB_ACTIONS="preserve-actions")
    before = dict(environment)
    value, calls, output = _archive_call(ROOT, _archive_stats(), environ=environment,
                                         stderr=b"warning: private-path-marker\n")
    check("valid statistics survive a native warning", value == 2049 / 1024.0)
    check("packed measurement does not print arbitrary command output", output == "")
    check("measurement invokes Git once", len(calls) == 1)
    if calls:
        args, kwargs = calls[0]
        check("Git receives fixed argv selecting ROOT", args == (["git", "-C", ROOT,
              "count-objects", "-v"],))
        check("Git runs without a shell", kwargs.get("shell", False) is False)
        check("Git captures both output streams", kwargs.get("capture_output") is True or
              (kwargs.get("stdout") is subprocess.PIPE and kwargs.get("stderr") is subprocess.PIPE))
        check("Git has a finite command timeout", type(kwargs.get("timeout")) in (int, float)
              and 0 < kwargs["timeout"] <= 30)
        routed = kwargs.get("env", {})
        check("inherited Git routing and injected config are removed",
              not any(key.upper().startswith("GIT_") for key in routed))
        check("CI flags survive environment isolation", routed.get("CI") == "preserve-ci"
              and routed.get("GITHUB_ACTIONS") == "preserve-actions")
    check("the caller environment stays exact", environment == before)


def test_packed_storage_unavailable_and_empty_command_responses():
    import subprocess

    for label, failure in (
            ("missing Git", FileNotFoundError("private-exception-marker")),
            ("unusable Git", PermissionError("private-exception-marker")),
            ("command timeout", subprocess.TimeoutExpired("private-command-marker", 1))):
        value, _, output = _archive_call(ROOT, failure=failure)
        check(label + " is unavailable", value is None)
        check(label + " exposes no exception text", output == "")
    value, _, output = _archive_call(ROOT, _archive_stats(), code=1,
                                     stderr=b"private-stderr-marker")
    check("failed Git is unavailable even with valid-looking output", value is None)
    check("failed Git exposes no stderr", output == "")
    empty = _archive_stats(**{"in-pack": "0", "packs": "0", "size-pack": "0"})
    value, _, _ = _archive_call(ROOT, empty)
    check("complete empty statistics measure a genuine zero", value == 0)
    value, _, _ = _archive_call(ROOT, empty.replace(b"count: 0", b"count: 1"))
    check("loose-only nonempty statistics are unavailable", value is None)
    value, _, _ = _archive_call(ROOT, _archive_stats(count="50", size="100000"))
    check("mixed storage measures existing packs without adding loose bytes", value == 2049 / 1024.0)


def test_packed_storage_refuses_malformed_or_incomplete_statistics():
    valid = _archive_stats()
    cases = [("empty output", b""), ("undecodable output", b"\xff"),
             ("arbitrary output", b"private-stdout-marker"),
             ("non-ASCII integer", valid.replace(b"2049", "\u0661".encode("utf-8"))),
             ("duplicate required statistic", valid + b"size-pack: 1\n")]
    for key in ("count", "size", "in-pack", "packs", "size-pack", "prune-packable",
                "garbage", "size-garbage"):
        cases.append(("missing " + key, b"".join(line for line in valid.splitlines(keepends=True)
                                                if not line.startswith((key + ":").encode("ascii")))))
        for invalid in ("-1", "+1", "1.5", "1e3", "NaN", "", "9223372036854775808"):
            cases.append((key + " invalid " + repr(invalid), _archive_stats(**{key: invalid})))
    cases.extend((
        ("pack bytes without packs", _archive_stats(packs="0")),
        ("pack objects without packs", _archive_stats(packs="0", **{"size-pack": "0"})),
        ("packs without objects", _archive_stats(**{"in-pack": "0"})),
        ("packs without packed bytes", _archive_stats(**{"size-pack": "0"})),
        ("malformed delimiter", valid.replace(b"size-pack:", b"size-pack=")),
        ("malformed integer tail", valid.replace(b"size-pack: 2049", b"size-pack: 2049 private-tail")),
    ))
    for label, response in cases:
        value, _, output = _archive_call(ROOT, response)
        check(label + " is unavailable", value is None)
        check(label + " does not leak output", output == "")


def test_budget_gate_rejects_unknown_and_keeps_literal_boundaries():
    check("the pre-registered constants stay literal",
          (BUDGET_MB, WARN_AT, RETAIN_DAYS) == (200, 0.8, 90))
    outcomes, warnings, output, error = _archive_gate(None)
    check("the actual gate rejects unavailable measurement without formatting it",
          error is None and len(outcomes) == 1 and outcomes[0][1] is False
          and "unavailable" in " ".join(str(item) for item in outcomes[0]).lower())
    check("unknown measurement is never a numeric green or warning", not warnings
          and not any(item[1] for item in outcomes) and "0.0 MB" not in output)
    for value, under, warned in ((0, True, False), (159.999, True, False),
                                 (160, True, True), (199.999, True, True),
                                 (200, False, False), (200.001, False, False)):
        outcomes, warnings, output, error = _archive_gate(value)
        budget = [item for item in outcomes if item[0] == "the packed repository is under budget"]
        check("literal boundary %.3f retains budget behavior" % value,
              error is None and len(budget) == 1 and budget[0][1] is under)
        check("literal boundary %.3f retains warning behavior" % value,
              bool(warnings) is warned)
        check("literal boundary %.3f retains the retention message" % value,
              len(budget) == 1 and "move snapshots older than 90 days to R2 now and keep a rolling window in git"
              in budget[0][2])
        if warnings:
            check("literal boundary %.3f keeps the warning wording" % value,
                  "is past 80% of the budget. B15's move to R2 is close: schedule it rather than waiting for a red build."
                  in warnings[0])


def main():
    print("=" * 68)
    print("B15: the archive stays public until a measured threshold")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    for w in _WARNINGS:
        print("  WARN  %s" % w)
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
