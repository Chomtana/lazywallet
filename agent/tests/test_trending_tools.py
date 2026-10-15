import json

from fakes import FakeChain, FakeTrendingSource, Outbox

from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.trending import CATEGORY_NETWORKS, TRENDING_TOOL, GeckoTerminalSource, Pool, RwaCoin, TokenInfo, TrendingTokens

COQ = "0x420fca0121dc28039145009570975747295f2329"
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"
ONDO_BODY = {"data": [{"id": "eth_x", "attributes": {"address": ONDO, "symbol": "ONDO", "name": "Ondo", "price_usd": "0.43", "volume_usd": {"h24": "1183578.3"}}}]}


def make(source: FakeTrendingSource) -> WalletTools:
    tools = WalletTools(FakeChain(), Outbox(), WalletContext(), Proposals())
    tools.trending = TrendingTokens(source, lambda: [RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8)])
    return tools


def text(result):
    return result["content"][0]["text"]


async def test_memes_by_default():
    tools = make(FakeTrendingSource([Pool(TokenInfo("COQ", "COQINU", COQ), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)]))
    result = await tools.list_trending_tokens({})
    assert not result.get("is_error")
    [coq] = json.loads(text(result))["tokens"]
    assert (coq["symbol"], coq["address"], coq["network"], coq["change_24h"], coq["buyable"], coq["note"]) == ("COQ", COQ, "avalanche", -5.1, True, None)


async def test_rwa_with_network():
    source = FakeTrendingSource(tokens={"ethereum": ONDO_BODY})
    result = await make(source).list_trending_tokens({"category": "rwa", "network": "Ethereum"})
    [ondo] = json.loads(text(result))["tokens"]
    assert (ondo["symbol"], ondo["network"], ondo["buyable"]) == ("ONDO", "ethereum", False)  # no pool in this body
    assert source.calls == [("tokens", "ethereum", (ONDO,))]


async def test_works_without_an_active_wallet():
    tools = make(FakeTrendingSource([]))
    assert tools.ctx.address is None
    assert json.loads(text(await tools.list_trending_tokens({})))["tokens"] == []


async def test_bad_arguments_are_errors_without_fetching():
    source = FakeTrendingSource()
    tools = make(source)
    bad = await tools.list_trending_tokens({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be one of: meme, rwa."
    eth_memes = await tools.list_trending_tokens({"category": "meme", "network": "ethereum"})
    assert text(eth_memes) == "meme tokens are only listed on Avalanche."
    assert source.calls == []


async def test_fetch_failure_is_a_friendly_error():
    source = FakeTrendingSource()
    source.fail = True
    result = await make(source).list_trending_tokens({"category": "rwa"})
    assert result["is_error"] is True and text(result) == "Couldn't load trending tokens right now."


def test_tool_schema_follows_the_category_registry():
    name, _, schema = TRENDING_TOOL
    assert name == "list_trending_tokens"
    assert schema["properties"]["category"]["enum"] == list(CATEGORY_NETWORKS) == ["meme", "rwa"]
    assert schema["properties"]["network"]["enum"] == ["ethereum", "avalanche"]


def test_default_source_is_geckoterminal():
    assert isinstance(WalletTools.trending.source, GeckoTerminalSource)
