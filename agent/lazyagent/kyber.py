"""KyberSwap aggregator for pairs Uniswap v4 / Dexalot can't do, and for any custom token.

Kyber's calldata is untrusted input: verify() decodes it and checks it against the user's request, and simulate()
runs it on the Sandbox fork, before any card is shown. Router ABI from the verified MetaAggregationRouterV2 source
(same address on Ethereum and Avalanche; selectors checked against real /route/build responses on 2026-10-15)."""

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from eth_abi import decode
from web3 import Web3

from .chain import Chain, PriceSource
from .faucet import TIMEOUT_S, _json
from .networks import Network
from .swaps import Step, SwapPlan, erc20_approval, min_out, parse_slippage, swap_rows
from .tokens import Token, find_token
from .transfers import NoRoute, TransferError, token_address_rows
from .uniswap import encode_erc20_allowance

API = "https://aggregator-api.kyberswap.com"
CHAIN_SLUG = {"ethereum": "ethereum", "avalanche": "avalanche"}
# Kyber's CDN answers 403 to Python's default user-agent.
HEADERS = {"x-client-id": "lazywallet", "user-agent": "lazywallet/0.1", "accept": "application/json"}
ROUTER = Web3.to_checksum_address("0x6131B5fae19EA4f9D964eAc0408E4408b66337b5")  # MetaAggregationRouterV2
NATIVE = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
DESC = "(address,address,address[],uint256[],address[],uint256[],address,uint256,uint256,uint256,bytes)"
EXECUTION = f"(address,address,bytes,{DESC},bytes)"
SWAP_SELECTOR = Web3.keccak(text=f"swap({EXECUTION})")[:4].hex()  # e21fd0e9
SIMPLE_SELECTOR = Web3.keccak(text=f"swapSimpleMode(address,{DESC},bytes,bytes)")[:4].hex()  # 8af033fb
# Kyber's API caps slippageTolerance at 5000 bps. Fine on a private fork (no MEV); the 5% simulation check
# below is what catches a wrong amount.
SANDBOX_KYBER_SLIPPAGE_BPS = 5000
SIM_TOLERANCE_PCT = 5
# The build's amountOut (which the minimum and the simulation check are measured against) may not be more than
# 1% below the separate /routes quote — a build response can't quietly lower the bar.
MAX_BUILD_SHORTFALL_BPS = 100
SWAP_GAS_FLOOR = 250_000
DEX_NAMES = {
    "traderjoe": "LFJ", "traderjoe-v21": "LFJ", "traderjoe-v22": "LFJ", "pangolin": "Pangolin", "pharaoh": "Pharaoh",
    "uniswap": "Uniswap", "uniswapv3": "Uniswap", "uniswap-v4": "Uniswap", "sushiswap": "SushiSwap",
    "pancake-v3": "PancakeSwap", "balancer-v2-weighted": "Balancer", "curve-stable-ng": "Curve",
    "arenadex": "Arena DEX", "blackhole": "Blackhole", "fluid": "Fluid", "curve": "Curve", "balancer": "Balancer",
}


def http_json(url: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    """GET (or POST `payload` as JSON); returns (status, JSON body or {}). Raises ConnectionError if unreachable."""
    h = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        h["content-type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=TIMEOUT_S) as res:
            return res.status, _json(res.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(str(e)) from e


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class Kyber(Protocol):
    async def route(self, network: str, token_in: str, token_out: str, amount: int) -> dict: ...
    async def build(self, network: str, summary: dict, sender: str, slippage_bps: int) -> dict: ...


class KyberClient:
    def __init__(self, api: str = API):
        self.api = api

    async def _call(self, network: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        url = f"{self.api}/{CHAIN_SLUG[network]}/api/v1/{path}"
        try:
            return await asyncio.to_thread(http_json, url, payload, HEADERS)
        except ConnectionError as e:
            raise TransferError("KyberSwap isn't reachable right now — try again in a moment.") from e

    async def route(self, network: str, token_in: str, token_out: str, amount: int) -> dict:
        query = urllib.parse.urlencode({"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount)})
        status, body = await self._call(network, f"routes?{query}")
        data = body.get("data")
        if not isinstance(data, dict):
            data = {}
        if status != 200 or _int((data.get("routeSummary") or {}).get("amountOut")) <= 0:
            raise NoRoute(f"KyberSwap has no route for that pair right now ({body.get('message') or status}).")
        return data

    async def build(self, network: str, summary: dict, sender: str, slippage_bps: int) -> dict:
        # skipSimulateTx: Kyber would otherwise simulate on the real chain, where Sandbox wallets hold nothing (400).
        payload = {"routeSummary": summary, "sender": sender, "recipient": sender, "slippageTolerance": slippage_bps, "skipSimulateTx": True}
        status, body = await self._call(network, "route/build", payload)
        if status != 200 or not isinstance(body.get("data"), dict):
            raise TransferError(f"KyberSwap couldn't build that swap ({body.get('message') or status}).")
        return body["data"]


def kyber_asset(token: Token) -> str:
    return NATIVE if token.address is None else token.address


def kyber_slippage(text: str | None) -> int:
    """Sandbox default unless the user named a slippage (then the usual 0.01–5% rule applies)."""
    return SANDBOX_KYBER_SLIPPAGE_BPS if text is None or not str(text).strip() else parse_slippage(text)


@dataclass(frozen=True)
class SwapRequest:
    token_in: str  # Kyber asset address (NATIVE for the native coin)
    token_out: str
    amount: int
    user: str
    slippage_bps: int


@dataclass(frozen=True)
class Verified:
    data: str
    value: int
    expected: int  # Kyber's quoted output
    minimum: int  # minReturnAmount the router enforces


def _desc(selector: str, args: bytes, native: bool) -> tuple | None:
    if selector == SWAP_SELECTOR:
        return decode([EXECUTION], args)[0][3]
    if selector == SIMPLE_SELECTOR and not native:  # swapSimpleMode is nonpayable
        return decode(["address", DESC, "bytes", "bytes"], args)[1]
    return None


def verify(build: dict, req: SwapRequest, quoted: int) -> Verified:
    """Refuse Kyber's built swap unless it does exactly what the user asked. `quoted` = the /routes amountOut."""

    def refuse(why: str) -> TransferError:
        return TransferError(f"KyberSwap's transaction didn't match your request ({why}), so I didn't show it. Try again.")

    if str(build.get("routerAddress", "")).lower() != ROUTER.lower():
        raise refuse("unexpected router")
    native = req.token_in.lower() == NATIVE.lower()
    value = _int(build.get("transactionValue"))
    if value != (req.amount if native else 0):
        raise refuse("wrong value")
    try:
        raw = bytes.fromhex(str(build.get("data", "")).removeprefix("0x"))
        desc = _desc(raw[:4].hex(), raw[4:], native)
    except Exception:
        raise refuse("unreadable calldata") from None
    if desc is None:
        raise refuse("unknown router function")
    src, dst, _, _, fee_receivers, _, receiver, amount, min_return, _, _ = desc
    if src.lower() != req.token_in.lower() or dst.lower() != req.token_out.lower():
        raise refuse("wrong tokens")
    if amount != req.amount:
        raise refuse("wrong amount")
    if receiver.lower() != req.user.lower():
        raise refuse("wrong recipient")
    if fee_receivers:
        raise refuse("extra fee")
    expected = _int(build.get("amountOut"))
    if expected <= 0 or min_return < min_out(expected, req.slippage_bps):
        raise refuse("minimum too low")
    if quoted <= 0 or expected * 10_000 < quoted * (10_000 - MAX_BUILD_SHORTFALL_BPS):
        raise refuse("build quote below the route quote")
    return Verified("0x" + raw.hex(), value, expected, min_return)


async def allowance_override(chain: Chain, token: str, owner: str, amount: int) -> dict:
    """State override giving ROUTER `amount` of allowance — the approve step hasn't run when we simulate.
    The token's allowance slot is one of the slots allowance(owner, ROUTER) reads; we keep the one that works."""
    data = encode_erc20_allowance(owner, ROUTER)
    value = "0x" + amount.to_bytes(32, "big").hex()
    for key in await chain.storage_keys(token, data):
        override = {Web3.to_checksum_address(token): {"stateDiff": {key: value}}}
        try:
            got = await chain.simulate({"to": token, "data": data}, override)
        except Exception:
            continue
        if int.from_bytes(got[:32], "big") == amount:
            return override
    raise TransferError("I couldn't simulate this swap (unusual token storage), so I didn't show it.")


async def simulate(chain: Chain, user: str, v: Verified, override: dict | None) -> int:
    """Run the swap with eth_call from the user; the router returns (returnAmount, gasUsed)."""
    try:
        raw = await chain.simulate({"from": user, "to": ROUTER, "data": v.data, "value": v.value}, override)
        returned = decode(["uint256", "uint256"], raw)[0]
    except Exception as e:
        raise TransferError(f"That KyberSwap route fails in simulation right now ({e}), so I didn't show it.") from e
    if abs(returned - v.expected) * 100 > v.expected * SIM_TOLERANCE_PCT:
        raise TransferError("KyberSwap's quote doesn't match what the swap does in simulation, so I didn't show it. Try again.")
    return returned


def _dex(exchange: str) -> str:
    key = exchange.split("/")[-1]  # "pmm-8/uniswap" → "uniswap"
    base = re.sub(r"-(v\d+|\d+)$", "", key)  # "arenadex-v2" → "arenadex", "pharaoh-2" → "pharaoh"
    return DEX_NAMES.get(key) or DEX_NAMES.get(base) or base.replace("-", " ").title()


def kyber_label(summary: dict) -> str:
    names = [_dex(str(p.get("exchange") or "")) for hop in summary.get("route") or [] for p in hop]
    names = list(dict.fromkeys(n for n in names if n))
    return f"KyberSwap via {', '.join(names)}" if names else "KyberSwap"


def usd_impact(summary: dict) -> float | None:
    """Value lost between input and output by Kyber's own USD estimates; None when it has no prices."""
    try:
        usd_in, usd_out = float(summary["amountInUsd"]), float(summary["amountOutUsd"])
    except (KeyError, TypeError, ValueError):
        return None
    return max(1 - usd_out / usd_in, 0.0) if usd_in > 0 and usd_out > 0 else None


def kyber_steps(token_in: Token, token_out: Token, amount: int, allowance: int, v: Verified, gas: int) -> list[Step]:
    steps = erc20_approval(token_in, allowance, amount, ROUTER) if token_in.address else []
    steps.append(Step(f"Swap {token_in.symbol} → {token_out.symbol}", {"to": ROUTER, "value": str(v.value), "data": v.data}, gas))
    return steps


@dataclass(frozen=True)
class KyberSwap:
    steps: list[Step]
    verified: Verified
    label: str
    impact: float | None
    bps: int


async def kyber_swap(client: Kyber, chain: Chain, net: Network, tin: Token, tout: Token, amount: int, user: str, slippage: str | None) -> KyberSwap:
    """Route, build, verify and simulate a KyberSwap swap."""
    bps = kyber_slippage(slippage)
    req = SwapRequest(kyber_asset(tin), kyber_asset(tout), amount, user, bps)
    route = await client.route(net.key, req.token_in, req.token_out, amount)
    summary = route["routeSummary"]
    v = verify(await client.build(net.key, summary, user, bps), req, _int(summary.get("amountOut")))
    allowance, override = 0, None
    if tin.address is not None:
        allowance = int.from_bytes((await chain.call(tin.address, encode_erc20_allowance(user, ROUTER)))[:32], "big")
        if allowance < amount:
            override = await allowance_override(chain, tin.address, user, amount)
    await simulate(chain, user, v, override)
    steps = kyber_steps(tin, tout, amount, allowance, v, max(_int(summary.get("gas")), SWAP_GAS_FLOOR))
    return KyberSwap(steps, v, kyber_label(summary), usd_impact(summary), bps)


async def kyber_plan(
    client: Kyber, chain: Chain, net: Network, tin: Token, tout: Token, amount: int, user: str, slippage: str | None
) -> SwapPlan:
    """kyber_swap as propose_swap's plan."""
    k = await kyber_swap(client, chain, net, tin, tout, amount, user, slippage)
    rows = swap_rows(user, k.label, k.impact) + token_address_rows(tin, tout)
    hint = f" The price probably moved more than the {k.bps / 100:g}% slippage — ask again for a fresh quote."
    return SwapPlan(k.steps, rows, hint, k.verified.expected, k.label, k.impact)


def usd_price(client: Kyber, net: Network) -> PriceSource:
    """Custom-token USD price from KyberSwap: route 1 USDC → token and invert
    (1 token → USDC rounds to 0–1 raw unit for memecoins)."""
    usdc = find_token("USDC", net.tokens)

    async def price(token: Token) -> float | None:
        try:
            data = await client.route(net.key, usdc.address, token.address, 10**usdc.decimals)
            out = int(data["routeSummary"]["amountOut"])
        except Exception:
            return None
        return 10**token.decimals / out if out > 0 else None

    return price
