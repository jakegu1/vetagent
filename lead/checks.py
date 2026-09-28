"""checks.py -- run every step of CI's offline `test` job, in order, and report each one.

Usage:  python lead/checks.py          (from the repository root; exit 0 only if every step passed
                                        and the run left every tracked file as it found it)

Why this exists. GitHub stops a job at its first failing step. On 2026-09-22 step 6 of 27
went red and stayed red, so for the next six days steps 7 to 27 never ran on CI and nobody
could say whether they passed. This runs every step anyway, so one known red cannot hide a
new one, and prints one line per step.

The step list is read from `.github/workflows/test.yml` every time, never typed here, so it
cannot drift from what CI runs. It refuses loudly rather than guessing:

- no `test:` job, or no steps found in it          -> exit 2 (a runner that finds nothing
                                                       would pass vacuously);
- a `run:` it cannot turn into a python command    -> that step is reported red.

It also fails if the run modified a tracked file. A check that edits the tree and puts it back
is safe only if it puts it back exactly. Until 2026-09-29 `tests/test_number_coverage.py`
restored `docs/EXPERIMENT_C.md` from a text-mode read, which turned a Windows checkout's CRLF
into LF, and this runner listed that file after every run as a known side effect to restore by
hand. A line that is always there is a line nobody reads, and it was the only line that would
show a mutated published number left behind.

The two network tests (`test_upstream_contract.py`, `test_backfill.py`) live in other jobs
and are not run here. The lead kit reads this command from `lead/config.yml`.
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "test.yml")
JOB = "test"


def steps_from_workflow(text):
    """[(name, command or None)] for every `run:` in the job, in file order."""
    lines = text.splitlines()
    try:
        start = lines.index("  %s:" % JOB) + 1
    except ValueError:
        return None
    block = []
    for line in lines[start:]:
        if re.match(r"^  \S", line):          # the next job, or a comment between jobs
            break
        block.append(line)

    steps, name, i = [], None, 0
    while i < len(block):
        line = block[i]
        m = re.match(r"^\s*- name:\s*(.+?)\s*$", line)
        if m:
            name = m.group(1)
        m = re.match(r"^(\s*)run:\s*(.*?)\s*$", line)
        if m:
            indent, value = len(m.group(1)), m.group(2)
            if value in ("|", ">", "|-", ">-"):
                cmds = []
                i += 1
                while i < len(block) and (not block[i].strip()
                                          or len(block[i]) - len(block[i].lstrip()) > indent):
                    if block[i].strip() and not block[i].strip().startswith("#"):
                        cmds.append(block[i].strip())
                    i += 1
                for cmd in cmds or [None]:
                    steps.append((name, cmd))
                continue
            steps.append((name, value or None))
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
        if not cmd or not cmd.startswith("python "):
            red.append(name)
            print("RED   unsupported step %r: %r -- teach lead/checks.py this shape" % (name, cmd))
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
