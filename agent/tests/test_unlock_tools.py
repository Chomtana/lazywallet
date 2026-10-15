import json
from datetime import UTC, datetime
from pathlib import Path

from fakes import FakeChain, FakeCoinList, FakeTokenomist, FakeTrendingSource, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.unlocks import UNLOCKS_TOOL, TokenomistHttp, Unlocks

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def make(tokenomist: FakeTokenomist) -> tuple[WalletTools, Outbox]:
    out = Outbox()
    tools = WalletTools(FakeChain(), out, WalletContext(), Proposals())
    tools.unlocks = Unlocks(
        tokenomist, FakeCoinList(load("coingecko_coins_list_unlocks.json")), FakeTrendingSource(tokens={"ethereum": load("geckoterminal_tokens_unlocks.json")}),
        now=lambda: datetime(2026, 10, 16, tzinfo=UTC),
    )
    return tools, out


def text(result):
    return result["content"][0]["text"]


async def test_list_unlocks_sends_the_card_and_works_without_a_wallet():
    tools, out = make(FakeTokenomist(load("tokenomist_upcoming.json"), load("tokenomist_token_list.json")))
    result = await tools.list_unlocks({})
    assert not result.get("is_error")
    [card] = out.of_type("unlocks")
    assert card["title"] == "Upcoming unlocks"
    assert [(i["symbol"], i["network"], i["buyable"]) for i in card["items"]] == [
        ("ZRO", "Ethereum", True), ("BTW", "Ethereum", False), ("HYPE", None, False), ("AVAX", "Avalanche", True),
    ]
    assert "ONE short sentence" in text(result)


async def test_list_unlocks_failure_is_a_friendly_error():
    tokenomist = FakeTokenomist(load("tokenomist_upcoming.json"))
    tokenomist.fail = True
    tools, out = make(tokenomist)
    result = await tools.list_unlocks({})
    assert result["is_error"] is True and text(result) == "Couldn't load token unlocks right now."
    assert out.messages == []


def test_tool_schema_and_default_source():
    assert UNLOCKS_TOOL[0] == "list_unlocks" and UNLOCKS_TOOL[2] == {"type": "object", "properties": {}}
    assert isinstance(WalletTools.unlocks.tokenomist, TokenomistHttp)
