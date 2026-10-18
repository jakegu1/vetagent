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
    allowed = {INSTALL, SYNC, expected, "uv --version", TARGET_SYNC, NPM_CI,
               LOCAL_WRANGLER, LOCK_BASELINE, LOCK_VERIFY, TRACKED_DIFF}
    for _, command in commands:
        if re.search(r"\buv\b|astral\.sh|\b(?:py)?wrangler\b.*\bdeploy\b", command) and command not in allowed:
            errors.append("%s has unpinned or unlocked host tooling; use uv 0.13.1 and --locked" % job)
    positions = [next((i for i, value in commands if value == command), None)
                 for command in (INSTALL, SYNC, expected)]
    if None not in positions and positions != sorted(positions):
        errors.append("%s must install pinned uv, sync --locked, then run --locked" % job)
    if runtime_complete_workflow(text, job):
        errors.extend(runtime_workflow_errors(text, job))
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
    if runtime_complete_workflow(text, "build"):
        expected = runtime_expected_commands("build")
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


# T-035 additive acceptance. The original T-033 functions, fixtures and controls stay frozen.
import base64
import hashlib
import json
import os
import shutil
import tempfile

NPM_CI = "npm ci --ignore-scripts --no-audit --no-fund"
LOCAL_WRANGLER = ("node -e \"const {execFileSync}=require('node:child_process'); "
                  "const version=execFileSync(process.execPath,['./node_modules/wrangler/bin/wrangler.js','--version'],"
                  "{encoding:'utf8'}).trim(); console.log(version); if(version!=='4.151.1') process.exit(1)\"")
LOCK_BASELINE = 'sha256sum uv.lock pylock.toml package-lock.json > "$RUNNER_TEMP/build-locks.sha256"'
LOCK_VERIFY = 'sha256sum --check "$RUNNER_TEMP/build-locks.sha256"'
TARGET_SYNC = "uv run --locked pywrangler sync"
OFFLINE = "python .github/scripts/offline_suite.py"
TRACKED_DIFF = "git diff --exit-code"
RUNTIME_WHEEL_SHA = "2bd6f5788fd6fdd38ff677e37c93fd92b37ff3a3ab33b43b7ed84ba50688a647"
RUNTIME_WHEEL_URL = ("https://files.pythonhosted.org/packages/ff/0d/"
                     "e042cc8ac587699e7479db34dee27bd653297d709386b22e926d2672bbc8/"
                     "workers_runtime_sdk-1.9.4-py3-none-any.whl")


def node_lock_errors(project_text, lock_text):
    errors = []
    try:
        project = json.loads(project_text) if project_text is not None else None
    except (ValueError, TypeError):
        project = None
    if not isinstance(project, dict):
        return ["package.json is missing or invalid JSON; commit a private dev-only Wrangler manifest"]
    if project.get("private") is not True or project.get("dependencies", {}) != {} or project.get("scripts", {}) != {}:
        errors.append("package.json must be private, dev-only and have no publish/install scripts")
    if project.get("devDependencies") != {"wrangler": "4.151.1"}:
        errors.append("pin exactly wrangler 4.151.1 as the only development dependency")
    if any(key in project for key in ("publishConfig", "workspaces", "optionalDependencies")):
        errors.append("keep the build manifest free of publishing, workspaces and runtime dependencies")
    try:
        lock = json.loads(lock_text) if lock_text is not None else None
    except (ValueError, TypeError):
        lock = None
    if not isinstance(lock, dict):
        return errors + ["package-lock.json is missing or invalid JSON; generate it with public npm"]
    packages = lock.get("packages")
    if lock.get("lockfileVersion") != 3 or not isinstance(packages, dict):
        return errors + ["package-lock.json must contain the npm version 3 packages lock"]
    root = packages.get("", {})
    if root.get("devDependencies") != {"wrangler": "4.151.1"} or root.get("dependencies", {}) != {}:
        errors.append("npm lock root must retain the exact dev-only Wrangler pin")
    if packages.get("node_modules/wrangler", {}).get("version") != "4.151.1":
        errors.append("npm lock must resolve wrangler 4.151.1")
    for name, package in packages.items():
        if not name:
            continue
        if not isinstance(package, dict):
            errors.append("npm lock package entries must be objects")
            continue
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.+-]+)?", str(package.get("version", ""))):
            errors.append("npm lock %s needs an exact resolved version" % name)
        url = urlsplit(str(package.get("resolved", "")))
        if (url.scheme != "https" or url.hostname != "registry.npmjs.org" or url.username
                or url.password or url.query or url.fragment or package.get("link")):
            errors.append("npm lock %s needs a credential-free public npm distribution" % name)
        integrity = str(package.get("integrity", ""))
        try:
            valid_hash = integrity.startswith("sha512-") and len(base64.b64decode(integrity[7:], validate=True)) == 64
        except (ValueError, TypeError):
            valid_hash = False
        if not valid_hash:
            errors.append("npm lock %s needs a SHA512 distribution integrity hash" % name)
    return errors


def target_lock_errors(text, ignored=False):
    errors = ["pylock.toml is ignored; track the inspected Linux target lock"] if ignored else []
    if text is None:
        return errors + ["pylock.toml is missing; use the inspected Linux target artifact"]
    try:
        lock = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return errors + ["pylock.toml must be valid target-lock TOML"]
    if (lock.get("lock-version") != "1.0" or lock.get("created-by") != "uv"
            or lock.get("requires-python") != ">=3.13.2"):
        errors.append("retain the actual Linux target metadata, distinct from the host lock")
    packages = lock.get("packages")
    if not isinstance(packages, list) or len(packages) != 1:
        return errors + ["target lock must contain only workers-runtime-sdk 1.9.4"]
    package = packages[0]
    if package.get("name") != "workers-runtime-sdk" or package.get("version") != "1.9.4":
        errors.append("target lock must select workers-runtime-sdk 1.9.4")
    wheels = package.get("wheels", [])
    if (len(wheels) != 1 or wheels[0].get("url") != RUNTIME_WHEEL_URL
            or wheels[0].get("hashes") != {"sha256": RUNTIME_WHEEL_SHA}
            or any(key not in {"name", "version", "wheels"} for key in package)):
        errors.append("target lock must retain the inspected public SDK wheel URL and SHA256, without local sources")
    return errors


def runtime_expected_commands(job):
    if job == "build":
        return [LOCK_BASELINE, INSTALL, "uv --version", NPM_CI, LOCAL_WRANGLER, SYNC,
                TARGET_SYNC, LOCK_VERIFY, TRACKED_DIFF, DRY_RUN, LOCK_VERIFY, TRACKED_DIFF]
    return [LOCK_BASELINE, OFFLINE, INSTALL, NPM_CI, LOCAL_WRANGLER, SYNC,
            TARGET_SYNC, LOCK_VERIFY, TRACKED_DIFF, DEPLOY]


def runtime_complete_workflow(text, job):
    # Original T-033 fixtures are partial workflow documents. Real workflows contain
    # the pre-existing offline job/gate even if every new T-035 step is deleted.
    jobs = workflow.jobs(text)
    if job == "build":
        return "test" in jobs
    return any(OFFLINE in step["run"] for step in workflow.steps(jobs.get(job, [])))


def runtime_workflow_errors(text, job):
    lines = workflow.jobs(text).get(job)
    if not lines:
        return [job + " job is missing"]
    steps = workflow.steps(lines)
    relevant = []
    expected = runtime_expected_commands(job)
    errors = []
    for step in steps:
        if job == "deploy" and step["keys"].get("id") == "creds":
            continue
        for command in step["run"]:
            relevant.append(command)
            if job == "deploy" and command == DEPLOY:
                break
        if job == "deploy" and DEPLOY in step["run"]:
            break
    if relevant != expected:
        errors.append(job + " must capture lock bytes before installs, npm ci, verify local Wrangler, sync locked host/target, check bytes and diff before upload; build also checks after dry-run")
    body = "\n".join(lines)
    if "--upgrade" in body:
        errors.append(job + " must not upgrade target resolution")
    for step in steps:
        if any(command in expected for command in step["run"]):
            keys = step["keys"]
            if "continue-on-error" in keys or "shell" in keys or "working-directory" in keys:
                errors.append(job + " locked steps must not soft-fail or change execution context")
            if job == "deploy" and keys.get("if") != "steps.creds.outputs.ready == 'true'":
                errors.append("deploy locked steps must keep the deployment credential condition")
            if job == "build" and any(key in keys for key in ("if", "env", "continue-on-error")):
                errors.append("build locked steps must remain credential-free and reachable")
    if job == "build":
        if not re.search(r"^      fail-fast: false\s*$", body, re.M) or not re.search(r"^        clean-build: \[1, 2\]\s*$", body, re.M):
            errors.append("build must use exactly two independent clean matrix entries with fail-fast false")
        matrices = re.findall(r"^      matrix:\n((?:        [^\n]*\n)*)", body + "\n", re.M)
        if len(matrices) != 1 or matrices[0].strip() != "clean-build: [1, 2]":
            errors.append("build matrix must remain bounded at exactly two")
        uploads = [step for step in steps if step["keys"].get("uses", "").startswith("actions/upload-artifact@")]
        if len(uploads) != 1 or uploads[0]["with"].get("name") != "public-python-runtime-lock-${{ matrix.clean-build }}":
            errors.append("build artifacts must have distinct fixed-matrix names")
    return errors


NODE_PROJECT = json.dumps({"name": "vetagent-build-tools", "version": "0.1.0", "private": True,
                           "devDependencies": {"wrangler": "4.151.1"}})
NODE_LOCK = json.dumps({"lockfileVersion": 3, "packages": {
    "": {"devDependencies": {"wrangler": "4.151.1"}},
    "node_modules/wrangler": {"version": "4.151.1", "resolved": "https://registry.npmjs.org/wrangler/-/wrangler-4.151.1.tgz",
                               "integrity": "sha512-" + base64.b64encode(b"x" * 64).decode("ascii")}}})
TARGET_LOCK = ('lock-version = "1.0"\ncreated-by = "uv"\nrequires-python = ">=3.13.2"\n'
               '[[packages]]\nname = "workers-runtime-sdk"\nversion = "1.9.4"\n'
               'wheels = [{ url = "%s", hashes = { sha256 = "%s" } }]\n') % (RUNTIME_WHEEL_URL, RUNTIME_WHEEL_SHA)


def runtime_fixture(job):
    header = "jobs:\n"
    if job == "build":
        header += "  test:\n    steps:\n      - run: python tests/test_risk.py\n"
    text = header + "  " + job + ":\n    runs-on: ubuntu-latest\n"
    if job == "build":
        text += "    strategy:\n      fail-fast: false\n      matrix:\n        clean-build: [1, 2]\n"
    text += "    steps:\n"
    for number, command in enumerate(runtime_expected_commands(job)):
        text += "      - name: locked step %d\n" % number
        if job == "deploy":
            text += "        if: steps.creds.outputs.ready == 'true'\n"
        text += "        run: " + command + "\n"
    if job == "build":
        text += ("      - uses: actions/upload-artifact@v4\n        with:\n"
                 "          name: public-python-runtime-lock-${{ matrix.clean-build }}\n"
                 "          path: pylock.toml\n          if-no-files-found: error\n")
    return text


def test_runtime_actual_node_and_target_locks():
    values = {}
    for name in ("package.json", "package-lock.json", "pylock.toml"):
        path = ROOT / name
        values[name] = path.read_text(encoding="utf-8") if path.is_file() else None
    errors = node_lock_errors(values["package.json"], values["package-lock.json"])
    check("actual public transitive npm lock pins dev-only Wrangler", not errors, "; ".join(errors))
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", "pylock.toml"], cwd=ROOT).returncode
    errors = target_lock_errors(values["pylock.toml"], ignored == 0)
    check("actual Linux target lock retains inspected SDK distribution", ignored in (0, 1) and not errors, "; ".join(errors))
    for name in values:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", name], cwd=ROOT, capture_output=True).returncode == 0
        check(name + " is a tracked lock input", tracked)


def test_runtime_actual_workflows_enforce_extended_sequence():
    for name, job in (("deploy.yml", "deploy"), ("test.yml", "build")):
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        errors = runtime_workflow_errors(text, job)
        check("actual " + job + " locks Node/target and byte-checks in order", not errors, "; ".join(errors))
        if job == "deploy":
            header = text.split("jobs:", 1)[0]
            for path in ("package.json", "package-lock.json", "pylock.toml"):
                check(path + " changes trigger deploy", bool(re.search(r'^\s+- ["\']' + re.escape(path) + r'["\']\s*$', header, re.M)))


def test_runtime_synthetic_positive_controls():
    check("synthetic public npm lock control", not node_lock_errors(NODE_PROJECT, NODE_LOCK))
    check("synthetic inspected target lock control", not target_lock_errors(TARGET_LOCK))
    for job in ("deploy", "build"):
        check("synthetic extended " + job + " sequence control", not runtime_workflow_errors(runtime_fixture(job), job))


def test_runtime_synthetic_resolution_negative_controls():
    controls = (
        ("missing npm lock", NODE_PROJECT, None, "package-lock.json"),
        ("floating Wrangler", NODE_PROJECT.replace("4.151.1", "^4.151.1"), NODE_LOCK, "pin exactly"),
        ("project install hook", NODE_PROJECT[:-1] + ', "scripts": {"postinstall": "echo hook"}}', NODE_LOCK, "no publish/install"),
        ("missing npm integrity", NODE_PROJECT, NODE_LOCK.replace('"integrity":', '"missing-integrity":'), "integrity hash"),
        ("private npm source", NODE_PROJECT, NODE_LOCK.replace("registry.npmjs.org", "packages.invalid"), "public npm"),
        ("credential npm source", NODE_PROJECT, NODE_LOCK.replace("https://registry", "https://user:password@registry"), "credential-free"),
        ("mismatched locked Wrangler", NODE_PROJECT, NODE_LOCK.replace('"version": "4.151.1"', '"version": "4.151.0"'), "resolve wrangler"),
    )
    for label, project, lock, expected in controls:
        errors = node_lock_errors(project, lock)
        check(label + " is refused", any(expected in error for error in errors), errors)
    for label, lock, ignored, expected in (
            ("missing target lock", None, False, "is missing"),
            ("ignored target lock", TARGET_LOCK, True, "is ignored"),
            ("wrong target SDK", TARGET_LOCK.replace('version = "1.9.4"', 'version = "1.9.5"'), False, "1.9.4"),
            ("unhashed target wheel", TARGET_LOCK.replace("sha256", "missing-hash"), False, "SHA256"),
            ("host lock used as target", TARGET_LOCK.replace(">=3.13.2", ">=3.12"), False, "target metadata"),
            ("private target wheel", TARGET_LOCK.replace("files.pythonhosted.org", "packages.invalid"), False, "public SDK")):
        errors = target_lock_errors(lock, ignored)
        check(label + " is refused", any(expected in error for error in errors), errors)


def test_runtime_synthetic_workflow_negative_controls():
    for job in ("deploy", "build"):
        source = runtime_fixture(job)
        controls = (("no npm ci", NPM_CI, "npm install"),
                    ("install hooks enabled", NPM_CI, "npm ci"),
                    ("fallback version check", LOCAL_WRANGLER, "npx --yes wrangler --version"),
                    ("no explicit target sync", TARGET_SYNC, "echo omitted target sync"),
                    ("target upgrade", TARGET_SYNC, TARGET_SYNC + " --upgrade"),
                    ("no byte baseline", LOCK_BASELINE, "echo omitted baseline"),
                    ("no pre-upload byte guard", LOCK_VERIFY, "echo omitted byte guard"),
                    ("no separate tracked diff", TRACKED_DIFF, "echo omitted diff"))
        for label, old, new in controls:
            assert old in source
            errors = runtime_workflow_errors(source.replace(old, new, 1), job)
            check(job + " " + label + " is refused", bool(errors), errors)
        late = source.replace("        run: " + LOCK_BASELINE, "        run: BASELINE_PLACEHOLDER", 1)
        late = late.replace("        run: " + NPM_CI, "        run: " + LOCK_BASELINE, 1)
        late = late.replace("        run: BASELINE_PLACEHOLDER", "        run: " + NPM_CI, 1)
        check(job + " baseline after installation is refused", bool(runtime_workflow_errors(late, job)))
        removed = source
        for command in (LOCK_BASELINE, NPM_CI, LOCAL_WRANGLER, TARGET_SYNC, LOCK_VERIFY):
            removed = removed.replace("        run: " + command, "        run: echo removed new step")
        check(job + " deleting all new steps cannot select legacy acceptance", bool(runtime_workflow_errors(removed, job)))
    build = runtime_fixture("build")
    for label, old, new in (("unbounded matrix", "clean-build: [1, 2]", "clean-build: [1, 2, 3]"),
                             ("additional matrix axis", "clean-build: [1, 2]", "clean-build: [1, 2]\n        extra: [1, 2]"),
                             ("artifact collision", "public-python-runtime-lock-${{ matrix.clean-build }}", "public-python-runtime-lock")):
        check(label + " is refused", bool(runtime_workflow_errors(build.replace(old, new, 1), "build")))


def test_runtime_named_helpers_validate_complete_extended_workflows():
    # Use the existing real workflow context so deletion of new steps cannot opt out.
    for name, job in (("deploy.yml", "deploy"), ("test.yml", "build")):
        actual = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        check(job + " complete workflow retains its pre-existing offline context", runtime_complete_workflow(actual, job))
        errors = host_commands(runtime_fixture(job), job, dry_run=(job == "build"))
        check(job + " named helper validates the enumerated complete extended sequence", not errors, errors)
        removed = actual
        for command in (LOCK_BASELINE, NPM_CI, LOCAL_WRANGLER, TARGET_SYNC, LOCK_VERIFY):
            removed = removed.replace("run: " + command, "run: echo omitted runtime step")
        check(job + " named helper requires T-035 even when new steps are absent",
              bool(host_commands(removed, job, dry_run=(job == "build"))))


def test_runtime_actual_byte_commands_refuse_newline_only_drift():
    actual = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    commands = [command for step in workflow.steps(workflow.jobs(actual).get("build", [])) for command in step["run"]]
    if LOCK_BASELINE not in commands or LOCK_VERIFY not in commands:
        check("actual byte-check commands exist for executable newline control", False,
              "capture raw lock hashes before installation and compare before upload/after dry-run")
        return
    bash = shutil.which("bash")
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            bash = str(candidate)
    check("bash is available to execute the actual CI byte commands", bool(bash))
    if not bash:
        return
    with tempfile.TemporaryDirectory(prefix="vetagent-t035-byte-") as directory:
        root = Path(directory)
        files = ("uv.lock", "pylock.toml", "package-lock.json")
        for name in files:
            (root / name).write_bytes(b"fixture\n")
        for args in (("init", "--quiet"), ("config", "core.autocrlf", "true"), ("add", *files)):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
        env = dict(os.environ, RUNNER_TEMP=root.as_posix())
        def run(command):
            return subprocess.run([bash, "--noprofile", "--norc", "-c", command], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=15)
        baseline = run(commands[commands.index(LOCK_BASELINE)])
        check("actual raw hash baseline executes", baseline.returncode == 0, baseline.stderr)
        check("actual byte guard accepts unchanged lock bytes", run(LOCK_VERIFY).returncode == 0)
        for name in files:
            (root / name).write_bytes(b"fixture\r\n")
            normalized = subprocess.run(["git", "diff", "--exit-code"], cwd=root, capture_output=True)
            result = run(LOCK_VERIFY)
            check(name + " newline-only change is invisible to normalized git diff", normalized.returncode == 0)
            check(name + " newline-only change fails the actual byte guard", result.returncode != 0 and "FAILED" in result.stdout, result.stdout + result.stderr)
            (root / name).write_bytes(b"fixture\n")
        check("restored exact fixture bytes pass the byte guard", run(LOCK_VERIFY).returncode == 0)


# T-035 amendment (b): the existing offline gate precedes checksum capture.
def test_runtime_deploy_checksum_capture_follows_gate_before_install():
    text = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    commands = [command for step in workflow.steps(workflow.jobs(text).get("deploy", [])) for command in step["run"]]
    required = (OFFLINE, LOCK_BASELINE, INSTALL, NPM_CI, SYNC, TARGET_SYNC, DEPLOY)
    unique = all(commands.count(command) == 1 for command in required)
    ordered = unique and commands.index(OFFLINE) < commands.index(LOCK_BASELINE) < min(
        commands.index(command) for command in (INSTALL, NPM_CI, SYNC, TARGET_SYNC, DEPLOY))
    check("deploy captures raw lock bytes after the offline gate and before any dependency install or sync",
          ordered, "retain the old gate ordering and capture checksums before project dependency preparation")


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
