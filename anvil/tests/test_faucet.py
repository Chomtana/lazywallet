from eth_abi import encode
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from lazysandbox.faucet import balance_storage_key, create_app, fund, summarize, summarize_networks, to_word
from lazysandbox.tokens import AVAX_TOKENS, TOKENS

HOLDER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def test_balance_storage_key_is_keccak_of_abi_encoded_holder_and_slot():
    expected = Web3.keccak(encode(["address", "uint256"], [HOLDER, 9])).to_0x_hex()
    assert balance_storage_key(HOLDER, 9) == expected


def test_to_word_pads_to_32_bytes():
    assert to_word(1) == "0x" + "00" * 31 + "01"


def test_summarize_formats_whole_tokens():
    funded = {"ETH": 10 * 10**18, "USDC": 10_000 * 10**6, "WBTC": 1 * 10**8}
    assert summarize(funded) == "10 ETH, 10,000 USDC, 1 WBTC"


def test_fund_rejects_invalid_address():
    client = TestClient(create_app("http://127.0.0.1:1", ["http://localhost:5174"]))
    res = client.post("/fund", json={"address": "nope"})
    assert res.status_code == 400


async def test_fund_sets_eth_and_token_balances(fork_rpc):
    w3 = AsyncWeb3(AsyncHTTPProvider(fork_rpc))
    address = Account.create().address
    funded = await fund(w3, address)
    assert funded["ETH"] == 100 * 10**18
    assert await w3.eth.get_balance(address) == 100 * 10**18
    for t in TOKENS:
        assert funded[t.symbol] == t.faucet_amount * 10**t.decimals


def test_summarize_networks_single_network_keeps_old_format():
    assert summarize_networks([("Ethereum", {"ETH": 10**18})]) == "1 ETH"


def test_summarize_networks_groups_by_network():
    parts = [("Ethereum", {"ETH": 100 * 10**18}), ("Avalanche", {"AVAX": 100 * 10**18, "BTC.b": 10**8})]
    assert summarize_networks(parts) == "Ethereum: 100 ETH · Avalanche: 100 AVAX, 1 BTC.b"


async def test_fund_sets_avalanche_balances(avax_fork_rpc):
    w3 = AsyncWeb3(AsyncHTTPProvider(avax_fork_rpc))
    address = Account.create().address
    funded = await fund(w3, address, AVAX_TOKENS, 100, "AVAX")
    assert funded["AVAX"] == 100 * 10**18
    assert await w3.eth.get_balance(address) == 100 * 10**18
    for t in AVAX_TOKENS:
        assert funded[t.symbol] == t.faucet_amount * 10**t.decimals
