"""Tokens beyond the built-in registry: the wallet's saved list (lw.tokens), contract addresses and symbol search."""

import asyncio
import re
import urllib.parse
from dataclasses import replace
from typing import Protocol

from eth_abi import decode
from web3 import Web3

from .chain import Chain
from .kyber import http_json
from .networks import Network
from .tokens import Token
from .transfers import TransferError

GECKO_API = "https://api.geckoterminal.com/api/v2"
GECKO_NETWORK = {"ethereum": "eth", "avalanche": "avax"}
MIN_RESERVE_USD = 10_000
SYMBOL, DECIMALS = "0x95d89b41", "0x313ce567"  # symbol(), decimals()
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _saved(entry: dict) -> Token | None:
    try:
        address, symbol, decimals = str(entry["address"]), str(entry["symbol"]).strip(), int(entry["decimals"])
    except (KeyError, TypeError, ValueError):
        return None
    if not ADDRESS.match(address) or not symbol or len(symbol) > 32 or not 0 <= decimals <= 255:
        return None
    return Token(symbol, Web3.to_checksum_address(address), decimals, custom=True)


def merge(net: Network, saved: list[dict]) -> Network:
    """The network plus the wallet's saved tokens on its chain. Built-ins win on a symbol or address clash."""
    taken = {t.symbol.upper() for t in net.tokens} | {t.address.lower() for t in net.tokens if t.address}
    extra: list[Token] = []
    for entry in saved:
        token = _saved(entry) if isinstance(entry, dict) and entry.get("chainId") == net.chain_id else None
        if token is None or token.symbol.upper() in taken or token.address.lower() in taken:
            continue
        taken |= {token.symbol.upper(), token.address.lower()}
        extra.append(token)
    return replace(net, tokens=net.tokens + tuple(extra)) if extra else net


def _symbol(raw: bytes) -> str:
    try:
        text = decode(["string"], raw)[0]
    except Exception:
        text = raw[:32].rstrip(b"\0").decode("utf-8", "ignore")  # bytes32 symbols (e.g. MKR)
    text = text.strip()
    return text if len(text) <= 32 and text.isprintable() else ""


async def read_token(chain: Chain, address: str) -> Token | None:
    """symbol() and decimals() on the fork; None if the address isn't an ERC-20 there."""
    try:
        raw_symbol, raw_decimals = await chain.call(address, SYMBOL), await chain.call(address, DECIMALS)
    except Exception:
        return None
    symbol = _symbol(raw_symbol)
    decimals = int.from_bytes(raw_decimals[:32], "big") if len(raw_decimals) >= 32 else -1
    if not symbol or not 0 <= decimals <= 255:
        return None
    return Token(symbol, Web3.to_checksum_address(address), decimals, custom=True)


def pick_pool(body: dict, symbol: str) -> tuple[str, str] | None:
    """(address, symbol) of the base token with exactly this symbol in the deepest pool, if that pool holds ≥ $10k."""
    try:
        tokens = {t["id"]: t["attributes"] for t in body.get("included") or [] if t.get("type") == "token"}
        best: tuple[float, str, str] | None = None
        for pool in body.get("data") or []:
            base = tokens.get(pool["relationships"]["base_token"]["data"]["id"])
            if not base or str(base.get("symbol", "")).lower() != symbol.strip().lower():
                continue
            reserve = float(pool["attributes"].get("reserve_in_usd") or 0)
            if best is None or reserve > best[0]:
                best = (reserve, base["address"], base["symbol"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    if best is None or best[0] < MIN_RESERVE_USD or not ADDRESS.match(best[1]):
        return None
    return best[1], best[2]


class Search(Protocol):
    async def pools(self, network: str, query: str) -> dict: ...


class GeckoSearch:
    """GeckoTerminal pool search (free API, no key)."""

    async def pools(self, network: str, query: str) -> dict:
        q = urllib.parse.urlencode({"query": query, "network": GECKO_NETWORK[network], "include": "base_token"})
        status, body = await asyncio.to_thread(http_json, f"{GECKO_API}/search/pools?{q}", None, {"accept": "application/json"})
        if status != 200:
            raise ConnectionError(f"GeckoTerminal search failed ({status})")
        return body


async def discover(text: str, net: Network, chain: Chain, search: Search | None) -> Token | None:
    """A token that's neither built in nor saved: a 0x address read on the fork, else a symbol search on that network.
    Raises TransferError for a token posing as one of the network's built-ins."""
    query = text.strip()
    if ADDRESS.match(query):
        return _not_an_impostor(await read_token(chain, query), net)
    if search is None or not query:
        return None
    try:
        found = pick_pool(await search.pools(net.key, query), query)
    except Exception:
        return None
    if found is None:
        return None
    token = _not_an_impostor(await read_token(chain, found[0]), net)
    return _not_an_impostor(replace(token, symbol=found[1], matched_by_symbol=True), net) if token else None


def _not_an_impostor(token: Token | None, net: Network) -> Token | None:
    """A discovered token may not use a built-in's symbol on the same network (e.g. a fake "USDC")."""
    if token and any(not t.custom and t.symbol.upper() == token.symbol.upper() for t in net.tokens):
        raise TransferError(
            f"That token calls itself {token.symbol} but isn't the real {token.symbol} on {net.name} Sandbox, so I won't trade it."
        )
    return token
