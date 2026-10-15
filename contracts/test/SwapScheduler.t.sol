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

    function test_swapperApprovalsPersistButUserAllowancesStayUnreachable() public {
        address attacker = makeAddr("attacker");
        uint256 id = _schedule(_now(), 0, 1, OUT);
        Call[] memory swap = _swapCalls(AMOUNT, OUT, alice);
        Call[] memory calls = new Call[](3);
        calls[0] = Call(address(tin), 0, abi.encodeCall(IERC20.approve, (attacker, type(uint256).max)));
        calls[1] = swap[0];
        calls[2] = swap[1];
        _execute(id, calls);
        // Residual: the Swapper's own approval persists (it holds no funds between runs).
        assertEq(tin.allowance(address(scheduler.swapper()), attacker), type(uint256).max);
        // User funds and allowances are unaffected.
        assertEq(tin.allowance(alice, attacker), 0);
        assertEq(tin.balanceOf(alice), 900e18);
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
