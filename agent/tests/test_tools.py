import asyncio

from fakes import FakeChain, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import TOOL_NAMES, WalletContext, WalletTools, build_mcp_server

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


async def fake_fund(address):
    fake_fund.calls.append(address)
    return "100 ETH, 10,000 USDC"


fake_fund.calls = []


def make(chain=None, timeout=5.0, fund=fake_fund):
    out = Outbox()
    ctx = WalletContext(address=ME, contacts=[{"name": "Alice", "address": ALICE}])
    proposals = Proposals()
    tools = WalletTools(chain or FakeChain(tokens={"USDC": 500 * 10**6}), out, ctx, proposals, approval_timeout=timeout, fund=fund)
    return tools, out, proposals


def text(result):
    return result["content"][0]["text"]


async def wait_for_confirm(out):
    for _ in range(100):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm sent")


async def test_get_balances_emits_card_and_summary():
    tools, out, _ = make()
    result = await tools.get_balances({})
    [card] = out.of_type("balances")
    assert card["holdings"] == [
        {"network": "Ethereum", "symbol": "ETH", "amount": 10.0, "usdPrice": 3200.0},
        {"network": "Ethereum", "symbol": "USDC", "amount": 500.0, "usdPrice": 1.0},
    ]
    assert "ETH 10 ($32,000.00)" in text(result)
    assert "Total $32,500.00" in text(result)


async def test_get_balances_without_address_is_error():
    tools, _, _ = make()
    tools.ctx.address = None
    assert (await tools.get_balances({}))["is_error"] is True


async def test_resolve_recipient():
    tools, _, _ = make()
    assert ALICE in text(await tools.resolve_recipient({"name_or_address": "alice"}))
    assert (await tools.resolve_recipient({"name_or_address": "bob"}))["is_error"] is True


async def test_propose_transfer_approved_flow():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    assert confirm["tx"]["title"] == "Send 0.1 ETH"
    assert confirm["tx"]["from"] == ME
    assert confirm["tx"]["steps"] == [{"label": "Send", "request": {"to": ALICE, "value": str(10**17), "data": "0x", "chainId": 1}}]
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xabc", "status": "success"})
    result = await task
    assert "Sent 0.1 ETH to Alice" in text(result)
    assert "0xabc" in text(result)


async def test_propose_transfer_rejected():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "10", "to": ALICE}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    assert "rejected" in text(await task)


async def test_propose_transfer_reverted_and_send_error():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xdef", "status": "reverted"})
    assert "reverted" in text(await task)

    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "error": "insufficient funds"})
    assert "insufficient funds" in text(await task)


async def test_propose_transfer_receipt_error_after_broadcast():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xfeed", "error": "timeout"})
    result = text(await task)
    assert "0xfeed" in result
    assert "failed before it was sent" not in result


async def test_propose_transfer_timeout():
    tools, out, _ = make(timeout=0.01)
    result = await tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"})
    assert out.of_type("confirm")
    assert "didn't respond" in text(result)


async def test_propose_transfer_validation_errors_send_no_card():
    cases = [
        ({"token": "DOGE", "amount": "1", "to": "Alice"}, "ETH, USDC"),
        ({"token": "ETH", "amount": "0", "to": "Alice"}, "more than 0"),
        ({"token": "ETH", "amount": "1", "to": "charlie"}, "address book"),
        ({"token": "ETH", "amount": "10", "to": "Alice"}, "network fee"),
        ({"token": "USDC", "amount": "501", "to": "Alice"}, "only have 500 USDC"),
    ]
    for args, fragment in cases:
        tools, out, _ = make()
        result = await tools.propose_transfer(args)
        assert result["is_error"] is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")


async def test_propose_transfer_chain_unreachable():
    chain = FakeChain()
    chain.fail = True
    tools, out, _ = make(chain=chain)
    result = await tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"})
    assert result["is_error"] is True
    assert "Sandbox chain" in text(result)


async def test_request_test_funds_on_sandbox():
    fake_fund.calls.clear()
    tools, out, _ = make()
    result = await tools.request_test_funds({})
    assert fake_fund.calls == [ME]
    assert "100 ETH, 10,000 USDC" in text(result)
    assert out.of_type("balances")


async def test_request_test_funds_refused_off_sandbox():
    fake_fund.calls.clear()
    chain = FakeChain()
    chain.sandbox = False
    tools, out, _ = make(chain=chain)
    result = await tools.request_test_funds({})
    assert result["is_error"] is True
    assert "only works on Sandbox" in text(result)
    assert fake_fund.calls == []


async def test_request_test_funds_faucet_down():
    async def down(address):
        raise ConnectionError("refused")

    tools, _, _ = make(fund=down)
    result = await tools.request_test_funds({})
    assert result["is_error"] is True
    assert "pnpm dev:sandbox" in text(result)


async def test_unsupported_action():
    tools, _, _ = make()
    assert "coming soon" in text(await tools.unsupported_action({"action": "swap"})).lower()


def test_mcp_server_and_names():
    tools, _, _ = make()
    assert build_mcp_server(tools)["name"] == "wallet"
    assert TOOL_NAMES == [
        "mcp__wallet__get_balances",
        "mcp__wallet__resolve_recipient",
        "mcp__wallet__propose_transfer",
        "mcp__wallet__propose_swap",
        "mcp__wallet__unsupported_action",
        "mcp__wallet__request_test_funds",
    ]


async def test_confirmed_transfer_shows_only_the_sent_token_change():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "USDC", "amount": "100", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    tools.chain.tokens["USDC"] -= 100 * 10**6
    tools.chain.eth -= 10**14  # gas only — not shown
    proposals.resolve(confirm["id"], {"outcome": "approved", "hash": "0xabc", "status": "success"})
    result = text(await task)
    [card] = out.of_type("balance_change")
    assert card["changes"] == [
        {"network": "Ethereum", "symbol": "USDC", "before": 500.0, "after": 400.0, "delta": -100.0, "usdPrice": 1.0}
    ]
    assert not out.of_type("balances")
    assert "USDC -100 (now 400)" in result


async def test_rejected_transfer_shows_no_balance_change():
    tools, out, proposals = make()
    task = asyncio.create_task(tools.propose_transfer({"token": "ETH", "amount": "0.1", "to": "Alice"}))
    confirm = await wait_for_confirm(out)
    proposals.resolve(confirm["id"], {"outcome": "rejected"})
    await task
    assert not out.of_type("balance_change")
