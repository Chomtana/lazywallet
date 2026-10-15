from lazyagent.tokens import Token

PRICES = {"ETH": 3200.0, "WETH": 3200.0, "WBTC": 64000.0}


class FakeChain:
    def __init__(self, eth: int = 10 * 10**18, tokens: dict[str, int] | None = None, gas_price: int = 10**9):
        self.eth = eth
        self.tokens = tokens or {}
        self.gp = gas_price
        self.fail = False
        self.sandbox = True
        self.fail_balance_reads = False
        self.call_responses: dict[str, bytes] = {}
        self.now = 1_700_000_000

    async def eth_balance(self, address: str) -> int:
        if self.fail:
            raise ConnectionError("connection refused")
        return self.eth

    async def token_balance(self, token: Token, address: str) -> int:
        if self.fail_balance_reads:
            raise ConnectionError("rpc hiccup")
        return self.tokens.get(token.symbol, 0)

    async def price_usd(self, token: Token) -> float:
        return PRICES.get(token.symbol, 1.0)

    async def gas_price(self) -> int:
        return self.gp

    async def is_sandbox(self) -> bool:
        return self.sandbox

    async def call(self, to: str, data: str, gas: int | None = None) -> bytes:
        return self.call_responses.get(data[:10], bytes(96))

    async def block_timestamp(self) -> int:
        return self.now


class FakeQuoter:
    def __init__(self, fn):
        self.fn = fn

    async def quote(self, route, amount_in):
        return self.fn(route, amount_in)


class Outbox:
    def __init__(self):
        self.messages: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.messages.append(msg)

    def of_type(self, kind: str) -> list[dict]:
        return [m for m in self.messages if m["type"] == kind]
