"""End to end on fresh forks with the real KyberSwap API, one token per chain: COQ on Avalanche (buy by address,
see it in balances, sell it) and PEPE on Ethereum (buy by address, see it in balances). Two live routes on Ethereum."""

import asyncio

import pytest
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

from fakes import FakeChain
from lazyagent.chain import RpcChain
from lazyagent.devsigner import execute_steps
from lazyagent.kyber import NATIVE, KyberClient, usd_price
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.tokens import Token, find_token
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.transfers import TransferError

COQ = "0x420FcA0121DC28039145009570975747295f2329"
PEPE = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
USDC = find_token("USDC", AVALANCHE.tokens)


class RecordingKyber(KyberClient):
    def __init__(self):
        super().__init__()
        self.built: list[dict] = []

    async def build(self, network, summary, sender, slippage_bps):
        data = await super().build(network, summary, sender, slippage_bps)
        self.built.append(data)
        return data


async def test_buy_hold_and_sell_a_memecoin_through_kyberswap(avax_fork_rpc):
    kyber = RecordingKyber()
    try:
        await kyber.route("avalanche", NATIVE, COQ, 10**18)
    except TransferError as e:
        pytest.skip(f"KyberSwap API not reachable: {e}")
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    proposals = Proposals()
    seen: list[dict] = []
    balances: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "balances":
            balances.append(msg)
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(avax_fork_rpc, poa=True, custom_price=usd_price(kyber, AVALANCHE))
    ctx = WalletContext(address=account.address)
    tools = WalletTools(FakeChain(), send, ctx, proposals, approval_timeout=120, avalanche=chain, kyber=kyber)

    # Buy by contract address: one Kyber step, received within 5% of the quote.
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ, "amount": "1"})
    text = result["content"][0]["text"]
    assert "Swapped 1 AVAX for" in text, text
    buy = seen[0]["tx"]
    assert [s["label"] for s in buy["steps"]] == ["Swap AVAX → COQ"]
    assert {"label": "COQ address", "value": COQ} in buy["rows"]
    held = await chain.token_balance(Token("COQ", COQ, 18, custom=True), account.address)
    quoted = int(kyber.built[0]["amountOut"])
    assert abs(held - quoted) * 100 <= quoted * 5

    # The wallet saves addToken; with it, balances list COQ with a USD price.
    ctx.tokens = [buy["addToken"]]
    await tools.get_balances({})
    coq = next(h for h in balances[-1]["holdings"] if h["symbol"] == "COQ")
    assert coq["network"] == "Avalanche" and coq["usdPrice"] and coq["usdPrice"] > 0

    # Sell half for USDC: approve + swap, simulated beforehand with an allowance override.
    half = str(held // 2 // 10**18)
    result = await tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": half})
    assert "Swapped" in result["content"][0]["text"], result
    assert [s["label"] for s in seen[1]["tx"]["steps"]] == ["Allow COQ", "Swap COQ → USDC"]
    assert await chain.token_balance(USDC, account.address) > 0


async def test_buy_a_memecoin_through_kyberswap_on_ethereum(fork_rpc):
    kyber = RecordingKyber()
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    account = Account.create()  # Kyber rejects Anvil's well-known dev accounts
    await w3.provider.make_request("anvil_setBalance", [account.address, hex(10 * 10**18)])
    proposals = Proposals()
    seen: list[dict] = []
    balances: list[dict] = []

    async def send(msg: dict) -> None:
        if msg["type"] == "balances":
            balances.append(msg)
        if msg["type"] == "confirm":
            seen.append(msg)

            async def approve() -> None:
                proposals.resolve(msg["id"], await execute_steps(w3, account.key.to_0x_hex(), msg["tx"]["steps"]))

            asyncio.create_task(approve())

    chain = RpcChain(fork_rpc, custom_price=usd_price(kyber, ETHEREUM))
    ctx = WalletContext(address=account.address)
    tools = WalletTools(chain, send, ctx, proposals, approval_timeout=120, kyber=kyber)

    # Live route 1 (+ build): buy PEPE by contract address.
    result = await tools.propose_swap({"token_in": "ETH", "token_out": PEPE, "amount": "0.1"})
    text = result["content"][0]["text"]
    if "KyberSwap isn't reachable" in text:
        pytest.skip(text)
    assert "Swapped 0.1 ETH for" in text, text
    buy = seen[0]["tx"]
    assert [s["label"] for s in buy["steps"]] == ["Swap ETH → PEPE"]
    assert buy["steps"][0]["request"]["chainId"] == 1
    assert {"label": "PEPE address", "value": PEPE} in buy["rows"]
    held = await chain.token_balance(Token("PEPE", PEPE, 18, custom=True), account.address)
    quoted = int(kyber.built[0]["amountOut"])
    assert abs(held - quoted) * 100 <= quoted * 5

    # Live route 2: the USD price for the balance card (1 USDC → PEPE, inverted).
    ctx.tokens = [buy["addToken"]]
    await tools.get_balances({})
    pepe = next(h for h in balances[-1]["holdings"] if h["symbol"] == "PEPE")
    assert pepe["network"] == "Ethereum" and pepe["usdPrice"] and pepe["usdPrice"] > 0
