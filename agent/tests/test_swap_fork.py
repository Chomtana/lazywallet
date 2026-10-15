import asyncio

from eth_abi import encode
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.proposals import Proposals
from lazyagent.tokens import find_token
from lazyagent.tools import WalletContext, WalletTools

USDC = find_token("USDC")
WBTC = find_token("WBTC")
WETH = find_token("WETH")
USDC_BALANCE_SLOT = 9


async def funded_account(rpc: str, usdc: int = 0):
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc))
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_BALANCE_SLOT])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [USDC.address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    return w3, account


async def swap(rpc: str, w3, account, args: dict) -> tuple[str, list[dict]]:
    proposals = Proposals()
    seen: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    tools = WalletTools(RpcChain(rpc), send, WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_swap(args)
    return result["content"][0]["text"], seen


async def test_eth_to_usdc(fork_rpc):
    w3, account = await funded_account(fork_rpc)
    text, seen = await swap(fork_rpc, w3, account, {"token_in": "ETH", "token_out": "USDC", "amount": "1"})
    assert "Swapped 1 ETH for" in text, text
    assert len(seen[0]["tx"]["steps"]) == 1
    assert await RpcChain(fork_rpc).token_balance(USDC, account.address) > 500 * 10**6


async def test_usdc_to_eth_with_approvals(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=5_000 * 10**6)
    text, seen = await swap(fork_rpc, w3, account, {"token_in": "USDC", "token_out": "ETH", "amount": "1000"})
    assert "Swapped 1000 USDC for about" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Allow Uniswap router", "Swap USDC → ETH"]
    assert await RpcChain(fork_rpc).token_balance(USDC, account.address) == 4_000 * 10**6


async def test_usdc_to_wbtc(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=5_000 * 10**6)
    text, _ = await swap(fork_rpc, w3, account, {"token_in": "USDC", "token_out": "WBTC", "amount": "500"})
    assert "Swapped 500 USDC for" in text, text
    assert await RpcChain(fork_rpc).token_balance(WBTC, account.address) > 0


async def test_wrap_eth(fork_rpc):
    w3, account = await funded_account(fork_rpc)
    text, _ = await swap(fork_rpc, w3, account, {"token_in": "ETH", "token_out": "WETH", "amount": "1"})
    assert "Swapped 1 ETH for 1 WETH" in text, text
    assert await RpcChain(fork_rpc).token_balance(WETH, account.address) == 10**18


LIT = find_token("LIT")


async def test_eth_to_lit(fork_rpc):
    w3, account = await funded_account(fork_rpc)
    text, _ = await swap(fork_rpc, w3, account, {"token_in": "ETH", "token_out": "LIT", "amount": "0.01"})
    assert "Swapped 0.01 ETH for" in text, text
    assert await RpcChain(fork_rpc).token_balance(LIT, account.address) > 0
