import os
import subprocess
import time
import urllib.request

import pytest
from web3 import HTTPProvider, Web3

from lazyagent.config import ROOT

TEST_PORT = 8646
AVAX_TEST_PORT = 8649
SANDBOX_TEST_PORT = 8650
AVAX_PUBLIC_RPC = "https://api.avax.network/ext/bc/C/rpc"
DEV_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def deploy_scheduler(rpc: str) -> None:
    """Idempotent CREATE2 deploy of contracts/ onto a test fork (same as `pnpm dev:sandbox` does)."""
    from lazyagent.scheduler import SCHEDULER

    if Web3(HTTPProvider(rpc)).eth.get_code(SCHEDULER):
        return
    cmd = ["forge", "script", "script/Deploy.s.sol:Deploy", "--rpc-url", rpc, "--broadcast", "--private-key", DEV_KEY]
    subprocess.run(cmd, cwd=ROOT / "contracts", check=True, capture_output=True)


def _wait(check, what: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{what} did not start")


def _anvil(url: str, port: int, chain_id: int, block: str | None = None):
    cmd = ["anvil", "--fork-url", url, "--chain-id", str(chain_id), "--port", str(port)]
    if block:
        cmd += ["--fork-block-number", block]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpc = f"http://127.0.0.1:{port}"
    try:
        _wait(lambda: Web3(HTTPProvider(rpc)).eth.chain_id == chain_id, "test fork")
        yield rpc
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="session")
def fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ.get("ETH_RPC_URL")
    if not url:
        pytest.skip("ETH_RPC_URL not set")
    yield from _anvil(url, TEST_PORT, 1, os.environ.get("FORK_BLOCK") or None)


@pytest.fixture(scope="session")
def avax_fork_rpc():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    yield from _anvil(os.environ.get("AVAX_RPC_URL") or AVAX_PUBLIC_RPC, AVAX_TEST_PORT, 43114)


@pytest.fixture(scope="session")
def avax_sandbox(avax_fork_rpc):
    """The real sandbox service (anvil/) pointed at the Avalanche test fork, for end-to-end Dexalot swaps."""
    code = (
        "import uvicorn; from lazysandbox.faucet import create_app; "
        f"uvicorn.run(create_app('http://127.0.0.1:1', ['http://localhost:5174'], '{avax_fork_rpc}'), "
        f"host='127.0.0.1', port={SANDBOX_TEST_PORT}, log_level='warning')"
    )
    proc = subprocess.Popen(["uv", "run", "--directory", str(ROOT / "anvil"), "python", "-c", code])
    url = f"http://127.0.0.1:{SANDBOX_TEST_PORT}"
    try:
        # Startup (incl. the signer patch) finishes before the server answers /health.
        _wait(lambda: urllib.request.urlopen(f"{url}/health", timeout=2).status == 200, "sandbox service", 180)
        yield avax_fork_rpc, url
    finally:
        proc.terminate()
        proc.wait()
