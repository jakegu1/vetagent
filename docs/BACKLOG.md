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
| W2 | Deployer history as a risk dimension | One of two dimensions still uncovered on the scorecard | Same measurement first. Needs a contract-creation source; Etherscan-family APIs are keyed | Open |
| W3 | Grow the genuine adversarial cohort beyond 9 | Contract-level recall is currently measured on 9 tokens and 4 of them are `low` when ablated. Every headline claim rests on this | `bench/run_benchmark.py`, the `unsafe` ablated column, n rising | Open |
| W4 | Cut the unknown rate below 10% | 17.9% now, worth 4 scorecard points. Remaining causes are a single sell-simulation source and chains it does not cover | Split reported in `bench/results.md` under "what the unknown rate is made of"; ours vs the token's | Open |
| W5 | A second, independent sell-simulation source | W4's real fix. One vendor's absence should not be decisive, and honeypot.is covers three chains of the eight we advertise | Coverage overlap measured first: does a candidate answer where honeypot.is 404s? | Open |
| W6 | EVM holder concentration | The last uncovered dimension | **Blocked** by `DECISIONS.md` B2 — the field belongs to the held-out oracle. Needs W1's bytecode route or a different source | Blocked |
| W7 | Point-in-time evaluation from the snapshot archive | The benchmark scores "now" against a retrospective label, so it cannot answer "would it have warned me". The archive records contemporaneous state and the labeller never reads it | **Blocked** on archive depth: needs ≥60 days of contemporaneous snapshots, 3 as of R11. Accrues on its own via `snapshot.yml`, so the wait is the work | Blocked |
| W17 | **Score** owner powers, rather than only disclosing them | The disclosure shipped in R12 but cannot be scored: the measurement needs a bad cohort big enough to tell 5% from 22% | **Blocked** on W3. Re-run the selector measurement when the adversarial cohort passes ~40 | Blocked |
| W8 | Consolidate `DECISIONS.md` | 63 rows against its own stated ceiling of 40. The file says test-enforced entries that never failed should collapse to one line | The row count, and that no enforcement is lost in the merge | Open |

## Yours

| # | Item | Why it matters | Verify | State |
|---|---|---|---|---|
| W9 | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` as GitHub Secrets | One action unlocks two things: automatic deploys, and the external-caller line on the scorecard, currently `not measured` and worth 5 points that cannot be earned any other way | `deploy.yml` stops skipping; `python bench/usage.py` returns a real answer | Open |
| W10 | List on Glama, then Smithery, mcp.so, the Claude plugin directory | Distribution is 2.5/15 and every channel needs an account I cannot create. Glama first — awesome-mcp-servers expects a listing to exist | `CHANNELS` in `bench/scorecard.py`, updated only by someone who went and looked | Open |
| W11 | Answer the 2026-09-18 gate | ≥1 external caller. The first gate that can stop anything | `python bench/usage.py`, counting rule already fixed in code; then a `Resolved:` line in `STRATEGY.md` §8, which `test_gates_get_reviewed.py` requires once due | Open |
| W12 | Decide the price-history trade-off | `HANDOFF.md` §9.1. Reading OHLCV buys drawdown detection and voids the outcome column as an independent measurement. Three routes written up; none chosen | A decision recorded in `DECISIONS.md`, either way | Open |
| W13 | Move the Cloudflare account and zone ids out of the public repo | Neither is a secret, both are useful for targeted phishing | They are gone from `HANDOFF.md` §2 and a private note has them | Open |

## Closed

| # | Item | Outcome |
|---|---|---|
| W14 | LP lock / burn detection | **Rejected** in R9. Measured over 74 V2 pairs: "LP is fully pullable" catches 4 of 8 bad tokens and fires on 22 of 38 good ones — worse than chance, because most honest projects never burn LP. Removed from the scorecard denominator rather than left as a permanent gap |
| W15 | Chain-history backfill via reserve events | **Rejected** in R8. A genuinely independent class of evidence, but free RPCs cap `eth_getLogs` at 10k–50k blocks regardless of filter, so one pool-year is ~1,580 calls. Swap-log harvesting was built instead |
| W1 | Detect dormant owner powers from bytecode | **Done R12** — measured, and split. Keccak-256 implemented so selectors are computed rather than remembered, then matched against the bytecode of 417 labelled contracts. It does not discriminate at the cohort size available: pausable 11% of unsafe against 5% of safe, mutable tax 11% against 0%, blacklist in neither, and **mintable runs the wrong way** — 12% of safe against 0% of unsafe. With nine tokens in the unsafe cohort, "11%" is one token. So the powers are **disclosed** as unscored evidence, which is what the audit's positioning complaint actually needed, and scoring them is W17, blocked on W3 |
| W16 | Let completed on-chain sells settle sellability | **Rejected** in R9. 72 of 97 unknowns had 20+ sells and 0 were bad, including WETH — but a simulation tests whether *you* can sell and a completed trade shows *someone else* could, and a blacklist honeypot is built to make those look identical. Reported as context, gap kept open |
