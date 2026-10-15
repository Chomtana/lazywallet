import json
from dataclasses import replace
from pathlib import Path

import pytest

from lazyagent.trending import Pool, TokenInfo, Trending, TrendingError, is_memecoin, parse_args, parse_pools, rank_memes, to_json

FIXTURES = Path(__file__).parent / "fixtures"
COQ = "0x420fca0121dc28039145009570975747295f2329"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def pools() -> list[Pool]:
    return parse_pools(load("geckoterminal_trending.json"), trending=True) + parse_pools(load("geckoterminal_arena.json"))


def meme(symbol: str, n: int, liquidity: float = 50_000, volume: float = 1_000, trending: int | None = None) -> Pool:
    return Pool(TokenInfo(symbol, f"{symbol} coin", f"0x{n:040x}"), 0.01, volume, 1.0, liquidity, "LFJ", trending)


def test_parse_pools_reads_token_numbers_and_dex_name():
    btc, coq = parse_pools(load("geckoterminal_trending.json"), trending=True)
    assert coq.token == TokenInfo("COQ", "COQINU", COQ)
    assert (coq.price_usd, coq.volume_24h, coq.change_24h, coq.liquidity_usd) == (0.000000121646674452088, 16937.5461895205, -5.1, 623823.6468)
    assert (coq.dex, coq.trending, btc.trending) == ("LFJ", 1, 0)


def test_parse_pools_without_trending_has_no_position():
    gator, nochill = parse_pools(load("geckoterminal_arena.json"))
    assert (gator.trending, nochill.trending, gator.dex) == (None, None, "Arena DEX")


def test_parse_pools_skips_pools_without_base_token_and_zeroes_missing_numbers():
    body = {
        "data": [
            {"attributes": {"name": "GHOST / WAVAX"}, "relationships": {"base_token": {"data": {"id": "avax_0xdead"}}}},
            {
                "attributes": {"base_token_price_usd": None, "volume_usd": {}, "reserve_in_usd": None},
                "relationships": {"base_token": {"data": {"id": "avax_0x01"}}, "dex": {"data": {"id": "mystery-dex"}}},
            },
        ],
        "included": [{"id": "avax_0x01", "type": "token", "attributes": {"address": "0x01", "symbol": "NEW"}}],
    }
    [p] = parse_pools(body)
    assert p.token == TokenInfo("NEW", "NEW", "0x01")
    assert (p.price_usd, p.volume_24h, p.change_24h, p.liquidity_usd, p.dex) == (0.0, 0.0, 0.0, 0.0, "mystery-dex")


def test_parse_pools_tolerates_an_empty_body():
    assert parse_pools({}) == []


def test_memecoin_filter_on_fixtures():
    assert {p.token.symbol: is_memecoin(p.token) for p in pools()} == {"BTC.b": False, "COQ": True, "GATOR": True, "NOCHILL": True}


def test_memecoin_filter_excludes_curated_protocol_tokens():
    assert not is_memecoin(TokenInfo("JOE", "JoeToken", "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd"))


def test_memecoin_filter_matches_registry_addresses_in_any_case():
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0x152b9d0FdC40C096757F570A51E494bd4b943E50"))  # BTC.b checksummed
    assert not is_memecoin(TokenInfo("XYZ", "XYZ", "0xB31F66AA3C1E785363F0875A1B74E27B85FD66C7"))  # WAVAX upper-case


def test_memecoin_filter_symbol_and_name_rules():
    def ok(symbol, name="Some Coin"):
        return is_memecoin(TokenInfo(symbol, name, "0x" + "1" * 40))

    assert not ok("avUSD") and not ok("AUSD") and not ok("EURC") and not ok("XAUt0")
    assert not ok("WAVAX") and not ok("sAVAX") and not ok("WBTC") and not ok("WETH.e") and not ok("LINK.e")
    assert not ok("p33", "Pharaoh Liquid Staking Token") and not ok("FOO", "Wrapped Foo") and not ok("BAR", "Bridged Bar")
    assert ok("KET") and ok("NOCHILL", "AVAX HAS NO CHILL")


def test_rank_memes_on_fixtures_drops_majors_and_thin_pools():
    ranked = rank_memes(pools())
    assert [t.symbol for t in ranked] == ["COQ", "GATOR"]  # BTC.b: major; NOCHILL: $2,050 liquidity
    assert ranked[0] == Trending("COQ", "COQINU", COQ, "avalanche", 0.000000121646674452088, 16937.5461895205, -5.1, 623823.6468, "LFJ", True)
    assert ranked[1].dex == "Arena DEX"


def test_rank_memes_keeps_one_entry_per_token_from_its_deepest_pool_and_best_trending_position():
    shallow = meme("DOG", 1, liquidity=20_000, volume=9_000, trending=3)
    deep = replace(shallow, liquidity_usd=900_000, volume_24h=100, dex="Pharaoh Exchange V3", trending=None)
    ranked = rank_memes([meme("CAT", 2, trending=5), deep, shallow])
    assert [t.symbol for t in ranked] == ["DOG", "CAT"]
    assert ranked[0].liquidity_usd == 900_000 and ranked[0].dex == "Pharaoh Exchange V3"


def test_rank_memes_liquidity_threshold_applies_to_the_deepest_pool():
    assert rank_memes([meme("THIN", 1, liquidity=9_999.99)]) == []
    assert [t.symbol for t in rank_memes([meme("EDGE", 1, liquidity=10_000)])] == ["EDGE"]


def test_rank_memes_puts_trending_first_then_volume():
    ranked = rank_memes([meme("A", 1, volume=10), meme("B", 2, volume=500), meme("C", 3, volume=1, trending=4), meme("D", 4, volume=1, trending=0)])
    assert [t.symbol for t in ranked] == ["D", "C", "B", "A"]


def test_rank_memes_caps_at_ten():
    ranked = rank_memes([meme(f"M{i}", i, volume=i) for i in range(1, 16)])
    assert len(ranked) == 10 and ranked[0].symbol == "M15"


def test_parse_args_defaults_and_normalises():
    assert parse_args({}) == ("meme", None)
    assert parse_args({"category": " RWA ", "network": "Ethereum"}) == ("rwa", "ethereum")
    assert parse_args({"category": "meme", "network": "avalanche"}) == ("meme", "avalanche")


def test_parse_args_rejects_unknown_category_and_unsupported_network():
    with pytest.raises(TrendingError, match="^category must be one of: meme, rwa.$"):
        parse_args({"category": "nft"})
    with pytest.raises(TrendingError, match="^meme tokens are only listed on Avalanche.$"):
        parse_args({"category": "meme", "network": "ethereum"})
    with pytest.raises(TrendingError, match="^rwa tokens are only listed on Ethereum and Avalanche.$"):
        parse_args({"category": "rwa", "network": "solana"})


def test_to_json_lists_tokens_for_the_model():
    body = json.loads(to_json(rank_memes(pools())))
    assert body["tokens"][0] == {
        "symbol": "COQ",
        "name": "COQINU",
        "address": COQ,
        "network": "avalanche",
        "price_usd": 0.000000121646674452088,
        "volume_24h": 16937.5461895205,
        "change_24h": -5.1,
        "liquidity_usd": 623823.6468,
        "dex": "LFJ",
        "buyable": True,
        "note": None,
    }
    assert "buyable" in body["note"] and "contract address" in body["note"]
    assert json.loads(to_json([]))["tokens"] == []
