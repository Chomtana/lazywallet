"""Trending tokens from live mainnet data (read-only): Avalanche memecoins and RWA project tokens on
Ethereum + Avalanche. Research: docs/research/2026-10-15-avalanche-trending-tokens.md.
Adding a category: an entry in CATEGORY_NETWORKS, a fetcher in TrendingTokens, a line in TRENDING_TOOL's description."""

import asyncio
import html
import json
import time
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol

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


# --- RWA project tokens (Ethereum + Avalanche) ---

# Hackathon sponsor showcase: always first in rwa results, in this order (network, lower-case address, note).
# XAUt0 is an asset token, not a project token — pinned deliberately and labelled.
PINNED = [
    ("avalanche", "0x2775d5105276781b4b85ba6ea6a6653beed1dd32", "tokenized gold — Avalanche showcase"),  # XAUt0
]
# In CoinGecko's RWA category, not in any tokenized-asset sub-category, but not RWA projects:
# infra / oracle / general-L1 tokens, a USD stablecoin without "USD" in its symbol, and funds CoinGecko left untagged.
NOT_RWA = {
    ("ethereum", "0x514910771af9ca656af840dff83e8264ecf986ca"),  # LINK
    ("avalanche", "0x5947bb275c521040051d82396192181b413227a3"),  # LINK.e
    ("ethereum", "0x4a220e6096b25eadb88358cb44068a3248254675"),  # QNT
    ("ethereum", "0xe28b3b32b6c345a34ff64674606124dd5aceca30"),  # INJ
    ("ethereum", "0xaa7a9ca87d3694b5755f213b5d04094b8d0f0a6f"),  # TRAC
    ("ethereum", "0xc43c6bfeda065fe2c4c11765bf838789bd0bb5de"),  # RED (RedStone)
    ("ethereum", "0x84ca8bc7997272c7cfb4d0cd3d55cd942b3c9419"),  # DIA
    ("ethereum", "0x8a2279d4a90b6fe1c4b30fa660cc9f926797baa2"),  # CHR (Chromia)
    ("ethereum", "0x07041776f5007aca2a54844f50503a18a72a8b68"),  # USAT (Tether US stablecoin)
    ("ethereum", "0xec1227bfb3e76d7a2a9bca24d9e98f68de8bf808"),  # MPRA (Maya Preferred — tokenized preferred stock)
    ("ethereum", "0x17418038ecf73ba4026c4f428547bf099706f27b"),  # ACRED (Apollo credit fund)
    ("avalanche", "0x7c64925002bfa705834b118a923e9911bee32875"),  # ACRED
    ("ethereum", "0x2255718832bc9fd3be1caf75084f4803da14ff01"),  # VBILL (VanEck treasury fund)
    ("avalanche", "0x7f4546ef315efc65336187fe3765ea779ac90183"),  # VBILL
}
RWA_SNAPSHOT = Path(__file__).parent / "data" / "rwa_coingecko.json"


@dataclass(frozen=True)
class RwaCoin:
    network: str
    address: str  # lower-case
    coingecko_id: str
    market_cap: float
    volume_24h: float  # CoinGecko, all venues — only used to pick which candidates to look up


def _opt(value) -> float | None:
    return None if value is None else _num(value)


# --- RWAs: pure ---


def rwa_addresses(markets: list[dict], coin_list: list[dict], asset_ids: set[str]) -> list[RwaCoin]:
    """CoinGecko RWA-category markets + coins/list?include_platform=true → one RwaCoin per
    (project token, network). Skips coins in a tokenized-asset sub-category (`asset_ids`), USD
    stablecoins (symbol contains "usd") and coins without an EVM address on a supported network."""
    platforms = {c.get("id"): c.get("platforms") or {} for c in coin_list}
    coins = []
    for m in markets:
        if m.get("id") in asset_ids or "usd" in str(m.get("symbol", "")).lower():
            continue
        for network in GT_NETWORKS:
            address = str(platforms.get(m.get("id"), {}).get(network) or "").lower()
            if address.startswith("0x") and len(address) == 42:
                coins.append(RwaCoin(network, address, m["id"], _num(m.get("market_cap")), _num(m.get("total_volume"))))
    return coins


def rwa_candidates(coins: list[RwaCoin], network: str) -> list[str]:
    """Addresses to look up on GeckoTerminal for one network (one batch): PINNED first, then half
    the busiest by CoinGecko volume, then the largest by market cap; NOT_RWA excluded."""
    out = [a for n, a, _ in PINNED if n == network]
    pool = [c for c in coins if c.network == network and (network, c.address) not in NOT_RWA]
    by_volume = sorted(pool, key=lambda c: (-c.volume_24h, -c.market_cap))
    by_mcap = sorted(pool, key=lambda c: (-c.market_cap, -c.volume_24h))
    for c in by_volume[: (GT_BATCH - len(out)) // 2] + by_mcap:
        if len(out) >= GT_BATCH:
            break
        if c.address not in out:
            out.append(c.address)
    return out


def parse_tokens(body: dict, network: str) -> list[Trending]:
    """GeckoTerminal tokens/multi JSON (include=top_pools) → entries. A token with no pool has
    price/change None, 0 volume and liquidity, buyable False. 24h change comes from the deepest
    pool only when the token is that pool's base token."""
    pools = {i.get("id"): i for i in body.get("included") or [] if i.get("type") == "pool"}
    out = []
    for t in body.get("data") or []:
        a = t.get("attributes") or {}
        if not a.get("address"):
            continue
        ids = [p.get("id") for p in ((t.get("relationships") or {}).get("top_pools") or {}).get("data") or []]
        top = [pools[i] for i in ids if i in pools]
        pool = max(top, key=lambda p: _num((p.get("attributes") or {}).get("reserve_in_usd")), default=None)
        liquidity, change, dex = 0.0, None, ""
        if pool:
            pa = pool.get("attributes") or {}
            liquidity = _num(pa.get("reserve_in_usd"))
            dex = _rel_id(pool, "dex") or ""
            if _rel_id(pool, "base_token") == t.get("id"):
                change = _opt((pa.get("price_change_percentage") or {}).get("h24"))
        symbol = a.get("symbol") or "?"
        out.append(
            Trending(
                symbol, html.unescape(a.get("name") or symbol), a["address"].lower(), network,
                _opt(a.get("price_usd")), _num((a.get("volume_usd") or {}).get("h24")), change,
                liquidity, dex, liquidity >= MIN_LIQUIDITY_USD,
            )
        )
    return out


def rank_rwas(items: list[Trending], coins: list[RwaCoin]) -> list[Trending]:
    """PINNED first (in order, with their note), then 24h DEX volume, then CoinGecko market cap;
    NOT_RWA and duplicates dropped; top 10."""
    pin = {(n, a): (i, note) for i, (n, a, note) in enumerate(PINNED)}
    mcap = {(c.network, c.address): c.market_cap for c in coins}
    seen, kept = set(), []
    for t in items:
        key = (t.network, t.address.lower())
        if key in seen or (key in NOT_RWA and key not in pin):
            continue
        seen.add(key)
        kept.append(replace(t, note=pin[key][1]) if key in pin else t)
    kept.sort(
        key=lambda t: (
            pin.get((t.network, t.address.lower()), (len(pin), None))[0],
            -t.volume_24h,
            -mcap.get((t.network, t.address.lower()), 0.0),
        )
    )
    return kept[:TOP_N]


def load_rwa_snapshot(path: Path = RWA_SNAPSHOT) -> list[RwaCoin]:
    body = json.loads(path.read_text())
    return [RwaCoin(**c) for c in body["coins"]]


# --- I/O ---


def _get(url: str):
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
        return json.loads(res.read())


class TrendingSource(Protocol):
    async def meme_pools(self) -> list[Pool]: ...
    async def tokens(self, network: str, addresses: list[str]) -> dict: ...


class GeckoTerminalSource:
    def __init__(self, base: str = GT_API):
        self.base = base

    async def meme_pools(self) -> list[Pool]:
        """Trending pools across all Avalanche DEXs, plus Arena DEX's busiest pools (where memecoins graduate to)."""
        trending = await asyncio.to_thread(_get, f"{self.base}/avax/trending_pools?include=base_token,dex")
        arena = await asyncio.to_thread(_get, f"{self.base}/avax/dexes/arena-dex/pools?sort=h24_volume_usd_desc&include=base_token,dex")
        return parse_pools(trending, trending=True) + parse_pools(arena)

    async def tokens(self, network: str, addresses: list[str]) -> dict:
        if not addresses:
            return {}
        url = f"{self.base}/{GT_NETWORKS[network]}/tokens/multi/{','.join(addresses[:GT_BATCH])}?include=top_pools"
        return await asyncio.to_thread(_get, url)


class TrendingTokens:
    """Ranked lists per (category, network), cached for 60 s. Errors propagate and are never cached."""

    def __init__(
        self,
        source: TrendingSource,
        rwa_coins: Callable[[], list[RwaCoin]] = load_rwa_snapshot,
        ttl: float = TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.source = source
        self.rwa_coins = rwa_coins
        self.ttl = ttl
        self.clock = clock
        self._cache: dict[tuple[str, str | None], tuple[float, list[Trending]]] = {}
        # one fetcher per CATEGORY_NETWORKS key
        self._fetchers: dict[str, Callable[[str | None], Awaitable[list[Trending]]]] = {"meme": self._memes, "rwa": self._rwas}

    async def fetch(self, category: str = "meme", network: str | None = None) -> list[Trending]:
        key = (category, network)
        now = self.clock()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        items = await self._fetchers[category](network)
        self._cache[key] = (now, items)
        return items

    async def _memes(self, network: str | None) -> list[Trending]:
        return rank_memes(await self.source.meme_pools())

    async def _rwas(self, network: str | None) -> list[Trending]:
        coins = self.rwa_coins()
        items: list[Trending] = []
        for net in [network] if network else CATEGORY_NETWORKS["rwa"]:
            items += parse_tokens(await self.source.tokens(net, rwa_candidates(coins, net)), net)
        return rank_rwas(items, coins)


TRENDING = TrendingTokens(GeckoTerminalSource())
