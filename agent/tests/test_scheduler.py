import re

import pytest
from eth_abi import decode, encode
from fakes import FakeChain
from web3 import Web3

from lazyagent.config import ROOT
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.scheduler import (
    FIXED_GAS,
    NEXT_ID,
    SCHEDULER,
    SWAPPER,
    Order,
    decode_order,
    describe_order,
    duration_label,
    encode_execute,
    encode_get_order,
    encode_schedule,
    gas_top_up,
    order_token,
    parse_schedule,
    read_orders,
    routing_token,
    schedule_label,
    schedule_rows,
    schedule_steps,
    token_at,
    wrapped_token,
)
from lazyagent.tokens import find_token
from lazyagent.transfers import TransferError

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
USDC = find_token("USDC", ETHEREUM.tokens)
WETH = find_token("WETH", ETHEREUM.tokens)


def order_bytes(owner=ME, token_in=USDC.address, token_out=WETH.address, executed=0, count=3, next_time=1_700_000_000, cancelled=False):
    return encode([ORDER_ABI], [(owner, token_in, token_out, 10 * 10**6, 4 * 10**15, 1_700_000_000, 60, count, executed, next_time, cancelled)])


def test_pinned_addresses_agree_everywhere():
    sol = (ROOT / "contracts/src/Deployment.sol").read_text()
    for name, value in (("SCHEDULER", SCHEDULER), ("SWAPPER", SWAPPER)):
        pinned = re.search(rf"{name} = (0x[0-9a-fA-F]{{40}})", sol).group(1)
        assert value == pinned
        assert f'"{pinned}"' in (ROOT / "anvil/lazysandbox/scheduler.py").read_text()
    assert f"'{re.search(r'SCHEDULER = (0x[0-9a-fA-F]{40})', sol).group(1)}'" in (ROOT / "apps/wallet/src/chain/scheduler.ts").read_text()


def test_decode_order_round_trip_and_state():
    o = decode_order(7, order_bytes(executed=1))
    assert o.id == 7 and o.owner == ME and o.token_out == WETH.address
    assert o.amount_in == 10 * 10**6 and o.interval == 60 and o.count == 3 and o.executed == 1
    assert o.active and o.due(1_700_000_000) and not o.due(1_699_999_999)
    assert not decode_order(1, order_bytes(executed=3)).active
    assert not decode_order(1, order_bytes(cancelled=True)).active


def test_encode_schedule_and_execute():
    data = encode_schedule(USDC.address, WETH.address, 10, 4, 100, 60, 3)
    assert data[:10] == "0x" + Web3.keccak(text="scheduleSwap(address,address,uint256,uint256,uint64,uint64,uint32)")[:4].hex()
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(data[10:]))
    assert args[2:] == (10, 4, 100, 60, 3)
    ex = encode_execute(5, [(USDC.address, 0, "0x1234"), (WETH.address, 9, "0x")])
    assert ex[:10] == "0x" + Web3.keccak(text="executeSwap(uint256,(address,uint256,bytes)[])")[:4].hex()
    oid, calls = decode(["uint256", "(address,uint256,bytes)[]"], bytes.fromhex(ex[10:]))
    assert oid == 5 and calls[0][2] == bytes.fromhex("1234") and calls[1][1] == 9


async def test_read_orders_filters_by_owner():
    chain = FakeChain()
    chain.call_responses[NEXT_ID[:10]] = (2).to_bytes(32, "big")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    assert [o.id for o in await read_orders(chain, ME)] == [0, 1]
    assert await read_orders(chain, "0x000000000000000000000000000000000000dEaD") == []


async def test_read_orders_empty_when_not_deployed():
    chain = FakeChain()
    chain.call_responses[NEXT_ID[:10]] = b""  # eth_call to an address with no code returns 0x
    assert await read_orders(chain) == []


def test_gas_top_up_covers_twice_the_rebates_minus_existing_balance():
    assert gas_top_up(10**9, 3, 0) == FIXED_GAS * 10**9 * 3 * 2
    assert gas_top_up(10**9, 3, 10**18) == 0


def test_parse_schedule_defaults_to_one_shot_now():
    assert parse_schedule(None, None, None) == (0, 1, 0)
    assert parse_schedule("60", "5", "0") == (60, 5, 0)
    assert parse_schedule(3600, 1, 30) == (0, 1, 30)  # interval ignored for one run


@pytest.mark.parametrize("count", [None, ""])
def test_parse_schedule_interval_without_count_asks_how_many(count):
    with pytest.raises(TransferError, match="How many times"):
        parse_schedule(3600, count, 0)


@pytest.mark.parametrize("interval,count,delay", [(30, 2, 0), (60, 0, 0), (60, 101, 0), (60, 2, -1), ("soon", 2, 0)])
def test_parse_schedule_rejects_nonsense(interval, count, delay):
    with pytest.raises(TransferError):
        parse_schedule(interval, count, delay)


def test_native_maps_to_wrapped_and_back():
    assert wrapped_token(ETHEREUM).symbol == "WETH" and wrapped_token(AVALANCHE).symbol == "WAVAX"
    assert order_token(ETHEREUM.native, ETHEREUM).symbol == "WETH"
    assert order_token(USDC, ETHEREUM) is USDC
    assert routing_token(WETH, ETHEREUM) is ETHEREUM.native
    assert token_at(AVALANCHE, wrapped_token(AVALANCHE).address.lower()).symbol == "WAVAX"
    assert token_at(ETHEREUM, "0x000000000000000000000000000000000000dEaD") is None


def test_labels():
    assert duration_label(45) == "45s" and duration_label(60) == "1 min" and duration_label(7200) == "2 h" and duration_label(86400 * 7) == "7 d"
    assert schedule_label(60, 5, 0) == "every 1 min × 5, starting now"
    assert schedule_label(0, 1, 120) == "once, in 2 min"
    o = decode_order(3, order_bytes(executed=1, next_time=1_700_000_030))
    assert describe_order(o, ETHEREUM, 1_700_000_000) == "#3: 10 USDC → WETH, every 1 min × 3, 1/3 done, next run in 30s"


def test_schedule_steps_wrap_approve_schedule_for_native_input():
    steps = schedule_steps(ETHEREUM.native, USDC, ETHEREUM, 10**17, 300 * 10**6, 100, 60, 3, allowance=0, top_up=5)
    assert [s.label for s in steps] == ["Wrap ETH → WETH", "Allow WETH", "Schedule swap"]
    assert steps[0].request == {"to": WETH.address, "value": str(3 * 10**17), "data": "0xd0e30db0"}
    assert steps[2].request["to"] == SCHEDULER and steps[2].request["value"] == "5"
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(steps[2].request["data"][10:]))
    assert args[0] == WETH.address.lower() and args[1] == USDC.address.lower()


def test_schedule_steps_skip_approval_and_reset_usdt():
    assert [s.label for s in schedule_steps(USDC, ETHEREUM.native, ETHEREUM, 10, 1, 0, 0, 1, allowance=10, top_up=0)] == ["Schedule swap"]
    # approve_amount raises the bar beyond this order's own total (other active orders share the allowance)
    assert [s.label for s in schedule_steps(USDC, ETHEREUM.native, ETHEREUM, 10, 1, 0, 0, 1, allowance=10, top_up=0, approve_amount=40)] == ["Allow USDC", "Schedule swap"]
    usdt = find_token("USDT", ETHEREUM.tokens)
    assert [s.label for s in schedule_steps(usdt, WETH, ETHEREUM, 10, 1, 0, 0, 1, allowance=1, top_up=0)] == ["Reset USDT allowance", "Allow USDT", "Schedule swap"]


def test_schedule_rows_mention_wrapped_output_and_contract():
    rows = {r["label"]: r["value"] for r in schedule_rows(ME, USDC, ETHEREUM.native, ETHEREUM, 10 * 10**6, 4 * 10**15, "every 1 min × 3, starting now", 0)}
    assert rows["Each run"] == "10 USDC → WETH"
    assert rows["Min received per run"] == "0.004 WETH"
    assert rows["You receive"] == "WETH (wrapped ETH)"
    assert rows["Gas deposit"] == "already covered"
    assert rows["Contract"].startswith(SCHEDULER[:6])
