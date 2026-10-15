"""Airdrops / points programs: a curated list (data/airdrops.json) enriched live with DefiLlama TVL and
GeckoTerminal liquidity, plus the calldata for executable farms (ERC-4626 deposit).
Research: docs/research/2026-10-15-rwa-airdrops.md. Points only count on real mainnet; the Sandbox is a demo."""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from eth_abi import encode
from web3 import Web3

from .chain import Chain
from .custom_tokens import GECKO_API, GECKO_NETWORK, MIN_RESERVE_USD
from .kyber import http_json
from .swaps import GAS, Step, display_units
from .tokens import Token
from .transfers import TransferError, format_units, format_usd, short, token_address_rows
from .uniswap import encode_erc20_allowance

DATA = Path(__file__).parent / "data" / "airdrops.json"
LLAMA_API = "https://api.llama.fi"
CHAIN_NAMES = {"ethereum": "Ethereum", "avalanche": "Avalanche"}  # DefiLlama's chain keys, and card labels
CATEGORIES = ("rwa", "other")
STATUSES = ("live", "unverified", "claim_pending")
ACTION_KINDS = ("hold", "deposit", "claim")
V4_THEN_KYBER, KYBER = "uniswap_v4_pinned_then_kyber", "kyber"  # deposit venues for the pay → asset swap
TTL_S = 600
MAX_RESULTS = 8
POINTS_NOTICE = "Only count on real mainnet. This Sandbox is a demo and earns nothing."


class AirdropError(Exception):
    """A message for the model (bad arguments)."""


@dataclass(frozen=True)
class FarmToken:
    network: str
    symbol: str
    address: str
    decimals: int


@dataclass(frozen=True)
class Deposit:
    name: str  # short program name for buttons and card titles, e.g. "Theo"
    network: str
    venue: str  # V4_THEN_KYBER (pinned Uniswap v4 pool, else KyberSwap) | KYBER
    vault: FarmToken  # the ERC-4626 share token
    asset: FarmToken  # what the vault takes — one of the program's farm tokens
    pay: str  # symbol of the built-in token the user pays with
    fee: int | None = None  # pinned v4 pool (V4_THEN_KYBER only)
    tick_spacing: int | None = None


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    category: str
    networks: tuple[str, ...]
    status: str
    reward: str
    token: str  # "none" | "n/a" | "live: X" | "pending: X"
    season_ends: str | None
    action: str
    action_kind: str
    kyc: str
    farm_tokens: tuple[FarmToken, ...]
    defillama_slug: str | None
    deposit: Deposit | None
    source_url: str
    verified_at: str
    demo_assumption: str | None = None  # set when the demo deliberately differs from reality (the model must not state real dates)
    featured: bool = False  # ranks first in list_airdrops regardless of category (Avant, for the demo)


def _checksummed(address: str) -> str:
    if not Web3.is_checksum_address(address):
        raise ValueError(f"not a checksummed address: {address}")
    return address


def _farm_token(d: dict) -> FarmToken:
    if d["network"] not in CHAIN_NAMES:
        raise ValueError(f"unknown network {d['network']}")
    return FarmToken(d["network"], str(d["symbol"]), _checksummed(d["address"]), int(d["decimals"]))


def parse_program(d: dict) -> Program:
    """One curated entry → Program. Raises ValueError/KeyError on anything malformed."""
    networks = tuple(d["networks"])
    if not networks or any(n not in CHAIN_NAMES for n in networks):
        raise ValueError(f"{d.get('id')}: bad networks {networks}")
    if d["category"] not in CATEGORIES or d["status"] not in STATUSES or d["action_kind"] not in ACTION_KINDS:
        raise ValueError(f"{d.get('id')}: bad category, status or action_kind")
    token = str(d["token"])
    if token not in ("none", "n/a") and not token.startswith(("live: ", "pending: ")):
        raise ValueError(f"{d.get('id')}: bad token {token}")
    farm_tokens = tuple(_farm_token(t) for t in d["farm_tokens"])
    deposit = None
    if d.get("deposit"):
        dep = d["deposit"]
        vault = _farm_token({**dep["vault"], "network": dep["network"]})
        asset = next((t for t in farm_tokens if t.address == dep["asset"] and t.network == dep["network"]), None)
        if asset is None:
            raise ValueError(f"{d['id']}: deposit asset is not one of its farm tokens")
        venue = dep["venue"]
        if venue == V4_THEN_KYBER:
            if dep["network"] != "ethereum":  # Uniswap v4 swaps run on Ethereum only
                raise ValueError(f"{d['id']}: a pinned v4 route needs network ethereum")
            fee, spacing = int(dep["route"]["fee"]), int(dep["route"]["tick_spacing"])
        elif venue == KYBER:
            fee = spacing = None
        else:
            raise ValueError(f"{d['id']}: unknown deposit venue {venue}")
        deposit = Deposit(str(dep["name"]), dep["network"], venue, vault, asset, str(dep["pay"]), fee, spacing)
    return Program(
        str(d["id"]), str(d["name"]), d["category"], networks, d["status"], str(d["reward"]), token, d.get("season_ends"),
        str(d["action"]), d["action_kind"], str(d["kyc"]), farm_tokens, d.get("defillama_slug"), deposit,
        str(d["source_url"]), str(d["verified_at"]), d.get("demo_assumption"), bool(d.get("featured", False)),
    )


def load_curated(path: Path = DATA) -> list[Program]:
    programs = [parse_program(d) for d in json.loads(path.read_text())]
    ids = [p.id for p in programs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate airdrop ids")
    return programs


PROGRAMS = load_curated()


def find_program(text: str, programs: list[Program] = PROGRAMS) -> Program | None:
    """By id ("theo-thusd") or by its farm's short name ("Theo"), case-insensitive."""
    q = text.strip().lower()
    return next((p for p in programs if p.id == q or (p.deposit and p.deposit.name.lower() == q)), None)


# --- live enrichment: pure ---


@dataclass(frozen=True)
class LiveToken:
    network: str
    symbol: str
    address: str
    liquidity_usd: float | None  # deepest pool; None = unknown (lookup failed)
    buyable: bool | None  # deepest pool ≥ $10k; None = unknown


@dataclass(frozen=True)
class Airdrop:
    program: Program
    tvl_usd: float | None
    token_launched: bool
    farm_tokens: tuple[LiveToken, ...]

    @property
    def executable(self) -> bool:
        return self.program.deposit is not None


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def deepest_pool_usd(body: dict) -> float:
    """GeckoTerminal /tokens/{address}/pools → the largest reserve_in_usd (0 when there are no pools)."""
    return max((_num((p.get("attributes") or {}).get("reserve_in_usd")) for p in body.get("data") or []), default=0.0)


def enrich(program: Program, llama: dict | None, pools: dict[str, dict | None]) -> Airdrop:
    """`llama` = DefiLlama /protocol/{slug} (None if unavailable); `pools` = farm token address (lower-case) →
    GeckoTerminal pools JSON (None if unavailable)."""
    tvl, launched = None, False
    if llama is not None:
        chains = llama.get("currentChainTvls") or {}
        found = [_num(chains[CHAIN_NAMES[n]]) for n in program.networks if CHAIN_NAMES[n] in chains]
        tvl = sum(found) if found else None
        symbol = str(llama.get("symbol") or "-").strip()
        launched = program.token == "none" and (bool(llama.get("gecko_id")) or symbol not in ("-", ""))
    live = []
    for t in program.farm_tokens:
        body = pools.get(t.address.lower())
        liquidity = None if body is None else deepest_pool_usd(body)
        live.append(LiveToken(t.network, t.symbol, t.address, liquidity, None if liquidity is None else liquidity >= MIN_RESERVE_USD))
    return Airdrop(program, tvl, launched, tuple(live))


def rank(airdrops: list[Airdrop]) -> list[Airdrop]:
    """Featured first (Avant, for the demo); then RWA; then live → unverified → claim_pending; then executable → buyable → no token yet; then TVL."""

    def key(a: Airdrop):
        p = a.program
        return (
            not p.featured,
            CATEGORIES.index(p.category),
            STATUSES.index(p.status),
            not a.executable,
            not any(t.buyable for t in a.farm_tokens),
            p.token != "none",
            -(a.tvl_usd or 0.0),
        )

    return sorted(airdrops, key=key)


def filter_programs(programs: list[Program], category: str, network: str | None) -> list[Program]:
    return [p for p in programs if category in ("all", p.category) and (network is None or network in p.networks)]


def parse_args(args: dict) -> tuple[str, str | None]:
    category = str(args.get("category") or "all").strip().lower()
    network = str(args["network"]).strip().lower() if args.get("network") else None
    if category not in (*CATEGORIES, "all"):
        raise AirdropError("category must be one of: rwa, other, all.")
    if network is not None and network not in CHAIN_NAMES:
        raise AirdropError("network must be one of: ethereum, avalanche.")
    return category, network


def to_json(airdrops: list[Airdrop]) -> str:
    entries = []
    for a in airdrops:
        p = a.program
        entries.append(
            {
                "id": p.id, "name": p.name, "category": p.category, "networks": list(p.networks), "status": p.status,
                "reward": p.reward, "token": p.token, "token_launched": a.token_launched, "season_ends": p.season_ends,
                "action": p.action, "action_kind": p.action_kind, "executable": a.executable, "kyc": p.kyc,
                "farm_tokens": [
                    {"network": t.network, "symbol": t.symbol, "address": t.address, "liquidity_usd": t.liquidity_usd, "buyable": t.buyable}
                    for t in a.farm_tokens
                ],
                "tvl_usd": a.tvl_usd, "source_url": p.source_url, "verified_at": p.verified_at,
                "demo_assumption": p.demo_assumption,
            }
        )
    return json.dumps({"source": "curated list + DefiLlama/GeckoTerminal (live mainnet)", "points": POINTS_NOTICE, "airdrops": entries})


def card(airdrops: list[Airdrop], category: str, network: str | None = None) -> dict:
    """The browser's airdrops card. Titles never name a chain. Buy = the first farm token (on `network`, if one
    was asked for) that isn't known to be unbuyable; executable programs get Farm instead."""
    items = []
    for a in airdrops:
        p = a.program
        tokens = [t for t in a.farm_tokens if t.buyable is not False and network in (None, t.network)]
        buy = None if a.executable or not tokens else tokens[0]
        items.append(
            {
                "id": p.id, "name": p.name, "category": p.category, "networks": [CHAIN_NAMES[n] for n in p.networks],
                "status": p.status, "action": p.action, "tvlUsd": a.tvl_usd,
                "farm": p.deposit.name if p.deposit else None,
                "buy": {"symbol": buy.symbol, "address": buy.address} if buy else None,
            }
        )
    return {"type": "airdrops", "title": "RWA airdrops" if category == "rwa" else "Airdrops", "items": items}


# --- live enrichment: I/O ---


class DefiLlamaSource(Protocol):
    async def protocol(self, slug: str) -> dict: ...


class GeckoSource(Protocol):
    async def pools(self, network: str, address: str) -> dict: ...


async def _get(url: str) -> dict:
    status, body = await asyncio.to_thread(http_json, url, None, {"accept": "application/json"})
    if status != 200:
        raise ConnectionError(f"{url} answered {status}")
    return body


class DefiLlamaHttp:
    async def protocol(self, slug: str) -> dict:
        return await _get(f"{LLAMA_API}/protocol/{slug}")


class GeckoPoolsHttp:
    async def pools(self, network: str, address: str) -> dict:
        return await _get(f"{GECKO_API}/networks/{GECKO_NETWORK[network]}/tokens/{address}/pools")


class Airdrops:
    """The curated programs, enriched live. Each lookup is cached for 10 min; a failed one reads as unknown
    (None) and isn't cached."""

    def __init__(
        self,
        llama: DefiLlamaSource,
        gecko: GeckoSource,
        programs: list[Program] = PROGRAMS,
        ttl: float = TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.llama, self.gecko, self.programs, self.ttl, self.clock = llama, gecko, programs, ttl, clock
        self._cache: dict[tuple, tuple[float, dict]] = {}

    async def _cached(self, key: tuple, fetch: Callable[[], Awaitable[dict]]) -> dict | None:
        hit = self._cache.get(key)
        if hit is not None and self.clock() - hit[0] < self.ttl:
            return hit[1]
        try:
            body = await fetch()
        except Exception:
            return None
        self._cache[key] = (self.clock(), body)
        return body

    async def _enrich(self, p: Program) -> Airdrop:
        llama = await self._cached(("llama", p.defillama_slug), lambda: self.llama.protocol(p.defillama_slug)) if p.defillama_slug else None
        pools = {}
        for t in p.farm_tokens:
            pools[t.address.lower()] = await self._cached(("pools", t.network, t.address.lower()), lambda t=t: self.gecko.pools(t.network, t.address))
        return enrich(p, llama, pools)

    async def list(self, category: str = "all", network: str | None = None) -> list[Airdrop]:
        programs = filter_programs(self.programs, category, network)
        return rank(list(await asyncio.gather(*(self._enrich(p) for p in programs))))[:MAX_RESULTS]


AIRDROPS = Airdrops(DefiLlamaHttp(), GeckoPoolsHttp())


# --- agent tools ---

AIRDROPS_TOOL = (
    "list_airdrops",
    "Airdrops and points programs the user can farm (read-only): a curated list with live TVL and farm-token "
    "liquidity. Featured first, then RWA programs. Each: id, name, category, networks, status (live | unverified = may have ended | "
    "claim_pending = claim not open yet), reward, token, action, executable (propose_deposit can farm it), farm_tokens "
    "(contract address, buyable). Also shows the user a card, so reply in one short sentence.",
    {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [*CATEGORIES, "all"], "description": "'rwa' only if the user said RWA / real-world assets; default 'all'"},
            "network": {"type": "string", "enum": list(CHAIN_NAMES), "description": "Only if the user named a network"},
        },
    },
)


async def airdrops_reply(airdrops: Airdrops, args: dict, send: Callable[[dict], Awaitable[None]]) -> str:
    """Sends the card and returns the tool's text. Raises AirdropError for bad arguments."""
    category, network = parse_args(args)
    items = await airdrops.list(category, network)
    if not items:
        return "No airdrops match that right now. Say so in one short sentence."
    await send(card(items, category, network))
    return (
        "The user now sees these as a card. Reply in ONE short sentence: name the top one or two and which one "
        "LazyWallet can farm or buy; say points only count on real mainnet. Don't read the list out. Data: " + to_json(items)
    )
