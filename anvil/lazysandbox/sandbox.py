import os
import subprocess
import sys

import uvicorn

from .faucet import create_app
from .rpc import anvil_command, load_env, wait_for_rpc

ANVIL_PORT = 8545
FAUCET_PORT = 8547


def main() -> None:
    load_env()
    fork_url = os.environ.get("ETH_RPC_URL")
    if not fork_url:
        sys.exit("ETH_RPC_URL is missing — add a mainnet archive RPC to .env (see .env.example).")
    origins = os.environ.get("WALLET_ORIGINS", "http://localhost:5174").split(",")
    proc = subprocess.Popen(anvil_command(fork_url, os.environ.get("FORK_BLOCK") or None, ANVIL_PORT))
    rpc = f"http://127.0.0.1:{ANVIL_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        print(f"Sandbox ready: Anvil fork {rpc} (chain id 1), faucet http://127.0.0.1:{FAUCET_PORT}")
        uvicorn.run(create_app(rpc, origins), host="127.0.0.1", port=FAUCET_PORT)
    finally:
        proc.terminate()
        proc.wait()
