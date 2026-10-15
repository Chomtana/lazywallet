# LazyWallet — Phase 3 (Uniswap v4 Swaps) Spec

Date: 2026-10-15
Status: Draft — awaiting user review
Builds on: `2026-10-14-lazywallet-mvp-agent-design.md` (Phase 2)

## 1. Goal

Let the user swap tokens by voice or text — "Swap 100 USDC to ETH" — through Uniswap v4 on the Sandbox fork, with the same agent-proposes / browser-signs model as transfers.

**Success criteria**
- "Swap 1 ETH to USDC", "Swap 1000 USDC to ETH" and "Swap 500 USDC to WBTC" each produce one confirm card; one Approve executes all steps in the browser and the agent reports the actual amount received.
- ERC-20 inputs add only the approval steps actually needed (sized to the swap amount). Sized approvals are consumed by the swap, so a later swap normally needs them again; any allowance that is still sufficient and unexpired is skipped.
- "Swap 1 ETH to WETH" / "WETH to ETH" wrap/unwrap via the WETH contract.
- Invalid or unroutable swaps never produce a card.
- `pnpm test`, `pnpm test:py` pass; fork integration tests execute real v4 swaps.

## 2. Decisions

| Topic | Decision |
|---|---|
| Swap type | Exact input only |
| Tokens | Existing six: ETH, USDC, USDT, DAI, WBTC, WETH |
| Pools | Uniswap v4, hookless (`hooks = 0`) only, native ETH = `address(0)` |
| Routing | Quote every fee tier (100/1, 500/10, 3000/60, 10000/200) for the direct pair; when neither side is ETH also every 2-hop route via ETH (16 tier combos); pick the highest output |
| ETH↔WETH | WETH `deposit()` / `withdraw(uint256)`, no pool |
| Quotes | V4Quoter `quoteExactInputSingle` / `quoteExactInput` via `eth_call` on the fork |
| Slippage | Default 1%; user may set 0.01–5% ("with 0.5% slippage") |
| Price impact | Compare effective rate with a quote for 1/1000 of the amount on the same route; refuse above 15% |
| Approvals | One card listing steps; approvals sized to the swap amount; Permit2 approval expires in 30 min; skip approvals already sufficient; USDT gets an approve-to-0 step when lowering/raising a nonzero allowance |
| Deadline | Fork block timestamp + 20 min |
| Result | Agent reports actual received amount from output-token balance before/after |

### Verified mainnet addresses
| Contract | Address |
|---|---|
| PoolManager | `0x000000000004444c5dc75cB358380D2e3dE08A90` |
| UniversalRouter (v4) | `0x66a9893cc07d91d95644aedd05d03f95e1dba8af` |
| Permit2 | `0x000000000022D473030F116dDEE9F6B43aC78BA3` |
| V4Quoter | `0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203` |
| StateView | `0x7ffe42c4a5deea5b0fec41c94c136cf115597227` |

## 3. Calldata recipe (verified on a fork)

- `UniversalRouter.execute(bytes commands, bytes[] inputs, uint256 deadline)` (selector `0x3593564c`), `commands = 0x10` (V4_SWAP), `inputs[0] = abi.encode(bytes actions, bytes[] params)`.
- PoolKey `(address currency0, address currency1, uint24 fee, int24 tickSpacing, address hooks)`, `currency0 < currency1`; `zeroForOne = (currencyIn == currency0)`.
- Single hop: `actions = 0x06 0x0c 0x0f` (SWAP_EXACT_IN_SINGLE, SETTLE_ALL, TAKE_ALL); params:
  1. `abi.encode((PoolKey, bool zeroForOne, uint128 amountIn, uint128 amountOutMinimum, bytes hookData=""))`
  2. `abi.encode(address currencyIn, uint256 amountIn)`
  3. `abi.encode(address currencyOut, uint256 amountOutMinimum)`
- Multi hop: `actions = 0x07 0x0c 0x0f`; first param `abi.encode((address currencyIn, PathKey[] path, uint128 amountIn, uint128 amountOutMinimum))`, `PathKey = (address intermediateCurrency, uint24 fee, int24 tickSpacing, address hooks, bytes hookData)`.
- Native ETH input: tx `value = amountIn`, no approvals.
- ERC-20 input: `token.approve(Permit2, amount)` then `Permit2.approve(address token, address spender=UniversalRouter, uint160 amount, uint48 expiration)`; check with `Permit2.allowance(owner, token, spender) → (uint160 amount, uint48 expiration, uint48 nonce)` and `token.allowance(owner, Permit2)`.

## 4. Agent

### 4.1 Tool `propose_swap`
Input: `token_in`, `token_out` (symbols), `amount` (decimal string, whole tokens of `token_in`), optional `slippage_percent` (string).

Flow: validate tokens/amount/slippage → balance check → route search (or wrap/unwrap) → price-impact check → build steps (approvals as needed + swap) → gas-reserve check across steps → send `confirm` → await `tx_result` → on success read output balance delta and report it.

Errors (no card): unsupported token, same token both sides, invalid amount, slippage out of range, insufficient balance, insufficient ETH for gas (2× reserve of fixed per-step gas: approve 60k, Permit2 approve 60k, wrap/unwrap 60k, 1-hop swap 170k, 2-hop 220k), no route, price impact > 15%, chain unreachable.

### 4.2 Confirm card rows
From · You pay · Expected · Minimum received · Route (e.g. `ETH → USDC · Uniswap v4 0.05%`, `USDC → ETH → WBTC · v4 0.05% / 0.05%`) · Price impact · Network fee · Network. Title `Swap 1000 USDC → ETH`.

### 4.3 Prompt
Swaps → `propose_swap` (pass slippage only if the user said one). `unsupported_action` now covers bridging, scheduling, alerts, dApps.

## 5. Protocol change (all confirm cards)

`confirm.tx.request` is replaced by `confirm.tx.steps: [{label, request}]` (transfers send one step labelled "Send"). `tx_result` gains `hashes: string[]` and `failed_step?: number` (0-based); `hash` stays = last hash. Browser:
- Executes steps sequentially; each waits for its receipt before the next.
- Status card shows `Step 2 of 3: Allow Uniswap router…` while running; final success/failed as before; failure text names the step.
- Stops on first error/revert.

## 6. Code layout

```
agent/lazyagent/uniswap.py     addresses, PoolKey/poolId, encoders (swap, approvals, wrap), route search over a Quoter
agent/lazyagent/swaps.py       pure swap validation, slippage parsing, card rows, gas reserve
agent/lazyagent/chain.py       + call(to, data) -> bytes, block_timestamp(), erc20_allowance, permit2_allowance
agent/lazyagent/tools.py       + propose_swap; transfers emit steps
apps/wallet/src/chain/executeTx.ts   + executeSteps(steps, deps, onProgress)
apps/wallet/src/agent/*        steps-aware protocol, status progress
```

## 7. Testing
- Encoders: byte-exact vectors from the research scripts (poolId, single-hop and 2-hop V4_SWAP inputs, Permit2 approve, WETH deposit/withdraw).
- Route search and validation with a fake quoter/chain.
- Fork integration: 1 ETH→USDC, 1000 USDC→ETH (with approvals executed), 500 USDC→WBTC via ETH, ETH→WETH — each signed by a test key, asserting balances move and output ≥ minimum.
- Vitest: `executeSteps` order, stop-on-failure, progress callback; reducer/hook with steps.
- Live: demo script swap prompt; browser walkthrough of ETH→USDC and USDC→ETH.

## 8. Out of scope
Exact-output swaps, hook pools, v2/v3 pools, tokens beyond the six, limit/scheduled orders, unlimited approvals, MEV protection.
