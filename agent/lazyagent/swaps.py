import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from .tokens import Token
from .transfers import FEE_HEADROOM, TransferError, format_units, format_usd, short
from .uniswap import PERMIT2, UNIVERSAL_ROUTER, Route, encode_erc20_approve, encode_permit2_approve, symbol_of

DEFAULT_SLIPPAGE_BPS = 100
MAX_SLIPPAGE_BPS = 500
MAX_PRICE_IMPACT = 0.15
DEADLINE_S = 20 * 60
PERMIT2_EXPIRY_S = 30 * 60
GAS = {"approve": 60_000, "permit2": 60_000, "wrap": 60_000, "swap1": 170_000, "swap2": 220_000, "deposit": 120_000}
_PERCENT = re.compile(r"^[0-9]*\.?[0-9]+$")


@dataclass(frozen=True)
class Step:
    label: str
    request: dict
    gas: int

    def to_json(self) -> dict:
        return {"label": self.label, "request": self.request}


@dataclass(frozen=True)
class SwapPlan:
    """A venue's answer for propose_swap: the steps, the card's Details rows and what its summary needs."""

    steps: list[Step]
    rows: list[dict]
    hint: str  # appended when the swap reverts
    expected: int
    via: str
    impact: float | None
    exact: bool = False  # a signed RFQ order: pays exactly `expected`


def parse_slippage(text: str | None) -> int:
    if text is None or not str(text).strip():
        return DEFAULT_SLIPPAGE_BPS
    cleaned = str(text).strip().rstrip("%").strip()
    if not _PERCENT.match(cleaned):
        raise TransferError(f'"{text}" isn\'t a valid slippage. Use a percentage like 0.5.')
    bps = Decimal(cleaned) * 100
    if bps != bps.to_integral_value() or not 1 <= bps <= MAX_SLIPPAGE_BPS:
        raise TransferError("Slippage must be between 0.01% and 5%.")
    return int(bps)


def min_out(quote: int, bps: int) -> int:
    return quote * (10_000 - bps) // 10_000


def price_impact(amount_in: int, amount_out: int, probe_in: int, probe_out: int) -> float:
    """How much worse the full trade's rate is than a tiny trade's rate on the same route."""
    if not probe_out or not amount_in:
        return 0.0
    return max(1 - (amount_out * probe_in) / (probe_out * amount_in), 0.0)


def display_units(amount: int, decimals: int) -> str:
    """About six significant digits, rounded down — for card display only."""
    value = Decimal(amount).scaleb(-decimals)
    if value == 0:
        return "0"
    places = max(0, 6 - value.adjusted() - 1)
    return format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN).normalize(), "f")


def _fee_label(fee: int) -> str:
    return f"{fee / 10_000:g}%"


def route_label(route: Route) -> str:
    path = " → ".join(symbol_of(c) for c in route.currencies)
    fees = " / ".join(_fee_label(h.fee) for h in route.hops)
    return f"{path} · Uniswap v4 {fees}"


def approval_steps(
    token: Token, erc20_allowance: int, permit2_amount: int, permit2_expiration: int, amount: int, now: int
) -> list[Step]:
    steps = erc20_approval(token, erc20_allowance, amount, PERMIT2)
    if permit2_amount < amount or permit2_expiration <= now + 60:
        data = encode_permit2_approve(token.address, UNIVERSAL_ROUTER, amount, now + PERMIT2_EXPIRY_S)
        steps.append(Step("Allow Uniswap router", _tx(PERMIT2, data), GAS["permit2"]))
    return steps


def erc20_approval(token: Token, allowance: int, amount: int, spender: str) -> list[Step]:
    """approve(spender, amount) steps for an ERC-20 input, or none if the allowance already covers it."""
    if allowance >= amount:
        return []
    steps: list[Step] = []
    if token.symbol == "USDT" and allowance > 0:
        # USDT reverts when changing one nonzero allowance to another.
        steps.append(Step("Reset USDT allowance", _tx(token.address, encode_erc20_approve(spender, 0)), GAS["approve"]))
    steps.append(Step(f"Allow {token.symbol}", _tx(token.address, encode_erc20_approve(spender, amount)), GAS["approve"]))
    return steps


def _tx(to: str, data: str, value: int = 0) -> dict:
    return {"to": to, "value": str(value), "data": data}


def gas_reserve(steps: list[Step], gas_price: int) -> int:
    return sum(s.gas for s in steps) * gas_price * FEE_HEADROOM


def check_swap_funds(token_in: Token, amount: int, balance: int, eth_balance: int, reserve: int, native: str = "ETH") -> None:
    if amount > balance:
        raise TransferError(f"You only have {format_units(balance, token_in.decimals)} {token_in.symbol}.")
    needed = reserve + (amount if token_in.address is None else 0)
    if needed > eth_balance:
        raise TransferError(
            f"Not enough {native} left for the network fees (keep ~{format_units(reserve, 18)} {native}). Try a smaller amount or add funds."
        )


WARN_PRICE_IMPACT = 0.05


def swap_rows(sender: str, label: str, impact: float | None) -> list[dict]:
    """The card's Details: what the summary above it doesn't already show."""
    return [
        {"label": "From", "value": short(sender)},
        {"label": "Route", "value": label},
        {"label": "Price impact", "value": "unknown" if impact is None else f"{impact * 100:.2f}%"},
    ]


def fee_text(fee_usd: float) -> str:
    return "< $0.01" if fee_usd < 0.005 else f"≈ {format_usd(fee_usd)}"


def impact_warning(impact: float | None) -> str | None:
    return f"Price impact {impact * 100:.1f}%" if impact is not None and impact > WARN_PRICE_IMPACT else None


def usd_value(amount: int, token: Token, price: float | None) -> float | None:
    return None if price is None else round(float(Decimal(amount).scaleb(-token.decimals)) * price, 2)


def side(token: Token, amount: int, display: str, price: float | None) -> dict:
    return {"symbol": token.symbol, "amount": display, "usd": usd_value(amount, token, price), "logo": token.logo}


def swap_summary(
    network: str, tin: Token, tout: Token, amount: int, expected: int, *, via: str, fee_usd: float, impact: float | None,
    prices: tuple[float | None, float | None], exact: bool = False,
) -> dict:
    """The confirm card's friendly top half (tx.summary). `exact` = a signed quote that pays exactly `expected`."""
    out = display_units(expected, tout.decimals)
    return {
        "kind": "swap",
        "network": network,
        "pay": side(tin, amount, format_units(amount, tin.decimals), prices[0]),
        "receive": {**side(tout, expected, out if exact else f"≈ {out}", prices[1]), "note": None},
        "via": via,
        "fee": fee_text(fee_usd),
        "warning": impact_warning(impact),
    }
