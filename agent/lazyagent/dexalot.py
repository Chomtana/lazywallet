"""Dexalot SimpleSwap on Avalanche: calldata, confirm-card steps and the sandbox quote client.
The sandbox (anvil/) signs the order; this module only turns it into transactions."""

import asyncio
from typing import Protocol

from eth_abi import encode
from web3 import Web3

from .faucet import _post
from .swaps import Step, display_units
from .tokens import Token
from .transfers import NoRoute, TransferError, short
from .uniswap import encode_erc20_approve

NATIVE = "0x0000000000000000000000000000000000000000"
ORDER_FIELDS = [
    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
]
ORDER_TUPLE = "(" + ",".join(t for _, t in ORDER_FIELDS) + ")"
SIMPLE_SWAP_SELECTOR = Web3.keccak(text=f"simpleSwap({ORDER_TUPLE},bytes)")[:4].hex()
GAS = {"approve": 60_000, "swap": 140_000}
DEXALOT_REVERT_HINT = " The Dexalot quote may have expired or already been used — ask again for a fresh one."


class Quotes(Protocol):
    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict: ...


def asset_of(token: Token) -> str:
    return NATIVE if token.address is None else token.address


def encode_simple_swap(order: dict, signature: str) -> str:
    values = tuple(int(order[k]) if t.startswith("uint") else Web3.to_checksum_address(order[k]) for k, t in ORDER_FIELDS)
    args = encode([ORDER_TUPLE, "bytes"], [values, bytes.fromhex(signature.removeprefix("0x"))])
    return "0x" + SIMPLE_SWAP_SELECTOR + args.hex()


def dexalot_steps(token_in: Token, token_out: Token, quote: dict, allowance: int) -> list[Step]:
    amount = int(quote["order"]["takerAmount"])
    maker = quote["maker"]
    steps: list[Step] = []
    if token_in.address is not None and allowance < amount:
        steps.append(Step(f"Allow {token_in.symbol}", {"to": token_in.address, "value": "0", "data": encode_erc20_approve(maker, amount)}, GAS["approve"]))
    value = amount if token_in.address is None else 0
    data = encode_simple_swap(quote["order"], quote["signature"])
    steps.append(Step(f"Swap {token_in.symbol} → {token_out.symbol}", {"to": maker, "value": str(value), "data": data}, GAS["swap"]))
    return steps


def dexalot_rows(sender: str, token_in: Token, token_out: Token, amount: int, received: int) -> list[dict]:
    rate = received * 10**token_in.decimals // amount
    return [
        {"label": "From", "value": short(sender)},
        {"label": "Rate", "value": f"1 {token_in.symbol} = {display_units(rate, token_out.decimals)} {token_out.symbol}"},
        {"label": "Route", "value": "Dexalot · signed quote at live price"},
    ]


class SandboxQuotes:
    """Asks the sandbox service (anvil/) for a sandbox-signed Dexalot order."""

    def __init__(self, url: str):
        self.url = url

    async def quote(self, token_in: str, token_out: str, amount_in: int, taker: str) -> dict:
        payload = {"token_in": token_in, "token_out": token_out, "amount_in": str(amount_in), "taker": taker}
        try:
            status, body = await asyncio.to_thread(_post, f"{self.url}/dexalot/quote", payload)
        except ConnectionError as e:
            raise TransferError("The Dexalot quote service isn't reachable — start it with `pnpm dev:sandbox`.") from e
        if status != 200:
            error = NoRoute if status == 404 else TransferError  # 404 = Dexalot doesn't offer the pair
            raise error(body.get("detail") or f"Dexalot quote failed ({status}).")
        return body
