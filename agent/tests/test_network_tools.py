import asyncio

from fakes import FakeChain, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def make(eth=None, avax=None):
    out = Outbox()
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}])
    eth = eth or FakeChain(tokens={"USDC": 500 * 10**6})
    avax = avax or FakeChain(tokens={"USDC": 20 * 10**6})
    tools = WalletTools(eth, out, ctx, Proposals(), approval_timeout=5, avalanche=avax)
    return tools, out


def text(result):
    return result["content"][0]["text"]


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


async def test_balances_cover_both_networks():
    tools, out = make()
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert [(h["network"], h["symbol"]) for h in card["holdings"]] == [
        ("Ethereum", "ETH"), ("Ethereum", "USDC"), ("Avalanche", "AVAX"), ("Avalanche", "USDC"),
    ]
    assert "Ethereum: ETH 10" in text(result) and "Avalanche: AVAX 10" in text(result)


async def test_balances_survive_one_network_down():
    avax = FakeChain()
    avax.fail = True
    tools, out = make(avax=avax)
    result = await tools.get_balances({})
    assert {h["network"] for h in out.of_type("balances")[0]["holdings"]} == {"Ethereum"}
    assert "Avalanche" in text(result) and "not reachable" in text(result).lower()


async def test_native_token_picks_its_network():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "AVAX", "amount": "1", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    assert {"label": "Network", "value": "Avalanche (Sandbox)"} in confirm["tx"]["rows"]
    task.cancel()


async def test_balance_decides_when_only_one_network_has_enough():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "100", "to": "Alice"}))
    confirm = await confirm_of(out)
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 1
    task.cancel()


async def test_ambiguous_token_sends_choice_and_asks_model_to_wait():
    tools, out = make()
    result = await tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice"})
    assert result["is_error"] is True and "wait for their answer" in text(result)
    [choice] = out.of_type("choice")
    assert [(o["label"], o["detail"], o["reply"]) for o in choice["options"]] == [
        ("Ethereum", "500 USDC", "Use Ethereum for that."),
        ("Avalanche", "20 USDC", "Use Avalanche for that."),
    ]
    assert not out.of_type("confirm")


async def test_explicit_network_wins_and_is_validated():
    tools, out = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice", "network": "avalanche"}))
    assert (await confirm_of(out))["tx"]["steps"][0]["request"]["chainId"] == 43114
    task.cancel()
    bad = await tools.propose_transfer({"token": "LIT", "amount": "1", "to": "Alice", "network": "avax"})
    assert bad["is_error"] is True and "isn't available on Avalanche" in text(bad)
    unknown = await tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice", "network": "solana"})
    assert unknown["is_error"] is True and "Ethereum, Avalanche" in text(unknown)


async def test_avalanche_gas_wording_uses_avax():
    avax = FakeChain(eth=0, tokens={"USDC": 20 * 10**6})
    tools, _ = make(avax=avax)
    result = await tools.propose_transfer({"token": "USDC", "amount": "10", "to": "Alice", "network": "avalanche"})
    assert "little AVAX" in text(result)


from lazyagent.dexalot import NATIVE  # noqa: E402
from lazyagent.transfers import TransferError  # noqa: E402

MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"


class FakeQuotes:
    def __init__(self, fail: str | None = None):
        self.calls = []
        self.fail = fail

    async def quote(self, token_in, token_out, amount_in, taker):
        self.calls.append((token_in, token_out, amount_in, taker))
        if self.fail:
            raise TransferError(self.fail)
        order = {"nonceAndMeta": "7", "expiry": "9999999999", "makerAsset": token_out, "takerAsset": token_in, "maker": MAKER,
                 "taker": taker, "makerAmount": "9574000", "takerAmount": str(amount_in)}
        return {"maker": MAKER, "order": order, "signature": "0x" + "11" * 65}


def make_swap(quotes=None, avax=None):
    out = Outbox()
    proposals = Proposals()
    avax = avax or FakeChain(tokens={"USDC": 20 * 10**6})
    tools = WalletTools(FakeChain(), out, WalletContext(address=ME), proposals, approval_timeout=5, avalanche=avax, dexalot=quotes or FakeQuotes())
    return tools, out, proposals, avax


async def test_avalanche_swap_uses_dexalot_and_reports_exact_output():
    quotes = FakeQuotes()
    tools, out, proposals, avax = make_swap(quotes)
    task = asyncio.create_task(tools.propose_swap({"token_in": "AVAX", "token_out": "USDC", "amount": "1"}))
    confirm = await confirm_of(out)
    assert quotes.calls == [(NATIVE, AVAX_USDC, 10**18, ME)]
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Swap AVAX → USDC"]
    assert confirm["tx"]["steps"][0]["request"]["chainId"] == 43114
    rows = {r["label"]: r["value"] for r in confirm["tx"]["rows"]}
    assert rows["Receive exactly"] == "9.574 USDC" and rows["Network"] == "Avalanche (Sandbox)"
    avax.tokens["USDC"] += 9_574_000
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xs"})
    result = text(await task)
    assert "Swapped 1 AVAX for 9.574 USDC" in result and "Avalanche (Sandbox)" in result


async def test_avalanche_erc20_swap_adds_approval():
    tools, out, _, _ = make_swap()
    task = asyncio.create_task(tools.propose_swap({"token_in": "USDC", "token_out": "AVAX", "amount": "10"}))
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow USDC", "Swap USDC → AVAX"]
    task.cancel()


async def test_avalanche_swap_errors_send_no_card():
    tools, out, _, _ = make_swap(FakeQuotes(fail="Dexalot doesn't offer that pair. Available: AVAX/USDC."))
    result = await tools.propose_swap({"token_in": "AVAX", "token_out": "BTC.b", "amount": "1"})
    assert result["is_error"] is True and "Available: AVAX/USDC" in text(result)
    assert not out.of_type("confirm")
