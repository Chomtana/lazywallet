from eth_account import Account

from lazysandbox.dexalot import NATIVE, DexalotSandbox, avalanche_w3

USDC = "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"
RFQ_ABI = [
    {"name": "swapSigner", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {
        "name": "simpleSwap", "type": "function", "stateMutability": "payable", "outputs": [],
        "inputs": [
            {"name": "_order", "type": "tuple", "components": [
                {"name": n, "type": t} for n, t in [
                    ("nonceAndMeta", "uint256"), ("expiry", "uint128"), ("makerAsset", "address"), ("takerAsset", "address"),
                    ("maker", "address"), ("taker", "address"), ("makerAmount", "uint256"), ("takerAmount", "uint256"),
                ]
            ]},
            {"name": "_signature", "type": "bytes"},
        ],
    },
]
BALANCE_OF = [{"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]}]


async def test_setup_patches_every_maker(avax_fork_rpc):
    w3 = avalanche_w3(avax_fork_rpc)
    d = DexalotSandbox(w3)
    await d.setup()
    assert d.error is None and len(d.makers) >= 1
    for m in d.makers:
        assert await w3.eth.contract(address=m, abi=RFQ_ABI).functions.swapSigner().call() == d.signer.address


async def _swap_one_avax(w3, d):
    user = Account.create()
    await w3.provider.make_request("anvil_setBalance", [user.address, hex(10 * 10**18)])
    q = await d.quote(NATIVE, USDC, 10**18, user.address)
    o = q["order"]
    order = (int(o["nonceAndMeta"]), int(o["expiry"]), o["makerAsset"], o["takerAsset"], o["maker"], o["taker"], int(o["makerAmount"]), int(o["takerAmount"]))
    rfq = w3.eth.contract(address=q["maker"], abi=RFQ_ABI)
    tx = await rfq.functions.simpleSwap(order, bytes.fromhex(q["signature"][2:])).build_transaction(
        {"from": user.address, "value": 10**18, "nonce": await w3.eth.get_transaction_count(user.address)}
    )
    receipt = await w3.eth.wait_for_transaction_receipt(await w3.eth.send_raw_transaction(user.sign_transaction(tx).raw_transaction))
    assert receipt["status"] == 1
    usdc = w3.eth.contract(address=USDC, abi=BALANCE_OF)
    assert await usdc.functions.balanceOf(user.address).call() == int(o["makerAmount"])


async def test_sandbox_signed_quote_executes(avax_fork_rpc):
    w3 = avalanche_w3(avax_fork_rpc)
    d = DexalotSandbox(w3)
    await d.setup()
    await _swap_one_avax(w3, d)


async def test_quote_after_idle_executes(avax_fork_rpc):
    """Anvil mines only on transactions: after idle time the next block is far past `latest`."""
    w3 = avalanche_w3(avax_fork_rpc)
    d = DexalotSandbox(w3)
    await d.setup()
    await w3.provider.make_request("evm_increaseTime", [1000])  # no mine
    await _swap_one_avax(w3, d)
