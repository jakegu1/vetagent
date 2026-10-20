---
id: T-047
title: Verify the bounded W40 archive and seal immutable source views
status: in_progress
level: 3
size: M
backlog: W40 prerequisite and live observation
depends_on: [T-046]
decisions: [B1, B2, B11, B15, P4]
---

## Context and goal

T045 supplies immutable offline enrollment/import; T046 supplies one native paired
packet. This task supplies the separate discovery-input transaction: verify the
existing owned archive, preserve every accepted byte/prefix and expose immutable
source views. It also fixes the shared storage, lock and trust ports needed by
T049/T050 so neither later task needs an edit to this module.

The three sequential source/review loops protect prospective selection and
irreplaceable evidence. Their cost is bounded engineering/review, existing local
disk and machine availability. Stop on an unverifiable binding, exhausted bound or
material contradiction; no protocol, scientific bar, source-rights or account
change is authorized. This task never enrolls, invokes a risk vendor, starts a
study or installs an OS task. Archive HTTP cannot start the scientific clock.

This is the adopted archive implementation contract. The lead completes its
dependency appendix below before the first acceptance commit. The later runtime
and scheduler specifications remain drafts until their own dependencies pass. T046 API
reference is `4dd847480659bc4c5100aade50dc10c04c45bb59`; its native SHA256 is
`ea483b0dc8afaebc4fe1e4b115af4930bb08f2427cc80e77390a1cc302831452`.
No placeholder is treated as a runtime receipt. Each loop requires actual Linux
source evidence before integration; a task branch may run ordinary CI for that
purpose within the existing engineering authorization.

## Scope and files

Only new `bench/w40_archive.py`, new `tests/test_w40_archive.py`, and one additive
unconditional `python tests/test_w40_archive.py` step in
`.github/workflows/test.yml` (ordinary step45). Preserve all previous44 steps,
conditions, jobs, pins, commands and build matrices exactly. Named old-test changes:
none. Preserve T044/T045/T046, their tests, the offline runner, engine/labels/rules,
active-study files, public archives/workflows, benchmarks/cache, access logs,
deployment and agent permissions. No package, service or credential is introduced.

Conflict search at the frozen native base covered configured `tests/test_*.py` and
`tests/fixtures/**`: no w40_archive/w40_local/w40_scheduler/w40-local or proposed
method/entry collision. Existing source_ref/plan_sha256/target_at/started_at,
intent/native_invocation/child_retired, endpoints and CI tests remain unchanged.
Refresh the search after the integrated base is bound, including every API below,
fixed schema/CLI field and error. Keep dataset/native assertions, registration/
reachability, deploy inventory, runtime pins and archive/privacy guards exact.

## Acceptance criteria

1. **Trust, shared ownership and offline entry.** Implement the fixed interface
   below. Default/help/plan/report are read-only and offline; seed only validates
   the configured already-local bundle. Normal CLI is exactly plan, seed and report
   with a fixed private config path and the two required reviewed hash-pin arguments
   specified below; it exposes no refresh/live/URL/owner/ref/date/
   clock/transport override. Every mutating API/CLI entry rejects actual CI or
   GITHUB_ACTIONS before any directory, lock, raw, source or OS-child operation.
   Do not clear flags or bypass the core/native guard. A missing/wrong executable,
   import origin, manifest or config is terminal source_drift. No import comes from
   the archive or working directory. Safe output is bounded to one MiB, fixed
   states/counts/hashes/UTC/ordinals with explicit omitted counts; never raw paths,
   addresses, URLs, account bindings, sentinels or arbitrary exception text.

2. **Exact existing-archive protocol.** The only source network operation is
   unauthenticated TLS-verified HTTPS GET to api.github.com for the private bound
   owned origin and refs/heads/master. Refuse arbitrary endpoints, alternate ref,
   redirect, auth/cookie/credential helper, proxy override and write verbs. Metadata
   Accept is application/vnd.github+json; blob Accept is
   application/vnd.github.raw+json; User-Agent vetagent-w40-local-source;
   Accept-Encoding identity; reviewed API version default 2026-03-10. Read one
   `/repos/{owner}/{repo}/git/ref/heads/master`, require exact ref and forty-hex
   commit, then `git/commits/{commitSHA}`, then exactly three non-recursive
   `git/trees/{treeSHA}` responses: root, bench, snapshots. Omit recursive entirely.
   Bind returned/requested SHAs, unique valid names, truncated=false, directory
   040000/tree and only `bench/snapshots/pools-YYYY-MM-DD.ndjson` 100644/blob inputs.
   Ignore other archive families explicitly. Reject mode/type/symlink/submodule/
   identity drift. Fetch new/changed allowed blobs by exact SHA; reuse unchanged
   bytes only after verification. Check declared length, Git SHA1 of `blob ` +
   ASCII length + NUL + bytes, and SHA256. Bound reading before parse/write; reject
   unexpected encoding, malformed/deep metadata JSON, oversized/incomplete body,
   premature EOF and hash mismatch. No base64 fallback, retries, Git operation,
   clone, pack, checkout or moving raw-branch URL. API availability/quota remains a
   runtime observation, never a source-code claim.

3. **Immutable whole views and source rows.** Advance the accepted view only after
   the entire candidate, all metadata and every prior byte/prefix verify. Source
   deletion or rewriting accepted bytes, including a previous trailing fragment,
   is terminal. Seal the exact interface below. Preserve original path byte order,
   line number and exact raw spans. Stage incomplete trailing lines privately;
   parse/enroll none of them until later completion preserves all previous bytes.
   Drain/hash/count oversized or malformed complete rows as row findings without
   dropping their bytes or falsely accepting an empty catalog. Metadata corruption
   is distinct from a malformed NDJSON row. No partial/truncated candidate becomes
   membership. A failed refresh retains the last accepted view and explicit
   unavailable/unexamined/gap counts. No source finding is a risk verdict.

4. **Complete offline seed and global allocation.** Before any task-owned seed
   write, reserve its actual worst simultaneous/retained copies within one GiB and
   the shared sixteen-GiB study allocation, plus actual free-space checks. Include
   staged input, all duplicate chunks/copies, metadata/manifests/indexes/pending
   files and terminal reserve; never multiply the allowance by an assumed copy
   count. Seed allows at most128 pool files, eight MiB/file, sixty-four-KiB stream
   buffers and parsed rows, twenty minutes total. Validate the complete root-bound
   ordered catalog/origin receipt and all commit/tree/blob/path/mode/length/hash/
   prefix/row mappings, not a history window. The root origin receipt derives from
   its actual owned Git objects and complete catalog verification; caller-supplied
   Git-shaped JSON is insufficient. Config pins the exact seed manifest/receipt
   hashes and bundle root. Seed makes no Git/network call and supplies no enrollment
   or earlier ingestion time. Oversize/missing/fabricated/mismatched input leaves
   the accepted view unchanged with an explicit incomplete-seed reason. Include a
   complete synthetic46-file catalog above64 MiB as a technical fixture, not a
   claim about a real inventory; exercise additional allowed files and all limits.

5. **Durable refresh admission and refusal.** One consumed reservation per
   fifteen-minute UTC slot and at most96 per actual UTC date, including failures,
   uninvoked and uncertain work. No restart reset/reuse. One source HTTP child and
   no concurrent study activity under the common writer. Maximum133 physical GETs
   per refresh: one ref, one commit, three trees, at most128 blobs; sixty seconds
   total including retirement, ten seconds per GET including setup/cleanup, one
   second between host starts; metadata at most one MiB each. Candidate metadata,
   blobs, retained failures/partials and all temporary/source writes share a
   pre-reserved64-MiB maximum. Fit full request time, allocation, current date and
   outer tick/study deadline before opening a request; recheck after persistence,
   pacing and child handshake. A candidate that cannot fit is wholly refused with
   explicit counts, even if the133-GET maximum cannot fit sixty seconds. Known
   401/403 is terminal source_permission; timeout/429/5xx retains last view and a
   gap, retry only a later unclaimed slot; corruption/drift is terminal. Reconcile
   actual durable headers after cancellation/failure before considering another
   request. No status/header premise is inferred from an unobserved response.

6. **Actual contained source child and restoration.** Source GET children begin
   disarmed and cannot contact a host before verified non-inheritable Windows
   kill-on-close Job assignment or actual tested Linux parent-death equivalent.
   Preserve private process creation identity/nonce, safe identity hash, durable
   intent/invocation/headers/partial body and verified retirement. T046 Job/identity
   helpers may be used only after manifest verification; its vendor allowlist and
   transport cannot be widened for archive requests. A dedicated source worker in
   this module enforces its own fixed protocol/caps. Source cleanup uses one fixed
   original0.4-second interval, observes both process exit and matching-identity
   retirement, never renews the budget, and retains unresolved ownership safely.
   Hard-kill actual parents before acknowledgement and after durable source entry
   with response blocked. A second actual process must verify that exact child
   exited, preserve consumed slot/attempt counts and bytes, refuse same-slot
   replay/concurrent writer, and either retain the previous view or commit only
   an already fully verified candidate. Unknown retirement or torn evidence stops;
   no repair/deletion/recreation of missing evidence. Exercise Windows locally and
   Linux ordinary CI. Test-only localhost routing is a Python injection with no
   production CLI/env bypass. Archive activity never starts a W40 clock.

7. **Contract and checks.** First commit only the new acceptance file, with exactly
   these seven stdlib unittest methods and direct unittest.main():
   `test_w40_archive_frozen_bootstrap_and_private_boundary`;
   `test_w40_archive_exact_rest_graph_and_blob_integrity`;
   `test_w40_archive_prefix_chunks_and_row_findings`;
   `test_w40_archive_seed_whole_catalog_and_allocation`;
   `test_w40_archive_refresh_ledger_caps_and_refusals`;
   `test_w40_archive_parent_death_and_fresh_process_restore`;
   `test_w40_archive_cli_and_complete_existing_runner`.
   Record a native missing-module red, then freeze all assertions/helpers/AST/main
   except named amendments. Include every AC2/3/4/5 negative and positive control,
   actual two-process kills, raw sentinels/ancestor junction/symlink into a real Git
   repository, scope-bound exact environment restoration and genuine CLI CI
   rejection. Ordinary tests never contact GitHub/vendors/production, register a
   task, benchmark or start W40. Focused CLI/direct/contract/native proof and frozen
   helpers precede one lead-granted exclusive complete45-step gate at exact clean
   HEAD. One controlled mutant here: replay an uncertain source slot. Keep total
   split-batch mutants at most3; T049 owns the other2. Preserve original44 bytes/
   ASTs/registrations and meaningful logs/exits. Independent review at least10/12,
   spec=2/invariants=2, adversarial none, all configured checks and actual Linux
   containment/restoration results precede integration. Unrun/mocked runtime facts
   remain gaps. One finding per repair commit, red before fix; no own merge/push.

## Fixed interface A — trust, writer and allocation (defined here; frozen later)

The following Python names/signatures and schemas are the dependency contract.
They use standard-library types only; reject unknown fields/versions. Fixture
injections are Python-only, never CLI/config selectors or mutable whitelists.
Canonical JSON is UTF-8, sorted keys, compact separators, finite numbers only;
SHA256 fields hash those bytes excluding their own final digest field. UTC is
normalized to microseconds/Z; object references are validated relative IDs below
their bound tree, never arbitrary paths. Every referenced byte/ancestor must be
regular, non-aliased, outside every Git worktree and revalidated before access.

- `verify_install(config_path, *, expected_config_sha256,
  expected_manifest_sha256, component)` returns an immutable FrozenBinding.
  component is exactly archive/runtime/scheduler. Both pins are required64-hex
  values supplied by the fixed reviewed action/command, never learned from files.
  Config schema w40-install-v1 has study_id_sha256, executable_commit, the pinned
  code_manifest_sha256, fixed roots (control/source/raw/safe/code/seed), bound
  manifest location, archive_origin, exact seed catalog/origin-receipt hashes,
  fixed task identity/selectors and already available reviewed quality/runtime
  gate references. It contains no own digest, action digest or future OS/arm
  receipt digest. Future receipt slots are fixed relative locations only. Policy
  limits are code constants, not overridable config.

  Hash direction is mandatory and acyclic: (1) w40-code-v1 manifest contains
  executable/import-closure files and resolved interpreter/PowerShell identities/
  hashes ONLY, no config/action/receipt or manifest-own digest; (2) immutable config
  pins that manifest; (3) fixed action carries BOTH expected config and manifest
  digests as literal reviewed arguments; (4) install/OS receipts bind actual
  normalized action/XML plus both digests; (5) scheduled-entry gate then arm receipt
  refer only backward. Any artifact digest is external to its own payload. Final
  config is never rewritten to insert later receipts. Quality gate references
  already known before installation do not point back to the final config/action.

  The final code manifest covers all three components, native/core/engine/labels/
  rules and trusted imports. Missing future components allow only source fixtures;
  production LIVE refuses. No production seed/state is reused across binding
  changes. Root prepares the final immutable code/config/action after all three
  source loops pass, before real seed. Each executable's stdlib-only phase0 accepts
  --config, --config-sha256 and --manifest-sha256 (PS equivalents in T050), verifies
  config bytes against the external pin, manifest bytes against its external pin
  and config's manifest pin, then self/interpreter/archive-bootstrap/whole closure
  before importing acquisition modules. Missing/mismatched pins fail, with zero
  automatic pin learning. Help or plan without bindings returns an offline
  configuration_required summary; it does not read arbitrary config or mutate.
  T047 source children inherit only that trusted import context and revalidate
  both pins in their fixed private request before acquisition imports. Do not add
  pin arguments or a bootstrap API to the unchanged T046 native child protocol;
  T049 validates its frozen child code/interpreter/import environment before
  launch and retains every existing native manifest/permit/handshake check.

  The shared task action digest is SHA256 of canonical ActionProjectionV1:
  schema=w40-action-v1, resolved executable path/SHA256 and the exact argv array
  [-NoProfile,-NonInteractive,-WindowStyle,Hidden,-File,resolved-wrapper,
  -Entry,tick,-Config,resolved-config,-ConfigSha256,expected-config-pin,
  -ManifestSha256,expected-manifest-pin]. Private paths stay in private bytes only.
  T049 derives it from the already pinned files/arguments; T050 parses actual OS
  action quoting into this same array and requires exact equality. It is not
  stored back into the code manifest or config. ClockEpoch has its separate fixed
  command projection and never impersonates the scheduled tick action.
- `study_writer(binding)` is a context manager yielding an opaque process-owned
  WriterLease: actual exclusive OS file lock held until exit/death, non-inheritable,
  fail-fast contention, no lockfile-existence substitute or stale-lock deletion.
  The final root-prepared installation supplies the fixed empty lock file; no
  read-only command creates one. Its bytes and bootstrap ledger writes are included
  in the initial inventory/reserve before ordinary writes.
  It serializes source and vendor work across processes. The lock is separate from
  consumed claims. All state mutations except request_stop require this lease.
  A runtime holding the lease passes that exact opaque owned object into nested
  archive seed/refresh/recovery/reserve/settle; none reacquires study_writer or
  accepts a boolean/serialized stand-in. Reentrant acquisition refuses immediately.
- `reserve(binding, lease, *, reservation_id, owner, ceilings)` returns an immutable
  AllocationTicket. Closed owners: bootstrap/seed/refresh/chunks/runtime/native/
  terminal/scheduler; closed areas: the six bound roots. The unique64-hex ID cannot
  be reused. Ticket binds study/config/code, owner, per-area ceilings, prior ledger
  head and its digest. The archive module alone appends the shared allocation
  journal. Count initial frozen code/config/staged input and every subsequent
  retained/pending byte plus outstanding ceilings; enforce total<=16 GiB and actual
  per-volume free space before writes. Reserve a fixed8-MiB terminal/control allowance before
  ordinary work, included in the16 GiB. A reservation includes its own worst-case
  bookkeeping and all writes performed by its owner; no uncharged side tree.
- `settle(binding, lease, ticket, *, inventory)` returns an AllocationReceipt only
  after verifying the ticket's whole retained-byte inventory and child retirement.
  Only proved never-materialized unused ceiling is released; all retained/failed/
  pending evidence stays charged and immutable. An uncertain ticket stays fully
  charged. This never reopens a logical attempt/refresh slot. No automatic pruning,
  overwriting or evidence deletion. Disk failure is terminal, not an OS-quota claim.
- `request_stop(binding, *, reason)` writes one bounded immutable stop-request
  outside the writer lock using the pre-reserved terminal allowance; repeated
  identical stop is idempotent. `stop_state(binding)` is read-only; present/torn/
  unreadable stop evidence always prohibits new acquisition. Reasons are fixed
  categories. Partial stop persistence is stop_unknown, never absence. T049/T050
  consume this same primitive; they do not invent another stop or allocation log.

Journals use bounded immutable contiguous hash-chained records with durable write
and readback. A partial/orphan/conflict is terminal, never silently repaired or
ignored. Do not add a mutable index that can override the committed chain. Safe
report details may be omitted with counts; complete accounting may not be omitted.

## Fixed interface B — source transaction and accepted view

- `seed(binding, lease, *, clock=None)` -> SourceResult.
- `refresh(binding, lease, *, live=False, deadline_mono, clock=None,
  transport=None, hooks=None)` -> SourceResult. live must be explicitly true; the
  frozen runtime authorizes it only after its arm/start/clock/stop checks. No live
  refresh CLI exists. Default real transport is the contained source worker;
  transport/hooks are test-only Python injections. clock has utc(), mono(), async
  sleep(seconds); before any request the caller's fixed continuity/stop checks are
  sampled again. The effective absolute deadline is min(now+60, deadline_mono),
  and the full ten-second request/cleanup must fit the actual UTC date as well.
- `recover_archive(binding, lease)` -> SourceResult is strictly offline and is
  required at every later runtime startup before source/vendor work.
- `accepted_view(binding)` -> AcceptedView or None is offline and verifies all
  committed metadata/raw mappings; it never repairs or fetches.
- `iter_complete_rows(binding, view, *, after_view_sha256=None)` streams only new
  complete SourceRows in view sequence, path byte order, original line order.
  It verifies the predecessor chain and exact chunks, not a mutable current file.

SourceResult contains schema=w40-source-result-v1, state=accepted/gap/terminal,
fixed reason, view_sha256 (possibly prior/None), transaction_receipt_sha256 and
allocation_receipt_sha256 plus explicit examined/unexamined/partial counts. The committed transaction receipt
binds seed or refresh, study/code/config, previous source ledger head, consumed
slot/date when applicable, attempts/invocations/statuses/retirements, allocation
ticket, candidate/view hash and final state. Its ledger is owned solely by
this module; T049 reads it and never rewrites counters or accepted views.

AcceptedView schema=w40-source-view-v1 binds study/code/config/origin, sequence and
previous_view_sha256, archive commit and three-tree chain, complete ordered catalog,
the already committed transaction-claim/allocation-ticket hashes and view_sha256. Each catalog entry binds
original allowed path, mode/type, blob SHA1, full bytes/SHA256, complete-prefix
bytes/lines/SHA256, previous full/prefix boundaries and hashes, trailing fragment
bytes/SHA256, and immutable chunk IDs with exact bytes/SHA256/original line ranges.
Chunks and retained whole blobs are charged wherever both exist; chunk reuse
cannot hide duplicate storage. View hashes never include outcomes or ingestion.
SourceRow binds view/path/blob/chunk SHA, original line, raw byte offset/length/
SHA256 and raw bytes up to64 KiB; oversized rows instead expose fixed row_cap plus
retained-span hash/count. Malformed rows expose fixed invalid_row plus exact span.
Every excluded/partial row stays discoverable without becoming a parsed member.

Commit direction is acyclic: allocation ticket -> source claim -> raw/chunks/view
-> source result receipt -> allocation settlement. A view never hashes a future
result/settlement that itself hashes the view. accepted_view exposes the new view
only after both the matching source result and independently verified allocation
settlement exist. A clean pending completion can append only that verified offline
settlement; a torn/conflicting record cannot be repaired. Settlement inventory
includes the source result, with its own fixed bookkeeping charged separately.

## Evidence, threats and rollback

READY shows every criterion/test mapping, exact dependency/source/test/workflow/
fixture/log hashes, first red, focused positives/negatives, actual source parent
kills and fresh-process restoration on Windows/Linux, caught single mutant,
scope/AST comparison,45/45 native exit0 and all tracked bytes before/after. Seal
private runners before full and never edit a sealed member. Private raw evidence
stays outside all Git; safe repo/console output contains no raw material.

Threats are accidental or hostile malformed metadata/rows, moving prefixes,
reparse ancestors/import shadowing, inherited environment/proxies, disk exhaustion,
slow/blocked body, lost acknowledgement, process death, stale lock/slot and a
misleading safe report. Preserve distinction between absent and unobserved.
Rollback is terminal stop, original bounded child retirement and byte preservation;
no source deletion, automatic retry, OS task, permission or scientific change.

## Adopted dependency and dispatch bindings

Implementation quality base: `1de0259c0036878d3be5d2d83429fc1342f454f0`. Actual combined local
gate: forty-four of forty-four, native exit zero, all 966 tracked files exact.
Actual feature Linux run39178913343 passes every required command, upstream
contract, backfill and both independent locked builds at that exact source.
Local gate log SHA256: `65979ab6c1d26c8b47b91703103760a81f060d58ce74f7e69b6b573e4b6eb81c`.
Native manifest actual checkout JSON SHA256: `a49acb9cecfb02608a83466cbe8d873e854dc9045082818527d4b1bd44db3328`.

- T044 source `6d300a30654d1bb9bcfc6bf39ac2af07caa041e1`; canonical SHA256
  `3ec1e7688240fbd705b386ee7680758e6606bb9354938e994927a440e6e4b8f4`; checkout SHA256
  `194ed61df3f45f99c87a7e56a2d5cb5c093a34395d911fc0fa82a223271cd689`.
- T045 source `2090c3da3c9ed94767b543b05b8a7166f66e17cc`; canonical SHA256
  `2e312e319229402088f6f1aaf15e53460d41a56468d6dd7d249c4123734e140d`; checkout SHA256
  `68195ebb75d29c1039dbcf48d7e689d641db7c3cb912ccc26858df6ba0b1591c`.
- T046 source `4dd847480659bc4c5100aade50dc10c04c45bb59`; canonical SHA256
  `ea483b0dc8afaebc4fe1e4b115af4930bb08f2427cc80e77390a1cc302831452`; checkout SHA256
  `ea483b0dc8afaebc4fe1e4b115af4930bb08f2427cc80e77390a1cc302831452`.

Exact adopted A/B contract text SHA256: `96be547868e703c289533e00738a3d73fbcc03f159dc330dcd875a7a82f4dc4c`.
T046 source decision is lead/reviews/T-046.md; its two ordinary rounds
remain spent and the final bounded privacy/retirement source verdicts pass.
Independent split-spec preflight finds no material ready-spec obstacle;
report SHA256 cc2bf4754baf1d1dfd30336677445e65ab78c4ce9f800d7d1645ac884921e2cf.

Only archive source implementation is dispatched. The finite T044 real
readout remains incomplete. Exact master CI, the sole root native control,
final frozen installation/seed, actual child-import origins and two real
unarmed scheduled entries remain separately bound runtime gates. No LIVE,
schedule, new scientific clock or ownership proof is supplied by adoption.

## Named recovery amendments

### R1 - Bind a direct Windows interpreter instead of a redirector

The acceptance-only commit remains `aa01264dc55b1afd2bdcfbfdad7de57d7c36ac02`.
Its frozen `prepare_code()` always bootstraps into a venv, and `Fixture.__init__`
always records that executable/config. Actual Windows positive and parent-death
controls reached ready with matching nonces but different Popen/child PID and
creation identities; neither request reached HTTP. The identity invariant must
remain strict. A launcher configuration is the defect, not an unavailable source.

Named test-helper changes only: on Windows, `prepare_code()` shall run the direct
verified base executable, relocated outside Git with its actual stdlib/DLL closure
as needed. Do not create/use a venv redirector for the worker. The existing fixture
interpreter record keeps the same fields; its `pyvenv_cfg` is None only for an
actual direct base (prefix equals base_prefix). Existing venv configuration remains
explicitly recorded where used on Linux. Child-only Python startup isolation may
remove PYTHONPATH/PYTHONHOME/PYTHONSTARTUP and set safe-path/user-site/bytecode
controls, while preserving actual CI flags. Verify actual origins and interpreter
bytes; never follow an unpinned base, relax identity equality, synthesize a ready
identity, add a production override or edit T046. All seven method names and their
existing behavior/identity/retirement/CI assertions remain exact.

Within `w40_archive.py`, the matching explicitly pinned direct-base configuration
may use `pyvenv_cfg=None` only with actual equal prefix/base_prefix, the direct
executable's path/hash and complete trusted import closure, no active venv config,
and the same empty-site/user-site/origin checks. A non-null venv config retains
its existing strict path/hash/include-system-site-packages=false checks. The
manifest/config hash DAG and all other interface fields stay unchanged. Do not
learn pins or create a production selector. Commit the named fixture correction
separately from the source compatibility correction, retain the actual original
red, and prove actual contained local requests/parent death afterwards.

### R2 - Deliver malformed response fields instead of raising in the fixture

`Transport.__call__` builds a dict with explicit content_length/content_encoding
and duplicate `**overrides`; its length/encoding controls raise TypeError before
the source sees those fields. Correct only that helper to construct defaults then
merge the supplied override dict. Preserve every existing response input and
assertion. Do not classify this unobserved TypeError as observed malformed HTTP
to turn the suite green. Retain the red and show the bad fields are delivered to
the real validator, which refuses them; the unchanged positive still accepts.
Commit as a separate named test-helper change.

### R3 - Make the above64-MiB seed fixture physically distinct

The large seed method gives all46 paths identical bytes. Content-addressed input,
whole blobs and chunks can therefore share one physical object. Its measured
retained-byte result is not comparable to the sum counting the same bytes46times.
Keep source deduplication and actual accounting; do not invent stored bytes or
create unnecessary per-path copies merely to satisfy that premise.

In `test_w40_archive_seed_whole_catalog_and_allocation` only, retain its46 exact
paths,64 lines per file, padding-only row shape and every existing assertion.
Before Fixture construction, salt only the otherwise unused padding value with
that file's deterministic ASCII filename. Add an assertion that the46 complete
file hashes are distinct. This strengthens the original intended above64-MiB
technical seed premise and changes no selection, outcome or production data.
Retain the original deduplicated red and verify the actual physical seed/source/
chunk bytes stay within the unchanged budgets. No additional synthetic coverage
or real inventory is implied. Commit this named fixture-input correction alone.

All other acceptance helpers/assertions and old44 tests remain frozen. Root owns
the separate truthful D-checkpoint task and any subsequently named baseline bind;
it is not a reason to bypass the live date guard here. These amendments repair
observed fixture premises before first READY; no scientific gate changes.

### R4 - Close the backward-only prior-gate and production-admission port

The initial interface requires prior quality/runtime gate references but does not
define their records. The frozen source fixture contains `quality_gates=[]`.
That is a technical fixture, not production eligibility. Complete the interface
before the T049/T050 acceptance commits; do not add future receipt references to
the final config or permanently refuse every real transport as a substitute.

`quality_gates` is a list of at most three unique records with exactly kind/path/
sha256. Closed kinds are source_quality, quota_pilot and native_control. Each
path is exactly `quality-gates/<kind>.json` below the bound control root; SHA256
is an external pin over its exact bytes. Reject unknown fields/kinds, duplicate
kinds and other paths even for offline validation. Empty or incomplete references
may support offline/source fixtures only. References and their evidence are
initial retained allocation, never an uncharged external tree.

Each referenced canonical JSON payload is at most64 KiB, with exactly schema,
kind, source_commit, source_files, evidence and result. Schema is
`w40-prior-gate-v1`; kind matches its reference; source_commit is forty lowercase
hex characters. evidence has exactly path/sha256; path is exactly
`quality-gates/evidence/<kind>.json` below control, a bounded existing root-
verified evidence receipt of at most one MiB. Its exact pinned bytes must exist.
Every read obeys the existing regular-file, alias, ancestor and bounded-read
rules. No digest is learned, no arbitrary path/URL is selected and no network
verification is introduced. The root supplies these externally pinned attestations
only after verifying the underlying existing evidence; fixture JSON never earns
actual quality, native, OS, quota, capacity or study credit.

source_files is a sorted unique list of records with exactly path and
canonical_sha256. Match the mandatory set for that kind exactly. Every record
must match an already verified code-manifest file and SHA256 of its actual code
bytes after CRLF-to-LF normalization. The manifest still pins exact actual bytes.
The source_quality set is the six already frozen T046 FROZEN paths plus
bench/w40_native.py, bench/w40_archive.py, bench/w40_local.py and
tools/w40-local.ps1. The native_control set is the same six FROZEN paths plus
bench/w40_native.py. The quota_pilot set is bench/goplus_quota_probe.py only.
Earlier quota/native receipts may have earlier source commits, while their
required unchanged file hashes must match the final installation. source_quality
source_commit equals config.executable_commit. No prior gate payload may name
the final config/code-manifest/action digest or a future OS/entry/arm receipt.

Closed result shapes:
- source_quality: passed=true, offline_steps, linux_steps and master_steps are
  equal integers at least47, locked_builds=2, independent="pass", redteam="none".
  These are root-verified complete configured executions at that source, not
  a workflow summary or skipped job. The minimum covers the three split loops;
  it is an engineering gate, not a scientific threshold.
- quota_pilot: completed=true, native_exit is integer0 or1, availability is a
  boolean copied truthfully from the sole finite real pilot. Completion does not
  require availability=true and supplies no daily allowance/reset/capacity claim.
  Retain the actual unsuccessful availability reading and all unknowns.
- native_control: seam_verified=true, native_exit=0, labels=0,
  scientific_start=false. Only the separately verified non-cohort native control
  may supply this; the original failed control stays failed.

Add the fixed read-only Python port `verify_live(binding) -> None`: verify the
current binding and all three complete pinned gates, required component/code
coverage and a non-null verified PowerShell identity; otherwise raise the fixed
source_drift error. It mutates nothing and has no CLI/env/config bypass. Call it
before default real refresh makes any claim/allocation/raw write, and before a
real-source child opens HTTPS; include its elapsed work in the original admission
deadline. Existing explicit Python transport/local-loopback injections remain
technical fixtures. Real default transport cannot gain eligibility from a hook.
T049 must call this same port before production arm and each production work
admission; T050 uses it before production activation. Their future scheduled/arm
evidence remains separately backward-bound in the already fixed DAG. This port
does not waive those gates or begin a scientific clock.

Named acceptance addition: preserve all seven method names, old assertions,
inputs, helpers and main. Only append finitely bounded new subtests to
test_w40_archive_frozen_bootstrap_and_private_boundary and add a dedicated
fixture-only prior-gate builder helper. Cover empty/incomplete production gates,
unknown/duplicate kind, wrong path/hash, missing evidence/component, changed
source bytes and a structurally valid technical positive, at most ten cases.
The actual default path with empty fixture gates must fail before any mocked
transport invocation or new claim/write; offline reads/seed and existing explicit
local transport controls retain their original behavior. Synthetic gate positives
never contact a host or assert real review/runtime credit. Commit this named test
addition first and alone, record its red on the old source, then freeze it before
the separate source fix. Original R1-R3 and all other test ASTs remain exact.

### R5 - Bind the separately reviewed due-checkpoint dependency

2026-10-20: the separately reviewed T051 source is published at
`9dc8686a445c43fd568555b140bf715d9dbfdbac`, retaining scheduled archive inputs by
normal merge. Its final source-bound local gate actually passes44 of44, native
exit zero, with all974 tracked files exact; log SHA256 is
`6531b11f730212e158c4c1f3806601639d67931515db4cc56f24576b62ca7ddd`.
Actual master push run39392487756 checks out that exact SHA and passes every
ordered44 command, upstream/backfill jobs and both independent locked builds.
Benchmark remains skipped. Independent T051 review is12/12 and red-team none.

Normally merge this exact accepted dependency before the final T047 gate. The
sole named prior-test baseline update is `tests/test_experiment_d_deadline.py`
from the accepted T051 task; its canonical Git-file SHA256 is
`b0df37b193768d82cf34213724ce928ea0d5b78a5be05994068667abafaae525`.
It preserves the approved date and existing undecided rule, and adds separation
of actual source and private pending fixtures. Do not edit that accepted file or
use the amendment to bypass its guard. All other old test files, the configured
original44 commands, offline runner, native/core/engine sources and frozen pins
remain exact to the original1de dependency. New scheduled data and their normal
generated documents are preserved separately from executable-source equality.

The T047 acceptance file remains frozen at
`841c063deca8e39edba71b9bd64769cac3497f8f17d52a490b90f082bffb9b2b`.
No source/API, acceptance assertion, fixture, allocation or scientific rule change
is authorized by R5. This is dependency reconciliation, not a new native runtime
or LIVE proof; failed native controls and all unavailable gates remain failed or
unavailable until a separately bound verified correction supplies actual evidence.

### R6 - Verify complete ordinary refresh bodies within the original allowance

2026-10-20: the independent functional review of6eb0f98 reproduces a normal
six-GET refresh with a9,218,250-byte complete Git blob containing150 valid JSON
rows of61,455 bytes each. These are an ordinary archive/NDJSON positive, not a
claim of150 valid admitted pool identities. The blob is below the unchanged
64-MiB refresh increment allowance and above the8-MiB seed-only per-file bound.
It is retained but _attempt_witness and _verify_transaction mistakenly apply
FILE_CAP+1 to body.bin, raise source_corrupt, and leave one claim/six attempts/
zero results with no accepted view. This blocks later valid source work. Preserve
that exact independent red and the original complete45 outcome separately.

The8-MiB per-file cap continues to apply to offline seed input. Refresh request,
wire reading, retained attempt verification and transaction re-verification must
instead agree with their original admitted body allowance. Verify before parse or
publication and preserve the unchanged64-MiB cumulative increment,60-second
refresh, bounded reads, source hashes, per-date/GET limits and16-GiB allocation.
Use the verified immutable request/permit body bound or the already fixed maximum
where appropriate; do not invent an unlimited read, enlarge a budget, drop source
bytes or change a row finding into a token/risk verdict. Existing over-limit and
seed-cap refusal assertions stay exact.

Named acceptance change, committed first and alone before the source correction:
append one bounded ordinary large-blob subtest to
test_w40_archive_exact_rest_graph_and_blob_integrity. It supplies one complete
blob strictly above8MiB and below10MiB, valid JSON rows each below64KiB, and an
otherwise exact small six-GET fixture graph. Assert one accepted committed view,
exact retained bytes/blob hashes, all complete row spans/findings preserved,
one result for the claim, and all actual request/storage accounting. Semantic
pool eligibility is not inferred from NDJSON syntax. Keep all original seven
method names, every existing assertion/input/helper/main and R1-R5 unchanged;
only a dedicated bounded fixture builder may be added if required.

Also read the committed state in a fresh actual offline OS process through the
existing bound report/verification port. It must verify the same view/attempt/
transaction/allocation chain with zero network, new claim, request or history
repair. Keep its runtime/import/CI/private-boundary checks real as allowed by the
existing fixture contract; no new production override or path bypass is added.

Record the new test's meaningful old-source red, then freeze its exact bytes and
apply only the bounded body-verification source correction in a separate commit.
Reproduce the normal positive and fresh readback, old seed-cap/over-limit tests
and existing single-mutant contract as needed. No new distinct mutant or broader
audit is authorized. The known-bad6eb complete45 is historical evidence only;
final fixed clean source requires its own true prior freeze, complete45, actual
Linux/builds and genuinely completed applicable independent reviews. Neither the
platform-interrupted review nor a later functional PASS supplies RED-TEAM none.
