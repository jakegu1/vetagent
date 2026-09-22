"""A bot that commits to master regenerates what its data moves, and its commit is tested.

Two bots commit here on a schedule, and on 2026-09-21 each one left master red in a
different way, neither of which any run noticed:

  503b7a6  snapshot   The first pass after midnight UTC moved `bench/scorecard.py`'s
                      "days of snapshots" item, and snapshot.yml regenerates nothing, so
                      docs/SCORECARD.md no longer matched its generator. Red for the four
                      hours until production.yml happened to regenerate it.
  c66c6be  production The probe moved the live unknown rate, and production.yml ran
                      scorecard, owner and rounds but not publish_numbers -- a hand-typed
                      list one generator short -- so docs/EXPERIMENT_C.md went stale. It was
                      the third time: f399498 had patched the same symptom the day before.

Both stayed silent for the same reason: a push made with GITHUB_TOKEN starts no workflow,
so test.yml never ran on a bot's commit. The weekly schedule caught the first one; the
second was found by a human review. production.yml's own comment said "or test.yml goes
red on this bot's push" -- test.yml could not go red on that push, because it never ran.

So this pins the whole seam, derived from the files rather than typed:

  * every workflow that pushes to master is one test.yml runs after (`workflow_run`), and
    on that trigger only the offline job runs -- no upstream budget spent five times a day;
  * every such workflow calls the one shared regeneration script, AFTER its data commit
    (the data is irreplaceable and must never share a commit that can conflict), with the
    full history that tools/owner.py and tools/rounds.py read;
  * that script runs every generator a test names as its remedy whose inputs a bot can
    move -- read from each generator's own source, so a new generator that reads the
    archive, or the production artifacts, or git history, is required automatically;
  * and it refuses to commit anything under src/, because a bot push there would deploy.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows")
SCRIPTS = os.path.join(ROOT, ".github", "scripts")
REGEN = ".github/scripts/regenerate-derived.sh"

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


def workflows():
    out = {}
    for name in sorted(os.listdir(WF)):
        if name.endswith((".yml", ".yaml")):
            out[name] = read(os.path.join(WF, name))
    return out


def _scripts_called(text):
    return re.findall(r"\.github/scripts/([A-Za-z0-9_.-]+\.sh)", text)


def _pushes(text):
    """True when this workflow, or a script it calls, pushes to the repository."""
    if re.search(r"\bgit push\b", text):
        return True
    for s in _scripts_called(text):
        path = os.path.join(SCRIPTS, s)
        if os.path.exists(path) and re.search(r"\bgit push\b", read(path)):
            return True
    return False


def _name(text):
    m = re.search(r"^name:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", text, re.M)
    return m.group(1).strip() if m else None


def _jobs(text):
    """{job id: its block of text}, from the top-level `jobs:` mapping."""
    m = re.search(r"^jobs:\s*$", text, re.M)
    if not m:
        return {}
    body = text[m.end():]
    heads = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$", body, re.M))
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out[h.group(1)] = body[h.start():end]
    return out


def test_every_pushing_workflow_is_tested_after():
    print("\n[bots] test.yml runs after every workflow that commits to master")
    wfs = workflows()
    pushers = {f: _name(t) for f, t in wfs.items() if _pushes(t) and f != "test.yml"}
    # The discovery has to see the two bots this file was written about, or it is blind.
    check("the push detector finds both scheduled bots",
          {"snapshot", "production"} <= set(pushers.values()), str(pushers))
    test_yml = wfs.get("test.yml", "")
    m = re.search(r"workflow_run:\s*\n\s*workflows:\s*\[([^\]]*)\]", test_yml)
    listed = {w.strip().strip("\"'") for w in m.group(1).split(",")} if m else set()
    check("test.yml has a workflow_run trigger", bool(m),
          "a GITHUB_TOKEN push starts no workflow, so nothing else would test a bot's commit")
    for f, name in sorted(pushers.items()):
        check("  and it names %s (%s)" % (name, f), name in listed,
              "listed: %s" % sorted(listed))
    if m:
        check("  and fires on completion", re.search(
            r"workflow_run:\s*\n\s*workflows:\s*\[[^\]]*\]\s*\n\s*types:\s*\[\s*completed\s*\]",
            test_yml) is not None)

    # On that trigger only the offline job runs. The other jobs spend real upstream
    # requests, and the bots run five times a day.
    for job, block in _jobs(test_yml).items():
        if job == "test":
            continue
        cond = re.search(r"^    if:\s*(.+)$", block, re.M)
        cond = cond.group(1) if cond else ""
        skips = ("workflow_run" in cond and "!=" in cond) or (
            "workflow_run" not in cond and "==" in cond and "event_name" in cond)
        check("  job %s does not run on a bot's workflow_run" % job, skips,
              "if: %r" % cond)


def test_every_pushing_workflow_regenerates_after_its_data():
    print("\n[bots] every bot regenerates the derived pages, after its data is pushed")
    for f, text in sorted(workflows().items()):
        if f == "test.yml" or not _pushes(text):
            continue
        if f == "deploy.yml":
            continue
        lines = text.splitlines()
        regen = [i for i, l in enumerate(lines) if REGEN in l]
        check("%s calls %s" % (f, REGEN), bool(regen))
        if not regen:
            continue
        # Every step that commits data must come before the regeneration step: the data
        # is pushed on its own first, so nothing the regeneration does can cost a pass.
        data = [i for i, l in enumerate(lines)
                if ("snapshot-commit.sh" in l or re.search(r"\bgit commit\b", l))]
        check("  and only after every data commit (lines %s < %s)"
              % ([i + 1 for i in data], regen[0] + 1),
              all(i < regen[0] for i in data))
        check("  and with the full history owner.py and rounds.py read",
              re.search(r"fetch-depth:\s*0\b", text) is not None,
              "a depth-1 checkout makes tools/rounds.py write a log of one commit")
        # The data commit itself must not carry the derived pages, or a conflict on a page
        # a human also regenerates would take the irreplaceable rows down with it.
        for i in data:
            window = "\n".join(lines[max(0, i - 8):i + 1])
            adds = re.findall(r"git add ([^\n]+)", window)
            leaked = [a for a in adds if re.search(r"docs/|README", a)]
            check("  and its data commit at line %d stages no derived page" % (i + 1),
                  not leaked, str(leaked))


def _required_generators():
    """Every generator a test names as its remedy whose inputs a bot can move."""
    named = set()
    for name in sorted(os.listdir(HERE)):
        if name.startswith("test_") and name.endswith(".py"):
            named |= set(re.findall(r"python ((?:bench|tools)/[a-z_]+\.py) --write",
                                    read(os.path.join(HERE, name))))
    required, excluded = set(), {}
    for gen in sorted(named):
        path = os.path.join(ROOT, gen)
        if not os.path.exists(path):
            continue
        src = read(path)
        # What a bot writes: the snapshot archive, the production artifacts, and commits.
        moved_by_bot = (re.search(r"[\"'/]snapshots[\"'/]", src)
                        or re.search(r"[\"'/]production[\"'/]", src)
                        or re.search(r"[\"']git[\"']\s*,\s*[\"'](log|rev-list)[\"']", src)
                        or re.search(r"import rounds|from rounds|tools\.rounds|rounds\.", src)
                        or re.search(r"SCORECARD\.md", src))
        if moved_by_bot:
            required.add(gen)
        else:
            excluded[gen] = "reads nothing a bot writes"
    return named, required, excluded


def test_the_shared_script_runs_every_generator_a_bot_can_stale():
    print("\n[bots] the regeneration script runs every generator whose inputs a bot moves")
    path = os.path.join(ROOT, REGEN)
    check("%s exists" % REGEN, os.path.exists(path))
    if not os.path.exists(path):
        return
    script = read(path)
    runs = set(re.findall(r"python ((?:bench|tools)/[a-z_]+\.py) --write", script))
    named, required, excluded = _required_generators()
    check("the tests name at least the four page generators as remedies",
          {"bench/publish_numbers.py", "bench/scorecard.py", "tools/owner.py",
           "tools/rounds.py"} <= named, str(sorted(named)))
    for gen in sorted(required):
        check("  it runs %s" % gen, gen in runs, "runs: %s" % sorted(runs))
    for gen, why in sorted(excluded.items()):
        print("  note: %s is a remedy but not a bot's: %s" % (gen, why))
    check("  and nothing it runs is missing from the repository",
          all(os.path.exists(os.path.join(ROOT, g)) for g in runs), str(sorted(runs)))
    check("it refuses to commit anything under src/ (a bot push there deploys)",
          re.search(r"git diff --name-only -- src/", script) is not None
          and re.search(r"':!src'|\":!src\"", script) is not None)
    code = "\n".join(l for l in script.splitlines() if not l.lstrip().startswith("#"))
    check("it regenerates on the new base rather than rebasing its commit",
          re.search(r"\bgit reset\b[^\n]*--hard", code) is not None
          and re.search(r"\bpull\b[^\n]*--rebase|\brebase\b", code) is None)
    check("it will not reset past a commit that never reached origin",
          re.search(r"rev-list --count", script) is not None)


def main():
    print("=" * 68)
    print("A bot's commit regenerates what it moves, and is tested")
    print("=" * 68)
    test_every_pushing_workflow_is_tested_after()
    test_every_pushing_workflow_regenerates_after_its_data()
    test_the_shared_script_runs_every_generator_a_bot_can_stale()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILS)))
    if _FAILS:
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
