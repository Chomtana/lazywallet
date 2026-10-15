from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int
    balance_slot: int  # storage slot of the token's balance mapping
    faucet_amount: int  # whole tokens


TOKENS = [
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, 9, 10_000),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, 2, 10_000),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, 2, 10_000),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, 0, 1),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, 3, 5),
    Token("LIT", "0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2", 18, 0, 1_000),
]

ETH_FAUCET_AMOUNT = 100
