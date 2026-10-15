from lazyagent.chain import RpcChain
from lazyagent.tokens import find_token
from lazyagent.uniswap import ZERO, ChainQuoter, Hop, Route, best_route, currency_of

USDC = currency_of(find_token("USDC"))
DAI = currency_of(find_token("DAI"))


async def test_quotes_eth_usdc_on_fork(fork_rpc):
    quoter = ChainQuoter(RpcChain(fork_rpc))
    out = await quoter.quote(Route((ZERO, USDC), (Hop(500, 10),)), 10**18)
    assert out is not None and out > 500 * 10**6


async def test_missing_pool_quotes_none(fork_rpc):
    quoter = ChainQuoter(RpcChain(fork_rpc))
    # verified: no hookless ETH/DAI pool at 0.01%
    assert await quoter.quote(Route((ZERO, DAI), (Hop(100, 1),)), 10**18) is None


async def test_best_route_on_fork(fork_rpc):
    found = await best_route(ChainQuoter(RpcChain(fork_rpc)), ZERO, USDC, 10**18)
    assert found is not None
    route, out = found
    assert route.currencies == (ZERO, USDC)
    assert out > 500 * 10**6
