import pytest
from test_faucet_client import serve
from web3 import Web3

from lazyagent.dexalot import NATIVE, SandboxQuotes, asset_of, dexalot_rows, dexalot_steps, encode_simple_swap
from lazyagent.tokens import AVAX, AVAX_TOKENS, find_token
from lazyagent.transfers import NoRoute, TransferError

USDC = find_token("USDC", AVAX_TOKENS)
MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
TAKER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
SIG = "0x" + "11" * 65
ORDER = {
    "nonceAndMeta": str((int(TAKER, 16) << 96) | 7), "expiry": "1000", "makerAsset": USDC.address, "takerAsset": NATIVE,
    "maker": MAKER, "taker": TAKER, "makerAmount": "9574000", "takerAmount": str(10**18),
}
ABI = [{
    "name": "simpleSwap", "type": "function", "stateMutability": "payable", "outputs": [],
    "inputs": [
        {"name": "_order", "type": "tuple", "components": [
            {"name": n, "type": t} for n, t in [
                ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
                ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
            ]
        ]},
        {"name": "_signature", "type": "bytes"},
    ],
}]


def test_simple_swap_calldata_matches_abi_encoding():
    c = Web3().eth.contract(abi=ABI)
    values = (int(ORDER["nonceAndMeta"]), 1000, USDC.address, NATIVE, MAKER, TAKER, 9574000, 10**18)
    assert encode_simple_swap(ORDER, SIG) == c.encode_abi("simpleSwap", args=[values, bytes.fromhex(SIG[2:])])


def test_avax_in_is_one_step_with_value():
    [step] = dexalot_steps(AVAX, USDC, {"maker": MAKER, "order": ORDER, "signature": SIG}, allowance=0)
    assert step.label == "Swap AVAX → USDC"
    assert step.request["to"] == MAKER and step.request["value"] == str(10**18)


def test_erc20_in_adds_sized_approval_only_when_needed():
    order = {**ORDER, "makerAsset": NATIVE, "takerAsset": USDC.address, "takerAmount": "10000000", "makerAmount": str(10**18)}
    quote = {"maker": MAKER, "order": order, "signature": SIG}
    steps = dexalot_steps(USDC, AVAX, quote, allowance=0)
    assert [s.label for s in steps] == ["Allow USDC", "Swap USDC → AVAX"]
    assert steps[0].request["to"] == USDC.address and steps[1].request["value"] == "0"
    assert [s.label for s in dexalot_steps(USDC, AVAX, quote, allowance=10_000_000)] == ["Swap USDC → AVAX"]


def test_rows():
    rows = dexalot_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", AVAX, USDC, 10**18, 9_574_000)
    assert {r["label"]: r["value"] for r in rows} == {
        "From": "0xf39F…2266", "Rate": "1 AVAX = 9.574 USDC", "Route": "Dexalot · signed quote at live price",
    }
    assert asset_of(AVAX) == NATIVE and asset_of(USDC) == USDC.address


async def test_sandbox_quotes_posts_and_surfaces_errors():
    server, received = serve(200, {"maker": MAKER, "order": ORDER, "signature": SIG})
    try:
        q = await SandboxQuotes(f"http://127.0.0.1:{server.server_port}").quote(NATIVE, USDC.address, 10**18, TAKER)
        assert q["maker"] == MAKER
        assert received == {"path": "/dexalot/quote", "body": {"token_in": NATIVE, "token_out": USDC.address, "amount_in": str(10**18), "taker": TAKER}}
    finally:
        server.shutdown()
    server, _ = serve(404, {"detail": "Dexalot doesn't offer that pair. Available: AVAX/USDC."})
    try:
        with pytest.raises(NoRoute, match="Available: AVAX/USDC"):  # 404 lets KyberSwap try the pair
            await SandboxQuotes(f"http://127.0.0.1:{server.server_port}").quote(NATIVE, USDC.address, 1, TAKER)
    finally:
        server.shutdown()
    with pytest.raises(TransferError, match="pnpm dev:sandbox"):
        await SandboxQuotes("http://127.0.0.1:1").quote(NATIVE, USDC.address, 1, TAKER)
