import pytest

from lazyagent.swaps import (
    GAS,
    Step,
    approval_steps,
    check_swap_funds,
    display_units,
    erc20_approval,
    fee_text,
    gas_reserve,
    impact_warning,
    min_out,
    parse_slippage,
    price_impact,
    route_label,
    swap_rows,
    swap_summary,
)
from lazyagent.tokens import ETH, find_token
from lazyagent.transfers import TransferError
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, ZERO, Hop, Route

USDC = find_token("USDC")
USDT = find_token("USDT")
WBTC = find_token("WBTC")
NOW = 1_700_000_000


@pytest.mark.parametrize(("text", "bps"), [(None, 100), ("", 100), ("0.5", 50), ("1%", 100), (" 5 ", 500), ("0.01", 1)])
def test_parse_slippage(text, bps):
    assert parse_slippage(text) == bps


@pytest.mark.parametrize("text", ["0", "5.5", "10", "-1", "abc", "0.005", "nan"])
def test_parse_slippage_rejects(text):
    with pytest.raises(TransferError):
        parse_slippage(text)


def test_min_out_rounds_down():
    assert min_out(1_000_000, 100) == 990_000
    assert min_out(999, 100) == 989


def test_price_impact():
    assert price_impact(1000, 2_000_000, 1, 2000) == 0.0
    assert price_impact(1000, 1_000_000, 1, 2000) == pytest.approx(0.5)
    assert price_impact(1000, 2_100_000, 1, 2000) == 0.0  # better than reference → 0
    assert price_impact(1000, 5, 1, 0) == 0.0


def test_display_units():
    assert display_units(2_358_835_338, 6) == "2358.83"
    assert display_units(423_670_123_456_789_012, 18) == "0.42367"
    assert display_units(10_000 * 10**6, 6) == "10000"
    assert display_units(0, 18) == "0"


def test_route_label():
    usdc = USDC.address
    wbtc = WBTC.address
    assert route_label(Route((ZERO, usdc), (Hop(500, 10),))) == "ETH → USDC · Uniswap v4 0.05%"
    assert route_label(Route((usdc, ZERO, wbtc), (Hop(500, 10), Hop(3000, 60)))) == "USDC → ETH → WBTC · Uniswap v4 0.05% / 0.3%"


def labels(steps):
    return [s.label for s in steps]


def test_approval_steps_none_when_already_allowed():
    assert approval_steps(USDC, 10**6, 10**6, NOW + 600, 10**6, NOW) == []


def test_approval_steps_both_when_nothing_allowed():
    steps = approval_steps(USDC, 0, 0, 0, 5 * 10**6, NOW)
    assert labels(steps) == ["Allow USDC", "Allow Uniswap router"]
    assert steps[0].request["to"] == USDC.address
    assert steps[1].request["to"] == PERMIT2
    assert UNIVERSAL_ROUTER.lower()[2:] in steps[1].request["data"]


def test_approval_steps_reapprove_expired_permit2():
    assert labels(approval_steps(USDC, 10**6, 10**6, NOW + 30, 10**6, NOW)) == ["Allow Uniswap router"]


def test_approval_steps_usdt_resets_nonzero_allowance():
    steps = approval_steps(USDT, 5, 0, 0, 10**6, NOW)
    assert labels(steps) == ["Reset USDT allowance", "Allow USDT", "Allow Uniswap router"]
    assert steps[0].request["data"].endswith("0" * 64)


def test_gas_reserve_and_funds():
    steps = [Step("a", {}, GAS["approve"]), Step("s", {}, GAS["swap1"])]
    assert gas_reserve(steps, 10**9) == (60_000 + 170_000) * 10**9 * 2
    check_swap_funds(ETH, 10**18, 2 * 10**18, 2 * 10**18, 10**15)
    with pytest.raises(TransferError, match="only have"):
        check_swap_funds(USDC, 2 * 10**6, 10**6, 10**18, 10**15)
    with pytest.raises(TransferError, match="network fees"):
        check_swap_funds(ETH, 10**18, 10**18, 10**18, 10**15)
    with pytest.raises(TransferError, match="network fees"):
        check_swap_funds(USDC, 10**6, 10**6, 10**14, 10**15)


def test_swap_rows_are_only_the_details():
    rows = swap_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "ETH → USDC · Uniswap v4 0.05%", 0.0012)
    assert rows == [
        {"label": "From", "value": "0xf39F…2266"},
        {"label": "Route", "value": "ETH → USDC · Uniswap v4 0.05%"},
        {"label": "Price impact", "value": "0.12%"},
    ]
    assert swap_rows("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "Dexalot", None)[-1] == {"label": "Price impact", "value": "unknown"}


def test_fee_text():
    assert fee_text(1.234) == "≈ $1.23"
    assert fee_text(0.004) == "< $0.01"


def test_impact_warning_only_above_five_percent():
    assert impact_warning(None) is None
    assert impact_warning(0.05) is None
    assert impact_warning(0.072) == "Price impact 7.2%"


def test_swap_summary():
    summary = swap_summary("Ethereum", ETH, USDC, 10**18, 2_358_835_338, via="Uniswap v4", fee_usd=1.234, impact=0.0012, prices=(3200.0, 1.0))
    assert summary == {
        "kind": "swap",
        "network": "Ethereum",
        "pay": {"symbol": "ETH", "amount": "1", "usd": 3200.0, "logo": ETH.logo},
        "receive": {"symbol": "USDC", "amount": "≈ 2358.83", "usd": 2358.84, "logo": USDC.logo, "note": None},
        "via": "Uniswap v4",
        "fee": "≈ $1.23",
        "warning": None,
    }


def test_swap_summary_exact_output_unknown_prices_and_a_warning():
    summary = swap_summary("Avalanche", USDC, WBTC, 10**6, 1_500, via="Dexalot", fee_usd=0.01, impact=0.08, prices=(None, None), exact=True)
    assert summary["pay"]["usd"] is None and summary["receive"]["usd"] is None
    assert summary["receive"]["amount"] == "0.000015"
    assert summary["warning"] == "Price impact 8.0%"


def test_erc20_approval_for_any_spender():
    spender = "0x6131B5fae19EA4f9D964eAc0408E4408b66337b5"
    assert erc20_approval(USDC, 10**6, 10**6, spender) == []
    [step] = erc20_approval(USDC, 0, 10**6, spender)
    assert step.label == "Allow USDC" and step.request["to"] == USDC.address
    assert step.request["data"].startswith("0x095ea7b3") and spender[2:].lower() in step.request["data"]
    assert [s.label for s in erc20_approval(USDT, 5, 10**6, spender)] == ["Reset USDT allowance", "Allow USDT"]

