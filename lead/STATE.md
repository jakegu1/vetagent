# Lead state (the baton)

> What is in flight right now. The lead updates this at every check-in and merge; a new lead
> session starts by reading it. Durable rules live in `AGENTS.md`, `lead/QUALITY.md` and
> `lead/decisions/`. Test for this file: could a stranger act on every row below?

Last updated: 2026-10-18 by Codex, starting the next dependency-ordered technical batch:
existing-provider discovery failover first, deterministic/live RPC separation second.

Current Owner decision: Experiment D moves to 2026-10-20 (ADR-0002). Its original
thresholds and unresolved state remain. T-024 reconciles the active gate and dependent
review dates. Historical Oct-16 records are retained with their original dates.
Uncommitted work in the primary checkout is preserved; this pass uses isolated worktrees.

## Starting a lead session

1. Read this file, then `lead/config.yml`, the Needs-you section and the latest log of
   `lead/OWNER.md`, and `lead/tasks/README.md`.
2. `git fetch`, then compare `master` with `origin/master`. Bots push to master several times a
   day; when behind, merge (never rebase) before starting work.
3. Reconcile: for each in-flight row, check the real branch, worktree or subagent result, and
   CI for all six workflows, not only `test.yml` (the command is in `CLAUDE.md`). Fix this file
   if it drifted.
4. Act on each row's next action. Then start the next ready task if WIP allows. Autonomy is
   **A0** (`lead/config.yml`): spec, dispatch, review and decide; merges and pushes need Owner
   authorization. The scoped technical release authorization below is already present.
5. Run `python lead/checks.py` before every commit to master, lead bookkeeping included.
6. Check the rotation rule (`lead-handoff`). Update this file and commit.

## Standing notes

- **Open the session with this repository as the project folder** (not its parent), so that
  `CLAUDE.md`'s lead block, the untagged-probe hook in `.claude/settings.json` and the
  SessionStart hook in `.claude/settings.local.json` load. **The SessionStart hook works:** at
  the start of lead session 2 the first 80 lines of this file appeared on their own.
- **Autonomy is A0.** The lead plans, dispatches and reviews; scoped Owner authorization is
  required for merges and pushes. The technical release authorization below does not change
  money, legal, privacy, permission-file or pre-registered product-gate requirements.
- **M1's clock is running** since run 36445100361 (2026-09-28 15:38 UTC, head `dc401b9`); still
  green on run 36754083925 (head `d033c90`, 2026-09-30 UTC, T-009's push). At each check-in, check
  `gh run list --workflow=test.yml`; any red run on master restarts it and stops new work until
  green (tripwire Q4).
- Pushing: fetch and merge origin first (never rebase), regenerate the derived pages
  (`merge.after` in `lead/config.yml`), run the checks, commit the regenerated pages if the
  merge moved them, check the commit messages for anything private, then push and watch CI.
  `git merge -F -` does not read a message from stdin here; write it to a file in the
  scratchpad and pass that file.
- The `vetagent` MCP server in `.mcp.json` points at production. It sends
  `x-mcp-client: vetagent-owner-editor` (read 2026-09-29), so its calls are filtered as ours;
  a lead session still has no reason to call its tools (invariant 7).

## In flight

| Task | Level | Stage | Who | Next action |
|---|---|---|---|---|
| T-032 | 3 | Done; both fresh reviews approve, merged 106ad21, post-merge 37/37 | Lead | Publish with related technical batch |
| T-034 | 3 | Round one changes required; unmatched prefixes shadow complete encoded markup | Executor after named amendment (a) | Add frozen regressions first, repair the recognizer, fresh combined final review |
| T-033 | 3 | Isolated host-lock implementation | Executor | Tests first, actual public-index lock and credential-free Linux build preparation |
| T-037 | 3 | Isolated eight-file safeguards and reproduction task under amendment (a) | Executor | Five tests-first findings; preserve newer inputs and wait for T-034 approval before integration |

## Autonomous technical continuation

The Owner explicitly authorizes continuing the known technical-gap queue while away,
including the choice of bounded delegation, quality verification, technical merges,
pushes and deployment. This extends the earlier two-task batch cap, not the sign-off
categories for money, source rights, privacy, permission files or product gates.
Dependency-related fixes are batched; changes sharing workflow registrations are
integrated serially. Fresh reviews, the tests-first contract and actual Linux/runtime
verification remain required. Do not treat unavailable upstream observations as passes.

T-032 is approved and integrated. T-034's rendered-template guard runs in a separate
worktree and its round-one boundary finding is corrected before integration. T-033 host
build locking starts from T-032's frozen source and integrates after its approval,
because both register workflow steps. Separate scoped
follow-ups cover live-backfill observation classification, remaining release guards,
Node/Pyodide build resolution, action/runner migration and reproduction instructions.
No new paid service, provider, benchmark rebaseline or product-threshold change is
implied. Calendar-time and externally unavailable evidence stay explicit gaps.

## Current batch baseline

Actual required Linux preflight 39099114314 passes at 6898b72. Required master CI
39099401243 also passes; observed upstream checks are 232 pass, zero failure, zero blind
and zero partial. Optional historical backfill still records two generic HTTP 400
failures and is not called successful. Actual deployment 39099401296 executes the
full thirty-six-step gate, uploads Worker version 6ff81833-7d6d-4019-aab3-1073bc9096f8,
and passes production smoke. T-027 and T-031 are deployed on that exact functional head.

Tagged dated readback sees complete discovery on Base and Solana and an actual Base
discovery-to-liquidity/assessment handoff. The assessment remains unknown where sellability
was not observed. This is an availability observation, not a sustained-uptime claim.
Observer 39099677836 succeeds in preservation, regeneration and snapshot health, in
that order. Its two bot commits are retained through 3ef4f45 and merge 7c6c5d0; complete
post-observer checks pass thirty-six of thirty-six. Later records below retain the
previous failed preflight and repair history; they do not describe current deployment.

T-032 fresh reviews approve twelve of twelve and RED-TEAM: none. All three sealed
evidence bundles verify. Merge 106ad21 preserves the tests-only and two separate fix
commits. Actual generation and the lead's post-merge gate pass all thirty-seven steps
in 109.7 seconds. T-034 round one
finds delimiter shadowing in both rejection directions; named amendment (a) keeps
all frozen assertions and adds only explicit regression tests before correction.

Repair (g) is independently approved twelve of twelve with RED-TEAM: none and merged
as 76747d3. A different reviewer reproduces the actual old 3.12 failure, verifies
unchanged digests/assertions and meaningful mutants on both runtimes, and passes
ordinary/inherited-denied thirty-six-step inventories. The lead verifies both sealed
eighty-one-artifact bundles and their two signatures each. Windows evidence does not
replace the new required exact-head Linux preflight; production promotion is pending.

Preflight 39097068303 fails T-027's structural acceptance under Python 3.12.15 because
the frozen 3.13 AST serialization omits empty fields. Later ordinary CI steps are skipped,
not passed. Production stays on its previous verified version. Named test fix (g) keeps
all frozen digests/assertions and changes only canonical serialization compatibility.
T-032 is paused before its first commit with an exact external draft backup; update its
base after the repair. Q1's post-integration regression rule demotes autonomy to A0.
The Owner's explicit autonomous technical repair/deployment authorization remains in
force; no new approval is needed inside that scope, and no other sign-off is waived.

T-027 final combined review passes twelve of twelve with RED-TEAM: none. Its fresh
ordinary and inherited-denied runners both pass all thirty-six steps. The initial
mixed-line-ending finding is retained and fixed under the exact two-form bar; all
original controls and live code remain. The lead verifies the fifty-artifact combined
seal and forty-six-artifact final executor seal, including both signatures each, before
merge a77d1e1. Source approval does not claim deployment; the actual release stages follow.

The Owner asks to continue the same method, repair upstream access fluctuation first,
then separate live RPC test dependencies, and deploy directly after quality checks.
This is scoped technical merge, push and deployment authorization; other sign-off
categories remain unchanged. The original two-implementation batch uses serial source
changes and bounded independent/adversarial reviews; the newer autonomous continuation
above authorizes the subsequent known technical-gap batches.

The integration branch retains scheduled data through b13aac2. The real fixed-point
generator succeeds; exact external backups restore only proved calendar/recent-log
display drift. Actual configured baseline passes all thirty-five steps in 132.7
seconds. Latest scheduled snapshot 39074841808 and subsequent bot CI 39075499305
succeed; all existing daily data is retained. The primary checkout is fingerprinted
outside the repository and is not an implementation target.

Fresh tagged discovery calls on both Base and Solana fail with the generic all-source
error. A separate external-network-blocked reproduction through the real fetch path
proves the configured keyed discovery route is never called when keyless replies 429.
The production refusal status and current key configuration remain unconfirmed.
T-031 repairs this measured bypass without adding a provider or changing risk logic.

T-031's tests-only 19d6632 yields 196 meaningful MCP failures and the preregistered
endpoint-template mismatch. Source ab3632b fixes the one new_pools routing finding;
generated receipt 358f210 is the clean frozen head. Its actual configured checks pass
35/35 in 118.9 seconds. The lead verifies both detached integrity signatures and all
thirty-five sealed artifact hashes before independent and adversarial review. These
are executor-stage checks; review and runtime proof remain separate evidence stages.

Subsequent T-031 review passes: independent twelve of twelve and adversarial none,
both with their own complete 35-step runs (115.8 and 114.7 seconds). Their sealed
manifests and original reports are verified before merge 32a94f9. The review record
keeps test-first and unchanged numerical boundaries explicit. Post-merge checks and
deployment are not implied by source approval and are the next actual stages.

The real post-merge fixed-point generator succeeds; only proved calendar/recent-log
display and newline drift is restored from exact external backups. Actual integrated
checks pass all thirty-five steps in 110.7 seconds, including 1432 MCP assertions.
T-031 is complete as reviewed source; actual batch deployment/runtime readback is still
pending. T-027 now starts from this green integration with the finalized specification.

T-027 preparation obtains genuine bytecode at finalized Ethereum block 26216600 with
four bounded requests to an existing provider and a same-block hash recheck. The lead
independently checks all raw receipt/code hashes. The unchanged original controls give
six passes when supplied that recorded code with network denied. The complete old
runner under inherited network controls passes 34/35 in 195.6 seconds, failing only
owner powers (51 passes, four failures); all 238 Python processes load the guard.
T-027's ready specification preserves deterministic controls and separate live coverage.

## Latest verified linked release

Published functional head 6898b72 contains T-031 discovery routing and the reviewed
T-027 recorded/live separation with compatibility repair (g). Exact-head preflight
39099114314 and master CI 39099401243 pass required jobs; actual deployment
39099401296 executes all thirty-six offline steps, uploads Worker version
6ff81833-7d6d-4019-aab3-1073bc9096f8 and passes tagged production smoke. Observed
upstream contracts are 232 pass with zero failed, unobserved or collapsed paths.
Optional historical backfill still has two HTTP 400 failures, kept separate.

Tagged Base and Solana discovery return complete new/trending listings, and an
actual Base result reaches both liquidity and risk tools. Unknown sellability is
still unknown. Production observer 39099677836 preserves records, regenerates and
checks snapshot health successfully. Its bot commits through 3ef4f45 are retained;
actual following workflow_run CI 39099886952 passes the complete offline job on
that exact bot head. These dated observations do not prove sustained availability
or every intended snapshot slot. T-032 is subsequently integrated and checked but
is not part of this already deployed head.

## Previous verified linked release

Published functional head d44d79a contains approved task merges 24c9aa7, a925eec and
629b5bc. Complete integrated checks pass all thirty-five steps in 110.3 seconds.
Exact-head Linux preflight 39054837848 and master CI 39055170253 pass required jobs
and all 219 observed upstream checks, with no unobserved or collapsed path. Actual
deployment 39055170209 runs the complete suite, uploads Worker version
173a8b2d-8873-4e75-9384-2e104ca84679 and passes tagged production smoke. The existing
optional Base backfill RPC HTTP 400 remains a separate unresolved item.

Tagged independent readback confirms the homepage, health and both new tool schemas.
The first discovery call cannot observe either source; the bounded retry returns
partial, with new usable and trending failed. One returned token is successfully
handed to both liquidity and assessment tools. Separate canonical controls actually
return the conditional reserve marker and qualification from both tools. This is
working partial-source behavior, not proof that discovery availability is solved.
Direct current upstream lists parse successfully outside the Worker; the precise
cause of the different Worker observations remains unconfirmed. No additional source,
key, provider, numerical change or untagged production request is introduced.

Actual observer run 39055381257 succeeds in order: Commit, Regenerate the pages that
quote it, Check snapshot freshness and coverage. Its new step reports healthy: latest
age 0.621 hours, 672 observation rows, forty pages, zero gaps and five complete passes
among five observed in the last twenty-four hours. Counts include manual observations;
they are not five scheduled-trigger proofs. The observer reads committed manifests
and does not itself collect a fresh pool pass. Its data and generated pages are retained
through 1324b7f, with deployed source and checks unchanged.

Latest actual scheduled snapshot 39052933968 succeeds in collection, preservation,
generation and coverage. Independent raw Git counts at a907e28 prove 672 observations,
671 unique pools, eight chains, sixteen listing slots, forty HTTP 200 manifest pages,
zero gaps and forty-five continuous archive dates. One pool appears in both listing
kinds; raw observations retain that provenance. Every original byte prefix of all 127
prior NDJSON files is preserved. This scheduled data is retained before deployment.

The Owner asks for related gaps to be completed in batches with the highest delivery
quality. Use a dependency graph: isolated nonoverlapping tasks run in parallel, each
finding has its own test/fix history and review, overlapping engine changes are serial,
and the batch gets a complete integrated check and one release. Cap this first batch
at three implementation tasks; a depth change needs the study evidence and T-028's
engine freeze first. Existing technical release authorization still applies; no change
to A1, product gates, spending, providers, privacy or agent permissions.

Both T-028 and T-029 pass final combined reviews and their separate post-merge gates.
The combined source/metadata base passes all thirty-five configured steps in 110.8
seconds and is committed as 5d37434. T-030 is dispatched only from this reviewed,
green base. All three implementations share the verified release above.

T-030 freezes at fd3c1d1 after tests-only 199077a, source af02714, the preregistered
recommendation-copy acceptance 7d1c0d9 and a separate generated receipt. Complete checks
pass all thirty-five steps in 114.2 seconds. Its isolated immutable replay preserves all
576 benchmark rows and both committed result files byte for byte. Complete answers
differ only by 106 conditional reserve-check markers, 106 exact qualifications and
four copies of that same qualification in the existing final recommendations. No
numerical gains or regressions are measured. Fresh independent review passes twelve
of twelve and adversarial review has no material finding. Both run all thirty-five
configured steps themselves; independent replay reproduces the complete frozen
benchmark, and the adversarial bounded grid compares 372 full answers. Signed reports
and all sealed artifact hashes are checked before merge 629b5bc. Shared integrated
checks and actual deployment are completed as recorded above.

The Oct-18 check-in fetches origin/master 4669cf0 and retains all scheduled observations
as 1fbabc5. Its actual configured baseline is 35/35 in 110.9 seconds. The real generator
succeeds; date/relative-label and recent-commit-only display drift is proved and restored
from an exact external backup. No source, test or workflow changed upstream. Latest
completed bot CI 39032278470 passes at 4669cf0. The primary checkout remains untouched.

Previous completed release: T-024 is merged as eb13f174, T-015 as 29afd0d9 and T-025 as
1d0a76f9, all after fresh required independent and adversarial approval. T-025's
bounded second round fixes the first adversarial finding at frozen 63651083;
acceptance is 335/0 with four unchanged unsettled cells, complete outputs unchanged,
and meaningful mutants caught. Original signed evidence remains private.

That previous release published head 19ea3af. Complete integrated checks pass 35/35 in 112.8 seconds;
exact-head Linux preflight 38853528116 passes required jobs and all 219 observed
upstream checks, with no unobserved or collapsed path. Actual deployment 38853922606
runs its complete suite, uploads Worker version 705371de-9252-45f5-a1a2-ed77a08184bb
and passes tagged production smoke. The lead independently reads the approved demo
caption and health at HTTP 200. Master CI 38853922502 also passes required jobs and
219 fully observed upstream checks. Optional backfill HTTP 400 remains separately parked.

Actual manual snapshot 38853950387 passes collection, pool and sellability commits,
generation and coverage. Independent raw Git counts at 123a856 prove 663 unique pools,
forty HTTP 200 manifest pages, thirty-seven successful pages and three observed listing
ends, eight chains and sixteen listing slots, zero pool-collection gaps, and forty-four
continuous dates from Sep 3 through Oct 16. Every original byte prefix in all 121 prior
raw NDJSON files is preserved. The optional sellability step records sixteen usable
answers and nine no-record observations; missing records are not successful simulations.
Bot CI 38854730840 passes the complete test job at 123a856; its network jobs are
intentionally skipped for workflow_run. Verified bot commits are merged as 45267d5.
The real fixed-point generator succeeds, with only proved newline drift restored from
exact external backups. The final integrated gate precedes this completion-record commit.
One manual pass proves neither four daily triggers nor long-term scheduled reliability.

The Owner authorized engineering repairs and prioritized deployment, then restored execution
permissions and explicitly asked to continue on 2026-10-11. This covers reviewed technical
merges, preflight pushes and deployment pushes. Keep A1 and all other sign-off categories.
This release starts from inspected origin/master 7ec4530 and preserves scheduled bot data;
unrelated unpublished local bookkeeping is not included.

Manual snapshot run 38139242886 persisted 415 pool rows and its manifest before reporting
eighteen gaps. Recovery saved another twenty-seven rows across three pages. Final outcomes
were twenty-three successful pages, fourteen failed fetches, four skipped pages and two
observed listing ends. These counts were independently read from the committed pass. HTTP
429 is now observed; shared-egress or provider capacity as its backend cause remains an
inference. The existing GitHub repository has Cloudflare credentials, but no CoinGecko key
secret. Do not present incomplete coverage as restored collection or silently add a paid source.

Read-only slower-pacing experiment 38140061977 completed with forty HTTP 200 responses,
672 independently counted pool rows and zero gaps across all eight chains. Its forty
manifest entries contain thirty-seven successful pages and three observed listing ends.
T-022 uses its measured 12.1-second interval in scheduled pool collection without changing
ordinary fetcher defaults, recovery budgets or the coverage rule. This is one measured
pass; scheduled reliability remains to be observed. T-016 is closed after verified deployment.

T-011 is deployed at fefe6d1 after round-2 independent approval and full integrated
checks. Exact final preflight 38145574532 passes required jobs; its upstream monitor
reports 219 checks passed, three probes unobserved and no paths collapsed. No new baseline
was frozen from that incomplete observation. Actual deployment 38146148169 uploaded and
deployed Worker version c375f494-2ed2-42ba-94e5-3a8006ed6c05; offline and tagged production
smoke steps all ran and passed. No real fill belongs to T-011. T-019 independently
reproduced its 91 misses over 89 URLs and backed up the original cache before the allowed
fill. The single fill added 89 entries without changing or deleting old entries. Its
zero-miss replay changes two token rows through their actually requested successful
upstream answer; the other 574 rows and the independence result are unchanged. The
data-only rebaseline now has fresh independent approval at 12/12 and red-team none.
Both reviewers reproduce the real publication red and generated fixed point. Approved
source is merged as e93169a, retaining all snapshot bot data. The lead's own immutable
integrated replay exits zero and reproduces both committed outputs byte for byte, with
zero network calls, after-clock selections or cache changes. Full integrated checks pass
all thirty-one steps, and exact-head Linux preflight 38150722554 passes required jobs and
219 observed upstream checks, with no unobserved or collapsed path. Published head is
a19c3dc. Actual deployment 38150990382 runs and passes its offline suite, Worker deployment
and tagged production smoke. The homepage and Agent text are read back with the new
measured figures, and health is HTTP 200 and ok. T-019 is complete; T-013 starts from this
exact published base. The optional backfill HTTP 400 remains an explicitly parked repair.

T-013 freezes at b99f2e7. Its tests-only first commit b164b3e has 761 passes and
sixty behavioral failures before source fix a6a31fe; all 706 older risk assertions
remain green. The immutable base replay is byte-identical and misses nothing. At the
fix, exactly five full-id seller URLs miss. The single fill records five HTTP 200
answers and adds five cache entries without changing older bytes. Final replay misses
nothing; the lead independently compares all 576 committed rows and finds exactly
four registered changes, 572 otherwise identical rows and no old high verdict reduced.
Unknown moves from 120 to 116. Executor final checks pass thirty-one steps at the
clean frozen head. Fresh independent review passes 12/12; red-team review has no
material finding after 563 independent probes. Both reproduce the immutable contract,
actual request attribution, all row/figure changes and generated fixed point. Approved
source is merged as 46fb2a6. The lead's own integrated replay is byte-identical for
all 576 rows, with zero misses, network calls, cache writes or after-clock selections;
source and copied caches remain unchanged. Full integrated checks, exact-head preflight
and actual production deployment are complete. Full integrated checks pass all thirty-one
steps in 79.6 seconds. Exact-head preflight 38155937648 passes required jobs and 219
observed upstream checks, with no unobserved or collapsed path. Published head is
7f796e4; actual deployment 38156203366 runs and passes the complete offline suite,
Worker deployment and tagged smoke. Worker version is 92c2e737-cf3a-46d3-8bdd-0d8faf74fdb6.
The lead independently reads the homepage and Agent text at HTTP 200 with the new
20.1 percent figure and health at HTTP 200 and ok. T-013 is complete. T-012's exact
base is this published head; its mandatory replay and row pre-registration precede
the first tests-only commit. The named ASCII evidence clarification
retains pre-existing English punctuation and proves every changed line is ASCII.

T-022's named tests-only red at 62cccc7 has 320 passes and sixteen behavioral failures
before source fix 8b54497. Its original 293 assertions remain green. Executor tests
now pass 336 assertions and all thirty source-baseline steps. Slow fake scheduled passes
preserve twenty-four observed rows at 1200 seconds, with twenty gaps and no late HTTP.
This is offline evidence, not deployed coverage. The pushed fix's missing red description
is corrected append-only in the review record; existing source history is never amended.
Combined round-2 review now approves exact 8b54497 at 12/12, with no material red-team
finding. It independently reproduces the old defects, immutable acceptance and broken
mutants. Source Linux preflight 38146049602 passes required jobs and all 219 observed
upstream checks, with no unobserved or collapsed path. Approved source is merged locally
as 9d2ed35. Full integrated checks pass all thirty-one steps in 79.3 seconds, including
336 archive assertions and 814 replay assertions. Exact-head preflight 38148113901 passes
required jobs and 219 observed upstream checks, with zero unobserved or collapsed path;
the optional backfill job retains its HTTP 400. Published head is 86a8111. Actual manual
snapshot 38148501978 completes successfully at 14:54:55 UTC. Independent counts of the
committed raw pass verify 676 unique pool rows, forty HTTP 200 manifest entries, thirty-seven
successful pages, three observed listing ends, all sixteen chain/listing slots and zero
gaps. Every prior pool, manifest and sellability byte remains a prefix. Its three bot
commits through f129baf are merged as 0beaa21. Real schedule 38165984869 now runs on
published e657c32 from 18:57:31 to 19:06:42 UTC. All collection, pool/sellability commits,
generation and final coverage steps actually run and pass. Independent raw Git counts
at 4fe3090 prove 664 unique pools, forty HTTP 200 manifest pages, thirty-seven successes
and three observed listing ends, all eight chains and sixteen chain/listing slots,
with zero gaps. Every pre-run pool, manifest and sellability byte remains a prefix.
Bot-triggered offline CI 38166626385 passes; network jobs are intentionally skipped
for this event. Bots through 4fe3090 are merged as 689debf. T-020 and T-022 are complete;
retain their minor DNS test follow-up. This proves one real scheduled paced pass, not
a long-term reliability rate or the cause of earlier missing nominal triggers.

## Waiting on the Owner

- H-15's earlier push is already present in public history at a31813b; its old pending entry
  was stale. The current technical release uses its own inspected remote base.
- **H-13 (postponed by the Owner on 2026-10-16 to 2026-10-20, ADR-0002): the 2026-10-20
  gate.** From 00:00 UTC that day `tests/test_gates_get_reviewed.py` is red, and so are `tests`
  and every deploy, until (a) the gate's row in `docs/STRATEGY.md` section 8 carries
  `Resolved: <what Experiment D measured> -> <decision>` and (b) O2, O8, O9 and O11 in
  `docs/OPPORTUNITIES.md` are decided and moved under "Reviewed and closed". The first bot run
  that day is `snapshot.yml` at 02:23 UTC. The plan: that morning the Owner gives the lead the
  result in one line, and the lead drafts both edits for the Owner's yes (the reading and the
  decisions are the Owner's). Nothing needed from the Owner before then. Since T-007 the
  conclusion needs an ASCII `->` with words on both sides, after `Resolved:`, in the gate's own
  row; a placeholder, U+2192, markup or the template pasted back is refused. Draft it that way,
  run `python tests/test_gates_get_reviewed.py` with the date forced to 2026-10-20 on the draft,
  and push it before 02:23 UTC (every push needs the Owner's yes).
- (H-14 done 2026-10-01, as recommended: T-007 merged as `3fb1d3d`, T-008 as `f1a767d`, then
  pushed after preflight run 36744394310 was green on Linux: `a5bcce5..26392ab`, `tests` run
  36744975640 green. T-009 merged by the lead under A2 as `235b20c`, pushed the same way after
  preflight run 36753548989 was green (the Owner page 379 of 379 on Linux, with the page's date a
  day ahead of UTC): `26392ab..d033c90`, `tests` run 36754083925 green. No deploy either time:
  nothing under `src/`. Both preflight branches deleted. Outgoing commit messages were scanned
  for local paths, addresses and non-ASCII: 27 and 13, clean.)
- (H-12 answered 2026-09-30: yes, as recommended. Autonomy A2, applied in `lead/config.yml`.)
- The Owner's own W5 steps (read Quick Intel's terms; the 17-call check on W3's adversarial
  cohort) are in `docs/BACKLOG.md` and `docs/OWNER.md`.
- (H-11 done 2026-09-30: merged T-005 as `0fa831a`, T-006 as `053fe0a`, the Level 0 branch as
  `b29c424`; checks 29 of 29. Preflight run 36669036422 green on Linux; pushed `d5bb216..3db4bf5`;
  `tests` run 36669385087 green; no deploy (nothing under `src/`). Preflight branch deleted.)
- (H-11 answered 2026-09-30: as recommended. Once T-006's round-2 re-review passes, merge
  T-005, T-006 and the Level 0 branch into local `master`, then push in two steps: the merged
  tree to a preflight branch first (`test.yml` on Linux, no deploy), then `master` once that is
  green. If T-006 does not pass, ask again before merging the other two alone.)
- (H-10 done 2026-09-29: merged origin (six bot commits), T-003 as `fec26df`, T-004 as
  `d0eb7e8`, the W5 row as `6c8b785` (its `docs/OWNER.md` conflict resolved by regenerating);
  checks 28 of 28. Preflight branch run 36557264402 green on Linux; pushed
  `8daa0f7..6c8b785` (50 commits); `tests` run 36557714268 green; `deploy` run 36557714265
  green: the gate reported "28 of 28 steps passed" in its log, then the deploy, the smoke test
  and IndexNow passed. Preflight branch deleted.)
- (H-9 answered 2026-09-29: update W5 with the method and the direction of the result, no
  figures, merged with T-003 and T-004. Figures derived from Quick Intel's answers stay out of
  this public repository, `lead/` included, until the Owner has read Quick Intel's terms.)
- (H-8 answered 2026-09-29: merge the three Level 0 branches locally, no push. Merged as
  `a8a758d`, `08915db`, `d592f8d`.)
- (H-7 answered 2026-09-29: yes; applied after the clean merge. Autonomy A1.)
- (H-6 done 2026-09-29: T-002 merged as `16e100e`; pushed `dc401b9..16e100e`; CI run
  36455682835 green; no deploy.)
- (H-5 answered 2026-09-29: yes to both items, as recommended. Item 1, the Level 0 fix, merged
  as `82acff3`; item 2 was T-002.)
- (H-4 answered 2026-09-28: stay at A0 for the next task; the lead proposes A1 again after one
  clean merge.)
- (H-1 done 2026-09-28: pushed `c954f43..dc401b9`; CI green on it.)

## Next up

The Owner authorizes autonomous completion and deployment of remaining known technical
gaps. Finish the current two-task release before extending its source. The next concrete
ready task is T-032, whose network-denied reproductions show an omitted inclusive terminal
block and nonterminating negative-window configurations. W51's actual HTTP-400 origin
and outage/defect distinction remain separate; do not blanket-retry an unexamined error.
Current official GitHub guidance and exact first-party release/runtime metadata are
being checked before an isolated Actions/runner migration task. Guard-template and parser
findings receive distinct bounded specifications rather than a miscellaneous refactor.

This extension protects existing data and the checks that make releases reviewable.
Keep one active implementation when workflow registrations overlap, parallel read-only
investigation/reviews, at most three total task WIP and the workspace agent cap. Each
finding keeps its own red-before-fix commit and each task its required fresh review.
Stop adding tasks when only preregistered calendar/data prerequisites or Owner sign-off
categories remain; record their cheapest decisive next experiment without changing the
bar or calling them complete. No new provider, spending, legal text or product gate.

Earlier release planning, retained as history:

T-026 is evidence-complete; T-028, T-029 and T-030 are released. W28's prospective
discovery status/schema gap is resolved without reclassifying historical usage.
For the next bounded batch, first investigate the observed Worker discovery
availability variation: review on 2026-10-19, no new spending, at most one working day
to distinguish failed transport, unusable bodies and parsing using privacy-safe
diagnostics and same-response comparisons. New evidence opens this follow-up; it did
not redirect the completed batch. Do not promise complete-market discovery.

Then ready T-027's deterministic-RPC regression split with real fixture provenance and
unchanged power/proxy assertions. The draft is not an implementation authorization.
Further unknown-coverage and numerical reserve work requires separate attribution
and bidirectional regression evidence. No new provider or spending is authorized.
Deployment still annotates Actions/runtime and runner-image migration warnings;
verify current official guidance and the complete Python/Worker build in an isolated
upgrade task before changing versions. Experiment D remains due Oct 20 unchanged.

T-011, T-019, T-013, T-012, T-016, T-020, T-021, T-022 and T-023 are complete with their
actual release or scheduled coverage evidence recorded. T-021 publishes exact 7da5bdf
after independent 12/12 and red-team none. The lead's integrated replay keeps all 576
raw rows and 6,741 cache entries unchanged with no network, fill or after-clock selection.
Full integrated checks pass 34/34 in 81.9 seconds. Final Linux preflight 38171028227
passes required jobs and all 219 observed upstream checks, without unobserved or collapsed
paths. Actual deployment 38171367523 runs and passes every offline, upload and tagged
smoke step; Worker version is 6539783c-f83d-48c6-a507-8812bcd14f2b. The lead reads back
the deployed nullable numeric schemas, unchanged generated public figures and healthy
service at HTTP 200. Master CI 38171367587 passes required jobs and all 219 observed
checks. Its optional backfill HTTP 400 is preserved as a separately parked repair.

The literal correction journal is separately reviewed at L0. Its initial missing concrete
reference produces an actual 502/1 owner-guard red and 33/34 integrated result. Naming
the actual supplemental guard restores 503/0 and the full 34/34; the initial review and
failed evidence are retained. Older entries, executable ASTs and the 14-day window stay
unchanged. An exact-source forced-date probe shows the old recency guard red on Oct 15,
and the truthful Oct-11-UTC entry green; this is not a claim about the entire future suite.

T-023 is approved on frozen 14a1ab2, with ready authority 1d4303b and published
base 7da5bdf. Whole-repository caller search
finds only the cold main writer path; all four old observation tests are retained by AST.
The lead's actual offline CLI, using eight fully observed synthetic probes and an unchanged
key/type shape, overwrites the private old baseline as coverage falls from one to zero.
The same comparison performed first makes the existing writer refuse and preserve bytes.
Actual baseline/status bytes and all network sources remain untouched. The executor's
tests-only b9f71b0 is genuinely red at 144/44; its separate source fix 14a1ab2 passes
188/0 and all 34 configured steps in 104.7 seconds. Three prescribed mutants fail and
are restored; sixteen offline default-monitor cases remain equivalent. Both fresh
reviewers independently approve the exact frozen SHA: independent 12/12 with no
required/optional change, red-team none. Their own full suites pass 34/34 in 90.9 and
156.0 seconds. Source Linux preflight 38174669994 passes all required steps and 219
observed upstream checks, with no unobserved or collapsed path. The optional RPC
backfill retains HTTP 400; the heavy benchmark is intentionally skipped.
Approved source is merged without squash as 83e40d9. The lead independently runs ten
actual cold/warm CLI controls with private synthetic files: refusals precede any write,
valid boundary/bootstrap writes work, one new collapse is retained after repeated calls,
zero network attempts occur and all real baseline/status/result bytes stay unchanged.
Full integrated checks pass 34/34 in 81.0 seconds. Final exact-head Linux preflight
38175433633 verifies 2a8204f, with required jobs and all their steps passing, 219 checks
passed, zero failed/unobserved/collapsed. This exact head is published to master.
Actual master CI 38175829622 passes required jobs and 219/0, with one RugCheck probe
unobserved after HTTP 400 and no collapsed path. That is an unobserved probe, not a
missing field; no real baseline is frozen. Optional Base RPC backfill HTTP 400 remains.
The tagged post-publication health request returns HTTP 200 and ok at 21:19:20 UTC.
This test-only repair updates CI; the already verified T-021 Worker remains deployed.
T-023 is complete. Keep the manual freeze rules binding.

The primary checkout is on codex/engineering-verified-20261012. Its original T-019
branch, unrelated local master, stash and permission-file bytes are preserved; advance
only this clean verified branch to the latest published completion record. No old
unpublished bookkeeping or permission change belongs to this release.

Separately parked technical follow-ups: the optional historical Base RPC query still
returns HTTP 400; diagnose supported free query windows before changing provider or
adding cost. A saved real selected-pool case also has a stated USD depth far above a
nearby quote-anchor balance-derived cap. A private saved-data selection control confirms
the seam, but actual fallback attribution, benchmark row impact, LP/manager eligibility
and runtime request cost remain unmeasured. Price the next bounded test at zero extra
spend and at most one working day. Do not silently alter anchors, bands, sources or
claimed depth, treat the static ID inventory as faulty rows, or redirect the completed
repair release into a new runtime policy without a ready specification.
Scoped technical merges and pushes already have Owner authorization;
A1 and all other sign-off categories remain unchanged. Older candidates and dated notes
below are retained as historical context, with their readings refreshed before action.

**The dates, in order** (all measured or read on 2026-10-01):
1. **2026-10-05 15:38 UTC: M1 completes** if no `tests` run on `master` goes red; record it in
   `lead/QUALITY.md`'s milestone table and `lead/OWNER.md`.
2. **About 2026-10-05: the first weekly pass** (`lead-weekly`; none since the adoption on
   2026-09-28). Tripwire Q3 is over its threshold (H-12, H-13, H-14 in two days after H-5 to H-11
   in three); A2 took the Level 0 to 2 merges off the Owner.
3. **The old Oct-15 correction deadline is closed** by the truthful Oct-11-UTC entry;
   the unchanged 14-day accountability rule continues to apply.
4. **2026-10-20: the gate** (H-13, Owner-approved postponement). The generated Owner page
   must show this date after T-024; the original decision rule is unchanged.

**Every check that can go red on the calendar alone** (a scan of `tests/` for `date.today()`,
2026-10-01): the gates and their parked entries in `tests/test_gates_get_reviewed.py`
(2026-10-16, 2026-12-04, 2027-03-04); in `tests/test_owner_page.py` the corrections window
(below), the page's age (7 days) and the newest snapshot's age (2 days), the last two kept fresh
by the bots. `tests/test_coverage_matrix.py` only prints fixture ages. Re-scan when a test is
added.

**Dated: the corrections window.** `tests/test_owner_page.py` requires an entry in `CORRECTIONS`
(`tools/owner.py`) dated within 14 days. After T-009 the newest is 2026-09-30, so the test goes
red on **2026-10-15 UTC** unless a newer entry exists: by 2026-10-14, add a real correction, or a
dated "nothing to report" (the test's own words), on a branch and pushed. It went unwatched once:
the 2026-09-19 entry would have turned master red on 2026-10-04, one day before M1 completes.

**Dated, checked 2026-09-30:** on 2026-10-16 `tests/test_gates_get_reviewed.py` turns red unless
the gate's row carries a conclusion and O2, O8, O9 and O11 are decided (H-13, told to the Owner).
T-007 makes a placeholder conclusion red as well, so it must be written as
`Resolved: <what the measurement said> -> <decision>` with real words on both sides. Check on
2026-10-14 that H-13 is on track.

Suggested order (lead #4, for lead #5): the dates above first. Then, if cheap before 2026-10-16,
T-007's follow-ups (decoding HTML entities before the markup step is measured at 98 of 98 still
passing). Then the two test-only follow-ups on `tests/test_bot_commits_stay_green.py` (T-008's
surviving mutants; T-006's speed and failed-read items), one after the other, never in parallel
(same file). Then the T-004 node-property follow-up.

- Candidate, Level 3 area (the deploy gate), from T-004's round-2 re-review: a YAML node
  property (`&anchor` or `!tag`) before an unclosed quote still ends the job early in the
  runner and the guard's reader (a one-line fix is in `lead/reviews/T-004.md`, follow-up 1);
  test gaps: an unclosed value under `with:`, escaped and doubled quotes, and the reader's own
  refusal pinned to the named line; the guard's `if:` reader misses a double-quoted value
  continued at six spaces (deliberate-edit class).
- Candidate, test file only, from T-006's round-2 re-review: AC 6's 15 s bound on Windows is
  not met (median 15.2 s); run each near-miss value of `GITHUB_ACTIONS` with one argument
  instead of three (about 1.7 s), bring the file's own timing line over the child check, make
  `_what_moved` say that a failed read is a failed read, and bring the module docstring up to
  the Actions rule (`lead/reviews/T-006.md`, round 2 lead decision). T-008's independent review
  adds to the same file (do it after T-008 merges): the status canary shares the failed-read
  blind spot (a missing `.git` read twice compares equal); the docstring should cover T-008's
  runs; the whole file now takes about 25.7 s on Windows (was 13.2 s).
- Candidate, test file only, from T-008's reviews: four surviving mutants of
  `snapshot-commit.sh` (`lead/reviews/T-008.md`): the nothing-new branch without `exit 0`
  (require no `commit` or `push` in that call's git trace, already captured); a `[Tt]rue` match
  (add `True` to the refused values); the retry loop cut to two attempts (add a case where every
  push fails: exit 1, `LOST`, five attempts, sleeps 10 to 50); `date` without `-u` (run the
  calls on Actions under a `TZ` whose date differs from UTC's). Not in parallel with the T-006
  follow-up (same file).
- Candidate, test file only, T-010's review optionals (`lead/reviews/T-010.md`): a fixture with
  no `##` heading before a stray dated row (kills mutant M4, `gates()` reading from character 0
  when section 8 is missing); the AC 6 test combines the guard's two conditions itself, so a
  third one added to the guard would go unseen. Neither is live today.
- Candidate, Level 3 area (the gate guard), T-007's follow-ups (`lead/reviews/T-007.md`): "variant
  B", typing `Resolved:` and pasting the whole failure message after it, is still accepted
  (judging the text after each `Resolved:` up to the next one closes it, measured, not applied);
  the template with entity-escaped brackets is accepted (decode with `html.unescape` before the
  markup step, measured: 98 of 98 still pass); three surviving mutants of the markup step and the
  row lookup need self-tests. Before 2026-10-16 if cheap; none of them is live today.
- Candidate, Level 1, from T-003's review: when the scorecard's production row is in the form
  `bench/scorecard.py` is not printing, its two targets report `absent` and `pattern not found`,
  and the second gets the "restore the sentence" advice, wrong for a generated row; three
  surviving mutants (the owner-powers advice naming the wrong file, the advice for a key
  nothing computes, a single rewrite listed); a line matching both retracted-claim patterns is
  printed twice, so its count is untrue.
- Candidate, Level 1: `_owner_power_figures()` raises on invalid JSON in
  `bench/owner_powers.json`, while the production readers treat an unreadable artifact as not
  measured. Same class as T-002.
- Candidate, Level 3 area (CI script): `regenerate-derived.sh` sends each generator's output to
  `/dev/null`, so a failing bot run shows only `::error::publish_numbers.py failed`, not what
  is left to fix.
- Candidate, Owner's call first (public text): the `docs/EXPERIMENT_C.md` production sentences
  quote the live rate even below the scorecard's 100-answer floor, and compute it as
  `100*u/n` while the scorecard row now uses `(u/n)*100`; the two round differently on 314 of
  about two million (u, n) pairs (T-001 review, problem 4). Whether a below-floor rate belongs
  in that text is a public-claim decision.
- Candidate, investigate first: deploy tooling is unpinned (`uv.lock` and `pylock.toml` are
  gitignored as build artifacts). Whether to commit a lock is a decision for
  `docs/DECISIONS.md`.
- Candidate, check mode vs the suite: `unsourced_competitor_figures()` fails check mode (and,
  after T-002, `--write`), but no test in the suite runs it, so CI would not see an undated
  competitor figure. Decide whether a test should, or whether check mode should not.
- Taken by lead #4 and removed from this list: the `snapshot-commit.sh` guard (now T-008, with
  a behavioural test of its retry path). The stray line 123 in `tests/test_gates_get_reviewed.py`
  (a mangled-heredoc leftover, a comment) is removed inside T-007 in its own commit; a scan of the
  repository for the same shape found no other.

## Rotation

The rule (`lead/config.yml`): rotate at about 0.4 of the context window or 72 hours, at a
natural boundary. **The context can be measured:** the desktop app's `get_usage` session tool
(load it with ToolSearch, `mcp__ccd_session_mgmt__get_usage`, session "self") returns tokens used
and the window. Lead session 4 rotated on 2026-10-01 after H-14 at 549,497 of 1,000,000 tokens
(55 of 100 parts), measured; it had passed the threshold unnoticed while reviews were running,
so check it at each natural boundary rather than once. Lead session 3 rotated on 2026-09-30 and
session 2 on 2026-09-29 on estimates; session 1 on 2026-09-28 at 50 of 100 parts.

## Handoff notes for lead #5

- **Open the session in this repository's folder and type /lead.** Nothing is in flight:
  `master` is `d033c90` on origin (T-007, T-008 and T-009 pushed; `tests` green; no deploy) plus
  the handoff commit, which is local and goes out with the next approved push.
- **Your first job is the dates** in Next up: M1 on 2026-10-05, the first weekly pass, a new
  correction by 2026-10-14, the gate on 2026-10-16. Nothing needs the Owner before 2026-10-16
  except pushes.
- **Autonomy is A2** (H-12): merge Level 0 to 2 after passing reviews and tell the Owner
  afterwards; Level 3 merges and every push are the Owner's. H-14's approval is used up.
- **Before every push**, scan the outgoing commit messages for local paths, e-mail addresses and
  non-ASCII (lead #4 did it with a short script in its scratchpad, which is gone: rewrite it, and
  watch it find something in older history before trusting a clean result). Push a preflight
  branch first while M1 runs; `test.yml` runs on every branch, `deploy.yml` only on `master`
  pushes touching `src/**`, `pyproject.toml` or `wrangler.jsonc`.
- **Two traps that bit lead #4:** a bash heredoc with quotes and backticks in a review record
  (nothing ran, but use the Write or Edit tool for every record), and a correction sentence of
  its own that a reviewer found not quite true (a correction entry has to be true in every word;
  have it reviewed).
- **A local date ahead of UTC** (after 16:00 UTC here) makes regenerated pages carry tomorrow's
  local date. T-009's review proved the Owner page is fully determined by its stamped date, so
  such a page passes on CI; a change that is only the date and the recent-commit list is still
  left to the bots (`merge.after`).
- **W5 is the Owner's, and it can be run now.** `python bench/second_oracle.py --plan --set
  adversarial`, then `--run --set adversarial` with their key: 17 calls, about 34 s, written to
  `bench/second_oracle_adversarial.json` (git-ignored); it refuses to start over an existing file.
  `--report bench/second_oracle.json` re-reads the earlier answers with the new classes. Raw
  answers and any figure derived from them stay out of this repository until the Owner has read
  Quick Intel's terms (H-9). The script cannot see how much of the month's allowance is spent.
- **Resuming an interrupted executor:** the previous process can end mid-round (it did on
  2026-09-30). Check the task branch and worktree for commits before assuming nothing landed;
  T-006's round 2 was complete on its branch with no READY report.
- **Scratch clones:** use `git clone --no-local`. A reviewer's hardlinked local clone reached only
  170 of 651 commits once (cause not found; see the log).
- **Agents in parallel:** give each executor and reviewer its own scratchpad subfolder by name
  (`lead/PITFALLS.md`). The Write and Edit tools decode backslash-u escapes into real
  characters; scan `lead/` for non-ASCII control characters before committing.

## Baseline

**Inspected origin/master ea545c0, 2026-10-11:** `python lead/checks.py` passed all twenty-nine
offline steps, exited zero and left the integration worktree clean. Real asyncio also works
in the restored execution environment. Latest master CI: run 38127088651, successful.

Before the lead kit, recorded 2026-09-28 on `f6c7c06` with `python lead/checks.py` (Windows,
Python 3.13.4, 19.0 s): 26 of 27 steps passed; the red one was `tests/test_published_numbers.py`.
After T-001 (`0a3098d`, 2026-09-28): 27 of 27. **Lead session 2 at `24a0a73` (2026-09-29):
27 of 27 in 19.0 s. After the Level 0 merge (`82acff3`): 27 of 27, and the run leaves the tree
clean. After T-002 (`16e100e`): 27 of 27, clean tree; `tests/test_published_numbers.py` 70 of
70. After H-10 (`6c8b785`): 28 of 28 (T-004 added `tests/test_deploy_gate.py`, 125 of 125);
`tests/test_published_numbers.py` 111 of 111; about 55 s locally. No failure is known.**
**After T-009 (`235b20c`, 2026-10-01): 29 of 29 in 87.2 s, tree clean; `tests/test_owner_page.py`
379 of 379 (T-009; 3.1 s, was 0.7 s). On CI, preflight 36753548989 and `master` 36754083925 on
`d033c90`: `test`, `upstream-contract` and `backfill-roundtrip` green.**
**After H-14's merges (`f1a767d`, 2026-10-01): 29 of 29 in 96.1 s, tree clean;
`tests/test_gates_get_reviewed.py` 98 of 98 (T-007), `tests/test_bot_commits_stay_green.py` 164
of 164 in about 25 to 30 s on Windows (T-008; was 13.2 s).**
**After H-11 (`b29c424`, 2026-09-30): 29 of 29 in 63.0 s. T-005 added `tests/test_second_oracle.py` (216 of 216, 0.5 s); after T-006 `tests/test_bot_commits_stay_green.py` runs the real script in scratch repositories (118 of 118, 13.2 s on Windows).** On CI (Linux), preflight run 36669036422 and `master` run
36669385087 on `3db4bf5`: `test`, `upstream-contract` and `backfill-roundtrip` green; the
regeneration script's 29 calls took 0.4 s there, so T-006 costs the deploy gate almost nothing.
Not part of the baseline: `tests/test_upstream_contract.py` and `tests/test_backfill.py`
(network; CI jobs `upstream-contract` and `backfill-roundtrip`).
**On CI:** `tests` was red from 2026-09-22 12:05 UTC to 2026-09-28: 32 runs, every one failing
at the step "Published accuracy figures match the benchmark". Run 36445100361 on `dc401b9`
(2026-09-28 15:38 UTC) is green: job `test` 27 of 27 steps, none skipped, and
`upstream-contract` and `backfill-roundtrip` succeeded. Run 36455682835 on `16e100e`
(2026-09-28 17:05 UTC, the H-6 push) is green: `test`, `upstream-contract` and
`backfill-roundtrip` succeeded; `benchmark` was skipped, as on every push (it runs only on a
schedule or a manual dispatch). No deploy ran. On `6c8b785` (2026-09-29 10:47 UTC, the H-10
push): `tests` run 36557714268 green, and `deploy` run 36557714265 green, the first deploy since
2026-09-22 and the first to run the whole offline suite first: its gate step logged "28 steps
from job 'test'" and "28 of 28 steps passed in 25.2s" before `pywrangler deploy`, the smoke
test and IndexNow. After it, the latest run of each of the six workflows had succeeded.
**No local side effect since `82acff3`:** `tests/test_number_coverage.py` restores
`docs/EXPERIMENT_C.md` byte for byte, and `python lead/checks.py` now exits 1 when a run
modifies a tracked file. If it lists one, find the step that wrote it; do not restore it by
hand and move on.

## Recent decisions

- 2026-10-01: T-009 merged by the lead under A2 as `235b20c` after a fresh review (12 of 12, no
  required changes). The reviewer found one sentence of the lead's own correction text not quite
  true (only the table cell was bold); the lead fixed it on the branch before merging (`f53417b`,
  `78c9275`), without a second review: a text fix in the reviewer's own words. Pushed under the
  Owner's H-14.

- 2026-10-01: H-14 approved as recommended. T-007 merged as `3fb1d3d` and T-008 as `f1a767d`
  (`--no-ff`, the tests-first commits kept). The post-merge regeneration moved only date-driven
  lines and the recent-commit list of `docs/OWNER.md` (local date 2026-10-01, UTC still
  2026-09-30), so it was restored and left to the bots (`merge.after`).

- 2026-09-30: the Owner answered H-12 as recommended: autonomy A2. The lead now merges Level 0
  to 2 tasks after passing reviews and reports each merge afterwards; Level 3 merges and every
  push still wait for the Owner (`lead/config.yml`).

- 2026-09-30: lead #4 put a new finding ahead of lead #3's list: the gate guard that decides
  whether the build goes red on 2026-10-16 accepts a placeholder conclusion (T-007, Level 3,
  because it enforces a pre-registered rule). The rule it enforces is the form its own failure
  message already asks for (`<what the measurement said> -> <decision>`), so no gate, test or
  threshold changes and no sign-off is needed; the Owner is told the form in H-13. T-008 (lead
  #3's first item) runs beside it. T-009 waits for T-007 so the Owner page and the guard share one
  rule instead of two.

- 2026-09-30: H-11 done as recommended: T-005, T-006 and the Level 0 branch merged and pushed
  in two steps (a preflight branch, then `master`); no deploy. T-006's AC 6 (15 s on Windows)
  is recorded as unmet (median 15.2 s) and not moved: the overrun came from the lead's own
  round-1 decision, and a slower local suite is not a blocking class under the round cap.
- 2026-09-30: both tasks went back for one round although their first verdicts passed, because
  each lost points in the class it existed to close (T-005: a share over rows that could not
  answer it; T-006: a check that could not run still passing the CI step). Both lessons are in
  `lead/PITFALLS.md` as spec-writing rules.
- 2026-09-29: lead #3 reordered lead #2's list: T-005 first (it unblocked the Owner's W5 step,
  due 2026-10-16), T-006 beside it (a plausible accident with data loss and an unapproved push),
  and the deploy gate's node-property variant later (a contrived edit that `tests` catches).
- 2026-09-29: H-10 done as recommended: T-003, T-004 and the W5 row merged and pushed in two
  steps, a preflight branch first (Linux, no deploy), then `master` (tests and a deploy). The
  deploy now runs every offline step before it ships; `.github/scripts/offline_suite.py` and
  its guard join the Level 3 list in `lead/QUALITY.md`. The T-004 round-2 residuals are one
  follow-up candidate, per the round cap.
- 2026-09-29: T-002 merged as `16e100e` (`--no-ff`, the tests-first commit kept) after a fresh
  review, 12 of 12 (`lead/reviews/T-002.md`), and pushed with the Owner's yes (H-6). The merge
  was clean (checks 27 of 27 on master, CI green on the pushed head), so autonomy is back to A1
  as the Owner approved in advance (H-7). The post-merge regeneration again changed only
  date-driven lines and the recent-commit list; left to the bots (`merge.after`).
- 2026-09-29: the Owner answered H-5 as recommended: both items. The Level 0 fix merged as
  `82acff3` (guard `e54f2bb` watched red first, fix `f1156eb`). Its post-merge regeneration
  changed only the date-driven parts of `docs/OWNER.md` and its recent-commit list, which
  `tests/test_owner_page.py` excuses; not committed, because the bots regenerate on the UTC
  date and the two would conflict before the next push. `lead/config.yml` `merge.after` says so.
- 2026-09-29: T-002 specced at Level 1 (the `KeyError` and `--write`'s exit status together:
  same file, same area, one fix commit each). The line-ending side effect is a separate Level 0
  item, because its writer turned out to be a test, not `publish_numbers.py`. Both put to the
  Owner as H-5.
- 2026-09-28: the Owner answered H-4 as recommended: autonomy stays A0 for the next task, and
  the lead proposes A1 again after one clean merge.
- 2026-09-28: T-001 merged (`0a3098d`, `git merge --no-ff`, the tests-first commit kept):
  review 12 of 12, verdict pass (`lead/reviews/T-001.md`). Milestone M0 (loop proven) reached.
- 2026-09-28: tripwire Q1 fired. The lead's own commit `f38ce82` put a CJK quote into
  `lead/STATE.md`, which broke the English-only rule on master; it was committed without a
  checks run and found by the T-001 reviewer. Fixed in `5959a8b`. **Autonomy demoted A1 to
  A0** (`lead/config.yml`). H-1's explicit approval (merge and push T-001) still stands.
- 2026-09-28: adopted the lead workflow (`lead/decisions/0001-adopt-lead-workflow.md`): lead/
  public and English, local-branches, merge commits instead of squash; `docs/OWNER.md`,
  `docs/BACKLOG.md` and `docs/DECISIONS.md` stay the project's records.

## Lead history

| # | Session | From | To | Why it ended |
|---|---|---|---|---|
| 1 | Claude Code desktop, local (opened in the parent folder) | 2026-09-28 | 2026-09-28 | Rotation rule: context at 50 of 100 parts of the window |
| 2 | Claude Code desktop, local (opened in this repository) | 2026-09-29 | 2026-09-29 | Rotation rule at a natural boundary after H-10; context judged past the threshold (not measured) |
| 3 | Claude Code desktop, local (opened in this repository) | 2026-09-29 | 2026-09-30 | Rotation rule at a natural boundary after H-11; context judged past the threshold (not measured) |
| 4 | Claude Code desktop, local (opened in this repository) | 2026-09-30 | 2026-10-01 | Rotation rule at a natural boundary after H-14 (T-007, T-008, T-009 pushed, nothing in flight); context measured at 55 of 100 parts of the window |
| 5 | next session, opened in this repository | | | |

## Log (newest first; keep the last ~20 lines)

- 2026-10-11: resumed the Owner-authorized technical release after execution permissions were
  restored. Fresh-origin full checks pass. T-020 preserves separate acceptance, first fix,
  named additive tests and absolute-timeout fix commits; final frozen source is unchanged.
  Linux preflight and independent completion review precede publication. T-016 remains
  separate until its observed upstream baseline and complete handoff checks pass.

- 2026-10-01: lead #5 check-in. Merged origin (six bot commits, `dd2d987`); every workflow's
  latest run green; M1 still running. Specced T-010 (Level 1: T-009's follow-ups, the page
  dropping a gate whose row is answered while its parked entries still fail the build) and
  dispatched it to a worktree. Did the Level 0 `.gitattributes` item on a branch (test watched
  red: both scripts "eol: unspecified"); fresh review 12 of 12, merged under A2 as `426d8f4`
  (`lead/reviews/L0-sh-eol-lf.md`).
- 2026-10-01: T-010 READY at `40d77ba`; fresh review 12 of 12 (AC 1 reproduced on the real
  files with the 2026-10-16 row answered and O2, O8, O9, O11 open: the page and the guard agree);
  merged under A2 as `47db199`. Regeneration moved only the recent-commit list (left to the
  bots). Worktree and branch removed. Push asked of the Owner as H-15.

- 2026-10-01: T-009 pushed: preflight run 36753548989 green (the Owner page 379 of 379 on Linux
  with its date a day ahead of UTC); `master` `26392ab..d033c90`; `tests` run 36754083925 green;
  no deploy; preflight branch deleted. Lead #4 hands off to lead #5 (rotation rule: context
  measured at 549,497 of 1,000,000 tokens; natural boundary, nothing in flight).

- 2026-10-01: T-009 review 12 of 12 (11 mutants caught; 101 forced dates; Python 3.12 run; the
  page proven independent of the clock). The lead fixed one sentence of its own correction text,
  then merged T-009 as `235b20c` (A2). Checks on master 29 of 29; `tests/test_owner_page.py` 379
  of 379. Regeneration moved only the recent-commit list (left to the bots). Worktree and branch
  removed. Pushing through a preflight branch (H-14).

- 2026-10-01: T-009 READY at `3af074d` (363 passed; CONTRACT HOLDS; acceptance-test fix
  `e3f3204` accepted: a synthetic gate's name contained "tomorrow"). Its executor found that
  master goes red on 2026-10-04 UTC: the Owner page's corrections list must have an entry within
  14 days and the newest was 2026-09-19. Measured by the lead (green to 2026-10-03, red on
  10-04). Two real, unentered mistakes fit: the page's answered gate shown overdue, and T-007's
  false "watched red" claim. Amended into T-009 before review; the lead wrote the text.

- 2026-10-01: H-14 pushed. Preflight run 36744394310 green on Linux; `master` pushed
  `a5bcce5..26392ab`; `tests` run 36744975640 green (`test`, `upstream-contract`,
  `backfill-roundtrip`); no deploy. Preflight branch deleted. M1 still running.

- 2026-10-01: H-14 yes. Origin had nothing new. Merged T-007 (`3fb1d3d`) and T-008 (`f1a767d`)
  at their reviewed heads; checks on master 29 of 29, exit 0, tree clean. Next: T-009 dispatched
  from the bookkeeping commit; the batch pushed to `preflight/h-14` first.

- 2026-09-30: T-007 round 2 combined re-review: 12 of 12, pass, red-team none (50 markup texts,
  20 row-lookup scenarios, 15 mutants of round 2's code). Decision: merge. Both Level 3 tasks
  wait for the Owner: asked H-14 (merge both, push through a preflight branch, then T-009 the
  same way). T-009's spec amended before dispatch: the template on the Owner page goes in a code
  span (entity-escaped brackets are still accepted by the guard; a follow-up).

- 2026-09-30: T-008 red-team: none (15 of 19 mutants caught; 31 near-miss values and names, 18
  invocations, CRLF emulated, `GIT_*` decoys: all held). Both reviews pass; decision: merge,
  waiting for the Owner with T-007. Four surviving mutants and an LF pin filed as candidates.

- 2026-09-30: T-008 independent review 12 of 12, pass (`lead/reviews/T-008.md`); red-team
  pending. T-007 round 2 READY at `19e3c60` (98 passed; named changes (c), (d), (e) each red
  first, as shown); the lead decided its two residuals before the re-review (variant B a
  follow-up; a line separator in a row fails closed) and dispatched the combined re-review.

- 2026-09-30: T-007 round 1 reviews: independent 12 of 12, pass; red-team 2 material. The guard
  accepted its own template and message pasted back, and markup that never renders (an HTML
  comment's `-->` taken as the arrow); a leak of `check` in the self-test harness would hide
  every red. Also a second table's same-dated row could answer a gate, against AC 4. Back for
  round 2, the last (lead decision in `lead/reviews/T-007.md`). T-008 READY at `1f9fba8`
  (CONTRACT HOLDS; the new checks' Windows median 9.85 s against a 10 s target, over it in 4 of
  10 runs); its independent and red-team reviews dispatched.

- 2026-09-30: H-12 yes (as recommended): autonomy A2. The Owner also agreed to H-13's plan for
  2026-10-16.

- 2026-09-30: T-007 READY at `8e14f10` (tests-first `521dfa6`: 12 red at that commit, no
  traceback; fix `37a9f3f`; stray line `8e14f10`); the lead saw 29 of 29 claimed and the contract
  holding by hunks (the kit script says BROKEN because the guard and its self-tests share one
  file). The executor measured a residual the threat model names: U+2192 counted as the
  conclusion's arrow, so a placeholder placed before the action text was answered by the
  table's own arrows. Amended before review (ASCII arrow only; named changes (a) and (b)).

- 2026-09-30: lead #4 check-in. The latest run of each of the six workflows succeeded. Merged
  origin (five bot commits) as `c597846`; checks 29 of 29, tree clean. Checked the 2026-10-16
  item early and measured its guard: with today forced to 2026-10-16, a bare `Resolved:` and
  `Resolved: no` both pass `tests/test_gates_get_reviewed.py`, whose docstrings say an audit
  watched both turn it red (the check is a substring test since `1762bd3`). Wrote T-007 (that
  guard, Level 3) and T-008 (the `snapshot-commit.sh` guard, Level 3), committed as `de567c0`,
  dispatched both in parallel (no file in common). Wrote T-009 (Level 1, the Owner page shows
  the answered 2026-09-18 gate as 12 days overdue in bold; after T-007). Asked H-12 (A2) and
  told H-13 (what 2026-10-16 needs).

- 2026-09-30: lead #3 hands off to lead #4 (rotation rule, natural boundary, nothing in flight).
- 2026-09-30: H-11 done. Preflight run 36669036422 green on Linux; pushed `d5bb216..3db4bf5`
  (40 commits); `tests` run 36669385087 green; no deploy. Preflight branch deleted; the three
  worktrees and task branches removed.
- 2026-09-30: T-006 round 2 passed its combined re-review (pass, RED-TEAM none); AC 6's 15 s
  bound on Windows is not met (median 15.2 s) and is recorded, not moved (lead decision in
  `lead/reviews/T-006.md`). The Owner approved H-11 as recommended. Merged T-005 as `0fa831a`,
  T-006 as `053fe0a` and the Level 0 branch as `b29c424` (a third commit, `893892b`, says in
  `CLAUDE.md` that the script now refuses its bots' mode off CI). Regeneration moved only the
  recent-commit list (left to the bots). Checks on master: 29 of 29, exit 0, tree clean.
- 2026-09-30: the session was resumed after the Claude Code process ended mid-round. T-006's
  executor had committed all of round 2 (`613f5bd`, `2958fc2`, `5d89eba`, `91e5d72`, `7a1a81a`)
  and left a clean worktree, but no READY report; the lead verified CONTRACT HOLDS and 118 of
  118 on the test file and dispatched the combined re-review. This clone's `user.name` checked
  unchanged. Merged origin's four snapshot commits as `0c02090`.
- 2026-09-30: T-005 round 2 passed its fresh re-review (12 of 12); decision: merge in the batch.
  T-006 round 1 passed both reviews (independent 12 of 12, red-team none) and went back once
  anyway: both reviewers found that "not run here" still lets the CI step pass. Two spec lessons
  added to `lead/PITFALLS.md`. Level 0 branch gained the W5 command line (`dcf3dfc`).
  Observed, cause not found: a reviewer's first local clone of this repository reached only 170
  of 651 commits (a missing parent object); a second clone minutes later was complete, and the
  main checkout's `git fsck --connectivity-only` is clean. A hypothesis, not a finding: a
  concurrent automatic gc while agents committed in worktrees. `git clone --no-local` avoids
  the hardlinked objects.
- 2026-09-30: T-006 READY at `e46cddc` (tests-first `0d9b8f7`, red on all 15 refused calls:
  the scratch identity rewritten and its uncommitted change gone). The lead saw CONTRACT HOLDS
  and only the two files in scope. Independent and red-team reviews dispatched in parallel.
  Level 0 committed on its branch as `0c6be16`: the `CLAUDE.md` note about the editor's
  client name was stale since `82e2470` (checks 28 of 28).
- 2026-09-29: lead #3 check-in. Merged origin (two production-probe bot commits) as `b1ecff6`;
  checks 28 of 28, tree clean; the latest run of all six workflows green; M1 still running.
  Wrote T-005 (Level 2): the Owner's remaining W5 step cannot be run safely today, because
  `bench/second_oracle.py` cannot select the adversarial cohort, paces calls faster than the
  free tier allows, and would overwrite the only copy of the earlier answers. Dispatched it.
  Wrote T-006 (Level 3) and dispatched it in parallel (no file in common): the regeneration
  script's bots' mode refuses to run outside GitHub Actions. Reordered from lead #2's list on
  purpose: a mistyped argument there is a plausible accident that rewrites the clone's git
  identity, can discard uncommitted work and pushes; the deploy gate's node-property variant
  needs a contrived edit and `tests` catches it.
- 2026-09-29: lead #2 hands off to lead #3 (rotation rule, natural boundary, nothing in flight).
