from eth_abi import decode, encode
from web3 import Web3

from lazyagent.uniswap import (
    PERMIT2,
    QUOTE_GAS,
    UNIVERSAL_ROUTER,
    ZERO,
    ChainQuoter,
    Hop,
    Route,
    best_route,
    candidate_routes,
    currency_of,
    decode_permit2_allowance,
    decode_quote,
    encode_erc20_allowance,
    encode_erc20_approve,
    encode_permit2_allowance,
    encode_permit2_approve,
    encode_quote,
    encode_swap,
    encode_weth_withdraw,
    pool_id,
    pool_key,
    symbol_of,
)
from lazyagent.tokens import ETH, find_token

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WBTC = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
OWNER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def test_currency_and_symbol():
    assert currency_of(ETH) == ZERO
    assert currency_of(find_token("USDC")) == USDC
    assert symbol_of(ZERO) == "ETH"
    assert symbol_of(USDC.lower()) == "USDC"


def test_pool_key_sorts_currencies_and_pool_id_matches_mainnet():
    key = pool_key(USDC, ZERO, Hop(500, 10))
    assert key == (ZERO, USDC, 500, 10, ZERO)
    # ETH/USDC 0.05% v4 pool id, verified on mainnet via StateView
    assert pool_id(key) == "0x21c67e77068de97969ba93d4aab21826d33ca12bb9f565d8496e8fda8a82ca27"


def test_single_hop_swap_calldata_matches_verified_recipe():
    data = encode_swap(Route((ZERO, USDC), (Hop(500, 10),)), 10**18, 2_330_000_000, 1_800_000_000)
    assert data.startswith("0x3593564c")
    assert Web3.keccak(hexstr=data).hex() == "76d036534e7538c2ebebf5ffa072b9caa74bc8c5139be272e1542b86b8846d2c"


def test_two_hop_swap_calldata_matches_verified_recipe():
    route = Route((USDC, ZERO, WBTC), (Hop(500, 10), Hop(500, 10)))
    data = encode_swap(route, 500 * 10**6, 6_000_000, 1_800_000_000)
    assert Web3.keccak(hexstr=data).hex() == "6be1ace07a64225f8104b8da301b66330840f16f561ccf57b31b10f2befcf15d"


def test_quote_calldata_selectors():
    assert encode_quote(Route((ZERO, USDC), (Hop(500, 10),)), 10**18)[:10] == "0x" + Web3.keccak(
        text="quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))"
    )[:4].hex()
    assert encode_quote(Route((USDC, ZERO, WBTC), (Hop(500, 10), Hop(500, 10))), 10**6)[:10] == "0x" + Web3.keccak(
        text="quoteExactInput((address,(address,uint24,int24,address,bytes)[],uint128))"
    )[:4].hex()
    assert decode_quote(encode(["uint256", "uint256"], [123, 456])) == 123


def test_approval_and_weth_encoders():
    approve = encode_erc20_approve(PERMIT2, 5)
    assert approve[:10] == "0x095ea7b3"
    spender, amount = decode(["address", "uint256"], bytes.fromhex(approve[10:]))
    assert (spender.lower(), amount) == (PERMIT2.lower(), 5)
    p2 = encode_permit2_approve(USDC, UNIVERSAL_ROUTER, 7, 1_700_000_000)
    assert p2[:10] == "0x87517c45"
    token, spender, amount, expiration = decode(["address", "address", "uint160", "uint48"], bytes.fromhex(p2[10:]))
    assert (token.lower(), spender.lower(), amount, expiration) == (USDC.lower(), UNIVERSAL_ROUTER.lower(), 7, 1_700_000_000)
    assert encode_erc20_allowance(OWNER, PERMIT2)[:10] == "0xdd62ed3e"
    assert encode_permit2_allowance(OWNER, USDC, UNIVERSAL_ROUTER)[:10] == "0x927da105"
    assert decode_permit2_allowance(encode(["uint160", "uint48", "uint48"], [9, 1_700_000_000, 0])) == (9, 1_700_000_000)
    assert encode_weth_withdraw(3)[:10] == "0x2e1a7d4d"


def test_candidate_routes():
    direct = candidate_routes(ZERO, USDC)
    assert len(direct) == 4
    assert all(r.currencies == (ZERO, USDC) for r in direct)
    via_eth = candidate_routes(USDC, WBTC)
    assert len(via_eth) == 4 + 16
    assert via_eth[-1].currencies == (USDC, ZERO, WBTC)


class TableQuoter:
    def __init__(self, table):
        self.table = table

    async def quote(self, route, amount_in):
        return self.table.get(route.hops)


async def test_best_route_picks_highest_output_and_handles_no_liquidity():
    q = TableQuoter({(Hop(500, 10),): 2358, (Hop(3000, 60),): 2356})
    route, out = await best_route(q, ZERO, USDC, 10**18)
    assert route.hops == (Hop(500, 10),) and out == 2358
    assert await best_route(TableQuoter({}), ZERO, USDC, 10**18) is None


class RecordingChain:
    def __init__(self):
        self.calls = []

    async def call(self, to, data, gas=None):
        self.calls.append(gas)
        return encode(["uint256", "uint256"], [42, 0])


async def test_chain_quoter_caps_gas_so_empty_pools_cannot_sweep_the_tick_range():
    chain = RecordingChain()
    assert await ChainQuoter(chain).quote(Route((ZERO, USDC), (Hop(500, 10),)), 10**18) == 42
    assert chain.calls == [QUOTE_GAS] and QUOTE_GAS == 1_000_000


def test_encode_swap_wrap_output_takes_to_router_then_wraps_to_caller():
    from lazyagent.uniswap import CONTRACT_BALANCE, TAKE, V4_SWAP, WRAP_ETH

    usdc = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    route = Route((usdc, ZERO), (Hop(500, 10),))
    data = encode_swap(route, 10**6, 123, 999, wrap_output=True)
    commands, inputs, deadline = decode(["bytes", "bytes[]", "uint256"], bytes.fromhex(data[10:]))
    assert commands == bytes([V4_SWAP, WRAP_ETH]) and deadline == 999
    actions, params = decode(["bytes", "bytes[]"], inputs[0])
    assert actions[-1] == TAKE
    taken = decode(["address", "address", "uint256"], params[2])
    assert (taken[0].lower(), taken[1].lower(), taken[2]) == (ZERO, "0x0000000000000000000000000000000000000002", 0)
    wrapped = decode(["address", "uint256"], inputs[1])
    assert (wrapped[0].lower(), wrapped[1]) == ("0x0000000000000000000000000000000000000001", CONTRACT_BALANCE)
    # default output is unchanged (matches the verified recipe tests above)
    assert encode_swap(route, 10**6, 123, 999) == encode_swap(route, 10**6, 123, 999, wrap_output=False)
