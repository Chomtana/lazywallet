import json
import urllib.error
from pathlib import Path

import pytest
from fakes import FakeTrendingSource
from http_stub import serve

from lazyagent.trending import PINNED, GeckoTerminalSource, Pool, RwaCoin, TokenInfo, TrendingTokens

FIXTURES = Path(__file__).parent / "fixtures"
COQ_POOL = Pool(TokenInfo("COQ", "COQINU", "0x420fca0121dc28039145009570975747295f2329"), 1.2e-7, 16_937.5, -5.1, 623_823.6, "LFJ", 0)
XAUT0 = PINNED[0][1]
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"
RSR = "0x320623b8e4ff03373931769a31fc52a4e78b5d70"


def ok(name: str):
    return (200, (FIXTURES / name).read_bytes(), {})


async def test_meme_pools_fetch_trending_and_arena():
    server, seen = serve({"/avax/trending_pools": ok("geckoterminal_trending.json"), "/avax/dexes/arena-dex/pools": ok("geckoterminal_arena.json")})
    try:
        pools = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").meme_pools()
    finally:
        server.shutdown()
    assert [(p.token.symbol, p.trending) for p in pools] == [("BTC.b", 0), ("COQ", 1), ("GATOR", None), ("NOCHILL", None)]
    assert seen == ["/avax/trending_pools?include=base_token,dex", "/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex"]


async def test_tokens_batch_url_per_network():
    server, seen = serve({"/eth/tokens/multi/": ok("geckoterminal_tokens_eth.json")})
    try:
        body = await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").tokens("ethereum", [ONDO, RSR])
    finally:
        server.shutdown()
    assert len(body["data"]) == 2
    assert seen == [f"/eth/tokens/multi/{ONDO},{RSR}?include=top_pools"]


async def test_tokens_with_no_addresses_makes_no_request():
    assert await GeckoTerminalSource("http://127.0.0.1:1").tokens("avalanche", []) == {}


async def test_source_raises_on_rate_limit():
    server, _ = serve({"/avax/trending_pools": (429, b'{"status":"429","error":"Rate limited"}', {})})
    try:
        with pytest.raises(urllib.error.HTTPError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").meme_pools()
    finally:
        server.shutdown()


async def test_source_raises_on_non_json_body():
    server, _ = serve({"/": (200, b"<html>oops</html>", {})})
    try:
        with pytest.raises(ValueError):
            await GeckoTerminalSource(f"http://127.0.0.1:{server.server_port}").tokens("avalanche", [XAUT0])
    finally:
        server.shutdown()


async def test_source_raises_when_unreachable():
    with pytest.raises(OSError):
        await GeckoTerminalSource("http://127.0.0.1:1").meme_pools()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def tokens_fixtures() -> dict:
    return {
        "ethereum": json.loads((FIXTURES / "geckoterminal_tokens_eth.json").read_text()),
        "avalanche": json.loads((FIXTURES / "geckoterminal_tokens_avax.json").read_text()),
    }


SNAPSHOT = [RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8), RwaCoin("ethereum", RSR, "reserve-rights-token", 1e8, 3e7)]


async def test_cache_serves_within_60_seconds_and_refetches_after():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=clock)
    first = await trending.fetch()
    clock.t += 59.9
    assert await trending.fetch() == first and len(source.calls) == 1
    clock.t += 0.2
    await trending.fetch()
    assert len(source.calls) == 2


async def test_cache_is_per_category_and_network():
    source = FakeTrendingSource([COQ_POOL], tokens_fixtures())
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=Clock())
    await trending.fetch("meme")
    await trending.fetch("rwa", "avalanche")
    await trending.fetch("rwa", "avalanche")
    await trending.fetch("rwa")
    assert source.calls == [
        ("meme_pools",),
        ("tokens", "avalanche", (XAUT0,)),
        ("tokens", "ethereum", (ONDO, RSR)),
        ("tokens", "avalanche", (XAUT0,)),
    ]


async def test_rwa_lists_both_networks_with_pinned_first():
    trending = TrendingTokens(FakeTrendingSource(tokens=tokens_fixtures()), lambda: SNAPSHOT, clock=Clock())
    both = await trending.fetch("rwa")
    assert [(t.symbol, t.network) for t in both] == [("XAUt0", "avalanche"), ("ONDO", "ethereum"), ("RSR", "ethereum"), ("NXRA", "avalanche")]
    assert both[0].note == PINNED[0][2]
    eth = await trending.fetch("rwa", "ethereum")
    assert [t.symbol for t in eth] == ["ONDO", "RSR"]


async def test_errors_are_not_cached():
    source, clock = FakeTrendingSource([COQ_POOL]), Clock()
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=clock)
    source.fail = True
    with pytest.raises(ConnectionError):
        await trending.fetch()
    source.fail = False
    assert [t.symbol for t in await trending.fetch()] == ["COQ"]
    assert len(source.calls) == 2


async def test_an_empty_list_is_cached_too():
    source = FakeTrendingSource([])
    trending = TrendingTokens(source, lambda: SNAPSHOT, clock=Clock())
    assert await trending.fetch() == [] and await trending.fetch() == []
    assert len(source.calls) == 1
