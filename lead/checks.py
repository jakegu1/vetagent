"""checks.py -- the lead workflow's command for the offline suite.

Usage:  python lead/checks.py          (from the repository root)

It runs `.github/scripts/offline_suite.py` in this process, so what it prints and the status
it exits with are the runner's: every step of test.yml's offline `test` job, one line each;
exit 0 only if every step passed and the run modified no tracked file, 2 when no steps are
found.

The runner lived here until 2026-09-29. It moved when deploy.yml began running it before every
deploy, because the product's deploy must not depend on `lead/`, the lead workflow's folder,
which is meant to be removable (ADR-0001). Its docstring carries this file's history: why
every step runs even after a red one, and why a run that modifies a tracked file fails. This
file stays because `lead/config.yml` and the lead kit call the suite by this name.
"""

import os
import runpy
import sys

RUNNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      ".github", "scripts", "offline_suite.py")

if __name__ == "__main__":
    if not os.path.isfile(RUNNER):
        sys.exit("no runner at .github/scripts/offline_suite.py -- refusing to report a pass")
    runpy.run_path(RUNNER, run_name="__main__")
