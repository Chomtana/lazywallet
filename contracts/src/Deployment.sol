// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

/// Deterministic deployment constants. SCHEDULER/SWAPPER are also pinned in anvil/lazysandbox/scheduler.py,
/// agent/lazyagent/scheduler.py and apps/wallet/src/chain/scheduler.ts — any bytecode change means re-pinning all four
/// (test/Deployment.t.sol and agent/tests/test_scheduler.py fail until you do).
library Deployment {
    bytes32 internal constant SALT = keccak256("lazywallet.swap-scheduler.v1");
    uint256 internal constant FIXED_GAS = 300_000;
    address internal constant SCHEDULER = 0xE99d9DFBeA09687AdCDdB9a45914d778f330b513;
    address internal constant SWAPPER = 0x4244a49afdBE8d73A3b8e430D5bCCBd6116B998B;
}
