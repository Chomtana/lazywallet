from eth_abi import encode
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from .tokens import AVAX_FAUCET_AMOUNT, AVAX_TOKENS, ETH_FAUCET_AMOUNT, TOKENS

ERC20_BALANCE_OF = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]
DECIMALS = {"ETH": 18, "AVAX": 18, **{t.symbol: t.decimals for t in TOKENS + AVAX_TOKENS}}


def balance_storage_key(holder: str, slot: int) -> str:
    """Storage key of balances[holder] for a Solidity mapping declared at `slot`."""
    return Web3.keccak(encode(["address", "uint256"], [holder, slot])).to_0x_hex()


def to_word(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


async def _rpc(w3: AsyncWeb3, method: str, params: list) -> None:
    res = await w3.provider.make_request(method, params)
    if "error" in res:
        raise RuntimeError(f"{method} failed: {res['error']}")


async def fund(w3: AsyncWeb3, address: str, tokens=TOKENS, native_amount: int = ETH_FAUCET_AMOUNT, native: str = "ETH") -> dict[str, int]:
    holder = Web3.to_checksum_address(address)
    amount_native = native_amount * 10**18
    await _rpc(w3, "anvil_setBalance", [holder, hex(amount_native)])
    funded = {native: amount_native}
    for t in tokens:
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


def summarize_networks(parts: list[tuple[str, dict[str, int]]]) -> str:
    if len(parts) == 1:
        return summarize(parts[0][1])
    return " · ".join(f"{name}: {summarize(funded)}" for name, funded in parts)


class FundRequest(BaseModel):
    address: str


def create_app(rpc_url: str, allowed_origins: list[str], avax_rpc_url: str | None = None) -> FastAPI:
    app = FastAPI(title="LazyWallet Sandbox Faucet")
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    avax_w3 = AsyncWeb3(AsyncHTTPProvider(avax_rpc_url)) if avax_rpc_url else None

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/fund")
    async def post_fund(req: FundRequest) -> dict:
        if not Web3.is_address(req.address):
            raise HTTPException(status_code=400, detail="Invalid address")
        try:
            parts = [("Ethereum", await fund(w3, req.address))]
            if avax_w3:
                parts.append(("Avalanche", await fund(avax_w3, req.address, AVAX_TOKENS, AVAX_FAUCET_AMOUNT, "AVAX")))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox chain error: {e}") from e
        return {"funded": {name: {k: str(v) for k, v in f.items()} for name, f in parts}, "summary": summarize_networks(parts)}

    return app
