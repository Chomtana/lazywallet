from eth_abi import encode
from fakes import FakeChain, FakeSearch

from lazyagent.custom_tokens import discover, merge, pick_pool, read_token
from lazyagent.networks import AVALANCHE, ETHEREUM
from lazyagent.tokens import Token, find_token

COQ_ADDR = "0x420FcA0121DC28039145009570975747295f2329"
COQ_SAVED = {"chainId": 43114, "address": COQ_ADDR.lower(), "symbol": "COQ", "decimals": 18}

# Trimmed real GeckoTerminal response: GET /search/pools?query=COQ&network=avax&include=base_token (2026-10-15).
GT_COQ = {
    "data": [
        {"id": "avax_0x41ab86eecbd110a82ca602d032a461f453066f1e", "type": "pool",
         "attributes": {"name": "COQ / WAVAX", "reserve_in_usd": "623823.6468"},
         "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000001", "type": "pool",
         "attributes": {"name": "COQ / USDC", "reserve_in_usd": "8844.7096"},
         "relationships": {"base_token": {"data": {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000002", "type": "pool",
         "attributes": {"name": "COQAI / COQ", "reserve_in_usd": "18166.7587"},
         "relationships": {"base_token": {"data": {"id": "avax_0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "type": "token"}}}},
        {"id": "avax_0x0000000000000000000000000000000000000003", "type": "pool",
         "attributes": {"name": "TINY / WAVAX", "reserve_in_usd": "9999.99"},
         "relationships": {"base_token": {"data": {"id": "avax_0x1111111111111111111111111111111111111111", "type": "token"}}}},
    ],
    "included": [
        {"id": "avax_0x420fca0121dc28039145009570975747295f2329", "type": "token",
         "attributes": {"address": "0x420fca0121dc28039145009570975747295f2329", "name": "COQINU", "symbol": "COQ", "decimals": 18}},
        {"id": "avax_0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "type": "token",
         "attributes": {"address": "0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "name": "COQ AI", "symbol": "COQAI", "decimals": 18}},
        {"id": "avax_0x1111111111111111111111111111111111111111", "type": "token",
         "attributes": {"address": "0x1111111111111111111111111111111111111111", "name": "Tiny", "symbol": "TINY", "decimals": 18}},
    ],
}


def erc20_chain(symbol: bytes, decimals: int = 18) -> FakeChain:
    chain = FakeChain()
    chain.call_responses["0x95d89b41"] = symbol
    chain.call_responses["0x313ce567"] = encode(["uint8"], [decimals])
    return chain


def test_merge_appends_saved_tokens_for_this_chain_only():
    net = merge(AVALANCHE, [COQ_SAVED, {**COQ_SAVED, "chainId": 1, "symbol": "PEPE"}])
    coq = find_token("coq", net.tokens)
    assert coq == Token("COQ", COQ_ADDR, 18, custom=True)  # checksummed
    assert net.tokens[: len(AVALANCHE.tokens)] == AVALANCHE.tokens
    assert find_token("PEPE", net.tokens) is None
    assert merge(ETHEREUM, [COQ_SAVED]) is ETHEREUM


def test_merge_builtins_win_and_bad_entries_are_skipped():
    saved = [
        {**COQ_SAVED, "symbol": "usdc"},  # symbol clash with a built-in
        {**COQ_SAVED, "address": AVALANCHE.tokens[1].address},  # address clash
        {**COQ_SAVED, "address": "0x123"},
        {**COQ_SAVED, "decimals": "lots"},
        {"chainId": 43114},
        "junk",
        COQ_SAVED,
        {**COQ_SAVED, "address": COQ_ADDR},  # duplicate in another case
    ]
    net = merge(AVALANCHE, saved)
    assert [t.symbol for t in net.tokens[len(AVALANCHE.tokens):]] == ["COQ"]


def test_find_token_matches_contract_addresses():
    net = merge(AVALANCHE, [COQ_SAVED])
    assert find_token(COQ_ADDR.lower(), net.tokens).symbol == "COQ"
    assert find_token("0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", net.tokens).symbol == "USDC"


def test_pick_pool_takes_the_deepest_exact_symbol_match():
    assert pick_pool(GT_COQ, "coq") == ("0x420fca0121dc28039145009570975747295f2329", "COQ")
    assert pick_pool(GT_COQ, "COQAI") == ("0xe7d69acbc00d0ec5d9c02162310ee21daa77f69c", "COQAI")
    assert pick_pool(GT_COQ, "TINY") is None  # below $10,000
    assert pick_pool(GT_COQ, "CO") is None
    assert pick_pool({"data": [{"broken": True}]}, "COQ") is None
    assert pick_pool({}, "COQ") is None


async def test_read_token_string_and_bytes32_symbols():
    token = await read_token(erc20_chain(encode(["string"], ["COQ"])), COQ_ADDR.lower())
    assert token == Token("COQ", COQ_ADDR, 18, custom=True)
    mkr = await read_token(erc20_chain(b"MKR".ljust(32, b"\0")), COQ_ADDR)
    assert mkr.symbol == "MKR"


async def test_read_token_refuses_non_tokens():
    assert await read_token(FakeChain(), COQ_ADDR) is None  # empty symbol (FakeChain answers zero bytes)
    eoa = FakeChain()
    eoa.call_responses["0x95d89b41"] = b""
    eoa.call_responses["0x313ce567"] = b""
    assert await read_token(eoa, COQ_ADDR) is None
    assert await read_token(erc20_chain(encode(["string"], ["X" * 40])), COQ_ADDR) is None


async def test_discover_by_address_reads_the_fork():
    chain = erc20_chain(encode(["string"], ["COQ"]))
    search = FakeSearch(GT_COQ)
    token = await discover(f" {COQ_ADDR} ", AVALANCHE, chain, search)
    assert token == Token("COQ", COQ_ADDR, 18, custom=True)
    assert search.calls == []


async def test_discover_by_symbol_marks_the_match():
    chain = erc20_chain(encode(["string"], ["COQ"]))
    search = FakeSearch(GT_COQ)
    token = await discover("coq", AVALANCHE, chain, search)
    assert token == Token("COQ", COQ_ADDR, 18, custom=True, matched_by_symbol=True)
    assert search.calls == [("avalanche", "coq")]
    assert await discover("TINY", AVALANCHE, chain, search) is None
    assert await discover("coq", AVALANCHE, chain, None) is None


async def test_discover_survives_a_failing_search():
    class Down:
        async def pools(self, network, query):
            raise ConnectionError("rate limited")

    assert await discover("coq", AVALANCHE, erc20_chain(encode(["string"], ["COQ"])), Down()) is None


FAKE_USDC = "0x1111111111111111111111111111111111111111"


def test_merge_drops_saved_tokens_posing_as_a_builtin():
    fake = {"chainId": 43114, "address": FAKE_USDC, "symbol": "USDC", "decimals": 6}
    net = merge(AVALANCHE, [fake, COQ_SAVED])
    assert [t.symbol for t in net.tokens[len(AVALANCHE.tokens):]] == ["COQ"]
    assert find_token("USDC", net.tokens) == find_token("USDC", AVALANCHE.tokens)  # the real one


async def test_discover_refuses_a_token_posing_as_a_builtin():
    import pytest

    from lazyagent.transfers import TransferError

    for symbol in ("USDC", "usdc"):
        with pytest.raises(TransferError, match=f"calls itself {symbol} but isn't the real {symbol} on Avalanche"):
            await discover(FAKE_USDC, AVALANCHE, erc20_chain(encode(["string"], [symbol])), None)
