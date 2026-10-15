import os
import subprocess
import sys

import uvicorn

from .faucet import create_app
from .rpc import AVAX_CHAIN_ID, AVAX_PUBLIC_RPC, anvil_command, load_env, wait_for_rpc
from .scheduler import SCHEDULER, ensure_scheduler

ANVIL_PORT = 8545
AVAX_PORT = 8546
FAUCET_PORT = 8547


def main() -> None:
    load_env()
    fork_url = os.environ.get("ETH_RPC_URL")
    if not fork_url:
        sys.exit("ETH_RPC_URL is missing — add a mainnet archive RPC to .env (see .env.example).")
    avax_url = os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC
    origins = os.environ.get("WALLET_ORIGINS", "http://localhost:5174").split(",")
    procs = [
        subprocess.Popen(anvil_command(fork_url, os.environ.get("FORK_BLOCK") or None, ANVIL_PORT)),
        subprocess.Popen(anvil_command(avax_url, None, AVAX_PORT, AVAX_CHAIN_ID)),
    ]
    rpc = f"http://127.0.0.1:{ANVIL_PORT}"
    avax_rpc = f"http://127.0.0.1:{AVAX_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        wait_for_rpc(avax_rpc, 120, AVAX_CHAIN_ID)
        for name, url in (("Ethereum", rpc), ("Avalanche", avax_rpc)):
            try:
                verb = "deployed" if ensure_scheduler(url) else "already at"
                print(f"SwapScheduler {verb} {SCHEDULER} on {name}", flush=True)
            except Exception as e:
                print(f"SwapScheduler deploy FAILED on {name} — scheduled swaps disabled there: {e}", flush=True)
        print(
            f"Sandbox ready: Ethereum fork {rpc} (chain id 1), Avalanche fork {avax_rpc} (chain id {AVAX_CHAIN_ID}), "
            f"faucet http://127.0.0.1:{FAUCET_PORT}",
            flush=True,
        )
        uvicorn.run(create_app(rpc, origins, avax_rpc), host="127.0.0.1", port=FAUCET_PORT)
    finally:
        for p in procs:
            p.terminate()
            p.wait()
