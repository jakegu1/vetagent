---
id: T-027
title: Separate recorded owner-power regression evidence from live RPC monitoring
status: draft
level: 3
size: S
depends_on: [T-015, T-024, T-025]
decisions: []
backlog: none
---

## Reproduced problem

During T-024's independent review a process-wide network audit hook made the complete
configured suite fail at test_owner_powers.py. Its existing real-contract case calls
backfill.rpc_batch for three Ethereum bytecodes. The ordinary runner succeeds with RPC
available; the blocked runner reports missing-bytecode failures. Consequently the job
described as offline depends on live public RPC availability. This is separate from the
new date/replay/copy acceptance tests, which pass with external network blocked.

## Next specification, not an implementation authorization

Review on 2026-10-17. Preserve all current power, proxy and disclosure assertions. Explore
an exact recorded-bytecode fixture with source and block provenance for deterministic
algorithm regression, keeping live RPC contract monitoring a distinct observation with
explicit observed/unobserved status. Do not invent bytecode, remove controls or silently
drop live coverage. A recording is historical evidence, never proof of current availability.

Before ready: identify the existing monitor's RPC coverage, allowed files, original test
assertions that must remain frozen, immutable acceptance contract, valid fixture provenance
and the actual red produced by blocking network. Complete configured checks should then
pass without external network while the separate live monitor preserves its own semantics.

Budget: no new paid service or provider, one small task, at most two review rounds.
Stop if fixture provenance or existing monitoring coverage cannot be established.
