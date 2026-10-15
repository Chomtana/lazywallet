from eth_abi import decode
from eth_abi import encode as abi_encode
from fakes import FakeChain

from lazyagent.executor import Executor, Target, dexalot_calls, uniswap_calls
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.scheduler import NEXT_ID, SWAPPER, Order, encode_get_order, wrapped_token
from lazyagent.tokens import find_token
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, WETH_DEPOSIT, ZERO, Hop, Route

USDC = find_token("USDC", ETHEREUM.tokens)
USDT = find_token("USDT", ETHEREUM.tokens)
WETH = wrapped_token(ETHEREUM)
WAVAX = wrapped_token(AVALANCHE)
AUSDC = find_token("USDC", AVALANCHE.tokens)
MAKER = "0x1111111111111111111111111111111111111111"


def order(token_in, token_out, amount=10**6, min_out=5):
    return Order(0, "0x" + "ab" * 20, token_in, token_out, amount, min_out, 0, 60, 2, 0, 0, False)


def test_uniswap_erc20_in_native_out_approves_permit2_and_wraps():
    calls = uniswap_calls(order(USDC.address, WETH.address), USDC, Route((USDC.address, ZERO), (Hop(500, 10),)), 1000, WETH.address)
    assert [c[0] for c in calls] == [USDC.address, PERMIT2, UNIVERSAL_ROUTER]
    assert calls[2][1] == 0
    commands = decode(["bytes", "bytes[]", "uint256"], bytes.fromhex(calls[2][2][10:]))[0]
    assert commands == bytes([0x10, 0x0B])


def test_uniswap_weth_in_unwraps_and_pays_value():
    calls = uniswap_calls(order(WETH.address, USDC.address, amount=10**17), WETH, Route((ZERO, USDC.address), (Hop(500, 10),)), 1000, WETH.address)
    assert calls[0][0] == WETH.address and calls[0][2].startswith("0x2e1a7d4d")  # withdraw(uint256)
    assert calls[1][0] == UNIVERSAL_ROUTER and calls[1][1] == 10**17


def test_uniswap_usdt_resets_permit2_allowance_first():
    calls = uniswap_calls(order(USDT.address, WETH.address), USDT, Route((USDT.address, ZERO), (Hop(500, 10),)), 1000, WETH.address)
    assert len(calls) == 4 and calls[0][0] == USDT.address


def quote(taker_asset, maker_asset, taker_amount, maker_amount):
    return {
        "maker": MAKER,
        "signature": "0x" + "11" * 65,
        "order": {
            "nonceAndMeta": "1", "expiry": "9", "makerAsset": maker_asset, "takerAsset": taker_asset,
            "maker": MAKER, "taker": SWAPPER, "makerAmount": str(maker_amount), "takerAmount": str(taker_amount),
        },
    }


def test_dexalot_wavax_in_unwraps_then_pays_native():
    calls = dexalot_calls(order(WAVAX.address, AUSDC.address, amount=10**18), quote(ZERO, AUSDC.address, 10**18, 20 * 10**6), WAVAX.address)
    assert [c[0] for c in calls] == [WAVAX.address, MAKER]
    assert calls[1][1] == 10**18


def test_dexalot_native_out_is_wrapped_to_wavax():
    calls = dexalot_calls(order(AUSDC.address, WAVAX.address), quote(AUSDC.address, ZERO, 10**6, 5 * 10**16), WAVAX.address)
    assert [c[0] for c in calls] == [AUSDC.address, MAKER, WAVAX.address]
    assert calls[2] == (WAVAX.address, 5 * 10**16, WETH_DEPOSIT)


ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"


class OrdersChain(FakeChain):
    """Two due orders (ids 0 and 1); FakeChain keys responses by selector only, so answer by full calldata."""

    async def call(self, to, data, gas=None):
        if data == NEXT_ID:
            return (2).to_bytes(32, "big")
        for i in (0, 1):
            if data == encode_get_order(i):
                return abi_encode([ORDER_ABI], [("0x" + "ab" * 20, USDC.address, WETH.address, 10**6, 1, 0, 0, 1, 0, 0, False)])
        return bytes(32)


class FakeExecutor(Executor):
    def __init__(self, targets, fail_ids=()):
        super().__init__(targets, None)
        self.fail_ids, self.sent = set(fail_ids), []

    async def build_calls(self, t, order, now):
        if order.id in self.fail_ids:
            raise RuntimeError("price below minOut")
        return []

    async def _send(self, t, order_id, calls):
        self.sent.append(order_id)
        return f"0x{order_id}"


async def test_tick_skips_failing_order_and_runs_the_next():
    ex = FakeExecutor([Target(ETHEREUM, OrdersChain(), None, None)], fail_ids={0})
    assert await ex.tick() == ["0x1"]
    assert ex.sent == [1]


async def test_tick_survives_unreachable_chain():
    down = FakeChain()
    down.fail = True

    async def boom(*a, **k):
        raise ConnectionError("connection refused")

    down.call = boom
    down.block_timestamp = boom
    ex = FakeExecutor([Target(ETHEREUM, down, None, None), Target(AVALANCHE, OrdersChain(), None, None)])
    assert await ex.tick() == ["0x0", "0x1"]
