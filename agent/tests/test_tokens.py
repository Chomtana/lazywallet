from lazyagent.tokens import TOKENS, find_token


def test_lit_is_lighter_token_with_no_feed():
    lit = find_token("lit")
    assert lit is not None
    assert lit.address == "0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2"
    assert lit.decimals == 18
    assert lit.price_feed is None and lit.fixed_price is None


def test_no_unofficial_tokens():
    assert {t.symbol for t in TOKENS} == {"ETH", "USDC", "USDT", "DAI", "WBTC", "WETH", "LIT"}
