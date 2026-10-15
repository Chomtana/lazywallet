"""Dexalot SimpleSwap on the Avalanche fork: sandbox-signed orders at Dexalot's live price.

Dexalot only signs firm quotes for addresses holding real mainnet funds, so on the fork we patch the RFQ
makers' immutable swapSigner to a sandbox key and sign orders ourselves. Never used on a real network."""

import asyncio
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3
from web3.middleware import ExtraDataToPOAMiddleware

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


PAIRS_TTL_S = 3600
ROUTER_ABI = [{"name": "getAllowedRFQs", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address[]"}]}]
SIGNER_ABI = [{"name": "swapSigner", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]}]
BALANCE_OF = [{"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}]


def avalanche_w3(url: str) -> AsyncWeb3:
    w3 = AsyncWeb3(AsyncHTTPProvider(url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Avalanche blocks carry long extraData
    return w3


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=API_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise QuoteError(502, f"Dexalot's API isn't reachable right now ({e}).") from e


class DexalotSandbox:
    def __init__(self, w3: AsyncWeb3, api: str = API):
        self.w3 = w3
        self.api = api
        self.signer = Account.create()  # process memory only
        self.makers: list[str] = []
        self.error: str | None = "not set up yet"
        self._pairs: list[Pair] = []
        self._pairs_at = 0.0

    async def _rpc(self, method: str, params: list) -> None:
        res = await self.w3.provider.make_request(method, params)
        if "error" in res:
            raise RuntimeError(f"{method} failed: {res['error']}")

    async def setup(self) -> None:
        """Make every Dexalot RFQ maker on the fork trust the sandbox signer (swapSigner is immutable → bytecode)."""
        router = self.w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)
        makers = []
        for m in await router.functions.getAllowedRFQs().call():
            rfq = self.w3.eth.contract(address=m, abi=SIGNER_ABI)
            try:
                old = await rfq.functions.swapSigner().call()
            except Exception:
                continue  # not a signer-based maker
            code = (await self.w3.eth.get_code(m)).to_0x_hex()
            patched, n = patch_code(code, old, self.signer.address)
            if n == 0:
                continue  # signer isn't an immutable in this maker (e.g. an upgradeable proxy keeping it in storage) — can't patch, don't use
            await self._rpc("anvil_setCode", [m, patched])
            if (await rfq.functions.swapSigner().call()).lower() != self.signer.address.lower():
                raise RuntimeError(f"patched {m} still reports another swapSigner")
            makers.append(m)
        if not makers:
            raise RuntimeError("no Dexalot RFQ makers found")
        self.makers, self.error = makers, None

    async def pairs(self) -> list[Pair]:
        if not self._pairs or time.monotonic() - self._pairs_at > PAIRS_TTL_S:
            self._pairs = parse_pairs(await asyncio.to_thread(_get_json, f"{self.api}/api/rfq/pairs?chainid={CHAIN_ID}"))
            self._pairs_at = time.monotonic()
        return self._pairs

    async def _holding(self, maker: str, token: str) -> int:
        if token.lower() == NATIVE:
            return await self.w3.eth.get_balance(maker)
        return await self.w3.eth.contract(address=Web3.to_checksum_address(token), abi=BALANCE_OF).functions.balanceOf(maker).call()

    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict:
        if self.error:
            raise QuoteError(503, f"Dexalot swaps are unavailable on this Sandbox ({self.error}).")
        pair, side, is_base = match_pair(await self.pairs(), token_in, token_out)
        decimals = pair.base_decimals if is_base else pair.quote_decimals
        query = urllib.parse.urlencode({
            "chainid": CHAIN_ID, "pair": pair.name, "amount": format(Decimal(amount_in).scaleb(-decimals).normalize(), "f"),
            "isbase": 1 if is_base else 0, "side": side, "taker": taker,
        })
        price = await asyncio.to_thread(_get_json, f"{self.api}/api/rfq/pairprice?{query}")
        out = maker_amount(price, pair, is_base)
        holding, maker = max([(await self._holding(m, token_out), m) for m in self.makers])
        if holding < out:
            symbol = pair.quote_symbol if is_base else pair.base_symbol
            raise QuoteError(409, f"Dexalot doesn't have enough {symbol} on Sandbox for that size — try a smaller amount.")
        now = (await self.w3.eth.get_block("latest"))["timestamp"]
        order = build_order(maker, taker, token_in, token_out, amount_in, out, now)
        return {
            "maker": order["maker"],
            "order": {k: str(v) for k, v in order.items()},
            "signature": sign_order(self.signer.key, order),
            "pair": pair.name,
            "price": price.get("price"),
        }
