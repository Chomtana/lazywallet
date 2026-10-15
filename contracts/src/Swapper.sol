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
/// It holds no user allowances and no balances between runs (everything is swept to the owner), so arbitrary calldata
/// can't reach anyone's approvals. Approvals the Swapper itself grants during a run may persist, so a later run whose
/// route calls untrusted code could pull that run's in-flight funds; each order's minOut check bounds the damage.
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
