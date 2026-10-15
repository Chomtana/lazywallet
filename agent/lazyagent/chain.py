from typing import Protocol

from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from .tokens import Token

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


class RpcChain:
    def __init__(self, rpc_url: str):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

    async def eth_balance(self, address: str) -> int:
        return await self.w3.eth.get_balance(Web3.to_checksum_address(address))

    async def token_balance(self, token: Token, address: str) -> int:
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(token.address), abi=ERC20_ABI)
        return await contract.functions.balanceOf(Web3.to_checksum_address(address)).call()

    async def price_usd(self, token: Token) -> float:
        if token.fixed_price is not None:
            return token.fixed_price
        feed = self.w3.eth.contract(address=Web3.to_checksum_address(token.price_feed), abi=AGGREGATOR_ABI)
        _, answer, _, _, _ = await feed.functions.latestRoundData().call()
        return answer / 10**FEED_DECIMALS

    async def gas_price(self) -> int:
        return await self.w3.eth.gas_price

    async def is_sandbox(self) -> bool:
        """True only for a local Anvil node — the faucet must never run against a real network."""
        try:
            res = await self.w3.provider.make_request("web3_clientVersion", [])
        except Exception:
            return False
        return str(res.get("result", "")).lower().startswith("anvil")
