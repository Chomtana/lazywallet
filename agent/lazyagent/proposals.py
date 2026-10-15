import asyncio
import secrets

EXECUTION_TIMEOUT_S = 600  # once the user taps Approve, wait for the browser's steps to finish


class Proposals:
    """Transfers waiting for the user's Approve/Reject in the browser."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future] = {}
        self._started: set[str] = set()

    def new(self) -> tuple[str, asyncio.Future]:
        # Random, not sequential: the browser keeps cards from earlier sessions across reconnects.
        pid = f"p{secrets.token_hex(8)}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[pid] = fut
        return pid, fut

    def start(self, pid: str) -> None:
        """The user tapped Approve: the browser is now sending, so don't report a timeout."""
        if pid in self._pending:
            self._started.add(pid)

    def resolve(self, pid: str, result: dict) -> bool:
        fut = self._pending.get(pid)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        return True

    async def wait(self, pid: str, fut: asyncio.Future, timeout: float, execution_timeout: float = EXECUTION_TIMEOUT_S) -> dict | None:
        try:
            try:
                return await asyncio.wait_for(asyncio.shield(fut), timeout)
            except TimeoutError:
                if pid not in self._started:
                    return None
            return await asyncio.wait_for(asyncio.shield(fut), execution_timeout)
        except TimeoutError:
            return None
        finally:
            self._pending.pop(pid, None)
            self._started.discard(pid)

    def cancel_all(self) -> None:
        for fut in self._pending.values():
            fut.cancel()
        self._pending.clear()
        self._started.clear()
