"""Live end-to-end check through the real model, using your Claude Code login.

Prereqs: `pnpm dev:sandbox` running, and a test wallet from
`uv run --directory anvil python scripts/seed.py`.
Usage: uv run --directory agent python scripts/demo.py
"""

import asyncio
import json

from web3 import AsyncHTTPProvider, AsyncWeb3

from lazyagent.chain import RpcChain
from lazyagent.claude import connect_claude
from lazyagent.config import ROOT, load_settings
from lazyagent.devsigner import execute_steps
from lazyagent.session import Session

ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
PROMPTS = ["What's my balance?", "Send 0.01 ETH to Alice", "Swap 0.5 ETH to USDC", "Swap 100 USDC to ETH"]


async def main() -> None:
    settings = load_settings()
    wallet = json.loads((ROOT / "anvil" / ".test-wallet.json").read_text())
    w3 = AsyncWeb3(AsyncHTTPProvider(settings.rpc_url))
    turn_done = asyncio.Event()
    session: Session

    async def approve(msg: dict) -> None:
        result = await execute_steps(w3, wallet["private_key"], msg["tx"]["steps"])
        print(f"\n  [auto-approved {len(msg['tx']['steps'])} step(s): {result.get('status') or result.get('error')}]")
        await session.handle({"type": "tx_result", "id": msg["id"], **result})

    async def send(msg: dict) -> None:
        kind = msg["type"]
        if kind == "text_delta":
            print(msg["text"], end="", flush=True)
        elif kind == "confirm":
            print(f"\n  [confirm card: {msg['tx']['title']}]", end="")
            asyncio.create_task(approve(msg))
        elif kind == "balances":
            print(f"\n  [balance card: {msg['holdings']}]")
        elif kind == "error":
            print(f"\n  [error: {msg['message']}]")
        elif kind == "turn_end":
            print()
            turn_done.set()

    async def factory(tools):
        return await connect_claude(tools, settings)

    session = Session(send, RpcChain(settings.rpc_url), factory)
    try:
        for prompt in PROMPTS:
            print(f"\n> {prompt}")
            turn_done.clear()
            await session.handle(
                {"type": "user", "text": prompt, "spoken": False, "address": wallet["address"], "contacts": [{"name": "Alice", "address": ALICE}]}
            )
            await turn_done.wait()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
