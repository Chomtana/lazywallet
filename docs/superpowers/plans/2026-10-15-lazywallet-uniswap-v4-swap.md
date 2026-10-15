# LazyWallet Phase 3 (Uniswap v4 Swaps) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact-input Uniswap v4 swaps (best hookless route, 1-hop or 2-hop via ETH, ETH↔WETH wrap) that the agent proposes as one multi-step confirm card and the browser executes in order.

**Architecture:** `agent/lazyagent/uniswap.py` holds verified addresses, calldata encoders and route search over a `Quoter`; `swaps.py` holds pure swap rules (slippage, minimum, price impact, approval planning, gas reserve, card rows). A new `propose_swap` tool builds `steps` and waits for the browser like transfers do. The confirm protocol changes from one `request` to `steps: [{label, request}]` everywhere; the browser runs steps sequentially with progress.

**Tech Stack:** Python (eth_abi, web3.py 8, claude-agent-sdk), React + viem, pytest/Vitest, Anvil fork.

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-uniswap-v4-swap-design.md`

## Global Constraints

- Addresses: UniversalRouter `0x66a9893cc07d91d95644aedd05d03f95e1dba8af`, Permit2 `0x000000000022D473030F116dDEE9F6B43aC78BA3`, V4Quoter `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203`, WETH `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`. Native ETH currency = `0x0000000000000000000000000000000000000000`.
- Fee tiers (fee, tickSpacing): (100,1), (500,10), (3000,60), (10000,200); hooks always zero.
- Action bytes: V4_SWAP 0x10; SWAP_EXACT_IN_SINGLE 0x06, SWAP_EXACT_IN 0x07, SETTLE_ALL 0x0c, TAKE_ALL 0x0f.
- Slippage default 1% (100 bps), allowed 0.01–5%. Price impact limit 15%. Deadline = fork block timestamp + 1200 s. Permit2 approval expiry = block timestamp + 1800 s.
- Approvals sized to the swap amount, never unlimited. USDT: approve-to-0 step before changing a nonzero allowance.
- Gas reserve per step kind: approve 60k, permit2 60k, wrap 60k, 1-hop swap 170k, 2-hop swap 220k; reserve = sum × gas price × `FEE_HEADROOM` (2).
- The model never writes calldata; Python builds every request.
- Confirm protocol: `tx.steps: [{label, request}]` replaces `tx.request` for all agent cards; `tx_result` adds `hashes`, `failed_step` (0-based); `hash` = hash of the last broadcast step, or of the failing step if it was broadcast, else absent.
- Existing tests must keep passing after updating their `request` → `steps` expectations.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Swap whose output is ETH: the before/after balance delta is reduced by gas paid → reported as "about … after network fees", never as an exact figure. (Task 5)
2. USDT input with an existing nonzero allowance smaller than the amount → a "Reset USDT allowance" step precedes "Allow USDT". (Task 3 + Task 5)
3. Permit2 allowance that is large enough but expired (or expiring within 60 s) → a fresh "Allow Uniswap router" step. (Task 3)
4. Card left open while the fork is reset / price moves → swap reverts at its step; the agent names the step, says earlier approvals were harmless and suggests slippage moved. (Task 4 + Task 5)
5. A pair with no hookless v4 liquidity or a huge amount (impact > 15%) → plain-text refusal, no card. (Task 5 + Task 6 fork tests)

---

## File Structure

```
agent/lazyagent/uniswap.py        NEW addresses, Hop/Route, pool_key/pool_id, encoders, decoders, candidate_routes, Quoter, ChainQuoter, best_route
agent/lazyagent/swaps.py          NEW Step, parse_slippage, min_out, price_impact, display_units, route_label, approval_steps, gas_reserve, check_swap_funds, swap_rows
agent/lazyagent/outcome.py        NEW outcome_text() shared by transfers and swaps
agent/lazyagent/devsigner.py      NEW execute_steps() — dev/test signer (demo + fork tests)
agent/lazyagent/chain.py          + call(), block_timestamp()
agent/lazyagent/tools.py          transfers emit steps; + propose_swap; quoter injection; tool list
agent/lazyagent/prompt.py         swap guidance
agent/scripts/demo.py             steps + swap prompts
agent/tests/test_uniswap.py, test_swaps.py, test_outcome.py, test_swap_tools.py, test_swap_fork.py  NEW
agent/tests/fakes.py              + call/block_timestamp, FakeQuoter
agent/tests/test_tools.py, test_server.py                                                       steps expectations
apps/wallet/src/types.ts          TxStep; TxDraft.steps replaces request
apps/wallet/src/agent/protocol.ts steps + tx_result fields
apps/wallet/src/chain/executeTx.ts + executeSteps, progressText; statusPatch(outcome, steps)
apps/wallet/src/agent/chatReducer.ts, useAgentChat.ts            steps
apps/wallet/src/chat/cards/ConfirmCard.tsx                        steps list
README.md, CLAUDE.md, agent/README.md                             docs
```

---

### Task 1: Uniswap v4 encoders and route search

**Files:**
- Create: `agent/lazyagent/uniswap.py`
- Test: `agent/tests/test_uniswap.py`

**Interfaces:**
- Consumes: `tokens.Token`, `tokens.TOKENS`, `chain.Chain` (only `call`, added in Task 2 — `ChainQuoter` is exercised in Task 2)
- Produces: constants `ZERO`, `UNIVERSAL_ROUTER`, `PERMIT2`, `V4_QUOTER`, `FEE_TIERS`, `WETH_DEPOSIT`; `Hop(fee, tick_spacing)`; `Route(currencies: tuple[str, ...], hops: tuple[Hop, ...])`; `currency_of(token) -> str`; `symbol_of(currency) -> str`; `pool_key(a, b, hop) -> tuple`; `pool_id(key) -> str`; `encode_swap(route, amount_in, min_out, deadline) -> str`; `encode_quote(route, amount_in) -> str`; `decode_quote(data: bytes) -> int`; `encode_erc20_approve(spender, amount) -> str`; `encode_permit2_approve(token, spender, amount, expiration) -> str`; `encode_erc20_allowance(owner, spender) -> str`; `encode_permit2_allowance(owner, token, spender) -> str`; `decode_permit2_allowance(data) -> tuple[int, int]`; `encode_weth_withdraw(amount) -> str`; `candidate_routes(cin, cout) -> list[Route]`; `Quoter` protocol `async quote(route, amount_in) -> int | None`; `ChainQuoter(chain)`; `async best_route(quoter, cin, cout, amount_in) -> tuple[Route, int] | None`.

- [ ] **Step 1: Write failing tests**

`agent/tests/test_uniswap.py`:
```python
from eth_abi import decode, encode
from web3 import Web3

from lazyagent.uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    ZERO,
    Hop,
    Route,
    best_route,
    candidate_routes,
    currency_of,
    decode_permit2_allowance,
    decode_quote,
    encode_erc20_allowance,
    encode_erc20_approve,
    encode_permit2_allowance,
    encode_permit2_approve,
    encode_quote,
    encode_swap,
    encode_weth_withdraw,
    pool_id,
    pool_key,
    symbol_of,
)
from lazyagent.tokens import ETH, find_token

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WBTC = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
OWNER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def test_currency_and_symbol():
    assert currency_of(ETH) == ZERO
    assert currency_of(find_token("USDC")) == USDC
    assert symbol_of(ZERO) == "ETH"
    assert symbol_of(USDC.lower()) == "USDC"


def test_pool_key_sorts_currencies_and_pool_id_matches_mainnet():
    key = pool_key(USDC, ZERO, Hop(500, 10))
    assert key == (ZERO, USDC, 500, 10, ZERO)
    # ETH/USDC 0.05% v4 pool id, verified on mainnet via StateView
    assert pool_id(key) == "0x21c67e77068de97969ba93d4aab21826d33ca12bb9f565d8496e8fda8a82ca27"


def test_single_hop_swap_calldata_matches_verified_recipe():
    data = encode_swap(Route((ZERO, USDC), (Hop(500, 10),)), 10**18, 2_330_000_000, 1_800_000_000)
    assert data.startswith("0x3593564c")
    assert Web3.keccak(hexstr=data).hex() == "76d036534e7538c2ebebf5ffa072b9caa74bc8c5139be272e1542b86b8846d2c"


def test_two_hop_swap_calldata_matches_verified_recipe():
    route = Route((USDC, ZERO, WBTC), (Hop(500, 10), Hop(500, 10)))
    data = encode_swap(route, 500 * 10**6, 6_000_000, 1_800_000_000)
    assert Web3.keccak(hexstr=data).hex() == "6be1ace07a64225f8104b8da301b66330840f16f561ccf57b31b10f2befcf15d"


def test_quote_calldata_selectors():
    assert encode_quote(Route((ZERO, USDC), (Hop(500, 10),)), 10**18)[:10] == "0x" + Web3.keccak(
        text="quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))"
    )[:4].hex()
    assert encode_quote(Route((USDC, ZERO, WBTC), (Hop(500, 10), Hop(500, 10))), 10**6)[:10] == "0x" + Web3.keccak(
        text="quoteExactInput((address,(address,uint24,int24,address,bytes)[],uint128))"
    )[:4].hex()
    assert decode_quote(encode(["uint256", "uint256"], [123, 456])) == 123


def test_approval_and_weth_encoders():
    approve = encode_erc20_approve(PERMIT2, 5)
    assert approve[:10] == "0x095ea7b3"
    spender, amount = decode(["address", "uint256"], bytes.fromhex(approve[10:]))
    assert (spender.lower(), amount) == (PERMIT2.lower(), 5)
    p2 = encode_permit2_approve(USDC, UNIVERSAL_ROUTER, 7, 1_700_000_000)
    assert p2[:10] == "0x87517c45"
    token, spender, amount, expiration = decode(["address", "address", "uint160", "uint48"], bytes.fromhex(p2[10:]))
    assert (token.lower(), spender.lower(), amount, expiration) == (USDC.lower(), UNIVERSAL_ROUTER.lower(), 7, 1_700_000_000)
    assert encode_erc20_allowance(OWNER, PERMIT2)[:10] == "0xdd62ed3e"
    assert encode_permit2_allowance(OWNER, USDC, UNIVERSAL_ROUTER)[:10] == "0x927da105"
    assert decode_permit2_allowance(encode(["uint160", "uint48", "uint48"], [9, 1_700_000_000, 0])) == (9, 1_700_000_000)
    assert encode_weth_withdraw(3)[:10] == "0x2e1a7d4d"


def test_candidate_routes():
    direct = candidate_routes(ZERO, USDC)
    assert len(direct) == 4
    assert all(r.currencies == (ZERO, USDC) for r in direct)
    via_eth = candidate_routes(USDC, WBTC)
    assert len(via_eth) == 4 + 16
    assert via_eth[-1].currencies == (USDC, ZERO, WBTC)


class TableQuoter:
    def __init__(self, table):
        self.table = table

    async def quote(self, route, amount_in):
        return self.table.get(route.hops)


async def test_best_route_picks_highest_output_and_handles_no_liquidity():
    q = TableQuoter({(Hop(500, 10),): 2358, (Hop(3000, 60),): 2356})
    route, out = await best_route(q, ZERO, USDC, 10**18)
    assert route.hops == (Hop(500, 10),) and out == 2358
    assert await best_route(TableQuoter({}), ZERO, USDC, 10**18) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest tests/test_uniswap.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.uniswap'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/uniswap.py`:
```python
"""Uniswap v4 on Ethereum mainnet (and the Sandbox fork): addresses, calldata and route search.

Recipe verified on a mainnet fork: UniversalRouter.execute with V4_SWAP, hookless pools, native ETH = address(0).
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from eth_abi import decode, encode
from web3 import Web3

from .tokens import TOKENS, Token

ZERO = "0x0000000000000000000000000000000000000000"
UNIVERSAL_ROUTER = Web3.to_checksum_address("0x66a9893cc07d91d95644aedd05d03f95e1dba8af")
PERMIT2 = Web3.to_checksum_address("0x000000000022D473030F116dDEE9F6B43aC78BA3")
V4_QUOTER = Web3.to_checksum_address("0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203")
FEE_TIERS = ((100, 1), (500, 10), (3000, 60), (10000, 200))

V4_SWAP = 0x10
SWAP_EXACT_IN_SINGLE, SWAP_EXACT_IN, SETTLE_ALL, TAKE_ALL = 0x06, 0x07, 0x0C, 0x0F
POOL_KEY = "(address,address,uint24,int24,address)"
PATH_KEY = "(address,uint24,int24,address,bytes)"
WETH_DEPOSIT = "0xd0e30db0"


@dataclass(frozen=True)
class Hop:
    fee: int
    tick_spacing: int


@dataclass(frozen=True)
class Route:
    currencies: tuple[str, ...]  # input, optional intermediate, output
    hops: tuple[Hop, ...]


def _call(signature: str, types: list[str], values: list) -> str:
    return "0x" + (Web3.keccak(text=signature)[:4] + encode(types, values)).hex()


def currency_of(token: Token) -> str:
    return ZERO if token.address is None else Web3.to_checksum_address(token.address)


def symbol_of(currency: str) -> str:
    if int(currency, 16) == 0:
        return "ETH"
    return next(t.symbol for t in TOKENS if t.address and t.address.lower() == currency.lower())


def pool_key(a: str, b: str, hop: Hop) -> tuple:
    c0, c1 = sorted((a, b), key=lambda c: int(c, 16))
    return (c0, c1, hop.fee, hop.tick_spacing, ZERO)


def pool_id(key: tuple) -> str:
    return Web3.keccak(encode(["address", "address", "uint24", "int24", "address"], list(key))).to_0x_hex()


def _path(route: Route) -> list[tuple]:
    return [(route.currencies[i + 1], h.fee, h.tick_spacing, ZERO, b"") for i, h in enumerate(route.hops)]


def encode_swap(route: Route, amount_in: int, min_out: int, deadline: int) -> str:
    cin, cout = route.currencies[0], route.currencies[-1]
    if len(route.hops) == 1:
        key = pool_key(cin, cout, route.hops[0])
        swap = encode([f"({POOL_KEY},bool,uint128,uint128,bytes)"], [(key, cin == key[0], amount_in, min_out, b"")])
        actions = bytes([SWAP_EXACT_IN_SINGLE, SETTLE_ALL, TAKE_ALL])
    else:
        swap = encode([f"(address,{PATH_KEY}[],uint128,uint128)"], [(cin, _path(route), amount_in, min_out)])
        actions = bytes([SWAP_EXACT_IN, SETTLE_ALL, TAKE_ALL])
    params = [swap, encode(["address", "uint256"], [cin, amount_in]), encode(["address", "uint256"], [cout, min_out])]
    v4_input = encode(["bytes", "bytes[]"], [actions, params])
    return _call("execute(bytes,bytes[],uint256)", ["bytes", "bytes[]", "uint256"], [bytes([V4_SWAP]), [v4_input], deadline])


def encode_quote(route: Route, amount_in: int) -> str:
    cin, cout = route.currencies[0], route.currencies[-1]
    if len(route.hops) == 1:
        key = pool_key(cin, cout, route.hops[0])
        params = f"({POOL_KEY},bool,uint128,bytes)"
        return _call(f"quoteExactInputSingle({params})", [params], [(key, cin == key[0], amount_in, b"")])
    params = f"(address,{PATH_KEY}[],uint128)"
    return _call(f"quoteExactInput({params})", [params], [(cin, _path(route), amount_in)])


def decode_quote(data: bytes) -> int:
    return decode(["uint256", "uint256"], data)[0]


def encode_erc20_approve(spender: str, amount: int) -> str:
    return _call("approve(address,uint256)", ["address", "uint256"], [spender, amount])


def encode_permit2_approve(token: str, spender: str, amount: int, expiration: int) -> str:
    return _call("approve(address,address,uint160,uint48)", ["address", "address", "uint160", "uint48"], [token, spender, amount, expiration])


def encode_erc20_allowance(owner: str, spender: str) -> str:
    return _call("allowance(address,address)", ["address", "address"], [owner, spender])


def encode_permit2_allowance(owner: str, token: str, spender: str) -> str:
    return _call("allowance(address,address,address)", ["address", "address", "address"], [owner, token, spender])


def decode_permit2_allowance(data: bytes) -> tuple[int, int]:
    amount, expiration, _nonce = decode(["uint160", "uint48", "uint48"], data)
    return amount, expiration


def encode_weth_withdraw(amount: int) -> str:
    return _call("withdraw(uint256)", ["uint256"], [amount])


def candidate_routes(cin: str, cout: str) -> list[Route]:
    routes = [Route((cin, cout), (Hop(f, t),)) for f, t in FEE_TIERS]
    if ZERO not in (cin, cout):
        routes += [Route((cin, ZERO, cout), (Hop(*a), Hop(*b))) for a in FEE_TIERS for b in FEE_TIERS]
    return routes


class Quoter(Protocol):
    async def quote(self, route: Route, amount_in: int) -> int | None: ...


class ChainQuoter:
    """Quotes through V4Quoter with eth_call; a missing or empty pool yields None."""

    def __init__(self, chain) -> None:
        self.chain = chain

    async def quote(self, route: Route, amount_in: int) -> int | None:
        try:
            out = decode_quote(await self.chain.call(V4_QUOTER, encode_quote(route, amount_in)))
        except Exception:
            return None
        return out or None


async def best_route(quoter: Quoter, cin: str, cout: str, amount_in: int) -> tuple[Route, int] | None:
    routes = candidate_routes(cin, cout)
    quotes = await asyncio.gather(*(quoter.quote(r, amount_in) for r in routes))
    found = [(q, i) for i, q in enumerate(quotes) if q]
    if not found:
        return None
    out, i = max(found)
    return routes[i], out
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS (whole agent suite; fork tests pass with `ETH_RPC_URL`).

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add Uniswap v4 calldata encoders and route search"
```

---

### Task 2: Chain calls and on-fork quoting

**Files:**
- Modify: `agent/lazyagent/chain.py`, `agent/tests/fakes.py`
- Test: `agent/tests/test_chain.py` (append), `agent/tests/test_quote_fork.py`

**Interfaces:**
- Produces: `Chain.call(to: str, data: str) -> bytes`, `Chain.block_timestamp() -> int` (protocol + `RpcChain`); `FakeChain.call` returns `self.call_responses.get(data[:10], bytes(96))`, `FakeChain.block_timestamp` returns `self.now` (default `1_700_000_000`); `fakes.FakeQuoter(fn)` with `async quote(route, amount_in) -> fn(route, amount_in)`.

- [ ] **Step 1: Write failing tests**

Append to `agent/tests/test_chain.py`:
```python
async def test_call_and_block_timestamp(fork_rpc):
    chain = RpcChain(fork_rpc)
    usdc = find_token("USDC")
    decimals = await chain.call(usdc.address, "0x313ce567")  # decimals()
    assert int.from_bytes(decimals, "big") == 6
    assert await chain.block_timestamp() > 1_700_000_000
```

`agent/tests/test_quote_fork.py`:
```python
from lazyagent.chain import RpcChain
from lazyagent.tokens import find_token
from lazyagent.uniswap import ZERO, ChainQuoter, Hop, Route, best_route, currency_of

USDC = currency_of(find_token("USDC"))
DAI = currency_of(find_token("DAI"))


async def test_quotes_eth_usdc_on_fork(fork_rpc):
    quoter = ChainQuoter(RpcChain(fork_rpc))
    out = await quoter.quote(Route((ZERO, USDC), (Hop(500, 10),)), 10**18)
    assert out is not None and out > 500 * 10**6


async def test_missing_pool_quotes_none(fork_rpc):
    quoter = ChainQuoter(RpcChain(fork_rpc))
    # verified: no hookless ETH/DAI pool at 0.01%
    assert await quoter.quote(Route((ZERO, DAI), (Hop(100, 1),)), 10**18) is None


async def test_best_route_on_fork(fork_rpc):
    found = await best_route(ChainQuoter(RpcChain(fork_rpc)), ZERO, USDC, 10**18)
    assert found is not None
    route, out = found
    assert route.currencies == (ZERO, USDC)
    assert out > 500 * 10**6
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest tests/test_chain.py tests/test_quote_fork.py -q`
Expected: FAIL — `AttributeError: 'RpcChain' object has no attribute 'call'` (and the quote tests fail because `ChainQuoter` swallows that AttributeError into `None`).

- [ ] **Step 3: Implement**

In `agent/lazyagent/chain.py`, add to the `Chain` protocol:
```python
    async def call(self, to: str, data: str) -> bytes: ...
    async def block_timestamp(self) -> int: ...
```
and to `RpcChain`:
```python
    async def call(self, to: str, data: str) -> bytes:
        return bytes(await self.w3.eth.call({"to": Web3.to_checksum_address(to), "data": data}))

    async def block_timestamp(self) -> int:
        return (await self.w3.eth.get_block("latest"))["timestamp"]
```

In `agent/tests/fakes.py`, in `FakeChain.__init__` add:
```python
        self.call_responses: dict[str, bytes] = {}
        self.now = 1_700_000_000
```
and methods:
```python
    async def call(self, to: str, data: str) -> bytes:
        return self.call_responses.get(data[:10], bytes(96))

    async def block_timestamp(self) -> int:
        return self.now
```
and append:
```python
class FakeQuoter:
    def __init__(self, fn):
        self.fn = fn

    async def quote(self, route, amount_in):
        return self.fn(route, amount_in)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS (fork tests require `ETH_RPC_URL`; they are present in this repo).

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add raw chain calls and on-fork v4 quoting"
```

---

### Task 3: Pure swap rules

**Files:**
- Create: `agent/lazyagent/swaps.py`
- Test: `agent/tests/test_swaps.py`

**Interfaces:**
- Consumes: Task 1 encoders/constants, `transfers.TransferError`, `transfers.FEE_HEADROOM`, `transfers.format_units`, `transfers.format_usd`, `transfers.short`
- Produces: `DEFAULT_SLIPPAGE_BPS=100`, `MAX_SLIPPAGE_BPS=500`, `MAX_PRICE_IMPACT=0.15`, `DEADLINE_S=1200`, `PERMIT2_EXPIRY_S=1800`, `GAS` dict; `Step(label, request, gas)` with `to_json()`; `parse_slippage(text) -> int`; `min_out(quote, bps) -> int`; `price_impact(amount_in, amount_out, probe_in, probe_out) -> float`; `display_units(amount, decimals) -> str`; `route_label(route) -> str`; `approval_steps(token, erc20_allowance, permit2_amount, permit2_expiration, amount, now) -> list[Step]`; `gas_reserve(steps, gas_price) -> int`; `check_swap_funds(token_in, amount, balance, eth_balance, reserve) -> None`; `swap_rows(sender, token_in, token_out, amount, expected, minimum, label, impact, fee_usd) -> list[dict]`.

- [ ] **Step 1: Write failing tests**

`agent/tests/test_swaps.py`:
```python
import pytest

from lazyagent.swaps import (
    GAS,
    Step,
    approval_steps,
    check_swap_funds,
    display_units,
    gas_reserve,
    min_out,
    parse_slippage,
    price_impact,
    route_label,
    swap_rows,
)
from lazyagent.tokens import ETH, find_token
from lazyagent.transfers import TransferError
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, ZERO, Hop, Route

USDC = find_token("USDC")
USDT = find_token("USDT")
WBTC = find_token("WBTC")
NOW = 1_700_000_000


@pytest.mark.parametrize(("text", "bps"), [(None, 100), ("", 100), ("0.5", 50), ("1%", 100), (" 5 ", 500), ("0.01", 1)])
def test_parse_slippage(text, bps):
    assert parse_slippage(text) == bps


@pytest.mark.parametrize("text", ["0", "5.5", "10", "-1", "abc", "0.005", "nan"])
def test_parse_slippage_rejects(text):
    with pytest.raises(TransferError):
        parse_slippage(text)


def test_min_out_rounds_down():
    assert min_out(1_000_000, 100) == 990_000
    assert min_out(999, 100) == 989


def test_price_impact():
    assert price_impact(1000, 2_000_000, 1, 2000) == 0.0
    assert price_impact(1000, 1_000_000, 1, 2000) == pytest.approx(0.5)
    assert price_impact(1000, 2_100_000, 1, 2000) == 0.0  # better than reference → 0
    assert price_impact(1000, 5, 1, 0) == 0.0


def test_display_units():
    assert display_units(2_358_835_338, 6) == "2358.83"
    assert display_units(423_670_123_456_789_012, 18) == "0.42367"
    assert display_units(10_000 * 10**6, 6) == "10000"
    assert display_units(0, 18) == "0"


def test_route_label():
    usdc = USDC.address
    wbtc = WBTC.address
    assert route_label(Route((ZERO, usdc), (Hop(500, 10),))) == "ETH → USDC · Uniswap v4 0.05%"
    assert route_label(Route((usdc, ZERO, wbtc), (Hop(500, 10), Hop(3000, 60)))) == "USDC → ETH → WBTC · Uniswap v4 0.05% / 0.3%"


def labels(steps):
    return [s.label for s in steps]


def test_approval_steps_none_when_already_allowed():
    assert approval_steps(USDC, 10**6, 10**6, NOW + 600, 10**6, NOW) == []


def test_approval_steps_both_when_nothing_allowed():
    steps = approval_steps(USDC, 0, 0, 0, 5 * 10**6, NOW)
    assert labels(steps) == ["Allow USDC", "Allow Uniswap router"]
    assert steps[0].request["to"] == USDC.address
    assert steps[1].request["to"] == PERMIT2
    assert UNIVERSAL_ROUTER.lower()[2:] in steps[1].request["data"]


def test_approval_steps_reapprove_expired_permit2():
    assert labels(approval_steps(USDC, 10**6, 10**6, NOW + 30, 10**6, NOW)) == ["Allow Uniswap router"]


def test_approval_steps_usdt_resets_nonzero_allowance():
    steps = approval_steps(USDT, 5, 0, 0, 10**6, NOW)
    assert labels(steps) == ["Reset USDT allowance", "Allow USDT", "Allow Uniswap router"]
    assert steps[0].request["data"].endswith("0" * 64)


def test_gas_reserve_and_funds():
    steps = [Step("a", {}, GAS["approve"]), Step("s", {}, GAS["swap1"])]
    assert gas_reserve(steps, 10**9) == (60_000 + 170_000) * 10**9 * 2
    check_swap_funds(ETH, 10**18, 2 * 10**18, 2 * 10**18, 10**15)
    with pytest.raises(TransferError, match="only have"):
        check_swap_funds(USDC, 2 * 10**6, 10**6, 10**18, 10**15)
    with pytest.raises(TransferError, match="network fees"):
        check_swap_funds(ETH, 10**18, 10**18, 10**18, 10**15)
    with pytest.raises(TransferError, match="network fees"):
        check_swap_funds(USDC, 10**6, 10**6, 10**14, 10**15)


def test_swap_rows():
    rows = swap_rows(
        "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", ETH, USDC, 10**18, 2_358_835_338, 2_335_246_984,
        "ETH → USDC · Uniswap v4 0.05%", 0.0012, 1.23,
    )
    assert rows == [
        {"label": "From", "value": "0xf39F…2266"},
        {"label": "You pay", "value": "1 ETH"},
        {"label": "Expected", "value": "≈ 2358.83 USDC"},
        {"label": "Minimum received", "value": "2335.24 USDC"},
        {"label": "Route", "value": "ETH → USDC · Uniswap v4 0.05%"},
        {"label": "Price impact", "value": "0.12%"},
        {"label": "Network fee", "value": "~$1.23"},
        {"label": "Network", "value": "Sandbox"},
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest tests/test_swaps.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lazyagent.swaps'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/swaps.py`:
```python
import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from .tokens import Token
from .transfers import FEE_HEADROOM, TransferError, format_units, format_usd, short
from .uniswap import PERMIT2, UNIVERSAL_ROUTER, Route, encode_erc20_approve, encode_permit2_approve, symbol_of

DEFAULT_SLIPPAGE_BPS = 100
MAX_SLIPPAGE_BPS = 500
MAX_PRICE_IMPACT = 0.15
DEADLINE_S = 20 * 60
PERMIT2_EXPIRY_S = 30 * 60
GAS = {"approve": 60_000, "permit2": 60_000, "wrap": 60_000, "swap1": 170_000, "swap2": 220_000}
_PERCENT = re.compile(r"^[0-9]*\.?[0-9]+$")


@dataclass(frozen=True)
class Step:
    label: str
    request: dict
    gas: int

    def to_json(self) -> dict:
        return {"label": self.label, "request": self.request}


def parse_slippage(text: str | None) -> int:
    if text is None or not str(text).strip():
        return DEFAULT_SLIPPAGE_BPS
    cleaned = str(text).strip().rstrip("%").strip()
    if not _PERCENT.match(cleaned):
        raise TransferError(f'"{text}" isn\'t a valid slippage. Use a percentage like 0.5.')
    bps = Decimal(cleaned) * 100
    if bps != bps.to_integral_value() or not 1 <= bps <= MAX_SLIPPAGE_BPS:
        raise TransferError("Slippage must be between 0.01% and 5%.")
    return int(bps)


def min_out(quote: int, bps: int) -> int:
    return quote * (10_000 - bps) // 10_000


def price_impact(amount_in: int, amount_out: int, probe_in: int, probe_out: int) -> float:
    """How much worse the full trade's rate is than a tiny trade's rate on the same route."""
    if not probe_out or not amount_in:
        return 0.0
    return max(1 - (amount_out * probe_in) / (probe_out * amount_in), 0.0)


def display_units(amount: int, decimals: int) -> str:
    """About six significant digits, rounded down — for card display only."""
    value = Decimal(amount).scaleb(-decimals)
    if value == 0:
        return "0"
    places = max(0, 6 - value.adjusted() - 1)
    return format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN).normalize(), "f")


def _fee_label(fee: int) -> str:
    return f"{fee / 10_000:g}%"


def route_label(route: Route) -> str:
    path = " → ".join(symbol_of(c) for c in route.currencies)
    fees = " / ".join(_fee_label(h.fee) for h in route.hops)
    return f"{path} · Uniswap v4 {fees}"


def approval_steps(
    token: Token, erc20_allowance: int, permit2_amount: int, permit2_expiration: int, amount: int, now: int
) -> list[Step]:
    steps: list[Step] = []
    if erc20_allowance < amount:
        if token.symbol == "USDT" and erc20_allowance > 0:
            # USDT reverts when changing one nonzero allowance to another.
            steps.append(Step("Reset USDT allowance", _tx(token.address, encode_erc20_approve(PERMIT2, 0)), GAS["approve"]))
        steps.append(Step(f"Allow {token.symbol}", _tx(token.address, encode_erc20_approve(PERMIT2, amount)), GAS["approve"]))
    if permit2_amount < amount or permit2_expiration <= now + 60:
        data = encode_permit2_approve(token.address, UNIVERSAL_ROUTER, amount, now + PERMIT2_EXPIRY_S)
        steps.append(Step("Allow Uniswap router", _tx(PERMIT2, data), GAS["permit2"]))
    return steps


def _tx(to: str, data: str, value: int = 0) -> dict:
    return {"to": to, "value": str(value), "data": data}


def gas_reserve(steps: list[Step], gas_price: int) -> int:
    return sum(s.gas for s in steps) * gas_price * FEE_HEADROOM


def check_swap_funds(token_in: Token, amount: int, balance: int, eth_balance: int, reserve: int) -> None:
    if amount > balance:
        raise TransferError(f"You only have {format_units(balance, token_in.decimals)} {token_in.symbol}.")
    needed = reserve + (amount if token_in.address is None else 0)
    if needed > eth_balance:
        raise TransferError(
            f"Not enough ETH left for the network fees (keep ~{format_units(reserve, 18)} ETH). Try a smaller amount or get test funds."
        )


def swap_rows(
    sender: str,
    token_in: Token,
    token_out: Token,
    amount: int,
    expected: int,
    minimum: int,
    label: str,
    impact: float,
    fee_usd: float,
) -> list[dict]:
    return [
        {"label": "From", "value": short(sender)},
        {"label": "You pay", "value": f"{format_units(amount, token_in.decimals)} {token_in.symbol}"},
        {"label": "Expected", "value": f"≈ {display_units(expected, token_out.decimals)} {token_out.symbol}"},
        {"label": "Minimum received", "value": f"{display_units(minimum, token_out.decimals)} {token_out.symbol}"},
        {"label": "Route", "value": label},
        {"label": "Price impact", "value": f"{impact * 100:.2f}%"},
        {"label": "Network fee", "value": f"~{format_usd(fee_usd)}"},
        {"label": "Network", "value": "Sandbox"},
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add swap rules — slippage, impact, approvals, gas reserve"
```

---

### Task 4: Multi-step confirm protocol (agent side) and dev signer

**Files:**
- Create: `agent/lazyagent/outcome.py`, `agent/lazyagent/devsigner.py`
- Modify: `agent/lazyagent/tools.py` (transfer emits steps, uses `outcome_text`), `agent/tests/test_tools.py`, `agent/tests/test_server.py`, `agent/scripts/demo.py`
- Test: `agent/tests/test_outcome.py`

**Interfaces:**
- Produces: `outcome_text(result: dict | None, steps: list[dict], what: str, success: str, revert_hint: str = "") -> str`; `devsigner.execute_steps(w3: AsyncWeb3, private_key: str, steps: list[dict]) -> dict` returning a `tx_result`-shaped dict (`outcome`, `hashes`, `hash`, `status`, `error`, `failed_step`).

- [ ] **Step 1: Write failing tests**

`agent/tests/test_outcome.py`:
```python
from lazyagent.outcome import outcome_text

ONE = [{"label": "Send", "request": {}}]
THREE = [{"label": "Allow USDC", "request": {}}, {"label": "Allow Uniswap router", "request": {}}, {"label": "Swap USDC → ETH", "request": {}}]


def test_timeout_and_reject():
    assert "didn't respond" in outcome_text(None, ONE, "transfer", "ok")
    assert outcome_text({"outcome": "rejected"}, ONE, "swap", "ok") == "The user rejected the swap. Nothing was sent."


def test_success_passthrough():
    assert outcome_text({"outcome": "approved", "status": "success", "hash": "0x1"}, ONE, "transfer", "Sent!") == "Sent!"


def test_single_step_failures_keep_phase2_wording():
    assert "failed before it was sent: nope" in outcome_text({"outcome": "approved", "error": "nope"}, ONE, "transfer", "ok")
    text = outcome_text({"outcome": "approved", "error": "timeout", "hash": "0xfeed"}, ONE, "transfer", "ok")
    assert "0xfeed" in text and "Don't resend" in text
    assert "reverted" in outcome_text({"outcome": "approved", "status": "reverted", "hash": "0x2"}, ONE, "transfer", "ok")


def test_multi_step_revert_names_step_and_hints():
    result = {"outcome": "approved", "status": "reverted", "hash": "0x3", "failed_step": 2}
    text = outcome_text(result, THREE, "swap", "ok", revert_hint=" The price probably moved more than the 1% slippage.")
    assert "step 3 (Swap USDC → ETH)" in text
    assert "approval steps did go through" in text
    assert "1% slippage" in text


def test_first_step_failure_has_no_harmless_note():
    text = outcome_text({"outcome": "approved", "error": "denied", "failed_step": 0}, THREE, "swap", "ok")
    assert "step 1 (Allow USDC)" in text
    assert "did go through" not in text
```

In `agent/tests/test_tools.py`, in `test_propose_transfer_approved_flow`, replace:
```python
    assert confirm["tx"]["request"] == {"to": ALICE, "value": str(10**17), "data": "0x"}
```
with:
```python
    assert confirm["tx"]["steps"] == [{"label": "Send", "request": {"to": ALICE, "value": str(10**17), "data": "0x"}}]
```

In `agent/tests/test_server.py`, replace `assert confirm["tx"]["request"]["to"] == ALICE` with `assert confirm["tx"]["steps"][0]["request"]["to"] == ALICE`.

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `lazyagent.outcome` missing; `KeyError: 'steps'` in tools/server tests.

- [ ] **Step 3: Implement**

`agent/lazyagent/outcome.py`:
```python
def outcome_text(result: dict | None, steps: list[dict], what: str, success: str, revert_hint: str = "") -> str:
    """Explain a browser tx_result to the model in one or two sentences."""
    if result is None:
        return f"The user didn't respond to the confirmation within 5 minutes, so the {what} wasn't sent."
    if result.get("outcome") == "rejected":
        return f"The user rejected the {what}. Nothing was sent."
    idx = result.get("failed_step")
    at = f" at step {idx + 1} ({steps[idx]['label']})" if isinstance(idx, int) and 0 <= idx < len(steps) and len(steps) > 1 else ""
    earlier = " The earlier approval steps did go through, which is harmless." if isinstance(idx, int) and idx > 0 else ""
    if result.get("error") and result.get("hash"):
        return (
            f"The {what} was broadcast{at} (tx {result['hash']}) but its confirmation couldn't be read "
            f"({result['error']}). Don't resend — ask the user to check their balance first."
        )
    if result.get("error"):
        return f"The {what} failed before it was sent{at}: {result['error']}.{earlier}"
    if result.get("status") == "reverted":
        return f"The {what} reverted{at}. Tx {result.get('hash')}.{earlier}{revert_hint}"
    return success
```

`agent/lazyagent/devsigner.py`:
```python
"""Sign and send confirm-card steps with a local key — for the demo script and fork tests only.
In the app, the browser does this with viem after the user taps Approve."""

from eth_account import Account
from web3 import AsyncWeb3, Web3

GAS_MARGIN = 1.2


async def execute_steps(w3: AsyncWeb3, private_key: str, steps: list[dict]) -> dict:
    account = Account.from_key(private_key)
    chain_id = await w3.eth.chain_id
    hashes: list[str] = []
    for i, step in enumerate(steps):
        req = step["request"]
        tx = {
            "from": account.address,
            "to": Web3.to_checksum_address(req["to"]),
            "value": int(req["value"]),
            "data": req["data"],
            "chainId": chain_id,
            "nonce": await w3.eth.get_transaction_count(account.address),
            "gasPrice": await w3.eth.gas_price,
        }
        try:
            tx["gas"] = int(await w3.eth.estimate_gas(tx) * GAS_MARGIN)
            tx_hash = await w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction)
        except Exception as e:
            return {"outcome": "approved", "hashes": hashes, "error": str(e), "failed_step": i}
        hashes.append(tx_hash.to_0x_hex())
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            return {"outcome": "approved", "hashes": hashes, "hash": hashes[-1], "status": "reverted", "failed_step": i}
    return {"outcome": "approved", "hashes": hashes, "hash": hashes[-1] if hashes else None, "status": "success"}
```

In `agent/lazyagent/tools.py`:
- Add `from .outcome import outcome_text`.
- In `propose_transfer`, replace the confirm-sending block and everything after it (from `human = …` to the final `return ok(f"Sent …")`) with:
```python
        human = f"{format_units(amount, token.decimals)} {token.symbol}"
        label = name or short(to)
        steps = [{"label": "Send", "request": build_request(token, to, amount)}]
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {
                    "title": f"Send {human}",
                    "from": self.ctx.address,
                    "rows": [{"label": "From", "value": short(self.ctx.address)}, *display_rows(token, amount, to, name, price, gas_cost, eth_price)],
                    "steps": steps,
                },
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        return ok(outcome_text(result, steps, "transfer", f"Sent {human} to {label}. Confirmed on Sandbox, tx {result and result.get('hash')}."))
```

In `agent/scripts/demo.py`:
- Replace the whole `approve` function with:
```python
    async def approve(msg: dict) -> None:
        result = await execute_steps(w3, wallet["private_key"], msg["tx"]["steps"])
        print(f"\n  [auto-approved {len(msg['tx']['steps'])} step(s): {result.get('status') or result.get('error')}]")
        await session.handle({"type": "tx_result", "id": msg["id"], **result})
```
- Replace the imports `from eth_account import Account` with `from lazyagent.devsigner import execute_steps`.
- Replace `PROMPTS` with `["What's my balance?", "Send 0.01 ETH to Alice", "Swap 0.5 ETH to USDC", "Swap 100 USDC to ETH"]`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): multi-step confirm cards and shared outcome wording"
```

---

### Task 5: `propose_swap` tool

**Files:**
- Modify: `agent/lazyagent/tools.py`, `agent/lazyagent/prompt.py`, `agent/tests/test_tools.py`
- Test: `agent/tests/test_swap_tools.py`

**Interfaces:**
- Consumes: Tasks 1–4
- Produces: `WalletTools(..., quoter: Quoter | None = None)` (defaults to `ChainQuoter(chain)`); `async propose_swap(args)` with args `token_in`, `token_out`, `amount`, optional `slippage_percent`; `TOOL_NAMES` = get_balances, resolve_recipient, propose_transfer, propose_swap, unsupported_action, request_test_funds.

- [ ] **Step 1: Write failing tests**

In `agent/tests/test_tools.py` update `test_mcp_server_and_names` expected list to:
```python
    assert TOOL_NAMES == [
        "mcp__wallet__get_balances",
        "mcp__wallet__resolve_recipient",
        "mcp__wallet__propose_transfer",
        "mcp__wallet__propose_swap",
        "mcp__wallet__unsupported_action",
        "mcp__wallet__request_test_funds",
    ]
```

`agent/tests/test_swap_tools.py`:
```python
import asyncio

from eth_abi import encode
from fakes import FakeChain, FakeQuoter, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, WETH_DEPOSIT, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_PER_ETH = 2358
USDC_ADDR = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def linear(route, amount_in):
    """Only the 0.05% ETH/USDC pool exists; 1 ETH = 2358 USDC both ways."""
    if route.hops != (Hop(500, 10),) or USDC_ADDR not in route.currencies or len(route.currencies) != 2:
        return None
    if int(route.currencies[0], 16) == 0:
        return amount_in * USDC_PER_ETH // 10**12
    return amount_in * 10**12 // USDC_PER_ETH


def make(chain=None, fn=linear):
    out = Outbox()
    proposals = Proposals()
    chain = chain or FakeChain(tokens={"USDC": 5_000 * 10**6, "USDT": 5_000 * 10**6})
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(fn))
    return tools, out, proposals, chain


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def labels(confirm):
    return [s["label"] for s in confirm["tx"]["steps"]]


async def test_eth_to_usdc_single_step_and_reports_received():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "USDC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["title"] == "Swap 1 ETH → USDC"
    assert labels(confirm) == ["Swap ETH → USDC"]
    step = confirm["tx"]["steps"][0]["request"]
    assert step["to"] == UNIVERSAL_ROUTER and step["value"] == str(10**18) and step["data"].startswith("0x3593564c")
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Route"] == "ETH → USDC · Uniswap v4 0.05%"
    assert rows["Minimum received"] == "2334.42 USDC"  # 1% slippage
    chain.tokens["USDC"] += 2_358 * 10**6
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs", "hashes": ["0xs"]})
    assert "Swapped 1 ETH for 2358 USDC" in text(await task)


async def test_usdc_to_eth_adds_approvals_and_reports_eth_as_about():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "1000"}))
    confirm = await confirm_of(out)
    assert labels(confirm) == ["Allow USDC", "Allow Uniswap router", "Swap USDC → ETH"]
    assert confirm["tx"]["steps"][1]["request"]["to"] == PERMIT2
    assert confirm["tx"]["steps"][2]["request"]["value"] == "0"
    chain.eth += 424 * 10**15
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    assert "about 0.424 ETH" in text(await task)


async def test_existing_allowances_are_skipped():
    chain = FakeChain(tokens={"USDC": 5_000 * 10**6})
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [10**30])
    chain.call_responses["0x927da105"] = encode(["uint160", "uint48", "uint48"], [10**30, chain.now + 3600, 0])
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10"}))
    assert labels(await confirm_of(out)) == ["Swap USDC → ETH"]
    task.cancel()


async def test_usdt_with_small_allowance_resets_first():
    chain = FakeChain(tokens={"USDT": 5_000 * 10**6})
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [5])

    def usdt(route, amount_in):
        return 10**15 if route.hops == (Hop(3000, 60),) else None

    tools, out, _, _ = make(chain=chain, fn=usdt)
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDT", "token_out": "ETH", "amount": "10"}))
    assert labels(await confirm_of(out)) == ["Reset USDT allowance", "Allow USDT", "Allow Uniswap router", "Swap USDT → ETH"]
    task.cancel()


async def test_wrap_and_unwrap():
    chain = FakeChain(tokens={"WETH": 3 * 10**18})
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "WETH", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"] == [{"label": "Wrap ETH → WETH", "request": {"to": WETH, "value": str(10**18), "data": WETH_DEPOSIT}}]
    task.cancel()

    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "WETH", "token_out": "ETH", "amount": "2"}))
    step = (await confirm_of(out))["tx"]["steps"][0]
    assert step["label"] == "Unwrap WETH → ETH"
    assert step["request"]["to"] == WETH and step["request"]["data"].startswith("0x2e1a7d4d")
    task.cancel()


async def test_revert_names_step_and_suggests_slippage():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "100", "slippage_percent": "0.5"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "reverted", "hash": "0xr", "failed_step": 2})
    result = text(await task)
    assert "step 3 (Swap USDC → ETH)" in result
    assert "0.5% slippage" in result


async def test_swap_refusals_send_no_card():
    def huge_impact(route, amount_in):
        q = linear(route, amount_in)
        return q // 2 if q and amount_in >= 10**18 else q

    cases = [
        ({"token_in": "ETH", "token_out": "ETH", "amount": "1"}, linear, "two different tokens"),
        ({"token_in": "DOGE", "token_out": "ETH", "amount": "1"}, linear, "only swap"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "0"}, linear, "more than 0"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "1", "slippage_percent": "9"}, linear, "between 0.01% and 5%"),
        ({"token_in": "USDC", "token_out": "ETH", "amount": "999999"}, linear, "only have"),
        ({"token_in": "DAI", "token_out": "WBTC", "amount": "0"}, linear, "more than 0"),
        ({"token_in": "ETH", "token_out": "WBTC", "amount": "1"}, linear, "couldn't find a Uniswap v4 route"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "1"}, huge_impact, "move the price"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "9.9999"}, linear, "network fees"),
    ]
    for args, fn, fragment in cases:
        tools, out, _, _ = make(fn=fn)
        result = await tools.propose_swap(args)
        assert result.get("is_error") is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent && uv run pytest -q`
Expected: FAIL — `WalletTools` has no `quoter` parameter / no `propose_swap`; `TOOL_NAMES` mismatch.

- [ ] **Step 3: Implement**

In `agent/lazyagent/tools.py`:

- Imports: add
```python
from .swaps import (
    DEADLINE_S,
    GAS,
    MAX_PRICE_IMPACT,
    Step,
    approval_steps,
    check_swap_funds,
    display_units,
    gas_reserve,
    min_out,
    parse_slippage,
    price_impact,
    route_label,
    swap_rows,
)
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ChainQuoter,
    Quoter,
    best_route,
    currency_of,
    decode_permit2_allowance,
    encode_erc20_allowance,
    encode_permit2_allowance,
    encode_swap,
    encode_weth_withdraw,
)
```
- `TOOL_NAMES` tuple becomes `("get_balances", "resolve_recipient", "propose_transfer", "propose_swap", "unsupported_action", "request_test_funds")`.
- `WalletTools.__init__`: add parameter `quoter: Quoter | None = None` after `fund`, and `self.quoter = quoter or ChainQuoter(chain)`.
- Add helpers on `WalletTools` and the tool (place after `propose_transfer`):
```python
    async def _balance(self, token) -> int:
        return await (self.chain.eth_balance(self.ctx.address) if token.address is None else self.chain.token_balance(token, self.ctx.address))

    async def _approvals(self, token, amount: int, now: int) -> list[Step]:
        erc20 = int.from_bytes(await self.chain.call(token.address, encode_erc20_allowance(self.ctx.address, PERMIT2))[:32], "big")
        p2_amount, p2_exp = decode_permit2_allowance(
            await self.chain.call(PERMIT2, encode_permit2_allowance(self.ctx.address, token.address, UNIVERSAL_ROUTER))
        )
        return approval_steps(token, erc20, p2_amount, p2_exp, amount, now)

    async def propose_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        tin = find_token(str(args.get("token_in", "")))
        tout = find_token(str(args.get("token_out", "")))
        if tin is None or tout is None:
            return err(f"I can only swap {SUPPORTED} in Sandbox.")
        if tin == tout:
            return err("Pick two different tokens to swap.")
        try:
            amount = parse_amount(str(args.get("amount", "")), tin.decimals)
            bps = parse_slippage(args.get("slippage_percent"))
            eth_balance = await self.chain.eth_balance(self.ctx.address)
            balance = await self._balance(tin)
            if amount > balance:
                raise TransferError(f"You only have {format_units(balance, tin.decimals)} {tin.symbol}.")
            now = await self.chain.block_timestamp()
            pair = (tin.symbol, tout.symbol)
            if pair in (("ETH", "WETH"), ("WETH", "ETH")):
                weth = tout if tin.address is None else tin
                request = (
                    {"to": weth.address, "value": str(amount), "data": WETH_DEPOSIT}
                    if tin.address is None
                    else {"to": weth.address, "value": "0", "data": encode_weth_withdraw(amount)}
                )
                verb = "Wrap" if tin.address is None else "Unwrap"
                steps = [Step(f"{verb} {tin.symbol} → {tout.symbol}", request, GAS["wrap"])]
                expected = minimum = amount
                label, impact = f"{verb} via WETH contract", 0.0
            else:
                found = await best_route(self.quoter, currency_of(tin), currency_of(tout), amount)
                if found is None:
                    raise TransferError(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol} on Sandbox.")
                route, expected = found
                probe_in = max(amount // 1000, 1)
                impact = price_impact(amount, expected, probe_in, await self.quoter.quote(route, probe_in) or 0)
                if impact > MAX_PRICE_IMPACT:
                    raise TransferError(f"That trade would move the price by about {impact:.0%}. Try a smaller amount.")
                minimum = min_out(expected, bps)
                steps = await self._approvals(tin, amount, now) if tin.address else []
                swap = {
                    "to": UNIVERSAL_ROUTER,
                    "value": str(amount if tin.address is None else 0),
                    "data": encode_swap(route, amount, minimum, now + DEADLINE_S),
                }
                steps.append(Step(f"Swap {tin.symbol} → {tout.symbol}", swap, GAS["swap1" if len(route.hops) == 1 else "swap2"]))
                label = route_label(route)
            gas_price = await self.chain.gas_price()
            reserve = gas_reserve(steps, gas_price)
            check_swap_funds(tin, amount, balance, eth_balance, reserve)
            fee_usd = float(Decimal(reserve // FEE_HEADROOM).scaleb(-18)) * await self.chain.price_usd(ETH)
            out_before = await self._balance(tout)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The Sandbox chain isn't reachable right now ({e}).")

        human_in = f"{format_units(amount, tin.decimals)} {tin.symbol}"
        steps_json = [s.to_json() for s in steps]
        pid, fut = self.proposals.new()
        await self.send(
            {
                "type": "confirm",
                "id": pid,
                "tx": {
                    "title": f"Swap {human_in} → {tout.symbol}",
                    "from": self.ctx.address,
                    "rows": swap_rows(self.ctx.address, tin, tout, amount, expected, minimum, label, impact, fee_usd),
                    "steps": steps_json,
                },
            }
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if result and result.get("status") == "success" and not result.get("error"):
            received = max(await self._balance(tout) - out_before, 0)
            got = f"{display_units(received, tout.decimals)} {tout.symbol}"
            got = f"about {got} (after network fees)" if tout.address is None else got
            success = f"Swapped {human_in} for {got}. Confirmed on Sandbox, tx {result.get('hash')}."
        hint = f" The price probably moved more than the {bps / 100:g}% slippage — ask again for a fresh quote."
        return ok(outcome_text(result, steps_json, "swap", success, revert_hint=hint))
```
- Add `FEE_HEADROOM` to the `.transfers` import list.
- `unsupported_action` text: `f"{action} is coming soon. Right now LazyWallet can check balances, send and swap {SUPPORTED} on Sandbox."`
- In `build_mcp_server`, add before `request_test_funds`:
```python
            tool(
                "propose_swap",
                "Propose swapping one supported token for another on Uniswap v4 (exact input). Finds the best route, shows one confirmation card with any approval steps, waits for approve/reject, and returns the amount received.",
                {
                    "type": "object",
                    "properties": {
                        "token_in": {"type": "string", "description": f"Token to pay, one of {SUPPORTED}"},
                        "token_out": {"type": "string", "description": f"Token to receive, one of {SUPPORTED}"},
                        "amount": {"type": "string", "description": "Decimal amount of token_in, e.g. '100'"},
                        "slippage_percent": {"type": "string", "description": "Only if the user stated one, e.g. '0.5'"},
                    },
                    "required": ["token_in", "token_out", "amount"],
                },
            )(t.propose_swap),
```
and change the `unsupported_action` description to `"Use for bridging, scheduling, price alerts, dApps or anything other than balances, sends, swaps and test funds."`.

In `agent/lazyagent/prompt.py`, replace the line starting `- Swaps, bridging, schedules` with:
```
- Swaps ("swap 100 USDC to ETH", "trade", "convert", "buy ETH with 50 USDC" = swap 50 USDC to ETH) → propose_swap with token_in, token_out and the amount of token_in. Pass slippage_percent only if the user said one. The card lists any approval steps; report what was received in one sentence.
- Bridging, schedules, price alerts, dApps or anything else → unsupported_action.
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd agent && uv run pytest -q`
Expected: PASS. If the `rows["Minimum received"]` assertion differs, recompute: `2_358_000_000 * 9900 // 10000 = 2_334_420_000` → `2334.42`.

- [ ] **Step 5: Commit**

```bash
git add agent
git commit -m "feat(agent): add propose_swap tool with v4 routing and approval steps"
```

---

### Task 6: Fork integration swaps

**Files:**
- Test: `agent/tests/test_swap_fork.py`

**Interfaces:**
- Consumes: `devsigner.execute_steps`, `WalletTools`, `RpcChain`, `Proposals`, fixture `fork_rpc`

- [ ] **Step 1: Write the tests**

`agent/tests/test_swap_fork.py`:
```python
import asyncio

from eth_abi import encode
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.proposals import Proposals
from lazyagent.tokens import find_token
from lazyagent.tools import WalletContext, WalletTools

USDC = find_token("USDC")
WBTC = find_token("WBTC")
WETH = find_token("WETH")
USDC_BALANCE_SLOT = 9


async def funded_account(rpc: str, usdc: int = 0):
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc))
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_BALANCE_SLOT])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [USDC.address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    return w3, account


async def swap(rpc: str, w3, account, args: dict) -> tuple[str, list[dict]]:
    proposals = Proposals()
    seen: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    tools = WalletTools(RpcChain(rpc), send, WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_swap(args)
    return result["content"][0]["text"], seen


async def test_eth_to_usdc(fork_rpc):
    w3, account = await funded_account(fork_rpc)
    text, seen = await swap(fork_rpc, w3, account, {"token_in": "ETH", "token_out": "USDC", "amount": "1"})
    assert "Swapped 1 ETH for" in text, text
    assert len(seen[0]["tx"]["steps"]) == 1
    assert await RpcChain(fork_rpc).token_balance(USDC, account.address) > 500 * 10**6


async def test_usdc_to_eth_with_approvals(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=5_000 * 10**6)
    text, seen = await swap(fork_rpc, w3, account, {"token_in": "USDC", "token_out": "ETH", "amount": "1000"})
    assert "Swapped 1000 USDC for about" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Allow Uniswap router", "Swap USDC → ETH"]
    assert await RpcChain(fork_rpc).token_balance(USDC, account.address) == 4_000 * 10**6


async def test_usdc_to_wbtc(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=5_000 * 10**6)
    text, _ = await swap(fork_rpc, w3, account, {"token_in": "USDC", "token_out": "WBTC", "amount": "500"})
    assert "Swapped 500 USDC for" in text, text
    assert await RpcChain(fork_rpc).token_balance(WBTC, account.address) > 0


async def test_wrap_eth(fork_rpc):
    w3, account = await funded_account(fork_rpc)
    text, _ = await swap(fork_rpc, w3, account, {"token_in": "ETH", "token_out": "WETH", "amount": "1"})
    assert "Swapped 1 ETH for 1 WETH" in text, text
    assert await RpcChain(fork_rpc).token_balance(WETH, account.address) == 10**18
```

- [ ] **Step 2: Run**

Run: `cd agent && uv run pytest tests/test_swap_fork.py -q`
Expected: PASS (4 tests; they need `ETH_RPC_URL`, which this repo has). These exercise Tasks 1–5 against real v4 pools; any failure here is a real encoding/routing bug — debug it, don't loosen the test.

- [ ] **Step 3: Commit**

```bash
git add agent
git commit -m "test(agent): fork integration tests for v4 swaps and wrap"
```

---

### Task 7: Wallet — steps execution and UI

**Files:**
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/agent/protocol.ts`, `apps/wallet/src/chain/executeTx.ts`, `apps/wallet/src/agent/chatReducer.ts`, `apps/wallet/src/agent/useAgentChat.ts`, `apps/wallet/src/chat/cards/ConfirmCard.tsx`
- Modify tests: `apps/wallet/src/chain/executeTx.test.ts`, `apps/wallet/src/agent/chatReducer.test.ts`, `apps/wallet/src/agent/useAgentChat.test.tsx`

**Interfaces:**
- Produces: `TxStep = { label: string; request: TxRequest }`; `TxDraft.steps?: TxStep[]` (replaces `request`); `StepsOutcome = { hashes: string[]; hash?: string; status?: 'success' | 'reverted'; error?: string; failedStep?: number }`; `executeSteps(steps, deps, onStep?) -> Promise<StepsOutcome>`; `statusPatch(o: StepsOutcome, steps: TxStep[])`; `progressText(i, steps) -> string`.

- [ ] **Step 1: Write failing tests**

Replace `apps/wallet/src/chain/executeTx.test.ts` with:
```ts
import { describe, expect, it, vi } from 'vitest'
import type { TxRequest, TxStep } from '@/types'
import { executeSteps, executeTx, progressText, statusPatch, type TxDeps } from './executeTx'

const req: TxRequest = { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '100', data: '0x' }
const HASH = '0xabc' as const
const ONE: TxStep[] = [{ label: 'Send', request: req }]
const THREE: TxStep[] = [
  { label: 'Allow USDC', request: req },
  { label: 'Allow Uniswap router', request: req },
  { label: 'Swap USDC → ETH', request: req },
]

describe('executeTx', () => {
  it('returns hash and receipt status', async () => {
    const deps: TxDeps = { send: async () => HASH, wait: async () => 'success' }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, status: 'success' })
  })

  it('reports send errors using the short message when present', async () => {
    const deps: TxDeps = {
      send: async () => {
        throw Object.assign(new Error('long details'), { shortMessage: 'insufficient funds' })
      },
      wait: async () => 'success',
    }
    expect(await executeTx(req, deps)).toEqual({ error: 'insufficient funds' })
  })

  it('reports receipt errors with the hash', async () => {
    const deps: TxDeps = {
      send: async () => HASH,
      wait: async () => {
        throw new Error('timeout')
      },
    }
    expect(await executeTx(req, deps)).toEqual({ hash: HASH, error: 'timeout' })
  })
})

describe('executeSteps', () => {
  it('runs every step in order and reports progress', async () => {
    let n = 0
    const deps: TxDeps = { send: async () => `0x${++n}` as `0x${string}`, wait: async () => 'success' }
    const onStep = vi.fn()
    expect(await executeSteps(THREE, deps, onStep)).toEqual({ hashes: ['0x1', '0x2', '0x3'], hash: '0x3', status: 'success' })
    expect(onStep.mock.calls.map((c) => c[0])).toEqual([0, 1, 2])
  })

  it('stops at the first reverted step', async () => {
    let n = 0
    const deps: TxDeps = { send: async () => `0x${++n}` as `0x${string}`, wait: async (h) => (h === '0x2' ? 'reverted' : 'success') }
    expect(await executeSteps(THREE, deps)).toEqual({ hashes: ['0x1', '0x2'], hash: '0x2', status: 'reverted', failedStep: 1 })
  })

  it('stops when a step cannot be sent', async () => {
    let n = 0
    const deps: TxDeps = {
      send: async () => {
        if (++n === 3) throw new Error('rejected by node')
        return `0x${n}` as `0x${string}`
      },
      wait: async () => 'success',
    }
    expect(await executeSteps(THREE, deps)).toEqual({ hashes: ['0x1', '0x2'], hash: undefined, error: 'rejected by node', failedStep: 2 })
  })
})

describe('statusPatch and progressText', () => {
  it('keeps single-step wording', () => {
    expect(statusPatch({ hashes: [HASH], hash: HASH, status: 'success' }, ONE)).toEqual({ state: 'success', text: 'Confirmed on Sandbox.', hash: HASH })
    expect(statusPatch({ hashes: [HASH], hash: HASH, status: 'reverted', failedStep: 0 }, ONE)).toEqual({
      state: 'failed',
      text: 'Transaction reverted.',
      hash: HASH,
    })
    expect(statusPatch({ hashes: [], error: 'nope', failedStep: 0 }, ONE)).toEqual({ state: 'failed', text: 'Failed: nope', hash: undefined })
  })

  it('names the failing step for multi-step cards', () => {
    expect(statusPatch({ hashes: ['0x1', '0x2'], hash: '0x2', status: 'reverted', failedStep: 2 }, THREE).text).toBe(
      'Swap USDC → ETH: Transaction reverted.',
    )
  })

  it('shows progress only for multi-step cards', () => {
    expect(progressText(1, THREE)).toBe('Step 2 of 3: Allow Uniswap router…')
    expect(progressText(0, ONE)).toBe('Submitting to Sandbox…')
  })
})
```

In `apps/wallet/src/agent/chatReducer.test.ts`, change the `confirmMsg` tx to use steps:
```ts
  tx: {
    title: 'Send 0.1 ETH',
    from: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
    rows: [],
    steps: [{ label: 'Send', request: { to: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', value: '1', data: '0x' } }],
  },
```

In `apps/wallet/src/agent/useAgentChat.test.tsx`, in the "different wallet" test, change the confirm tx to:
```ts
          tx: { title: 'Send 1 ETH', from: otherWallet, rows: [], steps: [{ label: 'Send', request: { to: otherWallet, value: '1', data: '0x' } }] },
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --filter wallet test`
Expected: FAIL — `executeSteps`/`progressText` missing; type errors on `steps` surface at build.

- [ ] **Step 3: Implement**

`apps/wallet/src/types.ts`: add after `TxRequest`:
```ts
export type TxStep = { label: string; request: TxRequest }
```
and in `TxDraft` replace `request?: TxRequest` with `steps?: TxStep[]`.

`apps/wallet/src/agent/protocol.ts`:
- Import `TxStep` instead of `TxRequest`: `import type { Address, Holding, TxDraft, TxStep } from '@/types'`.
- Confirm variant: `{ type: 'confirm'; id: string; tx: TxDraft & { steps: TxStep[]; from: Address } }`.
- `tx_result` variant: add `hashes?: string[]` and `failed_step?: number`.

Append to `apps/wallet/src/chain/executeTx.ts` and replace its `statusPatch`:
```ts
export type StepsOutcome = { hashes: string[]; hash?: string; status?: 'success' | 'reverted'; error?: string; failedStep?: number }

export async function executeSteps(steps: TxStep[], deps: TxDeps, onStep?: (index: number) => void): Promise<StepsOutcome> {
  const hashes: string[] = []
  for (let i = 0; i < steps.length; i++) {
    onStep?.(i)
    const r = await executeTx(steps[i].request, deps)
    if (r.hash) hashes.push(r.hash)
    if (r.error || r.status === 'reverted') return { hashes, hash: r.hash, status: r.status, error: r.error, failedStep: i }
  }
  return { hashes, hash: hashes.at(-1), status: 'success' }
}

export function statusPatch(o: StepsOutcome, steps: TxStep[]): { state: 'success' | 'failed'; text: string; hash?: string } {
  const at = o.failedStep !== undefined && steps.length > 1 ? `${steps[o.failedStep].label}: ` : ''
  if (o.error) return { state: 'failed', text: `${at}Failed: ${o.error}`, hash: o.hash }
  if (o.status === 'reverted') return { state: 'failed', text: `${at}Transaction reverted.`, hash: o.hash }
  return { state: 'success', text: 'Confirmed on Sandbox.', hash: o.hash }
}

export function progressText(index: number, steps: TxStep[]): string {
  return steps.length > 1 ? `Step ${index + 1} of ${steps.length}: ${steps[index].label}…` : 'Submitting to Sandbox…'
}
```
and change its type import to `import type { TxRequest, TxStep } from '@/types'`.

`apps/wallet/src/agent/chatReducer.ts`: in `expireAgentCards` replace `m.tx.request` with `m.tx.steps`.

`apps/wallet/src/agent/useAgentChat.ts`:
- Import: `import { executeSteps, progressText, statusPatch } from '@/chain/executeTx'` (drop `executeTx`).
- In `approve`, replace the block from `if (!m.tx.request) {` through `sendJson({ type: 'tx_result', id, outcome: 'approved', ...outcome })` with:
```ts
    const steps = m.tx.steps
    if (!steps) {
      // Phase-1 WalletConnect mock card: no real transaction.
      window.setTimeout(
        () => dispatch({ type: 'update', id: statusId, patch: { state: 'success', text: 'Done! Transaction confirmed.', hash: txHash() } }),
        MOCK_CONFIRM_MS,
      )
      return
    }
    const outcome = mnemonic
      ? await executeSteps(steps, txDepsFor(mnemonic), (i) => dispatch({ type: 'update', id: statusId, patch: { text: progressText(i, steps) } }))
      : { hashes: [], error: 'No wallet is unlocked.', failedStep: 0 }
    dispatch({ type: 'update', id: statusId, patch: statusPatch(outcome, steps) })
    sendJson({
      type: 'tx_result',
      id,
      outcome: 'approved',
      hash: outcome.hash,
      hashes: outcome.hashes,
      status: outcome.status,
      error: outcome.error,
      failed_step: outcome.failedStep,
    })
```
- In `reject`, replace `if (m.tx.request)` with `if (m.tx.steps)`.

`apps/wallet/src/chat/cards/ConfirmCard.tsx`: after the closing `</dl>` of the rows, insert:
```tsx
      {tx.steps && tx.steps.length > 1 && (
        <div className="mt-3 rounded-xl bg-secondary p-3">
          <p className="text-xs font-medium text-muted-foreground">Steps (one tap runs them in order)</p>
          <ol className="mt-1 space-y-0.5 text-sm">
            {tx.steps.map((s, i) => (
              <li key={i}>
                {i + 1}. {s.label}
              </li>
            ))}
          </ol>
        </div>
      )}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet
git commit -m "feat(wallet): run multi-step confirm cards with progress"
```

---

### Task 8: Docs and live verification

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `agent/README.md`

- [ ] **Step 1: Docs**

`README.md`:
- Status line → `> **Status: Phase 3 — Uniswap v4 swaps.** The chat runs on a real Claude agent. Balances, ETH/ERC-20 sends and Uniswap v4 swaps are real on "Sandbox" (an Anvil fork of Ethereum mainnet). Bridges, scheduled tasks and WalletConnect are still mocked or "coming soon".`
- "Try it" list: add `- "Swap 0.5 ETH to USDC"` and `- "Swap 100 USDC to ETH with 0.5% slippage"` after the send examples.
- Roadmap: mark 2 ✅, add `3. **Uniswap v4 swaps** (current) — best hookless route, approvals in one card.` and renumber "Next".

`CLAUDE.md`:
- Current phase → `Phase 3: Uniswap v4 swaps. Spec: docs/superpowers/specs/2026-10-15-lazywallet-uniswap-v4-swap-design.md.`
- Under wallet conventions add: `Agent confirm cards carry tx.steps ([{label, request}]); the browser runs them in order (chain/executeTx.ts executeSteps).` and `Uniswap v4 recipe and addresses live in agent/lazyagent/uniswap.py (verified on a fork) — change them only with a fork test.`
- Mock list: remove "swaps".

`agent/README.md`: tool list → `get_balances`, `resolve_recipient`, `propose_transfer`, `propose_swap` (Uniswap v4, exact input), `request_test_funds`, `unsupported_action`.

- [ ] **Step 2: Full verification**

Run:
```bash
pnpm test && pnpm build && pnpm lint && pnpm test:py
```
Expected: all pass, fork tests included.

Live (stop any old servers on 8545/8547/8787/5174 first):
```bash
pnpm dev:sandbox &           # wait for "Sandbox ready"
uv run --directory anvil python scripts/seed.py
uv run --directory agent python scripts/demo.py
```
Expected: balance card, ETH send confirmed, "Swapped 0.5 ETH for … USDC", "Swapped 100 USDC for about … ETH" (3 steps executed).

Browser: `pnpm dev:agent` + `pnpm --filter wallet dev`; create wallet → "Give me test funds" → "Swap 1 ETH to USDC" → Approve → confirmed → "Swap 500 USDC to ETH" → card shows 3 steps → Approve → status shows "Step 1 of 3…" progress → confirmed → agent reports received ETH. Stop all servers.

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md agent/README.md
git commit -m "docs: phase 3 Uniswap v4 swaps"
```
