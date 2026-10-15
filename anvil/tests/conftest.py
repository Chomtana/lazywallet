import os
import subprocess

import pytest

from lazysandbox.rpc import AVAX_CHAIN_ID, AVAX_PUBLIC_RPC, anvil_command, load_env, wait_for_rpc

TEST_PORT = 8645
AVAX_TEST_PORT = 8648


def _fork(cmd: list[str], rpc: str, chain_id: int):
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_rpc(rpc, 120, chain_id)
        yield rpc
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="session")
def fork_rpc():
    load_env()
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    cmd = anvil_command(url, os.environ.get("FORK_BLOCK") or None, TEST_PORT)
    yield from _fork(cmd, f"http://127.0.0.1:{TEST_PORT}", 1)


@pytest.fixture(scope="session")
def avax_fork_rpc():
    load_env()
    url = os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC
    cmd = anvil_command(url, None, AVAX_TEST_PORT, AVAX_CHAIN_ID)
    yield from _fork(cmd, f"http://127.0.0.1:{AVAX_TEST_PORT}", AVAX_CHAIN_ID)
