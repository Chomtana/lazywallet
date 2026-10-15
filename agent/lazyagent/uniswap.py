"""Uniswap v4 on Ethereum mainnet (and the Sandbox fork): addresses, calldata and route search.

Recipe verified on a mainnet fork: UniversalRouter.execute with V4_SWAP, hookless pools, native ETH = address(0).
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from eth_abi import decode, encode
from web3 import Web3

from .tokens import TOKENS, Token

ZERO = "0x0000000000000000000000000000000000000000"
UNIVERSAL_ROUTER = Web3.to_checksum_address("0x66a9893cc07d91d95644aedd05d03f95e1dba8af")
PERMIT2 = Web3.to_checksum_address("0x000000000022D473030F116dDEE9F6B43aC78BA3")
V4_QUOTER = Web3.to_checksum_address("0x52f0e24d1c21c8a0cb1e5a5dd6198556bd9e1203")
FEE_TIERS = ((100, 1), (500, 10), (3000, 60), (10000, 200))
# Real quotes use ≤ ~250k gas. Without a cap, an initialized-but-empty pool makes the quoter sweep the whole
# tick bitmap — thousands of cold storage reads that take minutes on a fresh fork.
QUOTE_GAS = 1_000_000

V4_SWAP = 0x10
SWAP_EXACT_IN_SINGLE, SWAP_EXACT_IN, SETTLE_ALL, TAKE_ALL = 0x06, 0x07, 0x0C, 0x0F
TAKE = 0x0E
WRAP_ETH = 0x0B  # Universal Router command
MSG_SENDER = "0x0000000000000000000000000000000000000001"
ADDRESS_THIS = "0x0000000000000000000000000000000000000002"
CONTRACT_BALANCE = 1 << 255
OPEN_DELTA = 0
POOL_KEY = "(address,address,uint24,int24,address)"
PATH_KEY = "(address,uint24,int24,address,bytes)"
WETH_DEPOSIT = "0xd0e30db0"


@dataclass(frozen=True)
class Hop:
    fee: int
    tick_spacing: int


@dataclass(frozen=True)
class Route:
    currencies: tuple[str, ...]  # input, optional intermediate, output
    hops: tuple[Hop, ...]


def _call(signature: str, types: list[str], values: list) -> str:
    return "0x" + (Web3.keccak(text=signature)[:4] + encode(types, values)).hex()


def currency_of(token: Token) -> str:
    return ZERO if token.address is None else Web3.to_checksum_address(token.address)


def symbol_of(currency: str) -> str:
    if int(currency, 16) == 0:
        return "ETH"
    return next(t.symbol for t in TOKENS if t.address and t.address.lower() == currency.lower())


def pool_key(a: str, b: str, hop: Hop) -> tuple:
    c0, c1 = sorted((a, b), key=lambda c: int(c, 16))
    return (c0, c1, hop.fee, hop.tick_spacing, ZERO)


def pool_id(key: tuple) -> str:
    return Web3.keccak(encode(["address", "address", "uint24", "int24", "address"], list(key))).to_0x_hex()


def _path(route: Route) -> list[tuple]:
    return [(route.currencies[i + 1], h.fee, h.tick_spacing, ZERO, b"") for i, h in enumerate(route.hops)]


def encode_swap(route: Route, amount_in: int, min_out: int, deadline: int, wrap_output: bool = False) -> str:
    """wrap_output (route must end in native ETH): TAKE the ETH into the router, then WRAP_ETH all of it to the caller
    as WETH — for the scheduler's Swapper, whose orders pay out WETH."""
    cin, cout = route.currencies[0], route.currencies[-1]
    if len(route.hops) == 1:
        key = pool_key(cin, cout, route.hops[0])
        swap = encode([f"({POOL_KEY},bool,uint128,uint128,bytes)"], [(key, cin == key[0], amount_in, min_out, b"")])
        first = SWAP_EXACT_IN_SINGLE
    else:
        swap = encode([f"(address,{PATH_KEY}[],uint128,uint128)"], [(cin, _path(route), amount_in, min_out)])
        first = SWAP_EXACT_IN
    settle = encode(["address", "uint256"], [cin, amount_in])
    if wrap_output:
        assert cout == ZERO, "wrap_output needs a route ending in native ETH"
        actions = bytes([first, SETTLE_ALL, TAKE])
        take = encode(["address", "address", "uint256"], [cout, ADDRESS_THIS, OPEN_DELTA])
        commands, extra = bytes([V4_SWAP, WRAP_ETH]), [encode(["address", "uint256"], [MSG_SENDER, CONTRACT_BALANCE])]
    else:
        actions = bytes([first, SETTLE_ALL, TAKE_ALL])
        take = encode(["address", "uint256"], [cout, min_out])
        commands, extra = bytes([V4_SWAP]), []
    v4_input = encode(["bytes", "bytes[]"], [actions, [swap, settle, take]])
    return _call("execute(bytes,bytes[],uint256)", ["bytes", "bytes[]", "uint256"], [commands, [v4_input, *extra], deadline])


def encode_quote(route: Route, amount_in: int) -> str:
    cin, cout = route.currencies[0], route.currencies[-1]
    if len(route.hops) == 1:
        key = pool_key(cin, cout, route.hops[0])
        params = f"({POOL_KEY},bool,uint128,bytes)"
        return _call(f"quoteExactInputSingle({params})", [params], [(key, cin == key[0], amount_in, b"")])
    params = f"(address,{PATH_KEY}[],uint128)"
    return _call(f"quoteExactInput({params})", [params], [(cin, _path(route), amount_in)])


def decode_quote(data: bytes) -> int:
    return decode(["uint256", "uint256"], data)[0]


def encode_erc20_approve(spender: str, amount: int) -> str:
    return _call("approve(address,uint256)", ["address", "uint256"], [spender, amount])


def encode_permit2_approve(token: str, spender: str, amount: int, expiration: int) -> str:
    return _call("approve(address,address,uint160,uint48)", ["address", "address", "uint160", "uint48"], [token, spender, amount, expiration])


def encode_erc20_allowance(owner: str, spender: str) -> str:
    return _call("allowance(address,address)", ["address", "address"], [owner, spender])


def encode_permit2_allowance(owner: str, token: str, spender: str) -> str:
    return _call("allowance(address,address,address)", ["address", "address", "address"], [owner, token, spender])


def decode_permit2_allowance(data: bytes) -> tuple[int, int]:
    amount, expiration, _nonce = decode(["uint160", "uint48", "uint48"], data)
    return amount, expiration


def encode_weth_withdraw(amount: int) -> str:
    return _call("withdraw(uint256)", ["uint256"], [amount])


def candidate_routes(cin: str, cout: str) -> list[Route]:
    routes = [Route((cin, cout), (Hop(f, t),)) for f, t in FEE_TIERS]
    if ZERO not in (cin, cout):
        routes += [Route((cin, ZERO, cout), (Hop(*a), Hop(*b))) for a in FEE_TIERS for b in FEE_TIERS]
    return routes


class Quoter(Protocol):
    async def quote(self, route: Route, amount_in: int) -> int | None: ...


class ChainQuoter:
    """Quotes through V4Quoter with eth_call; a missing or empty pool yields None."""

    def __init__(self, chain) -> None:
        self.chain = chain

    async def quote(self, route: Route, amount_in: int) -> int | None:
        try:
            out = decode_quote(await self.chain.call(V4_QUOTER, encode_quote(route, amount_in), gas=QUOTE_GAS))
        except Exception:
            return None
        return out or None


async def best_route(quoter: Quoter, cin: str, cout: str, amount_in: int) -> tuple[Route, int] | None:
    routes = candidate_routes(cin, cout)
    quotes = await asyncio.gather(*(quoter.quote(r, amount_in) for r in routes))
    found = [(q, i) for i, q in enumerate(quotes) if q]
    if not found:
        return None
    out, i = max(found)
    return routes[i], out
