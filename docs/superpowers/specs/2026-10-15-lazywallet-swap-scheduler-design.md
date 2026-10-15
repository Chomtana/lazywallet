# LazyWallet — On-chain Swap Scheduler Spec

Date: 2026-10-15
Status: Approved design — not yet implemented
Builds on: `2026-10-15-lazywallet-avalanche-dexalot-design.md` (Phase 4, merged to `main`)
Related: `2026-10-15-lazywallet-kyber-custom-tokens-design.md` (not yet implemented; Kyber routes for scheduled swaps come after it merges)

## 1. Goal

Replace the mocked scheduled tasks with real, on-chain scheduled swaps: the user signs once, a `SwapScheduler` contract holds the order, and **anyone** can execute it when it's due and get a gas rebate. We run an executor service; the tab no longer has to stay open. Judges get a deployed contract with a clear, permissionless design.

**Success criteria**
- "Swap 10 USDC to AVAX every minute, 5 times" shows one confirm card (approve + schedule). Approve executes in the browser; the order appears in the Scheduled tasks sheet.
- With `pnpm dev:executor` running, the order executes 5 times about a minute apart, with the browser closed; each run sends ≥ `minOut` to the user and pays the executor its rebate.
- Same on Ethereum (Uniswap v4 route). ETH/AVAX input works (wrapped in the confirm card).
- "Cancel my scheduled swap" stops further runs.
- The scheduler has **the same address on both forks**, deployed deterministically with CREATE2.
- `pnpm test:contracts`, `pnpm --filter wallet test`, `pnpm test:py`, `pnpm build && pnpm lint` pass; an opt-in fork test runs a scheduled swap end to end on each fork.

## 2. Decisions

| Topic | Decision |
|---|---|
| Trigger | Time + recurring: `startTime`, `interval`, `count`. One-shot = `count = 1`. `minOut` per run also acts as a price guard |
| Execution safety | Scheduler + isolated **Swapper** (§3). Arbitrary executor calldata runs only in the Swapper, which never holds user allowances |
| Executor input | A call list `Call[] {target, value, data}` (not a single target), so approve+swap, Permit2 and wrap/unwrap routes all fit |
| Tokens | ERC-20 only in the contract. Native ETH/AVAX is wrapped in the confirm card before scheduling |
| Allowance | User approves the scheduler for `amountIn × count`; tokens move only at each execution |
| Gas | Per-user deposit `gasBalance[user]`. Rebate = `fixedGas × tx.gasprice`, paid in the chain's native token. **Uncapped by choice** (§8) |
| `fixedGas` | Immutable constructor arg, same on both chains (`300_000`) |
| Deployment | Forks only. CREATE2 via Arachnid proxy `0x4e59b44847b379578588920cA78FbF26c0B4956C` — verified present on Ethereum and Avalanche mainnet on 2026-10-15 (69-byte code on both), therefore on both forks; Anvil also injects it by default |
| Toolchain | Foundry + OpenZeppelin (`SafeERC20`, `ReentrancyGuard`), pinned solc |
| Executor | `agent/lazyagent/executor.py`, separate process `pnpm dev:executor`, reuses existing route builders |
| Venues | Uniswap v4 (Ethereum), Dexalot (Avalanche). Kyber after its spec merges |
| Out of scope | Price alerts / conditional triggers, real testnet or mainnet deploy, Kyber/custom tokens, cancel from the tasks sheet, fee-on-transfer tokens, editing orders |

## 3. Contracts (`contracts/`)

### `SwapScheduler`

```solidity
struct Order {
    address owner; address tokenIn; address tokenOut;
    uint256 amountIn;  // per run
    uint256 minOut;    // per run
    uint64 startTime; uint64 interval; uint32 count; uint32 executed;
    uint64 nextTime; bool cancelled;
}
struct Call { address target; uint256 value; bytes data; }
```

- `constructor(uint256 fixedGas)` — stores `fixedGas`; deploys `Swapper` with `CREATE` (address deterministic from the scheduler's).
- `mapping(address => uint256) gasBalance`, `mapping(uint256 => Order) orders`, `uint256 nextId`.
- `depositGas()` payable → `gasBalance[msg.sender] += msg.value`. `withdrawGas(uint256 amount)` → reverts if insufficient, sends native.
- `scheduleSwap(tokenIn, tokenOut, amountIn, minOut, startTime, interval, count)` payable → returns `id`.
  - `msg.value` is added to `gasBalance[msg.sender]`.
  - Requires `tokenIn != tokenOut`, `amountIn > 0`, `count > 0`, `interval > 0` if `count > 1`.
  - `nextTime = startTime`. No token transfer.
  - Emits `SwapScheduled(id, owner, tokenIn, tokenOut, amountIn, minOut, startTime, interval, count)`.
- `cancel(id)` — owner only; sets `cancelled`; emits `SwapCancelled(id)`.
- `executeSwap(id, Call[] calls)` — anyone; `nonReentrant`:
  1. Require not cancelled, `executed < count`, `block.timestamp >= nextTime`.
  2. `executed++`; `nextTime` = first `startTime + k·interval` strictly after `block.timestamp` (no catch-up burst after downtime, no drift); skipped when `interval == 0` (one-shot).
  3. `safeTransferFrom(owner, swapper, amountIn)`.
  4. `before = tokenOut.balanceOf(owner)`; `swapper.run(tokenIn, tokenOut, owner, calls)`; require `balanceOf(owner) - before >= minOut`.
  5. `rebate = fixedGas * tx.gasprice`; require `gasBalance[owner] >= rebate`; deduct; send to `msg.sender`.
  6. Emit `SwapExecuted(id, msg.sender, amountOut, rebate)`.
- View `getOrder(id)` returning the struct (for the executor and wallet).

### `Swapper`

- `run(tokenIn, tokenOut, owner, calls)` — only the scheduler. Executes each `target.call{value}(data)`; any failure reverts the whole execution.
- Afterwards sends its whole `tokenIn` and `tokenOut` balance, and any native balance, to `owner`. Routes that pay the caller (Dexalot taker, Universal Router `MSG_SENDER`) therefore work unchanged, and unspent input returns to the user.
- `receive()` accepts native (for unwrap-then-swap routes, e.g. WAVAX → AVAX → Dexalot).
- Holds no allowances or balances outside a single `run`: a malicious call list can only touch the in-flight `amountIn`, and step 4's `minOut` check bounds that.

### Build settings (address stability)

`foundry.toml` pins `solc_version`, `optimizer = true`, `optimizer_runs`, `evm_version`, and sets `bytecode_hash = "none"`, `cbor_metadata = false`. The salt is a constant (`keccak256("lazywallet.swap-scheduler.v1")`).

## 4. Deployment

- `contracts/script/Deploy.s.sol`: `new SwapScheduler{salt: SALT}(300_000)` (Forge routes salted `new` through the CREATE2 proxy).
- `pnpm dev:sandbox`, after both forks are up: `eth_getCode(SCHEDULER_ADDRESS)` per fork; if empty, run `forge script script/Deploy.s.sol --rpc-url <fork> --broadcast` with an Anvil dev key. Restarts are no-ops.
- `SCHEDULER_ADDRESS` (and the Swapper address) are pinned in `agent/lazyagent/scheduler.py` and `apps/wallet/src/chain/scheduler.ts`. A Forge test asserts `vm.computeCreate2Address(SALT, initCodeHash, 0x4e59…)` equals the pinned constant — any bytecode change fails the test instead of silently moving the contract.
- New script `pnpm test:contracts` → `forge test` in `contracts/`.

## 5. Executor service

`agent/lazyagent/executor.py`, run by `pnpm dev:executor` (separate process).

- Signs with its own Anvil dev account (not the `devsigner` one — no nonce clashes); collects rebates.
- Every 10 s per fork: read `nextId`, `getOrder(i)` for each; due = not cancelled, `executed < count`, `nextTime <= latest block timestamp`.
- For each due order, build `calls` with the **Swapper as taker**:
  - Ethereum: Uniswap v4 from `uniswap.py` — `[tokenIn.approve(Permit2), Permit2.approve(token, UR, amount, exp), UR.execute(...)]`, unwrapping WETH first when the pool's leg is native ETH.
  - Avalanche: Dexalot from `dexalot.py` — fresh quote (quotes expire) with `taker = Swapper`; `[tokenIn.approve(RFQ), RFQ.simpleSwap(...)]`, unwrapping WAVAX first when the leg is native.
  - Output native (e.g. → AVAX): the route ends with a wrap so the Swapper holds WAVAX, which is the order's `tokenOut`.
- `eth_call executeSwap` first; revert (e.g. `minOut` not met at current price) → log and retry next tick. Success → send the transaction.
- Route-builder changes stay minimal: functions that hard-code the user as sender/recipient take a `taker` parameter.

## 6. Agent

New `agent/lazyagent/scheduler.py`: pinned addresses, ABI, calldata builders (the model never builds calldata).

- `propose_scheduled_swap(from, to, amount, start, interval_seconds, count, min_out?)`:
  - Token resolution as `propose_swap`. ETH/AVAX input maps to WETH/WAVAX in the order; ETH/AVAX output maps to WETH/WAVAX `tokenOut` (rows say so).
  - `minOut` = current venue quote × (1 − 5%) unless the user gives a limit ("only if I get at least 30 USDC").
  - `interval_seconds ≥ 60`; `start` defaults to now.
  - Steps: (1) wrap `amount × count` if native input; (2) `approve(scheduler, amount × count)`, skipped if allowance suffices (USDT reset rule reused); (3) `scheduleSwap{value: gasTopUp}` with `gasTopUp = max(0, fixedGas × gasprice × count × 2 − gasBalance)`.
  - Rows: pair, amount per run, schedule ("every 1 min × 5, starting now"), min received per run, gas deposit, scheduler address.
- `list_scheduled_swaps()` — the user's orders on both forks with status and next run.
- `cancel_scheduled_swap(id, chainId)` — one-step confirm card.
- Token registry: add `WAVAX` (`0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7`, 18, AVAX/USD feed) to `AVAX_TOKENS`.
- Prompt: scheduled and recurring swaps are supported; price alerts and conditional actions remain `unsupported_action`.

## 7. Wallet

- New `src/chain/scheduler.ts`: minimal ABI, pinned address, `readOrders(address)` over both forks via viem, and pure `orderStatus(order, now)` (active / done / cancelled, next run).
- `TasksSheet` shows real orders for the active wallet: pair, runs done / total, next run, status. Read-only; cancel happens in chat.
- Remove the DCA scheduled-task mocks from `mock/agent.ts` (and their tests).

## 8. Accepted risks

- **Uncapped rebate:** `tx.gasprice` is executor-chosen; a block producer acting as executor can inflate it and drain the owner's gas deposit. Acceptable on private forks; a real deploy would cap it (e.g. by `block.basefee`).
- `minOut` is fixed for the order's lifetime; a large price move pauses execution until it recovers or the user cancels.
- Fee-on-transfer and rebasing tokens are not supported.
- The standing allowance (`amountIn × count`) is spendable only through `executeSwap` on the user's own orders.

## 9. Testing

- **Forge** (`pnpm test:contracts`), with mock ERC-20s and a mock router:
  - schedule → execute → cancel; time gating; `nextTime` skips missed periods; runs stop at `count`.
  - Reverts: `minOut` not met, insufficient gas balance, not due, cancelled, non-owner cancel.
  - Rebate maths (`vm.txGasPrice`); deposit/withdraw.
  - Leftover `tokenIn`/native swept to owner.
  - Attacks: call list `tokenIn.transferFrom(victim, attacker, x)` reverts (Swapper has no allowance); reentering `executeSwap` from a call reverts; calling `Swapper.run` directly reverts.
  - CREATE2 address equals the pinned constant.
- **pytest:** `scheduler.py` calldata, steps and rows (native input, allowance skip, gas top-up); executor due-order selection and call building with fixtures.
- **Opt-in fork test** (existing fork-test convention): per fork, deploy, schedule a 2-run order, `evm_increaseTime`, run one executor tick each time; assert both runs paid ≥ `minOut` through real Uniswap v4 (Ethereum) and Dexalot (Avalanche) routes, and the executor received its rebate.
- **Vitest:** `orderStatus` and order parsing in `chain/scheduler.ts`.
- **Manual:** the success-criteria script in the wallet app.
