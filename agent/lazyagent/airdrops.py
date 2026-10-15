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
