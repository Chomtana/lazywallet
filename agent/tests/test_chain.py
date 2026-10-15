from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from lazyagent.chain import RpcChain
from lazyagent.tokens import ETH, find_token


async def test_balances_prices_and_gas(fork_rpc):
    chain = RpcChain(fork_rpc)
    address = Account.create().address
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    await w3.provider.make_request("anvil_setBalance", [address, hex(3 * 10**18)])

    assert await chain.eth_balance(address) == 3 * 10**18
    assert await chain.token_balance(find_token("USDC"), address) == 0
    assert 100 < await chain.price_usd(ETH) < 100_000
    assert 1_000 < await chain.price_usd(find_token("WBTC")) < 1_000_000
    assert await chain.price_usd(find_token("DAI")) == 1.0
    assert await chain.gas_price() > 0
