import re
import subprocess
import time

import pytest
from web3 import HTTPProvider, Web3

from lazysandbox.rpc import ROOT
from lazysandbox.scheduler import SCHEDULER, SWAPPER, deploy_command, ensure_scheduler

PORT = 8661


@pytest.fixture
def bare_anvil():
    proc = subprocess.Popen(["anvil", "--port", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{PORT}"
    w3 = Web3(HTTPProvider(url))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            w3.eth.chain_id
            break
        except Exception:
            time.sleep(0.2)
    try:
        yield url
    finally:
        proc.terminate()
        proc.wait()


def test_deploy_command_broadcasts_the_deploy_script():
    cmd = deploy_command("http://x")
    assert cmd[:3] == ["forge", "script", "script/Deploy.s.sol:Deploy"]
    assert "--broadcast" in cmd and cmd[cmd.index("--rpc-url") + 1] == "http://x"


def test_ensure_scheduler_deploys_once_at_the_pinned_address(bare_anvil):
    w3 = Web3(HTTPProvider(bare_anvil))
    assert ensure_scheduler(bare_anvil) is True
    assert w3.eth.get_code(SCHEDULER) and w3.eth.get_code(SWAPPER)
    assert ensure_scheduler(bare_anvil) is False  # idempotent across sandbox restarts


def test_pinned_addresses_match_deployment_sol():
    sol = (ROOT / "contracts/src/Deployment.sol").read_text()
    assert re.search(r"SCHEDULER = (0x[0-9a-fA-F]{40})", sol).group(1) == SCHEDULER
    assert re.search(r"SWAPPER = (0x[0-9a-fA-F]{40})", sol).group(1) == SWAPPER
