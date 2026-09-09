# Working notes for Claude Code

Read `docs/AUDIT_BRIEF.md` for what this project is and where it stands. This file is
only the things that cost time when nobody wrote them down.

## Traps that have each bitten more than once

**Never write a Python script through a bash heredoc.** `<<'EOF'` mangles backslashes in
this environment, so `"\n"` arrives as a real newline and the file is left syntactically
broken *after* being written but *before* `ast.parse` catches it. This happened five
times in one session. Use the **Write tool** for any script containing escapes, then run
it. If a file is already mangled, `git checkout <file>` and start over.

**Deploy from WSL, and clear the venv first.** `.venv-workers` is platform-specific:
built on Windows it has `Scripts/`, and a WSL run wants `bin/`.

```bash
rm -rf .venv-workers python_modules   # only if switching platforms
wsl -d Ubuntu -- bash -lc 'cd /mnt/d/Work/test/vetagent && \
  XDG_CONFIG_HOME=/mnt/c/Users/86277/AppData/Roaming/xdg.config uv run pywrangler deploy'
```

**`/tmp` is not shared.** Git Bash's `/tmp` is invisible to Windows Python. Use the
session scratchpad directory for anything both need to see.

**Windows console is GBK.** Prefix anything that prints non-ASCII with
`PYTHONIOENCODING=utf-8`, or it dies with `UnicodeEncodeError` — sometimes *before*
writing its output file.

**`git pull --rebase` rewrites commit SHAs**, which breaks the commit pinned in
`tools/rounds.py`. `test_rounds.py` catches it; repin and regenerate.

**Never let a workflow's agent count depend on model output.** On 2026-09-07 a review
workflow spawned **233 agents**, spent 5.2M output tokens, exhausted the account's session
limit and killed 190 of its own agents — including the synthesizer, whose memo was the
only thing wanted. 43 finished. About 80% of the spend bought nothing, and the account was
unusable for hours.

One line caused it: three verifiers per finding, where `findings` was whatever the models
returned. The schema had no `maxItems`, so seven finders returned 75 findings and the
verify stage became 225 agents. **The count has to be a constant known before the run.**

Use `.claude/workflows/budgeted-review.js` rather than writing a fresh fan-out. It encodes
the six rules that failure taught:

1. **Cap findings at the schema** (`maxItems`) — N finders → at most N×K findings.
2. **Dedup and rank in plain code** before spending. Triage costs zero tokens.
3. **Scale verifiers by severity** (3/2/1/0), not uniformly. A `low` cosmetic note got the
   same three adversarial refuters as a critical data-loss finding.
4. **Reserve budget for synthesis and check it.** The output that matters must not be last
   in a queue that may not reach it. Build a plain-code fallback memo so a result exists
   either way.
5. **Tier effort.** `opts.effort: 'low'` for verifiers checking whether a line number is
   real.
6. **Never cap silently.** `log()` what was dropped, and report an unjudged finding as
   *unverified* — not as absent, and not as confirmed.

Same seven dimensions under those caps: under 40 agents instead of 233. The twelve
findings that survived verification came entirely from the top slice the caps keep.

## The order that matters

After any change touching the engine or the benchmark:

```bash
python bench/run_benchmark.py          # ~10-20 min, refetches on any URL change
python bench/publish_numbers.py --write
python bench/scorecard.py --write
for f in tests/test_*.py; do python "$f"; done   # ~56s
```

Then commit, then deploy. Publishing before re-measuring puts a stale number on a live
page, and `test_published_numbers.py` will fail the build for it.

**Never run two benchmarks at once.** They share `bench/cache/` and race.

## How work is done here

**One finding, one commit, and a test that is red before the fix.** Not a convention —
several defects exist *because* that rule was skipped, and the commit message is expected
to say what the red looked like.

**Measure before concluding, and after.** A single confirming case is not a result: a
one-token fix for the honeypot pair parameter looked right on XAUt and turned out to be a
six-point regression on the full set. Both directions of a change get measured.

**A guard nobody has watched fail is not a guard.** Break the thing deliberately, watch
the test go red, restore. Four hand-maintained test runners in this repo were silently
skipping tests before anyone checked.

**Discoveries get parked, not chased.** `docs/OPPORTUNITIES.md`, with a gate. But park
with the *experiment* that settles it, and run that experiment — an unrun parked
experiment is indistinguishable from a forgotten one, and one of them hid a P0 for half
a day.

## Things that are deliberate — do not "fix" them

- **GoPlus is not an upstream.** It is the benchmark's held-out oracle (DECISIONS B2) and
  `tests/test_risk.py` fails the build if the string appears in `src/`.
- **No addresses, no identities, no tokens are logged.** This is why the usage gate
  cannot identify callers, and that trade stands.
- **`unknown` verdicts are the product working**, not a bug. Fail-closed: a critical
  check that could not run must never read as low risk.

## Current state

Started 2026-09-03. Rounds and commit counts live in `docs/ROUNDS.md`, which is where
they stay current; copying them here is how they went two rounds stale before anyone
looked. Score 55/100 by `docs/SCORECARD.md`, whose
ceiling for pure engineering is about 70 — the rest needs users, who do not exist yet.
The live question is the 2026-09-18 gate in `docs/STRATEGY.md` §8.
