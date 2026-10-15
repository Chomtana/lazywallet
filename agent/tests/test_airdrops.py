import json

import pytest
from web3 import Web3

from lazyagent.airdrops import (
    DATA,
    PROGRAMS,
    find_program,
    load_curated,
    parse_program,
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
