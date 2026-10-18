"""T-036: actual workflows pin supported action implementations and runner images.

This policy owns only workflow coverage, action identities/pins/release comments
and explicit per-job Ubuntu labels. Other guards own commands and release order.
Run: python tests/test_workflow_runtime_pins.py
"""
from pathlib import Path
import re
import sys
import tempfile

import test_deploy_gate as workflow

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {"deploy.yml", "production.yml", "snapshot.yml", "test.yml", "usage.yml", "zone-check.yml"}
ACTION_PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-python": ("5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0"),
    "actions/setup-node": ("949feb2413d6458794dcd2491c4babbbce0c15c1", "v7.1.0"),
    "actions/upload-artifact": ("cf430e030ddbb5b0abf93d22962f4752f3646cd9", "v7.0.2"),
}
ACTION_REF = re.compile(r"^(actions/[A-Za-z0-9_-]+)@([0-9a-f]{40})\s+#\s*(v[0-9]+\.[0-9]+\.[0-9]+)$")
PASSED, FAILURES, EXECUTED = 0, [], []


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
        print("  PASS " + name)
    else:
        FAILURES.append((name, str(detail)))
        print("  FAIL %s: %s" % (name, detail))


def workflow_texts(directory):
    # iterdir includes dotfiles; a glob that hides them would miss an added workflow.
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(directory.iterdir())
            if path.is_file() and path.suffix in (".yml", ".yaml")}


def workflow_errors(name, text):
    errors, inside = [], False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            inside = line == "jobs:"
        elif inside and len(line) - len(line.lstrip(" ")) == 2:
            if not re.fullmatch(r"  [A-Za-z0-9_-]+:\s*(?:#.*)?", line):
                errors.append(name + ": job declaration cannot be enumerated")
    jobs = workflow.jobs(text)
    if not jobs:
        errors.append(name + ": jobs must be present and enumerable")
    for job, lines in jobs.items():
        label = name + "/" + job
        runners = [match.group(1).strip() for line in lines
                   if (match := re.fullmatch(r"    runs-on:\s*(.*?)\s*", line))]
        if runners != ["ubuntu-24.04"]:
            errors.append(label + ": runner must be exactly one explicit ubuntu-24.04")
        outside = []
        parsed = workflow.steps(lines, outside)
        if outside:
            errors.append(label + ": action coverage cannot ignore lines outside parsed steps")
        # Retain each parsed step's source context only to account for literal
        # action-input payloads, which the offline reader flags as non-key lines.
        raw_steps = []
        at = next((i for i, line in enumerate(lines) if re.fullmatch(r"\s*steps:\s*", line)), None)
        dash = None
        if at is not None:
            for line in lines[at + 1:]:
                indent = workflow._indent(line)
                if indent <= workflow._indent(lines[at]):
                    break
                marker = re.match(r"^( *)- (.*)$", line)
                if marker and (dash is None or indent == dash):
                    dash = indent
                    raw_steps.append([" " * (indent + 2) + marker.group(2)])
                elif raw_steps:
                    raw_steps[-1].append(line)
        if len(raw_steps) != len(parsed):
            errors.append(label + ": action coverage lacks complete step source context")
        for index, step in enumerate(parsed):
            reference = step["keys"].get("uses")
            # The reader recognizes these non-action fields but does not execute
            # them locally. Node/upload actions are likewise recognized here.
            accounted = {"uses: " + reference} if reference is not None else set()
            for key in workflow.NOT_APPLIED:
                if key in step["keys"]:
                    value = step["keys"][key]
                    accounted.add(key + ":" + (" " + value if value else ""))
            within, scalar = None, None
            for line in raw_steps[index] if index < len(raw_steps) else []:
                indent = workflow._indent(line)
                if scalar is not None and indent > scalar:
                    accounted.add(line.strip())
                    continue
                scalar = None
                if within is not None and indent <= within:
                    within = None
                literal = re.fullmatch(r"\s*([A-Za-z0-9_-]+):\s*([|>][0-9+-]*)\s*", line)
                if within is not None and literal and step["with"].get(literal.group(1)) == literal.group(2):
                    scalar = indent
                if re.fullmatch(r"\s*with:\s*", line):
                    within = indent
            if any(line not in accounted for line in step["refused"]):
                errors.append(label + ": action coverage cannot ignore refused step syntax")
            if reference is None:
                continue
            match = ACTION_REF.fullmatch(reference)
            if (not match or ACTION_PINS.get(match.group(1)) != (match.group(2), match.group(3))):
                errors.append(label + ": action must use a supported identity, exact SHA and release comment")
    return errors


def policy_errors(documents):
    errors = []
    if set(documents) != WORKFLOWS:
        errors.append("workflow set must be exactly the six covered YAML files")
    for name, text in documents.items():
        errors.extend(workflow_errors(name, text))
    return errors


def valid_workflow():
    lines = ["name: synthetic runtime pins", "on: push", "jobs:", "  test:",
             "    runs-on: ubuntu-24.04", "    continue-on-error: true", "    steps:"]
    for action, (sha, release) in ACTION_PINS.items():
        lines.append("      - uses: " + action + "@" + sha + " # " + release)
    lines.extend(["  optional:", "    runs-on: ubuntu-24.04", "    steps:",
                  "      - name: An optional control", "        run: echo optional", ""])
    return "\n".join(lines)


def valid_documents():
    return {name: valid_workflow() for name in WORKFLOWS}


def test_actual_workflow_set_is_covered():
    documents = workflow_texts(ROOT / ".github/workflows")
    check("every actual YAML workflow is explicitly covered", set(documents) == WORKFLOWS,
          "missing=%s extra=%s" % (sorted(WORKFLOWS - set(documents)), sorted(set(documents) - WORKFLOWS)))


def test_actual_actions_and_every_job_are_pinned():
    for name, text in workflow_texts(ROOT / ".github/workflows").items():
        errors = workflow_errors(name, text)
        action_errors = [error for error in errors if ": action " in error]
        job_errors = [error for error in errors if ": action " not in error]
        check(name + " uses the verified full action SHAs and release comments", not action_errors,
              "; ".join(action_errors))
        check(name + " pins every job including optional jobs", not job_errors, "; ".join(job_errors))


def test_known_valid_action_and_runner_forms_pass():
    check("the synthetic six-workflow control passes", not policy_errors(valid_documents()))
    spaced = valid_workflow().replace(" # v", "  #  v")
    check("release comment spacing does not change the pin", not workflow_errors("control.yml", spaced))


def test_old_floating_wrong_or_unidentified_actions_are_refused():
    source = valid_workflow()
    checkout_sha = ACTION_PINS["actions/checkout"][0]
    controls = (
        ("old major", checkout_sha, "v4"),
        ("moving supported major", checkout_sha, "v7"),
        ("moving latest", checkout_sha, "latest"),
        ("wrong full SHA", checkout_sha, "0" * 40),
        ("wrong release comment", "# v7.0.1", "# v7.0.0"),
        ("missing release comment", " # v7.0.1", ""),
        ("unsupported action identity", "actions/checkout@", "actions/cache@"),
        ("continued reference", "# v7.0.1", "# v7.0.1\n          unexpected continuation"),
    )
    for label, old, new in controls:
        assert source.count(old) == 1, label
        errors = workflow_errors("control.yml", source.replace(old, new, 1))
        check(label + " is refused", any(": action " in error for error in errors), errors)


def test_missing_or_floating_job_runner_is_refused():
    source = valid_workflow()
    for label, replacement in (("ubuntu-latest", "ubuntu-latest"), ("other Ubuntu generation", "ubuntu-26.04"),
                               ("indirect runner", "${{ matrix.os }}")):
        errors = workflow_errors("control.yml", source.replace("runs-on: ubuntu-24.04", "runs-on: " + replacement, 1))
        check(label + " is refused", any(": runner " in error for error in errors), errors)
    optional = "  optional:\n    runs-on: ubuntu-24.04\n"
    assert source.count(optional) == 1
    missing = source.replace(optional, "  optional:\n", 1)
    check("a later optional job missing its runner is refused",
          any("/optional: runner " in error for error in workflow_errors("control.yml", missing)))
    duplicate = source.replace("    runs-on: ubuntu-24.04", "    runs-on: ubuntu-24.04\n    runs-on: ubuntu-24.04", 1)
    check("duplicate job runner fields are refused", bool(workflow_errors("control.yml", duplicate)))
    anchored = source.replace("  optional:", "  optional: &job", 1)
    check("an unenumerated job declaration is refused", bool(workflow_errors("control.yml", anchored)))


def test_extra_or_missing_workflow_documents_are_refused():
    documents = valid_documents()
    documents.pop("zone-check.yml")
    check("a missing covered workflow is refused", any("workflow set" in error for error in policy_errors(documents)))
    for extra in ("extra.yml", ".extra.yml", ".extra.yaml"):
        documents = valid_documents()
        documents[extra] = valid_workflow()
        check(extra + " is refused", any("workflow set" in error for error in policy_errors(documents)))


def test_hidden_yaml_files_are_in_the_actual_enumeration():
    with tempfile.TemporaryDirectory(prefix="workflow-runtime-pins-") as directory:
        folder = Path(directory)
        for name, text in valid_documents().items():
            (folder / name).write_text(text, encoding="utf-8")
        check("real directory enumeration accepts the covered set", not policy_errors(workflow_texts(folder)))
        for extra in (".extra.yml", ".extra.yaml"):
            path = folder / extra
            path.write_text(valid_workflow(), encoding="utf-8")
            errors = policy_errors(workflow_texts(folder))
            check(extra + " is enumerated and refused", any("workflow set" in error for error in errors), errors)
            path.unlink()


def test_unrelated_steps_and_soft_fail_changes_do_not_freeze_workflows():
    source = valid_workflow()
    added = source + "      - name: A future offline check\n        run: python tests/example_future.py\n"
    added += "      - name: Script text is not an action\n        run: |\n          echo 'uses: actions/checkout@v4'\n"
    changed = added.replace("    continue-on-error: true\n", "", 1)
    check("two new steps and a removed soft-fail remain outside pin policy",
          not workflow_errors("control.yml", changed), workflow_errors("control.yml", changed))


def test_refused_and_outside_steps_cannot_hide_action_references():
    source = valid_workflow()
    action = "      - uses: actions/checkout@" + ACTION_PINS["actions/checkout"][0] + " # v7.0.1"
    assert source.count(action) == 1
    controls = (
        ("single-quoted key", "      - 'uses': actions/checkout@v4"),
        ("double-quoted key", '      - "uses": actions/checkout@v4'),
        ("flow-map step", "      - {uses: actions/checkout@v4}"),
        ("unclosed quoted key", "      - 'uses: actions/checkout@v4"),
        ("indentless step list", "    - uses: actions/checkout@v4"),
    )
    for label, replacement in controls:
        text = source.replace(action, replacement, 1)
        outside = []
        parsed = workflow.steps(workflow.jobs(text)["test"], outside)
        refused = [line for step in parsed for line in step["refused"]]
        check(label + " is observed in the existing reader's refusal ledger", bool(refused or outside))
        errors = workflow_errors("control.yml", text)
        check(label + " cannot be accepted as a run-only step", bool(errors), errors)


def test_observer_prefix_refresh_preserves_the_actual_exact_guard():
    import ast
    import contextlib
    import io
    import os

    path = ROOT / "tests/test_sellability_archive.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    name = "test_snapshot_freshness_workflow_runs_last_always_and_cannot_swallow_failure"
    actual = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    approved = (ROOT / ".github/workflows/production.yml").read_text(encoding="utf-8")
    prefix_label = "all pre-existing observer bytes retain their original commands and order"
    with tempfile.TemporaryDirectory(prefix="observer-prefix-pins-") as directory:
        folder = Path(directory)
        workflow_path = folder / ".github/workflows/production.yml"
        workflow_path.parent.mkdir(parents=True)

        def invoke(text):
            workflow_path.write_text(text, encoding="utf-8")
            readings = []
            namespace = {"io": io, "os": os, "ROOT": str(folder),
                         "check": lambda label, condition, detail="": readings.append((label, condition))}
            # Execute the actual unchanged function body, with only fixture IO and its
            # check sink supplied. Importing or running the archive suite is unnecessary.
            exec(compile(ast.Module(body=[actual], type_ignores=[]), str(path), "exec"), namespace)
            with contextlib.redirect_stdout(io.StringIO()):
                namespace[name]()
            return readings

        readings = invoke(approved)
        check("the actual old function accepts the exact approved observer workflow",
              bool(readings) and all(condition for _, condition in readings), readings)
        command = "python bench/production_probe.py --write"
        assert approved.count(command) == 1
        changed = approved.replace(command, "python bench/production_probe.py", 1)
        readings = invoke(changed)
        check("the actual observer prefix guard still refuses unauthorized command bytes",
              any(label == prefix_label and not condition for label, condition in readings), readings)
        commit = approved.index("      - name: Commit\n")
        regenerate = approved.index("      - name: Regenerate the pages that quote it\n")
        health = approved.index("      - name: Check snapshot freshness and coverage\n")
        assert commit < regenerate < health
        reordered = approved[:commit] + approved[regenerate:health] + approved[commit:regenerate] + approved[health:]
        readings = invoke(reordered)
        check("the actual observer guard still refuses changed commit/generation order",
              any(label == prefix_label and not condition for label, condition in readings)
              and any(label == "health runs after both observation commit and fixed-point generation" and not condition
                      for label, condition in readings), readings)


def main():
    for name, function in sorted((name, value) for name, value in globals().items() if name.startswith("test_")):
        EXECUTED.append(name)
        try:
            function()
        except Exception as exc:  # noqa: BLE001 -- finish every test and fail visibly
            check(name + " completes", False, "%s: %s" % (type(exc).__name__, exc))
    print("Executed: " + ", ".join(EXECUTED))
    print("%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
