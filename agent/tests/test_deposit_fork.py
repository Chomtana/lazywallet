"""Opt-in: the two executable farms end to end on forks, one per chain — Theo on Ethereum (pinned Uniswap v4 pool)
and Avant on Avalanche (real KyberSwap API, simulated on the fork before the card)."""

import asyncio

import pytest
from eth_abi import encode
from eth_account import Account
from test_swap_fork import USDC, funded_account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.kyber import KyberClient
from lazyagent.networks import AVALANCHE
from lazyagent.proposals import Proposals
from lazyagent.tokens import Token, find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.transfers import TransferError

THUSD = Token("thUSD", "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3", 6, custom=True)
STHUSD = Token("sthUSD", "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", 6, custom=True)
AVAX_USDC = find_token("USDC", AVALANCHE.tokens)
AVUSD = Token("avUSD", "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346", 18, custom=True)
SAVUSD = Token("savUSD", "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E", 18, custom=True)
USDC_BALANCE_SLOT = 9  # Circle FiatToken on both chains


def approving(w3, account, proposals: Proposals, seen: list[dict]):
    async def send(msg: dict) -> None:
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    return send


async def test_farm_theo_on_a_fork(fork_rpc):
    w3, account = await funded_account(fork_rpc, usdc=500 * 10**6)
    proposals, seen = Proposals(), []
    chain = RpcChain(fork_rpc)
    tools = WalletTools(chain, approving(w3, account, proposals, seen), WalletContext(address=account.address), proposals, approval_timeout=120)
    result = await tools.propose_deposit({"farm": "theo-thusd", "amount": "100"})
    text = result["content"][0]["text"]
    assert "Staked" in text and "into sthUSD" in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == [
        "Allow USDC", "Allow Uniswap router", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD",
    ]
    rows = {r["label"]: r["value"] for r in seen[0]["tx"]["rows"]}
    assert rows["Route"] == "USDC → thUSD · Uniswap v4 0.01%"
    assert seen[0]["tx"]["summary"]["swap"]["via"] == "Uniswap v4"
    assert await chain.token_balance(USDC, account.address) == 400 * 10**6
    assert await chain.token_balance(STHUSD, account.address) > 0
    assert await chain.token_balance(THUSD, account.address) <= 100 * 10**6 * 15 // 1000  # ≤ 1.5% of the quote left


async def test_farm_avant_on_a_fork(avax_fork_rpc):
    kyber = KyberClient()
    try:
        await kyber.route("avalanche", AVAX_USDC.address, AVUSD.address, 100 * 10**6)
    except TransferError as e:
        pytest.skip(f"KyberSwap has no USDC → avUSD route right now: {e}")
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    key = Web3.keccak(encode(["address", "uint256"], [account.address, USDC_BALANCE_SLOT])).to_0x_hex()
    await w3.provider.make_request("anvil_setStorageAt", [AVAX_USDC.address, key, "0x" + (500 * 10**6).to_bytes(32, "big").hex()])
    proposals, seen = Proposals(), []
    avax = RpcChain(avax_fork_rpc, poa=True)
    tools = WalletTools(FakeChain(), approving(w3, account, proposals, seen), WalletContext(address=account.address), proposals,
                        approval_timeout=120, avalanche=avax, kyber=kyber)
    result = await tools.propose_deposit({"farm": "avant", "amount": "100"})
    text = result["content"][0]["text"]
    assert "Staked" in text and "into savUSD" in text and "Confirmed on Avalanche," in text, text
    assert [s["label"] for s in seen[0]["tx"]["steps"]] == ["Allow USDC", "Swap USDC → avUSD", "Allow avUSD", "Stake avUSD → savUSD"]
    assert await avax.token_balance(AVAX_USDC, account.address) == 400 * 10**6
    assert await avax.token_balance(SAVUSD, account.address) > 0
    assert await avax.token_balance(AVUSD, account.address) <= 100 * 10**18 * 15 // 1000  # ≤ 1.5% of ~100 avUSD left
