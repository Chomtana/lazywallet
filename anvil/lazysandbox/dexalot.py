"""Dexalot SimpleSwap on the Avalanche fork: sandbox-signed orders at Dexalot's live price.

Dexalot only signs firm quotes for addresses holding real mainnet funds, so on the fork we patch the RFQ
makers' immutable swapSigner to a sandbox key and sign orders ourselves. Never used on a real network."""

import secrets
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from eth_account import Account
from web3 import Web3

CHAIN_ID = 43114
NATIVE = "0x0000000000000000000000000000000000000000"
ROUTER = "0xf00240e5256e72771b46d095666594E0f40D085c"
API = "https://api.dexalot.com"
API_HEADERS = {"Origin": "https://app.dexalot.com", "User-Agent": "lazywallet-sandbox"}
EXPIRY_S = 15 * 60
ORDER_FIELDS = [
    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
]


class QuoteError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Pair:
    name: str
    base: str
    quote: str
    base_symbol: str
    quote_symbol: str
    base_decimals: int
    quote_decimals: int


def patch_code(code: str, old: str, new: str) -> tuple[str, int]:
    """Replace every byte-aligned occurrence of address `old` in runtime bytecode with `new`."""
    body = bytes.fromhex(code.removeprefix("0x"))
    o, n = bytes.fromhex(old.removeprefix("0x")), bytes.fromhex(new.removeprefix("0x"))
    return "0x" + body.replace(o, n).hex(), body.count(o)


def parse_pairs(data: dict) -> list[Pair]:
    return [
        Pair(name, p["baseAddress"], p["quoteAddress"], p["base"], p["quote"], int(p["baseDecimals"]), int(p["quoteDecimals"]))
        for name, p in data.items()
    ]


def match_pair(pairs: list[Pair], token_in: str, token_out: str) -> tuple[Pair, int, bool]:
    """Pair for selling token_in for token_out: side 1 sells the base, side 0 buys it."""
    tin, tout = token_in.lower(), token_out.lower()
    for p in pairs:
        if (p.base.lower(), p.quote.lower()) == (tin, tout):
            return p, 1, True
        if (p.base.lower(), p.quote.lower()) == (tout, tin):
            return p, 0, False
    raise QuoteError(404, f"Dexalot doesn't offer that pair. Available: {', '.join(p.name for p in pairs)}.")


def to_raw(amount: str, decimals: int) -> int:
    return int(Decimal(amount).scaleb(decimals).to_integral_value(ROUND_DOWN))


def maker_amount(price: dict, pair: Pair, is_base: bool) -> int:
    """Output of a pairprice reply: selling the base pays out quote tokens, selling the quote pays out base tokens."""
    if not price.get("success"):
        raise QuoteError(502, f"Dexalot isn't quoting {pair.name} right now — try again shortly.")
    out = to_raw(price["quoteAmount"], pair.quote_decimals) if is_base else to_raw(price["baseAmount"], pair.base_decimals)
    if out <= 0:
        raise QuoteError(502, "That amount is too small for Dexalot to quote.")
    return out


def build_order(maker: str, taker: str, token_in: str, token_out: str, amount_in: int, amount_out: int, now: int, nonce: int | None = None) -> dict:
    return {
        "nonceAndMeta": (int(taker, 16) << 96) | (secrets.randbits(64) if nonce is None else nonce),
        "expiry": now + EXPIRY_S,
        "makerAsset": Web3.to_checksum_address(token_out),
        "takerAsset": Web3.to_checksum_address(token_in),
        "maker": Web3.to_checksum_address(maker),
        "taker": Web3.to_checksum_address(taker),
        "makerAmount": amount_out,
        "takerAmount": amount_in,
    }


def typed_data(order: dict) -> dict:
    return {
        "domain": {"name": "Dexalot", "version": "2", "chainId": CHAIN_ID, "verifyingContract": order["maker"]},
        "types": {"Order": [{"name": n, "type": t} for n, t in ORDER_FIELDS]},
        "primaryType": "Order",
        "message": order,
    }


def sign_order(key, order: dict) -> str:
    return Account.sign_typed_data(key, full_message=typed_data(order)).signature.to_0x_hex()
