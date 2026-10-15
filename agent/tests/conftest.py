import os
import subprocess
import time

import pytest
from web3 import HTTPProvider, Web3

from lazyagent.config import ROOT

TEST_PORT = 8646


@pytest.fixture(scope="session")
def fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    cmd = ["anvil", "--fork-url", url, "--chain-id", "1", "--port", str(TEST_PORT)]
    if os.environ.get("FORK_BLOCK"):
        cmd += ["--fork-block-number", os.environ["FORK_BLOCK"]]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = f"http://127.0.0.1:{TEST_PORT}"
    w3 = Web3(HTTPProvider(rpc))
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                if w3.eth.chain_id == 1:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise TimeoutError("test fork did not start")
        yield rpc
    finally:
        proc.terminate()
        proc.wait()
