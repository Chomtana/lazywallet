import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from lazysandbox.dexalot import (
    NATIVE, Pair, QuoteError, build_order, maker_amount, match_pair, parse_pairs, patch_code, sign_order, to_raw, typed_data,
)

USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
USDT = "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"
BTCB = "0x152b9d0FdC40C096757F570A51E494bd4b943E50"
OLD = "0x08ea7d927d13802C3bc4b35B10e394f34a53Fa72"
NEW = "0x458e84C455c1D358EE67D0EE4D144d9B169AEb34"
TAKER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
MAKER = "0x1FDb2b265d2A5C4302A75cAd682222E4e7bCc313"
PAIRS_JSON = {
    "AVAX/USDC": {"base": "AVAX", "quote": "USDC", "baseAddress": NATIVE, "quoteAddress": USDC, "baseDecimals": 18, "quoteDecimals": 6},
    "BTC.b/USDC": {"base": "BTC.b", "quote": "USDC", "baseAddress": BTCB, "quoteAddress": USDC, "baseDecimals": 8, "quoteDecimals": 6},
}


def test_patch_code_replaces_every_aligned_occurrence():
    word = "7f" + "00" * 12 + OLD[2:].lower()
    code = "0x6080" + word + "5b" + word
    patched, n = patch_code(code, OLD, NEW)
    assert n == 2
    assert OLD[2:].lower() not in patched and patched.count(NEW[2:].lower()) == 2
    assert len(patched) == len(code)


def test_patch_code_counts_zero_when_absent():
    assert patch_code("0x6080", OLD, NEW) == ("0x6080", 0)


def test_match_pair_selling_base_and_quote():
    pairs = parse_pairs(PAIRS_JSON)
    pair, side, is_base = match_pair(pairs, NATIVE, USDC)
    assert (pair.name, side, is_base) == ("AVAX/USDC", 1, True)
    pair, side, is_base = match_pair(pairs, USDC.lower(), NATIVE)
    assert (pair.name, side, is_base) == ("AVAX/USDC", 0, False)


def test_match_pair_unknown_lists_available():
    with pytest.raises(QuoteError, match="AVAX/USDC, BTC.b/USDC") as e:
        match_pair(parse_pairs(PAIRS_JSON), NATIVE, BTCB)
    assert e.value.status == 404


def test_maker_amount_uses_the_other_side():
    pair = parse_pairs(PAIRS_JSON)[0]
    reply = {"success": True, "baseAmount": "1.045915699194644911", "quoteAmount": "10"}
    assert maker_amount(reply, pair, True) == 10_000_000
    assert maker_amount(reply, pair, False) == 1_045_915_699_194_644_911
    assert to_raw("9.5749999", 6) == 9_574_999


def test_maker_amount_refuses_failed_or_zero_quotes():
    pair = parse_pairs(PAIRS_JSON)[0]
    with pytest.raises(QuoteError) as e:
        maker_amount({"success": False}, pair, True)
    assert e.value.status == 502
    with pytest.raises(QuoteError, match="too small"):
        maker_amount({"success": True, "quoteAmount": "0", "baseAmount": "0"}, pair, True)


def test_build_order_layout():
    order = build_order(MAKER, TAKER, NATIVE, USDC, 10**18, 9_574_000, now=1_000, nonce=7)
    assert order["nonceAndMeta"] == (int(TAKER, 16) << 96) | 7
    assert (order["nonceAndMeta"] >> 88) & 0xFF == 0  # slipInfo byte must stay 0
    assert order["expiry"] == 1_000 + 900
    assert (order["makerAsset"], order["takerAsset"]) == (USDC, NATIVE)
    assert (order["makerAmount"], order["takerAmount"]) == (9_574_000, 10**18)


def test_sign_order_recovers_to_signer():
    signer = Account.create()
    order = build_order(MAKER, TAKER, NATIVE, USDC, 10**18, 9_574_000, now=1_000, nonce=7)
    sig = sign_order(signer.key, order)
    assert Account.recover_message(encode_typed_data(full_message=typed_data(order)), signature=sig) == signer.address
