# On-chain Swap Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mocked scheduled tasks with a permissionless on-chain `SwapScheduler` (same CREATE2 address on both Sandbox forks), an executor service that runs due orders, agent tools to schedule/list/cancel, and a Scheduled tasks sheet that reads real orders.

**Architecture:** `contracts/` (Foundry) holds `SwapScheduler` + an isolated `Swapper` that runs executor-supplied call lists with no standing allowances. `pnpm dev:sandbox` deploys it deterministically through the Arachnid CREATE2 proxy. The agent's `scheduler.py` builds all calldata (the model never does); `executor.py` reuses the Uniswap v4 / Dexalot builders with the Swapper as taker. The wallet reads orders with viem.

**Tech Stack:** Foundry (forge 1.x, solc 0.8.37, OpenZeppelin v5.7.0, forge-std v1.17.0), Python 3.12 + web3.py + eth_abi (uv), React + viem + TanStack Query, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-lazywallet-swap-scheduler-design.md`

## Global Constraints

- Trigger = `startTime` + `interval` + `count`; one-shot = `count = 1` (`interval` stored as 0). `minOut` is per run.
- Contract tokens are ERC-20 only; ETH/AVAX is wrapped (WETH / WAVAX) in the confirm card before scheduling; native output is delivered as WETH / WAVAX.
- Rebate = `fixedGas × tx.gasprice`, **uncapped by choice**, paid in the chain's native token; `fixedGas = 300_000`, immutable constructor arg.
- Deployment: forks only, CREATE2 via `0x4e59b44847b379578588920cA78FbF26c0B4956C`, salt `keccak256("lazywallet.swap-scheduler.v1")`. Same address on Ethereum (1) and Avalanche (43114).
- `foundry.toml` pins `solc_version`, `optimizer`, `optimizer_runs`, `evm_version`, and sets `bytecode_hash = "none"`, `cbor_metadata = false`.
- Scheduler address is pinned in exactly four places: `contracts/src/Deployment.sol`, `anvil/lazysandbox/scheduler.py`, `agent/lazyagent/scheduler.py`, `apps/wallet/src/chain/scheduler.ts`. Tests enforce they agree with the bytecode.
- The model never builds calldata. Every transaction goes through an Approve/Reject confirm card with `tx.steps`; every request carries `chainId`.
- Executor: separate process `pnpm dev:executor`, its own Anvil dev account #9 (not `devsigner`'s), polls every 10 s, simulates before sending.
- Agent `minOut` default = current venue quote × (1 − 5%); `interval ≥ 60 s`; gas top-up = `max(0, fixedGas × gasprice × count × 2 − gasBalance)`.
- Venues: Uniswap v4 (Ethereum), Dexalot (Avalanche). Kyber / custom tokens, price alerts, testnet/mainnet deploy, cancel from the sheet: out of scope.
- Uniswap v4 and Dexalot recipe changes only with a fork test (CLAUDE.md).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Sandbox restarted without the executor restarting** (fresh forks, scheduler not yet deployed, or a fork down) → executor logs and keeps polling; never crashes. Pinned by `test_tick_survives_unreachable_chain` (Task 6).
2. **One bad order (allowance revoked, tokens spent, price below `minOut`, gas deposit empty)** → executor skips it and still runs the other due orders on the same tick. Pinned by `test_tick_skips_failing_order_and_runs_the_next` (Task 6).
3. **User lacks `amount × count` of the input token, or enough native for wrap + gas deposit + fees** → clear error, no card. Pinned by `test_schedule_rejects_when_total_exceeds_balance` and `test_schedule_rejects_when_native_cannot_cover_wrap_and_deposit` (Task 4).
4. **Nonsense schedules (interval < 60 s, count 0 or > 100, negative delay, ETH→WETH which is the same token once wrapped)** → plain-language error. Pinned by `test_parse_schedule_*` (Task 3) and `test_schedule_rejects_same_token_once_wrapped` (Task 4).
5. **One fork unreachable while the wallet opens the Scheduled tasks sheet** → orders from the other fork still show. Pinned by `readOrders` using `Promise.allSettled` and `test('mergeSettled keeps fulfilled chains')` (Task 7).

---

## File Structure

| File | Responsibility |
|---|---|
| `contracts/foundry.toml`, `contracts/.gitignore`, `contracts/lib/*` (submodules) | Foundry project, pinned build settings |
| `contracts/src/Swapper.sol` | `Call` struct; runs the executor's call list; sweeps leftovers to the owner |
| `contracts/src/SwapScheduler.sol` | Orders, gas deposits, time gating, `minOut` check, rebate |
| `contracts/src/Deployment.sol` | `SALT`, `FIXED_GAS`, pinned `SCHEDULER` / `SWAPPER` |
| `contracts/script/Deploy.s.sol` | Salted CREATE2 deploy |
| `contracts/test/SwapScheduler.t.sol`, `contracts/test/Deployment.t.sol` | Unit + attack tests, pinned-address test |
| `anvil/lazysandbox/scheduler.py` | `ensure_scheduler(rpc)` — idempotent deploy on sandbox start |
| `anvil/lazysandbox/sandbox.py` | Calls `ensure_scheduler` for both forks |
| `agent/lazyagent/scheduler.py` | Pinned addresses, calldata, `Order` reads, schedule steps/rows, labels |
| `agent/lazyagent/tools.py` | `propose_scheduled_swap`, `list_scheduled_swaps`, `cancel_scheduled_swap` |
| `agent/lazyagent/uniswap.py` | `encode_swap(..., wrap_output=False)` |
| `agent/lazyagent/executor.py` | Call builders, `Executor.tick()`, `main()` |
| `apps/wallet/src/chain/scheduler.ts` | ABI, pinned address, `readOrders`, `orderStatus`, `durationLabel` |
| `apps/wallet/src/chain/useScheduledOrders.ts` | TanStack Query hook (10 s refetch) |
| `apps/wallet/src/components/TasksSheet.tsx`, `src/routes/WalletPage.tsx` | Real orders in the sheet and the top-bar badge |

---

### Task 1: Foundry project with `Swapper` and `SwapScheduler`

**Files:**
- Create: `contracts/foundry.toml`, `contracts/.gitignore`, `contracts/src/Swapper.sol`, `contracts/src/SwapScheduler.sol`
- Create (submodules): `contracts/lib/forge-std`, `contracts/lib/openzeppelin-contracts`
- Test: `contracts/test/SwapScheduler.t.sol`
- Modify: `package.json` (add `test:contracts`)

**Interfaces:**
- Produces (Solidity, used by Tasks 2–6):
  - `struct Call { address target; uint256 value; bytes data; }` (file-level in `Swapper.sol`)
  - `SwapScheduler(uint256 fixedGas)`; `fixedGas()`, `swapper()`, `nextId()`, `gasBalance(address)`
  - `depositGas() payable`, `withdrawGas(uint256)`
  - `scheduleSwap(address tokenIn, address tokenOut, uint256 amountIn, uint256 minOut, uint64 startTime, uint64 interval, uint32 count) payable returns (uint256 id)`
  - `cancel(uint256 id)`, `getOrder(uint256 id) returns (Order)` with `Order = (owner, tokenIn, tokenOut, amountIn, minOut, startTime, interval, count, executed, nextTime, cancelled)` = ABI `(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)`
  - `executeSwap(uint256 id, Call[] calls) returns (uint256 amountOut)` — selector signature `executeSwap(uint256,(address,uint256,bytes)[])`

- [ ] **Step 1: Scaffold the Foundry project**

```bash
mkdir -p contracts/src contracts/test contracts/script
cd contracts
forge install foundry-rs/forge-std@v1.17.0 OpenZeppelin/openzeppelin-contracts@v5.7.0
```

Check that `git status` shows `.gitmodules` with `contracts/lib/forge-std` and `contracts/lib/openzeppelin-contracts`. If `forge install` refuses because `contracts/` has no `foundry.toml`, write Step 2's files first and re-run.

`contracts/foundry.toml`:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.37"
evm_version = "cancun"
optimizer = true
optimizer_runs = 200
# Address stability: the CREATE2 address depends on the exact bytecode, so no metadata hash / CBOR tail.
bytecode_hash = "none"
cbor_metadata = false
remappings = [
  "@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/",
  "forge-std/=lib/forge-std/src/",
]
```

`contracts/.gitignore`:

```
out/
cache/
broadcast/
```

Root `package.json` scripts — add:

```json
"test:contracts": "forge test --root contracts",
```

- [ ] **Step 2: Write the failing tests**

`contracts/test/SwapScheduler.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

import {Test} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SwapScheduler} from "../src/SwapScheduler.sol";
import {Swapper, Call} from "../src/Swapper.sol";

contract MockERC20 is ERC20 {
    constructor(string memory name) ERC20(name, name) {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

/// Pulls tokenIn from the caller (needs an allowance) and mints amountOut of tokenOut to `to`.
contract MockRouter {
    function swap(MockERC20 tokenIn, MockERC20 tokenOut, uint256 amountIn, uint256 amountOut, address to) external {
        tokenIn.transferFrom(msg.sender, address(this), amountIn);
        tokenOut.mint(to, amountOut);
    }
}

contract Reenter {
    SwapScheduler immutable scheduler;

    constructor(SwapScheduler s) {
        scheduler = s;
    }

    function go(uint256 id) external {
        scheduler.executeSwap(id, new Call[](0));
    }
}

contract SwapSchedulerTest is Test {
    uint256 constant FIXED_GAS = 300_000;
    uint256 constant GAS_PRICE = 1 gwei;
    uint256 constant AMOUNT = 100e18;
    uint256 constant OUT = 50e18;

    SwapScheduler scheduler;
    MockERC20 tin;
    MockERC20 tout;
    MockRouter router;
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    address executor = makeAddr("executor");

    function setUp() public {
        vm.warp(1_000_000);
        scheduler = new SwapScheduler(FIXED_GAS);
        tin = new MockERC20("IN");
        tout = new MockERC20("OUT");
        router = new MockRouter();
        tin.mint(alice, 1_000e18);
        vm.prank(alice);
        tin.approve(address(scheduler), type(uint256).max);
        vm.deal(alice, 1 ether);
        vm.txGasPrice(GAS_PRICE);
    }

    function _schedule(uint64 start, uint64 interval, uint32 count, uint256 minOut) internal returns (uint256) {
        vm.prank(alice);
        return scheduler.scheduleSwap{value: 0.1 ether}(address(tin), address(tout), AMOUNT, minOut, start, interval, count);
    }

    function _swapCalls(uint256 amountIn, uint256 amountOut, address to) internal view returns (Call[] memory calls) {
        calls = new Call[](2);
        calls[0] = Call(address(tin), 0, abi.encodeCall(IERC20.approve, (address(router), amountIn)));
        calls[1] = Call(address(router), 0, abi.encodeCall(MockRouter.swap, (tin, tout, amountIn, amountOut, to)));
    }

    function _execute(uint256 id, Call[] memory calls) internal returns (uint256) {
        vm.prank(executor);
        return scheduler.executeSwap(id, calls);
    }

    function _now() internal view returns (uint64) {
        return uint64(block.timestamp);
    }

    function test_scheduleStoresOrderAndEmits() public {
        vm.expectEmit(true, true, false, true);
        emit SwapScheduler.SwapScheduled(0, alice, address(tin), address(tout), AMOUNT, OUT, _now(), 60, 3);
        uint256 id = _schedule(_now(), 60, 3, OUT);
        assertEq(id, 0);
        assertEq(scheduler.nextId(), 1);
        assertEq(scheduler.gasBalance(alice), 0.1 ether);
        SwapScheduler.Order memory o = scheduler.getOrder(id);
        assertEq(o.owner, alice);
        assertEq(o.amountIn, AMOUNT);
        assertEq(o.nextTime, _now());
        assertEq(o.count, 3);
        assertEq(tin.balanceOf(alice), 1_000e18); // nothing moves at schedule time
    }

    function test_scheduleRejectsInvalidOrders() public {
        vm.startPrank(alice);
        vm.expectRevert(SwapScheduler.InvalidOrder.selector);
        scheduler.scheduleSwap(address(tin), address(tin), AMOUNT, OUT, _now(), 0, 1);
        vm.expectRevert(SwapScheduler.InvalidOrder.selector);
        scheduler.scheduleSwap(address(tin), address(tout), 0, OUT, _now(), 0, 1);
        vm.expectRevert(SwapScheduler.InvalidOrder.selector);
        scheduler.scheduleSwap(address(tin), address(tout), AMOUNT, OUT, _now(), 60, 0);
        vm.expectRevert(SwapScheduler.InvalidOrder.selector);
        scheduler.scheduleSwap(address(tin), address(tout), AMOUNT, OUT, _now(), 0, 2);
        vm.stopPrank();
    }

    function test_executePaysOwnerAndRebatesExecutor() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        uint256 out = _execute(id, _swapCalls(AMOUNT, OUT, alice));
        assertEq(out, OUT);
        assertEq(tout.balanceOf(alice), OUT);
        assertEq(tin.balanceOf(alice), 900e18);
        assertEq(executor.balance, FIXED_GAS * GAS_PRICE);
        assertEq(scheduler.gasBalance(alice), 0.1 ether - FIXED_GAS * GAS_PRICE);
        assertEq(scheduler.getOrder(id).executed, 1);
    }

    function test_outputPaidToSwapperIsSweptToOwner() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        address swapper = address(scheduler.swapper());
        _execute(id, _swapCalls(AMOUNT, OUT, swapper));
        assertEq(tout.balanceOf(alice), OUT);
        assertEq(tout.balanceOf(swapper), 0);
    }

    function test_unspentInputReturnsToOwner() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        _execute(id, _swapCalls(AMOUNT / 2, OUT, alice));
        assertEq(tin.balanceOf(alice), 950e18);
    }

    function test_nativeLeftInSwapperGoesToOwner() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        vm.deal(address(scheduler.swapper()), 1 ether);
        _execute(id, _swapCalls(AMOUNT, OUT, alice));
        assertEq(alice.balance, 1 ether - 0.1 ether + 1 ether);
    }

    function test_revertsWhenOutputBelowMinimum() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        Call[] memory calls = _swapCalls(AMOUNT, OUT - 1, alice);
        vm.prank(executor);
        vm.expectRevert(abi.encodeWithSelector(SwapScheduler.InsufficientOutput.selector, OUT - 1, OUT));
        scheduler.executeSwap(id, calls);
    }

    function test_revertsBeforeStartTime() public {
        uint256 id = _schedule(_now() + 100, 0, 1, OUT);
        Call[] memory calls = _swapCalls(AMOUNT, OUT, alice);
        vm.prank(executor);
        vm.expectRevert(SwapScheduler.NotDue.selector);
        scheduler.executeSwap(id, calls);
    }

    function test_recurringSkipsMissedPeriodsWithoutCatchUp() public {
        uint64 start = _now();
        uint256 id = _schedule(start, 60, 5, OUT);
        _execute(id, _swapCalls(AMOUNT, OUT, alice));
        assertEq(scheduler.getOrder(id).nextTime, start + 60);
        vm.warp(start + 250); // executor was down for 4 periods
        _execute(id, _swapCalls(AMOUNT, OUT, alice));
        assertEq(scheduler.getOrder(id).nextTime, start + 300);
        Call[] memory calls = _swapCalls(AMOUNT, OUT, alice);
        vm.prank(executor);
        vm.expectRevert(SwapScheduler.NotDue.selector);
        scheduler.executeSwap(id, calls);
    }

    function test_stopsAfterCount() public {
        uint256 id = _schedule(_now(), 60, 2, OUT);
        _execute(id, _swapCalls(AMOUNT, OUT, alice));
        vm.warp(block.timestamp + 60);
        _execute(id, _swapCalls(AMOUNT, OUT, alice));
        vm.warp(block.timestamp + 60);
        Call[] memory calls = _swapCalls(AMOUNT, OUT, alice);
        vm.prank(executor);
        vm.expectRevert(SwapScheduler.OrderClosed.selector);
        scheduler.executeSwap(id, calls);
    }

    function test_cancelStopsExecution() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        vm.prank(alice);
        scheduler.cancel(id);
        assertTrue(scheduler.getOrder(id).cancelled);
        Call[] memory calls = _swapCalls(AMOUNT, OUT, alice);
        vm.prank(executor);
        vm.expectRevert(SwapScheduler.OrderClosed.selector);
        scheduler.executeSwap(id, calls);
    }

    function test_onlyOwnerCanCancel() public {
        uint256 id = _schedule(_now(), 0, 1, OUT);
        vm.prank(bob);
        vm.expectRevert(SwapScheduler.NotOwner.selector);
        scheduler.cancel(id);
    }

    function test_revertsWhenGasDepositTooLow() public {
        vm.prank(alice);
        uint256 id = scheduler.scheduleSwap(address(tin), address(tout), AMOUNT, OUT, _now(), 0, 1);
        Call[] memory calls = _swapCalls(AMOUNT, OUT, alice);
        vm.prank(executor);
        vm.expectRevert(abi.encodeWithSelector(SwapScheduler.InsufficientGas.selector, 0, FIXED_GAS * GAS_PRICE));
        scheduler.executeSwap(id, calls);
    }

    function test_depositAndWithdrawGas() public {
        vm.prank(alice);
        scheduler.depositGas{value: 0.5 ether}();
        assertEq(scheduler.gasBalance(alice), 0.5 ether);
        vm.prank(alice);
        scheduler.withdrawGas(0.2 ether);
        assertEq(scheduler.gasBalance(alice), 0.3 ether);
        assertEq(alice.balance, 0.7 ether);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(SwapScheduler.InsufficientGas.selector, 0.3 ether, 1 ether));
        scheduler.withdrawGas(1 ether);
    }

    function test_cannotSpendAnotherUsersAllowance() public {
        tin.mint(bob, 1_000e18);
        vm.prank(bob);
        tin.approve(address(scheduler), type(uint256).max);
        uint256 id = _schedule(_now(), 0, 1, 0);
        Call[] memory calls = new Call[](1);
        calls[0] = Call(address(tin), 0, abi.encodeCall(IERC20.transferFrom, (bob, executor, 1_000e18)));
        vm.prank(executor);
        vm.expectRevert(); // Swapper has no allowance from bob
        scheduler.executeSwap(id, calls);
        assertEq(tin.balanceOf(bob), 1_000e18);
    }

    function test_reentrancyIsBlocked() public {
        Reenter r = new Reenter(scheduler);
        uint256 first = _schedule(_now(), 0, 1, 0);
        uint256 second = _schedule(_now(), 0, 1, 0);
        Call[] memory calls = new Call[](1);
        calls[0] = Call(address(r), 0, abi.encodeCall(Reenter.go, (second)));
        vm.prank(executor);
        vm.expectRevert();
        scheduler.executeSwap(first, calls);
    }

    function test_swapperOnlyAcceptsScheduler() public {
        Swapper s = scheduler.swapper();
        vm.expectRevert(Swapper.OnlyScheduler.selector);
        s.run(address(tin), address(tout), alice, new Call[](0));
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm test:contracts`
Expected: compile error — `SwapScheduler.sol` / `Swapper.sol` not found.

- [ ] **Step 4: Implement `Swapper`**

`contracts/src/Swapper.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";

struct Call {
    address target;
    uint256 value;
    bytes data;
}

/// Runs an executor's arbitrary call list on one order's in-flight tokens, then returns everything to the owner.
/// It holds no allowances or balances between runs, so arbitrary calldata can't reach anyone's approvals.
contract Swapper {
    using SafeERC20 for IERC20;

    address public immutable scheduler;

    error OnlyScheduler();
    error CallFailed(uint256 index, bytes reason);

    constructor() {
        scheduler = msg.sender;
    }

    receive() external payable {}

    function run(address tokenIn, address tokenOut, address owner, Call[] calldata calls) external {
        if (msg.sender != scheduler) revert OnlyScheduler();
        for (uint256 i; i < calls.length; ++i) {
            (bool ok, bytes memory reason) = calls[i].target.call{value: calls[i].value}(calls[i].data);
            if (!ok) revert CallFailed(i, reason);
        }
        _sweep(IERC20(tokenIn), owner);
        _sweep(IERC20(tokenOut), owner);
        uint256 native = address(this).balance;
        if (native > 0) Address.sendValue(payable(owner), native);
    }

    function _sweep(IERC20 token, address to) private {
        uint256 balance = token.balanceOf(address(this));
        if (balance > 0) token.safeTransfer(to, balance);
    }
}
```

- [ ] **Step 5: Implement `SwapScheduler`**

`contracts/src/SwapScheduler.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Swapper, Call} from "./Swapper.sol";

/// Recurring swap orders anyone can execute. Users approve this contract and deposit gas; an executor supplies the
/// route as a call list (run by the isolated Swapper) and earns `fixedGas * tx.gasprice` per run.
contract SwapScheduler is ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct Order {
        address owner;
        address tokenIn;
        address tokenOut;
        uint256 amountIn; // per run
        uint256 minOut; // per run
        uint64 startTime;
        uint64 interval; // 0 for one-shot orders
        uint32 count;
        uint32 executed;
        uint64 nextTime;
        bool cancelled;
    }

    uint256 public immutable fixedGas;
    Swapper public immutable swapper;
    uint256 public nextId;
    mapping(address => uint256) public gasBalance;
    mapping(uint256 => Order) private _orders;

    event GasDeposited(address indexed user, uint256 amount);
    event GasWithdrawn(address indexed user, uint256 amount);
    event SwapScheduled(
        uint256 indexed id,
        address indexed owner,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minOut,
        uint64 startTime,
        uint64 interval,
        uint32 count
    );
    event SwapCancelled(uint256 indexed id);
    event SwapExecuted(uint256 indexed id, address indexed executor, uint256 amountOut, uint256 rebate);

    error InvalidOrder();
    error NotOwner();
    error NotDue();
    error OrderClosed();
    error InsufficientOutput(uint256 amountOut, uint256 minOut);
    error InsufficientGas(uint256 balance, uint256 needed);

    constructor(uint256 fixedGas_) {
        fixedGas = fixedGas_;
        swapper = new Swapper();
    }

    function depositGas() external payable {
        _deposit();
    }

    function withdrawGas(uint256 amount) external nonReentrant {
        uint256 balance = gasBalance[msg.sender];
        if (amount > balance) revert InsufficientGas(balance, amount);
        gasBalance[msg.sender] = balance - amount;
        emit GasWithdrawn(msg.sender, amount);
        Address.sendValue(payable(msg.sender), amount);
    }

    function scheduleSwap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minOut,
        uint64 startTime,
        uint64 interval,
        uint32 count
    ) external payable returns (uint256 id) {
        if (
            tokenIn == tokenOut || tokenIn == address(0) || tokenOut == address(0) || amountIn == 0 || count == 0
                || (count > 1 && interval == 0)
        ) revert InvalidOrder();
        if (msg.value > 0) _deposit();
        id = nextId++;
        _orders[id] = Order({
            owner: msg.sender,
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            amountIn: amountIn,
            minOut: minOut,
            startTime: startTime,
            interval: interval,
            count: count,
            executed: 0,
            nextTime: startTime,
            cancelled: false
        });
        emit SwapScheduled(id, msg.sender, tokenIn, tokenOut, amountIn, minOut, startTime, interval, count);
    }

    function cancel(uint256 id) external {
        Order storage o = _orders[id];
        if (o.owner != msg.sender) revert NotOwner();
        if (o.cancelled || o.executed >= o.count) revert OrderClosed();
        o.cancelled = true;
        emit SwapCancelled(id);
    }

    function getOrder(uint256 id) external view returns (Order memory) {
        return _orders[id];
    }

    function executeSwap(uint256 id, Call[] calldata calls) external nonReentrant returns (uint256 amountOut) {
        Order storage o = _orders[id];
        if (o.owner == address(0) || o.cancelled || o.executed >= o.count) revert OrderClosed();
        if (block.timestamp < o.nextTime) revert NotDue();

        address owner = o.owner;
        uint256 rebate = fixedGas * tx.gasprice;
        uint256 balance = gasBalance[owner];
        if (balance < rebate) revert InsufficientGas(balance, rebate);
        gasBalance[owner] = balance - rebate;

        o.executed += 1;
        if (o.interval > 0) {
            // Next period boundary strictly after now: no catch-up burst after downtime, no drift.
            uint256 periods = (block.timestamp - o.startTime) / o.interval + 1;
            o.nextTime = uint64(o.startTime + periods * o.interval);
        }

        IERC20 tokenOut = IERC20(o.tokenOut);
        IERC20(o.tokenIn).safeTransferFrom(owner, address(swapper), o.amountIn);
        uint256 before = tokenOut.balanceOf(owner);
        swapper.run(o.tokenIn, o.tokenOut, owner, calls);
        amountOut = tokenOut.balanceOf(owner) - before;
        if (amountOut < o.minOut) revert InsufficientOutput(amountOut, o.minOut);

        emit SwapExecuted(id, msg.sender, amountOut, rebate);
        Address.sendValue(payable(msg.sender), rebate);
    }

    function _deposit() private {
        gasBalance[msg.sender] += msg.value;
        emit GasDeposited(msg.sender, msg.value);
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm test:contracts`
Expected: all 17 tests in `SwapSchedulerTest` PASS.

- [ ] **Step 7: Commit**

```bash
git add .gitmodules contracts/foundry.toml contracts/.gitignore contracts/lib contracts/src contracts/test package.json
git commit -m "feat(contracts): SwapScheduler with isolated Swapper for permissionless scheduled swaps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Deterministic deployment + sandbox auto-deploy

**Files:**
- Create: `contracts/src/Deployment.sol`, `contracts/script/Deploy.s.sol`, `contracts/test/Deployment.t.sol`
- Create: `anvil/lazysandbox/scheduler.py`
- Modify: `anvil/lazysandbox/sandbox.py` (after both `wait_for_rpc` calls)
- Test: `anvil/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `SwapScheduler(uint256)`, `swapper()` (Task 1).
- Produces: `Deployment.SALT`, `Deployment.FIXED_GAS = 300_000`, `Deployment.SCHEDULER`, `Deployment.SWAPPER` (checksummed literals that Tasks 3 and 7 copy); `script/Deploy.s.sol:Deploy`; Python `lazysandbox.scheduler.ensure_scheduler(rpc_url: str, run=subprocess.run) -> bool`, `deploy_command(rpc_url: str) -> list[str]`, `SCHEDULER: str`, `SWAPPER: str`.

- [ ] **Step 1: Write `Deployment.sol` with zero addresses and the failing pinned-address test**

`contracts/src/Deployment.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

/// Deterministic deployment constants. SCHEDULER/SWAPPER are also pinned in anvil/lazysandbox/scheduler.py,
/// agent/lazyagent/scheduler.py and apps/wallet/src/chain/scheduler.ts — any bytecode change means re-pinning all four
/// (test/Deployment.t.sol and agent/tests/test_scheduler.py fail until you do).
library Deployment {
    bytes32 internal constant SALT = keccak256("lazywallet.swap-scheduler.v1");
    uint256 internal constant FIXED_GAS = 300_000;
    address internal constant SCHEDULER = address(0);
    address internal constant SWAPPER = address(0);
}
```

`contracts/test/Deployment.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

import {Test} from "forge-std/Test.sol";
import {SwapScheduler} from "../src/SwapScheduler.sol";
import {Deployment} from "../src/Deployment.sol";

contract DeploymentTest is Test {
    function test_pinnedAddressesMatchBytecode() public pure {
        bytes32 initCodeHash = keccak256(abi.encodePacked(type(SwapScheduler).creationCode, abi.encode(Deployment.FIXED_GAS)));
        assertEq(vm.computeCreate2Address(Deployment.SALT, initCodeHash, CREATE2_FACTORY), Deployment.SCHEDULER, "re-pin SCHEDULER");
        // The scheduler creates its Swapper in the constructor; a contract's first CREATE uses nonce 1.
        assertEq(vm.computeCreateAddress(Deployment.SCHEDULER, 1), Deployment.SWAPPER, "re-pin SWAPPER");
    }
}
```

- [ ] **Step 2: Run it to get the real addresses**

Run: `pnpm test:contracts --match-test test_pinnedAddressesMatchBytecode -vv`
Expected: FAIL `re-pin SCHEDULER: 0x<computed> != 0x0000…`. Copy `0x<computed>` into `SCHEDULER`, run again, then copy the address the SWAPPER assertion prints into `SWAPPER`. Run a third time: PASS. Use the checksummed form (solc rejects non-checksummed literals and prints the correct one).

- [ ] **Step 3: Write the deploy script**

`contracts/script/Deploy.s.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

import {Script, console} from "forge-std/Script.sol";
import {SwapScheduler} from "../src/SwapScheduler.sol";
import {Deployment} from "../src/Deployment.sol";

/// forge routes a salted `new` through the CREATE2 proxy 0x4e59…956C, present on both forks.
contract Deploy is Script {
    function run() external returns (SwapScheduler scheduler) {
        vm.startBroadcast();
        scheduler = new SwapScheduler{salt: Deployment.SALT}(Deployment.FIXED_GAS);
        vm.stopBroadcast();
        require(address(scheduler) == Deployment.SCHEDULER, "deployed address differs from Deployment.SCHEDULER");
        console.log("SwapScheduler", address(scheduler));
        console.log("Swapper", address(scheduler.swapper()));
    }
}
```

- [ ] **Step 4: Write the failing sandbox test**

`anvil/tests/test_scheduler.py` — runs the real `forge script` against a bare local Anvil (Anvil injects the CREATE2 proxy by default, no fork needed):

```python
import re
import subprocess
import time

import pytest
from web3 import HTTPProvider, Web3

from lazysandbox.rpc import ROOT
from lazysandbox.scheduler import SCHEDULER, SWAPPER, deploy_command, ensure_scheduler

PORT = 8661


@pytest.fixture
def bare_anvil():
    proc = subprocess.Popen(["anvil", "--port", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{PORT}"
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            w3.eth.chain_id
            break
        except Exception:
            time.sleep(0.2)
    try:
        yield url
    finally:
        proc.terminate()
        proc.wait()


def test_deploy_command_broadcasts_the_deploy_script():
    cmd = deploy_command("http://x")
    assert cmd[:3] == ["forge", "script", "script/Deploy.s.sol:Deploy"]
    assert "--broadcast" in cmd and cmd[cmd.index("--rpc-url") + 1] == "http://x"


def test_ensure_scheduler_deploys_once_at_the_pinned_address(bare_anvil):
    w3 = Web3(HTTPProvider(bare_anvil))
    assert ensure_scheduler(bare_anvil) is True
    assert w3.eth.get_code(SCHEDULER) and w3.eth.get_code(SWAPPER)
    assert ensure_scheduler(bare_anvil) is False  # idempotent across sandbox restarts


def test_pinned_addresses_match_deployment_sol():
    sol = (ROOT / "contracts/src/Deployment.sol").read_text()
    assert re.search(r"SCHEDULER = (0x[0-9a-fA-F]{40})", sol).group(1) == SCHEDULER
    assert re.search(r"SWAPPER = (0x[0-9a-fA-F]{40})", sol).group(1) == SWAPPER
```

Run: `uv run --directory anvil pytest tests/test_scheduler.py -q`
Expected: FAIL — `ModuleNotFoundError: lazysandbox.scheduler`.

- [ ] **Step 5: Implement `anvil/lazysandbox/scheduler.py`**

Use the two addresses from Step 2.

```python
"""Deterministic SwapScheduler deployment (contracts/) on the Sandbox forks."""

import subprocess

from web3 import HTTPProvider, Web3

from .rpc import ROOT

# = contracts/src/Deployment.sol (CREATE2, identical on both forks)
SCHEDULER = Web3.to_checksum_address("<Deployment.SCHEDULER from Step 2>")
SWAPPER = Web3.to_checksum_address("<Deployment.SWAPPER from Step 2>")
# Anvil dev account #0. CREATE2 makes the address independent of who deploys.
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
CONTRACTS = ROOT / "contracts"


def deploy_command(rpc_url: str) -> list[str]:
    return ["forge", "script", "script/Deploy.s.sol:Deploy", "--rpc-url", rpc_url, "--broadcast", "--private-key", DEPLOYER_KEY]


def ensure_scheduler(rpc_url: str, run=subprocess.run) -> bool:
    """Deploy the scheduler unless it's already there. True if this call deployed it."""
    w3 = Web3(HTTPProvider(rpc_url))
    if w3.eth.get_code(SCHEDULER):
        return False
    run(deploy_command(rpc_url), cwd=CONTRACTS, check=True, capture_output=True)
    if not w3.eth.get_code(SCHEDULER):
        raise RuntimeError(f"SwapScheduler isn't at {SCHEDULER} after deploying — re-pin it (contracts/src/Deployment.sol).")
    return True
```

(Replace both `<…>` strings with the literal addresses; the plan can't know them before the bytecode exists.)

- [ ] **Step 6: Call it from `sandbox.py`**

In `anvil/lazysandbox/sandbox.py`, add `from .scheduler import SCHEDULER, ensure_scheduler` and, right after `wait_for_rpc(avax_rpc, 120, AVAX_CHAIN_ID)`:

```python
        for name, url in (("Ethereum", rpc), ("Avalanche", avax_rpc)):
            try:
                verb = "deployed" if ensure_scheduler(url) else "already at"
                print(f"SwapScheduler {verb} {SCHEDULER} on {name}", flush=True)
            except Exception as e:
                print(f"SwapScheduler deploy FAILED on {name} — scheduled swaps disabled there: {e}", flush=True)
```

- [ ] **Step 7: Run the tests**

Run: `pnpm test:contracts && uv run --directory anvil pytest -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add contracts/src/Deployment.sol contracts/script contracts/test/Deployment.t.sol anvil/lazysandbox/scheduler.py anvil/lazysandbox/sandbox.py anvil/tests/test_scheduler.py
git commit -m "feat(sandbox): deploy SwapScheduler at a pinned CREATE2 address on both forks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Agent `scheduler.py` — calldata, orders, steps, labels

**Files:**
- Create: `agent/lazyagent/scheduler.py`
- Modify: `agent/lazyagent/tokens.py` (add WAVAX)
- Test: `agent/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `Step` (`swaps.py`), `Token`/`find_token` (`tokens.py`), `Network` (`networks.py`), `_call`, `encode_erc20_approve`, `WETH_DEPOSIT` (`uniswap.py`), `TransferError`, `format_units`, `short` (`transfers.py`), `display_units` (`swaps.py`), pinned addresses (Task 2).
- Produces (used by Tasks 4–6):
  - `SCHEDULER: str`, `SWAPPER: str`, `FIXED_GAS = 300_000`, `MIN_INTERVAL_S = 60`, `MAX_COUNT = 100`, `MIN_OUT_DISCOUNT_BPS = 500`, `GAS: dict[str, int]`
  - `Call = tuple[str, int, str]` (target, value, hex data)
  - `@dataclass(frozen=True) Order(id, owner, token_in, token_out, amount_in, min_out, start_time, interval, count, executed, next_time, cancelled)` with `.active: bool` and `.due(now: int) -> bool`
  - `encode_schedule(token_in, token_out, amount_in, min_out, start, interval, count) -> str`, `encode_cancel(order_id) -> str`, `encode_execute(order_id, calls: list[Call]) -> str`, `encode_get_order(order_id) -> str`, `encode_gas_balance(owner) -> str`, `NEXT_ID: str`, `decode_order(order_id, data: bytes) -> Order`
  - `async read_orders(chain, owner: str | None = None) -> list[Order]`, `async gas_balance(chain, owner) -> int`
  - `gas_top_up(gas_price, count, balance) -> int`, `parse_schedule(interval, count, delay) -> tuple[int, int, int]`
  - `wrapped_token(net) -> Token`, `order_token(token, net) -> Token`, `routing_token(token, net) -> Token`, `token_at(net, address) -> Token | None`
  - `duration_label(seconds) -> str`, `schedule_label(interval, count, delay) -> str`, `describe_order(order, net, now) -> str`
  - `schedule_steps(tin, tout, net, amount_in, min_out, start, interval, count, allowance, top_up) -> list[Step]`, `schedule_rows(sender, tin, tout, net, amount_in, min_out, label, top_up) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_scheduler.py`:

```python
import re

import pytest
from eth_abi import decode, encode
from fakes import FakeChain
from web3 import Web3

from lazyagent.config import ROOT
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.scheduler import (
    FIXED_GAS,
    NEXT_ID,
    SCHEDULER,
    SWAPPER,
    Order,
    decode_order,
    describe_order,
    duration_label,
    encode_execute,
    encode_get_order,
    encode_schedule,
    gas_top_up,
    order_token,
    parse_schedule,
    read_orders,
    routing_token,
    schedule_label,
    schedule_rows,
    schedule_steps,
    token_at,
    wrapped_token,
)
from lazyagent.tokens import find_token
from lazyagent.transfers import TransferError

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
USDC = find_token("USDC", ETHEREUM.tokens)
WETH = find_token("WETH", ETHEREUM.tokens)


def order_bytes(owner=ME, token_in=USDC.address, token_out=WETH.address, executed=0, count=3, next_time=1_700_000_000, cancelled=False):
    return encode([ORDER_ABI], [(owner, token_in, token_out, 10 * 10**6, 4 * 10**15, 1_700_000_000, 60, count, executed, next_time, cancelled)])


def test_pinned_addresses_agree_everywhere():
    sol = (ROOT / "contracts/src/Deployment.sol").read_text()
    for name, value in (("SCHEDULER", SCHEDULER), ("SWAPPER", SWAPPER)):
        pinned = re.search(rf"{name} = (0x[0-9a-fA-F]{{40}})", sol).group(1)
        assert value == pinned
        assert f'"{pinned}"' in (ROOT / "anvil/lazysandbox/scheduler.py").read_text()
    assert f"'{re.search(r'SCHEDULER = (0x[0-9a-fA-F]{40})', sol).group(1)}'" in (ROOT / "apps/wallet/src/chain/scheduler.ts").read_text()


def test_decode_order_round_trip_and_state():
    o = decode_order(7, order_bytes(executed=1))
    assert o.id == 7 and o.owner == ME and o.token_out == WETH.address
    assert o.amount_in == 10 * 10**6 and o.interval == 60 and o.count == 3 and o.executed == 1
    assert o.active and o.due(1_700_000_000) and not o.due(1_699_999_999)
    assert not decode_order(1, order_bytes(executed=3)).active
    assert not decode_order(1, order_bytes(cancelled=True)).active


def test_encode_schedule_and_execute():
    data = encode_schedule(USDC.address, WETH.address, 10, 4, 100, 60, 3)
    assert data[:10] == "0x" + Web3.keccak(text="scheduleSwap(address,address,uint256,uint256,uint64,uint64,uint32)")[:4].hex()
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(data[10:]))
    assert args[2:] == (10, 4, 100, 60, 3)
    ex = encode_execute(5, [(USDC.address, 0, "0x1234"), (WETH.address, 9, "0x")])
    assert ex[:10] == "0x" + Web3.keccak(text="executeSwap(uint256,(address,uint256,bytes)[])")[:4].hex()
    oid, calls = decode(["uint256", "(address,uint256,bytes)[]"], bytes.fromhex(ex[10:]))
    assert oid == 5 and calls[0][2] == bytes.fromhex("1234") and calls[1][1] == 9


async def test_read_orders_filters_by_owner():
    chain = FakeChain()
    chain.call_responses[NEXT_ID[:10]] = (2).to_bytes(32, "big")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    assert [o.id for o in await read_orders(chain, ME)] == [0, 1]
    assert await read_orders(chain, "0x000000000000000000000000000000000000dEaD") == []


async def test_read_orders_empty_when_not_deployed():
    chain = FakeChain()
    chain.call_responses[NEXT_ID[:10]] = b""  # eth_call to an address with no code returns 0x
    assert await read_orders(chain) == []


def test_gas_top_up_covers_twice_the_rebates_minus_existing_balance():
    assert gas_top_up(10**9, 3, 0) == FIXED_GAS * 10**9 * 3 * 2
    assert gas_top_up(10**9, 3, 10**18) == 0


def test_parse_schedule_defaults_to_one_shot_now():
    assert parse_schedule(None, None, None) == (0, 1, 0)
    assert parse_schedule("60", "5", "0") == (60, 5, 0)
    assert parse_schedule(3600, 1, 30) == (0, 1, 30)  # interval ignored for one run


@pytest.mark.parametrize("interval,count,delay", [(30, 2, 0), (60, 0, 0), (60, 101, 0), (60, 2, -1), ("soon", 2, 0)])
def test_parse_schedule_rejects_nonsense(interval, count, delay):
    with pytest.raises(TransferError):
        parse_schedule(interval, count, delay)


def test_native_maps_to_wrapped_and_back():
    assert wrapped_token(ETHEREUM).symbol == "WETH" and wrapped_token(AVALANCHE).symbol == "WAVAX"
    assert order_token(ETHEREUM.native, ETHEREUM).symbol == "WETH"
    assert order_token(USDC, ETHEREUM) is USDC
    assert routing_token(WETH, ETHEREUM) is ETHEREUM.native
    assert token_at(AVALANCHE, wrapped_token(AVALANCHE).address.lower()).symbol == "WAVAX"
    assert token_at(ETHEREUM, "0x000000000000000000000000000000000000dEaD") is None


def test_labels():
    assert duration_label(45) == "45s" and duration_label(60) == "1 min" and duration_label(7200) == "2 h" and duration_label(86400 * 7) == "7 d"
    assert schedule_label(60, 5, 0) == "every 1 min × 5, starting now"
    assert schedule_label(0, 1, 120) == "once, in 2 min"
    o = decode_order(3, order_bytes(executed=1, next_time=1_700_000_030))
    assert describe_order(o, ETHEREUM, 1_700_000_000) == "#3: 10 USDC → WETH, every 1 min × 3, 1/3 done, next run in 30s"


def test_schedule_steps_wrap_approve_schedule_for_native_input():
    steps = schedule_steps(ETHEREUM.native, USDC, ETHEREUM, 10**17, 300 * 10**6, 100, 60, 3, allowance=0, top_up=5)
    assert [s.label for s in steps] == ["Wrap ETH → WETH", "Allow WETH", "Schedule swap"]
    assert steps[0].request == {"to": WETH.address, "value": str(3 * 10**17), "data": "0xd0e30db0"}
    assert steps[2].request["to"] == SCHEDULER and steps[2].request["value"] == "5"
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(steps[2].request["data"][10:]))
    assert args[0] == WETH.address and args[1] == USDC.address


def test_schedule_steps_skip_approval_and_reset_usdt():
    assert [s.label for s in schedule_steps(USDC, ETHEREUM.native, ETHEREUM, 10, 1, 0, 0, 1, allowance=10, top_up=0)] == ["Schedule swap"]
    usdt = find_token("USDT", ETHEREUM.tokens)
    assert [s.label for s in schedule_steps(usdt, WETH, ETHEREUM, 10, 1, 0, 0, 1, allowance=1, top_up=0)] == ["Reset USDT allowance", "Allow USDT", "Schedule swap"]


def test_schedule_rows_mention_wrapped_output_and_contract():
    rows = {r["label"]: r["value"] for r in schedule_rows(ME, USDC, ETHEREUM.native, ETHEREUM, 10 * 10**6, 4 * 10**15, "every 1 min × 3, starting now", 0)}
    assert rows["Each run"] == "10 USDC → WETH"
    assert rows["Min received per run"] == "0.004 WETH"
    assert rows["You receive"] == "WETH (wrapped ETH)"
    assert rows["Gas deposit"] == "already covered"
    assert rows["Contract"].startswith(SCHEDULER[:6])
```

Run: `uv run --directory agent pytest tests/test_scheduler.py -q`
Expected: FAIL — `ModuleNotFoundError: lazyagent.scheduler`.

- [ ] **Step 2: Add WAVAX to the Avalanche registry**

In `agent/lazyagent/tokens.py`, append to `AVAX_TOKENS`:

```python
    Token("WAVAX", "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", 18, price_feed=AVAX_USD_FEED),
```

- [ ] **Step 3: Implement `agent/lazyagent/scheduler.py`**

Use the addresses pinned in Task 2.

```python
"""SwapScheduler (contracts/): pinned addresses, calldata, order reads and confirm-card steps.
The model never builds calldata — this module does."""

from dataclasses import dataclass

from eth_abi import decode
from web3 import Web3

from .networks import Network
from .swaps import Step, display_units
from .tokens import Token, find_token
from .transfers import TransferError, format_units, short
from .uniswap import WETH_DEPOSIT, _call, encode_erc20_approve

# = contracts/src/Deployment.sol (CREATE2, identical on both forks)
SCHEDULER = Web3.to_checksum_address("<Deployment.SCHEDULER>")
SWAPPER = Web3.to_checksum_address("<Deployment.SWAPPER>")
FIXED_GAS = 300_000
MIN_INTERVAL_S = 60
MAX_COUNT = 100
MIN_OUT_DISCOUNT_BPS = 500
MAX_LISTED = 200
GAS = {"wrap": 60_000, "approve": 60_000, "schedule": 220_000, "cancel": 60_000}
WRAPPED = {1: "WETH", 43114: "WAVAX"}
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
CALL_ABI = "(address,uint256,bytes)"
NEXT_ID = _call("nextId()", [], [])

Call = tuple[str, int, str]  # target, value, hex calldata


@dataclass(frozen=True)
class Order:
    id: int
    owner: str
    token_in: str
    token_out: str
    amount_in: int
    min_out: int
    start_time: int
    interval: int
    count: int
    executed: int
    next_time: int
    cancelled: bool

    @property
    def active(self) -> bool:
        return not self.cancelled and self.executed < self.count

    def due(self, now: int) -> bool:
        return self.active and self.next_time <= now


def encode_schedule(token_in: str, token_out: str, amount_in: int, min_out: int, start: int, interval: int, count: int) -> str:
    types = ["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"]
    return _call(f"scheduleSwap({','.join(types)})", types, [token_in, token_out, amount_in, min_out, start, interval, count])


def encode_cancel(order_id: int) -> str:
    return _call("cancel(uint256)", ["uint256"], [order_id])


def encode_execute(order_id: int, calls: list[Call]) -> str:
    values = [(Web3.to_checksum_address(t), v, bytes.fromhex(d.removeprefix("0x"))) for t, v, d in calls]
    return _call(f"executeSwap(uint256,{CALL_ABI}[])", ["uint256", f"{CALL_ABI}[]"], [order_id, values])


def encode_get_order(order_id: int) -> str:
    return _call("getOrder(uint256)", ["uint256"], [order_id])


def encode_gas_balance(owner: str) -> str:
    return _call("gasBalance(address)", ["address"], [owner])


def decode_order(order_id: int, data: bytes) -> Order:
    v = decode([ORDER_ABI], data)[0]
    return Order(order_id, *(Web3.to_checksum_address(a) for a in v[:3]), *v[3:])


def _uint(data: bytes) -> int:
    return int.from_bytes(data[:32], "big")


async def read_orders(chain, owner: str | None = None) -> list[Order]:
    """The newest MAX_LISTED orders, optionally only `owner`'s. No contract on this chain → no orders."""
    n = _uint(await chain.call(SCHEDULER, NEXT_ID))
    orders = [decode_order(i, await chain.call(SCHEDULER, encode_get_order(i))) for i in range(max(0, n - MAX_LISTED), n)]
    return [o for o in orders if owner is None or o.owner.lower() == owner.lower()]


async def gas_balance(chain, owner: str) -> int:
    return _uint(await chain.call(SCHEDULER, encode_gas_balance(owner)))


def gas_top_up(gas_price: int, count: int, balance: int) -> int:
    return max(0, FIXED_GAS * gas_price * count * 2 - balance)


def parse_schedule(interval, count, delay) -> tuple[int, int, int]:
    """(interval seconds, run count, start delay seconds). One run → interval 0."""
    try:
        n = int(count) if count not in (None, "") else 1
        every = int(interval) if interval not in (None, "") else 0
        wait = int(delay) if delay not in (None, "") else 0
    except (TypeError, ValueError) as e:
        raise TransferError("The schedule needs whole numbers: seconds between runs and how many runs.") from e
    if not 1 <= n <= MAX_COUNT:
        raise TransferError(f"Pick between 1 and {MAX_COUNT} runs.")
    if n > 1 and every < MIN_INTERVAL_S:
        raise TransferError("Runs need to be at least 1 minute apart.")
    if wait < 0:
        raise TransferError("The start can't be in the past.")
    return (every if n > 1 else 0), n, wait


def wrapped_token(net: Network) -> Token:
    return find_token(WRAPPED[net.chain_id], net.tokens)


def order_token(token: Token, net: Network) -> Token:
    """The ERC-20 an order holds: native ETH/AVAX becomes WETH/WAVAX."""
    return wrapped_token(net) if token.address is None else token


def routing_token(token: Token, net: Network) -> Token:
    """The token venues quote: WETH/WAVAX legs route through native pools/pairs."""
    return net.native if token.symbol == WRAPPED[net.chain_id] else token


def token_at(net: Network, address: str) -> Token | None:
    return next((t for t in net.tokens if t.address and t.address.lower() == address.lower()), None)


def duration_label(seconds: int) -> str:
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{round(seconds / size)} {unit}"
    return f"{seconds}s"


def schedule_label(interval: int, count: int, delay: int) -> str:
    when = "now" if delay <= 0 else f"in {duration_label(delay)}"
    if count == 1:
        return f"once, {when}"
    return f"every {duration_label(interval)} × {count}, starting {when}"


def describe_order(order: Order, net: Network, now: int) -> str:
    tin, tout = token_at(net, order.token_in), token_at(net, order.token_out)
    pay = f"{format_units(order.amount_in, tin.decimals)} {tin.symbol}" if tin else f"{order.amount_in} of {short(order.token_in)}"
    get = tout.symbol if tout else short(order.token_out)
    plan = f"every {duration_label(order.interval)} × {order.count}" if order.count > 1 else "once"
    if order.cancelled:
        status = "cancelled"
    elif not order.active:
        status = "finished"
    elif order.next_time <= now:
        status = "due now"
    else:
        status = f"next run in {duration_label(order.next_time - now)}"
    return f"#{order.id}: {pay} → {get}, {plan}, {order.executed}/{order.count} done, {status}"


def _tx(to: str, data: str, value: int = 0) -> dict:
    return {"to": to, "value": str(value), "data": data}


def schedule_steps(
    tin: Token, tout: Token, net: Network, amount_in: int, min_out: int, start: int, interval: int, count: int, allowance: int, top_up: int
) -> list[Step]:
    pay, get = order_token(tin, net), order_token(tout, net)
    total = amount_in * count
    steps: list[Step] = []
    if tin.address is None:
        steps.append(Step(f"Wrap {tin.symbol} → {pay.symbol}", _tx(pay.address, WETH_DEPOSIT, total), GAS["wrap"]))
    if allowance < total:
        if pay.symbol == "USDT" and allowance > 0:
            # USDT reverts when changing one nonzero allowance to another.
            steps.append(Step("Reset USDT allowance", _tx(pay.address, encode_erc20_approve(SCHEDULER, 0)), GAS["approve"]))
        steps.append(Step(f"Allow {pay.symbol}", _tx(pay.address, encode_erc20_approve(SCHEDULER, total)), GAS["approve"]))
    data = encode_schedule(pay.address, get.address, amount_in, min_out, start, interval, count)
    steps.append(Step("Schedule swap", _tx(SCHEDULER, data, top_up), GAS["schedule"]))
    return steps


def schedule_rows(sender: str, tin: Token, tout: Token, net: Network, amount_in: int, min_out: int, label: str, top_up: int) -> list[dict]:
    get = order_token(tout, net)
    rows = [
        {"label": "From", "value": short(sender)},
        {"label": "Each run", "value": f"{format_units(amount_in, tin.decimals)} {tin.symbol} → {get.symbol}"},
        {"label": "Schedule", "value": label},
        {"label": "Min received per run", "value": f"{display_units(min_out, get.decimals)} {get.symbol}"},
    ]
    if tout.address is None:
        rows.append({"label": "You receive", "value": f"{get.symbol} (wrapped {tout.symbol})"})
    rows += [
        {"label": "Gas deposit", "value": f"{format_units(top_up, 18)} {net.native.symbol}" if top_up else "already covered"},
        {"label": "Executed by", "value": "Anyone — the LazyWallet executor on Sandbox"},
        {"label": "Contract", "value": short(SCHEDULER)},
        {"label": "Network", "value": net.label},
    ]
    return rows
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory agent pytest -q`
Expected: `test_scheduler.py` passes except `test_pinned_addresses_agree_everywhere`, which fails until Task 7 creates `scheduler.ts`. Mark it `@pytest.mark.skip(reason="scheduler.ts lands in Task 7")` now; Task 7 removes the skip. If any existing test lists the Avalanche tokens (e.g. `supported()` text in `test_network_tools.py` / `test_tokens.py`), add `WAVAX` to its expected value.

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/scheduler.py agent/lazyagent/tokens.py agent/tests
git commit -m "feat(agent): scheduler calldata, order reads and schedule steps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Agent tools — schedule, list, cancel

**Files:**
- Modify: `agent/lazyagent/tools.py`, `agent/lazyagent/prompt.py`
- Test: `agent/tests/test_schedule_tools.py`

**Interfaces:**
- Consumes: everything Task 3 produces; existing `WalletTools._resolve`, `_balance_on`, `_steps_json`, `self.quoter`, `self.dexalot`, `best_route`, `currency_of`, `asset_of`, `min_out`, `gas_reserve`, `outcome_text`, `encode_erc20_allowance`.
- Produces: tools `propose_scheduled_swap(token_in, token_out, amount, interval_seconds?, count?, start_delay_seconds?, min_received?, network?)`, `list_scheduled_swaps()`, `cancel_scheduled_swap(order_id, network)`; names added to `TOOL_NAMES`.

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_schedule_tools.py`:

```python
import asyncio

from eth_abi import decode, encode
from fakes import FakeChain, FakeQuoter, Outbox

from lazyagent.networks import ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.scheduler import FIXED_GAS, NEXT_ID, SCHEDULER, encode_gas_balance, encode_get_order
from lazyagent.tokens import find_token
from lazyagent.tools import TOOL_NAMES, WalletContext, WalletTools
from lazyagent.uniswap import Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USDC = find_token("USDC", ETHEREUM.tokens)
WETH = find_token("WETH", ETHEREUM.tokens)
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
USDC_PER_ETH = 2358


def linear(route, amount_in):
    """Only the 0.05% ETH/USDC pool exists; 1 ETH = 2358 USDC both ways."""
    if route.hops != (Hop(500, 10),) or USDC.address not in route.currencies or len(route.currencies) != 2:
        return None
    if int(route.currencies[0], 16) == 0:
        return amount_in * USDC_PER_ETH // 10**12
    return amount_in * 10**12 // USDC_PER_ETH


def make(chain=None):
    out, proposals = Outbox(), Proposals()
    chain = chain or FakeChain(tokens={"USDC": 5_000 * 10**6})
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(linear))
    return tools, out, proposals, chain


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def test_tools_registered():
    for name in ("propose_scheduled_swap", "list_scheduled_swaps", "cancel_scheduled_swap"):
        assert f"mcp__wallet__{name}" in TOOL_NAMES


async def test_schedule_usdc_to_eth_shows_card_and_reports_success():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(
        tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "interval_seconds": "60", "count": "3"})
    )
    confirm = await confirm_of(out)
    steps = confirm["tx"]["steps"]
    assert [s["label"] for s in steps] == ["Allow USDC", "Schedule swap"]
    assert all(s["request"]["chainId"] == 1 for s in steps)
    schedule = steps[-1]["request"]
    assert schedule["to"] == SCHEDULER
    assert schedule["value"] == str(FIXED_GAS * chain.gp * 3 * 2)
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(schedule["data"][10:]))
    expected = 10 * 10**6 * 10**12 // USDC_PER_ETH
    assert args[:4] == (USDC.address, WETH.address, 10 * 10**6, expected * 9500 // 10_000)
    assert args[4:] == (chain.now, 60, 3)
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Schedule"] == "every 1 min × 3, starting now"
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xabc", "hashes": ["0x1", "0xabc"]})
    assert "Scheduled" in text(await task)


async def test_schedule_min_received_override():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(
        tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "min_received": "0.005"})
    )
    confirm = await confirm_of(out)
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(confirm["tx"]["steps"][-1]["request"]["data"][10:]))
    assert args[3] == 5 * 10**15 and args[5:] == (0, 1)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    assert "rejected" in text(await task)


async def test_schedule_skips_top_up_when_deposit_covers_it():
    tools, out, proposals, chain = make()
    chain.call_responses[encode_gas_balance(ME)[:10]] = (10**18).to_bytes(32, "big")
    task = asyncio.create_task(tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][-1]["request"]["value"] == "0"
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task


async def test_schedule_rejects_when_total_exceeds_balance():
    tools, out, _, _ = make(FakeChain(tokens={"USDC": 25 * 10**6}))
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "interval_seconds": 60, "count": 3})
    assert result.get("is_error") and "30 USDC" in text(result)
    assert not out.of_type("confirm")


async def test_schedule_rejects_when_native_cannot_cover_wrap_and_deposit():
    tools, out, _, _ = make(FakeChain(eth=10**17 + 1))
    result = await tools.propose_scheduled_swap({"token_in": "ETH", "token_out": "USDC", "amount": "0.05", "interval_seconds": 60, "count": 2})
    assert result.get("is_error") and "ETH" in text(result)
    assert not out.of_type("confirm")


async def test_schedule_rejects_same_token_once_wrapped():
    tools, _, _, _ = make()
    result = await tools.propose_scheduled_swap({"token_in": "ETH", "token_out": "WETH", "amount": "1"})
    assert result.get("is_error") and "same token" in text(result)


async def test_schedule_rejects_short_interval():
    tools, _, _, _ = make()
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "1", "interval_seconds": 10, "count": 2})
    assert result.get("is_error") and "1 minute" in text(result)


def order_bytes(owner=ME, executed=0, cancelled=False):
    return encode([ORDER_ABI], [(owner, USDC.address, WETH.address, 10 * 10**6, 1, 1_700_000_000, 60, 3, executed, 1_700_000_060, cancelled)])


async def test_list_scheduled_swaps():
    tools, _, _, chain = make()
    chain.call_responses[NEXT_ID[:10]] = (1).to_bytes(32, "big")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    result = await tools.list_scheduled_swaps({})
    assert "#0: 10 USDC → WETH, every 1 min × 3, 0/3 done, next run in 1 min" in text(result)


async def test_list_scheduled_swaps_empty():
    tools, _, _, _ = make()
    assert "No scheduled swaps" in text(await tools.list_scheduled_swaps({}))


async def test_cancel_scheduled_swap_card():
    tools, out, proposals, chain = make()
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    task = asyncio.create_task(tools.cancel_scheduled_swap({"order_id": "0", "network": "ethereum"}))
    confirm = await confirm_of(out)
    [step] = confirm["tx"]["steps"]
    assert step["request"]["to"] == SCHEDULER and step["request"]["chainId"] == 1
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xdef", "hashes": ["0xdef"]})
    assert "Cancelled scheduled swap #0" in text(await task)


async def test_cancel_refuses_someone_elses_or_finished_order():
    tools, _, _, chain = make()
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes(owner="0x000000000000000000000000000000000000dEaD")
    assert (await tools.cancel_scheduled_swap({"order_id": 0, "network": "ethereum"})).get("is_error")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes(executed=3)
    assert "already" in text(await tools.cancel_scheduled_swap({"order_id": 0, "network": "ethereum"}))
```

Run: `uv run --directory agent pytest tests/test_schedule_tools.py -q`
Expected: FAIL — `AttributeError: 'WalletTools' object has no attribute 'propose_scheduled_swap'`.

- [ ] **Step 2: Implement the tools**

In `agent/lazyagent/tools.py`:

Imports — add:

```python
from .scheduler import (
    MIN_OUT_DISCOUNT_BPS,
    SCHEDULER,
    decode_order,
    describe_order,
    encode_cancel,
    encode_get_order,
    gas_balance,
    gas_top_up,
    order_token,
    parse_schedule,
    read_orders,
    routing_token,
    schedule_label,
    schedule_rows,
    schedule_steps,
)
```

`TOOL_NAMES` tuple — add `"propose_scheduled_swap", "list_scheduled_swaps", "cancel_scheduled_swap"`.

Methods on `WalletTools` (after `propose_swap`):

```python
    async def _quote_out(self, net: Network, tin, tout, amount: int) -> int:
        """Today's output for one run, from the network's venue (wrapped legs quoted as native)."""
        a, b = routing_token(tin, net), routing_token(tout, net)
        if net.swap_venue == "dexalot":
            if self.dexalot is None:
                raise TransferError("Dexalot swaps aren't set up on this Sandbox.")
            return int((await self.dexalot.quote(asset_of(a), asset_of(b), amount, self.ctx.address))["order"]["makerAmount"])
        found = await best_route(self.quoter, currency_of(a), currency_of(b), amount)
        if found is None:
            raise TransferError(f"I couldn't find a Uniswap v4 route for {tin.symbol} → {tout.symbol} on Sandbox.")
        return found[1]

    async def propose_scheduled_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        sym_in, sym_out = str(args.get("token_in", "")).strip(), str(args.get("token_out", "")).strip()
        if sym_in.upper() == sym_out.upper():
            return err("Pick two different tokens to swap.")
        net = await self._resolve(args, [sym_in, sym_out], str(args.get("amount", "")), "schedule swaps of")
        if isinstance(net, dict):
            return net
        tin, tout = find_token(sym_in, net.tokens), find_token(sym_out, net.tokens)
        pay, get = order_token(tin, net), order_token(tout, net)
        chain = self.chains[net.key]
        try:
            if pay.address == get.address:
                raise TransferError(f"{tin.symbol} and {tout.symbol} are the same token once wrapped — pick two different tokens.")
            amount = parse_amount(str(args.get("amount", "")), tin.decimals)
            interval, count, delay = parse_schedule(args.get("interval_seconds"), args.get("count"), args.get("start_delay_seconds"))
            total = amount * count
            balance = await self._balance_on(net, tin)
            if total > balance:
                raise TransferError(
                    f"{count} runs of {format_units(amount, tin.decimals)} {tin.symbol} need {format_units(total, tin.decimals)} {tin.symbol}, "
                    f"but you have {format_units(balance, tin.decimals)}."
                )
            if args.get("min_received"):
                minimum = parse_amount(str(args["min_received"]), get.decimals)
            else:
                minimum = min_out(await self._quote_out(net, tin, tout, amount), MIN_OUT_DISCOUNT_BPS)
            start = await chain.block_timestamp() + delay
            allowance = int.from_bytes((await chain.call(pay.address, encode_erc20_allowance(self.ctx.address, SCHEDULER)))[:32], "big")
            gas_price = await chain.gas_price()
            top_up = gas_top_up(gas_price, count, await gas_balance(chain, self.ctx.address))
            steps = schedule_steps(tin, tout, net, amount, minimum, start, interval, count, allowance, top_up)
            needed = gas_reserve(steps, gas_price) + top_up + (total if tin.address is None else 0)
            native_balance = await chain.eth_balance(self.ctx.address)
            if needed > native_balance:
                raise TransferError(
                    f"Not enough {net.native.symbol} for the wrap, gas deposit and fees (need ~{format_units(needed, 18)} {net.native.symbol}). "
                    "Try fewer runs or get test funds."
                )
            label = schedule_label(interval, count, delay)
            rows = schedule_rows(self.ctx.address, tin, tout, net, amount, minimum, label, top_up)
        except TransferError as e:
            return err(str(e))
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")

        human = f"{format_units(amount, tin.decimals)} {tin.symbol}"
        steps_json = self._steps_json([s.to_json() for s in steps], net)
        pid, fut = self.proposals.new()
        await self.send(
            {"type": "confirm", "id": pid, "tx": {"title": f"Schedule {human} → {get.symbol}", "from": self.ctx.address, "rows": rows, "steps": steps_json}}
        )
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = ""
        if _succeeded(result):
            success = (
                f"Scheduled {human} → {get.symbol}, {label}, on {net.label} (tx {result.get('hash')}). "
                "The executor runs it on-chain — the app doesn't need to stay open. It's listed in Scheduled tasks."
            )
        return ok(outcome_text(result, steps_json, "scheduled swap", success))

    async def list_scheduled_swaps(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        lines, down = [], []
        for net in self.networks:
            chain = self.chains[net.key]
            try:
                orders = await read_orders(chain, self.ctx.address)
                now = await chain.block_timestamp()
            except Exception:
                down.append(net.name)
                continue
            lines += [f"{describe_order(o, net, now)} on {net.name}" for o in orders]
        note = f" Not reachable right now: {', '.join(down)}." if down else ""
        if not lines:
            return ok(f"No scheduled swaps yet.{note}")
        return ok(f"Scheduled swaps: {'; '.join(lines)}.{note}")

    async def cancel_scheduled_swap(self, args: dict) -> dict:
        if not self.ctx.address:
            return err("No wallet is active in the app.")
        net = find_network(str(args.get("network", "")))
        if net is None or net.key not in self.chains:
            return err(f"Which network is the scheduled swap on? {', '.join(n.name for n in self.networks)}.")
        try:
            oid = int(args.get("order_id"))
        except (TypeError, ValueError):
            return err("I need the scheduled swap's number, like 3.")
        chain = self.chains[net.key]
        try:
            order = decode_order(oid, await chain.call(SCHEDULER, encode_get_order(oid)))
            now = await chain.block_timestamp()
        except Exception as e:
            return err(f"The {net.name} Sandbox chain isn't reachable right now ({e}).")
        if order.owner.lower() != self.ctx.address.lower():
            return err(f"I can't find a scheduled swap #{oid} of yours on {net.name}.")
        if not order.active:
            return err(f"Scheduled swap #{oid} is already {'cancelled' if order.cancelled else 'finished'}.")
        steps = self._steps_json([{"label": "Cancel scheduled swap", "request": {"to": SCHEDULER, "value": "0", "data": encode_cancel(oid)}}], net)
        rows = [
            {"label": "From", "value": short(self.ctx.address)},
            {"label": "Order", "value": describe_order(order, net, now)},
            {"label": "Network", "value": net.label},
        ]
        pid, fut = self.proposals.new()
        await self.send({"type": "confirm", "id": pid, "tx": {"title": f"Cancel scheduled swap #{oid}", "from": self.ctx.address, "rows": rows, "steps": steps}})
        result = await self.proposals.wait(pid, fut, self.approval_timeout)
        success = f"Cancelled scheduled swap #{oid} on {net.label}, tx {result.get('hash')}." if _succeeded(result) else ""
        return ok(outcome_text(result, steps, "cancellation", success))
```

Registrations in `build_mcp_server` (before `request_test_funds`):

```python
            tool(
                "propose_scheduled_swap",
                "Propose an on-chain scheduled swap: one run now/later or recurring (e.g. every minute × 5). Shows one confirmation card "
                "(wrap if paying ETH/AVAX, allowance, schedule + gas deposit), waits for approve/reject. The executor runs it later; the app needn't stay open.",
                {
                    "type": "object",
                    "properties": {
                        "token_in": {"type": "string", "description": f"Token to pay each run, one of {t.supported()}"},
                        "token_out": {"type": "string", "description": f"Token to receive, one of {t.supported()}"},
                        "amount": {"type": "string", "description": "Decimal amount of token_in per run, e.g. '10'"},
                        "interval_seconds": {"type": "integer", "description": "Seconds between runs (≥ 60). Omit for a single run"},
                        "count": {"type": "integer", "description": "Number of runs (1–100). Default 1"},
                        "start_delay_seconds": {"type": "integer", "description": "Seconds from now until the first run. Default 0"},
                        "min_received": {"type": "string", "description": "Only if the user set a limit: minimum token_out per run, decimal"},
                        "network": {"type": "string", "description": "Only if the user named a network or answered a network choice: 'ethereum' or 'avalanche'"},
                    },
                    "required": ["token_in", "token_out", "amount"],
                },
            )(t.propose_scheduled_swap),
            tool("list_scheduled_swaps", "List the user's scheduled swaps on every Sandbox network with progress and next run.", {"type": "object", "properties": {}})(t.list_scheduled_swaps),
            tool(
                "cancel_scheduled_swap",
                "Propose cancelling one of the user's scheduled swaps (confirmation card). Use list_scheduled_swaps first to find its number and network.",
                {
                    "type": "object",
                    "properties": {"order_id": {"type": "integer"}, "network": {"type": "string", "description": "'ethereum' or 'avalanche'"}},
                    "required": ["order_id", "network"],
                },
            )(t.cancel_scheduled_swap),
```

`unsupported_action` description: replace `"Use for bridging, scheduling, price alerts, dApps or anything other than balances, sends, swaps and test funds."` with `"Use for bridging, price alerts, conditional actions, dApps or anything other than balances, sends, swaps, scheduled swaps and test funds."`.

- [ ] **Step 3: Update the prompt**

In `agent/lazyagent/prompt.py` replace the line `- Bridging between networks, schedules, price alerts, dApps or anything else → unsupported_action.` with:

```
- Scheduled or recurring swaps ("swap 10 USDC to AVAX every minute, 5 times", "buy ETH with 20 USDC in 10 minutes") → propose_scheduled_swap with the per-run amount, interval_seconds, count and start_delay_seconds. Pass min_received only if the user gave a limit. Runs are at least a minute apart, up to 100 runs; ETH/AVAX output arrives as WETH/WAVAX. "What's scheduled" → list_scheduled_swaps; "cancel my scheduled swap" → list first, then cancel_scheduled_swap with its number and network.
- Bridging between networks, price alerts, conditional actions ("if ETH drops…"), dApps or anything else → unsupported_action.
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory agent pytest -q`
Expected: all PASS (fork tests run or skip as before).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/tools.py agent/lazyagent/prompt.py agent/tests/test_schedule_tools.py
git commit -m "feat(agent): schedule, list and cancel on-chain swaps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Executor call builders (Uniswap with Swapper as taker, Dexalot)

**Files:**
- Modify: `agent/lazyagent/uniswap.py` (`encode_swap` gains `wrap_output`)
- Create: `agent/lazyagent/executor.py` (pure builders only in this task)
- Test: `agent/tests/test_uniswap.py` (add), `agent/tests/test_executor.py`

**Interfaces:**
- Consumes: `Order`, `Call`, `SWAPPER` (Task 3); `Route`, `ZERO`, `PERMIT2`, `UNIVERSAL_ROUTER`, `encode_erc20_approve`, `encode_permit2_approve`, `encode_weth_withdraw`, `WETH_DEPOSIT` (`uniswap.py`); `encode_simple_swap` (`dexalot.py`); `DEADLINE_S`, `PERMIT2_EXPIRY_S` (`swaps.py`).
- Produces: `encode_swap(route, amount_in, min_out, deadline, wrap_output: bool = False) -> str`; `uniswap_calls(order: Order, pay: Token, route: Route, now: int, wrapped: str) -> list[Call]`; `dexalot_calls(order: Order, quote: dict, wrapped: str) -> list[Call]`; constants `WRAP_ETH = 0x0B`, `TAKE = 0x0E`.

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_uniswap.py`:

```python
def test_encode_swap_wrap_output_takes_to_router_then_wraps_to_caller():
    from lazyagent.uniswap import CONTRACT_BALANCE, TAKE, WRAP_ETH

    usdc = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    route = Route((usdc, ZERO), (Hop(500, 10),))
    data = encode_swap(route, 10**6, 123, 999, wrap_output=True)
    commands, inputs, deadline = decode(["bytes", "bytes[]", "uint256"], bytes.fromhex(data[10:]))
    assert commands == bytes([V4_SWAP, WRAP_ETH]) and deadline == 999
    actions, params = decode(["bytes", "bytes[]"], inputs[0])
    assert actions[-1] == TAKE
    assert decode(["address", "address", "uint256"], params[2]) == (ZERO, "0x0000000000000000000000000000000000000002", 0)
    assert decode(["address", "uint256"], inputs[1]) == ("0x0000000000000000000000000000000000000001", CONTRACT_BALANCE)
    # default output is unchanged (matches the verified recipe tests above)
    assert encode_swap(route, 10**6, 123, 999) == encode_swap(route, 10**6, 123, 999, wrap_output=False)
```

(Add `V4_SWAP` to that file's `from lazyagent.uniswap import …` line if it isn't imported; `decode`, `Route`, `Hop`, `ZERO`, `encode_swap` already are — check the header and add any that are missing.)

`agent/tests/test_executor.py`:

```python
from eth_abi import decode

from lazyagent.executor import dexalot_calls, uniswap_calls
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.scheduler import SWAPPER, Order, wrapped_token
from lazyagent.tokens import find_token
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, WETH_DEPOSIT, ZERO, Hop, Route

USDC = find_token("USDC", ETHEREUM.tokens)
USDT = find_token("USDT", ETHEREUM.tokens)
WETH = wrapped_token(ETHEREUM)
WAVAX = wrapped_token(AVALANCHE)
AUSDC = find_token("USDC", AVALANCHE.tokens)
MAKER = "0x1111111111111111111111111111111111111111"


def order(token_in, token_out, amount=10**6, min_out=5):
    return Order(0, "0x" + "ab" * 20, token_in, token_out, amount, min_out, 0, 60, 2, 0, 0, False)


def test_uniswap_erc20_in_native_out_approves_permit2_and_wraps():
    calls = uniswap_calls(order(USDC.address, WETH.address), USDC, Route((USDC.address, ZERO), (Hop(500, 10),)), 1000, WETH.address)
    assert [c[0] for c in calls] == [USDC.address, PERMIT2, UNIVERSAL_ROUTER]
    assert calls[2][1] == 0
    commands = decode(["bytes", "bytes[]", "uint256"], bytes.fromhex(calls[2][2][10:]))[0]
    assert commands == bytes([0x10, 0x0B])


def test_uniswap_weth_in_unwraps_and_pays_value():
    calls = uniswap_calls(order(WETH.address, USDC.address, amount=10**17), WETH, Route((ZERO, USDC.address), (Hop(500, 10),)), 1000, WETH.address)
    assert calls[0][0] == WETH.address and calls[0][2].startswith("0x2e1a7d4d")  # withdraw(uint256)
    assert calls[1][0] == UNIVERSAL_ROUTER and calls[1][1] == 10**17


def test_uniswap_usdt_resets_permit2_allowance_first():
    calls = uniswap_calls(order(USDT.address, WETH.address), USDT, Route((USDT.address, ZERO), (Hop(500, 10),)), 1000, WETH.address)
    assert len(calls) == 4 and calls[0][0] == USDT.address


def quote(taker_asset, maker_asset, taker_amount, maker_amount):
    return {
        "maker": MAKER,
        "signature": "0x" + "11" * 65,
        "order": {
            "nonceAndMeta": "1", "expiry": "9", "makerAsset": maker_asset, "takerAsset": taker_asset,
            "maker": MAKER, "taker": SWAPPER, "makerAmount": str(maker_amount), "takerAmount": str(taker_amount),
        },
    }


def test_dexalot_wavax_in_unwraps_then_pays_native():
    calls = dexalot_calls(order(WAVAX.address, AUSDC.address, amount=10**18), quote(ZERO, AUSDC.address, 10**18, 20 * 10**6), WAVAX.address)
    assert [c[0] for c in calls] == [WAVAX.address, MAKER]
    assert calls[1][1] == 10**18


def test_dexalot_native_out_is_wrapped_to_wavax():
    calls = dexalot_calls(order(AUSDC.address, WAVAX.address), quote(AUSDC.address, ZERO, 10**6, 5 * 10**16), WAVAX.address)
    assert [c[0] for c in calls] == [AUSDC.address, MAKER, WAVAX.address]
    assert calls[2] == (WAVAX.address, 5 * 10**16, WETH_DEPOSIT)
```

Run: `uv run --directory agent pytest tests/test_uniswap.py tests/test_executor.py -q`
Expected: FAIL — `ImportError` (`CONTRACT_BALANCE`, `lazyagent.executor`).

- [ ] **Step 2: Extend `encode_swap`**

In `agent/lazyagent/uniswap.py`, after `SWAP_EXACT_IN_SINGLE, SWAP_EXACT_IN, SETTLE_ALL, TAKE_ALL = …`:

```python
TAKE = 0x0E
WRAP_ETH = 0x0B  # Universal Router command
MSG_SENDER = "0x0000000000000000000000000000000000000001"
ADDRESS_THIS = "0x0000000000000000000000000000000000000002"
CONTRACT_BALANCE = 1 << 255
OPEN_DELTA = 0
```

Replace `encode_swap` with:

```python
def encode_swap(route: Route, amount_in: int, min_out: int, deadline: int, wrap_output: bool = False) -> str:
    """wrap_output (route must end in native ETH): TAKE the ETH into the router, then WRAP_ETH all of it to the caller
    as WETH — for the scheduler's Swapper, whose orders pay out WETH."""
    cin, cout = route.currencies[0], route.currencies[-1]
    if len(route.hops) == 1:
        key = pool_key(cin, cout, route.hops[0])
        swap = encode([f"({POOL_KEY},bool,uint128,uint128,bytes)"], [(key, cin == key[0], amount_in, min_out, b"")])
        first = SWAP_EXACT_IN_SINGLE
    else:
        swap = encode([f"(address,{PATH_KEY}[],uint128,uint128)"], [(cin, _path(route), amount_in, min_out)])
        first = SWAP_EXACT_IN
    settle = encode(["address", "uint256"], [cin, amount_in])
    if wrap_output:
        assert cout == ZERO, "wrap_output needs a route ending in native ETH"
        actions = bytes([first, SETTLE_ALL, TAKE])
        take = encode(["address", "address", "uint256"], [cout, ADDRESS_THIS, OPEN_DELTA])
        commands, extra = bytes([V4_SWAP, WRAP_ETH]), [encode(["address", "uint256"], [MSG_SENDER, CONTRACT_BALANCE])]
    else:
        actions = bytes([first, SETTLE_ALL, TAKE_ALL])
        take = encode(["address", "uint256"], [cout, min_out])
        commands, extra = bytes([V4_SWAP]), []
    v4_input = encode(["bytes", "bytes[]"], [actions, [swap, settle, take]])
    return _call("execute(bytes,bytes[],uint256)", ["bytes", "bytes[]", "uint256"], [commands, [v4_input, *extra], deadline])
```

- [ ] **Step 3: Create `agent/lazyagent/executor.py` with the builders**

```python
"""Executor for the SwapScheduler: finds due orders on both Sandbox forks and executes them with a route built
for the Swapper (the taker), earning the gas rebate. Run with `pnpm dev:executor`."""

from .dexalot import encode_simple_swap
from .scheduler import Call, Order
from .swaps import DEADLINE_S, PERMIT2_EXPIRY_S
from .tokens import Token
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ZERO,
    Route,
    encode_erc20_approve,
    encode_permit2_approve,
    encode_swap,
    encode_weth_withdraw,
)


def uniswap_calls(order: Order, pay: Token, route: Route, now: int, wrapped: str) -> list[Call]:
    cin, cout = route.currencies[0], route.currencies[-1]
    calls: list[Call] = []
    if cin == ZERO:  # the order holds WETH; the pool takes native ETH
        calls.append((wrapped, 0, encode_weth_withdraw(order.amount_in)))
        value = order.amount_in
    else:
        if pay.symbol == "USDT":  # USDT reverts on nonzero → nonzero approvals
            calls.append((pay.address, 0, encode_erc20_approve(PERMIT2, 0)))
        calls.append((pay.address, 0, encode_erc20_approve(PERMIT2, order.amount_in)))
        calls.append((PERMIT2, 0, encode_permit2_approve(pay.address, UNIVERSAL_ROUTER, order.amount_in, now + PERMIT2_EXPIRY_S)))
        value = 0
    data = encode_swap(route, order.amount_in, order.min_out, now + DEADLINE_S, wrap_output=cout == ZERO)
    calls.append((UNIVERSAL_ROUTER, value, data))
    return calls


def dexalot_calls(order: Order, quote: dict, wrapped: str) -> list[Call]:
    o, maker = quote["order"], quote["maker"]
    native_in, native_out = int(o["takerAsset"], 16) == 0, int(o["makerAsset"], 16) == 0
    calls: list[Call] = []
    if native_in:  # the order holds WAVAX; Dexalot's pair is native AVAX
        calls.append((wrapped, 0, encode_weth_withdraw(order.amount_in)))
    else:
        calls.append((order.token_in, 0, encode_erc20_approve(maker, order.amount_in)))
    calls.append((maker, order.amount_in if native_in else 0, encode_simple_swap(o, quote["signature"])))
    if native_out:  # an RFQ order pays exactly makerAmount, so wrap exactly that
        calls.append((wrapped, int(o["makerAmount"]), WETH_DEPOSIT))
    return calls
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory agent pytest tests/test_uniswap.py tests/test_executor.py tests/test_swap_tools.py -q`
Expected: PASS (existing swap tests prove the default `encode_swap` output is unchanged).

- [ ] **Step 5: Commit**

```bash
git add agent/lazyagent/uniswap.py agent/lazyagent/executor.py agent/tests/test_uniswap.py agent/tests/test_executor.py
git commit -m "feat(agent): executor call builders for Uniswap v4 and Dexalot with the Swapper as taker

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Executor loop, `pnpm dev:executor`, fork tests

**Files:**
- Modify: `agent/lazyagent/executor.py` (add `Target`, `Executor`, `main`), `agent/pyproject.toml` (script), `package.json` (`dev:executor`)
- Modify: `agent/tests/conftest.py` (add `deploy_scheduler`)
- Test: `agent/tests/test_executor.py` (add), `agent/tests/test_scheduler_fork.py`

**Interfaces:**
- Consumes: `read_orders`, `encode_execute`, `SCHEDULER`, `SWAPPER`, `token_at`, `routing_token`, `wrapped_token` (Task 3); `uniswap_calls`, `dexalot_calls` (Task 5); `best_route`, `currency_of`, `ChainQuoter`; `asset_of`, `Quotes`, `SandboxQuotes`; `RpcChain`; `load_settings`.
- Produces: `@dataclass(frozen=True) Target(net: Network, chain: Chain, w3: AsyncWeb3, quoter: Quoter | None)`; `Executor(targets: list[Target], dexalot: Quotes | None, key: str = EXECUTOR_KEY)` with `async tick() -> list[str]`, `async build_calls(t, order, now) -> list[Call]`, `async run_forever()`; `main()`; `EXECUTOR_KEY` (Anvil account #9, address `0xa0Ee7A142d267C1f36714E4a8F75612F20a79720`).

- [ ] **Step 1: Write the failing unit tests**

Append to `agent/tests/test_executor.py` (move the new imports up into the file's import block):

```python
from eth_abi import encode as abi_encode
from fakes import FakeChain

from lazyagent.executor import Executor, Target
from lazyagent.scheduler import NEXT_ID, encode_get_order

ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"


class OrdersChain(FakeChain):
    """Two due orders (ids 0 and 1); FakeChain keys responses by selector only, so answer by full calldata."""

    async def call(self, to, data, gas=None):
        if data == NEXT_ID:
            return (2).to_bytes(32, "big")
        for i in (0, 1):
            if data == encode_get_order(i):
                return abi_encode([ORDER_ABI], [("0x" + "ab" * 20, USDC.address, WETH.address, 10**6, 1, 0, 0, 1, 0, 0, False)])
        return bytes(32)


class FakeExecutor(Executor):
    def __init__(self, targets, fail_ids=()):
        super().__init__(targets, None)
        self.fail_ids, self.sent = set(fail_ids), []

    async def build_calls(self, t, order, now):
        if order.id in self.fail_ids:
            raise RuntimeError("price below minOut")
        return []

    async def _send(self, t, order_id, calls):
        self.sent.append(order_id)
        return f"0x{order_id}"


async def test_tick_skips_failing_order_and_runs_the_next():
    ex = FakeExecutor([Target(ETHEREUM, OrdersChain(), None, None)], fail_ids={0})
    assert await ex.tick() == ["0x1"]
    assert ex.sent == [1]


async def test_tick_survives_unreachable_chain():
    down = FakeChain()
    down.fail = True

    async def boom(*a, **k):
        raise ConnectionError("connection refused")

    down.call = boom
    down.block_timestamp = boom
    ex = FakeExecutor([Target(ETHEREUM, down, None, None), Target(AVALANCHE, OrdersChain(), None, None)])
    assert await ex.tick() == ["0x0", "0x1"]
```

Run: `uv run --directory agent pytest tests/test_executor.py -q`
Expected: FAIL — `ImportError: cannot import name 'Executor'`.

- [ ] **Step 2: Implement the loop**

Add to `agent/lazyagent/executor.py` (merge imports with the existing block):

```python
import asyncio
import logging
from dataclasses import dataclass

from eth_account import Account
from web3 import AsyncWeb3

from .chain import Chain, RpcChain
from .config import load_settings
from .dexalot import Quotes, SandboxQuotes, asset_of
from .networks import AVALANCHE, ETHEREUM, Network
from .scheduler import SCHEDULER, SWAPPER, encode_execute, read_orders, routing_token, token_at, wrapped_token
from .uniswap import ChainQuoter, Quoter, best_route, currency_of

log = logging.getLogger("lazyagent.executor")
EXECUTOR_KEY = "0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6"  # Anvil dev account #9
TICK_S = 10
GAS_MARGIN = 1.2


class ExecutorError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    net: Network
    chain: Chain
    w3: AsyncWeb3 | None
    quoter: Quoter | None


class Executor:
    def __init__(self, targets: list[Target], dexalot: Quotes | None, key: str = EXECUTOR_KEY):
        self.targets = targets
        self.dexalot = dexalot
        self.account = Account.from_key(key)

    async def build_calls(self, t: Target, order, now: int) -> list:
        net = t.net
        pay, get = token_at(net, order.token_in), token_at(net, order.token_out)
        if pay is None or get is None:
            raise ExecutorError("order uses a token this executor doesn't route")
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

    async def _send(self, t: Target, order_id: int, calls: list) -> str:
        w3 = t.w3
        tx = {
            "from": self.account.address,
            "to": SCHEDULER,
            "value": 0,
            "data": encode_execute(order_id, calls),
            "chainId": t.net.chain_id,
            "gasPrice": await w3.eth.gas_price,
        }
        # Simulates with this gas price, so minOut, allowance and the owner's gas deposit are all checked before sending.
        tx["gas"] = int(await w3.eth.estimate_gas(tx) * GAS_MARGIN)
        tx["nonce"] = await w3.eth.get_transaction_count(self.account.address, "pending")
        tx_hash = await w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            raise ExecutorError(f"executeSwap reverted ({tx_hash.to_0x_hex()})")
        return tx_hash.to_0x_hex()

    async def tick(self) -> list[str]:
        sent: list[str] = []
        for t in self.targets:
            try:
                now = await t.chain.block_timestamp()
                due = [o for o in await read_orders(t.chain) if o.due(now)]
            except Exception as e:
                log.warning("%s: can't read scheduled orders (%s)", t.net.name, e)
                continue
            for order in due:
                try:
                    tx_hash = await self._send(t, order.id, await self.build_calls(t, order, now))
                except Exception as e:
                    log.warning("%s: order #%d skipped: %s", t.net.name, order.id, e)
                    continue
                log.info("%s: executed order #%d (%s)", t.net.name, order.id, tx_hash)
                sent.append(tx_hash)
        return sent

    async def run_forever(self) -> None:
        for t in self.targets:
            if not await t.chain.is_sandbox():
                raise SystemExit(f"{t.net.name} RPC isn't a local Anvil Sandbox — the executor only runs on Sandbox.")
        log.info("Executor %s watching %s on %s", self.account.address, SCHEDULER, ", ".join(t.net.name for t in self.targets))
        while True:
            await self.tick()
            await asyncio.sleep(TICK_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    s = load_settings()
    eth, avax = RpcChain(s.rpc_url), RpcChain(s.avax_rpc_url, poa=True)
    targets = [Target(ETHEREUM, eth, eth.w3, ChainQuoter(eth)), Target(AVALANCHE, avax, avax.w3, None)]
    asyncio.run(Executor(targets, SandboxQuotes(s.faucet_url)).run_forever())
```

`agent/pyproject.toml` `[project.scripts]` — add `executor = "lazyagent.executor:main"`.
Root `package.json` scripts — add `"dev:executor": "uv run --directory agent executor",`.

- [ ] **Step 3: Run unit tests**

Run: `uv run --directory agent pytest tests/test_executor.py -q`
Expected: PASS.

- [ ] **Step 4: Write the fork tests**

Add to `agent/tests/conftest.py`:

```python
DEV_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def deploy_scheduler(rpc: str) -> None:
    """Idempotent CREATE2 deploy of contracts/ onto a test fork (same as `pnpm dev:sandbox` does)."""
    from lazyagent.scheduler import SCHEDULER

    if Web3(HTTPProvider(rpc)).eth.get_code(SCHEDULER):
        return
    cmd = ["forge", "script", "script/Deploy.s.sol:Deploy", "--rpc-url", rpc, "--broadcast", "--private-key", DEV_KEY]
    subprocess.run(cmd, cwd=ROOT / "contracts", check=True, capture_output=True)
```

`agent/tests/test_scheduler_fork.py`:

```python
import asyncio

from conftest import deploy_scheduler
from eth_abi import encode
from eth_account import Account
from fakes import FakeChain
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.dexalot import SandboxQuotes
from lazyagent.executor import Executor, Target
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.scheduler import gas_balance, read_orders, wrapped_token
from lazyagent.tokens import find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import ChainQuoter

USDC_SLOT = 9  # both mainnet USDC and Avalanche native USDC


async def setup_account(w3, usdc_address: str | None = None, usdc: int = 0):
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(20 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_SLOT])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [usdc_address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    return account


def auto_approve(w3, account, proposals):
    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    return send


async def balance_of(chain, token, address):
    return await chain.token_balance(token, address)


async def warp(w3, seconds: int):
    await w3.provider.make_request("evm_increaseTime", [seconds])
    await w3.provider.make_request("evm_mine", [])


async def test_avalanche_avax_to_usdc_runs_twice(avax_sandbox):
    rpc, url = avax_sandbox
    deploy_scheduler(rpc)
    chain = RpcChain(rpc, poa=True)
    account = await setup_account(chain.w3)
    proposals = Proposals()
    tools = WalletTools(FakeChain(), auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=chain, dexalot=SandboxQuotes(url))
    result = await tools.propose_scheduled_swap({"token_in": "AVAX", "token_out": "USDC", "amount": "1", "interval_seconds": 60, "count": 2})
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    deposit = await gas_balance(chain, account.address)

    ex = Executor([Target(AVALANCHE, chain, chain.w3, None)], SandboxQuotes(url))
    usdc = find_token("USDC", AVALANCHE.tokens)
    assert len(await ex.tick()) == 1
    first = await balance_of(chain, usdc, account.address)
    assert first >= order.min_out
    assert await ex.tick() == []  # not due again yet
    await warp(chain.w3, 61)
    assert len(await ex.tick()) == 1
    assert await balance_of(chain, usdc, account.address) >= first + order.min_out
    [after] = await read_orders(chain, account.address)
    assert after.executed == 2 and not after.active
    assert await gas_balance(chain, account.address) < deposit  # rebates paid


async def test_avalanche_usdc_to_avax_pays_wavax(avax_sandbox):
    rpc, url = avax_sandbox
    deploy_scheduler(rpc)
    chain = RpcChain(rpc, poa=True)
    usdc = find_token("USDC", AVALANCHE.tokens)
    account = await setup_account(chain.w3, usdc.address, 100 * 10**6)
    proposals = Proposals()
    tools = WalletTools(FakeChain(), auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=chain, dexalot=SandboxQuotes(url))
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "AVAX", "amount": "10"})
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    assert len(await Executor([Target(AVALANCHE, chain, chain.w3, None)], SandboxQuotes(url)).tick()) == 1
    assert await balance_of(chain, wrapped_token(AVALANCHE), account.address) >= order.min_out


async def ethereum_run(fork_rpc, args: dict, usdc: int = 0):
    deploy_scheduler(fork_rpc)
    chain = RpcChain(fork_rpc)
    account = await setup_account(chain.w3, find_token("USDC").address, usdc)
    proposals = Proposals()
    tools = WalletTools(chain, auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_scheduled_swap(args)
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    assert len(await Executor([Target(ETHEREUM, chain, chain.w3, ChainQuoter(chain))], None).tick()) == 1
    return chain, account, order


async def test_ethereum_usdc_to_eth_pays_weth(fork_rpc):
    chain, account, order = await ethereum_run(fork_rpc, {"token_in": "USDC", "token_out": "ETH", "amount": "100"}, usdc=1_000 * 10**6)
    assert await balance_of(chain, wrapped_token(ETHEREUM), account.address) >= order.min_out


async def test_ethereum_eth_to_usdc(fork_rpc):
    chain, account, order = await ethereum_run(fork_rpc, {"token_in": "ETH", "token_out": "USDC", "amount": "0.1"})
    assert await balance_of(chain, find_token("USDC"), account.address) >= order.min_out
```

`ExtraDataToPOAMiddleware` and `AsyncHTTPProvider`/`AsyncWeb3` imports are unused if `RpcChain.w3` is used throughout; delete them if ruff flags them.

- [ ] **Step 5: Run the fork tests**

Run: `uv run --directory agent pytest tests/test_scheduler_fork.py -v`
Expected: 4 PASS (the Ethereum ones skip without `ETH_RPC_URL`). These are the gate for the `wrap_output` Uniswap recipe and the Dexalot-with-contract-taker path. If the Ethereum USDC→ETH test fails inside the Universal Router, confirm the `TAKE`/`WRAP_ETH` constants against the deployed router's `Commands.sol`/`Actions.sol` (v4-periphery `ActionConstants`) before changing anything else.

- [ ] **Step 6: Run everything**

Run: `pnpm test:py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add agent/lazyagent/executor.py agent/pyproject.toml package.json agent/tests
git commit -m "feat(agent): scheduled-swap executor service with fork tests on both networks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Wallet — real orders in the Scheduled tasks sheet

**Files:**
- Create: `apps/wallet/src/chain/scheduler.ts`, `apps/wallet/src/chain/scheduler.test.ts`, `apps/wallet/src/chain/useScheduledOrders.ts`
- Modify: `apps/wallet/src/components/TasksSheet.tsx`, `apps/wallet/src/routes/WalletPage.tsx`, `apps/wallet/src/mock/agent.ts`, `apps/wallet/src/mock/agent.test.ts`, `apps/wallet/src/mock/fixtures.ts`
- Modify: `agent/tests/test_scheduler.py` (remove the Task 3 skip)

**Interfaces:**
- Consumes: `sandboxChains` (`chain/networks.ts`), pinned `SCHEDULER` (Task 2), `getOrder`/`nextId` ABI (Task 1).
- Produces: `SCHEDULER_ADDRESS`, `schedulerAbi`, `type ScheduledOrder`, `type OrderStatus`, `durationLabel(seconds)`, `orderStatus(order, nowSec)`, `mergeSettled(results)`, `readOrders(owner)`; hook `useScheduledOrders(address?)`.

- [ ] **Step 1: Write the failing tests**

`apps/wallet/src/chain/scheduler.test.ts`:

```ts
import { describe, expect, test } from 'vitest'
import { durationLabel, mergeSettled, orderStatus } from './scheduler'

const base = { cancelled: false, executed: 1, count: 3, nextTime: 1_000 }

describe('durationLabel', () => {
  test('rounds to the largest unit', () => {
    expect(durationLabel(45)).toBe('45s')
    expect(durationLabel(60)).toBe('1 min')
    expect(durationLabel(7200)).toBe('2 h')
    expect(durationLabel(604800)).toBe('7 d')
  })
})

describe('orderStatus', () => {
  test('active with time until next run', () => {
    expect(orderStatus(base, 970)).toEqual({ state: 'active', label: 'Next run in 30s' })
  })
  test('due now once nextTime passes', () => {
    expect(orderStatus(base, 1_005)).toEqual({ state: 'active', label: 'Due now' })
  })
  test('done after the last run', () => {
    expect(orderStatus({ ...base, executed: 3 }, 0)).toEqual({ state: 'done', label: 'Done' })
  })
  test('cancelled wins', () => {
    expect(orderStatus({ ...base, cancelled: true }, 0)).toEqual({ state: 'cancelled', label: 'Cancelled' })
  })
})

describe('mergeSettled', () => {
  test('mergeSettled keeps fulfilled chains', () => {
    const ok: PromiseSettledResult<number[]> = { status: 'fulfilled', value: [1, 2] }
    const down: PromiseSettledResult<number[]> = { status: 'rejected', reason: new Error('fork down') }
    expect(mergeSettled([down, ok])).toEqual([1, 2])
  })
})
```

Run: `pnpm --filter wallet test`
Expected: FAIL — cannot resolve `./scheduler`.

- [ ] **Step 2: Implement `scheduler.ts`**

`apps/wallet/src/chain/scheduler.ts` (use the address pinned in Task 2, single quotes — the agent test greps for `'0x…'`):

```ts
import { createPublicClient, erc20Abi, http, type Chain } from 'viem'
import type { Address } from '@/types'
import { sandboxChains } from './networks'

// = contracts/src/Deployment.sol (CREATE2, identical on both forks)
export const SCHEDULER_ADDRESS: Address = '<Deployment.SCHEDULER>'
const MAX_LISTED = 200n

export const schedulerAbi = [
  { type: 'function', name: 'nextId', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  {
    type: 'function',
    name: 'getOrder',
    stateMutability: 'view',
    inputs: [{ name: 'id', type: 'uint256' }],
    outputs: [
      {
        type: 'tuple',
        components: [
          { name: 'owner', type: 'address' },
          { name: 'tokenIn', type: 'address' },
          { name: 'tokenOut', type: 'address' },
          { name: 'amountIn', type: 'uint256' },
          { name: 'minOut', type: 'uint256' },
          { name: 'startTime', type: 'uint64' },
          { name: 'interval', type: 'uint64' },
          { name: 'count', type: 'uint32' },
          { name: 'executed', type: 'uint32' },
          { name: 'nextTime', type: 'uint64' },
          { name: 'cancelled', type: 'bool' },
        ],
      },
    ],
  },
] as const

export type TokenInfo = { address: Address; symbol: string; decimals: number }
export type ScheduledOrder = {
  chainId: number
  network: string
  id: bigint
  tokenIn: TokenInfo
  tokenOut: TokenInfo
  amountIn: bigint
  minOut: bigint
  interval: number
  count: number
  executed: number
  nextTime: number
  cancelled: boolean
}
export type OrderStatus = { state: 'active' | 'done' | 'cancelled'; label: string }

export function durationLabel(seconds: number): string {
  for (const [size, unit] of [
    [86400, 'd'],
    [3600, 'h'],
    [60, 'min'],
  ] as const) {
    if (seconds >= size) return `${Math.round(seconds / size)} ${unit}`
  }
  return `${seconds}s`
}

export function orderStatus(o: Pick<ScheduledOrder, 'cancelled' | 'executed' | 'count' | 'nextTime'>, nowSec: number): OrderStatus {
  if (o.cancelled) return { state: 'cancelled', label: 'Cancelled' }
  if (o.executed >= o.count) return { state: 'done', label: 'Done' }
  const wait = o.nextTime - nowSec
  return { state: 'active', label: wait <= 0 ? 'Due now' : `Next run in ${durationLabel(wait)}` }
}

export function mergeSettled<T>(results: PromiseSettledResult<T[]>[]): T[] {
  return results.flatMap((r) => (r.status === 'fulfilled' ? r.value : []))
}

async function ordersOn(chain: Chain, owner: Address): Promise<ScheduledOrder[]> {
  const client = createPublicClient({ chain, transport: http(chain.rpcUrls.default.http[0]) })
  if (!(await client.getCode({ address: SCHEDULER_ADDRESS }))) return []
  const n = await client.readContract({ address: SCHEDULER_ADDRESS, abi: schedulerAbi, functionName: 'nextId' })
  const ids: bigint[] = []
  for (let i = n > MAX_LISTED ? n - MAX_LISTED : 0n; i < n; i++) ids.push(i)
  const all = await Promise.all(
    ids.map((id) => client.readContract({ address: SCHEDULER_ADDRESS, abi: schedulerAbi, functionName: 'getOrder', args: [id] })),
  )
  const mine = all.map((o, i) => ({ ...o, id: ids[i] })).filter((o) => o.owner.toLowerCase() === owner.toLowerCase())
  const tokens = new Map<string, TokenInfo>()
  for (const address of new Set(mine.flatMap((o) => [o.tokenIn, o.tokenOut]))) {
    const [symbol, decimals] = await Promise.all([
      client.readContract({ address, abi: erc20Abi, functionName: 'symbol' }),
      client.readContract({ address, abi: erc20Abi, functionName: 'decimals' }),
    ])
    tokens.set(address, { address, symbol, decimals })
  }
  return mine.map((o) => ({
    chainId: chain.id,
    network: chain.name,
    id: o.id,
    tokenIn: tokens.get(o.tokenIn)!,
    tokenOut: tokens.get(o.tokenOut)!,
    amountIn: o.amountIn,
    minOut: o.minOut,
    interval: Number(o.interval),
    count: o.count,
    executed: o.executed,
    nextTime: Number(o.nextTime),
    cancelled: o.cancelled,
  }))
}

/** The owner's orders on every Sandbox fork; a fork that's down just contributes none. */
export async function readOrders(owner: Address): Promise<ScheduledOrder[]> {
  return mergeSettled(await Promise.allSettled(sandboxChains.map((c) => ordersOn(c, owner))))
}
```

`apps/wallet/src/chain/useScheduledOrders.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import type { Address } from '@/types'
import { readOrders } from './scheduler'

export function useScheduledOrders(address?: Address) {
  return useQuery({
    queryKey: ['scheduled-orders', address],
    queryFn: () => readOrders(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  })
}
```

- [ ] **Step 3: Run tests**

Run: `pnpm --filter wallet test`
Expected: `scheduler.test.ts` PASS.

- [ ] **Step 4: Rewrite `TasksSheet` to show on-chain orders**

`apps/wallet/src/components/TasksSheet.tsx`:

```tsx
import { Repeat } from 'lucide-react'
import { formatUnits } from 'viem'
import { Badge } from '@/components/ui/badge'
import { BOTTOM_SHEET } from '@/components/sheet-styles'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { durationLabel, orderStatus, type ScheduledOrder } from '@/chain/scheduler'
import { formatAmount } from '@/lib/format'

type Props = { open: boolean; onOpenChange: (v: boolean) => void; orders: ScheduledOrder[]; loading: boolean }

export function TasksSheet({ open, onOpenChange, orders, loading }: Props) {
  const now = Math.floor(Date.now() / 1000)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className={BOTTOM_SHEET}>
        <SheetHeader>
          <SheetTitle>Scheduled tasks</SheetTitle>
          <SheetDescription>Scheduled swaps run on-chain — this tab doesn’t need to stay open. To cancel one, ask in chat.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {orders.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {loading ? 'Loading…' : 'No scheduled swaps yet. Try “Swap 10 USDC to AVAX every minute, 3 times”.'}
            </p>
          ) : (
            <ul className="divide-y">
              {orders.map((o) => {
                const status = orderStatus(o, now)
                const amount = formatAmount(Number(formatUnits(o.amountIn, o.tokenIn.decimals)))
                return (
                  <li key={`${o.chainId}-${o.id}`} className="flex items-center gap-3 py-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <Repeat className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        <span className="font-mono">{amount}</span> {o.tokenIn.symbol} → {o.tokenOut.symbol}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {o.count > 1 ? `Every ${durationLabel(o.interval)} · ` : ''}
                        {o.executed}/{o.count} done · {o.network}
                      </p>
                    </div>
                    <Badge variant={status.state === 'active' ? 'default' : 'secondary'}>{status.label}</Badge>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 5: Wire `WalletPage`**

In `apps/wallet/src/routes/WalletPage.tsx`:
- Remove `const [tasks, setTasks] = useStored<Task[]>(KEYS.tasks, [])` and drop `Task` from the `@/types` import.
- Add imports `import { orderStatus } from '@/chain/scheduler'` and `import { useScheduledOrders } from '@/chain/useScheduledOrders'`.
- Replace `const activeTasks = tasks.filter((t) => t.status === 'active').length` with:

```tsx
  const { data: orders = [], isLoading: ordersLoading } = useScheduledOrders(active?.address)
  const nowSec = Math.floor(Date.now() / 1000)
  const activeTasks = orders.filter((o) => orderStatus(o, nowSec).state === 'active').length
```

- Replace `<TasksSheet {...panelProps('tasks')} tasks={tasks} onChange={setTasks} />` with `<TasksSheet {...panelProps('tasks')} orders={orders} loading={ordersLoading} />`.

- [ ] **Step 6: Remove the DCA mock**

In `apps/wallet/src/mock/agent.ts`: delete the `DCA` regex constant and the `if ((m = text.match(DCA))) { … }` branch; delete `capitalize` if nothing else uses it. In `apps/wallet/src/mock/agent.test.ts`: delete the test that sends `'Buy ETH every Monday with 50 USDC'`. In `apps/wallet/src/mock/fixtures.ts` `EXAMPLES`: replace `'Buy ETH every Monday with 50 USDC'` with `'Swap 10 USDC to AVAX every minute, 3 times'`.

- [ ] **Step 7: Un-skip the cross-file pin test, run everything**

Remove the `@pytest.mark.skip` from `test_pinned_addresses_agree_everywhere` in `agent/tests/test_scheduler.py`.

Run: `pnpm --filter wallet test && pnpm build && pnpm lint && uv run --directory agent pytest tests/test_scheduler.py -q`
Expected: all PASS, no lint errors.

- [ ] **Step 8: Commit**

```bash
git add apps/wallet/src agent/tests/test_scheduler.py
git commit -m "feat(wallet): Scheduled tasks sheet shows on-chain scheduled swaps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Docs + end-to-end manual check

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update `CLAUDE.md`**

- Stack & layout: add `- \`contracts/\` — Foundry: \`SwapScheduler\` + isolated \`Swapper\` (permissionless scheduled swaps). Deployed by \`pnpm dev:sandbox\` via CREATE2 at the same address on both forks.`
- Commands block: add `pnpm dev:executor             # scheduled-swap executor (needs dev:sandbox)` and `pnpm test:contracts           # forge tests`.
- Real vs mock: move "scheduled tasks" from Mock to Real (`chain/scheduler.ts`, `agent/lazyagent/scheduler.py`, `executor.py`); Mock keeps only WalletConnect. Replace "Scheduled tasks only run while the tab is open." with "Scheduled swaps run on-chain via the executor; the tab can be closed."
- Add convention: `- The scheduler address is pinned in four files (Deployment.sol, anvil + agent scheduler.py, chain/scheduler.ts). Changing contract bytecode means re-pinning all four — forge and pytest tests fail until you do.`

- [ ] **Step 2: Update `README.md`**

Status line: scheduled swaps are real (on-chain `SwapScheduler`, executor service); WalletConnect still mocked. Add `pnpm dev:executor` to the run instructions next to `dev:sandbox` / `dev:agent`.

- [ ] **Step 3: Manual end-to-end check (spec success criteria)**

With `pnpm dev:sandbox`, `pnpm dev:agent`, `pnpm dev:executor`, `pnpm dev` running:
1. Sandbox log shows `SwapScheduler deployed <addr> on Ethereum` and the same `<addr>` on Avalanche.
2. In the wallet: "Give me test funds", then "Swap 10 USDC to AVAX every minute, 3 times" → one card (Allow USDC, Schedule swap) → Approve.
3. Close the tab. The executor log shows `Avalanche: executed order #N` three times about a minute apart.
4. Reopen: Scheduled tasks shows `3/3 done · Avalanche` / Done; balance shows WAVAX.
5. "Swap 0.01 ETH to USDC every minute, 5 times" → card with Wrap ETH → WETH, Allow WETH, Schedule swap; after one run, "cancel my scheduled swap" → list → cancel card → Approve; no further runs.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: on-chain scheduled swaps, executor and contracts commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
