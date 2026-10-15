import asyncio

from eth_abi import encode
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.dexalot import SandboxQuotes
from lazyagent.proposals import Proposals
from lazyagent.swaps import display_units
from lazyagent.tokens import AVAX_TOKENS, find_token
from lazyagent.tools import WalletContext, WalletTools

USDC = find_token("USDC", AVAX_TOKENS)


async def run_swap(avax_sandbox, args: dict, usdc: int = 0):
    rpc, sandbox_url = avax_sandbox
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, 9])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [USDC.address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    proposals = Proposals()
    seen = []

    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(rpc, poa=True)
    tools = WalletTools(FakeChain(), send, WalletContext(address=account.address), proposals, approval_timeout=120,
                        avalanche=chain, dexalot=SandboxQuotes(sandbox_url))
    result = await tools.propose_swap(args)
    return result["content"][0]["text"], seen, chain, account


async def test_avax_to_usdc_receives_exactly_the_signed_amount(avax_sandbox):
    text, seen, chain, account = await run_swap(avax_sandbox, {"token_in": "AVAX", "token_out": "USDC", "amount": "1"})
    assert "Swapped 1 AVAX for" in text, text
    received = await chain.token_balance(USDC, account.address)
    assert received > 1_000_000  # > $1
    rows = {r["label"]: r["value"] for r in seen[0]["tx"]["rows"]}
    assert rows["Receive exactly"] == f"{display_units(received, 6)} USDC"


async def test_usdc_to_avax_with_approval(avax_sandbox):
    text, seen, chain, account = await run_swap(avax_sandbox, {"token_in": "USDC", "token_out": "AVAX", "amount": "10"}, usdc=50 * 10**6)
    rows = {r["label"]: r["value"] for r in seen[0]["tx"]["rows"]}
    assert f"Swapped 10 USDC for {rows['Receive exactly']}." in text, text  # the signed amount, not a gas-reduced delta
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Swap USDC → AVAX"]
    assert await chain.token_balance(USDC, account.address) == 40 * 10**6
