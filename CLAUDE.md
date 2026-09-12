# Working notes for Claude Code

Read `docs/AUDIT_BRIEF.md` for what this project is and where it stands. This file is
only the things that cost time when nobody wrote them down.

## Traps that have each bitten more than once

**Never pass text through the shell when it contains backslashes or backticks.** `<<'EOF'` mangles backslashes in
this environment, so `"\n"` arrives as a real newline and the file is left syntactically
broken *after* being written but *before* `ast.parse` catches it. This happened **eight**
times in one session.

The second mechanism is backticks. Inside a double-quoted `python -c "..."`, bash performs
command substitution, so a backlog row containing `` `count` `` and `` `scanned` `` was
written with those words replaced by nothing -- and the commit in the same command was
fine, because its heredoc was quoted `<<'MSG'`. Same command, two mechanisms, opposite
outcomes.

Use the **Write tool** for any text containing a backslash or a backtick, then run it.
A quoted heredoc `<<'EOF'` is safe for prose; nothing is safe for scripts with escapes.
If a file is already mangled, `git checkout <file>` and start over.

**Never curl production bare. Name yourself, or you become the evidence.**

Every hand-run probe against `vetagent.dev` is recorded by `_record_call`, and with no
`x-mcp-client` header it is filed under its User-Agent -- `curl`. The gate's own list has
`curl` in `AMBIGUOUS_CLIENTS`, so it is then judged by country, and **this machine egresses
through Tokyo**: `curl https://vetagent.dev/cdn-cgi/trace` returns `loc=JP`, `colo=NRT`.
`OWNER_COUNTRIES` is `{"CN"}`. So an untagged probe from here reads as a foreign caller.

On 2026-09-11 the gate reported **YES** on `curl` -- 14 calls, 4 days, low x12 unknown x2,
JP on 14 of 14 rows. Verifying W18 and W24 against production, and checking a deploy, is
exactly that shape: a handful of `tools/call` requests returning `low` and `unknown`,
spread over the days the work happened.

The global notes already carried this incident once -- "the usage gate says YES, we have an
external caller / the caller was a verification request I had sent myself an hour earlier".
It did not prevent the repeat, because it recorded the wrong half: the conclusion rather
than the mechanism. The mechanism is one missing header.

```bash
curl -sS -H 'x-mcp-client: vetagent-manual-probe' \
     -H 'content-type: application/json' \
     -X POST https://vetagent.dev/mcp -d '{...}'
```

`deploy.yml` learned this first and tags every smoke-test curl `vetagent-ci-smoke`; the
landing page sends `vetagent-landing-demo`. Hand-run probes were the only untagged thing
left, and they are the ones aimed at the endpoint most often. Anything `vetagent-*` is
filtered as ours.

Two more of ours that are not tagged and should be watched: `.mcp.json` points the owner's
editor at production, so `claude-code` is the owner -- it is in `AMBIGUOUS_CLIENTS` too, and
it is connect-only today, but one real `assess_token_risk` from the editor enters the gate's
evidence as a stranger. And a browser opened on the landing page without the demo button
arrives as `mozilla`.

**Clear `__pycache__` after restoring a file, or a mutation test lies to you.**

Restoring `src/risk.py` from a backup with `cp` and immediately re-running left Python
serving a **stale `.pyc`**: the file on disk read `_SCAN_RECALL_PCT = "50.0"` and the test
reported 62.5, on 2026-09-12. Harmless when it makes a green run look red. Dangerous in the
other direction, which is the direction this repo's whole discipline runs in -- break the
thing, watch the guard go red, restore. A stale cache turns "I watched it fail" into a
sentence about a file that was not loaded.

```bash
find . -name __pycache__ -type d -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null
```

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

**Check every workflow, not the one you were thinking about.** There are four —
`deploy.yml`, `test.yml`, `snapshot.yml`, `usage.yml` — and only `deploy.yml` gates the
deploy. On 2026-09-09 `test.yml` was red for **eight consecutive commits** while every
report said the build was green, because each check ran
`gh run list --workflow=deploy.yml` and stopped there. The owner found it in his email.

```bash
gh run list --limit 12 --json workflowName,conclusion,headSha \
  -q '.[]|.conclusion+"  "+.workflowName+"  "+.headSha[0:7]' | sort -u
```

Same failure shape as reading one page of a directory and reporting the listing absent:
*checked one place, found green, reported green.*

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
