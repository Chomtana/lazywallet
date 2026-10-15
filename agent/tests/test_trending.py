import json
from dataclasses import replace
from pathlib import Path

import pytest

from lazyagent.trending import (
    CATEGORY_NETWORKS,
    CATEGORY_TITLES,
    Pool,
    TokenInfo,
    Trending,
    TrendingError,
    is_memecoin,
    parse_args,
    parse_pools,
    rank_memes,
    to_card,
    to_json,
)

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


def test_parse_pools_reads_the_logo_and_drops_placeholders():
    def pool(n: int) -> dict:
        return {"attributes": {}, "relationships": {"base_token": {"data": {"id": f"avax_0x0{n}"}}}}

    def token(n: int, image) -> dict:
        return {"id": f"avax_0x0{n}", "type": "token", "attributes": {"address": f"0x0{n}", "symbol": f"T{n}", "image_url": image}}

    logo = "https://coin-images.coingecko.com/coins/images/1/large/coq.png?1"
    body = {"data": [pool(1), pool(2), pool(3)], "included": [token(1, logo), token(2, "missing.png"), token(3, None)]}
    assert [p.token.image for p in parse_pools(body)] == [logo, None, None]
    [p] = rank_memes([replace(meme("COQ", 1), token=TokenInfo("COQ", "COQINU", COQ, logo))])
    assert p.image == logo


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
    assert "image" not in body["tokens"][0]  # the card shows logos; the model doesn't need them
    assert "card" in body["note"] and "buyable" in body["note"] and "contract address" in body["note"]
    assert json.loads(to_json([]))["tokens"] == []


def test_every_category_has_a_title_that_names_no_chain():
    assert CATEGORY_TITLES == {"meme": "Trending memecoins", "rwa": "Hot RWA tokens"}
    assert set(CATEGORY_TITLES) == set(CATEGORY_NETWORKS)


def test_to_card_is_the_browser_message():
    xaut0 = Trending("XAUt0", "XAUt0", "0x27", "avalanche", 4151.8, 1.4e5, None, 64_072.7, "blackhole-v3", True, "tokenized gold", "https://x/xaut.png")
    ondo = Trending("ONDO", "Ondo", "0xfa", "ethereum", 0.43, 1e6, -7.5, 1.7e6, "uniswap_v3", False)
    assert to_card("rwa", [xaut0, ondo]) == {
        "type": "tokens",
        "title": "Hot RWA tokens",
        "items": [
            {
                "symbol": "XAUt0", "name": "XAUt0", "network": "Avalanche", "address": "0x27", "priceUsd": 4151.8, "change24h": None,
                "liquidityUsd": 64_072.7, "dex": "blackhole-v3", "buyable": True, "note": "tokenized gold", "image": "https://x/xaut.png",
            },
            {
                "symbol": "ONDO", "name": "Ondo", "network": "Ethereum", "address": "0xfa", "priceUsd": 0.43, "change24h": -7.5,
                "liquidityUsd": 1.7e6, "dex": "uniswap_v3", "buyable": False, "note": None, "image": None,
            },
        ],
    }
    assert to_card("meme", [])["title"] == "Trending memecoins"
