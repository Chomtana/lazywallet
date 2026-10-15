import asyncio

import pytest

from lazyagent.proposals import Proposals


async def test_resolve_delivers_result():
    p = Proposals()
    pid, fut = p.new()
    asyncio.get_running_loop().call_soon(p.resolve, pid, {"outcome": "approved"})
    assert await p.wait(pid, fut, 1) == {"outcome": "approved"}


async def test_ids_are_unique_across_sessions():
    # The browser keeps old cards across reconnects; a new session must never reuse their ids.
    assert Proposals().new()[0] != Proposals().new()[0]


async def test_wait_times_out_with_none():
    p = Proposals()
    pid, fut = p.new()
    assert await p.wait(pid, fut, 0.01) is None
    assert p.resolve(pid, {"outcome": "approved"}) is False


async def test_unknown_id_is_ignored():
    assert Proposals().resolve("p9", {}) is False


async def test_cancel_all_cancels_waiters():
    p = Proposals()
    pid, fut = p.new()
    task = asyncio.create_task(p.wait(pid, fut, 5))
    await asyncio.sleep(0)
    p.cancel_all()
    with pytest.raises(asyncio.CancelledError):
        await task
