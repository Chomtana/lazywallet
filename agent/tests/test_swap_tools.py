import asyncio

from eth_abi import encode
from fakes import FakeChain, FakeQuoter, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, WETH_DEPOSIT, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_PER_ETH = 2358
USDC_ADDR = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def linear(route, amount_in):
    """Only the 0.05% ETH/USDC pool exists; 1 ETH = 2358 USDC both ways."""
    if route.hops != (Hop(500, 10),) or USDC_ADDR not in route.currencies or len(route.currencies) != 2:
        return None
    if int(route.currencies[0], 16) == 0:
        return amount_in * USDC_PER_ETH // 10**12
    return amount_in * 10**12 // USDC_PER_ETH


def make(chain=None, fn=linear):
    out = Outbox()
    proposals = Proposals()
    chain = chain or FakeChain(tokens={"USDC": 5_000 * 10**6, "USDT": 5_000 * 10**6})
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(fn))
    return tools, out, proposals, chain


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def labels(confirm):
    return [s["label"] for s in confirm["tx"]["steps"]]


async def test_eth_to_usdc_single_step_and_reports_received():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "USDC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["title"] == "Swap 1 ETH → USDC"
    assert labels(confirm) == ["Swap ETH → USDC"]
    step = confirm["tx"]["steps"][0]["request"]
    assert step["to"] == UNIVERSAL_ROUTER and step["value"] == str(10**18) and step["data"].startswith("0x3593564c")
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Route"] == "ETH → USDC · Uniswap v4 0.05%"
    assert rows["Minimum received"] == "2334.42 USDC"  # 1% slippage
    chain.tokens["USDC"] += 2_358 * 10**6
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs", "hashes": ["0xs"]})
    assert "Swapped 1 ETH for 2358 USDC" in text(await task)


async def test_usdc_to_eth_adds_approvals_and_reports_eth_as_about():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "1000"}))
    confirm = await confirm_of(out)
    assert labels(confirm) == ["Allow USDC", "Allow Uniswap router", "Swap USDC → ETH"]
    assert confirm["tx"]["steps"][1]["request"]["to"] == PERMIT2
    assert confirm["tx"]["steps"][2]["request"]["value"] == "0"
    chain.eth += 424 * 10**15
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    assert "about 0.424 ETH" in text(await task)


async def test_existing_allowances_are_skipped():
    chain = FakeChain(tokens={"USDC": 5_000 * 10**6})
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [10**30])
    chain.call_responses["0x927da105"] = encode(["uint160", "uint48", "uint48"], [10**30, chain.now + 3600, 0])
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "10"}))
    assert labels(await confirm_of(out)) == ["Swap USDC → ETH"]
    task.cancel()


async def test_usdt_with_small_allowance_resets_first():
    chain = FakeChain(tokens={"USDT": 5_000 * 10**6})
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [5])

    def usdt(route, amount_in):
        return amount_in * 4 * 10**8 if route.hops == (Hop(3000, 60),) else None  # linear, so price impact stays 0

    tools, out, _, _ = make(chain=chain, fn=usdt)
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDT", "token_out": "ETH", "amount": "10"}))
    assert labels(await confirm_of(out)) == ["Reset USDT allowance", "Allow USDT", "Allow Uniswap router", "Swap USDT → ETH"]
    task.cancel()


async def test_wrap_and_unwrap():
    chain = FakeChain(tokens={"WETH": 3 * 10**18})
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "WETH", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"] == [{"label": "Wrap ETH → WETH", "request": {"to": WETH, "value": str(10**18), "data": WETH_DEPOSIT}}]
    task.cancel()

    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_swap({"token_in": "WETH", "token_out": "ETH", "amount": "2"}))
    step = (await confirm_of(out))["tx"]["steps"][0]
    assert step["label"] == "Unwrap WETH → ETH"
    assert step["request"]["to"] == WETH and step["request"]["data"].startswith("0x2e1a7d4d")
    task.cancel()


async def test_revert_names_step_and_suggests_slippage():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "ETH", "amount": "100", "slippage_percent": "0.5"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "reverted", "hash": "0xr", "failed_step": 2})
    result = text(await task)
    assert "step 3 (Swap USDC → ETH)" in result
    assert "0.5% slippage" in result


async def test_swap_refusals_send_no_card():
    def huge_impact(route, amount_in):
        q = linear(route, amount_in)
        return q // 2 if q and amount_in >= 10**18 else q

    cases = [
        ({"token_in": "ETH", "token_out": "ETH", "amount": "1"}, linear, "two different tokens"),
        ({"token_in": "DOGE", "token_out": "ETH", "amount": "1"}, linear, "only swap"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "0"}, linear, "more than 0"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "1", "slippage_percent": "9"}, linear, "between 0.01% and 5%"),
        ({"token_in": "USDC", "token_out": "ETH", "amount": "999999"}, linear, "only have"),
        ({"token_in": "DAI", "token_out": "WBTC", "amount": "0"}, linear, "more than 0"),
        ({"token_in": "ETH", "token_out": "WBTC", "amount": "1"}, linear, "couldn't find a Uniswap v4 route"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "1"}, huge_impact, "move the price"),
        ({"token_in": "ETH", "token_out": "USDC", "amount": "9.9999"}, linear, "network fees"),
    ]
    for args, fn, fragment in cases:
        tools, out, _, _ = make(fn=fn)
        result = await tools.propose_swap(args)
        assert result.get("is_error") is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")


async def test_success_is_reported_even_if_the_balance_read_fails():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "USDC", "amount": "1"}))
    confirm = await confirm_of(out)
    chain.fail_balance_reads = True
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    result = text(await task)
    assert "Swapped 1 ETH" in result and "0xs" in result
    assert "couldn't read" in result
