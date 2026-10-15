import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import FakeCoinList, FakeTokenomist, FakeTrendingSource

from lazyagent.tokens import AVAX
from lazyagent.trending import parse_tokens
from lazyagent.unlocks import (
    UNAVAILABLE,
    Listing,
    TokenMeta,
    Unlock,
    UnlockError,
    Unlocks,
    ethereum_addresses,
    listing,
    parse_token_list,
    parse_upcoming,
    percent_of_supply,
    period_usd,
    soonest,
    to_card,
    unlocks_reply,
)

FIXTURES = Path(__file__).parent / "fixtures"
ZRO = "0x6985884c4392d348587b19cb9eaaf157f13271cd"
BTW = "0x3a63de3572c69a1307ff08394f3ee7702c16d25d"
NOW = datetime(2026, 10, 16, tzinfo=UTC)


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


UPCOMING = load("tokenomist_upcoming.json")
TOKEN_LIST = load("tokenomist_token_list.json")
COINS = load("coingecko_coins_list_unlocks.json")
GT = load("geckoterminal_tokens_unlocks.json")


# --- parsing ---


def test_parse_upcoming_reads_totals_and_allocation():
    unlocks = {u.token_id: u for u in parse_upcoming(UPCOMING)}
    assert set(unlocks) == {"layerzero", "bitway", "hyperliquid", "avalanche-2"}
    zro = unlocks["layerzero"]
    assert (zro.symbol, zro.name, zro.date) == ("ZRO", "LayerZero", "2026-10-20T11:00:00Z")
    assert zro.amount == 25708334 and zro.usd == pytest.approx(53_987_501.4)
    assert zro.allocation == "Investors, Team"  # biggest two standard allocations, by value
    assert unlocks["bitway"].allocation == "Community"
    assert unlocks["avalanche-2"].allocation == "Reserve"


def test_parse_upcoming_skips_malformed_entries():
    body = {"data": [{"tokenId": "x"}, {"tokenId": "y", "tokenSymbol": "Y", "upcomingEvent": {"unlockDate": "2026-10-20T00:00:00Z"}}]}
    [y] = parse_upcoming(body)
    assert (y.symbol, y.name, y.usd, y.amount, y.allocation) == ("Y", "Y", None, 0.0, None)
    assert parse_upcoming({}) == []


def test_soonest_keeps_the_window_takes_the_biggest_and_sorts_by_date():
    unlocks = parse_upcoming(UPCOMING)
    assert [u.symbol for u in soonest(unlocks, NOW)] == ["ZRO", "BTW", "HYPE", "AVAX"]
    # past events and events at/after the window's end drop out
    later = datetime(2026, 10, 25, tzinfo=UTC)
    assert [u.symbol for u in soonest(unlocks, later, days=14)] == ["BTW", "HYPE"]
    # top-N by USD value, then date order
    assert [u.symbol for u in soonest(unlocks, NOW, top=2)] == ["BTW", "HYPE"]


def test_parse_token_list():
    meta = parse_token_list(TOKEN_LIST)
    assert meta["layerzero"] == TokenMeta(1e9, True, False)
    assert meta["avalanche-2"] == TokenMeta(720e6, False, True)
    assert meta["bitway"].has_buyback is False and meta["bitway"].has_burn is False


def test_percent_of_supply():
    assert percent_of_supply(25_708_334, TokenMeta(1e9, True, False)) == pytest.approx(2.5708334)
    assert percent_of_supply(1, TokenMeta(None, False, False)) is None
    assert percent_of_supply(1, TokenMeta(0, False, False)) is None
    assert percent_of_supply(1, None) is None


def test_period_usd_from_buyback_and_burn_bodies():
    assert period_usd(load("tokenomist_buyback_layerzero.json")) == pytest.approx(352_479.5232)
    assert period_usd(load("tokenomist_burn_avalanche.json")) == pytest.approx(459_773.26, rel=1e-6)
    # Tokenomist's empty period answer
    assert period_usd({"data": {"tokenId": "kaito", "totalBuybackAmount": 0, "totalBuybackValue": None, "buybacks": []}}) is None
    assert period_usd(None) is None


# --- availability ---


def test_ethereum_addresses_from_coingecko_platforms():
    unlocks = parse_upcoming(UPCOMING)
    assert ethereum_addresses(COINS, unlocks) == {"layerzero": ZRO, "bitway": BTW}


def test_ethereum_addresses_need_a_matching_symbol():
    u = Unlock("layerzero", "LZ", "LayerZero", "2026-10-20T11:00:00Z", 1.0, 1.0, None)
    assert ethereum_addresses(COINS, [u]) == {}


def test_listing_uses_dex_liquidity_and_the_avax_exception():
    unlocks = {u.token_id: u for u in parse_upcoming(UPCOMING)}
    gt = {t.address: t for t in parse_tokens(GT, "ethereum")}
    zro = listing(unlocks["layerzero"], ZRO, gt)
    assert (zro.network, zro.address, zro.buyable) == ("ethereum", ZRO, True)
    assert zro.logo and zro.logo.startswith("https://coin-images.coingecko.com/")
    btw = listing(unlocks["bitway"], BTW, gt)
    assert (btw.network, btw.buyable) == ("ethereum", False)  # no pool ≥ $10k
    assert listing(unlocks["hyperliquid"], None, gt) == Listing(None, None, False)
    assert listing(unlocks["avalanche-2"], None, gt) == Listing("avalanche", None, True, AVAX.logo)
    # GeckoTerminal unavailable → availability alone decides
    assert listing(unlocks["layerzero"], ZRO, None) == Listing("ethereum", ZRO, True)


# --- the service ---


def service(tokenomist=None, coins=None, gecko=None, clock=None):
    tokenomist = tokenomist or FakeTokenomist(
        UPCOMING,
        TOKEN_LIST,
        buybacks={"layerzero": load("tokenomist_buyback_layerzero.json")},
        burns={"avalanche-2": load("tokenomist_burn_avalanche.json")},
    )
    t = [0.0]
    return Unlocks(
        tokenomist,
        coins or FakeCoinList(COINS),
        gecko or FakeTrendingSource(tokens={"ethereum": GT}),
        clock=clock or (lambda: t[0]),
        now=lambda: NOW,
    ), tokenomist, t


async def test_fetch_merges_buybacks_burns_and_availability():
    unlocks, tokenomist, _ = service()
    items = await unlocks.fetch()
    by = {i.unlock.symbol: i for i in items}
    assert [i.unlock.symbol for i in items] == ["ZRO", "BTW", "HYPE", "AVAX"]
    assert by["ZRO"].buyback_usd == pytest.approx(352_479.5232) and by["ZRO"].burn_usd is None
    assert by["AVAX"].burn_usd == pytest.approx(459_773.26, rel=1e-6) and by["AVAX"].buyback_usd is None
    assert by["HYPE"].buyback_usd is None and by["HYPE"].burn_usd is None  # flagged, but the lookup failed
    assert by["BTW"].buyback_usd is None and by["BTW"].burn_usd is None  # not flagged: not looked up
    assert by["ZRO"].percent_of_supply == pytest.approx(2.5708334)
    assert [c[0] for c in tokenomist.calls].count("buyback") == 2  # layerzero, hyperliquid
    assert ("upcoming", "2026-10-16", "2026-11-15") in tokenomist.calls
    assert ("buyback", "layerzero", "2026-09-16", "2026-10-16") in tokenomist.calls


async def test_fetch_is_cached_for_ten_minutes_and_errors_are_not():
    tokenomist = FakeTokenomist(UPCOMING, TOKEN_LIST)
    tokenomist.fail = True
    unlocks, _, t = service(tokenomist)
    with pytest.raises(ConnectionError):
        await unlocks.fetch()
    tokenomist.fail = False
    first = await unlocks.fetch()
    t[0] = 599
    assert await unlocks.fetch() is first
    assert [c[0] for c in tokenomist.calls].count("upcoming") == 2
    t[0] = 601
    await unlocks.fetch()
    assert [c[0] for c in tokenomist.calls].count("upcoming") == 3


async def test_coin_list_is_cached_for_a_day_and_its_failure_only_hides_availability():
    coins = FakeCoinList(None)
    unlocks, _, t = service(coins=coins)
    items = await unlocks.fetch()
    assert [(i.unlock.symbol, i.listing.network) for i in items] == [("ZRO", None), ("BTW", None), ("HYPE", None), ("AVAX", "avalanche")]
    coins.coins = COINS
    t[0] = 601
    items = await unlocks.fetch()
    assert items[0].listing.network == "ethereum"
    t[0] = 1300
    await unlocks.fetch()
    assert coins.calls == 2  # the successful list is reused


async def test_token_list_failure_drops_only_buybacks_and_burns():
    unlocks, tokenomist, _ = service(FakeTokenomist(UPCOMING, None))
    items = await unlocks.fetch()
    assert len(items) == 4 and all(i.buyback_usd is None and i.burn_usd is None and i.percent_of_supply is None for i in items)
    assert not any(c[0] in ("buyback", "burn") for c in tokenomist.calls)


async def test_geckoterminal_failure_falls_back_to_availability():
    gecko = FakeTrendingSource()
    gecko.fail = True
    unlocks, _, _ = service(gecko=gecko)
    by = {i.unlock.symbol: i for i in await unlocks.fetch()}
    assert by["BTW"].listing.buyable is True and by["BTW"].listing.logo is None


# --- card + reply ---


async def test_card_items_are_camel_case_with_display_networks():
    unlocks, _, _ = service()
    card = to_card(await unlocks.fetch())
    assert card["type"] == "unlocks" and card["title"] == "Upcoming unlocks"
    zro, btw, hype, avax = card["items"]
    assert set(zro) == {
        "symbol", "name", "logo", "date", "unlockUsd", "unlockAmount", "percentOfSupply", "allocation",
        "buybackUsd", "burnUsd", "network", "address", "buyable",
    }
    assert (zro["network"], zro["address"], zro["buyable"], zro["allocation"]) == ("Ethereum", ZRO, True, "Investors, Team")
    assert (avax["network"], avax["address"], avax["buyable"], avax["logo"]) == ("Avalanche", None, True, AVAX.logo)
    assert (hype["network"], hype["buyable"]) == (None, False)
    assert btw["date"] == "2026-11-02T08:00:00Z"


async def test_reply_sends_the_card_and_compact_json():
    unlocks, _, _ = service()
    sent = []

    async def send(msg):
        sent.append(msg)

    text = await unlocks_reply(unlocks, send)
    assert [m["type"] for m in sent] == ["unlocks"]
    data = json.loads(text.split("Data: ", 1)[1])
    zro = data["unlocks"][0]
    assert zro["symbol"] == "ZRO" and zro["network"] == "ethereum" and zro["address"] == ZRO and zro["buyable"] is True
    assert "logo" not in zro
    assert "ONE short sentence" in text


async def test_reply_failure_is_friendly():
    tokenomist = FakeTokenomist(UPCOMING)
    tokenomist.fail = True
    unlocks, _, _ = service(tokenomist)
    with pytest.raises(UnlockError) as e:
        await unlocks_reply(unlocks, lambda m: None)
    assert str(e.value) == UNAVAILABLE == "Couldn't load token unlocks right now."


async def test_reply_with_no_unlocks_sends_no_card():
    unlocks, _, _ = service(FakeTokenomist({"data": []}, TOKEN_LIST))
    sent = []

    async def send(msg):
        sent.append(msg)

    text = await unlocks_reply(unlocks, send)
    assert sent == [] and "No token unlocks" in text
