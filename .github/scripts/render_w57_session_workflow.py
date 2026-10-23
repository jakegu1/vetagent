"""Render the explicit finite W57 workflow; --check is read-only and guards drift.

LF and Windows CRLF checkouts are equivalent YAML. Rendering preserves the
existing checkout's line ending, without changing the exact runtime source pins.
No anchors, composites, provider calls, dispatches, or account changes are used.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ".github/workflows/rugcheck-w57.yml"
PINS = {"checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0",
        "upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2"}
COMMAND = "python bench/rugcheck_w57_session.py "


def expression(value):
    return "${{ " + value + " }}"


def upload(ident, condition, name, path, label=None):
    lines = ["      - " + ("name: " + label if label else "id: " + ident)]
    if label:
        lines.append("        id: " + ident)
    lines += ["        if: " + expression(condition),
              "        uses: actions/upload-artifact@" + PINS["upload-artifact"], "        with:",
              "          name: " + name, "          path: " + path,
              "          if-no-files-found: error", "          retention-days: 7"]
    return lines


def setup():
    # Capture the hosted-job clock before checkout/setup overhead. This executed
    # inline code belongs to the raw workflow hash in the composite source freeze.
    return ["    runs-on: ubuntu-24.04", "    timeout-minutes: 330", "    steps:",
            "      - name: Freeze the hosted job clock once",
            "        run: |",
            "          python3 -c 'import json,os,time; from pathlib import Path; Path(os.environ[\"RUNNER_TEMP\"],\"w57-job-clock.json\").write_text(json.dumps({\"utc\":time.time(),\"monotonic\":time.monotonic(),\"seconds\":19800}),encoding=\"utf-8\")'",
            "      - uses: actions/checkout@" + PINS["checkout"], "        with:", "          persist-credentials: false",
            "      - uses: actions/setup-python@" + PINS["setup-python"], "        with:", '          python-version: "3.12"',
            "      - name: Check generated control source without rewriting it",
            "        run: python .github/scripts/render_w57_session_workflow.py --check"]


def cycle(slot=None, canary=False, canary_slot=None):
    admission = slot is None
    key = "" if admission else "%03d" % slot
    p, i, c, r = ("prepare", "intent", "collect", "result") if admission else tuple(x + key for x in "picr")
    out = "$RUNNER_TEMP/w57-admission" if admission else "$RUNNER_TEMP/w57-" + key
    path = "${{ runner.temp }}/w57-admission" if admission else "${{ runner.temp }}/w57-" + key
    active = ("inputs.phase == 'pilot' || inputs.phase == 'start' || inputs.phase == 'report' || inputs.phase == 'legacy-report'"
              " || inputs.phase == 'pilot192' || inputs.phase == 'start192' || inputs.phase == 'report192'") if admission else (
                  "inputs.phase == 'start'" + (" || inputs.phase == 'start192'" if slot < 192 else ""))
    if canary:
        active += " || inputs.phase == 'canary'"
    command = "admit" if admission else "prepare --slot " + ('"$W57_SLOT"' if canary_slot is not None else str(slot))
    lines = ["      - name: " + ("Prepare explicit mode" if admission else "Wait for absolute slot " + key),
             "        id: " + p, "        if: " + expression(active)]
    if canary_slot is not None:
        lines += ["        env:", "          W57_SLOT: " + expression("inputs.phase == 'canary' && '%d' || '%d'" % (canary_slot, slot))]
    lines += ['        run: ' + COMMAND + command + ' --out "' + out + '"']
    ready = "steps." + p + ".outputs.ready == 'true'"
    collect = "steps." + p + ".outputs.action == 'collect'"
    if admission:
        lines += upload("admission", collect,
                        expression("(inputs.phase == 'pilot192' || inputs.phase == 'start192') && 'w57-admission-intent-v3' || 'w57-admission-intent-v2'"),
                        path + "/admission-intent")
    lines += upload(i, collect, expression("steps." + p + ".outputs.intent-name"), path + "/intent")
    condition = collect + " && steps." + i + ".outcome == 'success'"
    if admission:
        condition += " && steps.admission.outcome == 'success'"
    lines += ["      - id: " + c, "        if: " + expression(condition), "        continue-on-error: true", "        env:",
              "          W57_INTENT_ID: " + expression("steps." + i + ".outputs.artifact-id"),
              '        run: ' + COMMAND + 'collect --out "' + out + '"',
              "      - if: " + expression("always() && " + ready),
              '        run: ' + COMMAND + 'finalize --out "' + out + '"']
    lines += upload(r, "always() && " + ready, expression("steps." + p + ".outputs.result-name"), path + "/result",
                    "Preserve completed and partial observations" if admission else None)
    lines += ["      - if: " + expression("always() && " + ready), "        env:",
              "          W57_UPLOADED: " + expression("steps." + r + ".outcome"),
              "          W57_RESULT_ID: " + expression("steps." + r + ".outputs.artifact-id"),
              "          W57_RESULT_DIGEST: " + expression("steps." + r + ".outputs.artifact-digest"),
              '        run: ' + COMMAND + 'finish --out "' + out + '"']
    if admission:
        lines += upload("report", "always() && steps.prepare.outputs.report-ready == 'true'",
                        expression("format('w57-{0}-closure-r{1}-v{2}', inputs.phase == 'report192' && 'live192' || inputs.report-namespace, github.run_id, inputs.phase == 'report192' && '3' || '2')"),
                        path + "/report.json")
    return lines


def render():
    lines = ["# Generated by .github/scripts/render_w57_session_workflow.py; do not hand-edit.",
             "name: rugcheck-w57", "", "on:", "  workflow_dispatch:", "    inputs:", "      phase:",
             "        description: Explicit finite mode; canary never contacts a Vendor", "        type: choice",
             "        options: [canary, pilot, start, report, legacy-report, pilot192, start192, report192]", "        default: canary", "        required: true",
             "      study:", "        description: New ID for pilot/start; existing ID for report", "        type: string", "        required: false",
             "      pilot:", "        description: Successful earlier pilot result Artifact ID for start", "        type: string", "        required: false",
             "      source-run:", "        description: Existing v2 session run ID for read-only report", "        type: string", "        required: false",
             "      report-namespace:", "        description: Keep synthetic reports separate from live research", "        type: choice",
             "        options: [canary, live, live192]", "        default: canary", "", "permissions:", "  contents: read", "  actions: read", "",
             "concurrency:", "  group: rugcheck-w57-study", "  cancel-in-progress: false", "", "env:",
             "  W57_DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}", "  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
             "  PYTHONIOENCODING: utf-8", "  W57_PHASE: ${{ inputs.phase }}", "  W57_STUDY: ${{ inputs.study }}",
             "  W57_PILOT: ${{ inputs.pilot }}", "  W57_SOURCE_RUN: ${{ inputs.source-run }}",
             "  W57_REPORT_NAMESPACE: ${{ inputs.report-namespace }}", "", "jobs:"]
    for segment in range(10):
        job = "segment_%02d" % segment
        lines.append("  " + job + ":")
        if segment:
            lines.append("    needs: segment_%02d" % (segment - 1))
            enabled = "inputs.phase == 'start' || inputs.phase == 'start192'" + (" || inputs.phase == 'canary'" if segment == 1 else "")
            lines.append("    if: " + expression("success() && (" + enabled + ")"))
        lines += setup()
        if segment == 0:
            lines += cycle()
        # Canary spans two physical jobs: slots 0/1 in job zero, slot 2 in job one.
        for slot in range(segment * 20, min(193, (segment + 1) * 20)):
            canary = (segment == 0 and slot in (0, 1)) or (segment == 1 and slot == 20)
            lines += cycle(slot, canary=canary, canary_slot=2 if segment == 1 and slot == 20 else None)
        lines.append("")
    lines += ["  closure:", "    needs: [" + ", ".join("segment_%02d" % x for x in range(10)) + "]",
              "    if: " + expression("always() && inputs.phase != 'report' && inputs.phase != 'legacy-report' && inputs.phase != 'report192'")]
    lines += setup()
    out, path = "$RUNNER_TEMP/w57-closure", "${{ runner.temp }}/w57-closure"
    lines += ["      - id: close", '        run: ' + COMMAND + 'closure --out "' + out + '"']
    lines += upload("rescue", "always() && steps.close.outputs.rescue == 'true'",
                    expression("steps.close.outputs.result-name"), path + "/result")
    lines += ["      - id: index", "        if: " + expression("always() && steps.close.outputs.index-ready == 'true'"), "        env:",
              "          W57_UPLOADED: ${{ steps.rescue.outcome }}", "          W57_RESULT_ID: ${{ steps.rescue.outputs.artifact-id }}",
              "          W57_RESULT_DIGEST: ${{ steps.rescue.outputs.artifact-digest }}",
              '        run: ' + COMMAND + 'close-index --out "' + out + '"']
    lines += upload("admission", "always() && steps.index.outputs.ready == 'true'",
                    expression("(inputs.phase == 'pilot192' || inputs.phase == 'start192') && 'w57-admission-result-v3' || 'w57-admission-result-v2'"), path + "/admission-result")
    lines += upload("evidence", "always()", expression("format('w57-{0}-closure-r{1}-v{2}', inputs.phase == 'canary' && 'canary' || ((inputs.phase == 'pilot192' || inputs.phase == 'start192') && 'live192' || 'live'), github.run_id, (inputs.phase == 'pilot192' || inputs.phase == 'start192') && '3' || '2')"),
                    path)
    lines += ["      - if: " + expression("always()"), "        env:", "          W57_UPLOADED: ${{ steps.evidence.outcome }}",
              '        run: ' + COMMAND + 'closure-finish --out "' + out + '"', ""]
    newline = "\r\n" if TARGET.exists() and b"\r\n" in TARGET.read_bytes() else "\n"
    data = newline.join(lines).encode("utf-8")
    if len(data) >= 500000:
        raise ValueError("explicit workflow exceeds 500 KB")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    data = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_bytes().replace(b"\r\n", b"\n") != data.replace(b"\r\n", b"\n"):
            print("W57 generated workflow has drifted")
            return 1
        print("W57 generated workflow exact: %d bytes" % len(TARGET.read_bytes()))
        return 0
    TARGET.write_bytes(data)
    print("W57 workflow rendered: %d bytes" % len(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
