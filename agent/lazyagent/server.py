import logging

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .chain import Chain, RpcChain
from .claude import connect_claude
from .config import load_settings
from .faucet import request_funds
from .session import ClientFactory, Session
from .tools import Fund


def create_app(
    chain: Chain,
    client_factory: ClientFactory,
    allowed_origins: tuple[str, ...],
    approval_timeout: float = 300,
    fund: Fund | None = None,
) -> FastAPI:
    app = FastAPI(title="LazyWallet Agent")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        if ws.headers.get("origin") not in allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        session = Session(ws.send_json, chain, client_factory, approval_timeout, fund)
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

    app = create_app(RpcChain(settings.rpc_url), factory, settings.allowed_origins, fund=fund)
    print(f"LazyWallet agent on ws://127.0.0.1:{settings.port}/ws (model {settings.model}, chain {settings.rpc_url})", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=settings.port)
