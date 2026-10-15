from lazyagent.tokens import Token

PRICES = {"ETH": 3200.0, "WETH": 3200.0, "WBTC": 64000.0}


class FakeChain:
    def __init__(self, eth: int = 10 * 10**18, tokens: dict[str, int] | None = None, gas_price: int = 10**9):
        self.eth = eth
        self.tokens = tokens or {}
        self.gp = gas_price
        self.fail = False
        self.sandbox = True

    async def eth_balance(self, address: str) -> int:
        if self.fail:
            raise ConnectionError("connection refused")
        return self.eth

    async def token_balance(self, token: Token, address: str) -> int:
        return self.tokens.get(token.symbol, 0)

    async def price_usd(self, token: Token) -> float:
        return PRICES.get(token.symbol, 1.0)

    async def gas_price(self) -> int:
        return self.gp

    async def is_sandbox(self) -> bool:
        return self.sandbox


class Outbox:
    def __init__(self):
        self.messages: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.messages.append(msg)

    def of_type(self, kind: str) -> list[dict]:
        return [m for m in self.messages if m["type"] == kind]
