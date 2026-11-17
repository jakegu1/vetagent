# Development and verification

Use a full Git checkout: offline historical-fixture checks verify immutable objects
from earlier commits. A shallow checkout without those objects is not sufficient.
The public checks do not require maintainer documents or local editor configuration.

```sh
python lead/checks.py
```

This compatible entry point runs every configured offline step from the test workflow
through `.github/scripts/offline_suite.py`. Missing or unreachable test registrations
fail the checks. Deployment runs the same complete offline gate before upload.

When measured inputs or test counts change, regenerate the public derived pages:

```sh
bash .github/scripts/regenerate-derived.sh regenerate
```

Use only `regenerate` locally. Other modes belong to the scheduled bots and refuse to
run outside GitHub Actions. Regeneration does not collect new data. Data collection,
benchmarks and live probes are separate operations; offline verification is the default.

## Engineering invariants

- A critical check that could not run yields `unknown`, never reassurance.
- Logs and telemetry contain no token addresses, identities or individual queries.
- The benchmark's held-out oracle must not become an engine upstream.
- Published figures come from preserved measurements and retain effective guards.
- Keep existing research rules, thresholds, source identities and historical evidence.
- Commit a regression test before its fix and observe its failure. Preserve failed
  observations; distinguish an absent result from an unperformed check.
- Test interface handoffs as well as individual components. Changes to risk evidence
  require independent review, including counterexamples.
- Keep source, tests and public documentation in English. Preserve upstream data bytes.
- Do not rebase or amend published history: reproducibility relies on fixed commits.
- Never record secrets in code, commits or output. Keep local agent and management
  configuration outside tracked public content.

Manual production checks must carry an `x-mcp-client` value beginning with `vetagent-`
so they cannot be counted as external usage. `tools/no_untagged_probe.py` contains the
tested generic guard; installing it into an editor is a local configuration choice.

See [technical decisions](docs/DECISIONS.md) for rule-specific evidence and tests,
and [integration guidance](docs/AGENT-INTEGRATION.md) for the public tool contract.
Historical management files remain in Git history; removing their current paths is
not a claim that previously published copies have been erased.
