import json
from pathlib import Path

import pytest
from http_stub import serve

from lazyagent.unlocks import CoinGeckoCoins, TokenomistHttp

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "test-key-not-real"


def ok(name: str):
    return (200, (FIXTURES / name).read_bytes(), {})


async def test_requests_carry_the_key_in_a_header_only():
    headers: list[dict] = []
    server, seen = serve({"/v5/unlock/events/upcoming": ok("tokenomist_upcoming.json"), "/v5/buyback/layerzero": ok("tokenomist_buyback_layerzero.json")}, headers)
    try:
        src = TokenomistHttp(f"http://127.0.0.1:{server.server_port}/v5", key=lambda: KEY)
        body = await src.upcoming("2026-10-16", "2026-11-15")
        bb = await src.buyback("layerzero", "2026-09-16", "2026-10-16")
    finally:
        server.shutdown()
    assert len(body["data"]) == 4 and bb["data"]["tokenSymbol"] == "ZRO"
    assert seen == [
        "/v5/unlock/events/upcoming?start=2026-10-16&end=2026-11-15&pageSize=200",
        "/v5/buyback/layerzero?start=2026-09-16&end=2026-10-16",
    ]
    assert all(KEY not in path for path in seen)
    assert [{k.lower(): v for k, v in h.items()}.get("x-api-key") for h in headers] == [KEY, KEY]


async def test_token_list_and_burn_paths():
    server, seen = serve({"/v5/token/list": ok("tokenomist_token_list.json"), "/v5/burn/": ok("tokenomist_burn_avalanche.json")})
    try:
        src = TokenomistHttp(f"http://127.0.0.1:{server.server_port}/v5", key=lambda: KEY)
        await src.token_list(["layerzero", "avalanche-2"])
        await src.burn("avalanche-2", "2026-09-16", "2026-10-16")
    finally:
        server.shutdown()
    assert seen == ["/v5/token/list?tokenId=layerzero%2Cavalanche-2", "/v5/burn/avalanche-2?start=2026-09-16&end=2026-10-16"]


async def test_missing_key_never_calls_the_api():
    server, seen = serve({})
    try:
        with pytest.raises(ConnectionError) as e:
            await TokenomistHttp(f"http://127.0.0.1:{server.server_port}/v5", key=lambda: None).upcoming("a", "b")
    finally:
        server.shutdown()
    assert seen == [] and "TOKENOMIST_API_KEY" in str(e.value)


@pytest.mark.parametrize(
    "reply",
    [
        (429, json.dumps({"status": False, "statusCode": 429, "errorMessage": "Monthly credit limit reached"}).encode(), {}),
        (403, json.dumps({"status": False, "statusCode": 403, "errorMessage": "This token is not supported"}).encode(), {}),
        (200, json.dumps({"status": False}).encode(), {}),
    ],
)
async def test_errors_raise_without_the_key(reply):
    server, _ = serve({"/v5/": reply})
    try:
        with pytest.raises(ConnectionError) as e:
            await TokenomistHttp(f"http://127.0.0.1:{server.server_port}/v5", key=lambda: KEY).upcoming("a", "b")
    finally:
        server.shutdown()
    assert KEY not in str(e.value)


async def test_coingecko_coin_list_is_an_array_and_429_raises():
    server, _ = serve({"/ok": ok("coingecko_coins_list_unlocks.json"), "/busy": (429, b'{"status": {"error_code": 429}}', {"retry-after": "60"})})
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        coins = await CoinGeckoCoins(f"{base}/ok").coin_list()
        with pytest.raises(Exception):
            await CoinGeckoCoins(f"{base}/busy").coin_list()
    finally:
        server.shutdown()
    assert [c["id"] for c in coins] == ["bitway", "avalanche-2", "layerzero", "hyperliquid"]
