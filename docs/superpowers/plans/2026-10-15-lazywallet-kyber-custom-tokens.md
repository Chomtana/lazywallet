# LazyWallet — KyberSwap + Custom Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user buy, hold, send and sell any token (memecoins included) on both Sandbox networks. Pairs the built-in venues can't quote go through the KyberSwap aggregator, and the wallet remembers bought tokens so they then behave like built-in ones.

**Architecture:** The agent gets two new modules. `custom_tokens.py` merges the wallet's saved tokens into each network, reads a pasted contract address on the fork, and searches GeckoTerminal by symbol. `kyber.py` holds the KyberSwap client and treats Kyber's calldata as untrusted: it ABI-decodes it and checks it against the request, then simulates it on the fork with an `eth_call` (ERC-20 inputs get an allowance state override) before any card is shown. `tools.py` picks the venue (Uniswap v4, Dexalot, or KyberSwap) and puts `addToken` on the card. The wallet saves `addToken` to `lw.tokens` after a successful swap and sends the saved list with every `user` message.

**Tech Stack:** Python 3.12+ (uv, FastAPI, web3.py 8, eth-abi, pytest-asyncio), Anvil, stdlib `urllib` for HTTP. React + TypeScript + Vitest, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-kyber-custom-tokens-design.md`

## Global Constraints

- Kyber API: `https://aggregator-api.kyberswap.com/{chain}/api/v1`, chain slug `ethereum` / `avalanche`; `GET /routes?tokenIn&tokenOut&amountIn`, `POST /route/build` with `{routeSummary, sender, recipient, slippageTolerance, skipSimulateTx: true}`. Headers: `x-client-id: lazywallet`, plus `user-agent: lazywallet/0.1`. Kyber's CDN returns 403 to Python's default user-agent (verified 2026-10-15).
- Router pinned to `0x6131B5fae19EA4f9D964eAc0408E4408b66337b5` (MetaAggregationRouterV2, same on both chains). Any other `routerAddress` → refuse.
- Native token in Kyber requests = `0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`.
- Kyber calldata is untrusted. The model never sees or builds it; `kyber.verify()` + fork simulation run before a card is shown. Simulated output must be within **5%** of Kyber's quoted `amountOut`.
- Kyber slippage on Sandbox: default `SANDBOX_KYBER_SLIPPAGE_BPS = 5000` (see Deviations). A user-stated slippage still goes through `parse_slippage` (0.01–5%). Uniswap/Dexalot slippage is unchanged.
- Venue: Uniswap v4 (Ethereum) or Dexalot (Avalanche) when both tokens are built-in and the venue quotes the pair. Otherwise KyberSwap.
- Token resolution order: built-in registry → saved `lw.tokens` → pasted `0x` + 40 hex (read `symbol()`/`decimals()` on that fork) → GeckoTerminal symbol search (exact base-token symbol, deepest pool, reserve ≥ **$10,000**, marked `matched_by_symbol`).
- GeckoTerminal network slugs: `eth`, `avax`. The search URL carries `include=base_token` (needed to read the base token's symbol).
- Custom token price: KyberSwap route **1 USDC → token**, inverted; failure → `None` ("price unknown", left out of totals, never $0).
- Every confirm card that touches a custom token has a `<SYMBOL> address` row with the full contract address, suffixed ` (matched by symbol — verify)` when step 4 found it.
- Wallet store: `lw.tokens` = `{ [walletAddressLowercase]: CustomToken[] }`, add-only, deduplicated by `(chainId, address lowercase)`, non-secret. `CustomToken = { chainId, address, symbol, decimals }`.
- HTTP uses stdlib `urllib` in `asyncio.to_thread`, so there are no new dependencies.
- Tests must never use Anvil's dev account `0xf39F…2266` against the real Kyber API ("wallets invalid"); the fork tests use `Account.create()`.
- Live fork tests cover both chains with exactly one token each: COQ `0x420FcA0121DC28039145009570975747295f2329` on Avalanche (buy, balance, sell) and PEPE `0x6982508145454Ce325dDbE47a25d4ec3d2311933` on Ethereum (buy, balance: 2 live Kyber routes). Don't add other tokens to live tests.
- Don't touch ports 8545–8547 (the user's dev servers). Fork tests use the existing conftest ports.
- Parallel branch (`avax-trending`) also edits `agent/lazyagent/tools.py` and `prompt.py` to register one tool. Keep edits to those files to the hunks shown here; don't reformat or reorder anything else.

## Review Focus

- **Stale Sandbox fork vs live Kyber quote.** The user's fork may be hours old. For a memecoin, the fork's pools can differ from what Kyber priced, so the simulation can revert or come back more than 5% off. Expected: a plain error and no card (never a card that fails on Approve). Covered by Task 5 `test_kyber_failures_send_no_card` (reverting and 10%-off simulation cases).
- **A token on both networks at the same address (CREATE2 deploys) or found by symbol on both.** Expected: the existing network-choice card, never a silent pick. Covered by Task 5 `test_token_found_on_both_networks_asks_which`.
- **Hostile or odd token metadata:** a saved token whose symbol clashes with a built-in ("USDC"), a 40-character symbol, a `bytes32` symbol, an address with no code. Expected: built-ins win, junk is skipped, EOAs are "not a token", and the card always shows the address. Covered by Task 4 `test_merge_builtins_win_and_bad_entries_are_skipped` and `test_read_token_*`.
- **A swap that fails after the approve step, or a corrupt `lw.tokens`.** Expected: the token is not saved unless every step succeeded, and a corrupt store reads as empty without breaking the chat. Covered by Task 9 `tokenToSave` tests and Task 8 corrupt-JSON test.
- **KyberSwap or GeckoTerminal down or rate-limited.** Expected: swaps give a plain "isn't reachable"/"no route" error with no card. Balances still render, with custom tokens shown as "price unknown". Covered by Task 3 `test_client_errors` and `test_usd_price_routes_one_usdc_and_inverts` (no-route → `None`), and Task 4 `test_discover_survives_a_failing_search`.

## Verified facts this plan relies on (2026-10-15)

- Real `/route/build` responses for 5 routes all used selector `0xe21fd0e9` = `swap((address,address,bytes,(address,address,address[],uint256[],address[],uint256[],address,uint256,uint256,uint256,bytes),bytes))`. The routes were AVAX→COQ, COQ→USDC and USDC→COQ on Avalanche, and ETH→PEPE and USDC→PEPE on Ethereum. The other swap entry point is `0x8af033fb` = `swapSimpleMode(address,(address,address,address[],uint256[],address[],uint256[],address,uint256,uint256,uint256,bytes),bytes,bytes)`, which is nonpayable (ERC-20 input only). Both signatures come from the verified ABI on Routescan, and the ABI is identical on chain 1 and chain 43114.
- `SwapDescriptionV2` field order: `srcToken, dstToken, srcReceivers[], srcAmounts[], feeReceivers[], feeAmounts[], dstReceiver, amount, minReturnAmount, flags, permit`. `SwapExecutionParams`: `callTarget, approveTarget, targetData, desc, clientData`. Both functions return `(returnAmount, gasUsed)`.
- Router source: `srcReceivers` can pull up to `desc.amount` from `msg.sender`. The router enforces `returnAmount ≥ minReturnAmount`, measured at `dstReceiver`. So the checks that protect the user are `dstReceiver == user`, the `minReturnAmount` floor, empty `feeReceivers`, and the exact approve amount.
- Kyber returns `minReturnAmount == floor(amountOut × (10000 − bps) / 10000)`, which equals our `min_out(amountOut, bps)`.
- **`slippageTolerance` > 5000 → HTTP 400** `fieldViolations: slippageTolerance invalid` (5000 OK, 5001 rejected).
- ERC-20 allowance override: `eth_createAccessList` of `allowance(user, router)` on the token, then try each storage key of the token address as a `stateDiff` override and keep the one where `allowance()` returns the amount. Verified on a fresh Avalanche fork for USDC (a proxy: 3 keys, the third worked) and COQ (1 key). Without the override the swap `eth_call` reverts `TransferHelper: TRANSFER_FROM_FAILED`; with it, the returned amount equals the quote. web3.py 8: `await w3.eth.call(tx, "latest", {addr: {"stateDiff": {slot: value}}})` and `await w3.eth.create_access_list(tx)`.
- Kyber `GET /routes` for 1 COQ → USDC returns `amountOut: "1"` (useless). 1 USDC → COQ returns `8.2e24` raw, which is precise. Hence the inverted price.
- GeckoTerminal: pool `relationships.base_token.data.id` = `"<slug>_<address lowercase>"`; `included[]` tokens carry `attributes.{address, symbol, decimals}`. Pool names aren't reliable ("pepecoin / WETH" has base symbol `pepecoin`).
- The whole plan was prototyped in a scratch copy: all pytest (202 unit + both Kyber fork tests against the real API: COQ on an Avalanche fork, PEPE on an Ethereum mainnet fork) and Vitest (112), `tsc` and `oxlint` passed.

## Deviations from the spec (record them in the spec in Task 11)

1. **Sandbox Kyber slippage is 50% (`5000` bps), not 90%.** Kyber's API rejects anything above 5000. The 5% simulation check still catches amount/decimals bugs.
2. **Custom-token price = route 1 USDC → token, inverted**, not 1 token → USDC. The latter rounds to 0–1 raw USDC unit for memecoins.
3. **Card row label is `<SYMBOL> address`** (e.g. `COQ address`), not `Token address`. `ConfirmCard` keys rows by label, so two custom tokens on one card would collide.
4. **Price impact for Kyber swaps** comes from Kyber's own `amountInUsd`/`amountOutUsd` and shows "unknown" when Kyber has no USD values. It is not enforced: the 15% Uniswap refusal is not applied to Kyber, since the spec doesn't ask for it.
5. **Venue fallback is driven by a `NoRoute` error** (subclass of `TransferError`). Uniswap's "no route" and the sandbox's Dexalot 404 raise it, and `propose_swap` then tries Kyber. Other venue errors (price impact, sandbox down) still surface as before.
6. **`Chain` protocol gains `simulate(tx, overrides)` and `storage_keys(to, data)`**, and `price_usd` may return `None`.
7. **`ConfirmCard` values wrap** (`wrap-anywhere`) so a 42-character address fits at phone width.

---

## File structure

| File | Responsibility |
|---|---|
| `agent/lazyagent/tokens.py` | `Token.custom`, `Token.matched_by_symbol`; `find_token` also matches by contract address |
| `agent/lazyagent/transfers.py` | `NoRoute`; `display_rows` accepts an unknown price; `token_address_rows` |
| `agent/lazyagent/swaps.py` | `erc20_approval(token, allowance, amount, spender)` (shared USDT reset rule); `swap_rows` accepts unknown impact |
| `agent/lazyagent/dexalot.py` | Sandbox 404 (pair not offered) → `NoRoute` |
| `agent/lazyagent/chain.py` | `PriceSource`; custom-token prices; `simulate` (eth_call + state overrides); `storage_keys` (access list) |
| `agent/lazyagent/kyber.py` (new) | Kyber HTTP client, `verify`, allowance override, fork simulation, steps/rows, `kyber_plan`, `usd_price` |
| `agent/lazyagent/custom_tokens.py` (new) | `merge` saved tokens, `read_token` on the fork, GeckoTerminal `pick_pool`/`GeckoSearch`, `discover` |
| `agent/lazyagent/tools.py` | `WalletContext.tokens`; merged networks; discovery in `_resolve`; venue choice; `addToken`; address rows; unknown prices |
| `agent/lazyagent/session.py`, `server.py`, `prompt.py` | Wiring + one prompt bullet |
| `agent/tests/fakes.py` | `FakeChain` simulate/storage/prices; `FakeKyber`, `FakeSearch`, calldata helpers |
| `apps/wallet/src/types.ts`, `lib/storage.ts`, `lib/tokens.ts` (new) | `CustomToken`, `TxDraft.addToken`, nullable `usdPrice`; `lw.tokens` store |
| `apps/wallet/src/chain/executeTx.ts`, `agent/protocol.ts`, `agent/useAgentChat.ts` | `tokenToSave`; `tokens` on `user` messages; save after success |
| `apps/wallet/src/chat/cards/{BalanceCard,BalanceChangeCard,ConfirmCard}.tsx`, `mock/{agent,fixtures}.ts` | "price unknown"; wrapping values; mock type fixes |

Commands (run from the worktree root):
- One Python test file: `uv run --directory agent pytest -q tests/<file>.py`
- One Vitest file: `pnpm --filter wallet exec vitest run <path relative to apps/wallet>`

---

### Task 1: Token flags, `NoRoute`, and shared row/approval helpers

**Files:**
- Modify: `agent/lazyagent/tokens.py:7-14,45-47`, `agent/lazyagent/transfers.py:15-16,86-97` (+ append), `agent/lazyagent/swaps.py:70-86,103-124`, `agent/lazyagent/dexalot.py:13,81-82`
- Test: `agent/tests/test_tokens.py`, `agent/tests/test_transfers.py`, `agent/tests/test_swaps.py`, `agent/tests/test_dexalot.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `Token(..., custom: bool = False, matched_by_symbol: bool = False)` (frozen dataclass, hashable)
  - `find_token(symbol_or_address: str, tokens=TOKENS) -> Token | None` (case-insensitive symbol **or** address)
  - `class NoRoute(TransferError)` in `transfers.py`
  - `display_rows(token, amount, to, name, price: float | None, gas_cost, eth_price, network="Sandbox")`
  - `token_address_rows(*tokens: Token) -> list[dict]`: `{"label": f"{symbol} address", "value": address [+ " (matched by symbol — verify)"]}` for custom tokens only, deduplicated
  - `erc20_approval(token: Token, allowance: int, amount: int, spender: str) -> list[Step]` in `swaps.py`
  - `swap_rows(..., impact: float | None, ...)`: `None` renders `"unknown"`
  - `SandboxQuotes.quote` raises `NoRoute` on HTTP 404

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_tokens.py`:

```python
def test_builtins_are_not_custom_and_match_by_address():
    assert not any(t.custom or t.matched_by_symbol for t in TOKENS + AVAX_TOKENS)
    assert find_token("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48").symbol == "USDC"
    assert find_token("0x0000000000000000000000000000000000000000") is None  # native coins have no address
```

In `agent/tests/test_transfers.py`, change the imports to

```python
from lazyagent.tokens import ETH, Token, find_token
from lazyagent.transfers import (
    TransferError,
    build_request,
    display_rows,
    format_units,
    parse_amount,
    resolve_recipient,
    token_address_rows,
    validate,
)
```

and append:

```python
COQ = Token("COQ", "0x420FcA0121DC28039145009570975747295f2329", 18, custom=True)


def test_display_rows_without_a_price():
    rows = display_rows(COQ, 10**21, ALICE, None, None, 100_000 * 10**9, 25.0)
    assert {"label": "Amount", "value": "1000 COQ"} in rows


def test_token_address_rows_only_for_custom_tokens():
    guessed = Token("PEPE", "0x6982508145454Ce325dDbE47a25d4ec3d2311933", 18, custom=True, matched_by_symbol=True)
    assert token_address_rows(ETH, USDC) == []
    assert token_address_rows(COQ, COQ, USDC, guessed) == [
        {"label": "COQ address", "value": "0x420FcA0121DC28039145009570975747295f2329"},
        {"label": "PEPE address", "value": "0x6982508145454Ce325dDbE47a25d4ec3d2311933 (matched by symbol — verify)"},
    ]
```

In `agent/tests/test_swaps.py`, add `erc20_approval,` to the `from lazyagent.swaps import (...)` list (after `display_units,`) and append:

```python
def test_erc20_approval_for_any_spender():
    spender = "0x6131B5fae19EA4f9D964eAc0408E4408b66337b5"
    assert erc20_approval(USDC, 10**6, 10**6, spender) == []
    [step] = erc20_approval(USDC, 0, 10**6, spender)
    assert step.label == "Allow USDC" and step.request["to"] == USDC.address
    assert step.request["data"].startswith("0x095ea7b3") and spender[2:].lower() in step.request["data"]
    assert [s.label for s in erc20_approval(USDT, 5, 10**6, spender)] == ["Reset USDT allowance", "Allow USDT"]


def test_swap_rows_unknown_impact():
    rows = swap_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", ETH, USDC, 10**18, 2_358_835_338, 1_179_417_669, "KyberSwap via LFJ", None, 1.23)
    assert {"label": "Price impact", "value": "unknown"} in rows
```

In `agent/tests/test_dexalot.py`, change `from lazyagent.transfers import TransferError` to `from lazyagent.transfers import NoRoute, TransferError`, and in `test_sandbox_quotes_posts_and_surfaces_errors` change the 404 assertion line to:

```python
        with pytest.raises(NoRoute, match="Available: AVAX/USDC"):  # 404 lets KyberSwap try the pair
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_tokens.py tests/test_transfers.py tests/test_swaps.py tests/test_dexalot.py`
Expected: FAIL / collection ERROR. `ImportError: cannot import name 'token_address_rows'`, `'erc20_approval'`, `'NoRoute'`, and `AttributeError: 'Token' object has no attribute 'custom'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/tokens.py`: add two fields at the end of `Token`, and make `find_token` match addresses:

```python
@dataclass(frozen=True)
class Token:
    symbol: str
    address: str | None  # None = native ETH
    decimals: int
    price_feed: str | None = None
    fixed_price: float | None = None
    custom: bool = False  # not built in: saved by the wallet, or found by contract address / symbol search
    matched_by_symbol: bool = False  # found by symbol search — the card asks the user to verify the address
```

```python
def find_token(symbol: str, tokens: list[Token] | tuple[Token, ...] = TOKENS) -> Token | None:
    """By symbol or by contract address, case-insensitive."""
    s = symbol.strip().upper()
    return next((t for t in tokens if t.symbol.upper() == s or (t.address or "").upper() == s), None)
```

`agent/lazyagent/transfers.py`: add `NoRoute` right after `TransferError`:

```python
class NoRoute(TransferError):
    """The network's own venue has no quote for this pair — KyberSwap may still have one."""
```

Replace `display_rows` with:

```python
def display_rows(
    token: Token, amount: int, to: str, name: str | None, price: float | None, gas_cost: int, eth_price: float, network: str = "Sandbox"
) -> list[dict]:
    human = f"{format_units(amount, token.decimals)} {token.symbol}"
    if price is not None:
        human += f" ({format_usd(float(Decimal(amount).scaleb(-token.decimals)) * price)})"
    fee = float(Decimal(gas_cost).scaleb(-18)) * eth_price
    return [
        {"label": "To", "value": f"{name} ({short(to)})" if name else short(to)},
        {"label": "Amount", "value": human},
        {"label": "Network fee", "value": f"~{format_usd(fee)}"},
        {"label": "Network", "value": network},
    ]
```

Append:

```python
def token_address_rows(*tokens: Token) -> list[dict]:
    """Custom tokens aren't vetted: every card that touches one shows its full contract address."""
    rows = []
    for t in dict.fromkeys(tokens):
        if t.custom:
            note = " (matched by symbol — verify)" if t.matched_by_symbol else ""
            rows.append({"label": f"{t.symbol} address", "value": f"{t.address}{note}"})
    return rows
```

`agent/lazyagent/swaps.py`: in `approval_steps`, replace the first block (from `steps: list[Step] = []` through the `Allow {token.symbol}` append) with one call, then add `erc20_approval` above `_tx`:

```python
def approval_steps(
    token: Token, erc20_allowance: int, permit2_amount: int, permit2_expiration: int, amount: int, now: int
) -> list[Step]:
    steps = erc20_approval(token, erc20_allowance, amount, PERMIT2)
    if permit2_amount < amount or permit2_expiration <= now + 60:
        data = encode_permit2_approve(token.address, UNIVERSAL_ROUTER, amount, now + PERMIT2_EXPIRY_S)
        steps.append(Step("Allow Uniswap router", _tx(PERMIT2, data), GAS["permit2"]))
    return steps


def erc20_approval(token: Token, allowance: int, amount: int, spender: str) -> list[Step]:
    """approve(spender, amount) steps for an ERC-20 input, or none if the allowance already covers it."""
    if allowance >= amount:
        return []
    steps: list[Step] = []
    if token.symbol == "USDT" and allowance > 0:
        # USDT reverts when changing one nonzero allowance to another.
        steps.append(Step("Reset USDT allowance", _tx(token.address, encode_erc20_approve(spender, 0)), GAS["approve"]))
    steps.append(Step(f"Allow {token.symbol}", _tx(token.address, encode_erc20_approve(spender, amount)), GAS["approve"]))
    return steps
```

In `swap_rows`, change the parameter `impact: float,` to `impact: float | None,` and the row to:

```python
        {"label": "Price impact", "value": "unknown" if impact is None else f"{impact * 100:.2f}%"},
```

`agent/lazyagent/dexalot.py`: import `NoRoute` (`from .transfers import NoRoute, TransferError, format_units, format_usd, short`) and in `SandboxQuotes.quote` replace the non-200 branch with:

```python
        if status != 200:
            error = NoRoute if status == 404 else TransferError  # 404 = Dexalot doesn't offer the pair
            raise error(body.get("detail") or f"Dexalot quote failed ({status}).")
```

- [ ] **Step 4: Run the tests to verify they pass (old ones too)**

Run: `uv run --directory agent pytest -q tests/test_tokens.py tests/test_transfers.py tests/test_swaps.py tests/test_dexalot.py tests/test_swap_tools.py tests/test_network_tools.py tests/test_tools.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/tokens.py agent/lazyagent/transfers.py agent/lazyagent/swaps.py agent/lazyagent/dexalot.py agent/tests/test_tokens.py agent/tests/test_transfers.py agent/tests/test_swaps.py agent/tests/test_dexalot.py
git commit -m "feat(agent): custom token flags, NoRoute, address rows and shared ERC-20 approval"
```

---

### Task 2: Chain — custom-token prices, simulation with state overrides, access lists

**Files:**
- Modify: `agent/lazyagent/chain.py`, `agent/tests/fakes.py`
- Test: `agent/tests/test_chain.py`

**Interfaces:**
- Consumes: `Token.custom` (Task 1).
- Produces:
  - `PriceSource = Callable[[Token], Awaitable[float | None]]` in `chain.py`
  - `Chain.price_usd(token) -> float | None`; `Chain.simulate(tx: dict, overrides: dict | None = None) -> bytes`; `Chain.storage_keys(to: str, data: str) -> list[str]`
  - `RpcChain(rpc_url, poa=False, custom_price: PriceSource | None = None)`. A `custom` token's price comes only from `custom_price` (`None` without it).
  - `FakeChain` (tests): `prices: dict[str, float | None]`, `sim_out: int | Exception`, `sim_calls: list[(tx, overrides)]`, `access_keys: list[str]`, `allowance_slot: str | None`. `simulate` answers `allowance()` (selector `0xdd62ed3e`) from an override of `allowance_slot` only, and otherwise returns `encode(["uint256","uint256"], [sim_out, 150_000])` or raises `sim_out`.

- [ ] **Step 1: Write the failing test**

Append to `agent/tests/test_chain.py` (no fork needed):

```python
async def test_custom_token_price_comes_from_the_price_source():
    from lazyagent.tokens import Token

    coq = Token("COQ", "0x420FcA0121DC28039145009570975747295f2329", 18, custom=True)
    assert await RpcChain("http://127.0.0.1:1").price_usd(coq) is None  # no source: unknown, never $0

    async def source(token):
        return 1.5e-7 if token is coq else None

    assert await RpcChain("http://127.0.0.1:1", custom_price=source).price_usd(coq) == 1.5e-7
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --directory agent pytest -q tests/test_chain.py -k custom_token_price`
Expected: FAIL with `assert 0.0 is None`: the custom token falls through to the Uniswap pool price, whose quote fails on the unreachable RPC and yields 0.0. Once that is fixed, the next failure is `TypeError: ... unexpected keyword argument 'custom_price'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/chain.py`:

```python
from collections.abc import Awaitable, Callable
from typing import Protocol
```

After `FEED_DECIMALS = 8`:

```python
PriceSource = Callable[[Token], Awaitable[float | None]]  # USD price of a custom token, None if unknown
```

Protocol, replacing its body:

```python
class Chain(Protocol):
    async def eth_balance(self, address: str) -> int: ...
    async def token_balance(self, token: Token, address: str) -> int: ...
    async def price_usd(self, token: Token) -> float | None: ...
    async def gas_price(self) -> int: ...
    async def is_sandbox(self) -> bool: ...
    async def call(self, to: str, data: str, gas: int | None = None) -> bytes: ...
    async def block_timestamp(self) -> int: ...
    async def simulate(self, tx: dict, overrides: dict | None = None) -> bytes: ...
    async def storage_keys(self, to: str, data: str) -> list[str]: ...
```

`RpcChain.__init__` and the start of `price_usd`:

```python
    def __init__(self, rpc_url: str, poa: bool = False, custom_price: PriceSource | None = None):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.custom_price = custom_price
        if poa:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Avalanche blocks carry long extraData
```

```python
    async def price_usd(self, token: Token) -> float | None:
        if token.custom:
            return await self.custom_price(token) if self.custom_price else None
        if token.fixed_price is not None:
```

(the rest of `price_usd` is unchanged). Add after `call`:

```python
    async def simulate(self, tx: dict, overrides: dict | None = None) -> bytes:
        """eth_call with `from`/`value` and optional state overrides ({address: {"stateDiff": {slot: value}}})."""
        params = {k: Web3.to_checksum_address(v) if k in ("from", "to") else v for k, v in tx.items()}
        return bytes(await self.w3.eth.call(params, "latest", overrides))

    async def storage_keys(self, to: str, data: str) -> list[str]:
        """Storage slots of `to` that a call to it reads (eth_createAccessList)."""
        res = await self.w3.eth.create_access_list({"to": Web3.to_checksum_address(to), "data": data})
        keys = [k for e in res["accessList"] if e["address"].lower() == to.lower() for k in e["storageKeys"]]
        return [k if isinstance(k, str) else k.to_0x_hex() for k in keys]
```

`agent/tests/fakes.py`: add `from eth_abi import encode` at the top. In `FakeChain.__init__`, after `self.now = 1_700_000_000`:

```python
        self.prices: dict[str, float | None] = dict(PRICES)
        self.sim_out: int | Exception = 0  # what a simulated Kyber swap returns (or raises)
        self.sim_calls: list[tuple[dict, dict | None]] = []
        self.access_keys: list[str] = []  # storage slots eth_createAccessList reports
        self.allowance_slot: str | None = None  # the one that really holds allowance(owner, ROUTER)
```

Replace `price_usd` and add two methods after `block_timestamp`:

```python
    async def price_usd(self, token: Token) -> float | None:
        return self.prices.get(token.symbol, 1.0)
```

```python
    async def simulate(self, tx: dict, overrides: dict | None = None) -> bytes:
        self.sim_calls.append((tx, overrides))
        if tx["data"].startswith("0xdd62ed3e"):  # allowance(): only an override of the real slot counts
            diff = next(iter((overrides or {}).values()), {}).get("stateDiff", {})
            return int(diff.get(self.allowance_slot, "0x0"), 16).to_bytes(32, "big")
        if isinstance(self.sim_out, Exception):
            raise self.sim_out
        return encode(["uint256", "uint256"], [self.sim_out, 150_000])

    async def storage_keys(self, to: str, data: str) -> list[str]:
        return self.access_keys
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_chain.py -k "custom_token_price or unreachable" tests/test_tools.py tests/test_swap_tools.py`
Expected: PASS. RpcChain's `simulate`/`storage_keys` against a real fork are exercised by the Task 7 fork test.

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/chain.py agent/tests/fakes.py agent/tests/test_chain.py
git commit -m "feat(agent): chain simulation with state overrides and custom-token price source"
```

---

### Task 3: `kyber.py` — client, calldata verification, fork simulation, steps and rows

**Files:**
- Create: `agent/lazyagent/kyber.py`
- Modify: `agent/tests/fakes.py` (Kyber helpers)
- Test: `agent/tests/test_kyber.py`

**Interfaces:**
- Consumes: `NoRoute`, `TransferError`, `token_address_rows` (Task 1); `erc20_approval`, `swap_rows`, `min_out`, `parse_slippage`, `Step` (swaps); `Chain`, `PriceSource` (Task 2); `encode_erc20_allowance` (uniswap); `faucet._json`, `faucet.TIMEOUT_S`.
- Produces (all in `lazyagent.kyber`):
  - Constants `ROUTER`, `NATIVE`, `DESC`, `EXECUTION`, `SWAP_SELECTOR == "e21fd0e9"`, `SIMPLE_SELECTOR == "8af033fb"`, `SANDBOX_KYBER_SLIPPAGE_BPS = 5000`, `HEADERS`
  - `http_json(url, payload=None, headers=None) -> tuple[int, dict]` (raises `ConnectionError`)
  - `class Kyber(Protocol)`: `route(network, token_in, token_out, amount) -> dict` (Kyber `data`: `{routeSummary, routerAddress}`), `build(network, summary, sender, slippage_bps) -> dict` (Kyber `data`)
  - `class KyberClient(api=API)` implementing it (`route` raises `NoRoute`; both raise `TransferError` when unreachable)
  - `kyber_asset(token) -> str`, `kyber_slippage(text: str | None) -> int`
  - `@dataclass SwapRequest(token_in, token_out, amount, user, slippage_bps)`, `@dataclass Verified(data, value, expected, minimum)`
  - `verify(build: dict, req: SwapRequest) -> Verified` (raises `TransferError` "…didn't match your request (<why>)…")
  - `async allowance_override(chain, token, owner, amount) -> dict`, `async simulate(chain, user, v, override) -> int`
  - `kyber_label(summary) -> str`, `usd_impact(summary) -> float | None`, `kyber_steps(tin, tout, amount, allowance, v, gas) -> list[Step]`
  - `async kyber_plan(client, chain, net, tin, tout, amount, user, slippage: str | None) -> (steps, rows(fee_usd), hint, None)`, the same 4-tuple shape as `_uniswap_plan`/`_dexalot_plan`
  - `usd_price(client, net) -> PriceSource`
  - `fakes.py`: `EXECUTOR`, `kyber_desc(src, dst, receiver, amount, min_return, fee_receivers=())`, `swap_data(desc)`, `simple_data(desc)`, `FakeKyber(out=8_000_000*10**18, tamper=None, no_route=False)` with `.routes`/`.builds` call logs

- [ ] **Step 1: Add the test helpers to `agent/tests/fakes.py`**

Add these imports at the top (keep `from eth_abi import encode` from Task 2):

```python
from lazyagent.kyber import DESC, EXECUTION, NATIVE, ROUTER, SIMPLE_SELECTOR, SWAP_SELECTOR
from lazyagent.swaps import min_out
from lazyagent.transfers import NoRoute
```

Append:

```python
EXECUTOR = "0x8F10B468b06c6FD214B65F87778827F7D113f996"


def kyber_desc(src, dst, receiver, amount, min_return, fee_receivers=()):
    return (src, dst, [], [], list(fee_receivers), [1] * len(fee_receivers), receiver, amount, min_return, 0x200, b"")


def swap_data(desc) -> str:
    return "0x" + SWAP_SELECTOR + encode([EXECUTION], [(EXECUTOR, "0x" + "00" * 20, b"\x01", desc, b"")]).hex()


def simple_data(desc) -> str:
    return "0x" + SIMPLE_SELECTOR + encode(["address", DESC, "bytes", "bytes"], [EXECUTOR, desc, b"\x01", b""]).hex()


class FakeKyber:
    """Kyber API stand-in: a 2-hop LFJ route paying `out`, built honestly unless `tamper` edits the description."""

    def __init__(self, out: int = 8_000_000 * 10**18, tamper=None, no_route: bool = False):
        self.out, self.tamper, self.no_route = out, tamper, no_route
        self.routes: list[tuple] = []
        self.builds: list[tuple] = []

    async def route(self, network, token_in, token_out, amount):
        self.routes.append((network, token_in, token_out, amount))
        if self.no_route:
            raise NoRoute("KyberSwap has no route for that pair right now (route not found).")
        summary = {"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount), "amountOut": str(self.out),
                   "amountInUsd": "10", "amountOutUsd": "9.9", "gas": "180000",
                   "route": [[{"exchange": "traderjoe-v22"}], [{"exchange": "traderjoe"}]]}
        return {"routerAddress": ROUTER, "routeSummary": summary}

    async def build(self, network, summary, sender, slippage_bps):
        self.builds.append((network, sender, slippage_bps))
        amount = int(summary["amountIn"])
        desc = kyber_desc(summary["tokenIn"], summary["tokenOut"], sender, amount, min_out(self.out, slippage_bps))
        if self.tamper:
            desc = self.tamper(desc)
        native = summary["tokenIn"].lower() == NATIVE.lower()
        return {"routerAddress": ROUTER, "data": swap_data(desc), "transactionValue": str(amount if native else 0),
                "amountOut": str(self.out), "gas": "180000"}
```

- [ ] **Step 2: Write the failing tests**

Create `agent/tests/test_kyber.py`:

```python
import json

import pytest
from fakes import FakeChain, FakeKyber, kyber_desc, simple_data, swap_data

from lazyagent import kyber
from lazyagent.kyber import (
    NATIVE,
    ROUTER,
    SANDBOX_KYBER_SLIPPAGE_BPS,
    SIMPLE_SELECTOR,
    SWAP_SELECTOR,
    KyberClient,
    SwapRequest,
    Verified,
    allowance_override,
    kyber_label,
    kyber_slippage,
    kyber_steps,
    simulate,
    usd_impact,
    usd_price,
    verify,
)
from lazyagent.networks import AVALANCHE
from lazyagent.tokens import AVAX, Token, find_token
from lazyagent.transfers import NoRoute, TransferError

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
COQ_ADDR = "0x420FcA0121DC28039145009570975747295f2329"
COQ = Token("COQ", COQ_ADDR, 18, custom=True)
USDC = find_token("USDC", AVALANCHE.tokens)
OUT = 78_000_000 * 10**18
FIELDS = ("src", "dst", "srcReceivers", "srcAmounts", "feeReceivers", "feeAmounts", "receiver", "amount", "minReturn", "flags", "permit")
NATIVE_REQ = SwapRequest(NATIVE, COQ_ADDR, 10**18, ME, 5000)


def native_build(**desc_changes) -> dict:
    d = kyber_desc(NATIVE, COQ_ADDR, ME, 10**18, OUT // 2)
    d = tuple(desc_changes.get(k, v) for k, v in zip(FIELDS, d))
    return {"routerAddress": ROUTER, "data": swap_data(d), "transactionValue": str(10**18), "amountOut": str(OUT)}


def test_selectors_match_the_verified_router_abi():
    assert SWAP_SELECTOR == "e21fd0e9"
    assert SIMPLE_SELECTOR == "8af033fb"


def test_verify_accepts_an_honest_native_swap():
    v = verify(native_build(), NATIVE_REQ)
    assert v == Verified(native_build()["data"], 10**18, OUT, OUT // 2)


def test_verify_accepts_swap_simple_mode_for_erc20_input():
    d = kyber_desc(COQ_ADDR, USDC.address, ME, 10**24, 59_509)
    build = {"routerAddress": ROUTER, "data": simple_data(d), "transactionValue": "0", "amountOut": "119018"}
    v = verify(build, SwapRequest(COQ_ADDR, USDC.address, 10**24, ME, 5000))
    assert v.value == 0 and v.minimum == 59_509 and v.data.startswith("0x8af033fb")


@pytest.mark.parametrize(
    ("build", "why"),
    [
        ({**native_build(), "routerAddress": ALICE}, "unexpected router"),
        ({**native_build(), "transactionValue": "0"}, "wrong value"),
        (native_build(receiver=ALICE), "wrong recipient"),
        (native_build(feeReceivers=[ALICE], feeAmounts=[10]), "extra fee"),
        (native_build(minReturn=OUT // 2 - 1), "minimum too low"),
        (native_build(dst=USDC.address), "wrong tokens"),
        (native_build(amount=10**17), "wrong amount"),
        ({**native_build(), "data": "0x12345678" + native_build()["data"][10:]}, "unknown router function"),
        ({**native_build(), "data": "0xe21fd0e9dead"}, "unreadable calldata"),
        ({**native_build(), "amountOut": "0"}, "minimum too low"),
    ],
)
def test_verify_refuses(build, why):
    with pytest.raises(TransferError, match=why):
        verify(build, NATIVE_REQ)


def test_verify_refuses_simple_mode_with_native_input():
    d = kyber_desc(NATIVE, COQ_ADDR, ME, 10**18, OUT // 2)
    build = {"routerAddress": ROUTER, "data": simple_data(d), "transactionValue": str(10**18), "amountOut": str(OUT)}
    with pytest.raises(TransferError, match="unknown router function"):
        verify(build, NATIVE_REQ)


def test_kyber_slippage_defaults_to_the_sandbox_value():
    assert SANDBOX_KYBER_SLIPPAGE_BPS == 5000
    assert kyber_slippage(None) == 5000 and kyber_slippage(" ") == 5000
    assert kyber_slippage("2") == 200
    with pytest.raises(TransferError, match="between 0.01% and 5%"):
        kyber_slippage("50")


def test_kyber_label_and_impact():
    summary = {"route": [[{"exchange": "traderjoe-v22"}, {"exchange": "pmm-8/uniswap"}], [{"exchange": "traderjoe"}, {"exchange": "weird-dex"}]]}
    assert kyber_label(summary) == "KyberSwap via LFJ, Uniswap, weird-dex"
    assert kyber_label({}) == "KyberSwap"
    assert usd_impact({"amountInUsd": "10", "amountOutUsd": "9.9"}) == pytest.approx(0.01)
    assert usd_impact({"amountInUsd": "0", "amountOutUsd": "9.9"}) is None
    assert usd_impact({}) is None


def test_kyber_steps_native_and_erc20():
    v = Verified("0xe21fd0e9", 10**18, OUT, OUT // 2)
    assert [s.to_json() for s in kyber_steps(AVAX, COQ, 10**18, 0, v, 250_000)] == [
        {"label": "Swap AVAX → COQ", "request": {"to": ROUTER, "value": str(10**18), "data": "0xe21fd0e9"}}
    ]
    v0 = Verified("0xe21fd0e9", 0, 119018, 59509)
    steps = kyber_steps(COQ, USDC, 10**24, 0, v0, 250_000)
    assert [s.label for s in steps] == ["Allow COQ", "Swap COQ → USDC"]
    assert steps[0].request["to"] == COQ_ADDR and steps[0].request["data"].startswith("0x095ea7b3")
    assert [s.label for s in kyber_steps(COQ, USDC, 10**24, 10**24, v0, 250_000)] == ["Swap COQ → USDC"]


async def test_allowance_override_finds_the_real_slot():
    chain = FakeChain()
    chain.access_keys = ["0x01", "0xab"]
    chain.allowance_slot = "0xab"
    assert await allowance_override(chain, COQ_ADDR, ME, 5) == {COQ_ADDR: {"stateDiff": {"0xab": "0x" + (5).to_bytes(32, "big").hex()}}}
    chain.allowance_slot = None
    with pytest.raises(TransferError, match="couldn't simulate"):
        await allowance_override(chain, COQ_ADDR, ME, 5)


async def test_simulate_checks_the_returned_amount():
    v = Verified("0xe21fd0e9", 10**18, 1_000, 500)
    chain = FakeChain()
    chain.sim_out = 960
    assert await simulate(chain, ME, v, None) == 960
    assert chain.sim_calls[-1] == ({"from": ME, "to": ROUTER, "data": "0xe21fd0e9", "value": 10**18}, None)
    chain.sim_out = 940
    with pytest.raises(TransferError, match="doesn't match"):
        await simulate(chain, ME, v, None)
    chain.sim_out = RuntimeError("execution reverted")
    with pytest.raises(TransferError, match="fails on the Sandbox fork"):
        await simulate(chain, ME, v, None)


async def test_usd_price_routes_one_usdc_and_inverts():
    k = FakeKyber(out=8_000_000 * 10**18)
    price = usd_price(k, AVALANCHE)
    assert await price(COQ) == pytest.approx(1 / 8_000_000)
    assert k.routes == [("avalanche", USDC.address, COQ_ADDR, 10**6)]
    assert await usd_price(FakeKyber(no_route=True), AVALANCHE)(COQ) is None


async def test_client_route_and_build(monkeypatch):
    calls = []

    def fake_http(url, payload=None, headers=None):
        calls.append((url, payload, headers))
        if url.endswith("/route/build"):
            return 200, {"code": 0, "data": {"data": "0xe21fd0e9", "routerAddress": ROUTER}}
        return 200, {"code": 0, "data": {"routeSummary": {"amountOut": "5"}, "routerAddress": ROUTER}}

    monkeypatch.setattr(kyber, "http_json", fake_http)
    client = KyberClient()
    route = await client.route("avalanche", NATIVE, COQ_ADDR, 10**18)
    assert route["routeSummary"]["amountOut"] == "5"
    assert calls[0][0] == (
        "https://aggregator-api.kyberswap.com/avalanche/api/v1/routes"
        f"?tokenIn={NATIVE}&tokenOut={COQ_ADDR}&amountIn={10**18}"
    )
    assert calls[0][2]["x-client-id"] == "lazywallet" and calls[0][2]["user-agent"]
    await client.build("ethereum", {"amountOut": "5"}, ME, 5000)
    url, payload, _ = calls[1]
    assert url == "https://aggregator-api.kyberswap.com/ethereum/api/v1/route/build"
    assert payload == {"routeSummary": {"amountOut": "5"}, "sender": ME, "recipient": ME, "slippageTolerance": 5000, "skipSimulateTx": True}


async def test_client_errors(monkeypatch):
    monkeypatch.setattr(kyber, "http_json", lambda *a: (400, {"code": 4008, "message": "route not found"}))
    with pytest.raises(NoRoute, match="route not found"):
        await KyberClient().route("avalanche", NATIVE, COQ_ADDR, 1)
    with pytest.raises(TransferError, match="couldn't build"):
        await KyberClient().build("avalanche", {}, ME, 5000)

    def down(*a):
        raise ConnectionError("no network")

    monkeypatch.setattr(kyber, "http_json", down)
    with pytest.raises(TransferError, match="isn't reachable"):
        await KyberClient().route("avalanche", NATIVE, COQ_ADDR, 1)


def test_http_json_reads_error_bodies(monkeypatch):
    import io
    import urllib.error

    def raise_400(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(json.dumps({"message": "invalid"}).encode()))

    monkeypatch.setattr(kyber.urllib.request, "urlopen", raise_400)
    assert kyber.http_json("https://x.test/a") == (400, {"message": "invalid"})
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_kyber.py`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'lazyagent.kyber'` (raised from `fakes.py`).

- [ ] **Step 4: Implement `agent/lazyagent/kyber.py`**

```python
"""KyberSwap aggregator for pairs Uniswap v4 / Dexalot can't do, and for any custom token.

Kyber's calldata is untrusted input: verify() decodes it and checks it against the user's request, and simulate()
runs it on the Sandbox fork, before any card is shown. Router ABI from the verified MetaAggregationRouterV2 source
(same address on Ethereum and Avalanche; selectors checked against real /route/build responses on 2026-10-15)."""

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from eth_abi import decode
from web3 import Web3

from .chain import Chain, PriceSource
from .faucet import TIMEOUT_S, _json
from .networks import Network
from .swaps import Step, erc20_approval, min_out, parse_slippage, swap_rows
from .tokens import Token, find_token
from .transfers import NoRoute, TransferError, token_address_rows
from .uniswap import encode_erc20_allowance

API = "https://aggregator-api.kyberswap.com"
CHAIN_SLUG = {"ethereum": "ethereum", "avalanche": "avalanche"}
# Kyber's CDN answers 403 to Python's default user-agent.
HEADERS = {"x-client-id": "lazywallet", "user-agent": "lazywallet/0.1", "accept": "application/json"}
ROUTER = Web3.to_checksum_address("0x6131B5fae19EA4f9D964eAc0408E4408b66337b5")  # MetaAggregationRouterV2
NATIVE = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
DESC = "(address,address,address[],uint256[],address[],uint256[],address,uint256,uint256,uint256,bytes)"
EXECUTION = f"(address,address,bytes,{DESC},bytes)"
SWAP_SELECTOR = Web3.keccak(text=f"swap({EXECUTION})")[:4].hex()  # e21fd0e9
SIMPLE_SELECTOR = Web3.keccak(text=f"swapSimpleMode(address,{DESC},bytes,bytes)")[:4].hex()  # 8af033fb
# Kyber's API caps slippageTolerance at 5000 bps. Fine on a private fork (no MEV); the 5% simulation check
# below is what catches a wrong amount.
SANDBOX_KYBER_SLIPPAGE_BPS = 5000
SIM_TOLERANCE_PCT = 5
SWAP_GAS_FLOOR = 250_000
DEX_NAMES = {
    "traderjoe": "LFJ", "traderjoe-v21": "LFJ", "traderjoe-v22": "LFJ", "pangolin": "Pangolin", "pharaoh": "Pharaoh",
    "uniswap": "Uniswap", "uniswapv3": "Uniswap", "uniswap-v4": "Uniswap", "sushiswap": "SushiSwap",
    "pancake-v3": "PancakeSwap", "balancer-v2-weighted": "Balancer", "curve-stable-ng": "Curve",
}


def http_json(url: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    """GET (or POST `payload` as JSON); returns (status, JSON body or {}). Raises ConnectionError if unreachable."""
    h = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        h["content-type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=TIMEOUT_S) as res:
            return res.status, _json(res.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(str(e)) from e


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class Kyber(Protocol):
    async def route(self, network: str, token_in: str, token_out: str, amount: int) -> dict: ...
    async def build(self, network: str, summary: dict, sender: str, slippage_bps: int) -> dict: ...


class KyberClient:
    def __init__(self, api: str = API):
        self.api = api

    async def _call(self, network: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        url = f"{self.api}/{CHAIN_SLUG[network]}/api/v1/{path}"
        try:
            return await asyncio.to_thread(http_json, url, payload, HEADERS)
        except ConnectionError as e:
            raise TransferError("KyberSwap isn't reachable right now — try again in a moment.") from e

    async def route(self, network: str, token_in: str, token_out: str, amount: int) -> dict:
        query = urllib.parse.urlencode({"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount)})
        status, body = await self._call(network, f"routes?{query}")
        data = body.get("data") or {}
        if status != 200 or _int((data.get("routeSummary") or {}).get("amountOut")) <= 0:
            raise NoRoute(f"KyberSwap has no route for that pair right now ({body.get('message') or status}).")
        return data

    async def build(self, network: str, summary: dict, sender: str, slippage_bps: int) -> dict:
        # skipSimulateTx: Kyber would otherwise simulate on the real chain, where Sandbox wallets hold nothing (400).
        payload = {"routeSummary": summary, "sender": sender, "recipient": sender, "slippageTolerance": slippage_bps, "skipSimulateTx": True}
        status, body = await self._call(network, "route/build", payload)
        if status != 200 or not isinstance(body.get("data"), dict):
            raise TransferError(f"KyberSwap couldn't build that swap ({body.get('message') or status}).")
        return body["data"]


def kyber_asset(token: Token) -> str:
    return NATIVE if token.address is None else token.address


def kyber_slippage(text: str | None) -> int:
    """Sandbox default unless the user named a slippage (then the usual 0.01–5% rule applies)."""
    return SANDBOX_KYBER_SLIPPAGE_BPS if text is None or not str(text).strip() else parse_slippage(text)


@dataclass(frozen=True)
class SwapRequest:
    token_in: str  # Kyber asset address (NATIVE for the native coin)
    token_out: str
    amount: int
    user: str
    slippage_bps: int


@dataclass(frozen=True)
class Verified:
    data: str
    value: int
    expected: int  # Kyber's quoted output
    minimum: int  # minReturnAmount the router enforces


def _desc(selector: str, args: bytes, native: bool) -> tuple | None:
    if selector == SWAP_SELECTOR:
        return decode([EXECUTION], args)[0][3]
    if selector == SIMPLE_SELECTOR and not native:  # swapSimpleMode is nonpayable
        return decode(["address", DESC, "bytes", "bytes"], args)[1]
    return None


def verify(build: dict, req: SwapRequest) -> Verified:
    """Refuse Kyber's built swap unless it does exactly what the user asked."""

    def refuse(why: str) -> TransferError:
        return TransferError(f"KyberSwap's transaction didn't match your request ({why}), so I didn't show it. Try again.")

    if str(build.get("routerAddress", "")).lower() != ROUTER.lower():
        raise refuse("unexpected router")
    native = req.token_in.lower() == NATIVE.lower()
    value = _int(build.get("transactionValue"))
    if value != (req.amount if native else 0):
        raise refuse("wrong value")
    try:
        raw = bytes.fromhex(str(build.get("data", "")).removeprefix("0x"))
        desc = _desc(raw[:4].hex(), raw[4:], native)
    except Exception:
        raise refuse("unreadable calldata") from None
    if desc is None:
        raise refuse("unknown router function")
    src, dst, _, _, fee_receivers, _, receiver, amount, min_return, _, _ = desc
    if src.lower() != req.token_in.lower() or dst.lower() != req.token_out.lower():
        raise refuse("wrong tokens")
    if amount != req.amount:
        raise refuse("wrong amount")
    if receiver.lower() != req.user.lower():
        raise refuse("wrong recipient")
    if fee_receivers:
        raise refuse("extra fee")
    expected = _int(build.get("amountOut"))
    if expected <= 0 or min_return < min_out(expected, req.slippage_bps):
        raise refuse("minimum too low")
    return Verified("0x" + raw.hex(), value, expected, min_return)


async def allowance_override(chain: Chain, token: str, owner: str, amount: int) -> dict:
    """State override giving ROUTER `amount` of allowance — the approve step hasn't run when we simulate.
    The token's allowance slot is one of the slots allowance(owner, ROUTER) reads; we keep the one that works."""
    data = encode_erc20_allowance(owner, ROUTER)
    value = "0x" + amount.to_bytes(32, "big").hex()
    for key in await chain.storage_keys(token, data):
        override = {Web3.to_checksum_address(token): {"stateDiff": {key: value}}}
        try:
            got = await chain.simulate({"to": token, "data": data}, override)
        except Exception:
            continue
        if int.from_bytes(got[:32], "big") == amount:
            return override
    raise TransferError("I couldn't simulate this swap on the Sandbox fork (unusual token storage), so I didn't show it.")


async def simulate(chain: Chain, user: str, v: Verified, override: dict | None) -> int:
    """Run the swap with eth_call from the user; the router returns (returnAmount, gasUsed)."""
    try:
        raw = await chain.simulate({"from": user, "to": ROUTER, "data": v.data, "value": v.value}, override)
        returned = decode(["uint256", "uint256"], raw)[0]
    except Exception as e:
        raise TransferError(f"That KyberSwap route fails on the Sandbox fork right now ({e}), so I didn't show it.") from e
    if abs(returned - v.expected) * 100 > v.expected * SIM_TOLERANCE_PCT:
        raise TransferError("KyberSwap's quote doesn't match what the swap does on the Sandbox fork, so I didn't show it. Try again.")
    return returned


def _dex(exchange: str) -> str:
    key = exchange.split("/")[-1]  # "pmm-8/uniswap" → "uniswap"
    return DEX_NAMES.get(key, key)


def kyber_label(summary: dict) -> str:
    names = [_dex(str(p.get("exchange") or "")) for hop in summary.get("route") or [] for p in hop]
    names = list(dict.fromkeys(n for n in names if n))
    return f"KyberSwap via {', '.join(names)}" if names else "KyberSwap"


def usd_impact(summary: dict) -> float | None:
    """Value lost between input and output by Kyber's own USD estimates; None when it has no prices."""
    try:
        usd_in, usd_out = float(summary["amountInUsd"]), float(summary["amountOutUsd"])
    except (KeyError, TypeError, ValueError):
        return None
    return max(1 - usd_out / usd_in, 0.0) if usd_in > 0 and usd_out > 0 else None


def kyber_steps(token_in: Token, token_out: Token, amount: int, allowance: int, v: Verified, gas: int) -> list[Step]:
    steps = erc20_approval(token_in, allowance, amount, ROUTER) if token_in.address else []
    steps.append(Step(f"Swap {token_in.symbol} → {token_out.symbol}", {"to": ROUTER, "value": str(v.value), "data": v.data}, gas))
    return steps


async def kyber_plan(
    client: Kyber, chain: Chain, net: Network, tin: Token, tout: Token, amount: int, user: str, slippage: str | None
) -> tuple[list[Step], Callable[[float], list[dict]], str, None]:
    """Route, build, verify and simulate a KyberSwap swap; returns (steps, rows(fee_usd), revert hint, None)."""
    bps = kyber_slippage(slippage)
    req = SwapRequest(kyber_asset(tin), kyber_asset(tout), amount, user, bps)
    route = await client.route(net.key, req.token_in, req.token_out, amount)
    summary = route["routeSummary"]
    v = verify(await client.build(net.key, summary, user, bps), req)
    allowance, override = 0, None
    if tin.address is not None:
        allowance = int.from_bytes((await chain.call(tin.address, encode_erc20_allowance(user, ROUTER)))[:32], "big")
        if allowance < amount:
            override = await allowance_override(chain, tin.address, user, amount)
    await simulate(chain, user, v, override)
    steps = kyber_steps(tin, tout, amount, allowance, v, max(_int(summary.get("gas")), SWAP_GAS_FLOOR))
    label, impact = kyber_label(summary), usd_impact(summary)

    def rows(fee_usd: float) -> list[dict]:
        base = swap_rows(user, tin, tout, amount, v.expected, v.minimum, label, impact, fee_usd, network=net.label)
        return base + token_address_rows(tin, tout)

    return steps, rows, f" The price probably moved more than the {bps / 100:g}% slippage — ask again for a fresh quote.", None


def usd_price(client: Kyber, net: Network) -> PriceSource:
    """Custom-token USD price from KyberSwap: route 1 USDC → token and invert
    (1 token → USDC rounds to 0–1 raw unit for memecoins)."""
    usdc = find_token("USDC", net.tokens)

    async def price(token: Token) -> float | None:
        try:
            data = await client.route(net.key, usdc.address, token.address, 10**usdc.decimals)
            out = int(data["routeSummary"]["amountOut"])
        except Exception:
            return None
        return 10**token.decimals / out if out > 0 else None

    return price
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_kyber.py tests/test_tools.py tests/test_swap_tools.py tests/test_network_tools.py`
Expected: all PASS (23 in `test_kyber.py`).

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/kyber.py agent/tests/fakes.py agent/tests/test_kyber.py
git commit -m "feat(agent): KyberSwap client with calldata verification and fork simulation"
```

---

### Task 4: `custom_tokens.py` — saved tokens, contract addresses, symbol search

**Files:**
- Create: `agent/lazyagent/custom_tokens.py`
- Modify: `agent/tests/fakes.py` (FakeSearch)
- Test: `agent/tests/test_custom_tokens.py`

**Interfaces:**
- Consumes: `Token`, `find_token` (Task 1); `Chain.call` (existing); `kyber.http_json` (Task 3); `Network` (networks).
- Produces (in `lazyagent.custom_tokens`):
  - `ADDRESS` (regex `^0x[0-9a-fA-F]{40}$`), `MIN_RESERVE_USD = 10_000`, `GECKO_NETWORK = {"ethereum": "eth", "avalanche": "avax"}`
  - `merge(net: Network, saved: list[dict]) -> Network`. Appends valid saved tokens whose `chainId == net.chain_id` as `Token(custom=True)` with a checksummed address. Built-ins win on symbol/address clash, and malformed entries and duplicates are skipped. Returns `net` itself when nothing is added.
  - `async read_token(chain, address) -> Token | None` (`symbol()` string or bytes32, `decimals()`; `None` for EOAs/junk)
  - `pick_pool(body: dict, symbol: str) -> tuple[str, str] | None`: `(address, symbol)` of the deepest exact-symbol base token, if its reserve is ≥ $10k
  - `class Search(Protocol)`: `async pools(network_key, query) -> dict`; `class GeckoSearch` implements it
  - `async discover(text, net, chain, search: Search | None) -> Token | None` (address → `read_token`; symbol → search + `read_token`, `matched_by_symbol=True`, symbol as GeckoTerminal lists it)
  - `fakes.py`: `FakeSearch(body=None)` with `.calls`
  - `test_custom_tokens.py` exports `COQ_ADDR`, `COQ_SAVED`, `GT_COQ`, which Task 5's tests import

- [ ] **Step 1: Add `FakeSearch` to `agent/tests/fakes.py`** (append):

```python
class FakeSearch:
    def __init__(self, body: dict | None = None):
        self.body = body or {"data": [], "included": []}
        self.calls: list[tuple[str, str]] = []

    async def pools(self, network, query):
        self.calls.append((network, query))
        return self.body
```

- [ ] **Step 2: Write the failing tests**

Create `agent/tests/test_custom_tokens.py`:

```python
from eth_abi import encode
from fakes import FakeChain, FakeSearch

from lazyagent.custom_tokens import discover, merge, pick_pool, read_token
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.tokens import Token, find_token

COQ_ADDR = "0x420FcA0121DC28039145009570975747295f2329"
COQ_SAVED = {"chainId": 43114, "address": COQ_ADDR.lower(), "symbol": "COQ", "decimals": 18}

# Trimmed real GeckoTerminal response: GET /search/pools?query=COQ&network=avax&include=base_token (2026-10-15).
GT_COQ = {
    "data": [
        {"id": "avax_0x41ab86eecbd110a82ca602d032a461f453066f1e", "type": "pool",
         "attributes": {"name": "COQ / WAVAX", "reserve_in_usd": "623823.6468"},
         "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000001", "type": "pool",
         "attributes": {"name": "COQ / USDC", "reserve_in_usd": "8844.7096"},
         "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000002", "type": "pool",
         "attributes": {"name": "COQAI / COQ", "reserve_in_usd": "18166.7587"},
         "relationships": {"base_token": {"data": {"id": "avax_0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000003", "type": "pool",
         "attributes": {"name": "TINY / WAVAX", "reserve_in_usd": "9999.99"},
         "relationships": {"base_token": {"data": {"id": "avax_0x1111111111111111111111111111111111111111", "type": "token"}}}},
    ],
    "included": [
        {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token",
         "attributes": {"address": "0x420fca0121dc28039145009570975747295f2329", "name": "COQINU", "symbol": "COQ", "decimals": 18}},
        {"id": "avax_0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "type": "token",
         "attributes": {"address": "0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "name": "COQ AI", "symbol": "COQAI", "decimals": 18}},
        {"id": "avax_0x1111111111111111111111111111111111111111", "type": "token",
         "attributes": {"address": "0x1111111111111111111111111111111111111111", "name": "Tiny", "symbol": "TINY", "decimals": 18}},
    ],
}


def erc20_chain(symbol: bytes, decimals: int = 18) -> FakeChain:
    chain = FakeChain()
    chain.call_responses["0x95d89b41"] = symbol
    chain.call_responses["0x313ce567"] = encode(["uint8"], [decimals])
    return chain


def test_merge_appends_saved_tokens_for_this_chain_only():
    net = merge(AVALANCHE, [COQ_SAVED, {**COQ_SAVED, "chainId": 1, "symbol": "PEPE"}])
    coq = find_token("coq", net.tokens)
    assert coq == Token("COQ", COQ_ADDR, 18, custom=True)  # checksummed
    assert net.tokens[: len(AVALANCHE.tokens)] == AVALANCHE.tokens
    assert find_token("PEPE", net.tokens) is None
    assert merge(ETHEREUM, [COQ_SAVED]) is ETHEREUM


def test_merge_builtins_win_and_bad_entries_are_skipped():
    saved = [
        {**COQ_SAVED, "symbol": "usdc"},  # symbol clash with a built-in
        {**COQ_SAVED, "address": AVALANCHE.tokens[1].address},  # address clash
        {**COQ_SAVED, "address": "0x123"},
        {**COQ_SAVED, "decimals": "lots"},
        {"chainId": 43114},
        "junk",
        COQ_SAVED,
        {**COQ_SAVED, "address": COQ_ADDR},  # duplicate in another case
    ]
    net = merge(AVALANCHE, saved)
    assert [t.symbol for t in net.tokens[len(AVALANCHE.tokens):]] == ["COQ"]


def test_find_token_matches_contract_addresses():
    net = merge(AVALANCHE, [COQ_SAVED])
    assert find_token(COQ_ADDR.lower(), net.tokens).symbol == "COQ"
    assert find_token("0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", net.tokens).symbol == "USDC"


def test_pick_pool_takes_the_deepest_exact_symbol_match():
    assert pick_pool(GT_COQ, "coq") == ("0x420fca0121dc28039145009570975747295f2329", "COQ")
    assert pick_pool(GT_COQ, "COQAI") == ("0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "COQAI")
    assert pick_pool(GT_COQ, "TINY") is None  # below $10,000
    assert pick_pool(GT_COQ, "CO") is None
    assert pick_pool({"data": [{"broken": True}]}, "COQ") is None
    assert pick_pool({}, "COQ") is None


async def test_read_token_string_and_bytes32_symbols():
    token = await read_token(erc20_chain(encode(["string"], ["COQ"])), COQ_ADDR.lower())
    assert token == Token("COQ", COQ_ADDR, 18, custom=True)
    mkr = await read_token(erc20_chain(b"MKR".ljust(32, b"\0")), COQ_ADDR)
    assert mkr.symbol == "MKR"


async def test_read_token_refuses_non_tokens():
    assert await read_token(FakeChain(), COQ_ADDR) is None  # empty symbol (FakeChain answers zero bytes)
    eoa = FakeChain()
    eoa.call_responses["0x95d89b41"] = b""
    eoa.call_responses["0x313ce567"] = b""
    assert await read_token(eoa, COQ_ADDR) is None
    assert await read_token(erc20_chain(encode(["string"], ["X" * 40])), COQ_ADDR) is None


async def test_discover_by_address_reads_the_fork():
    chain = erc20_chain(encode(["string"], ["COQ"]))
    search = FakeSearch(GT_COQ)
    token = await discover(f" {COQ_ADDR} ", AVALANCHE, chain, search)
    assert token == Token("COQ", COQ_ADDR, 18, custom=True)
    assert search.calls == []


async def test_discover_by_symbol_marks_the_match():
    chain = erc20_chain(encode(["string"], ["COQ"]))
    search = FakeSearch(GT_COQ)
    token = await discover("coq", AVALANCHE, chain, search)
    assert token == Token("COQ", COQ_ADDR, 18, custom=True, matched_by_symbol=True)
    assert search.calls == [("avalanche", "coq")]
    assert await discover("TINY", AVALANCHE, chain, search) is None
    assert await discover("coq", AVALANCHE, chain, None) is None


async def test_discover_survives_a_failing_search():
    class Down:
        async def pools(self, network, query):
            raise ConnectionError("rate limited")

    assert await discover("coq", AVALANCHE, erc20_chain(encode(["string"], ["COQ"])), Down()) is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_custom_tokens.py`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'lazyagent.custom_tokens'`.

- [ ] **Step 4: Implement `agent/lazyagent/custom_tokens.py`**

```python
"""Tokens beyond the built-in registry: the wallet's saved list (lw.tokens), contract addresses and symbol search."""

import asyncio
import re
import urllib.parse
from dataclasses import replace
from typing import Protocol

from eth_abi import decode
from web3 import Web3

from .chain import Chain
from .kyber import http_json
from .networks import Network
from .tokens import Token

GECKO_API = "https://api.geckoterminal.com/api/v2"
GECKO_NETWORK = {"ethereum": "eth", "avalanche": "avax"}
MIN_RESERVE_USD = 10_000
SYMBOL, DECIMALS = "0x95d89b41", "0x313ce567"  # symbol(), decimals()
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _saved(entry: dict) -> Token | None:
    try:
        address, symbol, decimals = str(entry["address"]), str(entry["symbol"]).strip(), int(entry["decimals"])
    except (KeyError, TypeError, ValueError):
        return None
    if not ADDRESS.match(address) or not symbol or len(symbol) > 32 or not 0 <= decimals <= 255:
        return None
    return Token(symbol, Web3.to_checksum_address(address), decimals, custom=True)


def merge(net: Network, saved: list[dict]) -> Network:
    """The network plus the wallet's saved tokens on its chain. Built-ins win on a symbol or address clash."""
    taken = {t.symbol.upper() for t in net.tokens} | {t.address.lower() for t in net.tokens if t.address}
    extra: list[Token] = []
    for entry in saved:
        token = _saved(entry) if isinstance(entry, dict) and entry.get("chainId") == net.chain_id else None
        if token is None or token.symbol.upper() in taken or token.address.lower() in taken:
            continue
        taken |= {token.symbol.upper(), token.address.lower()}
        extra.append(token)
    return replace(net, tokens=net.tokens + tuple(extra)) if extra else net


def _symbol(raw: bytes) -> str:
    try:
        text = decode(["string"], raw)[0]
    except Exception:
        text = raw[:32].rstrip(b"\0").decode("utf-8", "ignore")  # bytes32 symbols (e.g. MKR)
    text = text.strip()
    return text if len(text) <= 32 and text.isprintable() else ""


async def read_token(chain: Chain, address: str) -> Token | None:
    """symbol() and decimals() on the fork; None if the address isn't an ERC-20 there."""
    try:
        raw_symbol, raw_decimals = await chain.call(address, SYMBOL), await chain.call(address, DECIMALS)
    except Exception:
        return None
    symbol = _symbol(raw_symbol)
    decimals = int.from_bytes(raw_decimals[:32], "big") if len(raw_decimals) >= 32 else -1
    if not symbol or not 0 <= decimals <= 255:
        return None
    return Token(symbol, Web3.to_checksum_address(address), decimals, custom=True)


def pick_pool(body: dict, symbol: str) -> tuple[str, str] | None:
    """(address, symbol) of the base token with exactly this symbol in the deepest pool, if that pool holds ≥ $10k."""
    try:
        tokens = {t["id"]: t["attributes"] for t in body.get("included") or [] if t.get("type") == "token"}
        best: tuple[float, str, str] | None = None
        for pool in body.get("data") or []:
            base = tokens.get(pool["relationships"]["base_token"]["data"]["id"])
            if not base or str(base.get("symbol", "")).lower() != symbol.strip().lower():
                continue
            reserve = float(pool["attributes"].get("reserve_in_usd") or 0)
            if best is None or reserve > best[0]:
                best = (reserve, base["address"], base["symbol"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    if best is None or best[0] < MIN_RESERVE_USD or not ADDRESS.match(best[1]):
        return None
    return best[1], best[2]


class Search(Protocol):
    async def pools(self, network: str, query: str) -> dict: ...


class GeckoSearch:
    """GeckoTerminal pool search (free API, no key)."""

    async def pools(self, network: str, query: str) -> dict:
        q = urllib.parse.urlencode({"query": query, "network": GECKO_NETWORK[network], "include": "base_token"})
        status, body = await asyncio.to_thread(http_json, f"{GECKO_API}/search/pools?{q}", None, {"accept": "application/json"})
        if status != 200:
            raise ConnectionError(f"GeckoTerminal search failed ({status})")
        return body


async def discover(text: str, net: Network, chain: Chain, search: Search | None) -> Token | None:
    """A token that's neither built in nor saved: a 0x address read on the fork, else a symbol search on that network."""
    query = text.strip()
    if ADDRESS.match(query):
        return await read_token(chain, query)
    if search is None or not query:
        return None
    try:
        found = pick_pool(await search.pools(net.key, query), query)
    except Exception:
        return None
    if found is None:
        return None
    token = await read_token(chain, found[0])
    return replace(token, symbol=found[1], matched_by_symbol=True) if token else None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_custom_tokens.py`
Expected: 9 PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/lazyagent/custom_tokens.py agent/tests/fakes.py agent/tests/test_custom_tokens.py
git commit -m "feat(agent): custom token resolution — saved list, contract address, GeckoTerminal search"
```

---

### Task 5: Wallet tools — custom tokens everywhere, venue choice, KyberSwap swaps

**Files:**
- Modify: `agent/lazyagent/tools.py`
- Test: `agent/tests/test_kyber_tools.py` (create)

**Interfaces:**
- Consumes: everything from Tasks 1–4: `merge`, `discover`, `ADDRESS`, `MIN_RESERVE_USD`, `Search`, `Kyber`, `kyber_plan`, `NoRoute`, `token_address_rows`.
- Produces:
  - `WalletContext(address=None, contacts=[], tokens=[])`: `tokens` holds the wallet's saved `CustomToken` dicts
  - `WalletTools(..., dexalot=None, kyber: Kyber | None = None, search: Search | None = None)`
  - `WalletTools.networks` returns networks merged with `ctx.tokens`, so balances, transfers and swaps see saved tokens
  - The swap confirm card's `tx` gains `addToken: {chainId, address, symbol, decimals}` when the output token is custom
  - Holdings/balance-change `usdPrice` may be `None`

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_kyber_tools.py`:

```python
import asyncio

from eth_abi import encode
from fakes import FakeChain, FakeKyber, FakeQuoter, FakeSearch, Outbox
from test_custom_tokens import COQ_ADDR, COQ_SAVED, GT_COQ

from lazyagent.kyber import NATIVE, ROUTER
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import UNIVERSAL_ROUTER, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
OUT = 8_000_000 * 10**18


def coq_chain(**tokens) -> FakeChain:
    """An Avalanche fork where COQ_ADDR answers symbol()/decimals() like the real COQ."""
    chain = FakeChain(tokens=tokens)
    chain.call_responses["0x95d89b41"] = encode(["string"], ["COQ"])
    chain.call_responses["0x313ce567"] = encode(["uint8"], [18])
    chain.sim_out = OUT
    return chain


def make(avax=None, kyber=None, search=None, saved=(), quoter=None, eth=None):
    out = Outbox()
    proposals = Proposals()
    avax = avax or coq_chain()
    kyber = kyber or FakeKyber(out=OUT)
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}], tokens=list(saved))
    tools = WalletTools(eth or FakeChain(), out, ctx, proposals, approval_timeout=5, quoter=quoter,
                        avalanche=avax, kyber=kyber, search=search)
    return tools, out, proposals, avax, kyber


def text(result):
    return result["content"][0]["text"]


def rows_of(confirm):
    return {r["label"]: r["value"] for r in confirm["tx"]["rows"]}


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


async def test_buy_by_contract_address_goes_through_kyber_and_saves_the_token():
    tools, out, proposals, avax, kyber = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["title"] == "Swap 1 AVAX → COQ"
    assert confirm["tx"]["steps"] == [
        {"label": "Swap AVAX → COQ", "request": {"to": ROUTER, "value": str(10**18), "data": confirm["tx"]["steps"][0]["request"]["data"], "chainId": 43114}}
    ]
    assert confirm["tx"]["steps"][0]["request"]["data"].startswith("0xe21fd0e9")
    assert confirm["tx"]["addToken"] == {"chainId": 43114, "address": COQ_ADDR, "symbol": "COQ", "decimals": 18}
    rows = rows_of(confirm)
    assert rows["Route"] == "KyberSwap via LFJ"
    assert rows["COQ address"] == COQ_ADDR
    assert rows["Expected"] == "≈ 8000000 COQ" and rows["Minimum received"] == "4000000 COQ"
    assert rows["Network"] == "Avalanche (Sandbox)"
    assert kyber.routes == [("avalanche", NATIVE, COQ_ADDR, 10**18)]
    assert kyber.builds == [("avalanche", ME, 5000)]
    assert avax.sim_calls[-1][1] is None  # native input needs no allowance override
    avax.tokens["COQ"] = OUT
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    assert "Swapped 1 AVAX for 8000000 COQ" in text(await task)


async def test_sell_saved_token_adds_approval_and_simulates_with_an_allowance_override():
    avax = coq_chain(COQ=10**24)
    avax.access_keys, avax.allowance_slot = ["0x01", "0xab"], "0xab"
    tools, out, _, _, _ = make(avax=avax, kyber=FakeKyber(out=119_018), saved=[COQ_SAVED])
    task = asyncio.create_task(tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": "1000000"}))
    avax.sim_out = 119_018
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow COQ", "Swap COQ → USDC"]
    assert confirm["tx"]["steps"][0]["request"]["to"] == COQ_ADDR
    assert confirm["tx"]["steps"][1]["request"]["value"] == "0"
    assert "addToken" not in confirm["tx"]  # USDC is built in
    swap_call = avax.sim_calls[-1]
    assert swap_call[0]["to"] == ROUTER
    assert swap_call[1] == {COQ_ADDR: {"stateDiff": {"0xab": "0x" + (10**24).to_bytes(32, "big").hex()}}}
    assert rows_of(confirm)["COQ address"] == COQ_ADDR
    task.cancel()


async def test_matched_by_symbol_is_flagged_on_the_card():
    tools, out, _, _, _ = make(search=FakeSearch(GT_COQ))
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": "coq", "amount": "1"}))
    confirm = await confirm_of(out)
    assert rows_of(confirm)["COQ address"] == f"{COQ_ADDR} (matched by symbol — verify)"
    task.cancel()


async def test_kyber_failures_send_no_card():
    def receiver_alice(d):
        return d[:6] + (ALICE,) + d[7:]

    reverting = coq_chain()
    reverting.sim_out = RuntimeError("execution reverted")
    off = coq_chain()
    off.sim_out = OUT * 90 // 100
    cases = [
        (dict(kyber=FakeKyber(no_route=True)), "no route"),
        (dict(kyber=FakeKyber(tamper=receiver_alice)), "wrong recipient"),
        (dict(avax=reverting), "fails on the Sandbox fork"),
        (dict(avax=off), "doesn't match"),
    ]
    for kwargs, fragment in cases:
        tools, out, _, _, _ = make(**kwargs)
        result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1"})
        assert result["is_error"] is True and fragment in text(result), (fragment, text(result))
        assert not out.of_type("confirm")


async def test_erc20_input_without_a_findable_allowance_slot_sends_no_card():
    tools, out, _, _, _ = make(avax=coq_chain(COQ=10**24), saved=[COQ_SAVED])
    result = await tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": "1"})
    assert result["is_error"] is True and "couldn't simulate" in text(result)
    assert not out.of_type("confirm")


async def test_user_slippage_still_applies_to_kyber():
    tools, out, _, _, kyber = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "slippage_percent": "2"}))
    await confirm_of(out)
    assert kyber.builds[-1][2] == 200
    task.cancel()


async def test_builtin_pair_without_a_venue_route_falls_back_to_kyber():
    eth = FakeChain()
    eth.sim_out = OUT
    tools, out, _, _, kyber = make(eth=eth, quoter=FakeQuoter(lambda route, amount: None))
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "WBTC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["to"] == ROUTER and confirm["tx"]["steps"][0]["request"]["chainId"] == 1
    assert "addToken" not in confirm["tx"] and "WBTC address" not in rows_of(confirm)
    assert kyber.routes[0][0] == "ethereum"
    task.cancel()


async def test_builtin_pair_with_a_venue_route_keeps_uniswap():
    def linear(route, amount_in):
        return amount_in * 2358 // 10**12 if route.hops == (Hop(500, 10),) and len(route.currencies) == 2 else None

    tools, out, _, _, kyber = make(quoter=FakeQuoter(linear))
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "USDC", "amount": "1"}))
    assert (await confirm_of(out))["tx"]["steps"][0]["request"]["to"] == UNIVERSAL_ROUTER
    assert kyber.routes == []
    task.cancel()


async def test_send_saved_token_shows_its_address():
    tools, out, _, _, _ = make(avax=coq_chain(COQ=10**24), saved=[COQ_SAVED])
    task = asyncio.create_task(tools.propose_transfer({"token": "COQ", "amount": "1000", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["to"] == COQ_ADDR
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    assert rows_of(confirm)["COQ address"] == COQ_ADDR
    task.cancel()


async def test_balances_list_saved_tokens_and_unknown_prices():
    avax = coq_chain(COQ=10**24)
    avax.prices["COQ"] = None
    tools, out, _, _, _ = make(avax=avax, saved=[COQ_SAVED])
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert {"network": "Avalanche", "symbol": "COQ", "amount": 1_000_000.0, "usdPrice": None} in card["holdings"]
    assert "COQ 1000000 (price unknown)" in text(result)
    assert "Total $32,010.00" in text(result)  # 10 ETH at $3,200 + 10 AVAX at the fake's $1; COQ excluded


async def test_unknown_tokens_are_explained():
    tools, out, _, _, _ = make(avax=FakeChain())
    bad = await tools.propose_swap({"token_in": "AVAX", "token_out": "0x1111111111111111111111111111111111111111", "amount": "1"})
    assert bad["is_error"] is True and text(bad) == "That address isn't a token on Avalanche Sandbox."
    missing = await tools.propose_transfer({"token": "NOPE", "amount": "1", "to": "Alice"})
    assert "with at least $10,000 of liquidity" in text(missing) and "contract address" in text(missing)
    named = await tools.propose_transfer({"token": "NOPE", "amount": "1", "to": "Alice", "network": "avalanche"})
    assert "isn't available on Avalanche" in text(named) and "contract address" in text(named)
    assert not out.of_type("confirm")


async def test_token_found_on_both_networks_asks_which():
    eth = coq_chain(COQ=10**24)
    avax = coq_chain(COQ=10**24)
    tools, out, _, _, _ = make(eth=eth, avax=avax)
    result = await tools.propose_transfer({"token": COQ_ADDR, "amount": "1", "to": "Alice"})
    assert result["is_error"] is True and "wait for their answer" in text(result)
    [choice] = out.of_type("choice")
    assert [o["label"] for o in choice["options"]] == ["Ethereum", "Avalanche"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory agent pytest -q tests/test_kyber_tools.py`
Expected: FAIL with `TypeError: WalletContext.__init__() got an unexpected keyword argument 'tokens'` (and `WalletTools ... unexpected keyword argument 'kyber'`).

- [ ] **Step 3: Implement in `agent/lazyagent/tools.py`**

Keep every edit to the hunks below. The parallel branch adds a tool to `TOOL_NAMES` and `build_mcp_server`; don't touch those lines except the two tool descriptions shown in 3h.

3a. Imports. Change `from dataclasses import dataclass, field` to `from dataclasses import dataclass, field, replace`. Add `from .custom_tokens import ADDRESS, MIN_RESERVE_USD, Search, discover, merge` after `from .chain import Chain`. Add `from .kyber import Kyber, kyber_plan` before the `from .networks import ...` line. In the `from .transfers import (...)` list, add `NoRoute,` after `FEE_HEADROOM,` and `token_address_rows,` after `short,`.

3b. Context, constructor, merged networks, and the price-unknown helper (put `_usd` right above `_succeeded`):

```python
def _usd(holding: dict) -> str:
    return "price unknown" if holding["usdPrice"] is None else format_usd(holding["amount"] * holding["usdPrice"])
```

```python
@dataclass
class WalletContext:
    address: str | None = None
    contacts: list[dict] = field(default_factory=list)
    tokens: list[dict] = field(default_factory=list)  # the wallet's saved custom tokens (lw.tokens)
```

In `WalletTools.__init__`, add two keyword parameters after `dexalot: Quotes | None = None,`, and store them first thing in the body:

```python
        kyber: Kyber | None = None,
        search: Search | None = None,
    ):
        self.fund = fund
        self.kyber = kyber
        self.search = search
```

```python
    @property
    def networks(self) -> list[Network]:
        return [merge(n, self.ctx.tokens) for n in NETWORKS if n.key in self.chains]
```

3c. `get_balances`: unknown prices print as such and stay out of the total. Replace the two lines that build `parts.append(...)` and `total = ...` with:

```python
                parts.append(f"{net.name}: " + ", ".join(f"{h['symbol']} {format_units(h['raw'], h['decimals'])} ({_usd(h)})" for h in mine))
        total = sum(h["amount"] * h["usdPrice"] for h in holdings if h["usdPrice"] is not None)
```

3d. `_resolve`: discovery plus clearer not-found errors. Replace the method's body from its docstring down to (and including) the `return err(f"I can only {verb} {self.supported()} on Sandbox.")` line with the code below. The rest of the method, from `if len(cands) == 1:` on, stays as it is.

```python
        """Which network a request runs on — or an error result (after sending a choice card when it's ambiguous)."""
        nets = self.networks
        explicit = args.get("network")
        if explicit:
            named = find_network(str(explicit))
            nets = [n for n in nets if named is not None and n.key == named.key]
            if not nets:
                return err(f"I can use {', '.join(n.name for n in self.networks)} on Sandbox.")
        nets = await self._discover(symbols, nets)
        if explicit:
            net = nets[0]
            missing = [s for s in symbols if find_token(s, net.tokens) is None]
            if missing:
                if ADDRESS.match(missing[0].strip()):
                    return err(f"That address isn't a token on {net.name} Sandbox.")
                return err(
                    f"{missing[0]} isn't available on {net.name} Sandbox, and I couldn't find it with at least "
                    f"${MIN_RESERVE_USD:,} of liquidity. Ask the user for its contract address."
                )
            return net
        cands = candidates(symbols, nets)
        if not cands:
            unknown = next((s for s in symbols if not any(find_token(s, n.tokens) for n in nets)), None)
            if unknown and ADDRESS.match(unknown.strip()):
                # Only the networks that have the request's other tokens were checked.
                where = [n for n in nets if all(find_token(s, n.tokens) for s in symbols if s != unknown)] or nets
                return err(f"That address isn't a token on {' or '.join(n.name for n in where)} Sandbox.")
            if unknown:
                return err(
                    f"I couldn't find {unknown} with at least ${MIN_RESERVE_USD:,} of liquidity on Sandbox. "
                    f"I can only {verb} {self.supported()} or a token by its contract address — ask the user for it."
                )
            return err(f"I can only {verb} {self.supported()} on Sandbox.")
```

Add this method right before `_send_choice`:

```python
    async def _discover(self, symbols: list[str], nets: list[Network]) -> list[Network]:
        """Adds tokens the user named that aren't built in or saved (a 0x address, else a symbol search) to each
        network where they're found. Skips a network that lacks a token the user named that exists elsewhere."""
        known = {s for s in symbols if any(find_token(s, n.tokens) for n in nets)}
        out = []
        for net in nets:
            missing = [s for s in symbols if find_token(s, net.tokens) is None]
            if missing and not known.intersection(missing):
                found = [await discover(s, net, self.chains[net.key], self.search) for s in missing]
                if all(found):
                    net = replace(net, tokens=net.tokens + tuple(found))
            out.append(net)
        return out
```

3e. `propose_transfer`: the card shows a custom token's address. Replace the `"rows": [...]` line of its confirm message with:

```python
                    "rows": [
                        {"label": "From", "value": short(self.ctx.address)},
                        *display_rows(token, amount, to, name, price, gas_cost, native_price, network=net.label),
                        *token_address_rows(token),
                    ],
```

3f. Venue choice. In `_uniswap_plan`, change `raise TransferError(f"I couldn't find a Uniswap v4 route ...` to `raise NoRoute(f"I couldn't find a Uniswap v4 route ...` (same message). Add this method right before `_approvals`:

```python
    async def _swap_plan(self, net: Network, tin, tout, amount: int, bps: int, slippage: str | None):
        """The network's venue for built-in pairs it can quote; KyberSwap for custom tokens and everything else."""
        if not (tin.custom or tout.custom):
            try:
                if net.swap_venue == "dexalot":
                    return await self._dexalot_plan(net, tin, tout, amount)
                return await self._uniswap_plan(tin, tout, amount, bps)
            except NoRoute:
                if self.kyber is None:
                    raise
        if self.kyber is None:
            raise TransferError("Swaps for tokens outside the built-in list aren't set up on this Sandbox.")
        return await kyber_plan(self.kyber, self.chains[net.key], net, tin, tout, amount, self.ctx.address, slippage)
```

In `propose_swap`, replace the four-line `if net.swap_venue == "dexalot": ... else: ...` block with:

```python
            steps, rows, hint, exact = await self._swap_plan(net, tin, tout, amount, bps, args.get("slippage_percent"))
```

3g. `addToken` on the swap card. In `propose_swap`, replace everything from `pid, fut = self.proposals.new()` through the closing `)` of `await self.send({...})` with:

```python
        tx = {"title": f"Swap {human_in} → {tout.symbol}", "from": self.ctx.address, "rows": rows(fee_usd), "steps": steps_json}
        if tout.custom:  # the wallet remembers it after the swap succeeds
            tx["addToken"] = {"chainId": net.chain_id, "address": tout.address, "symbol": tout.symbol, "decimals": tout.decimals}
        pid, fut = self.proposals.new()
        await self.send({"type": "confirm", "id": pid, "tx": tx})
```

3h. Tool descriptions in `build_mcp_server`. Change only these strings:

- `propose_transfer` description → `"Propose sending a native coin or any token. Shows a confirmation card and waits for the user to approve or reject; returns the outcome."`
- its `token` property → `{"type": "string", "description": f"Symbol (built in: {t.supported()}; or a token the user bought) or the token's 0x contract address"}`
- `propose_swap` description → `"Propose swapping one token for another (exact input): Uniswap v4 on Ethereum, Dexalot on Avalanche, KyberSwap for any other token or pair. Shows one confirmation card with any approval steps, waits for approve/reject, and returns the amount received."`
- `token_in` → `{"type": "string", "description": f"Token to pay: symbol (built in: {t.supported()}) or 0x contract address"}`
- `token_out` → `{"type": "string", "description": "Token to receive: symbol or 0x contract address (any token, e.g. a memecoin)"}`

- [ ] **Step 4: Run the new and existing tool tests**

Run: `uv run --directory agent pytest -q tests/test_kyber_tools.py tests/test_tools.py tests/test_swap_tools.py tests/test_network_tools.py tests/test_kyber.py tests/test_custom_tokens.py`
Expected: all PASS (12 in `test_kyber_tools.py`). The existing "DOGE" refusal tests still pass: the new message keeps "I can only send/swap ETH, USDC, …".

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/tools.py agent/tests/test_kyber_tools.py
git commit -m "feat(agent): any-token transfers and swaps — discovery, venue fallback to KyberSwap, addToken"
```

---

### Task 6: Session, server and prompt wiring

**Files:**
- Modify: `agent/lazyagent/session.py`, `agent/lazyagent/server.py`, `agent/lazyagent/prompt.py`
- Test: `agent/tests/test_server.py`

**Interfaces:**
- Consumes: `WalletTools(kyber=, search=)`, `WalletContext.tokens` (Task 5); `KyberClient`, `usd_price` (Task 3); `GeckoSearch` (Task 4).
- Produces: `Session(..., dexalot=None, kyber=None, search=None)`; `Session.handle` copies `msg["tokens"]` (or `[]`) into `ctx.tokens` on every `user` message; `create_app(..., kyber=None, search=None)`; `main()` wires the real clients and price sources.

- [ ] **Step 1: Write the failing test**

Append to `agent/tests/test_server.py`:

```python
async def test_session_stores_saved_tokens_and_passes_kyber():
    sent = []

    async def send(m):
        sent.append(m)

    async def factory(tools):
        raise RuntimeError("no claude here")

    coq = {"chainId": 43114, "address": "0x420FcA0121DC28039145009570975747295f2329", "symbol": "COQ", "decimals": 18}
    s = Session(send, FakeChain(), factory, kyber=object(), search=object())
    assert s.tools.kyber is not None and s.tools.search is not None
    await s.handle({**USER, "tokens": [coq]})
    await s._turn
    assert s.ctx.tokens == [coq]
    await s.handle(USER)  # an older wallet build sends no tokens
    await s._turn
    assert s.ctx.tokens == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --directory agent pytest -q tests/test_server.py -k saved_tokens`
Expected: FAIL with `TypeError: Session.__init__() got an unexpected keyword argument 'kyber'`.

- [ ] **Step 3: Implement**

`agent/lazyagent/session.py`: add `from .custom_tokens import Search` after `from .chain import Chain`, and `from .kyber import Kyber` after `from .dexalot import Quotes`. Add `kyber: Kyber | None = None,` and `search: Search | None = None,` after `dexalot: Quotes | None = None,` in `__init__`, and pass them on:

```python
        self.tools = WalletTools(chain, send, self.ctx, self.proposals, approval_timeout, fund, avalanche=avalanche, dexalot=dexalot, kyber=kyber, search=search)
```

In `handle`, after `self.ctx.contacts = ...`:

```python
            self.ctx.tokens = list(msg.get("tokens") or [])
```

`agent/lazyagent/server.py`: imports

```python
from .custom_tokens import GeckoSearch, Search
from .dexalot import Quotes, SandboxQuotes
from .faucet import request_funds
from .kyber import Kyber, KyberClient, usd_price
from .networks import AVALANCHE, ETHEREUM
```

`create_app` gets `kyber: Kyber | None = None,` and `search: Search | None = None,` after `dexalot`, and the session line becomes:

```python
        session = Session(ws.send_json, chain, client_factory, approval_timeout, fund, avalanche=avalanche, dexalot=dexalot, kyber=kyber, search=search)
```

In `main()`, replace the `app = create_app(...)` call with:

```python
    kyber = KyberClient()
    app = create_app(
        RpcChain(settings.rpc_url, custom_price=usd_price(kyber, ETHEREUM)),
        factory,
        settings.allowed_origins,
        fund=fund,
        avalanche=RpcChain(settings.avax_rpc_url, poa=True, custom_price=usd_price(kyber, AVALANCHE)),
        dexalot=SandboxQuotes(settings.faucet_url),
        kyber=kyber,
        search=GeckoSearch(),
    )
```

`agent/lazyagent/prompt.py`: insert one bullet directly after the `- Swaps (...)` bullet:

```
- Any token: propose_swap and propose_transfer also take tokens the app doesn't list, by symbol or 0x contract address ("buy 1 AVAX of COQ" = swap 1 AVAX to COQ). If the user gave a contract address, pass the address, not a symbol. Those swaps go through KyberSwap. If the card says a token was "matched by symbol", tell the user to check its contract address before approving.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --directory agent pytest -q tests/test_server.py tests/test_tools.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/session.py agent/lazyagent/server.py agent/lazyagent/prompt.py agent/tests/test_server.py
git commit -m "feat(agent): wire KyberSwap, GeckoTerminal and saved tokens into the session"
```

---

### Task 7: Fork tests — one memecoin per chain through KyberSwap (COQ on Avalanche, PEPE on Ethereum)

**Files:**
- Test: `agent/tests/test_kyber_swap_fork.py` (create)

**Interfaces:**
- Consumes: `avax_fork_rpc` fixture (conftest, port 8649, Avalanche public RPC or `AVAX_RPC_URL`); `fork_rpc` fixture (conftest, port 8646, `ETH_RPC_URL` from the root `.env`, optional `FORK_BLOCK`; skips without `ETH_RPC_URL`); `KyberClient`, `usd_price`, `NATIVE` (Task 3); `WalletTools(kyber=)`, `WalletContext.tokens` (Task 5); `devsigner.execute_steps`.
- Produces: nothing for later tasks.

This follows the existing fork-test convention: the Avalanche test uses the session-scoped `avax_fork_rpc` fixture (like `test_dexalot_swap_fork.py`), and the Ethereum test uses `fork_rpc` (like `test_swap_fork.py`), so it skips without `ETH_RPC_URL`. Both skip when the KyberSwap API isn't reachable. They need `anvil` and internet access. One token per chain only:

- **Avalanche, COQ:** buy 1 AVAX by contract address, see it in balances with a USD price, then sell half for USDC. This is the ERC-20 path: approve + swap, simulated with the allowance override.
- **Ethereum, PEPE:** buy 0.1 ETH by contract address, then see it in balances with a USD price. That is two live Kyber routes (the buy, and the 1 USDC → PEPE price) and one build. There is no sell: the ERC-20 path is already covered on Avalanche.

No FORK_BLOCK pin is needed. If `FORK_BLOCK` is set to an old block, the Ethereum simulation can be off from Kyber's live quote, and the test will then fail with "doesn't match" or "fails on the Sandbox fork". That is the Review Focus stale-fork case, not a bug.

- [ ] **Step 1: Write the test**

Create `agent/tests/test_kyber_swap_fork.py`:

```python
"""End to end on fresh forks with the real KyberSwap API, one token per chain: COQ on Avalanche (buy by address,
see it in balances, sell it) and PEPE on Ethereum (buy by address, see it in balances). Two live routes on Ethereum."""

import asyncio

import pytest
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.kyber import NATIVE, KyberClient, usd_price
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.tokens import Token, find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.transfers import TransferError

COQ = "0x420FcA0121DC28039145009570975747295f2329"
PEPE = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
USDC = find_token("USDC", AVALANCHE.tokens)


class RecordingKyber(KyberClient):
    def __init__(self):
        super().__init__()
        self.built: list[dict] = []

    async def build(self, network, summary, sender, slippage_bps):
        data = await super().build(network, summary, sender, slippage_bps)
        self.built.append(data)
        return data


async def test_buy_hold_and_sell_a_memecoin_through_kyberswap(avax_fork_rpc):
    kyber = RecordingKyber()
    try:
        await kyber.route("avalanche", NATIVE, COQ, 10**18)
    except TransferError as e:
        pytest.skip(f"KyberSwap API not reachable: {e}")
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    proposals = Proposals()
    seen: list[dict] = []
    balances: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "balances":
            balances.append(msg)
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(avax_fork_rpc, poa=True, custom_price=usd_price(kyber, AVALANCHE))
    ctx = WalletContext(address=account.address)
    tools = WalletTools(FakeChain(), send, ctx, proposals, approval_timeout=120, avalanche=chain, kyber=kyber)

    # Buy by contract address: one Kyber step, received within 5% of the quote.
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ, "amount": "1"})
    text = result["content"][0]["text"]
    assert "Swapped 1 AVAX for" in text, text
    buy = seen[0]["tx"]
    assert [s["label"] for s in buy["steps"]] == ["Swap AVAX → COQ"]
    assert {"label": "COQ address", "value": COQ} in buy["rows"]
    held = await chain.token_balance(Token("COQ", COQ, 18, custom=True), account.address)
    quoted = int(kyber.built[0]["amountOut"])
    assert abs(held - quoted) * 100 <= quoted * 5

    # The wallet saves addToken; with it, balances list COQ with a USD price.
    ctx.tokens = [buy["addToken"]]
    await tools.get_balances({})
    coq = next(h for h in balances[-1]["holdings"] if h["symbol"] == "COQ")
    assert coq["network"] == "Avalanche" and coq["usdPrice"] and coq["usdPrice"] > 0

    # Sell half for USDC: approve + swap, simulated beforehand with an allowance override.
    half = str(held // 2 // 10**18)
    result = await tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": half})
    assert "Swapped" in result["content"][0]["text"], result
    assert [s["label"] for s in seen[1]["tx"]["steps"]] == ["Allow COQ", "Swap COQ → USDC"]
    assert await chain.token_balance(USDC, account.address) > 0


async def test_buy_a_memecoin_through_kyberswap_on_ethereum(fork_rpc):
    kyber = RecordingKyber()
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    proposals = Proposals()
    seen: list[dict] = []
    balances: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "balances":
            balances.append(msg)
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(fork_rpc, custom_price=usd_price(kyber, ETHEREUM))
    ctx = WalletContext(address=account.address)
    tools = WalletTools(chain, send, ctx, proposals, approval_timeout=120, kyber=kyber)

    # Live route 1 (+ build): buy PEPE by contract address.
    result = await tools.propose_swap({"token_in": "ETH", "token_out": PEPE, "amount": "0.1"})
    text = result["content"][0]["text"]
    if "KyberSwap isn't reachable" in text:
        pytest.skip(text)
    assert "Swapped 0.1 ETH for" in text, text
    buy = seen[0]["tx"]
    assert [s["label"] for s in buy["steps"]] == ["Swap ETH → PEPE"]
    assert buy["steps"][0]["request"]["chainId"] == 1
    assert {"label": "PEPE address", "value": PEPE} in buy["rows"]
    held = await chain.token_balance(Token("PEPE", PEPE, 18, custom=True), account.address)
    quoted = int(kyber.built[0]["amountOut"])
    assert abs(held - quoted) * 100 <= quoted * 5

    # Live route 2: the USD price for the balance card (1 USDC → PEPE, inverted).
    ctx.tokens = [buy["addToken"]]
    await tools.get_balances({})
    pepe = next(h for h in balances[-1]["holdings"] if h["symbol"] == "PEPE")
    assert pepe["network"] == "Ethereum" and pepe["usdPrice"] and pepe["usdPrice"] > 0
```

- [ ] **Step 2: Run it**

Run: `uv run --directory agent pytest -q tests/test_kyber_swap_fork.py`
Expected: 2 PASS in about 30 s (1 PASS + 1 SKIP without `ETH_RPC_URL`). Both passed against the live API in prototyping on 2026-10-15. If the Avalanche test fails at the sell step with "couldn't simulate", the token's allowance slot wasn't in the access list. Debug `allowance_override` before you touch the tolerance.

- [ ] **Step 3: Commit**

```bash
git add agent/tests/test_kyber_swap_fork.py
git commit -m "test(agent): KyberSwap fork tests on both chains (COQ on Avalanche, PEPE on Ethereum)"
```

---

### Task 8: Wallet — custom token store (`lw.tokens`)

**Files:**
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/lib/storage.ts`
- Create: `apps/wallet/src/lib/tokens.ts`, `apps/wallet/src/lib/tokens.test.ts`

**Interfaces:**
- Consumes: `readJSON`, `writeJSON`, `KEYS` (storage).
- Produces:
  - `type CustomToken = { chainId: number; address: Address; symbol: string; decimals: number }` (types.ts)
  - `TxDraft.addToken?: CustomToken`
  - `KEYS.tokens = 'lw.tokens'`
  - `savedTokens(wallet: string): CustomToken[]`, `saveToken(wallet: string, token: CustomToken): boolean` (lib/tokens.ts)

- [ ] **Step 1: Write the failing test**

Create `apps/wallet/src/lib/tokens.test.ts`:

```ts
import { afterEach, describe, expect, it } from 'vitest'
import type { CustomToken } from '@/types'
import { KEYS } from './storage'
import { savedTokens, saveToken } from './tokens'

const ME = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'
const OTHER = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'
const COQ: CustomToken = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
const PEPE: CustomToken = { chainId: 1, address: '0x6982508145454Ce325dDbE47a25d4ec3d2311933', symbol: 'PEPE', decimals: 18 }

afterEach(() => localStorage.clear())

describe('custom token store', () => {
  it('adds tokens per wallet, keyed by lowercase address', () => {
    expect(saveToken(ME, COQ)).toBe(true)
    expect(saveToken(ME.toLowerCase(), PEPE)).toBe(true)
    expect(savedTokens(ME)).toEqual([COQ, PEPE])
    expect(Object.keys(JSON.parse(localStorage.getItem(KEYS.tokens)!))).toEqual([ME.toLowerCase()])
  })

  it('dedupes by chain and address, ignoring case', () => {
    saveToken(ME, COQ)
    saveToken(ME, { ...COQ, address: COQ.address.toLowerCase() as CustomToken['address'], symbol: 'coq' })
    expect(savedTokens(ME)).toEqual([COQ])
    saveToken(ME, { ...COQ, chainId: 1 })
    expect(savedTokens(ME)).toHaveLength(2)
  })

  it('keeps wallets apart', () => {
    saveToken(ME, COQ)
    expect(savedTokens(OTHER)).toEqual([])
  })

  it('survives corrupt or unexpected JSON', () => {
    localStorage.setItem(KEYS.tokens, '{not json')
    expect(savedTokens(ME)).toEqual([])
    localStorage.setItem(KEYS.tokens, '[1,2]')
    expect(savedTokens(ME)).toEqual([])
    localStorage.setItem(KEYS.tokens, JSON.stringify({ [ME.toLowerCase()]: 'nope' }))
    expect(savedTokens(ME)).toEqual([])
    expect(saveToken(ME, COQ)).toBe(true)
    expect(savedTokens(ME)).toEqual([COQ])
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter wallet exec vitest run src/lib/tokens.test.ts`
Expected: FAIL. `Failed to resolve import "./tokens"`.

- [ ] **Step 3: Implement**

`apps/wallet/src/types.ts`: add after the `BalanceChange` line

```ts
export type CustomToken = { chainId: number; address: Address; symbol: string; decimals: number }
```

and inside `TxDraft`, after `from?: Address`:

```ts
  addToken?: CustomToken // a token this swap buys; saved to lw.tokens once every step succeeded
```

`apps/wallet/src/lib/storage.ts`: add `tokens: 'lw.tokens',` after `tasks: 'lw.tasks',` in `KEYS`.

Create `apps/wallet/src/lib/tokens.ts`:

```ts
import type { CustomToken } from '@/types'
import { KEYS, readJSON, writeJSON } from './storage'

// lw.tokens: { [walletAddressLowercase]: CustomToken[] } — non-secret, add-only.
type Store = Record<string, CustomToken[]>

function load(): Store {
  const s = readJSON<unknown>(KEYS.tokens, {})
  return s && typeof s === 'object' && !Array.isArray(s) ? (s as Store) : {}
}

export function savedTokens(wallet: string): CustomToken[] {
  const list = load()[wallet.toLowerCase()]
  return Array.isArray(list) ? list : []
}

export function saveToken(wallet: string, token: CustomToken): boolean {
  const store = load()
  const key = wallet.toLowerCase()
  const list = savedTokens(key)
  const same = (t: CustomToken) => t.chainId === token.chainId && t.address.toLowerCase() === token.address.toLowerCase()
  if (list.some(same)) return true
  return writeJSON(KEYS.tokens, { ...store, [key]: [...list, token] })
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pnpm --filter wallet exec vitest run src/lib/tokens.test.ts`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/types.ts apps/wallet/src/lib/storage.ts apps/wallet/src/lib/tokens.ts apps/wallet/src/lib/tokens.test.ts
git commit -m "feat(wallet): lw.tokens store for bought custom tokens"
```

---

### Task 9: Wallet — send saved tokens to the agent, save bought tokens after success

**Files:**
- Modify: `apps/wallet/src/chain/executeTx.ts`, `apps/wallet/src/agent/protocol.ts`, `apps/wallet/src/agent/useAgentChat.ts`
- Test: `apps/wallet/src/chain/executeTx.test.ts`, `apps/wallet/src/agent/useAgentChat.test.tsx`

**Interfaces:**
- Consumes: `CustomToken`, `TxDraft.addToken`, `savedTokens`, `saveToken` (Task 8); `StepsOutcome` (executeTx).
- Produces: `tokenToSave(o: StepsOutcome, tx: TxDraft): CustomToken | undefined`. The `ClientMsg` `user` variant gains `tokens: CustomToken[]`.

- [ ] **Step 1: Write the failing tests**

In `apps/wallet/src/chain/executeTx.test.ts`, change the first two imports to

```ts
import type { CustomToken, TxDraft, TxRequest, TxStep } from '@/types'
import { executeSteps, executeTx, progressText, statusPatch, tokenToSave, type TxDeps } from './executeTx'
```

and append:

```ts
describe('tokenToSave', () => {
  const COQ: CustomToken = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
  const tx: TxDraft = { title: 'Swap 1 AVAX → COQ', rows: [], steps: ONE, addToken: COQ }

  it('returns the token only when every step succeeded', async () => {
    const ok: TxDeps = { send: async () => HASH, wait: async () => 'success' }
    expect(tokenToSave(await executeSteps(ONE, ok), tx)).toEqual(COQ)
    const reverted: TxDeps = { send: async () => HASH, wait: async () => 'reverted' }
    expect(tokenToSave(await executeSteps(ONE, reverted), tx)).toBeUndefined()
    const unsent: TxDeps = {
      send: async () => {
        throw new Error('rejected')
      },
      wait: async () => 'success',
    }
    expect(tokenToSave(await executeSteps(ONE, unsent), tx)).toBeUndefined()
  })

  it('returns nothing for cards without addToken', () => {
    expect(tokenToSave({ hashes: [HASH], hash: HASH, status: 'success' }, { ...tx, addToken: undefined })).toBeUndefined()
  })
})
```

In `apps/wallet/src/agent/useAgentChat.test.tsx`, add `import { savedTokens } from '@/lib/tokens'` above `import { useAgentChat } from './useAgentChat'`. Then add this test as the last `it(...)` inside `describe('useAgentChat', ...)`:

```tsx
  it('saves a bought token after the swap succeeds and sends saved tokens with each message', async () => {
    localStorage.clear()
    const { result } = renderHook(() => useAgentChat(OPTIONS), { reactStrictMode: true })
    const live = FakeWebSocket.instances.at(-1)!
    await act(async () => {
      live.open()
      await Promise.resolve()
    })
    const me = OPTIONS.address
    const COQ = { chainId: 43114, address: '0x420FcA0121DC28039145009570975747295f2329', symbol: 'COQ', decimals: 18 }
    const step = { label: 'Swap AVAX → COQ', request: { to: me, value: '1', data: '0x', chainId: 43114 } }
    act(() =>
      live.onmessage?.({
        data: JSON.stringify({ type: 'confirm', id: 'pbuy', tx: { title: 'Swap 1 AVAX → COQ', from: me, rows: [], steps: [step], addToken: COQ } }),
      }),
    )
    expect(savedTokens(me)).toEqual([])
    await act(() => result.current.approve('pbuy'))
    expect(savedTokens(me)).toEqual([COQ])
    act(() => result.current.send('sell all my COQ'))
    expect(JSON.parse(live.sent.at(-1)!)).toMatchObject({ type: 'user', text: 'sell all my COQ', tokens: [COQ] })
  })
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter wallet exec vitest run src/chain/executeTx.test.ts src/agent/useAgentChat.test.tsx`
Expected: FAIL. `tokenToSave is not a function` (or not exported), and `savedTokens(me)` is `[]` after approve.

- [ ] **Step 3: Implement**

`apps/wallet/src/chain/executeTx.ts`: change the type import to `import type { CustomToken, TxDraft, TxRequest, TxStep } from '@/types'` and append:

```ts
/** The token a swap card asked to remember — only once every step succeeded. */
export function tokenToSave(o: StepsOutcome, tx: TxDraft): CustomToken | undefined {
  return o.status === 'success' && !o.error ? tx.addToken : undefined
}
```

`apps/wallet/src/agent/protocol.ts`: add `CustomToken` to the type import, and in the `user` variant add after `contacts: ...`:

```ts
      tokens: CustomToken[]
```

`apps/wallet/src/agent/useAgentChat.ts`:

```ts
import { executeSteps, progressText, statusPatch, tokenToSave } from '@/chain/executeTx'
```

```ts
import { shortAddress, txHash, uid } from '@/lib/format'
import { savedTokens, saveToken } from '@/lib/tokens'
```

In `send`, add `tokens` to the `user` message:

```ts
      contacts: contacts.map((c) => ({ name: c.name, address: c.address })),
      tokens: savedTokens(address),
    })
```

In `approve`, right after `dispatch({ type: 'update', id: statusId, patch: statusPatch(outcome, steps) })`:

```ts
    const bought = tokenToSave(outcome, m.tx)
    if (bought && m.tx.from) saveToken(m.tx.from, bought)
```

- [ ] **Step 4: Run them to verify they pass**

Run: `pnpm --filter wallet exec vitest run src/chain/executeTx.test.ts src/agent/useAgentChat.test.tsx src/lib/tokens.test.ts`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/chain/executeTx.ts apps/wallet/src/chain/executeTx.test.ts apps/wallet/src/agent/protocol.ts apps/wallet/src/agent/useAgentChat.ts apps/wallet/src/agent/useAgentChat.test.tsx
git commit -m "feat(wallet): remember tokens bought via KyberSwap and send them with each message"
```

---

### Task 10: Wallet — "price unknown" and wrapping card values

**Files:**
- Modify: `apps/wallet/src/types.ts`, `apps/wallet/src/chat/cards/BalanceCard.tsx`, `apps/wallet/src/chat/cards/BalanceChangeCard.tsx`, `apps/wallet/src/chat/cards/ConfirmCard.tsx:38`, `apps/wallet/src/mock/fixtures.ts:9`, `apps/wallet/src/mock/agent.ts:69,83`
- Test: `apps/wallet/src/chat/cards/BalanceCard.test.tsx` (create), `apps/wallet/src/chat/cards/BalanceChangeCard.test.tsx`

**Interfaces:**
- Consumes: agent sends `usdPrice: null` for unknown prices (Task 5).
- Produces: `Holding.usdPrice: number | null`, `BalanceChange.usdPrice: number | null`.

- [ ] **Step 1: Write the failing tests**

Create `apps/wallet/src/chat/cards/BalanceCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BalanceCard } from './BalanceCard'

describe('BalanceCard', () => {
  it('shows price unknown and leaves the token out of the total', () => {
    render(
      <BalanceCard
        holdings={[
          { network: 'Avalanche', symbol: 'AVAX', amount: 10, usdPrice: 25 },
          { network: 'Avalanche', symbol: 'COQ', amount: 8e6, usdPrice: null },
        ]}
      />,
    )
    expect(screen.getByText('$250.00', { selector: 'p' })).toBeTruthy()
    expect(screen.getByText('price unknown')).toBeTruthy()
  })
})
```

Add inside `describe('BalanceChangeCard', ...)` in `BalanceChangeCard.test.tsx`:

```tsx
  it('says price unknown instead of $0 for a custom token without a price', () => {
    render(<BalanceChangeCard changes={[{ network: 'Avalanche', symbol: 'COQ', before: 0, after: 8e6, delta: 8e6, usdPrice: null }]} />)
    expect(screen.getByText('Now 8000000 · price unknown')).toBeTruthy()
  })
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter wallet exec vitest run src/chat/cards`
Expected: FAIL with `Unable to find an element with the text: price unknown`: the row shows `$0.00` because `null` coerces to 0.

- [ ] **Step 3: Implement**

`apps/wallet/src/types.ts`: replace the `Holding` and `BalanceChange` lines with:

```ts
// usdPrice null = price unknown (a custom token with no route to USDC) — shown as such, left out of totals.
export type Holding = { symbol: string; amount: number; usdPrice: number | null; network?: string }
export type BalanceChange = { network?: string; symbol: string; before: number; after: number; delta: number; usdPrice: number | null }
```

`BalanceCard.tsx`:

```tsx
  const total = holdings.reduce((sum, h) => sum + (h.usdPrice === null ? 0 : h.amount * h.usdPrice), 0)
```

```tsx
              <span className="block text-xs text-muted-foreground">
                {h.usdPrice === null ? 'price unknown' : formatUsd(h.amount * h.usdPrice)}
              </span>
```

`BalanceChangeCard.tsx`: replace the `Now …` template with

```tsx
                {`Now ${formatAmount(c.after)} · ${c.usdPrice === null ? 'price unknown' : `${sign(c.delta)}${formatUsd(Math.abs(c.delta) * c.usdPrice)}`}`}
```

`ConfirmCard.tsx`: let long values (full contract addresses) wrap at phone width:

```tsx
            <dd className="min-w-0 text-right font-mono wrap-anywhere">{r.value}</dd>
```

The mocks still type-check:
- `mock/fixtures.ts`: `export const PORTFOLIO_USD = HOLDINGS.reduce((sum, h) => sum + h.amount * (h.usdPrice ?? 0), 0)`
- `mock/agent.ts` line 69: `` `${formatAmount(amount)} ${sym} (${formatUsd(amount * (holding.usdPrice ?? 0))})` ``
- `mock/agent.ts` line 83: `const out = ((amount * (a.usdPrice ?? 0)) / (b.usdPrice ?? 1)) * 0.997`

- [ ] **Step 4: Run tests, type-check and lint**

Run: `pnpm --filter wallet test && pnpm --filter wallet build && pnpm --filter wallet lint`
Expected: all Vitest PASS; `tsc -b` + `vite build` succeed; oxlint shows only the 3 existing shadcn `only-export-components` warnings.

- [ ] **Step 5: Commit**

```bash
git add apps/wallet/src/types.ts apps/wallet/src/chat/cards apps/wallet/src/mock/fixtures.ts apps/wallet/src/mock/agent.ts
git commit -m "feat(wallet): show price unknown for custom tokens and wrap long card values"
```

---

### Task 11: Docs and full verification

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-10-15-lazywallet-kyber-custom-tokens-design.md`

**Interfaces:** none.

- [ ] **Step 1: Update `CLAUDE.md`**

Under "Wallet app conventions", after the `uniswap.py` bullet, add:

```markdown
- Any other token or pair goes through KyberSwap (`agent/lazyagent/kyber.py`). Its calldata is untrusted: `verify()` decodes it against the request and it is simulated on the fork (within 5% of the quote) before a card is shown. Change the router address/ABI only with the fork tests (`tests/test_kyber_swap_fork.py`, one token per chain).
- Custom tokens: the wallet keeps bought tokens in `lw.tokens` (non-secret, per wallet) and sends them with every `user` message; the agent stays stateless (`agent/lazyagent/custom_tokens.py`).
```

- [ ] **Step 2: Update the spec**

In the spec header, change `Status: Approved design — not yet implemented` to `Status: Implemented`. Append this section:

```markdown
## 7. Deviations decided while planning

1. Sandbox Kyber slippage is 5000 bps (50%), not 90%: Kyber's `/route/build` rejects `slippageTolerance` > 5000 (HTTP 400). The 5% simulation check still catches amount/decimals bugs.
2. Custom-token price routes 1 USDC → token and inverts it; 1 token → USDC rounds to 0–1 raw unit for memecoins.
3. The card row is `<SYMBOL> address` (e.g. `COQ address`) so two custom tokens on one card don't share a row key.
4. Kyber price impact comes from Kyber's own USD estimates ("unknown" without them) and isn't enforced.
5. Venue fallback uses a `NoRoute` error (Uniswap no route, Dexalot 404); other venue errors surface as before.
6. `Chain` gains `simulate(tx, overrides)` and `storage_keys(to, data)`; ERC-20 simulations find the allowance slot via `eth_createAccessList` and verify it before overriding.
7. Kyber needs a non-default `user-agent` header (403 otherwise); GeckoTerminal search adds `include=base_token`.
8. Confirm-card values wrap (`wrap-anywhere`) so full contract addresses fit on phones.
9. The opt-in fork tests cover both chains with one token each: COQ on Avalanche (buy, balance, sell) and PEPE on Ethereum (buy, balance).
```

- [ ] **Step 3: Full verification**

Run each and read the output:

```bash
pnpm --filter wallet test
pnpm test:py
pnpm build && pnpm lint
```

Expected: every Vitest test passes. pytest passes; with `ETH_RPC_URL` set, both Kyber fork tests in `test_kyber_swap_fork.py` run (without it, the Ethereum ones skip). Build succeeds, and lint has no errors.

- [ ] **Step 4: Manual check (wallet app)**

With `pnpm dev:sandbox`, `pnpm dev:agent`, `pnpm dev` running, and a funded wallet:
1. "Buy 1 AVAX of COQ" → one card, Route `KyberSwap via LFJ`, a `COQ address` row (with "matched by symbol — verify"). Approve → agent reports the amount.
2. "What's my balance" → COQ listed under Avalanche with a USD value.
3. "Send 1000 COQ to Bob" (Bob in the address book) → card with `COQ address`; approve.
4. "Sell all my COQ for USDC" → `Allow COQ` + `Swap COQ → USDC`; approve.
5. "Buy 0.01 ETH of PEPE" on Ethereum → same flow.
6. "Swap 1 ETH to USDC" → still Uniswap v4; "swap 1 AVAX to USDC" → still Dexalot.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-lazywallet-kyber-custom-tokens-design.md
git commit -m "docs: KyberSwap + custom tokens conventions and spec deviations"
```

---

## Merge notes (sibling branch `avax-trending`)

- Expected conflicts are in `agent/lazyagent/tools.py`, in the `build_mcp_server` tool list (our description edits vs their new tool) and possibly `TOOL_NAMES`, and in `prompt.py`, where both add a bullet near the Swaps line. Both are additive, so resolve by keeping both sides.
- If the sibling also adds constructor parameters to `WalletTools`/`Session`/`create_app` (e.g. a trending client), the parameter lists conflict too. Keep both sides' keyword parameters.
- The trending tool hands over a token **contract address**. With this branch, `propose_swap` accepts it directly as `token_out`.
