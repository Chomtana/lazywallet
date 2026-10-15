import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

from .chain import Chain
from .proposals import Proposals
from .stream import translate
from .tools import Fund, Send, WalletContext, WalletTools

log = logging.getLogger(__name__)
BUSY = "Still working on your last request."


class AgentClient(Protocol):
    async def query(self, prompt: str) -> None: ...
    def receive_response(self) -> Any: ...
    async def disconnect(self) -> None: ...


ClientFactory = Callable[[WalletTools], Awaitable[AgentClient]]


class Session:
    """One browser connection: wallet context, pending approvals and a lazily created Claude client."""

    def __init__(
        self,
        send: Send,
        chain: Chain,
        client_factory: ClientFactory,
        approval_timeout: float = 300,
        fund: Fund | None = None,
    ):
        self._send = send
        self._factory = client_factory
        self.ctx = WalletContext()
        self.proposals = Proposals()
        self.tools = WalletTools(chain, send, self.ctx, self.proposals, approval_timeout, fund)
        self._client: AgentClient | None = None
        self._turn: asyncio.Task | None = None

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "user":
            if self._turn and not self._turn.done():
                await self._send({"type": "error", "message": BUSY})
                return
            self.ctx.address = msg.get("address")
            self.ctx.contacts = list(msg.get("contacts") or [])
            self._turn = asyncio.create_task(self._run(str(msg.get("text", ""))))
        elif kind == "tx_result":
            self.proposals.resolve(str(msg.get("id", "")), msg)
        else:
            await self._send({"type": "error", "message": f"Unknown message type: {kind}"})

    async def _run(self, text: str) -> None:
        try:
            if self._client is None:
                self._client = await self._factory(self.tools)
            await self._client.query(text)
            async for m in self._client.receive_response():
                for out in translate(m):
                    await self._send(out)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("agent turn failed")
            await self._send({"type": "error", "message": f"Agent error: {e}"})
        await self._send({"type": "turn_end"})

    async def close(self) -> None:
        self.proposals.cancel_all()
        if self._turn and not self._turn.done():
            self._turn.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._turn
        if self._client is not None:
            with suppress(Exception):
                await self._client.disconnect()
