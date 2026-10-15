"""Reset the running sandbox back to the mainnet fork (drops all local transactions).

Usage: uv run --directory anvil python scripts/reset.py
"""

import os

from web3 import HTTPProvider, Web3

from lazysandbox.rpc import load_env

RPC = "http://127.0.0.1:8545"


def main() -> None:
    load_env()
    forking = {"jsonRpcUrl": os.environ["ETH_RPC_URL"]}
    if os.environ.get("FORK_BLOCK"):
        forking["blockNumber"] = int(os.environ["FORK_BLOCK"])
    res = Web3(HTTPProvider(RPC)).provider.make_request("anvil_reset", [{"forking": forking}])
    if "error" in res:
        raise SystemExit(f"Reset failed: {res['error']}")
    print("Sandbox reset to fork.")


if __name__ == "__main__":
    main()
