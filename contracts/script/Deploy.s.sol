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
