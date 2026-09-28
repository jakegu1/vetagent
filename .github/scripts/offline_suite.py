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
- a `run:` it cannot turn into a python command    -> that step is reported red;
- a line after `steps:` that it does not recognise -> that line is reported red, and the
                                                       step it is in does not run.

A `run:` joining commands with a shell operator (&&, ||, ;, |, &, a backtick, $(, >, <) is one
it cannot turn into a python command: GitHub's shell runs every command, while this would run
the first with the rest as its arguments and report a pass on half the step.

The lines it recognises after `steps:` are blank lines and comments, a step's first line (`- `
and a step key), a step key at the step's indentation, a `key: value` under `with:` or `env:`,
and the lines of a `run: |` block. Read line by line, other shapes YAML allows -- a flow-style
step, a `run:` value continued on the next line, a folded `run: >` that YAML makes one command
of -- come out as fewer or other commands than GitHub runs, so the class is refused rather
than taught one shape at a time. A value that opens a quote, `[` or `{` must close it on the
same line. `env:`, `working-directory:` and `shell:` on a step are refused too: this does not
apply them. So is a `uses:` other than actions/checkout and actions/setup-python, the two it
stands in for.

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

# What may follow `steps:` in the job: GitHub's keys for a step, a `key: value` under `with:`
# or `env:`, and a block scalar's indicator (`|` or `>`, with chomping or indentation).
STEP_KEY = re.compile(r"^(name|id|if|uses|with|env|run|shell|working-directory|"
                      r"continue-on-error|timeout-minutes):(?:\s+(.*?))?\s*$")
ENTRY = re.compile(r"^[A-Za-z0-9_.-]+:(\s|$)")
BLOCK = re.compile(r"^[|>][0-9+-]*$")

# The two actions this stands in for, by running in a checked-out repository, on Python. Any
# other action runs code this never runs.
ALLOWED_USES = re.compile(r"^actions/(checkout|setup-python)@[^\s#]+(\s+#.*)?$")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _closed(value):
    """False when a value opens a quote, `[` or `{` and does not close it on its own line.

    Such a value goes on over the next lines, and one of them at the jobs' indentation ends the
    job for this reader: a quoted step name continued so made the real test.yml read as 6 of 28
    steps, with nothing refused (measured 2026-09-29). So the line that opens it is refused.
    """
    v = value.strip()
    if v[:1] not in ("'", '"', "[", "{"):
        return True
    depth, quote, i = 0, None, 0
    while i < len(v):
        c = v[i]
        if quote == '"':
            if c == "\\":
                i += 1                             # an escaped character
            elif c == '"':
                quote = None
        elif quote == "'":
            if c == "'" and v[i + 1:i + 2] == "'":
                i += 1                             # '' is a quote inside the string
            elif c == "'":
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
        if quote is None and depth <= 0:
            return True
    return False


def steps_from_workflow(text):
    """([(name, command or None)], [(line number, line)]) for the job, or None without one.

    The first list has every command of every step, in file order; None is a `run:` with
    nothing to run. The second has every line after `steps:` that is not a blank line, a
    comment, a step's first line (`- ` and a step key), a step key at the step's indentation,
    a `key: value` under `with:` or `env:`, or a line of a `run: |` block, and every line with
    a key this does not apply (`env`, `working-directory`, `shell`) or an action other than
    the two it stands in for. A step holding such a line gives no command: this cannot say
    what GitHub would run for it.
    """
    lines = text.splitlines()
    try:
        start = lines.index("  %s:" % JOB) + 1
    except ValueError:
        return None
    # The job ends at the next job's id: exactly two spaces, a name, a colon. Never at a
    # comment or a blank line, which YAML reads as still inside the job. Ending at any
    # two-space line, one comment between two steps made this read 6 of 28 steps
    # (measured 2026-09-29), and the gate would have passed on those 6.
    end = start
    while end < len(lines) and not re.match(r"^  [A-Za-z0-9_-]+:(\s|$)", lines[end]):
        end += 1
    body = [i for i in range(start, end)
            if lines[i].strip() and not lines[i].lstrip().startswith("#")]
    at = [i for i in body if _indent(lines[i]) == _indent(lines[body[0]])
          and re.match(r"^\s*steps:\s*$", lines[i])] if body else []
    if not at:
        return [], []

    # Every line after `steps:` belongs to the step whose dash, in the steps' column, came
    # last before it, or is refused.
    items, unknown, dash = [], [], None
    for i in range(at[0] + 1, end):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            if items:
                items[-1].append(i)
            continue
        ind, starts = _indent(line), re.match(r"^\s*-(\s|$)", line) is not None
        if starts and dash is None and ind >= _indent(lines[at[0]]):
            dash = ind
        if starts and ind == dash:
            items.append([i])
        elif items and ind > dash:
            items[-1].append(i)
        else:
            unknown.append(i)

    steps = []
    for item in items:
        name, commands, refused = _step(lines, item, dash)
        unknown += refused
        if commands and not refused:
            label = name if name is not None else "Run %s" % (commands[0] or "")
            steps += [(label, cmd) for cmd in commands]
    return steps, [(i + 1, lines[i]) for i in sorted(unknown)]


def _step(lines, item, dash):
    """(name, [commands], [line indexes it refuses]) for the lines of one step."""
    at = dash + 2                          # the column of a step's keys
    name, runs, refused = None, [], []
    block = nested = None                  # the column of an open `run: |`, `with:` or `env:`
    for k, i in enumerate(item):
        if k == 0:
            # The first key follows the dash and can be any step key: `- run: ...` is a step
            # like the others. Skipped until 2026-09-29, it let the gate pass 27 of 27 with the
            # guard's own step written so, and never run it.
            text, ind = lines[i][dash + 1:].strip(), at
        else:
            text, ind = lines[i].strip(), _indent(lines[i])
            if not text:
                continue
            if block is not None and ind > block:          # a line of a `run: |` block
                if not text.startswith("#"):
                    runs[-1].append(text)
                continue
            block = None
            if text.startswith("#"):
                continue
            if nested is not None and ind > nested:        # under `with:` or `env:`
                entry = ENTRY.match(text)
                if not entry or not _closed(text[entry.end():]):
                    refused.append(i)
                continue
            nested = None
        m = STEP_KEY.match(text) if ind == at else None
        if m is None:
            refused.append(i)
            continue
        key, value = m.group(1), m.group(2) or ""
        if not _closed(value):
            refused.append(i)
            continue
        if key == "name":
            name = value
        elif key == "run" and BLOCK.match(value):
            block = at
            runs.append([])
            if value.startswith(">"):
                # Folded: YAML joins its lines into one command, which this would run as
                # several, and pass where the one command GitHub runs fails.
                refused.append(i)
        elif key == "run":
            runs.append([value or None])
        elif key in ("env", "working-directory", "shell"):
            # Keys this does not apply: it runs every command from the repository's root, in
            # its own environment and without a shell, so such a step could run differently
            # here than on GitHub.
            refused.append(i)
            nested = at if key == "env" and not value else None
        elif key == "with" and not value:
            nested = at
        elif key == "uses" and not ALLOWED_USES.match(value):
            refused.append(i)
    return name, [cmd for run in runs for cmd in (run or [None])], refused


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
        steps, unknown = steps_from_workflow(f.read()) or ([], [])
    if steps:
        print("%d steps from job '%s' in .github/workflows/test.yml" % (len(steps), JOB))
    else:
        print("no steps found in job '%s' of %s -- refusing to report a pass" % (JOB, WORKFLOW))
    for n, line in unknown:
        print("RED   unrecognised line %d of .github/workflows/test.yml: %r -- teach "
              ".github/scripts/offline_suite.py this shape; its step does not run"
              % (n, line.strip()))
    if not steps:
        return 2

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
    for n, _ in unknown:
        print("  RED  unrecognised line %d of .github/workflows/test.yml" % n)
    if moved:
        print("  RED  the run modified %d tracked file(s)" % len(moved))
    return 1 if red or moved or unknown else 0


if __name__ == "__main__":
    sys.exit(main())
