import json
from pathlib import Path

from lazyagent.trending import (
    GT_BATCH,
    NOT_RWA,
    PINNED,
    RwaCoin,
    Trending,
    load_rwa_snapshot,
    parse_tokens,
    rank_rwas,
    rwa_addresses,
    rwa_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures"
XAUT0 = "0x2775d5105276781b4b85ba6ea6a6653beed1dd32"  # Avalanche, pinned asset token
NXRA = "0x644192291cc835a93d6330b24ea5f5fedd0eef9e"  # Avalanche project token, no pool
ONDO = "0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3"  # Ethereum project token, base of its pool
RSR = "0x320623b8e4ff03373931769a31fc52a4e78b5d70"  # Ethereum project token, not the base of its pool
LINK = "0x514910771af9ca656af840dff83e8264ecf986ca"  # Ethereum, NOT_RWA
NOTE = "tokenized gold — Avalanche showcase"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def coin(network: str, n: int, mcap: float = 0, volume: float = 0) -> RwaCoin:
    return RwaCoin(network, f"0x{n:040x}", f"coin-{n}", mcap, volume)


def item(network: str, address: str, volume: float = 0, liquidity: float = 0) -> Trending:
    return Trending("T", "Token", address, network, None, volume, None, liquidity, "", liquidity >= 10_000)


def test_pinned_is_xaut0_on_avalanche_with_a_note():
    assert PINNED == [("avalanche", XAUT0, NOTE)]


def test_not_rwa_keeps_project_tokens():
    assert ("ethereum", LINK) in NOT_RWA
    assert not {("ethereum", ONDO), ("ethereum", RSR)} & NOT_RWA


def test_rwa_addresses_keeps_project_tokens_and_drops_asset_tokens():
    coins = rwa_addresses(load("coingecko_markets.json"), load("coingecko_coins_list.json"), {"tether-gold-tokens"})
    assert coins == [RwaCoin("ethereum", ONDO, "ondo-finance", 2108143509, 228379176)]


def test_rwa_addresses_maps_every_supported_network_and_skips_others():
    coins = rwa_addresses(load("coingecko_markets.json"), load("coingecko_coins_list.json"), set())
    assert [(c.network, c.coingecko_id) for c in coins] == [("ethereum", "ondo-finance"), ("avalanche", "tether-gold-tokens")]  # Solana ignored


def test_rwa_addresses_drops_usd_stablecoins_and_coins_missing_from_the_list():
    markets = [{"id": "wrapped-staked-usdt", "symbol": "wstusdt"}, {"id": "ghost", "symbol": "ghost"}]
    coin_list = [{"id": "wrapped-staked-usdt", "platforms": {"ethereum": "0x" + "1" * 40}}]
    assert rwa_addresses(markets, coin_list, set()) == []


def test_candidates_pin_first_and_skip_not_rwa():
    coins = [RwaCoin("ethereum", LINK, "chainlink", 9e9, 4e8), RwaCoin("ethereum", ONDO, "ondo-finance", 2e9, 2e8)]
    assert rwa_candidates(coins, "ethereum") == [ONDO]
    assert rwa_candidates(coins, "avalanche") == [XAUT0]


def test_candidates_mix_busiest_and_largest_and_fill_one_batch():
    busy = [coin("ethereum", i, mcap=1, volume=1_000 + i) for i in range(1, 41)]
    big = [coin("ethereum", 100 + i, mcap=1e9 + i, volume=0) for i in range(1, 41)]
    out = rwa_candidates(busy + big, "ethereum")
    assert len(out) == GT_BATCH
    assert out[:15] == [f"0x{i:040x}" for i in range(40, 25, -1)]  # 15 busiest
    assert out[15] == f"0x{140:040x}"  # then the largest by market cap


def test_parse_tokens_pool_and_no_pool():
    xaut0, nxra = parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert xaut0 == Trending("XAUt0", "XAUt0", XAUT0, "avalanche", 4151.7951702526, 145093.15533864, 0.241, 64072.6693, "blackhole-v3", True)
    assert nxra == Trending("NXRA", "AllianceBlock Nexera Token", NXRA, "avalanche", None, 0.0, None, 0.0, "", False)


def test_parse_tokens_change_only_when_token_is_the_pool_base():
    ondo, rsr = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum")
    assert (ondo.change_24h, ondo.liquidity_usd, ondo.dex, ondo.buyable) == (-7.529, 1765680.8565, "uniswap_v3", True)
    assert (rsr.address, rsr.change_24h, rsr.price_usd, rsr.dex, rsr.buyable) == (RSR, None, 0.001970645956, "curve", True)


def test_parse_tokens_tolerates_an_empty_body_and_unescapes_names():
    assert parse_tokens({}, "ethereum") == []
    [t] = parse_tokens({"data": [{"id": "x", "attributes": {"address": "0xAB", "symbol": "PRO", "name": "Propy &amp; Co"}}]}, "ethereum")
    assert (t.name, t.address) == ("Propy & Co", "0xab")


def test_rank_rwas_pinned_first_with_note_then_volume_then_market_cap():
    coins = [coin("ethereum", 1, mcap=10), coin("ethereum", 2, mcap=99)]
    items = [
        item("ethereum", f"0x{1:040x}"),
        item("ethereum", ONDO, volume=1e6, liquidity=2e6),
        item("avalanche", XAUT0, volume=1e5, liquidity=6e4),
        item("ethereum", f"0x{2:040x}"),
    ]
    ranked = rank_rwas(items, coins)
    assert [t.address for t in ranked] == [XAUT0, ONDO, f"0x{2:040x}", f"0x{1:040x}"]
    assert ranked[0].note == NOTE and ranked[1].note is None


def test_rank_rwas_keeps_unbuyable_drops_not_rwa_and_duplicates_and_caps_at_ten():
    items = [item("ethereum", LINK, volume=1e9, liquidity=1e7), item("avalanche", NXRA, volume=0.5), item("avalanche", NXRA, volume=0.5)]
    items += [item("ethereum", f"0x{i:040x}", volume=i) for i in range(1, 10)]
    ranked = rank_rwas(items, [])
    assert len(ranked) == 10
    assert LINK not in [t.address for t in ranked]
    assert [t.address for t in ranked].count(NXRA) == 1 and ranked[-1].buyable is False


def test_rank_rwas_with_live_fixtures_on_both_networks():
    items = parse_tokens(load("geckoterminal_tokens_eth.json"), "ethereum") + parse_tokens(load("geckoterminal_tokens_avax.json"), "avalanche")
    assert [t.symbol for t in rank_rwas(items, [])] == ["XAUt0", "ONDO", "RSR", "NXRA"]


def test_load_rwa_snapshot(tmp_path):
    path = tmp_path / "rwa.json"
    path.write_text(json.dumps({"generated": "2026-10-15", "coins": [{"network": "ethereum", "address": ONDO, "coingecko_id": "ondo-finance", "market_cap": 1.0, "volume_24h": 2.0}]}))
    assert load_rwa_snapshot(path) == [RwaCoin("ethereum", ONDO, "ondo-finance", 1.0, 2.0)]


def test_shipped_snapshot_has_project_tokens_not_asset_tokens():
    coins = {(c.network, c.address) for c in load_rwa_snapshot()}
    assert ("ethereum", ONDO) in coins  # project token
    assert ("avalanche", XAUT0) not in coins  # tokenized gold — only shown because it's PINNED
    assert all(a == a.lower() and a.startswith("0x") for _, a in coins)
