import logging

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .chain import Chain, RpcChain
from .claude import connect_claude
from .config import load_settings
from .custom_tokens import GeckoSearch, Search
from .dexalot import Quotes, SandboxQuotes
from .faucet import request_funds
from .kyber import Kyber, KyberClient, usd_price
from .networks import AVALANCHE, ETHEREUM
from .session import ClientFactory, Session
from .tools import Fund
from .tts import MAX_CHARS, ElevenLabsTts, Tts, TtsUnavailable


class TtsRequest(BaseModel):
    text: str


def create_app(
    chain: Chain,
    client_factory: ClientFactory,
    allowed_origins: tuple[str, ...],
    approval_timeout: float = 300,
    fund: Fund | None = None,
    avalanche: Chain | None = None,
    dexalot: Quotes | None = None,
    kyber: Kyber | None = None,
    search: Search | None = None,
    tts: Tts | None = None,
) -> FastAPI:
    app = FastAPI(title="LazyWallet Agent")
    app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins), allow_methods=["POST"], allow_headers=["content-type"])

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.post("/tts")
    async def tts_endpoint(body: TtsRequest, request: Request):
        if request.headers.get("origin") not in allowed_origins:
            return JSONResponse({"error": "Origin not allowed."}, status_code=403)
        text = body.text.strip()[:MAX_CHARS]
        if not text:
            return JSONResponse({"error": "No text."}, status_code=400)
        if tts is None:
            return JSONResponse({"error": "Text-to-speech is not configured."}, status_code=503)
        try:
            audio = await tts.stream(text)
        except TtsUnavailable as e:
            return JSONResponse({"error": f"Text-to-speech unavailable: {e}"}, status_code=503)
        return StreamingResponse(audio, media_type="audio/mpeg")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        if ws.headers.get("origin") not in allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        session = Session(ws.send_json, chain, client_factory, approval_timeout, fund, avalanche=avalanche, dexalot=dexalot, kyber=kyber, search=search)
        try:
            while True:
                try:
                    msg = await ws.receive_json()
                except ValueError:
                    await ws.send_json({"type": "error", "message": "Invalid message."})
                    continue
                await session.handle(msg)
        except WebSocketDisconnect:
            pass
        finally:
            await session.close()

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    async def factory(tools):
        return await connect_claude(tools, settings)

    async def fund(address: str) -> str:
        return await request_funds(settings.faucet_url, address)

    kyber = KyberClient()
    app = create_app(
        RpcChain(settings.rpc_url, custom_price=usd_price(kyber, ETHEREUM)),
        factory,
        settings.allowed_origins,
        fund=fund,
        avalanche=RpcChain(settings.avax_rpc_url, poa=True, custom_price=usd_price(kyber, AVALANCHE)),
        dexalot=SandboxQuotes(settings.faucet_url),
        kyber=kyber,
        search=GeckoSearch(),
        tts=ElevenLabsTts(),
    )
    print(
        f"LazyWallet agent on ws://127.0.0.1:{settings.port}/ws (model {settings.model}, "
        f"Ethereum {settings.rpc_url}, Avalanche {settings.avax_rpc_url})",
        flush=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=settings.port)
