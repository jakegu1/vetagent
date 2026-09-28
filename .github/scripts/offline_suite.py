"""offline_suite.py -- run every step of CI's offline `test` job, in order, and report each one.

Usage:  python .github/scripts/offline_suite.py   (from the repository root; exit 0 only if
                                                   every step passed and the run left every
                                                   tracked file as it found it)

deploy.yml runs this before every deploy, so production ships only from a commit on which
every step of that job passed; `tests/test_deploy_gate.py` pins that seam. The lead workflow
runs it as `python lead/checks.py`, a wrapper around this file. It lived at that path until
2026-09-29 and moved here because the product's deploy must not depend on `lead/`, a folder
that is meant to be removable.

Why this exists. GitHub stops a job at its first failing step. On 2026-09-22 step 6 of 27
went red and stayed red, so for the next six days steps 7 to 27 never ran on CI and nobody
could say whether they passed. This runs every step anyway, so one known red cannot hide a
new one, and prints one line per step.

The step list is read from `.github/workflows/test.yml` every time, never typed here, so it
cannot drift from what CI runs. The `test` job is read to the next job's id; a comment or a
blank line does not end it, because YAML reads both as still inside the job. It refuses
loudly rather than guessing:

- no `test:` job, or no steps found in it          -> exit 2 (a runner that finds nothing
                                                       would pass vacuously);
- a `run:` it cannot turn into a python command    -> that step is reported red.

That includes a `run:` joining commands with a shell operator (&&, ||, ;, |, &, a backtick,
$(, >, <): GitHub's shell runs every command, while this would run the first with the rest as
its arguments and report a pass on half the step.

It also fails if the run modified a tracked file. A check that edits the tree and puts it back
is safe only if it puts it back exactly. Until 2026-09-29 `tests/test_number_coverage.py`
restored `docs/EXPERIMENT_C.md` from a text-mode read, which turned a Windows checkout's CRLF
into LF, and this runner listed that file after every run as a known side effect to restore by
hand. A line that is always there is a line nobody reads, and it was the only line that would
show a mutated published number left behind.

The two network tests (`test_upstream_contract.py`, `test_backfill.py`) live in other jobs
and are not run here: a third party's outage must not block a deploy.
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "test.yml")
JOB = "test"

# A shell operator joins, pipes or redirects commands. The shell runs them all; a command
# split on spaces, as below, would run the first with the rest as its arguments. On
# 2026-09-29 `python a.py && python b.py` passed here with b.py never run.
SHELL_OPERATOR = re.compile(r"[&;|`<>]|\$\(")


def steps_from_workflow(text):
    """[(name, command or None)] for every `run:` in the job, in file order."""
    lines = text.splitlines()
    try:
        start = lines.index("  %s:" % JOB) + 1
    except ValueError:
        return None
    block = []
    for line in lines[start:]:
        # The job ends at the next job's id: exactly two spaces, a name, a colon. Never at a
        # comment or a blank line, which YAML reads as still inside the job. Ending at any
        # two-space line, one comment between two steps made this read 6 of 28 steps
        # (measured 2026-09-29), and the gate would have passed on those 6.
        if re.match(r"^  [A-Za-z0-9_-]+:(\s|$)", line):
            break
        block.append(line)

    steps, name, i = [], None, 0
    while i < len(block):
        line = block[i]
        if re.match(r"^\s*- ", line):
            name = None                   # a new step: the name of the one before is not its own
        m = re.match(r"^\s*- name:\s*(.+?)\s*$", line)
        if m:
            name = m.group(1)
        # `run` can be a step's first key (`- run: ...`); the key then sits two columns right of
        # the dash, and a block under it is indented past that. Such a step used to be skipped:
        # with the guard's own step written so, the gate passed 27 of 27 without running it
        # (measured 2026-09-29). A step with no name is called what GitHub calls it.
        m = re.match(r"^(\s*)(- )?run:\s*(.*?)\s*$", line)
        if m:
            indent, value = len(m.group(1)) + len(m.group(2) or ""), m.group(3)
            if value in ("|", ">", "|-", ">-"):
                cmds = []
                i += 1
                while i < len(block) and (not block[i].strip()
                                          or len(block[i]) - len(block[i].lstrip()) > indent):
                    if block[i].strip() and not block[i].strip().startswith("#"):
                        cmds.append(block[i].strip())
                    i += 1
                for cmd in cmds or [None]:
                    steps.append((name or "Run %s" % (cmds[0] if cmds else ""), cmd))
                continue
            steps.append((name or "Run %s" % value, value or None))
        i += 1
    return steps


def tracked_changes():
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                         capture_output=True, encoding="utf-8", errors="replace")
    return set(out.stdout.splitlines()) if out.returncode == 0 else set()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with open(WORKFLOW, encoding="utf-8") as f:
        steps = steps_from_workflow(f.read())
    if not steps:
        print("no steps found in job '%s' of %s -- refusing to report a pass" % (JOB, WORKFLOW))
        return 2
    print("%d steps from job '%s' in .github/workflows/test.yml" % (len(steps), JOB))

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    before = tracked_changes()
    red, t_all = [], time.time()
    for name, cmd in steps:
        if not cmd or not cmd.startswith("python ") or SHELL_OPERATOR.search(cmd):
            red.append(name)
            print("RED   unsupported step %r: %r -- teach .github/scripts/offline_suite.py "
                  "this shape" % (name, cmd))
            continue
        args = [sys.executable] + cmd.split()[1:]
        t0 = time.time()
        p = subprocess.run(args, cwd=ROOT, capture_output=True, encoding="utf-8",
                           errors="replace", env=env)
        out = (p.stdout or "") + (p.stderr or "")
        tally = [l.strip() for l in out.splitlines()
                 if re.search(r"\d+ passed, \d+ failed", l)]
        print("%-5s %5.1fs  %s%s" % ("ok" if p.returncode == 0 else "RED", time.time() - t0,
                                    cmd, ("  | " + tally[-1]) if tally else ""))
        if p.returncode != 0:
            red.append(name)
            for l in [l for l in out.splitlines() if l.strip()][-12:]:
                print("        " + l)

    moved = sorted(tracked_changes() - before)
    if moved:
        print("\nRED   tracked files this run modified (a check must leave the tree as it "
              "found it):")
        for l in moved:
            print("  " + l)
    print("\n%d of %d steps passed in %.1fs" % (len(steps) - len(red), len(steps),
                                               time.time() - t_all))
    for name in red:
        print("  RED  %s" % name)
    if moved:
        print("  RED  the run modified %d tracked file(s)" % len(moved))
    return 1 if red or moved else 0


if __name__ == "__main__":
    sys.exit(main())
