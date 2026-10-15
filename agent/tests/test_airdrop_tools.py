import json

from fakes import FakeChain, FakeGeckoPools, FakeLlama, Outbox

from lazyagent.airdrops import AIRDROPS_TOOL, Airdrops
from lazyagent.proposals import Proposals
from lazyagent.tools import WalletContext, WalletTools

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
