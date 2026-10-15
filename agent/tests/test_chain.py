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
    assert await chain.is_sandbox() is True


async def test_is_sandbox_false_when_unreachable():
    assert await RpcChain("http://127.0.0.1:1").is_sandbox() is False


async def test_call_and_block_timestamp(fork_rpc):
    chain = RpcChain(fork_rpc)
    usdc = find_token("USDC")
    decimals = await chain.call(usdc.address, "0x313ce567")  # decimals()
    assert int.from_bytes(decimals, "big") == 6
    assert await chain.block_timestamp() > 1_700_000_000


async def test_lit_price_comes_from_v4_pool(fork_rpc):
    price = await RpcChain(fork_rpc).price_usd(find_token("LIT"))
    assert 0.01 < price < 1_000


async def test_custom_token_price_comes_from_the_price_source():
    from lazyagent.tokens import Token

    coq = Token("COQ", "0x420FcA0121DC28039145009570975747295f2329", 18, custom=True)
    assert await RpcChain("http://127.0.0.1:1").price_usd(coq) is None  # no source: unknown, never $0

    async def source(token):
        return 1.5e-7 if token is coq else None

    assert await RpcChain("http://127.0.0.1:1", custom_price=source).price_usd(coq) == 1.5e-7
