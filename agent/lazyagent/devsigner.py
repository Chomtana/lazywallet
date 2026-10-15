"""Sign and send confirm-card steps with a local key — for the demo script and fork tests only.
In the app, the browser does this with viem after the user taps Approve."""

from eth_account import Account
from web3 import AsyncWeb3, Web3

GAS_MARGIN = 1.2


async def execute_steps(w3: AsyncWeb3, private_key: str, steps: list[dict]) -> dict:
    account = Account.from_key(private_key)
    chain_id = await w3.eth.chain_id
    hashes: list[str] = []
    for i, step in enumerate(steps):
        req = step["request"]
        tx = {
            "from": account.address,
            "to": Web3.to_checksum_address(req["to"]),
            "value": int(req["value"]),
            "data": req["data"],
            "chainId": chain_id,
            "nonce": await w3.eth.get_transaction_count(account.address),
            "gasPrice": await w3.eth.gas_price,
        }
        try:
            tx["gas"] = int(await w3.eth.estimate_gas(tx) * GAS_MARGIN)
            tx_hash = await w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction)
        except Exception as e:
            return {"outcome": "approved", "hashes": hashes, "error": str(e), "failed_step": i}
        hashes.append(tx_hash.to_0x_hex())
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            return {"outcome": "approved", "hashes": hashes, "hash": hashes[-1], "status": "reverted", "failed_step": i}
    return {"outcome": "approved", "hashes": hashes, "hash": hashes[-1] if hashes else None, "status": "success"}
