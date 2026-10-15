"""Create a fresh random test wallet on the running sandbox and fund it.

Usage: uv run --directory anvil python scripts/seed.py
Writes anvil/.test-wallet.json (gitignored).
"""

import asyncio
import json

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazysandbox.faucet import fund, summarize
from lazysandbox.rpc import ROOT

RPC = "http://127.0.0.1:8545"


async def main() -> None:
    account = Account.create()
    funded = await fund(AsyncWeb3(AsyncHTTPProvider(RPC)), account.address)
    out = ROOT / "anvil" / ".test-wallet.json"
    out.write_text(json.dumps({"address": account.address, "private_key": account.key.to_0x_hex()}, indent=2))
    print(f"Test wallet {account.address} funded with {summarize(funded)} → {out}")


if __name__ == "__main__":
    asyncio.run(main())
