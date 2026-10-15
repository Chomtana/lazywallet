import asyncio
import json

from eth_abi import decode, encode
from fakes import FakeChain, FakeGeckoPools, FakeKyber, FakeLlama, FakeQuoter, Outbox

from lazyagent.airdrops import AIRDROPS_TOOL, DEPOSIT_TOOL, Airdrops
from lazyagent.kyber import ROUTER
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools
from lazyagent.uniswap import PERMIT2, UNIVERSAL_ROUTER, Hop

ME = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def text(result):
    return result["content"][0]["text"]


# --- list_airdrops ---


def list_tools(airdrops: Airdrops, address: str | None = ME):
    out = Outbox()
    tools = WalletTools(FakeChain(), out, WalletContext(address=address), Proposals())
    tools.airdrops = airdrops
    return tools, out


async def test_list_airdrops_sends_a_card_and_asks_for_one_sentence():
    tools, out = list_tools(Airdrops(FakeLlama({"theo-network-thusd": {"currentChainTvls": {"Ethereum": 132e6}}}), FakeGeckoPools()))
    result = await tools.list_airdrops({"category": "rwa"})
    assert not result.get("is_error")
    [msg] = out.of_type("airdrops")
    assert msg["title"] == "RWA airdrops"
    assert [i["id"] for i in msg["items"]] == ["theo-thusd", "re"]
    assert "ONE short sentence" in text(result)
    data = json.loads(text(result).split("Data: ", 1)[1])
    assert data["airdrops"][0]["executable"] is True and data["airdrops"][0]["tvl_usd"] == 132e6


async def test_list_airdrops_works_without_a_wallet_and_rejects_bad_args():
    tools, out = list_tools(Airdrops(FakeLlama(), FakeGeckoPools()), address=None)
    assert not (await tools.list_airdrops({})).get("is_error")
    assert out.of_type("airdrops")[0]["title"] == "Airdrops"
    bad = await tools.list_airdrops({"category": "nft"})
    assert bad["is_error"] is True and text(bad) == "category must be one of: rwa, other, all."
    assert len(out.of_type("airdrops")) == 1


def test_list_tool_schema():
    assert AIRDROPS_TOOL[0] == "list_airdrops" and AIRDROPS_TOOL[2]["properties"]["category"]["enum"] == ["rwa", "other", "all"]


# --- propose_deposit ---

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
THUSD = "0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3"
STHUSD = "0xA808Bc9775cb41c52C7842f8b50427fE7A770326"
QUOTE_100 = 100_037_000  # 100 USDC → 100.037 thUSD (fork, 2026-10-15)
MINIMUM_100 = QUOTE_100 * 99 // 100  # 1% slippage
SHARES = 97_200_000
STEPS = ["Allow USDC", "Allow Uniswap router", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD"]


def theo_pool(route, amount_in):
    """Only the pinned USDC/thUSD 0.01% pool; 1 USDC = 1.00037 thUSD."""
    if route.hops != (Hop(100, 1),) or route.currencies != (USDC, THUSD):
        return None
    return amount_in * 100_037 // 100_000


def vault_chain(**tokens) -> FakeChain:
    chain = FakeChain(tokens={"USDC": 500 * 10**6, **tokens})
    chain.call_responses["0x38d52e0f"] = encode(["address"], [THUSD])  # asset()
    chain.call_responses["0x402d267d"] = encode(["uint256"], [2**256 - 1])  # maxDeposit(user)
    chain.call_responses["0xef8b30f7"] = encode(["uint256"], [SHARES])  # previewDeposit(assets)
    return chain


def make(chain=None, quote=theo_pool, kyber=None):
    out = Outbox()
    proposals = Proposals()
    chain = chain or vault_chain()
    tools = WalletTools(chain, out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(quote), kyber=kyber)
    return tools, out, proposals, chain


def rows_of(confirm):
    return {r["label"]: r["value"] for r in confirm["tx"]["rows"]}


async def confirm_of(out):
    for _ in range(200):
        if out.of_type("confirm"):
            return out.of_type("confirm")[0]
        await asyncio.sleep(0)
    raise AssertionError("no confirm")


def test_deposit_tool_schema():
    assert DEPOSIT_TOOL[0] == "propose_deposit" and DEPOSIT_TOOL[2]["required"] == ["farm", "amount"]


async def test_farm_theo_builds_every_step_and_stakes_the_minimum():
    tools, out, proposals, chain = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    tx = confirm["tx"]
    assert tx["title"] == "Farm Theo points: 100 USDC → sthUSD"
    assert [s["label"] for s in tx["steps"]] == STEPS
    assert [s["request"]["to"] for s in tx["steps"]] == [USDC, PERMIT2, UNIVERSAL_ROUTER, THUSD, STHUSD]
    assert all(s["request"]["chainId"] == 1 for s in tx["steps"])
    stake = tx["steps"][-1]["request"]["data"]
    assert stake.startswith("0x6e553f65")
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:])) == (MINIMUM_100, ME.lower())
    allow = tx["steps"][3]["request"]["data"]
    assert decode(["address", "uint256"], bytes.fromhex(allow[10:])) == (STHUSD.lower(), MINIMUM_100)
    rows = rows_of(confirm)
    assert rows["Swap"] == "USDC → thUSD · Uniswap v4 0.01%"
    assert rows["Expected"] == "≈ 100.037 thUSD"
    assert rows["Stake"] == "99.0366 thUSD → ≈ 97.2 sthUSD"
    assert rows["Left in wallet"] == "≈ 1.00037 thUSD"
    assert rows["Program"] == "Theo thUSD Points — Theo points — no token announced"
    assert rows["Points"] == "Only count on real mainnet. This Sandbox is a demo and earns nothing."
    assert rows["thUSD address"] == THUSD and rows["sthUSD address"] == STHUSD
    assert rows["Network"] == "Ethereum (Sandbox)"
    assert tx["addTokens"] == [
        {"chainId": 1, "address": THUSD, "symbol": "thUSD", "decimals": 6},
        {"chainId": 1, "address": STHUSD, "symbol": "sthUSD", "decimals": 6},
    ]
    chain.tokens.update(USDC=400 * 10**6, thUSD=QUOTE_100 - MINIMUM_100, sthUSD=SHARES)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xd"})
    result = text(await task)
    assert "Staked 99.0366 thUSD into sthUSD, got 97.2 sthUSD; 1.00037 thUSD left. Confirmed on Ethereum (Sandbox), tx 0xd." in result
    assert "Points only count on real mainnet" in result
    assert " Balance change (shown as a card): " in result
    [change] = out.of_type("balance_change")
    assert [c["symbol"] for c in change["changes"]] == ["USDC", "thUSD", "sthUSD"]
    assert [c["delta"] for c in change["changes"]] == [-100.0, (QUOTE_100 - MINIMUM_100) / 1e6, 97.2]
    assert {c["network"] for c in change["changes"]} == {"Ethereum"}


async def test_farm_balance_change_survives_an_unknown_share_price():
    chain = vault_chain()
    chain.prices["sthUSD"] = None
    priced = []
    price_usd = chain.price_usd

    async def recording(token):
        priced.append(token)
        return await price_usd(token)

    chain.price_usd = recording
    tools, out, proposals, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    chain.tokens.update(USDC=400 * 10**6, thUSD=QUOTE_100 - MINIMUM_100, sthUSD=SHARES)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xd"})
    assert "Balance change (shown as a card): " in text(await task)
    [change] = out.of_type("balance_change")
    assert [c["symbol"] for c in change["changes"]] == ["USDC", "thUSD", "sthUSD"]
    assert change["changes"][2]["usdPrice"] is None and change["changes"][2]["delta"] == 97.2
    # thUSD/sthUSD are custom tokens, so RpcChain.price_usd routes them to the custom price source
    farm = {t.symbol: t for t in priced if t.symbol in ("thUSD", "sthUSD")}
    assert farm["thUSD"].custom and farm["sthUSD"].custom
    assert (farm["thUSD"].address, farm["sthUSD"].address) == (THUSD, STHUSD)


async def test_farm_by_short_name_skips_allowances_that_already_cover_it():
    chain = vault_chain()
    chain.call_responses["0xdd62ed3e"] = encode(["uint256"], [10**30])  # USDC→Permit2 and thUSD→vault
    chain.call_responses["0x927da105"] = encode(["uint160", "uint48", "uint48"], [10**30, chain.now + 3600, 0])
    tools, out, _, _ = make(chain=chain)
    task = asyncio.create_task(tools.propose_deposit({"farm": "Theo", "amount": "100"}))
    assert [s["label"] for s in (await confirm_of(out))["tx"]["steps"]] == ["Swap USDC → thUSD", "Stake thUSD → sthUSD"]
    task.cancel()


async def test_without_a_v4_quote_kyber_buys_the_thusd_with_its_checks():
    chain = vault_chain()
    chain.sim_out = QUOTE_100
    chain.access_keys, chain.allowance_slot = ["0x09"], "0x09"
    kyber = FakeKyber(out=QUOTE_100)
    tools, out, _, _ = make(chain=chain, quote=lambda route, amount: None, kyber=kyber)
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    assert [s["label"] for s in confirm["tx"]["steps"]] == ["Allow USDC", "Swap USDC → thUSD", "Allow thUSD", "Stake thUSD → sthUSD"]
    assert confirm["tx"]["steps"][1]["request"]["to"] == ROUTER
    assert kyber.routes == [("ethereum", USDC, THUSD, 100 * 10**6)]
    assert kyber.builds == [("ethereum", ME, 100)]  # 1% — not the Sandbox's 50% default
    assert rows_of(confirm)["Swap"] == "USDC → thUSD · KyberSwap via LFJ"
    stake = confirm["tx"]["steps"][-1]["request"]["data"]
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:]))[0] == MINIMUM_100
    task.cancel()


async def test_deposit_refusals_send_no_card():
    wrong_asset = vault_chain()
    wrong_asset.call_responses["0x38d52e0f"] = encode(["address"], [USDC])
    full = vault_chain()
    full.call_responses["0x402d267d"] = encode(["uint256"], [10**6])
    broke = vault_chain()
    broke.eth = 0

    def huge_impact(route, amount_in):
        q = theo_pool(route, amount_in)
        return q // 2 if q and amount_in >= 10**8 else q

    cases = [
        ({"farm": "nope", "amount": "10"}, {}, "Call list_airdrops"),
        ({"farm": "re", "amount": "10"}, {}, "can list Re Points Season 2 but can't farm it from here yet"),
        ({"farm": "theo-thusd", "amount": "0"}, {}, "more than 0"),
        ({"farm": "theo-thusd", "amount": "1000"}, {}, "You only have 500 USDC."),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": wrong_asset}, "Theo's vault isn't accepting deposits right now."),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": full}, "Theo's vault isn't accepting deposits right now."),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": huge_impact}, "move the price"),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": lambda r, a: None}, "couldn't get a quote"),
        ({"farm": "theo-thusd", "amount": "100"}, {"quote": lambda r, a: None, "kyber": FakeKyber(no_route=True)}, "no route"),
        ({"farm": "theo-thusd", "amount": "100"}, {"chain": broke}, "network fees"),
    ]
    for args, kwargs, fragment in cases:
        tools, out, _, _ = make(**kwargs)
        result = await tools.propose_deposit(args)
        assert result.get("is_error") is True, args
        assert fragment in text(result), (args, text(result))
        assert not out.of_type("confirm")


async def test_deposit_needs_a_wallet():
    tools, _, _, _ = make()
    tools.ctx.address = None
    assert text(await tools.propose_deposit({"farm": "theo-thusd", "amount": "1"})) == "No wallet is active in the app."


async def test_reverted_stake_names_the_step():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "reverted", "hash": "0xr", "failed_step": 4})
    result = text(await task)
    assert result.startswith(
        "The deposit reverted at step 5 (Stake thUSD → sthUSD) (tx 0xr). The swap went through, so your thUSD is in your "
        "wallet but wasn't staked. Don't swap again; ask the user whether to try staking later."
    )
    assert "1% slippage" not in result and "harmless" not in result
    assert " Balance change (shown as a card): " in result
    assert len(out.of_type("balance_change")) == 1


async def test_unsent_approval_after_the_swap_says_the_token_is_unstaked():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "error": "user denied", "failed_step": 3})
    result = text(await task)
    assert result.startswith("The deposit failed before it was sent at step 4 (Allow thUSD): user denied. The swap went through")
    assert len(out.of_type("balance_change")) == 1


async def test_reverted_swap_keeps_the_slippage_hint():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "reverted", "hash": "0xr", "failed_step": 2})
    result = text(await task)
    assert "The deposit reverted at step 3 (Swap USDC → thUSD)" in result
    assert "1% slippage" in result and "unstaked" not in result and "wasn't staked" not in result
    assert not out.of_type("balance_change")


async def test_unreadable_confirmation_after_the_swap_still_says_dont_resend():
    tools, out, proposals, _ = make()
    task = asyncio.create_task(tools.propose_deposit({"farm": "theo-thusd", "amount": "100"}))
    confirm = await confirm_of(out)
    proposals.resolve(confirm["id"], {"outcome": "approved", "error": "timeout", "hash": "0xh", "failed_step": 4})
    assert "Don't resend" in text(await task)
    assert not out.of_type("balance_change")


async def test_a_reverting_preview_reads_as_a_closed_vault():
    chain = vault_chain()
    call = chain.call

    async def reverting(to, data, gas=None):
        if data.startswith("0xef8b30f7"):
            raise ValueError("execution reverted")
        return await call(to, data, gas)

    chain.call = reverting
    tools, out, _, _ = make(chain=chain)
    result = await tools.propose_deposit({"farm": "theo-thusd", "amount": "100"})
    assert text(result) == "Theo's vault isn't accepting deposits right now."
    assert not out.of_type("confirm")


# --- Avant: KyberSwap only, on Avalanche ---

AVAX_USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
AVUSD = "0x24dE8771bC5DdB3362Db529Fc3358F2df3A0E346"
SAVUSD = "0x06d47F3fb376649c3A9Dafe069B3D6E35572219E"
AVUSD_100 = 100_005 * 10**15  # 100 USDC → 100.005 avUSD (KyberSwap via Pharaoh, 2026-10-15)
AVUSD_MIN = AVUSD_100 * 99 // 100


def avant_chain() -> FakeChain:
    chain = FakeChain(tokens={"USDC": 500 * 10**6})
    chain.call_responses["0x38d52e0f"] = encode(["address"], [AVUSD])  # asset()
    chain.call_responses["0x402d267d"] = encode(["uint256"], [2**256 - 1])  # maxDeposit(user)
    chain.call_responses["0xef8b30f7"] = encode(["uint256"], [82 * 10**18])  # previewDeposit(assets)
    chain.sim_out = AVUSD_100
    chain.access_keys, chain.allowance_slot = ["0x0a"], "0x0a"
    return chain


def no_v4(route, amount_in):
    raise AssertionError("Avant must not quote Uniswap v4")


async def test_farm_avant_swaps_on_kyberswap_and_stakes_on_its_own_network():
    avax, kyber, out, proposals = avant_chain(), FakeKyber(out=AVUSD_100), Outbox(), Proposals()
    tools = WalletTools(FakeChain(), out, WalletContext(address=ME), proposals, approval_timeout=5, quoter=FakeQuoter(no_v4), avalanche=avax, kyber=kyber)
    task = asyncio.create_task(tools.propose_deposit({"farm": "Avant", "amount": "100"}))
    confirm = await confirm_of(out)
    tx = confirm["tx"]
    assert tx["title"] == "Farm Avant points: 100 USDC → savUSD"
    assert [s["label"] for s in tx["steps"]] == ["Allow USDC", "Swap USDC → avUSD", "Allow avUSD", "Stake avUSD → savUSD"]
    assert [s["request"]["to"] for s in tx["steps"]] == [AVAX_USDC, ROUTER, AVUSD, SAVUSD]
    assert all(s["request"]["chainId"] == 43114 for s in tx["steps"])
    assert kyber.routes == [("avalanche", AVAX_USDC, AVUSD, 100 * 10**6)] and kyber.builds == [("avalanche", ME, 100)]
    stake = tx["steps"][-1]["request"]["data"]
    assert decode(["uint256", "address"], bytes.fromhex(stake[10:])) == (AVUSD_MIN, ME.lower())
    rows = rows_of(confirm)
    assert rows["Swap"] == "USDC → avUSD · KyberSwap via LFJ"
    assert rows["Points"] == "Only count on real mainnet. This Sandbox is a demo and earns nothing."
    assert rows["Network"] == "Avalanche (Sandbox)"
    assert tx["addTokens"] == [
        {"chainId": 43114, "address": AVUSD, "symbol": "avUSD", "decimals": 18},
        {"chainId": 43114, "address": SAVUSD, "symbol": "savUSD", "decimals": 18},
    ]
    avax.tokens.update(USDC=400 * 10**6, avUSD=AVUSD_100 - AVUSD_MIN, savUSD=82 * 10**18)
    proposals.resolve(confirm["id"], {"outcome": "approved", "status": "success", "hash": "0xa"})
    assert "Staked 99.0049 avUSD into savUSD, got 82 savUSD; 1.00005 avUSD left. Confirmed on Avalanche (Sandbox), tx 0xa." in text(await task)
    [change] = out.of_type("balance_change")
    assert [c["symbol"] for c in change["changes"]] == ["USDC", "avUSD", "savUSD"]
    assert {c["network"] for c in change["changes"]} == {"Avalanche"}
    assert [c["delta"] for c in change["changes"]] == [-100.0, 1.00005, 82.0]


async def test_avant_needs_the_avalanche_sandbox():
    tools = WalletTools(FakeChain(tokens={"USDC": 500 * 10**6}), Outbox(), WalletContext(address=ME), Proposals(), kyber=FakeKyber())
    assert text(await tools.propose_deposit({"farm": "avant", "amount": "10"})) == "Avant farming isn't set up on this Sandbox."
