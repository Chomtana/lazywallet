import asyncio

from eth_abi import encode
from fakes import FakeChain, FakeKyber, FakeQuoter, FakeSearch, Outbox, assert_friendly
from test_custom_tokens import COQ_ADDR, COQ_LOGO, COQ_SAVED, GT_COQ

from lazyagent.kyber import NATIVE, ROUTER
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import UNIVERSAL_ROUTER, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
OUT = 8_000_000 * 10**18


def coq_chain(**tokens) -> FakeChain:
    """An Avalanche fork where COQ_ADDR answers symbol()/decimals() like the real COQ."""
    chain = FakeChain(tokens=tokens)
    chain.call_responses["0x95d89b41"] = encode(["string"], ["COQ"])
    chain.call_responses["0x313ce567"] = encode(["uint8"], [18])
    chain.sim_out = OUT
    return chain


def make(avax=None, kyber=None, search=None, saved=(), quoter=None, eth=None):
    out = Outbox()
    proposals = Proposals()
    avax = avax or coq_chain()
    kyber = kyber or FakeKyber(out=OUT)
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}], tokens=list(saved))
    tools = WalletTools(eth or FakeChain(), out, ctx, proposals, approval_timeout=5, quoter=quoter,
                        avalanche=avax, kyber=kyber, search=search)
    return tools, out, proposals, avax, kyber


def text(result):
    return result["content"][0]["text"]


def rows_of(confirm):
    return {r["label"]: r["value"] for r in confirm["tx"]["rows"]}


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


async def test_buy_by_contract_address_goes_through_kyber_and_saves_the_token():
    tools, out, proposals, avax, kyber = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["title"] == "Swap"
    assert confirm["tx"]["steps"] == [
        {"label": "Swap AVAX → COQ", "request": {"to": ROUTER, "value": str(10**18), "data": confirm["tx"]["steps"][0]["request"]["data"], "chainId": 43114}}
    ]
    assert confirm["tx"]["steps"][0]["request"]["data"].startswith("0xe21fd0e9")
    assert confirm["tx"]["addToken"] == {"chainId": 43114, "address": COQ_ADDR, "symbol": "COQ", "decimals": 18}
    rows = rows_of(confirm)
    assert rows["Route"] == "KyberSwap via LFJ"
    assert rows["COQ address"] == COQ_ADDR
    summary = assert_friendly(confirm["tx"])
    assert summary["network"] == "Avalanche" and summary["via"] == "KyberSwap via LFJ"
    assert summary["pay"]["amount"] == "1" and summary["receive"]["amount"] == "≈ 8000000" and summary["receive"]["symbol"] == "COQ"
    assert summary["receive"]["logo"] is None  # found by address: no logo without another lookup
    assert kyber.routes == [("avalanche", NATIVE, COQ_ADDR, 10**18)]
    assert kyber.builds == [("avalanche", ME, 5000)]
    assert avax.sim_calls[-1][1] is None  # native input needs no allowance override
    avax.tokens["COQ"] = OUT
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    assert "Swapped 1 AVAX for 8000000 COQ" in text(await task)


async def test_sell_saved_token_adds_approval_and_simulates_with_an_allowance_override():
    avax = coq_chain(COQ=10**24)
    avax.access_keys, avax.allowance_slot = ["0x01", "0xab"], "0xab"
    tools, out, _, _, _ = make(avax=avax, kyber=FakeKyber(out=119_018), saved=[COQ_SAVED])
    task = asyncio.create_task(tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": "1000000"}))
    avax.sim_out = 119_018
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow COQ", "Swap COQ → USDC"]
    assert confirm["tx"]["steps"][0]["request"]["to"] == COQ_ADDR
    assert confirm["tx"]["steps"][1]["request"]["value"] == "0"
    assert "addToken" not in confirm["tx"]  # USDC is built in
    swap_call = avax.sim_calls[-1]
    assert swap_call[0]["to"] == ROUTER
    assert swap_call[1] == {COQ_ADDR: {"stateDiff": {"0xab": "0x" + (10**24).to_bytes(32, "big").hex()}}}
    assert rows_of(confirm)["COQ address"] == COQ_ADDR
    task.cancel()


async def test_matched_by_symbol_is_flagged_on_the_card():
    tools, out, _, _, _ = make(search=FakeSearch(GT_COQ))
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": "coq", "amount": "1"}))
    confirm = await confirm_of(out)
    assert rows_of(confirm)["COQ address"] == f"{COQ_ADDR} (matched by symbol — verify)"
    assert confirm["tx"]["summary"]["receive"]["logo"] == COQ_LOGO
    assert confirm["tx"]["addToken"]["logo"] == COQ_LOGO  # the wallet saves it, so later balances show it
    task.cancel()


async def test_kyber_failures_send_no_card():
    def receiver_alice(d):
        return d[:6] + (ALICE,) + d[7:]

    reverting = coq_chain()
    reverting.sim_out = RuntimeError("execution reverted")
    off = coq_chain()
    off.sim_out = OUT * 90 // 100
    cases = [
        (dict(kyber=FakeKyber(no_route=True)), "no route"),
        (dict(kyber=FakeKyber(tamper=receiver_alice)), "wrong recipient"),
        (dict(kyber=FakeKyber(out=OUT, build_out=OUT * 98 // 100)), "build quote below the route quote"),
        (dict(avax=reverting), "fails in simulation"),
        (dict(avax=off), "doesn't match"),
    ]
    for kwargs, fragment in cases:
        tools, out, _, _, _ = make(**kwargs)
        result = await tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1"})
        assert result["is_error"] is True and fragment in text(result), (fragment, text(result))
        assert not out.of_type("confirm")


async def test_erc20_input_without_a_findable_allowance_slot_sends_no_card():
    tools, out, _, _, _ = make(avax=coq_chain(COQ=10**24), saved=[COQ_SAVED])
    result = await tools.propose_swap({"token_in": "COQ", "token_out": "USDC", "amount": "1"})
    assert result["is_error"] is True and "couldn't simulate" in text(result)
    assert not out.of_type("confirm")


async def test_user_slippage_still_applies_to_kyber():
    tools, out, _, _, kyber = make()
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": COQ_ADDR, "amount": "1", "slippage_percent": "2"}))
    await confirm_of(out)
    assert kyber.builds[-1][2] == 200
    task.cancel()


async def test_builtin_pair_without_a_venue_route_falls_back_to_kyber():
    eth = FakeChain()
    eth.sim_out = OUT
    tools, out, _, _, kyber = make(eth=eth, quoter=FakeQuoter(lambda route, amount: None))
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "WBTC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["to"] == ROUTER and confirm["tx"]["steps"][0]["request"]["chainId"] == 1
    assert "addToken" not in confirm["tx"] and "WBTC address" not in rows_of(confirm)
    assert kyber.routes[0][0] == "ethereum"
    task.cancel()


async def test_builtin_pair_with_a_venue_route_keeps_uniswap():
    def linear(route, amount_in):
        return amount_in * 2358 // 10**12 if route.hops == (Hop(500, 10),) and len(route.currencies) == 2 else None

    tools, out, _, _, kyber = make(quoter=FakeQuoter(linear))
    task = asyncio.create_task(tools.propose_swap({"token_in": "ETH", "token_out": "USDC", "amount": "1"}))
    assert (await confirm_of(out))["tx"]["steps"][0]["request"]["to"] == UNIVERSAL_ROUTER
    assert kyber.routes == []
    task.cancel()


async def test_send_saved_token_shows_its_address():
    tools, out, _, _, _ = make(avax=coq_chain(COQ=10**24), saved=[COQ_SAVED])
    task = asyncio.create_task(tools.propose_transfer({"token": "COQ", "amount": "1000", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["to"] == COQ_ADDR
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    assert rows_of(confirm)["COQ address"] == COQ_ADDR
    task.cancel()


async def test_balances_list_saved_tokens_and_unknown_prices():
    avax = coq_chain(COQ=10**24)
    avax.prices["COQ"] = None
    tools, out, _, _, _ = make(avax=avax, saved=[COQ_SAVED])
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert {"network": "Avalanche", "symbol": "COQ", "amount": 1_000_000.0, "usdPrice": None, "logo": None} in card["holdings"]
    assert "COQ 1000000 (price unknown)" in text(result)
    assert "Total $32,010.00" in text(result)  # 10 ETH at $3,200 + 10 AVAX at the fake's $1; COQ excluded


async def test_unknown_tokens_are_explained():
    tools, out, _, _, _ = make(avax=FakeChain())
    bad = await tools.propose_swap({"token_in": "AVAX", "token_out": "0x1111111111111111111111111111111111111111", "amount": "1"})
    assert bad["is_error"] is True and text(bad) == "That address isn't a token on Avalanche."
    missing = await tools.propose_transfer({"token": "NOPE", "amount": "1", "to": "Alice"})
    assert "with at least $10,000 of liquidity" in text(missing) and "contract address" in text(missing)
    named = await tools.propose_transfer({"token": "NOPE", "amount": "1", "to": "Alice", "network": "avalanche"})
    assert "isn't available on Avalanche" in text(named) and "contract address" in text(named)
    assert not out.of_type("confirm")


async def test_token_found_on_both_networks_asks_which():
    eth = coq_chain(COQ=10**24)
    avax = coq_chain(COQ=10**24)
    tools, out, _, _, _ = make(eth=eth, avax=avax)
    result = await tools.propose_transfer({"token": COQ_ADDR, "amount": "1", "to": "Alice"})
    assert result["is_error"] is True and "wait for their answer" in text(result)
    [choice] = out.of_type("choice")
    assert [o["label"] for o in choice["options"]] == ["Ethereum", "Avalanche"]


async def test_token_posing_as_a_builtin_is_refused_by_address():
    fake = FakeChain()
    fake.call_responses["0x95d89b41"] = encode(["string"], ["USDC"])
    fake.call_responses["0x313ce567"] = encode(["uint8"], [6])
    tools, out, _, _, kyber = make(avax=fake)
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": "0x1111111111111111111111111111111111111111", "amount": "1"})
    assert result["is_error"] is True
    assert text(result) == "That token calls itself USDC but isn't the real USDC on Avalanche, so I won't trade it."
    assert not out.of_type("confirm") and kyber.routes == []


async def test_saved_token_posing_as_a_builtin_is_ignored():
    fake = {"chainId": 43114, "address": "0x1111111111111111111111111111111111111111", "symbol": "USDC", "decimals": 6}
    tools, out, _, _, _ = make(avax=coq_chain(USDC=10**9), saved=[fake])
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "1", "to": "Alice", "network": "avalanche"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["to"] == AVAX_USDC
    assert "USDC address" not in rows_of(confirm)
    task.cancel()
