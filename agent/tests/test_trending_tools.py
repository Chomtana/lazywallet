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
    logo = "https://coin-images.coingecko.com/coins/images/1/large/coq.png"
    tools = make(FakeTrendingSource([Pool(TokenInfo("COQ", "COQINU", COQ, logo), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)]))
    result = await tools.list_trending_tokens({})
    assert not result.get("is_error")
    [coq] = json.loads(text(result))["tokens"]
    assert (coq["symbol"], coq["address"], coq["network"], coq["change_24h"], coq["buyable"], coq["note"]) == ("COQ", COQ, "avalanche", -5.1, True, None)
    [card] = tools.send.of_type("tokens")
    assert card["title"] == "Trending memecoins"
    assert card["items"] == [
        {
            "symbol": "COQ", "name": "COQINU", "network": "Avalanche", "address": COQ, "priceUsd": 1.2e-7, "change24h": -5.1,
            "liquidityUsd": 623_823.6, "dex": "LFJ", "buyable": True, "note": None, "image": logo,
        }
    ]


async def test_rwa_with_network():
    source = FakeTrendingSource(tokens={"ethereum": ONDO_BODY})
    tools = make(source)
    result = await tools.list_trending_tokens({"category": "rwa", "network": "Ethereum"})
    [ondo] = json.loads(text(result))["tokens"]
    assert (ondo["symbol"], ondo["network"], ondo["buyable"]) == ("ONDO", "ethereum", False)  # no pool in this body
    assert source.calls == [("tokens", "ethereum", (ONDO,))]
    [card] = tools.send.of_type("tokens")
    assert card["title"] == "Hot RWA tokens"
    assert [(i["symbol"], i["network"], i["buyable"]) for i in card["items"]] == [("ONDO", "Ethereum", False)]


async def test_works_without_an_active_wallet():
    tools = make(FakeTrendingSource([]))
    assert tools.ctx.address is None
    assert json.loads(text(await tools.list_trending_tokens({})))["tokens"] == []
    assert tools.send.of_type("tokens") == []  # nothing to show; the model says so


async def test_bad_arguments_are_errors_without_fetching():
    source = FakeTrendingSource()
    tools = make(source)
    bad = await tools.list_trending_tokens({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be one of: meme, rwa."
    eth_memes = await tools.list_trending_tokens({"category": "meme", "network": "ethereum"})
    assert text(eth_memes) == "meme tokens are only listed on Avalanche."
    assert source.calls == []
    assert tools.send.messages == []


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
