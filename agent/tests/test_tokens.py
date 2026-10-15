from lazyagent.tokens import AVAX, AVAX_TOKENS, TOKENS, find_token


def test_lit_is_lighter_token_with_no_feed():
    lit = find_token("lit")
    assert lit is not None
    assert lit.address == "0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2"
    assert lit.decimals == 18
    assert lit.price_feed is None and lit.fixed_price is None


def test_no_unofficial_tokens():
    assert {t.symbol for t in TOKENS} == {"ETH", "USDC", "USDT", "DAI", "WBTC", "WETH", "LIT"}


def test_avalanche_tokens():
    assert [t.symbol for t in AVAX_TOKENS] == ["AVAX", "USDC", "USDT", "BTC.b", "WETH.e"]
    assert AVAX.address is None and AVAX.price_feed == "0x0A77230d17318075983913bC2145DB16C7366156"
    assert find_token("btc.b", AVAX_TOKENS).decimals == 8
    assert find_token("usdt", AVAX_TOKENS).address == "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"
    assert find_token("ETH", AVAX_TOKENS) is None
    assert find_token("USDC").address == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # default stays Ethereum
