# Work backlog (BACKLOG.md)

> The queue. One line per item, a stable id, and **how it will be verified**.
> `tests/test_backlog.py` enforces the shape; `docs/ROUNDS.md` records what actually got
> done and when.

## The rule that keeps this from becoming a wishlist

**Every open item names a verification.** A command, a test, or a measurement that will
say whether it worked. An item that cannot name one is not a task, it is a hope, and it
gets deleted rather than carried.

This is the same standard the rest of the repository is held to, and it exists because
three plausible-sounding features were killed by measurement in a single day: LP-burn
detection (fired on 58% of good tokens), reserve-event backfill (unaffordable on free
RPCs), and using market activity to settle sellability (traded away the one attack the
check exists to catch). None would have been caught by a plan.

**Ids are permanent.** A closed item keeps its number and its outcome, including
`Rejected`, because "we looked at this and decided not to" is the most useful thing a
backlog can tell the next person. `Done` items name the round that did them.

**What does not belong here**: parked *ideas* that would change direction (→
`OPPORTUNITIES.md`, which has review dates and a test), decisions already taken (→
`DECISIONS.md`), and anything the scorecard already enumerates as a gap — link to it
instead of restating it.

| State | Meaning |
|---|---|
| `Open` | Queued. Must have an owner and a verification. |
| `Blocked` | Cannot start; the blocker is named. |
| `Done Rn` | Finished in round n. |
| `Rejected` | Measured and dropped. The evidence stays. |

---

## Mine

| # | Item | Why it matters | Verify | State |
|---|---|---|---|---|
| W2 | Deployer history as a risk dimension | One of two dimensions still uncovered on the scorecard | `python bench/scorecard.py` shows 10/11 dimensions covered, and the new signal separates dead from alive by >10pp on `bench/results.json`. Needs a contract-creation source first; Etherscan-family APIs are keyed | Open |
| W3 | Grow the genuine adversarial cohort beyond 9 | Every headline claim rests on it, and 6 of 17 still read `low` once liquidity-derived signals are stripped | **9 → 17 in R13** by harvesting recent days (B14). 13 of the 17 come from the last week of data, 3 from eleven days spanning a year. Still short of the ~40 a discrimination claim needs; the lever is more recent days, or a deeper sample per day — `max_pools` takes 250 of the 1,500–2,300 available | Open |
| W4 | Cut the unknown rate below 10% | 17.9%, worth 4 scorecard points | **Blocked** on W5. Measured 2026-09-06 after the chainID fix: of 100 unknowns, **1** is our side — down from 62. 57 are the simulator having no record of the token and 42 are its buy leg reverting. Both are one vendor's limits, and the remaining engineering on our side is done | Blocked |
| W6 | EVM holder concentration | The last uncovered dimension | **Blocked** by `DECISIONS.md` B2 — the field belongs to the held-out oracle. Needs W1's bytecode route or a different source | Blocked |
| W7 | Point-in-time evaluation from the snapshot archive | The benchmark scores "now" against a retrospective label, so it cannot answer "would it have warned me". The archive records contemporaneous state and the labeller never reads it | **Blocked** on archive depth: needs ≥60 days of contemporaneous snapshots, 3 as of R11. Accrues on its own via `snapshot.yml`, so the wait is the work | Blocked |
| W17 | **Score** owner powers, rather than only disclosing them | Blocked twice over: the cohort is 9, and the instrument finds 31% of what it looks for | **Blocked** on W18 and W3. Widening the list from the oracle's labels would fix recall and void the benchmark (B2), so it needs a source that is not the oracle | Blocked |
| W18 | A selector source that is not the labelling oracle | The bytecode scan finds 31% of the powers that exist because contracts name these functions in more ways than a fixed list holds. Deriving the list from the oracle's labels would fix it and void the benchmark | A public signature directory, or PUSH4 extraction plus a lookup. Verify by re-running the recall measurement against the oracle: it must clear ~80% before any discrimination claim means anything | Open |
| W8 | Consolidate `DECISIONS.md` | 55 rows against its own stated ceiling of 40. The file says test-enforced entries that never failed should collapse to one line | `python tests/test_decisions_enforcement.py` stays green and the stated row count reaches 40 or fewer | Open |

## Yours

| # | Item | Why it matters | Verify | State |
|---|---|---|---|---|
| W5 | A second, independent sell-simulation source | **Prerequisite for W3, not just a coverage fix.** The adversarial cohort cannot be cleaned without a third oracle the engine does not read: requiring honeypot.is corroboration would make the label circular under B1/B2. 15 of 17 `unsafe` tokens hold under $1, so the recall figure is measured on a cohort selected by recency rather than hostility. Also reduces the unknown rate | **Blocked** on a credential, not on engineering. Probed 2026-09-06: staysafu unreachable (SSL), quickintel 401, tokensniffer 401, de.fi public endpoint 404. Every candidate needs a paid key — this is a W9-shaped item that belongs to whoever holds the budget | Blocked |
| W9 | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` as GitHub Secrets | One action unlocks two things: automatic deploys, and the external-caller line on the scorecard, currently `not measured` and worth 5 points that cannot be earned any other way | `deploy.yml` stops skipping; `python bench/usage.py` returns a real answer | Done R17 |
| W10 | List on Glama, then Smithery, mcp.so, the Claude plugin directory | Distribution is 2.5/15 and every channel needs an account I cannot create. Glama first — awesome-mcp-servers expects a listing to exist | `CHANNELS` in `bench/scorecard.py`, updated only by someone who went and looked | Open |
| W11 | Answer the 2026-09-18 gate | ≥1 external caller. The first gate that can stop anything | `python bench/usage.py`, counting rule already fixed in code; then a `Resolved:` line in `STRATEGY.md` §8, which `test_gates_get_reviewed.py` requires once due | Open |
| W12 | Decide the price-history trade-off | `HANDOFF.md` §9.1. Reading OHLCV buys drawdown detection and voids the outcome column as an independent measurement. Three routes written up; none chosen | A decision recorded in `DECISIONS.md`, either way | Open |
| W13 | Move the Cloudflare account and zone ids out of the public repo | Neither is a secret, both are useful for targeted phishing | They are gone from `HANDOFF.md` §2 and a private note has them | Open |

## Closed

| # | Item | Outcome |
|---|---|---|
| W19 | Measure whether the pool we pick is the one that is wrong | **Done R15.** Ran the count O4 was gated on. 'Some pool disagrees' fires on 30.9% of tokens and is dust; 'the pool we picked disagrees with its peers' fires on 0.30% at 100x and is a real defect. Shipped as a selection rule in `_pick_best`. It was hiding a live P0: UNI priced at $4,576,980 by a pool with two trades in it |
| W20 | Compress the snapshot archive before it outgrows the repo | **Rejected 2026-09-07, corrected 2026-09-08. The verdict stands; three of its numbers did not, and the review caught them.** The original ticket projected ~250 MB/yr of files and ~1 GB of history, read off `du -sh .git` and the *loose* object store -- a transient local artefact, since git had not packed and GitHub packs on receive. Packed, the whole repository is 4.10 MiB and 9.33 MB of raw snapshot blobs collapse to 807 KB. **But the rejection then made the same class of error in the other direction.** (a) Its ~56 MiB/yr straddled three ramp-up days; measured over 2026-09-05 and 09-06, the only complete four-pass days, steady state is **92 MiB/yr packed** -- 11 years to GitHub's 1 GB soft limit, not 18. (b) It measured the history half only. The **working tree** grows at **~486 MB/yr** (1.40 MB/day over the same two days), and that is the number every CI checkout and every clone actually pays, five times the packed rate. (c) It argued gzip was wrong on readability, which is weak; the real reason is that gzip makes it **worse**. Measured: git stores all four versions of the 1,690,658-byte 09-05 file in 322,470 packed bytes, while `gzip -9` of the final version alone is 328,023 -- a .gz blob cannot be deltified and the plain blobs never leave history, so gzipping closed days is strictly additive. Nothing to do. Re-open on the constraint that actually binds: `du -sh bench/snapshots` above ~1 GB (about two years out), or a CI checkout over ~2 minutes. |
| W14 | LP lock / burn detection | **Rejected** in R9. Measured over 74 V2 pairs: "LP is fully pullable" catches 4 of 8 bad tokens and fires on 22 of 38 good ones — worse than chance, because most honest projects never burn LP. Removed from the scorecard denominator rather than left as a permanent gap |
| W15 | Chain-history backfill via reserve events | **Rejected** in R8. A genuinely independent class of evidence, but free RPCs cap `eth_getLogs` at 10k–50k blocks regardless of filter, so one pool-year is ~1,580 calls. Swap-log harvesting was built instead |
| W1 | Detect dormant owner powers from bytecode | **Reopened 2026-09-07.** The disclosure ships and is correct. What was closed and should not have been is the R12 conclusion that the powers do not discriminate: no measurement script was ever committed, no bytecode was cached, and the published table cannot be reproduced from the shipped selector list. A negative result used to justify not building something, that nobody could re-run | `python bench/owner_powers_measure.py` reproduces a per-power recall table from cached bytecode, and the selector list reaches 50% recall on at least one power | Open |
| W16 | Let completed on-chain sells settle sellability | **Rejected** in R9. 72 of 97 unknowns had 20+ sells and 0 were bad, including WETH — but a simulation tests whether *you* can sell and a completed trade shows *someone else* could, and a blacklist honeypot is built to make those look identical. Reported as context, gap kept open |
