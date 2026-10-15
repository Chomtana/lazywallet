"""Deterministic SwapScheduler deployment (contracts/) on the Sandbox forks."""

import subprocess

from web3 import HTTPProvider, Web3

from .rpc import ROOT

# = contracts/src/Deployment.sol (CREATE2, identical on both forks)
SCHEDULER = Web3.to_checksum_address("0xE99d9DFBeA09687AdCDdB9a45914d778f330b513")
SWAPPER = Web3.to_checksum_address("0x4244a49afdBE8d73A3b8e430D5bCCBd6116B998B")
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
    try:
        run(deploy_command(rpc_url), cwd=CONTRACTS, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        tail = "\n".join((e.stderr or e.stdout or "").strip().splitlines()[-20:])
        raise RuntimeError(f"Deploying the SwapScheduler failed (forge exit {e.returncode}):\n{tail}") from e
    if not w3.eth.get_code(SCHEDULER):
        raise RuntimeError(f"SwapScheduler isn't at {SCHEDULER} after deploying — re-pin it (contracts/src/Deployment.sol).")
    return True
