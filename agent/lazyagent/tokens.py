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
]


def find_token(symbol: str) -> Token | None:
    s = symbol.strip().upper()
    return next((t for t in TOKENS if t.symbol == s), None)
