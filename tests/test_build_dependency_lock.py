"""T-033: host SDK locks and credential-free Linux packaging stay explicit.

TOML is parsed, distribution provenance is checked, and uv owns resolver semantics.
All negative controls are synthetic and offline. No package install or build runs here.
Run: python tests/test_build_dependency_lock.py
"""
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_deploy_gate as workflow  # noqa: E402 -- reuse its independent workflow reader

ROOT = Path(__file__).resolve().parents[1]
PINS = {"workers-py": "1.17.8", "workers-runtime-sdk": "1.9.4"}
INSTALL = "python -m pip install --no-deps uv==0.13.1"
SYNC = "uv sync --locked"
DEPLOY = "uv run --locked pywrangler deploy"
DRY_RUN = DEPLOY + " --dry-run"
PASSED, FAILURES, EXECUTED = 0, [], []


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
        print("  PASS " + name)
    else:
        FAILURES.append((name, str(detail)))
        print("  FAIL %s: %s" % (name, detail))


def host_errors(project_text, lock_text, ignored=False):
    errors = []
    try:
        project = tomllib.loads(project_text)
    except tomllib.TOMLDecodeError:
        return ["pyproject.toml must be valid TOML"]
    metadata = project.get("project", {})
    if metadata.get("requires-python") != ">=3.12" or metadata.get("dependencies") != []:
        errors.append("keep the Python target and empty production dependencies")
    wanted = [name + "==" + version for name, version in PINS.items()]
    if project.get("dependency-groups", {}).get("dev") != wanted:
        errors.append("pin exactly workers-py==1.17.8 and workers-runtime-sdk==1.9.4 in dev")
    if ignored:
        errors.append("uv.lock is ignored; remove its ignore rule and commit the lock")
    if lock_text is None:
        return errors + ["uv.lock is missing; generate it with uv 0.13.1 and public PyPI"]
    try:
        lock = tomllib.loads(lock_text)
    except tomllib.TOMLDecodeError:
        return errors + ["uv.lock must be valid TOML"]
    packages = lock.get("package")
    if not isinstance(packages, list) or not packages:
        return errors + ["uv.lock must contain resolved package entries"]
    if lock.get("requires-python") != metadata.get("requires-python"):
        errors.append("uv.lock Python requirement must match pyproject.toml")
    for name, version in PINS.items():
        found = [item for item in packages if isinstance(item, dict) and item.get("name") == name]
        if not found or any(item.get("version") != version for item in found):
            errors.append("uv.lock must resolve %s==%s" % (name, version))
    roots = [item for item in packages if isinstance(item, dict)
             and item.get("name") == metadata.get("name") and item.get("source") == {"virtual": "."}]
    if len(roots) != 1:
        errors.append("uv.lock must identify exactly the virtual project root")
    else:
        root = roots[0]
        linked = root.get("dev-dependencies", {}).get("dev", [])
        declared = root.get("metadata", {}).get("requires-dev", {}).get("dev", [])
        if {item.get("name") for item in linked if isinstance(item, dict)} != set(PINS):
            errors.append("uv.lock root must link both direct development SDKs")
        if {item.get("name"): item.get("specifier") for item in declared if isinstance(item, dict)} != {
                name: "==" + version for name, version in PINS.items()}:
            errors.append("uv.lock root must retain the exact direct SDK specifiers")
    for package in packages:
        if not isinstance(package, dict):
            errors.append("uv.lock package entries must be tables")
            continue
        name = package.get("name", "unnamed")
        if not isinstance(package.get("version"), str) or not package["version"]:
            errors.append("uv.lock package %s needs a resolved version" % name)
        if package in roots:
            continue
        if package.get("source") != {"registry": "https://pypi.org/simple"}:
            errors.append("uv.lock package %s must use public PyPI, without private or local sources" % name)
        distributions = []
        if "sdist" in package:
            distributions.append(package["sdist"])
        wheels = package.get("wheels", [])
        if isinstance(wheels, list):
            distributions.extend(wheels)
        else:
            errors.append("uv.lock package %s wheels must be a list" % name)
        if not distributions:
            errors.append("uv.lock package %s needs hashed public distributions" % name)
        for distribution in distributions:
            if not isinstance(distribution, dict):
                errors.append("uv.lock package %s distributions must be tables" % name)
                continue
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(distribution.get("hash", ""))):
                errors.append("uv.lock package %s has an unhashed distribution" % name)
            url = urlsplit(str(distribution.get("url", "")))
            if (url.scheme != "https" or url.hostname != "files.pythonhosted.org"
                    or url.username or url.password or url.query or url.fragment):
                errors.append("uv.lock package %s needs a credential-free public distribution URL" % name)
    return errors


def host_commands(text, job, dry_run=False):
    lines = workflow.jobs(text).get(job)
    if not lines:
        return ["%s job is missing" % job]
    commands = [(i, command) for i, step in enumerate(workflow.steps(lines)) for command in step["run"]]
    expected = DRY_RUN if dry_run else DEPLOY
    errors = []
    for command in (INSTALL, SYNC, expected):
        if sum(value == command for _, value in commands) != 1:
            errors.append("%s must run exactly once: %s" % (job, command))
    allowed = {INSTALL, SYNC, expected, "uv --version"}
    for _, command in commands:
        if re.search(r"\buv\b|astral\.sh|\b(?:py)?wrangler\b.*\bdeploy\b", command) and command not in allowed:
            errors.append("%s has unpinned or unlocked host tooling; use uv 0.13.1 and --locked" % job)
    positions = [next((i for i, value in commands if value == command), None)
                 for command in (INSTALL, SYNC, expected)]
    if None not in positions and positions != sorted(positions):
        errors.append("%s must install pinned uv, sync --locked, then run --locked" % job)
    return errors


def build_errors(text):
    lines = workflow.jobs(text).get("build")
    if not lines:
        return ["build job is missing; add credential-free Linux pywrangler deploy --dry-run"]
    body = "\n".join(lines)
    errors = host_commands(text, "build", dry_run=True)
    if not re.search(r"^    runs-on:\s*ubuntu-[\w.-]+\s*$", body, re.M):
        errors.append("build must run on Linux")
    if not re.search(r"^    if: github.event_name != 'workflow_run'\s*$", body, re.M):
        errors.append("build must run on branch pushes and skip bot workflow_run events")
    if not re.search(r"^    needs:\s*test\s*$", body, re.M):
        errors.append("build must follow the required offline test job")
    if ("secrets." in body or re.search(r"^\s*(env|environment|continue-on-error):", body, re.M)
            or re.search(r"^env:", text.split("jobs:", 1)[0], re.M)):
        errors.append("build must have no secrets environment, credential gate or soft failure")
    steps = workflow.steps(lines)
    allowed_actions = ("actions/checkout@", "actions/setup-python@", "actions/setup-node@", "actions/upload-artifact@")
    for step in steps:
        keys = step["keys"]
        if "if" in keys or "continue-on-error" in keys or "env" in keys:
            errors.append("build steps must not be credential-skipped or soft-failed")
        uses = keys.get("uses", "")
        if uses and not uses.startswith(allowed_actions):
            errors.append("build has an unsupported action")
        # The shared reader flags node/upload actions because the offline runner cannot run them.
        # Their YAML remains parsed here; every other refusal must still fail this guard.
        if any(not line.startswith("uses: " + uses) for line in step["refused"]):
            errors.append("build contains unsupported workflow syntax")
    for action, key, value in (("actions/checkout@", "fetch-depth", "0"),
                               ("actions/checkout@", "persist-credentials", "false"),
                               ("actions/setup-python@", "python-version", "3.12"),
                               ("actions/setup-node@", "node-version", "22")):
        found = [step for step in steps if step["keys"].get("uses", "").startswith(action)]
        if len(found) != 1 or found[0]["with"].get(key) != value:
            errors.append("build must set %s %s=%s" % (action, key, value))
    uploads = [step for step in steps if step["keys"].get("uses", "").startswith("actions/upload-artifact@")]
    if (len(uploads) != 1 or uploads[0]["with"].get("path") != "pylock.toml"
            or uploads[0]["with"].get("if-no-files-found") != "error"):
        errors.append("build must retain only generated public pylock.toml, failing if it is missing")
    commands = [command for step in steps for command in step["run"]]
    expected = [INSTALL, "uv --version", SYNC, DRY_RUN, "git diff --exit-code"]
    if commands != expected:
        errors.append("build must dry-run without upload, then fail on tracked changes")
    if uploads and steps.index(uploads[0]) <= next((i for i, step in enumerate(steps) if DRY_RUN in step["run"]), len(steps)):
        errors.append("build must upload pylock only after the dry-run")
    return errors


PROJECT = '''[project]
name = "vetagent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []
[dependency-groups]
dev = ["workers-py==1.17.8", "workers-runtime-sdk==1.9.4"]
'''
LOCK = '''version = 1
revision = 5
requires-python = ">=3.12"
[[package]]
name = "vetagent"
version = "0.1.0"
source = { virtual = "." }
[package.dev-dependencies]
dev = [{ name = "workers-py" }, { name = "workers-runtime-sdk" }]
[package.metadata.requires-dev]
dev = [{ name = "workers-py", specifier = "==1.17.8" }, { name = "workers-runtime-sdk", specifier = "==1.9.4" }]
'''
for _name, _version, _digest in (("click", "8.5.0", "a"), ("workers-py", "1.17.8", "b"),
                                  ("workers-runtime-sdk", "1.9.4", "c")):
    LOCK += ('\n[[package]]\nname = "%s"\nversion = "%s"\n'
             'source = { registry = "https://pypi.org/simple" }\n'
             'wheels = [{ url = "https://files.pythonhosted.org/packages/fixture/%s.whl", '
             'hash = "sha256:%s" }]\n') % (_name, _version, _name, _digest * 64)
DEPLOY_WORKFLOW = '''on:
  push:
    branches: [master]
    paths:
      - "uv.lock"
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Install uv
        run: python -m pip install --no-deps uv==0.13.1
      - name: Sync dependencies
        run: uv sync --locked
      - name: Deploy
        run: uv run --locked pywrangler deploy
'''
BUILD_WORKFLOW = '''on:
  push:
    branches: ["**"]
jobs:
  build:
    if: github.event_name != 'workflow_run'
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: Install uv
        run: python -m pip install --no-deps uv==0.13.1
      - name: Verify uv version
        run: uv --version
      - name: Sync dependencies
        run: uv sync --locked
      - name: Build without credentials or upload
        run: uv run --locked pywrangler deploy --dry-run
      - name: Check tracked files
        run: git diff --exit-code
      - uses: actions/upload-artifact@v4
        with:
          name: public-python-runtime-lock
          path: pylock.toml
          if-no-files-found: error
'''


def test_actual_toml_pins_and_public_lock():
    lock = ROOT / "uv.lock"
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", "uv.lock"], cwd=ROOT).returncode
    check("git can inspect the lock ignore state", ignored in (0, 1), ignored)
    errors = host_errors((ROOT / "pyproject.toml").read_text(encoding="utf-8"),
                         lock.read_text(encoding="utf-8") if lock.is_file() else None, ignored == 0)
    check("actual exact SDK pins and hashed public host lock", not errors, "; ".join(errors))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "uv.lock"], cwd=ROOT,
                             capture_output=True).returncode == 0
    check("uv.lock is tracked rather than an ignored local artifact", tracked)


def test_actual_deploy_uses_locked_host_tooling():
    text = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    errors = host_commands(text, "deploy")
    check("actual deploy installs pinned uv and syncs/runs --locked", not errors, "; ".join(errors))
    header = text.split("jobs:", 1)[0]
    check("uv.lock changes trigger deployment", bool(re.search(r'^\s+- ["\']uv\.lock["\']\s*$', header, re.M)))


def test_actual_branch_build_has_no_cloudflare_credentials():
    text = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    errors = build_errors(text)
    check("actual Linux branch build is credential-free and retains public pylock", not errors, "; ".join(errors))
    check("branch pushes trigger the build workflow", bool(re.search(r'push:\s*\n\s*branches:\s*\["\*\*"\]', text)))
    runs = [command for step in workflow.steps(workflow.jobs(text).get("test", [])) for command in step["run"]]
    check("the new offline guard is registered exactly once", runs.count("python tests/test_build_dependency_lock.py") == 1)


def test_synthetic_valid_controls_pass():
    check("synthetic TOML control passes", not host_errors(PROJECT, LOCK))
    check("synthetic deploy control passes", not host_commands(DEPLOY_WORKFLOW, "deploy"))
    check("synthetic credential-free build control passes", not build_errors(BUILD_WORKFLOW))


def test_synthetic_lock_negative_controls_are_refused():
    controls = (
        ("missing lock", PROJECT, None, False, "uv.lock is missing"),
        ("ignored lock", PROJECT, LOCK, True, "uv.lock is ignored"),
        ("removed direct pin", PROJECT.replace("==1.17.8", "", 1), LOCK, False, "pin exactly"),
        ("missing direct SDK", PROJECT.replace("workers-runtime-sdk", "other-sdk", 1), LOCK, False, "pin exactly"),
        ("malformed project TOML", "[", LOCK, False, "valid TOML"),
        ("malformed lock TOML", PROJECT, "broken =", False, "valid TOML"),
        ("mismatched SDK", PROJECT, LOCK.replace('version = "1.17.8"', 'version = "1.17.7"', 1), False, "resolve workers-py==1.17.8"),
        ("unversioned transitive", PROJECT, LOCK.replace('version = "8.5.0"', 'version = ""', 1), False, "resolved version"),
        ("unhashed transitive", PROJECT, LOCK.replace('hash = "sha256:' + "a" * 64 + '"', 'size = 1', 1), False, "unhashed distribution"),
        ("malformed hash", PROJECT, LOCK.replace("sha256:" + "b" * 64, "sha256:short", 1), False, "unhashed distribution"),
        ("private index", PROJECT, LOCK.replace("https://pypi.org/simple", "https://packages.invalid/simple", 1), False, "public PyPI"),
        ("local source", PROJECT, LOCK.replace('registry = "https://pypi.org/simple"', 'directory = "../fixture"', 1), False, "public PyPI"),
        ("credential URL", PROJECT, LOCK.replace("https://files.pythonhosted.org", "https://user:password@files.pythonhosted.org", 1), False, "credential-free public"),
        ("nonpublic wheel", PROJECT, LOCK.replace("https://files.pythonhosted.org", "https://packages.invalid", 1), False, "credential-free public"),
        ("missing root links", PROJECT, LOCK.replace('[package.dev-dependencies]\ndev = [{ name = "workers-py" }, { name = "workers-runtime-sdk" }]', '[package.dev-dependencies]\ndev = []', 1), False, "root must link"),
        ("floating root metadata", PROJECT, LOCK.replace('specifier = "==1.17.8"', 'specifier = ">=1.17.8"', 1), False, "exact direct SDK specifiers"),
    )
    for name, project, lock, ignored, expected in controls:
        errors = host_errors(project, lock, ignored)
        check(name + " is refused actionably", any(expected in error for error in errors), errors)


def test_synthetic_workflow_negative_controls_are_refused():
    for label, source, job, dry in (("deploy", DEPLOY_WORKFLOW, "deploy", False),
                                     ("build", BUILD_WORKFLOW, "build", True)):
        for name, old, new in (("unversioned installer", INSTALL, "curl -LsSf https://astral.sh/uv/install.sh | sh"),
                               ("unlocked sync", SYNC, "uv sync"),
                               ("unlocked run", "uv run --locked", "uv run"),
                               ("wrong uv pin", "uv==0.13.1", "uv==0.12.18")):
            assert source.count(old) == 1
            errors = host_commands(source.replace(old, new, 1), job, dry_run=dry)
            check(label + " " + name + " turns the guard red", bool(errors), errors)
    mutations = (
        ("no dry-run", DRY_RUN, DEPLOY),
        ("credentials condition", "    needs: test", "    needs: test\n    env:\n      TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}"),
        ("step skipped", "      - name: Sync dependencies", "      - name: Sync dependencies\n        if: steps.creds.outputs.ready == 'true'"),
        ("soft failure", "    needs: test", "    needs: test\n    continue-on-error: true"),
        ("Windows runner", "ubuntu-latest", "windows-latest"),
        ("shallow history", "fetch-depth: 0", "fetch-depth: 1"),
        ("persisted credentials", "persist-credentials: false", "persist-credentials: true"),
        ("wrong host Python", 'python-version: "3.12"', 'python-version: "3.13"'),
        ("wrong Node input", 'node-version: "22"', 'node-version: "24"'),
        ("missing tracked-file check", "        run: git diff --exit-code", "        run: echo unchecked"),
        ("unsafe artifact", "path: pylock.toml", "path: ."),
        ("missing artifact accepted", "if-no-files-found: error", "if-no-files-found: ignore"),
        ("credential-gated job", "github.event_name != 'workflow_run'", "steps.creds.outputs.ready == 'true'"),
    )
    for name, old, new in mutations:
        assert BUILD_WORKFLOW.count(old) == 1
        errors = build_errors(BUILD_WORKFLOW.replace(old, new, 1))
        check("build " + name + " turns the guard red", bool(errors), errors)


def main():
    for name, function in sorted((name, value) for name, value in globals().items() if name.startswith("test_")):
        EXECUTED.append(name)
        try:
            function()
        except Exception as exc:  # noqa: BLE001 -- fail visibly while reaching every test
            check(name + " completes", False, "%s: %s" % (type(exc).__name__, exc))
    print("Executed: " + ", ".join(EXECUTED))
    print("%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
