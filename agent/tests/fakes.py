import json

from eth_abi import encode

from lazyagent.kyber import DESC, EXECUTION, NATIVE, ROUTER, SIMPLE_SELECTOR, SWAP_SELECTOR
from lazyagent.swaps import min_out
from lazyagent.transfers import NoRoute

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


EXECUTOR = "0x8F10B468b06c6FD214B65F87778827F7D113f996"


def kyber_desc(src, dst, receiver, amount, min_return, fee_receivers=()):
    return (src, dst, [], [], list(fee_receivers), [1] * len(fee_receivers), receiver, amount, min_return, 0x200, b"")


def swap_data(desc) -> str:
    return "0x" + SWAP_SELECTOR + encode([EXECUTION], [(EXECUTOR, "0x" + "00" * 20, b"\x01", desc, b"")]).hex()


def simple_data(desc) -> str:
    return "0x" + SIMPLE_SELECTOR + encode(["address", DESC, "bytes", "bytes"], [EXECUTOR, desc, b"\x01", b""]).hex()


class FakeKyber:
    """Kyber API stand-in: a 2-hop LFJ route paying `out`, built honestly unless `tamper` edits the description."""

    def __init__(self, out: int = 8_000_000 * 10**18, tamper=None, no_route: bool = False, build_out: int | None = None):
        self.out, self.tamper, self.no_route = out, tamper, no_route
        self.build_out = out if build_out is None else build_out  # what /route/build claims (normally = the route quote)
        self.routes: list[tuple] = []
        self.builds: list[tuple] = []

    async def route(self, network, token_in, token_out, amount):
        self.routes.append((network, token_in, token_out, amount))
        if self.no_route:
            raise NoRoute("KyberSwap has no route for that pair right now (route not found).")
        summary = {"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount), "amountOut": str(self.out),
                   "amountInUsd": "10", "amountOutUsd": "9.9", "gas": "180000",
                   "route": [[{"exchange": "traderjoe-v22"}], [{"exchange": "traderjoe"}]]}
        return {"routerAddress": ROUTER, "routeSummary": summary}

    async def build(self, network, summary, sender, slippage_bps):
        self.builds.append((network, sender, slippage_bps))
        amount = int(summary["amountIn"])
        desc = kyber_desc(summary["tokenIn"], summary["tokenOut"], sender, amount, min_out(self.build_out, slippage_bps))
        if self.tamper:
            desc = self.tamper(desc)
        native = summary["tokenIn"].lower() == NATIVE.lower()
        return {"routerAddress": ROUTER, "data": swap_data(desc), "transactionValue": str(amount if native else 0),
                "amountOut": str(self.build_out), "gas": "180000"}


class FakeSearch:
    def __init__(self, body: dict | None = None):
        self.body = body or {"data": [], "included": []}
        self.calls: list[tuple[str, str]] = []

    async def pools(self, network, query):
        self.calls.append((network, query))
        return self.body


class FakeTrendingSource:
    """Stands in for GeckoTerminal so tests never hit the network."""

    def __init__(self, pools=None, tokens=None):
        self.pools = pools if pools is not None else []
        self.token_bodies = tokens or {}  # network -> tokens/multi JSON
        self.calls: list[tuple] = []
        self.fail = False

    async def meme_pools(self):
        self.calls.append(("meme_pools",))
        if self.fail:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.pools

    async def tokens(self, network, addresses):
        self.calls.append(("tokens", network, tuple(addresses)))
        if self.fail:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.token_bodies.get(network, {})


class FakeLlama:
    """DefiLlama /protocol/{slug} stand-in: slug → body; a missing slug raises like an HTTP error."""

    def __init__(self, bodies: dict | None = None):
        self.bodies = bodies or {}
        self.calls: list[str] = []
        self.fail = False

    async def protocol(self, slug):
        self.calls.append(slug)
        if self.fail or slug not in self.bodies:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.bodies[slug]


class FakeGeckoPools:
    """GeckoTerminal /tokens/{address}/pools stand-in: lower-case address → body; missing raises."""

    def __init__(self, bodies: dict | None = None):
        self.bodies = bodies or {}
        self.calls: list[tuple[str, str]] = []

    async def pools(self, network, address):
        self.calls.append((network, address))
        if address.lower() not in self.bodies:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.bodies[address.lower()]


def assert_friendly(tx: dict) -> dict:
    """A swap/farm confirm card: it has a summary, and neither it nor the rows say Sandbox, minimum or slippage."""
    assert tx.get("summary"), "no summary"
    rows = json.dumps(tx["rows"]).lower()
    assert not any(word in rows for word in ("sandbox", "minimum", "slippage")), tx["rows"]
    assert "sandbox" not in json.dumps(tx["summary"]).lower() and "sandbox" not in tx["title"].lower()
    return tx["summary"]


class FakeTokenomist:
    """Tokenomist stand-in for unlocks.py: bodies from fixtures; buyback/burn keyed by token id (missing raises)."""

    def __init__(self, upcoming: dict, token_list: dict | None = None, buybacks: dict | None = None, burns: dict | None = None):
        self.upcoming_body, self.token_list_body = upcoming, token_list
        self.buybacks, self.burns = buybacks or {}, burns or {}
        self.calls: list[tuple] = []
        self.fail = False

    async def upcoming(self, start, end):
        self.calls.append(("upcoming", start, end))
        if self.fail:
            raise ConnectionError("Tokenomist answered 429")
        return self.upcoming_body

    async def token_list(self, ids):
        self.calls.append(("token_list", tuple(ids)))
        if self.token_list_body is None:
            raise ConnectionError("Tokenomist answered 500")
        return self.token_list_body

    async def buyback(self, token_id, start, end):
        self.calls.append(("buyback", token_id, start, end))
        if token_id not in self.buybacks:
            raise ConnectionError("Tokenomist answered 403")
        return self.buybacks[token_id]

    async def burn(self, token_id, start, end):
        self.calls.append(("burn", token_id, start, end))
        if token_id not in self.burns:
            raise ConnectionError("Tokenomist answered 403")
        return self.burns[token_id]


class FakeCoinList:
    """CoinGecko coins/list?include_platform=true stand-in."""

    def __init__(self, coins: list | None):
        self.coins = coins
        self.calls = 0

    async def coin_list(self):
        self.calls += 1
        if self.coins is None:
            raise ConnectionError("HTTP Error 429: Too Many Requests")
        return self.coins
