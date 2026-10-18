---
id: T-037
title: Keep release safeguards and reproduction instructions truthful
status: ready
level: 3
size: M
depends_on: [T-032, T-034]
decisions: [D2]
backlog: T-004 round-two follow-up and engineering inventory
---

## Context and goal

Repair five reproduced release/reporting failures in one serial eight-file task, with
one independent source commit per finding. The shared guards and publishing seams
justify grouping; existing registered runners cover the whole task. No experiment
date, scoring rule, published measurement, upstream selection or permission changes.

## Pinned evidence and limits

Preparation reads frozen Git blobs at 365409ee8a27bdc63e4d4211b77f5e41ba052e0c.
Reconcile all eight files with the actual dispatch base before implementing; preserve
any newer work. Preparation source and synthetic fixtures are not an implementation.

The two actual interpreters were CPython 3.12.14 and 3.13.4. Final receipts agree:

| Finding | Actual failing behavior at the pinned parent | Smallest demonstrated direction |
|---|---|---|
| Node properties precede an unclosed YAML value | Twelve synthetic workflows execute only the first of two Python marker commands and exit 0. Six also give zero independent-reader refusals; the other six are already refused independently. Both readers' _closed accept the unsupported leading properties. | Refuse leading anchor/tag properties in each independent _closed, rather than implement more YAML. Keep quoted literal punctuation accepted. |
| Failed observations compare equal | Six synthetic failed before/after readings pass the existing bot non-mutation canaries and produce empty change diagnostics. | Add a readable-observations assertion and return on its failure, before reaching each existing equality assertion. |
| Generator diagnostics disappear | Failure at each of the four generator positions produces exit 1, a generic stdout error and visible stderr, but loses the generator's useful stdout. | Capture stdout, print it only when the generator fails, keep stderr visible, and preserve the existing caller's status/order. |
| Malformed owner-power measurement | Invalid JSON raises JSONDecodeError in the reader and both main modes. Six valid-JSON consumed-container variants, including a top-level array, raise AttributeError. | Treat unavailable/unusable artifact input as the existing empty-measurement result, allowing existing per-target not-measured diagnostics and nonzero main status to run. |
| Reproduction recipe drift | README's default code block invokes live dataset building/plain benchmark mode. Experiment C retains September instructions, without a current replay/fixed-clock recipe. A proposed additive documentation guard is red on both current documents. | README gets current replay guidance; Experiment C keeps its historical prose/quoted post, labels them historical outside the quoted text, and appends current guidance. |

The YAML finding is fail-closed hardening of a deliberately limited parser. The historical
review reported a YAML 1.2 rejection; no live GitHub Actions acceptance or deployment exploit
was established. The two synthetic tail classes are retained separately in the receipts:
"hidden: # continued" fools both readers, while "hidden: continued" is already refused by the
independent reader. Do not collapse those observations.

No network, real benchmark, cache access, production probe, real generator, repository write,
private Git repository, staging or commit occurred in this preparation. The YAML main seam
used real isolated Python marker children with only unrelated git-status transport replaced by
a healthy empty result. The regeneration seam used shell functions for every git/python call
and the real script's local regenerate mode with GITHUB_ACTIONS unset. Whole old suites were
not run here; baseline AST/source preservation is not a claim of full-suite green.

## Exact scope

| File | Named change |
|---|---|
| .github/scripts/offline_suite.py | _closed only: reject unsupported leading YAML node properties. No job-boundary redesign or general YAML parser. |
| tests/test_deploy_gate.py | Independent _closed repair; additive test_node_properties_are_refused_at_their_origin and its explicit main call. Existing fixtures/assertions remain. |
| tests/test_bot_commits_stay_green.py | New pure reading-validity helper; additive guard statements in test_this_repository_was_not_reached and test_snapshot_commit_did_not_reach_this_repository; additive observation/diagnostic tests and explicit main calls. Existing equality assertions remain literally unchanged. |
| .github/scripts/regenerate-derived.sh | Preserve failed-generator stdout without changing success output, stderr, status, generator discovery, order, fixed-point loop or CI-only bot refusal. |
| bench/publish_numbers.py | _owner_power_figures unavailable-input handling and validation of containers the existing reader consumes. |
| tests/test_published_numbers.py | Add recorded check_owner_power_artifact_unavailability_is_reported and check_benchmark_reproduction_guidance_is_current. Existing main discovers check_ functions; no new main registration. |
| README.md | Replace only the technical reproduction recipe and adjacent mode explanation. No benchmark numbers or product claims. |
| docs/EXPERIMENT_C.md | Add historical labels outside old prose/quotes and append one current technical reproduction section. Preserve existing historical paragraph and whole quoted post exactly. |

Read-only dependencies: bench/run_benchmark.py, bench/fetcher.py,
tests/test_benchmark_replay.py, lead/tasks/T-011-freeze-benchmark-replay.md, test/deploy
workflows, .github/scripts/snapshot-commit.sh and existing publishing targets. No changes to
these files. No new workflow file or step is needed: test.yml already invokes
test_published_numbers.py at line 69, test_bot_commits_stay_green.py at line 215 and
test_deploy_gate.py at line 245 at this pin.

## Acceptance criteria (eight)

1. **Refuse the originating node-property line.** Both independent readers refuse anchored,
   tagged, combined-property and property-prefixed quote/flow values at step keys and nested
   with entries. Include both tail classes measured above; require the offending origin line
   to be named even where a continuation is already refused. Refusal of all unsupported
   leading ampersand/exclamation properties, including closed forms, is acceptable. Quoted
   literal ampersands/exclamation marks and ordinary interior punctuation retain behavior.
   The actual workflow retains its complete dispatch-base command list with no refusals
   (thirty-six commands at preparation, before subsequent registrations); all thirteen
   existing REFUSED fixtures remain unchanged and refused.

2. **Observation failures cannot pass the non-mutation canaries.** At both named canaries,
   before and after readings must be usable before the old equality assertion is reached.
   Cover equal OSError/TimeoutExpired sentinels, equal failed HEAD/config/status statuses,
   one-sided failures and genuine changed observations. A config exit 1 with empty output
   is legitimate absence of user configuration; HEAD/status require exit 0. Keep valid
   unchanged and absent-config positives. Failed reads produce a failure and no equality
   PASS; no raw identity values, stdout/stderr or secrets appear in diagnostics. Keep the
   existing no-bash/no-calls NOT RUN behavior and CI rule.

3. **Report the failed generator's actual stdout.** A synthetic failure at each of scorecard,
   publish_numbers, owner and rounds surfaces distinct stdout/stderr diagnostics once, still
   returns 1 and runs no later generator. Successful stdout remains quiet and successful
   stderr remains visible, as before. Preserve the literal "python path --write" spellings
   used by the existing generator-discovery regex. Capture command output as data. Preserve
   three-pass fixed-point order, data-before-derived ordering, and all existing refusal and
   retry contracts. The added test exercises only local regenerate mode in isolated stubs;
   it must not set GITHUB_ACTIONS to bypass the real repository guard.

4. **An unavailable owner-power artifact remains visibly unmeasured.** Missing input,
   simulated read/race OSError, invalid JSON syntax and invalid consumed containers return
   no measured owner-power keys. The bounded malformed grid is: top-level array, nonempty
   powers array, nonmapping power row, nonempty pooled array, nonempty out_of_sample array
   and nonmapping selected out_of_sample row. Preserve valid producer mappings, null/empty
   containers, previously tolerated falsey containers, unknown oracle flags and None values.
   Existing scan(write=False/True) and both main modes finish with truthful not-measured
   entries naming the artifact/key and nonzero status, without a traceback or invented zero.
   With --write, owner-power target values remain unchanged; unrelated genuinely fixable
   targets may still be rewritten according to the existing policy. This is not a new
   complete numeric schema or percentage-validation policy.

5. **Current documentation matches current modes without rewriting history.** One additive
   check_benchmark_reproduction_guidance_is_current reads source/docs only; it never imports
   or runs the benchmark. Scope it to explicit current-reproduction blocks so historical
   commands remain valid history. Require --replay as the default code-block command, the
   BENCH_CLOCK value read from source (currently 2026-09-21T02:00:00Z), no-network replay,
   nonzero miss refusal/list and unchanged results on misses, and the fact that complete
   replay can write results. State that the cache is not tracked/published, a fresh clone
   does not guarantee published figures, plain mode can fetch/write dated cache, and
   --fill FILE is an intentional reviewed HTTPS-list operation followed by a separate replay.
   Do not present a pinned logical clock as historical upstream state. Preserve September
   prose and the whole quoted post; add historical labels outside it and append current
   instructions. No cache upload, fill, cold run, sampling, rebaseline or new numbers.

6. **Freeze the old contract.** Preserve every old fixture assignment and old assertion in
   the three scoped test files. Preserve complete old test/check function ASTs except the
   two canaries, whose existing statements/assertions must remain in the same order with
   only the explicit readability assertion/early-return additions. Their old equality
   conditions do not change. Main functions may add named calls while preserving all old
   statements in order. _closed is implementation code in test_deploy_gate, not an immutable
   acceptance function. Use actual Python 3.12 and 3.13, comparing same-interpreter ASTs;
   do not spoof a version or assume cross-version dumps are identical.

7. **Tests first and five independent source commits.** First commit only the additive
   acceptance tests and their named registration, each meaningful new case red on the
   parent. Then five source commits, one finding each: YAML, failed-read canaries,
   regeneration diagnostics, unavailable owner-power input, current documentation.
   Frozen tests do not change after their first commit. The two canary guard insertions
   are the explicitly named implementation changes, not acceptance-test relaxation.
   Reverting each fix independently must make its own new acceptance fail; documentation
   mutants removing replay, changing the clock or removing cache/network disclosure must
   also fail. No generic parser/runner or fixture refactor.

8. **Configured gates and review complete the task.** Run the actual existing registered
   test runners, decision-enforcement/reachability checks and configured full offline gates,
   then fresh independent and red-team review. Include unchanged T011 replay tests as
   synthetic controls, without a real dataset/cache run. Give evidence for all eight criteria
   and source/fixture preservation under both real runtimes. Restore any temporary bytes
   exactly and demonstrate no published result, dataset, archive or cache changed. Generated
   output changes, if unexpectedly required by gates, go back to the lead as an explicit
   scope decision; do not hide them among these eight files.

## Frozen old tests and conflict search

The final runtime receipts contain hashes for 45 old test/check functions and 85 old
uppercase fixture assignments across the three test files. Each runtime independently
detects a controlled mutation of an old assertion in each file (three caught mutants).
The supplement proves the canary candidate preserves every old statement in order and
every old assertion, changing no other existing function AST. Invalid reads become one
FAIL/zero PASS; both legitimate positive types reach the two assertions and pass.

- test_deploy_gate: all five old test functions remain unchanged, especially
  test_the_runner_fails_closed, test_the_deploy_is_gated and the thirteen REFUSED entries.
  Add a new test and main call; do not append to or weaken the existing REFUSED table.
- test_bot_commits_stay_green: retain OFF_ACTIONS, DECOYS, REFUSAL,
  SNAPSHOT_OFF_ACTIONS, SNAPSHOT_CALLS and every old check. Keep
  test_the_shared_script_runs_every_generator_a_bot_can_stale, both off-Actions refusal
  tests, test_the_local_modes_are_unchanged and both could-not-run tests unchanged.
  Add test_repository_canaries_refuse_failed_observations and
  test_failed_regeneration_preserves_generator_diagnostics, with explicit main calls.
  New captured-canary tests must restore collectors and patched readers in finally.
- test_published_numbers: retain all old recorded checks, especially
  check_any_missing_key_is_reported, check_check_mode_names_what_is_not_measured,
  check_write_fails_with_no_production_artifact and the report/advice/exit-status checks.
  Use in_a_copy and run_main for real publishing seams; never mutate actual docs/artifacts.
  The new documentation check uses this runner's existing check_ auto-discovery.
- T011 controls to run unchanged:
  test_ac2_summary_counts_future_pairs_and_restores_clock,
  test_ac4_replay_roundtrip_and_complete_miss_refusal,
  test_ac5_fill_is_allowlisted_deduplicated_and_dated and
  test_ac5_replay_url_lines_fill_then_replay_without_misses, through their actual runner.
  The T011 spec explicitly left public instructions unchanged, explaining this residual.

## Execution order and threat model

Land serially after reconciling the current integration base. The YAML and canary fixes
both touch existing files that later fixes test, and stdout diagnostics share the bot
test file with the canary fix. The two publishing changes share test_published_numbers.
Keeping these five findings in one bounded task avoids concurrent edits while retaining
one finding per source commit. Source commit 5 must not rewrite the historical post.

The threats are a partial suite falsely reported green, blindness falsely reported as
non-mutation, a failed release generator withholding its remedy, an unavailable measurement
stopping the remaining guard/report, and instructions accidentally turning reproduction
into live remeasurement. This proposal does not change Experiment D's date/bar, classify
new users, authorize outreach, buy RPC access, fix W51 provider availability, implement
sell simulation/depth/W7, or validate commercial demand.

Adjacent topics not included: a full YAML implementation; offline_suite.tracked_changes
transport behavior (not reproduced in this proposal); complete owner-power numeric schema
validation; preserved-cache distribution; benchmark metadata/rebaseline. Do not describe
unexamined dimensions as observed absences.

## Amendments

None. The lead owns generated pages and release metadata separately.

