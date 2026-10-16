# Buy Now, Sell Later Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "Buy ZRO now and sell it tomorrow" produces the buy card and then, after a confirmed buy, a scheduled-sale card on its own for exactly the amount received. The executor can sell custom tokens through KyberSwap.

**Architecture:** `propose_swap` gains `sell_after_seconds`. After a confirmed buy, it calls a scheduling helper extracted from `propose_scheduled_swap`. Delayed one-run orders get a 50% price floor, and scheduling quotes custom tokens through KyberSwap. The executor falls back to KyberSwap: route and build with the Swapper as sender and recipient, checked by the existing `kyber.verify()`. No contract, pinned-address or wallet change.

**Tech Stack:** Python 3.12 (uv), web3.py, eth_abi, pytest (asyncio auto mode), existing `lazyagent` fakes (`FakeChain`, `FakeKyber`, `FakeQuoter`, `Outbox`).

**Spec:** `docs/superpowers/specs/2026-10-16-lazywallet-buy-then-sell-design.md`

## Global Constraints

- Two cards, never one combined card. The sale card is sent only after `_succeeded(result)` on the buy, with the exact raw received amount (`plan.expected` when `plan.exact`, otherwise the balance change).
- `sell_after_seconds` is an integer ≥ 60 (`MIN_INTERVAL_S`). The sale is `count = 1`, `interval = 0`, `delay = sell_after_seconds`, selling the bought token back to the paid token.
- Floors: `DELAYED_SALE_DISCOUNT_BPS = 5000` when `count == 1 and delay > 0`, otherwise `MIN_OUT_DISCOUNT_BPS = 500`. A user `min_received` always wins and 0 is still rejected.
- Venue rule, used by both the agent's quote and the executor: the network's venue (Uniswap v4 on Ethereum, Dexalot on Avalanche) for built-in pairs it can route, otherwise KyberSwap.
- Executor KyberSwap: order tokens are ERC-20 (WETH/WAVAX passed as-is, no unwrap); `build(net.key, summary, SWAPPER, SANDBOX_KYBER_SLIPPAGE_BPS)`; `verify(..., SwapRequest(token_in, token_out, amount_in, SWAPPER, bps), quoted)` must pass; calls = `[approve(ROUTER, amount_in), (ROUTER, 0, data)]`.
- The model never builds calldata. No "Sandbox" wording in user-facing text.
- Unchanged: `contracts/`, the four pinned scheduler addresses, `apps/wallet`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The buy succeeds but the sale can't be scheduled** (for example, no native coin left for the gas deposit). Expected: the buy is reported as done and the sale as not scheduled, with the reason, and no crash. Pinned by `test_buy_ok_but_sale_cannot_be_scheduled_reports_both` (Task 2).
2. **The bought token is the native coin** ("buy ETH with USDC, sell it tomorrow"). Expected: the sale card wraps the received ETH, then approves and schedules. Pinned by `test_buy_eth_then_sale_wraps_the_received_eth` (Task 2).
3. **The model passes `sell_after_seconds` as a string** ("86400"). Expected: it's accepted. Pinned by the string value in `test_buy_then_sell_sends_the_sale_card_after_the_buy` (Task 2).
4. **A custom-token order while KyberSwap isn't configured or is down.** Expected: the order is skipped with a clear log line, and other orders still run. Pinned by `test_custom_token_without_kyber_is_refused` (Task 3); the tick's per-order isolation is already tested.
5. **A built-in pair the venue can route.** Expected: it stays on Uniswap or Dexalot and never touches KyberSwap. Pinned by `test_builtin_pair_with_a_venue_route_keeps_uniswap` (Task 3).

---

## File Structure

| File | Change |
|---|---|
| `agent/lazyagent/scheduler.py` | `DELAYED_SALE_DISCOUNT_BPS`, `floor_bps()`, `schedule_rows(..., wide_floor=False)` |
| `agent/lazyagent/tools.py` | `_quote_out` falls back to KyberSwap; `_propose_schedule` helper; `propose_scheduled_swap` delegates; `propose_swap(sell_after_seconds)`; schema |
| `agent/lazyagent/prompt.py` | "buy now, sell later" line |
| `agent/lazyagent/executor.py` | `kyber_calls()`, `Executor(kyber=)`, KyberSwap fallback in `build_calls`, `main()` passes `KyberClient()` |
| `agent/tests/test_scheduler.py`, `test_schedule_tools.py`, `test_kyber_tools.py`, `test_executor.py`, `test_scheduler_fork.py` | tests |
| `CLAUDE.md`, `README.md` | docs |

---

### Task 1: Delayed-sale floor, shared scheduling helper, KyberSwap quote

**Files:**
- Modify: `agent/lazyagent/scheduler.py`, `agent/lazyagent/tools.py`
- Test: `agent/tests/test_scheduler.py`, `agent/tests/test_schedule_tools.py`, `agent/tests/test_kyber_tools.py`

**Interfaces:**
- Produces: `scheduler.DELAYED_SALE_DISCOUNT_BPS = 5000`; `scheduler.floor_bps(count: int, delay: int) -> int`; `scheduler.schedule_rows(sender, tin, tout, net, amount_in, min_out, label, top_up, wide_floor: bool = False)`; `WalletTools._propose_schedule(net, tin: Token, tout: Token, amount: int, interval: int, count: int, delay: int, min_received: str | None) -> dict` (Task 2 calls it).

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_scheduler.py` (add `DELAYED_SALE_DISCOUNT_BPS`, `MIN_OUT_DISCOUNT_BPS` and `floor_bps` to its `from lazyagent.scheduler import (...)` block):

```python
def test_floor_is_wide_only_for_a_delayed_single_run():
    assert floor_bps(1, 86400) == DELAYED_SALE_DISCOUNT_BPS == 5000
    assert floor_bps(1, 0) == MIN_OUT_DISCOUNT_BPS
    assert floor_bps(3, 86400) == MIN_OUT_DISCOUNT_BPS


def test_schedule_rows_explain_the_wide_floor():
    rows = {r["label"]: r["value"] for r in schedule_rows(ME, USDC, ETHEREUM.native, ETHEREUM, 10 * 10**6, 2 * 10**15, "once, in 1 d", 0, wide_floor=True)}
    assert rows["Min received per run"] == "0.002 WETH (sells even after a drop of up to 50%)"
```

Append to `agent/tests/test_schedule_tools.py`:

```python
def schedule_args(confirm):
    return decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(confirm["tx"]["steps"][-1]["request"]["data"][10:]))


async def test_delayed_single_run_uses_the_wide_floor():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "start_delay_seconds": "86400"}))
    confirm = await confirm_of(out)
    expected = 10 * 10**6 * 10**12 // USDC_PER_ETH
    args = schedule_args(confirm)
    assert args[3] == expected * 5000 // 10_000
    assert args[4:] == (chain.now + 86400, 0, 1)
    assert "drop of up to 50%" in {r["label"]: r["value"] for r in confirm["tx"]["rows"]}["Min received per run"]
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task


async def test_immediate_single_run_keeps_the_five_percent_floor():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10"}))
    confirm = await confirm_of(out)
    expected = 10 * 10**6 * 10**12 // USDC_PER_ETH
    assert schedule_args(confirm)[3] == expected * 9500 // 10_000
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task
```

Append to `agent/tests/test_kyber_tools.py` (add `from eth_abi import decode`, and `from lazyagent.networks import AVALANCHE` plus `from lazyagent.scheduler import SCHEDULER, wrapped_token` to its imports):

```python
async def test_scheduling_a_custom_token_sale_quotes_through_kyber():
    avax = coq_chain(COQ=10**24)
    tools, out, proposals, _, kyber = make(avax=avax, saved=[COQ_SAVED])
    task = asyncio.create_task(
        tools.propose_scheduled_swap({"token_in": "COQ", "token_out": "AVAX", "amount": "1000000", "start_delay_seconds": 86400})
    )
    confirm = await confirm_of(out)
    wavax = wrapped_token(AVALANCHE).address
    network, token_in, token_out, amount = kyber.routes[-1]
    assert (network, token_in.lower(), token_out.lower(), amount) == ("avalanche", COQ_ADDR.lower(), wavax.lower(), 10**24)
    schedule = confirm["tx"]["steps"][-1]["request"]
    assert schedule["to"] == SCHEDULER
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(schedule["data"][10:]))
    assert args[3] == OUT * 5000 // 10_000
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_scheduler.py tests/test_schedule_tools.py tests/test_kyber_tools.py`
Expected: FAIL. `floor_bps` / `DELAYED_SALE_DISCOUNT_BPS` can't be imported, the floors are 9500, and the custom-token quote raises "I couldn't find a Uniswap…" or a Dexalot error.

- [ ] **Step 3: Implement in `scheduler.py`**

Under `MIN_OUT_DISCOUNT_BPS = 500` add:

```python
DELAYED_SALE_DISCOUNT_BPS = 5000  # "sell it tomorrow" must still sell after a drop; only a collapse or a bad route stops it
```

After `gas_top_up`, add:

```python
def floor_bps(count: int, delay: int) -> int:
    """How far below today's quote a run may fill: wide for one run that waits, 5% for recurring or immediate orders."""
    return DELAYED_SALE_DISCOUNT_BPS if count == 1 and delay > 0 else MIN_OUT_DISCOUNT_BPS
```

Change `schedule_rows` to take `wide_floor: bool = False` as its last parameter and build the min row as:

```python
    floor = f"{display_units(min_out, get.decimals)} {get.symbol}"
    if wide_floor:
        floor += f" (sells even after a drop of up to {DELAYED_SALE_DISCOUNT_BPS // 100}%)"
```

with `{"label": "Min received per run", "value": floor}`.

- [ ] **Step 4: Implement in `tools.py`**

Add `DELAYED_SALE_DISCOUNT_BPS` (unused there; skip it if the linter objects) and `floor_bps` to the `from .scheduler import (...)` block, and `NoRoute` is already imported from `.transfers`.

Replace `_quote_out` with:

```python
    async def _quote_out(self, net: Network, tin, tout, amount: int) -> int:
        """Today's output for one run: the network's venue for built-in pairs (wrapped legs quoted as native), else KyberSwap."""
        if not (tin.custom or tout.custom):
            try:
                return await self._venue_quote(net, tin, tout, amount)
            except NoRoute:
                if self.kyber is None:
                    raise
        if self.kyber is None:
            raise TransferError("Swaps for tokens outside the built-in list aren't set up here.")
        pay, get = order_token(tin, net), order_token(tout, net)
        route = await self.kyber.route(net.key, pay.address, get.address, amount)
        return int(route["routeSummary"]["amountOut"])

    async def _venue_quote(self, net: Network, tin, tout, amount: int) -> int:
        a, b = routing_token(tin, net), routing_token(tout, net)
        if net.swap_venue == "dexalot":
            if self.dexalot is None:
                raise TransferError("Dexalot swaps aren't set up here.")
            return int((await self.dexalot.quote(asset_of(a), asset_of(b), amount, self.ctx.address))["order"]["makerAmount"])
        found = await best_route(self.quoter, currency_of(a), currency_of(b), amount)
        if found is None:
            raise NoRoute(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol}.")
        return found[1]
```

Split `propose_scheduled_swap`. It keeps everything up to and including `tin, tout = find_token(...)`, then:

```python
        try:
            amount = parse_amount(str(args.get("amount", "")), tin.decimals)
            interval, count, delay = parse_schedule(args.get("interval_seconds"), args.get("count"), args.get("start_delay_seconds"))
        except TransferError as e:
            return err(str(e))
        return await self._propose_schedule(net, tin, tout, amount, interval, count, delay, args.get("min_received"))

    async def _propose_schedule(self, net: Network, tin, tout, amount: int, interval: int, count: int, delay: int, min_received) -> dict:
        """One schedule card for tokens already resolved — used by propose_scheduled_swap and by propose_swap's sale."""
        pay, get = order_token(tin, net), order_token(tout, net)
        chain = self.chains[net.key]
        try:
            if pay.address == get.address:
                raise TransferError(f"{tin.symbol} and {tout.symbol} are the same token once wrapped — pick two different tokens.")
            total = amount * count
```

From `# Remaining runs of the user's other active orders…` down to the end of the old method, move the existing body unchanged into `_propose_schedule`, with three edits:
- `if args.get("min_received"):` becomes `if min_received:`, and `parse_amount(str(args["min_received"]), get.decimals)` becomes `parse_amount(str(min_received), get.decimals)`.
- `min_out(await self._quote_out(net, tin, tout, amount), MIN_OUT_DISCOUNT_BPS)` becomes `min_out(await self._quote_out(net, tin, tout, amount), floor_bps(count, delay))`.
- `schedule_rows(self.ctx.address, tin, tout, net, amount, minimum, label, top_up)` becomes `schedule_rows(self.ctx.address, tin, tout, net, amount, minimum, label, top_up, wide_floor=not min_received and floor_bps(count, delay) != MIN_OUT_DISCOUNT_BPS)`.

Remove `MIN_OUT_DISCOUNT_BPS` from the tools import only if nothing references it any more. The `wide_floor` expression above does use it.

- [ ] **Step 5: Run the tests**

Run: `uv run --directory agent pytest -q --deselect tests/test_swap_fork.py --deselect tests/test_dexalot_swap_fork.py --deselect tests/test_quote_fork.py --deselect tests/test_scheduler_fork.py --deselect tests/test_kyber_swap_fork.py --deselect tests/test_deposit_fork.py`
Expected: all PASS (the new tests plus every existing scheduling test, unchanged). If a fork-test filename above doesn't exist, drop that `--deselect`.

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/scheduler.py agent/lazyagent/tools.py agent/tests/test_scheduler.py agent/tests/test_schedule_tools.py agent/tests/test_kyber_tools.py
git commit -m "feat(agent): wide floor for delayed sales, shared schedule helper, KyberSwap quotes for custom tokens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `propose_swap(sell_after_seconds)` sends the sale card after a confirmed buy

**Files:**
- Modify: `agent/lazyagent/tools.py`, `agent/lazyagent/prompt.py`
- Test: `agent/tests/test_kyber_tools.py`, `agent/tests/test_schedule_tools.py`

**Interfaces:**
- Consumes: `WalletTools._propose_schedule(net, tin, tout, amount, interval, count, delay, min_received) -> dict` (Task 1); `scheduler.MIN_INTERVAL_S` (60).
- Produces: tool input `propose_swap.sell_after_seconds` (integer).

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_kyber_tools.py`:

```python
async def nth_confirm(out, n):
    for _ in range(400):
        if len(out.of_type("confirm")) >= n:
            return out.of_type("confirm")[n - 1]
        await asyncio.sleep(0)
    raise AssertionError(f"no confirm #{n}")


async def test_buy_then_sell_sends_the_sale_card_after_the_buy():
    tools, out, proposals, avax, kyber = make()
    task = asyncio.create_task(
        tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": "86400"})
    )
    buy = await nth_confirm(out, 1)
    avax.tokens["COQ"] = OUT  # what the buy delivered
    proposals.resolve(buy["id"], {"outcome": "approved", "status": "success", "hash": "0xb"})
    sale = await nth_confirm(out, 2)
    assert [s["label"] for s in sale["tx"]["steps"]] == ["Allow COQ", "Schedule swap"]
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(sale["tx"]["steps"][-1]["request"]["data"][10:]))
    assert args[0].lower() == COQ_ADDR.lower() and args[1].lower() == wrapped_token(AVALANCHE).address.lower()
    assert args[2] == OUT and args[3] == OUT * 5000 // 10_000
    assert args[4:] == (avax.now + 86400, 0, 1)
    proposals.resolve(sale["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    result = text(await task)
    assert "Swapped 1 AVAX for 8000000 COQ" in result and "Scheduled" in result


async def test_rejected_buy_sends_no_sale_card():
    tools, out, proposals, _, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": 86400}))
    buy = await nth_confirm(out, 1)
    proposals.resolve(buy["id"], {"outcome": "rejected"})
    assert "rejected" in text(await task)
    assert len(out.of_type("confirm")) == 1


async def test_rejected_sale_card_says_the_buy_went_through():
    tools, out, proposals, avax, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": 86400}))
    buy = await nth_confirm(out, 1)
    avax.tokens["COQ"] = OUT
    proposals.resolve(buy["id"], {"outcome": "approved", "status": "success", "hash": "0xb"})
    sale = await nth_confirm(out, 2)
    proposals.resolve(sale["id"], {"outcome": "rejected"})
    result = text(await task)
    assert "Swapped 1 AVAX for" in result and "The buy went through" in result and "rejected the scheduled swap" in result


async def test_unreadable_received_amount_schedules_nothing():
    tools, out, proposals, _, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": 86400}))
    buy = await nth_confirm(out, 1)
    proposals.resolve(buy["id"], {"outcome": "approved", "status": "success", "hash": "0xb"})  # balance never changed
    assert "didn't schedule the sale" in text(await task)
    assert len(out.of_type("confirm")) == 1


async def test_buy_ok_but_sale_cannot_be_scheduled_reports_both():
    tools, out, proposals, avax, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": 86400}))
    buy = await nth_confirm(out, 1)
    avax.tokens["COQ"] = OUT
    avax.eth = 0  # nothing left for the sale's gas deposit and fees
    proposals.resolve(buy["id"], {"outcome": "approved", "status": "success", "hash": "0xb"})
    result = text(await task)
    assert "Swapped 1 AVAX for" in result and "didn't schedule the sale" in result and "Not enough AVAX" in result
    assert len(out.of_type("confirm")) == 1


async def test_sell_after_under_a_minute_is_refused_before_any_card():
    tools, out, _, _, _ = make()
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "sell_after_seconds": 30})
    assert result.get("is_error") and "at least 1 minute" in text(result)
    assert not out.of_type("confirm")
```

Append to `agent/tests/test_schedule_tools.py`:

```python
async def test_buy_eth_then_sale_wraps_the_received_eth():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "sell_after_seconds": 3600}))
    for _ in range(200):
        if out.of_type("confirm"):
            break
        await asyncio.sleep(0)
    buy = out.of_type("confirm")[0]
    received = 4 * 10**15
    chain.eth += received
    chain.tokens["USDC"] -= 10 * 10**6
    proposals.resolve(buy["id"], {"outcome": "approved", "status": "success", "hash": "0xb"})
    for _ in range(400):
        if len(out.of_type("confirm")) >= 2:
            break
        await asyncio.sleep(0)
    sale = out.of_type("confirm")[1]
    assert [s["label"] for s in sale["tx"]["steps"]] == ["Wrap ETH → WETH", "Allow WETH", "Schedule swap"]
    assert sale["tx"]["steps"][0]["request"]["value"] == str(received)
    proposals.resolve(sale["id"], {"outcome": "rejected"})
    await task
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_kyber_tools.py tests/test_schedule_tools.py`
Expected: FAIL. No second card arrives (`AssertionError: no confirm #2`), and `sell_after_seconds=30` isn't refused.

- [ ] **Step 3: Implement in `propose_swap`**

Add `MIN_INTERVAL_S` to the `from .scheduler import (...)` block. In `propose_swap`, right after the `if sym_in.upper() == sym_out.upper():` check, add:

```python
        sell_after = args.get("sell_after_seconds")
        if sell_after not in (None, ""):
            try:
                sell_after = int(sell_after)
            except (TypeError, ValueError):
                return err("sell_after_seconds has to be a whole number of seconds.")
            if sell_after < MIN_INTERVAL_S:
                return err("The sale needs to be at least 1 minute after the buy.")
        else:
            sell_after = None
```

At the end of `propose_swap`, replace `return ok(outcome_text(result, steps_json, "swap", success, revert_hint=plan.hint))` with:

```python
        reply = outcome_text(result, steps_json, "swap", success, revert_hint=plan.hint)
        if sell_after is not None and _succeeded(result):
            reply += await self._sell_later(net, tout, tin, received, sell_after)
        return ok(reply)

    async def _sell_later(self, net: Network, bought, paid, received: int | None, delay: int) -> str:
        """After a confirmed buy: the scheduled-sale card for exactly what arrived, back to the token that was paid."""
        if not received:
            return " I couldn't read how much you received, so I didn't schedule the sale — check the balance, then ask again."
        sale = await self._propose_schedule(net, bought, paid, received, 0, 1, delay, None)
        reason = sale["content"][0]["text"]
        if sale.get("is_error"):
            return f" The buy went through, but I didn't schedule the sale: {reason}"
        return f" The buy went through. For the sale: {reason}"
```

`received` is already set on every success path of `propose_swap`. `_sell_later` runs only when `_succeeded(result)`, so `received` is always bound when used.

- [ ] **Step 4: Schema and prompt**

In `build_mcp_server`, add this to the `propose_swap` schema's `properties`, after `"network"`:

```python
                        "sell_after_seconds": {"type": "integer", "description": "Only when the user also wants to sell what they buy later ('sell it tomorrow' = 86400): seconds after the buy, at least 60. The sale card appears by itself once the buy is confirmed."},
```

In `agent/lazyagent/prompt.py`, add this line directly after the `- Swaps ("swap 100 USDC to ETH", …` line:

```
- "Buy X now and sell it tomorrow / in N hours" → ONE propose_swap with sell_after_seconds (tomorrow = 86400, in 6 hours = 21600). Don't ask about the sale first: its card appears by itself once the buy is confirmed, for exactly the amount received. Report both outcomes in one or two sentences.
```

- [ ] **Step 5: Run the tests**

Run the unit suite from Task 1 Step 5.
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_kyber_tools.py agent/tests/test_schedule_tools.py
git commit -m "feat(agent): buy now, sell later — the sale card follows a confirmed buy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Executor routes custom tokens through KyberSwap

**Files:**
- Modify: `agent/lazyagent/executor.py`
- Test: `agent/tests/test_executor.py`

**Interfaces:**
- Consumes: `kyber.ROUTER`, `kyber.SANDBOX_KYBER_SLIPPAGE_BPS`, `kyber.Kyber`, `kyber.KyberClient`, `kyber.SwapRequest`, `kyber.Verified`, `kyber.verify`; `scheduler.SWAPPER`, `scheduler.token_at`.
- Produces: `executor.kyber_calls(order: Order, v: Verified) -> list[Call]`; `Executor(targets, dexalot, kyber: Kyber | None = None, key: str = EXECUTOR_KEY)`.

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_executor.py`, moving the imports up into its import block:

```python
import pytest
from fakes import FakeKyber, FakeQuoter

from lazyagent.executor import ExecutorError
from lazyagent.kyber import ROUTER
from lazyagent.transfers import TransferError
from lazyagent.uniswap import encode_erc20_approve

COQ = "0x420FcA0121DC28039145009570975747295f2329"


async def test_custom_token_order_goes_through_kyberswap_with_the_swapper_as_receiver():
    kyber = FakeKyber(out=10**18)
    calls = await Executor([], None, kyber=kyber).build_calls(Target(AVALANCHE, FakeChain(), None, None), order(COQ, WAVAX.address, amount=10**24), 0)
    assert kyber.routes == [("avalanche", COQ, WAVAX.address, 10**24)]
    assert kyber.builds[0][1] == SWAPPER
    assert [c[0] for c in calls] == [COQ, ROUTER]
    assert calls[0] == (COQ, 0, encode_erc20_approve(ROUTER, 10**24))
    assert calls[1][1] == 0 and calls[1][2].startswith("0xe21fd0e9")


async def test_kyber_build_paying_someone_else_is_refused():
    kyber = FakeKyber(out=10**18, tamper=lambda d: d[:6] + ("0x" + "11" * 20,) + d[7:])
    with pytest.raises(TransferError, match="wrong recipient"):
        await Executor([], None, kyber=kyber).build_calls(Target(AVALANCHE, FakeChain(), None, None), order(COQ, WAVAX.address), 0)


async def test_custom_token_without_kyber_is_refused():
    with pytest.raises(ExecutorError, match="KyberSwap"):
        await Executor([], None).build_calls(Target(AVALANCHE, FakeChain(), None, None), order(COQ, WAVAX.address), 0)


async def test_builtin_pair_with_a_venue_route_keeps_uniswap():
    kyber = FakeKyber()
    quoter = FakeQuoter(lambda route, amount: 5 if route.hops == (Hop(500, 10),) and len(route.currencies) == 2 else None)
    calls = await Executor([], None, kyber=kyber).build_calls(Target(ETHEREUM, FakeChain(), None, quoter), order(USDC.address, WETH.address), 0)
    assert calls[-1][0] == UNIVERSAL_ROUTER and kyber.routes == []


async def test_builtin_pair_without_a_venue_route_falls_back_to_kyber():
    kyber = FakeKyber(out=10**18)
    t = Target(ETHEREUM, FakeChain(), None, FakeQuoter(lambda route, amount: None))
    calls = await Executor([], None, kyber=kyber).build_calls(t, order(USDC.address, WETH.address), 0)
    assert calls[-1][0] == ROUTER and kyber.routes[0][0] == "ethereum"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_executor.py`
Expected: FAIL. `Executor.__init__` has no `kyber`, and custom tokens raise "order uses a token this executor doesn't route".

- [ ] **Step 3: Implement**

In `agent/lazyagent/executor.py`, add these imports:

```python
from .kyber import ROUTER as KYBER_ROUTER
from .kyber import SANDBOX_KYBER_SLIPPAGE_BPS, Kyber, KyberClient, SwapRequest, Verified, verify
from .transfers import TransferError
```

After `dexalot_calls`, add:

```python
def kyber_calls(order: Order, v: Verified) -> list[Call]:
    """The order's ERC-20 input (WETH/WAVAX included — no unwrap) straight into Kyber's router; the Swapper sweeps the output."""
    return [(order.token_in, 0, encode_erc20_approve(KYBER_ROUTER, order.amount_in)), (KYBER_ROUTER, 0, v.data)]
```

Change `Executor.__init__` to `def __init__(self, targets: list[Target], dexalot: Quotes | None, kyber: Kyber | None = None, key: str = EXECUTOR_KEY):` and store `self.kyber = kyber`.

Replace `build_calls` with the three methods below. `_venue_calls` is the old body from `wrapped = …` onward, unchanged:

```python
    async def build_calls(self, t: Target, order, now: int) -> list:
        """The network's venue for built-in pairs it can route; KyberSwap for custom tokens and everything else."""
        net = t.net
        pay, get = token_at(net, order.token_in), token_at(net, order.token_out)
        if pay is not None and get is not None:
            try:
                return await self._venue_calls(t, order, pay, get, now)
            except (ExecutorError, TransferError) as e:
                if self.kyber is None:
                    raise
                log.info("%s: order #%d falls back to KyberSwap (%s)", net.name, order.id, e)
        if self.kyber is None:
            raise ExecutorError("order needs KyberSwap (custom token or no venue route), which isn't configured")
        return await self._kyber_route(net, order)

    async def _venue_calls(self, t: Target, order, pay, get, now: int) -> list:
        net = t.net
        wrapped = wrapped_token(net).address
        a, b = routing_token(pay, net), routing_token(get, net)
        if net.swap_venue == "dexalot":
            if self.dexalot is None:
                raise ExecutorError("no Dexalot quote source")
            quote = await self.dexalot.quote(asset_of(a), asset_of(b), order.amount_in, SWAPPER)
            o = quote["order"]
            if o["taker"].lower() != SWAPPER.lower() or int(o["takerAmount"]) != order.amount_in:
                raise ExecutorError("Dexalot quote doesn't match the order")
            return dexalot_calls(order, quote, wrapped)
        found = await best_route(t.quoter, currency_of(a), currency_of(b), order.amount_in)
        if found is None:
            raise ExecutorError(f"no Uniswap v4 route {pay.symbol} → {get.symbol}")
        return uniswap_calls(order, pay, found[0], now, wrapped)

    async def _kyber_route(self, net: Network, order) -> list:
        req = SwapRequest(order.token_in, order.token_out, order.amount_in, SWAPPER, SANDBOX_KYBER_SLIPPAGE_BPS)
        summary = (await self.kyber.route(net.key, req.token_in, req.token_out, req.amount))["routeSummary"]
        built = await self.kyber.build(net.key, summary, SWAPPER, req.slippage_bps)
        # verify(): pinned router, exact input, the Swapper as receiver, no fee receivers. The contract's minOut is the real guard.
        return kyber_calls(order, verify(built, req, int(summary.get("amountOut") or 0)))
```

In `main()`, change the last line to `asyncio.run(Executor(targets, SandboxQuotes(s.faucet_url), kyber=KyberClient()).run_forever())`.

- [ ] **Step 4: Run the tests**

Run: `uv run --directory agent pytest -q tests/test_executor.py`, then the unit suite from Task 1 Step 5.
Expected: all PASS, including the existing tick tests (`FakeExecutor` calls `super().__init__(targets, None)`, which still works).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/executor.py agent/tests/test_executor.py
git commit -m "feat(agent): executor sells custom tokens through KyberSwap with the Swapper as receiver

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: End-to-end fork test and docs

**Files:**
- Modify: `agent/tests/test_scheduler_fork.py`, `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–3; fixtures `avax_sandbox` (agent/tests/conftest.py), `deploy_scheduler`; helpers `setup_account`, `auto_approve`, `warp`, `balance_of` in `test_scheduler_fork.py`; `KyberClient`, `NATIVE`, `usd_price` (`lazyagent.kyber`).

- [ ] **Step 1: Write the fork test**

Append to `agent/tests/test_scheduler_fork.py` (merge the imports into its header):

```python
import pytest

from lazyagent.kyber import NATIVE, KyberClient, usd_price
from lazyagent.tokens import Token
from lazyagent.transfers import TransferError

COQ = "0x420FcA0121DC28039145009570975747295f2329"


async def test_buy_coq_then_the_scheduled_sale_runs_through_kyberswap(avax_sandbox):
    rpc, url = avax_sandbox
    kyber = KyberClient()
    try:
        await kyber.route("avalanche", NATIVE, COQ, 10**18)
    except TransferError as e:
        pytest.skip(f"KyberSwap API not reachable: {e}")
    deploy_scheduler(rpc)
    chain = RpcChain(rpc, poa=True, custom_price=usd_price(kyber, AVALANCHE))
    account = await setup_account(chain.w3)  # a random address: Kyber rejects Anvil's well-known ones
    proposals = Proposals()
    tools = WalletTools(FakeChain(), auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=chain, dexalot=SandboxQuotes(url), kyber=kyber)
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ, "amount": "1", "sell_after_seconds": 60})
    text = result["content"][0]["text"]
    assert "Swapped 1 AVAX for" in text and "Scheduled" in text, text

    coq = Token("COQ", COQ, 18, custom=True)
    [order] = await read_orders(chain, account.address)
    assert order.amount_in == await chain.token_balance(coq, account.address)  # exactly what the buy delivered

    await warp(chain.w3, 61)
    wavax = wrapped_token(AVALANCHE)
    before = await balance_of(chain, wavax, account.address)
    ex = Executor([Target(AVALANCHE, chain, chain.w3, None)], SandboxQuotes(url), kyber=kyber)
    assert len(await ex.tick()) == 1
    assert await chain.token_balance(coq, account.address) == 0
    assert await balance_of(chain, wavax, account.address) - before >= order.min_out
```

- [ ] **Step 2: Run it**

Run: `uv run --directory agent pytest -v tests/test_scheduler_fork.py`
Expected: 5 PASS, or this new test SKIPS if the KyberSwap API is unreachable. The root `.env` must exist. If `tick()` returns `[]`, inspect the executor's warning log line for the skipped order (the Kyber build or verify reason) and fix the cause. Don't weaken the assertions.

- [ ] **Step 3: Docs**

`CLAUDE.md`: after the line starting `- The scheduler address is pinned in four files`, add:

```
- Buy now, sell later: `propose_swap(sell_after_seconds)` sends a scheduled-sale card right after a confirmed buy, for exactly the amount received (two cards, never one). One-run orders with a start delay use a 50% price floor (`DELAYED_SALE_DISCOUNT_BPS`); recurring and immediate orders keep 5%. The executor routes custom tokens (and pairs its venue can't route) through KyberSwap, with the Swapper as receiver and `kyber.verify()` checking the build. Design: `docs/superpowers/specs/2026-10-16-lazywallet-buy-then-sell-design.md`.
```

`README.md`: in the list of example prompts (the one containing "Give me test funds"), add `- "Buy 1 AVAX of COQ and sell it tomorrow" (buy card, then the scheduled-sale card)`.

- [ ] **Step 4: Full verification**

Run: `pnpm test:py && pnpm test:contracts && pnpm --filter wallet test && pnpm build && pnpm lint`
Expected: all PASS, and lint shows 0 errors.

- [ ] **Step 5: Commit**

```bash
git add agent/tests/test_scheduler_fork.py CLAUDE.md README.md
git commit -m "test(agent): buy COQ then the scheduled sale runs through KyberSwap on a fork; docs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
