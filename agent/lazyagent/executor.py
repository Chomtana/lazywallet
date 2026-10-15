"""Executor for the SwapScheduler: finds due orders on both Sandbox forks and executes them with a route built
for the Swapper (the taker), earning the gas rebate. Run with `pnpm dev:executor`."""

from .dexalot import encode_simple_swap
from .scheduler import Call, Order
from .swaps import DEADLINE_S, PERMIT2_EXPIRY_S
from .tokens import Token
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ZERO,
    Route,
    encode_erc20_approve,
    encode_permit2_approve,
    encode_swap,
    encode_weth_withdraw,
)


def uniswap_calls(order: Order, pay: Token, route: Route, now: int, wrapped: str) -> list[Call]:
    cin, cout = route.currencies[0], route.currencies[-1]
    calls: list[Call] = []
    if cin == ZERO:  # the order holds WETH; the pool takes native ETH
        calls.append((wrapped, 0, encode_weth_withdraw(order.amount_in)))
        value = order.amount_in
    else:
        if pay.symbol == "USDT":  # USDT reverts on nonzero → nonzero approvals
            calls.append((pay.address, 0, encode_erc20_approve(PERMIT2, 0)))
        calls.append((pay.address, 0, encode_erc20_approve(PERMIT2, order.amount_in)))
        calls.append((PERMIT2, 0, encode_permit2_approve(pay.address, UNIVERSAL_ROUTER, order.amount_in, now + PERMIT2_EXPIRY_S)))
        value = 0
    data = encode_swap(route, order.amount_in, order.min_out, now + DEADLINE_S, wrap_output=cout == ZERO)
    calls.append((UNIVERSAL_ROUTER, value, data))
    return calls


def dexalot_calls(order: Order, quote: dict, wrapped: str) -> list[Call]:
    o, maker = quote["order"], quote["maker"]
    native_in, native_out = int(o["takerAsset"], 16) == 0, int(o["makerAsset"], 16) == 0
    calls: list[Call] = []
    if native_in:  # the order holds WAVAX; Dexalot's pair is native AVAX
        calls.append((wrapped, 0, encode_weth_withdraw(order.amount_in)))
    else:
        calls.append((order.token_in, 0, encode_erc20_approve(maker, order.amount_in)))
    calls.append((maker, order.amount_in if native_in else 0, encode_simple_swap(o, quote["signature"])))
    if native_out:  # an RFQ order pays exactly makerAmount, so wrap exactly that
        calls.append((wrapped, int(o["makerAmount"]), WETH_DEPOSIT))
    return calls
