# LazyWallet — Buy Now, Sell Later Spec

Date: 2026-10-16
Status: Approved design — not yet implemented
Builds on: `2026-10-15-lazywallet-swap-scheduler-design.md` (merged), `2026-10-15-lazywallet-kyber-custom-tokens-design.md` (merged)

## 1. Goal

"Can we buy ZRO now and sell it tomorrow" should take two taps and no retyping. The agent shows the buy card. As soon as that buy is confirmed, the scheduled-sale card appears on its own, for exactly the amount received. Scheduled sales of custom tokens (ZRO, COQ, …) must also actually execute. Today the executor only routes built-in tokens, so such an order would wait at "Due now" forever.

**Success criteria**
- "Buy 100 USDC of ZRO and sell it tomorrow" produces one buy card. After Approve, a second card appears for "Sell <exact received> ZRO → USDC, once, in 1 day", with the price floor shown. The agent doesn't ask first.
- If the buy is rejected or fails, no second card appears. If the sale card is rejected, the agent says the buy went through and nothing is scheduled.
- With `pnpm dev:executor` running, a scheduled custom-token sale executes through KyberSwap when it's due.
- `pnpm --filter wallet test`, `pnpm test:py`, `pnpm test:contracts`, `pnpm build && pnpm lint` pass. An opt-in Avalanche fork test buys COQ, schedules the sale, warps time, and the executor sells it through KyberSwap.

## 2. Decisions

| Topic | Decision |
|---|---|
| Two cards, not one | The sale amount is only known after the buy, so the sale is a second card that the tool sends right after a confirmed buy. One approval covering both was rejected: it would need a contract change ("sell up to X") or would leave the slippage margin unsold |
| Chaining | In code (`propose_swap(..., sell_after_seconds)`), not by prompt. The tool uses the exact raw received amount and doesn't depend on the model choosing not to ask |
| Delayed-sale floor | One-run orders with a start delay (`count == 1`, delay > 0): `minOut` = today's quote × (1 − 50%). Recurring or immediate orders keep 5%. A user-given `min_received` always wins. This applies to direct `propose_scheduled_swap` calls too ("sell my ZRO tomorrow") |
| Executor venue | Same rule as `propose_swap`: Uniswap (Ethereum) / Dexalot (Avalanche) when both tokens are built in and the venue quotes the pair, otherwise KyberSwap |
| Contract, pinned address, wallet UI | Unchanged |

## 3. Agent

### `propose_swap(..., sell_after_seconds?)`
- New optional integer input `sell_after_seconds` (≥ 60). It is only valid together with a buy.
- The buy runs unchanged. After `_succeeded(result)` and a known `received` (exact `plan.expected` for Dexalot, otherwise the balance change), the tool calls the shared scheduling helper (below) with:
  - `tin` = the bought token (`tout` of the buy), `tout` = the token that was paid (`tin` of the buy)
  - amount = `received` (raw units), `count = 1`, `interval = 0`, `delay = sell_after_seconds`
- If `received` is unknown, no sale card is sent and the result says so ("I couldn't read how much you received, so I didn't schedule the sale — check the balance, then ask again").
- The returned text covers both cards: the buy outcome, then the sale outcome (scheduled, rejected — "the buy went through; nothing is scheduled" — or an error, such as not enough native for the gas deposit).
- Native coin received (e.g. buy AVAX): the sale wraps it as with any native-input schedule. Native coin paid: the sale's output arrives as WETH/WAVAX (existing rule, shown on the card).

### Shared scheduling helper
- Extract the body of `propose_scheduled_swap`, from the token objects onward, into `_propose_schedule(net, tin, tout, amount_raw, interval, count, delay, min_received_text)` → tool result. `propose_scheduled_swap` keeps its argument parsing and resolution and then calls the helper. `propose_swap` calls it with Token objects it already holds, so a token bought this turn works even though the wallet hasn't saved it yet.
- Floor: `DELAYED_SALE_DISCOUNT_BPS = 5000` when `count == 1 and delay > 0`, else `MIN_OUT_DISCOUNT_BPS` (500). The card's "Min received" row shows the floor; delayed sales add "(sells even after a drop of up to 50%)".
- `_quote_out` falls back to KyberSwap (`client.route`'s `amountOut`, wrapped legs passed as the WETH/WAVAX ERC-20) when either token is custom or the venue has no quote, the same rule as `propose_swap`. Today a ZRO → USDC floor can't be quoted at all.

### Prompt
- "Buy X now and sell it tomorrow / in N hours / later today" → one `propose_swap` with `sell_after_seconds` (tomorrow = 86400). Don't ask before the sale card; it appears after the buy. Report both outcomes in one or two sentences.

## 4. Executor — KyberSwap route

In `executor.py`, `Executor.build_calls`:
- Token lookup by address. When `token_at(net, …)` is `None` (a custom token), the order is still routable through KyberSwap; only the built-in venues need registry tokens.
- Venue: if both tokens are built in, try the venue as today. If a token is custom, or the venue has no route or quote, use KyberSwap.
- KyberSwap call building (new pure helper `kyber_calls(order, verified) -> list[Call]`):
  - `route(net.key, token_in, token_out, amount_in)` with the order's ERC-20 addresses (WETH/WAVAX as plain ERC-20, no unwrap), then `build(net.key, summary, SWAPPER, SANDBOX_KYBER_SLIPPAGE_BPS)`.
  - `verify(build, SwapRequest(token_in, token_out, amount_in, SWAPPER, bps), quoted)`: pinned router, exact input amount, `dstReceiver == SWAPPER`, no fee receivers. A refusal skips the order this tick.
  - Calls: `[token_in.approve(ROUTER, amount_in), (ROUTER, 0, verified.data)]`. The Swapper sweeps the output to the owner, and the contract's `minOut` stays the real guard. No separate simulation: the executor's `estimate_gas` on `executeSwap` already simulates the whole run.
- `Executor(…, kyber: Kyber | None)`; `main()` passes `KyberClient()`. Without a client, custom-token orders are skipped with a log line.

## 5. Testing
- pytest (fakes, no network):
  - Buy then sale: after an approved buy, a second confirm card arrives with the exact received amount, `count 1`, start = now + delay, and the 50% floor. A rejected or failed buy sends no second card. A rejected sale card gives "the buy went through" text. Unknown received amount gives no sale card and explains why.
  - Floor rules: delayed one-shot uses 50%, recurring and immediate use 5%, `min_received` overrides.
  - `_quote_out` uses KyberSwap for a custom token (fixture).
  - Executor: `kyber_calls` from a fixture build; refusal of a build with the wrong receiver; venue choice (built-in pair → venue; custom token → KyberSwap).
- Opt-in fork test (Avalanche, existing `avax_sandbox` fixture plus the live KyberSwap API): buy COQ with AVAX via `propose_swap(sell_after_seconds=60)`, auto-approve both cards, warp 61 s, run one executor tick, and assert the COQ was sold for ≥ `minOut` WAVAX.

## 6. Out of scope
One-approval batching, "sell when price 2×" (limit orders), cancelling from the sheet, and sale amounts other than "all of what was just bought".
