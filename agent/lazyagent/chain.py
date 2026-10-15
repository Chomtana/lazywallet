from typing import Protocol

from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .tokens import ETH, Token
from .uniswap import ZERO, ChainQuoter, best_route, currency_of

ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]
AGGREGATOR_ABI = [
    {
        "name": "latestRoundData",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
    }
]
FEED_DECIMALS = 8


class Chain(Protocol):
    async def eth_balance(self, address: str) -> int: ...
    async def token_balance(self, token: Token, address: str) -> int: ...
    async def price_usd(self, token: Token) -> float: ...
    async def gas_price(self) -> int: ...
    async def is_sandbox(self) -> bool: ...
    async def call(self, to: str, data: str, gas: int | None = None) -> bytes: ...
    async def block_timestamp(self) -> int: ...


class RpcChain:
    def __init__(self, rpc_url: str, poa: bool = False):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        if poa:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Avalanche blocks carry long extraData

    async def eth_balance(self, address: str) -> int:
        return await self.w3.eth.get_balance(Web3.to_checksum_address(address))

    async def token_balance(self, token: Token, address: str) -> int:
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(token.address), abi=ERC20_ABI)
        return await contract.functions.balanceOf(Web3.to_checksum_address(address)).call()

    async def price_usd(self, token: Token) -> float:
        if token.fixed_price is not None:
            return token.fixed_price
        if token.price_feed is None:
            return await self._pool_price(token)
        feed = self.w3.eth.contract(address=Web3.to_checksum_address(token.price_feed), abi=AGGREGATOR_ABI)
        _, answer, _, _, _ = await feed.functions.latestRoundData().call()
        return answer / 10**FEED_DECIMALS

    async def _pool_price(self, token: Token) -> float:
        """Tokens without a Chainlink feed: 1 token → ETH on the best v4 route, times ETH/USD."""
        found = await best_route(ChainQuoter(self), currency_of(token), ZERO, 10**token.decimals)
        if found is None:
            return 0.0
        return found[1] / 10**18 * await self.price_usd(ETH)

    async def gas_price(self) -> int:
        return await self.w3.eth.gas_price

    async def call(self, to: str, data: str, gas: int | None = None) -> bytes:
        tx = {"to": Web3.to_checksum_address(to), "data": data}
        if gas is not None:
            tx["gas"] = gas
        return bytes(await self.w3.eth.call(tx))

    async def block_timestamp(self) -> int:
        """Timestamp the next block will get — Anvil mines only on transactions, so `latest` goes stale while idle."""
        return (await self.w3.eth.get_block("pending"))["timestamp"]

    async def is_sandbox(self) -> bool:
        """True only for a local Anvil node — the faucet must never run against a real network."""
        try:
            res = await self.w3.provider.make_request("web3_clientVersion", [])
        except Exception:
            return False
        return str(res.get("result", "")).lower().startswith("anvil")
