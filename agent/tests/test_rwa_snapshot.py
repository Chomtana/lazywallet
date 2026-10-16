import json
import urllib.error
from pathlib import Path

import pytest
from http_stub import serve

from lazyagent.rwa_snapshot import CoinGeckoRwaSource, snapshot_json
from lazyagent.trending import RwaCoin, load_rwa_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
MARKETS = json.loads((FIXTURES / "coingecko_markets.json").read_text())  # ondo-finance, tether-gold-tokens
RWA = "/coins/markets?vs_currency=usd&category=real-world-assets-rwa"
ASSETS = "/coins/markets?vs_currency=usd&category=tokenized-products"


def body(obj) -> bytes:
    return json.dumps(obj).encode()


def test_pages_both_categories_and_drops_asset_tokens():
    server, seen = serve(
        {
            RWA: [(200, body(MARKETS[:1]), {}), (200, body(MARKETS[1:]), {}), (200, b"[]", {})],
            ASSETS: [(200, body([{"id": "tether-gold-tokens"}]), {}), (200, b"[]", {})],
            "/coins/list": (200, (FIXTURES / "coingecko_coins_list.json").read_bytes(), {}),
        }
    )
    sleeps = []
    try:
        coins = CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=sleeps.append, per_page=1).coins()
    finally:
        server.shutdown()
    assert seen == [
        f"{RWA}&per_page=1&page=1",
        f"{RWA}&per_page=1&page=2",
        f"{RWA}&per_page=1&page=3",
        f"{ASSETS}&per_page=1&page=1",
        f"{ASSETS}&per_page=1&page=2",
        "/coins/list?include_platform=true",
    ]
    assert [(c.network, c.coingecko_id) for c in coins] == [("ethereum", "ondo-finance")]
    assert sleeps == [15.0] * 5  # after every markets page


def test_waits_out_429_using_retry_after():
    server, _ = serve({"/coins/list": [(429, b"{}", {"Retry-After": "7"}), (200, b"[]", {})]})
    sleeps = []
    try:
        assert CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=sleeps.append).coin_list() == []
    finally:
        server.shutdown()
    assert sleeps == [7.0]


def test_gives_up_after_the_retries():
    server, _ = serve({"/coins/list": (429, b"{}", {"Retry-After": "1"})})
    try:
        with pytest.raises(urllib.error.HTTPError):
            CoinGeckoRwaSource(f"http://127.0.0.1:{server.server_port}", sleep=lambda s: None, retries=2).coin_list()
    finally:
        server.shutdown()


def test_snapshot_json_round_trips_and_sorts(tmp_path):
    coins = [RwaCoin("ethereum", "0x01", "a", 1.0, 1.0), RwaCoin("avalanche", "0x02", "b", 5.0, 0.0), RwaCoin("avalanche", "0x03", "c", 1.0, 9.0)]
    path = tmp_path / "rwa.json"
    path.write_text(snapshot_json(coins, "2026-10-15"))
    assert json.loads(path.read_text())["generated"] == "2026-10-15"
    assert [c.coingecko_id for c in load_rwa_snapshot(path)] == ["c", "b", "a"]
