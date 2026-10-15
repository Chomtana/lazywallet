import asyncio

from conftest import deploy_scheduler
from eth_abi import encode
from eth_account import Account
from fakes import FakeChain
from web3 import Web3

from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.dexalot import SandboxQuotes
from lazyagent.executor import Executor, Target
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.scheduler import gas_balance, read_orders, wrapped_token
from lazyagent.tokens import find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import ChainQuoter

USDC_SLOT = 9  # both mainnet USDC and Avalanche native USDC


async def setup_account(w3, usdc_address: str | None = None, usdc: int = 0):
    account = Account.create()
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(20 * 10**18)])
    if usdc:
        key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_SLOT])).to_0x_hex()
        await w3.provider.make_request("anvil_setStorageAt", [usdc_address, key, "0x" + usdc.to_bytes(32, "big").hex()])
    return account


def auto_approve(w3, account, proposals):
    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    return send


async def balance_of(chain, token, address):
    return await chain.token_balance(token, address)


async def warp(w3, seconds: int):
    await w3.provider.make_request("evm_increaseTime", [seconds])
    await w3.provider.make_request("evm_mine", [])


async def test_avalanche_avax_to_usdc_runs_twice(avax_sandbox):
    rpc, url = avax_sandbox
    deploy_scheduler(rpc)
    chain = RpcChain(rpc, poa=True)
    account = await setup_account(chain.w3)
    proposals = Proposals()
    tools = WalletTools(FakeChain(), auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=chain, dexalot=SandboxQuotes(url))
    result = await tools.propose_scheduled_swap({"token_in": "AVAX", "token_out": "USDC", "amount": "1", "interval_seconds": 60, "count": 2})
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    deposit = await gas_balance(chain, account.address)

    ex = Executor([Target(AVALANCHE, chain, chain.w3, None)], SandboxQuotes(url))
    usdc = find_token("USDC", AVALANCHE.tokens)
    assert len(await ex.tick()) == 1
    first = await balance_of(chain, usdc, account.address)
    assert first >= order.min_out
    assert await ex.tick() == []  # not due again yet
    await warp(chain.w3, 61)
    assert len(await ex.tick()) == 1
    assert await balance_of(chain, usdc, account.address) >= first + order.min_out
    [after] = await read_orders(chain, account.address)
    assert after.executed == 2 and not after.active
    assert await gas_balance(chain, account.address) < deposit  # rebates paid


async def test_avalanche_usdc_to_avax_pays_wavax(avax_sandbox):
    rpc, url = avax_sandbox
    deploy_scheduler(rpc)
    chain = RpcChain(rpc, poa=True)
    usdc = find_token("USDC", AVALANCHE.tokens)
    account = await setup_account(chain.w3, usdc.address, 100 * 10**6)
    proposals = Proposals()
    tools = WalletTools(FakeChain(), auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=chain, dexalot=SandboxQuotes(url))
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "AVAX", "amount": "10"})
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    assert len(await Executor([Target(AVALANCHE, chain, chain.w3, None)], SandboxQuotes(url)).tick()) == 1
    assert await balance_of(chain, wrapped_token(AVALANCHE), account.address) >= order.min_out


async def ethereum_run(fork_rpc, args: dict, usdc: int = 0):
    deploy_scheduler(fork_rpc)
    chain = RpcChain(fork_rpc)
    account = await setup_account(chain.w3, find_token("USDC").address, usdc)
    proposals = Proposals()
    tools = WalletTools(chain, auto_approve(chain.w3, account, proposals), WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_scheduled_swap(args)
    assert "Scheduled" in result["content"][0]["text"], result
    [order] = await read_orders(chain, account.address)
    assert len(await Executor([Target(ETHEREUM, chain, chain.w3, ChainQuoter(chain))], None).tick()) == 1
    return chain, account, order


async def test_ethereum_usdc_to_eth_pays_weth(fork_rpc):
    chain, account, order = await ethereum_run(fork_rpc, {"token_in": "USDC", "token_out": "ETH", "amount": "100"}, usdc=1_000 * 10**6)
    assert await balance_of(chain, wrapped_token(ETHEREUM), account.address) >= order.min_out


async def test_ethereum_eth_to_usdc(fork_rpc):
    chain, account, order = await ethereum_run(fork_rpc, {"token_in": "ETH", "token_out": "USDC", "amount": "0.1"})
    assert await balance_of(chain, find_token("USDC"), account.address) >= order.min_out
