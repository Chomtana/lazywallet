"""Executor for the SwapScheduler: finds due orders on both Sandbox forks and executes them with a route built
for the Swapper (the taker), earning the gas rebate. Run with `pnpm dev:executor`."""

import asyncio
import logging
from dataclasses import dataclass

from eth_account import Account
from web3 import AsyncWeb3

from .chain import Chain, RpcChain
from .config import load_settings
from .dexalot import Quotes, SandboxQuotes, asset_of, encode_simple_swap
from .kyber import ROUTER as KYBER_ROUTER
from .kyber import SANDBOX_KYBER_SLIPPAGE_BPS, Kyber, KyberClient, SwapRequest, Verified, verify
from .networks import AVALANCHE, ETHEREUM, Network
from .scheduler import SCHEDULER, SWAPPER, Call, Order, encode_execute, read_orders, routing_token, token_at, wrapped_token
from .swaps import DEADLINE_S, PERMIT2_EXPIRY_S
from .tokens import Token
from .transfers import TransferError
from .uniswap import (
    PERMIT2,
    UNIVERSAL_ROUTER,
    WETH_DEPOSIT,
    ZERO,
    ChainQuoter,
    Quoter,
    Route,
    best_route,
    currency_of,
    encode_erc20_approve,
    encode_permit2_approve,
    encode_swap,
    encode_weth_withdraw,
)

log = logging.getLogger("lazyagent.executor")
EXECUTOR_KEY = "0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6"  # Anvil dev account #9
TICK_S = 10
GAS_MARGIN = 1.2


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


def kyber_calls(order: Order, v: Verified) -> list[Call]:
    """The order's ERC-20 input (WETH/WAVAX included — no unwrap) straight into Kyber's router; the Swapper sweeps the output."""
    return [(order.token_in, 0, encode_erc20_approve(KYBER_ROUTER, order.amount_in)), (KYBER_ROUTER, 0, v.data)]


class ExecutorError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    net: Network
    chain: Chain
    w3: AsyncWeb3 | None
    quoter: Quoter | None


class Executor:
    def __init__(self, targets: list[Target], dexalot: Quotes | None, kyber: Kyber | None = None, key: str = EXECUTOR_KEY):
        self.targets = targets
        self.dexalot = dexalot
        self.kyber = kyber
        self.account = Account.from_key(key)

    async def build_calls(self, t: Target, order, now: int) -> list:
        """The network's venue for built-in pairs it can route; KyberSwap for custom tokens and everything else."""
        net = t.net
        pay, get = token_at(net, order.token_in), token_at(net, order.token_out)
        if pay is not None and get is not None:
            try:
                return await self._venue_calls(t, order, pay, get, now)
            except (ExecutorError, TransferError) as e:
                if self.kyber is None:
                    raise
                log.info("%s: order #%d falls back to KyberSwap (%s)", net.name, order.id, e)
        if self.kyber is None:
            raise ExecutorError("order needs KyberSwap (custom token or no venue route), which isn't configured")
        return await self._kyber_route(net, order)

    async def _venue_calls(self, t: Target, order, pay, get, now: int) -> list:
        net = t.net
        wrapped = wrapped_token(net).address
        a, b = routing_token(pay, net), routing_token(get, net)
        if net.swap_venue == "dexalot":
            if self.dexalot is None:
                raise ExecutorError("no Dexalot quote source")
            quote = await self.dexalot.quote(asset_of(a), asset_of(b), order.amount_in, SWAPPER)
            o = quote["order"]
            if o["taker"].lower() != SWAPPER.lower() or int(o["takerAmount"]) != order.amount_in:
                raise ExecutorError("Dexalot quote doesn't match the order")
            return dexalot_calls(order, quote, wrapped)
        found = await best_route(t.quoter, currency_of(a), currency_of(b), order.amount_in)
        if found is None:
            raise ExecutorError(f"no Uniswap v4 route {pay.symbol} → {get.symbol}")
        return uniswap_calls(order, pay, found[0], now, wrapped)

    async def _kyber_route(self, net: Network, order) -> list:
        req = SwapRequest(order.token_in, order.token_out, order.amount_in, SWAPPER, SANDBOX_KYBER_SLIPPAGE_BPS)
        summary = (await self.kyber.route(net.key, req.token_in, req.token_out, req.amount))["routeSummary"]
        built = await self.kyber.build(net.key, summary, SWAPPER, req.slippage_bps)
        # verify(): pinned router, exact input, the Swapper as receiver, no fee receivers. The contract's minOut is the real guard.
        return kyber_calls(order, verify(built, req, int(summary.get("amountOut") or 0)))

    async def _send(self, t: Target, order_id: int, calls: list) -> str:
        w3 = t.w3
        tx = {
            "from": self.account.address,
            "to": SCHEDULER,
            "value": 0,
            "data": encode_execute(order_id, calls),
            "chainId": t.net.chain_id,
            "gasPrice": await w3.eth.gas_price,
        }
        # Simulates with this gas price, so minOut, allowance and the owner's gas deposit are all checked before sending.
        tx["gas"] = int(await w3.eth.estimate_gas(tx) * GAS_MARGIN)
        tx["nonce"] = await w3.eth.get_transaction_count(self.account.address, "pending")
        tx_hash = await w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            raise ExecutorError(f"executeSwap reverted ({tx_hash.to_0x_hex()})")
        return tx_hash.to_0x_hex()

    async def tick(self) -> list[str]:
        sent: list[str] = []
        for t in self.targets:
            try:
                now = await t.chain.block_timestamp()
                due = [o for o in await read_orders(t.chain) if o.due(now)]
            except Exception as e:
                log.warning("%s: can't read scheduled orders (%s)", t.net.name, e)
                continue
            for order in due:
                try:
                    tx_hash = await self._send(t, order.id, await self.build_calls(t, order, now))
                except Exception as e:
                    log.warning("%s: order #%d skipped: %s", t.net.name, order.id, e)
                    continue
                log.info("%s: executed order #%d (%s)", t.net.name, order.id, tx_hash)
                sent.append(tx_hash)
        return sent

    async def run_forever(self) -> None:
        for t in self.targets:
            if not await t.chain.is_sandbox():
                raise SystemExit(f"{t.net.name} RPC isn't a local Anvil Sandbox — the executor only runs on Sandbox.")
        log.info("Executor %s watching %s on %s", self.account.address, SCHEDULER, ", ".join(t.net.name for t in self.targets))
        while True:
            await self.tick()
            await asyncio.sleep(TICK_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    s = load_settings()
    eth, avax = RpcChain(s.rpc_url), RpcChain(s.avax_rpc_url, poa=True)
    targets = [Target(ETHEREUM, eth, eth.w3, ChainQuoter(eth)), Target(AVALANCHE, avax, avax.w3, None)]
    asyncio.run(Executor(targets, SandboxQuotes(s.faucet_url), kyber=KyberClient()).run_forever())
