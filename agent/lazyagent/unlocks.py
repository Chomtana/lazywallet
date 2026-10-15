"""Upcoming token unlocks (Tokenomist API v5, read-only), with each token's buybacks and burns over the last
30 days and whether LazyWallet can buy it. Design: docs/superpowers/specs/2026-10-16-lazywallet-token-unlocks-design.md.

Tokenomist token ids are CoinGecko coin ids ("layerzero", "avalanche-2"), so CoinGecko's coins/list platforms map
them to Ethereum contract addresses; GeckoTerminal then gives the logo and DEX liquidity (buyable = deepest pool
≥ $10k, the trending.py rule). AVAX (Avalanche's native coin) is the one non-Ethereum exception.
The API key (TOKENOMIST_API_KEY in the root .env) is only read here, in the agent, and never leaves it."""

import asyncio
import json
import os
import time
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from urllib.parse import quote, urlencode

from .kyber import http_json
from .networks import find_network
from .tokens import AVAX
from .trending import MIN_LIQUIDITY_USD, GeckoTerminalSource, Trending, parse_tokens

TOKENOMIST_API = "https://api.tokenomist.ai/v5"
KEY_ENV = "TOKENOMIST_API_KEY"
CG_COINS_URL = "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
AVAX_ID = "avalanche-2"  # Tokenomist / CoinGecko id of AVAX
WINDOW_DAYS = 30  # unlocks in the next 30 days; buybacks and burns over the last 30
PAGE_SIZE = 200  # one page holds the whole month (139 events on 2026-10-16)
TOP_N = 10
TTL_S = 600
COINS_TIMEOUT_S = 30
COINS_TTL_S = 86_400  # CoinGecko's coin list (~4 MB) changes slowly; its free tier rate-limits hard
UNAVAILABLE = "Couldn't load token unlocks right now."
# Tokenomist's standard allocation names → card wording
ALLOCATION_LABELS = {"Founder / Team": "Team", "Private Investors": "Investors", "Public Investors": "Public sale", "Others": "Other"}


class UnlockError(Exception):
    """A message for the model."""


@dataclass(frozen=True)
class Unlock:
    token_id: str  # Tokenomist slug = CoinGecko id
    symbol: str
    name: str
    date: str  # ISO 8601 UTC, as Tokenomist gives it
    usd: float | None  # value at Tokenomist's reference price
    amount: float  # tokens
    allocation: str | None  # e.g. "Investors, Team"


@dataclass(frozen=True)
class TokenMeta:
    max_supply: float | None
    has_buyback: bool
    has_burn: bool


@dataclass(frozen=True)
class Listing:
    """Where LazyWallet can buy the token: network "ethereum" | "avalanche" | None; address None for native AVAX."""

    network: str | None
    address: str | None
    buyable: bool
    logo: str | None = None


@dataclass(frozen=True)
class UnlockItem:
    unlock: Unlock
    percent_of_supply: float | None
    buyback_usd: float | None  # last 30 days; None = none or unknown
    burn_usd: float | None
    listing: Listing


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _when(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


# --- pure ---


def _allocation(breakdown: list[dict]) -> str | None:
    """The biggest two standard allocations by value, e.g. "Investors, Team"."""
    names: list[str] = []
    for a in sorted(breakdown, key=lambda a: -(_num(a.get("cliffValue")) or 0.0)):
        raw = a.get("standardAllocationName") or a.get("allocationName")
        name = ALLOCATION_LABELS.get(raw, raw) if raw else None
        if name and name not in names:
            names.append(name)
    return ", ".join(names[:2]) or None


def parse_upcoming(body: dict) -> list[Unlock]:
    """Tokenomist /unlock/events/upcoming → unlocks. Entries without an id, symbol or date are skipped."""
    out = []
    for x in body.get("data") or []:
        event = x.get("upcomingEvent") or {}
        if not x.get("tokenId") or not x.get("tokenSymbol") or not event.get("unlockDate"):
            continue
        cliff = event.get("cliffUnlocks") or {}
        out.append(
            Unlock(
                x["tokenId"], x["tokenSymbol"], x.get("tokenName") or x["tokenSymbol"], event["unlockDate"],
                _num(cliff.get("totalCliffValue")), _num(cliff.get("totalCliffAmount")) or 0.0,
                _allocation(cliff.get("allocationBreakdown") or []),
            )
        )
    return out


def soonest(unlocks: list[Unlock], now: datetime, days: int = WINDOW_DAYS, top: int = TOP_N) -> list[Unlock]:
    """Unlocks from now until `days` ahead; the `top` biggest by USD value, soonest first."""
    end = now + timedelta(days=days)
    window = [u for u in unlocks if now <= _when(u.date) < end]
    biggest = sorted(window, key=lambda u: -(u.usd or 0.0))[:top]
    return sorted(biggest, key=lambda u: (_when(u.date), -(u.usd or 0.0)))


def parse_token_list(body: dict) -> dict[str, TokenMeta]:
    """Tokenomist /token/list → id → max supply and whether it has buyback / burn data."""
    return {
        t["id"]: TokenMeta(_num(t.get("maxSupply")), bool(t.get("hasBuyback")), bool(t.get("hasBurn")))
        for t in body.get("data") or []
        if t.get("id")
    }


def percent_of_supply(amount: float, meta: TokenMeta | None) -> float | None:
    if meta is None or not meta.max_supply:
        return None
    return amount / meta.max_supply * 100


def period_usd(body: dict | None) -> float | None:
    """Tokenomist /buyback or /burn for a date range → its USD total; None when there's none or no price."""
    data = (body or {}).get("data") or {}
    value = _num(data.get("totalBuybackValue", data.get("totalBurnValue")))
    return value if value else None


def ethereum_addresses(coin_list: list[dict], unlocks: list[Unlock]) -> dict[str, str]:
    """CoinGecko coins/list?include_platform=true → token id → lower-case Ethereum address. The CoinGecko
    symbol must match Tokenomist's, so a reused id can't point at another token."""
    coins = {c.get("id"): c for c in coin_list}
    out = {}
    for u in unlocks:
        coin = coins.get(u.token_id) or {}
        address = str((coin.get("platforms") or {}).get("ethereum") or "").lower()
        if str(coin.get("symbol", "")).upper() == u.symbol.upper() and address.startswith("0x") and len(address) == 42:
            out[u.token_id] = address
    return out


def listing(unlock: Unlock, eth_address: str | None, gecko: dict[str, Trending] | None) -> Listing:
    """`gecko` = GeckoTerminal tokens by lower-case address (None when that lookup failed: then being on
    Ethereum is enough). AVAX is native on Avalanche."""
    if unlock.token_id == AVAX_ID:
        return Listing("avalanche", None, True, AVAX.logo)
    if not eth_address:
        return Listing(None, None, False)
    if gecko is None:
        return Listing("ethereum", eth_address, True)
    t = gecko.get(eth_address)
    return Listing("ethereum", eth_address, bool(t and t.liquidity_usd >= MIN_LIQUIDITY_USD), t.image if t else None)


def to_card(items: list[UnlockItem]) -> dict:
    """The "unlocks" message the app shows as a card. network is a display name; never in the title."""
    return {
        "type": "unlocks",
        "title": "Upcoming unlocks",
        "items": [
            {
                "symbol": i.unlock.symbol,
                "name": i.unlock.name,
                "logo": i.listing.logo,
                "date": i.unlock.date,
                "unlockUsd": i.unlock.usd,
                "unlockAmount": i.unlock.amount,
                "percentOfSupply": i.percent_of_supply,
                "allocation": i.unlock.allocation,
                "buybackUsd": i.buyback_usd,
                "burnUsd": i.burn_usd,
                "network": find_network(i.listing.network).name if i.listing.network else None,
                "address": i.listing.address,
                "buyable": i.listing.buyable,
            }
            for i in items
        ],
    }


def to_json(items: list[UnlockItem]) -> str:
    def r(x: float | None) -> float | None:
        return None if x is None else round(x, 2)

    return json.dumps(
        {
            "source": "Tokenomist (unlocks, buybacks and burns over the last 30 days), live",
            "note": "Offer to buy only buyable tokens: propose_swap with network = the token's network and token_out = its "
            "contract address (AVAX has none: token_out AVAX on avalanche).",
            "unlocks": [
                {
                    "symbol": i.unlock.symbol, "name": i.unlock.name, "date": i.unlock.date, "unlock_usd": r(i.unlock.usd),
                    "unlock_amount": r(i.unlock.amount), "percent_of_supply": r(i.percent_of_supply), "allocation": i.unlock.allocation,
                    "buyback_usd_30d": r(i.buyback_usd), "burn_usd_30d": r(i.burn_usd), "network": i.listing.network,
                    "address": i.listing.address, "buyable": i.listing.buyable,
                }
                for i in items
            ],
        }
    )


# --- I/O ---


class TokenomistSource(Protocol):
    async def upcoming(self, start: str, end: str) -> dict: ...
    async def token_list(self, ids: list[str]) -> dict: ...
    async def buyback(self, token_id: str, start: str, end: str) -> dict: ...
    async def burn(self, token_id: str, start: str, end: str) -> dict: ...


class CoinListSource(Protocol):
    async def coin_list(self) -> list[dict]: ...


class GeckoTokens(Protocol):
    async def tokens(self, network: str, addresses: list[str]) -> dict: ...


class TokenomistHttp:
    """The API key comes from the environment (the root .env, loaded by config.load_settings) on each call and is
    only ever sent in the x-api-key header — never in a URL, a log line or an error message."""

    def __init__(self, base: str = TOKENOMIST_API, key: Callable[[], str | None] = lambda: os.environ.get(KEY_ENV)):
        self.base, self.key = base, key

    async def _get(self, path: str, params: dict) -> dict:
        key = self.key()
        if not key:
            raise ConnectionError(f"{KEY_ENV} is not set")
        url = f"{self.base}{path}?{urlencode(params)}"
        status, body = await asyncio.to_thread(http_json, url, None, {"accept": "application/json", "x-api-key": key})
        if status != 200 or body.get("status") is False:
            raise ConnectionError(f"Tokenomist {path} answered {status}")  # 429 = rate limit or monthly credits used up
        return body

    async def upcoming(self, start: str, end: str) -> dict:
        return await self._get("/unlock/events/upcoming", {"start": start, "end": end, "pageSize": PAGE_SIZE})

    async def token_list(self, ids: list[str]) -> dict:
        return await self._get("/token/list", {"tokenId": ",".join(ids)})

    async def buyback(self, token_id: str, start: str, end: str) -> dict:
        return await self._get(f"/buyback/{quote(token_id)}", {"start": start, "end": end})

    async def burn(self, token_id: str, start: str, end: str) -> dict:
        return await self._get(f"/burn/{quote(token_id)}", {"start": start, "end": end})


def _get_list(url: str):
    """http_json only reads JSON objects; coins/list is an array. HTTP errors (e.g. 429) raise."""
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=COINS_TIMEOUT_S) as res:
        return json.loads(res.read())


class CoinGeckoCoins:
    def __init__(self, url: str = CG_COINS_URL):
        self.url = url

    async def coin_list(self) -> list[dict]:
        body = await asyncio.to_thread(_get_list, self.url)
        if not isinstance(body, list):
            raise ConnectionError("CoinGecko coins/list didn't answer a list")
        return body


async def _or_none(fetch: Awaitable):
    try:
        return await fetch
    except Exception:
        return None


class Unlocks:
    """The month's biggest unlocks, enriched. Cached for 10 min (the coin list for a day); errors are never
    cached. Only the unlock list itself is required — any other lookup failing just leaves its fields empty."""

    def __init__(
        self,
        tokenomist: TokenomistSource,
        coins: CoinListSource,
        gecko: GeckoTokens,
        ttl: float = TTL_S,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.tokenomist, self.coins, self.gecko, self.ttl, self.clock, self.now = tokenomist, coins, gecko, ttl, clock, now
        self._cache: tuple[float, list[UnlockItem]] | None = None
        self._coins: tuple[float, list[dict]] | None = None

    async def _coin_list(self) -> list[dict] | None:
        if self._coins is not None and self.clock() - self._coins[0] < COINS_TTL_S:
            return self._coins[1]
        coins = await _or_none(self.coins.coin_list())
        if coins is not None:
            self._coins = (self.clock(), coins)
        return coins

    async def fetch(self) -> list[UnlockItem]:
        if self._cache is not None and self.clock() - self._cache[0] < self.ttl:
            return self._cache[1]
        now = self.now()
        today = now.date()
        unlocks = soonest(parse_upcoming(await self.tokenomist.upcoming(_day(today), _day(today + timedelta(days=WINDOW_DAYS)))), now)
        items = await self._enrich(unlocks, today) if unlocks else []
        self._cache = (self.clock(), items)
        return items

    async def _enrich(self, unlocks: list[Unlock], today: date) -> list[UnlockItem]:
        start, end = _day(today - timedelta(days=WINDOW_DAYS)), _day(today)
        listed = await _or_none(self.tokenomist.token_list([u.token_id for u in unlocks]))
        meta = parse_token_list(listed) if listed else {}

        async def period(u: Unlock, kind: str) -> float | None:
            m = meta.get(u.token_id)
            if not m or not (m.has_buyback if kind == "buyback" else m.has_burn):
                return None
            fetch = self.tokenomist.buyback if kind == "buyback" else self.tokenomist.burn
            return period_usd(await _or_none(fetch(u.token_id, start, end)))

        buybacks = await asyncio.gather(*(period(u, "buyback") for u in unlocks))
        burns = await asyncio.gather(*(period(u, "burn") for u in unlocks))
        coins = await self._coin_list()
        addresses = ethereum_addresses(coins, unlocks) if coins else {}
        gecko = None
        if addresses:
            body = await _or_none(self.gecko.tokens("ethereum", list(dict.fromkeys(addresses.values()))))
            gecko = None if body is None else {t.address: t for t in parse_tokens(body, "ethereum")}
        return [
            UnlockItem(u, percent_of_supply(u.amount, meta.get(u.token_id)), bb, bn, listing(u, addresses.get(u.token_id), gecko))
            for u, bb, bn in zip(unlocks, buybacks, burns, strict=True)
        ]


def _day(d: date) -> str:
    return d.isoformat()


UNLOCKS = Unlocks(TokenomistHttp(), CoinGeckoCoins(), GeckoTerminalSource())


# --- agent tool ---

UNLOCKS_TOOL = (
    "list_unlocks",
    "Upcoming token unlocks (vesting cliffs) in the next 30 days, live from Tokenomist (read-only): the biggest ones, "
    "soonest first. Each: symbol, name, date, unlock value in USD, amount, percent of max supply, allocation (Team, "
    "Investors, …), buyback and burn USD over the last 30 days, network and contract address where LazyWallet can "
    "buy it, buyable. Also shows the user a card, so reply in one short sentence.",
    {"type": "object", "properties": {}},
)


async def unlocks_reply(unlocks: Unlocks, send: Callable[[dict], Awaitable[None]]) -> str:
    """Sends the card and returns the tool's text. Raises UnlockError (friendly text) when the data is unavailable."""
    try:
        items = await unlocks.fetch()
    except Exception as e:
        raise UnlockError(UNAVAILABLE) from e
    if not items:
        return "No token unlocks found for the next 30 days. Say so in one short sentence."
    await send(to_card(items))
    return (
        "The user now sees these as a card. Reply in ONE short sentence: the biggest unlock coming up soon and whether "
        "that token has buybacks or burns. Don't read the list out, never name a chain, never invent numbers. Data: " + to_json(items)
    )
