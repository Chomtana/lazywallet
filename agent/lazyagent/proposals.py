import asyncio
import secrets


class Proposals:
    """Transfers waiting for the user's Approve/Reject in the browser."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future] = {}

    def new(self) -> tuple[str, asyncio.Future]:
        # Random, not sequential: the browser keeps cards from earlier sessions across reconnects.
        pid = f"p{secrets.token_hex(8)}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[pid] = fut
        return pid, fut

    def resolve(self, pid: str, result: dict) -> bool:
        fut = self._pending.get(pid)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        return True

    async def wait(self, pid: str, fut: asyncio.Future, timeout: float) -> dict | None:
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except TimeoutError:
            return None
        finally:
            self._pending.pop(pid, None)

    def cancel_all(self) -> None:
        for fut in self._pending.values():
            fut.cancel()
        self._pending.clear()
