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
