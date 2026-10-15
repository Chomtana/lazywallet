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
