# W40 split: immutable interfaces and complete coverage

Adopted interface map: T047 -> T049 -> T050, Level3/M each; dispatch requires actual bound
reviews/manifests and integrated green44/45/46 respectively. Native API reference
is 4dd847480659bc4c5100aade50dc10c04c45bb59. Each task appendix gates its source implementation; this map grants no LIVE authority.

| Frozen seam | Sole owner and immutable interface | Consumer obligation |
|---|---|---|
| A: trust/bootstrap | T047 verify_install(config_path, *, expected_config_sha256, expected_manifest_sha256, component); code/import/interpreter manifest -> immutable config pin -> fixed action with BOTH external pins -> install/OS -> scheduled gate -> arm | No manifest-own/config/action hash cycle, pin learning or future receipt in config; every phase0 verifies before imports/OS calls; final binding before real seed, no mid-study rewrite |
| A: writer/allocation/stop | T047 study_writer/reserve/settle/request_stop/stop_state; process OS lock, unique ticket, common16-GiB inventory/outstanding ceilings and terminal reserve | Same opaque owned lease passed into nested source/runtime; no reacquire/bool/serialized lease. One service charges all duplicates/free space; uncertain stays charged, no resets |
| B: source | T047 seed/refresh/recover_archive/accepted_view/iter_complete_rows; fixed versioned view/catalog/blob/chunk/original-line/hash and separate source ledger | T049 accepts complete verified views in committed order; no accepted-prefix mutation or source ledger writes; admitted-only core128-source/64-MiB chunks plus exact original mapping |
| C: runtime/ordinary entry | T049 lifecycle/entry_receipt/stop_status; admission/native-budget/start/tick chains; TickEntry + TickReceipt | T050 calls same unarmed/live tick action, never declares scheduler origin from an entry alone; source/code commit stays independent of archive commit |
| C: epoch/status/scheduler intent | T049 freezes ClockEpoch/status ports and w40-task-operation-v1 before tests; T050 implements | Fixed5-second CIM helper, Linux64-byte boot_id, safe epoch hash; absent/unproved is terminal; pending task intent blocks arm/live, no later runtime edits |
| D: OS ownership/proof | T050 fixed wrapper/Python bridge; exact task XML/install/readback, two correlated OS instances + completed unarmed receipts -> SchedulerGate | Same T047 allocation/writer; closed prepare/complete protocol, no cross-process lease transfer; T049 verifies actual gate/status, arbitrary JSON/manual/mock/exit0 never arms |

| Original AC | Complete destination/scenario mapping |
|---|---|
| 1: offline/private/frozen | T047 AC1/A; T049 AC1/6/C; T050 AC1/3: default/help/plan/report offline, seed no enrollment/start, arm no network, unchanged unarmed tick, actualCI-before-write, import shadowing/source drift, raw sentinels/all ancestor aliases, separate roots, bounded1-MiB safe reports/omissions |
| 2: archive/seed | T047 AC2–6/B: exact ref/commit/three nonrecursive trees/raw media/length/Git framing/SHA; wrong ref/SHA/mode/type/recursive/truncated/encoding/deep JSON/EOF; prefix rewrite/deletion/trailing completion;128 files/133 GET/96 daily/15-minute slot/1-second gap/64-MiB candidate/60-second refresh/10-second request; complete synthetic46-file >64-MiB seed, additional files/8-MiB per-file/1-GiB worst-copy/64-KiB stream+row/20-minute seed; fabricated/missing catalog/origin, malformed/oversized retained rows, whole-candidate refusal,401/403 terminal vs429/5xx/timeout gaps, same-slot no replay |
| 3: membership | T049 AC1: actual ingestion/order before outcomes, birth+24h/equality/missed boundary, first-pool identity/65th arrival/permanent exclusions/global10,000 across restart/subplans, no replacements/early call/retrospective selection, original row mappings, explicit source/late denominators |
| 4: admission/evidence | T047 AC4/5 + T049 AC2/3: one global activity/physical child,64 GoPlus/1,216 actual-date attempts,19/16 native caps/retries, all fixed host gaps,30-second/20-minute/25-minute lifetimes, midnight/slow writes/policy/handshake rechecks, storage/free-space refusal, all retained failed/cache dependencies, reserve both label+eligibility, known overlap with unknown endpoints fails, held-out GoPlus/floor/oracle/same-moment unchanged |
| 5: clock/start/stop | T049 AC4/6 + T050 AC5: first failed actual due entry starts; uninvoked/registration/seed/arm/archive/T044/non-cohort do not; lost first proof start_uncertain, no replacement, forged future flags, changed/unavailable epoch/bracket continuity, terminal stop/restart/no extension, exact30 days/no18-count early stop, core declared-start limitation and unfinished/outside-window denominators |
| 6: restore/scheduler | T047 AC6 source + T049 AC5 native: actual Windows/Linux parent kills before ack/after blocked entry, fresh-process matching child death/zero re-ask/counters/bytes/start, core-success producer-loss reconciliation, distinct due slot once/concurrent refusal, missing/corrupt/junction raw/dependencies/torn histories terminal. T050 AC2–4: exact owned XML/action/task identity, current-user Limited/Interactive, PT1M/logon/IgnoreNew/PT26M/no wake/restarts, stale/conflicting ownership, two actual unarmed firings, busy-writer stop/uncertain cleanup/disable/readback/exact uninstall, all availability gaps |
| 7: quality/evidence | Each final AC: acceptance-only native red/frozen methods/helpers/AST/main, original44 exact plus additive steps45/46/47, scoped CI restoration, ordinary offline fixtures, focused/CLI/contract/actual-child proof before exclusive full, immutable helper seals/logs/exits/hashes, fresh independent>=10/12/spec2/invariants2 + adversarial none, actual Linux before each integration, no skipped/mock/runtime substitution |

Finite methods: archive7, runtime7, scheduler6, named in their specs before tests.
Controlled mutants across the entire split: source uncertain replay1, runtime
membership1 and clock/start/stop restart1, scheduler0. All originals remain exact.
Source readiness never grants LIVE: actual T044/native GET+RPC/Linux, final private
installation/config/seed and two real scheduled firings remain root gates; only
recoverable admitted vendor entry starts30 elapsed days. No unresolved policy or
technical choice is delegated to model output; actual bindings and host proof
availability are evidence prerequisites, not new Owner permission questions.
