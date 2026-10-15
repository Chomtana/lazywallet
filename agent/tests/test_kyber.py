import json

import pytest
from fakes import FakeChain, FakeKyber, kyber_desc, simple_data, swap_data

from lazyagent import kyber
from lazyagent.kyber import (
    NATIVE,
    ROUTER,
    SANDBOX_KYBER_SLIPPAGE_BPS,
    SIMPLE_SELECTOR,
    SWAP_SELECTOR,
    KyberClient,
    SwapRequest,
    Verified,
    allowance_override,
    kyber_label,
    kyber_slippage,
    kyber_steps,
    simulate,
    usd_impact,
    usd_price,
    verify,
)
from lazyagent.networks import AVALANCHE
from lazyagent.tokens import AVAX, Token, find_token
from lazyagent.transfers import NoRoute, TransferError

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
COQ_ADDR = "0x420FcA0121DC28039145009570975747295f2329"
COQ = Token("COQ", COQ_ADDR, 18, custom=True)
USDC = find_token("USDC", AVALANCHE.tokens)
OUT = 78_000_000 * 10**18
FIELDS = ("src", "dst", "srcReceivers", "srcAmounts", "feeReceivers", "feeAmounts", "receiver", "amount", "minReturn", "flags", "permit")
NATIVE_REQ = SwapRequest(NATIVE, COQ_ADDR, 10**18, ME, 5000)


def native_build(**desc_changes) -> dict:
    d = kyber_desc(NATIVE, COQ_ADDR, ME, 10**18, OUT // 2)
    d = tuple(desc_changes.get(k, v) for k, v in zip(FIELDS, d))
    return {"routerAddress": ROUTER, "data": swap_data(d), "transactionValue": str(10**18), "amountOut": str(OUT)}


def test_selectors_match_the_verified_router_abi():
    assert SWAP_SELECTOR == "e21fd0e9"
    assert SIMPLE_SELECTOR == "8af033fb"


def test_verify_accepts_an_honest_native_swap():
    v = verify(native_build(), NATIVE_REQ)
    assert v == Verified(native_build()["data"], 10**18, OUT, OUT // 2)


def test_verify_accepts_swap_simple_mode_for_erc20_input():
    d = kyber_desc(COQ_ADDR, USDC.address, ME, 10**24, 59_509)
    build = {"routerAddress": ROUTER, "data": simple_data(d), "transactionValue": "0", "amountOut": "119018"}
    v = verify(build, SwapRequest(COQ_ADDR, USDC.address, 10**24, ME, 5000))
    assert v.value == 0 and v.minimum == 59_509 and v.data.startswith("0x8af033fb")


@pytest.mark.parametrize(
    ("build", "why"),
    [
        ({**native_build(), "routerAddress": ALICE}, "unexpected router"),
        ({**native_build(), "transactionValue": "0"}, "wrong value"),
        (native_build(receiver=ALICE), "wrong recipient"),
        (native_build(feeReceivers=[ALICE], feeAmounts=[10]), "extra fee"),
        (native_build(minReturn=OUT // 2 - 1), "minimum too low"),
        (native_build(dst=USDC.address), "wrong tokens"),
        (native_build(amount=10**17), "wrong amount"),
        ({**native_build(), "data": "0x12345678" + native_build()["data"][10:]}, "unknown router function"),
        ({**native_build(), "data": "0xe21fd0e9dead"}, "unreadable calldata"),
        ({**native_build(), "amountOut": "0"}, "minimum too low"),
    ],
)
def test_verify_refuses(build, why):
    with pytest.raises(TransferError, match=why):
        verify(build, NATIVE_REQ)


def test_verify_refuses_simple_mode_with_native_input():
    d = kyber_desc(NATIVE, COQ_ADDR, ME, 10**18, OUT // 2)
    build = {"routerAddress": ROUTER, "data": simple_data(d), "transactionValue": str(10**18), "amountOut": str(OUT)}
    with pytest.raises(TransferError, match="unknown router function"):
        verify(build, NATIVE_REQ)


def test_kyber_slippage_defaults_to_the_sandbox_value():
    assert SANDBOX_KYBER_SLIPPAGE_BPS == 5000
    assert kyber_slippage(None) == 5000 and kyber_slippage(" ") == 5000
    assert kyber_slippage("2") == 200
    with pytest.raises(TransferError, match="between 0.01% and 5%"):
        kyber_slippage("50")


def test_kyber_label_and_impact():
    summary = {"route": [[{"exchange": "traderjoe-v22"}, {"exchange": "pmm-8/uniswap"}], [{"exchange": "traderjoe"}, {"exchange": "weird-dex"}]]}
    assert kyber_label(summary) == "KyberSwap via LFJ, Uniswap, weird-dex"
    assert kyber_label({}) == "KyberSwap"
    assert usd_impact({"amountInUsd": "10", "amountOutUsd": "9.9"}) == pytest.approx(0.01)
    assert usd_impact({"amountInUsd": "0", "amountOutUsd": "9.9"}) is None
    assert usd_impact({}) is None


def test_kyber_steps_native_and_erc20():
    v = Verified("0xe21fd0e9", 10**18, OUT, OUT // 2)
    assert [s.to_json() for s in kyber_steps(AVAX, COQ, 10**18, 0, v, 250_000)] == [
        {"label": "Swap AVAX → COQ", "request": {"to": ROUTER, "value": str(10**18), "data": "0xe21fd0e9"}}
    ]
    v0 = Verified("0xe21fd0e9", 0, 119018, 59509)
    steps = kyber_steps(COQ, USDC, 10**24, 0, v0, 250_000)
    assert [s.label for s in steps] == ["Allow COQ", "Swap COQ → USDC"]
    assert steps[0].request["to"] == COQ_ADDR and steps[0].request["data"].startswith("0x095ea7b3")
    assert [s.label for s in kyber_steps(COQ, USDC, 10**24, 10**24, v0, 250_000)] == ["Swap COQ → USDC"]


async def test_allowance_override_finds_the_real_slot():
    chain = FakeChain()
    chain.access_keys = ["0x01", "0xab"]
    chain.allowance_slot = "0xab"
    assert await allowance_override(chain, COQ_ADDR, ME, 5) == {COQ_ADDR: {"stateDiff": {"0xab": "0x" + (5).to_bytes(32, "big").hex()}}}
    chain.allowance_slot = None
    with pytest.raises(TransferError, match="couldn't simulate"):
        await allowance_override(chain, COQ_ADDR, ME, 5)


async def test_simulate_checks_the_returned_amount():
    v = Verified("0xe21fd0e9", 10**18, 1_000, 500)
    chain = FakeChain()
    chain.sim_out = 960
    assert await simulate(chain, ME, v, None) == 960
    assert chain.sim_calls[-1] == ({"from": ME, "to": ROUTER, "data": "0xe21fd0e9", "value": 10**18}, None)
    chain.sim_out = 940
    with pytest.raises(TransferError, match="doesn't match"):
        await simulate(chain, ME, v, None)
    chain.sim_out = RuntimeError("execution reverted")
    with pytest.raises(TransferError, match="fails on the Sandbox fork"):
        await simulate(chain, ME, v, None)


async def test_usd_price_routes_one_usdc_and_inverts():
    k = FakeKyber(out=8_000_000 * 10**18)
    price = usd_price(k, AVALANCHE)
    assert await price(COQ) == pytest.approx(1 / 8_000_000)
    assert k.routes == [("avalanche", USDC.address, COQ_ADDR, 10**6)]
    assert await usd_price(FakeKyber(no_route=True), AVALANCHE)(COQ) is None


async def test_client_route_and_build(monkeypatch):
    calls = []

    def fake_http(url, payload=None, headers=None):
        calls.append((url, payload, headers))
        if url.endswith("/route/build"):
            return 200, {"code": 0, "data": {"data": "0xe21fd0e9", "routerAddress": ROUTER}}
        return 200, {"code": 0, "data": {"routeSummary": {"amountOut": "5"}, "routerAddress": ROUTER}}

    monkeypatch.setattr(kyber, "http_json", fake_http)
    client = KyberClient()
    route = await client.route("avalanche", NATIVE, COQ_ADDR, 10**18)
    assert route["routeSummary"]["amountOut"] == "5"
    assert calls[0][0] == (
        "https://aggregator-api.kyberswap.com/avalanche/api/v1/routes"
        f"?tokenIn={NATIVE}&tokenOut={COQ_ADDR}&amountIn={10**18}"
    )
    assert calls[0][2]["x-client-id"] == "lazywallet" and calls[0][2]["user-agent"]
    await client.build("ethereum", {"amountOut": "5"}, ME, 5000)
    url, payload, _ = calls[1]
    assert url == "https://aggregator-api.kyberswap.com/ethereum/api/v1/route/build"
    assert payload == {"routeSummary": {"amountOut": "5"}, "sender": ME, "recipient": ME, "slippageTolerance": 5000, "skipSimulateTx": True}


async def test_client_errors(monkeypatch):
    monkeypatch.setattr(kyber, "http_json", lambda *a: (400, {"code": 4008, "message": "route not found"}))
    with pytest.raises(NoRoute, match="route not found"):
        await KyberClient().route("avalanche", NATIVE, COQ_ADDR, 1)
    with pytest.raises(TransferError, match="couldn't build"):
        await KyberClient().build("avalanche", {}, ME, 5000)

    def down(*a):
        raise ConnectionError("no network")

    monkeypatch.setattr(kyber, "http_json", down)
    with pytest.raises(TransferError, match="isn't reachable"):
        await KyberClient().route("avalanche", NATIVE, COQ_ADDR, 1)


def test_http_json_reads_error_bodies(monkeypatch):
    import io
    import urllib.error

    def raise_400(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(json.dumps({"message": "invalid"}).encode()))

    monkeypatch.setattr(kyber.urllib.request, "urlopen", raise_400)
    assert kyber.http_json("https://x.test/a") == (400, {"message": "invalid"})
