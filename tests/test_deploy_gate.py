"""test_deploy_gate.py -- production deploys only from a commit on which the offline suite passed.

deploy.yml ships production on a push to master that touches src/, pyproject.toml,
wrangler.jsonc or deploy.yml itself, and on a manual dispatch. Until 2026-09-29 its only tests
were two files typed into its "Regression tests" step, test_risk.py and test_mcp.py, while the
tests workflow's offline `test` job ran 27 steps. The two workflows start side by side on the
same push and the deploy does not wait for the tests, so a push to src/ that broke any of the
other 25 steps deployed anyway -- among them the steps that pin that nothing identifying is
recorded, that the published figures match the benchmark, and that nothing private is
published.

The deploy job now runs .github/scripts/offline_suite.py, which reads that job's steps from
test.yml when it runs. This pins the seam, from the files rather than from a typed list:

  * The runner runs exactly the `run:` steps of the `test` job, in file order, and every one
    of them even after a red one. It exits 0 only when every step passed and no tracked file
    was modified, 2 when it finds no such job or no steps in it, and it reports a `run:` it
    cannot run as a red step. All of that is shown on synthetic workflows, in a scratch
    repository without a lead/ folder, so none of it depends on the real suite passing or on
    the lead workflow's folder existing.
  * lead/checks.py is the same tool: whatever the runner prints and exits with, it does.
  * The deploy job checks out the whole history the suite reads, runs the runner after Python
    is set up and before anything installs deploy tooling or deploys, under the deploy step's
    own condition, with nothing that lets a red gate pass. And it names no test file of its
    own, so there is no second list to drift.

The real suite is never run from here: this file is one of its steps.

Run:  python tests/test_deploy_gate.py
"""

import contextlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER_REL = ".github/scripts/offline_suite.py"
WRAPPER_REL = "lead/checks.py"
RUNNER = os.path.join(ROOT, *RUNNER_REL.split("/"))
WRAPPER = os.path.join(ROOT, *WRAPPER_REL.split("/"))
TEST_YML = os.path.join(ROOT, ".github", "workflows", "test.yml")
DEPLOY_YML = os.path.join(ROOT, ".github", "workflows", "deploy.yml")

GATE = "python " + RUNNER_REL
THIS_STEP = "python tests/test_deploy_gate.py"

# A step that deploys; a step that installs or runs deploy tooling; and the status functions
# that let GitHub run a step after an earlier one failed. An `if:` without any of them is read
# as `success() && (...)`; with one, that default is gone -- `success() || x` included.
DEPLOYS = re.compile(r"wrangler\b.*\bdeploy\b")
TOOLING = re.compile(r"\buv\b|astral\.sh|wrangler")
STATUS_FUNCTIONS = re.compile(r"\b(always|failure|cancelled|success)\s*\(",
                              re.I)                 # named change (e): GitHub ignores the case

_FAILS = []
_PASSED = 0


def check(label, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  " + label)
    else:
        _FAILS.append(label)
        print("  FAIL  " + label + ("  " + detail if detail else ""))


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _tail(out, n=8):
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    return " | ".join(lines[-n:])


def _first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return "at #%d: %r against %r" % (i + 1, x, y)
    return "none" if len(a) == len(b) else "after #%d" % min(len(a), len(b))


# ---------------------------------------------------------------- reading a workflow
#
# Written apart from the runner's own parser, on purpose. Here a job ends only at the next
# job id, never at a comment, and steps are split at their list markers. Where the two
# readers disagree about the real test.yml, one of them is wrong, and a check goes red.

def _indent(line):
    return len(line) - len(line.lstrip(" "))


def jobs(text):
    """{job id: its lines} under the top-level `jobs:`, without comment or blank lines."""
    out, current, inside = {}, None, False
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if _indent(line) == 0:
            inside, current = re.match(r"^jobs:\s*$", line) is not None, None
            continue
        head = re.match(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$", line)
        if inside and head:
            current = head.group(1)
            out[current] = []
        elif inside and current:
            out[current].append(line)
    return out


def steps(job_lines):
    """The job's steps in order, each {"keys": {key: value}, "run": [commands], "with": {}}."""
    at = [i for i, l in enumerate(job_lines) if re.match(r"^\s*steps:\s*$", l)]
    if not at:
        return []
    base, items = _indent(job_lines[at[0]]), []
    for line in job_lines[at[0] + 1:]:
        if _indent(line) <= base:
            break
        item = re.match(r"^( *)- (.*)$", line)
        if item and (not items or len(item.group(1)) == items[0][0]):
            dash = len(item.group(1))
            items.append((dash, [" " * (dash + 2) + item.group(2)]))
        elif items:
            items[-1][1].append(line)
    return [_step(lines, dash + 2) for dash, lines in items]


def _step(lines, at):
    step, i = {"keys": {}, "run": [], "with": {}}, 0
    while i < len(lines):
        m = re.match(r"^ *([A-Za-z0-9_-]+):\s*(.*?)\s*$", lines[i])
        mine = m is not None and _indent(lines[i]) == at
        i += 1
        if not mine:
            continue
        key, value, children = m.group(1), m.group(2), []
        while i < len(lines) and _indent(lines[i]) > at:
            children.append(lines[i].strip())
            i += 1
        # Named change (e). A value is every line of it, as GitHub reads it: a block scalar's
        # lines, or a plain value with the lines that continue it. Read by its first line
        # alone, `|| true` on the next line, or an `if: >-`, passed the checks below.
        block = re.match(r"^[|>][0-9+-]*$", value) is not None
        whole = " ".join(children if block or not value else [value] + children)
        step["keys"][key] = value if key in ("with", "env") else whole
        if key == "run":
            step["run"] = children if block or not value else [whole]
        elif key == "with":
            for c in children:
                kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", c)
                if kv:
                    step["with"][kv.group(1)] = kv.group(2).strip("\"'")
    return step


def commands(text, job):
    return [c for s in steps(jobs(text).get(job, [])) for c in s["run"]]


def _cond(value):
    """A step's `if:` as GitHub evaluates it: no ${{ }}, no outer quotes, single spaces."""
    v = (value or "").strip()
    for _ in range(2):
        if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1].strip()
        m = re.match(r"^\$\{\{(.*)\}\}$", v, re.S)
        if m:
            v = m.group(1).strip()
    return re.sub(r"\s+", " ", v)


def _label(step, i):
    return step["keys"].get("name") or step["keys"].get("uses") or "step %d" % (i + 1)


# ---------------------------------------------------------------- scratch repositories
#
# The runner is copied from this tree, when the check runs, into a scratch git repository at
# the same relative path, beside a synthetic test.yml. It finds the workflow, and runs the
# steps, relative to where it is -- so this points the file in this tree at a temporary
# workflow without an option that deploy.yml could pass it. There is no lead/ folder in the
# scratch repository unless a check copies the wrapper in.

MARK = "\n".join([            # python mark.py NAME [STATUS]: record that NAME ran, exit STATUS
    "import sys",
    "with open('ran.txt', 'a') as f:",
    "    print(sys.argv[1], file=f)",
    "sys.exit(int(sys.argv[2]) if len(sys.argv) > 2 else 0)",
    "",
])
TOUCH = "\n".join([           # python touch.py: pass, and modify a tracked file
    "with open('tracked.txt', 'a') as f:",
    "    print('modified by a step', file=f)",
    "",
])
STUB = "\n".join([            # a runner that is not the runner
    "import sys",
    "print('stub runner ran')",
    "sys.exit(7)",
    "",
])

# Variables that would point git at a repository other than the scratch one.
_GIT_REPO_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                  "GIT_OBJECT_DIRECTORY")


def _env():
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REPO_VARS}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _write(path, text):
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _remove(tree):
    # git writes its objects read-only, and on Windows rmtree cannot delete those.
    for folder, dirs, files in os.walk(tree):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(folder, name), stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
            except OSError:
                pass
    shutil.rmtree(tree, ignore_errors=True)


@contextlib.contextmanager
def scratch(workflow):
    """A scratch git repository: the runner, `workflow` as its test.yml (none when None), the
    helpers the synthetic steps call, and one tracked file. Every file is staged."""
    tree = tempfile.mkdtemp(prefix="deploy-gate-")
    try:
        os.makedirs(os.path.join(tree, ".github", "scripts"))
        shutil.copyfile(RUNNER, os.path.join(tree, *RUNNER_REL.split("/")))
        if workflow is not None:
            _write(os.path.join(tree, ".github", "workflows", "test.yml"), workflow)
        _write(os.path.join(tree, "mark.py"), MARK)
        _write(os.path.join(tree, "touch.py"), TOUCH)
        _write(os.path.join(tree, "tracked.txt"), "tracked\n")
        for args in (["init", "-q"], ["add", "-A"]):
            subprocess.run(["git"] + args, cwd=tree, capture_output=True, env=_env(), check=True)
        yield tree
    finally:
        _remove(tree)


def add_wrapper(tree):
    os.makedirs(os.path.join(tree, "lead"))
    shutil.copyfile(WRAPPER, os.path.join(tree, *WRAPPER_REL.split("/")))


def run(tree, script):
    """(exit status, everything printed) of `python <script>` in the scratch repository."""
    p = subprocess.run([sys.executable, os.path.join(tree, *script.split("/"))], cwd=tree,
                       capture_output=True, encoding="utf-8", errors="replace", env=_env(),
                       timeout=600)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ran(tree):
    """What the synthetic steps recorded, in the order they ran."""
    path = os.path.join(tree, "ran.txt")
    return read(path).split() if os.path.exists(path) else []


def statuses(out):
    """The status of each step line the runner printed, in order."""
    return re.findall(r"^(ok|RED) ", out, re.M)


def printed_commands(out):
    """The command of each step line the runner printed, in order."""
    return re.findall(r"^(?:ok|RED) +\d+\.\ds  (.+?)(?:  \| .*)?$", out, re.M)


def untimed(out):
    return re.sub(r" *\d+\.\ds\b", " #s", out)


# ---------------------------------------------------------------- synthetic workflows

GREEN = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: first
        run: python mark.py one
      # a comment between two steps
      - name: a block with two commands and a comment
        run: |
          python mark.py two
          # a comment inside the block
          python mark.py three
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: last
        run: python mark.py four

  # the jobs after this one are not the offline suite
  other:
    runs-on: ubuntu-latest
    steps:
      - name: a step of another job
        run: python mark.py other
"""

RED = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: passes
        run: python mark.py one
      - name: fails
        run: python mark.py two 1
      - name: passes after a red step
        run: python mark.py three
      - name: fails after it too
        run: python mark.py four 3
"""

NO_JOB = """\
name: tests
on: push
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - name: a step of a job that is not called test
        run: python mark.py tests
"""

NO_STEPS = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
  other:
    runs-on: ubuntu-latest
    steps:
      - name: a step of another job
        run: python mark.py other
"""

UNSUPPORTED = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: supported
        run: python mark.py one
      - name: a shell command
        run: echo hello
      - name: an empty block
        run: |
          # nothing to run
      - name: supported after them
        run: python mark.py two
"""

TRACKED = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: passes, and modifies a tracked file
        run: python touch.py
      - name: passes
        run: python mark.py one
"""

# Named change (a). A comment at the jobs' indentation between two steps is still inside the
# job, and so is a blank line: YAML, and so GitHub, reads every step after them.
COMMENTED = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: before the comment
        run: python mark.py one
  # a comment at the jobs' indentation, between two steps of the test job
      - name: after the comment
        run: python mark.py two

      - name: after a blank line
        run: python mark.py three

  # a comment between two jobs
  other:
    runs-on: ubuntu-latest
    steps:
      - name: a step of another job
        run: python mark.py other
"""

# Named change (b). A `run:` that joins two commands: GitHub's shell runs both, and a runner
# that splits on spaces runs the first with the rest as its arguments. The helper ignores
# arguments it does not expect, as most test files here do, so nothing goes red by itself.
QUIET = "\n".join([           # python quiet.py NAME ...: record NAME, ignore the rest, pass
    "import sys",
    "with open('ran.txt', 'a') as f:",
    "    print(sys.argv[1], file=f)",
    "",
])

CHAINED_AND = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: before
        run: python mark.py one
      - name: two commands joined with &&
        run: python quiet.py two && python quiet.py three
      - name: after
        run: python mark.py four
"""

CHAINED_SEMICOLON = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: before
        run: python mark.py one
      - name: two commands joined with ;
        run: python quiet.py two; python quiet.py three
      - name: after
        run: python mark.py four
"""

# Named change (c). Three shapes valid YAML allows that a runner reading line by line can take
# for fewer commands than GitHub runs. A step whose first key is `run` must run, a last,
# guard-like step included; a flow-style step and a `run:` value continued on the next line
# must be refused and named, not skipped.
DASH_RUN = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python mark.py one
      - name: a named step between them
        run: python mark.py two
      - run: |
          python mark.py three
          python mark.py four
        name: a block whose name comes after it
      - run: python mark.py guard
"""

FLOW_STEP = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: before
        run: python mark.py one
      - { name: flow, run: python mark.py two }
      - name: after
        run: python mark.py three
"""

CONTINUED = """\
name: tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: before
        run: python mark.py one
      - name: continued
        run: python mark.py two
          && python mark.py three
      - name: after
        run: python mark.py four
"""


# ---------------------------------------------------------------- the checks

def test_one_list_read_at_run_time():
    """Criterion 1: exactly the `run:` steps of test.yml's `test` job, in file order, read when
    it runs, with the exits lead/checks.py had."""
    print("\n[gate] the runner runs the one list in test.yml, read when it runs")
    present = os.path.isfile(RUNNER)
    check("the runner is at %s, outside lead/" % RUNNER_REL, present,
          "not found: the deploy must not depend on the lead workflow's folder")
    if not present:
        return

    # The real list, from the runner run as a program on a copy of test.yml. None of the step
    # files is in the scratch repository, so each step fails at once and nothing of the real
    # suite runs -- this file is one of its steps.
    text = read(TEST_YML)
    expected = commands(text, "test")
    with scratch(text) as tree:
        code, out = run(tree, RUNNER_REL)
    got = printed_commands(out)
    check("on test.yml it runs the %d commands an independent reader finds in the `test` job, "
          "in file order" % len(expected),
          bool(expected) and got == expected
          and ("%d steps from job 'test'" % len(expected)) in out,
          "runner %d, reader %d, first difference %s: %s"
          % (len(got), len(expected), _first_difference(got, expected), _tail(out, 3)))
    check("  and one of them runs this file, so every deploy runs this guard too",
          THIS_STEP in got, "no `run: %s` in the `test` job" % THIS_STEP)
    # Named change (c): the runner refuses no line of the real job.
    refused = [l.strip() for l in out.splitlines() if "unrecognised" in l]
    check("  and it recognises every line of that job's steps: none is refused",
          not refused, str(refused[:3]))

    with scratch(GREEN) as tree:
        code, out = run(tree, RUNNER_REL)
        done = ran(tree)
    check("on a synthetic test.yml it runs exactly the `test` job's steps, in file order, both "
          "commands of a block included", done == ["one", "two", "three", "four"],
          "ran %s" % done)
    check("  one line per step", statuses(out) == ["ok"] * 4
          and "4 steps from job 'test'" in out, _tail(out))
    check("  exit 0 when every step passed, though the steps wrote untracked files, in a "
          "repository with no lead/ folder", code == 0 and "4 of 4 steps passed" in out,
          "exit %d: %s" % (code, _tail(out)))

    with scratch(TRACKED) as tree:
        code, out = run(tree, RUNNER_REL)
    check("  and exit 1 when a step modified a tracked file, although every step passed",
          code == 1 and "2 of 2 steps passed" in out and "tracked.txt" in out,
          "exit %d: %s" % (code, _tail(out)))

    # Named change (a).
    with scratch(COMMENTED) as tree:
        code, out = run(tree, RUNNER_REL)
        done = ran(tree)
    check("a comment at the jobs' indentation between two steps does not end the job: the "
          "steps after it and after a blank line run, the next job's do not",
          done == ["one", "two", "three"], "ran %s" % done)
    check("  and the run reports all three steps and passes",
          code == 0 and "3 steps from job 'test'" in out and "3 of 3 steps passed" in out,
          "exit %d: %s" % (code, _tail(out)))

    # Named change (c).
    with scratch(DASH_RUN) as tree:
        code, out = run(tree, RUNNER_REL)
        done = ran(tree)
    check("steps written `- run: python ...` run, in file order, a block and a last "
          "guard-like step included", done == ["one", "two", "three", "four", "guard"],
          "ran %s" % done)
    check("  and the run reports all five and passes",
          code == 0 and "5 steps from job 'test'" in out and "5 of 5 steps passed" in out,
          "exit %d: %s" % (code, _tail(out)))


def test_the_wrapper_is_the_same_tool():
    """Criterion 2: python lead/checks.py prints what the runner prints and exits as it exits."""
    print("\n[gate] lead/checks.py is the same tool as the runner")
    # Named change (d). lead/ is the lead workflow's folder, and removing it is how that
    # workflow is undone. Without it there is no wrapper to compare; that must not fail the
    # guard, or undoing the workflow would block every deploy.
    if not os.path.isdir(os.path.join(ROOT, "lead")):
        print("  ----  lead/checks.py  (not checked here: there is no lead/ folder)")
        return
    if not os.path.isfile(RUNNER):
        check("the runner is at %s" % RUNNER_REL, False, "not found")
        return
    check("lead/checks.py is still there, for lead/config.yml and the lead kit",
          os.path.isfile(WRAPPER), "not found")
    if not os.path.isfile(WRAPPER):
        return

    for label, workflow in (("a green workflow", GREEN), ("a red one", RED),
                            ("one with no `test` job", NO_JOB)):
        with scratch(workflow) as tree:
            add_wrapper(tree)
            code, out = run(tree, RUNNER_REL)
            code2, out2 = run(tree, WRAPPER_REL)
        check("on %s: the same exit status (%d) and the same output, timings aside"
              % (label, code), code2 == code and untimed(out2) == untimed(out),
              "runner %d, wrapper %d: %s" % (code, code2, _tail(out2)))

    with scratch(GREEN) as tree:
        add_wrapper(tree)
        _write(os.path.join(tree, *RUNNER_REL.split("/")), STUB)
        code, out = run(tree, WRAPPER_REL)
        check("it runs whatever is at %s, and exits with its status" % RUNNER_REL,
              code == 7 and "stub runner ran" in out, "exit %d: %s" % (code, _tail(out)))
        os.remove(os.path.join(tree, *RUNNER_REL.split("/")))
        code, out = run(tree, WRAPPER_REL)
        check("  and with no runner there it exits non-zero rather than report a pass",
              code != 0 and "steps passed" not in out, "exit %d: %s" % (code, _tail(out)))


def test_the_runner_fails_closed():
    """Criterion 3: shown on synthetic workflows; nothing here needs the real suite to pass."""
    print("\n[gate] the runner fails closed")
    if not os.path.isfile(RUNNER):
        check("the runner is at %s" % RUNNER_REL, False, "not found")
        return

    with scratch(RED) as tree:
        code, out = run(tree, RUNNER_REL)
        done = ran(tree)
    check("a failing step makes it exit non-zero", code != 0, "exit %d" % code)
    check("  and every step after it still runs", done == ["one", "two", "three", "four"],
          "ran %s" % done)
    check("  each reported on its own line", statuses(out) == ["ok", "RED", "ok", "RED"]
          and "2 of 4 steps passed" in out, _tail(out))

    for label, workflow in (("a workflow with no `test` job (a job called tests is not it)",
                             NO_JOB),
                            ("an empty workflow file", ""),
                            ("a `test` job whose steps have no `run:`", NO_STEPS)):
        with scratch(workflow) as tree:
            code, out = run(tree, RUNNER_REL)
            done = ran(tree)
        check("%s exits 2 and runs nothing" % label,
              code == 2 and done == [] and "steps passed" not in out,
              "exit %d, ran %s: %s" % (code, done, _tail(out)))

    with scratch(None) as tree:
        code, out = run(tree, RUNNER_REL)
    check("no test.yml at all exits non-zero", code != 0 and "steps passed" not in out,
          "exit %d: %s" % (code, _tail(out)))

    with scratch(UNSUPPORTED) as tree:
        code, out = run(tree, RUNNER_REL)
        done = ran(tree)
    red = [l for l in out.splitlines() if l.startswith("RED") and "unsupported" in l]
    check("a `run:` it cannot run is a red step: a shell command, and a block with no command",
          len(red) == 2 and "a shell command" in red[0] and "an empty block" in red[1],
          _tail(out))
    check("  the run exits non-zero, and the steps around them still run",
          code != 0 and done == ["one", "two"] and statuses(out) == ["ok", "RED", "RED", "ok"],
          "exit %d, ran %s" % (code, done))

    # Named change (b).
    for op, workflow in (("&&", CHAINED_AND), (";", CHAINED_SEMICOLON)):
        with scratch(workflow) as tree:
            _write(os.path.join(tree, "quiet.py"), QUIET)
            code, out = run(tree, RUNNER_REL)
            done = ran(tree)
        red = [l for l in out.splitlines() if l.startswith("RED") and "unsupported" in l]
        check("a `run:` joining two commands with %s is a red step, reported unsupported" % op,
              len(red) == 1 and "two commands joined" in red[0], _tail(out))
        check("  the run exits non-zero, and the steps around it still run",
              code != 0 and done == ["one", "four"], "exit %d, ran %s" % (code, done))

    # Named change (c).
    for label, workflow, text, around in (
            ("a flow-style step", FLOW_STEP, "- { name: flow, run: python mark.py two }",
             ["one", "three"]),
            ("a plain `run:` value continued on the next line", CONTINUED,
             "&& python mark.py three", ["one", "four"])):
        number = [l.strip() for l in workflow.splitlines()].index(text) + 1
        with scratch(workflow) as tree:
            code, out = run(tree, RUNNER_REL)
            done = ran(tree)
        named = [l for l in out.splitlines() if l.startswith("RED") and "unrecognised" in l
                 and ("line %d " % number) in l and text in l]
        check("%s is red, named by its line number (%d) and its text" % (label, number),
              len(named) == 1, _tail(out))
        check("  the run exits non-zero; that step does not run, the steps around it do",
              code != 0 and done == around, "exit %d, ran %s" % (code, done))


def test_the_deploy_is_gated():
    """Criterion 4: the deploy job runs the runner before it deploys, and a red gate stops it."""
    print("\n[gate] deploy.yml runs the offline suite before it deploys")
    text = read(DEPLOY_YML)
    all_jobs = jobs(text)
    found = [(job, i) for job, lines in sorted(all_jobs.items())
             for i, s in enumerate(steps(lines)) if DEPLOYS.search(" ".join(s["run"]))]
    check("one step deploys (pywrangler deploy)", len(found) == 1, str(found))
    if len(found) != 1:
        return
    job, i_deploy = found[0]
    job_lines = all_jobs[job]
    ss = steps(job_lines)
    deploy = ss[i_deploy]

    checkout = [i for i, s in enumerate(ss)
                if s["keys"].get("uses", "").startswith("actions/checkout@")]
    check("its job checks the repository out once", len(checkout) == 1, str(checkout))
    if checkout:
        depth = ss[checkout[0]]["with"].get("fetch-depth")
        check("  with the whole history (fetch-depth: 0), which the suite reads: at depth 1 its "
              "rounds check fails on every run", depth == "0", "fetch-depth: %s" % depth)

    gates = [i for i, s in enumerate(ss) if "offline_suite" in " ".join(s["run"])]
    check("one step of that job runs the offline suite", len(gates) == 1,
          "%d steps do" % len(gates))
    if len(gates) != 1:
        return
    i_gate = gates[0]
    gate = ss[i_gate]
    check("  it runs exactly `%s`: no argument, no `|| true`, no `set +e`, no second command"
          % GATE, gate["run"] == [GATE], str(gate["run"]))

    setup = [i for i, s in enumerate(ss)
             if s["keys"].get("uses", "").startswith("actions/setup-python@")]
    tooling = [i for i, s in enumerate(ss) if TOOLING.search(" ".join(s["run"]))]
    check("  after the checkout", bool(checkout) and i_gate > checkout[0],
          "step %d, checkout %s" % (i_gate + 1, [i + 1 for i in checkout]))
    check("  after Python is set up", bool(setup) and i_gate > setup[0],
          "step %d, setup-python %s" % (i_gate + 1, [i + 1 for i in setup]))
    check("  before uv is installed, dependencies are synced and pywrangler deploy runs",
          bool(tooling) and i_gate < min(tooling) and i_gate < i_deploy,
          "step %d; tooling at %s, deploy at %d"
          % (i_gate + 1, [i + 1 for i in tooling], i_deploy + 1))
    check("  under the deploy step's own condition, so the deploy cannot run while it is skipped",
          _cond(gate["keys"].get("if")) == _cond(deploy["keys"].get("if")),
          "gate if: %r, deploy if: %r" % (gate["keys"].get("if"), deploy["keys"].get("if")))

    check("nothing lets it fail without failing the job: no continue-on-error on the step",
          "continue-on-error" not in gate["keys"], gate["keys"].get("continue-on-error", ""))
    top = [l.strip() for l in job_lines if _indent(l) == _indent(job_lines[0])]
    soft = [l for l in top if l.startswith("continue-on-error")]
    check("  nor on its job", not soft, str(soft))
    check("  no shell of its own", "shell" not in gate["keys"], gate["keys"].get("shell", ""))
    loose = [(_label(s, i), _cond(s["keys"].get("if"))) for i, s in enumerate(ss)
             if i > i_gate and STATUS_FUNCTIONS.search(_cond(s["keys"].get("if")))]
    check("  and no later step's `if:` runs it after a failure (always(), failure(), "
          "cancelled(), success() ...)", not loose, str(loose))


def test_the_deploy_keeps_no_second_list():
    """Criterion 5: the list lives in test.yml, and only there."""
    print("\n[gate] deploy.yml keeps no list of its own")
    text = read(DEPLOY_YML)
    named = sorted(set(re.findall(r"tests/test_[A-Za-z0-9_]*\.py", text)))
    check("deploy.yml names no tests/test_*.py file", not named, str(named))
    lead = [c for lines in jobs(text).values() for s in steps(lines) for c in s["run"]
            if "lead/" in c]
    check("  and runs nothing from lead/, which is meant to be removable", not lead, str(lead))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("=" * 68)
    print("A deploy runs only after every step of the offline suite passed")
    print("=" * 68)
    test_one_list_read_at_run_time()
    test_the_wrapper_is_the_same_tool()
    test_the_runner_fails_closed()
    test_the_deploy_is_gated()
    test_the_deploy_keeps_no_second_list()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILS)))
    if _FAILS:
        print("\nFailures:")
        for label in _FAILS:
            print("  - " + label)
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
