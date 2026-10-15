import asyncio

from eth_abi import decode, encode
from fakes import FakeChain, FakeQuoter, Outbox

from lazyagent.networks import ETHEREUM
from lazyagent.proposals import Proposals
from lazyagent.scheduler import FIXED_GAS, NEXT_ID, SCHEDULER, encode_gas_balance, encode_get_order
from lazyagent.tokens import find_token
from lazyagent.tools import TOOL_NAMES, WalletContext, WalletTools
from lazyagent.uniswap import Hop, encode_erc20_allowance

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USDC = find_token("USDC", ETHEREUM.tokens)
WETH = find_token("WETH", ETHEREUM.tokens)
ORDER_ABI = "(address,address,address,uint256,uint256,uint64,uint64,uint32,uint32,uint64,bool)"
USDC_PER_ETH = 2358


def linear(route, amount_in):
    """Only the 0.05% ETH/USDC pool exists; 1 ETH = 2358 USDC both ways."""
    if route.hops != (Hop(500, 10),) or USDC.address not in route.currencies or len(route.currencies) != 2:
        return None
    if int(route.currencies[0], 16) == 0:
        return amount_in * USDC_PER_ETH // 10**12
    return amount_in * 10**12 // USDC_PER_ETH


def make(chain=None):
    out, proposals = Outbox(), Proposals()
    chain = chain or FakeChain(tokens={"USDC": 5_000 * 10**6})
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(linear))
    return tools, out, proposals, chain


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def test_tools_registered():
    for name in ("propose_scheduled_swap", "list_scheduled_swaps", "cancel_scheduled_swap"):
        assert f"mcp__wallet__{name}" in TOOL_NAMES


async def test_schedule_usdc_to_eth_shows_card_and_reports_success():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(
        tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "interval_seconds": "60", "count": "3"})
    )
    confirm = await confirm_of(out)
    steps = confirm["tx"]["steps"]
    assert [s["label"] for s in steps] == ["Allow USDC", "Schedule swap"]
    assert all(s["request"]["chainId"] == 1 for s in steps)
    schedule = steps[-1]["request"]
    assert schedule["to"] == SCHEDULER
    assert schedule["value"] == str(FIXED_GAS * chain.gp * 3 * 2)
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(schedule["data"][10:]))
    expected = 10 * 10**6 * 10**12 // USDC_PER_ETH
    # eth_abi decodes addresses lowercase, so compare case-insensitively
    assert tuple(str(a).lower() for a in args[:2]) == (USDC.address.lower(), WETH.address.lower())
    assert args[2:4] == (10 * 10**6, expected * 9500 // 10_000)
    assert args[4:] == (chain.now, 60, 3)
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Schedule"] == "every 1 min × 3, starting now"
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xabc", "hashes": ["0x1", "0xabc"]})
    assert "Scheduled" in text(await task)


async def test_schedule_min_received_override():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(
        tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "min_received": "0.005"})
    )
    confirm = await confirm_of(out)
    args = decode(["address", "address", "uint256", "uint256", "uint64", "uint64", "uint32"], bytes.fromhex(confirm["tx"]["steps"][-1]["request"]["data"][10:]))
    assert args[3] == 5 * 10**15 and args[5:] == (0, 1)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    assert "rejected" in text(await task)


async def test_schedule_skips_top_up_when_deposit_covers_it():
    tools, out, proposals, chain = make()
    chain.call_responses[encode_gas_balance(ME)[:10]] = (10**18).to_bytes(32, "big")
    task = asyncio.create_task(tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][-1]["request"]["value"] == "0"
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task


async def test_schedule_rejects_when_total_exceeds_balance():
    tools, out, _, _ = make(FakeChain(tokens={"USDC": 25 * 10**6}))
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "interval_seconds": 60, "count": 3})
    assert result.get("is_error") and "30 USDC" in text(result)
    assert not out.of_type("confirm")


async def test_schedule_rejects_when_native_cannot_cover_wrap_and_deposit():
    tools, out, _, _ = make(FakeChain(eth=10**17 + 1))
    result = await tools.propose_scheduled_swap({"token_in": "ETH", "token_out": "USDC", "amount": "0.05", "interval_seconds": 60, "count": 2})
    assert result.get("is_error") and "ETH" in text(result)
    assert not out.of_type("confirm")


async def test_schedule_rejects_same_token_once_wrapped():
    tools, _, _, _ = make()
    result = await tools.propose_scheduled_swap({"token_in": "ETH", "token_out": "WETH", "amount": "1"})
    assert result.get("is_error") and "same token" in text(result)


async def test_schedule_rejects_short_interval():
    tools, _, _, _ = make()
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "1", "interval_seconds": 10, "count": 2})
    assert result.get("is_error") and "1 minute" in text(result)


def order_bytes(owner=ME, executed=0, cancelled=False):
    return encode([ORDER_ABI], [(owner, USDC.address, WETH.address, 10 * 10**6, 1, 1_700_000_000, 60, 3, executed, 1_700_000_060, cancelled)])


async def test_list_scheduled_swaps():
    tools, _, _, chain = make()
    chain.call_responses[NEXT_ID[:10]] = (1).to_bytes(32, "big")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    result = await tools.list_scheduled_swaps({})
    assert "#0: 10 USDC → WETH, every 1 min × 3, 0/3 done, next run in 1 min" in text(result)


async def test_list_scheduled_swaps_empty():
    tools, _, _, _ = make()
    assert "No scheduled swaps" in text(await tools.list_scheduled_swaps({}))


async def test_cancel_scheduled_swap_card():
    tools, out, proposals, chain = make()
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    task = asyncio.create_task(tools.cancel_scheduled_swap({"order_id": "0", "network": "ethereum"}))
    confirm = await confirm_of(out)
    [step] = confirm["tx"]["steps"]
    assert step["request"]["to"] == SCHEDULER and step["request"]["chainId"] == 1
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xdef", "hashes": ["0xdef"]})
    assert "Cancelled scheduled swap #0" in text(await task)


async def test_cancel_refuses_someone_elses_or_finished_order():
    tools, _, _, chain = make()
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes(owner="0x000000000000000000000000000000000000dEaD")
    assert (await tools.cancel_scheduled_swap({"order_id": 0, "network": "ethereum"})).get("is_error")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes(executed=3)
    assert "already" in text(await tools.cancel_scheduled_swap({"order_id": 0, "network": "ethereum"}))


def committed_chain(allowance=None):
    """One active order (10 USDC × 3, nothing run yet) of ME's on USDC."""
    chain = FakeChain(tokens={"USDC": 5_000 * 10**6})
    chain.call_responses[NEXT_ID[:10]] = (1).to_bytes(32, "big")
    chain.call_responses[encode_get_order(0)[:10]] = order_bytes()
    if allowance is not None:
        chain.call_responses[encode_erc20_allowance(ME, SCHEDULER)[:10]] = allowance.to_bytes(32, "big")
    return chain


async def schedule_5x2(chain):
    tools, out, proposals, _ = make(chain)
    task = asyncio.create_task(tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "5", "interval_seconds": 60, "count": 2}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task
    return confirm["tx"]["steps"]


async def test_schedule_approval_covers_other_active_orders_on_same_token():
    steps = await schedule_5x2(committed_chain())
    assert steps[0]["label"] == "Allow USDC"
    assert decode(["address", "uint256"], bytes.fromhex(steps[0]["request"]["data"][10:]))[1] == (10 + 30) * 10**6  # this order 10 + existing 30


async def test_schedule_reapproves_when_allowance_only_covers_the_old_order():
    steps = await schedule_5x2(committed_chain(allowance=30 * 10**6))
    assert [s["label"] for s in steps] == ["Allow USDC", "Schedule swap"]


async def test_schedule_skips_approval_when_allowance_covers_everything():
    steps = await schedule_5x2(committed_chain(allowance=40 * 10**6))
    assert [s["label"] for s in steps] == ["Schedule swap"]


async def test_schedule_balance_check_includes_other_active_orders():
    chain = committed_chain()
    chain.tokens["USDC"] = 35 * 10**6  # 10 × 2 fits alone, not with the 30 already reserved
    tools, out, _, _ = make(chain)
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "interval_seconds": 60, "count": 2})
    assert result.get("is_error") and "reserved" in text(result)
    assert not out.of_type("confirm")


async def test_schedule_rejects_zero_min_received():
    tools, out, _, _ = make()
    result = await tools.propose_scheduled_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10", "min_received": "0"})
    assert result.get("is_error") and "more than 0" in text(result)
    assert not out.of_type("confirm")
