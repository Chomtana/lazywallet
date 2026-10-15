from eth_abi import encode
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from .tokens import ETH_FAUCET_AMOUNT, TOKENS

ERC20_BALANCE_OF = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]
DECIMALS = {"ETH": 18, **{t.symbol: t.decimals for t in TOKENS}}


def balance_storage_key(holder: str, slot: int) -> str:
    """Storage key of balances[holder] for a Solidity mapping declared at `slot`."""
    return Web3.keccak(encode(["address", "uint256"], [holder, slot])).to_0x_hex()


def to_word(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


async def _rpc(w3: AsyncWeb3, method: str, params: list) -> None:
    res = await w3.provider.make_request(method, params)
    if "error" in res:
        raise RuntimeError(f"{method} failed: {res['error']}")


async def fund(w3: AsyncWeb3, address: str) -> dict[str, int]:
    holder = Web3.to_checksum_address(address)
    eth = ETH_FAUCET_AMOUNT * 10**18
    await _rpc(w3, "anvil_setBalance", [holder, hex(eth)])
    funded = {"ETH": eth}
    for t in TOKENS:
        amount = t.faucet_amount * 10**t.decimals
        await _rpc(w3, "anvil_setStorageAt", [t.address, balance_storage_key(holder, t.balance_slot), to_word(amount)])
        contract = w3.eth.contract(address=Web3.to_checksum_address(t.address), abi=ERC20_BALANCE_OF)
        actual = await contract.functions.balanceOf(holder).call()
        if actual != amount:
            raise RuntimeError(f"{t.symbol} balance slot {t.balance_slot} is wrong: balanceOf={actual}, expected {amount}")
        funded[t.symbol] = amount
    return funded


def summarize(funded: dict[str, int]) -> str:
    return ", ".join(f"{amount // 10 ** DECIMALS[symbol]:,} {symbol}" for symbol, amount in funded.items())


class FundRequest(BaseModel):
    address: str


def create_app(rpc_url: str, allowed_origins: list[str]) -> FastAPI:
    app = FastAPI(title="LazyWallet Sandbox Faucet")
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/fund")
    async def post_fund(req: FundRequest) -> dict:
        if not Web3.is_address(req.address):
            raise HTTPException(status_code=400, detail="Invalid address")
        try:
            funded = await fund(w3, req.address)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox chain error: {e}") from e
        return {"funded": {k: str(v) for k, v in funded.items()}, "summary": summarize(funded)}

    return app
