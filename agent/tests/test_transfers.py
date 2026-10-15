import pytest

from lazyagent.tokens import ETH, find_token
from lazyagent.transfers import (
    TransferError,
    build_request,
    display_rows,
    format_units,
    parse_amount,
    resolve_recipient,
    validate,
)

USDC = find_token("usdc")
ALICE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
CONTACTS = [{"name": "Alice", "address": ALICE}]


@pytest.mark.parametrize(
    ("text", "decimals", "expected"),
    [("0.1", 18, 10**17), (".5", 18, 5 * 10**17), ("1,000", 6, 10**9), ("  2 ", 8, 2 * 10**8), ("1.5", 6, 1_500_000)],
)
def test_parse_amount_valid(text, decimals, expected):
    assert parse_amount(text, decimals) == expected


@pytest.mark.parametrize("text", ["0", "0.000", "-1", "1e18", "abc", "", "1.2.3", "0,5", "1,5", "12,34", "٣"])
def test_parse_amount_invalid(text):
    with pytest.raises(TransferError):
        parse_amount(text, 18)


def test_parse_amount_thousands_separators():
    assert parse_amount("1,000,000.5", 6) == 1_000_000_500_000


def test_parse_amount_never_rounds_long_inputs():
    with pytest.raises(TransferError, match="18 decimal places"):
        parse_amount("0.1000000000000000000000000000001", 18)


def test_parse_amount_too_many_decimals():
    with pytest.raises(TransferError, match="6 decimal places"):
        parse_amount("0.0000001", 6)


def test_format_units():
    assert format_units(10 * 10**18, 18) == "10"
    assert format_units(1_500_000, 6) == "1.5"
    assert format_units(0, 18) == "0"


def test_resolve_recipient_by_name_case_insensitive():
    assert resolve_recipient("alice", CONTACTS) == (ALICE, "Alice")


def test_resolve_recipient_by_address_checksums():
    assert resolve_recipient(ALICE.lower(), CONTACTS) == (ALICE, "Alice")
    other = "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc"
    assert resolve_recipient(other, []) == ("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", None)


def test_resolve_recipient_unknown():
    with pytest.raises(TransferError, match="address book"):
        resolve_recipient("charlie", CONTACTS)


def test_validate_eth_over_balance():
    with pytest.raises(TransferError, match="only have 1 ETH"):
        validate(ETH, 2 * 10**18, 10**18, 10**18, 21_000 * 10**9)


def test_validate_eth_whole_balance_leaves_no_gas():
    with pytest.raises(TransferError, match="network fee"):
        validate(ETH, 10**18, 10**18, 10**18, 21_000 * 10**9)


def test_validate_eth_keeps_headroom_for_fee_spikes():
    gas = 21_000 * 10**9
    with pytest.raises(TransferError, match="network fee"):
        validate(ETH, 10**18 - gas, 10**18, 10**18, gas)


def test_validate_token_over_balance():
    with pytest.raises(TransferError, match="only have 5 USDC"):
        validate(USDC, 6 * 10**6, 5 * 10**6, 10**18, 10**14)


def test_validate_token_needs_eth_for_gas():
    with pytest.raises(TransferError, match="ETH for the network fee"):
        validate(USDC, 10**6, 5 * 10**6, 0, 10**14)


def test_validate_ok():
    validate(ETH, 10**17, 10**18, 10**18, 21_000 * 10**9)
    validate(USDC, 10**6, 5 * 10**6, 10**18, 10**14)


def test_build_request_eth():
    assert build_request(ETH, ALICE, 10**17) == {"to": ALICE, "value": str(10**17), "data": "0x"}


def test_build_request_erc20_transfer_calldata():
    req = build_request(USDC, ALICE, 1_500_000)
    assert req["to"] == USDC.address
    assert req["value"] == "0"
    assert req["data"] == (
        "0xa9059cbb"
        + "00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8"
        + "000000000000000000000000000000000000000000000000000000000016e360"
    )


def test_display_rows():
    rows = display_rows(ETH, 10**17, ALICE, "Alice", 3200.0, 21_000 * 10**9, 3200.0)
    assert rows == [
        {"label": "To", "value": "Alice (0x7099…79C8)"},
        {"label": "Amount", "value": "0.1 ETH ($320.00)"},
        {"label": "Network fee", "value": "~$0.07"},
        {"label": "Network", "value": "Sandbox"},
    ]
