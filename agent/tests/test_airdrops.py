import json

import pytest
from fakes import FakeGeckoPools, FakeLlama
from web3 import Web3

from lazyagent.airdrops import (
    DATA,
    MAX_RESULTS,
    PROGRAMS,
    AirdropError,
    Airdrops,
    card,
    enrich,
    farm_rows,
    farm_summary,
    filter_programs,
    find_program,
    load_curated,
    parse_args,
    parse_program,
    rank,
    to_json,
)

THUSD = "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3"
REUSD_ETH = "0x5086bf358635B81D8C47C66d1C8b9E567Db70c72"
REUSD_AVAX = "0x180aF87b47Bf272B2df59dccf2D76a6eaFa625Bf"
AVUSD = "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346"


def program(id_: str):
    return next(p for p in PROGRAMS if p.id == id_)


def raw(id_: str) -> dict:
    return next(d for d in json.loads(DATA.read_text()) if d["id"] == id_)


def test_the_real_curated_file_is_valid():
    programs = load_curated()
    assert [p.id for p in programs] == ["theo-thusd", "re", "tori", "avant", "suzaku-s2", "aave-v4-avax"]
    for p in programs:
        for t in p.farm_tokens:
            assert Web3.is_checksum_address(t.address)
        if p.deposit:
            assert p.deposit.asset in p.farm_tokens and p.deposit.network in p.networks
    assert [p.id for p in programs if p.deposit] == ["theo-thusd", "avant"]
    theo = program("theo-thusd").deposit
    assert (theo.name, theo.network, theo.venue, theo.vault.address, theo.asset.address, theo.pay, theo.fee, theo.tick_spacing) == (
        "Theo", "ethereum", "uniswap_v4_pinned_then_kyber", "0xA808Bc9775cb41c52C7842f8b50427fE7A770326", THUSD, "USDC", 100, 1,
    )
    avant = program("avant")
    assert (avant.deposit.name, avant.deposit.network, avant.deposit.venue, avant.deposit.fee) == ("Avant", "avalanche", "kyber", None)
    assert (avant.deposit.asset.address, avant.deposit.asset.decimals) == (AVUSD, 18)
    assert (avant.deposit.vault.symbol, avant.deposit.vault.address) == ("savUSD", "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E")
    # Season 1 is assumed running for the demo; the real state stays on record and no real date is shown.
    assert (avant.status, avant.category, avant.season_ends) == ("live", "other", None)
    assert "ended 2026-05-15" in avant.demo_assumption
    assert all(p.demo_assumption is None for p in programs if p.id != "avant")
    assert avant.featured is True
    assert all(p.featured is False for p in programs if p.id != "avant")


@pytest.mark.parametrize(
    "patch",
    [
        {"category": "airdrop"},
        {"status": "ended"},
        {"networks": ["base"]},
        {"token": "soon"},
        {"farm_tokens": [{"network": "ethereum", "symbol": "thUSD", "address": THUSD.lower(), "decimals": 6}]},
    ],
)
def test_malformed_entries_fail_loudly(patch):
    with pytest.raises((ValueError, KeyError)):
        parse_program({**raw("theo-thusd"), **patch})


def test_deposit_asset_must_be_a_farm_token():
    bad = raw("theo-thusd")
    bad["deposit"] = {**bad["deposit"], "asset": REUSD_ETH}
    with pytest.raises(ValueError, match="farm tokens"):
        parse_program(bad)


def test_deposit_venue_must_be_known_and_v4_only_on_ethereum():
    unknown = raw("avant")
    unknown["deposit"] = {**unknown["deposit"], "venue": "dexalot"}
    with pytest.raises(ValueError, match="unknown deposit venue"):
        parse_program(unknown)
    v4_on_avalanche = raw("avant")
    v4_on_avalanche["deposit"] = {**v4_on_avalanche["deposit"], "venue": "uniswap_v4_pinned_then_kyber", "route": {"fee": 100, "tick_spacing": 1}}
    with pytest.raises(ValueError, match="needs network ethereum"):
        parse_program(v4_on_avalanche)


def test_find_program_by_id_or_farm_name():
    assert find_program("theo-thusd").id == "theo-thusd"
    assert find_program(" THEO ").id == "theo-thusd"
    assert find_program("Avant").id == "avant"
    assert find_program("re").id == "re"
    assert find_program("nope") is None


# --- enrichment, ranking, card ---


def pools(*reserves) -> dict:
    return {"data": [{"attributes": {"reserve_in_usd": str(r)}} for r in reserves]}


def llama(tvls: dict, symbol="-", gecko_id=None) -> dict:
    return {"currentChainTvls": tvls, "symbol": symbol, "gecko_id": gecko_id}


def test_enrich_sums_tvl_over_the_programs_networks_only():
    a = enrich(program("re"), llama({"Ethereum": 400e6, "Avalanche": 5e3, "Base": 4e6, "Ethereum-borrowed": 1e9}), {})
    assert a.tvl_usd == 400e6 + 5e3
    assert enrich(program("re"), llama({"Base": 4e6}), {}).tvl_usd is None


def test_token_launched_flips_only_for_programs_without_a_token():
    assert enrich(program("theo-thusd"), llama({}, gecko_id="theo"), {}).token_launched is True
    assert enrich(program("theo-thusd"), llama({}, symbol="THEO"), {}).token_launched is True
    assert enrich(program("theo-thusd"), llama({}), {}).token_launched is False
    assert enrich(program("re"), llama({}, symbol="RE", gecko_id="re"), {}).token_launched is False  # already "live: RE"


def test_buyable_at_the_10k_rule_and_unknown_when_lookup_failed():
    a = enrich(program("re"), None, {REUSD_ETH.lower(): pools(25e6, 2e6), REUSD_AVAX.lower(): pools(6151.3, 93)})
    assert [(t.network, t.liquidity_usd, t.buyable) for t in a.farm_tokens] == [("ethereum", 25e6, True), ("avalanche", 6151.3, False)]
    assert enrich(program("re"), None, {REUSD_ETH.lower(): pools(10_000)}).farm_tokens[0].buyable is True
    assert enrich(program("re"), None, {REUSD_ETH.lower(): pools()}).farm_tokens[0].buyable is False
    unknown = enrich(program("re"), None, {REUSD_ETH.lower(): None})
    assert (unknown.tvl_usd, unknown.farm_tokens[0].liquidity_usd, unknown.farm_tokens[0].buyable) == (None, None, None)


def test_rank_featured_then_rwa_then_status_then_executable_then_tvl():
    items = [enrich(p, llama({"Ethereum": 1e9, "Avalanche": 1e9}), {}) for p in PROGRAMS]
    assert [a.program.id for a in rank(items)] == ["avant", "theo-thusd", "re", "tori", "aave-v4-avax", "suzaku-s2"]
    # Without enrichment the curated order still holds: RWA → other, live → unverified → claim_pending.
    plain = [a.program.id for a in rank([enrich(p, None, {}) for p in PROGRAMS])]
    assert plain[:3] == ["avant", "theo-thusd", "re"] and plain[-1] == "suzaku-s2"


def test_rank_puts_buyable_and_tokenless_ahead_at_equal_status():
    tori = enrich(program("tori"), llama({"Ethereum": 1}), {"0xd0580192e98ea6ceb9c7b6191ed2e27560911697": pools(2.6e6)})
    aave = enrich(program("aave-v4-avax"), llama({"Avalanche": 1e9}), {})
    assert [a.program.id for a in rank([aave, tori])] == ["tori", "aave-v4-avax"]


def test_filter_and_args():
    assert [p.id for p in filter_programs(PROGRAMS, "rwa", None)] == ["theo-thusd", "re"]
    assert [p.id for p in filter_programs(PROGRAMS, "all", "avalanche")] == ["re", "avant", "suzaku-s2", "aave-v4-avax"]
    assert [p.id for p in filter_programs(PROGRAMS, "other", "avalanche")] == ["avant", "suzaku-s2", "aave-v4-avax"]
    assert [p.id for p in filter_programs(PROGRAMS, "rwa", "avalanche")] == ["re"]
    assert parse_args({}) == ("all", None)
    assert parse_args({"category": "RWA", "network": "Avalanche"}) == ("rwa", "avalanche")
    with pytest.raises(AirdropError, match="category must be one of: rwa, other, all."):
        parse_args({"category": "meme"})
    with pytest.raises(AirdropError, match="network must be one of: ethereum, avalanche."):
        parse_args({"network": "base"})


def test_to_json_entry_shape():
    a = enrich(program("re"), llama({"Ethereum": 1.5e6}), {REUSD_ETH.lower(): pools(25e6)})
    [entry] = json.loads(to_json([a]))["airdrops"]
    assert list(entry) == [
        "id", "name", "category", "networks", "status", "reward", "token", "token_launched", "season_ends", "action",
        "action_kind", "executable", "kyc", "farm_tokens", "tvl_usd", "source_url", "verified_at", "demo_assumption",
    ]
    assert entry["farm_tokens"][0] == {"network": "ethereum", "symbol": "reUSD", "address": REUSD_ETH, "liquidity_usd": 25e6, "buyable": True}
    assert entry["farm_tokens"][1]["buyable"] is None
    assert "earn no real points" in json.loads(to_json([a]))["points"]
    assert "sandbox" not in json.loads(to_json([a]))["points"].lower()


def test_card_titles_never_name_a_chain_and_buttons_follow_the_data():
    theo = enrich(program("theo-thusd"), llama({"Ethereum": 132e6}), {THUSD.lower(): pools(3.5e6)})
    re_ = enrich(program("re"), None, {REUSD_ETH.lower(): pools(25e6), REUSD_AVAX.lower(): pools(6e3)})
    avant = enrich(program("avant"), None, {})
    msg = card([theo, re_, avant], "rwa")
    assert msg["type"] == "airdrops" and msg["title"] == "RWA airdrops"
    assert card([], "all")["title"] == card([], "other")["title"] == "Airdrops"
    t, r, a = msg["items"]
    assert t == {
        "id": "theo-thusd", "name": "Theo thUSD Points", "category": "rwa", "networks": ["Ethereum"], "status": "live",
        "action": "Stake thUSD (a T-bill-backed dollar) into sthUSD", "tvlUsd": 132e6, "farm": "Theo", "buy": None,
    }
    assert (r["farm"], r["buy"]) == (None, {"symbol": "reUSD", "address": REUSD_ETH})
    assert (a["farm"], a["buy"], a["status"], a["networks"]) == ("Avant", None, "live", ["Avalanche"])
    # Asked for one network: only that network's farm token, and never one known to be unbuyable.
    assert card([re_], "all", "avalanche")["items"][0]["buy"] is None
    assert card([enrich(program("re"), None, {})], "all")["items"][0]["buy"] == {"symbol": "reUSD", "address": REUSD_ETH}  # unknown → offer


# --- live sources and cache ---


async def test_list_enriches_ranks_and_caps():
    source = Airdrops(FakeLlama({"theo-network-thusd": llama({"Ethereum": 132e6})}), FakeGeckoPools({THUSD.lower(): pools(3.5e6)}))
    items = await source.list()
    assert len(items) == len(PROGRAMS) <= MAX_RESULTS
    assert items[0].program.id == "avant"
    theo = next(a for a in items if a.program.id == "theo-thusd")
    assert theo.tvl_usd == 132e6 and theo.farm_tokens[0].buyable is True
    assert all(a.tvl_usd is None for a in items if a is not theo)  # every other lookup failed → curated data with nulls


async def test_cache_is_10_minutes_and_errors_are_not_cached():
    now = [0.0]
    llama_src = FakeLlama({"theo-network-thusd": llama({"Ethereum": 1})})
    gecko = FakeGeckoPools({})
    source = Airdrops(llama_src, gecko, clock=lambda: now[0])
    await source.list("rwa")
    await source.list("rwa")
    assert llama_src.calls.count("theo-network-thusd") == 1
    assert llama_src.calls.count("re") == 2  # failed both times, never cached
    assert gecko.calls.count(("ethereum", THUSD)) == 2
    now[0] = 601
    await source.list("rwa")
    assert llama_src.calls.count("theo-network-thusd") == 2


def farm_tokens():
    from lazyagent.tokens import AVAX_TOKENS, Token, find_token

    usdc = find_token("USDC", AVAX_TOKENS)
    avusd = Token("avUSD", AVUSD, 18, custom=True)
    savusd = Token("savUSD", "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E", 18, custom=True)
    return usdc, avusd, savusd


def test_farm_summary_is_a_three_stage_flow():
    usdc, avusd, savusd = farm_tokens()
    dep = program("avant").deposit
    s = farm_summary(dep, "Avalanche", usdc, avusd, savusd, 50 * 10**6, 50_002 * 10**15, 49_501 * 10**15, 41_3 * 10**17,
                     via="KyberSwap via Pharaoh", fee_usd=0.021, impact=0.001, prices=(1.0, 1.0))
    assert s == {
        "kind": "farm",
        "network": "Avalanche",
        "pay": {"symbol": "USDC", "amount": "50", "usd": 50.0, "logo": usdc.logo},
        "swap": {"symbol": "avUSD", "amount": "≈ 50.002", "via": "KyberSwap via Pharaoh", "logo": None},
        "receive": {"symbol": "savUSD", "amount": "≈ 41.3", "usd": 49.5, "logo": None, "note": "staked avUSD"},
        "fee": "≈ $0.02",
        "program": "Avant points program",
        "warning": None,
    }
    assert farm_summary(dep, "Avalanche", usdc, avusd, savusd, 1, 1, 1, 1, via="x", fee_usd=0, impact=0.2, prices=(None, None))["warning"] == "Price impact 20.0%"


def test_farm_rows_hold_the_details_without_minimum_slippage_or_points():
    usdc, avusd, savusd = farm_tokens()
    rows = farm_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", program("avant"), usdc, avusd, savusd,
                     50_002 * 10**15, 49_501 * 10**15, 41_3 * 10**17, "KyberSwap via Pharaoh", 0.001)
    assert {r["label"]: r["value"] for r in rows} == {
        "From": "0xf39F…2266",
        "Route": "USDC → avUSD · KyberSwap via Pharaoh",
        "Price impact": "0.10%",
        "Stake": "49.501 avUSD → ≈ 41.3 savUSD",
        "Left in wallet": "≈ 0.501 avUSD",
        "Program": "Avant Season 1 points — " + program("avant").reward,
        "avUSD address": AVUSD,
        "savUSD address": savusd.address,
    }
