from lazyagent.networks import AVALANCHE, ETHEREUM, NETWORKS, Choice, candidates, find_network, pick_network


def test_registry():
    assert [n.key for n in NETWORKS] == ["ethereum", "avalanche"]
    assert (ETHEREUM.chain_id, AVALANCHE.chain_id) == (1, 43114)
    assert AVALANCHE.native.symbol == "AVAX" and AVALANCHE.swap_venue == "dexalot"
    assert ETHEREUM.label == "Ethereum (Sandbox)"


def test_find_network_aliases():
    assert find_network("Avalanche") is AVALANCHE
    assert find_network(" avax ") is AVALANCHE
    assert find_network("eth") is ETHEREUM
    assert find_network("solana") is None
    assert find_network(None) is None


def test_candidates_need_every_symbol():
    assert candidates(["ETH"], NETWORKS) == [ETHEREUM]
    assert candidates(["avax", "usdc"], NETWORKS) == [AVALANCHE]
    assert candidates(["USDC"], NETWORKS) == [ETHEREUM, AVALANCHE]
    assert candidates(["USDC", "LIT"], NETWORKS) == [ETHEREUM]
    assert candidates(["DOGE"], NETWORKS) == []
    assert candidates(["USDC"], [ETHEREUM]) == [ETHEREUM]


def test_pick_network():
    both = [ETHEREUM, AVALANCHE]
    assert pick_network([AVALANCHE], {}) is AVALANCHE
    assert pick_network(both, {"ethereum": False, "avalanche": True}) is AVALANCHE
    assert pick_network(both, {"ethereum": True, "avalanche": True}) == Choice((ETHEREUM, AVALANCHE))
    assert pick_network(both, {"ethereum": False, "avalanche": False}) == Choice((ETHEREUM, AVALANCHE))
