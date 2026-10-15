from eth_abi import encode

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
        self.prices: dict[str, float | None] = dict(PRICES)
        self.sim_out: int | Exception = 0  # what a simulated Kyber swap returns (or raises)
        self.sim_calls: list[tuple[dict, dict | None]] = []
        self.access_keys: list[str] = []  # storage slots eth_createAccessList reports
        self.allowance_slot: str | None = None  # the one that really holds allowance(owner, ROUTER)

    async def eth_balance(self, address: str) -> int:
        if self.fail:
            raise ConnectionError("connection refused")
        return self.eth

    async def token_balance(self, token: Token, address: str) -> int:
        if self.fail_balance_reads:
            raise ConnectionError("rpc hiccup")
        return self.tokens.get(token.symbol, 0)

    async def price_usd(self, token: Token) -> float | None:
        return self.prices.get(token.symbol, 1.0)

    async def gas_price(self) -> int:
        return self.gp

    async def is_sandbox(self) -> bool:
        return self.sandbox

    async def call(self, to: str, data: str, gas: int | None = None) -> bytes:
        return self.call_responses.get(data[:10], bytes(96))

    async def block_timestamp(self) -> int:
        return self.now

    async def simulate(self, tx: dict, overrides: dict | None = None) -> bytes:
        self.sim_calls.append((tx, overrides))
        if tx["data"].startswith("0xdd62ed3e"):  # allowance(): only an override of the real slot counts
            diff = next(iter((overrides or {}).values()), {}).get("stateDiff", {})
            return int(diff.get(self.allowance_slot, "0x0"), 16).to_bytes(32, "big")
        if isinstance(self.sim_out, Exception):
            raise self.sim_out
        return encode(["uint256", "uint256"], [self.sim_out, 150_000])

    async def storage_keys(self, to: str, data: str) -> list[str]:
        return self.access_keys


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
