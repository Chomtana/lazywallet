import re
from decimal import Decimal, localcontext

from eth_abi import encode
from web3 import Web3

from .tokens import Token

ERC20_TRANSFER_SELECTOR = "a9059cbb"
_AMOUNT = re.compile(r"^[0-9]*\.?[0-9]+$")
_THOUSANDS = re.compile(r"^[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?$")
FEE_HEADROOM = 2  # wallets sign EIP-1559 with maxFeePerGas well above the current gas price


class TransferError(Exception):
    """A user-facing reason a transfer can't be proposed."""


class NoRoute(TransferError):
    """The network's own venue has no quote for this pair — KyberSwap may still have one."""


def parse_amount(text: str, decimals: int) -> int:
    cleaned = text.strip()
    if "," in cleaned:
        # Only thousands separators ("1,000.5"); "0,5" is a decimal comma and must not become 5.
        if not _THOUSANDS.match(cleaned):
            raise TransferError(f'"{text}" isn\'t a valid amount. Use a dot for decimals, like 0.5.')
        cleaned = cleaned.replace(",", "")
    if not _AMOUNT.match(cleaned):
        raise TransferError(f'"{text}" isn\'t a valid amount.')
    value = Decimal(cleaned)
    if value <= 0:
        raise TransferError("The amount needs to be more than 0.")
    if -value.as_tuple().exponent > decimals:
        raise TransferError(f"That token supports at most {decimals} decimal places.")
    with localcontext(prec=100):
        return int(value.scaleb(decimals))


def format_units(amount: int, decimals: int) -> str:
    return format(Decimal(amount).scaleb(-decimals).normalize(), "f")


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


def format_usd(value: float) -> str:
    return f"${value:,.2f}"


def resolve_recipient(name_or_address: str, contacts: list[dict]) -> tuple[str, str | None]:
    query = name_or_address.strip()
    for c in contacts:
        if c.get("name", "").lower() == query.lower():
            return Web3.to_checksum_address(c["address"]), c["name"]
    if Web3.is_address(query):
        address = Web3.to_checksum_address(query)
        name = next((c["name"] for c in contacts if c.get("address", "").lower() == address.lower()), None)
        return address, name
    raise TransferError(f'I don\'t know "{query}" yet. Add them in the address book, then try again.')


def gas_units(token: Token) -> int:
    return 21_000 if token.address is None else 100_000


def validate(token: Token, amount: int, balance: int, eth_balance: int, gas_cost: int, native: str = "ETH") -> None:
    have = f"{format_units(balance, token.decimals)} {token.symbol}"
    if amount > balance:
        raise TransferError(f"You only have {have}.")
    reserve = gas_cost * FEE_HEADROOM
    if token.address is None:
        if amount + reserve > eth_balance:
            raise TransferError(
                f"That leaves too little for the network fee (keep ~{format_units(reserve, 18)} {native}). Try a slightly smaller amount."
            )
    elif reserve > eth_balance:
        raise TransferError(f"You need a little {native} for the network fee. Add funds from the wallet menu.")


def build_request(token: Token, to: str, amount: int) -> dict:
    if token.address is None:
        return {"to": to, "value": str(amount), "data": "0x"}
    calldata = ERC20_TRANSFER_SELECTOR + encode(["address", "uint256"], [to, amount]).hex()
    return {"to": token.address, "value": "0", "data": "0x" + calldata}


def display_rows(
    token: Token, amount: int, to: str, name: str | None, price: float | None, gas_cost: int, eth_price: float, network: str = "Ethereum"
) -> list[dict]:
    human = f"{format_units(amount, token.decimals)} {token.symbol}"
    if price is not None:
        human += f" ({format_usd(float(Decimal(amount).scaleb(-token.decimals)) * price)})"
    fee = float(Decimal(gas_cost).scaleb(-18)) * eth_price
    return [
        {"label": "To", "value": f"{name} ({short(to)})" if name else short(to)},
        {"label": "Amount", "value": human},
        {"label": "Network fee", "value": f"~{format_usd(fee)}"},
        {"label": "Network", "value": network},
    ]


def token_address_rows(*tokens: Token) -> list[dict]:
    """Custom tokens aren't vetted: every card that touches one shows its full contract address."""
    rows = []
    for t in dict.fromkeys(tokens):
        if t.custom:
            note = " (matched by symbol — verify)" if t.matched_by_symbol else ""
            rows.append({"label": f"{t.symbol} address", "value": f"{t.address}{note}"})
    return rows
