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

The script is also run for real (T-006). Any argument but `regenerate` is the bots' mode: it
writes the bot's identity into the clone's git config, which every worktree of the clone
shares, resets the checkout to origin, commits and pushes. On a laptop that is always an
accident -- a typo, a case change, the CI line pasted from the script's header -- so off GitHub
Actions it must be refused before a single git command, while the bots, `regenerate` and the
usage stay as they were. Every call runs in a scratch repository that cannot reach this one
(`_Scratch` says how), and where no usable bash exists those checks say they were not run.
"""
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows")
SCRIPTS = os.path.join(ROOT, ".github", "scripts")
REGEN = ".github/scripts/regenerate-derived.sh"

_FAILS = []
_PASSED = 0
_NOT_RUN = []


def check(label, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  " + label)
    else:
        _FAILS.append(label)
        print("  FAIL  " + label + ("  " + detail if detail else ""))


def not_run(label, why):
    """A check this machine cannot run. It is said, and it never counts as passed; on GitHub
    Actions it fails the file (see main)."""
    _NOT_RUN.append((label, why))
    print("  NOT RUN HERE  %s  (%s)" % (label, why))


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


# ---------------------------------------------------------------------------------------------
# T-006. The script, run for real. Any argument but `regenerate` is the bots' mode: it writes the
# bot's identity into the clone's git config (every worktree of the clone shares it), resets the
# checkout to origin, commits and pushes. Off GitHub Actions that is always an accident, so it
# must be refused there before a single git command, and nothing else may change.
# ---------------------------------------------------------------------------------------------

# Off GitHub Actions: GITHUB_ACTIONS as a laptop has it (unset), and values that are not exactly
# `true`, near misses included (named change (b)): a space before or after it and all capitals,
# so a comparison on a prefix, a suffix or without case fails here. And what a person types by
# accident: a typo, a case change, and the CI usage line pasted from the script's own header.
OFF_ACTIONS = ((None, "GITHUB_ACTIONS unset"), ("1", "GITHUB_ACTIONS=1"),
               ("false", "GITHUB_ACTIONS=false"), ("", "GITHUB_ACTIONS empty"),
               ("True", "GITHUB_ACTIONS=True"), (" true", "GITHUB_ACTIONS=' true'"),
               ("true ", "GITHUB_ACTIONS='true '"), ("TRUE", "GITHUB_ACTIONS=TRUE"))
MISTAKES = ("regenrate", "Regenerate", "Snapshot 2026-09-22")
# Variables close to GITHUB_ACTIONS in meaning or in name; GitHub sets both. Every refused call
# sets them to the value that would open a check reading them instead, and the call on Actions
# sets neither, so a check on the wrong variable fails both ways.
DECOYS = {"CI": "true", "GITHUB_ACTION": "true"}

SCRATCH_IDENTITY = {"user.name": "Scratch Repository", "user.email": "scratch@example.invalid"}
TRACKED, COMMITTED, UNCOMMITTED = "notes.txt", "committed\n", "an uncommitted change\n"
GENERATOR_LOG_VAR = "REGEN_TEST_GENERATOR_LOG"
GENERATOR_STUB = '''"""A generator's stub in a scratch repository: it changes nothing, and says it ran."""
import os
import sys

log = os.environ.get("%s")
if log:
    with open(log, "a") as f:
        f.write(" ".join(sys.argv).replace(os.sep, "/") + chr(10))
''' % GENERATOR_LOG_VAR

# `regenerate` on its own, not as part of the script's name or of a path.
REGENERATE_WORD = re.compile(r"(?<![\w./-])regenerate(?![\w./-])")
# What `regenerate` must never run: the identity, fetch, reset, commit, push and their kin.
WRITES = {"config", "fetch", "pull", "reset", "checkout", "switch", "restore", "clean", "stash",
          "add", "commit", "push", "merge", "rebase", "update-ref"}
CALL_TIMEOUT = 120


def _no_git_vars():
    """This process's environment without any GIT_* variable, so nothing inherited can point
    git at another repository, work tree, index or config."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}


def _write(path, text):
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _read_text(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _remove(tree):
    # git writes its objects read-only, and on Windows rmtree cannot delete those.
    for folder, dirs, files in os.walk(tree):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(folder, name), stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
            except OSError:
                pass
    shutil.rmtree(tree, ignore_errors=True)


def _same(path, other):
    try:
        return bool(path) and os.path.samefile(path, other)
    except OSError:
        return False


def _inside(child, parent):
    child, parent = [os.path.normcase(os.path.realpath(p)) for p in (child, parent)]
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def _short(text):
    return " | ".join(l.strip() for l in text.strip().splitlines())[:400]


def _git_commands(trace):
    """The git commands a GIT_TRACE log shows, in order: "config", "fetch", ..."""
    return re.findall(r"trace: built-in: git '?([a-z][a-z-]*)", trace)


def _find_bash():
    """(bash, folders to put first on PATH, None), or (None, [], why no bash is usable here).

    On Windows the bash.exe that PATH finds is usually the one in the system directory, which
    starts WSL: another machine, with its own git, Python and files. Git for Windows ships its
    own bash, found here from git's own install (`git --exec-path`, up to three folders up),
    never from PATH.
    """
    if os.name != "nt":
        bash = shutil.which("bash")
        return (bash, [], None) if bash else (None, [], "no bash on PATH")
    try:
        p = subprocess.run(["git", "--exec-path"], capture_output=True, encoding="utf-8",
                           errors="replace", env=_no_git_vars(), timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return None, [], "git could not be run to find its install (%s)" % e.__class__.__name__
    folder = os.path.normpath(p.stdout.strip()) if p.returncode == 0 else ""
    if not folder or folder == ".":
        return None, [], "`git --exec-path` named no folder"
    windows = os.path.normcase(os.environ.get("SystemRoot") or os.environ.get("WINDIR")
                               or "C:/Windows")
    for _ in range(3):
        folder = os.path.dirname(folder)
        for rel in (("bin", "bash.exe"), ("usr", "bin", "bash.exe")):
            bash = os.path.join(folder, *rel)
            low = os.path.normcase(bash)
            if (os.path.isfile(bash) and not _inside(low, windows)
                    and "windowsapps" not in low):
                return bash, [os.path.dirname(bash)], None
    return None, [], ("git's install has no bash.exe, and the one on PATH starts WSL, "
                      "another machine")


def _this_repository():
    """This repository's git identity as git resolves it here, and its HEAD: the first things
    the bots' mode would change if a call ever reached it."""
    out = []
    for args in (["config", "--get-regexp", "^user[.]"], ["rev-parse", "-q", "--verify", "HEAD"]):
        try:
            p = subprocess.run(["git"] + args, cwd=ROOT, env=_no_git_vars(), capture_output=True,
                               encoding="utf-8", errors="replace", timeout=60)
            out.append((p.returncode, p.stdout.strip()))
        except (OSError, subprocess.SubprocessError) as e:
            out.append((None, e.__class__.__name__))
    return out


class _Call(object):
    """One run of the script: its exit status and output, the git commands it ran (GIT_TRACE),
    the generators it ran, the scratch repository afterwards, and what changed there in words
    ("" when nothing did)."""

    def __init__(self, code, out, err, trace, generators, after, changed):
        self.code, self.out, self.err = code, out, err
        self.trace, self.git = trace, _git_commands(trace)
        self.generators = generators
        self.after, self.changed = after, changed


class _Scratch(object):
    """A scratch repository that cannot reach this one.

    It is created under the system temporary directory, outside this repository, with a local
    bare repository beside it as its origin. Every git command, the script's and this test's,
    runs with the scratch directory as its working directory AND with GIT_DIR and GIT_WORK_TREE
    naming it, so even a wrong working directory reaches no other repository (git itself unsets
    both for the local transport to origin), after every GIT_* variable this process inherited
    is dropped. It has its own identity, no commit signing and an empty hooks folder, and the
    machine's global and system git config are not read (GIT_CONFIG_GLOBAL names an empty file,
    GIT_CONFIG_NOSYSTEM=1).

    It holds the real script, copied byte for byte to the same path; a stub for every generator
    the script names, which changes nothing and records that it ran; and one tracked file with
    an uncommitted change. Its one commit is on origin too. `base` is that state.
    """

    def __init__(self, script, generators):
        self.root = tempfile.mkdtemp(prefix="regenerate-derived-")
        try:
            self._build(script, generators)
        except BaseException:
            self.remove()
            raise

    def _build(self, script, generators):
        self.work = os.path.join(self.root, "work")
        self.origin = os.path.join(self.root, "origin.git")
        self.empty_config = os.path.join(self.root, "empty.gitconfig")
        self.trace = os.path.join(self.root, "git-trace.log")
        self.generator_log = os.path.join(self.root, "generators.log")
        hooks = os.path.join(self.root, "no-hooks")
        os.makedirs(hooks)
        _write(self.empty_config, "")
        self.must(["init", "-q", "--bare", self.origin], pinned=False)
        self.must(["--git-dir=" + self.origin, "symbolic-ref", "HEAD", "refs/heads/master"],
                  pinned=False)
        self.must(["init", "-q", self.work], pinned=False)
        self.must(["symbolic-ref", "HEAD", "refs/heads/master"])
        for key, value in (("user.name", SCRATCH_IDENTITY["user.name"]),
                           ("user.email", SCRATCH_IDENTITY["user.email"]),
                           ("commit.gpgsign", "false"), ("core.hooksPath", hooks),
                           ("maintenance.auto", "false")):
            self.must(["config", key, value])
        path = os.path.join(self.work, *REGEN.split("/"))
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(script)
        for gen in generators:
            _write(os.path.join(self.work, *gen.split("/")), GENERATOR_STUB)
        _write(os.path.join(self.work, TRACKED), COMMITTED)
        self.must(["add", "-A"])
        self.must(["commit", "-q", "-m", "scratch base"])
        self.must(["remote", "add", "origin", self.origin])
        self.must(["push", "-q", "origin", "master:master"])
        _write(os.path.join(self.work, TRACKED), UNCOMMITTED)
        self.base = self.state()

    def env(self, pinned=True):
        env = _no_git_vars()
        env["GIT_CONFIG_GLOBAL"] = self.empty_config
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        if pinned:
            env["GIT_DIR"] = os.path.join(self.work, ".git")
            env["GIT_WORK_TREE"] = self.work
        return env

    def git(self, args, pinned=True, cwd=None):
        """(exit status, stdout, stderr) of git; pinned to the scratch repository unless told."""
        p = subprocess.run(["git"] + args, cwd=cwd or (self.work if pinned else self.root),
                           env=self.env(pinned), capture_output=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return p.returncode, p.stdout, p.stderr

    def must(self, args, pinned=True):
        code, out, err = self.git(args, pinned)
        if code:
            raise RuntimeError("git %s failed: %s" % (
                next(a for a in args if not a.startswith("-")), _short(err)))
        return out

    def isolated(self):
        """"" when this is its own repository, outside this one; otherwise what is wrong."""
        wrong = []
        if not _inside(self.root, tempfile.gettempdir()):
            wrong.append("it is not under the system temporary directory")
        if _inside(self.root, ROOT) or _inside(ROOT, self.root):
            wrong.append("it overlaps this repository")
        # Found from the working directory alone, as git would find it without GIT_DIR ...
        code, out, _ = self.git(["rev-parse", "--show-toplevel"], pinned=False, cwd=self.work)
        if code or not _same(out.strip(), self.work):
            wrong.append("found from its directory, `git rev-parse --show-toplevel` is not it")
        # ... and as every call pins it.
        code, out, _ = self.git(["rev-parse", "--show-toplevel", "--absolute-git-dir"])
        lines = out.splitlines()
        if (code or len(lines) != 2 or not _same(lines[0], self.work)
                or not _same(lines[1], os.path.join(self.work, ".git"))):
            wrong.append("pinned by GIT_DIR and GIT_WORK_TREE, git names another repository")
        code, out, _ = self.git(["config", "--get", "remote.origin.url"])
        if code or not _same(out.strip(), self.origin):
            wrong.append("its origin is not the bare repository beside it")
        return "; ".join(wrong)

    def state(self):
        """What a refused call must leave as it was."""
        _, ident, _ = self.git(["config", "--get-regexp", "^user[.]"])
        pairs = dict(l.split(" ", 1) for l in ident.splitlines() if " " in l)
        _, head, _ = self.git(["rev-parse", "-q", "--verify", "HEAD"])
        _, commits, _ = self.git(["--git-dir=" + self.origin, "rev-list", "--all"], pinned=False)
        try:
            with io.open(os.path.join(self.work, TRACKED), encoding="utf-8", newline="") as f:
                text = f.read()
        except (IOError, OSError):
            text = None
        return {"user.name": pairs.get("user.name"), "user.email": pairs.get("user.email"),
                TRACKED: text, "HEAD": head.strip(), "origin": sorted(commits.split())}

    def changes(self, after):
        """What differs from `base`, in words; "" when nothing does."""
        base, out = self.base, []
        for key in ("user.name", "user.email"):
            if after[key] != base[key]:
                out.append("%s is %r, was %r" % (key, after[key], base[key]))
        if after[TRACKED] == COMMITTED:
            out.append("the uncommitted change is gone (%s is back to its committed text)"
                       % TRACKED)
        elif after[TRACKED] != base[TRACKED]:
            out.append("%s reads %r, not the uncommitted change" % (TRACKED, after[TRACKED]))
        if after["HEAD"] != base["HEAD"]:
            out.append("HEAD moved from %s to %s" % (base["HEAD"][:7], after["HEAD"][:7] or "?"))
        new = sorted(set(after["origin"]) - set(base["origin"]))
        if new or set(base["origin"]) - set(after["origin"]):
            out.append("origin's commits changed (%d new)" % len(new))
        return "; ".join(out)

    def script_env(self, github_actions, decoys, path_first):
        """The environment of one call: pinned git, GITHUB_REF_NAME=master, GITHUB_ACTIONS as
        given (None: unset), the decoys if asked, and nothing else from GitHub."""
        env = self.env(pinned=True)
        for name in list(env):
            if name.upper().startswith("GITHUB_") or name.upper() == "CI":
                del env[name]
        env["GITHUB_REF_NAME"] = "master"
        if github_actions is not None:
            env["GITHUB_ACTIONS"] = github_actions
        if decoys:
            env.update(DECOYS)
        env["GIT_TRACE"] = self.trace
        env[GENERATOR_LOG_VAR] = self.generator_log
        env["PATH"] = os.pathsep.join(path_first + [env.get("PATH", "")])
        return env

    def run(self, bash, args, env):
        for path in (self.trace, self.generator_log):
            if os.path.exists(path):
                os.remove(path)
        try:
            p = subprocess.run([bash, REGEN] + list(args), cwd=self.work, env=env,
                               capture_output=True, encoding="utf-8", errors="replace",
                               timeout=CALL_TIMEOUT)
            code, out, err = p.returncode, p.stdout or "", p.stderr or ""
        except subprocess.TimeoutExpired:
            code, out, err = None, "", "no exit: timed out after %ds" % CALL_TIMEOUT
        trace = _read_text(self.trace) if os.path.exists(self.trace) else ""
        ran = (_read_text(self.generator_log).splitlines()
               if os.path.exists(self.generator_log) else [])
        after = self.state()
        return _Call(code, out, err, trace, ran, after, self.changes(after))

    def remove(self):
        _remove(self.root)


class _Harness(object):
    """Finds a usable bash and runs the script in scratch repositories: a fresh one before the
    first call and after any call that changed the last. When nothing can be run here, `bash`
    is None and `why` says why."""

    def __init__(self):
        with open(os.path.join(ROOT, *REGEN.split("/")), "rb") as f:
            self.script = f.read()
        text = self.script.decode("utf-8", "replace")
        self.generators = sorted(set(re.findall(
            r"python ((?:bench|tools)/[a-z_]+\.py) --write", text)))
        self.bot = {}
        for key in ("user.name", "user.email"):
            m = re.search(r'git config %s "([^"]+)"' % re.escape(key), text)
            self.bot[key] = m.group(1) if m else None
        self.scratch, self.dirty, self.calls, self.built = None, False, 0, 0
        self.this_repository = _this_repository()
        self.bash, first, self.why = _find_bash()
        self.path_first = [os.path.dirname(sys.executable)] + first
        if self.bash:
            self.why = self._probe()
            if self.why:
                self.bash = None

    def _probe(self):
        """None when the bash found finds what the script runs: git, md5sum and python."""
        env = _no_git_vars()
        env["PATH"] = os.pathsep.join(self.path_first + [env.get("PATH", "")])
        try:
            p = subprocess.run([self.bash, "-c", "command -v git && command -v md5sum && "
                                "command -v python"], cwd=tempfile.gettempdir(), env=env,
                               capture_output=True, encoding="utf-8", errors="replace",
                               timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            return "%s could not be started (%s)" % (self.bash, e.__class__.__name__)
        if p.returncode:
            return "%s does not find git, md5sum and python" % self.bash
        return None

    def fresh(self):
        """A new scratch repository, checked before its first call. False when there is none,
        and then nothing more is run."""
        self.close()
        self.built += 1
        try:
            scratch = _Scratch(self.script, self.generators)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            check("scratch repository %d can be built" % self.built, False, str(e))
            self.bash, self.why = None, "no scratch repository could be built"
            return False
        wrong = scratch.isolated()
        check("scratch repository %d is its own, before its first call: `git rev-parse "
              "--show-toplevel` there is its directory, found and pinned; it is outside this "
              "repository, in the system temporary directory; its origin is a bare repository "
              "beside it" % self.built, not wrong, wrong)
        if wrong:
            scratch.remove()
            self.bash, self.why = None, "a scratch repository failed its isolation check"
            return False
        self.scratch, self.dirty = scratch, False
        return True

    def call(self, args, github_actions=None, decoys=False):
        """One run of the script as a _Call, or None when it cannot run here."""
        if not self.bash:
            return None
        if (self.scratch is None or self.dirty) and not self.fresh():
            return None
        env = self.scratch.script_env(github_actions, decoys, self.path_first)
        self.calls += 1
        r = self.scratch.run(self.bash, args, env)
        self.dirty = bool(r.changed)
        return r

    def close(self):
        if self.scratch is not None:
            self.scratch.remove()
            self.scratch = None


def test_the_calls_run_in_a_scratch_repository(h):
    print("\n[bots] the script's modes run for real, in a scratch repository and nowhere else")
    if not h.bash:
        not_run("the script's modes, run in a scratch repository", h.why)
        return
    print("  bash: %s" % h.bash)
    h.fresh()


def test_off_actions_the_bots_mode_is_refused(h):
    print("\n[bots] off GitHub Actions, any argument but `regenerate` is refused before any "
          "git command")
    print("  (every call here also has %s, which must not open it)"
          % " and ".join("%s=%s" % kv for kv in sorted(DECOYS.items())))
    if not h.bash:
        not_run("%d calls off GitHub Actions" % (len(OFF_ACTIONS) * len(MISTAKES)), h.why)
        return
    for value, where in OFF_ACTIONS:
        for arg in MISTAKES:
            label = "%s, argument %r" % (where, arg)
            r = h.call([arg], github_actions=value, decoys=True)
            if r is None:
                not_run(label, h.why)
                continue
            check(label + ": exit 2, and the error names GITHUB_ACTIONS and `regenerate`",
                  r.code == 2 and "GITHUB_ACTIONS" in r.err
                  and REGENERATE_WORD.search(r.err) is not None,
                  "exit %s; stderr %r" % (r.code, _short(r.err)))
            check("  and no git command ran", not r.trace.strip(),
                  "git ran: %s" % " ".join(r.git))
            check("  and the scratch repository is as it was: user.name and user.email, the "
                  "uncommitted change, HEAD, origin", not r.changed, r.changed)


def test_the_local_modes_are_unchanged(h):
    print("\n[bots] no argument still prints the usage, and `regenerate` still only regenerates")
    if not h.bash:
        not_run("the usage and `regenerate`, on and off GitHub Actions", h.why)
        return
    wanted = sorted("%s --write" % g for g in h.generators)
    for value, where in ((None, "GITHUB_ACTIONS unset"), ("true", "GITHUB_ACTIONS=true")):
        label = "%s, no argument" % where
        r = h.call([], github_actions=value)
        if r is None:
            not_run(label, h.why)
            continue
        check(label + ": the usage, exit 2", r.code == 2 and "usage:" in r.err,
              "exit %s; stderr %r" % (r.code, _short(r.err)))
        check("  and no git command ran, and nothing in the scratch repository changed",
              not r.trace.strip() and not r.changed,
              r.changed or "git ran: %s" % " ".join(r.git))
    for value, where in ((None, "GITHUB_ACTIONS unset"), ("true", "GITHUB_ACTIONS=true")):
        label = "%s, argument 'regenerate'" % where
        r = h.call(["regenerate"], github_actions=value)
        if r is None:
            not_run(label, h.why)
            continue
        check(label + ": exit 0, having run every generator the script names",
              r.code == 0 and sorted(set(r.generators)) == wanted,
              "exit %s; ran %s; stderr %r" % (r.code, r.generators, _short(r.err)))
        check("  and no git identity, reset, commit or push: user.name and user.email, the "
              "uncommitted change, HEAD and origin as they were", not r.changed, r.changed)
        wrote = sorted(set(r.git) & WRITES)
        check("  and git ran only to read (the trace shows `diff`, and nothing that writes)",
              "diff" in r.git and not wrote, "git ran: %s" % (" ".join(r.git) or "nothing"))


def test_on_actions_the_bots_still_run(h):
    print("\n[bots] on GitHub Actions the bots' mode still runs, and ends as it does today")
    label = "GITHUB_ACTIONS=true, argument 'Snapshot 2026-09-22'"
    if not h.bash:
        not_run(label, h.why)
        return
    r = h.call(["Snapshot 2026-09-22"], github_actions="true")
    if r is None:
        not_run(label, h.why)
        return
    ident = {k: r.after[k] for k in ("user.name", "user.email")}
    check(label + ": it gets past the check, and writes the bot's identity into the scratch "
          "repository's config", all(h.bot.values()) and ident == h.bot,
          "identity %s; the script's bot is %s; stderr %r" % (ident, h.bot, _short(r.err)))
    check("  and the git trace saw it run git, so an empty trace above means no git ran",
          "config" in r.git, "git ran: %s" % (" ".join(r.git) or "nothing"))
    check("  and it ends as today with generators that change nothing: exit 0, \"the derived "
          "pages are already current\"",
          r.code == 0 and "the derived pages are already current" in r.out,
          "exit %s; stdout %r; stderr %r" % (r.code, _short(r.out), _short(r.err)))
    check("  and it ran the generators",
          sorted(set(r.generators)) == sorted("%s --write" % g for g in h.generators),
          "ran %s" % r.generators)
    check("  and nothing was committed or pushed: HEAD unchanged, and origin has no new commit",
          r.after["HEAD"] == h.scratch.base["HEAD"]
          and r.after["origin"] == h.scratch.base["origin"], r.changed)


def test_this_repository_was_not_reached(h):
    print("\n[bots] this repository is as it was before the calls")
    if not h.calls:
        not_run("this repository's identity and HEAD after the calls",
                h.why or "the script was not run")
        return
    now = _this_repository()
    check("its git identity and HEAD are what they were before the first call",
          now == h.this_repository, _what_moved(h.this_repository, now))


def _what_moved(before, after):
    """What differs between two readings of _this_repository(), in words: the names of the
    user.* keys that changed, never their values, which on a laptop are the owner's own and
    would travel with any output pasted into a public file (named change (c))."""
    def keys(reading):
        code, text = reading
        found = {}
        if code is not None:
            for line in text.splitlines():
                key, _, value = line.partition(" ")
                found.setdefault(key, []).append(value)
        return found
    b, a = keys(before[0]), keys(after[0])
    moved = [k for k in sorted(set(b) | set(a)) if b.get(k) != a.get(k)]
    out = ["changed: %s (values not shown)" % ", ".join(moved)] if moved else []
    if not moved and before[0] != after[0]:
        out.append("reading its user.* config went differently (exit %s, then %s)"
                   % (before[0][0], after[0][0]))
    if before[1] != after[1]:
        out.append("HEAD moved")
    return "; ".join(out)


# Named change (a), T-006 round 2. On GitHub Actions bash always exists, so a check that could
# not run there is a guard that silently declined to look, and an ok step would hide it.
SIMULATED_NO_BASH = "simulated here: no usable bash"


def test_on_actions_a_check_that_could_not_run_fails_this_file():
    print("\n[bots] on GitHub Actions a check that could not run fails this file; elsewhere "
          "it is said")
    # A child process runs this file with no usable bash, simulated where the file decides it
    # (_find_bash reports none), once on GitHub Actions and once off it. The child skips this
    # check, which would otherwise start another child.
    me = test_on_actions_a_check_that_could_not_run_fails_this_file.__name__
    module = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
    child = ("import sys; sys.path.insert(0, %r); import %s as t; "
             "t._find_bash = lambda: (None, [], %r); t.%s = lambda: None; t.main()"
             % (HERE, module, SIMULATED_NO_BASH, me))
    for value, where, want in (("true", "GITHUB_ACTIONS=true", 1),
                               (None, "GITHUB_ACTIONS unset", 0)):
        env = {k: v for k, v in os.environ.items() if k.upper() != "GITHUB_ACTIONS"}
        env["PYTHONIOENCODING"] = "utf-8"
        if value is not None:
            env["GITHUB_ACTIONS"] = value
        try:
            p = subprocess.run([sys.executable, "-c", child], cwd=ROOT, env=env,
                               capture_output=True, encoding="utf-8", errors="replace",
                               timeout=CALL_TIMEOUT)
            code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = None, "no exit: timed out after %ds" % CALL_TIMEOUT
        printed = "NOT RUN HERE" in out and SIMULATED_NO_BASH in out
        summary = out.rsplit("=" * 68, 1)[-1]
        if want:
            says_why = "GitHub Actions" in summary and SIMULATED_NO_BASH in summary
            check("%s, no usable bash: this file exits 1, prints the not-run lines, and its "
                  "summary says why" % where, code == 1 and printed and says_why,
                  "exit %s; not-run lines %s; summary %r" % (code, printed, _short(summary)))
        else:
            check("%s, no usable bash: this file exits 0 and prints the not-run lines" % where,
                  code == 0 and printed,
                  "exit %s; not-run lines %s; summary %r" % (code, printed, _short(summary)))


def main():
    print("=" * 68)
    print("A bot's commit regenerates what it moves, and is tested")
    print("=" * 68)
    test_every_pushing_workflow_is_tested_after()
    test_every_pushing_workflow_regenerates_after_its_data()
    test_the_shared_script_runs_every_generator_a_bot_can_stale()
    started = time.time()
    h = _Harness()
    try:
        test_the_calls_run_in_a_scratch_repository(h)
        test_off_actions_the_bots_mode_is_refused(h)
        test_the_local_modes_are_unchanged(h)
        test_on_actions_the_bots_still_run(h)      # last: it writes the bot's identity
    finally:
        h.close()
    test_this_repository_was_not_reached(h)
    print("\n  the script ran %d times in %d scratch repositories; %.1fs"
          % (h.calls, h.built, time.time() - started))
    test_on_actions_a_check_that_could_not_run_fails_this_file()
    print("\n" + "=" * 68)
    print("%d passed, %d failed%s" % (_PASSED, len(_FAILS),
                                      ", %d not run here" % len(_NOT_RUN) if _NOT_RUN else ""))
    # On GitHub Actions bash always exists, so a check that could not run there is not a
    # machine's limit but a guard that declined to look, and an ok step would hide it.
    blind = bool(_NOT_RUN) and os.environ.get("GITHUB_ACTIONS") == "true"
    if blind:
        print("FAILED: on GitHub Actions every check must run, and %d could not:" % len(_NOT_RUN))
        for why in sorted(set(why for _, why in _NOT_RUN)):
            print("  " + why)
    if _FAILS or blind:
        sys.exit(1)
    if _NOT_RUN:
        print("everything that ran passed; %d check(s) could not run here and are not passed"
              % len(_NOT_RUN))
    else:
        print("all passed")


if __name__ == "__main__":
    main()
