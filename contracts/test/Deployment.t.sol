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
