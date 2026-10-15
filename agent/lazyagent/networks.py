from dataclasses import dataclass

from .tokens import AVAX, AVAX_TOKENS, ETH, TOKENS, Token, find_token


@dataclass(frozen=True)
class Network:
    key: str
    name: str
    chain_id: int
    native: Token
    tokens: tuple[Token, ...]
    swap_venue: str  # "uniswap" | "dexalot"

    @property
    def label(self) -> str:
        return self.name


ETHEREUM = Network("ethereum", "Ethereum", 1, ETH, tuple(TOKENS), "uniswap")
AVALANCHE = Network("avalanche", "Avalanche", 43114, AVAX, tuple(AVAX_TOKENS), "dexalot")
NETWORKS = [ETHEREUM, AVALANCHE]
_ALIASES = {"ethereum": ETHEREUM, "eth": ETHEREUM, "avalanche": AVALANCHE, "avax": AVALANCHE}


@dataclass(frozen=True)
class Choice:
    """More than one network fits; the user has to pick."""

    networks: tuple[Network, ...]


def find_network(text: str | None) -> Network | None:
    return _ALIASES.get(str(text or "").strip().lower())


def candidates(symbols: list[str], networks: list[Network]) -> list[Network]:
    return [n for n in networks if all(find_token(s, n.tokens) for s in symbols)]


def pick_network(cands: list[Network], enough: dict[str, bool]) -> Network | Choice:
    if len(cands) == 1:
        return cands[0]
    fits = [n for n in cands if enough.get(n.key)]
    return fits[0] if len(fits) == 1 else Choice(tuple(cands))
