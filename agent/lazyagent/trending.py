"""Trending tokens from live mainnet data (read-only): Avalanche memecoins and RWA project tokens on
Ethereum + Avalanche. Research: docs/research/2026-10-15-avalanche-trending-tokens.md.
Adding a category: an entry in CATEGORY_NETWORKS, a fetcher in TrendingTokens, a line in TRENDING_TOOL's description."""

import json
from dataclasses import asdict, dataclass

from .tokens import AVAX_TOKENS

GT_API = "https://api.geckoterminal.com/api/v2/networks"
GT_NETWORKS = {"ethereum": "eth", "avalanche": "avax"}
# category → networks it covers (first is the default when there's only one)
CATEGORY_NETWORKS = {"meme": ("avalanche",), "rwa": ("ethereum", "avalanche")}
TIMEOUT_S = 15
TTL_S = 60
MIN_LIQUIDITY_USD = 10_000
TOP_N = 10
GT_BATCH = 30  # GeckoTerminal tokens/multi accepts at most 30 addresses
UNAVAILABLE = "Couldn't load trending tokens right now."

# --- memecoins (Avalanche) ---

WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
# Protocol / governance tokens that keep showing up in Avalanche trending but aren't memes.
# GeckoTerminal has no reliable meme flag (its categories tag JOE as "joe-biden"), so this is curated.
NOT_MEMES = {
    "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd",  # JOE (LFJ)
    "0x13a466998ce03db73abc2d4df3bbd845ed1f28e7",  # PHAR (Pharaoh)
    "0xcd94a87696fac69edae3a70fe5725307ae1c43f6",  # BLACK (Blackhole)
    "0x8729438eb15e2c8b576fcc6aecda6a148776c0f5",  # QI (Benqi)
    "0xff7f8f301f7a706e3cfd3d2275f5dc0b9ee8009b",  # FOLKS (Folks Finance)
    "0xb8d7710f7d8349a506b75dd184f05777c82dad0c",  # ARENA (Arena platform token)
    "0x6b1ecf0c181afff3d7096b26c3d2bc31f55ceab9",  # MUON (Muon Network)
    "0x62d0a8458ed7719fdaf978fe5929c6d342b0bfce",  # BEAM (Beam gaming)
    "0x6985884c4392d348587b19cb9eaaf157f13271cd",  # ZRO (LayerZero)
    "0x26debd39d5ed069770406fca10a0e4f8d2c743eb",  # GUN (Gunz)
    "0x5e0e90e268bc247cc850c789a0db0d5c7621fb59",  # NXPC (Nexpace, bridged)
}
EXCLUDED = {t.address.lower() for t in AVAX_TOKENS if t.address} | {WAVAX} | NOT_MEMES
STABLES = {"DAI", "AUSD", "EURC", "EUROC", "XAUT", "XAUT0", "FRAX", "GHO", "MIM", "JPYC"}
MAJORS = ("AVAX", "BTC", "ETH")  # any symbol containing one: wrapped, bridged or staked majors
NOT_MEME_WORDS = ("staked", "staking", "wrapped", "bridged")


@dataclass(frozen=True)
class TokenInfo:
    symbol: str
    name: str
    address: str


@dataclass(frozen=True)
class Pool:
    token: TokenInfo  # the pool's base token
    price_usd: float
    volume_24h: float
    change_24h: float
    liquidity_usd: float
    dex: str
    trending: int | None = None  # position in GeckoTerminal's trending list; None = not in it


@dataclass(frozen=True)
class Trending:
    symbol: str
    name: str
    address: str
    network: str  # "ethereum" | "avalanche"
    price_usd: float | None  # None = no DEX market
    volume_24h: float
    change_24h: float | None
    liquidity_usd: float  # deepest pool
    dex: str
    buyable: bool  # deepest pool ≥ $10k
    note: str | None = None  # only for pinned entries


class TrendingError(Exception):
    """A message for the model (bad arguments or data unavailable)."""


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rel_id(obj: dict, name: str) -> str | None:
    return (((obj.get("relationships") or {}).get(name) or {}).get("data") or {}).get("id")


# --- memecoins: pure ---


def parse_pools(body: dict, trending: bool = False) -> list[Pool]:
    """GeckoTerminal pools JSON (requested with include=base_token,dex) → pools. Pools whose
    base token isn't in `included` are skipped; missing numbers read as 0."""
    included = {(i.get("type"), i.get("id")): i.get("attributes") or {} for i in body.get("included") or []}
    pools = []
    for n, p in enumerate(body.get("data") or []):
        attrs = p.get("attributes") or {}
        token = included.get(("token", _rel_id(p, "base_token")))
        if not token or not token.get("address") or not token.get("symbol"):
            continue
        dex_id = _rel_id(p, "dex") or "unknown"
        pools.append(
            Pool(
                token=TokenInfo(token["symbol"], token.get("name") or token["symbol"], token["address"]),
                price_usd=_num(attrs.get("base_token_price_usd")),
                volume_24h=_num((attrs.get("volume_usd") or {}).get("h24")),
                change_24h=_num((attrs.get("price_change_percentage") or {}).get("h24")),
                liquidity_usd=_num(attrs.get("reserve_in_usd")),
                dex=(included.get(("dex", dex_id)) or {}).get("name") or dex_id,
                trending=n if trending else None,
            )
        )
    return pools


def is_memecoin(token: TokenInfo) -> bool:
    if token.address.lower() in EXCLUDED:
        return False
    symbol = token.symbol.upper()
    if "USD" in symbol or symbol in STABLES or symbol.endswith((".E", ".B")):
        return False
    if any(m in symbol for m in MAJORS):
        return False
    return not any(w in token.name.lower() for w in NOT_MEME_WORDS)


def rank_memes(pools: list[Pool]) -> list[Trending]:
    """One entry per memecoin (its highest-liquidity pool), liquidity ≥ $10k,
    trending order first then 24h volume, top 10."""
    best: dict[str, Pool] = {}
    order: dict[str, int] = {}
    for p in pools:
        if not is_memecoin(p.token):
            continue
        key = p.token.address.lower()
        if p.trending is not None:
            order[key] = min(order.get(key, p.trending), p.trending)
        if key not in best or p.liquidity_usd > best[key].liquidity_usd:
            best[key] = p
    kept = [(k, p) for k, p in best.items() if p.liquidity_usd >= MIN_LIQUIDITY_USD]
    kept.sort(key=lambda kp: (order.get(kp[0], float("inf")), -kp[1].volume_24h))
    return [
        Trending(p.token.symbol, p.token.name, p.token.address, "avalanche", p.price_usd, p.volume_24h, p.change_24h, p.liquidity_usd, p.dex, True)
        for _, p in kept[:TOP_N]
    ]


# --- shared ---


def parse_args(args: dict) -> tuple[str, str | None]:
    """Tool arguments → (category, network). Raises TrendingError with text for the model."""
    category = str(args.get("category") or "meme").strip().lower()
    network = str(args["network"]).strip().lower() if args.get("network") else None
    if category not in CATEGORY_NETWORKS:
        raise TrendingError(f"category must be one of: {', '.join(CATEGORY_NETWORKS)}.")
    allowed = CATEGORY_NETWORKS[category]
    if network is not None and network not in allowed:
        raise TrendingError(f"{category} tokens are only listed on {' and '.join(n.capitalize() for n in allowed)}.")
    return category, network


def to_json(items: list[Trending]) -> str:
    return json.dumps(
        {
            "source": "GeckoTerminal, live mainnet",
            "note": "Offer to buy only buyable tokens. Buy with propose_swap: network = the token's network, token_out = its contract address.",
            "tokens": [asdict(t) for t in items],
        }
    )
