import os
import subprocess

import pytest

from lazysandbox.rpc import anvil_command, load_env, wait_for_rpc

TEST_PORT = 8645


@pytest.fixture(scope="session")
def fork_rpc():
    load_env()
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    proc = subprocess.Popen(
        anvil_command(url, os.environ.get("FORK_BLOCK") or None, TEST_PORT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc = f"http://127.0.0.1:{TEST_PORT}"
    try:
        wait_for_rpc(rpc, 120)
        yield rpc
    finally:
        proc.terminate()
        proc.wait()
