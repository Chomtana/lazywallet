from lazyagent.chain import RpcChain
from lazyagent.tokens import AVAX, AVAX_TOKENS, find_token


async def test_avalanche_prices_blocks_and_calls(avax_fork_rpc):
    chain = RpcChain(avax_fork_rpc, poa=True)
    assert 1 < await chain.price_usd(AVAX) < 10_000
    assert 1_000 < await chain.price_usd(find_token("BTC.b", AVAX_TOKENS)) < 1_000_000
    assert 100 < await chain.price_usd(find_token("WETH.e", AVAX_TOKENS)) < 100_000
    assert await chain.block_timestamp() > 1_700_000_000
    assert await chain.is_sandbox() is True
    usdc = find_token("USDC", AVAX_TOKENS)
    assert int.from_bytes(await chain.call(usdc.address, "0x313ce567"), "big") == 6
