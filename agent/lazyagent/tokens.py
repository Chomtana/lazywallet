from dataclasses import dataclass

ETH_USD_FEED = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
BTC_USD_FEED = "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str | None  # None = native ETH
    decimals: int
    price_feed: str | None = None
    fixed_price: float | None = None


ETH = Token("ETH", None, 18, price_feed=ETH_USD_FEED)

TOKENS = [
    ETH,
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, fixed_price=1.0),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, fixed_price=1.0),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, fixed_price=1.0),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, price_feed=BTC_USD_FEED),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, price_feed=ETH_USD_FEED),
    # Lighter (LIT) — no Chainlink feed; priced from its Uniswap v4 pool.
    Token("LIT", "0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2", 18),
]


AVAX_USD_FEED = "0x0A77230d17318075983913bC2145DB16C7366156"
AVAX_BTC_USD_FEED = "0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743"
AVAX_ETH_USD_FEED = "0x976B3D034E162d8bD72D6b9C989d545b839003b0"

AVAX = Token("AVAX", None, 18, price_feed=AVAX_USD_FEED)

AVAX_TOKENS = [
    AVAX,
    Token("USDC", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6, fixed_price=1.0),
    Token("USDT", "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6, fixed_price=1.0),  # on-chain symbol USDt
    Token("BTC.b", "0x152b9d0FdC40C096757F570A51E494bd4b943E50", 8, price_feed=AVAX_BTC_USD_FEED),
    Token("WETH.e", "0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB", 18, price_feed=AVAX_ETH_USD_FEED),
    Token("WAVAX", "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", 18, price_feed=AVAX_USD_FEED),
]


def find_token(symbol: str, tokens: list[Token] | tuple[Token, ...] = TOKENS) -> Token | None:
    s = symbol.strip().upper()
    return next((t for t in tokens if t.symbol.upper() == s), None)
