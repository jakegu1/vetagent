# Our own sell simulation (SELL_SIMULATION.md)

> W41. A design page and a measurement plan, written and committed **before** the prototype
> runs, so the rule that judges it cannot be fitted to its result. Nothing here goes into
> `src/` before the 2026-09-18 gate reads (STRATEGY §8: no features before 09-18).

## The question

On 2026-09-15, 122 of the 576 benchmark answers are `unknown`, and 94 of those are sellability gaps: the one
free sell simulator the engine uses, honeypot.is, has no record of the token or its buy leg
reverted. No change to how we read honeypot.is can close that; only a second simulator can. The
question this page sets up is narrow:

> Can a simulation we run ourselves, on public RPCs, give a definite buy/sell answer for the
> tokens honeypot.is cannot -- and does it agree with honeypot.is where both can answer,
> including on honeypots?

## What is already measured (2026-09-15)

- All three RPC hosts the engine already uses (`_CHAIN_RPC`: rpc.mevblocker.io,
  mainnet.base.org, bsc-dataseed.bnbchain.org) accept `eth_call` with a code override: an
  empty address overridden to return 42 returned 42, and without the override returned `0x`.
- All three also accept **`eth_simulateV1`** with a balance override and several calls in one
  block, state carried from one call to the next (`scratchpad/w41/probe_simulate.py`: two
  value transfers from an overridden, funded address, both `status 0x1`). That removes the
  hardest part of the audit's plan: **no tester contract, no compiler, no deployment.** A buy, an
  approval and a sell are three ordinary router calls from a funded address in one request.
- The benchmark's BSC sellability unknowns by the engine's pool: PancakeSwap V3 15, PancakeSwap
  V2 13, Uniswap (v4 pool ids) 6, no pool 4. Across all three chains the audit-verification
  replay counted 22 of 86 sellability unknowns on Uniswap V4 pools, which a V2 or V3 router call
  cannot reach.
- Routers, read from honeypot.is's own answers rather than remembered: Uniswap V2 router
  `0x7a250d56...` on Ethereum (265 archived answers), `0x4752ba5d...` on Base (104), PancakeSwap V2
  `0x10ed43c7...` on BSC (45 cached answers).

## Mechanism (V2-style routers)

One `eth_simulateV1` request per token, pinned to one block, from a fresh address given a
native balance by state override, `validation: false`:

1. `router.getAmountsOut(amountIn, [WNATIVE, (quote,) token])` -- the no-tax expectation.
2. `router.swapExactETHForTokensSupportingFeeOnTransferTokens(0, path, sender, deadline)` with
   `value = amountIn`.
3. `token.balanceOf(sender)` -- what arrived. Buy tax = 1 - arrived / expected.
4. `token.approve(router, max)`.
5. `router.getAmountsOut(arrived, reverse path)` -- the no-tax expectation for the sale. The amount
   is known from a first, identical request that stops after step 3, at the same pinned block.
6. `router.swapExactTokensForTokensSupportingFeeOnTransferTokens(arrived, 0, reverse path,
   sender, deadline)`, selling into the wrapped native token so the proceeds are readable.
7. `WNATIVE.balanceOf(sender)`. Sell tax = 1 - proceeds / expected.

`amountIn` is fixed per chain before the run: 0.02 ETH on Ethereum and Base, 0.1 BNB on BSC.
Selectors are computed with `bench/keccak.py` (E20), never pasted.

## What it can and cannot see

- It answers **can a new buyer buy, and sell straight back**, with the tax each way. That is the
  question honeypot.is's own simulation answers, from an independent implementation.
- It does **not** run honeypot.is's holder test: a fresh address passes a contract that blocks
  specific holders (W44 is about exactly that signal). `eth_simulateV1` can simulate a call
  *from* a real holder address with no key, so a holder test is possible later; it needs a holder
  list, which is not in scope here.
- A same-block buy and sell fails on tokens with a cooldown or a max-transaction limit. That
  reads as a failed sell, the same limitation honeypot.is has; the revert reason is kept so the
  cases can be told apart.
- It is engine-side. Under B1/B2 it can never be W3's labelling oracle.

## Adapters, in order of what they would close

| Adapter | Unknowns it could reach (verification replay, 86 sellability unknowns) | Work |
|---|---|---|
| UniswapV2-style router (Uniswap V2, PancakeSwap V2, forks) | 15-17 | this page |
| UniswapV3 / PancakeSwap V3 (`exactInputSingle`, fee tier from the pool) | 18 | next, if the V2 rule passes |
| Solidly / Aerodrome (`Route` struct, stable flag) | 20 | after V3 |
| Uniswap V4 (PoolManager unlock callback, or Universal Router plus Permit2) | 22 | the most work; hooks can change behaviour |
| Curve stable pools (`exchange`) | 3 | last |

Coverage is not success: nobody has measured how many of these would become a definite answer.
That is what the prototype is for.

## The prototype, and the rule that judges it -- fixed before it runs

**Where.** `bench/sim_probe.py`, outside `src/`, with its own cache directory `bench/cache_sim/`
(never `bench/cache`, which the benchmark owns and races on). Results committed to
`bench/sim_probe/`.

**Sets.**

- **U** -- the 13 BSC benchmark tokens whose engine pool is PancakeSwap V2 and whose answer is
  `unknown` on a sellability gap (12 "no record", 1 "BUY_FAILED"), as listed by
  `scratchpad/w41/targets.py` on 2026-09-15.
- **C-clean** -- tokens honeypot.is simulated cleanly on a V2 pool: the 11 BSC benchmark tokens
  on the engine's own PancakeSwap V2 pool (WBNB itself excluded), plus the 20 lowest token
  addresses among archived clean Uniswap V2 answers on Ethereum and the 20 lowest on Base.
- **C-honeypot** -- the 16 Ethereum Uniswap V2 tokens honeypot.is answered as proven honeypots
  (sell reverted, or sell tax 50% or more) in the snapshot archive.

honeypot.is is asked again for every control on the day of the run, and a control counts only if
today's answer still has the shape it was chosen for: archived answers are from the pool's first
hours, and a pool can be drained or a tax changed since.

**Definitions.**

- *Definite*: the buy executed and delivered tokens, and the sell either executed or reverted. A
  reverting buy, an RPC error, or no V2 path is *no answer*.
- *Agrees, clean control*: buy and sell both executed, and each tax is within 5 points of
  honeypot.is's.
- *Agrees, honeypot control*: the sell reverted, or our sell tax is 50% or more.

**Decision.**

- **Build the V3 adapter next** only if all three hold: a definite answer on at least 10 of the 13
  in U; agreement on at least 90% of countable clean controls; agreement on at least 80% of
  countable honeypot controls. If fewer than 5 honeypot controls are countable, the positive
  control is recorded as not measurable and the V3 step waits for a positive set.
- **Stop** if U gets a definite answer on fewer than 7 of 13: the gap is on the token side, not
  in honeypot.is's routing, and more adapters would not close it.
- **Anything between** is inconclusive: every failure is classified by revert reason before any
  further adapter is written.
- The thresholds, sets and amounts above do not change after the run. A wrong threshold is
  fixed in a new, dated section, with the result that prompted it stated.

**Cost.** About 80 `eth_simulateV1` requests (two per token) and about 60 honeypot.is requests,
on the free endpoints the engine already uses. $0.

## Run 1, 2026-09-15 -- result under the rule above: INCONCLUSIVE

`python bench/sim_probe.py` at blocks ethereum 0x18c7aa6, base 0x30f8122, bsc 0x7465920.
Everything it saw is in `bench/sim_probe/v2-2026-09-15.json`.

| Test | Bar | Result |
|---|---|---|
| U: definite answers | at least 10 of 13 | **12 of 13** -- all 12 sold, taxes 0-7% each way; SPR's buy reverted (`Pancake: TRANSFER_FAILED`), as honeypot.is's did |
| Clean controls agree | at least 90% of countable | **50 of 51** (98%); the one miss is an RPC transport error (SSL EOF), counted against us as the definition requires |
| Honeypot controls agree | at least 80% of countable, at least 5 countable | **10 of 13** (77%) -- under the bar |

So the rule says inconclusive, and the V3 adapter is not written. The thresholds do not move.

**The failures, classified by revert reason as the rule requires.** None of the three honeypot
disagreements is a honeypot our simulation let through:

- `0x17e6b79b...`: honeypot.is's own answer today puts its pool at $0.00000000000065, with
  `INSUFFICIENT_OUTPUT_AMOUNT` and zero gas. Our simulation "sold" dust into the same empty pool.
  Neither answer describes a token; both describe a corpse.
- `0x2c43ebde...` and `0xe1cb7c7e...`: pools holding $0.30 and $0.0004, quoted in USDT through a
  different V2 fork's router (`0xeff92a26...`), so our Uniswap V2 router has no path at all.

Of the 10 agreements, 7 bought normally and then reverted on the sell
(`TransferHelper: TRANSFER_FROM_FAILED`), and 3 sold at a 99.99-100% sell tax. Those are honeypots,
caught by an implementation that shares no code with honeypot.is.

**What was wrong was the positive set, not the simulation**: an archived birth-time honeypot is,
days later, usually a drained pool, and honeypot.is's answer on a drained pool keeps the honeypot
shape. That is a flaw in how the set was defined, found after seeing the result, so it is
recorded here and does not re-score run 1.

## Amendment 1, 2026-09-15 (after run 1, prompted by the result above)

A positive control counts only if honeypot.is's own answer on the day puts its pool at $1,000
or more. Applied to what exists today, that leaves **4** unused candidates across the cache and
the archive -- all on Base, all with an empty router and zero gas, the shape W31 and W46 read as
a trade that never ran. Fewer than 5 countable positives: under the rule's own clause, **the
positive control is not measurable yet, and the V3 adapter waits for a positive set.** A set with
money in it is exactly what W40 (label while the pool is alive) produces; until then the V2
result stands as measured and nothing goes into `src/` (STRATEGY §8).

Two things run 1 did establish, stated as measured and no further:

- For 12 of the 13 PancakeSwap V2 tokens honeypot.is has no record of, a plain router buy and sell
  from a fresh address works, with ordinary taxes. On these, the gap was honeypot.is's index, not
  the tokens.
- Zero gas in a honeypot.is answer that names a router is not evidence that nothing executed
  (W47): in 7 such archived answers our simulation bought normally and the sell then reverted.
